"""Cancellable in-process scheduler; PostgreSQL leases remain the authority."""

from __future__ import annotations

import asyncio
from collections import deque
from datetime import datetime, timedelta
import logging
from typing import Callable, Protocol, Sequence

from app.core.time_utils import utc_now


logger = logging.getLogger(__name__)
_MAX_ACCOUNT_CONCURRENCY = 8


class IngestionService(Protocol):
    def due_accounts(self, now: datetime) -> Sequence[int]: ...
    async def ingest_account(self, *, account_id: int, now: datetime) -> bool: ...
    def purge_expired_raw(self, now: datetime, batch_size: int = 1000) -> int: ...


class PresenceService(Protocol):
    def close_stale_presence(self, *, now: datetime, batch_size: int = 100) -> int: ...


class DatabaseIngestionRuntime:
    """Open one database session per scan, account poll, or cleanup batch."""

    def __init__(self, *, session_factory, ingestion_factory, presence_factory):
        self._session_factory = session_factory
        self._ingestion_factory = ingestion_factory
        self._presence_factory = presence_factory

    def due_accounts(self, now: datetime) -> Sequence[int]:
        with self._session_factory() as db:
            return tuple(self._ingestion_factory(db).due_accounts(now))

    async def ingest_account(self, *, account_id: int, now: datetime) -> bool:
        with self._session_factory() as db:
            return await self._ingestion_factory(db).ingest_account(
                account_id=account_id, now=now
            )

    def close_stale_presence(self, *, now: datetime, batch_size: int = 100) -> int:
        with self._session_factory() as db:
            try:
                count = self._presence_factory(db).close_stale_presence(
                    now=now, batch_size=batch_size
                )
                db.commit()
                return count
            except Exception:
                db.rollback()
                raise

    def purge_expired_raw(self, now: datetime, batch_size: int = 1000) -> int:
        with self._session_factory() as db:
            return self._ingestion_factory(db).purge_expired_raw(
                now, batch_size=batch_size
            )


class IngestionWorker:
    """Poll due accounts while delegating exclusion/backoff to ingestion leases."""

    def __init__(
        self,
        ingestion: IngestionService,
        presence: PresenceService,
        *,
        clock: Callable[[], datetime] = utc_now,
        interval_seconds: int = 60,
        commit: Callable[[], None] | None = None,
        rollback: Callable[[], None] | None = None,
        cleanup_batch_size: int = 1000,
        cleanup_max_batches_per_scan: int = 2,
        max_concurrent_accounts: int = 4,
        presence_batch_size: int = 100,
        account_budget_seconds: float = 10.0,
    ) -> None:
        if not 15 <= interval_seconds <= 60:
            raise ValueError("worker interval must be between 15 and 60 seconds")
        if not 1 <= max_concurrent_accounts <= _MAX_ACCOUNT_CONCURRENCY:
            raise ValueError("concurrent account limit must be between 1 and 8")
        if cleanup_batch_size < 1 or cleanup_max_batches_per_scan < 1:
            raise ValueError("cleanup batch limits must be positive")
        if presence_batch_size < 1 or account_budget_seconds <= 0:
            raise ValueError("presence and account budgets must be positive")
        self._ingestion = ingestion
        self._presence = presence
        self._clock = clock
        self._interval_seconds = interval_seconds
        self._stop_event = asyncio.Event()
        self._last_cleanup_at: datetime | None = None
        self._commit = commit or (lambda: None)
        self._rollback = rollback or (lambda: None)
        self._cleanup_batch_size = cleanup_batch_size
        self._cleanup_max_batches_per_scan = cleanup_max_batches_per_scan
        self._presence_batch_size = presence_batch_size
        self._account_budget_seconds = account_budget_seconds
        self._cleanup_pending = False
        self._max_concurrent_accounts = max_concurrent_accounts
        self._active_accounts: dict[int, asyncio.Task] = {}
        self._pending_accounts: deque[int] = deque()
        self._pending_account_ids: set[int] = set()
        self._idle_event = asyncio.Event()
        self._idle_event.set()
        self._scan_lock = asyncio.Lock()

    async def scan_once(self) -> list[asyncio.Task]:
        # Account work owns the configured budget. Control scans reserve one
        # additional short-lived session so due-account discovery still runs on
        # its configured cadence while account slots are occupied. Serialize that
        # control slot to keep total ingestion sessions at account cap + 1; slow
        # dependencies may extend wall-clock time between completed scans.
        async with self._scan_lock:
            current_utc = self._clock()
            started = self._discover_and_start(current_utc)
            # create_task only schedules account work. Yield before synchronous
            # control I/O so the first wave can acquire leases immediately.
            await asyncio.sleep(0)
            await asyncio.to_thread(self._run_control, current_utc)
            return started

    def _discover_and_start(self, current_utc: datetime) -> list[asyncio.Task]:
        for account_id in self._ingestion.due_accounts(current_utc):
            if self._stop_event.is_set():
                break
            if (
                account_id in self._active_accounts
                or account_id in self._pending_account_ids
            ):
                continue
            self._pending_accounts.append(account_id)
            self._pending_account_ids.add(account_id)
            self._idle_event.clear()

        started = self._start_pending_accounts()

        return started

    def _run_control(self, current_utc: datetime) -> None:
        """Run one serialized bounded maintenance slice off the event loop."""
        try:
            self._presence.close_stale_presence(
                now=current_utc, batch_size=self._presence_batch_size
            )
            self._commit()
        except Exception:
            self._rollback()
            logger.exception(
                "presence cleanup failed",
                extra={"error_code": "presence_cleanup_failed"},
            )

        if (
            self._cleanup_pending
            or self._last_cleanup_at is None
            or current_utc - self._last_cleanup_at >= timedelta(days=1)
        ):
            self._cleanup_pending = True
            try:
                for _ in range(self._cleanup_max_batches_per_scan):
                    deleted = self._ingestion.purge_expired_raw(
                        current_utc, batch_size=self._cleanup_batch_size
                    )
                    if deleted < self._cleanup_batch_size:
                        self._cleanup_pending = False
                        self._last_cleanup_at = current_utc
                        break
            except Exception:
                # An unavailable database gets one attempt per day rather than
                # one attempt per scheduler tick.
                self._cleanup_pending = False
                self._last_cleanup_at = current_utc
                logger.exception(
                    "raw cleanup failed", extra={"error_code": "raw_cleanup_failed"}
                )

    async def run_once(self) -> None:
        await self.scan_once()
        await self._idle_event.wait()

    def _start_pending_accounts(self) -> list[asyncio.Task]:
        started: list[asyncio.Task] = []
        while (
            not self._stop_event.is_set()
            and self._pending_accounts
            and len(self._active_accounts) < self._max_concurrent_accounts
        ):
            account_id = self._pending_accounts.popleft()
            self._pending_account_ids.remove(account_id)
            task = asyncio.create_task(
                self._ingest_account(account_id, self._clock()),
                name=f"amocrm-ingestion-{account_id}",
            )
            self._active_accounts[account_id] = task
            task.add_done_callback(
                lambda completed, account=account_id: self._forget_account(
                    account, completed
                )
            )
            started.append(task)
        return started

    async def _ingest_account(self, account_id: int, now: datetime) -> None:
        try:
            async with asyncio.timeout(self._account_budget_seconds):
                await self._ingestion.ingest_account(account_id=account_id, now=now)
        except TimeoutError:
            logger.warning(
                "account ingestion exceeded its bounded scheduler slot",
                extra={
                    "account_id": account_id,
                    "error_code": "worker_poll_timeout",
                },
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception(
                "account ingestion failed",
                extra={
                    "account_id": account_id,
                    "error_code": "worker_poll_failed",
                },
            )

    def _forget_account(self, account_id: int, task: asyncio.Task) -> None:
        if self._active_accounts.get(account_id) is task:
            self._active_accounts.pop(account_id, None)
        self._start_pending_accounts()
        if not self._active_accounts and not self._pending_accounts:
            self._idle_event.set()

    async def run(self) -> None:
        while not self._stop_event.is_set():
            try:
                await self.scan_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception(
                    "ingestion worker cycle failed",
                    extra={"error_code": "worker_cycle_failed"},
                )
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(), timeout=self._interval_seconds
                )
            except TimeoutError:
                pass

    async def stop(self) -> None:
        self._stop_event.set()
        self._pending_accounts.clear()
        self._pending_account_ids.clear()
        active = list(self._active_accounts.values())
        for task in active:
            task.cancel()
        if active:
            await asyncio.gather(*active, return_exceptions=True)
        self._idle_event.set()
        await asyncio.sleep(0)
