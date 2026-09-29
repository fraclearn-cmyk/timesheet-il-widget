# Phase 6 Monitoring and Seven-Day Activity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an account-scoped team monitor and a secure seven-calendar-day activity window for administrators and group managers.

**Architecture:** The existing `/api/v1/team` router remains the boundary, but its phase-6 paths use strict response schemas and a rewritten bulk-query read service over `WidgetGroup`, `GroupMember`, `WorkSession`, and phase-5 `ActivityInterval`. The widget mounts a small monitoring launcher and a self-contained vanilla-JavaScript dashboard; it polls one summary per open account, loads detail only for the selected employee, and renders confirmed intervals as green segments without inventing duration for point events.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, PostgreSQL 15/SQLite tests, Pydantic v2, vanilla AMD/UMD JavaScript, Node test runner, jsdom, Playwright Chrome, pytest.

**Spec:** `Plan.md`, section `Фаза 6. API мониторинга и окно активности`; phase-5 activity semantics in `docs/superpowers/specs/2026-09-23-amocrm-event-ingestion-activity-design.md`.

## Global Constraints

- Every query is scoped by the verified `RequestContext.account_id`; request path, query, browser account ID, and browser user ID are never authority.
- Status visibility is: verified admin sees all active account groups/users; verified manager sees active members of groups they manage plus self; employee sees only self.
- Activity detail is stricter: verified admin may view an active user in the account; verified manager may view an active member of an active group they currently manage; employees cannot open detail, and a manager's self row has no detail unless self is an active member of a managed group.
- Unauthorized, foreign-account, inactive, and inaccessible targets return the same stable `404 NOT_FOUND` response without existence disclosure.
- `from` and `to` are inclusive local calendar dates in the target user's group timezone; both are required and the inclusive range is `1..7` dates.
- Stored timestamps remain naive UTC. API timestamps are emitted as ISO 8601 UTC with `Z`; calendar labels and shift bounds are derived from the group timezone, including overnight shifts and DST.
- Only `kind=confirmed` intervals are green. `unconfirmed_input` remains non-green and communicates “Нет подтверждённой активности”. A zero-duration CRM event remains a point with `duration_source=point`, drawn as a marker without changing its duration.
- Tooltip data uses text nodes and validated server values. User or CRM text is never inserted with `innerHTML`; outbound card links use `target=_blank` and `rel=noopener noreferrer`.
- No phase-6 migration is planned: phase 5 already stores every required interval field. Optional card/call metadata is resolved in bounded bulk queries from normalized evidence; no raw payload is exposed.
- Capacity target is at least 40 active accounts: one status request per visible dashboard, no per-user API fan-out, constant-count bulk SQL per request, detail only for one selected user, no process-global tenant cache or lock, and bounded polling backoff `30s -> 60s -> 120s -> 240s -> 300s` with jitter and one timer per dashboard.
- Polling pauses while the page is hidden, resumes with an immediate refresh, preserves the selected user/modal/zoom state, and never overlaps an in-flight request.
- Existing phase-5 ingestion, presence, widget overlay, settings, package security, and deferred live amoCRM gates must keep passing.
- User-facing failures are simple Russian messages; technical details stay in structured server logs and no secrets or raw activity payloads enter browser/server logs.

## Review Focus

- Duplicate external user IDs in different accounts must never leak status or intervals; Tasks 1 and 2 pin account scope with 40-account fixtures.
- A manager whose role snapshot changed, an inactive membership, or a self row outside the managed group must not gain activity detail; Task 2 pins each case.
- Seven dates across an overnight shift or DST boundary must remain seven local calendar dates even when UTC duration is not 168 hours; Task 2 pins local-date bounds.
- Point events, overlapping confirmed intervals, and intervals clipped at the requested window must render without inventing time or hiding empty gaps; Task 3 pins normalization and geometry.
- A failed/slow refresh must not start overlapping requests, clear the current employee, or spin timers for 40 accounts; Task 4 pins backoff, cancellation, and state preservation.

---

### Task 1: Strict team-status contract and bulk visibility read model

**Files:**
- Modify: `backend/app/schemas/team.py`
- Modify: `backend/app/services/team_service.py`
- Modify: `backend/app/api/v1/team.py`
- Create: `backend/tests/api/test_team_visibility.py`
- Modify: `backend/tests/integration/test_authorized_routes.py`
- Modify: `backend/tests/integration/test_request_context.py`

**Interfaces:**
- Consumes: `RequestContext`, `AccessPolicy.is_admin()`, `AccessPolicy.is_manager()`, active `WidgetGroup`/`GroupMember`, `WorkSession`, `ActivityInterval`, and `utc_now()`.
- Produces: `TeamStatusResponse`, `TeamGroupSummary`, `TeamMemberSummary`, `TeamStatusTotals`; `TeamService.get_monitoring_status(context, *, search, status_filter, group_id, now) -> TeamStatusResponse`; phase-6 `GET /api/v1/team/status`.

- [x] **Step 1: Write failing role/account/filter tests**

In `test_team_visibility.py`, create admin, manager, employee, inactive membership, stale manager-role snapshot, ungrouped user, and duplicate external IDs in a foreign account. Assert:

```python
response = actor("manager").get("/api/v1/team/status?search=Петр&status=working")
assert response.status_code == 200
assert response.json()["viewer"]["role"] == "manager"
assert {row["amocrm_user_id"] for row in response.json()["employees"]} == {manager_id, managed_member_id}
assert all(row["account_id"] == own_account for row in response.json()["employees"])
```

Also assert admin visibility, employee self-only visibility, inactive/stale assignments excluded, inaccessible `group_id` returns stable 404, invalid status returns 422, case-insensitive trimmed search works, and response ordering is group name/name/id stable.

- [x] **Step 2: Write failing aggregate/capacity tests**

Seed open/finished/multiple sessions and confirmed/unconfirmed intervals. Assert canonical statuses `working|on_break|finished|not_started`, UTC `Z` timestamps, group timezone/workday bounds, and summary totals. Seed 40 accounts with repeated amoCRM user IDs and assert each verified account receives only its own rows. Instrument SQLAlchemy and assert one status request uses a constant bounded number of SELECTs (target at most 8), independent of 1 versus 40 visible employees.

- [x] **Step 3: Run RED**

Run from `backend/`:

```powershell
..\.venv312\Scripts\python.exe -m pytest tests/api/test_team_visibility.py -q --tb=short
```

Expected: schema/service assertions fail because the endpoint still returns the legacy list and performs per-user CRM queries.

- [x] **Step 4: Add strict monitoring schemas**

All phase-6 schemas use `ConfigDict(extra="forbid")`. Define exact response fields:

```python
class TeamMemberSummary(BaseModel):
    id: int                       # internal, account-scoped API reference
    amocrm_user_id: int
    account_id: int
    name: str
    avatar_url: str | None
    group_id: int | None
    group_name: str | None
    timezone: str
    workday_started_at: datetime
    workday_ended_at: datetime
    status: Literal["working", "on_break", "finished", "not_started"]
    status_since: datetime | None
    session_started_at: datetime | None
    session_ended_at: datetime | None
    work_seconds: int
    break_seconds: int
    confirmed_seconds: int
    confirmed_events: int
    activity_detail_allowed: bool

class TeamStatusResponse(BaseModel):
    generated_at: datetime
    viewer: TeamViewer              # role + can_view_activity
    groups: list[TeamGroupSummary]
    employees: list[TeamMemberSummary]
    totals: TeamStatusTotals
```

Response serialization must append `Z` to UTC-naive persisted values. Keep old timeline/stats schemas for old routes until a later cleanup; do not silently reuse their 15-minute buckets.

- [x] **Step 5: Implement the bulk read service and route**

Implement `TeamService.get_monitoring_status(...)` with set-based queries: resolve visible groups/members once, include viewer self, load relevant sessions once, and aggregate interval counts/durations once. Clamp intervals to each local workday before summing. Apply search/status/group filters server-side after visibility is fixed. Do not call `AccessPolicy.can_view_user()` in a loop and do not query CRM events per employee.

Change only `GET /status` to return `TeamStatusResponse`. Keep `/stats`, `/activity`, legacy timeline, and force-finish routes behavior-compatible. Use `Query(alias="status")` for the public status filter and `APIProblem`/`not_found()` for stable Russian errors.

- [x] **Step 6: Run GREEN and route regressions**

```powershell
..\.venv312\Scripts\python.exe -m pytest tests/api/test_team_visibility.py tests/integration/test_authorized_routes.py tests/integration/test_request_context.py -q --tb=short
```

Expected: all pass; the updated legacy assertions consume the new status envelope while unrelated routes retain their contracts.

- [x] **Step 7: Independent review and commit**

Review specifically for N+1 queries, account scope, stale role snapshots, self visibility, and incorrect status/day boundaries. Then:

```powershell
git add backend/app/schemas/team.py backend/app/services/team_service.py backend/app/api/v1/team.py backend/tests/api/test_team_visibility.py backend/tests/integration/test_authorized_routes.py backend/tests/integration/test_request_context.py
git commit -m "feat: add account-scoped team monitoring status"
```

---

### Task 2: Seven-calendar-day activity detail API

**Files:**
- Modify: `backend/app/core/access_policy.py`
- Modify: `backend/app/core/business_time.py`
- Modify: `backend/app/schemas/team.py`
- Modify: `backend/app/services/team_service.py`
- Modify: `backend/app/api/v1/team.py`
- Create: `backend/tests/api/test_activity_window.py`
- Modify: `backend/tests/unit/test_timezone_schedule.py`

**Interfaces:**
- Consumes: Task 1 internal user references and viewer scope; `ActivityInterval`, `CrmEvent`, `CallEvent`, group timezone/schedule.
- Produces: `AccessPolicy.can_view_activity_detail(target) -> bool`; `local_date_range_utc_bounds(from_date, to_date, zone_name)`; `TeamService.get_activity_window(context, target_user_id, from_date, to_date) -> ActivityWindowResponse`; `GET /api/v1/team/{user_id}/activity?from=YYYY-MM-DD&to=YYYY-MM-DD`.

- [x] **Step 1: Write failing access/range tests**

Assert admin succeeds, manager succeeds only for an active member of an active group managed with the current role snapshot, employee receives the same 404 for self/other, manager self outside the managed membership receives 404, and foreign/inactive/missing targets are indistinguishable. Assert missing/invalid dates fail validation, reversed dates return `400 ACTIVITY_RANGE_INVALID`, and eight inclusive dates return `400 ACTIVITY_RANGE_TOO_LARGE` with “Можно выбрать не больше 7 календарных дней.”

- [x] **Step 2: Write failing timezone and response tests**

Cover a seven-date range through a DST change and an overnight schedule. Seed confirmed point, calculated CRM, measured call, unconfirmed presence, overlap, and boundary-crossing intervals. Assert UTC clipping, local day assignment, no raw payload, correct aggregates, stable chronological order, point duration zero, call metadata, and `card_url` only when bounded normalized evidence matches.

- [x] **Step 3: Run RED**

```powershell
..\.venv312\Scripts\python.exe -m pytest tests/api/test_activity_window.py tests/unit/test_timezone_schedule.py -q --tb=short
```

- [x] **Step 4: Add strict detail access and local-date helpers**

`can_view_activity_detail()` must not inherit `can_view_user()` self access. It allows verified admin, or a verified manager whose current user/role pair owns an active group containing the active target membership. Add a helper that converts inclusive local dates to a half-open UTC range `[from 00:00 local, day-after-to 00:00 local)` without assuming 24-hour days.

- [x] **Step 5: Implement the bounded detail service**

Load the target/group once, validate access and inclusive range before activity queries, then fetch all overlapping intervals with:

```python
ActivityInterval.account_id == context.account_id
ActivityInterval.user_id == target.id
ActivityInterval.started_at < utc_end
ActivityInterval.ended_at >= utc_start
```

Clamp presentation bounds, preserve stored `duration_source`, and split presentation across local dates only when an interval crosses a local midnight. Resolve optional `card_url`, call direction and measured duration using at most two bulk evidence queries; never read/expose raw envelopes. The response contains target/group metadata, requested dates/timezone, totals, and `days[]` with shift bounds plus ordered interval DTOs.

- [x] **Step 6: Add the route and stable errors**

Use internal `user_id` from Task 1. Declare `from_date: date = Query(alias="from")` and `to_date: date = Query(alias="to")`. Emit `404 NOT_FOUND` for all access/identity failures and stable Russian `400` errors for range failures.

- [x] **Step 7: Run GREEN plus phase-5 interval regressions**

```powershell
..\.venv312\Scripts\python.exe -m pytest tests/api/test_activity_window.py tests/unit/test_timezone_schedule.py tests/unit/test_activity_intervals.py tests/integration/test_activity_ingestion.py -q --tb=short
```

- [x] **Step 8: Independent review and commit**

```powershell
git add backend/app/core/access_policy.py backend/app/core/business_time.py backend/app/schemas/team.py backend/app/services/team_service.py backend/app/api/v1/team.py backend/tests/api/test_activity_window.py backend/tests/unit/test_timezone_schedule.py
git commit -m "feat: expose bounded activity windows"
```

---

### Task 3: Safe timeline geometry, zoom and tooltip rendering

**Files:**
- Create: `frontend/monitoring/timeline.js`
- Create: `frontend/monitoring/activity-modal.js`
- Create: `frontend/monitoring/styles.css`
- Create: `frontend/tests/monitoring-timeline.test.js`
- Modify: `package.json`

**Interfaces:**
- Consumes: Task 2 `ActivityWindowResponse.days[].intervals`.
- Produces: `Timeline.normalizeDay(day)`, `Timeline.layoutDay(day, zoom)`, `Timeline.render(root, day, options)`; `ActivityModal.create(options)` with `open(payload)`, `update(payload)`, `close()`, `destroy()`, `isOpen()`.

- [x] **Step 1: Write failing Node/jsdom tests**

Test confirmed duration segments, zero-duration point markers, non-green unconfirmed spans, overlap lanes/merge policy, clipping, empty gaps, local/DST labels, zoom `1|2|4`, tooltip fields, safe text rendering, safe card links, Escape close, focus return, body scroll restoration, and fullscreen class/ARIA toggle.

- [x] **Step 2: Run RED**

```powershell
node --test frontend/tests/monitoring-timeline.test.js
```

- [x] **Step 3: Implement the pure timeline module**

Use UMD so Node tests and amoCRM AMD both load it. Geometry is based on each day's explicit API UTC bounds; gaps remain visible. Confirmed duration is green; confirmed points are accessible markers with minimum visual width only; unconfirmed intervals use a neutral hatch and never contribute to green totals. Zoom changes pixels-per-minute/scroll width, not data or durations.

- [x] **Step 4: Implement the modal controller**

Create DOM with `createElement`/`textContent`. The modal shows seven day rows, totals, zoom controls, loading/error/empty states, close button, Escape handling, focus trap/return, and fullscreen toggle using an internal CSS class with the Fullscreen API as progressive enhancement. It must update in place when polling refreshes the selected employee.

- [x] **Step 5: Run GREEN**

```powershell
node --test frontend/tests/monitoring-timeline.test.js
```

- [x] **Step 6: Independent review and commit**

Review XSS, accessibility, zero-duration semantics, timezone labels, listener cleanup, and geometry. Then:

```powershell
git add frontend/monitoring/timeline.js frontend/monitoring/activity-modal.js frontend/monitoring/styles.css frontend/tests/monitoring-timeline.test.js package.json
git commit -m "feat: render safe activity timelines"
```

---

### Task 4: Monitoring dashboard, polling and amoCRM widget integration

**Files:**
- Create: `frontend/monitoring/dashboard.html`
- Create: `frontend/monitoring/dashboard.js`
- Create: `frontend/tests/monitoring-dashboard.test.js`
- Create: `frontend/tests/monitoring.spec.js`
- Modify: `widget/script.js`
- Modify: `widget/styles.css`
- Modify: `frontend/tests/widget-lifecycle.test.js`
- Modify: `frontend/tests/widget-working.spec.js`
- Modify: `build_widget.ps1`
- Modify: `validate_widget_zip.py`
- Modify: `test_widget_package.py`
- Modify: `package.json`

**Interfaces:**
- Consumes: Tasks 1–3 APIs/modules and existing `widget.$authorizedAjax`/`api_url`/`settings.path`.
- Produces: `MonitoringDashboard.mount(root, {transport, schedule, now, random, document})`; a widget “Сотрудники” launcher; packaged `monitoring/dashboard.js`, `monitoring/activity-modal.js`, `monitoring/timeline.js`, `monitoring/styles.css`.

- [ ] **Step 1: Write failing controller tests**

In jsdom, assert grouped employee rows, Russian status labels, server-side search/status/group parameters, hamburger visibility from `activity_detail_allowed`, exact seven-date detail request, manual refresh, selected employee preservation, modal in-place refresh, and clean destroy/remount.

Use a fake scheduler to assert one in-flight status request, success returns to 30 seconds, failures follow bounded `30/60/120/240/300` seconds with ±10% injected jitter, page-hidden cancels the timer, visibility resumes immediately, and stale/aborted responses cannot overwrite newer state.

- [ ] **Step 2: Run dashboard RED**

```powershell
node --test frontend/tests/monitoring-dashboard.test.js frontend/tests/widget-lifecycle.test.js
```

- [ ] **Step 3: Implement dashboard and standalone harness**

`dashboard.js` is UMD and receives a transport rather than reading browser identity. It renders group sections, totals, employees, status, shift/aggregate values, search/status/group controls, a manual “Обновить” button, last-success time, and simple Russian error text. Preserve `selectedUserId`, open modal and zoom across refresh. `dashboard.html` is a credential-free local/demo harness and does not hardcode an API URL.

- [ ] **Step 4: Integrate with the widget lifecycle**

Add AMD dependencies for the three monitoring modules. Mount one owned host/launcher in normal `everywhere` operation and call only `$authorizedAjax` against `apiUrl(widget) + '/team/...'`. Load monitoring CSS from the widget asset path. Do not mount in `settings`/`advanced_settings`; do not disturb native amoCRM nodes, settings controller, activity tracker, or overlay. `destroy()` removes timers, requests/listeners, modal, styles and owned DOM. Backend failure leaves amoCRM usable.

- [ ] **Step 5: Write browser acceptance tests**

Mock authorized status/detail responses and verify admin grouping, manager self plus own group, employee self-only/no hamburger, filters, manual/poll refresh, preserved selection, seven-day modal, green bars, visible empty gaps, tooltip, zoom, Escape, fullscreen toggle, backend failure/backoff, and no unauthorized direct `fetch`/identity headers.

- [ ] **Step 6: Extend and verify the exact widget package**

Add the four monitoring runtime files to the allowlists/build map, raising the exact archive count from 19 to 23. Keep `dashboard.html` outside the production ZIP. Update dependency validation and lifecycle/package tests.

Run:

```powershell
node --test frontend/tests/monitoring-dashboard.test.js frontend/tests/monitoring-timeline.test.js frontend/tests/widget-lifecycle.test.js frontend/tests/settings-controller.test.js frontend/tests/settings-smoke.test.js frontend/tests/timesheet-controller.test.js frontend/tests/activity-tracker.test.js
npx playwright test frontend/tests/monitoring.spec.js frontend/tests/widget-working.spec.js frontend/tests/activity-tracker.spec.js frontend/tests/overlay.spec.js
..\.venv312\Scripts\python.exe -m unittest test_widget_package.py
powershell -ExecutionPolicy Bypass -File .\build_widget.ps1
..\.venv312\Scripts\python.exe validate_widget_zip.py widget.zip
```

- [ ] **Step 7: Independent review and commit**

```powershell
git add frontend/monitoring frontend/tests/monitoring-dashboard.test.js frontend/tests/monitoring.spec.js frontend/tests/widget-lifecycle.test.js frontend/tests/widget-working.spec.js widget/script.js widget/styles.css build_widget.ps1 validate_widget_zip.py test_widget_package.py package.json widget.zip
git commit -m "feat: add team monitoring dashboard"
```

---

### Task 5: Phase-wide verification, documentation and Plan.md status

**Files:**
- Modify: `docs/API.md`
- Modify: `docs/development-workflow.md` only if the phase reveals a new repeatable gate
- Modify: `Plan.md`
- Modify: phase-6 progress/report artifacts under `.superpowers/sdd/2026-09-28-phase6-monitoring-activity/`

**Interfaces:**
- Consumes: Tasks 1–4 and the phase-6 acceptance criteria.
- Produces: reviewed phase-6 implementation, reproducible verification evidence, updated user-checkable scenarios, and checked phase/tasks in `Plan.md`.

- [ ] **Step 1: Run focused backend and PostgreSQL gates**

```powershell
cd backend
..\.venv312\Scripts\python.exe -m pytest tests/api/test_team_visibility.py tests/api/test_activity_window.py tests/unit/test_timezone_schedule.py tests/unit/test_activity_intervals.py tests/integration/test_authorized_routes.py tests/integration/test_request_context.py -q --tb=short
$env:TEST_POSTGRES_ADMIN_URL='postgresql://phase5_test@127.0.0.1:55435/postgres'
..\.venv312\Scripts\python.exe -m pytest tests/api/test_team_visibility.py tests/api/test_activity_window.py tests/integration/test_activity_ingestion.py -q --tb=short
```

- [ ] **Step 2: Run the complete backend/frontend/browser/package gates**

```powershell
cd backend
..\.venv312\Scripts\python.exe -m pytest -q --tb=short
cd ..
node --test frontend/tests/*.test.js
npx playwright test frontend/tests/*.spec.js
..\.venv312\Scripts\python.exe -m unittest test_widget_package.py
powershell -ExecutionPolicy Bypass -File .\build_widget.ps1
..\.venv312\Scripts\python.exe validate_widget_zip.py widget.zip
cd backend
..\.venv312\Scripts\python.exe -m alembic heads
```

Expected: all pass, exactly one `013 (head)`, and exactly 23 widget runtime files. Phase 6 adds no migration.

- [ ] **Step 3: Run final security/capacity checks**

Run `git diff --check`, Black check for changed Python, `compileall`, and review that 40-account fixtures stay account-isolated, status SQL count is bounded, polling has one timer/request, raw payloads are absent, tooltip rendering has no unsafe HTML, and Excel/export files were not changed to include activity.

- [ ] **Step 4: Independent whole-phase review**

Review the complete phase diff against `Plan.md` lines 228–251, with explicit verdicts for all eight task checkboxes and the 40-account constraint. Fix every Critical/Important issue and rerun affected plus full gates.

- [ ] **Step 5: Update documentation and Plan.md only from fresh evidence**

Document the two endpoints and exact visibility/range/error contracts in `docs/API.md`. In `Plan.md`, check all eight phase-6 tasks, change the phase table row to `Локально выполнена; live gate отложен`, update “Таблица прогресса”, “Что сделано”, “Что можно проверить”, “Блокеры”, current-status paragraph, and change log with exact fresh counts/files. State the manual checks now available: role visibility, filters, activity button, seven-day limit, green/empty timeline, tooltip, zoom, Escape/fullscreen, manual refresh/backoff, and absence of activity in Excel.

- [ ] **Step 6: Commit**

```powershell
git add docs/API.md docs/development-workflow.md Plan.md
git commit -m "docs: mark phase six locally complete"
```

## Self-Review Record

- Spec coverage: all eight phase-6 checkboxes map to Tasks 1–4; final status/documentation maps to Task 5.
- Type consistency: UI uses internal `TeamMemberSummary.id` for the detail route and never treats amoCRM IDs as interchangeable internal references.
- Review focus: tenant duplication, role drift, seven local dates/DST, point/overlap/gap geometry, and polling races each have an owning test step.
- Migration decision: no schema addition is needed because normalized evidence and `ActivityInterval` contain the required display facts; bounded matching supplies optional link/call metadata.
- Phase-5 conflict check: new monitoring uses read-only phase-5 data, `$authorizedAjax`, existing `013` head, and does not change ingestion/interval derivation or Excel exports.
