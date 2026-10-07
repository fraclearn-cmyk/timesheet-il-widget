(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else if (typeof define === 'function') define([], factory);
  else root.TimesheetReports = factory();
}(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  const COLUMNS = [
    ['employee', 'Сотрудник'], ['date', 'Дата'], ['start', 'Начало'], ['end', 'Окончание'],
    ['break', 'Перерыв'], ['work', 'Работа'], ['lateness', 'Опоздание'], ['status', 'Статус'],
  ];
  const STATUS = { working: 'Работает', on_break: 'На перерыве', finished: 'Завершил' };
  const mounts = new WeakMap();

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
    for (const [key, label] of COLUMNS) {
      const wrap = element(document, 'label', 'ts-reports__column');
      const input = element(document, 'input'); input.type = 'checkbox'; input.checked = true; input.dataset.column = key;
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
    for (const [, label] of COLUMNS) header.appendChild(element(document, 'th', '', label));
    head.appendChild(header); table.appendChild(head);
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
    function updateEmployees() {
      const groupId = group.value ? Number(group.value) : null;
      updateOptions(employee, employees.filter((item) => groupId === null || Number(item.group_id) === groupId), 'Все сотрудники');
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
          duration(item.late_seconds), STATUS[item.status] || '—'];
        for (const value of cells) tr.appendChild(element(document, 'td', '', value));
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
    listen(clear, 'click', () => { from.value = today; to.value = today; group.value = ''; updateEmployees(); employee.value = ''; page = 1; refresh(); });
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
  return { mount };
}));
