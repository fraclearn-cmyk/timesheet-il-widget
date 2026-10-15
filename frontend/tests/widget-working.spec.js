const { test, expect } = require('@playwright/test');
const { readFileSync } = require('node:fs');
const { resolve } = require('node:path');
test.use({ channel: 'chrome' });

const sources = Object.fromEntries([
  ['settings', 'frontend/settings/settings.js'],
  ['controller', 'widget/timesheet/controller.js'],
  ['overlay', 'widget/overlay.js'], ['tracker', 'widget/activity-tracker.js'],
  ['timeline', 'frontend/monitoring/timeline.js'], ['modal', 'frontend/monitoring/activity-modal.js'],
  ['dashboard', 'frontend/monitoring/dashboard.js'], ['widget', 'widget/script.js'],
  ['reports', 'frontend/reports/controller.js'],
].map(([key, file]) => [key, readFileSync(resolve(__dirname, '../..', file), 'utf8')]));
const css = readFileSync(resolve(__dirname, '../../widget/styles.css'), 'utf8');
const monitoringCss = readFileSync(resolve(__dirname, '../monitoring/styles.css'), 'utf8');
const reportsCss = readFileSync(resolve(__dirname, '../reports/styles.css'), 'utf8');

async function boot(page, cssHandler, role = 'employee', timesheetStatus = 'on_break', lateness = {}) {
  await page.route('https://widget.test/**', async (route) => {
    if (route.request().url().includes('/monitoring/styles.css')) {
      return route.fulfill({ contentType: 'text/css', body: monitoringCss });
    }
    if (route.request().url().includes('/reports/styles.css')) {
      return route.fulfill({ contentType: 'text/css', body: reportsCss });
    }
    if (route.request().url().includes('/styles.css')) return cssHandler(route);
    return route.fulfill({ contentType: 'text/html', body: '<button id="crm">CRM</button><div id="list_page_holder"></div>' });
  });
  await page.goto('https://widget.test/');
  await page.evaluate(({ code, role, timesheetStatus, lateness }) => {
    const modules = {};
    for (const name of ['settings', 'controller', 'overlay', 'tracker']) {
      window.define = (factory) => { modules[name] = factory(); };
      window.define.amd = {};
      (0, eval)(code[name]);
    }
    window.define = (_ids, factory) => { modules.timeline = factory(); }; window.define.amd = {}; (0, eval)(code.timeline);
    window.define = (_ids, factory) => { modules.modal = factory(modules.timeline); }; window.define.amd = {}; (0, eval)(code.modal);
    window.define = (_ids, factory) => { modules.dashboard = factory(modules.modal); }; window.define.amd = {}; (0, eval)(code.dashboard);
    window.define = (_ids, factory) => { modules.reports = factory(); }; window.define.amd = {}; (0, eval)(code.reports);
    window.define = (_ids, factory) => { window.Widget = factory({}, modules.settings, modules.controller, modules.overlay,
      modules.tracker, modules.timeline, modules.modal, modules.dashboard, modules.reports); };
    (0, eval)(code.widget);
    window.widget = new window.Widget();
    window.area = 'lcard'; window.calls = [];
    window.widget.system = () => ({ area: window.area });
    window.widget.get_settings = () => ({ api_url: 'https://api.test/api/v1/', path: 'https://widget.test/assets/', version: '3.0.2' });
    window.widget.$authorizedAjax = (request) => {
      window.calls.push(request);
      if (request.url.includes('/settings/')) return new Promise(() => {});
      if (request.url.includes('/team/status')) return Promise.resolve({ generated_at: '2026-09-29T09:00:00Z',
        viewer: { role, can_view_activity: false }, groups: [], employees: [],
        totals: { employees: 0, working: 0, on_break: 0, finished: 0, not_started: 0 } });
      if (request.url.includes('/reports/detailed')) return Promise.resolve({ items: [], page: 1, total: 0 });
      return Promise.resolve({ session_id: 7, status: timesheetStatus, started_at: '2026-09-22T08:00:00Z',
        ended_at: null, break_seconds: 0, track_time: true, hide_widget: false, restart_allowed: false,
        late_reason_required: false, late_reason_kind: null, late_minutes: 0, break_sequence: null, ...lateness });
    };
    window.widget.callbacks.init();
  }, { code: sources, role, timesheetStatus, lateness });
}

for (const [status, action, kind, sequence, label, message] of [
  ['not_started', 'start-work', 'shift_start', null, 'Начать рабочий день', 'Опоздание к началу дня: 8 мин.'],
  ['on_break', 'end-break', 'break_return', 2, 'Продолжить работу', 'Опоздание с перерыва №2: 8 мин.'],
]) {
  test(`${status}: accessible explanation enables command while CRM remains blocked`, async ({ page }) => {
    await boot(page, (route) => route.fulfill({ contentType: 'text/css', body: css }), 'employee', status,
      { late_reason_required: true, late_reason_kind: kind, late_minutes: 8, break_sequence: sequence });
    const input = page.getByRole('textbox', { name: 'Причина опоздания' });
    const button = page.getByRole('button', { name: label, exact: true });
    await expect(page.getByRole('dialog')).toHaveAccessibleName('Учёт рабочего времени');
    await expect(page.getByText(message, { exact: true })).toBeVisible();
    await expect(input).toHaveCount(1);
    await expect(input).toBeFocused();
    await expect(input).toHaveAttribute('maxlength', '1000');
    await expect(button).toBeDisabled();
    await expect(button).toHaveCSS('background-color', 'rgb(142, 151, 161)');
    await input.pressSequentially('   ');
    await expect(button).toBeDisabled();
    await page.evaluate(() => {
      window.crmClicks = 0; window.crmKeys = [];
      document.querySelector('#crm').onclick = () => window.crmClicks++;
      for (const type of ['keydown', 'keypress', 'keyup']) {
        document.addEventListener(type, (event) => window.crmKeys.push(event.key));
      }
    });
    await input.press('Control+A');
    await input.pressSequentially('задержался');
    await input.press('Enter');
    await input.pressSequentially('на встрече');
    await expect(input).toHaveValue('задержался\nна встрече');
    await expect(button).toBeEnabled();
    await expect(button).toHaveCSS('background-color', 'rgb(36, 105, 168)');
    expect(await page.evaluate(() => window.crmKeys)).toEqual([]);
    await page.keyboard.press('Tab');
    await expect(button).toBeFocused();
    await page.keyboard.press('Shift+Tab');
    await expect(input).toBeFocused();
    const crmBounds = await page.locator('#crm').boundingBox();
    await page.mouse.click(crmBounds.x + 3, crmBounds.y + 3);
    expect(await page.evaluate(() => window.crmClicks)).toBe(0);
    await input.fill('');
    await input.pressSequentially('x'.repeat(1001));
    await expect(input).toHaveValue('x'.repeat(1000));
    await expect(page.locator('.timesheet-overlay__reason-count')).toHaveText('1000 / 1000');
    const literal = '<img src=x onerror="window.injected=true"> & <script>alert(1)</script>';
    await input.fill('  ' + literal + '  ');
    await page.evaluate(async () => window.widget.timesheetController.load());
    await expect(input).toHaveValue('  ' + literal + '  ');
    await expect(page.locator('.timesheet-overlay img, .timesheet-overlay script')).toHaveCount(0);
    expect(await page.evaluate(() => window.injected)).toBeUndefined();
    await input.focus(); await page.keyboard.press('Tab'); await page.keyboard.press('Enter');
    await expect.poll(() => page.evaluate(() => window.calls.filter((call) => call.method === 'POST' &&
      /\/timesheet\//.test(call.url)).length)).toBe(1);
    const posted = await page.evaluate(() => window.calls.find((call) => call.method === 'POST' && /\/timesheet\//.test(call.url)));
    expect(posted.url).toBe('https://api.test/api/v1/' + 'timesheet/' + action);
    expect(JSON.parse(posted.data).reason).toBe(literal);
  });

  test(`${status}: same-event refresh preserves editing focus, selection, scroll and focused action`, async ({ page }) => {
    await page.clock.install();
    await boot(page, (route) => route.fulfill({ contentType: 'text/css', body: css }), 'employee', status,
      { late_reason_required: true, late_reason_kind: kind, late_minutes: 8, break_sequence: sequence });
    const input = page.getByRole('textbox', { name: 'Причина опоздания' });
    const button = page.getByRole('button', { name: label, exact: true });
    const draft = 'alpha beta\n' + 'another line\n'.repeat(30);
    await input.fill(draft);
    const editing = await input.evaluate((node) => {
      node.setSelectionRange(2, 7, 'backward');
      node.scrollTop = 50;
      return { start: node.selectionStart, end: node.selectionEnd, direction: node.selectionDirection, top: node.scrollTop };
    });
    await page.evaluate(() => {
      const original = window.widget.$authorizedAjax;
      window.widget.$authorizedAjax = (request) => Promise.resolve(original(request)).then((snapshot) =>
        request.url.includes('/timesheet/my-status') ? { ...snapshot, late_minutes: 9 } : snapshot);
    });
    await page.clock.runFor(30000);
    await expect(page.locator('.timesheet-overlay__message')).toContainText('9 мин.');
    await expect(input).toBeFocused();
    expect(await input.evaluate((node) => ({ start: node.selectionStart, end: node.selectionEnd,
      direction: node.selectionDirection, top: node.scrollTop }))).toEqual(editing);
    await input.evaluate((node) => node.setSelectionRange(5, 5));
    await page.evaluate(() => window.dispatchEvent(new Event('focus')));
    await expect.poll(() => page.evaluate(() => window.calls.filter((call) => call.url.includes('/timesheet/my-status')).length)).toBe(3);
    await expect(input).toBeFocused();
    await input.pressSequentially(' INSERTED');
    await expect(input).toHaveValue('alpha INSERTED beta\n' + 'another line\n'.repeat(30));
    await button.focus();
    await page.evaluate(async () => window.widget.timesheetController.load());
    await expect(button).toBeFocused();
    const monitoring = page.locator('.ts-monitoring-widget__launcher');
    await monitoring.focus();
    await page.evaluate(async () => window.widget.timesheetController.load());
    await expect(monitoring).toBeFocused();
    const oldInput = await input.elementHandle();
    await page.evaluate(() => window.widget.callbacks.destroy());
    expect(await oldInput.evaluate((node) => ({ value: node.value, focused: document.activeElement === node,
      connected: node.isConnected }))).toEqual({ value: '', focused: false, connected: false });
  });
}

test('admin report launcher opens its own panel and leaves native CRM content intact', async ({ page }) => {
  await boot(page, (route) => route.fulfill({ contentType: 'text/css', body: css }), 'admin', 'working');
  const launcher = page.locator('.ts-reports-widget__launcher');
  await expect(launcher).toHaveCount(1);
  await expect(launcher).toHaveText('Табель');
  await expect(launcher).toHaveAttribute('aria-expanded', 'false');
  const panelId = await launcher.getAttribute('aria-controls');
  expect(panelId).toBeTruthy();
  await expect(page.locator(`#${panelId}.ts-reports-widget__panel`)).toHaveCount(1);
  await launcher.click();
  await expect(launcher).toHaveAttribute('aria-expanded', 'true');
  await expect(page.locator('.ts-reports__title')).toBeVisible();
  await expect(page.locator('.ts-reports-widget__panel')).toHaveCSS('background-color', 'rgb(255, 255, 255)');
  await page.evaluate(() => window.widget.callbacks.destroy());
  await expect(page.locator('.ts-reports-widget, link[href*="reports/styles.css"]')).toHaveCount(0);
  await expect(page.locator('#crm')).toHaveCount(1);
});

test('employee receives no report launcher or panel', async ({ page }) => {
  await boot(page, (route) => route.fulfill({ contentType: 'text/css', body: css }));
  await expect(page.locator('.timesheet-overlay')).toHaveCount(1);
  await expect(page.locator('.ts-reports-widget')).toHaveCount(0);
  await expect(page.locator('link[href*="reports/styles.css"]')).toHaveCount(0);
});

test('settings sidebar opens the full report page for an admin', async ({ page }) => {
  await boot(page, (route) => route.fulfill({ contentType: 'text/css', body: css }), 'admin', 'working');
  await page.evaluate(() => { window.area = 'advanced_settings'; window.widget.callbacks.advancedSettings(); });
  await expect(page.locator('.ts-reports-page .ts-reports__title')).toHaveText('Табель');
  await expect(page.locator('.ts-reports-page .ts-reports__controls')).toBeVisible();
  await expect(page.locator('.ts-reports-page .ts-reports__export')).toBeEnabled();
  await expect(page.locator('.ts-reports-widget__launcher')).toHaveCount(0);
  expect(await page.evaluate(() => window.calls.filter((call) => call.url.includes('/team/status')).length)).toBeGreaterThan(0);
  expect(await page.evaluate(() => window.calls.filter((call) => call.url.includes('/reports/detailed')).length)).toBeGreaterThan(0);
});

test('settings sidebar keeps the report page but denies an employee', async ({ page }) => {
  await boot(page, (route) => route.fulfill({ contentType: 'text/css', body: css }), 'employee', 'working');
  await page.evaluate(() => { window.area = 'advanced_settings'; window.widget.callbacks.advancedSettings(); });
  await expect(page.locator('.ts-reports-page')).toContainText('У вас нет доступа к этому разделу.');
  await expect(page.locator('.ts-reports__export')).toHaveCount(0);
  expect(await page.evaluate(() => window.calls.filter((call) => call.url.includes('/reports/detailed')).length)).toBe(0);
});

test('widget init loads versioned CSS before real blocking UI and removes it on destroy', async ({ page }) => {
  let release;
  const ready = new Promise((resolve) => { release = resolve; });
  await boot(page, async (route) => { await ready; await route.fulfill({ contentType: 'text/css', body: css }); });
  await expect(page.locator('link[href="https://widget.test/assets/styles.css?v=3.0.2"]')).toHaveCount(1);
  await expect(page.locator('.timesheet-overlay')).toHaveCount(0);
  expect(await page.evaluate(() => window.calls.length)).toBe(0);
  release();
  await expect(page.locator('.timesheet-overlay')).toHaveCount(1);
  await expect(page.locator('.timesheet-overlay')).toHaveCSS('position', 'fixed');
  await page.evaluate(() => { window.crmClicks = 0; document.querySelector('#crm').onclick = () => window.crmClicks++; });
  const bounds = await page.locator('#crm').boundingBox();
  await page.mouse.click(bounds.x + 3, bounds.y + 3);
  expect(await page.evaluate(() => window.crmClicks)).toBe(0);
  await page.evaluate(() => window.widget.callbacks.destroy());
  await expect(page.locator('.timesheet-overlay, link[href*="/styles.css"]')).toHaveCount(0);
});

test('stylesheet failure stays fail-open without buttons or requests', async ({ page }) => {
  await boot(page, (route) => route.abort());
  await expect(page.locator('.timesheet-overlay, .timesheet-actions')).toHaveCount(0);
  await expect.poll(() => page.evaluate(() => window.widget.timesheetController)).toBeNull();
  expect(await page.evaluate(() => window.calls.length)).toBe(0);
});

for (const entry of ['settings-init', 'advanced_settings-init', 'settings', 'advancedSettings']) {
  test(`reused widget clears working resources on ${entry}`, async ({ page }) => {
    await boot(page, (route) => route.fulfill({ contentType: 'text/css', body: css }));
    await expect(page.locator('.timesheet-overlay')).toHaveCount(1);
    await page.evaluate((entry) => {
      window.area = entry.startsWith('settings') ? 'settings' : 'advanced_settings';
      window.widget.callbacks[entry.endsWith('-init') ? 'init' : entry]();
      window.dispatchEvent(new Event('focus'));
    }, entry);
    await expect(page.locator('.timesheet-overlay, .timesheet-action')).toHaveCount(0);
    if (entry === 'advancedSettings') {
      await expect(page.locator('.ts-reports-page, link[href*="reports/styles.css"]')).toHaveCount(2);
    } else {
      await expect(page.locator('link[href*="/styles.css"]')).toHaveCount(0);
    }
    expect(await page.evaluate(() => window.widget.timesheetController === null && window.widget.removeFocusRefresh === null)).toBe(true);
    expect(await page.evaluate(() => window.calls.filter((call) => call.url.includes('/timesheet/')).length)).toBe(1);
  });
}
