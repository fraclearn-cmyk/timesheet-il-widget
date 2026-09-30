"""Proof that authorization and timesheet flags are read from current DB state."""

from app.core.access_policy import AccessPolicy, RequestContext
from app.models.group_member import GroupMember
from app.models.user import User, UserRole
from app.models.widget_group import WidgetGroup


REPORT_PATH = "/api/v1/reports/detailed"
REPORT_PARAMS = {"date_from": "2026-09-29", "date_to": "2026-09-29"}


def test_access_policy_isolates_repeated_external_user_id_across_forty_accounts(db):
    repeated_external_id = 777_777
    users = [
        User(
            id=10_000 + offset,
            amocrm_user_id=repeated_external_id,
            amocrm_account_id=100 + offset,
            name=f"Tenant {offset}",
            role=UserRole.ADMIN,
            amocrm_rights={"is_admin": True, "role_id": 1},
            amocrm_role_id=1,
        )
        for offset in range(40)
    ]
    db.add_all(users)
    db.commit()

    for user in users:
        context = RequestContext(account_id=user.amocrm_account_id, user=user)
        policy = AccessPolicy(db, context)
        assert policy.visible_internal_user_ids() == {user.id}
        assert policy.visible_external_user_ids() == {repeated_external_id}


def test_admin_role_change_applies_to_report_and_monitor_on_next_request(
    scoped_client, db
):
    client = scoped_client("admin")
    assert client.get(REPORT_PATH, params=REPORT_PARAMS).status_code == 200
    assert client.get("/api/v1/team/status").json()["viewer"]["role"] == "admin"

    admin = db.get(User, 1)
    admin.amocrm_rights = {"role_id": 70, "is_admin": False}
    db.commit()

    denied = client.get(REPORT_PATH, params=REPORT_PARAMS)
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "ACCESS_DENIED"
    monitor = client.get("/api/v1/team/status")
    assert monitor.status_code == 200
    assert monitor.json()["viewer"]["role"] == "employee"
    assert [row["id"] for row in monitor.json()["employees"]] == [1]


def test_manager_assignment_and_membership_changes_apply_on_next_request(
    scoped_client, db
):
    manager = scoped_client("manager")
    assert manager.get(REPORT_PATH, params=REPORT_PARAMS).status_code == 200
    assert {
        row["id"] for row in manager.get("/api/v1/team/status").json()["employees"]
    } == {
        2,
        3,
    }

    membership = db.query(GroupMember).filter_by(account_id=10, user_id=2).one()
    membership.is_active = False
    db.commit()
    monitor = manager.get("/api/v1/team/status")
    assert [row["id"] for row in monitor.json()["employees"]] == [3]
    assert (
        manager.get(REPORT_PATH, params={**REPORT_PARAMS, "user_id": 2}).status_code
        == 404
    )

    group = db.get(WidgetGroup, 10)
    group.manager_role_id = 999
    db.commit()
    denied = manager.get(REPORT_PATH, params=REPORT_PARAMS)
    assert denied.status_code == 403
    assert manager.get("/api/v1/team/status").json()["viewer"]["role"] == "employee"


def test_tracking_and_widget_flags_apply_on_next_status_request(scoped_client, db):
    employee = scoped_client("employee")
    initial = employee.get("/api/v1/timesheet/my-status")
    assert initial.status_code == 200
    assert (initial.json()["track_time"], initial.json()["hide_widget"]) == (
        True,
        False,
    )

    membership = db.query(GroupMember).filter_by(account_id=10, user_id=2).one()
    membership.track_time = False
    membership.hide_widget = True
    db.commit()

    changed = employee.get("/api/v1/timesheet/my-status")
    assert changed.status_code == 200
    assert (changed.json()["track_time"], changed.json()["hide_widget"]) == (
        False,
        True,
    )
