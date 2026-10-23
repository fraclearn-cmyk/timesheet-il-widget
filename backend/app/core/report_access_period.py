"""Role-scoped calendar bounds for the detailed timesheet and Excel export."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from collections.abc import Sequence

from sqlalchemy.orm import Session

from app.core.access_policy import AccessPolicy, RequestContext
from app.core.business_time import business_date
from app.core.report_period import ReportPeriodError
from app.core.time_utils import utc_now
from app.models.widget_group import WidgetGroup


REPORT_RETENTION_DAYS = 365


@dataclass(frozen=True)
class ReportAccessPeriod:
    min_date: date
    max_date: date
    history_days: int


def resolve_report_access_period(
    db: Session,
    context: RequestContext,
    group_id: int | None = None,
    *,
    today: date | None = None,
    now: datetime | None = None,
    groups: Sequence[WidgetGroup] | None = None,
) -> ReportAccessPeriod:
    policy = AccessPolicy(db, context)
    is_admin = policy.is_admin()
    supplied_groups = groups is not None
    resolved_groups = list(groups) if supplied_groups else []
    is_manager = False
    if not is_admin:
        if supplied_groups:
            is_manager = (
                context.privileges_verified
                and isinstance(context.user.amocrm_role_id, int)
                and bool(resolved_groups)
                and all(
                    group.account_id == context.account_id
                    and group.manager_user_id == context.user.id
                    and group.manager_role_id == context.user.amocrm_role_id
                    and group.is_active
                    for group in resolved_groups
                )
            )
        else:
            is_manager = policy.is_manager()
    if is_admin:
        days = REPORT_RETENTION_DAYS
    elif not is_manager:
        raise PermissionError("report access denied")

    if not supplied_groups:
        query = db.query(WidgetGroup).filter(
            WidgetGroup.account_id == context.account_id,
            WidgetGroup.is_active.is_(True),
        )
        if group_id is not None:
            query = query.filter(WidgetGroup.id == group_id)
        if is_manager:
            query = query.filter(
                WidgetGroup.manager_user_id == context.user.id,
                WidgetGroup.manager_role_id == context.user.amocrm_role_id,
            )
        resolved_groups = query.all()
    if group_id is not None and not resolved_groups:
        raise LookupError("group not found")
    if is_manager:
        if not resolved_groups:
            raise LookupError("group not found")
        days = min(group.report_history_days for group in resolved_groups)

    if today is not None:
        max_date = today
        min_date = max_date - timedelta(days=days - 1)
    elif resolved_groups:
        instant = now or utc_now()
        if instant.tzinfo is not None:
            instant = instant.astimezone(timezone.utc).replace(tzinfo=None)
        group_bounds = [
            (
                business_date(
                    instant,
                    group.timezone,
                    group.work_start_time,
                    group.work_end_time,
                ),
                REPORT_RETENTION_DAYS
                if policy.is_admin()
                else group.report_history_days,
            )
            for group in resolved_groups
        ]
        max_date = max(day for day, _history_days in group_bounds)
        min_date = max(
            day - timedelta(days=history_days - 1)
            for day, history_days in group_bounds
        )
    else:
        max_date = (now or utc_now()).date()
        min_date = max_date - timedelta(days=days - 1)
    return ReportAccessPeriod(
        min_date=min_date,
        max_date=max_date,
        history_days=days,
    )


def require_report_period(
    db: Session,
    context: RequestContext,
    date_from: date,
    date_to: date,
    group_id: int | None = None,
    *,
    groups: Sequence[WidgetGroup] | None = None,
) -> ReportAccessPeriod:
    period = resolve_report_access_period(db, context, group_id, groups=groups)
    if date_from < period.min_date or date_to > period.max_date:
        raise ReportPeriodError(
            "REPORT_PERIOD_ACCESS_DENIED",
            "Выбранный период находится за пределами доступной истории табеля.",
        )
    return period
