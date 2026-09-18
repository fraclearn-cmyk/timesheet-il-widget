# Phase 2 implementation report

Date: 2026-09-18. Base: `d04cdc5` on `main`.

## Scope and result

This change adds a server-side OAuth/account context boundary, an async amoCRM
transport, non-destructive user synchronization, account-scoped access-policy
primitives, and migration `006`. `Plan.md` was deliberately not edited.

- `AmoCRMClient` has a finite timeout/retry budget, retries only timeout,
  transport and 502/503/504 failures, observes `Retry-After` for 429, and does
  not log request credentials or payloads.
- OAuth token pairs are encrypted with Fernet derived from configured secret
  material. Diagnostics mask values; a refresh writes neither replacement token
  unless amoCRM returned the full pair.
- `oauth_connections` keeps account metadata and encrypted token pairs. Users
  store observed avatar/rights/role evidence but local Admin/ROP/employee role
  is not inferred from unvalidated amoCRM rights mapping.
- User sync upserts known users and marks missing users inactive without deleting
  membership or work-history rows.
- Protected routers require `get_request_context`. In production legacy
  `X-User-Id`/`X-Account-Id` are rejected; after OAuth verification only
  server-derived compatibility values are injected for old handlers. The legacy
  adapter is enabled solely when `ENVIRONMENT=test`.
- `GET /api/v1/me` returns only the verified account/user context. `AccessPolicy`
  constrains employee self access, active-group manager access and active,
  account-scoped admin access.

## TDD evidence

Initial RED, from `backend`:

```powershell
..\.venv312\Scripts\python.exe -m pytest -q tests/integration/test_oauth.py tests/integration/test_access_policy.py tests/integration/test_user_sync.py --tb=short
```

Observed: three collection failures for the then-missing `amocrm_client`,
`access_policy` and `user_sync_service` modules. After the minimum implementation,
the same checks were green (7 passed). The request-context test was added and
observed RED as `404` before `/api/v1/me` existed; after implementation its three
cases passed.

One test-fixture correction was required during GREEN: the alleged foreign group
initially used the same manager ID, so access was correctly granted. The fixture
was corrected to use a distinct manager; policy code was not loosened.

## PostgreSQL migration verification

A dedicated local PostgreSQL 15 container named
`timesheet_phase2_disposable_pg` (label
`purpose=disposable-phase2-verification`) was created with an automatically
allocated localhost port. It was not the existing application database container.
The test fixture created and dropped only UUID-named databases. Result:

```powershell
$env:TEST_POSTGRES_ADMIN_URL='postgresql://postgres@127.0.0.1:<ephemeral-port>/postgres'
..\.venv312\Scripts\python.exe -m pytest -q -s tests/integration/test_migrations.py --tb=short
```

`4 passed, 2 warnings`. The clean cycle exercised `001 → … → 006 → 004 → 006`.
The disposable container was removed after verifying no fixture databases remained.

## Final verification

| Check | Result |
|---|---|
| Focused phase tests | `9 passed` |
| Full `pytest -q --tb=short` | `149 passed, 4 skipped, 25 warnings` |
| Disposable PostgreSQL migration suite | `4 passed, 2 warnings` |
| `python -m compileall -q app migrations` | exit 0 |
| `python -m alembic heads` | exactly `006 (head)` |
| Black on phase files | unchanged / exit 0 |
| Flake8 on phase files (`E501,W503` project ignores) | exit 0 |
| `git diff --check` | exit 0 |

The 25 warnings include the documented phase-1 legacy/dependency warnings and
one Starlette TestClient dependency deprecation surfaced by the new HTTP boundary
test. No warning filter was added.

## Files

Created: `backend/app/integrations/amocrm_client.py`,
`backend/app/integrations/oauth.py`, `backend/app/models/oauth_connection.py`,
`backend/app/core/access_policy.py`, `backend/app/api/v1/dependencies.py`,
`backend/app/services/user_sync_service.py`, migration `006`, and four phase
integration test files.

Modified: `main.py`, user model/model exports, Alembic environment and migration
integration assertions.

## Limits for review

- No live amoCRM request was made and no ignored `.env` credential was read. The
  auth-code redirect and live rights-to-role mapping remain explicitly unverified.
- The phase-0 contract confirms only one observed users page. Pagination follows
  explicit `next` links but does not invent page-number behavior.
- Legacy endpoint response schemas and business-specific 403/404/409 mappings
  still need their route-by-route consolidation in the later API phases. The new
  global context gate prevents production use of caller-provided identity headers;
  `AccessPolicy` is the required account/group-scoped primitive for that work.
