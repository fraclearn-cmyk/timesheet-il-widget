"""Phase-6 team monitor visibility, aggregates and capacity contract."""

from datetime import datetime, time

from sqlalchemy import event

from app.models import (
    ActivityInterval,
    GroupMember,
    StatusTransition,
    User,
    WidgetGroup,
    WorkSession,
)
from app.models.user import UserRole
from app.models.work_session import WorkStatus


NOW = datetime(2026, 9, 28, 12, 0)


def _user(id_, external_id, account_id, name, *, admin=False, active=True, role_id=1):
    return User(
        id=id_,
        amocrm_user_id=external_id,
        amocrm_account_id=account_id,
        name=name,
        role=UserRole.ADMIN if admin else UserRole.EMPLOYEE,
        amocrm_rights={"is_admin": admin, "role_id": role_id},
        amocrm_role_id=role_id,
        is_active=active,
    )


def test_role_visibility_filters_and_stable_errors(scoped_client, db, monkeypatch):
    monkeypatch.setattr("app.api.v1.team.utc_now", lambda: NOW)
    monkeypatch.setattr("app.services.team_service.utc_now", lambda: NOW)
    db.add_all(
        [
            _user(5, 105, 10, "Петр Активный"),
            _user(6, 106, 10, "Inactive member", active=False),
            _user(7, 107, 10, "Ungrouped"),
            WidgetGroup(
                id=12,
                account_id=10,
                name="Stale",
                manager_user_id=3,
                manager_role_id=999,
            ),
            GroupMember(account_id=10, group_id=10, user_id=5, is_active=True),
            GroupMember(account_id=10, group_id=12, user_id=6, is_active=True),
        ]
    )
    db.commit()

    manager = scoped_client("manager").get(
        "/api/v1/team/status?search=%20%D0%BF%D0%95%D0%A2%D0%A0%20&status=not_started"
    )
    assert manager.status_code == 200
    payload = manager.json()
    assert payload["viewer"] == {"id": 3, "role": "manager", "can_view_activity": True}
    assert [row["amocrm_user_id"] for row in payload["employees"]] == [105]
    assert all(row["account_id"] == 10 for row in payload["employees"])

    employee = scoped_client("employee").get("/api/v1/team/status")
    assert [row["id"] for row in employee.json()["employees"]] == [2]
    assert employee.json()["employees"][0]["activity_detail_allowed"] is False

    admin = scoped_client("admin").get("/api/v1/team/status")
    assert {row["id"] for row in admin.json()["employees"]} == {1, 2, 3, 5, 7}
    assert [row["name"] for row in admin.json()["groups"]] == ["Stale", "Zebra"]

    missing = scoped_client("manager").get("/api/v1/team/status?group_id=12")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "NOT_FOUND"
    invalid = scoped_client("admin").get("/api/v1/team/status?status=online")
    assert invalid.status_code == 422


def test_report_filter_choices_match_active_tracked_membership_and_viewer_scope(scoped_client, db):
    db.add_all([
        _user(5, 105, 10, "Untracked"),
        _user(6, 106, 10, "Inactive group"),
        _user(7, 107, 10, "Other manager group"),
        WidgetGroup(id=12, account_id=10, name="Other", manager_user_id=3, manager_role_id=999),
        GroupMember(account_id=10, group_id=10, user_id=5, is_active=True, track_time=False),
        GroupMember(account_id=10, group_id=11, user_id=6, is_active=True, track_time=True),
        GroupMember(account_id=10, group_id=12, user_id=7, is_active=True, track_time=True),
    ])
    db.commit()

    admin = scoped_client("admin").get("/api/v1/team/status")
    assert admin.status_code == 200
    assert {row["id"]: row["report_filter_allowed"] for row in admin.json()["employees"]} == {
        1: False, 2: True, 3: False, 5: False, 6: False, 7: True,
    }
    manager = scoped_client("manager").get("/api/v1/team/status")
    assert manager.status_code == 200
    assert {row["id"]: row["report_filter_allowed"] for row in manager.json()["employees"]} == {
        2: True, 3: False, 5: False,
    }
    employee = scoped_client("employee").get("/api/v1/team/status")
    assert employee.status_code == 200
    assert employee.json()["employees"][0]["report_filter_allowed"] is False

    assert scoped_client("admin").get("/api/v1/reports/detailed", params={
        "date_from": "2026-09-29", "date_to": "2026-09-29", "user_id": 2,
    }).status_code == 200
    assert scoped_client("admin").get("/api/v1/reports/detailed", params={
        "date_from": "2026-09-29", "date_to": "2026-09-29", "user_id": 5,
    }).status_code == 404


def test_status_workday_and_aggregate_contract(scoped_client, db, monkeypatch):
    monkeypatch.setattr("app.api.v1.team.utc_now", lambda: NOW)
    monkeypatch.setattr("app.services.team_service.utc_now", lambda: NOW)
    group = db.get(WidgetGroup, 10)
    group.timezone = "UTC"
    group.work_start_time = time(9)
    group.work_end_time = time(18)
    db.add_all(
        [
            _user(5, 105, 10, "Break user"),
            _user(6, 106, 10, "Finished user"),
            _user(7, 107, 10, "Not started user"),
            GroupMember(account_id=10, group_id=10, user_id=5, is_active=True),
            GroupMember(account_id=10, group_id=10, user_id=6, is_active=True),
            GroupMember(account_id=10, group_id=10, user_id=7, is_active=True),
            WorkSession(
                id=200,
                amocrm_user_id=102,
                amocrm_account_id=10,
                user_name="Employee",
                start_time=datetime(2026, 9, 28, 8, 30),
                current_status=WorkStatus.WORKING,
                total_work_time=99999,
                total_break_time=99999,
            ),
            WorkSession(
                id=201,
                amocrm_user_id=105,
                amocrm_account_id=10,
                user_name="Break user",
                start_time=datetime(2026, 9, 28, 9, 15),
                current_status=WorkStatus.BREAK,
            ),
            WorkSession(
                id=202,
                amocrm_user_id=106,
                amocrm_account_id=10,
                user_name="Finished user",
                start_time=datetime(2026, 9, 28, 9, 30),
                end_time=datetime(2026, 9, 28, 11),
                current_status=WorkStatus.FINISHED,
            ),
        ]
    )
    db.flush()
    db.add_all(
        [
            StatusTransition(
                work_session_id=200,
                from_status=None,
                to_status="working",
                timestamp=datetime(2026, 9, 28, 8, 30),
            ),
            StatusTransition(
                work_session_id=200,
                from_status="working",
                to_status="break",
                timestamp=datetime(2026, 9, 28, 10),
                duration=3600,
            ),
            StatusTransition(
                work_session_id=200,
                from_status="break",
                to_status="working",
                timestamp=datetime(2026, 9, 28, 10, 15),
                duration=900,
            ),
            StatusTransition(
                work_session_id=202,
                from_status=None,
                to_status="working",
                timestamp=datetime(2026, 9, 28, 9, 30),
            ),
            StatusTransition(
                work_session_id=202,
                from_status="working",
                to_status="break",
                timestamp=datetime(2026, 9, 28, 10),
            ),
            StatusTransition(
                work_session_id=202,
                from_status="break",
                to_status="working",
                timestamp=datetime(2026, 9, 28, 10, 10),
            ),
            StatusTransition(
                work_session_id=202,
                from_status="working",
                to_status="finished",
                timestamp=datetime(2026, 9, 28, 11),
            ),
            ActivityInterval(
                account_id=10,
                user_id=2,
                work_session_id=200,
                started_at=datetime(2026, 9, 28, 10),
                ended_at=datetime(2026, 9, 28, 10, 5),
                kind="confirmed",
                source="crm_event",
                duration_source="calculated",
            ),
            ActivityInterval(
                account_id=10,
                user_id=2,
                work_session_id=200,
                started_at=datetime(2026, 9, 28, 10, 3),
                ended_at=datetime(2026, 9, 28, 10, 8),
                kind="confirmed",
                source="crm_event",
                duration_source="calculated",
            ),
            ActivityInterval(
                account_id=10,
                user_id=2,
                work_session_id=200,
                started_at=datetime(2026, 9, 28, 10, 9),
                ended_at=datetime(2026, 9, 28, 10, 9),
                kind="confirmed",
                source="crm_event",
                duration_source="point",
            ),
            ActivityInterval(
                account_id=10,
                user_id=2,
                work_session_id=None,
                started_at=datetime(2026, 9, 28, 10),
                ended_at=datetime(2026, 9, 28, 11),
                kind="unconfirmed",
                source="unconfirmed_input",
                duration_source="observed",
            ),
        ]
    )
    db.commit()

    response = scoped_client("admin").get("/api/v1/team/status?group_id=10")
    assert response.status_code == 200
    rows = {row["id"]: row for row in response.json()["employees"]}
    assert {user_id: row["status"] for user_id, row in rows.items()} == {
        2: "working",
        5: "on_break",
        6: "finished",
        7: "not_started",
    }
    row = rows[2]
    assert row["workday_started_at"] == "2026-09-28T09:00:00Z"
    assert row["workday_ended_at"] == "2026-09-28T18:00:00Z"
    assert row["session_started_at"] == "2026-09-28T08:30:00Z"
    assert row["work_seconds"] == 9_900
    assert row["break_seconds"] == 900
    assert row["confirmed_seconds"] == 480
    assert row["confirmed_events"] == 3
    assert rows[6]["work_seconds"] == 4_800
    assert rows[6]["break_seconds"] == 600
    totals = response.json()["totals"]
    assert {
        key: totals[key]
        for key in ("employees", "working", "on_break", "finished", "not_started")
    } == {
        "employees": 4,
        "working": 1,
        "on_break": 1,
        "finished": 1,
        "not_started": 1,
    }
    assert totals["confirmed_seconds"] == 480
    assert totals["confirmed_events"] == 3


def test_forty_accounts_duplicate_ids_and_constant_query_count(
    scoped_client, db, monkeypatch
):
    monkeypatch.setattr("app.api.v1.team.utc_now", lambda: NOW)
    monkeypatch.setattr("app.services.team_service.utc_now", lambda: NOW)
    for offset in range(40):
        account_id = 1000 + offset
        user_id = 1000 + offset
        db.add(
            _user(user_id, 777, account_id, f"Tenant {offset}", admin=True, role_id=70)
        )
        db.add(
            WidgetGroup(id=1000 + offset, account_id=account_id, name=f"Group {offset}")
        )
    for offset in range(39):
        db.add(_user(2000 + offset, 5000 + offset, 10, f"Visible {offset}"))
    db.add_all(
        [
            WorkSession(
                id=9000,
                amocrm_user_id=777,
                amocrm_account_id=1000,
                user_name="Tenant 0",
                start_time=datetime(2026, 9, 28, 9),
                current_status=WorkStatus.WORKING,
            ),
            StatusTransition(
                work_session_id=9000,
                from_status=None,
                to_status="working",
                timestamp=datetime(2026, 9, 28, 9),
            ),
            WorkSession(
                id=9001,
                amocrm_user_id=101,
                amocrm_account_id=10,
                user_name="Admin",
                start_time=datetime(2026, 9, 28, 9),
                current_status=WorkStatus.WORKING,
            ),
            StatusTransition(
                work_session_id=9001,
                from_status=None,
                to_status="working",
                timestamp=datetime(2026, 9, 28, 9),
            ),
        ]
    )
    db.commit()

    # Every repeated external identity resolves inside its verified account.
    raw_client = scoped_client("admin")._client
    for offset in range(40):
        response = raw_client.get(
            "/api/v1/team/status",
            headers={"X-User-Id": "777", "X-Account-Id": str(1000 + offset)},
        )
        assert response.status_code == 200
        assert {row["account_id"] for row in response.json()["employees"]} == {
            1000 + offset
        }

    selects = 0

    def count_selects(_conn, _cursor, statement, *_args):
        nonlocal selects
        if statement.lstrip().upper().startswith("SELECT"):
            selects += 1

    engine = db.get_bind()
    event.listen(engine, "before_cursor_execute", count_selects)
    try:
        small = raw_client.get(
            "/api/v1/team/status",
            headers={"X-User-Id": "777", "X-Account-Id": "1000"},
        )
    finally:
        event.remove(engine, "before_cursor_execute", count_selects)
    small_selects = selects
    selects = 0
    event.listen(engine, "before_cursor_execute", count_selects)
    try:
        response = scoped_client("admin").get("/api/v1/team/status")
    finally:
        event.remove(engine, "before_cursor_execute", count_selects)
    assert small.status_code == 200
    assert response.status_code == 200
    assert len(response.json()["employees"]) == 42
    assert selects == small_selects == 6
