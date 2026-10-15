const test = require('node:test');
const assert = require('node:assert/strict');
const { JSDOM } = require('jsdom');
const { createTimesheetController } = require('../../widget/timesheet/controller');
const { createOverlay } = require('../../widget/overlay');

const status = (name = 'on_break', extra = {}) => ({ session_id: name === 'not_started' ? null : 7,
  status: name, started_at: '2026-09-22T08:00:00Z', ended_at: null, break_seconds: 60,
  track_time: true, hide_widget: false, restart_allowed: false,
  late_reason_required: false, late_reason_kind: null, late_minutes: 0, break_sequence: null, ...extra });
function fixture(responses, realOverlay = false) {
  const dom = new JSDOM('<body><main id="amo">content</main></body>');
  const calls = []; const jobs = [];
  let now = 0, commandNumber = 0;
  const render = (snapshot) => { clear(); dom.window.document.body.insertAdjacentHTML('beforeend',
    `<div class="timesheet-overlay"><button class="timesheet-action">${snapshot.status}</button></div>`); };
  const clear = () => dom.window.document.querySelectorAll('.timesheet-overlay, .timesheet-action')
    .forEach((node) => node.remove());
  const overlay = createOverlay(dom.window.document);
  const controller = createTimesheetController({
    request: (options) => { calls.push(options); const answer = responses.shift();
      return typeof answer === 'function' ? answer(options) : answer; },
    render: realOverlay ? (snapshot) => overlay.render(snapshot, controller.command) : render,
    clear: realOverlay ? overlay.clear : clear,
    schedule: (fn, delay) => { fn.delay = delay; fn.at = now + delay; jobs.push(fn); return () => { const i = jobs.indexOf(fn); if (i >= 0) jobs.splice(i, 1); }; },
    uuid: () => '123e4567-e89b-42d3-a456-42661417400' + commandNumber++,
  });
  async function advance(milliseconds) {
    const target = now + milliseconds;
    while (jobs.some((job) => job.at <= target)) {
      jobs.sort((a, b) => a.at - b.at);
      const job = jobs.shift();
      now = job.at;
      job();
      await flush();
    }
    now = target;
  }
  return { controller, document: dom.window.document, calls, jobs, advance, dom };
}
const flush = () => new Promise(setImmediate);
function fire(f, delay) {
  const index = f.jobs.findIndex((job) => job.delay === delay);
  assert.notEqual(index, -1, `missing scheduled job at ${delay}ms`);
  f.jobs.splice(index, 1)[0]();
}

test('periodic status probe detects outage after success and retries to recover', async () => {
  const f = fixture([status(), () => Promise.reject(new Error('offline')), status()]);
  await f.controller.load();
  fire(f, 30000); await flush();
  assert.equal(f.calls.length, 2);
  assert.equal(f.document.querySelectorAll('.timesheet-overlay').length, 0);
  fire(f, 5000); await flush();
  assert.equal(f.document.querySelectorAll('.timesheet-overlay').length, 1);
  f.controller.destroy();
  assert.equal(f.jobs.length, 0);
});

test('hung GET clears prior UI at deadline and ignores its late success', async () => {
  let finish;
  const f = fixture([status(), new Promise((resolve) => { finish = resolve; }), status('working')]);
  await f.controller.load();
  const pending = f.controller.load(); await flush();
  fire(f, 10000); await pending;
  assert.equal(f.document.querySelectorAll('.timesheet-overlay').length, 0);
  finish(status()); await flush();
  assert.equal(f.document.querySelectorAll('.timesheet-overlay').length, 0);
  fire(f, 5000); await flush();
  assert.equal(f.document.querySelector('.timesheet-action').textContent, 'working');
});

test('repeated focus during hung periodic GET cannot postpone bounded fail-open', async () => {
  let finish;
  const hung = new Promise((resolve) => { finish = resolve; });
  const responses = [status(), hung, hung, hung];
  const f = fixture(responses);
  await f.controller.load();
  await f.advance(30000); // Periodic probe starts at t=30s.
  await f.advance(4000);
  f.controller.load(); await flush(); // Focus at t=34s.
  await f.advance(4000);
  f.controller.load(); await flush(); // Focus at t=38s.
  await f.advance(1999);
  assert.equal(f.document.querySelectorAll('.timesheet-overlay').length, 1);
  await f.advance(1); // The first probe's deadline is still t=40s.
  assert.equal(f.document.querySelectorAll('.timesheet-overlay, .timesheet-action').length, 0);
  assert.equal(f.calls.length, 2);
  finish(status()); await flush();
  assert.equal(f.document.querySelectorAll('.timesheet-overlay').length, 0);
  responses.splice(0, responses.length, status('working'));
  await f.advance(5000);
  assert.equal(f.document.querySelector('.timesheet-action').textContent, 'working');
  f.controller.destroy();
  assert.equal(f.jobs.length, 0);
});

test('hung POST clears UI at deadline and retries identical UUID despite focus', async () => {
  let finish;
  const f = fixture([status('working'), new Promise((resolve) => { finish = resolve; }), status()]);
  await f.controller.load();
  const pending = f.controller.command('start-break'); await flush();
  fire(f, 10000); await pending;
  assert.equal(f.document.querySelectorAll('.timesheet-overlay').length, 0);
  await f.controller.load();
  assert.deepEqual(f.calls.map((call) => call.method), ['GET', 'POST', 'POST']);
  assert.equal(f.calls[1].data, f.calls[2].data);
  finish(status('working')); await flush();
  assert.equal(f.document.querySelector('.timesheet-action').textContent, 'on_break');
});

test('focus during POST preserves completion and allows next end-break command', async () => {
  let finish;
  const f = fixture([status('working'), new Promise((resolve) => { finish = resolve; }), status('working')]);
  await f.controller.load();
  const pending = f.controller.command('start-break'); await flush();
  const focused = f.controller.load(); await flush();
  finish(status()); await Promise.all([pending, focused]);
  await f.controller.command('end-break');
  assert.deepEqual(f.calls.map((call) => call.url), [
    '/timesheet/my-status', '/timesheet/start-break', '/timesheet/end-break',
  ]);
  assert.equal(f.document.querySelector('.timesheet-action').textContent, 'working');
});

test('initial outage leaves amoCRM available without timesheet UI', async () => {
  const f = fixture([Promise.reject(new Error('offline'))]);
  await f.controller.load();
  assert.equal(f.document.querySelectorAll('.timesheet-overlay, .timesheet-action').length, 0);
  assert.equal(f.document.querySelector('#amo').textContent, 'content');
  assert.equal(f.jobs.length, 1);
});
test('outage after confirmed break removes overlay synchronously and recovery restores it', async () => {
  const f = fixture([status(), Promise.reject(new Error('offline')), status()]);
  await f.controller.load();
  assert.equal(f.document.querySelectorAll('.timesheet-overlay').length, 1);
  const pending = f.controller.load();
  await pending;
  assert.equal(f.document.querySelectorAll('.timesheet-overlay, .timesheet-action').length, 0);
  f.jobs.shift()(); await flush();
  assert.equal(f.document.querySelectorAll('.timesheet-overlay').length, 1);
});
test('invalid snapshot clears previously confirmed UI', async () => {
  const f = fixture([status(), { status: 'working' }]);
  await f.controller.load(); await f.controller.load();
  assert.equal(f.document.querySelectorAll('.timesheet-overlay, .timesheet-action').length, 0);
});
test('older GET success cannot restore UI after a newer command outage clears it', async () => {
  let resolveOlder;
  const older = new Promise((resolve) => { resolveOlder = resolve; });
  const f = fixture([status('working'), older, () => Promise.reject(new Error('offline'))]);
  await f.controller.load();
  const first = f.controller.load();
  await Promise.resolve();
  await f.controller.command('start-break');
  assert.equal(f.document.querySelectorAll('.timesheet-overlay, .timesheet-action').length, 0);
  resolveOlder(status('on_break'));
  await first;
  assert.equal(f.document.querySelectorAll('.timesheet-overlay, .timesheet-action').length, 0);
});
test('lost POST response reuses UUID and never shows local success', async () => {
  const f = fixture([status('not_started'), Promise.reject(new Error('lost')), status('working')]);
  await f.controller.load(); await f.controller.command('start-work');
  assert.equal(f.document.querySelectorAll('.timesheet-overlay, .timesheet-action').length, 0);
  await f.controller.command('start-work');
  assert.equal(JSON.parse(f.calls[1].data).idempotency_key, JSON.parse(f.calls[2].data).idempotency_key);
  assert.equal(f.document.querySelectorAll('.timesheet-overlay').length, 1);
});
test('scheduled lost-POST retry reuses its UUID before rendering confirmed status', async () => {
  const f = fixture([status('not_started'), Promise.reject(new Error('lost')), status('working')]);
  await f.controller.load();
  await f.controller.command('start-work', '  задержался  ');
  f.jobs.shift()();
  await flush();
  assert.equal(JSON.parse(f.calls[1].data).idempotency_key, JSON.parse(f.calls[2].data).idempotency_key);
  assert.equal(JSON.parse(f.calls[2].data).reason, 'задержался');
  assert.equal(f.document.querySelectorAll('.timesheet-overlay').length, 1);
});
test('409 command conflict clears stale UI and reloads the confirmed status', async () => {
  const f = fixture([status('working'), Promise.reject({ status: 409 }), status('on_break')]);
  await f.controller.load();
  await f.controller.command('start-break');
  assert.deepEqual(f.calls.map((call) => [call.method, call.url]), [
    ['GET', '/timesheet/my-status'], ['POST', '/timesheet/start-break'], ['GET', '/timesheet/my-status'],
  ]);
  assert.equal(f.document.querySelectorAll('.timesheet-overlay').length, 1);
});
test('double click sends one POST while first request is pending', async () => {
  let finish; const pending = new Promise((resolve) => { finish = resolve; });
  const f = fixture([status('working'), pending]);
  await f.controller.load(); const first = f.controller.command('start-break');
  const second = f.controller.command('start-break');
  await Promise.resolve();
  assert.equal(f.calls.length, 2);
  finish(status()); await Promise.all([first, second]);
});
test('disabled tracking and hidden widget clear UI and reject commands', async () => {
  for (const extra of [{ track_time: false }, { hide_widget: true }]) {
    const f = fixture([status('working'), status('working', extra)]);
    await f.controller.load(); await f.controller.load(); await f.controller.command('start-break');
    assert.equal(f.document.querySelectorAll('.timesheet-overlay, .timesheet-action').length, 0);
    assert.equal(f.calls.length, 2);
  }
});
test('destroy clears UI and cancels retry', async () => {
  const f = fixture([Promise.reject(new Error('offline'))]);
  await f.controller.load(); f.controller.destroy();
  assert.equal(f.jobs.length, 0);
  assert.equal(f.document.querySelectorAll('.timesheet-overlay, .timesheet-action').length, 0);
});

test('invalid lateness fields fail open instead of offering a working command', async () => {
  for (const extra of [
    { late_reason_required: undefined }, { late_reason_required: 'true' },
    { late_reason_kind: 'other' }, { late_reason_kind: undefined },
    { late_minutes: -1 }, { late_minutes: 1.5 }, { late_minutes: Infinity },
    { break_sequence: 0 }, { break_sequence: '1' }, { break_sequence: undefined },
    { late_reason_required: true },
    { late_reason_required: true, late_reason_kind: 'shift_start', late_minutes: 2 },
  ]) {
    const f = fixture([status('on_break', extra)]);
    await f.controller.load();
    assert.equal(f.document.querySelector('.timesheet-overlay'), null, JSON.stringify(extra));
    f.controller.destroy();
  }
});

for (const [name, action, kind, sequence] of [
  ['not_started', 'start-work', 'shift_start', null], ['on_break', 'end-break', 'break_return', 2],
]) {
  test(`${action} sends trimmed reason and retries its exact content and key after a lost response`, async () => {
    const f = fixture([status(name, { late_reason_required: true, late_reason_kind: kind,
      late_minutes: 8, break_sequence: sequence }), Promise.reject(new Error('lost')), status('working')]);
    await f.controller.load();
    await f.controller.command(action, '  задержался\nна встрече  ');
    assert.equal(f.document.querySelector('.timesheet-overlay'), null);
    await f.controller.command(action, 'changed draft must not replace uncertain command');
    assert.deepEqual(JSON.parse(f.calls[1].data), {
      idempotency_key: '123e4567-e89b-42d3-a456-426614174000', reason: 'задержался\nна встрече',
    });
    assert.equal(f.calls[1].data, f.calls[2].data);
    f.controller.destroy();
  });
}

test('unrelated actions never serialize an explanation', async () => {
  for (const action of ['start-break', 'finish-work']) {
    const f = fixture([status('working'), status('finished')]);
    await f.controller.load(); await f.controller.command(action, 'private draft');
    assert.deepEqual(JSON.parse(f.calls[1].data), { idempotency_key: '123e4567-e89b-42d3-a456-426614174000' });
    f.controller.destroy();
  }
});

test('LATE_REASON_REQUIRED refreshes confirmed status and keeps the current edited draft', async () => {
  let rejectCommand;
  const late = status('on_break', { late_reason_required: true, late_reason_kind: 'break_return',
    late_minutes: 8, break_sequence: 2 });
  const f = fixture([late, new Promise((_resolve, reject) => { rejectCommand = reject; }),
    { ...late, late_minutes: 9 }, status('working')], true);
  await f.controller.load();
  const input = f.document.querySelector('textarea');
  assert.ok(input, 'required explanation field');
  input.value = 'initial';
  const pending = f.controller.command('end-break', input.value); await flush();
  input.value = '  still editing <img src=x onerror=alert(1)>  ';
  rejectCommand({ status: 409, responseJSON: { error: { code: 'LATE_REASON_REQUIRED',
    details: { kind: 'break_return', late_minutes: 9, sequence: 2 } } } });
  await pending;
  assert.deepEqual(f.calls.map((call) => call.method), ['GET', 'POST', 'GET']);
  assert.equal(f.document.querySelector('textarea').value, '  still editing <img src=x onerror=alert(1)>  ');
  assert.equal(f.document.querySelector('img'), null);
  assert.match(f.document.querySelector('.timesheet-overlay').textContent, /9 мин/);
  await f.controller.command('end-break', 'new reason');
  assert.equal(JSON.parse(f.calls[3].data).reason, 'new reason');
  assert.notEqual(JSON.parse(f.calls[1].data).idempotency_key, JSON.parse(f.calls[3].data).idempotency_key);
  assert.equal(f.document.querySelector('textarea'), null);
  f.controller.destroy();
});

test('periodic refresh preserves draft only for the same shift and action; clear removes values and listeners', async () => {
  const late = status('on_break', { late_reason_required: true, late_reason_kind: 'break_return',
    late_minutes: 8, break_sequence: 1 });
  const f = fixture([late, { ...late, late_minutes: 9 }, { ...late, session_id: 8 }], true);
  await f.controller.load();
  const oldInput = f.document.querySelector('textarea');
  assert.ok(oldInput, 'required explanation field');
  oldInput.value = 'draft';
  await f.controller.load();
  assert.equal(f.document.querySelector('textarea').value, 'draft');
  assert.equal(oldInput.value, '');
  await f.controller.load();
  assert.equal(f.document.querySelector('textarea').value, '');
  const detachedInput = f.document.querySelector('textarea');
  const detachedButton = f.document.querySelector('[data-action=end-break]');
  detachedInput.value = 'private';
  f.controller.destroy();
  assert.equal(detachedInput.value, '');
  detachedButton.click();
  assert.equal(f.calls.length, 3);
  assert.equal(f.jobs.length, 0);
});

test('crossing lateness boundary after GET requests explanation without confirming a transition', async () => {
  const f = fixture([status('not_started'), Promise.reject({ status: 409,
    responseJSON: { error: { code: 'LATE_REASON_REQUIRED' } } }),
  status('not_started', { late_reason_required: true, late_reason_kind: 'shift_start', late_minutes: 1 })], true);
  await f.controller.load();
  await f.controller.command('start-work');
  assert.deepEqual(f.calls.map((call) => call.method), ['GET', 'POST', 'GET']);
  assert.equal(f.document.querySelectorAll('textarea').length, 1);
  assert.equal(f.document.querySelector('[data-action=start-work]').disabled, true);
  assert.equal(f.document.querySelector('[data-action=start-break]'), null);
  f.controller.destroy();
});

test('outage during requirement-conflict refresh clears the draft and stays fail-open', async () => {
  const f = fixture([status('on_break', { late_reason_required: true, late_reason_kind: 'break_return',
    late_minutes: 1, break_sequence: 1 }), Promise.reject({ status: 409,
    responseJSON: { error: { code: 'LATE_REASON_REQUIRED' } } }), Promise.reject(new Error('offline'))], true);
  await f.controller.load();
  const input = f.document.querySelector('textarea');
  input.value = 'draft';
  await f.controller.command('end-break', input.value);
  assert.equal(f.document.querySelector('.timesheet-overlay'), null);
  assert.equal(input.value, '');
  assert.equal(f.jobs.length, 1);
  assert.equal(f.jobs[0].delay, 5000);
  f.controller.destroy();
});
