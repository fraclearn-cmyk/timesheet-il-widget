"""Detailed timesheet rows based only on current tracked group membership."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.api.v1.dependencies import access_denied, not_found
from app.core.access_policy import AccessPolicy, RequestContext
from app.core.report_period import validate_report_period
from app.core.time_utils import utc_now
from app.models.group_member import GroupMember
from app.models.status_transition import StatusTransition
from app.models.user import User
from app.models.widget_group import WidgetGroup
from app.models.work_session import WorkSession
from app.schemas.report import DetailedReportResponse, DetailedReportRow, DetailedReportTotals


def _utc_naive(value: datetime) -> datetime:
    return value.astimezone(timezone.utc).replace(tzinfo=None) if value.tzinfo else value


def _seconds(start: datetime, end: datetime) -> int:
    return max(0, int((end - start).total_seconds()))


def _elapsed(session: WorkSession, transitions: list[StatusTransition], now: datetime) -> tuple[int, int]:
    """Rebuild durations from status changes; closed pre-transition rows use legacy counters."""
    if not transitions and session.end_time is not None:
        return max(0, int(session.total_work_time or 0)), max(0, int(session.total_break_time or 0))

    start = _utc_naive(session.start_time)
    finish = min(_utc_naive(session.end_time), now) if session.end_time else now
    finish = max(start, finish)
    cursor = start
    state = "working"
    work = breaks = 0
    for transition in sorted(transitions, key=lambda item: (_utc_naive(item.timestamp), item.id)):
        at = min(finish, max(cursor, _utc_naive(transition.timestamp)))
        elapsed = _seconds(cursor, at)
        if state == "working":
            work += elapsed
        elif state == "break":
            breaks += elapsed
        cursor = at
        state = transition.to_status
    elapsed = _seconds(cursor, finish)
    if state == "working":
        work += elapsed
    elif state == "break":
        breaks += elapsed
    return work, breaks


class TimesheetReportService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_rows(
        self,
        context: RequestContext,
        date_from: date,
        date_to: date,
        group_id: int | None = None,
        user_id: int | None = None,
        page: int = 1,
        now: datetime | None = None,
    ) -> DetailedReportResponse:
        validate_report_period(date_from, date_to)
        policy = AccessPolicy(self.db, context)
        is_admin = policy.is_admin()
        if not is_admin and not policy.is_manager():
            raise access_denied()
        if page < 1:
            raise ValueError("page must be positive")

        account = context.account_id
        group_scope = [WidgetGroup.account_id == account, WidgetGroup.is_active.is_(True)]
        if not is_admin:
            group_scope += [
                WidgetGroup.manager_user_id == context.user.id,
                WidgetGroup.manager_role_id == context.user.amocrm_role_id,
            ]
        if group_id is not None:
            group = self.db.query(WidgetGroup.id).filter(WidgetGroup.id == group_id, *group_scope).first()
            if group is None:
                raise not_found()

        membership = (
            self.db.query(User, WidgetGroup)
            .join(GroupMember, and_(GroupMember.account_id == User.amocrm_account_id,
                                    GroupMember.user_id == User.id))
            .join(WidgetGroup, and_(WidgetGroup.account_id == GroupMember.account_id,
                                    WidgetGroup.id == GroupMember.group_id))
            .filter(User.amocrm_account_id == account, User.is_active.is_(True),
                    GroupMember.account_id == account, GroupMember.is_active.is_(True),
                    GroupMember.track_time.is_(True), *group_scope)
        )
        if group_id is not None:
            membership = membership.filter(WidgetGroup.id == group_id)
        if user_id is not None:
            membership = membership.filter(User.id == user_id)
        visible = {user.id: (user, group) for user, group in membership.all()}
        if user_id is not None and user_id not in visible:
            raise not_found()
        if not visible:
            return DetailedReportResponse(
                items=[], page=page, total=0,
                totals=DetailedReportTotals(work_seconds=0, break_seconds=0,
                                            late_seconds=0, days=0, employees=0),
            )

        # Select distinct internal-user/day keys before applying the page window.
        # Account predicates on both identities prevent external-ID collisions.
        keys_query = (
            self.db.query(User.id, WorkSession.business_date, User.name)
            .join(WorkSession, and_(WorkSession.amocrm_account_id == User.amocrm_account_id,
                                    WorkSession.amocrm_user_id == User.amocrm_user_id))
            .filter(User.amocrm_account_id == account,
                    WorkSession.amocrm_account_id == account,
                    WorkSession.business_date >= date_from,
                    WorkSession.business_date <= date_to,
                    User.id.in_(visible))
            .distinct()
        )
        ordered_keys = sorted(
            keys_query.all(),
            key=lambda item: (-item.business_date.toordinal(), item.name.strip().casefold(), item.id),
        )
        total = len(ordered_keys)
        page_keys = {(item.id, item.business_date) for item in ordered_keys[(page - 1) * 10:page * 10]}
        if not ordered_keys:
            return DetailedReportResponse(
                items=[], page=page, total=0,
                totals=DetailedReportTotals(work_seconds=0, break_seconds=0,
                                            late_seconds=0, days=0, employees=0),
            )

        # Full-filter totals and the page use the same canonical rows. Both
        # collections are fetched in bulk, so employee count does not drive SQL count.
        sessions = (
            self.db.query(WorkSession, User.id)
            .join(User, and_(User.amocrm_account_id == WorkSession.amocrm_account_id,
                             User.amocrm_user_id == WorkSession.amocrm_user_id))
            .filter(WorkSession.amocrm_account_id == account,
                    User.amocrm_account_id == account,
                    WorkSession.business_date >= date_from,
                    WorkSession.business_date <= date_to,
                    User.id.in_(visible))
            .all()
        )
        by_key: dict[tuple[int, date], list[WorkSession]] = defaultdict(list)
        for session, internal_id in sessions:
            by_key[(internal_id, session.business_date)].append(session)
        transitions_by_session: dict[int, list[StatusTransition]] = defaultdict(list)
        if sessions:
            transition_query = (
                self.db.query(StatusTransition)
                .join(WorkSession, WorkSession.id == StatusTransition.work_session_id)
                .join(User, and_(User.amocrm_account_id == WorkSession.amocrm_account_id,
                                 User.amocrm_user_id == WorkSession.amocrm_user_id))
                .filter(WorkSession.amocrm_account_id == account,
                        User.amocrm_account_id == account,
                        WorkSession.business_date >= date_from,
                        WorkSession.business_date <= date_to,
                        User.id.in_(visible))
            )
            for transition in transition_query.all():
                transitions_by_session[transition.work_session_id].append(transition)

        effective_now = _utc_naive(now or utc_now())
        all_rows = {}
        for key, day_sessions in by_key.items():
            internal_id, day = key
            user, group = visible[internal_id]
            day_sessions.sort(key=lambda item: (_utc_naive(item.start_time), item.id))
            work = breaks = 0
            for session in day_sessions:
                session_work, session_breaks = _elapsed(session, transitions_by_session[session.id], effective_now)
                work += session_work
                breaks += session_breaks
            first = day_sessions[0]
            latest = day_sessions[-1]
            all_rows[key] = DetailedReportRow(
                user_id=internal_id,
                amocrm_user_id=user.amocrm_user_id,
                employee_name=user.name,
                group_id=group.id,
                group_name=group.name,
                group_timezone=group.timezone,
                date=day,
                started_at=first.start_time,
                ended_at=latest.end_time,
                break_seconds=breaks,
                work_seconds=work,
                late_seconds=max(0, int(first.late_minutes or 0)) * 60,
                status="on_break" if latest.current_status.value == "break" else latest.current_status.value,
            )
        rows = [all_rows[key] for key in [(item.id, item.business_date) for item in ordered_keys] if key in page_keys]
        totals = DetailedReportTotals(
            work_seconds=sum(row.work_seconds for row in all_rows.values()),
            break_seconds=sum(row.break_seconds for row in all_rows.values()),
            late_seconds=sum(row.late_seconds for row in all_rows.values()),
            days=total,
            employees=len({key[0] for key in all_rows}),
        )
        return DetailedReportResponse(items=rows, page=page, total=total, totals=totals)
