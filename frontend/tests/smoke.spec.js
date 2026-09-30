const { test, expect } = require('@playwright/test');
const { readFileSync } = require('node:fs');
const { resolve } = require('node:path');

test.use({ channel: 'chrome' });

const sources = Object.fromEntries([
  ['settings', 'frontend/settings/settings.js'],
  ['controller', 'widget/timesheet/controller.js'],
  ['overlay', 'widget/overlay.js'],
  ['tracker', 'widget/activity-tracker.js'],
  ['timeline', 'frontend/monitoring/timeline.js'],
  ['modal', 'frontend/monitoring/activity-modal.js'],
  ['dashboard', 'frontend/monitoring/dashboard.js'],
  ['reports', 'frontend/reports/controller.js'],
  ['widget', 'widget/script.js'],
].map(([key, file]) => [
  key,
  readFileSync(resolve(__dirname, '../..', file), 'utf8'),
]));

const css = {
  working: readFileSync(resolve(__dirname, '../../widget/styles.css'), 'utf8'),
  monitoring: readFileSync(resolve(__dirname, '../monitoring/styles.css'), 'utf8'),
  reports: readFileSync(resolve(__dirname, '../reports/styles.css'), 'utf8'),
};

async function boot(page) {
  await page.route('https://widget.test/**', async (route) => {
    const url = route.request().url();
    if (url.includes('/monitoring/styles.css')) {
      return route.fulfill({ contentType: 'text/css', body: css.monitoring });
    }
    if (url.includes('/reports/styles.css')) {
      return route.fulfill({ contentType: 'text/css', body: css.reports });
    }
    if (url.includes('/styles.css')) {
      return route.fulfill({ contentType: 'text/css', body: css.working });
    }
    return route.fulfill({
      contentType: 'text/html',
      body: '<button id="crm">CRM</button><div id="list_page_holder"></div>',
    });
  });
  await page.goto('https://widget.test/');
  await page.evaluate(({ code }) => {
    const modules = {};
    for (const name of ['settings', 'controller', 'overlay', 'tracker']) {
      window.define = (factory) => { modules[name] = factory(); };
      window.define.amd = {};
      (0, eval)(code[name]);
    }
    window.define = (_ids, factory) => { modules.timeline = factory(); };
    window.define.amd = {};
    (0, eval)(code.timeline);
    window.define = (_ids, factory) => { modules.modal = factory(modules.timeline); };
    window.define.amd = {};
    (0, eval)(code.modal);
    window.define = (_ids, factory) => { modules.dashboard = factory(modules.modal); };
    window.define.amd = {};
    (0, eval)(code.dashboard);
    window.define = (_ids, factory) => { modules.reports = factory(); };
    window.define.amd = {};
    (0, eval)(code.reports);
    window.define = (_ids, factory) => {
      window.Widget = factory(
        {}, modules.settings, modules.controller, modules.overlay, modules.tracker,
        modules.timeline, modules.modal, modules.dashboard, modules.reports,
      );
    };
    (0, eval)(code.widget);

    // Application timers are held by the test. This proves retry scheduling
    // without sleeping and prevents a hidden tight retry loop from looking green.
    let timerSequence = 0;
    const timers = new Map();
    window.setTimeout = (callback, delay) => {
      const id = ++timerSequence;
      timers.set(id, { callback, delay });
      return id;
    };
    window.clearTimeout = (id) => timers.delete(id);
    window.appTimers = timers;

    const requestId = '123e4567-e89b-42d3-a456-426614174000';
    window.backendUp = false;
    window.reportAvailable = false;
    window.calls = [];
    window.widget = new window.Widget();
    window.widget.system = () => ({ area: 'lcard' });
    window.widget.get_settings = () => ({
      api_url: 'https://api.test/api/v1/',
      path: 'https://widget.test/assets/',
      version: '3.0.2',
    });
    window.widget.$authorizedAjax = (request) => {
      window.calls.push(request.url);
      if (!window.backendUp) return Promise.reject(new Error('private network failure'));
      if (request.url.includes('/team/status')) {
        return Promise.resolve({
          generated_at: '2026-09-30T12:00:00Z',
          viewer: { role: 'admin', can_view_activity: true },
          groups: [], employees: [],
          totals: { employees: 0, working: 0, on_break: 0, finished: 0, not_started: 0 },
        });
      }
      if (request.url.includes('/reports/detailed') && !window.reportAvailable) {
        return Promise.reject({
          message: 'private database details',
          responseText: 'private stack and token',
          responseJSON: { error: {
            code: 'INTERNAL_ERROR',
            message: 'Сервис временно недоступен. Повторите попытку позже.',
            request_id: requestId,
          } },
        });
      }
      if (request.url.includes('/reports/detailed')) {
        return Promise.resolve({ items: [], page: 1, page_size: 10, total: 0, total_pages: 0 });
      }
      return Promise.resolve({
        session_id: 7, status: 'working', started_at: '2026-09-30T08:00:00Z',
        ended_at: null, break_seconds: 0, track_time: true,
        hide_widget: false, restart_allowed: false,
      });
    };
    window.widget.callbacks.init();
  }, { code: sources });
}

test('backend outage recovers without false work state, leaks or lifecycle duplication', async ({ page }) => {
  await boot(page);

  await expect(page.locator('.timesheet-overlay, .timesheet-action')).toHaveCount(0);
  await expect(page.locator('.ts-monitoring__message')).toHaveText(
    'Не удалось обновить список. Попробуем ещё раз автоматически.',
  );
  expect(await page.evaluate(() => window.calls.filter((url) => url.includes('/timesheet/')).length)).toBe(1);
  await expect.poll(() => page.evaluate(() => {
    const delays = [...window.appTimers.values()].map((timer) => timer.delay);
    return {
      count: delays.length,
      timesheetRetries: delays.filter((delay) => delay === 5000).length,
      monitoringRetries: delays.filter((delay) => delay >= 27000 && delay <= 33000).length,
    };
  })).toEqual({ count: 2, timesheetRetries: 1, monitoringRetries: 1 });

  await page.evaluate(() => {
    window.backendUp = true;
    const retries = [...window.appTimers.entries()];
    for (const [id, timer] of retries) {
      window.appTimers.delete(id);
      timer.callback();
    }
  });
  await expect(page.locator('.timesheet-actions')).toHaveCount(1);
  await expect(page.locator('.timesheet-action')).toHaveCount(2);
  await expect(page.locator('.ts-monitoring__message')).toHaveText('');

  // Remount asks the recovered backend for role/report data. The report's safe
  // server message and correlation ID are useful; private transport text is not.
  await page.evaluate(() => window.widget.callbacks.init());
  await page.evaluate(() => window.widget.workingStyle.dispatchEvent(new Event('load')));
  await expect(page.locator('.ts-reports-widget__launcher')).toHaveCount(1);
  await page.locator('.ts-reports-widget__launcher').click();
  await expect(page.locator('.ts-reports__message')).toContainText(
    'Сервис временно недоступен. Повторите попытку позже.',
  );
  await expect(page.locator('.ts-reports__message')).toContainText(
    'Код обращения: 123e4567-e89b-42d3-a456-426614174000',
  );
  await expect(page.locator('body')).not.toContainText(/private database|private stack|token/);

  await page.evaluate(() => {
    window.reportAvailable = true;
    document.querySelector('.ts-reports__retry').click();
  });
  await expect(page.locator('.ts-reports__message')).toHaveText(
    'За выбранный период данных нет.',
  );

  await page.evaluate(() => window.widget.callbacks.destroy());
  await expect(page.locator(
    '.timesheet-overlay, .timesheet-action, .ts-monitoring-widget, .ts-reports-widget, link[href*="/styles.css"]',
  )).toHaveCount(0);
  await expect(page.locator('#crm')).toHaveCount(1);

  await page.evaluate(() => window.widget.callbacks.init());
  await page.evaluate(() => window.widget.workingStyle.dispatchEvent(new Event('load')));
  await expect(page.locator('.timesheet-actions')).toHaveCount(1);
  await expect(page.locator('.ts-monitoring-widget')).toHaveCount(1);
  await expect(page.locator('.ts-reports-widget')).toHaveCount(1);
});
