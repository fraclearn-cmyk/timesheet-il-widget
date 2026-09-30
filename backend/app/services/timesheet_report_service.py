"""Detailed timesheet rows based only on current tracked group membership."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone

from sqlalchemy import and_, tuple_
from sqlalchemy.orm import Session

from app.api.v1.dependencies import APIProblem, access_denied, not_found
from app.core.access_policy import AccessPolicy, RequestContext
from app.core.report_period import validate_report_period
from app.core.time_utils import utc_now
from app.models.group_member import GroupMember
from app.models.status_transition import StatusTransition
from app.models.user import User
from app.models.widget_group import WidgetGroup
from app.models.work_session import WorkSession
from app.schemas.report import (
    DetailedReportResponse,
    DetailedReportRow,
    DetailedReportTotals,
)

MAX_EXPORT_ROWS = 10000
REPORT_ROW_BATCH_SIZE = 250


def _utc_naive(value: datetime) -> datetime:
    return (
        value.astimezone(timezone.utc).replace(tzinfo=None) if value.tzinfo else value
    )


def _seconds(start: datetime, end: datetime) -> int:
    return max(0, int((end - start).total_seconds()))


def _elapsed(
    session: WorkSession, transitions: list[StatusTransition], now: datetime
) -> tuple[int, int]:
    """Rebuild durations from status changes; closed pre-transition rows use legacy counters."""
    if not transitions and session.end_time is not None:
        return max(0, int(session.total_work_time or 0)), max(
            0, int(session.total_break_time or 0)
        )

    start = _utc_naive(session.start_time)
    finish = min(_utc_naive(session.end_time), now) if session.end_time else now
    finish = max(start, finish)
    cursor = start
    state = "working"
    work = breaks = 0
    for transition in sorted(
        transitions, key=lambda item: (_utc_naive(item.timestamp), item.id)
    ):
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

    def _visible_members(
        self,
        context: RequestContext,
        group_id: int | None,
        user_id: int | None,
    ) -> dict[int, tuple[User, WidgetGroup]]:
        policy = AccessPolicy(self.db, context)
        is_admin = policy.is_admin()
        if not is_admin and not policy.is_manager():
            raise access_denied()
        account = context.account_id
        group_scope = [
            WidgetGroup.account_id == account,
            WidgetGroup.is_active.is_(True),
        ]
        if not is_admin:
            group_scope += [
                WidgetGroup.manager_user_id == context.user.id,
                WidgetGroup.manager_role_id == context.user.amocrm_role_id,
            ]
        if group_id is not None:
            group = (
                self.db.query(WidgetGroup.id)
                .filter(WidgetGroup.id == group_id, *group_scope)
                .first()
            )
            if group is None:
                raise not_found()
        membership = (
            self.db.query(User, WidgetGroup)
            .join(
                GroupMember,
                and_(
                    GroupMember.account_id == User.amocrm_account_id,
                    GroupMember.user_id == User.id,
                ),
            )
            .join(
                WidgetGroup,
                and_(
                    WidgetGroup.account_id == GroupMember.account_id,
                    WidgetGroup.id == GroupMember.group_id,
                ),
            )
            .filter(
                User.amocrm_account_id == account,
                User.is_active.is_(True),
                GroupMember.account_id == account,
                GroupMember.is_active.is_(True),
                GroupMember.track_time.is_(True),
                *group_scope,
            )
        )
        if group_id is not None:
            membership = membership.filter(WidgetGroup.id == group_id)
        if user_id is not None:
            membership = membership.filter(User.id == user_id)
        visible = {user.id: (user, group) for user, group in membership.all()}
        if user_id is not None and user_id not in visible:
            raise not_found()
        return visible

    def _ordered_keys(
        self,
        account: int,
        visible_ids: list[int],
        date_from: date,
        date_to: date,
        limit: int | None = None,
    ):
        keys_query = (
            self.db.query(User.id, WorkSession.business_date, User.name)
            .join(
                WorkSession,
                and_(
                    WorkSession.amocrm_account_id == User.amocrm_account_id,
                    WorkSession.amocrm_user_id == User.amocrm_user_id,
                ),
            )
            .filter(
                User.amocrm_account_id == account,
                WorkSession.amocrm_account_id == account,
                WorkSession.business_date >= date_from,
                WorkSession.business_date <= date_to,
                User.id.in_(visible_ids),
            )
            .distinct()
        )
        if limit is not None:
            keys_query = keys_query.limit(limit)
        return sorted(
            keys_query.all(),
            key=lambda item: (
                -item.business_date.toordinal(),
                item.name.strip().casefold(),
                item.id,
            ),
        )

    def export_rows(
        self,
        context: RequestContext,
        date_from: date,
        date_to: date,
        group_id: int | None = None,
        user_id: int | None = None,
        now: datetime | None = None,
    ) -> list[DetailedReportRow]:
        validate_report_period(date_from, date_to)
        visible = self._visible_members(context, group_id, user_id)
        if not visible:
            return []
        keys = self._ordered_keys(
            context.account_id,
            list(visible),
            date_from,
            date_to,
            limit=MAX_EXPORT_ROWS + 1,
        )
        if len(keys) > MAX_EXPORT_ROWS:
            raise APIProblem(
                413,
                "REPORT_EXPORT_TOO_LARGE",
                "Слишком много строк для выгрузки отчёта.",
            )
        effective_now = _utc_naive(now or utc_now())
        rows: list[DetailedReportRow] = []
        for start in range(0, len(keys), REPORT_ROW_BATCH_SIZE):
            rows.extend(
                self._rows_for_keys(
                    context.account_id,
                    visible,
                    date_from,
                    date_to,
                    keys[start : start + REPORT_ROW_BATCH_SIZE],
                    effective_now,
                )
            )
        return rows

    def _stream_totals(
        self,
        account: int,
        visible_ids: list[int],
        date_from: date,
        date_to: date,
        now: datetime,
        days: int,
        employees: int,
    ) -> DetailedReportTotals:
        """Fold one projected session/transition stream without retaining period rows."""
        rows = (
            self.db.query(
                User.id.label("user_id"),
                WorkSession.business_date.label("day"),
                WorkSession.id.label("session_id"),
                WorkSession.start_time.label("started_at"),
                WorkSession.end_time.label("ended_at"),
                WorkSession.total_work_time.label("legacy_work"),
                WorkSession.total_break_time.label("legacy_break"),
                WorkSession.late_minutes.label("late_minutes"),
                StatusTransition.id.label("transition_id"),
                StatusTransition.timestamp.label("transition_at"),
                StatusTransition.to_status.label("to_status"),
            )
            .join(
                User,
                and_(
                    User.amocrm_account_id == WorkSession.amocrm_account_id,
                    User.amocrm_user_id == WorkSession.amocrm_user_id,
                ),
            )
            .outerjoin(
                StatusTransition, StatusTransition.work_session_id == WorkSession.id
            )
            .filter(
                WorkSession.amocrm_account_id == account,
                User.amocrm_account_id == account,
                WorkSession.business_date >= date_from,
                WorkSession.business_date <= date_to,
                User.id.in_(visible_ids),
            )
            .order_by(
                User.id,
                WorkSession.business_date,
                WorkSession.start_time,
                WorkSession.id,
                StatusTransition.timestamp,
                StatusTransition.id,
            )
            .yield_per(512)
        )
        work_total = break_total = late_total = 0
        current_session_id = None
        current_day = None
        session_work = session_break = 0
        has_transition = False

        def finish_session() -> tuple[int, int]:
            if not has_transition and ended_at is not None:
                return max(0, int(legacy_work or 0)), max(0, int(legacy_break or 0))
            elapsed = _seconds(cursor, finish)
            return (
                session_work + (elapsed if state == "working" else 0),
                session_break + (elapsed if state == "break" else 0),
            )

        for row in rows:
            if row.session_id != current_session_id:
                if current_session_id is not None:
                    work, breaks = finish_session()
                    work_total += work
                    break_total += breaks
                current_session_id = row.session_id
                day_key = (row.user_id, row.day)
                if day_key != current_day:
                    late_total += max(0, int(row.late_minutes or 0)) * 60
                    current_day = day_key
                ended_at = row.ended_at
                legacy_work, legacy_break = row.legacy_work, row.legacy_break
                start = _utc_naive(row.started_at)
                finish = min(_utc_naive(ended_at), now) if ended_at else now
                finish = max(start, finish)
                cursor = start
                state = "working"
                session_work = session_break = 0
                has_transition = False
            if row.transition_id is not None:
                has_transition = True
                at = min(finish, max(cursor, _utc_naive(row.transition_at)))
                elapsed = _seconds(cursor, at)
                if state == "working":
                    session_work += elapsed
                elif state == "break":
                    session_break += elapsed
                cursor = at
                state = row.to_status
        if current_session_id is not None:
            work, breaks = finish_session()
            work_total += work
            break_total += breaks
        return DetailedReportTotals(
            work_seconds=work_total,
            break_seconds=break_total,
            late_seconds=late_total,
            days=days,
            employees=employees,
        )

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
        if page < 1:
            raise ValueError("page must be positive")
        account = context.account_id
        visible = self._visible_members(context, group_id, user_id)
        if not visible:
            return DetailedReportResponse(
                items=[],
                page=page,
                total=0,
                totals=DetailedReportTotals(
                    work_seconds=0, break_seconds=0, late_seconds=0, days=0, employees=0
                ),
            )

        ordered_keys = self._ordered_keys(account, list(visible), date_from, date_to)
        total = len(ordered_keys)
        if not ordered_keys:
            return DetailedReportResponse(
                items=[],
                page=page,
                total=0,
                totals=DetailedReportTotals(
                    work_seconds=0, break_seconds=0, late_seconds=0, days=0, employees=0
                ),
            )

        effective_now = _utc_naive(now or utc_now())
        rows = self._rows_for_keys(
            account,
            visible,
            date_from,
            date_to,
            ordered_keys[(page - 1) * 10 : page * 10],
            effective_now,
        )
        totals = self._stream_totals(
            account,
            list(visible),
            date_from,
            date_to,
            effective_now,
            total,
            len({item.id for item in ordered_keys}),
        )
        return DetailedReportResponse(items=rows, page=page, total=total, totals=totals)

    def _rows_for_keys(
        self,
        account: int,
        visible: dict[int, tuple[User, WidgetGroup]],
        date_from: date,
        date_to: date,
        ordered_keys,
        effective_now: datetime,
    ) -> list[DetailedReportRow]:
        if not ordered_keys:
            return []
        page_keys = {(item.id, item.business_date) for item in ordered_keys}
        sessions_query = (
            self.db.query(WorkSession, User.id)
            .join(
                User,
                and_(
                    User.amocrm_account_id == WorkSession.amocrm_account_id,
                    User.amocrm_user_id == WorkSession.amocrm_user_id,
                ),
            )
            .filter(
                WorkSession.amocrm_account_id == account,
                User.amocrm_account_id == account,
                WorkSession.business_date >= date_from,
                WorkSession.business_date <= date_to,
                tuple_(User.id, WorkSession.business_date).in_(page_keys),
            )
        )
        sessions = sessions_query.all() if page_keys else []
        by_key: dict[tuple[int, date], list[WorkSession]] = defaultdict(list)
        for session, internal_id in sessions:
            by_key[(internal_id, session.business_date)].append(session)
        transitions_by_session: dict[int, list[StatusTransition]] = defaultdict(list)
        if sessions:
            transition_query = (
                self.db.query(StatusTransition)
                .join(WorkSession, WorkSession.id == StatusTransition.work_session_id)
                .join(
                    User,
                    and_(
                        User.amocrm_account_id == WorkSession.amocrm_account_id,
                        User.amocrm_user_id == WorkSession.amocrm_user_id,
                    ),
                )
                .filter(
                    WorkSession.amocrm_account_id == account,
                    User.amocrm_account_id == account,
                    WorkSession.business_date >= date_from,
                    WorkSession.business_date <= date_to,
                    tuple_(User.id, WorkSession.business_date).in_(page_keys),
                )
            )
            for transition in transition_query.all():
                transitions_by_session[transition.work_session_id].append(transition)

        page_rows = {}
        for key, day_sessions in by_key.items():
            internal_id, day = key
            user, group = visible[internal_id]
            day_sessions.sort(key=lambda item: (_utc_naive(item.start_time), item.id))
            work = breaks = 0
            for session in day_sessions:
                session_work, session_breaks = _elapsed(
                    session, transitions_by_session[session.id], effective_now
                )
                work += session_work
                breaks += session_breaks
            first = day_sessions[0]
            latest = day_sessions[-1]
            page_rows[key] = DetailedReportRow(
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
                status=(
                    "on_break"
                    if latest.current_status.value == "break"
                    else latest.current_status.value
                ),
            )
        return [page_rows[(item.id, item.business_date)] for item in ordered_keys]
