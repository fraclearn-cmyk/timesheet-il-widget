import asyncio
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
import hashlib
import threading
import time

import pytest
from alembic import command
from sqlalchemy.orm import Session

from app.services.ingestion_worker import IngestionWorker

from test_migrations import migrated_db as _postgres_fixture


migrated_db = _postgres_fixture


class FakeClock:
    def __init__(self):
        self.now = datetime(2026, 9, 23, 9)

    def __call__(self):
        return self.now


class FakeService:
    def __init__(self):
        self.due = {10: datetime(2026, 9, 23, 9)}
        self.ingested = []
        self.cleaned = []
        self.active = set()
        self.max_parallel = 0
        self.fail = False
        self.cleanup_results = []
        self.cleanup_error = None
        self.cleanup_calls = 0
        self.blocked_account = None
        self.blocked_accounts = set()
        self.block_started = asyncio.Event()
        self.block_release = asyncio.Event()

    def due_accounts(self, now):
        return [account for account, due in self.due.items() if due <= now]

    async def ingest_account(self, *, account_id, now):
        if account_id in self.active:
            return False
        self.active.add(account_id)
        self.max_parallel = max(self.max_parallel, len(self.active))
        if account_id == self.blocked_account or account_id in self.blocked_accounts:
            self.block_started.set()
            await self.block_release.wait()
        await asyncio.sleep(0)
        self.ingested.append((account_id, now))
        self.active.remove(account_id)
        if self.fail:
            attempts = sum(account == account_id for account, _ in self.ingested)
            self.due[account_id] = now + timedelta(
                seconds=min(60 * 2 ** (attempts - 1), 3600)
            )
            return False
        self.due[account_id] = now + timedelta(seconds=60)
        return True

    def purge_expired_raw(self, now, batch_size=1000):
        self.cleanup_calls += 1
        self.cleaned.append(now)
        if self.cleanup_error is not None:
            raise self.cleanup_error
        if self.cleanup_results:
            return self.cleanup_results.pop(0)
        return 0


class FakePresence:
    def __init__(self):
        self.closed = []

    def close_stale_presence(self, *, now):
        self.closed.append(now)
        return 0


@pytest.mark.asyncio
async def test_due_account_runs_within_sixty_seconds_and_closes_presence():
    clock, service, presence = FakeClock(), FakeService(), FakePresence()
    worker = IngestionWorker(service, presence, clock=clock, interval_seconds=60)
    await worker.run_once()
    assert service.ingested == [(10, clock.now)]
    assert presence.closed == [clock.now]


@pytest.mark.asyncio
async def test_two_worker_loops_cannot_process_the_same_lease_concurrently():
    clock, service, presence = FakeClock(), FakeService(), FakePresence()
    first = IngestionWorker(service, presence, clock=clock, interval_seconds=60)
    second = IngestionWorker(service, presence, clock=clock, interval_seconds=60)
    await asyncio.gather(first.run_once(), second.run_once())
    assert service.max_parallel == 1
    assert [account for account, _ in service.ingested] == [10]


@pytest.mark.asyncio
async def test_failed_poll_uses_bounded_backoff():
    clock, service, presence = FakeClock(), FakeService(), FakePresence()
    service.fail = True
    worker = IngestionWorker(service, presence, clock=clock, interval_seconds=60)
    for _ in range(8):
        service.due[10] = clock.now
        await worker.run_once()
    assert timedelta(seconds=60) <= service.due[10] - clock.now <= timedelta(hours=1)


@pytest.mark.asyncio
async def test_shutdown_interrupts_wait_promptly():
    clock, service, presence = FakeClock(), FakeService(), FakePresence()
    worker = IngestionWorker(service, presence, clock=clock, interval_seconds=60)
    task = asyncio.create_task(worker.run())
    await asyncio.sleep(0)
    await asyncio.wait_for(worker.stop(), timeout=0.2)
    await asyncio.wait_for(task, timeout=0.2)


@pytest.mark.asyncio
async def test_cleanup_runs_at_most_daily_without_delaying_first_poll():
    clock, service, presence = FakeClock(), FakeService(), FakePresence()
    worker = IngestionWorker(service, presence, clock=clock, interval_seconds=60)
    await worker.run_once()
    await worker.run_once()
    clock.now += timedelta(days=1)
    service.due[10] = clock.now
    await worker.run_once()
    assert service.cleaned == [datetime(2026, 9, 23, 9), datetime(2026, 9, 24, 9)]
    assert service.ingested[0] == (10, datetime(2026, 9, 23, 9))


@pytest.mark.asyncio
async def test_daily_cleanup_is_bounded_per_scan_and_continues_until_drained():
    clock, service, presence = FakeClock(), FakeService(), FakePresence()
    service.cleanup_results = [1000, 1000, 7]
    worker = IngestionWorker(
        service,
        presence,
        clock=clock,
        interval_seconds=60,
        cleanup_max_batches_per_scan=2,
    )

    await worker.run_once()
    assert service.cleanup_calls == 2
    await worker.run_once()
    assert service.cleanup_calls == 3
    await worker.run_once()

    assert service.cleanup_calls == 3
    clock.now += timedelta(days=1)
    await worker.run_once()
    assert service.cleanup_calls == 4


@pytest.mark.asyncio
async def test_failed_cleanup_is_not_retried_until_next_day():
    clock, service, presence = FakeClock(), FakeService(), FakePresence()
    service.cleanup_error = RuntimeError("database unavailable")
    worker = IngestionWorker(service, presence, clock=clock, interval_seconds=60)

    await worker.run_once()
    await worker.run_once()
    assert service.cleanup_calls == 1
    clock.now += timedelta(days=1)
    await worker.run_once()
    assert service.cleanup_calls == 2


@pytest.mark.asyncio
async def test_slow_account_does_not_block_next_due_account_scan():
    clock, service, presence = FakeClock(), FakeService(), FakePresence()
    service.blocked_account = 10
    worker = IngestionWorker(service, presence, clock=clock, interval_seconds=60)

    await worker.scan_once()
    await asyncio.wait_for(service.block_started.wait(), timeout=0.2)
    clock.now += timedelta(seconds=60)
    service.due[11] = clock.now
    await worker.scan_once()
    await asyncio.sleep(0)

    assert 11 in service.active or any(account == 11 for account, _ in service.ingested)
    service.block_release.set()
    await worker.stop()


@pytest.mark.asyncio
async def test_due_accounts_beyond_cap_do_not_open_more_concurrent_runs():
    clock, service, presence = FakeClock(), FakeService(), FakePresence()
    service.due = {account_id: clock.now for account_id in range(1, 11)}
    service.blocked_accounts = set(service.due)
    worker = IngestionWorker(
        service,
        presence,
        clock=clock,
        interval_seconds=60,
        max_concurrent_accounts=3,
    )

    first_scan = await asyncio.wait_for(worker.scan_once(), timeout=0.2)
    await asyncio.wait_for(service.block_started.wait(), timeout=0.2)
    await asyncio.sleep(0)
    second_scan = await asyncio.wait_for(worker.scan_once(), timeout=0.2)

    assert len(first_scan) == 3
    assert second_scan == []
    assert service.max_parallel == 3
    assert len(service.active) == 3

    service.block_release.set()
    await worker.stop()


@pytest.mark.asyncio
async def test_forty_due_accounts_are_refilled_fairly_without_another_scan():
    clock, service, presence = FakeClock(), FakeService(), FakePresence()
    service.due = {account_id: clock.now for account_id in range(1, 41)}
    service.blocked_accounts = set(service.due)
    worker = IngestionWorker(
        service,
        presence,
        clock=clock,
        interval_seconds=60,
        max_concurrent_accounts=4,
    )

    run = asyncio.create_task(worker.run_once())
    await asyncio.wait_for(service.block_started.wait(), timeout=0.2)
    await asyncio.sleep(0)

    # Repeated scheduler ticks while the first wave is active must neither
    # duplicate queued tenants nor reset their order.
    for _ in range(3):
        assert await worker.scan_once() == []
    assert len(service.active) == 4

    service.block_release.set()
    await asyncio.wait_for(run, timeout=1)

    account_ids = [account_id for account_id, _ in service.ingested]
    assert len(account_ids) == 40
    assert set(account_ids) == set(range(1, 41))
    assert len(account_ids) == len(set(account_ids))
    assert service.max_parallel == 4


@pytest.mark.parametrize("concurrency_cap", [1, 4])
@pytest.mark.asyncio
async def test_forty_accounts_reserve_one_serial_control_session_above_account_cap(
    concurrency_cap,
):
    from app.services.ingestion_worker import DatabaseIngestionRuntime

    current_sessions = 0
    max_sessions = 0
    release = asyncio.Event()
    started = asyncio.Event()
    completed = []
    active_accounts = 0
    max_active_accounts = 0
    due_calls = 0
    cleanup_calls = 0
    presence_calls = 0

    class CountingSessionContext:
        def __enter__(self):
            nonlocal current_sessions, max_sessions
            current_sessions += 1
            max_sessions = max(max_sessions, current_sessions)
            return object()

        def __exit__(self, *args):
            nonlocal current_sessions
            current_sessions -= 1

    class RuntimeService:
        def due_accounts(self, now):
            nonlocal due_calls
            due_calls += 1
            return range(1, 41)

        async def ingest_account(self, *, account_id, now):
            nonlocal active_accounts, max_active_accounts
            active_accounts += 1
            max_active_accounts = max(max_active_accounts, active_accounts)
            started.set()
            await release.wait()
            completed.append(account_id)
            active_accounts -= 1
            return True

        def purge_expired_raw(self, now, batch_size=1000):
            nonlocal cleanup_calls
            cleanup_calls += 1
            return 0

    class CountingPresence:
        def close_stale_presence(self, *, now):
            nonlocal presence_calls
            presence_calls += 1
            return 0

    runtime = DatabaseIngestionRuntime(
        session_factory=CountingSessionContext,
        ingestion_factory=lambda db: RuntimeService(),
        presence_factory=lambda db: CountingPresence(),
    )
    worker = IngestionWorker(
        runtime,
        runtime,
        clock=clock_now,
        max_concurrent_accounts=concurrency_cap,
    )

    run = asyncio.create_task(worker.run_once())
    await asyncio.wait_for(started.wait(), timeout=0.2)
    await asyncio.sleep(0)
    assert max_sessions == concurrency_cap

    # Overlapping scheduler ticks keep their <=60 second control cadence while
    # account work is saturated, but share one serialized control-session slot.
    scans = await asyncio.gather(*(worker.scan_once() for _ in range(3)))
    assert scans == [[], [], []]
    assert max_active_accounts == concurrency_cap
    assert max_sessions == concurrency_cap + 1
    assert presence_calls == 4
    assert due_calls == 4
    assert cleanup_calls == 1

    release.set()
    await asyncio.wait_for(run, timeout=1)
    assert set(completed) == set(range(1, 41))
    assert len(completed) == 40
    assert max_active_accounts == concurrency_cap
    assert max_sessions == concurrency_cap + 1
    assert current_sessions == 0


@pytest.mark.asyncio
async def test_queued_account_uses_fresh_start_time_and_keeps_lease_from_takeover():
    clock = FakeClock()
    presence = FakePresence()
    lease_duration = timedelta(seconds=30)

    class SharedState:
        def __init__(self):
            self.leases = {}
            self.started = []
            self.takeovers = 0
            self.first_started = asyncio.Event()
            self.first_release = asyncio.Event()
            self.second_started = asyncio.Event()
            self.second_release = asyncio.Event()

    state = SharedState()

    class LeaseService:
        def __init__(self, owner, due):
            self.owner = owner
            self.due = due

        def due_accounts(self, now):
            return self.due

        async def ingest_account(self, *, account_id, now):
            existing = state.leases.get(account_id)
            if existing is not None:
                existing_owner, expires_at = existing
                if existing_owner != self.owner and expires_at > now:
                    return False
                if existing_owner != self.owner:
                    state.takeovers += 1

            state.leases[account_id] = (self.owner, now + lease_duration)
            state.started.append((self.owner, account_id, now))
            if self.owner == "first" and account_id == 1:
                state.first_started.set()
                await state.first_release.wait()
            if self.owner == "first" and account_id == 2:
                state.second_started.set()
                await state.second_release.wait()

            if state.leases.get(account_id, (None,))[0] == self.owner:
                state.leases.pop(account_id, None)
            return True

        def purge_expired_raw(self, now, batch_size=1000):
            return 0

    first = IngestionWorker(
        LeaseService("first", [1, 2]),
        presence,
        clock=clock,
        max_concurrent_accounts=1,
    )
    second = IngestionWorker(
        LeaseService("second", [2]),
        presence,
        clock=clock,
        max_concurrent_accounts=1,
    )

    first_run = asyncio.create_task(first.run_once())
    await asyncio.wait_for(state.first_started.wait(), timeout=0.2)
    clock.now += lease_duration * 2
    fresh_start = clock.now
    state.first_release.set()
    await asyncio.wait_for(state.second_started.wait(), timeout=0.2)

    # A second process scanning at the current time must see the queued task's
    # lease as active. A timestamp retained from the original scan would make
    # this lease expired immediately and permit a spurious takeover.
    await asyncio.wait_for(second.run_once(), timeout=0.2)
    first_second_start = next(
        started_at
        for owner, account_id, started_at in state.started
        if owner == "first" and account_id == 2
    )
    assert first_second_start == fresh_start
    assert state.takeovers == 0
    assert not any(
        owner == "second" and account_id == 2 for owner, account_id, _ in state.started
    )

    state.second_release.set()
    await asyncio.wait_for(first_run, timeout=0.2)


def test_account_concurrency_cap_cannot_exceed_runtime_budget():
    clock, service, presence = FakeClock(), FakeService(), FakePresence()

    for invalid in (0, 9):
        with pytest.raises(ValueError, match="concurrent account"):
            IngestionWorker(
                service,
                presence,
                clock=clock,
                max_concurrent_accounts=invalid,
            )


def test_account_concurrency_setting_is_configurable_within_runtime_budget():
    from pydantic import ValidationError

    from app.core.config import Settings, settings

    values = settings.model_dump()
    values["INGESTION_MAX_CONCURRENT_ACCOUNTS"] = 8
    assert Settings(**values).INGESTION_MAX_CONCURRENT_ACCOUNTS == 8

    values["INGESTION_MAX_CONCURRENT_ACCOUNTS"] = 9
    with pytest.raises(ValidationError):
        Settings(**values)


@pytest.mark.asyncio
async def test_session_scoped_runtime_closes_session_when_ingestion_is_cancelled():
    from app.services.ingestion_worker import DatabaseIngestionRuntime

    closed = []
    entered = asyncio.Event()

    class SessionContext:
        def __enter__(self):
            return object()

        def __exit__(self, *args):
            closed.append(True)

    class BlockingService:
        async def ingest_account(self, *, account_id, now):
            entered.set()
            await asyncio.Event().wait()

    runtime = DatabaseIngestionRuntime(
        session_factory=SessionContext,
        ingestion_factory=lambda db: BlockingService(),
        presence_factory=lambda db: FakePresence(),
    )
    task = asyncio.create_task(runtime.ingest_account(account_id=10, now=clock_now()))
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert closed == [True]


def clock_now():
    return datetime(2026, 9, 23, 9)


def test_concurrent_webhook_ensure_reuses_one_durable_secret(migrated_db, monkeypatch):
    from app.integrations.oauth import OAuthTokenCipher
    from app.models import IngestionCursor, OAuthConnection
    from app.services.webhook_subscription_service import WebhookSubscriptionService

    config, engine = migrated_db
    command.upgrade(config, "head")
    cipher = OAuthTokenCipher.from_secret(
        "synthetic-test-key-with-at-least-32-characters"
    )
    with Session(engine) as db:
        db.add(
            OAuthConnection(
                account_id=10,
                account_url="https://tenant.amocrm.ru",
                encrypted_access_token=cipher.encrypt("access-token"),
                encrypted_refresh_token=cipher.encrypt("refresh-token"),
            )
        )
        db.commit()

    generated = []
    generated_lock = threading.Lock()

    def slow_secret(_):
        with generated_lock:
            value = "a" * 43 if not generated else "b" * 43
            generated.append(value)
        time.sleep(0.1)
        return value

    monkeypatch.setattr(
        "app.services.webhook_subscription_service.secrets.token_urlsafe", slow_secret
    )

    class Client:
        def __init__(self):
            self.destinations = []
            self.lock = threading.Lock()

        async def ensure_webhook(self, account_url, access_token, **payload):
            with self.lock:
                self.destinations.append(payload["destination"])

    client = Client()
    start = threading.Barrier(2)

    def ensure():
        with Session(engine) as db:
            service = WebhookSubscriptionService(
                db,
                client,
                cipher,
                public_base_url="https://public.example",
                clock=clock_now,
            )
            start.wait()
            return asyncio.run(service.ensure(10))

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: ensure(), range(2)))

    assert results == [True, True]
    assert len(generated) == 1
    assert len(set(client.destinations)) == 1
    with Session(engine) as db:
        cursor = db.get(IngestionCursor, 10)
        hook_id = cipher.decrypt(cursor.encrypted_webhook_key)
        assert cursor.webhook_key_hash == hashlib.sha256(hook_id.encode()).hexdigest()
