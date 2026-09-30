# Phase 7 Timesheet Reports and Excel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a role-scoped timesheet preview and Excel export for one day through three calendar months, with ten rows per page and no activity, CRM event, call, or card-link data.

**Architecture:** Add a strict report-period validator and a new read-only `TimesheetReportService` beside the legacy reporting service. JSON preview and XLSX export consume the same canonical employee-day rows, while the widget UI uses only `$authorizedAjax` and safe DOM APIs. Existing legacy routes remain available for compatibility.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, PostgreSQL 15, Pydantic, openpyxl, vanilla JavaScript/AMD, jsdom Node tests, Playwright.

**Spec:** `Plan.md` Phase 7 and `docs/api-contract.md` section “Отчёт и экспорт”.

## Global Constraints

- Execute Tasks 1–6 in order and update `Plan.md` only from fresh evidence.
- Account, user and current amoCRM rights come only from verified `RequestContext`; browser identity fields are forbidden.
- `admin` sees tracked members of all active groups in the account; a current `manager` sees tracked members of active groups they manage; `employee` cannot access reports or export.
- An inaccessible `group_id` or `user_id` returns the same `404 NOT_FOUND`; an employee viewer receives `403 ACCESS_DENIED`.
- `user_id` is the internal account-scoped `User.id`; responses also expose `amocrm_user_id` for display/integration only.
- A row is one user plus one `business_date`; repeated same-day sessions are merged before pagination.
- The inclusive range is one day through three calendar months. `date_to <= add_calendar_months(date_from, 3)`; invalid order and over-limit ranges use stable Russian errors.
- Page size is fixed at ten rows. Ordering is `business_date DESC`, normalized employee name, internal user ID.
- Only active users with active `GroupMember.track_time=true` in active widget groups are included.
- Times are stored in UTC and displayed/exported in the row group’s current timezone. This phase does not add historical group/timezone snapshots.
- Excel has an explicit allowlist of timesheet columns. Activity intervals, CRM events, calls, payloads and card links never enter report DTOs or workbook generation.
- Preserve legacy reports/excel routes; no database migration unless PostgreSQL evidence proves an index is required.
- Capacity fixtures cover 40 accounts with duplicate external IDs and bounded bulk SQL queries.

## Review Focus

- Month-end range arithmetic: January 31 allows through April 30 and rejects May 1.
- Repeated same-day sessions: merge without duplicate rows, double lateness or pagination gaps.
- Open working/break sessions: totals are computed at one injected `now`, without trusting stale counters.
- Tenant and role isolation: duplicate external IDs across 40 accounts never affect rows, totals or exports.
- Spreadsheet safety: formula-like text, filenames and selected columns cannot inject formulas, paths, activity fields or hidden links.

---

### Task 1: Strict report period and DTO contracts

**Files:**
- Create: `backend/app/core/report_period.py`
- Modify: `backend/app/schemas/report.py`
- Test: `backend/tests/unit/test_report_period.py`

**Interfaces:**
- Produces: `maximum_report_date(date_from: date) -> date`, `validate_report_period(date_from: date, date_to: date) -> None`.
- Produces: `TimesheetColumn`, `DetailedReportRow`, `DetailedReportTotals`, `DetailedReportResponse`, `ReportExcelRequest`.
- Errors: `ReportPeriodError(code, message)` with `REPORT_DATE_RANGE_INVALID` or `REPORT_RANGE_LIMIT`.

- [x] **Step 1: Write failing period and schema tests**

Cover one day, seven days, exact one/three calendar months, leap/month-end clamping, reversed dates, one day beyond the limit, fixed positive page, duplicate/unknown/empty Excel columns, and an allowlist containing only employee, date, start, end, break, work, lateness and status fields.

- [x] **Step 2: Run RED**

```powershell
Set-Location backend
& ..\.venv312\Scripts\python.exe -m pytest tests/unit/test_report_period.py -q --tb=short
```

- [x] **Step 3: Implement the validator and DTOs**

Use calendar-month arithmetic without adding a dependency. DTOs must reject extra fields and must not define activity, CRM, call, URL or payload properties.

- [x] **Step 4: Run GREEN and contract regressions**

```powershell
& ..\.venv312\Scripts\python.exe -m pytest tests/unit/test_report_period.py tests/unit/test_models.py -q --tb=short
```

- [x] **Step 5: Independent review and commit**

Review range boundaries, error text, column allowlist and DTO leakage. Commit as `feat: define strict timesheet report contracts`.

---

### Task 2: Role-scoped detailed timesheet API

**Files:**
- Create: `backend/app/services/timesheet_report_service.py`
- Modify: `backend/app/api/v1/reports.py`
- Test: `backend/tests/api/test_reports.py`

**Interfaces:**
- Consumes: Task 1 validator and DTOs; existing `RequestContext`, `AccessPolicy`, `business_date`, group schedules, sessions and transitions.
- Produces: `TimesheetReportService.list_rows(context, date_from, date_to, group_id, user_id, page, now) -> DetailedReportResponse`.
- Produces: `GET /api/v1/reports/detailed?date_from=&date_to=&group_id=&user_id=&page=`.

- [x] **Step 1: Write failing scope and aggregation tests**

Assert admin/manager visibility, employee 403, uniform 404 for foreign/inactive group or user, active tracked membership, empty-filter scoping, several same-day sessions merged into one row, first-session lateness, current/final status, overnight/DST dates, stable ten-row pages and page bounds.

- [x] **Step 2: Add failure-mode and capacity tests**

Assert reversed/over-limit Russian errors, no activity-shaped fields, duplicate external IDs in 40 foreign accounts, and the same bounded SELECT count for one and at least 40 visible employees.

- [x] **Step 3: Run RED**

```powershell
Set-Location backend
& ..\.venv312\Scripts\python.exe -m pytest tests/api/test_reports.py -q --tb=short
```

- [x] **Step 4: Implement account-scoped row selection**

Select distinct `(internal_user_id, business_date)` keys before pagination, then bulk-load the page’s sessions, status transitions, current group and users. Reconstruct working/break seconds from transitions at one injected `now`; use legacy nonnegative counters only when a historical session has no transitions. Do not import activity models.

- [x] **Step 5: Register the strict route before `/{report_id}`**

Translate `ReportPeriodError` to the stable error envelope, and use existing `not_found()`/access-denied helpers without exposing whether a foreign filter exists.

- [x] **Step 6: Run focused and PostgreSQL GREEN**

```powershell
& ..\.venv312\Scripts\python.exe -m pytest tests/unit/test_report_period.py tests/api/test_reports.py tests/integration/test_authorized_routes.py -q --tb=short
$env:TEST_POSTGRES_ADMIN_URL='postgresql://phase5_test@127.0.0.1:55435/postgres'
& ..\.venv312\Scripts\python.exe -m pytest tests/api/test_reports.py -q --tb=short
```

- [x] **Step 7: Independent review and commit**

Review role drift, pagination-before-join, transition math, tenant isolation, query bounds and response fields. Commit as `feat: add scoped detailed timesheet reports`.

---

### Task 3: Excel export from canonical report rows

**Files:**
- Create: `backend/app/services/timesheet_excel_service.py`
- Modify: `backend/app/api/v1/reports.py`
- Test: `backend/tests/api/test_excel_export.py`

**Interfaces:**
- Consumes: Task 1 `ReportExcelRequest`; Task 2 canonical unpaginated scoped row iterator with an explicit safety limit.
- Produces: `TimesheetExcelService.render(rows, columns) -> bytes` and `safe_report_filename(date_from, date_to) -> str`.
- Produces: `POST /api/v1/reports/export-excel` with XLSX content type and `Content-Disposition`.

- [x] **Step 1: Write failing workbook and access tests**

Cover one day, seven days, one month, exact three months and over-limit rejection; selected column order; local times for different group timezones; multiple same-day sessions; manager foreign-group denial; safe fixed filename; formula-like employee text; and absence of activity, CRM, calls, URLs, raw payloads and hyperlinks.

- [x] **Step 2: Run RED**

```powershell
Set-Location backend
& ..\.venv312\Scripts\python.exe -m pytest tests/api/test_excel_export.py -q --tb=short
```

- [x] **Step 3: Implement allowlisted workbook rendering**

Render one `Табель` worksheet from canonical rows, format durations as `[h]:mm`, serialize timestamps in each row’s timezone, freeze the heading row, enable filters, and prefix formula-like text with an apostrophe. Filename is `timesheet_YYYY-MM-DD_YYYY-MM-DD.xlsx` and contains no user input.

- [x] **Step 4: Implement the export route**

Apply the same scope, filter and period rules as preview. Build the file in memory from DTOs only; never pass ORM activity objects to the exporter.

- [x] **Step 5: Run focused and PostgreSQL GREEN**

```powershell
& ..\.venv312\Scripts\python.exe -m pytest tests/api/test_reports.py tests/api/test_excel_export.py -q --tb=short
$env:TEST_POSTGRES_ADMIN_URL='postgresql://phase5_test@127.0.0.1:55435/postgres'
& ..\.venv312\Scripts\python.exe -m pytest tests/api/test_excel_export.py -q --tb=short
```

- [x] **Step 6: Independent review and commit**

Review spreadsheet injection, content headers, permissions, memory bounds, timezone conversion and excluded data. Commit as `feat: export safe timesheet workbooks`.

---

### Task 4: Safe report preview controller

**Files:**
- Create: `frontend/reports/controller.js`
- Create: `frontend/reports/styles.css`
- Create: `frontend/tests/reports.test.js`
- Create: `frontend/tests/reports.spec.js`
- Modify: `package.json`

**Interfaces:**
- Consumes: strict detailed/export APIs and a caller-supplied authorized transport; may reuse `/team/status` for allowed group/user choices.
- Produces: `TimesheetReports.mount(root, {transport, document, url, now})` with `refresh()`, `destroy()` and download behavior.

- [x] **Step 1: Write failing Node controller tests**

Assert date/group/employee filters, fixed ten-row pagination, loading/empty/error/success, Russian range errors, safe text rendering, disabled export while running, selected-column allowlist, blob download cleanup, repeat mount/destroy and no direct `fetch` or browser identity headers.

- [x] **Step 2: Run RED**

```powershell
$env:PATH='C:\Users\Lenovo\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin;' + $env:PATH
& 'C:\Users\Lenovo\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' --test frontend/tests/reports.test.js
```

- [x] **Step 3: Implement the UMD/AMD controller and styles**

Use `createElement`/`textContent`, one active preview request, stale-response guards and explicit listener cleanup. Do not reuse the legacy mock `frontend/assets/js/reports.js` or its timeline/CRM columns.

- [x] **Step 4: Add browser acceptance tests**

Verify admin and manager filters, employee denial/no launcher, 10-row pagination, states, selected columns, successful/failed export and the complete absence of activity/CRM/call/link columns.

- [x] **Step 5: Run GREEN**

```powershell
& 'C:\Users\Lenovo\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' --test frontend/tests/reports.test.js
& .\node_modules\.bin\playwright.cmd test frontend/tests/reports.spec.js
```

- [x] **Step 6: Independent review and commit**

Review XSS, request races, URL/blob cleanup, keyboard access and error recovery. Commit as `feat: add safe timesheet report preview`.

---

### Task 5: Widget lifecycle and exact package integration

**Files:**
- Modify: `widget/script.js`
- Modify: `frontend/tests/widget-lifecycle.test.js`
- Modify: `frontend/tests/widget-working.spec.js`
- Modify: `build_widget.ps1`
- Modify: `validate_widget_zip.py`
- Modify: `test_widget_package.py`
- Modify: `package.json`

**Interfaces:**
- Consumes: Task 4 report controller/styles and existing widget `$authorizedAjax`, API URL, lifecycle ownership and monitoring launcher patterns.
- Produces: one admin/manager “Табель” launcher and owned report panel; packaged `reports/controller.js` and `reports/styles.css`.

- [x] **Step 1: Write failing lifecycle/package tests**

Assert no launcher for employee/settings contexts, one launcher after repeated init, `$authorizedAjax` only, no identity headers, correct JSON/blob requests, error recovery, and full cleanup of requests/listeners/styles/DOM on context change or destroy.

- [x] **Step 2: Run RED**

```powershell
node --test frontend/tests/widget-lifecycle.test.js frontend/tests/reports.test.js
& .\.venv312\Scripts\python.exe -m unittest test_widget_package.py
```

- [x] **Step 3: Integrate reports with the widget lifecycle**

Add the AMD dependency and stylesheet beside monitoring. Share only verified status/viewer information, keep controllers independently destroyable, and leave amoCRM usable on report failures.

- [x] **Step 4: Extend the exact production package**

Add two runtime files to build and validation allowlists, raising the exact archive from 23 to 25 files. Keep legacy/demo report HTML and test files outside the ZIP.

- [x] **Step 5: Run complete frontend/browser/package GREEN**

```powershell
node --test frontend/tests/*.test.js
& .\node_modules\.bin\playwright.cmd test frontend/tests/*.spec.js
& .\.venv312\Scripts\python.exe -m unittest test_widget_package.py
powershell -NoProfile -ExecutionPolicy Bypass -File .\build_widget.ps1
& .\.venv312\Scripts\python.exe .\validate_widget_zip.py .\widget.zip
```

- [x] **Step 6: Independent review and commit**

Review lifecycle ownership, role visibility, authorized transport, archive exactness and regression risk. Commit as `feat: integrate timesheet reports into widget`.

---

### Task 6: Phase-wide verification, documentation and Plan.md status

**Files:**
- Modify: `docs/API.md`
- Modify: `docs/api-contract.md`
- Modify: `docs/development-workflow.md` if a new repeatable gate is confirmed
- Modify: `Plan.md`
- Modify: phase-7 progress/report artifacts under `.superpowers/sdd/2026-09-29-phase7-timesheet-reports-excel/`

**Interfaces:**
- Consumes: Tasks 1–5 and all seven Phase 7 acceptance checkboxes.
- Produces: reviewed Phase 7 implementation, reproducible evidence, user-checkable scenarios and updated plan status.

- [ ] **Step 1: Run focused and full PostgreSQL backend gates**

```powershell
Set-Location backend
$env:TEST_POSTGRES_ADMIN_URL='postgresql://phase5_test@127.0.0.1:55435/postgres'
& ..\.venv312\Scripts\python.exe -m pytest tests/unit/test_report_period.py tests/api/test_reports.py tests/api/test_excel_export.py tests/integration/test_authorized_routes.py -q --tb=short
& ..\.venv312\Scripts\python.exe -m pytest -q --tb=short
```

- [ ] **Step 2: Run full frontend/browser/package gates**

```powershell
Set-Location ..
node --test frontend/tests/*.test.js
& .\node_modules\.bin\playwright.cmd test frontend/tests/*.spec.js
& .\.venv312\Scripts\python.exe -m unittest test_widget_package.py
powershell -NoProfile -ExecutionPolicy Bypass -File .\build_widget.ps1
& .\.venv312\Scripts\python.exe .\validate_widget_zip.py .\widget.zip
```

- [ ] **Step 3: Run quality, migration and security checks**

Run Black on changed Python, `compileall`, `git diff --check`, one Alembic head, a scan for unsafe HTML/direct fetch/browser identity, workbook field inspection and the 40-account/query-bound tests. If no migration was added, explicitly record that decision.

- [ ] **Step 4: Independent whole-phase review**

Review the complete Phase 7 diff against all seven `Plan.md` checkboxes. Fix every Critical/Important issue and rerun affected plus full gates.

- [ ] **Step 5: Update docs and Plan.md from fresh evidence**

Document exact endpoints, roles, IDs, range semantics, pagination, columns, XLSX safety and limits. Mark every Phase 7 checkbox only after evidence; add what changed, files, commands/results, manual checks and live amoCRM limitations.

- [ ] **Step 6: Commit**

Commit as `docs: mark phase seven locally complete`.

## Self-Review Record

- Spec coverage: Tasks 1–5 cover all seven Phase 7 checkboxes; Task 6 owns the final evidence and status update.
- Step scan: each task has a RED, implementation, GREEN, independent review and commit boundary.
- Type consistency: filters use internal `User.id`; canonical rows feed both preview and export; frontend receives only the strict DTO.
- Review focus: month ends, repeated sessions, open transitions, 40-account isolation and workbook injection each have an owning test step.
- Scope: legacy APIs and demo files remain compatible; no unrelated report storage, activity export, PDF/CSV or settings persistence is introduced.
