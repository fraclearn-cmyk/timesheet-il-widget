# amoCRM Event Ingestion and Activity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build account-scoped amoCRM event ingestion and privacy-preserving browser presence tracking that produces confirmed points/measured calls and neutral five-minute-bounded intervals without inventing work duration.

**Architecture:** A PostgreSQL-leased worker polls `GET /api/v4/events` at least once per 60 seconds; an untrusted webhook can only advance the next poll time. Raw envelopes expire after 30 days, normalization is fail-closed, deduplication is database-enforced, and interval creation is restricted to verified `WORKING` windows. The widget sends only aggregated presence batches and remains fail-open.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy/Alembic, PostgreSQL 15, Pydantic v2, httpx, vanilla AMD JavaScript, Node test runner, Playwright Chrome, pytest.

**Spec:** `docs/superpowers/specs/2026-09-23-amocrm-event-ingestion-activity-design.md`

## Global Constraints

- Normal polling delay is at most 60 seconds; webhook is only an acceleration signal and never event evidence.
- Raw payload retention is exactly 30 days; normalized records and intervals remain after cleanup.
- Browser signals contain no key values, text, coordinates, DOM values, card content, account ID, or user ID.
- Inactivity threshold is exactly 300 seconds; waiting time is not added to an interval.
- Confirmed activity exists only inside a server-verified `WORKING` segment for the same account and user.
- CRM events without verified duration are zero-duration points with `duration_source=point`.
- Calls remain incomplete unless source, author, direction, start and measured duration are verified.
- Unknown, malformed, foreign-account and system-authored events never create confirmed activity.
- All timestamps are stored as naive UTC consistently with the existing schema and rendered with explicit `Z` at API boundaries.
- OAuth tokens, webhook hook IDs, raw payloads and personal input never appear in logs.
- Backend outage or ingestion failure never blocks amoCRM or synthesizes success.
- No ngrok URL or customer server URL is hardcoded; `PUBLIC_BASE_URL` is optional validated HTTPS configuration.
- Live amoCRM installation/acceptance remains deferred until phases 5–9 are locally complete.

## Review Focus

- Two events with the same `created_at` but different opaque IDs both survive cursor advancement; Task 3 pins this with pagination/watermark tests.
- A forged or repeated webhook can cause at most a rate-limited early poll and cannot create activity; Task 5 pins this at the API/database boundary.
- A late browser batch spanning `WORKING -> BREAK` is clamped/rejected rather than extending activity; Task 4 pins transition-boundary behavior.
- Multi-worker lease expiry permits recovery without concurrent account polling; Task 3 pins owner/expiry races on PostgreSQL.
- Deleting 30-day raw data does not cascade into normalized events or timeline intervals; Tasks 1 and 3 pin schema and cleanup behavior.

---

### Task 1: Account-scoped ingestion persistence and migration 012

**Files:**
- Create: `backend/app/models/ingestion_cursor.py`
- Create: `backend/app/models/raw_ingestion_event.py`
- Create: `backend/app/models/event_type_catalog.py`
- Create: `backend/app/models/presence_batch.py`
- Create: `backend/migrations/versions/012_event_ingestion_activity.py`
- Create: `backend/tests/unit/test_ingestion_models.py`
- Modify: `backend/app/models/crm_event.py`
- Modify: `backend/app/models/call_event.py`
- Modify: `backend/app/models/activity_interval.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/tests/integration/test_migrations.py`

**Interfaces:**
- Consumes: existing `Base`, account-scoped `User`, `WorkSession`, `CrmEvent`, `CallEvent`, `ActivityInterval`; migration head `011`.
- Produces: `IngestionCursor`, `RawIngestionEvent`, `EventTypeCatalog`, `PresenceBatch`; migration head `012`; database uniqueness used by Tasks 3–5.

- [ ] **Step 1: Write failing model tests for defaults, constraints and account scope**

```python
def test_raw_event_dedup_is_account_and_source_scoped(db):
    first = RawIngestionEvent(account_id=1, source="crm_event", dedup_key="a" * 64,
        payload={"id": "evt"}, received_at=utc(2026, 9, 23),
        expires_at=utc(2026, 10, 23), normalization_status="pending")
    db.add(first); db.commit()
    db.add(RawIngestionEvent(account_id=1, source="crm_event", dedup_key="a" * 64,
        payload={}, received_at=utc(2026, 9, 23), expires_at=utc(2026, 10, 23),
        normalization_status="pending"))
    with pytest.raises(IntegrityError):
        db.commit()
```

Also assert a different account or source accepts the same hash, lease timestamps are UTC-naive, `PresenceBatch` UUID is unique per account/user, `CallEvent` has account-scoped source uniqueness/completeness, and `ActivityInterval.duration_source` accepts only `point|observed|calculated`.

- [ ] **Step 2: Run model tests to verify RED**

Run from `backend/`: `..\.venv312\Scripts\python.exe -m pytest tests/unit/test_ingestion_models.py -q --tb=short`

Expected: collection/import failure because the four models do not exist.

- [ ] **Step 3: Implement focused SQLAlchemy models**

Use these table contracts:

```python
class IngestionCursor(Base):
    __tablename__ = "ingestion_cursors"
    account_id: Mapped[int] = mapped_column(ForeignKey("oauth_connections.account_id"), primary_key=True)
    last_created_at: Mapped[datetime | None]
    last_event_id: Mapped[str | None] = mapped_column(String(255))
    next_poll_at: Mapped[datetime]
    last_success_at: Mapped[datetime | None]
    failure_count: Mapped[int] = mapped_column(default=0, server_default="0")
    lease_owner: Mapped[str | None] = mapped_column(String(128))
    lease_until: Mapped[datetime | None]
    webhook_key_hash: Mapped[str | None] = mapped_column(String(64), unique=True)
    encrypted_webhook_key: Mapped[str | None]

class RawIngestionEvent(Base):
    __tablename__ = "raw_ingestion_events"
    # UniqueConstraint("account_id", "source", "dedup_key")
    account_id: Mapped[int]
    source: Mapped[str]                 # crm_event | call
    external_id: Mapped[str | None]
    occurred_at: Mapped[datetime | None]
    dedup_key: Mapped[str]              # lowercase SHA-256 hex
    payload: Mapped[dict]
    received_at: Mapped[datetime]
    expires_at: Mapped[datetime]
    normalization_status: Mapped[str]   # pending | complete | incomplete
    error_code: Mapped[str | None]

class EventTypeCatalog(Base):
    __tablename__ = "event_type_catalog"
    # UniqueConstraint("account_id", "event_key")
    account_id: Mapped[int]
    event_key: Mapped[str]
    label: Mapped[str | None]
    refreshed_at: Mapped[datetime]

class PresenceBatch(Base):
    __tablename__ = "presence_batches"
    # UniqueConstraint("account_id", "user_id", "command_id")
    account_id: Mapped[int]
    user_id: Mapped[int]
    command_id: Mapped[UUID]
    window_started_at: Mapped[datetime]
    last_seen_at: Mapped[datetime]
    signal_count: Mapped[int]           # 1..100000
```

Keep existing legacy fields readable. Add `CrmEvent.raw_event_id`, `original_event_type`; add `CallEvent.raw_event_id`, `is_complete`; enforce PostgreSQL uniqueness for `(account_id, source_event_id, occurred_at)`. Replace payload ownership gradually: existing nullable payload columns remain for compatibility but new ingestion writes raw data only to `RawIngestionEvent`.

- [ ] **Step 4: Create migration 012 with safe populated upgrade/downgrade**

Use `revision = "012"` and `down_revision = "011"`. Create all four tables, indexes, foreign keys and checks. Backfill `crm_events.original_event_type = event_type`; do not fabricate raw envelopes. Downgrade raises `RuntimeError` when any new table contains rows or new FK fields are populated, then removes only phase-5 schema.

- [ ] **Step 5: Extend migration tests**

Add clean and populated `011 -> 012 -> 011 -> 012` coverage on PostgreSQL. Assert one Alembic head, old CRM/call rows survive upgrade, and destructive downgrade refuses new ingestion rows.

- [ ] **Step 6: Run GREEN gates**

Run:

```powershell
..\.venv312\Scripts\python.exe -m pytest tests/unit/test_ingestion_models.py tests/unit/test_models.py -q --tb=short
..\.venv312\Scripts\python.exe -m pytest tests/integration/test_migrations.py -q --tb=short
..\.venv312\Scripts\python.exe -m alembic heads
```

Expected: all pass; exactly one `012 (head)`.

- [ ] **Step 7: Commit**

```powershell
git add backend/app/models backend/migrations/versions/012_event_ingestion_activity.py backend/tests/unit/test_ingestion_models.py backend/tests/unit/test_models.py backend/tests/integration/test_migrations.py
git commit -m "feat: add account-scoped ingestion persistence"
```

---

### Task 2: Fail-closed CRM event and call normalization

**Files:**
- Create: `backend/app/services/event_normalizer.py`
- Create: `backend/tests/unit/test_event_normalizer.py`
- Modify: `backend/app/integrations/amocrm_contract.py`
- Modify: `backend/tests/integration/test_amocrm_contract.py`
- Modify: `docs/api-contract.md`

**Interfaces:**
- Consumes: `RawIngestionEvent`, known account event-type keys, trusted tenant origin and phase-0 URL checks.
- Produces: immutable `NormalizedActivityEvent`; `canonical_payload_hash`; `normalize_crm_event`; `normalize_call_event`. Task 3 persists the result and Task 4 builds intervals from it.

- [ ] **Step 1: Write failing unit tests for the normalized value object**

```python
result = normalize_crm_event(
    observed_payload,
    expected_account_id=108,
    expected_origin="https://example.amocrm.ru",
    known_types={"lead_added"},
)
assert result.normalized_type == "lead_added"
assert result.original_type == "lead_added"
assert result.is_complete is True
assert result.occurred_at == datetime(2026, 9, 23, 9, 0)
```

Cover every official catalog key via parametrization; unknown type becomes `normalized_type="unknown"` while preserving `original_type`; boolean-as-int, system author, foreign account, mismatched embedded entity, unsafe link, invalid timestamp and missing ID are incomplete. Hashes must be stable across JSON key order and differ across source/account.

- [ ] **Step 2: Run tests to verify RED**

Run: `..\.venv312\Scripts\python.exe -m pytest tests/unit/test_event_normalizer.py -q --tb=short`

Expected: import failure for `app.services.event_normalizer`.

- [ ] **Step 3: Implement exact normalization interface**

```python
@dataclass(frozen=True)
class NormalizedActivityEvent:
    external_id: str | None
    source: Literal["crm_event", "call"]
    normalized_type: str
    original_type: str | None
    occurred_at: datetime | None
    author_amocrm_user_id: int | None
    object_type: str | None
    object_id: int | None
    card_url: str | None
    direction: Literal["incoming", "outgoing"] | None
    duration_seconds: int | None
    is_complete: bool
    error_code: str | None
```

Implement these exact public signatures: `canonical_payload_hash(*, account_id: int, source: str, external_id: str | None, occurred_at: datetime | None, payload: Mapping[str, Any]) -> str`; `normalize_crm_event(payload: Mapping[str, Any], *, expected_account_id: int, expected_origin: str, known_types: Collection[str]) -> NormalizedActivityEvent`; `normalize_call_event(payload: Mapping[str, Any], *, expected_account_id: int, expected_origin: str, source_verified: bool) -> NormalizedActivityEvent`.

Reuse the strict tenant/entity URL functions from `amocrm_contract.py` rather than creating a second weaker validator. Keep compatibility wrappers `normalize_timeline_event` and the old `normalize_call_event` contract until their existing tests are migrated; wrappers must delegate to the new normalizer.

- [ ] **Step 4: Define call completeness without inference**

A call is complete only when `source_verified=True`, ID is non-empty, account matches, positive author maps later, direction is exactly `incoming|outgoing`, duration is an integer `>=0`, occurred time is valid UTC and object/link validate. Otherwise return `unknown_call`, no direction/duration, `is_complete=False`.

- [ ] **Step 5: Run GREEN and compatibility tests**

Run:

```powershell
..\.venv312\Scripts\python.exe -m pytest tests/unit/test_event_normalizer.py tests/integration/test_amocrm_contract.py -q --tb=short
```

Expected: all new and phase-0 tests pass.

- [ ] **Step 6: Update API contract and commit**

Document `unknown`, `unknown_call`, `point`, 30-day raw retention and the verified-call gate, then:

```powershell
git add backend/app/services/event_normalizer.py backend/app/integrations/amocrm_contract.py backend/tests/unit/test_event_normalizer.py backend/tests/integration/test_amocrm_contract.py docs/api-contract.md
git commit -m "feat: normalize amoCRM activity evidence"
```

---

### Task 3: Polling transport, transactional ingestion, leases and retention

**Files:**
- Create: `backend/app/services/event_ingestion_service.py`
- Create: `backend/tests/integration/test_activity_ingestion.py`
- Modify: `backend/app/integrations/amocrm_client.py`
- Modify: `backend/app/integrations/oauth.py`
- Modify: `backend/app/models/crm_event.py`
- Modify: `backend/app/models/call_event.py`

**Interfaces:**
- Consumes: Task 1 models and Task 2 normalizer; existing encrypted OAuth connection.
- Produces: `AmoCRMClient.list_events_page`, `list_event_types`; `EventIngestionService.acquire_lease`, `ingest_account`, `purge_expired_raw`; persisted `CrmEvent`/`CallEvent` consumed by Task 4.

- [ ] **Step 1: Write transport RED tests**

Using `httpx.MockTransport`, assert:

```python
page = await client.list_events_page(
    "https://example.amocrm.ru", "token", created_from=1_790_150_400
)
assert [item["id"] for item in page.items] == ["a", "b"]
assert page.next_url == "https://example.amocrm.ru/api/v4/events?limit=100&page=2"
```

Reject cross-tenant, credentials, fragment, non-HTTPS or wrong-path `next`; cap pages/items; return an empty final page on `204`; preserve existing `Retry-After` behavior. Test `/api/v4/events/types` parsing as key/label pairs.

- [ ] **Step 2: Write ingestion RED tests against PostgreSQL**

Cover: same-timestamp IDs across two pages, overlap replay, mid-page transaction failure, concurrent duplicate insert, active lease rejection, expired lease takeover, `401 -> one refresh -> success`, second `401` disable/backoff state, `429`, incomplete event storage, foreign/system author, and cleanup at exactly 30 days.

Core expectation:

```python
await service.ingest_account(account_id=108, now=utc(2026, 9, 23, 10))
await service.ingest_account(account_id=108, now=utc(2026, 9, 23, 10, 1))
assert db.query(RawIngestionEvent).count() == 2
assert db.query(CrmEvent).count() == 2
assert cursor.last_event_id == "b"
```

- [ ] **Step 3: Run RED suites**

Run:

```powershell
..\.venv312\Scripts\python.exe -m pytest tests/integration/test_activity_ingestion.py -q --tb=short
```

Expected: missing client methods/service.

- [ ] **Step 4: Implement bounded event transport**

Add:

```python
@dataclass(frozen=True)
class AmoCRMEventPage:
    items: Sequence[Mapping[str, Any]]
    next_url: str | None
```

Implement exact methods `async list_events_page(self, account_url: str, access_token: str, *, created_from: int, page_url: str | None = None) -> AmoCRMEventPage` and `async list_event_types(self, account_url: str, access_token: str) -> Sequence[tuple[str, str | None]]`.

Use limit 100 and a two-second overlap before `last_created_at`. Validate every returned account ID again during normalization.

- [ ] **Step 5: Implement database lease and transactional page ingestion**

`acquire_lease(account_id, owner, now, lease_seconds=120)` uses a PostgreSQL atomic conditional update/insert. Each fetched page is written in one transaction; `ON CONFLICT DO NOTHING` handles raw dedup. Resolve `author_amocrm_user_id` only against active/inactive historical `User` rows with the same account. Persist incomplete events but do not fabricate a user. Update watermark to the maximum `(created_at, opaque_id)` only after commit.

- [ ] **Step 6: Implement catalog refresh, OAuth retry and cleanup**

Refresh type catalog at most daily. Decrypt access token only at request time. On first `401`, call existing `OAuthService.refresh`, reload token and retry once. `purge_expired_raw(now, batch_size=1000)` deletes only `RawIngestionEvent.expires_at <= now`; foreign keys to normalized records use `SET NULL`.

- [ ] **Step 7: Run GREEN gates and commit**

Run:

```powershell
..\.venv312\Scripts\python.exe -m pytest tests/integration/test_activity_ingestion.py tests/unit/test_event_normalizer.py -q --tb=short
```

Then:

```powershell
git add backend/app/integrations backend/app/services/event_ingestion_service.py backend/app/models/crm_event.py backend/app/models/call_event.py backend/tests/integration/test_activity_ingestion.py
git commit -m "feat: ingest amoCRM events transactionally"
```

---

### Task 4: Activity points, measured calls and five-minute presence intervals

**Files:**
- Create: `backend/app/services/activity_interval_service.py`
- Create: `backend/tests/unit/test_activity_intervals.py`
- Modify: `backend/app/models/activity_interval.py`
- Modify: `backend/app/models/work_session.py`
- Modify: `backend/app/services/timesheet_service.py`
- Modify: `backend/app/services/event_ingestion_service.py`

**Interfaces:**
- Consumes: normalized evidence persisted by Task 3, `PresenceBatch`, `WorkSession.status_transitions`.
- Produces: `ActivityIntervalService.attach_crm_event`, `attach_call`, `record_presence`, `close_stale_presence`, `close_for_status_transition`; correct session duration aggregates.

- [ ] **Step 1: Write RED tests for confirmed evidence boundaries**

```python
interval = service.attach_crm_event(complete_event)
assert interval.started_at == interval.ended_at == complete_event.occurred_at
assert interval.kind == "confirmed"
assert interval.source == "crm_event"
assert interval.duration_source == "point"
```

Assert no interval for incomplete, system, foreign account/user, `BREAK`, `FINISHED`, before start, after end, or a timestamp inside a non-working transition. A verified 45-second call creates exactly 45 seconds with `duration_source="observed"`; a call crossing a break creates no confirmed interval.

- [ ] **Step 2: Write RED tests for presence and review-focus boundaries**

Cover `0`, `299`, `300`, and `301` second gaps; a batch spanning a break; repeated UUID; out-of-order packet; hidden user; late packet after finish; and server closure after browser disappears.

```python
service.record_presence(context, batch(t0, t0 + seconds(50), count=8))
service.close_stale_presence(now=t0 + seconds(351))
interval = one_unconfirmed_interval(db)
assert interval.ended_at == t0 + seconds(50)
assert interval.duration_source == "observed"
```

- [ ] **Step 3: Run RED**

Run: `..\.venv312\Scripts\python.exe -m pytest tests/unit/test_activity_intervals.py -q --tb=short`

Expected: service import failure.

- [ ] **Step 4: Implement interval service with explicit boundaries**

Use exact signatures `attach_crm_event(self, event: CrmEvent) -> ActivityInterval | None`, `attach_call(self, event: CallEvent) -> ActivityInterval | None`, `record_presence(self, *, account_id: int, user: User, command_id: UUID, window_started_at: datetime, last_seen_at: datetime, signal_count: int, received_at: datetime) -> ActivityInterval | None`, `close_stale_presence(self, *, now: datetime) -> int`, and `close_for_status_transition(self, session: WorkSession, *, at: datetime) -> int`.

Presence timestamps must be UTC-naive, no more than 60 seconds into the future, no more than 10 minutes older than receipt for a new batch, ordered, and inside a verified current/historical `WORKING` segment. Merge only same account/user/session when `next.window_started_at - current.ended_at <= 300s`; ending time is always the last observed action.

- [ ] **Step 5: Integrate status transitions and duration aggregates**

After Task 3 persists a complete normalized row, call `attach_crm_event` or `attach_call` in the same page transaction; incomplete evidence deliberately creates no interval. Before committing `start-break` or `finish`, call `close_for_status_transition` in the same transaction. Recompute `active_duration` from measured confirmed intervals only and `unconfirmed_duration` from neutral intervals; point events add zero seconds. Never count overlap twice.

- [ ] **Step 6: Run GREEN and regression tests**

Run:

```powershell
..\.venv312\Scripts\python.exe -m pytest tests/unit/test_activity_intervals.py tests/unit/test_interval_rules.py tests/unit/test_timesheet_transitions.py tests/api/test_timesheet.py -q --tb=short
```

- [ ] **Step 7: Commit**

```powershell
git add backend/app/services/activity_interval_service.py backend/app/services/event_ingestion_service.py backend/app/models/activity_interval.py backend/app/models/work_session.py backend/app/services/timesheet_service.py backend/tests/unit/test_activity_intervals.py
git commit -m "feat: derive bounded activity intervals"
```

---

### Task 5: Presence API, untrusted webhook trigger and leased worker lifecycle

**Files:**
- Create: `backend/app/schemas/activity_ingestion.py`
- Create: `backend/app/api/v1/webhooks.py`
- Create: `backend/app/services/ingestion_worker.py`
- Create: `backend/app/services/webhook_subscription_service.py`
- Create: `backend/tests/api/test_activity_presence.py`
- Create: `backend/tests/api/test_webhooks.py`
- Create: `backend/tests/integration/test_ingestion_worker.py`
- Modify: `backend/app/api/v1/activity.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/core/config.py`
- Modify: `backend/tests/conftest.py`

**Interfaces:**
- Consumes: Task 3 ingestion service/lease and Task 4 presence service.
- Produces: `POST /api/v1/activity/presence`, `POST /api/v1/webhooks/amocrm/{hook_id}`, admin-only `POST /api/v1/activity/ingestion/webhook/ensure`, optional admin poll trigger, and application worker start/stop.

- [ ] **Step 1: Write presence API RED tests**

Exact request:

```json
{
  "command_id": "b50f5f6d-f97d-4f9b-b878-098f00424851",
  "window_started_at": "2026-09-23T09:00:00Z",
  "last_seen_at": "2026-09-23T09:00:44Z",
  "signal_count": 12
}
```

Expect `202` with canonical interval summary or `204` when not `WORKING`; replay returns the same result without a second batch. Reject extra fields, browser identity, invalid UUID/time/count, foreign verified context and timestamps outside bounds.

- [ ] **Step 2: Write webhook RED tests**

Unknown hook ID returns `202` with no account disclosure and no DB change. Valid ID updates only `next_poll_at`; repeated or oversized requests are rate-limited; arbitrary payload cannot insert raw/normalized/activity rows. Ensure hook ID is absent from captured logs.

Also test webhook subscription reconciliation: non-admin is denied, missing `PUBLIC_BASE_URL` returns stable `409 WEBHOOK_URL_MISSING`, and an admin call creates or updates the official destination/settings idempotently without returning the opaque hook ID.

- [ ] **Step 3: Write worker RED tests**

Use a fake clock and fake ingestion service. Assert a due account runs within 60 seconds, two worker loops cannot hold the same lease, failure schedules bounded backoff, shutdown cancels promptly, and daily cleanup is invoked without blocking request startup.

- [ ] **Step 4: Run RED suites**

Run:

```powershell
..\.venv312\Scripts\python.exe -m pytest tests/api/test_activity_presence.py tests/api/test_webhooks.py tests/integration/test_ingestion_worker.py -q --tb=short
```

- [ ] **Step 5: Implement strict schemas and routes**

`PresenceBatchCreate` uses `ConfigDict(extra="forbid")`, UUID4, aware datetimes normalized to UTC and `signal_count: int = Field(ge=1, le=100000)`. The presence route uses `RequestContext` only. Webhook route is included outside the global amoCRM auth dependency, accepts at most 64 KiB, hashes the path ID before lookup, responds quickly and never calls normalization directly.

`WebhookSubscriptionService.ensure(account_id)` generates a 256-bit hook ID once, stores its SHA-256 lookup hash plus an encrypted copy using the existing server-side cipher, constructs the destination from validated `PUBLIC_BASE_URL`, and uses the account's server-side OAuth token to reconcile the official webhook settings. The admin API returns only `{"enabled": true}`. Plain hook IDs never enter logs or API responses. Polling remains active when subscription is absent or fails.

- [ ] **Step 6: Implement worker/config lifecycle**

Add validated configuration:

```python
EVENT_POLL_INTERVAL_SECONDS: int = 60
RAW_EVENT_RETENTION_DAYS: int = 30
INGESTION_WORKER_ENABLED: bool = True
PUBLIC_BASE_URL: str | None = None
```

Validate poll interval `15..60`, retention exactly `30`, and optional public base as HTTPS origin without credentials/query/fragment. Use FastAPI lifespan to create one cancellable loop; database leases provide cross-process exclusion. Each loop obtains `current_utc = utc_now()` and calls `close_stale_presence(now=current_utc)`; raw cleanup runs at most daily. Tests disable the worker by dependency/config override.

- [ ] **Step 7: Run GREEN plus auth regressions**

Run:

```powershell
..\.venv312\Scripts\python.exe -m pytest tests/api/test_activity_presence.py tests/api/test_webhooks.py tests/integration/test_ingestion_worker.py tests/integration/test_authorized_routes.py -q --tb=short
```

- [ ] **Step 8: Commit**

```powershell
git add backend/app/schemas/activity_ingestion.py backend/app/api/v1/activity.py backend/app/api/v1/webhooks.py backend/app/services/ingestion_worker.py backend/app/services/webhook_subscription_service.py backend/app/main.py backend/app/core/config.py backend/tests
git commit -m "feat: expose safe activity ingestion endpoints"
```

---

### Task 6: Privacy-preserving widget activity tracker

**Files:**
- Create: `widget/activity-tracker.js`
- Create: `frontend/tests/activity-tracker.test.js`
- Create: `frontend/tests/activity-tracker.spec.js`
- Modify: `widget/timesheet/controller.js`
- Modify: `widget/script.js`
- Modify: `build_widget.ps1`
- Modify: `validate_widget_zip.py`
- Modify: `test_widget_package.py`
- Modify: `package.json`

**Interfaces:**
- Consumes: authenticated `/activity/presence`; timesheet snapshots containing `track_time`, `hide_widget`, `status`.
- Produces: AMD `ActivityTracker.createActivityTracker(options)` with `updateSnapshot(snapshot)` and `destroy()`; package runtime grows from 18 to 19 files.

- [ ] **Step 1: Write Node RED tests with controlled clock/scheduler**

```javascript
tracker.updateSnapshot({track_time: true, hide_widget: true, status: 'working'});
document.dispatchEvent(new KeyboardEvent('keydown', {key: 'SecretText'}));
clock.advance(60000);
assert.deepEqual(Object.keys(sent[0]).sort(),
  ['command_id', 'last_seen_at', 'signal_count', 'window_started_at']);
assert.equal(JSON.stringify(sent[0]).includes('SecretText'), false);
```

Test one-minute batching, pointer/keyboard aggregation, visibility flush, same UUID retry after lost response, bounded in-memory state, `break|finished|tracking_disabled` suppression, hidden tracking without UI, and destroy cleanup.

- [ ] **Step 2: Write Playwright RED privacy/lifecycle tests**

Boot the real widget modules and authorized transport. Assert no input value, key, coordinates, account ID or user ID enters the request body; server failure adds no overlay/buttons; transition to settings/destroy removes tracker listeners/timers.

- [ ] **Step 3: Run RED**

Run:

```powershell
node --test frontend/tests/activity-tracker.test.js
npx playwright test frontend/tests/activity-tracker.spec.js --workers=1 --reporter=line
```

- [ ] **Step 4: Implement tracker module**

Use:

```javascript
ActivityTracker.createActivityTracker({
  request: function(payload) { /* authorized POST */ },
  schedule: function(fn, delay) { /* cancellable */ },
  now: function() { return new Date(); },
  uuid: uuid
});
```

Listen to `pointerdown`, `keydown` and `visibilitychange` only to update `windowStartedAt`, `lastSeenAt` and integer count. Do not retain the Event object. Retry one pending aggregate with the same UUID; cap count at 100000; drop bounded stale state after leaving `WORKING`.

- [ ] **Step 5: Integrate with real widget lifecycle**

Load the AMD module from `widget/script.js`. The timesheet controller calls a snapshot observer after server-confirmed responses, including hidden/tracking-disabled states. Tracker is silent and has no DOM. `stopTimesheet`, settings transitions and destroy tear it down. Backend/CSS failure keeps amoCRM clear.

- [ ] **Step 6: Update package allowlist and scripts**

Include `activity-tracker.js` as the 19th exact runtime file. Add `npm run test:activity` for Node tests. Package tests assert no credential-like text and exact runtime list.

- [ ] **Step 7: Run GREEN and regression gates**

Run:

```powershell
npm run test:activity
npm run test:timesheet
npm run test:settings
npx playwright test frontend/tests/activity-tracker.spec.js frontend/tests/overlay.spec.js frontend/tests/widget-working.spec.js --workers=1 --reporter=line
.\.venv312\Scripts\python.exe -m pytest test_widget_package.py -q --tb=short
```

- [ ] **Step 8: Commit**

```powershell
git add widget/activity-tracker.js widget/timesheet/controller.js widget/script.js frontend/tests build_widget.ps1 validate_widget_zip.py test_widget_package.py package.json
git commit -m "feat: batch privacy-safe browser presence"
```

---

### Task 7: End-to-end phase-5 gate, contracts and deployment-neutral package

**Files:**
- Create: `backend/tests/integration/test_phase5_activity_pipeline.py`
- Modify: `docs/api-contract.md`
- Modify: `docs/amocrm-integration-limits.md`
- Modify: `.env.example`
- Modify: `docker-compose.yml`
- Modify: `Plan.md` only after all implementation reviews and final verification are clean
- Rebuild: `widget.zip` only after final review is clean

**Interfaces:**
- Consumes: Tasks 1–6 complete and reviewed.
- Produces: one verified local phase-5 pipeline, current deployment documentation, exact 19-file `widget.zip`, and phase report in `Plan.md`.

- [ ] **Step 1: Write an integration RED scenario spanning the complete pipeline**

Create account/user/group and a `WORKING -> BREAK -> WORKING` session. Feed two same-time CRM events with replay, a system event, an unknown event, a call without verified source, presence packets separated by 301 seconds, and a forged webhook. Assert:

```python
assert confirmed_points == 2
assert measured_call_intervals == 0
assert unconfirmed_intervals == 2
assert activity_during_break == 0
assert duplicate_rows == 0
assert forged_webhook_rows == 0
```

- [ ] **Step 2: Run RED and implement only missing integration glue**

Run: `..\.venv312\Scripts\python.exe -m pytest tests/integration/test_phase5_activity_pipeline.py -q --tb=short`

Expected: fail only where cross-task wiring is absent. Fix router/service/model wiring without adding new behavior beyond the spec.

- [ ] **Step 3: Update deployment-neutral documentation**

Document `PUBLIC_BASE_URL`, polling-only fallback, webhook setup/reconciliation, 30-day cleanup, no readable calls source, worker lease, migration `012`, and exact 19-file archive. `.env.example` contains placeholders only; compose passes variables without test/ngrok values.

- [ ] **Step 4: Run focused and full verification**

Against an isolated disposable PostgreSQL database run:

```powershell
..\.venv312\Scripts\python.exe -m pytest -q --tb=short --disable-warnings
..\.venv312\Scripts\python.exe -m alembic heads
```

From repository root run:

```powershell
npm run test:settings
npm run test:timesheet
npm run test:activity
npx playwright test frontend/tests/overlay.spec.js frontend/tests/widget-working.spec.js frontend/tests/activity-tracker.spec.js --workers=1 --reporter=line
.\.venv312\Scripts\python.exe -m pytest test_widget_package.py -q --tb=short
git diff --check
```

- [ ] **Step 5: Request broad whole-phase code review**

Review from phase-5 base through HEAD against this plan and the design spec. Resolve every Critical/Important finding through the prescribed fix/re-review loop. Live amoCRM remains explicitly out of scope; local transport/browser/database behavior is in scope.

- [ ] **Step 6: Build and validate root archive after review**

Preserve any locked prior `widget.zip` under a unique verified backup name; do not delete backups. Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\build_widget.ps1
.\.venv312\Scripts\python.exe .\validate_widget_zip.py .\widget.zip
Get-FileHash -Algorithm SHA256 .\widget.zip
```

Expected: `VALIDATION PASSED: 19 exact runtime files`.

- [ ] **Step 7: Update `Plan.md`, commit and push**

Only after every gate is green: mark phase 5 locally complete/live gate deferred, list actual files and exact test counts, explain what can be checked, retain call/live limitations, add journal entry, then:

```powershell
git add backend/tests/integration/test_phase5_activity_pipeline.py docs .env.example docker-compose.yml Plan.md
git commit -m "docs: mark phase five locally complete"
git push origin main
```

Do not write the global completion phrase: phases 6–9 remain.
