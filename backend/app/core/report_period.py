"""Calendar-month bounds for detailed timesheet reports."""

from calendar import monthrange
from datetime import date


class ReportPeriodError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


def maximum_report_date(date_from: date) -> date:
    """Return the inclusive three-calendar-month boundary, clamping month ends."""
    month_index = date_from.year * 12 + date_from.month - 1 + 3
    year, zero_based_month = divmod(month_index, 12)
    month = zero_based_month + 1
    return date(year, month, min(date_from.day, monthrange(year, month)[1]))


def validate_report_period(date_from: date, date_to: date) -> None:
    if date_to < date_from:
        raise ReportPeriodError(
            "REPORT_DATE_RANGE_INVALID",
            "Дата окончания периода не может быть раньше даты начала.",
        )
    if date_to > maximum_report_date(date_from):
        raise ReportPeriodError(
            "REPORT_RANGE_LIMIT", "Период отчёта не может быть больше 3 месяцев."
        )
