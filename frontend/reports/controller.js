(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else if (typeof define === 'function') define([], factory);
  else root.TimesheetReports = factory();
}(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  const COLUMNS = [
    ['employee', 'Сотрудник'], ['date', 'Дата'], ['start', 'Начало'], ['end', 'Окончание'],
    ['break', 'Перерыв'], ['work', 'Работа'], ['status', 'Статус'],
    ['shift_lateness', 'Начало дня — минуты'], ['shift_late_reason', 'Начало дня — объяснительная'],
    ['break_lateness', 'Перерыв — минуты'], ['break_late_reason', 'Перерыв — объяснительная'],
  ];
  const STATUS = { working: 'Работает', on_break: 'На перерыве', finished: 'Завершил' };
  const mounts = new WeakMap();

  function normalizeColumns(values) {
    const allowed = COLUMNS.map(([key]) => key);
    const selected = Array.isArray(values)
      ? values.map((key) => key === 'lateness' ? 'shift_lateness' : key).filter((key) => allowed.includes(key))
      : allowed;
    return selected.length ? Array.from(new Set(selected)) : allowed;
  }

  function minutes(seconds) { return String(Math.ceil(Math.max(0, Number(seconds) || 0) / 60)); }

  function element(document, tag, className, label) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (label !== undefined) node.textContent = label;
    return node;
  }

  function duration(value) {
    const seconds = Math.max(0, Number(value) || 0);
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    return hours ? `${hours} ч ${minutes} мин` : `${minutes} мин`;
  }

  function clock(value, timezone) {
    if (!value) return '—';
    try {
      const date = new Date(value);
      if (Number.isNaN(date.valueOf())) return '—';
      return new Intl.DateTimeFormat('ru-RU', {
        timeZone: timezone || 'UTC', hour: '2-digit', minute: '2-digit', hour12: false,
      }).format(date);
    } catch (_error) { return '—'; }
  }

  function date(value) {
    const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(value || ''));
    return match ? `${match[3]}.${match[2]}.${match[1]}` : '—';
  }

  function localDate(value) {
    const pad = (part) => String(part).padStart(2, '0');
    return `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())}`;
  }

  function publicError(error, fallback) {
    const message = error && error.publicMessage;
    return typeof message === 'string' && message.trim().length > 0 && message.length <= 250 && !/[\r\n]/.test(message)
      ? message : fallback;
  }

  function mount(root, options) {
    const settings = options || {};
    const document = settings.document || (root && root.ownerDocument);
    const transport = settings.transport;
    if (!root || !document || !transport || typeof transport.directory !== 'function' ||
        typeof transport.report !== 'function' || typeof transport.export !== 'function') {
      throw new TypeError('Root, document, and report transport are required');
    }
    if (mounts.has(root)) mounts.get(root).destroy();
    const now = settings.now || (() => new Date());
    const today = localDate(now());
    const createObjectURL = settings.createObjectURL || ((blob) => URL.createObjectURL(blob));
    const revokeObjectURL = settings.revokeObjectURL || ((url) => URL.revokeObjectURL(url));
    const listeners = [];
    let destroyed = false;
    let directoryAbort = null;
    let previewAbort = null;
    let exportAbort = null;
    let directoryVersion = 0;
    let previewVersion = 0;
    let exportVersion = 0;
    let authorized = false;
    let groups = [];
    let employees = [];
    let reportPeriod = null;
    let page = 1;
    let exporting = false;

    function listen(target, type, handler) {
      target.addEventListener(type, handler);
      listeners.push(() => target.removeEventListener(type, handler));
    }
    function button(label, action) {
      const node = element(document, 'button', `ts-reports__${action}`, label);
      node.type = 'button'; node.dataset.action = action;
      return node;
    }
    function field(label, name, tag, type) {
      const wrap = element(document, 'label', 'ts-reports__field');
      wrap.appendChild(element(document, 'span', '', label));
      const input = element(document, tag, `ts-reports__${name}`);
      if (type) input.type = type;
      input.dataset.filter = name;
      wrap.appendChild(input);
      return { wrap, input };
    }
    const host = element(document, 'section', 'ts-reports');
    host.setAttribute('aria-label', 'Табель');
    host.appendChild(element(document, 'h2', 'ts-reports__title', 'Табель'));
    const controls = element(document, 'div', 'ts-reports__controls');
    const fromField = field('С', 'date-from', 'input', 'date');
    const toField = field('По', 'date-to', 'input', 'date');
    const groupField = field('Группа', 'group', 'select');
    const employeeField = field('Сотрудник', 'employee', 'select');
    const from = fromField.input, to = toField.input, group = groupField.input, employee = employeeField.input;
    from.value = today; to.value = today;
    const show = button('Показать', 'show');
    const clear = button('Очистить', 'clear');
    controls.append(fromField.wrap, toField.wrap, groupField.wrap, employeeField.wrap, show, clear);
    host.appendChild(controls);
    const columnBox = element(document, 'fieldset', 'ts-reports__columns');
    columnBox.appendChild(element(document, 'legend', '', 'Колонки Excel'));
    const columnInputs = new Map();
    const selectedColumns = normalizeColumns(settings.columns);
    for (const [key, label] of COLUMNS) {
      const wrap = element(document, 'label', 'ts-reports__column');
      const input = element(document, 'input'); input.type = 'checkbox'; input.checked = selectedColumns.includes(key); input.dataset.column = key;
      columnInputs.set(key, input);
      wrap.append(input, element(document, 'span', '', label));
      columnBox.appendChild(wrap);
    }
    host.appendChild(columnBox);
    const exportButton = button('Скачать Excel', 'export');
    exportButton.disabled = true;
    host.appendChild(exportButton);
    const exportMessage = element(document, 'div', 'ts-reports__export-message');
    exportMessage.setAttribute('role', 'status'); host.appendChild(exportMessage);
    const message = element(document, 'div', 'ts-reports__message');
    message.setAttribute('role', 'status'); host.appendChild(message);
    const retry = button('Повторить', 'retry'); retry.hidden = true; host.appendChild(retry);
    const table = element(document, 'table', 'ts-reports__table');
    const head = element(document, 'thead'); const header = element(document, 'tr');
    for (const [, label] of COLUMNS.slice(0, 7)) {
      const th = element(document, 'th', '', label); th.rowSpan = 3; th.scope = 'col'; header.appendChild(th);
    }
    const lateness = element(document, 'th', '', 'Опоздания'); lateness.colSpan = 4; lateness.scope = 'colgroup'; header.appendChild(lateness);
    head.appendChild(header);
    const headerGroups = element(document, 'tr');
    for (const label of ['Начало дня', 'Перерыв']) {
      const th = element(document, 'th', '', label); th.colSpan = 2; th.scope = 'colgroup'; headerGroups.appendChild(th);
    }
    head.appendChild(headerGroups);
    const children = element(document, 'tr');
    for (const label of ['Минуты', 'Объяснительная', 'Минуты', 'Объяснительная']) {
      const th = element(document, 'th', '', label); th.scope = 'col'; children.appendChild(th);
    }
    head.appendChild(children); table.appendChild(head);
    const body = element(document, 'tbody'); table.appendChild(body); host.appendChild(table);
    const pagination = element(document, 'nav', 'ts-reports__pagination');
    pagination.setAttribute('aria-label', 'Страницы табеля');
    const previous = button('Назад', 'previous'); previous.disabled = true;
    const pageLabel = element(document, 'span', 'ts-reports__page', 'Страница 1');
    const next = button('Вперёд', 'next'); next.disabled = true;
    pagination.append(previous, pageLabel, next); host.appendChild(pagination);
    root.appendChild(host);

    function updateOptions(select, options, allLabel) {
      const selected = select.value;
      select.replaceChildren();
      const all = element(document, 'option', '', allLabel); all.value = ''; select.appendChild(all);
      for (const item of options) {
        const id = Number(item.id);
        if (!Number.isSafeInteger(id) || id <= 0) continue;
        const option = element(document, 'option', '', String(item.name || 'Без названия'));
        option.value = String(id); select.appendChild(option);
      }
      if (Array.from(select.options).some((option) => option.value === selected)) select.value = selected;
    }
    function normalizePeriod(value) {
      const validDate = (part) => /^\d{4}-\d{2}-\d{2}$/.test(String(part || ''));
      if (!value || !validDate(value.min_date) || !validDate(value.max_date) || value.min_date > value.max_date) return null;
      return { min: value.min_date, max: value.max_date };
    }
    function activePeriod() {
      if (group.value) {
        const selected = groups.find((item) => Number(item.id) === Number(group.value));
        const selectedPeriod = selected && normalizePeriod({
          min_date: selected.report_min_date, max_date: selected.report_max_date,
        });
        if (selectedPeriod) return selectedPeriod;
      }
      return reportPeriod || { min: today, max: today };
    }
    function applyPeriodBounds(reset) {
      const period = activePeriod();
      for (const input of [from, to]) {
        input.min = period.min;
        input.max = period.max;
        if (reset) input.value = period.max;
        else if (!input.value || input.value > period.max) input.value = period.max;
        else if (input.value < period.min) input.value = period.min;
      }
    }
    function updateEmployees() {
      const groupId = group.value ? Number(group.value) : null;
      updateOptions(employee, employees.filter((item) => groupId === null || Number(item.group_id) === groupId), 'Все сотрудники');
      applyPeriodBounds(false);
    }
    function filters() {
      const params = { date_from: from.value, date_to: to.value };
      if (group.value) params.group_id = Number(group.value);
      if (employee.value) params.user_id = Number(employee.value);
      return params;
    }
    function renderRows(items) {
      body.replaceChildren();
      for (const item of items) {
        const tr = element(document, 'tr');
        const cells = [String(item.employee_name || ''), date(item.date), clock(item.started_at, item.group_timezone),
          clock(item.ended_at, item.group_timezone), duration(item.break_seconds), duration(item.work_seconds),
          STATUS[item.status] || '—', minutes(item.shift_late_seconds ?? item.late_seconds), String(item.shift_late_reason || ''),
          minutes(item.break_late_seconds)];
        for (const value of cells) tr.appendChild(element(document, 'td', '', value));
        tr.children[8].className = 'ts-reports__reason';
        const explanations = element(document, 'td', 'ts-reports__reason');
        for (const incident of Array.isArray(item.break_late_reason) ? item.break_late_reason : []) {
          const label = `Перерыв №${incident.sequence} — ${minutes(incident.late_seconds)} мин`;
          explanations.appendChild(element(document, 'div', 'ts-reports__break-reason',
            incident.reason ? `${label}: ${incident.reason}` : label));
        }
        tr.appendChild(explanations);
        body.appendChild(tr);
      }
    }
    async function refresh() {
      if (destroyed || !authorized) return null;
      if (previewAbort) previewAbort.abort();
      const abort = new AbortController(); previewAbort = abort;
      const version = ++previewVersion;
      const params = { ...filters(), page };
      message.textContent = 'Загрузка табеля…'; retry.hidden = true;
      body.replaceChildren(); previous.disabled = true; next.disabled = true;
      try {
        const response = await transport.report(params, abort.signal);
        if (destroyed || abort.signal.aborted || version !== previewVersion) return null;
        const items = Array.isArray(response.items) ? response.items.slice(0, 10) : [];
        page = Number(response.page) || page;
        renderRows(items);
        message.textContent = items.length ? '' : 'За выбранный период данных нет.';
        pageLabel.textContent = `Страница ${page}`;
        previous.disabled = page <= 1;
        next.disabled = page * 10 >= Number(response.total || 0);
        return response;
      } catch (error) {
        if (destroyed || abort.signal.aborted || version !== previewVersion) return null;
        message.textContent = publicError(error, 'Не удалось загрузить табель. Повторите попытку.');
        retry.hidden = false;
        return null;
      } finally {
        if (previewAbort === abort) previewAbort = null;
      }
    }
    async function loadDirectory() {
      if (destroyed) return null;
      if (directoryAbort) directoryAbort.abort();
      const abort = new AbortController(); directoryAbort = abort;
      const version = ++directoryVersion;
      message.textContent = 'Загрузка табеля…'; retry.hidden = true;
      try {
        const response = await transport.directory(abort.signal);
        if (destroyed || abort.signal.aborted || version !== directoryVersion) return null;
        if (!response.viewer || !['admin', 'manager'].includes(response.viewer.role)) {
          authorized = false; message.textContent = 'У вас нет доступа к этому разделу.';
          host.replaceChildren(element(document, 'h2', 'ts-reports__title', 'Табель'), message);
          return null;
        }
        authorized = true;
        groups = Array.isArray(response.groups) ? response.groups : [];
        reportPeriod = normalizePeriod(response.report_period);
        employees = Array.isArray(response.employees)
          ? response.employees.filter((item) => item.report_filter_allowed === true) : [];
        updateOptions(group, groups, 'Все группы'); updateEmployees();
        exportButton.disabled = false;
        return refresh();
      } catch (error) {
        if (destroyed || abort.signal.aborted || version !== directoryVersion) return null;
        message.textContent = publicError(error, 'Не удалось загрузить табель. Повторите попытку.');
        retry.hidden = false;
        return null;
      } finally {
        if (directoryAbort === abort) directoryAbort = null;
      }
    }
    async function download() {
      if (destroyed || !authorized || exporting) return null;
      exporting = true; exportButton.disabled = true; exportMessage.textContent = '';
      const abort = new AbortController(); exportAbort = abort;
      const version = ++exportVersion;
      const columns = COLUMNS.map(([key]) => key).filter((key) => columnInputs.get(key).checked);
      const body = { ...filters(), columns };
      let anchor = null, url = null;
      try {
        const result = await transport.export(body, abort.signal);
        if (destroyed || abort.signal.aborted || version !== exportVersion) return null;
        url = createObjectURL(result.blob);
        anchor = element(document, 'a'); anchor.href = url; anchor.download = result.filename;
        host.appendChild(anchor); anchor.click();
        return result;
      } catch (error) {
        if (!destroyed && !abort.signal.aborted && version === exportVersion) {
          exportMessage.textContent = publicError(error, 'Не удалось скачать Excel. Повторите попытку.');
        }
        return null;
      } finally {
        if (anchor) anchor.remove();
        if (url) revokeObjectURL(url);
        if (exportAbort === abort) exportAbort = null;
        if (!destroyed && version === exportVersion) { exporting = false; exportButton.disabled = false; }
      }
    }
    function destroy() {
      if (destroyed) return;
      destroyed = true;
      if (directoryAbort) directoryAbort.abort();
      if (previewAbort) previewAbort.abort();
      if (exportAbort) exportAbort.abort();
      ++directoryVersion; ++previewVersion; ++exportVersion;
      for (const remove of listeners) remove();
      host.remove();
      if (mounts.get(root) === api) mounts.delete(root);
    }
    listen(group, 'change', updateEmployees);
    listen(show, 'click', () => { page = 1; refresh(); });
    listen(clear, 'click', () => { group.value = ''; updateEmployees(); applyPeriodBounds(true); employee.value = ''; page = 1; refresh(); });
    listen(previous, 'click', () => { if (page > 1) { --page; refresh(); } });
    listen(next, 'click', () => { if (!next.disabled) { ++page; refresh(); } });
    listen(retry, 'click', () => { if (authorized) refresh(); else loadDirectory(); });
    listen(exportButton, 'click', download);
    for (const input of columnInputs.values()) listen(input, 'change', () => {
      if (!Array.from(columnInputs.values()).some((item) => item.checked)) input.checked = true;
    });
    const api = { ready: null, refresh, destroy };
    mounts.set(root, api);
    api.ready = loadDirectory();
    return api;
  }
  return { mount, normalizeColumns };
}));
