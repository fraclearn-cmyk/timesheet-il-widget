const test = require('node:test');
const assert = require('node:assert/strict');
const { JSDOM } = require('jsdom');
const { createActivityTracker } = require('../../widget/activity-tracker');
const { createTimesheetController } = require('../../widget/timesheet/controller');

const WORKING = { status: 'working', track_time: true, hide_widget: true };

function fixture(responses = []) {
  const dom = new JSDOM('<body><input id="secret" value="Customer private note"></body>');
  const jobs = [];
  const sent = [];
  let milliseconds = Date.parse('2026-09-23T09:00:00.000Z');
  let uuidNumber = 0;
  const tracker = createActivityTracker({
    document: dom.window.document,
    now: () => new Date(milliseconds),
    uuid: () => `00000000-0000-4000-8000-${String(++uuidNumber).padStart(12, '0')}`,
    request: (payload) => {
      sent.push(JSON.parse(JSON.stringify(payload)));
      const response = responses.shift();
      return typeof response === 'function' ? response(payload) : Promise.resolve(response);
    },
    schedule: (fn, delay) => {
      const job = { fn, at: milliseconds + delay };
      jobs.push(job);
      return () => { const index = jobs.indexOf(job); if (index >= 0) jobs.splice(index, 1); };
    },
  });
  async function advance(delay) {
    const target = milliseconds + delay;
    while (jobs.some((job) => job.at <= target)) {
      jobs.sort((left, right) => left.at - right.at);
      const job = jobs.shift();
      milliseconds = job.at;
      job.fn();
      await new Promise(setImmediate);
    }
    milliseconds = target;
    await new Promise(setImmediate);
  }
  return { dom, jobs, sent, tracker, advance };
}

test('one-minute batch contains only aggregate fields and never browser input', async () => {
  const f = fixture();
  f.tracker.updateSnapshot(WORKING);
  const input = f.dom.window.document.querySelector('#secret');
  input.dispatchEvent(new f.dom.window.KeyboardEvent('keydown', { key: 'SecretText', bubbles: true }));
  input.dispatchEvent(new f.dom.window.MouseEvent('pointerdown', { clientX: 713, clientY: 419, bubbles: true }));
  await f.advance(59999);
  assert.equal(f.sent.length, 0);
  await f.advance(1);
  assert.deepEqual(Object.keys(f.sent[0]).sort(),
    ['command_id', 'last_seen_at', 'signal_count', 'window_started_at']);
  assert.equal(f.sent[0].signal_count, 2);
  assert.equal(f.sent[0].window_started_at, '2026-09-23T09:00:00.000Z');
  assert.equal(f.sent[0].last_seen_at, '2026-09-23T09:00:00.000Z');
  const body = JSON.stringify(f.sent[0]);
  for (const forbidden of ['SecretText', 'Customer private note', '713', '419', 'account_id', 'user_id']) {
    assert.equal(body.includes(forbidden), false, forbidden);
  }
  f.tracker.destroy();
});

test('lost response retries one pending aggregate with the same UUID and payload', async () => {
  const f = fixture([() => Promise.reject(new Error('offline')), undefined]);
  f.tracker.updateSnapshot(WORKING);
  f.dom.window.document.dispatchEvent(new f.dom.window.KeyboardEvent('keydown', { key: 'x' }));
  await f.advance(60000);
  assert.equal(f.sent.length, 1);
  await f.advance(59999);
  assert.equal(f.sent.length, 1);
  await f.advance(1);
  assert.equal(f.sent.length, 2);
  assert.deepEqual(f.sent[1], f.sent[0]);
  f.tracker.destroy();
});

test('visibility change flushes a working aggregate without creating UI', async () => {
  const f = fixture();
  f.tracker.updateSnapshot(WORKING);
  f.dom.window.document.dispatchEvent(new f.dom.window.MouseEvent('pointerdown'));
  Object.defineProperty(f.dom.window.document, 'visibilityState', { value: 'hidden', configurable: true });
  f.dom.window.document.dispatchEvent(new f.dom.window.Event('visibilitychange'));
  await new Promise(setImmediate);
  assert.equal(f.sent.length, 1);
  assert.equal(f.dom.window.document.body.children.length, 1);
  f.tracker.destroy();
});

test('two hidden flushes cannot send two new batches inside one minute', async () => {
  const f = fixture();
  f.tracker.updateSnapshot(WORKING);
  Object.defineProperty(f.dom.window.document, 'visibilityState', { value: 'hidden', configurable: true });
  f.dom.window.document.dispatchEvent(new f.dom.window.KeyboardEvent('keydown', { key: 'first' }));
  f.dom.window.document.dispatchEvent(new f.dom.window.Event('visibilitychange'));
  await new Promise(setImmediate);
  assert.equal(f.sent.length, 1);

  await f.advance(10000);
  f.dom.window.document.dispatchEvent(new f.dom.window.KeyboardEvent('keydown', { key: 'second' }));
  f.dom.window.document.dispatchEvent(new f.dom.window.Event('visibilitychange'));
  await new Promise(setImmediate);
  assert.equal(f.sent.length, 1);
  await f.advance(49999);
  assert.equal(f.sent.length, 1);
  await f.advance(1);
  assert.equal(f.sent.length, 2);
  assert.notEqual(f.sent[1].command_id, f.sent[0].command_id);
  assert.equal(f.sent[1].signal_count, 1);
  f.tracker.destroy();
});

test('break, finished and tracking-disabled snapshots discard stale state', async () => {
  for (const snapshot of [
    { ...WORKING, status: 'on_break' },
    { ...WORKING, status: 'finished' },
    { ...WORKING, track_time: false },
  ]) {
    const f = fixture();
    f.tracker.updateSnapshot(WORKING);
    f.dom.window.document.dispatchEvent(new f.dom.window.KeyboardEvent('keydown', { key: 'private' }));
    f.tracker.updateSnapshot(snapshot);
    await f.advance(180000);
    assert.deepEqual(f.sent, []);
    assert.equal(f.jobs.length, 0);
    f.tracker.destroy();
  }
});

test('signal count is capped and destroy removes listeners and timers', async () => {
  const f = fixture();
  f.tracker.updateSnapshot(WORKING);
  for (let index = 0; index < 100005; index += 1) {
    f.dom.window.document.dispatchEvent(new f.dom.window.Event('pointerdown'));
  }
  await f.advance(60000);
  assert.equal(f.sent[0].signal_count, 100000);
  f.dom.window.document.dispatchEvent(new f.dom.window.Event('keydown'));
  f.tracker.destroy();
  assert.equal(f.jobs.length, 0);
  f.dom.window.document.dispatchEvent(new f.dom.window.Event('pointerdown'));
  await f.advance(180000);
  assert.equal(f.sent.length, 1);
});

test('timesheet observer disables tracking when confirmed status becomes unavailable', async () => {
  const snapshots = [];
  const responses = [
    { session_id: 7, status: 'working', started_at: '2026-09-23T08:00:00Z', ended_at: null,
      break_seconds: 0, track_time: true, hide_widget: true, restart_allowed: false },
    Promise.reject(new Error('offline')),
  ];
  const jobs = [];
  const controller = createTimesheetController({
    request: () => responses.shift(),
    render: () => {}, clear: () => {}, uuid: () => 'unused',
    onSnapshot: (snapshot) => snapshots.push(snapshot),
    schedule: (fn, delay) => { const job = { fn, delay }; jobs.push(job); return () => {
      const index = jobs.indexOf(job); if (index >= 0) jobs.splice(index, 1);
    }; },
  });
  await controller.load();
  await controller.load();
  assert.equal(snapshots[0].status, 'working');
  assert.equal(snapshots[1], null);
  controller.destroy();
});

test('forty account browser contexts keep their batches and UUID state isolated', async () => {
  const accounts = Array.from({ length: 40 }, () => fixture());
  for (const [index, account] of accounts.entries()) {
    account.tracker.updateSnapshot(WORKING);
    account.dom.window.document.dispatchEvent(new account.dom.window.KeyboardEvent('keydown', {
      key: `private-account-${index + 1}`,
    }));
  }
  await Promise.all(accounts.map((account) => account.advance(60000)));
  for (const [index, account] of accounts.entries()) {
    assert.equal(account.sent.length, 1, `account ${index + 1}`);
    assert.equal(account.sent[0].signal_count, 1);
    assert.equal(account.sent[0].command_id, '00000000-0000-4000-8000-000000000001');
    const body = JSON.stringify(account.sent[0]);
    assert.equal(body.includes(`private-account-${index + 1}`), false);
    assert.equal(body.includes('account_id'), false);
    assert.equal(body.includes('user_id'), false);
    account.tracker.destroy();
    account.dom.window.close();
  }
});
