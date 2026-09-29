const test = require('node:test');
const assert = require('node:assert/strict');
const { JSDOM } = require('jsdom');

const Dashboard = require('../monitoring/dashboard');

function response(overrides = {}) {
  return {
    generated_at: '2026-09-29T09:00:00Z',
    viewer: { role: 'admin', can_view_activity: true },
    groups: [{ id: 10, name: 'Продажи' }, { id: 20, name: 'Поддержка' }],
    employees: [
      { id: 2, amocrm_user_id: 102, account_id: 1, name: 'Анна', avatar_url: null, group_id: 10,
        group_name: 'Продажи', timezone: 'Europe/Moscow', workday_started_at: '2026-09-29T06:00:00Z',
        workday_ended_at: '2026-09-29T15:00:00Z', status: 'working', status_since: '2026-09-29T06:00:00Z',
        session_started_at: '2026-09-29T06:00:00Z', session_ended_at: null, work_seconds: 3600,
        break_seconds: 60, confirmed_seconds: 600, confirmed_events: 2, activity_detail_allowed: true },
      { id: 3, amocrm_user_id: 103, account_id: 1, name: 'Борис', avatar_url: null, group_id: 20,
        group_name: 'Поддержка', timezone: 'Europe/Moscow', workday_started_at: '2026-09-29T06:00:00Z',
        workday_ended_at: '2026-09-29T15:00:00Z', status: 'not_started', status_since: null,
        session_started_at: null, session_ended_at: null, work_seconds: 0, break_seconds: 0,
        confirmed_seconds: 0, confirmed_events: 0, activity_detail_allowed: false },
    ],
    totals: { working: 1, on_break: 0, finished: 0, not_started: 1, work_seconds: 3600,
      break_seconds: 60, confirmed_seconds: 600, confirmed_events: 2 },
    ...overrides,
  };
}

function activity(userId = 2) {
  return { target: { id: userId, name: 'Анна', amocrm_user_id: 102, avatar_url: null },
    group: { id: 10, name: 'Продажи' }, timezone: 'Europe/Moscow', from: '2026-09-23', to: '2026-09-29',
    totals: { confirmed_seconds: 0, confirmed_events: 0, unconfirmed_seconds: 0 }, days: [] };
}

function scheduler() {
  const jobs = [];
  return {
    schedule(fn, delay) {
      const job = { fn, delay, cancelled: false };
      jobs.push(job);
      return () => { job.cancelled = true; };
    },
    jobs,
    latest() { return jobs.filter((job) => !job.cancelled).at(-1); },
  };
}

async function tick() { await new Promise(setImmediate); }

function boot(options = {}) {
  const dom = new JSDOM('<main id="root"></main>', { url: 'https://account.amocrm.ru' });
  Object.defineProperty(dom.window.document, 'hidden', { value: false, configurable: true });
  const queue = options.statusQueue || [Promise.resolve(response())];
  const calls = [];
  const fake = scheduler();
  const transport = {
    status(params, signal) {
      calls.push({ kind: 'status', params, signal });
      const queued = queue.shift();
      return typeof queued === 'function' ? queued() : (queued || Promise.resolve(response()));
    },
    activity(userId, from, to, signal) {
      calls.push({ kind: 'activity', userId, from, to, signal });
      return Promise.resolve(activity(userId));
    },
  };
  const dashboard = Dashboard.mount(dom.window.document.querySelector('#root'), {
    transport, schedule: fake.schedule, now: () => new Date('2026-09-29T12:00:00Z'), random: () => 0.5,
    document: dom.window.document,
  });
  return { dom, document: dom.window.document, dashboard, calls, fake, transport };
}

test('renders grouped rows, totals, Russian statuses, and activity permission', async () => {
  const fixture = boot();
  await fixture.dashboard.ready;
  assert.deepEqual(Array.from(fixture.document.querySelectorAll('.ts-monitoring__group-title'), (node) => node.textContent), ['Продажи', 'Поддержка']);
  assert.match(fixture.document.body.textContent, /Работает/);
  assert.match(fixture.document.body.textContent, /Не начинал/);
  assert.match(fixture.document.body.textContent, /Рабочий день: 09:00–18:00/);
  assert.equal(fixture.document.querySelectorAll('[data-activity-user-id]').length, 1);
  assert.match(fixture.document.querySelector('.ts-monitoring__totals').textContent, /Работают: 1/);
  fixture.dashboard.destroy();
});

test('sends search, status, and group filters to the server and supports manual refresh', async () => {
  const fixture = boot();
  await fixture.dashboard.ready;
  const search = fixture.document.querySelector('[data-filter="search"]');
  search.value = ' Анна ';
  search.dispatchEvent(new fixture.dom.window.Event('change', { bubbles: true }));
  await tick();
  const status = fixture.document.querySelector('[data-filter="status"]');
  status.value = 'working'; status.dispatchEvent(new fixture.dom.window.Event('change', { bubbles: true }));
  await tick();
  const group = fixture.document.querySelector('[data-filter="group"]');
  group.value = '10'; group.dispatchEvent(new fixture.dom.window.Event('change', { bubbles: true }));
  await tick();
  fixture.document.querySelector('[data-action="refresh"]').click();
  await tick();
  assert.deepEqual(fixture.calls.at(-1).params, { search: 'Анна', status: 'working', group_id: 10 });
  fixture.dashboard.destroy();
});

test('requests exactly seven local dates and refreshes an open modal in place', async () => {
  const fixture = boot();
  await fixture.dashboard.ready;
  fixture.document.querySelector('[data-activity-user-id="2"]').click();
  await tick();
  const firstModal = fixture.document.querySelector('.ts-activity-modal');
  assert.deepEqual(fixture.calls.at(-1), { kind: 'activity', userId: 2, from: '2026-09-23', to: '2026-09-29', signal: fixture.calls.at(-1).signal });
  await fixture.dashboard.refresh();
  await tick();
  assert.equal(fixture.document.querySelector('.ts-activity-modal'), firstModal);
  assert.equal(fixture.calls.filter((call) => call.kind === 'activity').length, 2);
  fixture.dashboard.destroy();
});

test('uses one status request and bounded backoff, then resets to 30 seconds', async () => {
  let rejectFirst;
  const first = new Promise((_resolve, reject) => { rejectFirst = reject; });
  const fixture = boot({ statusQueue: [first, () => Promise.reject(new Error('offline')), Promise.resolve(response())] });
  assert.equal(fixture.calls.filter((call) => call.kind === 'status').length, 1);
  assert.equal(fixture.fake.latest(), undefined);
  rejectFirst(new Error('offline'));
  await tick();
  assert.equal(fixture.fake.latest().delay, 30000);
  fixture.fake.latest().fn(); await tick();
  assert.equal(fixture.fake.latest().delay, 60000);
  fixture.fake.latest().fn(); await tick();
  assert.equal(fixture.fake.latest().delay, 30000);
  fixture.dashboard.destroy();
});

test('backoff sequence is capped and jitter stays within ten percent', async () => {
  const dom = new JSDOM('<main id="root"></main>');
  Object.defineProperty(dom.window.document, 'hidden', { value: false, configurable: true });
  const fake = scheduler();
  const delays = [];
  const dashboard = Dashboard.mount(dom.window.document.querySelector('#root'), {
    transport: { status: () => Promise.reject(new Error('offline')), activity: () => Promise.resolve(activity()) },
    schedule(fn, delay) { delays.push(delay); return fake.schedule(fn, delay); },
    now: () => new Date('2026-09-29T12:00:00Z'), random: () => 1, document: dom.window.document,
  });
  for (let index = 0; index < 6; index += 1) { await tick(); const job = fake.latest(); job.fn(); }
  await tick();
  assert.deepEqual(delays.slice(0, 6), [33000, 66000, 132000, 264000, 330000, 330000]);
  dashboard.destroy();
});

test('hidden page pauses polling and visible page resumes immediately', async () => {
  const fixture = boot();
  await fixture.dashboard.ready;
  Object.defineProperty(fixture.document, 'hidden', { value: true, configurable: true });
  fixture.document.dispatchEvent(new fixture.dom.window.Event('visibilitychange'));
  assert.equal(fixture.fake.jobs.every((job) => job.cancelled), true);
  const before = fixture.calls.length;
  Object.defineProperty(fixture.document, 'hidden', { value: false, configurable: true });
  fixture.document.dispatchEvent(new fixture.dom.window.Event('visibilitychange'));
  await tick();
  assert.equal(fixture.calls.length, before + 1);
  fixture.dashboard.destroy();
});

test('aborted stale responses cannot overwrite newer state', async () => {
  let resolveOld;
  const old = new Promise((resolve) => { resolveOld = resolve; });
  const fixture = boot({ statusQueue: [old, Promise.resolve(response({ employees: [response().employees[1]], groups: [response().groups[1]] }))] });
  const newer = fixture.dashboard.refresh();
  assert.equal(fixture.calls.filter((call) => call.kind === 'status').length, 1);
  assert.equal(fixture.calls[0].signal.aborted, true);
  resolveOld(response());
  await newer;
  await tick();
  await tick();
  assert.equal(fixture.calls.filter((call) => call.kind === 'status').length, 2);
  assert.match(fixture.document.body.textContent, /Борис/);
  assert.doesNotMatch(fixture.document.body.textContent, /Анна/);
  fixture.dashboard.destroy();
});

test('rapid manual, filter, and visibility refreshes coalesce without overlapping transport', async () => {
  const dom = new JSDOM('<main id="root"></main>', { url: 'https://account.amocrm.ru' });
  Object.defineProperty(dom.window.document, 'hidden', { value: false, configurable: true });
  const fake = scheduler();
  const pending = [];
  let active = 0;
  let maxActive = 0;
  let calls = 0;
  const dashboard = Dashboard.mount(dom.window.document.querySelector('#root'), {
    document: dom.window.document, schedule: fake.schedule, random: () => 0.5,
    transport: {
      status() {
        calls += 1; active += 1; maxActive = Math.max(maxActive, active);
        return new Promise((resolve) => pending.push(() => { active -= 1; resolve(response()); }));
      },
      activity() { return Promise.reject(new Error('not used')); },
    },
  });
  dom.window.document.querySelector('[data-action="refresh"]').click();
  dom.window.document.querySelector('[data-filter="search"]').dispatchEvent(new dom.window.Event('change', { bubbles: true }));
  Object.defineProperty(dom.window.document, 'hidden', { value: true, configurable: true });
  dom.window.document.dispatchEvent(new dom.window.Event('visibilitychange'));
  Object.defineProperty(dom.window.document, 'hidden', { value: false, configurable: true });
  dom.window.document.dispatchEvent(new dom.window.Event('visibilitychange'));
  assert.equal(calls, 1);
  assert.equal(maxActive, 1);

  pending.shift()();
  await tick(); await tick();
  assert.equal(calls, 2);
  assert.equal(active, 1);
  assert.equal(maxActive, 1);
  pending.shift()();
  await tick(); await tick();
  assert.equal(active, 0);
  assert.equal(fake.jobs.filter((job) => !job.cancelled).length, 1);
  dashboard.destroy();
  dom.window.close();
});

test('destroy aborts work, removes listeners and DOM, and remount is clean', async () => {
  let resolvePending;
  const pending = new Promise((resolve) => { resolvePending = resolve; });
  const fixture = boot({ statusQueue: [Promise.resolve(response()), pending, Promise.resolve(response())] });
  await fixture.dashboard.ready;
  const inFlight = fixture.dashboard.refresh();
  const firstSignal = fixture.calls.at(-1).signal;
  fixture.dashboard.destroy();
  assert.equal(firstSignal.aborted, true);
  assert.equal(fixture.document.querySelector('.ts-monitoring'), null);
  resolvePending(response());
  await inFlight;
  const second = Dashboard.mount(fixture.document.querySelector('#root'), {
    transport: fixture.transport, schedule: fixture.fake.schedule, now: () => new Date('2026-09-29T12:00:00Z'),
    random: () => 0.5, document: fixture.document,
  });
  await second.ready;
  assert.equal(fixture.document.querySelectorAll('.ts-monitoring').length, 1);
  second.destroy();
});

test('forty account dashboards keep rows, requests, and polling timers isolated', async () => {
  const fixtures = Array.from({ length: 40 }, (_, index) => {
    const accountId = index + 1;
    const dom = new JSDOM('<main id="root"></main>', { url: `https://account-${accountId}.amocrm.ru` });
    Object.defineProperty(dom.window.document, 'hidden', { value: false, configurable: true });
    const fake = scheduler();
    const calls = [];
    const ownResponse = response({
      groups: [{ id: 10, name: `Группа ${accountId}` }],
      employees: [{ ...response().employees[0], id: accountId, account_id: accountId,
        amocrm_user_id: 777, name: `Сотрудник ${accountId}` }],
      totals: { employees: 1, working: 1, on_break: 0, finished: 0, not_started: 0 },
    });
    const dashboard = Dashboard.mount(dom.window.document.querySelector('#root'), {
      document: dom.window.document,
      transport: {
        status(params, signal) { calls.push({ params, signal }); return Promise.resolve(ownResponse); },
        activity() { return Promise.reject(new Error('not used')); },
      },
      schedule: fake.schedule, now: () => new Date('2026-09-29T12:00:00Z'), random: () => 0.5,
    });
    return { accountId, dom, dashboard, calls, fake };
  });

  await Promise.all(fixtures.map((fixture) => fixture.dashboard.ready));
  for (const fixture of fixtures) {
    assert.equal(fixture.calls.length, 1);
    assert.equal(fixture.fake.jobs.filter((job) => !job.cancelled).length, 1);
    assert.match(fixture.dom.window.document.body.textContent, new RegExp(`Сотрудник ${fixture.accountId}`));
    const foreign = fixture.accountId === 40 ? 1 : fixture.accountId + 1;
    assert.doesNotMatch(fixture.dom.window.document.body.textContent, new RegExp(`Сотрудник ${foreign}(?!\\d)`));
    fixture.dashboard.destroy();
    fixture.dom.window.close();
  }
});
