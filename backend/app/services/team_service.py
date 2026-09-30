from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from datetime import date, datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
from zoneinfo import ZoneInfo

from app.models.work_session import WorkSession, WorkStatus
from app.models.activity_interval import ActivityInterval
from app.models.group_member import GroupMember
from app.models.status_transition import StatusTransition
from app.models.user import User
from app.models.widget_group import WidgetGroup
from app.models.crm_event import CrmEvent
from app.models.call_event import CallEvent
from app.core.access_policy import AccessPolicy, RequestContext
from app.core.business_time import (
    business_date,
    local_date_range_utc_bounds,
    local_period_utc_bounds,
    local_shift_utc_bounds,
    shift_start_utc,
)
from app.core.time_utils import utc_now
from app.schemas.team import (
    ActivityWindowDay,
    ActivityWindowGroup,
    ActivityWindowInterval,
    ActivityWindowResponse,
    ActivityWindowTarget,
    ActivityWindowTotals,
    TeamGroupSummary,
    TeamMemberSummary,
    TeamStatusResponse,
    TeamStatusTotals,
    TeamViewer,
)


class ActivityRangeError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class TeamService:
    """Service for team monitoring"""

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _utc(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @staticmethod
    def _workday(
        group: WidgetGroup | None, now: datetime
    ) -> tuple[str, datetime, datetime]:
        if group is None:
            day = now.date()
            start = datetime.combine(day, datetime.min.time())
            return "UTC", start, start + timedelta(days=1)
        day = business_date(
            now, group.timezone, group.work_start_time, group.work_end_time
        )
        start = shift_start_utc(day, group.timezone, group.work_start_time)
        end_day = day + timedelta(days=group.work_end_time <= group.work_start_time)
        end = (
            datetime.combine(end_day, group.work_end_time, ZoneInfo(group.timezone))
            .astimezone(timezone.utc)
            .replace(tzinfo=None)
        )
        return group.timezone, start, end

    @staticmethod
    def _session_seconds(
        session: WorkSession,
        transitions: list[StatusTransition],
        *,
        day_start: datetime,
        day_end: datetime,
        now: datetime,
    ) -> tuple[int, int]:
        """Reconstruct clamped work/break spans from the lifecycle journal."""

        totals = {WorkStatus.WORKING.value: 0, WorkStatus.BREAK.value: 0}

        def add_span(start: datetime, end: datetime, state: str) -> None:
            if state not in totals:
                return
            clipped_start = max(start, day_start)
            clipped_end = min(end, day_end, now)
            totals[state] += max(0, int((clipped_end - clipped_start).total_seconds()))

        cursor = session.start_time
        if transitions:
            state = WorkStatus.WORKING.value
            for transition in transitions:
                boundary = transition.timestamp
                if boundary >= cursor:
                    add_span(cursor, boundary, state)
                    cursor = boundary
                state = transition.to_status
        elif session.current_status == WorkStatus.BREAK:
            state = WorkStatus.BREAK.value
        else:
            # Legacy sessions without journal rows started in WORKING. A closed
            # FINISHED row therefore represents work through its end time.
            state = WorkStatus.WORKING.value

        segment_end = session.end_time or now
        add_span(cursor, segment_end, state)
        return totals[WorkStatus.WORKING.value], totals[WorkStatus.BREAK.value]

    @staticmethod
    def _merged_seconds(ranges: list[tuple[datetime, datetime]]) -> int:
        merged: list[list[datetime]] = []
        for start, end in sorted(ranges):
            if end <= start:
                continue
            if not merged or start > merged[-1][1]:
                merged.append([start, end])
            else:
                merged[-1][1] = max(merged[-1][1], end)
        return sum(int((end - start).total_seconds()) for start, end in merged)

    def get_activity_window(
        self,
        context: RequestContext,
        target_user_id: int,
        from_date: date,
        to_date: date,
    ) -> ActivityWindowResponse:
        """Return one bounded, account-scoped activity window in group-local dates."""
        row = (
            self.db.query(User, GroupMember, WidgetGroup)
            .outerjoin(
                GroupMember,
                (GroupMember.account_id == User.amocrm_account_id)
                & (GroupMember.user_id == User.id)
                & (GroupMember.is_active.is_(True)),
            )
            .outerjoin(
                WidgetGroup,
                (WidgetGroup.account_id == GroupMember.account_id)
                & (WidgetGroup.id == GroupMember.group_id)
                & (WidgetGroup.is_active.is_(True)),
            )
            .filter(
                User.id == target_user_id,
                User.amocrm_account_id == context.account_id,
                User.is_active.is_(True),
            )
            .one_or_none()
        )
        if row is None:
            raise LookupError("target not found")
        target, membership, group = row
        if not AccessPolicy(self.db, context).can_view_activity_detail(target):
            raise LookupError("target not found")
        if to_date < from_date:
            raise ActivityRangeError(
                "ACTIVITY_RANGE_INVALID",
                "Дата окончания должна быть не раньше даты начала.",
            )
        day_count = (to_date - from_date).days + 1
        if day_count > 7:
            raise ActivityRangeError(
                "ACTIVITY_RANGE_TOO_LARGE",
                "Можно выбрать не больше 7 календарных дней.",
            )

        zone_name = group.timezone if group is not None else "UTC"
        utc_start, utc_end = local_date_range_utc_bounds(from_date, to_date, zone_name)
        intervals = (
            self.db.query(ActivityInterval)
            .filter(
                ActivityInterval.account_id == context.account_id,
                ActivityInterval.user_id == target.id,
                ActivityInterval.started_at < utc_end,
                ActivityInterval.ended_at >= utc_start,
            )
            .order_by(
                ActivityInterval.started_at,
                ActivityInterval.ended_at,
                ActivityInterval.id,
            )
            .all()
        )
        # Non-point intervals that merely touch the lower boundary do not
        # overlap the half-open request window. Points at the lower bound do.
        intervals = [
            item
            for item in intervals
            if item.started_at == item.ended_at or item.ended_at > utc_start
        ]

        crm_rows = []
        call_rows = []
        if intervals:
            if any(item.source == "crm_event" for item in intervals):
                crm_rows = (
                    self.db.query(
                        CrmEvent.id,
                        CrmEvent.event_type,
                        CrmEvent.object_type,
                        CrmEvent.object_id,
                        CrmEvent.occurred_at,
                        CrmEvent.card_url,
                    )
                    .filter(
                        CrmEvent.account_id == context.account_id,
                        CrmEvent.user_id == target.id,
                        CrmEvent.is_complete == 1,
                        CrmEvent.occurred_at >= utc_start,
                        CrmEvent.occurred_at < utc_end,
                    )
                    .all()
                )
            if any(item.source == "call" for item in intervals):
                call_rows = (
                    self.db.query(
                        CallEvent.id,
                        CallEvent.object_type,
                        CallEvent.object_id,
                        CallEvent.occurred_at,
                        CallEvent.card_url,
                        CallEvent.direction,
                        CallEvent.duration_seconds,
                    )
                    .filter(
                        CallEvent.account_id == context.account_id,
                        CallEvent.user_id == target.id,
                        CallEvent.is_complete == 1,
                        CallEvent.occurred_at >= utc_start,
                        CallEvent.occurred_at < utc_end,
                    )
                    .all()
                )

        def crm_evidence(interval):
            matches = [
                item
                for item in crm_rows
                if item.event_type == interval.event_type
                and item.object_type == interval.object_type
                and item.object_id == interval.object_id
                and interval.started_at <= item.occurred_at <= interval.ended_at
            ]
            return matches[0] if len(matches) == 1 else None

        def call_evidence(interval):
            matches = [
                item
                for item in call_rows
                if item.object_type == interval.object_type
                and item.object_id == interval.object_id
                and interval.started_at <= item.occurred_at <= interval.ended_at
                and item.duration_seconds
                == int((interval.ended_at - interval.started_at).total_seconds())
                and item.direction in {"incoming", "outgoing"}
            ]
            return matches[0] if len(matches) == 1 else None

        crm_by_interval = {
            item.id: crm_evidence(item)
            for item in intervals
            if item.source == "crm_event"
        }
        calls_by_interval = {
            item.id: call_evidence(item) for item in intervals if item.source == "call"
        }
        days: list[ActivityWindowDay] = []
        total_confirmed_ranges: list[tuple[datetime, datetime]] = []
        total_unconfirmed_ranges: list[tuple[datetime, datetime]] = []
        confirmed_ids: set[int] = set()
        for offset in range(day_count):
            local_day = from_date + timedelta(days=offset)
            day_start, day_end = local_period_utc_bounds(local_day, zone_name)
            if group is None:
                shift_start, shift_end = day_start, day_end
            else:
                shift_start, shift_end = local_shift_utc_bounds(
                    local_day,
                    zone_name,
                    group.work_start_time,
                    group.work_end_time,
                )
            dto_intervals: list[ActivityWindowInterval] = []
            confirmed_ranges: list[tuple[datetime, datetime]] = []
            unconfirmed_ranges: list[tuple[datetime, datetime]] = []
            day_confirmed_ids: set[int] = set()
            for interval in intervals:
                is_point = interval.started_at == interval.ended_at
                if is_point:
                    if not day_start <= interval.started_at < day_end:
                        continue
                    segment_start = segment_end = interval.started_at
                else:
                    segment_start = max(interval.started_at, day_start, utc_start)
                    segment_end = min(interval.ended_at, day_end, utc_end)
                    if segment_end <= segment_start:
                        continue
                if interval.kind == "confirmed":
                    day_confirmed_ids.add(interval.id)
                    confirmed_ids.add(interval.id)
                    if segment_end > segment_start:
                        confirmed_ranges.append((segment_start, segment_end))
                        total_confirmed_ranges.append((segment_start, segment_end))
                else:
                    if segment_end > segment_start:
                        unconfirmed_ranges.append((segment_start, segment_end))
                        total_unconfirmed_ranges.append((segment_start, segment_end))
                crm = crm_by_interval.get(interval.id)
                call = calls_by_interval.get(interval.id)
                dto_intervals.append(
                    ActivityWindowInterval(
                        id=interval.id,
                        started_at=self._utc(segment_start),
                        ended_at=self._utc(segment_end),
                        duration_seconds=int(
                            (segment_end - segment_start).total_seconds()
                        ),
                        kind=interval.kind,
                        source=interval.source,
                        duration_source=interval.duration_source,
                        event_type=interval.event_type,
                        object_type=interval.object_type,
                        object_id=interval.object_id,
                        description=interval.description,
                        card_url=(
                            crm.card_url if crm else call.card_url if call else None
                        ),
                        call_direction=call.direction if call else None,
                        call_duration_seconds=call.duration_seconds if call else None,
                        message=(
                            "Нет подтверждённой активности"
                            if interval.kind == "unconfirmed"
                            else None
                        ),
                    )
                )
            dto_intervals.sort(
                key=lambda item: (item.started_at, item.ended_at, item.id)
            )
            days.append(
                ActivityWindowDay(
                    date=local_day,
                    started_at=self._utc(day_start),
                    ended_at=self._utc(day_end),
                    shift_started_at=self._utc(shift_start),
                    shift_ended_at=self._utc(shift_end),
                    confirmed_seconds=self._merged_seconds(confirmed_ranges),
                    confirmed_events=len(day_confirmed_ids),
                    unconfirmed_seconds=self._merged_seconds(unconfirmed_ranges),
                    intervals=dto_intervals,
                )
            )
        return ActivityWindowResponse(
            target=ActivityWindowTarget(
                id=target.id,
                amocrm_user_id=target.amocrm_user_id,
                name=target.name,
                avatar_url=target.avatar_url,
            ),
            group=(
                ActivityWindowGroup(id=group.id, name=group.name) if group else None
            ),
            timezone=zone_name,
            from_date=from_date,
            to_date=to_date,
            totals=ActivityWindowTotals(
                confirmed_seconds=self._merged_seconds(total_confirmed_ranges),
                confirmed_events=len(confirmed_ids),
                unconfirmed_seconds=self._merged_seconds(total_unconfirmed_ranges),
            ),
            days=days,
        )

    def get_monitoring_status(
        self,
        context: RequestContext,
        *,
        search: str | None = None,
        status_filter: str | None = None,
        group_id: int | None = None,
        now: datetime | None = None,
    ) -> TeamStatusResponse:
        """Build one account-scoped monitor snapshot with bounded bulk queries."""
        now = now or utc_now()
        if now.tzinfo is not None:
            now = now.astimezone(timezone.utc).replace(tzinfo=None)
        policy = AccessPolicy(self.db, context)
        is_admin = policy.is_admin()
        is_manager = False if is_admin else policy.is_manager()
        role = "admin" if is_admin else "manager" if is_manager else "employee"

        groups_query = self.db.query(WidgetGroup).filter(
            WidgetGroup.account_id == context.account_id,
            WidgetGroup.is_active.is_(True),
        )
        if is_manager:
            groups_query = groups_query.filter(
                WidgetGroup.manager_user_id == context.user.id,
                WidgetGroup.manager_role_id == context.user.amocrm_role_id,
            )
        elif not is_admin:
            groups_query = groups_query.join(
                GroupMember,
                (GroupMember.group_id == WidgetGroup.id)
                & (GroupMember.account_id == WidgetGroup.account_id),
            ).filter(
                GroupMember.user_id == context.user.id,
                GroupMember.is_active.is_(True),
            )
        groups = groups_query.all()
        groups_by_id = {item.id: item for item in groups}
        accessible_group_ids = set(groups_by_id)
        if group_id is not None and group_id not in accessible_group_ids:
            raise LookupError("group not found")

        member_join = and_(
            GroupMember.account_id == User.amocrm_account_id,
            GroupMember.user_id == User.id,
            GroupMember.is_active.is_(True),
        )
        if accessible_group_ids:
            member_join = and_(
                member_join, GroupMember.group_id.in_(accessible_group_ids)
            )
        else:
            member_join = and_(member_join, GroupMember.id.is_(None))
        users_query = (
            self.db.query(User, GroupMember)
            .outerjoin(GroupMember, member_join)
            .filter(
                User.amocrm_account_id == context.account_id,
                User.is_active.is_(True),
            )
        )
        if is_manager:
            users_query = users_query.filter(
                or_(User.id == context.user.id, GroupMember.id.isnot(None))
            )
        elif not is_admin:
            users_query = users_query.filter(User.id == context.user.id)
        rows = users_query.all()

        visible: dict[int, tuple[User, GroupMember | None, WidgetGroup | None]] = {}
        for user, membership in rows:
            group = groups_by_id.get(membership.group_id) if membership else None
            visible[user.id] = (user, membership, group)
        if group_id is not None:
            visible = {
                user_id: row
                for user_id, row in visible.items()
                if row[1] is not None and row[1].group_id == group_id
            }

        workdays = {
            user_id: self._workday(group, now)
            for user_id, (_user, _membership, group) in visible.items()
        }
        min_start = min((value[1] for value in workdays.values()), default=now)
        max_end = max((value[2] for value in workdays.values()), default=now)
        external_ids = {row[0].amocrm_user_id for row in visible.values()}
        sessions = []
        if external_ids:
            sessions = (
                self.db.query(WorkSession)
                .filter(
                    WorkSession.amocrm_account_id == context.account_id,
                    WorkSession.amocrm_user_id.in_(external_ids),
                    WorkSession.start_time < max_end,
                    or_(
                        WorkSession.end_time.is_(None),
                        WorkSession.end_time > min_start,
                    ),
                )
                .all()
            )
        sessions_by_external: dict[int, list[WorkSession]] = {}
        for session in sessions:
            sessions_by_external.setdefault(session.amocrm_user_id, []).append(session)

        transitions_by_session: dict[int, list[StatusTransition]] = {}
        session_ids = [session.id for session in sessions]
        if session_ids:
            transition_rows = (
                self.db.query(StatusTransition)
                .filter(StatusTransition.work_session_id.in_(session_ids))
                .order_by(
                    StatusTransition.work_session_id,
                    StatusTransition.timestamp,
                    StatusTransition.id,
                )
                .all()
            )
            for transition in transition_rows:
                transitions_by_session.setdefault(
                    transition.work_session_id, []
                ).append(transition)

        intervals = []
        if visible:
            intervals = (
                self.db.query(ActivityInterval)
                .filter(
                    ActivityInterval.account_id == context.account_id,
                    ActivityInterval.user_id.in_(visible),
                    ActivityInterval.kind == "confirmed",
                    ActivityInterval.started_at < max_end,
                    ActivityInterval.ended_at >= min_start,
                )
                .all()
            )
        intervals_by_user: dict[int, list[ActivityInterval]] = {}
        for interval in intervals:
            intervals_by_user.setdefault(interval.user_id, []).append(interval)

        employees: list[TeamMemberSummary] = []
        normalized_search = (
            search.strip().casefold() if search and search.strip() else None
        )
        for user_id, (user, membership, group) in visible.items():
            timezone_name, day_start, day_end = workdays[user_id]
            user_sessions = [
                item
                for item in sessions_by_external.get(user.amocrm_user_id, [])
                if item.start_time < day_end
                and (item.end_time is None or item.end_time > day_start)
            ]
            user_sessions.sort(
                key=lambda item: (item.start_time, item.id), reverse=True
            )
            current = user_sessions[0] if user_sessions else None
            current_transitions = (
                transitions_by_session.get(current.id, []) if current else []
            )
            latest_transition_at = (
                current_transitions[-1].timestamp if current_transitions else None
            )
            if current is None:
                canonical_status = "not_started"
                status_since = None
            elif (
                current.end_time is not None
                or current.current_status == WorkStatus.FINISHED
            ):
                canonical_status = "finished"
                status_since = (
                    current.end_time or latest_transition_at or current.updated_at
                )
            elif current.current_status == WorkStatus.BREAK:
                canonical_status = "on_break"
                status_since = latest_transition_at or current.start_time
            else:
                canonical_status = "working"
                status_since = latest_transition_at or current.start_time

            if normalized_search and normalized_search not in user.name.casefold():
                continue
            if status_filter and canonical_status != status_filter:
                continue

            work_seconds = 0
            break_seconds = 0
            for session in user_sessions:
                session_work, session_break = self._session_seconds(
                    session,
                    transitions_by_session.get(session.id, []),
                    day_start=day_start,
                    day_end=day_end,
                    now=now,
                )
                work_seconds += session_work
                break_seconds += session_break

            confirmed_ranges: list[tuple[datetime, datetime]] = []
            confirmed_events = 0
            for interval in intervals_by_user.get(user_id, []):
                start = max(interval.started_at, day_start)
                end = min(interval.ended_at, day_end)
                is_point = interval.started_at == interval.ended_at
                overlaps = (
                    day_start <= interval.started_at < day_end
                    if is_point
                    else interval.started_at < day_end and interval.ended_at > day_start
                )
                if overlaps:
                    confirmed_events += 1
                    if end > start:
                        confirmed_ranges.append((start, end))
            confirmed_ranges.sort()
            merged_ranges: list[list[datetime]] = []
            for start, end in confirmed_ranges:
                if not merged_ranges or start > merged_ranges[-1][1]:
                    merged_ranges.append([start, end])
                else:
                    merged_ranges[-1][1] = max(merged_ranges[-1][1], end)
            confirmed_seconds = sum(
                int((end - start).total_seconds()) for start, end in merged_ranges
            )
            detail_allowed = is_admin or (
                is_manager
                and membership is not None
                and membership.group_id in accessible_group_ids
            )
            report_filter_allowed = (
                (is_admin or is_manager)
                and membership is not None
                and bool(membership.track_time)
                and group is not None
            )
            employees.append(
                TeamMemberSummary(
                    id=user.id,
                    amocrm_user_id=user.amocrm_user_id,
                    account_id=user.amocrm_account_id,
                    name=user.name,
                    avatar_url=user.avatar_url,
                    group_id=group.id if group else None,
                    group_name=group.name if group else None,
                    timezone=timezone_name,
                    workday_started_at=self._utc(day_start),
                    workday_ended_at=self._utc(day_end),
                    status=canonical_status,
                    status_since=self._utc(status_since),
                    session_started_at=(
                        self._utc(current.start_time) if current else None
                    ),
                    session_ended_at=self._utc(current.end_time) if current else None,
                    work_seconds=work_seconds,
                    break_seconds=break_seconds,
                    confirmed_seconds=confirmed_seconds,
                    confirmed_events=confirmed_events,
                    activity_detail_allowed=detail_allowed,
                    report_filter_allowed=report_filter_allowed,
                )
            )

        employees.sort(
            key=lambda item: (
                item.group_name is None,
                (item.group_name or "").casefold(),
                item.name.casefold(),
                item.id,
            )
        )
        group_summaries = []
        for group in sorted(groups, key=lambda item: (item.name.casefold(), item.id)):
            _zone, start, end = self._workday(group, now)
            count = sum(1 for item in employees if item.group_id == group.id)
            group_summaries.append(
                TeamGroupSummary(
                    id=group.id,
                    name=group.name,
                    timezone=group.timezone,
                    workday_started_at=self._utc(start),
                    workday_ended_at=self._utc(end),
                    employee_count=count,
                )
            )
        counts = {
            status: sum(item.status == status for item in employees)
            for status in ("working", "on_break", "finished", "not_started")
        }
        return TeamStatusResponse(
            generated_at=self._utc(now),
            viewer=TeamViewer(
                id=context.user.id,
                role=role,
                can_view_activity=is_admin or is_manager,
            ),
            groups=group_summaries,
            employees=employees,
            totals=TeamStatusTotals(
                employees=len(employees),
                working=counts["working"],
                on_break=counts["on_break"],
                finished=counts["finished"],
                not_started=counts["not_started"],
                work_seconds=sum(item.work_seconds for item in employees),
                break_seconds=sum(item.break_seconds for item in employees),
                confirmed_seconds=sum(item.confirmed_seconds for item in employees),
                confirmed_events=sum(item.confirmed_events for item in employees),
            ),
        )

    def get_team_status(
        self,
        department: Optional[str] = None,
        account_id: Optional[int] = None,
        visible_external_user_ids: Optional[set[int]] = None,
    ) -> List[Dict[str, Any]]:
        """Get current status of all team members"""
        query = self.db.query(WorkSession).filter(
            WorkSession.current_status != WorkStatus.FINISHED
        )
        if account_id is not None:
            query = query.filter(WorkSession.amocrm_account_id == account_id)
        if visible_external_user_ids is not None:
            query = query.filter(
                WorkSession.amocrm_user_id.in_(visible_external_user_ids)
            )

        if department:
            query = query.filter(WorkSession.department == department)

        sessions = query.all()

        # Get unique users from all sessions (including finished today)
        today_start = utc_now().replace(hour=0, minute=0, second=0, microsecond=0)
        all_users_query = self.db.query(
            WorkSession.amocrm_account_id,
            WorkSession.amocrm_user_id,
            WorkSession.user_name,
            WorkSession.department,
        ).filter(WorkSession.start_time >= today_start)
        if account_id is not None:
            all_users_query = all_users_query.filter(
                WorkSession.amocrm_account_id == account_id
            )
        if visible_external_user_ids is not None:
            all_users_query = all_users_query.filter(
                WorkSession.amocrm_user_id.in_(visible_external_user_ids)
            )

        if department:
            all_users_query = all_users_query.filter(
                WorkSession.department == department
            )

        all_users = all_users_query.distinct().all()

        # Build status list
        status_list = []
        active_users = {(s.amocrm_account_id, s.amocrm_user_id): s for s in sessions}

        for account_id, user_id, user_name, dept in all_users:
            if (account_id, user_id) in active_users:
                session = active_users[(account_id, user_id)]
                status_list.append(
                    {
                        "user_id": session.amocrm_user_id,
                        "user_name": session.user_name,
                        "department": session.department,
                        "current_status": session.current_status.value,
                        "session_id": session.id,
                        "session_start": session.start_time,
                        "work_time": session.total_work_time,
                        "break_time": session.total_break_time,
                        "break_count": session.break_count,
                        "last_activity": session.updated_at,
                    }
                )
            else:
                status_list.append(
                    {
                        "user_id": user_id,
                        "user_name": user_name,
                        "department": dept,
                        "current_status": "not_working",
                        "session_id": None,
                        "session_start": None,
                        "work_time": 0,
                        "break_time": 0,
                        "break_count": 0,
                        "last_activity": None,
                    }
                )

        return status_list

    def get_team_stats(
        self,
        department: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        account_id: Optional[int] = None,
        visible_external_user_ids: Optional[set[int]] = None,
    ) -> Dict[str, Any]:
        """Get team statistics"""
        if not date_from:
            date_from = utc_now().replace(hour=0, minute=0, second=0, microsecond=0)

        if not date_to:
            date_to = utc_now()

        query = self.db.query(WorkSession).filter(
            and_(WorkSession.start_time >= date_from, WorkSession.start_time <= date_to)
        )
        if account_id is not None:
            query = query.filter(WorkSession.amocrm_account_id == account_id)
        if visible_external_user_ids is not None:
            query = query.filter(
                WorkSession.amocrm_user_id.in_(visible_external_user_ids)
            )

        if department:
            query = query.filter(WorkSession.department == department)

        sessions = query.all()

        # Calculate stats
        total_members = len(
            set((s.amocrm_account_id, s.amocrm_user_id) for s in sessions)
        )
        working = sum(1 for s in sessions if s.current_status == WorkStatus.WORKING)
        on_break = sum(1 for s in sessions if s.current_status == WorkStatus.BREAK)
        not_working = total_members - working - on_break

        total_work_time = sum(s.total_work_time for s in sessions)
        total_break_time = sum(s.total_break_time for s in sessions)

        avg_work_time = total_work_time / total_members if total_members > 0 else 0
        avg_break_time = total_break_time / total_members if total_members > 0 else 0

        return {
            "total_members": total_members,
            "working": working,
            "on_break": on_break,
            "not_working": not_working,
            "total_work_time": total_work_time,
            "total_break_time": total_break_time,
            "avg_work_time": round(avg_work_time, 2),
            "avg_break_time": round(avg_break_time, 2),
        }

    def get_team_activity(
        self,
        date: datetime,
        department: Optional[str] = None,
        account_id: Optional[int] = None,
        visible_external_user_ids: Optional[set[int]] = None,
    ) -> List[Dict[str, Any]]:
        """Get team activity for specific date"""
        date_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        date_end = date_start + timedelta(days=1)

        query = self.db.query(WorkSession).filter(
            and_(
                WorkSession.start_time >= date_start, WorkSession.start_time < date_end
            )
        )
        if account_id is not None:
            query = query.filter(WorkSession.amocrm_account_id == account_id)
        if visible_external_user_ids is not None:
            query = query.filter(
                WorkSession.amocrm_user_id.in_(visible_external_user_ids)
            )

        if department:
            query = query.filter(WorkSession.department == department)

        sessions = query.all()

        activity = []
        for session in sessions:
            activity.append(
                {
                    "user_id": session.amocrm_user_id,
                    "user_name": session.user_name,
                    "department": session.department,
                    "start_time": session.start_time,
                    "end_time": session.end_time,
                    "status": session.current_status.value,
                    "work_time": session.total_work_time,
                    "break_time": session.total_break_time,
                    "break_count": session.break_count,
                }
            )

        return activity

    def get_team_status_with_rbac(
        self,
        accessible_dept_ids: Optional[List[int]],
        department_id: Optional[int] = None,
        status_filter: Optional[str] = None,
        online_only: bool = False,
        search: Optional[str] = None,
        account_id: Optional[int] = None,
        visible_internal_user_ids: Optional[set[int]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get team status with RBAC filtering.
        accessible_dept_ids: None = all (Admin), List = allowed (ROP), [] = none
        """
        from app.models.user import User
        from app.models.crm_event import CrmEvent

        # Base query for users
        query = self.db.query(User).filter(User.is_active.is_(True))
        if account_id is not None:
            query = query.filter(User.amocrm_account_id == account_id)
        if visible_internal_user_ids is not None:
            query = query.filter(User.id.in_(visible_internal_user_ids))

        # RBAC filtering by department
        if accessible_dept_ids is not None:  # Not Admin
            if not accessible_dept_ids:  # Empty list - no access
                return []
            query = query.filter(User.department_id.in_(accessible_dept_ids))

        # Filter by specific department
        if department_id:
            query = query.filter(User.department_id == department_id)

        # Search by name
        if search:
            query = query.filter(User.name.ilike(f"%{search}%"))

        users = query.all()

        # Get active sessions
        today_start = utc_now().replace(hour=0, minute=0, second=0, microsecond=0)
        sessions_query = self.db.query(WorkSession).filter(
            WorkSession.start_time >= today_start,
            WorkSession.current_status != WorkStatus.FINISHED,
        )
        if account_id is not None:
            sessions_query = sessions_query.filter(
                WorkSession.amocrm_account_id == account_id
            )
        sessions = {
            (s.amocrm_account_id, s.amocrm_user_id): s for s in sessions_query.all()
        }

        # Get last CRM activity (last 5 minutes for online check)
        five_min_ago = utc_now() - timedelta(minutes=5)

        status_list = []
        for user in users:
            session = sessions.get((user.amocrm_account_id, user.amocrm_user_id))

            # Get last activity from CRM
            last_crm_activity = (
                self.db.query(CrmEvent)
                .filter(
                    CrmEvent.user_id == user.id,
                    CrmEvent.is_complete == 1,
                )
                .order_by(CrmEvent.occurred_at.desc())
                .first()
            )

            last_activity_time = (
                last_crm_activity.occurred_at if last_crm_activity else None
            )
            is_online = (
                last_activity_time is not None and last_activity_time >= five_min_ago
            )

            # Online filter
            if online_only and not is_online:
                continue

            if session:
                current_status = session.current_status.value

                # Status filter
                if status_filter and current_status != status_filter:
                    continue

                status_list.append(
                    {
                        "user_id": user.amocrm_user_id,
                        "user_name": user.name,
                        "department": user.department.name if user.department else None,
                        "department_id": user.department_id,
                        "current_status": current_status,
                        "session_id": session.id,
                        "session_start": session.start_time,
                        "work_time": session.total_work_time,
                        "break_time": session.total_break_time,
                        "break_count": session.break_count,
                        "last_activity": session.updated_at,
                        "last_activity_time": last_activity_time,
                        "is_online": is_online,
                    }
                )
            else:
                current_status = "not_working"

                # Status filter
                if status_filter and current_status != status_filter:
                    continue

                status_list.append(
                    {
                        "user_id": user.amocrm_user_id,
                        "user_name": user.name,
                        "department": user.department.name if user.department else None,
                        "department_id": user.department_id,
                        "current_status": current_status,
                        "session_id": None,
                        "session_start": None,
                        "work_time": 0,
                        "break_time": 0,
                        "break_count": 0,
                        "last_activity": None,
                        "last_activity_time": last_activity_time,
                        "is_online": is_online,
                    }
                )

        return status_list

    def get_user_timeline(
        self, user_id: int, date: Optional[str] = None, account_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get user CRM activity timeline for specific date"""
        from app.models.crm_event import CrmEvent

        if not date:
            target_date = utc_now().date()
        else:
            target_date = datetime.strptime(date, "%Y-%m-%d").date()

        date_start = datetime.combine(target_date, datetime.min.time())
        date_end = datetime.combine(target_date, datetime.max.time())

        # Get user
        from app.services.session_service import SessionService

        session_service = SessionService(self.db)
        user = (
            session_service._user(account_id, user_id)
            if account_id is not None
            else session_service._legacy_user(user_id)
        )
        user_name = user.name if user else f"User {user_id}"

        # Get CRM activities
        activities = (
            self.db.query(CrmEvent)
            .filter(
                CrmEvent.user_id == user.id,
                CrmEvent.occurred_at >= date_start,
                CrmEvent.occurred_at <= date_end,
            )
            .all()
        )

        # Create 15-minute intervals (96 intervals per day)
        intervals = []
        current_time = date_start

        for _ in range(96):  # 24 * 4 = 96 intervals
            interval_end = current_time + timedelta(minutes=15)

            # Count activities in this interval
            interval_activities = [
                a for a in activities if current_time <= a.occurred_at < interval_end
            ]

            deals = sum(1 for a in interval_activities if a.object_type == "lead")
            contacts = sum(1 for a in interval_activities if a.object_type == "contact")
            companies = sum(
                1 for a in interval_activities if a.object_type == "company"
            )
            tasks = sum(1 for a in interval_activities if a.object_type == "task")
            calls = sum(1 for a in interval_activities if a.event_type == "call")

            intervals.append(
                {
                    "start_time": current_time.strftime("%H:%M"),
                    "end_time": interval_end.strftime("%H:%M"),
                    "deals": deals,
                    "contacts": contacts,
                    "companies": companies,
                    "tasks": tasks,
                    "calls": calls,
                    "total_events": len(interval_activities),
                }
            )

            current_time = interval_end

        return {
            "user_id": user_id,
            "user_name": user_name,
            "date": target_date.strftime("%Y-%m-%d"),
            "intervals": intervals,
            "total_events": len(activities),
        }

    def get_user_timeline_history(
        self, user_id: int, account_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get user CRM activity history for last 7 days"""
        from app.models.crm_event import CrmEvent

        from app.services.session_service import SessionService

        session_service = SessionService(self.db)
        user = (
            session_service._user(account_id, user_id)
            if account_id is not None
            else session_service._legacy_user(user_id)
        )
        user_name = user.name if user else f"User {user_id}"

        days = []
        for i in range(7):
            target_date = utc_now().date() - timedelta(days=i)
            date_start = datetime.combine(target_date, datetime.min.time())
            date_end = datetime.combine(target_date, datetime.max.time())

            activities = (
                self.db.query(CrmEvent)
                .filter(
                    CrmEvent.user_id == user.id,
                    CrmEvent.occurred_at >= date_start,
                    CrmEvent.occurred_at <= date_end,
                )
                .all()
            )

            deals = sum(1 for a in activities if a.object_type == "lead")
            contacts = sum(1 for a in activities if a.object_type == "contact")
            companies = sum(1 for a in activities if a.object_type == "company")
            tasks = sum(1 for a in activities if a.object_type == "task")
            calls = sum(1 for a in activities if a.event_type == "call")

            days.append(
                {
                    "date": target_date.strftime("%Y-%m-%d"),
                    "total_events": len(activities),
                    "deals": deals,
                    "contacts": contacts,
                    "companies": companies,
                    "tasks": tasks,
                    "calls": calls,
                }
            )

        return {"user_id": user_id, "user_name": user_name, "days": days}

    def force_finish_session(
        self,
        target_user_id: int,
        admin_id: int,
        admin_name: str,
        reason: str,
        account_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Force finish work session for employee"""
        from app.services.session_service import SessionService

        session_service = SessionService(self.db)
        user = (
            session_service._user(account_id, target_user_id)
            if account_id is not None
            else session_service._legacy_user(target_user_id)
        )
        # Find active session
        session = (
            self.db.query(WorkSession)
            .filter(
                WorkSession.amocrm_user_id == target_user_id,
                WorkSession.amocrm_account_id == user.amocrm_account_id,
                WorkSession.current_status != WorkStatus.FINISHED,
            )
            .first()
        )

        if not session:
            return {
                "success": False,
                "message": "No active session found",
                "session_id": 0,
            }

        # Calculate total time
        now = utc_now()
        last_status_change = max(
            (t.timestamp for t in session.status_transitions),
            default=session.start_time,
        )
        if session.current_status == WorkStatus.WORKING:
            session.total_work_time += int((now - last_status_change).total_seconds())
        elif session.current_status == WorkStatus.BREAK:
            session.total_break_time += int((now - last_status_change).total_seconds())

        # Update session
        session.current_status = WorkStatus.FINISHED
        session.end_time = now
        session.forced_finish = True
        session.forced_finish_by = admin_id
        session.forced_finish_reason = reason
        session.updated_at = now

        self.db.commit()
        self.db.refresh(session)

        return {
            "success": True,
            "message": f"Session force finished by {admin_name}",
            "session_id": session.id,
        }
