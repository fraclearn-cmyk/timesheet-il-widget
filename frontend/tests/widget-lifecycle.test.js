const test = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { resolve } = require('node:path');
const { JSDOM } = require('jsdom');

const settingsSource = readFileSync(resolve(__dirname, '../settings/settings.js'), 'utf8');
const widgetSource = readFileSync(resolve(__dirname, '../../widget/script.js'), 'utf8');
const manifest = JSON.parse(readFileSync(resolve(__dirname, '../../widget/manifest.json'), 'utf8'));

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

function boot(options = {}) {
  const dom = new JSDOM('<!doctype html><html><head></head><body><form id="install-form"></form>' +
    '<div id="list_page_holder"><p id="amo-owned">amoCRM content</p></div><div id="timesheet-overlay"></div></body></html>', {
    url: 'https://account.amocrm.ru', runScripts: 'outside-only',
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
    Widget = factory({ ajax() { throw new Error('working AJAX not expected'); } }, window.SettingsController);
  };
  window.eval(widgetSource);
  assert.deepEqual(moduleIds, ['jquery', './settings/settings']);
  const requests = [];
  const widget = new Widget();
  widget.system = () => ({ area: options.area || 'advanced_settings' });
  widget.get_settings = () => ({ api_url: options.apiUrl === undefined ? 'https://api.example.test/api/v1/' : options.apiUrl,
    path: '/widgets/timesheet/', version: '3.0.2' });
  widget.$authorizedAjax = (request) => {
    requests.push(request);
    if (request.method === 'GET') return options.load || Promise.resolve(snapshot());
    return options.save || Promise.resolve(snapshot());
  };
  widget.createOverlay = () => { widget.overlayCreated = true; };
  widget.updateOverlayState = () => {};
  widget.startUpdateTimer = () => {};
  widget.removeOverlay = () => { document.querySelector('#timesheet-overlay')?.remove(); };
  return { dom, document, widget, requests };
}

test('init keeps settings editor out of working area', () => {
  const { document, widget, requests } = boot({ apiUrl: null, area: 'lcard' });
  widget.callbacks.init();
  assert.equal(widget.overlayCreated, true);
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

test('manifest declares only settings locations while working init remains unexposed', () => {
  assert.deepEqual(manifest.locations, ['settings', 'advanced_settings']);
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
  assert.equal(document.querySelectorAll('.button-input_blue.timesheet-settings__save').length, 1);
  assert.ok(document.querySelector('#list_page_holder .timesheet-settings'));
  assert.ok(document.querySelector('link[href="/widgets/timesheet/settings/settings.css?v=3.0.2"]'));
  assert.ok(document.querySelector('#amo-owned'));
  assert.equal(requests[0].method, 'GET');
  assert.equal(requests[0].url, 'https://api.example.test/api/v1/settings/snapshot');
  assert.equal('headers' in requests[0], false);
});

test('in-panel button and onSave share one authorized PUT and adopt canonical response', async () => {
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
  document.querySelector('.timesheet-settings__save').click();
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

test('destroy removes settings only and leaves amoCRM content and working overlay owner intact', async () => {
  const { document, widget } = boot();
  widget.callbacks.advancedSettings();
  await widget.settingsController.ready;
  widget.callbacks.destroy();
  assert.equal(document.querySelector('.timesheet-settings'), null);
  assert.equal(document.querySelector('link[href="/widgets/timesheet/settings/settings.css?v=3.0.2"]'), null);
  assert.ok(document.querySelector('#amo-owned'));
  assert.equal(document.querySelector('#timesheet-overlay'), null);
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
