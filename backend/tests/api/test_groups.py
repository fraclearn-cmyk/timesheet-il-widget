import pytest


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
