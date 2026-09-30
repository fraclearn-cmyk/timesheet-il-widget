"""End-to-end recovery contracts for the durable amoCRM ingestion pipeline."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from typing import Any

from alembic import command
import httpx
import pytest
from sqlalchemy.orm import Session

from app.integrations.amocrm_client import (
    AmoCRMClient,
    AmoCRMEventPage,
    AmoCRMRateLimited,
    AmoCRMUnavailable,
)
from app.models import (
    CrmEvent,
    EventTypeCatalog,
    IngestionCursor,
    OAuthConnection,
    RawIngestionEvent,
    User,
)
from app.services.event_ingestion_service import EventIngestionService
from test_migrations import migrated_db as _postgres_fixture


migrated_db = _postgres_fixture
NOW = datetime(2026, 9, 30, 12)
EVENT_TIMESTAMP = int(NOW.replace(tzinfo=UTC).timestamp())


def run(awaitable):
    return asyncio.run(awaitable)


def event(
    account_id: int, event_id: str, *, offset: int = 0, entity_id: int | None = None
) -> dict[str, Any]:
    account_url = f"https://account-{account_id}.amocrm.ru"
    entity_id = account_id * 100 if entity_id is None else entity_id
    return {
        "id": event_id,
        "type": "lead_status_changed",
        "created_at": EVENT_TIMESTAMP + offset,
        "created_by": account_id * 10,
        "account_id": account_id,
        "entity_id": entity_id,
        "entity_type": "lead",
        "_links": {"self": {"href": f"{account_url}/api/v4/events/{event_id}"}},
        "_embedded": {
            "account": {"id": account_id},
            "entity": {
                "id": entity_id,
                "_links": {"self": {"href": f"{account_url}/api/v4/leads/{entity_id}"}},
            },
        },
    }


class PlainOAuth:
    """Test OAuth adapter that also models a single durable token rotation."""

    def __init__(self) -> None:
        self.refreshes = 0

    def load_access_token(self, connection):
        return connection.encrypted_access_token

    def snapshot_refresh(self, connection):
        return (
            connection.account_id,
            connection.encrypted_access_token,
            connection.encrypted_refresh_token,
        )

    def request_refresh(self, snapshot):
        self.refreshes += 1
        return ("access-after-refresh", "refresh-after-refresh")

    def apply_refresh(self, connection, snapshot, tokens):
        if (
            connection.encrypted_access_token != snapshot[1]
            or connection.encrypted_refresh_token != snapshot[2]
        ):
            return False
        connection.encrypted_access_token, connection.encrypted_refresh_token = tokens
        return True


def add_account(db: Session, account_id: int) -> None:
    db.add_all(
        [
            OAuthConnection(
                account_id=account_id,
                account_url=f"https://account-{account_id}.amocrm.ru",
                encrypted_access_token="access-before-refresh",
                encrypted_refresh_token="refresh-token",
                is_active=True,
            ),
            User(
                amocrm_user_id=account_id * 10,
                amocrm_account_id=account_id,
                name=f"User {account_id}",
            ),
        ]
    )


@pytest.mark.parametrize(
    ("failure", "expected_error"),
    [
        (429, AmoCRMRateLimited),
        (500, AmoCRMUnavailable),
        (503, AmoCRMUnavailable),
        ("timeout", AmoCRMUnavailable),
    ],
)
def test_amocrm_transport_bounds_every_transient_failure(failure, expected_error):
    """429, every 5xx and timeouts use exactly the configured retry budget."""
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if failure == "timeout":
            raise httpx.ReadTimeout("synthetic timeout", request=request)
        headers = {"Retry-After": "0"} if failure == 429 else {}
        return httpx.Response(failure, headers=headers, request=request)

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            with pytest.raises(expected_error):
                await AmoCRMClient(http, max_retries=1, backoff_seconds=0).get_json(
                    "https://example.amocrm.ru/api/v4/events"
                )

    run(scenario())
    assert calls == 2


class RestartablePagingClient:
    def __init__(self, account_id: int) -> None:
        self.account_id = account_id
        self.fail_page_two_once = True
        self.event_calls: list[str | None] = []

    async def list_event_types(self, account_url, access_token):
        return (("lead_status_changed", "Lead status changed"),)

    async def list_events_page(
        self, account_url, access_token, *, created_from, page_url=None
    ):
        self.event_calls.append(page_url)
        if page_url is None:
            return AmoCRMEventPage(
                items=(event(self.account_id, "newer", offset=20),),
                next_url=f"{account_url}/api/v4/events?limit=100&page=2",
            )
        if self.fail_page_two_once:
            self.fail_page_two_once = False
            raise AmoCRMUnavailable("synthetic second-page outage")
        return AmoCRMEventPage(
            items=(event(self.account_id, "older", offset=10),), next_url=None
        )


def test_later_page_failure_restarts_from_checkpoint_without_watermark_or_data_loss(
    migrated_db,
):
    """A process restart resumes page two and publishes only the complete watermark."""
    config, engine = migrated_db
    command.upgrade(config, "head")
    account_id = 701
    client = RestartablePagingClient(account_id)
    with Session(engine) as db:
        add_account(db, account_id)
        db.commit()
        first = EventIngestionService(db, client, PlainOAuth(), owner="worker-before")
        assert not run(first.ingest_account(account_id=account_id, now=NOW))
        db.expire_all()
        checkpoint = db.get(IngestionCursor, account_id)
        assert checkpoint.last_created_at is None
        assert checkpoint.last_event_id is None
        assert checkpoint.pending_last_event_id == "newer"
        assert checkpoint.continuation_url.endswith("page=2")
        assert db.query(RawIngestionEvent).count() == 1

    with Session(engine) as db:
        restarted = EventIngestionService(
            db, client, PlainOAuth(), owner="worker-after"
        )
        assert run(
            restarted.ingest_account(
                account_id=account_id, now=NOW + timedelta(minutes=1)
            )
        )
        # Replaying the complete traversal must remain exactly once.
        assert run(
            restarted.ingest_account(
                account_id=account_id, now=NOW + timedelta(minutes=2)
            )
        )

    with Session(engine) as db:
        assert {row.external_id for row in db.query(RawIngestionEvent)} == {
            "newer",
            "older",
        }
        assert {row.external_id for row in db.query(CrmEvent)} == {"newer", "older"}
        cursor = db.get(IngestionCursor, account_id)
        assert cursor.pending_last_created_at is None
        assert cursor.pending_last_event_id is None
        assert cursor.continuation_url is None
        assert cursor.last_event_id == "newer"


class RefreshThenBlockClient:
    def __init__(self, account_id: int) -> None:
        self.account_id = account_id
        self.unauthorized = True
        self.block = True
        self.started = asyncio.Event()

    async def list_event_types(self, account_url, access_token):
        if self.unauthorized:
            self.unauthorized = False
            request = httpx.Request("GET", f"{account_url}/api/v4/events/types")
            response = httpx.Response(401, request=request)
            raise httpx.HTTPStatusError(
                "unauthorized", request=request, response=response
            )
        return (("lead_status_changed", "Lead status changed"),)

    async def list_events_page(
        self, account_url, access_token, *, created_from, page_url=None
    ):
        if self.block:
            self.started.set()
            await asyncio.Event().wait()
        return AmoCRMEventPage(
            items=(event(self.account_id, "after-restart"),), next_url=None
        )


def test_oauth_rotation_cancellation_and_lease_takeover_survive_worker_restart(
    migrated_db,
):
    """A cancelled worker leaves the rotated token usable by the takeover worker."""
    config, engine = migrated_db
    command.upgrade(config, "head")
    account_id = 702
    client = RefreshThenBlockClient(account_id)
    oauth = PlainOAuth()
    with Session(engine) as db:
        add_account(db, account_id)
        db.commit()

    async def cancel_first_worker():
        with Session(engine) as db:
            service = EventIngestionService(db, client, oauth, owner="cancelled")
            task = asyncio.create_task(
                service.ingest_account(account_id=account_id, now=NOW)
            )
            await asyncio.wait_for(client.started.wait(), timeout=1)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

    run(cancel_first_worker())
    with Session(engine) as db:
        connection = db.get(OAuthConnection, account_id)
        cursor = db.get(IngestionCursor, account_id)
        assert connection.encrypted_access_token == "access-after-refresh"
        assert connection.encrypted_refresh_token == "refresh-after-refresh"
        assert connection.is_active is True
        assert cursor.lease_owner is None
        assert cursor.failure_count == 1
        assert db.query(RawIngestionEvent).count() == 0

        # Model a hard process loss after it acquired the next lease. The new
        # process must take over only after the durable lease expires.
        cursor.lease_owner = "dead-worker-run"
        cursor.lease_until = NOW + timedelta(seconds=30)
        db.commit()

    client.block = False
    with Session(engine) as db:
        takeover = EventIngestionService(db, client, oauth, owner="restarted")
        assert run(
            takeover.ingest_account(
                account_id=account_id, now=NOW + timedelta(minutes=1)
            )
        )
        assert db.query(RawIngestionEvent).count() == 1
        assert db.query(CrmEvent).count() == 1
        assert db.get(IngestionCursor, account_id).last_event_id == "after-restart"
    assert oauth.refreshes == 1


class FortyAccountReplayClient:
    def __init__(self) -> None:
        self.attempts = defaultdict(int)

    async def list_event_types(self, account_url, access_token):
        return (("lead_status_changed", "Lead status changed"),)

    async def list_events_page(
        self, account_url, access_token, *, created_from, page_url=None
    ):
        account_id = int(account_url.split("account-", 1)[1].split(".", 1)[0])
        self.attempts[account_id] += 1
        if self.attempts[account_id] == 1:
            raise AmoCRMUnavailable("synthetic account outage")
        return AmoCRMEventPage(
            items=(event(account_id, "shared-event", entity_id=999),), next_url=None
        )


def test_retry_and_replay_are_exactly_once_across_forty_isolated_accounts(
    migrated_db,
):
    """Every tenant recovers independently and replay cannot cross or duplicate data."""
    config, engine = migrated_db
    command.upgrade(config, "head")
    account_ids = list(range(801, 841))
    client = FortyAccountReplayClient()
    with Session(engine) as db:
        for account_id in account_ids:
            add_account(db, account_id)
        db.commit()

    def poll(account_id: int, attempt: int) -> bool:
        with Session(engine) as db:
            return run(
                EventIngestionService(
                    db, client, PlainOAuth(), owner=f"worker-{attempt}-{account_id}"
                ).ingest_account(
                    account_id=account_id, now=NOW + timedelta(minutes=attempt)
                )
            )

    with ThreadPoolExecutor(max_workers=8) as pool:
        first = list(pool.map(lambda account_id: poll(account_id, 0), account_ids))
    assert first == [False] * 40

    with ThreadPoolExecutor(max_workers=8) as pool:
        recovered = list(pool.map(lambda account_id: poll(account_id, 1), account_ids))
        replayed = list(pool.map(lambda account_id: poll(account_id, 2), account_ids))
    assert recovered == [True] * 40
    assert replayed == [True] * 40

    with Session(engine) as db:
        raw = db.query(RawIngestionEvent).all()
        normalized = db.query(CrmEvent).all()
        assert len(raw) == len(normalized) == 40
        assert {(row.account_id, row.external_id) for row in raw} == {
            (account_id, "shared-event") for account_id in account_ids
        }
        assert {(row.account_id, row.external_id) for row in normalized} == {
            (account_id, "shared-event") for account_id in account_ids
        }
        assert all(
            db.get(IngestionCursor, account_id).last_event_id == "shared-event"
            for account_id in account_ids
        )
