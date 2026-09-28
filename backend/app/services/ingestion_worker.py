"""Cancellable in-process scheduler; PostgreSQL leases remain the authority."""

from __future__ import annotations

import asyncio
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
    def close_stale_presence(self, *, now: datetime) -> int: ...


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

    def close_stale_presence(self, *, now: datetime) -> int:
        with self._session_factory() as db:
            try:
                count = self._presence_factory(db).close_stale_presence(now=now)
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
    ) -> None:
        if not 15 <= interval_seconds <= 60:
            raise ValueError("worker interval must be between 15 and 60 seconds")
        if not 1 <= max_concurrent_accounts <= _MAX_ACCOUNT_CONCURRENCY:
            raise ValueError("concurrent account limit must be between 1 and 8")
        if cleanup_batch_size < 1 or cleanup_max_batches_per_scan < 1:
            raise ValueError("cleanup batch limits must be positive")
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
        self._cleanup_pending = False
        self._max_concurrent_accounts = max_concurrent_accounts
        self._active_accounts: dict[int, asyncio.Task] = {}

    async def scan_once(self) -> list[asyncio.Task]:
        current_utc = self._clock()
        try:
            self._presence.close_stale_presence(now=current_utc)
            self._commit()
        except Exception:
            self._rollback()
            logger.exception(
                "presence cleanup failed",
                extra={"error_code": "presence_cleanup_failed"},
            )

        started: list[asyncio.Task] = []
        available_slots = self._max_concurrent_accounts - len(self._active_accounts)
        for account_id in self._ingestion.due_accounts(current_utc):
            if self._stop_event.is_set() or available_slots <= 0:
                break
            if account_id in self._active_accounts:
                continue
            task = asyncio.create_task(
                self._ingest_account(account_id, current_utc),
                name=f"amocrm-ingestion-{account_id}",
            )
            self._active_accounts[account_id] = task
            task.add_done_callback(
                lambda completed, account=account_id: self._forget_account(
                    account, completed
                )
            )
            started.append(task)
            available_slots -= 1

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
        return started

    async def run_once(self) -> None:
        started = await self.scan_once()
        if started:
            await asyncio.gather(*started, return_exceptions=True)

    async def _ingest_account(self, account_id: int, now: datetime) -> None:
        try:
            await self._ingestion.ingest_account(account_id=account_id, now=now)
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
        active = list(self._active_accounts.values())
        for task in active:
            task.cancel()
        if active:
            await asyncio.gather(*active, return_exceptions=True)
        await asyncio.sleep(0)
