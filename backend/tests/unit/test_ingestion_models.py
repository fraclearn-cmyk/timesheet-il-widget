"""Persistence contracts for account-scoped phase-5 ingestion."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import Base
from app.models import (
    ActivityInterval,
    CallEvent,
    CrmEvent,
    EventTypeCatalog,
    IngestionCursor,
    OAuthConnection,
    PresenceBatch,
    RawIngestionEvent,
    User,
)


def utc(year, month, day, hour=0, minute=0):
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


@pytest.fixture
def db():
    engine = create_engine("sqlite://")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, _connection_record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all(
            [
                OAuthConnection(
                    account_id=1,
                    account_url="https://one.example.invalid",
                    encrypted_access_token="access-1",
                    encrypted_refresh_token="refresh-1",
                ),
                OAuthConnection(
                    account_id=2,
                    account_url="https://two.example.invalid",
                    encrypted_access_token="access-2",
                    encrypted_refresh_token="refresh-2",
                ),
                User(id=10, amocrm_user_id=100, amocrm_account_id=1, name="One"),
                User(id=20, amocrm_user_id=200, amocrm_account_id=2, name="Two"),
            ]
        )
        session.commit()
        yield session
    engine.dispose()


def raw_event(*, account_id=1, source="crm_event", dedup_key="a" * 64):
    return RawIngestionEvent(
        account_id=account_id,
        source=source,
        dedup_key=dedup_key,
        payload={"id": "evt"},
        received_at=utc(2026, 9, 23),
        expires_at=utc(2026, 10, 23),
        normalization_status="pending",
    )


def test_raw_event_dedup_is_account_and_source_scoped(db):
    db.add(raw_event())
    db.commit()

    db.add(raw_event())
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

    db.add_all(
        [
            raw_event(account_id=2),
            raw_event(source="call"),
        ]
    )
    db.commit()


@pytest.mark.parametrize("source", ["browser", "webhook"])
def test_raw_event_rejects_untrusted_sources(db, source):
    db.add(raw_event(source=source))
    with pytest.raises(IntegrityError):
        db.commit()


@pytest.mark.parametrize("status", ["new", "failed"])
def test_raw_event_rejects_unknown_normalization_status(db, status):
    event = raw_event()
    event.normalization_status = status
    db.add(event)
    with pytest.raises(IntegrityError):
        db.commit()


def test_cursor_defaults_and_lease_timestamps_round_trip_as_utc_naive(db):
    lease_until = utc(2026, 9, 23, 12)
    cursor = IngestionCursor(
        account_id=1,
        next_poll_at=utc(2026, 9, 23, 11),
        lease_owner="worker-1",
        lease_until=lease_until,
        webhook_key_hash="b" * 64,
        encrypted_webhook_key="encrypted-hook-key",
    )
    db.add(cursor)
    db.commit()
    db.expire_all()

    stored = db.get(IngestionCursor, 1)
    assert stored.failure_count == 0
    assert stored.lease_until == lease_until.replace(tzinfo=None)
    assert stored.next_poll_at == utc(2026, 9, 23, 11).replace(tzinfo=None)
    assert stored.webhook_key_hash == "b" * 64
    assert stored.encrypted_webhook_key == "encrypted-hook-key"


def test_webhook_hash_is_globally_unique_for_lookup(db):
    db.add_all(
        [
            IngestionCursor(
                account_id=1,
                next_poll_at=utc(2026, 9, 23),
                webhook_key_hash="c" * 64,
            ),
            IngestionCursor(
                account_id=2,
                next_poll_at=utc(2026, 9, 23),
                webhook_key_hash="c" * 64,
            ),
        ]
    )
    with pytest.raises(IntegrityError):
        db.commit()


def test_presence_command_uuid_is_unique_per_account_and_user(db):
    command_id = uuid4()
    kwargs = dict(
        account_id=1,
        user_id=10,
        command_id=command_id,
        window_started_at=utc(2026, 9, 23, 10),
        last_seen_at=utc(2026, 9, 23, 10, 1),
        signal_count=1,
    )
    db.add(PresenceBatch(**kwargs))
    db.commit()
    db.add(PresenceBatch(**kwargs))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

    db.add(
        PresenceBatch(
            **{
                **kwargs,
                "account_id": 2,
                "user_id": 20,
            }
        )
    )
    db.commit()


@pytest.mark.parametrize("signal_count", [0, 100001])
def test_presence_signal_count_is_bounded(db, signal_count):
    db.add(
        PresenceBatch(
            account_id=1,
            user_id=10,
            command_id=uuid4(),
            window_started_at=utc(2026, 9, 23),
            last_seen_at=utc(2026, 9, 23),
            signal_count=signal_count,
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()


def test_event_catalog_key_is_unique_within_an_account(db):
    db.add(
        EventTypeCatalog(
            account_id=1,
            event_key="lead_added",
            label="Lead added",
            refreshed_at=utc(2026, 9, 23),
        )
    )
    db.commit()
    db.add(
        EventTypeCatalog(
            account_id=1,
            event_key="lead_added",
            refreshed_at=utc(2026, 9, 23),
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    db.add(
        EventTypeCatalog(
            account_id=2,
            event_key="lead_added",
            refreshed_at=utc(2026, 9, 23),
        )
    )
    db.commit()


def test_call_source_identity_is_account_and_time_scoped_and_incomplete_by_default(db):
    first = CallEvent(
        account_id=1,
        source_event_id="call-1",
        occurred_at=utc(2026, 9, 23),
    )
    db.add(first)
    db.commit()
    assert first.is_complete == 0

    db.add(
        CallEvent(
            account_id=1,
            source_event_id="call-1",
            occurred_at=utc(2026, 9, 23),
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

    db.add_all(
        [
            CallEvent(
                account_id=1,
                source_event_id="call-1",
                occurred_at=utc(2026, 9, 23, 0, 1),
            ),
            CallEvent(
                account_id=2,
                source_event_id="call-1",
                occurred_at=utc(2026, 9, 23),
            ),
        ]
    )
    db.commit()


def test_raw_expiry_preserves_normalized_events_and_clears_references(db):
    crm_raw = raw_event(dedup_key="c" * 64)
    call_raw = raw_event(source="call", dedup_key="d" * 64)
    db.add_all([crm_raw, call_raw])
    db.flush()
    crm = CrmEvent(
        account_id=1,
        external_id="crm-expiry",
        author_amocrm_user_id=100,
        user_id=10,
        event_type="lead_added",
        original_event_type="lead_added",
        occurred_at=utc(2026, 9, 23),
        is_complete=1,
        raw_event_id=crm_raw.id,
    )
    call = CallEvent(
        account_id=1,
        source_event_id="call-expiry",
        author_amocrm_user_id=100,
        user_id=10,
        direction="incoming",
        occurred_at=utc(2026, 9, 23),
        duration_seconds=30,
        raw_event_id=call_raw.id,
    )
    db.add_all([crm, call])
    db.commit()

    db.delete(crm_raw)
    db.delete(call_raw)
    db.commit()
    db.refresh(crm)
    db.refresh(call)

    assert crm.raw_event_id is None
    assert call.raw_event_id is None


@pytest.mark.parametrize("duration_source", ["point", "observed", "calculated"])
def test_activity_interval_accepts_supported_duration_sources(db, duration_source):
    interval = ActivityInterval(
        account_id=1,
        user_id=10,
        started_at=utc(2026, 9, 23),
        ended_at=utc(2026, 9, 23),
        kind="unconfirmed",
        source="unconfirmed_input",
        duration_source=duration_source,
    )
    db.add(interval)
    db.commit()


def test_activity_interval_rejects_unknown_duration_source(db):
    db.add(
        ActivityInterval(
            account_id=1,
            user_id=10,
            started_at=utc(2026, 9, 23),
            ended_at=utc(2026, 9, 23),
            kind="unconfirmed",
            source="unconfirmed_input",
            duration_source="guessed",
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
