# Phase 8 Integration, Security and Performance Plan

**Goal:** Make the existing widget/backend reproducible to run, observable, resilient and measurable for 40 isolated amoCRM accounts without weakening the access boundaries completed in Phases 2–7.

**Architecture:** Keep PostgreSQL as the durable coordination layer and amoCRM polling as the authoritative ingestion path. Add production-safe container orchestration, request-scoped observability, bounded ingress controls, evidence-based composite indexes, explicit cache rules, recovery smoke tests and one repeatable CI gate. Docker execution and live amoCRM remain separately recorded external gates when the local environment cannot provide them.

**Tech stack:** Python 3.12/FastAPI/SQLAlchemy/Alembic/PostgreSQL 15, Docker Compose, GitHub Actions, Node 22, Playwright.

**Source of truth:** `Plan.md` Phase 8. `SPEC.md` is absent.

## Task 1: Reproducible production runtime and health

**Files:**
- Modify: `docker-compose.yml`, `backend/Dockerfile`, `backend/app/core/config.py`, `backend/app/main.py`
- Create: `backend/.env.example`, `backend/docker-entrypoint.sh`
- Create/modify tests: `backend/tests/integration/test_deployment.py`, `backend/tests/integration/test_health.py`

- [x] Write failing static/deployment tests for weak defaults, host-published DB, bind mounts/reload, root user, missing migration gate and health checks.
- [x] Split liveness from readiness; readiness must verify PostgreSQL and the single expected Alembic head without exposing secrets.
- [x] Make startup run migrations before the API, add a non-root image user and a backend healthcheck. Production Compose must have no weak password fallback, source bind mount, reload or public database port.
- [x] Validate config parsing, Alembic head/upgrade on disposable PostgreSQL, health behavior and Compose structure. Record Docker build/up as an external gate because Docker is unavailable locally.
- [x] Independent review, fix all Critical/Important findings and commit.

## Task 2: Correlation IDs, JSON logs, redaction and error catalog

**Files:**
- Create: `backend/app/core/middleware.py`, `backend/app/core/error_catalog.py`
- Modify: `backend/app/core/logging.py`, `backend/app/main.py`
- Create: `backend/tests/integration/test_request_observability.py`, `backend/tests/integration/test_security.py`

- [x] Write failing tests for malformed/untrusted request IDs, response correlation, safe generic 500, JSON fields and recursive secret redaction.
- [x] Generate or validate a bounded request ID, propagate it through response headers/error bodies/context and structured logs.
- [x] Centralize stable Russian public messages and redact authorization, cookie, token, password, secret and webhook identifiers from values and nested structures.
- [x] Verify that unexpected exceptions expose only the catalog error and support request ID while logs retain safe diagnostic context.
- [x] Independent security review and commit.

## Task 3: Ingress and rate-limit hardening for 40 accounts

**Files:**
- Modify: `backend/app/main.py`, `backend/app/api/v1/webhooks.py`, `backend/app/services/webhook_subscription_service.py`, `backend/app/core/config.py`
- Modify tests: `backend/tests/api/test_webhooks.py`, `backend/tests/integration/test_authorized_routes.py`

- [x] Write failing tests proving 40 tenants behind one IP do not consume one shared authenticated bucket; unknown clients remain bounded.
- [x] Replace the process-local all-route IP policy with bounded route/identity-aware limits that preserve CORS and `Retry-After`.
- [x] Preserve the 64 KiB webhook limit, opaque 256-bit callback secret, constant-time lookup behavior, bounded unknown-source buckets and poll-only semantics. Document the opaque secret as the provider-compatible signature equivalent; do not invent an HMAC header amoCRM does not send.
- [x] Prove replay cannot create domain data, only idempotently make authoritative polling due; document the multi-worker boundary.
- [x] Independent security review and commit.

## Task 4: PostgreSQL indexes, query plans and SLA

**Files:**
- Create: `backend/migrations/versions/014_phase8_performance_indexes.py`
- Modify matching SQLAlchemy model metadata only where needed
- Create: `backend/tests/integration/test_query_plans.py`, `backend/tests/integration/test_phase8_performance.py`

- [x] Capture representative PostgreSQL EXPLAIN plans for team status, activity window, reports, worker due-account lookup and raw cleanup.
- [x] Add only composite indexes proven useful for account/user/group/time/status access paths; keep one Alembic head and reversible downgrade.
- [x] Verify index presence/use, migration roundtrip, constant monitoring query count and a documented 40-account timing threshold on the local test environment.
- [x] Independent database/performance review and commit.

## Task 5: Safe catalog cache and immediate authorization changes

**Files:**
- Modify if necessary: `backend/app/services/event_ingestion_service.py`
- Modify tests: ingestion/catalog and access-policy integration tests

- [x] Prove the durable account-scoped event-type catalog is reused only within its one-day TTL and refreshes after expiry/failure rules.
- [x] Prove role/group/tracking changes are read from current database state and are never served from an uninvalidated cache.
- [x] Add no new cache unless measurements demonstrate a safe directory needs one; record the explicit no-rights-cache rule.
- [x] Independent review and commit.

## Task 6: Failure recovery and browser smoke

**Files:**
- Create: `backend/tests/integration/test_failure_recovery.py`, `frontend/tests/smoke.spec.js`
- Modify recovery code only when a failing scenario proves a defect

- [ ] Cover amoCRM 429/5xx/timeout, later-page rollback, token refresh, lease takeover, worker cancellation and restart without cursor or normalized-data loss.
- [ ] Cover backend-down/recovery in the widget: no false success/Working state, simple Russian error, bounded retry and clean lifecycle.
- [ ] Verify deduplication and replay behavior across retries for 40 isolated accounts.
- [ ] Independent recovery review and commit.

## Task 7: CI, operations and phase-wide gate

**Files:**
- Create: `.github/workflows/ci.yml`, `docs/operations.md`
- Modify: `docs/API.md`, `docs/development-workflow.md`, `Plan.md`

- [ ] Add PostgreSQL 15 CI with Alembic upgrade/head checks, full backend, Node, Playwright, package/ZIP, Black/compileall/diff checks and static Compose validation; build the backend image on the CI runner.
- [ ] Document clean startup, migrations, liveness/readiness, backup/restore, 40-account sizing, logs/request IDs, recovery, rate limits, SLA and the external Docker/live amoCRM gates.
- [ ] Run fresh full PostgreSQL/backend/frontend/browser/package/security/performance gates.
- [ ] Review the full Phase 8 diff against all seven `Plan.md` checkboxes; fix every Critical/Important finding.
- [ ] Update every Phase 8 checkbox, status/progress tables, final report, files, exact results and user-checkable scenarios; commit only after evidence.

## Boundaries and rulings

- The production Compose file is secure by default; developer conveniences belong in an ignored override file.
- The webhook body remains untrusted and is never a source of domain events. The high-entropy callback path is the provider-compatible authenticity control until amoCRM documents a verifiable signature.
- Authorization and group membership are not cached. The durable event-type catalog is the only current safe TTL-backed catalog.
- Local absence of Docker blocks only the local container execution proof, not static configuration, PostgreSQL migration, CI definition or application tests. The external gate must stay visible in `Plan.md`.
