# Phase 1 recovery implementation report

Date: 2026-09-17. Base: `1415991fb1cef99c98e51442cabb14f75cccb31c` on `main`.

## Recovery note and scope

The original implementer stopped before report/commit. Recovery preserved the dirty
worktree, inspected the actual implementation, tests and migration graph, and reran
verification independently. Its reported `139 tests` was not used as evidence.
The final count is 143: 110 phase-0 cases and 33 phase-1 cases.
No subagents, reviewer, live amoCRM access, user database migrations or phase-2
implementation were performed. `Plan.md` was not changed.

Status: implementation ready for independent review, with the explicitly recorded
legacy lint/warning limitations below. This is not an independent approval of phase 1.

## Implemented behavior

- `User.id` is the internal PK. External identity is the unique pair
  `(amocrm_account_id, amocrm_user_id)`. `WorkSession` stores that explicit pair and
  a composite FK. Equal external user IDs across accounts remain distinct.
- Group manager/member and activity/event attribution references are account-scoped.
  `GroupMember.is_active` has a PostgreSQL partial unique index. Multiple inactive
  historical memberships are allowed; two active memberships are rejected.
- `WidgetGroup` retains timezone, work start/end, manager and active flag; existing
  fields from 004 were verified rather than recreated. WidgetSettings nullability,
  lowercase enum persistence and the missing User/Department relationship were aligned.
- Four nonnegative NOT NULL duration counters store whole seconds with default 0.
  Legacy elapsed work is backfilled as unconfirmed, never as confirmed CRM work.
- `CrmEvent.external_id` preserves opaque strings. Raw external author is separate
  from nullable internal attribution. Unknown/system authors remain unattributed and
  cannot produce complete CRM evidence.
- `ActivityInterval.from_evidence` requires an attributed matching source, positive
  external author, WORKING status, valid chronological bounds and no crossing of a
  break/finish transition for confirmed intervals. Browser input is unconfirmed;
  calls require observed duration and direction. Aware timestamps normalize to naive
  UTC, including mixed aware/naive transition histories.
- Session schema/service adapters retain legacy wire `user_id` only as an explicitly
  external amoCRM ID; ambiguous accountless external identities fail closed. Existing
  session routes, KPI, reports, Excel and team consumers use actual model fields.
  `WorkComment.work_session_id` is used; its already-correct model did not need changes.
- Changed defaults/services use `utc_now()` (aware UTC converted to naive UTC), and
  session serialization uses Pydantic v2 APIs without changing the wire contract.

## Self-review and TDD evidence

Recovery reviewed all tracked diffs and new files against the phase-1 brief and ledger.
It found and fixed two additional defects with failing regression tests first:

1. Factory only compared raw author with User external ID. If a malformed legacy User
   itself had external ID 0/-1, system evidence could be confirmed. Two parametrized
   cases now explicitly require a positive external author.
2. Employee-report event counts omitted account and period predicates while the
   associated session/activity query was scoped. A three-session fixture (same external
   user ID in two accounts plus older same-account history) returned 3 instead of 1.
   The query now applies the same account and date boundaries.

Fresh RED command, from `backend`:

```powershell
../.venv312/Scripts/python.exe -m pytest -q tests/unit/test_interval_rules.py::test_system_author_cannot_be_confirmed_even_if_a_legacy_user_matches tests/unit/test_models.py::test_employee_report_event_count_stays_in_account_and_period
```

Before fixes: `3 failed, 39 warnings in 4.60s` (two `DID NOT RAISE ValueError`,
one `assert 3 == 1`). Same command after minimal fixes:
`3 passed, 39 warnings in 4.44s`.

Warnings were subsequently treated as errors for the affected behavior:

```powershell
../.venv312/Scripts/python.exe -m pytest -q tests/unit/test_models.py::test_account_scoped_external_identity_and_session_lifecycle -W 'error::DeprecationWarning:app.services.session_service' --tb=short
../.venv312/Scripts/python.exe -m pytest -q tests/unit/test_models.py::test_legacy_session_routes_use_external_ids_and_persist_transitions -W 'error::DeprecationWarning:pydantic.main' --tb=short
```

UTC RED: `1 failed, 14 warnings`, at `SessionService.create_session` calling
`datetime.utcnow()`. GREEN after shared UTC helper: `1 passed, 10 warnings`.
Serialization RED: `1 failed, 10 warnings`, at `WorkSessionResponse.from_orm`.
GREEN after `model_validate` and ConfigDict: `1 passed, 8 warnings`.
Permanent test markers now promote these specific warnings and ORM timestamp-default
warnings to errors in the relevant lifecycle tests; they do not suppress warnings.

Original implementer historical RED output was not available in the recovery context.
No claim is made that recovery observed tests being written before that inherited
implementation. Existing tests were inspected and freshly executed. The recovery RED
evidence above is directly observed; this provenance distinction must be retained.

## PostgreSQL migration verification

Docker Desktop was stopped initially. It was started hidden. Recovery created its own
PostgreSQL 15 container `timesheet_phase1_recovery_test_pg` with label
`purpose=disposable-phase1-recovery-test`, bound only to localhost on allocated port
61176. It did not reuse `timesheet_db` or the earlier implementer's stopped test
container. An initial launch on port 55440 was rejected by Windows port reservation;
the newly created failed container was removed and recreated with automatic port
allocation. No user container/database was deleted.

Every test creates `timesheet_phase1_test_<uuid>` and drops only that owned database
in fixture cleanup. The test server uses local trust authentication, no application
credentials. The test configuration replaces application settings with synthetic values.

```powershell
$env:TEST_POSTGRES_ADMIN_URL='postgresql://postgres@127.0.0.1:61176/postgres'
../.venv312/Scripts/python.exe -m pytest -q -s tests/integration/test_migrations.py
```

Fresh output: `4 passed, 2 warnings in 10.61s`.

Observed migration output for clean upgrade:

```text
Context impl PostgresqlImpl.
Will assume transactional DDL.
Running upgrade  -> 001, create base timesheet tables
Running upgrade 001 -> 002, add reports table
Running upgrade 002 -> 003, add rbac tables and extend work_session
Running upgrade 003 -> e1db632ded80, add remaining tables
Running upgrade e1db632ded80 -> 004, add widget groups and normalized activity tables
Running upgrade 004 -> 005, Unify account-scoped identities, membership history and activity semantics.
Running downgrade 005 -> 004, Unify account-scoped identities, membership history and activity semantics.
Running upgrade 004 -> 005, Unify account-scoped identities, membership history and activity semantics.
```

The populated test independently ran `upgrade 004`, inserted legacy work/activity/system
event rows, then `upgrade head`, `downgrade 004`, and `upgrade head`. It verified the
original external user ID, account mapping, 120 seconds of unconfirmed work, 30 seconds
of breaks, opaque event ID and raw system author survive without invented activity.

Real PostgreSQL assertions verify target columns/nullability, lowercase enum reads,
default duration values, account isolation, historical inactive memberships, rejection
of a second active membership and cross-account group references, invalid activity
source/kind, negative durations and system-author attribution.
Separate tests verify unmappable legacy sessions abort transactionally at 004 with
data intact, and a downgrade refuses to erase membership history at 005.

The original `1415991` version of migration 001 was also executed directly using
Alembic Operations/MigrationContext on another owned disposable PostgreSQL database.
Fresh result:

```text
Baseline 001 reproduced: DuplicateTable ix_work_sessions_user_id (SQLSTATE 42P07)
Owned disposable baseline reproduction database removed
```

Thus the ledger-authorized removal of only duplicate `index=True` in 001 is necessary.
The explicit index creation/name remains unchanged. Migration 005 is the only new
revision, with `down_revision = "004"`.

## Final verification

Commands use `D:/табель/.venv312/Scripts/python.exe` (Python 3.12) from `backend`
unless noted otherwise, with the explicit test PostgreSQL URL set for pytest.

| Check | Observed result |
|---|---|
| Focused `pytest -q tests/unit tests/integration/test_migrations.py --tb=short` | 33 passed, 24 warnings, 14.77s |
| Full `pytest -q --tb=short` | 143 passed, 24 warnings, 14.21s |
| Phase-0-only `pytest -q tests/integration/test_amocrm_contract.py` | 110 passed, no warnings, 1.17s |
| `python -m compileall -q app migrations` | exit 0 |
| `python -m alembic heads` | exactly `005 (head)` |
| Real PostgreSQL migration tests with visible Alembic logs | 4 passed, 2 warnings, 10.61s |
| Black on 25 changed/new Python files excluding historical 001 | 25 files unchanged, exit 0 |
| flake8 on all 26 changed/new Python files | exit 0 with scoped legacy ignores below |
| `git diff --check` | exit 0 |

Black full-file check of 001 still reports existing long-line formatting. The exact
baseline file from HEAD also fails Black. A line-range check likewise reformats the
surrounding multiline DDL expression. Recovery deliberately did not expand the narrowly
authorized historical-migration edit merely to reformat unrelated lines. This is a
documented pre-existing lint limitation, not a claim that all-file Black is clean.

flake8 retains project-compatible E501/W503 ignores. Extra per-file ignores cover only
verified baseline idioms: `work_session.py` schema E402 for late forward-reference imports;
Excel/Team services E712 for SQLAlchemy boolean comparisons; KPI service E711 for SQLAlchemy
NULL comparisons. These predicates/import locations were already present in HEAD.
No blanket suppression/config changes were committed.

```powershell
python -m flake8 --ignore=E501,W503 --per-file-ignores='backend/app/schemas/work_session.py:E402,backend/app/services/excel_service.py:E712,backend/app/services/kpi_service.py:E711,backend/app/services/team_service.py:E712' <all changed/new Python paths>
```

## Warning baseline comparison

Initial fresh full run: 143 passed with 152 warnings. After cleanup: 24 remain.
The 128 removed occurrences came from affected model UTC defaults/service calls
(99 ORM-default occurrences down to 4; 25 direct service calls removed), session
`from_orm` (6 removed), and WorkSession schema class Config (2 removed).

| Remaining category | Count in focused/full run | Source and baseline status |
|---|---:|---|
| PydanticDeprecatedSince20, class Config | 11 | Unchanged legacy schema imports, reported at `pydantic/_internal/_config.py:272` |
| SQLAlchemy MovedIn20Warning | 1 | Unchanged `app/core/database.py:13`, `declarative_base()` import |
| DeprecationWarning, datetime.utcnow | 4 | Unchanged Department/WorkComment defaults, surfaced by `sqlalchemy/sql/schema.py:3585` |
| DeprecationWarning, datetime.utcnow | 6 | Installed openpyxl `packaging/core.py:99` |
| DeprecationWarning, datetime.utcnow | 2 | Installed openpyxl `writer/excel.py:292` |

The phase-0-only 110-test suite emits zero warnings because it does not exercise these
legacy ORM/report/schema paths. Therefore raw warning count cannot be compared as if
the same tests existed at baseline. Source comparison with HEAD verifies unchanged
remaining application sources; the new tests expose existing warnings. No warning is
described as pristine output, and no broad warning filter was added. Dependency updates
and untouched legacy schema modernization are outside this implementation.

## Files

New: `backend/app/core/time_utils.py`, `backend/migrations/versions/005_unified_domain.py`,
`backend/tests/conftest.py`, `backend/tests/unit/test_models.py`,
`backend/tests/unit/test_interval_rules.py`, `backend/tests/integration/test_migrations.py`,
`docs/domain-model.md`, this report.

Modified models: `activity_event.py`, `activity_interval.py`, `activity_session.py`,
`call_event.py`, `crm_event.py`, `group_member.py`, `status_transition.py`, `user.py`,
`widget_group.py`, `widget_settings.py`, `work_session.py`.

Modified consumers: `backend/app/schemas/work_session.py`,
`backend/app/api/v1/sessions.py`, `backend/app/api/v1/endpoints/kpi.py`,
`backend/app/services/session_service.py`, `team_service.py`, `report_service.py`,
`kpi_service.py`, `excel_service.py`.

Historical migration: `backend/migrations/versions/001_initial_timesheet_tables.py`
only removes duplicate implicit index creation (plus existing end-of-file normalization).

## Concerns and explicit limits

- Authorization/RBAC and verified request context remain phase 2. Legacy accountless
  routes are compatibility adapters, not an authorization boundary. Existing routes
  accepting internal IDs were not expanded or represented as secured.
- Phase 4 owns full status automation and duration accumulation. New counters are not
  automatically derived from legacy elapsed totals after migration; confirmed activity
  cannot be inferred from those totals. Existing team force-finish behavior remains a
  legacy path to consolidate with that state machine.
- Direct SQL/ORM construction does not validate interval status history; callers must use
  the domain factory. DDL separately validates structural source/kind/time/attribution.
- Bad legacy account links/statuses/durations or unmapped external users abort upgrade
  rather than invent mappings or silently delete data. Working databases were not tested
  or altered; production data reconciliation is a separate deployment responsibility.
- Downgrade intentionally refuses data states 004 cannot represent (membership history,
  repeated cross-account external IDs, independent duration counters, unknown raw author
  or call direction, non-UTC department timezone). Destructive downgrade is not provided.
- Historical RED provenance and the baseline 001 Black limitation are stated above.
  Remaining legacy/dependency warnings are visible for independent review.

## Final recovery gate

Secret scan passed for all 28 phase files. It compared sensitive ignored `.env` values
against candidate file contents in memory without printing values, rejected `.env` and
private-key filenames, and scanned JWT/private-key/GitHub-token signatures. No actual
credentials were found. The report contains only the credential-free disposable server
URL. Test fixtures contain explicitly synthetic non-production strings.

Immediately before cleanup, the owned PostgreSQL server reported zero databases matching
`timesheet_phase1_test_%`: all UUID fixtures had cleaned up. Recovery then removed only
its own `timesheet_phase1_recovery_test_pg` container and anonymous test volume. These
disposable synthetic database artifacts are deleted, not recoverable; the earlier test
container and user containers were not removed.

All 28 reviewed files are included in the phase-1 commit; no Plan.md, .env, credentials
or unrelated files are included. The report is explicitly force-added because the SDD
working directory is generally ignored, consistent with the tracked phase-0 report.
The resulting commit identifier is returned in the recovery handoff.
