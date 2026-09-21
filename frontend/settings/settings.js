(function (global) {
  'use strict';

  function node(doc, tag, className, value) {
    var item = doc.createElement(tag);
    if (className) item.className = className;
    if (value != null) item.textContent = String(value);
    return item;
  }
  function control(doc, tag, field, value) {
    var item = node(doc, tag, 'timesheet-settings__control');
    item.dataset.field = field;
    if (tag === 'input') item.type = 'text';
    if (value != null) item.value = String(value);
    return item;
  }
  function labeled(doc, title, input) {
    var label = node(doc, 'label', 'timesheet-settings__label');
    label.append(node(doc, 'span', '', title), input);
    return label;
  }
  function checkbox(doc, field, checked) {
    var input = control(doc, 'input', field);
    input.type = 'checkbox';
    input.checked = Boolean(checked);
    return input;
  }
  function clone(value) { return JSON.parse(JSON.stringify(value)); }

  function SettingsController(root, transport) {
    if (!root || !transport || typeof transport.load !== 'function' || typeof transport.save !== 'function') {
      throw new TypeError('Settings root and load/save transport are required');
    }
    this.root = root;
    this.transport = transport;
    this.snapshot = null;
    this.users = [];
    this.groups = [];
    this.settings = null;
    this.query = '';
    this.activeTab = 'users';
    this.errors = [];
    this.message = '';
    this.destroyed = false;
    this.groupCounter = 0;
    this.showState('Загрузка…');
    this.ready = this.load();
  }
  SettingsController.mount = function (root, transport) { return new SettingsController(root, transport); };

  SettingsController.prototype.showState = function (message) {
    if (this.destroyed) return;
    var shell = node(this.root.ownerDocument, 'div', 'timesheet-settings');
    shell.setAttribute('role', 'status');
    shell.append(node(this.root.ownerDocument, 'p', 'timesheet-settings__state', message));
    this.root.replaceChildren(shell);
  };
  SettingsController.prototype.accept = function (snapshot) {
    this.snapshot = snapshot;
    this.settings = clone(snapshot.settings);
    this.groups = snapshot.groups.map(function (group) {
      var item = clone(group);
      delete item.account_id;
      return item;
    });
    this.users = snapshot.users.map(function (user) {
      return { amocrm_user_id: user.amocrm_user_id, track_time: Boolean(user.track_time),
        hide_widget: Boolean(user.hide_widget), group_ref: user.group_id == null ? null : 'id:' + user.group_id };
    });
    this.errors = [];
    this.message = '';
    this.render();
  };
  SettingsController.prototype.load = async function () {
    try {
      var snapshot = await this.transport.load();
      if (!this.destroyed) this.accept(snapshot);
    } catch (error) {
      if (!this.destroyed) this.showState(error && error.status === 403 ? 'Нет доступа к настройкам.' :
        error && error.status === 401 ? 'Авторизация истекла. Переподключите виджет.' :
          'Не удалось загрузить настройки. Повторите попытку.');
      throw error;
    }
  };
  SettingsController.prototype.groupRef = function (group) {
    return group.id != null ? 'id:' + group.id : 'client:' + group.client_key;
  };

  SettingsController.prototype.render = function () {
    if (this.destroyed) return;
    var self = this;
    var doc = this.root.ownerDocument;
    var shell = node(doc, 'div', 'timesheet-settings');
    var tabs = node(doc, 'div', 'timesheet-settings__tabs');
    tabs.setAttribute('role', 'tablist');
    [['users', 'Пользователи'], ['settings', 'Настройки']].forEach(function (entry) {
      var tab = node(doc, 'button', 'timesheet-settings__tab', entry[1]);
      tab.type = 'button';
      tab.setAttribute('role', 'tab');
      tab.setAttribute('aria-selected', String(self.activeTab === entry[0]));
      tab.addEventListener('click', function () { self.switchTab(entry[0]); });
      tabs.append(tab);
    });
    shell.append(tabs);
    var usersPanel = node(doc, 'section', 'timesheet-settings__panel');
    usersPanel.setAttribute('role', 'tabpanel');
    usersPanel.hidden = this.activeTab !== 'users';
    var search = control(doc, 'input', 'search', this.query);
    search.type = 'search';
    search.placeholder = 'Поиск по имени или email';
    search.setAttribute('aria-label', 'Поиск пользователей');
    search.addEventListener('input', function () { self.query = search.value; self.renderUsers(list); });
    usersPanel.append(search);
    var list = node(doc, 'div', 'timesheet-settings__users');
    usersPanel.append(list);
    this.renderUsers(list);
    shell.append(usersPanel);
    var settingsPanel = node(doc, 'section', 'timesheet-settings__panel');
    settingsPanel.setAttribute('role', 'tabpanel');
    settingsPanel.hidden = this.activeTab !== 'settings';
    this.renderSettings(settingsPanel);
    shell.append(settingsPanel);
    var message = node(doc, 'div', 'timesheet-settings__message', this.message);
    message.setAttribute('role', 'alert');
    shell.append(message);
    this.root.replaceChildren(shell);
    this.markErrors();
  };
  SettingsController.prototype.switchTab = function (tab) {
    if (tab !== 'users' && tab !== 'settings') return;
    this.activeTab = tab;
    if (tab === 'users' && !this.pendingSave) {
      this.renderUsers(this.root.querySelector('.timesheet-settings__users'));
    }
    this.root.querySelectorAll('[role=tab]').forEach(function (item, index) {
      item.setAttribute('aria-selected', String((index === 0) === (tab === 'users')));
    });
    this.root.querySelectorAll('[role=tabpanel]').forEach(function (item, index) {
      item.hidden = (index === 0) !== (tab === 'users');
    });
  };

  SettingsController.prototype.renderUsers = function (list) {
    var self = this;
    var doc = this.root.ownerDocument;
    list.replaceChildren();
    var query = this.query.trim().toLocaleLowerCase();
    var groups = new Map();
    this.snapshot.users.forEach(function (user, index) {
      if (query && !(String(user.name || '') + ' ' + String(user.email || '')).toLocaleLowerCase().includes(query)) return;
      var label = user.amocrm_group_label || 'Без группы amoCRM';
      if (!groups.has(label)) groups.set(label, []);
      groups.get(label).push({ user: user, index: index });
    });
    groups.forEach(function (entries, label) {
      var section = node(doc, 'section', 'timesheet-settings__user-group');
      section.dataset.amocrmGroup = label;
      section.append(node(doc, 'h3', 'timesheet-settings__heading', label));
      entries.forEach(function (entry) {
        var user = entry.user;
        var state = self.users[entry.index];
        var row = node(doc, 'div', 'timesheet-settings__user');
        row.dataset.userId = String(user.amocrm_user_id);
        var identity = node(doc, 'div', 'timesheet-settings__identity');
        if (user.avatar_url) {
          try {
            var avatarUrl = new doc.defaultView.URL(user.avatar_url, doc.baseURI);
            if (avatarUrl.protocol === 'https:' || avatarUrl.protocol === 'http:') {
              var avatar = node(doc, 'img', 'timesheet-settings__avatar');
              avatar.src = avatarUrl.href;
              avatar.alt = '';
              identity.append(avatar);
            }
          } catch (ignore) { /* Invalid avatar URL: show the text identity only. */ }
        }
        identity.append(node(doc, 'strong', '', user.name), node(doc, 'small', '', user.email));
        if (!user.is_active) identity.append(node(doc, 'small', '', 'Неактивен — только просмотр'));
        row.append(identity);
        [['track_time', 'Учитывать рабочее время'], ['hide_widget', 'Скрыть виджет']].forEach(function (item) {
          var input = checkbox(doc, item[0], state[item[0]]);
          input.disabled = !user.is_active;
          input.addEventListener('change', function () { self.setUser(user.amocrm_user_id, { [item[0]]: input.checked }); });
          row.append(labeled(doc, item[1], input));
        });
        var select = control(doc, 'select', 'group_ref');
        var none = node(doc, 'option', '', 'Без группы учёта');
        none.value = '';
        select.append(none);
        self.groups.forEach(function (group) {
          var ref = self.groupRef(group);
          if (!group.is_active && ref !== state.group_ref) return;
          var option = node(doc, 'option', '', group.name);
          option.value = ref;
          select.append(option);
        });
        select.value = state.group_ref || '';
        select.disabled = !user.is_active;
        select.addEventListener('change', function () { self.setUser(user.amocrm_user_id, { group_ref: select.value || null }); });
        row.append(labeled(doc, 'Группа учёта', select));
        section.append(row);
      });
      list.append(section);
    });
  };

  SettingsController.prototype.renderSettings = function (panel) {
    var self = this;
    var doc = this.root.ownerDocument;
    var account = node(doc, 'section', 'timesheet-settings__account');
    account.append(node(doc, 'h3', 'timesheet-settings__heading', 'Общие настройки'));
    var phone = control(doc, 'input', 'support_phone', this.settings.support_phone || '');
    phone.addEventListener('input', function () { self.settings.support_phone = phone.value || null; });
    account.append(labeled(doc, 'Телефон поддержки', phone));
    [['working', 'Работает'], ['break', 'Перерыв'], ['finished', 'Завершил']].forEach(function (entry) {
      var input = checkbox(doc, 'allowed_statuses', self.settings.allowed_statuses.includes(entry[0]));
      input.value = entry[0];
      input.addEventListener('change', function () {
        self.settings.allowed_statuses = [...account.querySelectorAll('[data-field="allowed_statuses"]')]
          .filter(function (item) { return item.checked; }).map(function (item) { return item.value; });
      });
      account.append(labeled(doc, entry[1], input));
    });
    var restart = checkbox(doc, 'default_allow_restart_session', this.settings.default_allow_restart_session);
    restart.addEventListener('change', function () { self.settings.default_allow_restart_session = restart.checked; });
    account.append(labeled(doc, 'Разрешить повторный запуск смены по умолчанию', restart));
    panel.append(account);
    var groups = node(doc, 'section', 'timesheet-settings__groups');
    groups.append(node(doc, 'h3', 'timesheet-settings__heading', 'Группы учёта'));
    this.groups.forEach(function (group) {
      var card = node(doc, 'fieldset', 'timesheet-settings__group');
      card.dataset.groupRef = self.groupRef(group);
      card.append(node(doc, 'legend', '', group.name || 'Новая группа'));
      [['name', 'Название', 'text'], ['timezone', 'Часовой пояс IANA', 'text'],
        ['work_start_time', 'Начало дня', 'time'], ['work_end_time', 'Конец дня', 'time']].forEach(function (entry) {
        var input = control(doc, 'input', entry[0], group[entry[0]]);
        input.type = entry[2];
        if (entry[2] === 'time') input.value = String(group[entry[0]]).slice(0, 5);
        input.addEventListener('input', function () { group[entry[0]] = entry[2] === 'time' ? input.value + ':00' : input.value; });
        card.append(labeled(doc, entry[1], input));
      });
      var manager = control(doc, 'select', 'manager_amocrm_user_id');
      var empty = node(doc, 'option', '', 'Без руководителя');
      empty.value = '';
      manager.append(empty);
      self.snapshot.users.filter(function (user) { return user.is_active; }).forEach(function (user) {
        var option = node(doc, 'option', '', user.name);
        option.value = String(user.amocrm_user_id);
        manager.append(option);
      });
      manager.value = group.manager_amocrm_user_id == null ? '' : String(group.manager_amocrm_user_id);
      manager.addEventListener('change', function () { group.manager_amocrm_user_id = manager.value ? Number(manager.value) : null; });
      card.append(labeled(doc, 'Руководитель', manager));
      [['is_active', 'Активна'], ['allow_restart_session', 'Разрешить повторный запуск смены']].forEach(function (entry) {
        var input = checkbox(doc, entry[0], group[entry[0]]);
        input.addEventListener('change', function () { group[entry[0]] = input.checked; });
        card.append(labeled(doc, entry[1], input));
      });
      groups.append(card);
    });
    var add = node(doc, 'button', 'timesheet-settings__add-group', 'Добавить группу');
    add.type = 'button';
    add.addEventListener('click', function () { self.addGroup(); });
    groups.append(add);
    panel.append(groups);
  };
  SettingsController.prototype.addGroup = function () {
    if (this.pendingSave) throw new Error('Cannot edit while saving');
    this.groupCounter += 1;
    this.groups.push({ client_key: 'group_' + this.groupCounter, name: '', timezone: 'Europe/Minsk',
      work_start_time: '09:00:00', work_end_time: '18:00:00', manager_amocrm_user_id: null,
      is_active: true, allow_restart_session: false });
    this.render();
  };
  SettingsController.prototype.setUser = function (id, changes) {
    if (this.pendingSave) throw new Error('Cannot edit while saving');
    var original = this.snapshot.users.find(function (item) { return item.amocrm_user_id === id; });
    var user = this.users.find(function (item) { return item.amocrm_user_id === id; });
    if (!user) throw new Error('Unknown user');
    if (!original.is_active) throw new Error('Cannot modify inactive user');
    ['track_time', 'hide_widget', 'group_ref'].forEach(function (key) {
      if (Object.prototype.hasOwnProperty.call(changes, key)) user[key] = changes[key];
    });
  };
  SettingsController.prototype.setSupportPhone = function (value) {
    if (this.pendingSave) throw new Error('Cannot edit while saving');
    if (!this.settings) throw new Error('Settings have not loaded');
    this.settings.support_phone = value || null;
    var input = this.root.querySelector('[data-field="support_phone"]');
    if (input) input.value = value || '';
  };
  SettingsController.prototype.serialize = function () {
    if (!this.snapshot) throw new Error('Settings have not loaded');
    return { revision: this.snapshot.revision, settings: clone(this.settings), groups: clone(this.groups), users: clone(this.users) };
  };
  SettingsController.prototype.validate = function () {
    var errors = [];
    var self = this;
    if (!this.settings.allowed_statuses.length) {
      errors.push({ code: 'ALLOWED_STATUSES_REQUIRED', field: 'settings.allowed_statuses' });
    }
    this.groups.forEach(function (group, index) {
      if (!group.name.trim()) errors.push({ code: 'GROUP_NAME_REQUIRED', field: 'groups.' + index + '.name' });
    });
    var active = new Set(this.groups.filter(function (group) { return group.is_active; }).map(function (group) { return self.groupRef(group); }));
    this.users.forEach(function (user, index) {
      if (!self.snapshot.users[index].is_active) return;
      if (user.track_time && !user.group_ref) errors.push({ code: 'TRACKED_USER_GROUP_REQUIRED', field: 'users.' + index + '.group_ref' });
      else if (user.track_time && !active.has(user.group_ref)) errors.push({ code: 'GROUP_INACTIVE', field: 'users.' + index + '.group_ref' });
    });
    return errors;
  };
  SettingsController.prototype.markErrors = function () {
    var self = this;
    this.root.querySelectorAll('[aria-invalid]').forEach(function (item) { item.removeAttribute('aria-invalid'); });
    this.errors.forEach(function (error) {
      var match = /^(users|groups)\.(\d+)\.(\w+)$/.exec(error.field || '');
      var target;
      if (match && match[1] === 'users' && self.snapshot.users[Number(match[2])]) {
        var userId = self.snapshot.users[Number(match[2])].amocrm_user_id;
        target = self.root.querySelector('[data-user-id="' + userId + '"] [data-field="' + match[3] + '"]');
      } else if (match && match[1] === 'groups' && self.groups[Number(match[2])]) {
        var ref = self.groupRef(self.groups[Number(match[2])]);
        target = self.root.querySelector('[data-group-ref="' + ref + '"] [data-field="' + match[3] + '"]');
      } else if (error.field && /^settings\.\w+$/.test(error.field)) {
        target = self.root.querySelector('[data-field="' + error.field.slice(9) + '"]');
      }
      if (target) target.setAttribute('aria-invalid', 'true');
    });
  };
  SettingsController.prototype.showError = function (error) {
    var body = error && (error.error || (error.responseJSON && error.responseJSON.error)) || error || {};
    this.errors = body.field ? [body] : [];
    var status = Number(error && error.status);
    var retryValue = error && error.retryAfter;
    var retryText = String(retryValue);
    var retrySeconds = /^\d+$/.test(retryText) ? Number(retryText) :
      retryValue == null ? 0 : Math.ceil((Date.parse(retryText) - Date.now()) / 1000);
    var retry = Math.max(0, Math.min(3600, retrySeconds || 0));
    this.message = status === 401 ? 'Авторизация истекла. Переподключите виджет.' :
      status === 403 ? 'Нет доступа к настройкам.' :
        status === 404 ? 'Данные изменились. Обновите настройки и повторите попытку.' :
          status === 409 ? 'Конфликт настроек. Проверьте отмеченные поля и обновите данные при необходимости.' :
            status === 429 ? 'Слишком много запросов. Повторите ' + (retry ? 'через ' + retry + ' секунд.' : 'позже.') :
              'Не удалось сохранить настройки.';
    var message = this.root.querySelector('.timesheet-settings__message');
    if (message) message.textContent = this.message;
    this.markErrors();
  };
  SettingsController.prototype.save = function () {
    if (this.pendingSave) return this.pendingSave;
    var self = this;
    var pending = this.performSave();
    this.pendingSave = pending;
    this.setEditingLocked(true);
    function unlock() { self.pendingSave = null; self.setEditingLocked(false); }
    pending.then(unlock, unlock);
    return pending;
  };
  SettingsController.prototype.setEditingLocked = function (locked) {
    this.root.querySelectorAll('.timesheet-settings input, .timesheet-settings select, ' +
      '.timesheet-settings__add-group').forEach(function (item) {
      if (locked && !item.disabled) {
        item.disabled = true;
        item.dataset.saveLocked = 'true';
      } else if (!locked && item.dataset.saveLocked === 'true') {
        item.disabled = false;
        delete item.dataset.saveLocked;
      }
    });
  };
  SettingsController.prototype.performSave = async function () {
    if (!this.snapshot || this.destroyed) throw new Error('Settings are unavailable');
    var errors = this.validate();
    if (errors.length) {
      var failure = new Error('Проверьте обязательные поля.');
      failure.errors = errors;
      this.errors = errors;
      this.message = failure.message;
      this.root.querySelector('.timesheet-settings__message').textContent = this.message;
      this.markErrors();
      throw failure;
    }
    try {
      var canonical = await this.transport.save(this.serialize());
      if (!this.destroyed) this.accept(canonical);
      return canonical;
    } catch (error) {
      if (!this.destroyed) this.showError(error);
      throw error;
    }
  };
  SettingsController.prototype.destroy = function () { this.destroyed = true; this.root.replaceChildren(); };

  global.SettingsController = SettingsController;
  if (typeof define === 'function' && define.amd) define(function () { return SettingsController; });
  if (typeof module !== 'undefined' && module.exports) module.exports = SettingsController;
})(typeof window !== 'undefined' ? window : globalThis);
