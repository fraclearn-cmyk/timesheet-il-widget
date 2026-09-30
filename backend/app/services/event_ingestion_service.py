"""Authoritative, account-scoped amoCRM event polling and persistence."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import logging
from typing import Any, Awaitable, Callable, Collection, Mapping, Sequence, TypeVar
from uuid import uuid4

import httpx
from sqlalchemy import delete, or_, select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.time_utils import utc_now
from app.integrations.amocrm_client import (
    AmoCRMClient,
    AmoCRMClientError,
    AmoCRMRateLimited,
    AmoCRMUnavailable,
)
from app.integrations.oauth import OAuthService
from app.models.crm_event import CrmEvent
from app.models.event_type_catalog import EventTypeCatalog
from app.models.ingestion_cursor import IngestionCursor
from app.models.oauth_connection import OAuthConnection
from app.models.raw_ingestion_event import RawIngestionEvent
from app.models.user import User
from app.services.event_normalizer import (
    OBSERVED_MINIMUM_EVENT_TYPES,
    canonical_payload_hash,
    normalize_crm_event,
)
from app.services.activity_interval_service import ActivityIntervalService


_T = TypeVar("_T")
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _PageOutcome:
    inserted: int
    watermark: tuple[datetime, str] | None


class _OAuthRejected(AmoCRMClientError):
    pass


class _AccountAccessDenied(AmoCRMClientError):
    pass


class _LeaseLost(RuntimeError):
    pass


class EventIngestionService:
    """Poll one trusted OAuth account and commit each page atomically."""

    _RAW_RETENTION = timedelta(days=30)
    _CATALOG_MAX_AGE = timedelta(days=1)
    _OVERLAP = timedelta(seconds=2)
    _MAX_BACKOFF_SECONDS = 3600

    def __init__(
        self,
        db: Session,
        client: AmoCRMClient,
        oauth_service: OAuthService,
        *,
        owner: str,
        max_pages: int = 100,
        max_items: int = 10_000,
        lease_clock: Callable[[], datetime] | None = None,
        poll_interval_seconds: int = 60,
    ) -> None:
        if not owner or len(owner) > 128:
            raise ValueError("lease owner must contain 1 to 128 characters")
        if max_pages < 1 or max_items < 1:
            raise ValueError("page and item limits must be positive")
        if not 15 <= poll_interval_seconds <= 60:
            raise ValueError("poll interval must be between 15 and 60 seconds")
        self._db = db
        self._client = client
        self._oauth = oauth_service
        self._owner = owner
        self._max_pages = max_pages
        self._max_items = max_items
        self._lease_clock = lease_clock or utc_now
        self._poll_interval = timedelta(seconds=poll_interval_seconds)

    def acquire_lease(
        self,
        account_id: int,
        owner: str,
        now: datetime,
        lease_seconds: int = 120,
    ) -> bool:
        """Atomically create or take over one account lease."""
        if not owner or len(owner) > 128 or lease_seconds < 1:
            raise ValueError("lease owner and duration must be valid")
        now = self._naive_utc(now)
        lease_until = now + timedelta(seconds=lease_seconds)
        insert = self._dialect_insert(IngestionCursor)
        statement = (
            insert.values(
                account_id=account_id,
                next_poll_at=now,
                lease_owner=owner,
                lease_until=lease_until,
            )
            .on_conflict_do_update(
                index_elements=[IngestionCursor.account_id],
                set_={"lease_owner": owner, "lease_until": lease_until},
                where=or_(
                    IngestionCursor.lease_until.is_(None),
                    IngestionCursor.lease_until <= now,
                ),
            )
            .returning(IngestionCursor.account_id)
        )
        try:
            acquired = self._db.execute(statement).scalar_one_or_none() is not None
            self._db.commit()
            return acquired
        except Exception:
            self._db.rollback()
            raise

    def due_accounts(self, now: datetime) -> list[int]:
        """Return active OAuth accounts whose authoritative poll is due."""
        now = self._naive_utc(now)
        return list(
            self._db.scalars(
                select(OAuthConnection.account_id)
                .outerjoin(
                    IngestionCursor,
                    IngestionCursor.account_id == OAuthConnection.account_id,
                )
                .where(
                    OAuthConnection.is_active.is_(True),
                    or_(
                        IngestionCursor.account_id.is_(None),
                        IngestionCursor.next_poll_at <= now,
                    ),
                )
                .order_by(OAuthConnection.account_id)
            )
        )

    async def ingest_account(self, *, account_id: int, now: datetime) -> bool:
        """Poll and persist one account, returning false on lease/upstream failure."""
        now = self._naive_utc(now)
        run_owner = self._run_owner()
        if not self.acquire_lease(account_id, run_owner, now):
            return False

        disable_oauth = False
        failure: Exception | None = None
        try:
            connection = self._db.get(OAuthConnection, account_id)
            if connection is None or not connection.is_active:
                self._release_lease(account_id, run_owner, now)
                return False
            account_url = connection.account_url
            refresh_state = {"used": False}
            known_types = await self._load_catalog(
                connection, account_url, now, refresh_state, run_owner
            )

            cursor = self._db.get(IngestionCursor, account_id)
            last_created_at = cursor.last_created_at if cursor is not None else None
            page_url = cursor.continuation_url if cursor is not None else None
            if cursor is not None and (
                (cursor.pending_last_created_at is None)
                != (cursor.pending_last_event_id is None)
                or (page_url is None and cursor.pending_last_created_at is not None)
            ):
                raise AmoCRMClientError(
                    "amoCRM ingestion checkpoint has an invalid watermark"
                )
            self._db.commit()
            created_from = 0
            if last_created_at is not None:
                created_from = max(
                    0,
                    int(
                        (last_created_at - self._OVERLAP)
                        .replace(tzinfo=UTC)
                        .timestamp()
                    ),
                )

            pages = 0
            total_items = 0
            while True:
                page = await self._authorized_request(
                    account_id,
                    run_owner,
                    refresh_state,
                    lambda token: self._client.list_events_page(
                        account_url,
                        token,
                        created_from=created_from,
                        page_url=page_url,
                    ),
                )
                pages += 1
                total_items += len(page.items)
                final_page = page.next_url is None
                budget_reached = not final_page and (
                    pages >= self._max_pages or total_items >= self._max_items
                )

                with self._db.begin():
                    self._require_and_renew_lease(account_id, run_owner)
                    outcome = self._persist_page(
                        account_id=account_id,
                        account_url=account_url,
                        known_types=known_types,
                        items=page.items,
                        now=now,
                    )
                    cursor = self._db.scalar(
                        select(IngestionCursor).where(
                            IngestionCursor.account_id == account_id,
                            IngestionCursor.lease_owner == run_owner,
                        )
                    )
                    if cursor is None:
                        raise _LeaseLost("account ingestion lease was lost")
                    self._merge_pending_watermark(cursor, outcome.watermark)
                    cursor.continuation_url = page.next_url
                    if final_page:
                        self._publish_pending_watermark(cursor)
                        cursor.last_success_at = now
                    if final_page or budget_reached:
                        cursor.next_poll_at = now + self._poll_interval
                        cursor.failure_count = 0
                        cursor.lease_owner = None
                        cursor.lease_until = None

                if final_page or budget_reached:
                    return True
                page_url = page.next_url
        except _OAuthRejected as error:
            disable_oauth = True
            failure = error
        except _AccountAccessDenied as error:
            disable_oauth = True
            failure = error
        except asyncio.CancelledError:
            self._db.rollback()
            self._record_failure(
                account_id,
                run_owner,
                self._naive_utc(self._lease_clock()),
                disable_oauth=False,
            )
            raise
        except _LeaseLost as error:
            self._db.rollback()
            self._log_failure(account_id, error)
            return False
        except Exception as error:
            failure = error

        self._db.rollback()
        if failure is not None:
            self._log_failure(account_id, failure)
        self._record_failure(account_id, run_owner, now, disable_oauth=disable_oauth)
        return False

    def purge_expired_raw(self, now: datetime, batch_size: int = 1000) -> int:
        """Delete one bounded batch whose retention deadline has been reached."""
        if batch_size < 1:
            raise ValueError("batch size must be positive")
        now = self._naive_utc(now)
        candidates = (
            select(RawIngestionEvent.id)
            .where(RawIngestionEvent.expires_at <= now)
            .order_by(RawIngestionEvent.id)
            .limit(batch_size)
        )
        if self._db.bind is not None and self._db.bind.dialect.name == "postgresql":
            candidates = candidates.with_for_update(skip_locked=True)
        try:
            ids = list(self._db.scalars(candidates))
            if not ids:
                self._db.commit()
                return 0
            self._db.execute(
                delete(RawIngestionEvent).where(RawIngestionEvent.id.in_(ids))
            )
            self._db.commit()
            return len(ids)
        except Exception:
            self._db.rollback()
            raise

    async def _load_catalog(
        self,
        connection: OAuthConnection,
        account_url: str,
        now: datetime,
        refresh_state: dict[str, bool],
        run_owner: str,
    ) -> Collection[str]:
        account_id = connection.account_id
        cursor = self._db.get(IngestionCursor, account_id)
        if cursor is None:
            raise _LeaseLost("account ingestion cursor disappeared")
        latest = cursor.catalog_refreshed_at
        known = set(
            self._db.scalars(
                select(EventTypeCatalog.event_key).where(
                    EventTypeCatalog.account_id == account_id
                )
            )
        )
        if latest is not None and latest > now - self._CATALOG_MAX_AGE:
            self._db.commit()
            return known | OBSERVED_MINIMUM_EVENT_TYPES

        try:
            entries = await self._authorized_request(
                account_id,
                run_owner,
                refresh_state,
                lambda token: self._client.list_event_types(account_url, token),
            )
        except AmoCRMUnavailable:
            # The small observed floor lets polling continue safely during an
            # initial catalog outage. An expired durable account catalog remains
            # safe to classify against while its unchanged timestamp forces a
            # refresh retry on the next poll.
            return known | OBSERVED_MINIMUM_EVENT_TYPES
        with self._db.begin():
            self._require_and_renew_lease(account_id, run_owner)
            cursor = self._db.get(IngestionCursor, account_id)
            if cursor is None or cursor.lease_owner != run_owner:
                raise _LeaseLost("account ingestion lease was lost")
            cursor.catalog_refreshed_at = now
            self._db.execute(
                delete(EventTypeCatalog).where(
                    EventTypeCatalog.account_id == account_id
                )
            )
            self._db.add_all(
                EventTypeCatalog(
                    account_id=account_id,
                    event_key=key,
                    label=label,
                    refreshed_at=now,
                )
                for key, label in entries
            )
        return {key for key, _label in entries} | OBSERVED_MINIMUM_EVENT_TYPES

    async def _authorized_request(
        self,
        account_id: int,
        run_owner: str,
        refresh_state: dict[str, bool],
        operation: Callable[[str], Awaitable[_T]],
    ) -> _T:
        connection = self._db.get(OAuthConnection, account_id)
        if connection is None:
            raise _OAuthRejected("OAuth connection disappeared")
        token = self._oauth.load_access_token(connection)
        # Loading the ORM state starts a transaction. End it before yielding to
        # amoCRM so a slow network request never retains a DB connection.
        self._db.commit()
        try:
            return await operation(token)
        except httpx.HTTPStatusError as error:
            if error.response.status_code in {402, 403}:
                raise _AccountAccessDenied(
                    "amoCRM account access is permanently unavailable"
                ) from error
            if error.response.status_code != 401:
                raise
            self._db.rollback()
            if refresh_state["used"]:
                raise _OAuthRejected("amoCRM rejected refreshed OAuth credentials")
            refresh_state["used"] = True
            try:
                with self._db.begin():
                    self._require_and_renew_lease(account_id, run_owner)
                    connection = self._db.scalar(
                        select(OAuthConnection)
                        .where(OAuthConnection.account_id == account_id)
                        .with_for_update()
                    )
                    if connection is None:
                        raise _OAuthRejected("OAuth connection disappeared")
                    snapshot = self._oauth.snapshot_refresh(connection)

                refresh = asyncio.create_task(
                    self._refresh_and_persist(account_id, run_owner, snapshot),
                    name=f"amocrm-oauth-refresh-{account_id}",
                )
                try:
                    await asyncio.shield(refresh)
                except asyncio.CancelledError as cancellation:
                    # asyncio.to_thread cannot stop a request already in flight. Keep
                    # the exchange and its token CAS together, so shutdown cannot
                    # discard a successfully rotated refresh token. The sync client
                    # has its own bounded timeout, and worker.stop waits for this
                    # account task before the shared clients are closed.
                    while not refresh.done():
                        try:
                            await asyncio.shield(refresh)
                        except asyncio.CancelledError:
                            continue
                        except Exception:
                            break
                    try:
                        refresh.result()
                    except Exception:
                        logger.exception(
                            "OAuth refresh finalization failed during cancellation",
                            extra={
                                "account_id": account_id,
                                "error_code": "oauth_refresh_finalize_failed",
                            },
                        )
                    raise cancellation

                connection = self._db.get(OAuthConnection, account_id)
                if connection is None:
                    raise _OAuthRejected("OAuth connection disappeared")
                token = self._oauth.load_access_token(connection)
                self._db.commit()
                return await operation(token)
            except httpx.HTTPStatusError as retry_error:
                self._db.rollback()
                if retry_error.response.status_code in {402, 403}:
                    raise _AccountAccessDenied(
                        "amoCRM account access is permanently unavailable"
                    ) from retry_error
                if retry_error.response.status_code == 401:
                    raise _OAuthRejected(
                        "amoCRM rejected refreshed OAuth credentials"
                    ) from retry_error
                raise

    async def _refresh_and_persist(self, account_id, run_owner, snapshot) -> None:
        """Finish one refresh exchange and its fenced CAS as one shutdown unit."""
        tokens = await asyncio.to_thread(self._oauth.request_refresh, snapshot)
        with self._db.begin():
            self._require_and_renew_lease(account_id, run_owner)
            connection = self._db.scalar(
                select(OAuthConnection)
                .where(OAuthConnection.account_id == account_id)
                .with_for_update()
            )
            if connection is None:
                raise _OAuthRejected("OAuth connection disappeared")
            self._oauth.apply_refresh(connection, snapshot, tokens)

    def _persist_page(
        self,
        *,
        account_id: int,
        account_url: str,
        known_types: Collection[str],
        items: Sequence[Mapping[str, Any]],
        now: datetime,
    ) -> _PageOutcome:
        inserted = 0
        watermark: tuple[datetime, str] | None = None
        prepared = []
        users_to_lock: dict[int, User] = {}
        for payload in items:
            normalized = normalize_crm_event(
                payload,
                expected_account_id=account_id,
                expected_origin=account_url,
                known_types=known_types,
            )
            user = None
            if normalized.author_amocrm_user_id is not None:
                user = self._db.scalar(
                    select(User).where(
                        User.amocrm_account_id == account_id,
                        User.amocrm_user_id == normalized.author_amocrm_user_id,
                    )
                )
                if user is not None:
                    users_to_lock[user.id] = user
            prepared.append((payload, normalized, user))

        # Every transaction that can retain more than one user lock uses the
        # same ascending order. This matches stale-presence cleanup and avoids
        # reversed amoCRM payload order forming a PostgreSQL wait cycle.
        for user_id in sorted(users_to_lock):
            self._db.execute(
                select(User.id)
                .where(User.id == user_id, User.amocrm_account_id == account_id)
                .with_for_update()
            ).scalar_one()

        for payload, normalized, user in prepared:
            is_complete = normalized.is_complete and user is not None
            error_code = normalized.error_code
            if normalized.is_complete and user is None:
                error_code = "author_not_synced"

            dedup_key = canonical_payload_hash(
                account_id=account_id,
                source="crm_event",
                external_id=normalized.external_id,
                occurred_at=normalized.occurred_at,
                payload=payload,
            )
            raw_statement = (
                self._dialect_insert(RawIngestionEvent)
                .values(
                    account_id=account_id,
                    source="crm_event",
                    external_id=normalized.external_id,
                    occurred_at=normalized.occurred_at,
                    dedup_key=dedup_key,
                    payload=dict(payload),
                    received_at=now,
                    expires_at=now + self._RAW_RETENTION,
                    normalization_status=("complete" if is_complete else "incomplete"),
                    error_code=error_code,
                )
                .on_conflict_do_nothing(
                    index_elements=[
                        RawIngestionEvent.account_id,
                        RawIngestionEvent.source,
                        RawIngestionEvent.dedup_key,
                    ]
                )
                .returning(RawIngestionEvent.id)
            )
            raw_id = self._db.execute(raw_statement).scalar_one_or_none()
            if raw_id is not None:
                inserted += 1
                if (
                    normalized.external_id is not None
                    and normalized.occurred_at is not None
                ):
                    normalized_statement = (
                        self._dialect_insert(CrmEvent)
                        .values(
                            account_id=account_id,
                            external_id=normalized.external_id,
                            author_amocrm_user_id=normalized.author_amocrm_user_id,
                            user_id=(
                                user.id if is_complete and user is not None else None
                            ),
                            event_type=normalized.normalized_type,
                            original_event_type=normalized.original_type,
                            object_type=normalized.object_type,
                            object_id=normalized.object_id,
                            occurred_at=normalized.occurred_at,
                            card_url=normalized.card_url,
                            payload=None,
                            raw_event_id=raw_id,
                            is_complete=1 if is_complete else 0,
                            created_at=now,
                        )
                        .on_conflict_do_nothing(
                            index_elements=[CrmEvent.account_id, CrmEvent.external_id]
                        )
                        .returning(CrmEvent.id)
                    )
                    normalized_id = self._db.execute(
                        normalized_statement
                    ).scalar_one_or_none()
                    if normalized_id is not None and is_complete:
                        persisted = self._db.get(CrmEvent, normalized_id)
                        if persisted is not None:
                            ActivityIntervalService(self._db).attach_crm_event(
                                persisted
                            )

            if (
                normalized.error_code != "account_mismatch"
                and normalized.external_id is not None
                and normalized.occurred_at is not None
            ):
                candidate = (normalized.occurred_at, normalized.external_id)
                if watermark is None or candidate > watermark:
                    watermark = candidate
        return _PageOutcome(inserted=inserted, watermark=watermark)

    def _record_failure(
        self,
        account_id: int,
        run_owner: str,
        now: datetime,
        *,
        disable_oauth: bool,
    ) -> bool:
        try:
            cursor = self._db.scalar(
                select(IngestionCursor)
                .where(
                    IngestionCursor.account_id == account_id,
                    IngestionCursor.lease_owner == run_owner,
                )
                .with_for_update()
            )
            if cursor is None:
                self._db.commit()
                return False
            cursor.failure_count += 1
            seconds = min(
                60 * (2 ** min(cursor.failure_count - 1, 10)),
                self._MAX_BACKOFF_SECONDS,
            )
            cursor.next_poll_at = now + timedelta(seconds=seconds)
            cursor.lease_owner = None
            cursor.lease_until = None
            if disable_oauth:
                connection = self._db.get(OAuthConnection, account_id)
                if connection is not None:
                    connection.is_active = False
            self._db.commit()
            return True
        except Exception:
            self._db.rollback()
            raise

    def _release_lease(self, account_id: int, run_owner: str, now: datetime) -> bool:
        cursor = self._db.scalar(
            select(IngestionCursor)
            .where(
                IngestionCursor.account_id == account_id,
                IngestionCursor.lease_owner == run_owner,
            )
            .with_for_update()
        )
        if cursor is not None:
            cursor.lease_owner = None
            cursor.lease_until = None
            cursor.next_poll_at = now + self._poll_interval
        self._db.commit()
        return cursor is not None

    def _require_and_renew_lease(self, account_id: int, run_owner: str) -> None:
        lease_at = self._naive_utc(self._lease_clock())
        statement = (
            IngestionCursor.__table__.update()
            .where(
                IngestionCursor.account_id == account_id,
                IngestionCursor.lease_owner == run_owner,
            )
            .values(lease_until=lease_at + timedelta(seconds=120))
            .returning(IngestionCursor.account_id)
        )
        if self._db.execute(statement).scalar_one_or_none() is None:
            raise _LeaseLost("account ingestion lease was lost")

    def _run_owner(self) -> str:
        return f"{self._owner[:95]}:{uuid4().hex}"

    @staticmethod
    def _log_failure(account_id: int, error: Exception) -> None:
        error_code = EventIngestionService._failure_code(error)
        level = (
            logging.ERROR
            if error_code in {"database_error", "unexpected_error"}
            else logging.WARNING
        )
        logger.log(
            level,
            "amoCRM ingestion failed",
            extra={"account_id": account_id, "error_code": error_code},
        )

    @staticmethod
    def _failure_code(error: Exception) -> str:
        if isinstance(error, _LeaseLost):
            return "lease_lost"
        if isinstance(error, _OAuthRejected):
            return "oauth_rejected"
        if isinstance(error, _AccountAccessDenied):
            return "account_access_denied"
        if isinstance(error, AmoCRMRateLimited):
            return "amocrm_rate_limited"
        if isinstance(error, AmoCRMClientError):
            return "amocrm_transport_error"
        if isinstance(error, httpx.HTTPError):
            return "amocrm_http_error"
        if isinstance(error, SQLAlchemyError):
            return "database_error"
        return "unexpected_error"

    def _dialect_insert(self, model):
        if self._db.bind is not None and self._db.bind.dialect.name == "postgresql":
            return postgresql_insert(model)
        if self._db.bind is not None and self._db.bind.dialect.name == "sqlite":
            return sqlite_insert(model)
        raise RuntimeError("event ingestion requires PostgreSQL or SQLite")

    @staticmethod
    def _is_newer_watermark(
        cursor: IngestionCursor, watermark: tuple[datetime, str]
    ) -> bool:
        if cursor.last_created_at is None or cursor.last_event_id is None:
            return True
        return watermark > (cursor.last_created_at, cursor.last_event_id)

    @staticmethod
    def _merge_pending_watermark(
        cursor: IngestionCursor, watermark: tuple[datetime, str] | None
    ) -> None:
        if watermark is None:
            return
        pending = None
        if (
            cursor.pending_last_created_at is not None
            and cursor.pending_last_event_id is not None
        ):
            pending = (
                cursor.pending_last_created_at,
                cursor.pending_last_event_id,
            )
        if pending is None or watermark > pending:
            cursor.pending_last_created_at, cursor.pending_last_event_id = watermark

    @staticmethod
    def _publish_pending_watermark(cursor: IngestionCursor) -> None:
        if (
            cursor.pending_last_created_at is not None
            and cursor.pending_last_event_id is not None
        ):
            pending = (
                cursor.pending_last_created_at,
                cursor.pending_last_event_id,
            )
            if EventIngestionService._is_newer_watermark(cursor, pending):
                cursor.last_created_at, cursor.last_event_id = pending
        cursor.pending_last_created_at = None
        cursor.pending_last_event_id = None

    @staticmethod
    def _naive_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value
        return value.astimezone(UTC).replace(tzinfo=None)
