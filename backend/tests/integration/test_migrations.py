"""Run against a fresh, disposable PostgreSQL database, never the application DB.

Set TEST_POSTGRES_ADMIN_URL to a PostgreSQL admin connection. Every test creates
and drops only its own UUID-suffixed database. Without an explicit URL these
tests skip, allowing contract/unit tests on machines without PostgreSQL.
"""

import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from time import sleep
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import User, WorkSession, WorkStatus, GroupMember, WidgetGroup, CrmEvent, CallEvent, PresenceBatch, StatusTransition, OAuthConnection
from app.core.database import Base
from app.models import ActivityInterval
from app.core.access_policy import RequestContext
from app.services.timesheet_service import TimesheetConflict, TimesheetService
from app.services.activity_interval_service import ActivityIntervalService
from app.services.event_ingestion_service import EventIngestionService
from datetime import datetime, timezone
from datetime import timedelta


def test_011_backfills_group_business_date_and_rejects_duplicate_open_sessions(migrated_db):
    config, engine = migrated_db
    command.upgrade(config, "010")
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO users (id,amocrm_user_id,amocrm_account_id,name) VALUES (7,700,100,'One')"))
        conn.execute(text("INSERT INTO widget_groups (id,account_id,name,name_key,timezone,work_start_time,work_end_time,is_active,allow_restart_session,created_at,updated_at) VALUES (10,100,'Night','night','Europe/Minsk','22:00','06:00',true,false,now(),now())"))
        conn.execute(text("INSERT INTO group_members (id,account_id,group_id,user_id,track_time,hide_widget,is_active,created_at,updated_at) VALUES (20,100,10,7,true,false,true,now(),now())"))
        conn.execute(text("INSERT INTO work_sessions (id,amocrm_account_id,amocrm_user_id,user_name,start_time,end_time,current_status,created_at,updated_at) VALUES (1,100,700,'One','2026-09-21 23:00:00','2026-09-22 02:00:00','finished',now(),now())"))
    command.upgrade(config, "011")
    with engine.connect() as conn:
        assert str(conn.scalar(text("SELECT business_date FROM work_sessions WHERE id=1"))) == "2026-09-21"
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO timesheet_commands (account_id,amocrm_user_id,key,action,response,created_at) VALUES (100,700,'11111111-1111-4111-8111-111111111111','start-work','{}',now())"))
    with pytest.raises(RuntimeError, match="phase-4 data"):
        command.downgrade(config, "010")


def test_011_rejects_preexisting_duplicate_open_sessions_without_rewriting(migrated_db):
    config, engine = migrated_db
    command.upgrade(config, "010")
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO users (id,amocrm_user_id,amocrm_account_id,name) VALUES (7,700,100,'One')"))
        conn.execute(text("INSERT INTO work_sessions (id,amocrm_account_id,amocrm_user_id,user_name,start_time,current_status,created_at,updated_at) VALUES (1,100,700,'One','2026-09-21 08:00:00','working',now(),now()), (2,100,700,'One','2026-09-22 08:00:00','working',now(),now())"))
    with pytest.raises(RuntimeError, match="duplicate open work_sessions"):
        command.upgrade(config, "011")
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT version_num FROM alembic_version")) == "010"
        assert conn.scalar(text("SELECT count(*) FROM work_sessions")) == 2


def test_011_downgrade_refuses_new_session_without_command(migrated_db):
    config, engine = migrated_db
    command.upgrade(config, "011")
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO users (id,amocrm_user_id,amocrm_account_id,name) VALUES (7,700,100,'One')"))
        conn.execute(text("INSERT INTO work_sessions (amocrm_account_id,amocrm_user_id,user_name,start_time,end_time,current_status,business_date,created_at,updated_at) VALUES (100,700,'One','2026-09-22 06:00:00','2026-09-22 07:00:00','finished','2026-09-22',now(),now())"))
    with pytest.raises(RuntimeError, match="phase-4 data"):
        command.downgrade(config, "010")
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT version_num FROM alembic_version")) == "011"
        assert conn.scalar(text("SELECT count(*) FROM work_sessions")) == 1


def test_011_two_connections_competing_start_create_one_session(migrated_db):
    config, engine = migrated_db
    command.upgrade(config, "011")
    with Session(engine) as db:
        db.add(User(id=7, amocrm_user_id=700, amocrm_account_id=100, name="One"))
        db.add(WidgetGroup(id=10, account_id=100, name="Sales", timezone="UTC"))
        db.flush()
        db.add(GroupMember(account_id=100, user_id=7, group_id=10, is_active=True, track_time=True))
        db.commit()
    barrier = Barrier(2)

    def start():
        with Session(engine) as db:
            user = db.get(User, 7)
            barrier.wait(timeout=10)
            try:
                return TimesheetService(db).apply(RequestContext(100, user), "start-work", uuid4(), datetime(2026, 9, 22, 6)).status
            except TimesheetConflict as exc:
                return str(exc)

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: start(), range(2)))
    assert sorted(outcomes) == ["STATUS_TRANSITION_INVALID", "working"]
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM work_sessions")) == 1
        assert conn.scalar(text("SELECT count(*) FROM status_transitions")) == 1
        assert conn.scalar(text("SELECT count(*) FROM timesheet_commands")) == 1


def test_011_partial_unique_index_rejects_second_open_session(migrated_db):
    config, engine = migrated_db
    command.upgrade(config, "011")
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO users (id,amocrm_user_id,amocrm_account_id,name) VALUES (7,700,100,'One')"))
        conn.execute(text("INSERT INTO work_sessions (amocrm_account_id,amocrm_user_id,user_name,start_time,current_status,created_at,updated_at) VALUES (100,700,'One','2026-09-22 06:00:00','working',now(),now())"))
    with pytest.raises(IntegrityError):
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO work_sessions (amocrm_account_id,amocrm_user_id,user_name,start_time,current_status,created_at,updated_at) VALUES (100,700,'One','2026-09-22 07:00:00','working',now(),now())"))


def test_012_clean_upgrade_downgrade_upgrade(migrated_db):
    config, engine = migrated_db
    command.upgrade(config, "011")
    command.upgrade(config, "012")

    assert {
        "ingestion_cursors",
        "raw_ingestion_events",
        "event_type_catalog",
        "presence_batches",
    }.issubset(set(inspect(engine).get_table_names()))
    assert {
        "continuation_url",
        "pending_last_created_at",
        "pending_last_event_id",
    }.issubset(
        {column["name"] for column in inspect(engine).get_columns("ingestion_cursors")}
    )
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT version_num FROM alembic_version")) == "012"

    command.downgrade(config, "011")
    assert not {
        "ingestion_cursors",
        "raw_ingestion_events",
        "event_type_catalog",
        "presence_batches",
    }.intersection(set(inspect(engine).get_table_names()))
    assert "raw_event_id" not in {
        column["name"] for column in inspect(engine).get_columns("crm_events")
    }
    command.upgrade(config, "012")
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT version_num FROM alembic_version")) == "012"


def test_012_preserves_legacy_event_rows_and_backfills_original_type(migrated_db):
    config, engine = migrated_db
    command.upgrade(config, "011")
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users "
                "(id,amocrm_user_id,amocrm_account_id,name) "
                "VALUES (7,700,100,'One')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO crm_events "
                "(id,account_id,external_id,author_amocrm_user_id,user_id,event_type,"
                "occurred_at,payload,is_complete,created_at) "
                "VALUES (1,100,'crm-1',700,7,'lead_added','2026-09-23 08:00:00',"
                "'{\"legacy\": true}',1,now())"
            )
        )
        conn.execute(
            text(
                "INSERT INTO call_events "
                "(id,account_id,source_event_id,author_amocrm_user_id,user_id,direction,"
                "occurred_at,duration_seconds,payload,created_at) "
                "VALUES (1,100,'call-1',700,7,'incoming','2026-09-23 09:00:00',30,"
                "'{\"legacy\": true}',now())"
            )
        )

    command.upgrade(config, "012")
    with engine.connect() as conn:
        assert conn.execute(
            text(
                "SELECT original_event_type,raw_event_id,payload "
                "FROM crm_events WHERE id=1"
            )
        ).one() == ("lead_added", None, {"legacy": True})
        assert conn.execute(
            text(
                "SELECT raw_event_id,is_complete,payload "
                "FROM call_events WHERE id=1"
            )
        ).one() == (None, 0, {"legacy": True})

    command.downgrade(config, "011")
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT external_id FROM crm_events WHERE id=1")) == "crm-1"
        assert conn.scalar(text("SELECT source_event_id FROM call_events WHERE id=1")) == "call-1"
    command.upgrade(config, "012")
    with engine.connect() as conn:
        assert conn.scalar(
            text("SELECT original_event_type FROM crm_events WHERE id=1")
        ) == "lead_added"


def test_012_downgrade_refuses_to_erase_ingestion_data(migrated_db):
    config, engine = migrated_db
    command.upgrade(config, "012")
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO oauth_connections "
                "(account_id,account_url,encrypted_access_token,encrypted_refresh_token,"
                "is_active,created_at,updated_at) "
                "VALUES (100,'https://example.invalid','access','refresh',true,now(),now())"
            )
        )
        conn.execute(
            text(
                "INSERT INTO raw_ingestion_events "
                "(account_id,source,dedup_key,payload,received_at,expires_at,normalization_status) "
                "VALUES (100,'crm_event',:dedup,'{}',now(),now() + interval '30 days','pending')"
            ),
            {"dedup": "a" * 64},
        )

    with pytest.raises(RuntimeError, match="phase-5 ingestion data"):
        command.downgrade(config, "011")
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT version_num FROM alembic_version")) == "012"
        assert conn.scalar(text("SELECT count(*) FROM raw_ingestion_events")) == 1


def test_012_raw_expiry_preserves_normalized_events_and_clears_references(
    migrated_db,
):
    config, engine = migrated_db
    command.upgrade(config, "012")
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO oauth_connections "
                "(account_id,account_url,encrypted_access_token,encrypted_refresh_token,"
                "is_active,created_at,updated_at) "
                "VALUES (100,'https://example.invalid','access','refresh',true,now(),now())"
            )
        )
        conn.execute(
            text(
                "INSERT INTO users (id,amocrm_user_id,amocrm_account_id,name) "
                "VALUES (7,700,100,'One')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO raw_ingestion_events "
                "(id,account_id,source,external_id,occurred_at,dedup_key,payload,"
                "received_at,expires_at,normalization_status) VALUES "
                "(1,100,'crm_event','crm-1','2026-09-23 08:00:00',:crm_dedup,'{}',"
                "now(),now() + interval '30 days','complete'),"
                "(2,100,'call','call-1','2026-09-23 09:00:00',:call_dedup,'{}',"
                "now(),now() + interval '30 days','incomplete')"
            ),
            {"crm_dedup": "a" * 64, "call_dedup": "b" * 64},
        )
        conn.execute(
            text(
                "INSERT INTO crm_events "
                "(account_id,external_id,author_amocrm_user_id,user_id,event_type,"
                "original_event_type,occurred_at,is_complete,raw_event_id,created_at) "
                "VALUES (100,'crm-1',700,7,'lead_added','lead_added',"
                "'2026-09-23 08:00:00',1,1,now())"
            )
        )
        conn.execute(
            text(
                "INSERT INTO call_events "
                "(account_id,source_event_id,author_amocrm_user_id,user_id,direction,"
                "occurred_at,duration_seconds,is_complete,raw_event_id,created_at) "
                "VALUES (100,'call-1',700,7,'incoming','2026-09-23 09:00:00',"
                "30,0,2,now())"
            )
        )

        conn.execute(text("DELETE FROM raw_ingestion_events WHERE id IN (1,2)"))

        assert conn.execute(
            text("SELECT external_id,raw_event_id FROM crm_events")
        ).one() == ("crm-1", None)
        assert conn.execute(
            text("SELECT source_event_id,raw_event_id FROM call_events")
        ).one() == ("call-1", None)


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


@pytest.mark.parametrize("replay", [True, False], ids=["same_uuid", "distinct_packets"])
def test_013_concurrent_presence_serializes_replay_and_merge(migrated_db, replay):
    config, engine = migrated_db
    command.upgrade(config, "head")
    started_at = datetime(2026, 9, 23, 8)
    command_id = uuid4()
    with Session(engine) as db:
        db.add(User(id=7, amocrm_account_id=100, amocrm_user_id=700, name="One"))
        work = WorkSession(
            amocrm_account_id=100, amocrm_user_id=700, user_name="One",
            start_time=started_at, business_date=started_at.date(),
            current_status=WorkStatus.WORKING,
        )
        db.add(work)
        db.flush()
        db.add(StatusTransition(work_session_id=work.id, to_status="working", timestamp=started_at))
        db.commit()

    first_written = Event()
    second_started = Event()
    release_first = Event()

    def submit(*, first: bool):
        with Session(engine) as db:
            user = db.get(User, 7)
            if not first:
                second_started.set()
            interval = ActivityIntervalService(db).record_presence(
                account_id=100,
                user=user,
                command_id=command_id if first or replay else uuid4(),
                window_started_at=started_at if first or replay else started_at + timedelta(seconds=20),
                last_seen_at=started_at + timedelta(seconds=10 if first or replay else 30),
                signal_count=8,
                received_at=started_at + timedelta(seconds=31),
            )
            if first:
                first_written.set()
                assert release_first.wait(10)
            db.commit()
            return interval.id if interval is not None else None

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(submit, first=True)
        assert first_written.wait(10)
        second = pool.submit(submit, first=False)
        assert second_started.wait(10)
        sleep(0.2)
        release_first.set()
        assert first.result(timeout=10) == second.result(timeout=10)

    with Session(engine) as db:
        assert db.query(PresenceBatch).count() == (1 if replay else 2)
        intervals = db.query(ActivityInterval).all()
        assert len(intervals) == 1
        assert intervals[0].started_at == started_at
        assert intervals[0].ended_at == started_at + timedelta(seconds=10 if replay else 30)


@pytest.mark.parametrize("evidence", ["presence", "call"])
def test_013_activity_waits_for_finish_before_validating_working_span(migrated_db, evidence):
    config, engine = migrated_db
    command.upgrade(config, "head")
    started_at = datetime(2026, 9, 23, 8)
    with Session(engine) as db:
        db.add(User(id=7, amocrm_account_id=100, amocrm_user_id=700, name="One"))
        db.add(WidgetGroup(id=10, account_id=100, name="Sales", timezone="UTC"))
        db.flush()
        db.add(GroupMember(account_id=100, user_id=7, group_id=10, track_time=True, is_active=True))
        db.commit()
        context = RequestContext(100, db.get(User, 7))
        TimesheetService(db).apply(context, "start-work", uuid4(), started_at)
        db.add(CallEvent(
            account_id=100, source_event_id="call-racing-finish",
            author_amocrm_user_id=700, user_id=7, direction="outgoing",
            occurred_at=started_at + timedelta(seconds=20),
            duration_seconds=20, is_complete=1,
        ))
        db.commit()

    finish_ready = Event()
    presence_started = Event()
    release_finish = Event()

    def finish():
        with Session(engine) as db:
            def hold_commit(_):
                finish_ready.set()
                assert release_finish.wait(10)

            event.listen(db, "before_commit", hold_commit, once=True)
            context = RequestContext(100, db.get(User, 7))
            TimesheetService(db).apply(
                context, "finish-work", uuid4(), started_at + timedelta(seconds=30)
            )

    def incoming_activity():
        with Session(engine) as db:
            presence_started.set()
            service = ActivityIntervalService(db)
            if evidence == "call":
                interval = service.attach_call(
                    db.query(CallEvent).filter_by(source_event_id="call-racing-finish").one()
                )
            else:
                interval = service.record_presence(
                    account_id=100,
                    user=db.get(User, 7),
                    command_id=uuid4(),
                    window_started_at=started_at + timedelta(seconds=20),
                    last_seen_at=started_at + timedelta(seconds=40),
                    signal_count=8,
                    received_at=started_at + timedelta(seconds=41),
                )
            db.commit()
            return interval

    with ThreadPoolExecutor(max_workers=2) as pool:
        finishing = pool.submit(finish)
        assert finish_ready.wait(10)
        incoming = pool.submit(incoming_activity)
        assert presence_started.wait(10)
        sleep(0.2)
        release_finish.set()
        finishing.result(timeout=10)
        assert incoming.result(timeout=10) is None

    with Session(engine) as db:
        assert db.query(PresenceBatch).count() == (1 if evidence == "presence" else 0)
        assert db.query(ActivityInterval).count() == 0


@pytest.mark.parametrize("order", ["presence_first", "finish_first"])
def test_013_future_presence_never_crosses_concurrent_finish(migrated_db, order):
    config, engine = migrated_db
    command.upgrade(config, "head")
    started_at = datetime(2026, 9, 23, 8)
    finish_at = started_at + timedelta(seconds=30)
    with Session(engine) as db:
        db.add(User(id=7, amocrm_account_id=100, amocrm_user_id=700, name="One"))
        db.add(WidgetGroup(id=10, account_id=100, name="Sales", timezone="UTC"))
        db.flush()
        db.add(GroupMember(account_id=100, user_id=7, group_id=10, track_time=True, is_active=True))
        db.commit()
        TimesheetService(db).apply(
            RequestContext(100, db.get(User, 7)),
            "start-work",
            uuid4(),
            started_at,
        )

    first_ready = Event()
    second_started = Event()
    release_first = Event()

    def submit_presence():
        with Session(engine) as db:
            if order == "finish_first":
                second_started.set()
            try:
                ActivityIntervalService(db).record_presence(
                    account_id=100,
                    user=db.get(User, 7),
                    command_id=uuid4(),
                    window_started_at=started_at + timedelta(seconds=20),
                    last_seen_at=started_at + timedelta(seconds=40),
                    signal_count=8,
                    received_at=finish_at,
                )
            except ValueError:
                rejected = True
            else:
                rejected = False
            if order == "presence_first":
                first_ready.set()
                assert release_first.wait(10)
            if rejected:
                db.rollback()
            else:
                db.commit()
            return rejected

    def finish():
        with Session(engine) as db:
            if order == "finish_first":
                def hold_commit(_):
                    first_ready.set()
                    assert release_first.wait(10)

                event.listen(db, "before_commit", hold_commit, once=True)
            else:
                second_started.set()
            TimesheetService(db).apply(
                RequestContext(100, db.get(User, 7)),
                "finish-work",
                uuid4(),
                finish_at,
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(submit_presence if order == "presence_first" else finish)
        assert first_ready.wait(10)
        second = pool.submit(finish if order == "presence_first" else submit_presence)
        assert second_started.wait(10)
        sleep(0.2)
        release_first.set()
        assert first.result(timeout=10) is not False
        second_result = second.result(timeout=10)
        if order == "finish_first":
            assert second_result is True

    with Session(engine) as db:
        assert db.query(ActivityInterval).count() == 0
        work = db.query(WorkSession).one()
        late = ActivityIntervalService(db).record_presence(
            account_id=100,
            user=db.get(User, 7),
            command_id=uuid4(),
            window_started_at=started_at + timedelta(seconds=5),
            last_seen_at=started_at + timedelta(seconds=10),
            signal_count=8,
            received_at=finish_at + timedelta(seconds=1),
        )
        db.commit()
        assert late is not None
        assert late.closed_at == finish_at
        assert late.ended_at <= work.end_time


def test_013_ingestion_locks_multiple_users_in_global_order(migrated_db, monkeypatch):
    config, engine = migrated_db
    command.upgrade(config, "head")
    started_at = datetime(2026, 9, 23, 8)
    with Session(engine) as db:
        db.add(
            OAuthConnection(
                account_id=100,
                account_url="https://example.amocrm.ru",
                encrypted_access_token="test",
                encrypted_refresh_token="test",
            )
        )
        for user_id, amocrm_user_id in [(7, 700), (8, 800)]:
            db.add(User(id=user_id, amocrm_account_id=100, amocrm_user_id=amocrm_user_id, name=str(user_id)))
            work = WorkSession(
                amocrm_account_id=100,
                amocrm_user_id=amocrm_user_id,
                user_name=str(user_id),
                start_time=started_at,
                business_date=started_at.date(),
                current_status=WorkStatus.WORKING,
            )
            db.add(work)
            db.flush()
            db.add(StatusTransition(work_session_id=work.id, to_status="working", timestamp=started_at))
        db.commit()

    original_lock = ActivityIntervalService._lock_user

    def slow_after_each_user_lock(self, user):
        original_lock(self, user)
        self.db.execute(text("SELECT pg_sleep(0.2)"))

    monkeypatch.setattr(ActivityIntervalService, "_lock_user", slow_after_each_user_lock)
    start_together = Barrier(2)

    def payload(event_id, author):
        return {
            "id": event_id,
            "type": "lead_status_changed",
            "created_at": int(
                (started_at + timedelta(seconds=10))
                .replace(tzinfo=timezone.utc)
                .timestamp()
            ),
            "created_by": author,
            "account_id": 100,
            "entity_id": author,
            "entity_type": "lead",
            "_links": {"self": {"href": f"https://example.amocrm.ru/api/v4/events/{event_id}"}},
            "_embedded": {
                "account": {"id": 100},
                "entity": {
                    "id": author,
                    "_links": {"self": {"href": f"https://example.amocrm.ru/api/v4/leads/{author}"}},
                },
            },
        }

    def persist_page(authors, prefix):
        with Session(engine) as db:
            start_together.wait(10)
            with db.begin():
                return EventIngestionService(db, object(), object(), owner=prefix)._persist_page(
                    account_id=100,
                    account_url="https://example.amocrm.ru",
                    known_types={"lead_status_changed"},
                    items=[payload(f"{prefix}-{author}", author) for author in authors],
                    now=started_at + timedelta(seconds=20),
                )

    with ThreadPoolExecutor(max_workers=2) as pool:
        forward = pool.submit(persist_page, [700, 800], "forward")
        reverse = pool.submit(persist_page, [800, 700], "reverse")
        assert forward.result(timeout=15).inserted == 2
        assert reverse.result(timeout=15).inserted == 2

    with Session(engine) as db:
        assert db.query(ActivityInterval).count() == 4


def test_013_downgrade_preserves_recorded_presence_closures(migrated_db):
    config, engine = migrated_db
    command.upgrade(config, "head")
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO users (id,amocrm_user_id,amocrm_account_id,name) VALUES (7,700,100,'One')"))
        conn.execute(text("INSERT INTO work_sessions (id,amocrm_account_id,amocrm_user_id,user_name,start_time,current_status,created_at,updated_at) VALUES (1,100,700,'One','2026-09-23 08:00:00','working',now(),now())"))
        conn.execute(text("INSERT INTO activity_intervals (account_id,user_id,work_session_id,started_at,ended_at,kind,source,duration_source,closed_at,created_at) VALUES (100,7,1,'2026-09-23 08:00:00','2026-09-23 08:00:10','unconfirmed','unconfirmed_input','observed','2026-09-23 08:05:10',now())"))
    with pytest.raises(RuntimeError, match="recorded presence closure data"):
        command.downgrade(config, "012")
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM activity_intervals WHERE closed_at IS NOT NULL")) == 1


def test_clean_upgrade_downgrade_upgrade_and_real_constraints(migrated_db):
    config, engine = migrated_db
    command.upgrade(config, "head")
    target_tables = [
        "departments",
        "users",
        "widget_settings",
        "widget_groups",
        "group_members",
        "work_sessions",
        "activity_categories",
        "status_transitions",
        "activity_intervals",
        "crm_events",
        "call_events",
        "work_comments",
        "oauth_connections",
        "timesheet_commands",
        "ingestion_cursors",
        "raw_ingestion_events",
        "event_type_catalog",
        "presence_batches",
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
        assert conn.scalar(text("select version_num from alembic_version")) == "013"
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


def test_category_scope_backfills_only_unambiguous_accounts(migrated_db):
    config, engine = migrated_db
    command.upgrade(config, "006")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO users (id,amocrm_user_id,amocrm_account_id,name)
                VALUES (7,700,100,'One'), (8,800,200,'Two')
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO work_sessions
                (id,amocrm_user_id,amocrm_account_id,user_name,start_time,current_status,created_at,updated_at)
                VALUES
                (1,700,100,'One','2026-09-16 08:00:00','working',now(),now()),
                (2,800,200,'Two','2026-09-16 08:00:00','working',now(),now())
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO activity_categories
                (id,name,display_name,color,is_active,sort_order)
                VALUES
                (1,'one','One','#fff',true,0),
                (2,'ambiguous','Ambiguous','#000',true,0),
                (3,'unused','Unused','#111',true,0)
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO activity_sessions
                (id,work_session_id,entity_type,entity_id,start_time,created_at,updated_at)
                VALUES (1,1,'lead',1,'2026-09-16 08:00:00',now(),now()),
                       (2,2,'lead',2,'2026-09-16 08:00:00',now(),now())
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO activity_events
                (id,activity_session_id,event_type,timestamp,created_at,category_id)
                VALUES (1,1,'card_opened',now(),now(),1),
                       (2,1,'card_closed',now(),now(),2),
                       (3,2,'card_closed',now(),now(),2)
                """
            )
        )
    command.upgrade(config, "head")
    with engine.connect() as conn:
        rows = dict(
            conn.execute(
                text("SELECT id,account_id FROM activity_categories ORDER BY id")
            ).all()
        )
    assert rows == {1: 100, 2: None, 3: None}


def test_category_account_ownership_refuses_lossy_007_downgrade(migrated_db):
    config, engine = migrated_db
    command.upgrade(config, "head")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO activity_categories
                (id,name,display_name,color,account_id,is_active,sort_order)
                VALUES (1,'owned','Owned','#fff',100,true,0)
                """
            )
        )
    with pytest.raises(
        RuntimeError, match="explicit activity category account ownership"
    ):
        command.downgrade(config, "006")
    with engine.connect() as conn:
        assert conn.scalar(text("select version_num from alembic_version")) == "013"


def test_category_account_name_scope_allows_duplicate_names_per_account(migrated_db):
    config, engine = migrated_db
    command.upgrade(config, "head")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO activity_categories
                (id,name,display_name,color,account_id,is_active,sort_order)
                VALUES (1,'shared','One','#fff',100,true,0),
                       (2,'shared','Two','#000',200,true,0)
                """
            )
        )
    with engine.connect() as conn:
        assert conn.scalar(text("select count(*) from activity_categories")) == 2


def test_manager_role_snapshot_backfills_and_downgrade_refuses_loss(migrated_db):
    config, engine = migrated_db
    command.upgrade(config, "006")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO users
                (id,amocrm_user_id,amocrm_account_id,name,amocrm_role_id)
                VALUES (7,700,100,'Manager',77)
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO widget_groups
                (id,account_id,name,manager_user_id,timezone,work_start_time,work_end_time,created_at,updated_at)
                VALUES (1,100,'Sales',7,'UTC','09:00','18:00',now(),now())
                """
            )
        )
    command.upgrade(config, "head")
    with engine.connect() as conn:
        assert conn.scalar(text("select manager_role_id from widget_groups")) == 77
    with pytest.raises(RuntimeError, match="trusted manager role snapshots"):
        command.downgrade(config, "007")


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
        assert conn.scalar(text("select version_num from alembic_version")) == "013"
        assert conn.scalar(text("select count(*) from group_members")) == 2


def test_department_scope_backfills_only_unambiguous_accounts(migrated_db):
    config, engine = migrated_db
    command.upgrade(config, "008")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO departments
                (id,name,work_start_time,work_end_time,is_active,created_at,updated_at,timezone)
                VALUES (1,'One','09:00','18:00',true,now(),now(),'UTC'),
                       (2,'Ambiguous','09:00','18:00',true,now(),now(),'UTC'),
                       (3,'Unused','09:00','18:00',true,now(),now(),'UTC')
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO users
                (id,amocrm_user_id,amocrm_account_id,name,department_id)
                VALUES (7,700,100,'One',1), (8,800,100,'Two',2),
                       (9,900,200,'Three',2)
                """
            )
        )
    command.upgrade(config, "head")
    with engine.connect() as conn:
        rows = dict(conn.execute(text("SELECT id,account_id FROM departments")).all())
    assert rows == {1: 100, 2: None, 3: None}


def test_department_account_names_and_downgrade_are_data_safe(migrated_db):
    config, engine = migrated_db
    command.upgrade(config, "head")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO departments
                (id,name,account_id,work_start_time,work_end_time,is_active,created_at,updated_at,timezone)
                VALUES (1,'Shared',100,'09:00','18:00',true,now(),now(),'UTC'),
                       (2,'Shared',200,'09:00','18:00',true,now(),now(),'UTC')
                """
            )
        )
    with pytest.raises(RuntimeError, match="department account ownership"):
        command.downgrade(config, "008")
    with engine.connect() as conn:
        assert conn.scalar(text("select version_num from alembic_version")) == "013"
        assert conn.scalar(text("select count(*) from departments")) == 2


def test_010_backfills_defaults_and_preserves_group_membership_on_cycle(migrated_db):
    config, engine = migrated_db
    command.upgrade(config, "009")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO users (id,amocrm_user_id,amocrm_account_id,name)
                VALUES (7,700,100,'One')
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO widget_settings
                (account_id,polling_interval,inactivity_timeout,enable_activity_tracking,
                 enable_overlay_blocking,enable_auto_finish,created_at,updated_at)
                VALUES (100,15,300,true,true,false,now(),now())
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO widget_groups
                (id,account_id,name,timezone,work_start_time,work_end_time,is_active,created_at,updated_at)
                VALUES (10,100,'  STRAẞE  ','UTC','09:00','18:00',true,now(),now())
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO group_members
                (id,account_id,group_id,user_id,track_time,hide_widget,is_active,created_at,updated_at)
                VALUES (20,100,10,7,false,false,true,now(),now())
                """
            )
        )

    command.upgrade(config, "010")
    with engine.connect() as conn:
        assert conn.scalar(text("select version_num from alembic_version")) == "010"
        assert (
            conn.execute(
                text(
                    """
                SELECT support_phone, allowed_statuses, default_allow_restart_session, revision
                FROM widget_settings WHERE account_id=100
                """
                )
            ).one()
            == (None, ["working", "break", "finished"], False, 1)
        )
        assert (
            conn.execute(
                text(
                    """
                SELECT name_key, allow_restart_session
                FROM widget_groups WHERE id=10
                """
                )
            ).one()
            == ("strasse", False)
        )
        assert conn.scalar(text("select amocrm_group_id from users where id=7")) is None
        assert conn.scalar(text("select count(*) from group_members where id=20")) == 1
        with pytest.raises(IntegrityError):
            conn.execute(
                text(
                    """
                    INSERT INTO widget_groups
                    (account_id,name,name_key,timezone,work_start_time,work_end_time,
                     allow_restart_session,is_active,created_at,updated_at)
                    VALUES (100,'Duplicate','strasse','UTC','09:00','18:00',false,true,now(),now())
                    """
                )
            )

    command.downgrade(config, "009")
    with engine.connect() as conn:
        assert conn.scalar(text("select count(*) from widget_groups where id=10")) == 1
        assert conn.scalar(text("select count(*) from group_members where id=20")) == 1
    command.upgrade(config, "010")
    with engine.connect() as conn:
        assert (
            conn.scalar(text("select name_key from widget_groups where id=10"))
            == "strasse"
        )
        assert conn.scalar(text("select count(*) from group_members where id=20")) == 1


def test_010_preserves_maximum_unicode_casefold_expansion_and_account_scope(
    migrated_db,
):
    config, engine = migrated_db
    source_name = "\u0390" * 255
    expected_key = source_name.casefold()
    assert len(source_name) == 255
    assert len(expected_key) == 765
    command.upgrade(config, "009")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO widget_groups
                (id,account_id,name,timezone,work_start_time,work_end_time,is_active,created_at,updated_at)
                VALUES (10,100,:name,'UTC','09:00','18:00',true,now(),now()),
                       (11,200,:name,'UTC','09:00','18:00',true,now(),now())
                """
            ),
            {"name": source_name},
        )

    command.upgrade(config, "010")
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT account_id,name_key FROM widget_groups ORDER BY account_id")
        ).all()
        assert rows == [(100, expected_key), (200, expected_key)]
        assert (
            next(
                column
                for column in inspect(engine).get_columns("widget_groups")
                if column["name"] == "name_key"
            )["type"].length
            == 765
        )

    with pytest.raises(IntegrityError):
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO widget_groups
                    (id,account_id,name,name_key,timezone,work_start_time,work_end_time,
                     allow_restart_session,is_active,created_at,updated_at)
                    VALUES (12,100,'Duplicate',:name_key,'UTC','09:00','18:00',
                            false,true,now(),now())
                    """
                ),
                {"name_key": expected_key},
            )


def test_010_aborts_before_unique_constraint_when_normalized_names_collide(
    migrated_db,
):
    config, engine = migrated_db
    command.upgrade(config, "009")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO widget_groups
                (id,account_id,name,timezone,work_start_time,work_end_time,is_active,created_at,updated_at)
                VALUES (10,100,' Sales ','UTC','09:00','18:00',true,now(),now()),
                       (11,100,'sales','UTC','09:00','18:00',true,now(),now())
                """
            )
        )
    with pytest.raises(RuntimeError, match="normalized widget group names collide"):
        command.upgrade(config, "010")
    with engine.connect() as conn:
        assert conn.scalar(text("select version_num from alembic_version")) == "009"
        assert conn.scalar(text("select count(*) from widget_groups")) == 2


def test_010_backfills_current_hide_widget_and_refuses_loss(migrated_db):
    config, engine = migrated_db
    command.upgrade(config, "009")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
            INSERT INTO users (id,amocrm_user_id,amocrm_account_id,name)
            VALUES (7,700,100,'Active'), (8,800,100,'Historical'), (9,900,100,'Unassigned')
        """
            )
        )
        conn.execute(
            text(
                """
            INSERT INTO widget_groups
            (id,account_id,name,timezone,work_start_time,work_end_time,is_active,created_at,updated_at)
            VALUES (10,100,'Sales','UTC','09:00','18:00',true,now(),now())
        """
            )
        )
        conn.execute(
            text(
                """
            INSERT INTO group_members
            (id,account_id,group_id,user_id,track_time,hide_widget,is_active,created_at,updated_at)
            VALUES (20,100,10,7,true,true,true,now(),now()),
                   (21,100,10,7,true,false,false,now(),now()),
                   (22,100,10,8,true,true,false,now(),now())
        """
            )
        )
    command.upgrade(config, "010")
    with engine.connect() as conn:
        assert conn.execute(
            text("SELECT id,hide_widget FROM users ORDER BY id")
        ).all() == [
            (7, True),
            (8, True),
            (9, False),
        ]
    with pytest.raises(RuntimeError, match="phase-3 values"):
        command.downgrade(config, "009")
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT version_num FROM alembic_version")) == "010"
        assert conn.scalar(text("SELECT count(*) FROM group_members")) == 3


def test_010_downgrade_refuses_non_default_phase_3_values(migrated_db):
    config, engine = migrated_db
    command.upgrade(config, "010")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO users
                (id,amocrm_user_id,amocrm_account_id,name,amocrm_group_id)
                VALUES (7,700,100,'One',71)
                """
            )
        )
    with pytest.raises(RuntimeError, match="phase-3 values"):
        command.downgrade(config, "009")
    with engine.connect() as conn:
        assert conn.scalar(text("select version_num from alembic_version")) == "010"
        assert conn.scalar(text("select amocrm_group_id from users where id=7")) == 71
