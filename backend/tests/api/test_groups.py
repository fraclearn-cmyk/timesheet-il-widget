import pytest

from test_settings import dump_state, snapshot_update
from app.models.user import User
from app.models.widget_group import WidgetGroup


@pytest.mark.parametrize(
    "changes,code,field,status",
    [
        ({"id": 999}, "GROUP_NOT_FOUND", "groups.0.id", 404),
        ({"id": 20}, "GROUP_NOT_FOUND", "groups.0.id", 404),
        ({"id": 10}, "GROUP_REFERENCE_DUPLICATE", "groups.1.id", 409),
        ({"name": " ZEBRA "}, "GROUP_DUPLICATE", "groups.1.name", 409),
        (
            {"timezone": "Mars/Olympus"},
            "GROUP_TIMEZONE_INVALID",
            "groups.0.timezone",
            409,
        ),
        (
            {"work_start_time": "18:00"},
            "GROUP_SCHEDULE_INVALID",
            "groups.0.work_end_time",
            409,
        ),
        (
            {"manager_amocrm_user_id": 201},
            "GROUP_MANAGER_INVALID",
            "groups.0.manager_amocrm_user_id",
            409,
        ),
        (
            {"manager_amocrm_user_id": 999},
            "GROUP_MANAGER_INVALID",
            "groups.0.manager_amocrm_user_id",
            409,
        ),
        ({"client_key": "both"}, "GROUP_REFERENCE_INVALID", "groups.0.id", 409),
    ],
)
def test_group_validation_is_atomic(scoped_client, db, changes, code, field, status):
    admin = scoped_client("admin")
    payload = snapshot_update(admin.get("/api/v1/settings/snapshot").json())
    payload["groups"][0].update(changes)
    before = dump_state(db)
    response = admin.put("/api/v1/settings/snapshot", json=payload)
    assert response.status_code == status, response.text
    assert response.json()["error"]["code"] == code
    assert response.json()["error"]["field"] == field
    assert response.json()["error"]["message"]
    assert dump_state(db) == before


@pytest.mark.parametrize("inactive", [True, False])
def test_manager_must_be_active_with_observed_role(scoped_client, db, inactive):
    if inactive:
        db.get(User, 3).is_active = False
    else:
        db.get(User, 3).amocrm_role_id = None
    db.commit()
    admin = scoped_client("admin")
    payload = snapshot_update(admin.get("/api/v1/settings/snapshot").json())
    before = dump_state(db)
    response = admin.put("/api/v1/settings/snapshot", json=payload)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "GROUP_MANAGER_INVALID"
    assert dump_state(db) == before


def test_same_group_name_in_other_account_is_allowed(scoped_client, db):
    admin = scoped_client("admin")
    payload = snapshot_update(admin.get("/api/v1/settings/snapshot").json())
    payload["groups"][0]["name"] = "Foreign"
    response = admin.put("/api/v1/settings/snapshot", json=payload)
    assert response.status_code == 200, response.text
    assert db.query(WidgetGroup).filter_by(name_key="foreign").count() == 2


@pytest.mark.parametrize(
    "reference,code",
    [
        ("id:11", "GROUP_INACTIVE"),
        ("id:20", "GROUP_NOT_FOUND"),
        ("client:missing", "GROUP_NOT_FOUND"),
    ],
)
def test_user_group_reference_must_resolve_to_active_group(
    scoped_client, db, reference, code
):
    admin = scoped_client("admin")
    payload = snapshot_update(admin.get("/api/v1/settings/snapshot").json())
    payload["users"][1]["group_ref"] = reference
    before = dump_state(db)
    response = admin.put("/api/v1/settings/snapshot", json=payload)
    assert response.status_code in (404, 409)
    assert response.json()["error"]["code"] == code
    assert response.json()["error"]["field"] == "users.1.group_ref"
    assert dump_state(db) == before


def test_duplicate_client_keys_are_rejected(scoped_client, db):
    admin = scoped_client("admin")
    payload = snapshot_update(admin.get("/api/v1/settings/snapshot").json())
    for index, group in enumerate(payload["groups"]):
        del group["id"]
        group.update(client_key="same", name=f"New {index}")
    before = dump_state(db)
    response = admin.put("/api/v1/settings/snapshot", json=payload)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "GROUP_REFERENCE_DUPLICATE"
    assert dump_state(db) == before


@pytest.mark.parametrize("key", ["", "x" * 65, "contains spaces"])
def test_new_group_client_key_is_bounded(scoped_client, db, key):
    admin = scoped_client("admin")
    payload = snapshot_update(admin.get("/api/v1/settings/snapshot").json())
    del payload["groups"][0]["id"]
    payload["groups"][0]["client_key"] = key
    before = dump_state(db)
    response = admin.put("/api/v1/settings/snapshot", json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["field"] == "groups.0.client_key"
    assert dump_state(db) == before


def test_unicode_casefold_group_names_conflict(scoped_client, db):
    admin = scoped_client("admin")
    payload = snapshot_update(admin.get("/api/v1/settings/snapshot").json())
    payload["groups"][0]["name"] = " STRAẞE "
    payload["groups"][1]["name"] = "strasse"
    before = dump_state(db)
    response = admin.put("/api/v1/settings/snapshot", json=payload)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "GROUP_DUPLICATE"
    assert dump_state(db) == before


def test_omitted_historical_group_name_remains_reserved(scoped_client, db):
    admin = scoped_client("admin")
    payload = snapshot_update(admin.get("/api/v1/settings/snapshot").json())
    payload["groups"] = [payload["groups"][1]]
    payload["groups"][0]["name"] = "ALPHA"
    before = dump_state(db)
    response = admin.put("/api/v1/settings/snapshot", json=payload)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "GROUP_DUPLICATE"
    assert dump_state(db) == before


def test_group_name_swap_is_atomic(scoped_client):
    admin = scoped_client("admin")
    payload = snapshot_update(admin.get("/api/v1/settings/snapshot").json())
    payload["groups"][0]["name"], payload["groups"][1]["name"] = "Zebra", "alpha"
    response = admin.put("/api/v1/settings/snapshot", json=payload)
    assert response.status_code == 200, response.text
    assert {g["id"]: g["name"] for g in response.json()["groups"]} == {
        10: "alpha",
        11: "Zebra",
    }


def test_groups_endpoint_matches_stably_sorted_snapshot_groups(scoped_client):
    admin = scoped_client("admin")

    snapshot = admin.get("/api/v1/settings/snapshot")
    response = admin.get("/api/v1/settings/groups")

    assert snapshot.status_code == 200
    assert response.status_code == 200
    assert response.json() == snapshot.json()["groups"]
    assert [group["id"] for group in response.json()] == [11, 10]
    assert set(response.json()[0]) == {
        "id",
        "account_id",
        "name",
        "timezone",
        "work_start_time",
        "work_end_time",
        "manager_amocrm_user_id",
        "is_active",
        "allow_restart_session",
    }
    assert response.json()[1]["manager_amocrm_user_id"] == 103


def test_users_endpoint_matches_stably_sorted_snapshot_users(scoped_client):
    admin = scoped_client("admin")

    snapshot = admin.get("/api/v1/settings/snapshot")
    response = admin.get("/api/v1/settings/users")

    assert snapshot.status_code == 200
    assert response.status_code == 200
    assert response.json() == snapshot.json()["users"]
    assert [user["amocrm_user_id"] for user in response.json()] == [101, 102, 103]
    assert set(response.json()[0]) == {
        "amocrm_user_id",
        "name",
        "email",
        "avatar_url",
        "amocrm_group_id",
        "amocrm_group_label",
        "is_active",
        "track_time",
        "hide_widget",
        "group_id",
    }


@pytest.mark.parametrize("path", ["/api/v1/settings/users", "/api/v1/settings/groups"])
@pytest.mark.parametrize("actor", ["employee", "manager"])
def test_settings_collections_require_admin_before_loading_account_data(
    scoped_client, monkeypatch, path, actor
):
    from app.services.settings_snapshot_service import SettingsSnapshotService

    def forbidden_load(*_args, **_kwargs):
        raise AssertionError("account data was queried before the admin check")

    monkeypatch.setattr(SettingsSnapshotService, "load", forbidden_load)

    response = scoped_client(actor).get(path)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ACCESS_DENIED"
