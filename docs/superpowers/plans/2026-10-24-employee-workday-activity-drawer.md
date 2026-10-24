# Employee Workday Activity Drawer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace 24-hour employee activity scales with server-defined workday ranges and open each employee's seven-day activity in a 520px right-side drawer.

**Architecture:** A focused backend helper derives authoritative timeline bounds from all work sessions intersecting a local day, with an eight-hour minimum and the configured group schedule as fallback. The team status and activity-window APIs expose those bounds; the monitoring list and detailed timeline consume them without repeating timezone or role logic. The existing activity modal controller keeps its data lifecycle and accessibility behavior while its presentation changes to a single reusable right-side drawer.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, Pydantic, pytest, vanilla JavaScript AMD/CommonJS modules, Node test runner, jsdom, Playwright, CSS, amoCRM Widget SDK.

**Spec:** `docs/superpowers/specs/2026-10-24-employee-workday-activity-drawer-design.md`

## Global Constraints

- The normal drawer width is `min(520px, 100vw)` and it must not move the amoCRM page.
- A day with sessions starts at the first intersecting session and spans at least eight hours; overtime extends the end to the last session end.
- An open session uses the server's current time as its natural end.
- A day without sessions uses the group's configured work interval, extended to eight hours when shorter.
- `timeline_started_at` and `timeline_ended_at` are authoritative ISO datetime fields; clients must not recalculate role or timezone rules.
- Existing `started_at`, `ended_at`, `shift_started_at`, `shift_ended_at`, seven-day limits, activity totals and access rules remain compatible.
- One drawer instance is reused when another employee is selected.
- Changes follow RED→GREEN TDD, update `Plan.md` after every task, and target 50 amoCRM accounts without account-crossing queries.

## Review Focus

- A late or overnight session whose eight-hour minimum crosses midnight must retain a positive range and all visible events; pin this in Task 1 unit tests and Task 2 API tests.
- Multiple same-day sessions must use the earliest start and latest end rather than only the current session; pin this in Tasks 1 and 2.
- An open session must not use the browser clock or display a negative/future-only span; pin server `now` in Tasks 1 and 2.
- Missing/invalid timeline fields must fail safely without placing segments outside the track; pin fallback and clipping behavior in Task 3.
- Rapidly selecting two employees must leave one drawer showing the second employee without a stale first response; pin request-version behavior in Task 4.

---

### Task 1: Authoritative timeline range helper

**Files:**
- Create: `backend/app/core/activity_timeline_range.py`
- Create: `backend/tests/unit/test_activity_timeline_range.py`
- Modify: `Plan.md`

**Interfaces:**
- Consumes: UTC-aware `day_start`, `day_end`, configured `scheduled_start`, `scheduled_end`, session `(start, optional end)` pairs, and a fixed UTC `now`.
- Produces: `activity_timeline_bounds(*, day_start: datetime, day_end: datetime, scheduled_start: datetime, scheduled_end: datetime, sessions: Sequence[tuple[datetime, datetime | None]], now: datetime, minimum: timedelta = timedelta(hours=8)) -> tuple[datetime, datetime]`.

- [x] **Step 1: Write failing unit tests**

Add tests named:

- `test_uses_schedule_when_day_has_no_sessions`
- `test_extends_short_session_to_eight_hours`
- `test_extends_to_overtime_end`
- `test_combines_multiple_sessions`
- `test_open_session_uses_fixed_now`
- `test_overnight_range_stays_positive_and_contains_session`

Assert exact UTC start/end values and verify input sessions outside the relevant local day do not change the range.

- [x] **Step 2: Run tests and confirm RED**

Run from `backend`: `..\.venv312\Scripts\python.exe -m pytest tests/unit/test_activity_timeline_range.py -q`

Expected: collection/import failure because `activity_timeline_bounds` does not exist.

- [x] **Step 3: Implement the helper**

Create the exact signature above. Normalize datetimes to UTC, select intersecting sessions, use earliest start/latest natural end, apply the eight-hour minimum, and keep a positive range for an overnight interval. Do not import SQLAlchemy models into the core helper.

- [x] **Step 4: Run unit tests and confirm GREEN**

Run: `..\.venv312\Scripts\python.exe -m pytest tests/unit/test_activity_timeline_range.py -q`

Expected: all new tests pass.

- [x] **Step 5: Update phase status and commit**

Mark Task 1 complete in `Plan.md`, list created files and what can be tested.

Commit: `feat: calculate employee activity ranges`

---

### Task 2: Expose timeline bounds through team APIs

**Files:**
- Modify: `backend/app/schemas/team.py`
- Modify: `backend/app/services/team_service.py`
- Modify: `backend/tests/api/test_activity_window.py`
- Modify: `backend/tests/api/test_team_visibility.py`
- Modify: `docs/api-contract.md`
- Modify: `Plan.md`

**Interfaces:**
- Consumes: `activity_timeline_bounds(...)` from Task 1 and `WorkSession` rows scoped by `(account_id, amocrm_user_id)`.
- Produces: required `timeline_started_at: datetime` and `timeline_ended_at: datetime` on `TeamMemberSummary` and `ActivityWindowDay`.

- [x] **Step 1: Write failing API tests for the detailed seven-day response**

Extend `test_activity_window.py` with exact assertions for no-session fallback, two completed sessions, overtime, an open session under fixed server time, an overnight shift, and tenant isolation. Assert legacy calendar/shift fields stay unchanged.

- [x] **Step 2: Write failing API tests for the monitoring response**

Extend `test_team_visibility.py` so the current-day summary exposes the same authoritative bounds for administrator and manager responses while an employee cannot gain access to another user's data.

- [x] **Step 3: Run the focused API tests and confirm RED**

Run from `backend`:

`..\.venv312\Scripts\python.exe -m pytest tests/api/test_activity_window.py tests/api/test_team_visibility.py -q`

Expected: failures because the two timeline fields are absent.

- [x] **Step 4: Implement account-scoped session loading and schema fields**

Add the two datetime fields to both schemas. In `TeamService`, fetch all relevant sessions in bounded queries, group them by employee/day, call Task 1's helper, and serialize UTC values. Keep query count independent of employee count and avoid per-employee database queries.

- [x] **Step 5: Document and verify GREEN**

Document both response fields and their eight-hour/fallback meaning in `docs/api-contract.md`.

Run the focused tests plus the existing query-count tests for 50 users/accounts. Expected: all pass and query counts remain bounded.

- [x] **Step 6: Update phase status and commit**

Mark Task 2 complete in `Plan.md` and record the test totals.

Commit: `feat: expose workday activity bounds`

---

### Task 3: Workday scale and employee-row interaction

**Files:**
- Modify: `frontend/monitoring/dashboard.js`
- Modify: `frontend/monitoring/styles.css`
- Modify: `frontend/tests/monitoring-dashboard.test.js`
- Modify: `frontend/tests/monitoring.spec.js`
- Modify: `Plan.md`

**Interfaces:**
- Consumes: `employee.timeline_started_at`, `employee.timeline_ended_at`, activity segments and `activity_detail_allowed`.
- Produces: `activityScale(document, employee)` relative to the supplied range and an accessible employee row that emits the existing employee-selection behavior by mouse, `Enter`, or `Space`.

- [x] **Step 1: Write failing Node tests for range-relative rendering**

Assert a `09:00–17:00` range places `13:00` at 50%, clips partially overlapping segments, skips invalid segments safely, and renders five labels `09:00`, `11:00`, `13:00`, `15:00`, `17:00` instead of 24-hour labels.

- [x] **Step 2: Write failing interaction tests**

Assert the employee article is focusable only when `activity_detail_allowed=true`; click, `Enter`, and `Space` open that employee; users without permission remain noninteractive; the inline scale is not a nested button.

- [x] **Step 3: Run monitoring tests and confirm RED**

Run: `node --test frontend/tests/monitoring-dashboard.test.js`

Expected: failures showing 1440-minute placement and missing row keyboard behavior.

- [x] **Step 4: Implement range utilities and row behavior**

Add focused helpers for parsing bounds, formatting five ticks and projecting segments. Reuse `openActivity(employee, row)`; preserve request cancellation, polling, filters and role behavior.

- [x] **Step 5: Verify Node and browser GREEN**

Run:

- `node --test frontend/tests/monitoring-dashboard.test.js`
- `npx playwright test frontend/tests/monitoring.spec.js`

Expected: all monitoring-list tests pass and no nested interactive element appears.

- [x] **Step 6: Update phase status and commit**

Mark Task 3 complete in `Plan.md` and record files and test totals.

Commit: `feat: scale monitoring to employee workday`

---

### Task 4: Detailed workday timeline in a reusable right drawer

**Files:**
- Modify: `frontend/monitoring/timeline.js`
- Modify: `frontend/monitoring/activity-modal.js`
- Modify: `frontend/monitoring/styles.css`
- Modify: `frontend/tests/monitoring-timeline.test.js`
- Modify: `frontend/tests/monitoring-dashboard.test.js`
- Modify: `frontend/tests/monitoring.spec.js`
- Modify: `Plan.md`

**Interfaces:**
- Consumes: `ActivityWindowDay.timeline_started_at`, `timeline_ended_at`, existing intervals and payload timezone.
- Produces: `Timeline.normalizeDay(day)` clipped to the authoritative workday range and the existing `ActivityModal.create(...)` controller rendered as one reusable right drawer.

- [x] **Step 1: Write failing timeline tests**

Change fixtures to include timeline fields. Assert an eight-hour day has `durationMinutes=480`, hour labels use the work range, overtime widens the track, point/interval grouping remains one horizontal lane, and legacy calendar fields no longer determine placement.

- [x] **Step 2: Write failing drawer behavior and layout tests**

Assert the panel is anchored right, has a `520px` desktop width, full mobile width, does not alter amoCRM content geometry, closes by close button/backdrop/`Escape`, restores focus, preserves fullscreen and zoom, and updates in place when a second employee is selected.

- [x] **Step 3: Write the stale-response regression test**

Start requests for employees A then B, resolve A last, and assert the single drawer still shows B with B's data.

- [x] **Step 4: Run focused tests and confirm RED**

Run:

- `node --test frontend/tests/monitoring-timeline.test.js frontend/tests/monitoring-dashboard.test.js`
- `npx playwright test frontend/tests/monitoring.spec.js`

Expected: failures for 24-hour duration, centered modal geometry and/or stale content.

- [x] **Step 5: Implement authoritative timeline bounds**

Update `normalizeDay(day)` to require valid timeline bounds, clip intervals to them, and keep tooltip times/durations from source data. Render five evenly spaced labels synchronized with zoom.

- [x] **Step 6: Convert the modal presentation to a drawer**

Keep the exported `create`, `open`, `update`, `close`, `destroy`, `isOpen` API. Change DOM/CSS behavior to a fixed right-side panel with backdrop dismissal and one reusable instance; preserve focus trap, cleanup, fullscreen and tooltip behavior.

- [x] **Step 7: Verify focused and complete frontend GREEN**

Run all Node tests: `node --test frontend/tests/*.test.js`

Run all browser tests: `npx playwright test frontend/tests/*.spec.js`

Expected: every frontend and Playwright test passes.

- [x] **Step 8: Update phase status and commit**

Mark Task 4 complete in `Plan.md`, list modified files and what can be checked locally.

Commit: `feat: open employee activity in workday drawer`

---

### Task 5: Release 3.0.28 and live role verification

**Files:**
- Modify: `widget/manifest.json`
- Modify: `widget/script.js`
- Modify: `validate_widget_zip.py`
- Modify: `test_widget_package.py`
- Modify: `frontend/tests/widget-lifecycle.test.js`
- Modify: `docs/release-checklist.md`
- Modify: `Plan.md`

**Interfaces:**
- Consumes: completed Tasks 1–4.
- Produces: validated `widget.zip` version `3.0.28` and live evidence for administrator, manager and employee behavior.

- [ ] **Step 1: Write failing package/version tests**

Change expected version and all eight AMD runtime URLs from `3.0.27` to `3.0.28`, then run package and lifecycle tests to confirm RED before production version files change.

- [ ] **Step 2: Update release version and confirm package GREEN**

Update manifest, AMD URLs and validator constant to `3.0.28`.

Run:

- `.\.venv312\Scripts\python.exe -m unittest test_widget_package.py`
- `node --test frontend/tests/widget-lifecycle.test.js`

Expected: all pass with one consistent version.

- [ ] **Step 3: Run the complete release gate**

Run from `backend`: `..\.venv312\Scripts\python.exe -m pytest -q --tb=short` and `..\.venv312\Scripts\python.exe -m alembic heads`.

Run from the repository root:

- `node --test frontend/tests/*.test.js`
- `npx playwright test frontend/tests/*.spec.js`
- `powershell -NoProfile -File build_widget.ps1`
- `.\.venv312\Scripts\python.exe validate_widget_zip.py widget.zip`
- `git diff --check`

Record exact totals, file count, archive size and SHA-256 in `Plan.md` and `docs/release-checklist.md`.

- [ ] **Step 4: Review the complete diff**

Review access isolation, session batching, timezone/overnight calculations, stale selection handling, accessibility and package contents. Fix every Critical/Important finding through a new RED→GREEN cycle.

- [ ] **Step 5: Upload and verify in Edge**

Upload `widget.zip` to the private amoCRM integration. Verify:

- administrator and manager see workday-scaled rows and can open each permitted employee;
- employee sees only permitted self data;
- the drawer is `520px`, opens on the right without shifting amoCRM, replaces its contents when another employee is selected, and closes correctly;
- historical test activity and explanations remain visible;
- local and public `/health/ready` return `200`.

- [ ] **Step 6: Finish documentation and push**

Mark every completed task in this plan and `Plan.md`, list all created/modified files and user-checkable steps, commit release evidence, and push `main` to GitHub.

Commit: `release: publish widget 3.0.28`
