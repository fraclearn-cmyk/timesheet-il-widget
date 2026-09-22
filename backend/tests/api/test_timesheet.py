from uuid import uuid4

from app.models.group_member import GroupMember


BASE = "/api/v1/timesheet"


def command(client, action, key=None, **extra):
    return client.post(f"{BASE}/{action}", json={"idempotency_key": str(key or uuid4()), **extra})


def test_no_session_returns_not_started(scoped_client):
    response = scoped_client("employee").get(f"{BASE}/my-status")
    assert response.status_code == 200
    assert response.json() == {
        "session_id": None, "status": "not_started", "started_at": None,
        "ended_at": None, "break_seconds": 0, "track_time": True,
        "hide_widget": False, "restart_allowed": False,
    }


def test_commands_follow_status_lifecycle_and_emit_utc_z(scoped_client):
    client = scoped_client("employee")
    for action, expected in [
        ("start-work", "working"), ("start-break", "on_break"),
        ("end-break", "working"), ("finish-work", "finished"),
    ]:
        response = command(client, action)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == expected
        assert isinstance(data["session_id"], int)
        assert data["started_at"].endswith("Z")
        assert "+00:00" not in data["started_at"]
        assert data["message"]
    assert data["ended_at"].endswith("Z")
    assert client.get(f"{BASE}/my-status").json()["status"] == "finished"


def test_command_requires_uuid_and_rejects_browser_identity(scoped_client):
    client = scoped_client("employee")
    assert command(client, "start-work", "not-a-uuid").status_code == 422
    for field, value in [("user_id", 101), ("account_id", 11), ("session_id", 1), ("amocrm_user_id", 101)]:
        assert command(client, "start-work", **{field: value}).status_code in {404, 422}
    assert client.get(f"{BASE}/my-status", params={"user_id": 101}).status_code == 404
    assert client.get(f"{BASE}/my-status", headers={"X-Account-Id": "11"}).status_code == 401


def test_disabled_tracking_and_hidden_widget(scoped_client, db):
    member = db.query(GroupMember).filter_by(user_id=2).one()
    member.track_time = False
    member.hide_widget = True
    db.commit()
    client = scoped_client("employee")
    status = client.get(f"{BASE}/my-status")
    assert status.status_code == 200
    assert status.json()["track_time"] is False
    assert status.json()["hide_widget"] is True
    response = command(client, "start-work")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "TRACK_TIME_DISABLED"


def test_hidden_widget_does_not_disable_server_tracking(scoped_client, db):
    member = db.query(GroupMember).filter_by(user_id=2).one()
    member.hide_widget = True
    db.commit()
    client = scoped_client("employee")
    status = client.get(f"{BASE}/my-status")
    assert status.json()["track_time"] is True
    assert status.json()["hide_widget"] is True
    assert command(client, "start-work").json()["status"] == "working"


def test_same_uuid_replays_original_response_and_different_action_conflicts(scoped_client):
    client = scoped_client("employee")
    key = uuid4()
    first = command(client, "start-work", key)
    assert first.status_code == 200
    assert command(client, "start-work", key).json() == first.json()
    conflict = command(client, "start-break", key)
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"


def test_other_user_cannot_replay_employee_key(scoped_client):
    key = uuid4()
    employee = scoped_client("employee")
    assert command(employee, "start-work", key).status_code == 200
    admin = scoped_client("admin")
    response = command(admin, "start-work", key)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "TRACK_TIME_DISABLED"


def test_invalid_transition_has_stable_conflict_code(scoped_client):
    response = command(scoped_client("employee"), "end-break")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "STATUS_TRANSITION_INVALID"
