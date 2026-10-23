"""Role-scoped calendar bounds for the detailed timesheet and Excel export."""

from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.core.access_policy import AccessPolicy, RequestContext
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
) -> ReportAccessPeriod:
    policy = AccessPolicy(db, context)
    max_date = today or utc_now().date()
    if policy.is_admin():
        days = REPORT_RETENTION_DAYS
    elif policy.is_manager():
        query = db.query(WidgetGroup).filter(
            WidgetGroup.account_id == context.account_id,
            WidgetGroup.manager_user_id == context.user.id,
            WidgetGroup.manager_role_id == context.user.amocrm_role_id,
            WidgetGroup.is_active.is_(True),
        )
        if group_id is not None:
            query = query.filter(WidgetGroup.id == group_id)
        groups = query.all()
        if not groups:
            raise LookupError("group not found")
        days = min(group.report_history_days for group in groups)
    else:
        raise PermissionError("report access denied")
    return ReportAccessPeriod(
        min_date=max_date - timedelta(days=days - 1),
        max_date=max_date,
        history_days=days,
    )


def require_report_period(
    db: Session,
    context: RequestContext,
    date_from: date,
    date_to: date,
    group_id: int | None = None,
) -> ReportAccessPeriod:
    period = resolve_report_access_period(db, context, group_id)
    if date_from < period.min_date or date_to > period.max_date:
        raise ReportPeriodError(
            "REPORT_PERIOD_ACCESS_DENIED",
            "Выбранный период находится за пределами доступной истории табеля.",
        )
    return period
