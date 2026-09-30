"""Public XLSX contract for the scoped detailed timesheet."""

from datetime import date, datetime, timedelta
from io import BytesIO
from types import SimpleNamespace
from zipfile import ZipFile
import xml.etree.ElementTree as ET
import os
from uuid import uuid4

import pytest
from openpyxl import load_workbook
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.core.access_policy import RequestContext
from app.core.database import Base
from app.api.v1.dependencies import APIProblem
from app.models import (
    GroupMember,
    StatusTransition,
    User,
    WidgetGroup,
    WorkSession,
    WorkStatus,
)


PATH = "/api/v1/reports/export-excel"
PERIOD = {"date_from": "2026-09-22", "date_to": "2026-09-22"}


def export(client, **body):
    return client.post(PATH, json={**PERIOD, **body})


def sheet(response):
    assert response.status_code == 200, response.text
    assert (
        response.headers["content-type"]
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    book = load_workbook(BytesIO(response.content))
    assert book.sheetnames == ["Табель"]
    return book.active


def add_session(
    db,
    *,
    day=date(2026, 9, 22),
    external_id=102,
    account=10,
    start=datetime(2026, 9, 22, 6),
    end=datetime(2026, 9, 22, 7),
    status=WorkStatus.FINISHED,
    work=3600,
    breaks=0,
    late=0,
    transitions=(),
):
    row = WorkSession(
        amocrm_account_id=account,
        amocrm_user_id=external_id,
        user_name="PRIVATE CRM snapshot",
        department="PRIVATE department",
        business_date=day,
        start_time=start,
        end_time=end,
        current_status=status,
        total_work_time=work,
        total_break_time=breaks,
        late_minutes=late,
        late_reason="PRIVATE payload https://example.invalid",
    )
    db.add(row)
    db.flush()
    for state, at in transitions:
        db.add(StatusTransition(work_session_id=row.id, to_status=state, timestamp=at))
    db.flush()
    return row


@pytest.mark.parametrize(
    "start,end,days",
    [
        ("2026-09-22", "2026-09-22", [date(2026, 9, 22)]),
        ("2026-09-22", "2026-09-28", [date(2026, 9, 22), date(2026, 9, 28)]),
        ("2026-09-01", "2026-09-30", [date(2026, 9, 22), date(2026, 9, 30)]),
        ("2026-06-22", "2026-09-22", [date(2026, 6, 22), date(2026, 9, 22)]),
    ],
)
def test_periods_include_exact_employee_days(scoped_client, db, start, end, days):
    add_session(db)
    if end == "2026-09-28":
        add_session(
            db,
            day=date(2026, 9, 28),
            start=datetime(2026, 9, 28, 6),
            end=datetime(2026, 9, 28, 7),
        )
    if end == "2026-09-30":
        add_session(
            db,
            day=date(2026, 9, 30),
            start=datetime(2026, 9, 30, 6),
            end=datetime(2026, 9, 30, 7),
        )
    if start == "2026-06-22":
        add_session(
            db,
            day=date(2026, 6, 22),
            start=datetime(2026, 6, 22, 6),
            end=datetime(2026, 6, 22, 7),
        )
    db.commit()
    response = export(scoped_client("admin"), date_from=start, date_to=end)
    ws = sheet(response)
    assert [cell.value.date() for cell in ws["B"][1:]] == list(reversed(days))
    assert (
        response.headers["content-disposition"]
        == f'attachment; filename="timesheet_{start}_{end}.xlsx"'
    )


def test_selected_columns_local_times_durations_and_same_day_merge(
    scoped_client, db, monkeypatch
):
    from app.services import timesheet_report_service

    monkeypatch.setattr(
        timesheet_report_service, "utc_now", lambda: datetime(2026, 9, 22, 9)
    )
    add_session(
        db,
        start=datetime(2026, 9, 22, 6, 15),
        end=datetime(2026, 9, 22, 7, 15),
        work=99999,
        breaks=99999,
        late=15,
        transitions=[
            ("working", datetime(2026, 9, 22, 6, 15)),
            ("finished", datetime(2026, 9, 22, 7, 15)),
        ],
    )
    add_session(
        db,
        start=datetime(2026, 9, 22, 8),
        end=None,
        status=WorkStatus.BREAK,
        work=99999,
        breaks=99999,
        late=180,
        transitions=[
            ("working", datetime(2026, 9, 22, 8)),
            ("break", datetime(2026, 9, 22, 8, 30)),
        ],
    )
    db.commit()
    ws = sheet(
        export(
            scoped_client("admin"),
            columns=[
                "status",
                "end",
                "start",
                "work",
                "break",
                "lateness",
                "employee",
                "date",
            ],
        )
    )
    assert [cell.value for cell in ws[1]] == [
        "Статус",
        "Окончание",
        "Начало",
        "Работа",
        "Перерыв",
        "Опоздание",
        "Сотрудник",
        "Дата",
    ]
    assert [cell.value for cell in ws[2]] == [
        "Перерыв",
        None,
        datetime(2026, 9, 22, 9, 15),
        timedelta(seconds=5400),
        timedelta(seconds=1800),
        timedelta(seconds=900),
        "Employee",
        datetime(2026, 9, 22),
    ]
    assert [ws.cell(2, col).number_format for col in (3, 4, 5, 6, 8)] == [
        "dd.mm.yyyy hh:mm",
        "[h]:mm",
        "[h]:mm",
        "[h]:mm",
        "dd.mm.yyyy",
    ]
    assert ws.freeze_panes == "A2"
    assert ws.auto_filter.ref == "A1:H2"


def test_zero_duration_is_numeric_excel_zero(scoped_client, db):
    add_session(db, work=0, breaks=0, late=0)
    db.commit()
    response = export(scoped_client("admin"), columns=["work", "break", "lateness"])
    ws = sheet(response)
    assert [cell.value for cell in ws[2]] == [timedelta(0)] * 3
    with ZipFile(BytesIO(response.content)) as archive:
        root = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
    ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    for coordinate in ("A2", "B2", "C2"):
        cell = root.find(f".//x:c[@r='{coordinate}']", ns)
        assert cell is not None
        assert cell.get("t", "n") == "n"
        assert cell.find("x:v", ns).text == "0"


def test_distinct_group_timezones_and_status_labels(scoped_client, db):
    group = WidgetGroup(id=12, account_id=10, name="Berlin", timezone="Europe/Berlin")
    db.add(group)
    db.flush()
    db.add(
        User(
            id=5,
            amocrm_account_id=10,
            amocrm_user_id=105,
            name="Berlin employee",
            amocrm_rights={"is_admin": False},
        )
    )
    db.flush()
    db.add(
        GroupMember(
            id=5, account_id=10, group_id=12, user_id=5, is_active=True, track_time=True
        )
    )
    add_session(db, external_id=105, end=None, status=WorkStatus.WORKING)
    add_session(db, status=WorkStatus.FINISHED)
    db.commit()
    ws = sheet(
        export(scoped_client("admin"), columns=["employee", "start", "end", "status"])
    )
    values = {row[0]: row[1:] for row in ws.iter_rows(min_row=2, values_only=True)}
    assert values["Employee"] == (
        datetime(2026, 9, 22, 9),
        datetime(2026, 9, 22, 10),
        "Закончил(а)",
    )
    assert values["Berlin employee"] == (datetime(2026, 9, 22, 8), None, "Работает")


def test_denial_and_foreign_filters_match_preview(scoped_client, db):
    add_session(db)
    db.commit()
    assert export(scoped_client("employee")).json()["error"]["code"] == "ACCESS_DENIED"
    for kwargs in ({"group_id": 20}, {"group_id": 11}, {"user_id": 4}):
        response = export(scoped_client("manager"), **kwargs)
        assert (response.status_code, response.json()["error"]["code"]) == (
            404,
            "NOT_FOUND",
        )


@pytest.mark.parametrize("actor", ["admin", "manager"])
def test_export_filter_uses_accessible_internal_user_id(scoped_client, db, actor):
    add_session(db)
    db.commit()
    ws = sheet(export(scoped_client(actor), user_id=2, columns=["employee", "work"]))
    assert ws.max_row == 2
    assert [cell.value for cell in ws[2]] == ["Employee", timedelta(hours=1)]


def test_employee_with_internal_user_filter_is_denied_before_visibility_lookup(
    scoped_client, db
):
    add_session(db)
    db.commit()
    response = export(scoped_client("employee"), user_id=2)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ACCESS_DENIED"


@pytest.mark.parametrize(
    "start,end,code",
    [
        ("2026-09-23", "2026-09-22", "REPORT_DATE_RANGE_INVALID"),
        ("2026-01-31", "2026-05-01", "REPORT_RANGE_LIMIT"),
        ("9999-12-31", "9999-12-31", "REPORT_DATE_OUT_OF_RANGE"),
    ],
)
def test_period_errors_keep_stable_russian_contract(scoped_client, start, end, code):
    response = export(scoped_client("admin"), date_from=start, date_to=end)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == code
    assert any("а" <= char <= "я" for char in response.json()["error"]["message"])


def test_forty_foreign_accounts_cannot_enter_export(scoped_client, db):
    add_session(db, work=77)
    for offset in range(40):
        account = 1000 + offset
        user_id = 1000 + offset
        db.add(
            User(
                id=user_id,
                amocrm_account_id=account,
                amocrm_user_id=102,
                name="PRIVATE foreign",
                amocrm_rights={"is_admin": False},
            )
        )
        db.add(
            WidgetGroup(
                id=user_id, account_id=account, name=f"Foreign {offset}", timezone="UTC"
            )
        )
        db.flush()
        db.add(
            GroupMember(
                id=user_id,
                account_id=account,
                group_id=user_id,
                user_id=user_id,
                is_active=True,
                track_time=True,
            )
        )
        add_session(db, account=account, work=999)
    db.commit()
    ws = sheet(export(scoped_client("admin")))
    assert ws.max_row == 2
    assert ws["A2"].value == "Employee"
    assert ws["F2"].value == timedelta(seconds=77)


@pytest.mark.parametrize("prefix", ["=", "+", "-", "@"])
def test_formula_text_and_private_fields_never_become_workbook_content(
    scoped_client, db, prefix
):
    db.get(User, 2).name = f'  {prefix}HYPERLINK("https://evil.invalid")'
    add_session(db)
    db.commit()
    response = export(scoped_client("admin"))
    ws = sheet(response)
    assert ws["A2"].value == f'\'  {prefix}HYPERLINK("https://evil.invalid")'
    assert ws["A2"].data_type == "s"
    assert all(cell.hyperlink is None for row in ws for cell in row)
    with ZipFile(BytesIO(response.content)) as archive:
        xml = b"\n".join(
            archive.read(name) for name in archive.namelist() if name.endswith(".xml")
        )
    for secret in (b"PRIVATE", b"stale", b"amocrm", b"late_reason"):
        assert secret not in xml


def test_export_rejects_employee_day_count_above_limit(scoped_client, db, monkeypatch):
    from app.services import timesheet_report_service

    monkeypatch.setattr(timesheet_report_service, "MAX_EXPORT_ROWS", 1)
    add_session(db)
    add_session(
        db,
        day=date(2026, 9, 23),
        start=datetime(2026, 9, 23, 6),
        end=datetime(2026, 9, 23, 7),
    )
    db.commit()
    response = export(scoped_client("admin"), date_to="2026-09-23")
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "REPORT_EXPORT_TOO_LARGE"
    assert any("а" <= char <= "я" for char in response.json()["error"]["message"])


def test_real_ten_thousand_day_boundary(db):
    from app.services.timesheet_report_service import TimesheetReportService

    users = [
        User(
            id=100 + index,
            amocrm_account_id=10,
            amocrm_user_id=200 + index,
            name=f"Person {index:03d}",
            amocrm_rights={"is_admin": False},
        )
        for index in range(110)
    ]
    db.add_all(users)
    db.flush()
    db.add_all(
        GroupMember(
            id=100 + index,
            account_id=10,
            group_id=10,
            user_id=100 + index,
            is_active=True,
            track_time=True,
        )
        for index in range(110)
    )
    db.flush()

    def session_values(index):
        day = date(2026, 9, 1) + timedelta(days=index % 91)
        return dict(
            amocrm_account_id=10,
            amocrm_user_id=200 + index // 91,
            user_name="old snapshot",
            business_date=day,
            start_time=datetime.combine(day, datetime.min.time()),
            end_time=datetime.combine(day, datetime.min.time()) + timedelta(hours=1),
            current_status="finished",
            total_work_time=3600,
            total_break_time=0,
        )

    for start in range(0, 10000, 1000):
        db.execute(
            WorkSession.__table__.insert(),
            [session_values(index) for index in range(start, start + 1000)],
        )
    db.commit()
    service = TimesheetReportService(db)
    context = RequestContext(account_id=10, user=db.get(User, 1))
    assert (
        len(service.export_rows(context, date(2026, 9, 1), date(2026, 11, 30))) == 10000
    )
    db.execute(WorkSession.__table__.insert(), [session_values(10000)])
    db.commit()
    with pytest.raises(APIProblem) as error:
        service.export_rows(context, date(2026, 9, 1), date(2026, 11, 30))
    assert getattr(error.value, "status_code", None) == 413
    assert getattr(error.value, "code", None) == "REPORT_EXPORT_TOO_LARGE"


def test_export_query_count_is_bounded_without_n_plus_one(db):
    from app.services.timesheet_report_service import TimesheetReportService

    for offset in range(40):
        user_id = 100 + offset
        external_id = 200 + offset
        db.add(
            User(
                id=user_id,
                amocrm_account_id=10,
                amocrm_user_id=external_id,
                name=f"Person {offset}",
                amocrm_rights={"is_admin": False},
            )
        )
        db.flush()
        db.add(
            GroupMember(
                id=user_id,
                account_id=10,
                group_id=10,
                user_id=user_id,
                is_active=True,
                track_time=True,
            )
        )
        add_session(db, external_id=external_id)
    db.commit()
    statements = []

    def record(_conn, _cursor, statement, _parameters, _context, _executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    event.listen(db.get_bind(), "before_cursor_execute", record)
    try:
        rows = TimesheetReportService(db).export_rows(
            RequestContext(account_id=10, user=db.get(User, 1)),
            date(2026, 9, 22),
            date(2026, 9, 22),
        )
    finally:
        event.remove(db.get_bind(), "before_cursor_execute", record)
    assert len(rows) == 40
    assert len(statements) <= 5, repr(statements)


def test_export_fetches_employee_days_in_bounded_batches(db, monkeypatch):
    from app.services import timesheet_report_service
    from app.services.timesheet_report_service import TimesheetReportService

    monkeypatch.setattr(timesheet_report_service, "REPORT_ROW_BATCH_SIZE", 3)
    for offset in range(8):
        user_id = 100 + offset
        external_id = 200 + offset
        db.add(
            User(
                id=user_id,
                amocrm_account_id=10,
                amocrm_user_id=external_id,
                name=f"Person {offset}",
                amocrm_rights={"is_admin": False},
            )
        )
        db.flush()
        db.add(
            GroupMember(
                id=user_id,
                account_id=10,
                group_id=10,
                user_id=user_id,
                is_active=True,
                track_time=True,
            )
        )
        add_session(db, external_id=external_id)
    db.commit()

    service = TimesheetReportService(db)
    original = service._rows_for_keys
    batch_sizes = []

    def record_batch(*args, **kwargs):
        ordered_keys = args[4]
        batch_sizes.append(len(ordered_keys))
        return original(*args, **kwargs)

    monkeypatch.setattr(service, "_rows_for_keys", record_batch)
    rows = service.export_rows(
        RequestContext(account_id=10, user=db.get(User, 1)),
        date(2026, 9, 22),
        date(2026, 9, 22),
    )

    assert batch_sizes == [3, 3, 2]
    assert [row.employee_name for row in rows] == [
        f"Person {offset}" for offset in range(8)
    ]


def test_employee_day_details_reject_unbounded_session_source(db, monkeypatch):
    from app.services import timesheet_report_service
    from app.services.timesheet_report_service import TimesheetReportService

    add_session(db, start=datetime(2026, 9, 22, 6), end=datetime(2026, 9, 22, 7))
    add_session(db, start=datetime(2026, 9, 22, 8), end=datetime(2026, 9, 22, 9))
    db.commit()
    visible = {2: (db.get(User, 2), db.get(WidgetGroup, 10))}
    keys = [SimpleNamespace(id=2, business_date=date(2026, 9, 22))]

    monkeypatch.setattr(timesheet_report_service, "REPORT_SOURCE_ROW_LIMIT", 1)
    with pytest.raises(APIProblem) as error:
        TimesheetReportService(db)._rows_for_keys(
            10,
            visible,
            date(2026, 9, 22),
            date(2026, 9, 22),
            keys,
            datetime(2026, 9, 22, 10),
        )
    assert error.value.status_code == 413
    assert error.value.code == "REPORT_EXPORT_SOURCE_TOO_LARGE"


def test_employee_day_details_reject_unbounded_transition_source(db, monkeypatch):
    from app.services import timesheet_report_service
    from app.services.timesheet_report_service import TimesheetReportService

    add_session(
        db,
        start=datetime(2026, 9, 22, 6),
        end=datetime(2026, 9, 22, 7),
        transitions=[
            ("break", datetime(2026, 9, 22, 6, 15)),
            ("working", datetime(2026, 9, 22, 6, 30)),
        ],
    )
    db.commit()
    visible = {2: (db.get(User, 2), db.get(WidgetGroup, 10))}
    keys = [SimpleNamespace(id=2, business_date=date(2026, 9, 22))]

    monkeypatch.setattr(timesheet_report_service, "REPORT_SOURCE_ROW_LIMIT", 1)
    with pytest.raises(APIProblem) as error:
        TimesheetReportService(db)._rows_for_keys(
            10,
            visible,
            date(2026, 9, 22),
            date(2026, 9, 22),
            keys,
            datetime(2026, 9, 22, 8),
        )
    assert error.value.status_code == 413
    assert error.value.code == "REPORT_EXPORT_SOURCE_TOO_LARGE"


@pytest.fixture
def postgres_db():
    admin_url = os.getenv("TEST_POSTGRES_ADMIN_URL")
    if not admin_url:
        pytest.skip("TEST_POSTGRES_ADMIN_URL required for disposable PostgreSQL test")
    url = make_url(admin_url)
    assert url.get_backend_name() == "postgresql"
    name = "timesheet_excel_test_" + uuid4().hex
    admin = create_engine(url, isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{name}"'))
    engine = create_engine(url.set(database=name))
    Base.metadata.create_all(engine)
    database = sessionmaker(bind=engine)()
    try:
        yield database
    finally:
        database.close()
        engine.dispose()
        with admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
        admin.dispose()


def test_postgres_export_uses_scoped_canonical_rows(postgres_db):
    from app.services.timesheet_report_service import TimesheetReportService
    from app.services.timesheet_excel_service import TimesheetExcelService
    from app.schemas.report import TimesheetColumn

    db = postgres_db
    admin = User(
        id=1,
        amocrm_user_id=101,
        amocrm_account_id=10,
        name="Admin",
        amocrm_rights={"is_admin": True},
    )
    employee = User(
        id=2,
        amocrm_user_id=102,
        amocrm_account_id=10,
        name="Employee",
        amocrm_rights={"is_admin": False},
    )
    db.add_all(
        [
            admin,
            employee,
            WidgetGroup(id=10, account_id=10, name="Team", timezone="Europe/Minsk"),
        ]
    )
    db.flush()
    db.add(
        GroupMember(
            id=1, account_id=10, group_id=10, user_id=2, is_active=True, track_time=True
        )
    )
    add_session(db, work=77)
    db.commit()
    rows = TimesheetReportService(db).export_rows(
        RequestContext(account_id=10, user=admin), date(2026, 9, 22), date(2026, 9, 22)
    )
    assert len(rows) == 1
    assert (rows[0].employee_name, rows[0].work_seconds, rows[0].group_timezone) == (
        "Employee",
        77,
        "Europe/Minsk",
    )
    content = TimesheetExcelService().render(
        rows, [TimesheetColumn.EMPLOYEE, TimesheetColumn.WORK]
    )
    ws = load_workbook(BytesIO(content)).active
    assert [cell.value for cell in ws[2]] == ["Employee", timedelta(seconds=77)]
