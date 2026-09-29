"""Contract tests for the strict, account-scoped detailed timesheet."""

from datetime import date, datetime, time
import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.core.access_policy import RequestContext
from app.core.database import Base
from app.models import GroupMember, StatusTransition, User, WidgetGroup, WorkSession, WorkStatus


PATH = "/api/v1/reports/detailed"
PERIOD = {"date_from": "2026-09-22", "date_to": "2026-09-22"}


def add_user(db, *, user_id, external_id, account=10, name="Alice", active=True):
    user = User(
        id=user_id,
        amocrm_user_id=external_id,
        amocrm_account_id=account,
        name=name,
        amocrm_rights={"is_admin": False},
        is_active=active,
    )
    db.add(user)
    db.flush()
    return user


def add_member(db, *, member_id, user_id, group_id=10, account=10, active=True, tracked=True):
    db.add(GroupMember(
        id=member_id, account_id=account, group_id=group_id, user_id=user_id,
        is_active=active, track_time=tracked,
    ))
    db.flush()


def add_session(db, *, account=10, external_id=102, day=date(2026, 9, 22),
                start=datetime(2026, 9, 22, 6), end=datetime(2026, 9, 22, 7),
                status=WorkStatus.FINISHED, late=0, work=0, break_time=0,
                transitions=()):
    session = WorkSession(
        amocrm_account_id=account, amocrm_user_id=external_id,
        user_name="stale snapshot", department="stale department",
        business_date=day, start_time=start, end_time=end,
        current_status=status, late_minutes=late,
        total_work_time=work, total_break_time=break_time,
    )
    db.add(session)
    db.flush()
    for state, at in transitions:
        db.add(StatusTransition(work_session_id=session.id, to_status=state, timestamp=at))
    db.flush()
    return session


def get(client, **params):
    return client.get(PATH, params={**PERIOD, **params})


def assert_problem(response, status, code):
    assert response.status_code == status, response.text
    assert response.json()["error"]["code"] == code
    assert response.json()["error"]["message"]


def test_admin_and_current_manager_are_scoped_to_active_tracked_members(scoped_client, db):
    add_session(db)
    add_user(db, user_id=5, external_id=105, name="Bea")
    db.add(WidgetGroup(id=12, account_id=10, name="Other", timezone="UTC"))
    db.flush()
    add_member(db, member_id=5, user_id=5, group_id=12)
    add_session(db, external_id=105)
    add_user(db, user_id=6, external_id=106, name="Untracked")
    add_member(db, member_id=6, user_id=6, tracked=False)
    add_session(db, external_id=106)
    add_user(db, user_id=7, external_id=107, name="Inactive member")
    add_member(db, member_id=7, user_id=7, active=False)
    add_session(db, external_id=107)
    add_user(db, user_id=8, external_id=108, name="Inactive user", active=False)
    add_member(db, member_id=8, user_id=8)
    add_session(db, external_id=108)
    db.commit()

    admin = get(scoped_client("admin"))
    manager = get(scoped_client("manager"))
    assert admin.status_code == manager.status_code == 200
    assert {item["user_id"] for item in admin.json()["items"]} == {2, 5}
    assert [item["user_id"] for item in manager.json()["items"]] == [2]
    for hidden_user_id in (6, 7, 8):
        assert_problem(get(scoped_client("admin"), user_id=hidden_user_id), 404, "NOT_FOUND")
    assert_problem(get(scoped_client("employee")), 403, "ACCESS_DENIED")
    assert_problem(get(scoped_client("employee"), user_id=2), 403, "ACCESS_DENIED")
    assert_problem(get(scoped_client("employee"), user_id=4), 403, "ACCESS_DENIED")

    db.get(User, 3).amocrm_role_id = 78
    db.commit()
    assert_problem(get(scoped_client("manager")), 403, "ACCESS_DENIED")


@pytest.mark.parametrize("filter_name,filter_value", [
    ("group_id", 20), ("group_id", 11), ("group_id", 999),
    ("user_id", 4), ("user_id", 999),
])
def test_foreign_inactive_and_missing_filters_have_uniform_404(scoped_client, filter_name, filter_value):
    response = get(scoped_client("admin"), **{filter_name: filter_value})
    assert_problem(response, 404, "NOT_FOUND")
    assert response.json()["error"]["message"] == "Данные не найдены."


def test_filters_check_report_scope_after_general_identity_scope(scoped_client, db):
    add_user(db, user_id=5, external_id=105, name="Outside")
    db.add(WidgetGroup(id=12, account_id=10, name="Other", timezone="UTC"))
    db.flush()
    add_member(db, member_id=5, user_id=5, group_id=12)
    add_session(db, external_id=105)
    db.commit()
    assert_problem(get(scoped_client("manager"), group_id=12), 404, "NOT_FOUND")
    assert_problem(get(scoped_client("manager"), user_id=5), 404, "NOT_FOUND")
    assert_problem(get(scoped_client("admin"), group_id=10, user_id=5), 404, "NOT_FOUND")
    assert get(scoped_client("admin"), user_id=5).json()["items"][0]["user_id"] == 5


def test_same_day_sessions_merge_and_transitions_override_legacy_counters(scoped_client, db, monkeypatch):
    from app.services import timesheet_report_service

    monkeypatch.setattr(timesheet_report_service, "utc_now", lambda: datetime(2026, 9, 22, 9))
    add_session(
        db, start=datetime(2026, 9, 22, 6, 15), end=datetime(2026, 9, 22, 7, 15),
        late=15, work=99999, break_time=99999,
        transitions=[("working", datetime(2026, 9, 22, 6, 15)),
                     ("finished", datetime(2026, 9, 22, 7, 15))],
    )
    add_session(
        db, start=datetime(2026, 9, 22, 8), end=None, status=WorkStatus.BREAK,
        late=180, work=99999, break_time=99999,
        transitions=[("working", datetime(2026, 9, 22, 8)),
                     ("break", datetime(2026, 9, 22, 8, 30))],
    )
    db.commit()
    response = get(scoped_client("admin"))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == body["totals"]["days"] == body["totals"]["employees"] == 1
    assert len(body["items"]) == 1
    row = body["items"][0]
    assert row["employee_name"] == "Employee"
    assert row["group_name"] == "Zebra"
    assert row["status"] == "on_break"
    assert row["started_at"].startswith("2026-09-22T06:15")
    assert row["ended_at"] is None
    assert (row["work_seconds"], row["break_seconds"], row["late_seconds"]) == (5400, 1800, 900)
    assert body["totals"]["work_seconds"] == 5400
    assert not ({"activities", "events", "calls", "activity_count", "entity_url"} & set(row))


def test_historical_counter_fallback_and_final_status(scoped_client, db):
    add_session(db, work=-30, break_time=-20, late=-10)
    add_session(db, day=date(2026, 9, 21), work=3600, break_time=600, late=5)
    db.commit()
    response = scoped_client("admin").get(PATH, params={"date_from": "2026-09-21", "date_to": "2026-09-22"})
    assert response.status_code == 200, response.text
    assert [(row["date"], row["work_seconds"], row["break_seconds"], row["late_seconds"], row["status"])
            for row in response.json()["items"]] == [
                ("2026-09-22", 0, 0, 0, "finished"),
                ("2026-09-21", 3600, 600, 300, "finished"),
            ]


def test_overnight_dst_uses_persisted_business_date(scoped_client, db):
    group = db.get(WidgetGroup, 10)
    group.timezone = "Europe/Berlin"
    group.work_start_time, group.work_end_time = time(22), time(6)
    add_session(db, day=date(2026, 10, 24), start=datetime(2026, 10, 25, 0, 30),
                end=datetime(2026, 10, 25, 1), work=1800)
    add_session(db, day=date(2026, 10, 24), start=datetime(2026, 10, 25, 2, 30),
                end=datetime(2026, 10, 25, 3), work=1800)
    db.commit()
    response = scoped_client("admin").get(PATH, params={"date_from": "2026-10-24", "date_to": "2026-10-24"})
    assert response.status_code == 200, response.text
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["date"] == "2026-10-24"
    assert response.json()["items"][0]["group_timezone"] == "Europe/Berlin"
    assert response.json()["items"][0]["work_seconds"] == 3600


def test_distinct_keys_sort_and_page_before_loading_sessions(scoped_client, db):
    for n in range(12):
        user_id = 100 + n
        external_id = 200 + n
        add_user(db, user_id=user_id, external_id=external_id, name=f"Person {n:02d}")
        add_member(db, member_id=user_id, user_id=user_id)
        add_session(db, external_id=external_id, work=60)
        add_session(db, external_id=external_id, start=datetime(2026, 9, 22, 8),
                    end=datetime(2026, 9, 22, 9), work=60)
    db.commit()
    first = get(scoped_client("admin"), page=1)
    second = get(scoped_client("admin"), page=2)
    assert first.status_code == second.status_code == 200
    assert (first.json()["page_size"], first.json()["total"], len(first.json()["items"])) == (10, 12, 10)
    assert len(second.json()["items"]) == 2
    assert first.json()["totals"] == second.json()["totals"]
    assert first.json()["totals"] == {
        "work_seconds": 1440, "break_seconds": 0, "late_seconds": 0,
        "days": 12, "employees": 12,
    }
    assert [row["employee_name"] for row in first.json()["items"]] == [f"Person {n:02d}" for n in range(10)]
    assert [row["employee_name"] for row in second.json()["items"]] == ["Person 10", "Person 11"]
    assert [row["user_id"] for row in first.json()["items"]] == [row["user_id"] for row in get(scoped_client("admin"), page=1).json()["items"]]
    assert get(scoped_client("admin"), page=3).json()["items"] == []
    assert_problem(get(scoped_client("admin"), page=0), 422, "REQUEST_INVALID")


@pytest.mark.parametrize("start,end,code", [
    ("2026-09-23", "2026-09-22", "REPORT_DATE_RANGE_INVALID"),
    ("2026-01-31", "2026-05-01", "REPORT_RANGE_LIMIT"),
])
def test_period_errors_have_russian_messages(scoped_client, start, end, code):
    response = scoped_client("admin").get(PATH, params={"date_from": start, "date_to": end})
    assert_problem(response, 422, code)
    assert any("а" <= char <= "я" for char in response.json()["error"]["message"])


def test_duplicate_external_ids_in_forty_foreign_accounts_never_leak(scoped_client, db):
    add_session(db, work=77)
    for offset in range(40):
        account = 1000 + offset
        user_id = 1000 + offset
        add_user(db, user_id=user_id, external_id=102, account=account, name="Foreign")
        db.add(WidgetGroup(id=1000 + offset, account_id=account, name="Foreign", timezone="UTC"))
        db.flush()
        add_member(db, member_id=1000 + offset, user_id=user_id, group_id=1000 + offset, account=account)
        add_session(db, account=account, external_id=102, work=999)
    db.commit()
    response = get(scoped_client("admin"))
    assert response.status_code == 200, response.text
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["user_id"] == 2
    assert response.json()["totals"]["work_seconds"] == 77


@pytest.mark.parametrize("employee_count", [1, 42])
def test_service_select_count_is_bounded_by_fixed_bulk_queries(db, employee_count):
    from app.services.timesheet_report_service import TimesheetReportService

    for offset in range(employee_count - 1):
        user_id = 100 + offset
        external_id = 200 + offset
        add_user(db, user_id=user_id, external_id=external_id, name=f"Person {offset:02d}")
        add_member(db, member_id=user_id, user_id=user_id)
        add_session(db, external_id=external_id, work=60)
    add_session(db, work=60)
    db.commit()
    context = RequestContext(account_id=10, user=db.get(User, 1))
    selects = []

    def record(_conn, _cursor, statement, _parameters, _context, _executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            selects.append(statement)

    event.listen(db.get_bind(), "before_cursor_execute", record)
    try:
        result = TimesheetReportService(db).list_rows(
            context, date(2026, 9, 22), date(2026, 9, 22), None, None, 1,
            datetime(2026, 9, 23),
        )
    finally:
        event.remove(db.get_bind(), "before_cursor_execute", record)
    assert result.total == employee_count
    assert len(result.items) == min(10, employee_count)
    assert len(selects) == 4, "unexpected N+1 queries: " + repr(selects)


@pytest.fixture
def postgres_db():
    admin_url = os.getenv("TEST_POSTGRES_ADMIN_URL")
    if not admin_url:
        pytest.skip("TEST_POSTGRES_ADMIN_URL required for disposable PostgreSQL test")
    url = make_url(admin_url)
    assert url.get_backend_name() == "postgresql"
    name = "timesheet_report_test_" + uuid4().hex
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


def test_postgres_real_scoped_bulk_report(postgres_db):
    from app.services.timesheet_report_service import TimesheetReportService

    db = postgres_db
    admin = add_user(db, user_id=1, external_id=101, name="Admin")
    admin.amocrm_rights = {"is_admin": True}
    add_user(db, user_id=2, external_id=102, name="Employee")
    db.add(WidgetGroup(id=10, account_id=10, name="Team", timezone="UTC"))
    db.flush()
    add_member(db, member_id=1, user_id=2)
    add_session(db, work=60)
    for offset in range(40):
        account = 1000 + offset
        user_id = 1000 + offset
        add_user(db, user_id=user_id, external_id=102, account=account, name="Foreign")
        db.add(WidgetGroup(id=user_id, account_id=account, name="Other", timezone="UTC"))
        db.flush()
        add_member(db, member_id=user_id, user_id=user_id, group_id=user_id, account=account)
        add_session(db, account=account, external_id=102, work=999)
    db.commit()
    context = RequestContext(account_id=10, user=admin)
    selects = []

    def record(_conn, _cursor, statement, _parameters, _context, _executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            selects.append(statement)

    event.listen(db.get_bind(), "before_cursor_execute", record)
    try:
        result = TimesheetReportService(db).list_rows(
            context, date(2026, 9, 22), date(2026, 9, 22), now=datetime(2026, 9, 23)
        )
    finally:
        event.remove(db.get_bind(), "before_cursor_execute", record)
    assert result.total == 1
    assert result.items[0].user_id == 2
    assert result.totals.work_seconds == 60
    assert len(selects) == 4, "unexpected N+1 queries: " + repr(selects)
