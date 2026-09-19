# Phase 2 implementation report

Date: 2026-09-19. Base: `d04cdc5` on `main`.

## Scope and result

This change adds a server-side OAuth/account context boundary, an async amoCRM
transport, non-destructive user synchronization, enforced account/group access
policy, and migrations `006` through `008`. `Plan.md` was deliberately not edited.
The final round-4 verification below supersedes all historical baseline counts.

- `AmoCRMClient` has a finite timeout/retry budget, retries only timeout,
  transport and 502/503/504 failures, observes `Retry-After` for 429, and does
  not log request credentials or payloads.
- OAuth token pairs are encrypted with Fernet derived from configured secret
  material. Diagnostics mask values; a refresh writes neither replacement token
  unless amoCRM returned the full pair.
- `oauth_connections` keeps account metadata and encrypted token pairs. Users
  store observed avatar/rights/role evidence. Admin access requires verified
  `rights.is_admin=true`; manager access requires an active same-account assignment
  whose own `manager_role_id` snapshot equals the current live `role_id`. Local
  `User.role` never grants manager/admin privileges. No `rights.is_active` field
  is assumed; local user/account active state and live user presence are checked.
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

## Initial implementation verification (historical)

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

- Initial implementation used hermetic tests. A later read-only live probe returned
  401, so the production redirect/live privilege flow remains unverified. Round 4
  made no live request and read no `.env` or secret credential.
- The phase-0 contract confirms only one observed users page. Pagination follows
  explicit `next` links but does not invent page-number behavior.
- Connected protected routes enforce account/user/object scope and normalized
  401/403/404/409/429 responses. Later API phases still own the full product
  contract, report-period limits and unfinished saved-report download rendering.

## Review round 1 corrections

The first review found that `AccessPolicy` was only a primitive and did not bind
legacy route identifiers to the verified request context. This is corrected by
`enforce_route_scope`, now installed on every connected protected router. It rejects
foreign account query/path values, resolves user references in the current account
through `AccessPolicy`, and validates session ownership before a handler runs.
Settings and sessions also have explicit handler-level account/policy checks, so they
do not rely on compatibility headers. Session mutations remain self-only; reads use
verified visibility. Session state conflicts are now HTTP 409 with
`SESSION_CONFLICT`; the rate limiter returns the standard 429 body and Retry-After.

For production credentials, the context reads account and current-user data from
amoCRM on every request and persists observed rights evidence. The initial local-role
restriction was replaced in round 3 by live admin evidence and per-assignment manager
snapshots; neither production nor test contexts grant privileges from local ROP alone.

Additional RED/GREEN evidence:

- HTTP tests initially reproduced foreign settings access reaching the handler and a
  foreign session mutation reaching service logic. Both now return normalized 404
  before business execution.
- A 429 middleware contract test initially found the old `{detail: ...}` body; it now
  returns `RATE_LIMITED` plus `Retry-After`.
- A pagination test initially failed because `AmoCRMClient` had no page/item limits.
  It now enforces configurable `max_pages` and `max_items` in addition to loop
  detection.
- OAuth tests now exercise code-exchange persistence encryption and a rejected refresh
  retaining the original encrypted pair.

The round-1 baseline was `156 passed, 4 skipped, 25 warnings`; the fresh
round-2 verification below supersedes that stale count.

## Recovery review: complete protected-route identifier coverage

The route-by-route audit after the first correction found that the global
dependency was installed on every connected router, but it did not yet inspect
all identifiers consumed by those routers.  The following checks are now
performed before the handler runs (and return the normalized `NOT_FOUND`
response for foreign objects):

- `work_session_id` and `activity_session_id` inherit account/user visibility
  from the owning work session;
- `report_id` is matched against the report account;
- `department_id`/`dept_id` require account ownership evidence and the principal's
  own department or a department containing a currently visible group member;
- `group_id` is matched against an active widget group in the account;
- `category_id` requires explicit category account ownership (migration `007`);
  unowned legacy categories fail closed;
- body user/session/department IDs and Excel department lists use the same scope
  checks as path/query identifiers; `generated_by` must equal the verified actor's
  internal ID and persistence always takes it from the context.

The identifier reference resolver now rejects ambiguous internal-vs-external
numeric IDs rather than choosing an arbitrary mapping.  Activity history now
has an explicit `1..1000` item bound, and report totals no longer issue an
unbounded `limit=10000` query.

TDD evidence for this recovery: the new authorized-route tests first observed
`200` for foreign activity/report/department identifiers and `403` for an
unowned Excel department body; after the central guard they return normalized
`404`.  The pagination test first observed `200` for `limit=1001`, then
returned FastAPI's bounded-parameter `422` after the minimal route change.

## Review round 2 corrections

The second review identified collection endpoints where omission of an ID
could still widen the result set.  Team stats/activity, reports without a
`user_id`, departments, and both ID-free Excel exports now apply the verified
account and visibility set: employees see only themselves, ROP users see
themselves plus active members of their own active group, and admins see
active users in the current account.  The Excel service receives the verified
account explicitly, including when no department filter is supplied.  A
multi-account workbook test verifies that a foreign row is absent from both
department and late-arrival exports.

The round-2 rights implementation was superseded by round 3: live
`rights.is_admin` and opaque `rights.role_id` are the observed fields; local ROP
is not a grant, and `rights.is_active` is not part of the accepted contract.
The read-only probe returned 401, so no successful live privilege verification
was asserted and no secret was printed.

Migration `007` adds nullable `activity_categories.account_id` and backfills
only categories whose historical events unambiguously identify one account;
ambiguous and unreferenced legacy categories remain unowned and fail closed.
Category creation can therefore authorize the first event through explicit
account ownership.  PostgreSQL tests cover first-event ownership,
cross-account denial, ambiguous backfill, downgrade safety, and the complete
`001 -> 007` disposable cycle.

Route-specific numeric semantics are explicit: sessions/team use amoCRM
external IDs, while KPI and Excel employee paths use internal IDs.  Collision
tests cover the same numeric value representing different identities.

Historical round-2 verification from `backend`:

| Check | Result |
|---|---|
| Full `pytest -q --tb=short` | `173 passed, 5 skipped, 54 warnings` |
| Disposable PostgreSQL migration suite | `5 passed, 2 warnings` (migration `007`) |
| `python -m compileall -q app migrations` | exit 0 |
| `python -m alembic heads` | exactly `007 (head)` |
| Black check on touched recovery files | exit 0 |
| Flake8 on touched recovery files (`E501,W503` ignored) | exit 0 |
| `git diff --check` | exit 0 |
| HTTP matrix evidence | normalized 401/403/404/409/429 tests green; OAuth partial refresh preserves old encrypted pair |

The disposable PostgreSQL container was removed after the migration run; no
application database container or fixture database was reused.

## Review round 3 corrections

Production privilege decisions no longer treat the local `User.role` value as
a ROP/manager grant and no longer require an invented `rights.is_active`
field.  The current amoCRM payload is accepted using the observed
`rights.is_admin` and opaque `rights.role_id` fields only.  A live admin grant
requires `is_admin=true`.  Manager access requires all of: an active
same-account `WidgetGroup` assignment, a non-null `manager_role_id` snapshot
captured at trusted assignment/backfill, and equality between that snapshot and
the current live `role_id` on every request.  A changed or missing live role
fails closed.  No role-id value is interpreted semantically.  Existing
privileged handlers now consume these policy capabilities rather than local
ROP/admin enum checks; employees retain self-only visibility.

Migration `008` adds `widget_groups.manager_role_id`, backfills only from the
unique same-account manager identity's observed role snapshot, and provides a
future `WidgetGroup.assign_manager()` path that requires an observed snapshot.
Its downgrade refuses to erase non-null snapshots or duplicate cross-account
category names.  Migration `007` now refuses to drop any explicit category
ownership it cannot reconstruct.  PostgreSQL tests cover backfill, both
lossy-downgrade guards, and the full `001 -> 008` cycle.

Activity category creation now takes account ownership exclusively from the
verified request context, persists `display_name`/description/order, exposes
`account_id` in the response schema, and enforces `(account_id, name)` rather
than global name uniqueness.  HTTP tests create the same name in two accounts
and verify both first-category responses and ownership.

Historical round-3 verification:

| Check | Result |
|---|---|
| Full `pytest -q --tb=short` | `177 passed, 8 skipped, 56 warnings` |
| Disposable PostgreSQL migration suite | `8 passed, 2 warnings` (migration `008`) |
| `python -m compileall -q app migrations` | exit 0 |
| `python -m alembic heads` | exactly `008 (head)` |
| Black check on touched recovery files | exit 0 |
| Flake8 on touched recovery files (`E501,W503` ignored) | exit 0 |
| `git diff --check` | exit 0 |

The round-3 disposable PostgreSQL container was removed after verification.

## Review round 4 corrections and final verification

Base: `7d9f6bd`. All five code findings were reproduced before their fixes.
No schema/migration was changed, no external service was contacted, and no push
or `Plan.md` edit was performed.

- `can_view_user` now compares the live manager role with the target member's
  own group snapshot. Two assignments with snapshots `77` and `78`, live role
  `78`, permit only the `78` group's members. Policy ID sets and HTTP team/report
  collections preserve that restriction.
- Department schedule reads now require the employee's own department, a currently
  authorized manager group's department, or verified account-admin access. The
  common department resolver checks both ownership and visibility. All four
  department routes were audited: list remains manager/admin only and scoped;
  schedule is self/group/account scoped; create is verified-admin only; update
  requires verified admin plus account ownership. KPI and both department Excel
  exports additionally filter individual users, so a shared legacy department
  cannot expand access to another widget group's members.
- `generated_by` in query or JSON must match the verified actor's internal ID.
  A manager/admin cannot attribute a report to a visible subordinate. Persistence
  uses `context.user.id`, independently of the supplied compatibility parameter.
- Session current/history/by-ID reads use verified user/session visibility and
  explicit account context. Managers can read their current group's members;
  employees remain self-only. Duplicate external IDs in another account no longer
  break current/history reads. Mutation authorization remains self-only.
- Employee report generation accepts and enforces the explicit visibility set.
  Missing sessions return normalized 404. Real persistence tests also exposed
  date/datetime values left in JSON by `.dict()`; generated payloads now use
  `model_dump(mode="json")`. The team collection HTTP check exposed nullable
  `is_online` for absent activity; it now returns `false` and satisfies its schema.

RED/GREEN evidence:

| Regression | Observed RED | Focused GREEN |
|---|---|---|
| Per-group role snapshot | stale group's member incorrectly visible | access policy: `6 passed` |
| Department schedule matrix | employee/manager received `200` for foreign same-account department | department schedule/list/update matrix: `16 passed` |
| Forged report provenance | after exposing/fixing JSON serialization, forged query/body returned `201` | author rejection/persistence: `7 passed` |
| Session read policy | manager/admin received `404`; duplicate external ID raised `ValueError` | session read matrix: `8 passed` |
| Employee report interface | unsupported `visible_external_user_ids` raised `TypeError` | generation and service filtering: `8 passed` |
| Shared department aggregates | KPI counted 2 instead of 1; Excel contained foreign-group employee | KPI/Excel plus team collection: `4 passed` |

The first full run also exposed test-only shared rate-limiter state and a legacy
direct-call unit test omitting `RequestContext`. Fixtures now instantiate fresh
middleware state per test, and the unit test passes a real context. Production
authorization and rate limiting were not bypassed or disabled.

Final commands from `backend` (Python: `..\.venv312\Scripts\python.exe`):

| Check | Final result |
|---|---|
| `-m pytest -q --tb=short` | `224 passed, 8 skipped, 345 warnings` |
| `-m pytest -q tests/integration/test_access_policy.py tests/integration/test_authorized_routes.py tests/integration/test_request_context.py tests/integration/test_oauth.py tests/integration/test_user_sync.py --tb=short --disable-warnings` | `85 passed, 333 warnings` |
| `-m compileall -q app migrations` | exit 0 |
| `-m alembic heads` | exactly `008 (head)` |
| Black check on all 15 touched Python files, line length 88 | exit 0 |
| Flake8 on all 15 touched Python files (`E501,W503` ignored) | exit 0 |
| `git diff --check` | exit 0 |
| Secret-pattern scan of changed diff (private keys/JWT/token/password/API-key literals; values not printed) | 0 matches |

The eight skipped tests require disposable PostgreSQL. Round 4 did not rerun that
suite because neither models nor migrations changed; the round-3 `8 passed` result
above is historical evidence, not a new run. Warnings are existing datetime,
Pydantic, SQLAlchemy and dependency deprecations exercised more often by the expanded
HTTP matrix; no production warning suppression was added.

Files changed in this round: access policy; dependencies; department, Excel, KPI,
report and session routes; Excel, KPI, report, session and team services; access-policy
and authorized-route integration tests; the existing model/route unit test; this report.
Self-review checked the complete diff, account joins, per-group predicates, author
source, denied-write persistence, real report serialization and workbook contents.

Manual/reviewable scenarios: use the test adapter only under `ENVIRONMENT=test`,
seed two manager assignments with snapshots `77`/`78`, then run the authorized-route
tests above. They exercise normalized foreign-object denials, permitted self/group
reads, author forgery, successful saved employee reports and shared-department exports.
For production, a successful OAuth/live-context verification still requires valid
credentials; no successful live claim is made here. Legacy departments retain their
pre-account schema and require active-user ownership evidence, so unassigned
departments remain unaddressable until ownership is established.
