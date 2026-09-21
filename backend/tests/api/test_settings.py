import pytest

from app.models.group_member import GroupMember
from app.models.user import User
from app.models.widget_settings import WidgetSettings
from app.models.widget_group import WidgetGroup


def snapshot_update(body):
    """Project the public read snapshot onto editable fields."""
    return {
        "revision": body["revision"],
        "settings": body["settings"],
        "groups": [
            {key: value for key, value in group.items() if key != "account_id"}
            for group in body["groups"]
        ],
        "users": [
            {
                "amocrm_user_id": user["amocrm_user_id"],
                "track_time": user["track_time"],
                "hide_widget": user["hide_widget"],
                "group_ref": f"id:{user['group_id']}" if user["group_id"] else None,
            }
            for user in body["users"]
        ],
    }


def dump_state(db):
    return {
        model.__tablename__: [
            tuple(getattr(row, column.name) for column in model.__table__.columns)
            for row in db.query(model).order_by(model.id)
        ]
        for model in (WidgetSettings, WidgetGroup, GroupMember, User)
    }


@pytest.fixture
def valid_snapshot(scoped_client):
    return snapshot_update(
        scoped_client("admin").get("/api/v1/settings/snapshot").json()
    )


def test_save_is_atomic_when_one_user_has_no_group(scoped_client, db, valid_snapshot):
    before = dump_state(db)
    valid_snapshot["settings"]["support_phone"] = "+375 29 000-00-00"
    valid_snapshot["users"][0].update(track_time=True, group_ref=None)
    response = scoped_client("admin").put(
        "/api/v1/settings/snapshot", json=valid_snapshot
    )
    assert response.status_code == 409
    assert response.json()["error"] == {
        "code": "TRACKED_USER_GROUP_REQUIRED",
        "message": "Для учёта сотруднику нужно назначить группу.",
        "field": "users.0.group_ref",
    }
    assert dump_state(db) == before


def test_stale_revision_does_not_overwrite(scoped_client, db, valid_snapshot):
    admin = scoped_client("admin")
    first = admin.put("/api/v1/settings/snapshot", json=valid_snapshot)
    assert first.status_code == 200
    assert first.json()["revision"] == 2
    before = dump_state(db)
    valid_snapshot["settings"]["support_phone"] = "stale"
    second = admin.put("/api/v1/settings/snapshot", json=valid_snapshot)
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "SETTINGS_VERSION_CONFLICT"
    assert dump_state(db) == before


@pytest.mark.parametrize("actor", ["employee", "manager"])
def test_save_requires_admin(scoped_client, db, valid_snapshot, actor):
    before = dump_state(db)
    response = scoped_client(actor).put(
        "/api/v1/settings/snapshot", json=valid_snapshot
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ACCESS_DENIED"
    assert dump_state(db) == before


def test_save_requires_verified_identity(scoped_client, db, valid_snapshot):
    before = dump_state(db)
    response = scoped_client("admin").put(
        "/api/v1/settings/snapshot",
        json=valid_snapshot,
        headers={"X-User-Id": "", "X-Account-Id": ""},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AMOCRM_TOKEN_EXPIRED"
    assert dump_state(db) == before


def test_body_account_cannot_replace_verified_account(
    scoped_client, db, valid_snapshot
):
    valid_snapshot["account_id"] = 11
    before = dump_state(db)
    response = scoped_client("admin").put(
        "/api/v1/settings/snapshot", json=valid_snapshot
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
    assert dump_state(db) == before


def test_canonical_repeat_does_not_duplicate_groups_or_memberships(
    scoped_client, db, valid_snapshot
):
    admin = scoped_client("admin")
    valid_snapshot["groups"].append(
        {
            "client_key": "sales",
            "name": " Sales ",
            "timezone": "Europe/Minsk",
            "work_start_time": "09:00",
            "work_end_time": "18:00",
            "manager_amocrm_user_id": 103,
            "is_active": True,
            "allow_restart_session": True,
        }
    )
    valid_snapshot["users"][1]["group_ref"] = "client:sales"
    first = admin.put("/api/v1/settings/snapshot", json=valid_snapshot)
    assert first.status_code == 200, first.text
    group = db.query(WidgetGroup).filter_by(account_id=10, name_key="sales").one()
    assert (group.name, group.manager_user_id, group.manager_role_id) == (
        "Sales",
        3,
        77,
    )
    before_ids = [row.id for row in db.query(GroupMember).order_by(GroupMember.id)]
    second = admin.put("/api/v1/settings/snapshot", json=snapshot_update(first.json()))
    assert second.status_code == 200, second.text
    assert db.query(WidgetGroup).count() == 4
    assert [
        row.id for row in db.query(GroupMember).order_by(GroupMember.id)
    ] == before_ids
    assert db.query(GroupMember).filter_by(user_id=2, is_active=True).count() == 1
    assert db.get(GroupMember, 1).is_active is False
    assert db.get(GroupMember, 1).group_id == 10
    assert second.json()["revision"] == 3


@pytest.mark.parametrize("track_time", [True, False])
def test_hide_widget_is_independent_and_restored(
    scoped_client, db, valid_snapshot, track_time
):
    valid_snapshot["users"][1].update(track_time=track_time, hide_widget=True)
    response = scoped_client("admin").put(
        "/api/v1/settings/snapshot", json=valid_snapshot
    )
    assert response.status_code == 200, response.text
    body = scoped_client("admin").get("/api/v1/settings/snapshot").json()
    employee = next(user for user in body["users"] if user["amocrm_user_id"] == 102)
    assert (employee["track_time"], employee["hide_widget"]) == (track_time, True)
    assert db.get(GroupMember, 1).is_active is track_time
    assert db.query(GroupMember).filter_by(user_id=2).count() == 1


def test_hide_widget_without_group_is_saved(scoped_client, db, valid_snapshot):
    valid_snapshot["users"][0]["hide_widget"] = True
    response = scoped_client("admin").put(
        "/api/v1/settings/snapshot", json=valid_snapshot
    )
    assert response.status_code == 200, response.text
    admin = next(
        user for user in response.json()["users"] if user["amocrm_user_id"] == 101
    )
    assert (admin["track_time"], admin["hide_widget"], admin["group_id"]) == (
        False,
        True,
        None,
    )
    assert db.query(GroupMember).filter_by(user_id=1).count() == 0
    assert (
        scoped_client("admin").get("/api/v1/settings/snapshot").json()
        == response.json()
    )


@pytest.mark.parametrize("omit_group", [True, False])
def test_deactivation_preserves_history(scoped_client, db, valid_snapshot, omit_group):
    valid_snapshot["users"][1].update(
        track_time=False, hide_widget=True, group_ref=None
    )
    if omit_group:
        valid_snapshot["groups"] = [
            g for g in valid_snapshot["groups"] if g["id"] != 10
        ]
    else:
        next(g for g in valid_snapshot["groups"] if g["id"] == 10)["is_active"] = False
    response = scoped_client("admin").put(
        "/api/v1/settings/snapshot", json=valid_snapshot
    )
    assert response.status_code == 200, response.text
    assert db.get(WidgetGroup, 10).is_active is False
    assert db.get(GroupMember, 1).is_active is False
    assert db.get(GroupMember, 1).group_id == 10
    employee = next(
        user for user in response.json()["users"] if user["amocrm_user_id"] == 102
    )
    assert employee["track_time"] is False
    assert employee["hide_widget"] is True


def test_omitted_user_membership_is_closed(scoped_client, db, valid_snapshot):
    valid_snapshot["users"] = [
        u for u in valid_snapshot["users"] if u["amocrm_user_id"] != 102
    ]
    response = scoped_client("admin").put(
        "/api/v1/settings/snapshot", json=valid_snapshot
    )
    assert response.status_code == 200, response.text
    assert db.get(GroupMember, 1).is_active is False
    assert db.get(GroupMember, 1).track_time is False


def test_disabling_historical_tracking_without_group_restores_false(scoped_client, db):
    db.get(GroupMember, 1).is_active = False
    db.commit()
    admin = scoped_client("admin")
    payload = snapshot_update(admin.get("/api/v1/settings/snapshot").json())
    payload["users"][1].update(track_time=False, group_ref=None)
    response = admin.put("/api/v1/settings/snapshot", json=payload)
    assert response.status_code == 200, response.text
    employee = next(u for u in response.json()["users"] if u["amocrm_user_id"] == 102)
    assert employee["track_time"] is False
    assert db.query(GroupMember).filter_by(user_id=2).count() == 1


def test_repeated_disable_and_reactivation_preserve_membership_history(
    scoped_client, db, valid_snapshot
):
    admin = scoped_client("admin")
    valid_snapshot["users"][1]["track_time"] = False
    first = admin.put("/api/v1/settings/snapshot", json=valid_snapshot)
    assert first.status_code == 200
    second = admin.put("/api/v1/settings/snapshot", json=snapshot_update(first.json()))
    assert second.status_code == 200
    assert db.query(GroupMember).filter_by(user_id=2).count() == 1
    payload = snapshot_update(second.json())
    payload["users"][1]["track_time"] = True
    third = admin.put("/api/v1/settings/snapshot", json=payload)
    assert third.status_code == 200, third.text
    assert db.query(GroupMember).filter_by(user_id=2).count() == 2
    assert db.get(GroupMember, 1).is_active is False
    assert db.query(GroupMember).filter_by(user_id=2, is_active=True).count() == 1


@pytest.mark.parametrize("reference", [201, 999])
def test_unknown_or_foreign_user_is_rejected_atomically(
    scoped_client, db, valid_snapshot, reference
):
    valid_snapshot["users"][0]["amocrm_user_id"] = reference
    before = dump_state(db)
    response = scoped_client("admin").put(
        "/api/v1/settings/snapshot", json=valid_snapshot
    )
    assert response.status_code == 404
    assert response.json()["error"]["field"] == "users.0.amocrm_user_id"
    assert dump_state(db) == before


def test_duplicate_user_cannot_create_second_active_membership(
    scoped_client, db, valid_snapshot
):
    valid_snapshot["users"].append({**valid_snapshot["users"][1], "group_ref": "id:11"})
    before = dump_state(db)
    response = scoped_client("admin").put(
        "/api/v1/settings/snapshot", json=valid_snapshot
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "USER_DUPLICATE"
    assert dump_state(db) == before


def test_inactive_user_only_allows_unchanged_history(scoped_client, db):
    db.get(User, 2).is_active = False
    db.get(GroupMember, 1).is_active = False
    db.commit()
    admin = scoped_client("admin")
    payload = snapshot_update(admin.get("/api/v1/settings/snapshot").json())
    first = admin.put("/api/v1/settings/snapshot", json=payload)
    assert first.status_code == 200, first.text
    payload = snapshot_update(first.json())
    next(u for u in payload["users"] if u["amocrm_user_id"] == 102)[
        "hide_widget"
    ] = True
    before = dump_state(db)
    second = admin.put("/api/v1/settings/snapshot", json=payload)
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "USER_INACTIVE"
    assert dump_state(db) == before


@pytest.mark.parametrize(
    "change,field",
    [
        ({"revision": True}, "revision"),
        ({"revision": "1"}, "revision"),
        ({"settings": {"support_phone": None}}, "settings.allowed_statuses"),
        ({"unexpected": 10}, "unexpected"),
    ],
)
def test_malformed_snapshot_has_stable_field_error(
    scoped_client, db, valid_snapshot, change, field
):
    valid_snapshot.update(change)
    before = dump_state(db)
    response = scoped_client("admin").put(
        "/api/v1/settings/snapshot", json=valid_snapshot
    )
    assert response.status_code == 422
    assert response.json()["error"] == {
        "code": "SETTINGS_INVALID",
        "message": "Некорректное значение поля.",
        "field": field,
    }
    assert dump_state(db) == before


def test_database_failure_rolls_back_every_write(scoped_client, db, valid_snapshot):
    from sqlalchemy import event
    from sqlalchemy.exc import IntegrityError

    valid_snapshot["settings"]["support_phone"] = "must roll back"
    valid_snapshot["users"][1]["hide_widget"] = True
    before = dump_state(db)

    def fail_after_flush(session, flush_context):
        raise IntegrityError(
            "synthetic failure after SQL writes", {}, Exception("failure")
        )

    event.listen(db, "after_flush_postexec", fail_after_flush, once=True)
    response = scoped_client("admin").put(
        "/api/v1/settings/snapshot", json=valid_snapshot
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "SETTINGS_SAVE_CONFLICT"
    assert dump_state(db) == before


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
                hide_widget=True,
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
