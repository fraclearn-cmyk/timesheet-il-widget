# Phase 4 Timesheet Status and Overlay Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver server-authoritative work statuses and an amoCRM overlay that disappears completely whenever the timesheet server cannot confirm state.

**Architecture:** A timezone helper determines the group business date, a transactional service owns state transitions and idempotency, and authenticated `/api/v1/timesheet/*` routes expose state to a small widget controller. The overlay renders only a confirmed server snapshot. Legacy session routes remain available but are not used by the new controller.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy, Alembic, PostgreSQL 15, pytest; amoCRM Widget SDK, vanilla JavaScript/CSS, Node 22+, jsdom; Playwright Chromium for the overlay interaction check.

**Spec:** `docs/superpowers/specs/2026-09-22-timesheet-status-overlay-design.md`

## Global Constraints

- The final amoCRM upload artifact is `widget.zip`; full live amoCRM acceptance is deferred until every local phase is implemented.
- Backend is the sole authority for status, permission, group timezone, and account-scoped identity. Widget requests use `$authorizedAjax`, never hand-written browser auth headers.
- On API outage, timeout, invalid response, or unverified identity: remove *all* timesheet buttons and dark overlay; leave amoCRM usable. Do not infer `working` or backfill elapsed time.
- `track_time` and `hide_widget` come from active `GroupMember` and remain independent. The latter hides UI but does not erase server data.
- UTC timestamps are stored as UTC-naive in existing columns and emitted as UTC `Z` in JSON. Calendar dates use the group's IANA timezone, including overnight shifts.
- `api_url` stays an installation setting; no fixed ngrok/company endpoint, secret, OAuth token, or test account data in executable widget sources or the final `widget.zip`. The archive's help text uses a neutral HTTPS example.
- Do not mark phase 4 complete in `Plan.md` until backend, widget, migration, package, and independent review gates pass. Do not mark live amoCRM acceptance complete here.

## Review Focus

1. A network failure *after* an overlay was shown must remove the overlay and buttons immediately: Task 4 widget test and Task 5 browser test.
2. Two tabs starting simultaneously must not create two open sessions: Task 2 transaction/database test.
3. A UUID reused for a different route must fail without replaying or mutating the first command: Task 2 idempotency test.
4. A local day boundary and overnight shift must not move a session into the wrong reporting day: Task 1 timezone/KPI tests.
5. A hidden but tracked employee must retain server records while no UI is mounted: Task 3 API test and Task 4 widget test.

## File map and interfaces

| Unit | Responsibility |
|---|---|
| `backend/app/core/business_time.py` | Pure group-calendar calculations; consumes UTC-naive datetime, IANA zone, shift times. |
| `backend/app/services/kpi_service.py` | Existing KPI period queries use UTC boundaries derived from group-local calendar. |
| `backend/app/models/work_session.py`, `backend/app/models/timesheet_command.py`, `backend/migrations/versions/011_timesheet_commands.py` | Persist business date, one-open-session invariant, command replay result. |
| `backend/app/services/timesheet_service.py` | Account-scoped status snapshot and transactional transitions. |
| `backend/app/schemas/timesheet.py`, `backend/app/api/v1/timesheet.py`, `backend/app/main.py` | Five authenticated status/command routes and stable response shape. |
| `widget/timesheet/controller.js`, `widget/overlay.js`, `widget/styles.css`, `widget/script.js`, `widget/manifest.json` | Authenticated transport, fail-open lifecycle, namespaced overlay, work-area registration. |
| `build_widget.ps1`, `validate_widget_zip.py`, `test_widget_package.py` | Package only approved runtime modules and validate the work-area manifest. |
| `docs/api-contract.md`, `Plan.md` | Record exact response extension and, only after verification, phase results. |

---

### Task 1: Group calendar and deterministic KPI boundary

**Files:**
- Create: `backend/app/core/business_time.py`
- Modify: `backend/app/services/kpi_service.py`
- Test: `backend/tests/unit/test_timezone_schedule.py`, `backend/tests/unit/test_models.py`

**Interfaces:**
- Consumes: UTC-naive `datetime`, `WidgetGroup.timezone`, `work_start_time`, `work_end_time`.
- Produces: `business_date(now_utc, zone_name, start, end) -> date`, `shift_start_utc(day, zone_name, start) -> datetime`, `local_period_utc_bounds(day, zone_name) -> tuple[datetime, datetime]`, `minutes_late(now_utc, shift_start) -> int`.

- [ ] **Step 1: Write failing boundary tests.** Freeze the input instant explicitly; do not depend on the computer's current date.

```python
def test_minsk_day_uses_group_calendar():
    from datetime import datetime, time
    from app.core.business_time import business_date
    assert business_date(datetime(2026, 9, 21, 23), "Europe/Minsk", time(9), time(18)).isoformat() == "2026-09-22"

def test_overnight_shift_keeps_start_date():
    from datetime import datetime, time
    from app.core.business_time import business_date
    assert business_date(datetime(2026, 9, 21, 23), "Europe/Minsk", time(22), time(6)).isoformat() == "2026-09-21"
```

Also pin `minutes_late` to zero before shift start and positive whole minutes after it; pin a DST transition with `Europe/Berlin`. In `test_models.py`, use a fixed clock so the existing `test_legacy_consumers_query_canonical_fields_and_correct_account` is independent of the hour it runs.

- [ ] **Step 2: Run red tests.** From `backend`: `..\.venv312\Scripts\python.exe -m pytest -q tests/unit/test_timezone_schedule.py tests/unit/test_models.py::test_legacy_consumers_query_canonical_fields_and_correct_account`. Expect the new helper import/tests to fail before implementation.
- [ ] **Step 3: Implement the helper and replace local-machine `datetime.now()` boundaries in the relevant KPI paths.** Resolve active group membership and zone for each user's KPI; for department KPI aggregate account-scoped users using each user's group-local day. For ungrouped legacy records use UTC as an explicit fallback, not Windows local time. Keep UTC-naive DB comparisons and use aware `ZoneInfo` only inside conversion.

```python
from datetime import timezone
from zoneinfo import ZoneInfo

def local_period_utc_bounds(day, zone_name):
    zone = ZoneInfo(zone_name)
    local_start = datetime.combine(day, time.min, zone)
    local_end = datetime.combine(day + timedelta(days=1), time.min, zone)
    return (local_start.astimezone(timezone.utc).replace(tzinfo=None),
            local_end.astimezone(timezone.utc).replace(tzinfo=None))
```

- [ ] **Step 4: Run focused and full unit tests.** From `backend`: `..\.venv312\Scripts\python.exe -m pytest -q tests/unit/test_timezone_schedule.py tests/unit/test_models.py`; expect pass at any local hour.
- [ ] **Step 5: Commit:** `git add backend/app/core/business_time.py backend/app/services/kpi_service.py backend/tests/unit/test_timezone_schedule.py backend/tests/unit/test_models.py && git commit -m "fix: use group calendar for timesheet and KPI"` (use equivalent separate PowerShell commands).

### Task 2: Durable, concurrent status transitions

**Files:**
- Create: `backend/app/models/timesheet_command.py`, `backend/app/services/timesheet_service.py`, `backend/migrations/versions/011_timesheet_commands.py`
- Modify: `backend/app/models/work_session.py`, `backend/app/models/__init__.py`, `backend/app/models/status_transition.py`
- Test: `backend/tests/unit/test_timesheet_transitions.py`, `backend/tests/integration/test_migrations.py`

**Interfaces:**
- Consumes: Task 1 calendar helpers; verified `RequestContext.account_id` and `context.user`; active `GroupMember`/`WidgetGroup`.
- Produces: `TimesheetService(db).get_status(context, now_utc=None) -> TimesheetSnapshot` and `.apply(context, action: str, key: UUID, now_utc=None) -> TimesheetSnapshot`; `TimesheetSnapshot` is a domain dataclass in this service, and `TimesheetCommand` records account/user/key/action and its JSON response.

- [ ] **Step 1: Write failing service and migration tests.** Create account-scoped users/groups/member fixtures using the patterns in `backend/tests/api/test_settings.py`. Cover `not_started -> working -> on_break -> working -> finished`, invalid transitions, finished restart denied/allowed, repeated same UUID, same UUID on a different action, separate accounts, two concurrent starts, and upgrade/downgrade from revision `010`.

```python
def test_same_key_is_replayed_without_new_transition(service, context):
    key = UUID("11111111-1111-4111-8111-111111111111")
    first = service.apply(context, "start-work", key, now_utc=FIXED_UTC)
    second = service.apply(context, "start-work", key, now_utc=FIXED_UTC + timedelta(seconds=5))
    assert second == first
    assert service.db.query(StatusTransition).count() == 1
```

The fixture constructs a real test database session, `RequestContext`, and active membership; `FIXED_UTC = datetime(2026, 9, 22, 6)`.

- [ ] **Step 2: Run red tests.** From `backend`: `..\.venv312\Scripts\python.exe -m pytest -q tests/unit/test_timesheet_transitions.py tests/integration/test_migrations.py`.
- [ ] **Step 3: Implement the smallest transaction that passes.** Add `business_date` to `WorkSession`; add a command table with unique `(account_id, amocrm_user_id, key)` and response JSON; add a PostgreSQL/SQLite partial unique index for one open session per account/user. Backfill existing sessions' business date from their group zone when unambiguous; if no active group exists, use UTC and record the migration rule in its docstring. Reject pre-existing duplicate open sessions with a diagnostic migration error instead of silently changing history. Lock/recheck inside transaction; catch uniqueness races by rolling back and re-reading the winner. Never let a duplicate action create a second transition. Preserve existing history and legacy routes.

```python
if previous_command is not None:
    if previous_command.action != action:
        raise TimesheetConflict("IDEMPOTENCY_KEY_REUSED")
    return TimesheetSnapshot(**previous_command.response)
if action == "start-work" and current_status == "finished" and not group.allow_restart_session:
    raise TimesheetConflict("STATUS_TRANSITION_INVALID")
```

- [ ] **Step 4: Run focused tests and PostgreSQL migration tests.** From `backend`: `..\.venv312\Scripts\python.exe -m pytest -q tests/unit/test_timesheet_transitions.py tests/integration/test_migrations.py`. Verify only one Alembic head and no data loss on upgrade. Downgrade must reject real new phase-4 data if it would erase it.
- [ ] **Step 5: Commit:** `git add backend/app/models backend/app/services/timesheet_service.py backend/migrations/versions/011_timesheet_commands.py backend/tests/unit/test_timesheet_transitions.py backend/tests/integration/test_migrations.py` then `git commit -m "feat: persist timesheet transitions and command replay"`.

### Task 3: Authenticated timesheet API

**Files:**
- Create: `backend/app/schemas/timesheet.py`, `backend/app/api/v1/timesheet.py`, `backend/tests/api/test_timesheet.py`
- Modify: `backend/app/main.py`, `docs/api-contract.md`

**Interfaces:**
- Consumes: `TimesheetService.get_status/apply` from Task 2, existing `get_request_context` and `enforce_route_scope`.
- Produces: `GET /api/v1/timesheet/my-status`; `POST /api/v1/timesheet/{start-work|start-break|end-break|finish-work}`. Response: `session_id: int|null`, `status`, `started_at`, `ended_at`, `break_seconds`, `track_time`, `hide_widget`, `restart_allowed`; commands add `message`.

- [ ] **Step 1: Write failing endpoint tests.** Reuse the authenticated test-client override pattern in `backend/tests/api/conftest.py`; check all five routes, status-code/shape, no browser ID trust, wrong-account/other-user rejection, `track_time=false`, `hide_widget=true`, and UUID replay.

```python
def test_start_requires_uuid(client):
    response = client.post("/api/v1/timesheet/start-work", json={"idempotency_key": "not-a-uuid"})
    assert response.status_code == 422

def test_no_session_returns_not_started(client):
    response = client.get("/api/v1/timesheet/my-status")
    assert response.status_code == 200
    assert response.json()["status"] == "not_started"
```

- [ ] **Step 2: Run red test:** from `backend`, `..\.venv312\Scripts\python.exe -m pytest -q tests/api/test_timesheet.py`.
- [ ] **Step 3: Implement Pydantic response/request models, route handlers, router registration and public error mapping.** Read account/user only from `RequestContext`; map service invalid transition to `APIProblem(409, "STATUS_TRANSITION_INVALID", "Статус уже изменился. Обновите страницу.")`; map reused-key conflict to a distinct 409 code and disabled tracking to 403. Emit UTC `Z` rather than naive timestamps. Extend `docs/api-contract.md` with the three display flags, without changing the old routes.

```python
class CommandRequest(BaseModel):
    idempotency_key: UUID

@router.post("/start-work", response_model=TimesheetCommandResponse)
def start_work(body: CommandRequest, db: Session = Depends(get_db),
               context: RequestContext = Depends(get_request_context)):
    return TimesheetService(db).apply(context, "start-work", body.idempotency_key)
```

- [ ] **Step 4: Run API, auth and full backend tests.** From `backend`: `..\.venv312\Scripts\python.exe -m pytest -q tests/api/test_timesheet.py tests/integration/test_authorized_routes.py`, then `..\.venv312\Scripts\python.exe -m pytest -q --disable-warnings`. Both runs must pass (document existing skipped tests).
- [ ] **Step 5: Commit:** `git add backend/app/schemas/timesheet.py backend/app/api/v1/timesheet.py backend/app/main.py backend/tests/api/test_timesheet.py docs/api-contract.md` then `git commit -m "feat: expose authenticated timesheet API"`.

### Task 4: Widget transport and fail-open lifecycle

**Files:**
- Create: `widget/timesheet/controller.js`, `frontend/tests/timesheet-controller.test.js`
- Modify: `widget/script.js`, `frontend/tests/widget-lifecycle.test.js`, `package.json`

**Interfaces:**
- Consumes: Task 3 API and existing `apiUrl(widget)`/`$authorizedAjax`; `render(snapshot)` callback from Task 5 overlay.
- Produces: `createTimesheetController({request, render, clear, schedule})` with `load()`, `command(action)`, `destroy()`; no UI exists until a valid snapshot is received.

- [ ] **Step 1: Write failing Node/jsdom tests.** Test initial outage, outage after confirmed `on_break`, invalid JSON, lost POST response/retry same UUID, double click, recovery, focus refresh, `track_time=false`, `hide_widget=true`, and destroy cleanup. Replace the old lifecycle test that currently expects an overlay with no API URL.

```js
test('API outage clears an existing overlay and every button', async () => {
  await controller.load(); // first mock GET confirms on_break
  assert.equal(document.querySelectorAll('.timesheet-overlay').length, 1);
  await controller.load(); // second mock GET rejects
  assert.equal(document.querySelectorAll('.timesheet-overlay, .timesheet-action').length, 0);
});
```

Use a deterministic injected scheduler/request in the test fixture; assert `$authorizedAjax` receives the configured `api_url + '/timesheet/my-status'`, never `/sessions/current`, and sends no browser account/user IDs.

- [ ] **Step 2: Run red test:** `node --test frontend/tests/timesheet-controller.test.js frontend/tests/widget-lifecycle.test.js`.
- [ ] **Step 3: Implement the controller and update `script.js` AMD dependencies.** Remove demo IDs, `$.ajax` working calls, local successful status mutation, and inline fallback. Use one pending UUID per click until outcome is known; after 409 refresh confirmed state; on any uncertain transport/identity failure invoke `clear()` synchronously before scheduling retry. Use configured `api_url`; no hardcoded test/server URL. Keep settings/advanced-settings callbacks working.

```js
function failOpen() {
  state.confirmed = null;
  clear();
  scheduleRetry();
}
```

- [ ] **Step 4: Run frontend suite:** `npm run test:settings` plus `node --test frontend/tests/timesheet-controller.test.js`. Expect both pass, including old settings save/lifecycle behavior.
- [ ] **Step 5: Commit:** `git add widget/script.js widget/timesheet/controller.js frontend/tests/timesheet-controller.test.js frontend/tests/widget-lifecycle.test.js package.json` then `git commit -m "feat: load work status without offline fallback"`.

### Task 5: Namespaced overlay, work locations and package gate

**Files:**
- Create: `widget/overlay.js`, `frontend/tests/overlay.spec.js`
- Modify: `widget/styles.css`, `widget/script.js`, `widget/manifest.json`, `package.json`, `package-lock.json`, `frontend/tests/widget-lifecycle.test.js`, `test_widget_package.py`, `build_widget.ps1`, `validate_widget_zip.py`, `widget/i18n/ru.json`, `widget/i18n/en.json`

**Interfaces:**
- Consumes: confirmed Task 3 snapshot and Task 4 `render/clear` hooks.
- Produces: `createOverlay(document).render(snapshot)` and `.clear()`; never leaves an intercepting element when state is unknown or widget is destroyed.

- [ ] **Step 1: Write failing overlay and package tests.** Assert only server-permitted actions show for each status, `hide_widget`/`track_time=false` mounts nothing, and a network failure after visible overlay removes all interceptors. In the browser check, click an amoCRM mock action and press Tab/Enter: confirmed `on_break` prevents the background action; after `clear()` the same action works. Add package assertions that `overlay.js` and `timesheet/controller.js` are included in `widget.zip` and referenced AMD modules exist.

```js
test('unknown state leaves amoCRM controls usable', async ({ page }) => {
  await page.setContent('<button id="crm-action">CRM action</button>');
  await page.addScriptTag({ path: 'widget/overlay.js' });
  await page.click('#crm-action');
  await expect(page.locator('.timesheet-overlay')).toHaveCount(0);
});
```

- [ ] **Step 2: Prepare and run red tests:** add `@playwright/test` as a dev dependency and install Chromium with `npx playwright install chromium` if it is not already available. Run `node --test frontend/tests/widget-lifecycle.test.js`, `npx playwright test frontend/tests/overlay.spec.js`, and from the repository root `.venv312\Scripts\python.exe -m pytest -q test_widget_package.py`.
- [ ] **Step 3: Implement overlay/CSS and enable work locations.** Move overlay markup and inline CSS from `script.js` into focused `overlay.js` and `.timesheet-*` selectors in `styles.css`. Explicitly constrain focus and pointer events while confirmed blocked; `clear()` removes DOM, event listeners, and focus trap. Keep settings locations and add `everywhere` for the work UI; gate settings callbacks by `widget.system().area`. This name is documented in the [official amoCRM locations list](https://www.amocrm.ru/developers/content/integrations/areas). Update `validate_widget_zip.py` and package tests for the exact expanded runtime list and manifest locations. Ensure `build_widget.ps1` packages the new modules and retains the exact `widget.zip` name. Replace build-time API URL insertion into i18n with a neutral HTTPS example; the native `api_url` field remains the operational source of the address.

```js
if (!snapshot || !snapshot.track_time || snapshot.hide_widget) {
  overlay.clear();
  return;
}
overlay.render(snapshot);
```

- [ ] **Step 4: Run all phase gates.** Backend full pytest, PostgreSQL migration upgrade/downgrade, `npm run test:settings`, controller Node tests, Playwright overlay test, `test_widget_package.py`, `build_widget.ps1`, `validate_widget_zip.py widget.zip`; inspect `git diff --check` and a fresh independent code review. Fix review findings and rerun affected gates. Record exact counts and new/changed files in `Plan.md`; mark phase 4 locally complete but keep live amoCRM check deferred.
- [ ] **Step 5: Commit and push:** stage only reviewed phase-4 files and `Plan.md`, commit `feat: finish phase four work-status UI`, then `git push origin main`. Preserve ignored `.env`, live tokens, and historical archives.

## Completion handoff

Report in Russian: what each task delivered, files created/changed, exact test results, what the user can check locally, and what remains deferred in amoCRM. Do not use the final all-plan phrase until phases 0–9 are implemented and the promised end-to-end manual check plan is written.
