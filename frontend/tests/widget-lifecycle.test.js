const test = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { resolve } = require('node:path');
const { JSDOM, ResourceLoader } = require('jsdom');

const settingsSource = readFileSync(resolve(__dirname, '../settings/settings.js'), 'utf8');
const widgetSource = readFileSync(resolve(__dirname, '../../widget/script.js'), 'utf8');
const manifest = JSON.parse(readFileSync(resolve(__dirname, '../../widget/manifest.json'), 'utf8'));
const workingCss = readFileSync(resolve(__dirname, '../../widget/styles.css'));
const monitoringCss = readFileSync(resolve(__dirname, '../monitoring/styles.css'));
const reportsCss = readFileSync(resolve(__dirname, '../reports/styles.css'));
const fixtures = [];
test.afterEach(() => {
  for (const { widget, dom } of fixtures.splice(0)) {
    widget.callbacks.destroy();
    dom.window.close();
  }
});

class WidgetResources extends ResourceLoader {
  fetch(url) {
    if (url.includes('/widgets/timesheet/reports/styles.css')) return Promise.resolve(reportsCss);
    if (url.includes('/widgets/timesheet/monitoring/styles.css')) return Promise.resolve(monitoringCss);
    if (url.includes('/widgets/timesheet/styles.css')) return Promise.resolve(workingCss);
    return null;
  }
}

function snapshot() {
  return {
    revision: 3,
    settings: { support_phone: null, allowed_statuses: ['working', 'break', 'finished'], default_allow_restart_session: false },
    groups: [{ id: 10, account_id: 1, name: 'Продажи', timezone: 'Europe/Minsk', work_start_time: '09:00:00',
      work_end_time: '18:00:00', manager_amocrm_user_id: null, is_active: true, allow_restart_session: false }],
    users: [{ amocrm_user_id: 101, name: 'Анна', email: 'anna@example.test', avatar_url: null,
      amocrm_group_id: 900, amocrm_group_label: 'Группа amoCRM #900', is_active: true,
      track_time: false, hide_widget: false, group_id: null }],
  };
}

function response() {
  return { generated_at: '2026-09-29T09:00:00Z', viewer: { id: 1, role: 'admin', can_view_activity: true },
    groups: [{ id: 10, name: 'Продажи', timezone: 'Europe/Moscow', workday_started_at: '2026-09-29T06:00:00Z',
      workday_ended_at: '2026-09-29T15:00:00Z', employee_count: 1 }],
    employees: [{ id: 2, amocrm_user_id: 102, account_id: 1, name: 'Анна', avatar_url: null, group_id: 10,
      group_name: 'Продажи', timezone: 'Europe/Moscow', workday_started_at: '2026-09-29T06:00:00Z',
      workday_ended_at: '2026-09-29T15:00:00Z', status: 'working', status_since: '2026-09-29T06:00:00Z',
      session_started_at: '2026-09-29T06:00:00Z', session_ended_at: null, work_seconds: 3600, break_seconds: 0,
      confirmed_seconds: 600, confirmed_events: 2, activity_detail_allowed: true }],
    totals: { employees: 1, working: 1, on_break: 0, finished: 0, not_started: 0, work_seconds: 3600,
      break_seconds: 0, confirmed_seconds: 600, confirmed_events: 2 } };
}

function boot(options = {}) {
  const dom = new JSDOM('<!doctype html><html><head></head><body><form id="install-form"></form>' +
    '<div id="list_page_holder"><p id="amo-owned">amoCRM content</p></div><div id="timesheet-overlay"></div></body></html>', {
    url: 'https://account.amocrm.ru', runScripts: 'outside-only', resources: new WidgetResources(), pretendToBeVisual: true,
  });
  const { window } = dom;
  const { document } = window;
  window.console = { log() {}, warn() {}, error() {} };
  window.AMOCRM = { constant: (key) => key === 'account' ? { id: 1 } : { id: 101, name: 'Анна' } };
  window.eval(settingsSource);
  const moduleIds = [];
  let Widget;
  window.define = (ids, factory) => {
    moduleIds.push(...ids);
    Widget = factory(
      {},
      window.SettingsController,
      require('../../widget/timesheet/controller'),
      require('../../widget/overlay'),
      require('../../widget/activity-tracker'),
      require('../monitoring/timeline'),
      require('../monitoring/activity-modal'),
      require('../monitoring/dashboard'),
      options.reportsController || require('../reports/controller'),
    );
  };
  window.eval(widgetSource);
  assert.deepEqual(moduleIds, [
    'jquery', './settings/settings', './timesheet/controller', './overlay', './activity-tracker',
    './monitoring/timeline', './monitoring/activity-modal', './monitoring/dashboard', './reports/controller',
  ]);
  const requests = [];
  const widget = new Widget();
  widget.system = () => ({ area: options.area || 'advanced_settings' });
  widget.get_settings = () => ({ api_url: options.apiUrl === undefined ? 'https://api.example.test/api/v1/' : options.apiUrl,
    path: '/widgets/timesheet/', version: '3.0.2' });
  widget.$authorizedAjax = (request) => {
    requests.push(request);
    if (request.url.includes('/team/status')) return Promise.resolve(options.monitoringStatus || response());
    if (request.url.includes('/team/') && request.url.includes('/activity')) return Promise.resolve(activity());
    if (request.url.includes('/reports/detailed')) return options.reportResponse || Promise.resolve({ items: [], page: 1, total: 0 });
    if (request.url.includes('/reports/export-excel')) return options.exportResponse || Promise.resolve(new Blob(['xlsx']));
    if (request.method === 'GET') return options.load || Promise.resolve(snapshot());
    return options.save || Promise.resolve(snapshot());
  };
  const fixture = { dom, document, widget, requests };
  fixtures.push(fixture);
  return fixture;
}

function activity() {
  return { target: { id: 2, amocrm_user_id: 102, name: 'Анна', avatar_url: null }, group: { id: 10, name: 'Продажи' },
    timezone: 'Europe/Moscow', from: '2026-09-23', to: '2026-09-29',
    totals: { confirmed_seconds: 0, confirmed_events: 0, unconfirmed_seconds: 0 }, days: [] };
}

test('working init without API URL remains fail-open and keeps settings editor out', () => {
  const { document, widget, requests } = boot({ apiUrl: null, area: 'lcard' });
  widget.callbacks.init();
  assert.equal(document.querySelector('.timesheet-overlay'), null);
  assert.equal(document.querySelector('.timesheet-settings'), null);
  assert.equal(requests.length, 0);
});

test('init in settings area does not start working overlay', () => {
  for (const area of ['settings', 'advanced_settings']) {
    const { document, widget, requests } = boot({ area });
    widget.callbacks.init();
    assert.equal(widget.overlayCreated, undefined);
    assert.equal(document.querySelector('.timesheet-settings'), null);
    assert.equal(requests.length, 0);
  }
});

test('manifest enables working locations', () => {
  assert.deepEqual(manifest.locations, ['settings', 'advanced_settings', 'everywhere']);
});

test('settings script registers an AMD module for the widget dependency', () => {
  const dom = new JSDOM('<!doctype html>', { runScripts: 'outside-only' });
  let exported;
  dom.window.define = (factory) => { exported = factory(); };
  dom.window.define.amd = {};
  dom.window.eval(settingsSource);
  assert.equal(typeof exported.mount, 'function');
});

test('settings callback leaves native install form and advancedSettings owns only its child', async () => {
  const { document, widget, requests } = boot();
  const form = document.querySelector('#install-form');
  widget.callbacks.settings();
  assert.equal(document.querySelector('#install-form'), form);
  assert.equal(requests.length, 0);
  widget.callbacks.advancedSettings();
  await widget.settingsController.ready;
  assert.equal(document.querySelectorAll('[role=tab]').length, 2);
  assert.equal(document.querySelectorAll('.timesheet-settings__save').length, 0);
  assert.ok(document.querySelector('#list_page_holder .timesheet-settings'));
  assert.ok(document.querySelector('link[href="/widgets/timesheet/settings/settings.css?v=3.0.2"]'));
  assert.ok(document.querySelector('#amo-owned'));
  assert.equal(requests[0].method, 'GET');
  assert.equal(requests[0].url, 'https://api.example.test/api/v1/settings/snapshot');
  assert.equal('headers' in requests[0], false);
});

test('amoCRM onSave is the only editor save action and adopts the canonical response', async () => {
  let finishSave;
  const pending = new Promise((resolve) => { finishSave = resolve; });
  const { document, widget, requests } = boot({ save: pending });
  widget.callbacks.advancedSettings();
  await widget.settingsController.ready;
  const phone = document.querySelector('[data-field="support_phone"]');
  phone.value = '+375 29 000-00-00';
  phone.dispatchEvent(new document.defaultView.Event('input', { bubbles: true }));
  const track = document.querySelector('[data-user-id="101"] [data-field="track_time"]');
  track.checked = true;
  track.dispatchEvent(new document.defaultView.Event('change', { bubbles: true }));
  const group = document.querySelector('[data-user-id="101"] [data-field="group_ref"]');
  group.value = 'id:10';
  group.dispatchEvent(new document.defaultView.Event('change', { bubbles: true }));
  assert.equal(document.querySelector('.timesheet-settings__save'), null);
  const callbackSave = widget.callbacks.onSave();
  assert.equal(requests.length, 2);
  assert.equal(requests[1].method, 'PUT');
  assert.equal(requests[1].contentType, 'application/json');
  assert.equal(requests[1].dataType, 'json');
  assert.equal('headers' in requests[1], false);
  const payload = JSON.parse(requests[1].data);
  assert.equal(payload.settings.support_phone, '+375 29 000-00-00');
  assert.deepEqual(payload.users[0], { amocrm_user_id: 101, track_time: true, hide_widget: false, group_ref: 'id:10' });
  assert.deepEqual(Object.keys(payload), ['revision', 'settings', 'groups', 'users']);
  const canonical = snapshot();
  canonical.revision = 4;
  canonical.settings.support_phone = '+375 29 000-00-00';
  finishSave(canonical);
  await callbackSave;
  assert.equal(widget.settingsController.serialize().revision, 4);
});

test('destroy removes settings without deleting amoCRM-owned DOM', async () => {
  const { document, widget } = boot();
  widget.callbacks.advancedSettings();
  await widget.settingsController.ready;
  widget.callbacks.destroy();
  assert.equal(document.querySelector('.timesheet-settings'), null);
  assert.equal(document.querySelector('link[href="/widgets/timesheet/settings/settings.css?v=3.0.2"]'), null);
  assert.ok(document.querySelector('#amo-owned'));
  assert.ok(document.querySelector('#timesheet-overlay'));
});

test('working init uses authorized timesheet API without browser identity and refreshes on focus', async () => {
  const { dom, document, widget, requests } = boot({ area: 'lcard', load: Promise.resolve({
    session_id: 7, status: 'on_break', started_at: '2026-09-22T08:00:00Z', ended_at: null,
    break_seconds: 60, track_time: true, hide_widget: false, restart_allowed: false,
  }) });
  widget.callbacks.init();
  await new Promise(setImmediate);
  const timesheetRequest = requests.find((request) => request.url.endsWith('/timesheet/my-status'));
  assert.equal(timesheetRequest.url, 'https://api.example.test/api/v1/timesheet/my-status');
  assert.equal(timesheetRequest.method, 'GET');
  assert.equal('data' in timesheetRequest, false);
  assert.equal(document.querySelectorAll('.timesheet-overlay').length, 1);
  dom.window.dispatchEvent(new dom.window.Event('focus'));
  await new Promise(setImmediate);
  assert.equal(requests.filter((request) => request.url.endsWith('/timesheet/my-status')).length, 2);
});

test('working init mounts one monitoring launcher and uses authorized team APIs without identity headers', async () => {
  const { document, widget, requests } = boot({ area: 'lcard' });
  widget.callbacks.init();
  await new Promise(setImmediate);
  assert.equal(document.querySelectorAll('.ts-monitoring-widget').length, 1);
  assert.equal(document.querySelectorAll('.ts-monitoring-widget__launcher').length, 1);
  const statusRequest = requests.find((request) => request.url.includes('/team/status'));
  assert.equal(statusRequest.method, 'GET');
  assert.equal(statusRequest.dataType, 'json');
  assert.equal('headers' in statusRequest, false);
  assert.equal('beforeSend' in statusRequest, false);
  widget.callbacks.destroy();
  assert.equal(document.querySelector('.ts-monitoring-widget'), null);
  assert.equal(document.querySelector('link[href*="monitoring/styles.css"]'), null);
});

test('repeated working init replaces monitoring DOM and does not duplicate launchers', async () => {
  const { document, widget } = boot({ area: 'lcard' });
  widget.callbacks.init(); await new Promise(setImmediate);
  widget.callbacks.init(); await new Promise(setImmediate);
  assert.equal(document.querySelectorAll('.ts-monitoring-widget').length, 1);
  assert.equal(document.querySelectorAll('link[href*="monitoring/styles.css"]').length, 1);
});

test('report launcher appears only after admin preflight, reuses directory and is owned across init and destroy', async () => {
  const { document, widget, requests } = boot({ area: 'lcard' });
  widget.callbacks.init();
  assert.equal(document.querySelector('.ts-reports-widget'), null);
  await new Promise(setImmediate);
  assert.equal(document.querySelectorAll('.ts-reports-widget__launcher').length, 1);
  assert.equal(document.querySelector('.ts-reports-widget__launcher').textContent, 'Табель');
  assert.equal(document.querySelector('.ts-reports-widget__launcher').getAttribute('aria-expanded'), 'false');
  assert.equal(requests.filter((request) => request.url.endsWith('/team/status')).length, 2);
  assert.equal(requests.filter((request) => request.url.endsWith('/reports/detailed')).length, 1);
  assert.ok(document.querySelector('link[href="/widgets/timesheet/reports/styles.css?v=3.0.2"]'));
  widget.callbacks.init(); await new Promise(setImmediate);
  assert.equal(document.querySelectorAll('.ts-reports-widget').length, 1);
  widget.callbacks.destroy();
  assert.equal(document.querySelector('.ts-reports-widget'), null);
  assert.equal(document.querySelector('link[href*="reports/styles.css"]'), null);
  assert.ok(document.querySelector('#amo-owned'));
});

test('employee and stale preflight responses never create report DOM', async () => {
  const employee = response(); employee.viewer.role = 'employee';
  const employeeFixture = boot({ area: 'lcard', monitoringStatus: employee });
  employeeFixture.widget.callbacks.init(); await new Promise(setImmediate);
  assert.equal(employeeFixture.document.querySelector('.ts-reports-widget'), null);
  assert.equal(employeeFixture.document.querySelector('link[href*="reports/styles.css"]'), null);
  let finishStatus;
  const pending = new Promise((resolve) => { finishStatus = resolve; });
  const stale = boot({ area: 'lcard', monitoringStatus: pending });
  stale.widget.callbacks.init(); await new Promise(setImmediate);
  stale.widget.callbacks.destroy();
  finishStatus(response()); await new Promise(setImmediate);
  assert.equal(stale.document.querySelector('.ts-reports-widget'), null);
  assert.equal(stale.document.querySelector('link[href*="reports/styles.css"]'), null);
});

test('report mount failure removes its shell without interrupting timesheet UI', async () => {
  const { document, widget } = boot({ area: 'lcard',
    load: Promise.resolve({ session_id: 7, status: 'on_break', started_at: '2026-09-22T08:00:00Z', ended_at: null,
      break_seconds: 60, track_time: true, hide_widget: false, restart_allowed: false }),
    reportsController: { mount() { throw new Error('broken report'); } } });
  widget.callbacks.init(); await new Promise(setImmediate);
  assert.equal(document.querySelector('.ts-reports-widget'), null);
  assert.equal(document.querySelector('link[href*="reports/styles.css"]'), null);
  assert.equal(document.querySelectorAll('.timesheet-overlay').length, 1);
  assert.equal(document.querySelectorAll('.ts-monitoring-widget').length, 1);
});

test('report preview and Excel use authorized transport, safe filename and public errors', async () => {
  const { dom, document, widget, requests } = boot({ area: 'lcard' });
  let downloaded;
  dom.window.HTMLAnchorElement.prototype.click = function() { downloaded = this.download; };
  const original = widget.$authorizedAjax;
  widget.$authorizedAjax = (options) => {
    if (options.url.endsWith('/reports/export-excel')) {
      requests.push(options);
      return Object.assign(Promise.resolve(new Blob(['xlsx'])), {
        getResponseHeader: () => 'attachment; filename="../../evil.xlsx"', abort() {},
      });
    }
    return original(options);
  };
  widget.callbacks.init(); await new Promise(setImmediate);
  const preview = requests.find((request) => request.url.endsWith('/reports/detailed'));
  assert.equal(preview.method, 'GET'); assert.equal(preview.dataType, 'json');
  assert.equal(preview.data.page, 1);
  assert.equal('headers' in preview, false);
  const from = document.querySelector('.ts-reports__date-from');
  const to = document.querySelector('.ts-reports__date-to');
  from.value = '2026-09-01'; to.value = '2026-09-30';
  document.querySelector('.ts-reports__export').click(); await new Promise(setImmediate);
  const request = requests.find((item) => item.url.endsWith('/reports/export-excel'));
  assert.equal(request.method, 'POST');
  assert.equal(request.contentType, 'application/json');
  assert.equal(request.xhrFields.responseType, 'blob');
  assert.deepEqual(JSON.parse(request.data).columns, ['employee', 'date', 'start', 'end', 'break', 'work', 'lateness', 'status']);
  assert.equal('headers' in request, false);
  assert.equal(downloaded, 'timesheet_2026-09-01_2026-09-30.xlsx');
});

test('valid disposition filename is used and report errors expose only bounded backend messages', async () => {
  const { dom, document, widget, requests } = boot({ area: 'lcard' });
  let downloaded;
  dom.window.HTMLAnchorElement.prototype.click = function() { downloaded = this.download; };
  const original = widget.$authorizedAjax;
  widget.$authorizedAjax = (request) => {
    if (request.url.endsWith('/reports/export-excel')) {
      requests.push(request);
      return Object.assign(Promise.resolve(new Blob(['xlsx'])), {
        getResponseHeader: () => 'attachment; filename="timesheet_2026-09-03_2026-09-29.xlsx"', abort() {},
      });
    }
    if (request.url.endsWith('/reports/detailed')) {
      requests.push(request);
      return Promise.reject({ message: 'private token', responseText: 'private stack',
        responseJSON: { error: { message: 'Публичная ошибка' } } });
    }
    return original(request);
  };
  widget.callbacks.init(); await new Promise(setImmediate);
  assert.match(document.querySelector('.ts-reports__message').textContent, /Публичная ошибка/);
  assert.doesNotMatch(document.querySelector('.ts-reports-widget').textContent, /private token|private stack/);
  document.querySelector('.ts-reports__export').click(); await new Promise(setImmediate);
  assert.equal(downloaded, 'timesheet_2026-09-03_2026-09-29.xlsx');
});

test('destroy aborts report role and export jqXHR without late report DOM or download', async () => {
  const preflight = boot({ area: 'lcard' });
  let statusCalls = 0;
  let roleAborted = false;
  let resolveRole;
  preflight.widget.$authorizedAjax = (request) => {
    if (request.url.endsWith('/team/status')) {
      ++statusCalls;
      const pending = new Promise((resolve) => { if (statusCalls === 2) resolveRole = resolve; });
      return Object.assign(pending, { abort() { if (statusCalls === 2) roleAborted = true; } });
    }
    return Promise.resolve({});
  };
  preflight.widget.callbacks.init(); await new Promise(setImmediate);
  preflight.widget.callbacks.destroy();
  assert.equal(roleAborted, true);
  resolveRole(response()); await new Promise(setImmediate);
  assert.equal(preflight.document.querySelector('.ts-reports-widget'), null);

  const exporting = boot({ area: 'lcard' });
  let exportAborted = false;
  let resolveExport;
  let downloaded = false;
  exporting.dom.window.HTMLAnchorElement.prototype.click = function() { downloaded = true; };
  const original = exporting.widget.$authorizedAjax;
  exporting.widget.$authorizedAjax = (request) => request.url.endsWith('/reports/export-excel')
    ? Object.assign(new Promise((resolve) => { resolveExport = resolve; }), { abort() { exportAborted = true; } })
    : original(request);
  exporting.widget.callbacks.init(); await new Promise(setImmediate);
  exporting.document.querySelector('.ts-reports__export').click();
  exporting.widget.callbacks.destroy();
  assert.equal(exportAborted, true);
  resolveExport(new Blob(['late'])); await new Promise(setImmediate);
  assert.equal(downloaded, false);
});

test('repeated working init replaces its controller and focus refresh listener', async () => {
  const { dom, widget, requests } = boot({ area: 'lcard', load: Promise.resolve({
    session_id: 7, status: 'working', started_at: '2026-09-22T08:00:00Z', ended_at: null,
    break_seconds: 0, track_time: true, hide_widget: false, restart_allowed: false,
  }) });
  widget.callbacks.init();
  await new Promise(setImmediate);
  widget.callbacks.init();
  await new Promise(setImmediate);
  dom.window.dispatchEvent(new dom.window.Event('focus'));
  await new Promise(setImmediate);
  assert.equal(requests.filter((request) => request.url.endsWith('/timesheet/my-status')).length, 3);
});

test('API outage after a visible break removes its overlay and work buttons', async () => {
  let outage = false;
  const { dom, document, widget } = boot({ area: 'lcard' });
  widget.$authorizedAjax = () => outage ? Promise.reject(new Error('offline')) : Promise.resolve({
    session_id: 7, status: 'on_break', started_at: '2026-09-22T08:00:00Z', ended_at: null,
    break_seconds: 60, track_time: true, hide_widget: false, restart_allowed: false,
  });
  widget.callbacks.init();
  await new Promise(setImmediate);
  assert.equal(document.querySelectorAll('.timesheet-overlay').length, 1);
  outage = true;
  dom.window.dispatchEvent(new dom.window.Event('focus'));
  await new Promise(setImmediate);
  assert.equal(document.querySelectorAll('.timesheet-overlay, .timesheet-action').length, 0);
  widget.callbacks.destroy();
});

test('missing API URL shows a safe state without issuing a request', () => {
  const { document, widget, requests } = boot({ apiUrl: null });
  widget.callbacks.advancedSettings();
  assert.match(document.querySelector('#list_page_holder').textContent, /URL API/i);
  assert.equal(requests.length, 0);
});

test('authorizedAjax jqXHR Retry-After reaches the editor without losing its draft', async () => {
  const { document, widget, requests } = boot({ save: {
    then(_resolve, reject) {
      reject({ status: 429, getResponseHeader: (name) => name === 'Retry-After' ? '30' : null });
    },
  } });
  widget.callbacks.advancedSettings();
  await widget.settingsController.ready;
  widget.settingsController.setSupportPhone('draft');
  await assert.rejects(widget.callbacks.onSave());
  assert.equal(requests.length, 2);
  assert.equal(widget.settingsController.serialize().settings.support_phone, 'draft');
  assert.match(document.querySelector('.timesheet-settings').textContent, /30 секунд/);
});

test('reopening advanced settings replaces only the prior owned editor', async () => {
  const { document, widget, requests } = boot();
  widget.callbacks.advancedSettings();
  await widget.settingsController.ready;
  const original = widget.settingsController;
  widget.callbacks.advancedSettings();
  await widget.settingsController.ready;
  assert.equal(original.destroyed, true);
  assert.equal(document.querySelectorAll('.timesheet-settings').length, 1);
  assert.equal(document.querySelectorAll('link[href*="settings/settings.css"]').length, 1);
  assert.equal(requests.filter((request) => request.method === 'GET').length, 2);
  assert.ok(document.querySelector('#amo-owned'));
});

test('onSave waits for an in-progress settings load before saving', async () => {
  let finishLoad;
  const load = new Promise((resolve) => { finishLoad = resolve; });
  const { widget, requests } = boot({ load });
  widget.callbacks.advancedSettings();
  const saving = widget.callbacks.onSave();
  assert.equal(requests.length, 1);
  finishLoad(snapshot());
  await saving;
  assert.deepEqual(requests.map((request) => request.method), ['GET', 'PUT']);
});
