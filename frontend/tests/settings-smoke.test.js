const test = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { resolve } = require('node:path');
const { JSDOM } = require('jsdom');

const controllerSource = readFileSync(resolve(__dirname, '../settings/settings.js'), 'utf8');
const widgetSource = readFileSync(resolve(__dirname, '../../widget/script.js'), 'utf8');

function snapshot(revision = 3) {
  return {
    revision,
    settings: { support_phone: null, allowed_statuses: ['working', 'break', 'finished'], default_allow_restart_session: false },
    groups: [],
    users: [{ amocrm_user_id: 101, name: 'Anna', email: 'anna@example.test', avatar_url: null,
      amocrm_group_id: 900, amocrm_group_label: 'Sales', is_active: true,
      track_time: false, hide_widget: false, group_id: null }],
  };
}

test('advanced settings smoke saves a canonical snapshot without rendering in working area', async () => {
  const dom = new JSDOM('<!doctype html><html><head></head><body><div id="list_page_holder"></div></body></html>', {
    url: 'https://account.amocrm.ru', runScripts: 'outside-only',
  });
  const { window } = dom;
  const { document } = window;
  window.console = { log() {}, warn() {}, error() {} };
  window.AMOCRM = { constant: () => ({ id: 101, name: 'Anna' }) };
  window.eval(controllerSource);
  let Widget;
  window.define = (_ids, factory) => { Widget = factory({}, window.SettingsController); };
  window.eval(widgetSource);
  const requests = [];
  const widget = new Widget();
  widget.system = () => ({ area: 'advanced_settings' });
  widget.get_settings = () => ({ api_url: 'https://api.example.test/api/v1', path: '/widgets/timesheet/', version: '3.0.2' });
  widget.removeOverlay = () => {};
  widget.$authorizedAjax = (request) => {
    requests.push(request);
    if (request.method === 'GET') return Promise.resolve(snapshot());
    const payload = JSON.parse(request.data);
    assert.equal(payload.revision, 3);
    assert.equal(payload.users[0].track_time, true);
    assert.equal(payload.users[0].hide_widget, false);
    assert.match(payload.users[0].group_ref, /^client:group_\d+$/);
    assert.deepEqual(payload.groups.map(({ name, timezone }) => ({ name, timezone })),
      [{ name: 'Sales', timezone: 'Europe/Minsk' }]);
    assert.equal(payload.users[0].group_ref, 'client:' + payload.groups[0].client_key);
    const canonical = snapshot(4);
    canonical.groups = [{ ...payload.groups[0], id: 20, account_id: 1 }];
    canonical.users[0] = { ...canonical.users[0], track_time: true, group_id: 20 };
    return Promise.resolve(canonical);
  };
  widget.callbacks.advancedSettings();
  await widget.settingsController.ready;
  assert.deepEqual([...document.querySelectorAll('[role=tab]')].map((tab) => tab.textContent), ['Пользователи', 'Настройки']);
  assert.equal(document.querySelectorAll('.timesheet-settings__save').length, 1);
  document.querySelector('[role=tab]:last-child').click();
  document.querySelector('.timesheet-settings__add-group').click();
  const newGroup = document.querySelector('[data-group-ref^="client:"]');
  const name = newGroup.querySelector('[data-field="name"]');
  name.value = 'Sales';
  name.dispatchEvent(new window.Event('input', { bubbles: true }));
  widget.settingsController.setUser(101, { track_time: true, group_ref: newGroup.getAttribute('data-group-ref') });
  document.querySelector('.timesheet-settings__save').click();
  await widget.settingsController.save();
  assert.deepEqual(requests.map((request) => request.method), ['GET', 'PUT']);
  assert.equal(widget.settingsController.serialize().revision, 4);
  assert.equal(widget.settingsController.serialize().users[0].group_ref, 'id:20');
  widget.callbacks.destroy();
  assert.equal(document.querySelector('.timesheet-settings'), null);
  widget.system = () => ({ area: 'lcard' });
  widget.get_settings = () => ({ api_url: null });
  widget.createOverlay = () => {};
  widget.updateOverlayState = () => {};
  widget.startUpdateTimer = () => {};
  widget.callbacks.init();
  assert.equal(document.querySelector('.timesheet-settings'), null);
});
