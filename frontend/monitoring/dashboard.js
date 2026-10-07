(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory(require('./activity-modal'));
  } else if (typeof define === 'function') {
    define(['./activity-modal'], factory);
  } else {
    root.TimesheetMonitoringDashboard = factory(root.TimesheetActivityModal);
  }
}(typeof self !== 'undefined' ? self : this, function (ActivityModal) {
  'use strict';

  const STATUS_LABELS = {
    working: 'Работает', on_break: 'На перерыве', finished: 'Завершил', not_started: 'Не начинал',
  };
  const BACKOFF_SECONDS = [30, 60, 120, 240, 300];

  function element(document, tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function duration(seconds) {
    const total = Math.max(0, Number(seconds) || 0);
    const hours = Math.floor(total / 3600);
    const minutes = Math.floor((total % 3600) / 60);
    return hours ? `${hours} ч ${minutes} мин` : `${minutes} мин`;
  }

  function clock(value, timezone) {
    if (!value) return '—';
    try {
      return new Intl.DateTimeFormat('ru-RU', {
        timeZone: timezone || 'UTC', hour: '2-digit', minute: '2-digit', hour12: false,
      }).format(new Date(value));
    } catch (_error) {
      return '—';
    }
  }

  function localIsoDate(date, timezone) {
    const parts = new Intl.DateTimeFormat('en-CA', {
      timeZone: timezone || 'UTC', year: 'numeric', month: '2-digit', day: '2-digit',
    }).formatToParts(date);
    const value = Object.fromEntries(parts.map((part) => [part.type, part.value]));
    return `${value.year}-${value.month}-${value.day}`;
  }

  function shiftDate(isoDate, days) {
    const date = new Date(`${isoDate}T12:00:00Z`);
    date.setUTCDate(date.getUTCDate() + days);
    return date.toISOString().slice(0, 10);
  }

  function mount(root, options) {
    const settings = options || {};
    const document = settings.document || (root && root.ownerDocument);
    const transport = settings.transport;
    if (!root || !document || !transport || typeof transport.status !== 'function' || typeof transport.activity !== 'function') {
      throw new TypeError('Root, document, and monitoring transport are required');
    }
    const schedule = settings.schedule || ((fn, delay) => {
      const timer = setTimeout(fn, delay);
      return () => clearTimeout(timer);
    });
    const now = settings.now || (() => new Date());
    const random = settings.random || Math.random;

    const host = element(document, 'section', 'ts-monitoring');
    host.setAttribute('aria-label', 'Мониторинг сотрудников');
    const header = element(document, 'header', 'ts-monitoring__header');
    header.appendChild(element(document, 'h2', 'ts-monitoring__title', 'Сотрудники'));
    const lastSuccess = element(document, 'span', 'ts-monitoring__last-success', 'Ещё не обновлялось');
    header.appendChild(lastSuccess);
    host.appendChild(header);

    const controls = element(document, 'div', 'ts-monitoring__controls');
    const search = element(document, 'input', 'ts-monitoring__search');
    search.type = 'search'; search.placeholder = 'Поиск сотрудника'; search.dataset.filter = 'search';
    search.setAttribute('aria-label', 'Поиск сотрудника');
    const status = element(document, 'select', 'ts-monitoring__status');
    status.dataset.filter = 'status'; status.setAttribute('aria-label', 'Статус сотрудника');
    [['', 'Все статусы'], ['working', 'Работает'], ['on_break', 'На перерыве'], ['finished', 'Завершил'], ['not_started', 'Не начинал']]
      .forEach(([value, label]) => { const option = element(document, 'option', '', label); option.value = value; status.appendChild(option); });
    const group = element(document, 'select', 'ts-monitoring__group');
    group.dataset.filter = 'group'; group.setAttribute('aria-label', 'Группа');
    const refreshButton = element(document, 'button', 'ts-monitoring__refresh', 'Обновить');
    refreshButton.type = 'button'; refreshButton.dataset.action = 'refresh';
    controls.append(search, status, group, refreshButton);
    host.appendChild(controls);
    const totals = element(document, 'div', 'ts-monitoring__totals');
    host.appendChild(totals);
    const message = element(document, 'div', 'ts-monitoring__message');
    message.setAttribute('role', 'status');
    host.appendChild(message);
    const content = element(document, 'div', 'ts-monitoring__content');
    host.appendChild(content);
    root.appendChild(host);

    const modal = ActivityModal.create({ document, mount: host });
    const listeners = [];
    let destroyed = false;
    let statusAbort = null;
    let detailAbort = null;
    let timerCancel = null;
    let requestVersion = 0;
    let detailVersion = 0;
    let failureCount = 0;
    let selectedUserId = null;
    let latestResponse = null;
    let statusInFlight = null;
    let refreshQueued = false;

    function listen(target, type, handler) {
      target.addEventListener(type, handler);
      listeners.push(() => target.removeEventListener(type, handler));
    }

    function cancelTimer() {
      if (timerCancel) timerCancel();
      timerCancel = null;
    }

    function nextDelay(success) {
      const seconds = success ? 30 : BACKOFF_SECONDS[Math.min(Math.max(failureCount - 1, 0), BACKOFF_SECONDS.length - 1)];
      return Math.round(seconds * 1000 * (0.9 + (0.2 * Math.max(0, Math.min(1, Number(random()) || 0)))));
    }

    function armTimer(success) {
      cancelTimer();
      if (destroyed || document.hidden) return;
      timerCancel = schedule(() => { timerCancel = null; refresh(); }, nextDelay(success));
    }

    function filters() {
      const result = {};
      const searchValue = search.value.trim();
      if (searchValue) result.search = searchValue;
      if (status.value) result.status = status.value;
      if (group.value) result.group_id = Number(group.value);
      return result;
    }

    function updateGroupOptions(groups) {
      const selected = group.value;
      group.replaceChildren();
      const all = element(document, 'option', '', 'Все группы'); all.value = ''; group.appendChild(all);
      for (const item of groups || []) {
        const option = element(document, 'option', '', String(item.name || 'Без названия'));
        option.value = String(item.id); group.appendChild(option);
      }
      if (Array.from(group.options).some((option) => option.value === selected)) group.value = selected;
    }

    function employeeRow(employee) {
      const row = element(document, 'article', `ts-monitoring__employee ts-monitoring__employee--${employee.status}`);
      row.dataset.userId = String(employee.id);
      const identity = element(document, 'div', 'ts-monitoring__identity');
      identity.appendChild(element(document, 'strong', 'ts-monitoring__name', String(employee.name || 'Сотрудник')));
      identity.appendChild(element(document, 'span', 'ts-monitoring__employee-status', STATUS_LABELS[employee.status] || 'Статус неизвестен'));
      const metrics = element(document, 'div', 'ts-monitoring__metrics');
      metrics.textContent = `Работа: ${duration(employee.work_seconds)} · Перерыв: ${duration(employee.break_seconds)} · Активность: ${duration(employee.confirmed_seconds)}`;
      const shift = element(document, 'div', 'ts-monitoring__shift',
        `Рабочий день: ${clock(employee.workday_started_at, employee.timezone)}–${clock(employee.workday_ended_at, employee.timezone)}`);
      row.append(identity, metrics, shift);
      if (employee.activity_detail_allowed) {
        const button = element(document, 'button', 'ts-monitoring__activity', '⋮');
        button.type = 'button'; button.dataset.activityUserId = String(employee.id);
        button.setAttribute('aria-label', `Активность: ${employee.name}`);
        row.appendChild(button);
      }
      return row;
    }

    function render(response) {
      latestResponse = response;
      updateGroupOptions(response.groups || []);
      const count = response.totals || {};
      totals.textContent = `Сотрудников: ${Number(count.employees) || (response.employees || []).length} · Работают: ${Number(count.working) || 0} · На перерыве: ${Number(count.on_break) || 0} · Завершили: ${Number(count.finished) || 0}`;
      content.replaceChildren();
      const employees = Array.isArray(response.employees) ? response.employees : [];
      const byGroup = new Map();
      for (const employee of employees) {
        const key = employee.group_id == null ? 'none' : String(employee.group_id);
        if (!byGroup.has(key)) byGroup.set(key, []);
        byGroup.get(key).push(employee);
      }
      const ordered = (response.groups || []).map((item) => ({ key: String(item.id), name: item.name }));
      if (byGroup.has('none')) ordered.push({ key: 'none', name: 'Без группы' });
      for (const item of ordered) {
        const members = byGroup.get(item.key) || [];
        if (!members.length) continue;
        const section = element(document, 'section', 'ts-monitoring__group');
        section.appendChild(element(document, 'h3', 'ts-monitoring__group-title', String(item.name)));
        for (const employee of members) section.appendChild(employeeRow(employee));
        content.appendChild(section);
      }
      if (!employees.length) content.appendChild(element(document, 'p', 'ts-monitoring__empty', 'Сотрудники не найдены.'));
    }

    function dateRange(employee) {
      const to = localIsoDate(now(), employee.timezone || 'UTC');
      return { from: shiftDate(to, -6), to };
    }

    function findSelected() {
      return latestResponse && (latestResponse.employees || []).find((employee) => Number(employee.id) === Number(selectedUserId));
    }

    function loadActivity(employee, trigger, initial) {
      if (!employee || destroyed) return Promise.resolve();
      if (detailAbort) detailAbort.abort();
      detailAbort = new AbortController();
      const version = ++detailVersion;
      const range = dateRange(employee);
      if (initial) modal.open({ state: 'loading', target: employee }, { trigger });
      else modal.update({ state: 'loading', target: employee });
      return Promise.resolve(transport.activity(employee.id, range.from, range.to, detailAbort.signal)).then((payload) => {
        if (!destroyed && version === detailVersion && !detailAbort.signal.aborted && Number(selectedUserId) === Number(employee.id)) modal.update(payload);
      }).catch((error) => {
        if (!destroyed && version === detailVersion && (!error || error.name !== 'AbortError')) modal.update({ state: 'error', target: employee });
      });
    }

    function openActivity(employee, trigger) {
      selectedUserId = employee.id;
      loadActivity(employee, trigger, true);
    }

    function refresh() {
      if (destroyed || document.hidden) return Promise.resolve(null);
      cancelTimer();
      if (statusInFlight) {
        refreshQueued = true;
        if (statusAbort) statusAbort.abort();
        return statusInFlight;
      }
      const abort = new AbortController();
      statusAbort = abort;
      const version = ++requestVersion;
      refreshButton.disabled = true;
      message.textContent = latestResponse ? '' : 'Загрузка сотрудников…';
      const operation = Promise.resolve(transport.status(filters(), abort.signal)).then((response) => {
        if (destroyed || abort.signal.aborted || version !== requestVersion) return null;
        failureCount = 0;
        render(response);
        message.textContent = '';
        lastSuccess.textContent = `Обновлено: ${now().toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}`;
        const selected = findSelected();
        if (selected && modal.isOpen()) loadActivity(selected, null, false);
        else if (modal.isOpen()) { selectedUserId = null; modal.close(); }
        armTimer(true);
        return response;
      }).catch((error) => {
        if (destroyed || abort.signal.aborted || version !== requestVersion || (error && error.name === 'AbortError')) return null;
        failureCount += 1;
        message.textContent = 'Не удалось обновить список. Попробуем ещё раз автоматически.';
        armTimer(false);
        return null;
      });
      const tracked = operation.finally(() => {
        if (statusInFlight === tracked) statusInFlight = null;
        if (statusAbort === abort) statusAbort = null;
        if (!destroyed && version === requestVersion) refreshButton.disabled = false;
        if (refreshQueued && !destroyed && !document.hidden) {
          refreshQueued = false;
          refresh();
        }
      });
      statusInFlight = tracked;
      return tracked;
    }

    function onFilter() { refresh(); }
    function onContentClick(event) {
      const button = event.target && event.target.closest && event.target.closest('[data-activity-user-id]');
      if (!button || !content.contains(button) || !latestResponse) return;
      const employee = (latestResponse.employees || []).find((item) => String(item.id) === button.dataset.activityUserId);
      if (employee && employee.activity_detail_allowed) openActivity(employee, button);
    }
    function onVisibility() {
      if (document.hidden) { refreshQueued = false; cancelTimer(); if (statusAbort) statusAbort.abort(); }
      else refresh();
    }
    listen(search, 'change', onFilter);
    listen(status, 'change', onFilter);
    listen(group, 'change', onFilter);
    listen(refreshButton, 'click', refresh);
    listen(content, 'click', onContentClick);
    listen(document, 'visibilitychange', onVisibility);

    const ready = refresh();

    function destroy() {
      if (destroyed) return;
      destroyed = true;
      refreshQueued = false;
      requestVersion += 1; detailVersion += 1;
      cancelTimer();
      if (statusAbort) statusAbort.abort();
      if (detailAbort) detailAbort.abort();
      for (const remove of listeners.splice(0)) remove();
      modal.destroy();
      host.remove();
    }

    return { ready, refresh, destroy };
  }

  return { mount };
}));
