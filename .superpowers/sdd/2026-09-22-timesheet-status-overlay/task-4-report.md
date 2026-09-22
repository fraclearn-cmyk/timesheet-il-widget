# Task 4 report — Widget transport and fail-open lifecycle

## Result

Implemented the fail-open status controller and wired the working widget lifecycle to the configured `api_url` through `$authorizedAjax`.

## Changed files

- `widget/timesheet/controller.js` — UMD controller with confirmed-snapshot validation, one in-flight command/UUID, retry, 409 refresh, and synchronous clear on uncertain state.
- `widget/script.js` — AMD dependency on the controller; `$authorizedAjax` transport for `/timesheet/*`; focus refresh and destruction cleanup. Removed legacy `$.ajax` session routes, browser identity payloads, demo identities, local-success fallbacks, and inline working UI.
- `frontend/tests/timesheet-controller.test.js` — Node/jsdom behavior coverage.
- `frontend/tests/widget-lifecycle.test.js` — working lifecycle integration coverage while preserving Phase 3 settings behavior.

## Tests run

- `node --test frontend/tests/timesheet-controller.test.js` — 8 passed.
- `npm run test:settings` — 40 passed, including `frontend/tests/widget-lifecycle.test.js`.
- `git diff --check` — passed.

The controller tests cover initial outage, outage after confirmed UI and scheduled recovery, invalid snapshot, lost POST response with reused UUID, 409 refresh, double click, `track_time=false`, `hide_widget=true`, and destroy cleanup. Lifecycle tests verify no-URL fail-open, configured authenticated GET to `api_url + /timesheet/my-status` without browser identity fields, focus refresh, and Phase 3 settings callbacks.

## Double-click finding

The original failing assertion checked the mock transport before the controller's deliberate Promise microtask dispatched the POST. The second click was already correctly deduplicated by `inFlight`. The test now yields one microtask before observing the request boundary, so it asserts the intended contract: exactly one POST while the first request remains pending.

The prior agent's original RED/GREEN evidence is unavailable after its limit failure. In this continuation I observed the supplied failing test, added/updated the regression coverage, and ran the resulting GREEN suites recorded above.

## Self-review

- No working request uses `$.ajax`, legacy `/sessions/*`, demo identities, or browser account/user IDs.
- Requests render only validated snapshots; all transport, invalid-data, and no-URL paths clear working UI before retry/no-op.
- Existing Phase 3 settings transport, advanced-settings ownership, native `onSave`, and settings tests remain intact.
- `renderTimesheetStatus`/`clearTimesheetStatus` are intentionally optional integration hooks for Task 5's overlay module; Task 4 does not create an offline fallback UI.

## Concerns

`widget/manifest.json` still exposes only settings locations, as protected by the existing Phase 3 lifecycle test. Enabling a working amoCRM location and implementing the actual namespaced overlay remain the responsibility of the later UI task; this task is ready to receive that renderer without creating UI on unconfirmed state.

## Fix round 1

Added a request generation guard: only the latest status/command operation may apply a snapshot or a failure. An out-of-order old GET success therefore cannot restore UI after a newer failed refresh has entered fail-open mode. Repeated working-area initialization now disposes the prior controller and focus listener before installing a replacement. `package.json` now exposes `npm run test:timesheet` without changing `test:settings`.

Added regressions for the stale GET/outage ordering, scheduler-driven lost-POST retry with the same UUID, and duplicate working initialization/focus listener.

### RED

`node --test frontend/tests/timesheet-controller.test.js frontend/tests/widget-lifecycle.test.js` produced 23 tests: 21 passed and 2 failed as expected:

- `older GET success cannot restore UI after a newer outage clears it`: stale success rendered 2 UI nodes, expected 0.
- `repeated working init replaces its controller and focus refresh listener`: focus caused 4 GETs, expected 3.

The scheduler-driven retry test already passed against the prior implementation; it documents existing required behavior and required no production change.

### GREEN

- `npm run test:timesheet` — 10 passed.
- `node --test frontend/tests/widget-lifecycle.test.js` — 13 passed.
- `npm run test:settings` — 41 passed.
- `git diff --check` — passed.

The original agent's RED evidence remains unavailable; the RED results above are only from this fix round.
