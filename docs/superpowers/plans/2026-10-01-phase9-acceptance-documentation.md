# Phase 9: Acceptance and documentation

Started: 2026-10-01
Base commit: `d445ec6`

## Task 1: Backend role and failure acceptance

**Files:**
- Create: `backend/tests/e2e/test_user_scenarios.py`
- Modify production code only when a failing scenario proves a defect

- [x] Prove the employee hidden/visible lifecycle: start, break, resume, finish and an actual same-business-day restart only when the group permits it.
- [x] Prove the manager sees only the assigned group, cannot open own detailed activity and cannot request a foreign group or employee.
- [x] Prove the administrator flow connects users/groups/schedule/permissions with monitoring, detailed report and safe Excel export.
- [x] Cover the acceptance failure matrix for 401/403/409/422/429/500/503 with stable Russian messages, request IDs and safe logs where applicable.
- [x] Independent review and commit.

## Task 2: Browser acceptance and event evidence

**Files:**
- Create: `frontend/tests/e2e.spec.js`
- Reuse: existing overlay, monitoring, reports and smoke suites

- [x] Prove the stateful employee UI flow, hidden/visible behavior, permitted restart, cleanup and recovery without false Working state.
- [x] Prove manager/admin navigation and access affordances without trusting the browser for authorization.
- [x] Re-run the existing seven-day activity contract: tooltip, zoom, gaps, fullscreen and Escape.
- [x] Consolidate local evidence for catalog snapshots, unknown events, complete/incomplete calls, duplicates, replay, checkpoints and 40-account isolation; keep live catalog/calls/latency explicitly external.
- [x] Independent review and commit.

## Task 3: User, configuration and deployment documentation

**Files:**
- Modify: `README.md`, `docs/API.md`
- Create: `docs/CONFIGURATION.md`, `docs/DEPLOYMENT.md`

- [x] Replace stale routes, commands and broken links in README with the current installation and user workflow.
- [x] Document required/optional settings, secrets, 40-account defaults, group schedule/timezone and multi-worker rate-limit boundary.
- [x] Document backup, migration, Docker/health/readiness, rollback/recovery and target-environment verification without claiming an unrun Docker gate.
- [x] Cross-check API examples, roles, reports, errors and request IDs against current code.
- [x] Independent documentation review and commit.

## Task 4: Acceptance report and release checklist

**Files:**
- Create: `docs/acceptance-report.md`, `docs/release-checklist.md`

- [x] Map every Phase 9 checkbox to current automated evidence, manual local checks and unresolved external evidence.
- [x] Record known amoCRM limits: OAuth/scopes/role mapping, iframe callbacks/CORS/styles, full event catalog/pagination/latency and readable call source.
- [x] Separate completed local gates from required GitHub CI, Docker target and controlled live amoCRM release gates.
- [x] Include backup/schema-preflight requirement for the previously stamped `010` database and sizing/observability checks for 40 accounts.
- [x] Independent release review and commit.

## Task 5: Phase-wide gate and plan closure

- [ ] Run a fresh full PostgreSQL backend suite with `TEST_POSTGRES_ADMIN_URL`, Node, Playwright, package/ZIP, Alembic `014`, Black, compileall and diff checks.
- [ ] Review the complete Phase 9 diff and fix every Critical/Important finding.
- [ ] Update only the Phase 9 checkboxes supported by evidence; mark the phase locally complete with external gates visible when live/Docker/CI have not run.
- [ ] Update status/progress tables, journal, final report, exact files/results, user-checkable scenarios and remaining risks in `Plan.md`.
- [ ] Commit only after evidence.

## Boundaries

- Do not claim a current full amoCRM event catalog, readable calls endpoint or delivery latency from local fixtures.
- Do not claim GitHub CI or Docker build/up passed until an external runner actually reports success.
- Browser visibility is not authorization; server policy remains the source of truth.
- Acceptance evidence must preserve isolation for at least 40 accounts with repeated external identifiers.
- Leave the pre-existing untracked `test-results/` directory untouched.
