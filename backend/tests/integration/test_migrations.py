"""Run against a fresh, disposable PostgreSQL database, never the application DB.

Set TEST_POSTGRES_ADMIN_URL to a PostgreSQL admin connection. Every test creates
and drops only its own UUID-suffixed database. Without an explicit URL these
tests skip, allowing contract/unit tests on machines without PostgreSQL.
"""

import os
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import User, WorkSession, WorkStatus, GroupMember, WidgetGroup, CrmEvent
from app.core.database import Base
from app.models import ActivityInterval


@pytest.fixture
def migrated_db(monkeypatch):
    admin_url = os.getenv("TEST_POSTGRES_ADMIN_URL")
    if not admin_url:
        pytest.skip("TEST_POSTGRES_ADMIN_URL required for disposable PostgreSQL tests")
    url = make_url(admin_url)
    assert url.get_backend_name() == "postgresql"
    name = "timesheet_phase1_test_" + uuid4().hex
    admin = create_engine(url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{name}"'))
    db_url = url.set(database=name)
    monkeypatch.setattr(
        settings, "DATABASE_URL", db_url.render_as_string(hide_password=False)
    )
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    config.set_main_option(
        "script_location", str(Path(__file__).resolve().parents[2] / "migrations")
    )
    engine = create_engine(db_url)
    try:
        yield config, engine
    finally:
        engine.dispose()
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
        admin.dispose()


def test_clean_upgrade_downgrade_upgrade_and_real_constraints(migrated_db):
    config, engine = migrated_db
    command.upgrade(config, "head")
    target_tables = [
        "users",
        "widget_settings",
        "widget_groups",
        "group_members",
        "work_sessions",
        "status_transitions",
        "activity_intervals",
        "crm_events",
        "call_events",
        "work_comments",
    ]
    for table_name in target_tables:
        actual = {c["name"]: c for c in inspect(engine).get_columns(table_name)}
        expected = Base.metadata.tables[table_name].columns
        assert set(actual) == set(expected.keys()), table_name
        for column in expected:
            assert actual[column.name]["nullable"] == column.nullable, (
                table_name,
                column.name,
            )
    with engine.connect() as conn:
        assert conn.scalar(text("select version_num from alembic_version")) == "005"
    assert "amocrm_user_id" in {
        c["name"] for c in inspect(engine).get_columns("work_sessions")
    }
    command.downgrade(config, "004")
    assert "user_id" in {
        c["name"] for c in inspect(engine).get_columns("work_sessions")
    }
    command.upgrade(config, "head")
    with Session(engine) as db:
        one = User(id=7, amocrm_user_id=700, amocrm_account_id=100, name="One")
        two = User(id=8, amocrm_user_id=700, amocrm_account_id=200, name="Two")
        db.add_all([one, two])
        db.commit()
        assert db.get(User, 7).role.value == "employee"
        group = WidgetGroup(
            account_id=100, name="A", manager_user_id=7, timezone="Europe/Minsk"
        )
        other = WidgetGroup(account_id=100, name="B")
        db.add_all([group, other])
        db.commit()
        for active in (False, False, True):
            db.add(
                GroupMember(
                    account_id=100, user_id=7, group_id=group.id, is_active=active
                )
            )
        db.commit()
        db.add(
            GroupMember(account_id=100, user_id=7, group_id=other.id, is_active=True)
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        db.add(GroupMember(account_id=200, user_id=8, group_id=group.id))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        work = WorkSession(amocrm_account_id=100, amocrm_user_id=700, user_name="One")
        db.add(work)
        db.commit()
        assert work.current_status is WorkStatus.WORKING
        assert work.user.id == 7
        assert [
            work.active_duration,
            work.unconfirmed_duration,
            work.break_duration,
            work.idle_duration,
        ] == [0, 0, 0, 0]
        interval = ActivityInterval(
            account_id=100,
            user_id=7,
            work_session_id=work.id,
            started_at=work.start_time,
            ended_at=work.start_time,
            kind="unconfirmed",
            source="unconfirmed_input",
            duration_source="observed",
        )
        db.add(interval)
        db.commit()
        interval.kind = "confirmed"
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        interval.source = "mouse"
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        work.active_duration = -1
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        event = CrmEvent(
            account_id=100,
            external_id="opaque-A1",
            event_type="unknown_event",
            occurred_at=work.start_time,
        )
        db.add(event)
        db.commit()
        assert event.user_id is None
        assert not event.is_complete
        assert event.occurred_at == work.start_time
        event.user_id = 7
        event.author_amocrm_user_id = 0
        event.is_complete = 1
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


def test_legacy_data_is_preserved_without_inventing_confirmed_work(migrated_db):
    config, engine = migrated_db
    command.upgrade(config, "004")
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users (id,amocrm_user_id,amocrm_account_id,name) VALUES (7,700,100,'One')"
            )
        )
        conn.execute(
            text(
                """INSERT INTO work_sessions
            (user_id,user_name,start_time,current_status,total_work_time,total_break_time,created_at,updated_at)
            VALUES (700,'One','2026-09-16 08:00:00','working',120,30,now(),now())"""
            )
        )
        conn.execute(
            text(
                """INSERT INTO crm_events
            (account_id,source_event_id,user_id,event_type,occurred_at,created_at)
            VALUES (100,'opaque-A1',0,'system',now(),now())"""
            )
        )
        conn.execute(
            text(
                """INSERT INTO activity_sessions
            (work_session_id,entity_type,entity_id,start_time,created_at,updated_at)
            SELECT id,'lead',1001,start_time,now(),now() FROM work_sessions"""
            )
        )
        conn.execute(
            text(
                """INSERT INTO activity_events
            (activity_session_id,event_type,timestamp,created_at)
            SELECT id,'card_updated',now(),now() FROM activity_sessions"""
            )
        )
    command.upgrade(config, "head")
    with Session(engine) as db:
        work = db.query(WorkSession).one()
        assert work.amocrm_account_id == 100
        assert work.amocrm_user_id == 700
        assert work.active_duration == 0
        assert work.unconfirmed_duration == 120
        assert work.break_duration == 30
        assert work.activity_sessions[0].entity_type.value == "lead"
        assert (
            work.activity_sessions[0].activity_events[0].event_type.value
            == "card_updated"
        )
        event = db.query(CrmEvent).one()
        assert event.user_id is None
        assert not event.is_complete
        assert event.external_id == "opaque-A1"
    command.downgrade(config, "004")
    with engine.connect() as conn:
        assert conn.scalar(text("select user_id from work_sessions")) == 700
        assert conn.scalar(text("select user_id from crm_events")) == 0
    command.upgrade(config, "head")


def test_unattributable_legacy_session_aborts_upgrade_without_data_loss(migrated_db):
    config, engine = migrated_db
    command.upgrade(config, "004")
    with engine.begin() as conn:
        conn.execute(
            text(
                """INSERT INTO work_sessions
            (user_id,user_name,start_time,created_at,updated_at)
            VALUES (999,'Unknown',now(),now(),now())"""
            )
        )
    with pytest.raises(Exception, match="unmapped legacy work_sessions"):
        command.upgrade(config, "head")
    with engine.connect() as conn:
        assert conn.scalar(text("select version_num from alembic_version")) == "004"
        assert conn.scalar(text("select user_id from work_sessions")) == 999


def test_downgrade_refuses_to_erase_membership_history(migrated_db):
    config, engine = migrated_db
    command.upgrade(config, "head")
    with Session(engine) as db:
        db.add(User(id=7, amocrm_account_id=100, amocrm_user_id=700, name="One"))
        db.commit()
        group = WidgetGroup(account_id=100, name="A")
        db.add(group)
        db.commit()
        db.add_all(
            [
                GroupMember(
                    account_id=100, user_id=7, group_id=group.id, is_active=False
                ),
                GroupMember(
                    account_id=100, user_id=7, group_id=group.id, is_active=True
                ),
            ]
        )
        db.commit()
    with pytest.raises(RuntimeError, match="membership history"):
        command.downgrade(config, "004")
    with engine.connect() as conn:
        assert conn.scalar(text("select version_num from alembic_version")) == "005"
        assert conn.scalar(text("select count(*) from group_members")) == 2
