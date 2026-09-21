"""Exercise save serialization and real late rollback on disposable PostgreSQL."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from alembic import command
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.access_policy import RequestContext
from app.models.user import User
from app.models.widget_group import WidgetGroup
from app.models.widget_settings import WidgetSettings
from app.models.group_member import GroupMember
from app.schemas.settings_snapshot import SettingsSnapshotUpdate
from app.services.settings_snapshot_service import (
    SettingsProblem,
    SettingsSnapshotService,
)

# Re-export the existing fixture so both suites use the same disposable-DB policy.
from test_migrations import migrated_db as _postgres_fixture

migrated_db = _postgres_fixture


def _seed(engine, existing_settings):
    with Session(engine) as db:
        db.add_all(
            [
                User(
                    id=1,
                    amocrm_user_id=101,
                    amocrm_account_id=10,
                    name="Admin A",
                    amocrm_rights={"is_admin": True},
                ),
                User(
                    id=2,
                    amocrm_user_id=102,
                    amocrm_account_id=10,
                    name="Admin B",
                    amocrm_rights={"is_admin": True},
                ),
                User(id=3, amocrm_user_id=103, amocrm_account_id=10, name="Employee"),
            ]
        )
        if existing_settings:
            db.add(WidgetSettings(account_id=10, revision=1))
        db.commit()


def _payload(phone):
    return SettingsSnapshotUpdate.model_validate(
        {
            "revision": 1,
            "settings": {
                "support_phone": phone,
                "allowed_statuses": ["working", "break", "finished"],
                "default_allow_restart_session": False,
            },
            "groups": [
                {
                    "client_key": "sales",
                    "name": "Sales",
                    "timezone": "UTC",
                    "work_start_time": "09:00",
                    "work_end_time": "18:00",
                    "is_active": True,
                    "allow_restart_session": False,
                }
            ],
            "users": [
                {
                    "amocrm_user_id": 101,
                    "group_ref": None,
                    "track_time": False,
                    "hide_widget": False,
                },
                {
                    "amocrm_user_id": 102,
                    "group_ref": None,
                    "track_time": False,
                    "hide_widget": False,
                },
                {
                    "amocrm_user_id": 103,
                    "group_ref": "client:sales",
                    "track_time": True,
                    "hide_widget": True,
                },
            ],
        }
    )


@pytest.mark.parametrize("existing_settings", [True, False])
def test_concurrent_saves_have_one_winner(migrated_db, existing_settings):
    config, engine = migrated_db
    command.upgrade(config, "head")
    _seed(engine, existing_settings)
    ready = Barrier(2)

    def save(user_id):
        with Session(engine) as db:
            user = db.get(User, user_id)
            db.query(
                WidgetSettings
            ).all()  # an earlier read must not bypass the lock refresh
            ready.wait(timeout=10)
            try:
                snapshot = SettingsSnapshotService(db).save(
                    RequestContext(10, user), _payload(str(user_id))
                )
                return "saved", snapshot.settings.support_phone
            except SettingsProblem as problem:
                return problem.error["code"], None

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(save, [1, 2]))
    assert sorted(result[0] for result in outcomes) == [
        "SETTINGS_VERSION_CONFLICT",
        "saved",
    ]
    winner = next(phone for code, phone in outcomes if code == "saved")
    with Session(engine) as db:
        assert db.query(WidgetSettings).one().revision == 2
        assert db.query(WidgetSettings).one().support_phone == winner
        assert db.query(WidgetGroup).count() == 1
        assert db.query(GroupMember).count() == 1
        assert db.get(User, 3).hide_widget is True


def test_postgres_late_membership_failure_rolls_back_all_tables(migrated_db):
    config, engine = migrated_db
    command.upgrade(config, "head")
    _seed(engine, True)
    with engine.begin() as connection:
        connection.execute(
            text(
                """
            CREATE FUNCTION reject_test_membership() RETURNS trigger AS $$
            BEGIN RAISE EXCEPTION 'synthetic late membership failure'; END;
            $$ LANGUAGE plpgsql;
            CREATE TRIGGER reject_test_membership BEFORE INSERT ON group_members
            FOR EACH ROW EXECUTE FUNCTION reject_test_membership();
        """
            )
        )
    with Session(engine) as db:
        with pytest.raises(SettingsProblem) as failure:
            SettingsSnapshotService(db).save(
                RequestContext(10, db.get(User, 1)), _payload("must roll back")
            )
        assert failure.value.error["code"] == "SETTINGS_SAVE_CONFLICT"
        assert db.query(WidgetSettings).one().revision == 1
        assert db.query(WidgetSettings).one().support_phone is None
        assert db.query(WidgetGroup).count() == 0
        assert db.query(GroupMember).count() == 0
        assert db.get(User, 3).hide_widget is False
