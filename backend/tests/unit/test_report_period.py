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


def test_report_period_rejects_start_that_cannot_represent_three_month_boundary():
    from app.core.report_period import ReportPeriodError, validate_report_period

    with pytest.raises(ReportPeriodError) as error:
        validate_report_period(date(9999, 12, 31), date(9999, 12, 31))
    assert error.value.code == "REPORT_DATE_OUT_OF_RANGE"


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
        "user_id",
        "amocrm_user_id",
        "employee_name",
        "group_id",
        "group_name",
        "group_timezone",
        "date",
        "started_at",
        "ended_at",
        "break_seconds",
        "work_seconds",
        "late_seconds",
        "shift_late_seconds",
        "shift_late_reason",
        "break_late_seconds",
        "break_late_reason",
        "status",
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
        DetailedReportResponse.model_validate(
            {**payload, "totals": {**payload["totals"], "calls": 1}}
        )


def test_excel_columns_allow_lateness_fields_and_normalize_legacy_alias():
    from app.schemas.report import ReportExcelRequest, TimesheetColumn

    allowed = {
        "employee",
        "date",
        "start",
        "end",
        "break",
        "work",
        "shift_lateness",
        "shift_late_reason",
        "break_lateness",
        "break_late_reason",
        "status",
    }
    assert {column.value for column in TimesheetColumn} == allowed
    request = ReportExcelRequest(
        date_from=date(2026, 9, 1),
        date_to=date(2026, 9, 7),
        group_id=3,
        user_id=7,
        columns=["status", "employee", "date"],
    )
    assert request.columns == [
        TimesheetColumn.STATUS,
        TimesheetColumn.EMPLOYEE,
        TimesheetColumn.DATE,
    ]
    assert [
        column.value
        for column in ReportExcelRequest(
            date_from=date(2026, 9, 1), date_to=date(2026, 9, 1)
        ).columns
    ] == [column.value for column in TimesheetColumn]
    for columns in (
        [],
        ["date", "date"],
        ["lateness", "shift_lateness"],
        ["activity"],
        ["crm"],
        ["call"],
        ["url"],
        ["payload"],
    ):
        with pytest.raises(ValidationError):
            ReportExcelRequest(
                date_from=date(2026, 9, 1), date_to=date(2026, 9, 1), columns=columns
            )
    with pytest.raises(ValidationError):
        ReportExcelRequest(
            date_from=date(2026, 9, 1), date_to=date(2026, 9, 1), activity=True
        )
    legacy = ReportExcelRequest(date_from=date(2026, 9, 1), date_to=date(2026, 9, 1), columns=["lateness"])
    assert legacy.model_dump(mode="json")["columns"] == ["shift_lateness"]


def test_command_reason_normalizes_before_length_validation():
    from app.schemas.timesheet import CommandRequest

    key = "11111111-1111-4111-8111-111111111111"
    assert CommandRequest(idempotency_key=key).reason is None
    assert CommandRequest(idempotency_key=key, reason=" \n ").reason is None
    assert CommandRequest(idempotency_key=key, reason="  " + "x" * 1000 + "  ").reason == "x" * 1000
    for reason in ("x" * 1001, 123):
        with pytest.raises(ValidationError):
            CommandRequest(idempotency_key=key, reason=reason)


@pytest.mark.parametrize("limit", [1, 60, 720])
def test_settings_contract_accepts_break_limit_boundaries_and_member_flag(limit):
    from app.schemas.settings_snapshot import SettingsGroupUpdate, SettingsUserUpdate

    group = SettingsGroupUpdate(name="Sales", timezone="UTC", work_start_time="09:00", work_end_time="18:00", is_active=True, allow_restart_session=False, break_limit_minutes=limit)
    member = SettingsUserUpdate(amocrm_user_id=700, track_time=True, hide_widget=False, group_ref=None, require_late_reason=True)
    assert group.break_limit_minutes == limit
    assert member.require_late_reason is True


@pytest.mark.parametrize("limit", [0, 721, 1.5, True, "60"])
def test_settings_contract_rejects_invalid_break_limit(limit):
    from app.schemas.settings_snapshot import SettingsGroupUpdate

    with pytest.raises(ValidationError):
        SettingsGroupUpdate(name="Sales", timezone="UTC", work_start_time="09:00", work_end_time="18:00", is_active=True, allow_restart_session=False, break_limit_minutes=limit)


def test_settings_lateness_defaults_and_strict_member_flag():
    from app.schemas.settings_snapshot import SettingsGroupUpdate, SettingsUserUpdate

    assert SettingsGroupUpdate(name="Sales", timezone="UTC", work_start_time="09:00", work_end_time="18:00", is_active=True, allow_restart_session=False).break_limit_minutes == 60
    assert SettingsUserUpdate(amocrm_user_id=700, track_time=True, hide_widget=False, group_ref=None).require_late_reason is False
    with pytest.raises(ValidationError):
        SettingsUserUpdate(amocrm_user_id=700, track_time=True, hide_widget=False, group_ref=None, require_late_reason="true")


def test_status_contract_contains_optional_lateness_requirement():
    from app.schemas.timesheet import TimesheetStatusResponse

    payload = dict(session_id=None, status="not_started", started_at=None, ended_at=None, break_seconds=0, track_time=True, hide_widget=False, restart_allowed=False)
    status = TimesheetStatusResponse(**payload)
    assert (status.late_reason_required, status.late_reason_kind, status.late_minutes, status.break_sequence) == (False, None, 0, None)
    status = TimesheetStatusResponse(**payload, late_reason_required=True, late_reason_kind="break_return", late_minutes=1, break_sequence=2)
    assert status.late_reason_kind == "break_return"
    for changes in ({"late_reason_kind": "unknown"}, {"late_minutes": -1}, {"break_sequence": 0}, {"late_reason_required": "true"}, {"unexpected": 1}):
        with pytest.raises(ValidationError):
            TimesheetStatusResponse(**payload, **changes)


def test_break_lateness_contract_preserves_individual_reasons_and_validates_limits():
    from app.schemas.report import BreakLateness, DetailedReportRow

    item = BreakLateness(sequence=1, late_seconds=60, reason="  " + "x" * 1000 + "  ")
    assert item.reason == "x" * 1000
    for changes in ({"sequence": 0}, {"late_seconds": -1}, {"reason": "x" * 1001}, {"reason": "   "}, {"unsafe": 1}):
        with pytest.raises(ValidationError):
            BreakLateness.model_validate({**item.model_dump(), **changes})
    row = DetailedReportRow(user_id=7, amocrm_user_id=700, employee_name="One", group_id=3, group_name="Sales", group_timezone="UTC", date=date(2026, 10, 15), started_at=None, ended_at=None, break_seconds=0, work_seconds=0, late_seconds=120, break_late_seconds=60, break_late_reason=[item], status="working")
    assert row.shift_late_seconds == 120
    assert row.break_late_reason[0].sequence == 1
    assert row.shift_late_reason is None
    for changes in ({"shift_late_seconds": -1}, {"break_late_seconds": -1}, {"shift_late_reason": "x" * 1001}):
        with pytest.raises(ValidationError):
            DetailedReportRow.model_validate({**row.model_dump(), **changes})
