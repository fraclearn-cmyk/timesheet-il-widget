const test = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { resolve } = require('node:path');
const { JSDOM } = require('jsdom');

const scriptPath = resolve(__dirname, '../settings/settings.js');

function snapshot() {
  return {
    revision: 3,
    settings: {
      support_phone: null,
      allowed_statuses: ['working', 'break', 'finished'],
      default_allow_restart_session: false,
    },
    groups: [{
      id: 10, account_id: 1, name: 'Продажи', timezone: 'Europe/Minsk',
      work_start_time: '09:00:00', work_end_time: '18:00:00',
      manager_amocrm_user_id: 102, is_active: true, allow_restart_session: false,
    }],
    users: [{
      amocrm_user_id: 101, name: 'Анна', email: 'anna@example.test', avatar_url: null,
      amocrm_group_id: 900, amocrm_group_label: 'Отдел A', is_active: true,
      track_time: false, hide_widget: false, group_id: null,
    }, {
      amocrm_user_id: 102, name: 'Борис', email: 'boris@example.test', avatar_url: null,
      amocrm_group_id: 901, amocrm_group_label: 'Отдел B', is_active: true,
      track_time: true, hide_widget: false, group_id: 10,
    }],
  };
}

function setup(data = snapshot(), transport = {}) {
  const dom = new JSDOM('<!doctype html><div id="list_page_holder"></div>', {
    url: 'https://example.test', runScripts: 'outside-only',
  });
  const { document } = dom.window;
  const root = document.querySelector('#list_page_holder');
  const source = readFileSync(scriptPath, 'utf8');
  dom.window.eval(source);
  const saves = [];
  const controller = dom.window.SettingsController.mount(root, {
    load: transport.load || (() => Promise.resolve(data)),
    save: transport.save || ((payload) => { saves.push(payload); return Promise.resolve(data); }),
  });
  return { dom, root, controller, saves };
}

test('mount renders exactly two tabs, no embedded save action, and treats server strings as text', async () => {
  const data = snapshot();
  data.users[0].name = '<img src=x onerror=alert(1)>';
  data.groups[0].name = '<script>alert(1)</script>';
  const { root, controller } = setup(data);
  await controller.ready;
  assert.deepEqual([...root.querySelectorAll('[role=tab]')].map((node) => node.textContent), ['Пользователи', 'Настройки']);
  assert.equal(root.querySelector('img, script'), null);
  assert.match(root.textContent, /<img src=x/);
  assert.match(root.textContent, /<script>alert/);
  assert.equal(root.querySelectorAll('.timesheet-settings__save').length, 0);
});

test('hide_widget does not change track_time and serializes all visible users', async () => {
  const { controller } = setup();
  await controller.ready;
  controller.setUser(101, { track_time: true, group_ref: 'id:10' });
  controller.setUser(101, { hide_widget: true });
  assert.deepEqual(JSON.parse(JSON.stringify(controller.serialize().users)), [{
    amocrm_user_id: 101, track_time: true, hide_widget: true, group_ref: 'id:10',
  }, {
    amocrm_user_id: 102, track_time: true, hide_widget: false, group_ref: 'id:10',
  }]);
});

test('tab switch exposes one panel at a time', async () => {
  const { root, controller } = setup();
  await controller.ready;
  const tabs = [...root.querySelectorAll('[role=tab]')];
  const panels = [...root.querySelectorAll('[role=tabpanel]')];
  assert.deepEqual(panels.map((panel) => panel.hidden), [false, true]);
  tabs[1].click();
  assert.deepEqual(panels.map((panel) => panel.hidden), [true, false]);
  assert.deepEqual(tabs.map((tab) => tab.getAttribute('aria-selected')), ['false', 'true']);
});

test('search normalizes name and email and preserves all users in payload', async () => {
  const { root, controller } = setup();
  await controller.ready;
  const search = root.querySelector('[data-field="search"]');
  search.value = '  BORIS@EXAMPLE.TEST  ';
  search.dispatchEvent(new root.ownerDocument.defaultView.Event('input', { bubbles: true }));
  assert.deepEqual([...root.querySelectorAll('[data-user-id]')].map((row) => row.textContent.includes('Борис')), [true]);
  assert.equal(controller.serialize().users.length, 2);
  assert.deepEqual([...root.querySelectorAll('[data-amocrm-group] h3')].map((heading) => heading.textContent), ['Отдел B']);
});

test('inactive historical user remains visible and read-only', async () => {
  const data = snapshot();
  data.users[1].is_active = false;
  const { root, controller } = setup(data);
  await controller.ready;
  const row = root.querySelector('[data-user-id="102"]');
  assert.ok(row);
  assert.equal(row.querySelector('[data-field="track_time"]').disabled, true);
  assert.equal(row.querySelector('[data-field="hide_widget"]').disabled, true);
  assert.equal(row.querySelector('[data-field="group_ref"]').disabled, true);
  assert.throws(() => controller.setUser(102, { hide_widget: true }), /inactive/i);
  assert.deepEqual(JSON.parse(JSON.stringify(controller.serialize().users[1])), {
    amocrm_user_id: 102, track_time: true, hide_widget: false, group_ref: 'id:10',
  });
});

test('tracked user needs an active accounting group', async () => {
  const { controller } = setup();
  await controller.ready;
  controller.setUser(101, { track_time: true });
  assert.deepEqual(JSON.parse(JSON.stringify(controller.validate())), [{
    code: 'TRACKED_USER_GROUP_REQUIRED', field: 'users.0.group_ref',
  }]);
  controller.setUser(101, { group_ref: 'id:10' });
  assert.equal(controller.validate().length, 0);
});

test('user controls keep track_time and hide_widget independent', async () => {
  const { root, controller } = setup();
  await controller.ready;
  const row = root.querySelector('[data-user-id="101"]');
  const hide = row.querySelector('[data-field="hide_widget"]');
  hide.checked = true;
  hide.dispatchEvent(new root.ownerDocument.defaultView.Event('change', { bubbles: true }));
  assert.equal(controller.serialize().users[0].hide_widget, true);
  assert.equal(controller.serialize().users[0].track_time, false);
});

test('settings and group controls serialize exact backend fields', async () => {
  const { root, controller } = setup();
  await controller.ready;
  root.querySelectorAll('[role=tab]')[1].click();
  const phone = root.querySelector('[data-field="support_phone"]');
  phone.value = '+375 29 000-00-00';
  phone.dispatchEvent(new root.ownerDocument.defaultView.Event('input', { bubbles: true }));
  const name = root.querySelector('[data-group-ref="id:10"] [data-field="name"]');
  name.value = 'Новая группа';
  name.dispatchEvent(new root.ownerDocument.defaultView.Event('input', { bubbles: true }));
  const payload = JSON.parse(JSON.stringify(controller.serialize()));
  assert.equal(payload.revision, 3);
  assert.equal(payload.settings.support_phone, '+375 29 000-00-00');
  assert.deepEqual(payload.groups[0], {
    id: 10, name: 'Новая группа', timezone: 'Europe/Minsk',
    work_start_time: '09:00:00', work_end_time: '18:00:00',
    manager_amocrm_user_id: 102, is_active: true, allow_restart_session: false,
  });
  assert.equal('account_id' in payload, false);
});

test('new group gets client reference and can be assigned before save', async () => {
  const { root, controller } = setup();
  await controller.ready;
  root.querySelectorAll('[role=tab]')[1].click();
  root.querySelector('.timesheet-settings__add-group').click();
  const group = root.querySelector('[data-group-ref^="client:"]');
  assert.ok(group);
  const ref = group.getAttribute('data-group-ref');
  assert.match(ref, /^client:[A-Za-z0-9_-]+$/);
  assert.equal(controller.serialize().groups[1].client_key, ref.slice(7));
  controller.setUser(101, { track_time: true, group_ref: ref });
  assert.equal(controller.serialize().users[0].group_ref, ref);
});

test('save sends complete snapshot and adopts canonical response', async () => {
  const data = snapshot();
  const canonical = snapshot();
  canonical.revision = 4;
  canonical.users[0].hide_widget = true;
  const { controller, saves } = setup(data, { save: async (payload) => { saves.push(payload); return canonical; } });
  await controller.ready;
  controller.setUser(101, { hide_widget: true });
  await controller.save();
  assert.equal(saves.length, 1);
  assert.equal(saves[0].users.length, 2);
  assert.equal(controller.serialize().revision, 4);
  assert.equal(controller.serialize().users[0].hide_widget, true);
});

test('failed save keeps draft and displays field error', async () => {
  const { root, controller } = setup(snapshot(), {
    save: async () => { throw { status: 409, error: { code: 'GROUP_DUPLICATE', field: 'groups.0.name', message: 'Повтор' } }; },
  });
  await controller.ready;
  root.querySelectorAll('[role=tab]')[1].click();
  const name = root.querySelector('[data-group-ref="id:10"] [data-field="name"]');
  name.value = 'Копия';
  name.dispatchEvent(new root.ownerDocument.defaultView.Event('input', { bubbles: true }));
  await assert.rejects(controller.save());
  assert.equal(controller.serialize().groups[0].name, 'Копия');
  assert.equal(root.querySelector('[data-group-ref="id:10"] [data-field="name"]').getAttribute('aria-invalid'), 'true');
  assert.match(root.textContent, /Проверьте отмеченные поля/);
});

test('loading rejection shows denied state and no editable form', async () => {
  const { root, controller } = setup(snapshot(), { load: async () => { throw { status: 403 }; } });
  await assert.rejects(controller.ready);
  assert.match(root.textContent, /нет доступа/i);
  assert.equal(root.querySelector('[data-field="support_phone"]'), null);
});

test('destroy removes owned UI and ignores late loading response', async () => {
  let resolveLoad;
  const { root, controller } = setup(snapshot(), {
    load: () => new Promise((resolve) => { resolveLoad = resolve; }),
  });
  controller.destroy();
  resolveLoad(snapshot());
  await controller.ready;
  assert.equal(root.querySelector('.timesheet-settings'), null);
});

test('HTML mounting template has two tabs and no embedded save action', () => {
  const html = readFileSync(resolve(__dirname, '../settings/settings.html'), 'utf8');
  const dom = new JSDOM(html);
  const root = dom.window.document.querySelector('.timesheet-settings');
  assert.ok(root);
  assert.deepEqual([...root.querySelectorAll('[role=tab]')].map((tab) => tab.textContent.trim()), ['Пользователи', 'Настройки']);
  assert.equal(root.querySelectorAll('.timesheet-settings__save').length, 0);
});

test('rate limit leaves draft in place and bounds retry message', async () => {
  const { root, controller } = setup(snapshot(), {
    save: async () => { throw { status: 429, retryAfter: '30' }; },
  });
  await controller.ready;
  const phone = root.querySelector('[data-field="support_phone"]');
  phone.value = '+375 29 000-00-00';
  phone.dispatchEvent(new root.ownerDocument.defaultView.Event('input', { bubbles: true }));
  await assert.rejects(controller.save());
  assert.equal(controller.serialize().settings.support_phone, '+375 29 000-00-00');
  assert.match(root.textContent, /30 секунд/);
});

test('save error statuses show safe Russian messages without replacing draft', async () => {
  for (const [status, expected] of [
    [401, /Переподключите виджет/],
    [403, /Нет доступа к настройкам/],
    [404, /Обновите настройки/],
    [409, /Проверьте отмеченные поля/],
  ]) {
    const { root, controller } = setup(snapshot(), {
      save: async () => { throw { status, responseJSON: { error: { field: 'settings.support_phone', message: 'internal SQL detail' } } }; },
    });
    await controller.ready;
    controller.setSupportPhone('draft');
    await assert.rejects(controller.save());
    assert.equal(controller.serialize().settings.support_phone, 'draft');
    assert.match(root.textContent, expected);
    assert.doesNotMatch(root.textContent, /internal SQL detail/);
    assert.equal(root.querySelector('[data-field="support_phone"]').getAttribute('aria-invalid'), 'true');
  }
});

test('rate limit clamps untrusted Retry-After and handles absent delay', async () => {
  for (const [retryAfter, expected] of [['999999999', /3600 секунд/], ['not-a-number', /позже/]]) {
    const { root, controller } = setup(snapshot(), { save: async () => { throw { status: 429, retryAfter }; } });
    await controller.ready;
    controller.setSupportPhone('draft');
    await assert.rejects(controller.save());
    assert.equal(controller.serialize().settings.support_phone, 'draft');
    assert.match(root.textContent, expected);
  }
});

test('rate limit accepts an HTTP-date Retry-After and bounds it to one hour', async () => {
  const retryAfter = new Date(Date.now() + 24 * 60 * 60 * 1000).toUTCString();
  const { root, controller } = setup(snapshot(), { save: async () => { throw { status: 429, retryAfter }; } });
  await controller.ready;
  await assert.rejects(controller.save());
  assert.match(root.textContent, /3600 секунд/);
});

test('avatar uses only safe URL schemes', async () => {
  const data = snapshot();
  data.users[0].avatar_url = 'javascript:alert(1)';
  data.users[1].avatar_url = 'https://cdn.example.test/avatar.png';
  const { root, controller } = setup(data);
  await controller.ready;
  assert.equal(root.querySelector('[data-user-id="101"] img'), null);
  assert.equal(root.querySelector('[data-user-id="102"] img').getAttribute('src'), 'https://cdn.example.test/avatar.png');
});

test('validation rejects empty statuses and incomplete new group before transport', async () => {
  const { controller, saves } = setup();
  await controller.ready;
  controller.settings.allowed_statuses = [];
  controller.addGroup();
  assert.deepEqual(JSON.parse(JSON.stringify(controller.validate())), [{
    code: 'ALLOWED_STATUSES_REQUIRED', field: 'settings.allowed_statuses',
  }, {
    code: 'GROUP_NAME_REQUIRED', field: 'groups.1.name',
  }]);
  await assert.rejects(controller.save());
  assert.equal(saves.length, 0);
});

test('setSupportPhone updates draft without browser authority fields', async () => {
  const { controller } = setup();
  await controller.ready;
  controller.setSupportPhone('+375 29 000-00-00');
  const payload = controller.serialize();
  assert.equal(payload.settings.support_phone, '+375 29 000-00-00');
  assert.deepEqual(Object.keys(payload), ['revision', 'settings', 'groups', 'users']);
});

test('concurrent save calls share one in-flight snapshot save', async () => {
  let resolveSave;
  let calls = 0;
  const canonical = snapshot();
  canonical.revision = 4;
  const { controller } = setup(snapshot(), { save: () => {
    calls += 1;
    return new Promise((resolve) => { resolveSave = resolve; });
  } });
  await controller.ready;
  const first = controller.save();
  const second = controller.save();
  assert.equal(calls, 1);
  resolveSave(canonical);
  await Promise.all([first, second]);
  assert.equal(controller.serialize().revision, 4);
});

test('pending host-triggered save locks every editable control until the canonical response arrives', async () => {
  let resolveSave;
  let sent;
  const canonical = snapshot();
  canonical.revision = 4;
  canonical.settings.support_phone = 'before';
  const { root, controller } = setup(snapshot(), { save: (payload) => {
    sent = payload;
    return new Promise((resolve) => { resolveSave = resolve; });
  } });
  await controller.ready;
  controller.setSupportPhone('before');
  const pending = controller.save();
  const editableControls = [...root.querySelectorAll('input, select, .timesheet-settings__add-group')];
  assert.ok(editableControls.length > 0);
  assert.deepEqual(editableControls.map((control) => control.disabled), editableControls.map(() => true));
  assert.equal(root.querySelector('.timesheet-settings__save'), null);
  assert.throws(() => controller.setSupportPhone('after'), /saving/i);
  assert.throws(() => controller.setUser(101, { hide_widget: true }), /saving/i);
  assert.equal(sent.settings.support_phone, 'before');
  resolveSave(canonical);
  await pending;
  assert.equal(controller.serialize().settings.support_phone, 'before');
  const unlockedControls = [...root.querySelectorAll('input, select, .timesheet-settings__add-group')];
  assert.deepEqual(unlockedControls.map((control) => control.disabled), unlockedControls.map(() => false));
});

test('failed pending save unlocks draft controls', async () => {
  let rejectSave;
  const { root, controller } = setup(snapshot(), { save: () => new Promise((_, reject) => { rejectSave = reject; }) });
  await controller.ready;
  controller.setSupportPhone('draft');
  const pending = controller.save();
  assert.equal(root.querySelector('[data-field="support_phone"]').disabled, true);
  rejectSave({ status: 429, retryAfter: '5' });
  await assert.rejects(pending);
  assert.equal(root.querySelector('[data-field="support_phone"]').disabled, false);
  assert.equal(controller.serialize().settings.support_phone, 'draft');
});

test('renaming an accounting group refreshes assignment label without losing search or selection', async () => {
  const { root, controller } = setup();
  await controller.ready;
  const select = root.querySelector('[data-user-id="101"] [data-field="group_ref"]');
  select.value = 'id:10';
  select.dispatchEvent(new root.ownerDocument.defaultView.Event('change', { bubbles: true }));
  const search = root.querySelector('[data-field="search"]');
  search.value = 'ANNA';
  search.dispatchEvent(new root.ownerDocument.defaultView.Event('input', { bubbles: true }));
  root.querySelectorAll('[role=tab]')[1].click();
  const name = root.querySelector('[data-group-ref="id:10"] [data-field="name"]');
  name.value = 'Новая группа';
  name.dispatchEvent(new root.ownerDocument.defaultView.Event('input', { bubbles: true }));
  root.querySelectorAll('[role=tab]')[0].click();
  const refreshed = root.querySelector('[data-user-id="101"] [data-field="group_ref"]');
  assert.equal(root.querySelector('[data-field="search"]').value, 'ANNA');
  assert.equal(root.querySelectorAll('[data-user-id]').length, 1);
  assert.equal(refreshed.value, 'id:10');
  assert.equal(refreshed.querySelector('option[value="id:10"]').textContent, 'Новая группа');
});

test('activating an accounting group makes it available for assignment immediately', async () => {
  const data = snapshot();
  data.groups.push({ ...data.groups[0], id: 11, name: 'Резерв', is_active: false });
  const { root, controller } = setup(data);
  await controller.ready;
  assert.equal(root.querySelector('[data-user-id="101"] option[value="id:11"]'), null);
  root.querySelectorAll('[role=tab]')[1].click();
  const active = root.querySelector('[data-group-ref="id:11"] [data-field="is_active"]');
  active.checked = true;
  active.dispatchEvent(new root.ownerDocument.defaultView.Event('change', { bubbles: true }));
  root.querySelectorAll('[role=tab]')[0].click();
  assert.equal(root.querySelector('[data-user-id="101"] option[value="id:11"]').textContent, 'Резерв');
});

test('unchanged inactive historical user does not fail active-group client validation', async () => {
  const data = snapshot();
  data.groups[0].is_active = false;
  data.users[1].is_active = false;
  const { controller, saves } = setup(data);
  await controller.ready;
  assert.equal(controller.validate().length, 0);
  await controller.save();
  assert.deepEqual(JSON.parse(JSON.stringify(saves[0].users[1])), {
    amocrm_user_id: 102, track_time: true, hide_widget: false, group_ref: 'id:10',
  });
});
