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
