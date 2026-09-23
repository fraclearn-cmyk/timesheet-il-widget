"""PostgreSQL-backed contracts for authoritative amoCRM event polling."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
import importlib
import logging
from threading import Barrier, Event
from typing import Any, Mapping

from alembic import command
import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.amocrm_client import (
    AmoCRMClient,
    AmoCRMClientError,
    AmoCRMRateLimited,
)
from app.integrations.oauth import OAuthService
from app.models import (
    CrmEvent,
    EventTypeCatalog,
    IngestionCursor,
    OAuthConnection,
    RawIngestionEvent,
    User,
)
from test_migrations import migrated_db as _postgres_fixture


migrated_db = _postgres_fixture
ACCOUNT_URL = "https://example.amocrm.ru"
ACCOUNT_ID = 108
EVENT_TIME = 1_790_154_000


def utc(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute)


def run(awaitable):
    return asyncio.run(awaitable)


def service_type():
    return importlib.import_module(
        "app.services.event_ingestion_service"
    ).EventIngestionService


def event(
    event_id: str,
    *,
    event_type: str = "lead_status_changed",
    created_at: int = EVENT_TIME,
    created_by: int = 456,
    account_id: int = ACCOUNT_ID,
    **extra: Any,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": event_id,
        "type": event_type,
        "created_at": created_at,
        "created_by": created_by,
        "account_id": account_id,
        "entity_id": 1001,
        "entity_type": "lead",
        "_links": {"self": {"href": f"{ACCOUNT_URL}/api/v4/events/{event_id}"}},
        "_embedded": {
            "account": {"id": account_id},
            "entity": {
                "id": 1001,
                "_links": {"self": {"href": f"{ACCOUNT_URL}/api/v4/leads/1001"}},
            },
        },
    }
    payload.update(extra)
    return payload


def add_account(db: Session, *, account_id: int = ACCOUNT_ID) -> OAuthConnection:
    connection = OAuthConnection(
        account_id=account_id,
        account_url=ACCOUNT_URL,
        encrypted_access_token="encrypted-access-1",
        encrypted_refresh_token="encrypted-refresh",
        is_active=True,
    )
    db.add(connection)
    db.commit()
    return connection


class FakeOAuth:
    def __init__(self) -> None:
        self.loaded: list[str] = []
        self.refreshes = 0

    def load_access_token(self, connection: OAuthConnection) -> str:
        self.loaded.append(connection.encrypted_access_token)
        return (
            "access-2"
            if connection.encrypted_access_token == "encrypted-access-2"
            else "access-1"
        )

    def refresh(self, connection: OAuthConnection) -> OAuthConnection:
        self.refreshes += 1
        connection.encrypted_access_token = "encrypted-access-2"
        return connection


class PagingClient:
    def __init__(self, pages: list[list[Mapping[str, Any]]]) -> None:
        self.pages = pages
        self.catalog_calls = 0
        self.event_calls: list[tuple[int, str | None, str]] = []
        self._poll = -1

    async def list_event_types(self, account_url: str, access_token: str):
        self.catalog_calls += 1
        return [("lead_status_changed", "Lead status changed")]

    async def list_events_page(
        self,
        account_url: str,
        access_token: str,
        *,
        created_from: int,
        page_url: str | None = None,
    ):
        page_type = importlib.import_module(
            "app.integrations.amocrm_client"
        ).AmoCRMEventPage
        if page_url is None:
            self._poll += 1
            page_number = 0
        else:
            page_number = 1
        self.event_calls.append((created_from, page_url, access_token))
        items = self.pages[min(page_number, len(self.pages) - 1)]
        next_url = (
            f"{ACCOUNT_URL}/api/v4/events?limit=100&page=2"
            if page_number == 0 and len(self.pages) > 1
            else None
        )
        return page_type(items=items, next_url=next_url)


class BlockingEventsClient(PagingClient):
    def __init__(self, items: list[Mapping[str, Any]]) -> None:
        super().__init__([items])
        self.started = Event()
        self.release = Event()

    async def list_events_page(
        self,
        account_url: str,
        access_token: str,
        *,
        created_from: int,
        page_url: str | None = None,
    ):
        self.started.set()
        while not self.release.is_set():
            await asyncio.sleep(0.01)
        return await super().list_events_page(
            account_url,
            access_token,
            created_from=created_from,
            page_url=page_url,
        )


class LaterPageFailureClient(PagingClient):
    def __init__(self) -> None:
        super().__init__([[event("newer", created_at=EVENT_TIME + 100)]])
        self.traversal = 0

    async def list_events_page(
        self,
        account_url: str,
        access_token: str,
        *,
        created_from: int,
        page_url: str | None = None,
    ):
        page_type = importlib.import_module(
            "app.integrations.amocrm_client"
        ).AmoCRMEventPage
        self.event_calls.append((created_from, page_url, access_token))
        if page_url is None:
            self.traversal += 1
            return page_type(
                items=(event("newer", created_at=EVENT_TIME + 100),),
                next_url=f"{ACCOUNT_URL}/api/v4/events?limit=100&page=2",
            )
        if self.traversal == 1:
            raise RuntimeError("synthetic later-page failure")
        return page_type(
            items=(event("older", created_at=EVENT_TIME + 10),),
            next_url=None,
        )


class AccountMismatchCursorClient(PagingClient):
    def __init__(self) -> None:
        super().__init__([[]])
        self.poll = 0

    async def list_events_page(
        self,
        account_url: str,
        access_token: str,
        *,
        created_from: int,
        page_url: str | None = None,
    ):
        page_type = importlib.import_module(
            "app.integrations.amocrm_client"
        ).AmoCRMEventPage
        self.poll += 1
        self.event_calls.append((created_from, page_url, access_token))
        if self.poll == 1:
            items = (
                event(
                    "foreign-future",
                    created_at=EVENT_TIME + 10_000,
                    account_id=999,
                ),
                event("legitimate-1", created_at=EVENT_TIME),
            )
        else:
            candidate = event("legitimate-2", created_at=EVENT_TIME + 1)
            items = (candidate,) if candidate["created_at"] >= created_from else ()
        return page_type(items=items, next_url=None)


def build_service(db: Session, client, oauth: FakeOAuth | None = None, **kwargs):
    return service_type()(
        db,
        client,
        oauth or FakeOAuth(),
        owner=kwargs.pop("owner", "worker-1"),
        **kwargs,
    )


def test_event_page_uses_bounded_query_and_returns_trusted_next_link() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "_embedded": {"events": [{"id": "a"}, {"id": "b"}]},
                "_links": {
                    "next": {"href": f"{ACCOUNT_URL}/api/v4/events?limit=100&page=2"}
                },
            },
            request=request,
        )

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            client = AmoCRMClient(http)
            return await client.list_events_page(
                ACCOUNT_URL, "token", created_from=1_790_150_400
            )

    page = run(scenario())

    assert [item["id"] for item in page.items] == ["a", "b"]
    assert page.next_url == f"{ACCOUNT_URL}/api/v4/events?limit=100&page=2"
    assert requests[0].headers["Authorization"] == "Bearer token"
    assert requests[0].url.params["limit"] == "100"
    assert requests[0].url.params["filter[created_at][from]"] == "1790150400"


@pytest.mark.parametrize(
    "next_url",
    [
        "http://example.amocrm.ru/api/v4/events?page=2",
        "https://user@example.amocrm.ru/api/v4/events?page=2",
        "https://other.amocrm.ru/api/v4/events?page=2",
        "https://example.amocrm.ru/api/v4/users?page=2",
        "https://example.amocrm.ru/api/v4/events?page=2#fragment",
    ],
)
def test_event_page_rejects_untrusted_returned_next_link(next_url: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "_embedded": {"events": []},
                "_links": {"next": {"href": next_url}},
            },
            request=request,
        )

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            with pytest.raises(AmoCRMClientError, match="next"):
                await AmoCRMClient(http).list_events_page(
                    ACCOUNT_URL, "token", created_from=1
                )

    run(scenario())


def test_event_page_rejects_untrusted_requested_page_before_sending_token() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={}, request=request)

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            with pytest.raises(AmoCRMClientError, match="page URL"):
                await AmoCRMClient(http).list_events_page(
                    ACCOUNT_URL,
                    "token",
                    created_from=1,
                    page_url="https://attacker.invalid/api/v4/events?page=2",
                )

    run(scenario())
    assert calls == 0


def test_event_page_caps_page_and_item_budgets() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"_embedded": {"events": [{"id": "a"}, {"id": "b"}]}},
            request=request,
        )

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            client = AmoCRMClient(http, max_pages=2, max_items=1)
            with pytest.raises(AmoCRMClientError, match="item budget"):
                await client.list_events_page(ACCOUNT_URL, "token", created_from=1)
            with pytest.raises(AmoCRMClientError, match="page budget"):
                await client.list_events_page(
                    ACCOUNT_URL,
                    "token",
                    created_from=1,
                    page_url=f"{ACCOUNT_URL}/api/v4/events?page=3",
                )

    run(scenario())


def test_event_page_returns_empty_final_page_for_204() -> None:
    async def scenario():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(204, request=request)
            )
        ) as http:
            return await AmoCRMClient(http).list_events_page(
                ACCOUNT_URL, "token", created_from=1
            )

    assert run(scenario()).items == ()
    assert run(scenario()).next_url is None


def test_event_page_preserves_retry_after_behavior() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(429, headers={"Retry-After": "0"}, request=request)

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            with pytest.raises(AmoCRMRateLimited):
                await AmoCRMClient(http, max_retries=1).list_events_page(
                    ACCOUNT_URL, "token", created_from=1
                )

    run(scenario())
    assert calls == 2


def test_event_type_catalog_is_parsed_as_key_label_pairs() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "_embedded": {
                    "events_types": [
                        {"key": "lead_added", "lang": "Lead added", "type": 1},
                        {"key": "task_completed", "lang": None, "type": 9},
                    ]
                }
            },
            request=request,
        )

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            return await AmoCRMClient(http).list_event_types(ACCOUNT_URL, "token")

    assert run(scenario()) == (
        ("lead_added", "Lead added"),
        ("task_completed", None),
    )


def test_oauth_access_loader_decrypts_only_access_token() -> None:
    decrypted: list[str] = []

    class Cipher:
        def decrypt(self, value: str) -> str:
            decrypted.append(value)
            return "plain-access"

    connection = OAuthConnection(
        account_id=ACCOUNT_ID,
        account_url=ACCOUNT_URL,
        encrypted_access_token="encrypted-access",
        encrypted_refresh_token="encrypted-refresh",
    )

    token = OAuthService(None, None, Cipher()).load_access_token(connection)

    assert token == "plain-access"
    assert decrypted == ["encrypted-access"]


def test_polling_pages_same_timestamp_and_overlap_replay_are_deduplicated(
    migrated_db,
) -> None:
    config, engine = migrated_db
    command.upgrade(config, "head")
    first_now = utc(2026, 9, 23, 10)
    with Session(engine) as db:
        add_account(db)
        db.add(
            User(
                id=7,
                amocrm_user_id=456,
                amocrm_account_id=ACCOUNT_ID,
                name="Historical author",
                is_active=False,
            )
        )
        db.commit()
        client = PagingClient([[event("a")], [event("b")]])
        service = build_service(db, client)

        assert run(service.ingest_account(account_id=ACCOUNT_ID, now=first_now))
        assert run(
            service.ingest_account(
                account_id=ACCOUNT_ID, now=first_now + timedelta(minutes=1)
            )
        )

        assert db.query(RawIngestionEvent).count() == 2
        assert db.query(CrmEvent).count() == 2
        cursor = db.get(IngestionCursor, ACCOUNT_ID)
        assert cursor.last_event_id == "b"
        assert cursor.last_created_at == datetime.fromtimestamp(
            EVENT_TIME, UTC
        ).replace(tzinfo=None)
        assert client.event_calls[2][0] == EVENT_TIME - 2
        assert client.catalog_calls == 1
        assert {row.user_id for row in db.query(CrmEvent)} == {7}


def test_mid_page_transaction_failure_does_not_write_or_advance_cursor(
    migrated_db, caplog
) -> None:
    config, engine = migrated_db
    command.upgrade(config, "head")
    with Session(engine) as db:
        add_account(db)
        db.add(
            User(
                id=7,
                amocrm_user_id=456,
                amocrm_account_id=ACCOUNT_ID,
                name="Author",
            )
        )
        db.commit()
        bad = event("b", unserializable={"not-json"})
        service = build_service(db, PagingClient([[event("a"), bad]]))
        ingestion_logger = logging.getLogger("app.services.event_ingestion_service")
        logger_was_disabled = ingestion_logger.disabled
        ingestion_logger.disabled = False
        ingestion_logger.addHandler(caplog.handler)

        try:
            assert not run(
                service.ingest_account(account_id=ACCOUNT_ID, now=utc(2026, 9, 23, 10))
            )
        finally:
            ingestion_logger.removeHandler(caplog.handler)
            ingestion_logger.disabled = logger_was_disabled

        db.expire_all()
        assert db.query(RawIngestionEvent).count() == 0
        assert db.query(CrmEvent).count() == 0
        cursor = db.get(IngestionCursor, ACCOUNT_ID)
        assert cursor.last_created_at is None
        assert cursor.failure_count == 1
        records = [
            record
            for record in caplog.records
            if record.name == "app.services.event_ingestion_service"
        ]
        assert [record.error_code for record in records] == ["database_error"]
        assert "not-json" not in records[0].getMessage()


def test_later_page_failure_keeps_traversal_boundary_for_newer_first_retry(
    migrated_db,
) -> None:
    config, engine = migrated_db
    command.upgrade(config, "head")
    now = utc(2026, 9, 23, 10)
    seed_time = datetime.fromtimestamp(EVENT_TIME - 100, UTC).replace(tzinfo=None)
    with Session(engine) as db:
        add_account(db)
        db.add_all(
            [
                User(
                    id=7,
                    amocrm_user_id=456,
                    amocrm_account_id=ACCOUNT_ID,
                    name="Author",
                ),
                IngestionCursor(
                    account_id=ACCOUNT_ID,
                    last_created_at=seed_time,
                    last_event_id="seed",
                    next_poll_at=now,
                ),
                EventTypeCatalog(
                    account_id=ACCOUNT_ID,
                    event_key="lead_status_changed",
                    label="Lead status changed",
                    refreshed_at=now,
                ),
            ]
        )
        db.commit()
        client = LaterPageFailureClient()
        service = build_service(db, client)

        assert not run(service.ingest_account(account_id=ACCOUNT_ID, now=now))
        db.expire_all()
        cursor = db.get(IngestionCursor, ACCOUNT_ID)
        assert cursor.last_created_at == seed_time
        assert cursor.last_event_id == "seed"
        assert db.query(RawIngestionEvent).count() == 1

        assert run(
            service.ingest_account(
                account_id=ACCOUNT_ID, now=now + timedelta(minutes=1)
            )
        )
        db.expire_all()
        assert client.event_calls[2][0] == EVENT_TIME - 102
        assert {row.external_id for row in db.query(RawIngestionEvent)} == {
            "newer",
            "older",
        }
        assert {row.external_id for row in db.query(CrmEvent)} == {
            "newer",
            "older",
        }
        cursor = db.get(IngestionCursor, ACCOUNT_ID)
        assert cursor.last_created_at == datetime.fromtimestamp(
            EVENT_TIME + 100, UTC
        ).replace(tzinfo=None)
        assert cursor.last_event_id == "newer"


def test_concurrent_raw_duplicate_insert_is_conflict_safe(migrated_db) -> None:
    config, engine = migrated_db
    command.upgrade(config, "head")
    with Session(engine) as db:
        add_account(db)
        db.add(
            User(
                id=7,
                amocrm_user_id=456,
                amocrm_account_id=ACCOUNT_ID,
                name="Author",
            )
        )
        db.commit()
    barrier = Barrier(2)

    def persist(owner: str) -> bool:
        with Session(engine) as db:
            service = build_service(db, PagingClient([[event("a")]]), owner=owner)
            barrier.wait(timeout=10)
            with db.begin():
                outcome = service._persist_page(
                    account_id=ACCOUNT_ID,
                    account_url=ACCOUNT_URL,
                    known_types={"lead_status_changed"},
                    items=[event("a")],
                    now=utc(2026, 9, 23, 10),
                )
            return outcome.inserted > 0

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(persist, ("one", "two")))

    assert any(outcomes)
    with Session(engine) as db:
        assert db.query(RawIngestionEvent).count() == 1
        assert db.query(CrmEvent).count() == 1


def test_active_lease_rejects_second_owner_and_expired_lease_can_be_taken_over(
    migrated_db,
) -> None:
    config, engine = migrated_db
    command.upgrade(config, "head")
    now = utc(2026, 9, 23, 10)
    with Session(engine) as setup:
        add_account(setup)
    with Session(engine) as first, Session(engine) as second:
        service_one = build_service(first, PagingClient([[]]), owner="one")
        service_two = build_service(second, PagingClient([[]]), owner="two")

        assert service_one.acquire_lease(ACCOUNT_ID, "one", now)
        assert not service_two.acquire_lease(
            ACCOUNT_ID, "two", now + timedelta(seconds=119)
        )
        assert service_two.acquire_lease(
            ACCOUNT_ID, "two", now + timedelta(seconds=120)
        )

    with Session(engine) as db:
        cursor = db.get(IngestionCursor, ACCOUNT_ID)
        assert cursor.lease_owner == "two"
        assert cursor.lease_until == now + timedelta(seconds=240)


def test_expired_lease_takeover_fences_old_poll_before_page_persistence(
    migrated_db,
) -> None:
    config, engine = migrated_db
    command.upgrade(config, "head")
    now = utc(2026, 9, 23, 10)
    client = BlockingEventsClient([event("old-worker-event")])
    with Session(engine) as setup:
        add_account(setup)
        setup.add(
            EventTypeCatalog(
                account_id=ACCOUNT_ID,
                event_key="lead_status_changed",
                label="Lead status changed",
                refreshed_at=now,
            )
        )
        setup.commit()

    def poll_as_old_owner() -> bool:
        with Session(engine) as db:
            return run(
                build_service(
                    db,
                    client,
                    owner="worker-old",
                    lease_clock=lambda: now,
                ).ingest_account(account_id=ACCOUNT_ID, now=now)
            )

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(poll_as_old_owner)
        assert client.started.wait(timeout=10)
        with Session(engine) as takeover_db:
            takeover = build_service(
                takeover_db, PagingClient([[]]), owner="worker-new"
            )
            assert takeover.acquire_lease(
                ACCOUNT_ID,
                "worker-new-run",
                now + timedelta(seconds=120),
            )
        client.release.set()
        assert future.result(timeout=10) is False

    with Session(engine) as db:
        assert db.query(RawIngestionEvent).count() == 0
        assert db.query(CrmEvent).count() == 0
        cursor = db.get(IngestionCursor, ACCOUNT_ID)
        assert cursor.lease_owner == "worker-new-run"
        assert cursor.lease_until == now + timedelta(seconds=240)


def test_same_configured_owner_cannot_start_two_account_polls(migrated_db) -> None:
    config, engine = migrated_db
    command.upgrade(config, "head")
    now = utc(2026, 9, 23, 10)
    first_client = BlockingEventsClient([])
    with Session(engine) as setup:
        add_account(setup)
        setup.add(
            EventTypeCatalog(
                account_id=ACCOUNT_ID,
                event_key="lead_status_changed",
                label="Lead status changed",
                refreshed_at=now,
            )
        )
        setup.commit()

    def first_poll() -> bool:
        with Session(engine) as db:
            return run(
                build_service(db, first_client, owner="shared-worker").ingest_account(
                    account_id=ACCOUNT_ID, now=now
                )
            )

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(first_poll)
        assert first_client.started.wait(timeout=10)
        with Session(engine) as second_db:
            second_result = run(
                build_service(
                    second_db, PagingClient([[]]), owner="shared-worker"
                ).ingest_account(account_id=ACCOUNT_ID, now=now)
            )
        first_client.release.set()
        first_result = future.result(timeout=10)

    assert sorted((first_result, second_result)) == [False, True]


class UnauthorizedOnceClient(PagingClient):
    def __init__(self, *, always: bool = False) -> None:
        super().__init__([[]])
        self.always = always
        self.attempts = 0

    async def list_event_types(self, account_url: str, access_token: str):
        self.attempts += 1
        if self.always or self.attempts == 1:
            request = httpx.Request("GET", f"{account_url}/api/v4/events/types")
            response = httpx.Response(401, request=request)
            raise httpx.HTTPStatusError(
                "unauthorized", request=request, response=response
            )
        return await super().list_event_types(account_url, access_token)


def test_first_401_refreshes_once_and_retries_with_reloaded_access_token(
    migrated_db,
) -> None:
    config, engine = migrated_db
    command.upgrade(config, "head")
    with Session(engine) as db:
        add_account(db)
        oauth = FakeOAuth()
        client = UnauthorizedOnceClient()
        service = build_service(db, client, oauth)

        assert run(
            service.ingest_account(account_id=ACCOUNT_ID, now=utc(2026, 9, 23, 10))
        )

        assert oauth.refreshes == 1
        assert oauth.loaded[:2] == ["encrypted-access-1", "encrypted-access-2"]
        assert set(oauth.loaded[2:]) <= {"encrypted-access-2"}
        assert client.attempts == 2
        assert db.get(OAuthConnection, ACCOUNT_ID).is_active is True


def test_second_401_disables_account_and_records_backoff(migrated_db) -> None:
    config, engine = migrated_db
    command.upgrade(config, "head")
    now = utc(2026, 9, 23, 10)
    with Session(engine) as db:
        add_account(db)
        oauth = FakeOAuth()
        service = build_service(db, UnauthorizedOnceClient(always=True), oauth)

        assert not run(service.ingest_account(account_id=ACCOUNT_ID, now=now))

        db.expire_all()
        assert oauth.refreshes == 1
        assert db.get(OAuthConnection, ACCOUNT_ID).is_active is False
        cursor = db.get(IngestionCursor, ACCOUNT_ID)
        assert cursor.failure_count == 1
        assert cursor.next_poll_at > now
        assert cursor.lease_owner is None


class RateLimitedClient(PagingClient):
    async def list_event_types(self, account_url: str, access_token: str):
        raise AmoCRMRateLimited("bounded rate limit")


class UnexpectedFailureClient(PagingClient):
    async def list_events_page(
        self,
        account_url: str,
        access_token: str,
        *,
        created_from: int,
        page_url: str | None = None,
    ):
        raise RuntimeError(
            "must-not-log token=secret-token raw=personal-customer-payload"
        )


class EmptyCatalogClient(PagingClient):
    async def list_event_types(self, account_url: str, access_token: str):
        self.catalog_calls += 1
        return ()


def test_429_records_bounded_backoff_without_disabling_account(
    migrated_db, caplog
) -> None:
    config, engine = migrated_db
    command.upgrade(config, "head")
    now = utc(2026, 9, 23, 10)
    with Session(engine) as db:
        add_account(db)
        service = build_service(db, RateLimitedClient([[]]))
        ingestion_logger = logging.getLogger("app.services.event_ingestion_service")
        logger_was_disabled = ingestion_logger.disabled
        ingestion_logger.disabled = False
        ingestion_logger.addHandler(caplog.handler)

        try:
            assert not run(service.ingest_account(account_id=ACCOUNT_ID, now=now))
        finally:
            ingestion_logger.removeHandler(caplog.handler)
            ingestion_logger.disabled = logger_was_disabled

        db.expire_all()
        cursor = db.get(IngestionCursor, ACCOUNT_ID)
        assert cursor.failure_count == 1
        assert now < cursor.next_poll_at <= now + timedelta(hours=1)
        assert db.get(OAuthConnection, ACCOUNT_ID).is_active is True
        records = [
            record
            for record in caplog.records
            if record.name == "app.services.event_ingestion_service"
        ]
        assert [record.error_code for record in records] == ["amocrm_rate_limited"]


def test_unexpected_failure_logs_only_safe_stable_classification(
    migrated_db, caplog
) -> None:
    config, engine = migrated_db
    command.upgrade(config, "head")
    now = utc(2026, 9, 23, 10)
    with Session(engine) as db:
        add_account(db)
        db.add(
            EventTypeCatalog(
                account_id=ACCOUNT_ID,
                event_key="lead_status_changed",
                label="Lead status changed",
                refreshed_at=now,
            )
        )
        db.commit()
        service = build_service(db, UnexpectedFailureClient([[]]))
        ingestion_logger = logging.getLogger("app.services.event_ingestion_service")
        logger_was_disabled = ingestion_logger.disabled
        ingestion_logger.disabled = False
        ingestion_logger.addHandler(caplog.handler)

        try:
            with caplog.at_level(
                "ERROR", logger="app.services.event_ingestion_service"
            ):
                assert not run(service.ingest_account(account_id=ACCOUNT_ID, now=now))
        finally:
            ingestion_logger.removeHandler(caplog.handler)
            ingestion_logger.disabled = logger_was_disabled

        records = [
            record
            for record in caplog.records
            if record.name == "app.services.event_ingestion_service"
        ]
        assert len(records) == 1
        assert records[0].error_code == "unexpected_error"
        assert records[0].account_id == ACCOUNT_ID
        rendered = records[0].getMessage()
        assert "secret-token" not in rendered
        assert "personal-customer-payload" not in rendered
        assert rendered == "amoCRM ingestion failed"
        db.expire_all()
        assert db.get(IngestionCursor, ACCOUNT_ID).failure_count == 1


def test_incomplete_foreign_and_system_events_are_stored_without_user_attribution(
    migrated_db,
) -> None:
    config, engine = migrated_db
    command.upgrade(config, "head")
    with Session(engine) as db:
        add_account(db)
        add_account(db, account_id=999)
        db.add(
            User(
                id=9,
                amocrm_user_id=999,
                amocrm_account_id=999,
                name="Foreign account user",
            )
        )
        db.commit()
        client = PagingClient(
            [
                [
                    event("unknown", event_type="future_event"),
                    event("system", created_by=0),
                    event("foreign", created_by=999),
                    event("wrong-account", account_id=999),
                ]
            ]
        )
        service = build_service(db, client)

        assert run(
            service.ingest_account(account_id=ACCOUNT_ID, now=utc(2026, 9, 23, 10))
        )

        rows = db.scalars(select(CrmEvent).order_by(CrmEvent.external_id)).all()
        assert [row.external_id for row in rows] == [
            "foreign",
            "system",
            "unknown",
            "wrong-account",
        ]
        assert all(row.user_id is None and not row.is_complete for row in rows)
        raw = db.scalars(
            select(RawIngestionEvent).order_by(RawIngestionEvent.external_id)
        ).all()
        assert all(row.normalization_status == "incomplete" for row in raw)
        assert {row.error_code for row in raw} >= {
            "unknown_event_type",
            "invalid_author",
            "author_not_synced",
            "account_mismatch",
        }


def test_account_mismatch_future_timestamp_cannot_advance_trusted_cursor(
    migrated_db,
) -> None:
    config, engine = migrated_db
    command.upgrade(config, "head")
    now = utc(2026, 9, 23, 10)
    with Session(engine) as db:
        add_account(db)
        db.add_all(
            [
                User(
                    id=7,
                    amocrm_user_id=456,
                    amocrm_account_id=ACCOUNT_ID,
                    name="Author",
                ),
                EventTypeCatalog(
                    account_id=ACCOUNT_ID,
                    event_key="lead_status_changed",
                    label="Lead status changed",
                    refreshed_at=now,
                ),
            ]
        )
        db.commit()
        client = AccountMismatchCursorClient()
        service = build_service(db, client)

        assert run(service.ingest_account(account_id=ACCOUNT_ID, now=now))
        db.expire_all()
        cursor = db.get(IngestionCursor, ACCOUNT_ID)
        assert cursor.last_event_id == "legitimate-1"
        assert cursor.last_created_at == datetime.fromtimestamp(
            EVENT_TIME, UTC
        ).replace(tzinfo=None)

        assert run(
            service.ingest_account(
                account_id=ACCOUNT_ID, now=now + timedelta(minutes=1)
            )
        )
        db.expire_all()
        assert client.event_calls[1][0] == EVENT_TIME - 2
        assert {row.external_id for row in db.query(RawIngestionEvent)} == {
            "foreign-future",
            "legitimate-1",
            "legitimate-2",
        }
        assert db.get(IngestionCursor, ACCOUNT_ID).last_event_id == "legitimate-2"


def test_catalog_refresh_happens_no_more_than_daily(migrated_db) -> None:
    config, engine = migrated_db
    command.upgrade(config, "head")
    now = utc(2026, 9, 23, 10)
    with Session(engine) as db:
        add_account(db)
        client = PagingClient([[]])
        service = build_service(db, client)

        assert run(service.ingest_account(account_id=ACCOUNT_ID, now=now))
        assert run(
            service.ingest_account(
                account_id=ACCOUNT_ID, now=now + timedelta(hours=23, minutes=59)
            )
        )
        assert client.catalog_calls == 1
        assert run(
            service.ingest_account(account_id=ACCOUNT_ID, now=now + timedelta(days=1))
        )
        assert client.catalog_calls == 2
        assert db.query(EventTypeCatalog).count() == 1


def test_empty_successful_catalog_refresh_is_recorded_independently(
    migrated_db,
) -> None:
    config, engine = migrated_db
    command.upgrade(config, "head")
    now = utc(2026, 9, 23, 10)
    with Session(engine) as db:
        add_account(db)
        client = EmptyCatalogClient([[]])
        service = build_service(db, client)

        assert run(service.ingest_account(account_id=ACCOUNT_ID, now=now))
        assert run(
            service.ingest_account(
                account_id=ACCOUNT_ID, now=now + timedelta(minutes=1)
            )
        )

        db.expire_all()
        assert client.catalog_calls == 1
        assert db.query(EventTypeCatalog).count() == 0
        assert db.get(IngestionCursor, ACCOUNT_ID).catalog_refreshed_at == now


def test_cleanup_at_exactly_thirty_days_preserves_normalized_row(migrated_db) -> None:
    config, engine = migrated_db
    command.upgrade(config, "head")
    now = utc(2026, 9, 23, 10)
    with Session(engine) as db:
        add_account(db)
        expired = RawIngestionEvent(
            account_id=ACCOUNT_ID,
            source="crm_event",
            external_id="old",
            occurred_at=now - timedelta(days=30),
            dedup_key="a" * 64,
            payload={"id": "old"},
            received_at=now - timedelta(days=30),
            expires_at=now,
            normalization_status="incomplete",
            error_code="test",
        )
        fresh = RawIngestionEvent(
            account_id=ACCOUNT_ID,
            source="crm_event",
            external_id="fresh",
            occurred_at=now,
            dedup_key="b" * 64,
            payload={"id": "fresh"},
            received_at=now - timedelta(days=29),
            expires_at=now + timedelta(seconds=1),
            normalization_status="incomplete",
            error_code="test",
        )
        db.add_all([expired, fresh])
        db.flush()
        normalized = CrmEvent(
            account_id=ACCOUNT_ID,
            external_id="old",
            event_type="unknown",
            original_event_type=None,
            occurred_at=now - timedelta(days=30),
            raw_event_id=expired.id,
            is_complete=0,
        )
        db.add(normalized)
        db.commit()
        service = build_service(db, PagingClient([[]]))

        assert service.purge_expired_raw(now=now, batch_size=1) == 1

        db.expire_all()
        assert db.query(RawIngestionEvent).count() == 1
        assert db.query(RawIngestionEvent).one().external_id == "fresh"
        assert db.query(CrmEvent).one().raw_event_id is None
