const test = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { runInNewContext } = require('node:vm');
const { JSDOM } = require('jsdom');
const Reports = require('../reports/controller');

const directory = (role = 'admin') => ({
  generated_at: '2026-09-29T09:00:00Z', viewer: { role, can_view_activity: false },
  groups: [{ id: 10, name: 'Продажи' }, { id: 20, name: 'Поддержка' }],
  employees: [
    { id: 2, amocrm_user_id: 102, account_id: 1, name: 'Анна', group_id: 10, group_name: 'Продажи', timezone: 'Europe/Moscow', status: 'working' },
    { id: 3, amocrm_user_id: 103, account_id: 1, name: 'Борис', group_id: 20, group_name: 'Поддержка', timezone: 'Europe/Moscow', status: 'finished' },
  ],
  totals: { employees: 2, working: 1, on_break: 0, finished: 1, not_started: 0 },
});
const row = (name = 'Анна') => ({ user_id: 2, amocrm_user_id: 102, employee_name: name,
  group_id: 10, group_name: 'Продажи', group_timezone: 'Europe/Moscow', date: '2026-09-29',
  started_at: '2026-09-29T06:00:00Z', ended_at: '2026-09-29T15:00:00Z',
  break_seconds: 3660, work_seconds: 28740, late_seconds: 120, status: 'finished' });
const report = (items = [row()], extra = {}) => ({ items, page: 1, page_size: 10, total: items.length,
  totals: { work_seconds: 28740, break_seconds: 3660, late_seconds: 120, days: items.length, employees: 1 }, ...extra });
const deferred = () => { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no; }); return { promise, resolve, reject }; };
const tick = () => new Promise(setImmediate);

function boot(options = {}) {
  const dom = new JSDOM('<main id="root"></main>', { url: 'https://example.amocrm.ru' });
  const document = dom.window.document;
  const calls = [];
  const transport = {
    directory(signal) { calls.push({ kind: 'directory', signal }); return options.directoryResult || Promise.resolve(directory(options.role)); },
    report(params, signal) { calls.push({ kind: 'report', params, signal }); return options.reportResult ? options.reportResult(params, signal) : Promise.resolve(report()); },
    export(body, signal) { calls.push({ kind: 'export', body, signal }); return options.exportResult ? options.exportResult(body, signal) : Promise.resolve({ blob: new dom.window.Blob(['xlsx']), filename: 'табель.xlsx' }); },
  };
  const createCalls = [], revokeCalls = [];
  const controller = Reports.mount(document.querySelector('#root'), {
    document, transport, now: () => new Date('2026-09-29T12:00:00Z'),
    createObjectURL(blob) { createCalls.push(blob); return 'blob:test'; },
    revokeObjectURL(url) { revokeCalls.push(url); },
  });
  return { dom, document, controller, calls, createCalls, revokeCalls };
}
const select = (fixture, name) => fixture.document.querySelector(`[data-filter="${name}"]`);
const action = (fixture, name) => fixture.document.querySelector(`[data-action="${name}"]`);

test('loads authorized directory before first preview and sends default calendar dates', async () => {
  const waiting = deferred();
  const fixture = boot({ directoryResult: waiting.promise });
  assert.deepEqual(fixture.calls.map((call) => call.kind), ['directory']);
  waiting.resolve(directory());
  await fixture.controller.ready;
  assert.deepEqual(fixture.calls.map((call) => call.kind), ['directory', 'report']);
  assert.deepEqual(fixture.calls[1].params, { date_from: '2026-09-29', date_to: '2026-09-29', page: 1 });
  assert.equal(select(fixture, 'date-from').value, '2026-09-29');
  assert.equal(select(fixture, 'date-to').value, '2026-09-29');
  fixture.controller.destroy();
});

test('group narrows authorized employees, filters use internal ids, and clear restores defaults', async () => {
  const fixture = boot(); await fixture.controller.ready;
  select(fixture, 'date-from').value = '2026-09-01';
  select(fixture, 'date-to').value = '2026-09-30';
  select(fixture, 'group').value = '10';
  select(fixture, 'group').dispatchEvent(new fixture.dom.window.Event('change'));
  assert.deepEqual(Array.from(select(fixture, 'employee').options, (option) => option.value), ['', '2']);
  select(fixture, 'employee').value = '2';
  action(fixture, 'show').click(); await tick();
  assert.deepEqual(fixture.calls.at(-1).params, { date_from: '2026-09-01', date_to: '2026-09-30', page: 1, group_id: 10, user_id: 2 });
  action(fixture, 'clear').click(); await tick();
  assert.deepEqual(fixture.calls.at(-1).params, { date_from: '2026-09-29', date_to: '2026-09-29', page: 1 });
  assert.equal(select(fixture, 'group').value, '');
  assert.equal(select(fixture, 'employee').value, '');
  fixture.controller.destroy();
});

test('renders only eight safe columns with local clocks and readable durations', async () => {
  const poisoned = { ...row('<img src=x onerror=alert(1)>'), group_timezone: 'Europe/Moscow',
    activity: 'SECRET_ACTIVITY', crm_url: 'https://secret.invalid', calls: 'SECRET_CALL' };
  const fixture = boot({ reportResult: () => Promise.resolve(report([poisoned])) });
  await fixture.controller.ready;
  assert.deepEqual(Array.from(fixture.document.querySelectorAll('thead th'), (node) => node.textContent),
    ['Сотрудник', 'Дата', 'Начало', 'Окончание', 'Перерыв', 'Работа', 'Опоздание', 'Статус']);
  assert.deepEqual(Array.from(fixture.document.querySelectorAll('tbody td'), (node) => node.textContent),
    ['<img src=x onerror=alert(1)>', '29.09.2026', '09:00', '18:00', '1 ч 1 мин', '7 ч 59 мин', '2 мин', 'Завершил']);
  assert.equal(fixture.document.querySelector('tbody img'), null);
  assert.doesNotMatch(fixture.document.body.textContent, /Europe\/Moscow|SECRET|https:\/\/secret|Активность|CRM|Звонки/i);
  fixture.controller.destroy();
});

test('pagination is server driven with ten rows and preserves filters at both boundaries', async () => {
  const fixture = boot({ reportResult: (params) => Promise.resolve(report(
    params.page === 1 ? Array.from({ length: 10 }, (_, index) => row(`Сотрудник ${index}`)) : [row('Последний')],
    { page: params.page, total: 11 })) });
  await fixture.controller.ready;
  assert.equal(fixture.document.querySelectorAll('tbody tr').length, 10);
  assert.equal(action(fixture, 'previous').disabled, true);
  select(fixture, 'group').value = '10'; select(fixture, 'group').dispatchEvent(new fixture.dom.window.Event('change'));
  action(fixture, 'next').click(); await tick();
  assert.equal(fixture.document.querySelectorAll('tbody tr').length, 1);
  assert.deepEqual(fixture.calls.at(-1).params, { date_from: '2026-09-29', date_to: '2026-09-29', page: 2, group_id: 10 });
  assert.equal(action(fixture, 'next').disabled, true);
  action(fixture, 'previous').click(); await tick();
  assert.equal(fixture.calls.at(-1).params.page, 1);
  fixture.controller.destroy();
});

test('loading, empty, generic error, safe Russian error and retry are visible', async () => {
  const waiting = deferred(); let result = waiting.promise;
  const fixture = boot({ reportResult: () => result });
  await tick();
  assert.match(fixture.document.body.textContent, /Загрузка табеля…/);
  waiting.resolve(report([])); await fixture.controller.ready;
  assert.match(fixture.document.body.textContent, /За выбранный период данных нет/);
  result = Promise.reject(new Error('stack detail secret')); await fixture.controller.refresh();
  assert.match(fixture.document.body.textContent, /Не удалось загрузить табель\. Повторите попытку/);
  assert.doesNotMatch(fixture.document.body.textContent, /stack detail secret/);
  result = Promise.reject({ message: '<b>Период недоступен</b>', detail: 'secret' });
  action(fixture, 'retry').click(); await tick();
  assert.match(fixture.document.body.textContent, /<b>Период недоступен<\/b>/);
  assert.equal(fixture.document.querySelector('.ts-reports__message b'), null);
  assert.doesNotMatch(fixture.document.body.textContent, /secret/);
  fixture.controller.destroy();
});

test('employee viewer is denied without preview or export', async () => {
  const fixture = boot({ role: 'employee' }); await fixture.controller.ready;
  assert.match(fixture.document.body.textContent, /У вас нет доступа к этому разделу/);
  assert.deepEqual(fixture.calls.map((call) => call.kind), ['directory']);
  assert.equal(action(fixture, 'export'), null);
  fixture.controller.destroy();
});

test('export sends selected columns and filters, disables repeat, and cleans up download URL', async () => {
  const waiting = deferred();
  const fixture = boot({ exportResult: () => waiting.promise }); await fixture.controller.ready;
  select(fixture, 'group').value = '10'; select(fixture, 'group').dispatchEvent(new fixture.dom.window.Event('change'));
  fixture.document.querySelector('[data-column="start"]').click();
  const anchors = [];
  fixture.document.body.addEventListener('click', (event) => { if (event.target.tagName === 'A') { anchors.push([event.target.download, event.target.href]); event.preventDefault(); } });
  action(fixture, 'export').click();
  assert.equal(action(fixture, 'export').disabled, true);
  assert.deepEqual(fixture.calls.at(-1).body, { date_from: '2026-09-29', date_to: '2026-09-29', group_id: 10,
    columns: ['employee', 'date', 'end', 'break', 'work', 'lateness', 'status'] });
  waiting.resolve({ blob: new fixture.dom.window.Blob(['xlsx']), filename: 'точный.xlsx' }); await tick();
  assert.deepEqual(anchors, [['точный.xlsx', 'blob:test']]);
  assert.equal(fixture.document.querySelector('a[download]'), null);
  assert.deepEqual(fixture.revokeCalls, ['blob:test']);
  assert.equal(action(fixture, 'export').disabled, false);
  fixture.controller.destroy();
});

test('export failure shows safe error and retains at least one selected column', async () => {
  const fixture = boot({ exportResult: () => Promise.reject({ message: 'Экспорт недоступен', detail: 'private' }) });
  await fixture.controller.ready;
  for (const input of fixture.document.querySelectorAll('[data-column]')) input.click();
  assert.equal(fixture.document.querySelectorAll('[data-column]:checked').length, 1);
  action(fixture, 'export').click(); await tick();
  assert.match(fixture.document.body.textContent, /Экспорт недоступен/);
  assert.doesNotMatch(fixture.document.body.textContent, /private/);
  assert.equal(action(fixture, 'export').disabled, false);
  assert.deepEqual(fixture.revokeCalls, []);
  fixture.controller.destroy();
});

test('stale preview cannot replace newer result; destroy aborts work and repeat mount owns one view', async () => {
  const first = deferred(), second = deferred(); let number = 0;
  const fixture = boot({ reportResult: () => (++number === 1 ? first.promise : second.promise) });
  await tick();
  const oldSignal = fixture.calls.at(-1).signal;
  const newest = fixture.controller.refresh();
  assert.equal(oldSignal.aborted, true);
  second.resolve(report([row('Новая')])); await newest;
  first.resolve(report([row('Старая')])); await tick();
  assert.match(fixture.document.body.textContent, /Новая/);
  assert.doesNotMatch(fixture.document.body.textContent, /Старая/);
  fixture.controller.destroy();
  assert.equal(fixture.document.querySelector('.ts-reports'), null);
  const again = Reports.mount(fixture.document.querySelector('#root'), { document: fixture.document,
    transport: { directory: () => Promise.resolve(directory()), report: () => Promise.resolve(report()), export: () => Promise.resolve({}) },
    now: () => new Date('2026-09-29T12:00:00Z') });
  await again.ready;
  assert.equal(fixture.document.querySelectorAll('.ts-reports').length, 1);
  again.destroy();
});

test('controller makes no direct fetch and emits no account, browser user or role headers', async () => {
  const original = global.fetch;
  global.fetch = () => { throw new Error('direct fetch forbidden'); };
  try {
    const fixture = boot(); await fixture.controller.ready;
    fixture.document.body.addEventListener('click', (event) => { if (event.target.tagName === 'A') event.preventDefault(); });
    action(fixture, 'export').click(); await tick();
    assert.deepEqual(fixture.calls.map((call) => call.kind), ['directory', 'report', 'export']);
    assert.deepEqual(Object.keys(fixture.calls[1].params), ['date_from', 'date_to', 'page']);
    assert.deepEqual(Object.keys(fixture.calls[2].body), ['date_from', 'date_to', 'columns']);
    fixture.controller.destroy();
  } finally { global.fetch = original; }
});

test('destroy aborts an active export and prevents a late download', async () => {
  const waiting = deferred();
  const fixture = boot({ exportResult: () => waiting.promise }); await fixture.controller.ready;
  action(fixture, 'export').click();
  const signal = fixture.calls.at(-1).signal;
  fixture.controller.destroy();
  assert.equal(signal.aborted, true);
  waiting.resolve({ blob: new fixture.dom.window.Blob(['xlsx']), filename: 'late.xlsx' }); await tick();
  assert.deepEqual(fixture.createCalls, []);
  assert.equal(fixture.document.querySelector('a[download]'), null);
});

test('the same controller registers through AMD without CommonJS', () => {
  let loaded;
  const define = (dependencies, factory) => { assert.deepEqual(Array.from(dependencies), []); loaded = factory(); };
  define.amd = {};
  runInNewContext(readFileSync(require.resolve('../reports/controller'), 'utf8'), { define });
  assert.equal(typeof loaded.mount, 'function');
});
