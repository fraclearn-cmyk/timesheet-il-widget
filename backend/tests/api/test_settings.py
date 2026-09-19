import pytest

from app.models.group_member import GroupMember
from app.models.user import User
from app.models.widget_settings import WidgetSettings


def test_admin_snapshot_is_account_scoped(scoped_client):
    response = scoped_client("admin").get("/api/v1/settings/snapshot")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"revision", "settings", "groups", "users"}
    assert {user["amocrm_user_id"] for user in body["users"]} == {101, 102, 103}
    assert all(group["account_id"] == 10 for group in body["groups"])
    assert 201 not in {user["amocrm_user_id"] for user in body["users"]}


@pytest.mark.parametrize("actor", ["employee", "manager"])
def test_snapshot_requires_live_admin_before_loading_account_data(
    scoped_client, monkeypatch, actor
):
    from app.services.settings_snapshot_service import SettingsSnapshotService

    def forbidden_load(*_args, **_kwargs):
        raise AssertionError("account data was queried before the admin check")

    monkeypatch.setattr(SettingsSnapshotService, "load", forbidden_load)

    response = scoped_client(actor).get("/api/v1/settings/snapshot")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ACCESS_DENIED"


def test_snapshot_without_settings_returns_defaults_without_writing(scoped_client, db):
    assert db.query(WidgetSettings).count() == 0

    response = scoped_client("admin").get("/api/v1/settings/snapshot")

    assert response.status_code == 200
    assert response.json()["revision"] == 1
    assert response.json()["settings"] == {
        "support_phone": None,
        "allowed_statuses": ["working", "break", "finished"],
        "default_allow_restart_session": False,
    }
    assert db.query(WidgetSettings).count() == 0


def test_snapshot_reads_persisted_account_settings(scoped_client, db):
    db.add(
        WidgetSettings(
            account_id=10,
            support_phone="+375 29 000-00-00",
            allowed_statuses=["working", "break"],
            default_allow_restart_session=True,
            revision=7,
        )
    )
    db.add(
        WidgetSettings(
            account_id=11,
            support_phone="foreign-secret-value",
            allowed_statuses=["finished"],
            revision=99,
        )
    )
    db.commit()

    response = scoped_client("admin").get("/api/v1/settings/snapshot")

    assert response.status_code == 200
    assert response.json()["revision"] == 7
    assert response.json()["settings"] == {
        "support_phone": "+375 29 000-00-00",
        "allowed_statuses": ["working", "break"],
        "default_allow_restart_session": True,
    }
    assert "foreign-secret-value" not in response.text


def test_snapshot_includes_inactive_user_only_with_historical_membership(
    scoped_client, db
):
    db.add_all(
        [
            User(
                id=5,
                amocrm_user_id=104,
                amocrm_account_id=10,
                name="Former member",
                amocrm_group_id=902,
                is_active=False,
            ),
            User(
                id=6,
                amocrm_user_id=105,
                amocrm_account_id=10,
                name="Former non-member",
                amocrm_group_id=903,
                is_active=False,
            ),
            GroupMember(
                id=2,
                account_id=10,
                group_id=10,
                user_id=5,
                is_active=False,
                track_time=True,
                hide_widget=True,
            ),
        ]
    )
    db.commit()

    response = scoped_client("admin").get("/api/v1/settings/snapshot")

    assert response.status_code == 200
    users = {row["amocrm_user_id"]: row for row in response.json()["users"]}
    assert 104 in users
    assert 105 not in users
    assert users[104]["is_active"] is False
    assert users[104]["group_id"] == 10
    assert users[104]["track_time"] is True
    assert users[104]["hide_widget"] is True
    assert db.query(GroupMember).filter_by(user_id=5).count() == 1


def test_snapshot_uses_observed_numeric_amocrm_group_labels(scoped_client):
    response = scoped_client("admin").get("/api/v1/settings/snapshot")

    assert response.status_code == 200
    users = {row["amocrm_user_id"]: row for row in response.json()["users"]}
    assert users[101]["amocrm_group_label"] == "Группа amoCRM #900"
    assert users[102]["amocrm_group_label"] == "Группа amoCRM #901"
    assert users[103]["amocrm_group_label"] == "Без группы amoCRM"


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/api/v1/settings/10"),
        ("put", "/api/v1/settings/10"),
        ("post", "/api/v1/settings/10/reset"),
    ],
)
def test_stale_account_id_settings_routes_are_retired(scoped_client, method, path):
    kwargs = {"json": {}} if method == "put" else {}
    response = getattr(scoped_client("admin"), method)(path, **kwargs)

    assert response.status_code == 404
