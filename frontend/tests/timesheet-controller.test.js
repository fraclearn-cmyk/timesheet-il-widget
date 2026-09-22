const test = require('node:test');
const assert = require('node:assert/strict');
const { JSDOM } = require('jsdom');
const { createTimesheetController } = require('../../widget/timesheet/controller');

const status = (name = 'on_break', extra = {}) => ({ session_id: name === 'not_started' ? null : 7,
  status: name, started_at: '2026-09-22T08:00:00Z', ended_at: null, break_seconds: 60,
  track_time: true, hide_widget: false, restart_allowed: false, ...extra });
function fixture(responses) {
  const dom = new JSDOM('<body><main id="amo">content</main></body>');
  const calls = []; const jobs = [];
  const render = (snapshot) => { dom.window.document.body.insertAdjacentHTML('beforeend',
    `<div class="timesheet-overlay"><button class="timesheet-action">${snapshot.status}</button></div>`); };
  const clear = () => dom.window.document.querySelectorAll('.timesheet-overlay, .timesheet-action')
    .forEach((node) => node.remove());
  const controller = createTimesheetController({
    request: (options) => { calls.push(options); const answer = responses.shift();
      return typeof answer === 'function' ? answer(options) : answer; },
    render, clear, schedule: (fn) => { jobs.push(fn); return () => { const i = jobs.indexOf(fn); if (i >= 0) jobs.splice(i, 1); }; },
    uuid: () => '123e4567-e89b-42d3-a456-426614174000',
  });
  return { controller, document: dom.window.document, calls, jobs };
}

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
  f.jobs.shift()(); await Promise.resolve(); await Promise.resolve();
  assert.equal(f.document.querySelectorAll('.timesheet-overlay').length, 1);
});
test('invalid snapshot clears previously confirmed UI', async () => {
  const f = fixture([status(), { status: 'working' }]);
  await f.controller.load(); await f.controller.load();
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
