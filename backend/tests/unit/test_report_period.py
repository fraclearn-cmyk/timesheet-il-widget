"""Boundary tests for the strict timesheet report contract."""

from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError


@pytest.mark.parametrize(
    ("start", "maximum"),
    [
        (date(2026, 1, 31), date(2026, 4, 30)),
        (date(2024, 2, 29), date(2024, 5, 29)),
        (date(2026, 11, 30), date(2027, 2, 28)),
        (date(2024, 11, 30), date(2025, 2, 28)),
    ],
)
def test_maximum_report_date_clamps_calendar_months(start, maximum):
    from app.core.report_period import maximum_report_date

    assert maximum_report_date(start) == maximum


@pytest.mark.parametrize(
    ("start", "end"),
    [
        (date(2026, 1, 31), date(2026, 1, 31)),
        (date(2026, 1, 31), date(2026, 2, 6)),
        (date(2026, 1, 31), date(2026, 2, 28)),
        (date(2026, 1, 31), date(2026, 4, 30)),
        (date(2024, 11, 30), date(2025, 2, 28)),
    ],
)
def test_report_period_accepts_inclusive_range_through_three_months(start, end):
    from app.core.report_period import validate_report_period

    assert validate_report_period(start, end) is None


@pytest.mark.parametrize(
    ("start", "end", "code", "message"),
    [
        (
            date(2026, 2, 2),
            date(2026, 2, 1),
            "REPORT_DATE_RANGE_INVALID",
            "Дата окончания периода не может быть раньше даты начала.",
        ),
        (
            date(2026, 1, 31),
            date(2026, 5, 1),
            "REPORT_RANGE_LIMIT",
            "Период отчёта не может быть больше 3 месяцев.",
        ),
        (
            date(2024, 11, 30),
            date(2025, 3, 1),
            "REPORT_RANGE_LIMIT",
            "Период отчёта не может быть больше 3 месяцев.",
        ),
    ],
)
def test_report_period_rejects_invalid_or_over_limit_range(start, end, code, message):
    from app.core.report_period import ReportPeriodError, validate_report_period

    with pytest.raises(ReportPeriodError) as error:
        validate_report_period(start, end)
    assert error.value.code == code
    assert error.value.message == message
    assert str(error.value) == message


def test_detailed_report_row_contains_only_timesheet_fields():
    from app.schemas.report import DetailedReportRow

    row = DetailedReportRow(
        user_id=7,
        amocrm_user_id=700,
        employee_name="One",
        group_id=3,
        group_name="Sales",
        group_timezone="Europe/Moscow",
        date=date(2026, 9, 11),
        started_at=datetime(2026, 9, 11, 5, tzinfo=timezone.utc),
        ended_at=None,
        break_seconds=1800,
        work_seconds=3600,
        late_seconds=0,
        status="working",
    )
    assert row.user_id == 7
    assert row.amocrm_user_id == 700
    assert row.ended_at is None
    assert set(row.model_dump()) == {
        "user_id", "amocrm_user_id", "employee_name", "group_id", "group_name",
        "group_timezone", "date", "started_at", "ended_at", "break_seconds",
        "work_seconds", "late_seconds", "status",
    }
    with pytest.raises(ValidationError):
        DetailedReportRow.model_validate({**row.model_dump(), "crm_payload": {"id": 1}})
    with pytest.raises(ValidationError):
        DetailedReportRow.model_validate({**row.model_dump(), "status": "on_call"})
    with pytest.raises(ValidationError):
        DetailedReportRow.model_validate({**row.model_dump(), "work_seconds": -1})


def test_report_response_has_fixed_ten_row_page_and_strict_totals():
    from app.schemas.report import DetailedReportResponse

    payload = {
        "items": [],
        "page": 1,
        "total": 0,
        "totals": {
            "work_seconds": 0,
            "break_seconds": 0,
            "late_seconds": 0,
            "days": 0,
            "employees": 0,
        },
    }
    response = DetailedReportResponse.model_validate(payload)
    assert response.page_size == 10
    for change in ({"page": 0}, {"page_size": 9}, {"activity_count": 1}):
        with pytest.raises(ValidationError):
            DetailedReportResponse.model_validate({**payload, **change})
    with pytest.raises(ValidationError):
        DetailedReportResponse.model_validate({**payload, "totals": {**payload["totals"], "calls": 1}})


def test_excel_columns_allow_only_eight_timesheet_fields():
    from app.schemas.report import ReportExcelRequest, TimesheetColumn

    allowed = {"employee", "date", "start", "end", "break", "work", "lateness", "status"}
    assert {column.value for column in TimesheetColumn} == allowed
    request = ReportExcelRequest(
        date_from=date(2026, 9, 1),
        date_to=date(2026, 9, 7),
        group_id=3,
        user_id=7,
        columns=["status", "employee", "date"],
    )
    assert request.columns == [TimesheetColumn.STATUS, TimesheetColumn.EMPLOYEE, TimesheetColumn.DATE]
    assert [column.value for column in ReportExcelRequest(
        date_from=date(2026, 9, 1), date_to=date(2026, 9, 1)
    ).columns] == [column.value for column in TimesheetColumn]
    for columns in ([], ["date", "date"], ["activity"], ["crm"], ["call"], ["url"], ["payload"]):
        with pytest.raises(ValidationError):
            ReportExcelRequest(date_from=date(2026, 9, 1), date_to=date(2026, 9, 1), columns=columns)
    with pytest.raises(ValidationError):
        ReportExcelRequest(date_from=date(2026, 9, 1), date_to=date(2026, 9, 1), activity=True)
