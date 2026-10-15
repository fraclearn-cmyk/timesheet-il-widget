# Lateness Explanations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Добавить настраиваемые объяснительные при опоздании к началу дня и с перерыва, сохранить их в табеле и показать отдельными колонками на экране и в Excel.

**Architecture:** Отдельная таблица `lateness_incidents` хранит каждый случай опоздания, а настройки остаются в `WidgetGroup` и `GroupMember`. `TimesheetService` рассчитывает опоздание по серверному времени и атомарно сохраняет событие вместе с переходом статуса; отчёт и Excel читают один канонический набор строк. Виджет получает только подтверждённое сервером состояние и активирует рабочую кнопку после непустого текста.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy, Alembic, PostgreSQL 15/SQLite tests, openpyxl, vanilla AMD JavaScript, Node test runner, jsdom, Playwright.

**Spec:** `docs/superpowers/specs/2026-10-15-lateness-explanations-design.md`

## Global Constraints

- Обязательная объяснительная включается отдельно для каждого сотрудника одним флагом для начала дня и перерыва.
- Допустимый перерыв настраивается отдельно для каждой группы в диапазоне 1–720 минут; значение по умолчанию — 60.
- Предел применяется к следующему возврату с перерыва и не пересчитывает сохранённые события.
- Причина после `strip()` содержит 1–1000 символов; расчёт времени выполняет только сервер.
- Кнопка без обязательного текста серая и отключённая, после ввода — синяя и активная.
- Отчёт заканчивается блоком «Опоздания»: начало дня/минуты, начало дня/объяснительная, перерыв/минуты, перерыв/объяснительная.
- Несколько поздних перерывов показываются нумерованным списком, а их превышения суммируются.
- Старое значение экспортной колонки `lateness` принимается как совместимый псевдоним `shift_lateness`.
- Все операции ограничены подтверждённым `account_id`; сотрудник пишет только в свою текущую смену, руководитель читает только назначенные группы.
- Производительность сохраняет расчёт на 40 аккаунтов без запроса к БД на каждую строку отчёта.
- Версия итогового пакета — `3.0.20`; секреты, токены и тестовые учётные данные в Git и ZIP не добавляются.
- После каждой задачи обновляется `Plan.md`: выполненные пункты, созданные/изменённые файлы, результаты тестов и доступный пользователю сценарий проверки; затем пользователю отправляется краткий отчёт на русском.

## Review Focus

- Граница времени: ровно в начале смены и ровно на пределе перерыва опоздания нет; первая неполная превышенная минута даёт 1 минуту.
- Изменение группового предела во время уже начатого перерыва: команда возврата использует текущее сохранённое значение, а прежние события не меняются.
- Повтор ключа идемпотентности с другим текстом причины: сервер отвечает конфликтом и не создаёт второе событие.
- Два и более поздних перерыва одной смены: номера стабильны, минуты суммируются, тексты не теряются и не вызывают N+1 запросов.
- Текст, начинающийся с `=`, `+`, `-` или `@`: безопасно отображается и записывается в Excel как текст, без формулы.

---

## Карта файлов

| Область | Файлы и ответственность |
| --- | --- |
| Данные | `backend/app/models/lateness_incident.py`, `group_member.py`, `widget_group.py`, `work_session.py`, `models/__init__.py`, миграция `015` |
| Контракты и настройки | `backend/app/schemas/timesheet.py`, `settings_snapshot.py`, `report.py`, `backend/app/services/settings_snapshot_service.py`, `frontend/settings/settings.js` |
| Команды | `backend/app/services/lateness_service.py`, `timesheet_service.py`, `backend/app/api/v1/timesheet.py`, общий безопасный контракт ошибки |
| Рабочий интерфейс | `widget/timesheet/controller.js`, `widget/overlay.js`, `widget/styles.css`, `widget/script.js` |
| Отчёт и Excel | `backend/app/services/timesheet_report_service.py`, `timesheet_excel_service.py`, `frontend/reports/controller.js`, `frontend/reports/styles.css` |
| Выпуск | `widget/manifest.json`, пакетные валидаторы, `docs/api-contract.md`, `Plan.md`, `widget.zip` |

### Task 1: Миграция, модели и базовые контракты

**Files:**
- Create: `backend/app/models/lateness_incident.py`
- Create: `backend/migrations/versions/015_lateness_explanations.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/models/group_member.py`
- Modify: `backend/app/models/widget_group.py`
- Modify: `backend/app/models/work_session.py`
- Modify: `backend/app/models/timesheet_command.py`
- Modify: `backend/app/schemas/timesheet.py`
- Modify: `backend/app/schemas/settings_snapshot.py`
- Modify: `backend/app/schemas/report.py`
- Test: `backend/tests/unit/test_models.py`
- Test: `backend/tests/unit/test_report_period.py`
- Test: `backend/tests/integration/test_migrations.py`

**Interfaces:**
- Produces: `LatenessKind.SHIFT_START`, `LatenessKind.BREAK_RETURN`, `LatenessIncident`; `GroupMember.require_late_reason: bool`; `WidgetGroup.break_limit_minutes: int`.
- Produces: `TimesheetCommand.request_hash: str | None`; `CommandRequest.reason: str | None`; status fields `late_reason_required`, `late_reason_kind`, `late_minutes`, `break_sequence`.
- Produces: `BreakLateness(sequence: int, late_seconds: int, reason: str | None)` and four report/export fields `shift_lateness`, `shift_late_reason`, `break_lateness`, `break_late_reason`.

- [ ] **Step 1: Write failing model, schema and migration tests.** Assert defaults `False`/`60`, range `1..720`, reason max 1000, event uniqueness `(work_session_id, kind, sequence)`, account-scoped foreign keys/indexes, nullable 64-character `timesheet_commands.request_hash` for old rows, upgrade from migration `014`, downgrade to `014`, and preservation of populated work sessions. Assert exactly-on-boundary Pydantic validation and normalization of legacy `lateness` to `shift_lateness` before duplicate detection.

- [ ] **Step 2: Run RED from `backend`.**

  `& ..\.venv312\Scripts\python.exe -m pytest tests/unit/test_models.py tests/unit/test_report_period.py tests/integration/test_migrations.py -q --tb=short`

  Expected: failures for missing model, columns, migration and new enum/DTO fields.

- [ ] **Step 3: Add migration `015` and ORM model.** Store incident `account_id`, `work_session_id`, `amocrm_user_id`, `kind`, `sequence`, `occurred_at`, positive `late_minutes`, nullable `reason`, `created_at`; use sequence `0` for `shift_start`; add uniqueness and account/session lookup indexes. Add defaults and constraints to group/member columns, expand legacy `late_reason` to 1000 characters, and add nullable `request_hash` so pre-update idempotency rows remain readable.

- [ ] **Step 4: Extend strict Pydantic contracts.** Validate stripped optional reason, group break limit, member flag and new report fields. Keep legacy `late_seconds` response for compatibility, but define it as shift-start lateness. Exclude legacy `lateness` from new defaults while accepting it as the `shift_lateness` alias.

- [ ] **Step 5: Run GREEN and migration round trip.** Use the Step 2 command and the existing PostgreSQL migration test environment when available; all selected tests pass.

- [ ] **Step 6: Update phase status.** Mark Task 1 complete in `Plan.md`, list migration/model/schema files and the verified migration checks, and state what can already be inspected.

- [ ] **Step 7: Commit.** `git commit -m "feat: add lateness incident data model"`, then report the completed phase to the user before Task 2.

### Task 2: Настройки группы и сотрудника

**Files:**
- Modify: `backend/app/services/settings_snapshot_service.py`
- Modify: `backend/tests/api/test_settings.py`
- Modify: `backend/tests/integration/test_settings_snapshot_transactions.py`
- Modify: `frontend/settings/settings.js`
- Modify: `frontend/tests/settings-controller.test.js`
- Modify: `frontend/tests/settings-smoke.test.js`

**Interfaces:**
- Consumes: `SettingsGroup.break_limit_minutes` and `SettingsUser.require_late_reason` from Task 1.
- Produces: round-trip settings snapshot/update and administrator controls `break_limit_minutes`/`require_late_reason`.

- [ ] **Step 1: Write failing settings tests.** Assert administrator load/save for per-group limits and per-user flags, values 1/720 accepted, 0/721 rejected, inactive-user protection retained, manager/employee denied, tenant isolation retained, rollback leaves the prior snapshot unchanged, and a newly added group starts at 60.

- [ ] **Step 2: Run backend and Node RED.**

  From `backend`: `& ..\.venv312\Scripts\python.exe -m pytest tests/api/test_settings.py tests/integration/test_settings_snapshot_transactions.py -q --tb=short`

  From root: `node --test frontend/tests/settings-controller.test.js frontend/tests/settings-smoke.test.js`

- [ ] **Step 3: Persist both settings in `SettingsSnapshotService`.** Include them in response construction, update allowlists, group creation, member upsert and revision transaction. Do not copy the member flag to `User`.

- [ ] **Step 4: Render administrator controls.** Add a numeric group input with `min=1`, `max=720`, integer validation and Russian error; add «Объяснительная при опоздании» to each active user row and serialize it with the existing group reference.

- [ ] **Step 5: Run GREEN.** Both Step 2 commands pass, including rollback and role cases.

- [ ] **Step 6: Update phase status.** Mark Task 2 complete in `Plan.md`, list settings files and test results, and state how the administrator controls can be checked.

- [ ] **Step 7: Commit.** `git commit -m "feat: configure lateness explanations"`, then report the completed phase to the user before Task 3.

### Task 3: Серверная проверка команд и атомарное хранение

**Files:**
- Create: `backend/app/services/lateness_service.py`
- Modify: `backend/app/services/timesheet_service.py`
- Modify: `backend/app/api/v1/timesheet.py`
- Modify: `backend/app/api/v1/dependencies.py`
- Modify: `backend/app/main.py`
- Modify: `backend/tests/unit/test_timesheet_transitions.py`
- Modify: `backend/tests/api/test_timesheet.py`
- Modify: `backend/tests/integration/test_authorized_routes.py`
- Modify: `backend/tests/e2e/test_user_scenarios.py`

**Interfaces:**
- Consumes: Task 1 models/contracts and Task 2 settings.
- Produces: `LatenessDecision(kind, sequence, late_minutes, reason_required)`; `LatenessService.for_shift_start(...)`, `for_break_return(...)`, `record(...)`.
- Produces: `TimesheetService.apply(context, action, key, reason=None, now_utc=None)` and `409 LATE_REASON_REQUIRED` with safe `details` containing kind, minutes and sequence.

- [ ] **Step 1: Write failing calculation and command tests.** Cover on-time/equal-boundary/one-second-over, disabled requirement with an incident whose reason is empty, blank/whitespace/1000/1001-character required reason, start and return flows, current group limit after mid-break change, multiple break sequences, restart session, finish while on break, rollback, foreign account/user attempts and 40-account identity isolation.

- [ ] **Step 2: Write failing idempotency tests.** Assert same key/action/normalized reason replays one response and one incident; same key with changed reason or action returns `IDEMPOTENCY_KEY_REUSED`; concurrent distinct keys create only the valid transition.

- [ ] **Step 3: Run RED from `backend`.**

  `& ..\.venv312\Scripts\python.exe -m pytest tests/unit/test_timesheet_transitions.py tests/api/test_timesheet.py tests/integration/test_authorized_routes.py tests/e2e/test_user_scenarios.py -q --tb=short`

- [ ] **Step 4: Implement `LatenessService`.** Use `ceil(positive_seconds / 60)`, the group timezone for shift start, the latest `start-break` transition for break duration, current `break_limit_minutes`, and `WorkSession.break_count` as the stable break sequence. Query only within confirmed account/session scope.

- [ ] **Step 5: Enforce in `TimesheetService`.** Store a SHA-256 hash of canonical action/reason input, reject before creating a session or transition, record every late `start-work`/`end-break` atomically even when the explanation requirement is off, mirror shift reason/minutes to legacy fields, and return dynamic requirement fields from `_snapshot`.

- [ ] **Step 6: Extend the safe error envelope.** Allow `APIProblem` to carry an allowlisted `details` object; expose details only for `LATE_REASON_REQUIRED`. `_apply` passes `body.reason`. Tests assert no traceback, account ID or internal IDs leak.

- [ ] **Step 7: Run GREEN.** Step 3 passes and incident query counts remain bounded.

- [ ] **Step 8: Update phase status.** Mark Task 3 complete in `Plan.md`, list service/API files and test results, and state which API scenarios can be checked.

- [ ] **Step 9: Commit.** `git commit -m "feat: require explanations for late returns"`, then report the completed phase to the user before Task 4.

### Task 4: Поле объяснительной и состояния кнопок сотрудника

**Files:**
- Modify: `widget/timesheet/controller.js`
- Modify: `widget/overlay.js`
- Modify: `widget/styles.css`
- Modify: `widget/script.js`
- Modify: `frontend/tests/timesheet-controller.test.js`
- Modify: `frontend/tests/widget-working.spec.js`
- Modify: `frontend/tests/widget-lifecycle.test.js`

**Interfaces:**
- Consumes: status requirement fields and `CommandRequest.reason` from Task 3.
- Produces: `controller.command(action, reason)` and overlay callback `(action, reason)` with one owned textarea and accessible disabled/enabled state.

- [ ] **Step 1: Write failing Node tests.** Validate the new status contract, trimmed reason in POST, pending retry retaining the exact reason/key, conflict refresh after `LATE_REASON_REQUIRED`, preservation of current textarea text across that refresh, no reason on unrelated actions, and cleanup on destroy/context change.

- [ ] **Step 2: Write failing Playwright tests.** For both `not_started` and `on_break`, assert visible minutes/kind, gray disabled button for empty/whitespace, blue enabled button after text, keyboard operation, 1000-character limit, safe literal rendering, and amoCRM background blocking behavior.

- [ ] **Step 3: Run RED from root.**

  `node --test frontend/tests/timesheet-controller.test.js frontend/tests/widget-lifecycle.test.js`

  `& .\node_modules\.bin\playwright.cmd test frontend/tests/widget-working.spec.js --workers=1 --reporter=line`

- [ ] **Step 4: Extend controller transport.** Validate all new fields, accept `reason`, store it in the pending command, serialize only for `start-work`/`end-break`, and on requirement conflict refresh status without falsely confirming a transition.

- [ ] **Step 5: Render accessible explanation UI.** Create elements with DOM APIs and `textContent`; disable the relevant button until `textarea.value.trim()` is nonempty; use namespaced gray/blue CSS and keep finish-day behavior unchanged. Remove listeners and values in `clear()`.

- [ ] **Step 6: Run GREEN.** Both Step 3 commands pass.

- [ ] **Step 7: Update phase status.** Mark Task 4 complete in `Plan.md`, list widget files and Node/Playwright results, and state how the disabled/active buttons can be checked.

- [ ] **Step 8: Commit.** `git commit -m "feat: collect employee lateness explanations"`, then report the completed phase to the user before Task 5.

### Task 5: Групповой блок отчёта и Excel

**Files:**
- Modify: `backend/app/services/timesheet_report_service.py`
- Modify: `backend/app/services/timesheet_excel_service.py`
- Modify: `backend/tests/api/test_reports.py`
- Modify: `backend/tests/api/test_excel_export.py`
- Modify: `backend/tests/integration/test_query_plans.py`
- Modify: `frontend/reports/controller.js`
- Modify: `frontend/reports/styles.css`
- Modify: `frontend/tests/reports.test.js`
- Modify: `frontend/tests/reports.spec.js`

**Interfaces:**
- Consumes: Task 1 `LatenessIncident`, `BreakLateness` and new export enum values.
- Produces: canonical employee-day rows with shift explanation, total break lateness and ordered break explanation list; screen and workbook three-level grouped headers.

- [ ] **Step 1: Write failing report API tests.** Assert one shift event, no event, legacy-session fallback, two late breaks ordered by sequence, summed excess minutes, blank historical reasons, admin/manager scope, employee denial, cross-account isolation and a bounded query count for a 40-account-sized fixture.

- [ ] **Step 2: Write failing Excel tests.** Assert independent selection of four fields, legacy `lateness` normalization, three header rows with merged «Опоздания»/«Начало дня»/«Перерыв», integer minute values and `0` number format, freeze/filter below row 3, wrapped numbered break lines and formula-safe explanation cells.

- [ ] **Step 3: Write failing frontend tests.** Assert the 11 visible columns and exact three-row header structure, safe text nodes, numbered break explanations, independent export checkboxes and legacy saved-selection normalization.

- [ ] **Step 4: Run RED.**

  From `backend`: `& ..\.venv312\Scripts\python.exe -m pytest tests/api/test_reports.py tests/api/test_excel_export.py tests/integration/test_query_plans.py -q --tb=short`

  From root: `node --test frontend/tests/reports.test.js`; then `& .\node_modules\.bin\playwright.cmd test frontend/tests/reports.spec.js --workers=1 --reporter=line`.

- [ ] **Step 5: Aggregate incidents without N+1.** Join or batch-load all incidents for the selected page/export set, preserve legacy shift values when no structured event exists, sum break excess and build ordered `BreakLateness` objects. Keep the existing role-scoped base query.

- [ ] **Step 6: Render the screen header and rows.** Build `rowSpan`/`colSpan` with DOM APIs, append the four lateness columns at the end, show minute cells as whole numbers, render multiple break explanations as separate safe lines and expose four independent export choices.

- [ ] **Step 7: Render the workbook header and data.** Generate three header rows only when a lateness child column is selected, merge contiguous group cells, write lateness as whole minute numbers with format `0`, wrap explanation cells, protect formula-like text, freeze at the first data row and set the filter there.

- [ ] **Step 8: Run GREEN.** All Step 4 commands pass, including query-count and spreadsheet security cases.

- [ ] **Step 9: Update phase status.** Mark Task 5 complete in `Plan.md`, list report/Excel files and test results, and state how the grouped headers and explanations can be checked.

- [ ] **Step 10: Commit.** `git commit -m "feat: report structured lateness details"`, then report the completed phase to the user before Task 6.

### Task 6: Полная проверка, документация и пакет 3.0.20

**Files:**
- Modify: `widget/manifest.json`
- Modify: `validate_widget_zip.py`
- Modify: `test_widget_package.py`
- Modify: `docs/api-contract.md`
- Modify: `docs/release-checklist.md`
- Modify: `Plan.md`
- Rebuild: `widget.zip`

**Interfaces:**
- Consumes: Tasks 1–5.
- Produces: проверенный пакет `3.0.20`, итоговые результаты и пошаговый сценарий проверки администратором, руководителем и сотрудником.

- [ ] **Step 1: Add release/package assertions.** Verify manifest and every AMD cache-busting URL use `3.0.20`, the exact runtime allowlist remains 25 files, secrets are absent and the archive contains no tests/demo files.

- [ ] **Step 2: Run focused regression.** Repeat every GREEN command from Tasks 1–5 and fix only evidenced failures.

- [ ] **Step 3: Run full local gates.**

  From `backend`: `& ..\.venv312\Scripts\python.exe -m pytest -q --tb=short`.

  From root: `node --test frontend/tests/*.test.js`; `& .\node_modules\.bin\playwright.cmd test frontend/tests --workers=1 --reporter=line`; `& .\.venv312\Scripts\python.exe -m unittest test_widget_package.py`; `& .\build_widget.ps1`; `& .\.venv312\Scripts\python.exe .\validate_widget_zip.py .\widget.zip`; `git diff --check`.

- [ ] **Step 4: Run PostgreSQL and migration gates.** Upgrade a clean and populated PostgreSQL test database to `015`, run the existing multi-worker/query/security suite, downgrade to `014`, upgrade again, and record actual results. Do not claim an external CI result until GitHub reports it.

- [ ] **Step 5: Update documentation and `Plan.md`.** Mark each completed phase and task, list every created/changed file, exact test counts, known external gates and what the user can already verify. Document the admin settings path, employee late-start/late-return flow, role-visible report and four Excel fields.

- [ ] **Step 6: Independent whole-change review.** Review spec coverage, tenant isolation, role boundaries, idempotency, time boundaries, report query bounds, XSS/formula injection and archive contents; fix findings and rerun affected gates.

- [ ] **Step 7: Commit and push.** `git commit -m "release: prepare lateness explanations 3.0.20"`, push `main`, then verify the pushed commit and GitHub checks.

- [ ] **Step 8: Live amoCRM smoke test when the local HTTPS endpoint is available.** Upload `widget.zip`, save the current API URL, test administrator settings and one employee flow, inspect manager/admin report and Excel, then restore test data. Record this separately from local completion if the external environment is unavailable.

