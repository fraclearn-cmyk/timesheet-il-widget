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

async function boot(page, options = {}) {
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
  await page.evaluate(({ code, setup }) => {
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

    let timerSequence = 0;
    const timers = new Map();
    window.setTimeout = (callback, delay) => {
      const id = ++timerSequence;
      timers.set(id, { callback, delay });
      return id;
    };
    window.clearTimeout = (id) => timers.delete(id);
    window.appTimers = timers;
    window.acceptanceSetup = setup;
    window.calls = [];
    window.backendUp = setup.backendUp !== false;
    window.timesheet = {
      session_id: null,
      status: setup.status || 'not_started',
      started_at: null,
      ended_at: null,
      break_seconds: 0,
      track_time: setup.trackTime !== false,
      hide_widget: setup.hideWidget === true,
      restart_allowed: setup.restartAllowed === true,
    };

    const employee = (id, name, allowed, reportAllowed = allowed) => ({
      id,
      amocrm_user_id: 1000 + id,
      account_id: 1,
      name,
      avatar_url: null,
      group_id: 10,
      group_name: 'Продажи',
      timezone: 'Europe/Moscow',
      workday_started_at: '2026-10-01T06:00:00Z',
      workday_ended_at: '2026-10-01T15:00:00Z',
      status: 'working',
      status_since: '2026-10-01T06:00:00Z',
      session_started_at: '2026-10-01T06:00:00Z',
      session_ended_at: null,
      work_seconds: 3600,
      break_seconds: 0,
      confirmed_seconds: 600,
      confirmed_events: 1,
      activity_detail_allowed: allowed,
      report_filter_allowed: reportAllowed,
    });
    window.teamStatus = {
      generated_at: '2026-10-01T09:00:00Z',
      viewer: { role: setup.role || 'employee', can_view_activity: setup.role !== 'employee' },
      groups: [{ id: 10, name: 'Продажи' }],
      employees: setup.role === 'manager'
        ? [employee(1, 'Руководитель', false, false), employee(2, 'Анна', true, true)]
        : setup.role === 'admin'
          ? [employee(1, 'Руководитель', true, true), employee(2, 'Анна', true, true)]
          : [employee(2, 'Анна', false, false)],
      totals: { employees: 2, working: 2, on_break: 0, finished: 0, not_started: 0 },
    };

    window.widget = new window.Widget();
    window.widget.system = () => ({ area: 'lcard' });
    window.widget.get_settings = () => ({
      api_url: 'https://api.test/api/v1/',
      path: 'https://widget.test/assets/',
      version: '3.0.2',
    });
    window.widget.$authorizedAjax = (request) => {
      window.calls.push({ url: request.url, method: request.method, data: request.data });
      if (request.url.includes('/activity/presence')) return Promise.resolve({ accepted: true });
      if (request.url.includes('/timesheet/')) {
        if (!window.backendUp) return Promise.reject(new Error('offline'));
        const action = request.url.split('/').at(-1);
        if (request.method === 'POST') {
          if (action === 'start-work') {
            window.timesheet = {
              ...window.timesheet,
              session_id: (window.timesheet.session_id || 0) + 1,
              status: 'working',
              started_at: '2026-10-01T09:00:00Z',
              ended_at: null,
              restart_allowed: false,
            };
          } else if (action === 'start-break') {
            window.timesheet = { ...window.timesheet, status: 'on_break' };
          } else if (action === 'end-break') {
            window.timesheet = { ...window.timesheet, status: 'working', break_seconds: 300 };
          } else if (action === 'finish-work') {
            window.timesheet = {
              ...window.timesheet,
              status: 'finished',
              ended_at: '2026-10-01T18:00:00Z',
              restart_allowed: true,
            };
          }
        }
        return Promise.resolve({ ...window.timesheet });
      }
      if (request.url.includes('/team/999/activity')) {
        return Promise.reject({ status: 403, responseJSON: { error: { code: 'FORBIDDEN' } } });
      }
      if (/\/team\/\d+\/activity/.test(request.url)) {
        return Promise.resolve({
          target: window.teamStatus.employees.find((item) => request.url.includes(`/team/${item.id}/`)),
          group: { id: 10, name: 'Продажи' },
          timezone: 'Europe/Moscow',
          from: '2026-09-25',
          to: '2026-10-01',
          totals: { confirmed_seconds: 0, confirmed_events: 0, unconfirmed_seconds: 0 },
          days: [],
        });
      }
      if (request.url.includes('/team/status')) return Promise.resolve(window.teamStatus);
      if (request.url.includes('/reports/detailed')) {
        return Promise.resolve({ items: [], page: 1, page_size: 10, total: 0, total_pages: 0 });
      }
      throw new Error(`Unexpected request: ${request.url}`);
    };
    window.widget.callbacks.init();
  }, { code: sources, setup: options });
}

async function clickAction(page, action) {
  await page.locator(`[data-action="${action}"]`).click();
  await expect.poll(() => page.evaluate(() => window.timesheet.status)).not.toBe('');
}

test('employee hidden state becomes a full permitted workday flow and survives a clean recovery', async ({ page }) => {
  await boot(page, { role: 'employee', hideWidget: true });
  await expect(page.locator('.timesheet-overlay, .timesheet-actions')).toHaveCount(0);

  await page.evaluate(() => {
    window.timesheet.hide_widget = false;
    window.dispatchEvent(new Event('focus'));
  });
  await expect(page.locator('[data-action="start-work"]')).toHaveText('Начать рабочий день');
  await clickAction(page, 'start-work');
  await expect(page.locator('.timesheet-actions')).toHaveCount(1);
  await expect(page.locator('[data-action="start-break"]')).toHaveText('Перерыв');

  await clickAction(page, 'start-break');
  await expect(page.locator('[data-action="end-break"]')).toHaveText('Продолжить');
  await clickAction(page, 'end-break');
  await expect(page.locator('.timesheet-actions')).toHaveCount(1);
  await clickAction(page, 'finish-work');
  await expect(page.locator('[data-action="start-work"]')).toHaveText('Начать рабочий день');
  await clickAction(page, 'start-work');
  await expect(page.locator('.timesheet-actions')).toHaveCount(1);
  expect(await page.evaluate(() => window.calls
    .filter((call) => call.method === 'POST' && call.url.includes('/timesheet/'))
    .map((call) => call.url.split('/').at(-1))))
    .toEqual(['start-work', 'start-break', 'end-break', 'finish-work', 'start-work']);

  await page.evaluate(() => window.widget.callbacks.destroy());
  await expect(page.locator(
    '.timesheet-overlay, .timesheet-actions, .ts-monitoring-widget, .ts-reports-widget, link[href*="/styles.css"]',
  )).toHaveCount(0);
  await page.evaluate(() => {
    window.backendUp = false;
    window.widget.callbacks.init();
  });
  await expect(page.locator('.timesheet-overlay, .timesheet-actions')).toHaveCount(0);
  await expect.poll(() => page.evaluate(() => [...window.appTimers.values()]
    .filter((timer) => timer.delay === 5000).length)).toBe(1);

  await page.evaluate(() => {
    window.backendUp = true;
    const retry = [...window.appTimers.entries()].find(([, timer]) => timer.delay === 5000);
    window.appTimers.delete(retry[0]);
    retry[1].callback();
  });
  await expect(page.locator('.timesheet-actions')).toHaveCount(1);
  await expect(page.locator('.timesheet-overlay')).toHaveCount(0);
});

test('manager and admin affordances use server scope while a foreign resource remains forbidden', async ({ page }) => {
  await boot(page, { role: 'manager', status: 'working' });
  await page.locator('.ts-monitoring-widget__launcher').click();
  await expect(page.locator('.ts-monitoring__name')).toHaveText(['Руководитель', 'Анна']);
  await expect(page.locator('[data-activity-user-id]')).toHaveCount(1);
  await expect(page.locator('[data-activity-user-id="2"]')).toHaveCount(1);
  await expect(page.locator('.ts-reports-widget__launcher')).toHaveCount(1);
  await page.locator('.ts-reports-widget__launcher').click();
  await expect(page.locator('.ts-reports__employee option')).toHaveText(['Все сотрудники', 'Анна']);

  const denial = await page.evaluate(async () => {
    try {
      await window.widget.$authorizedAjax({
        url: 'https://api.test/api/v1/team/999/activity', method: 'GET', dataType: 'json',
      });
      return null;
    } catch (error) {
      return { status: error.status, code: error.responseJSON.error.code };
    }
  });
  expect(denial).toEqual({ status: 403, code: 'FORBIDDEN' });
  await expect(page.locator('[data-activity-user-id="999"]')).toHaveCount(0);

  await page.evaluate(() => {
    window.widget.callbacks.destroy();
    window.teamStatus.viewer = { role: 'admin', can_view_activity: true };
    window.teamStatus.employees.forEach((employee) => {
      employee.activity_detail_allowed = true;
      employee.report_filter_allowed = true;
    });
    window.widget.callbacks.init();
  });
  await expect(page.locator('.ts-monitoring-widget')).toHaveCount(1);
  await expect(page.locator('.ts-reports-widget__launcher')).toHaveCount(1);
  await page.locator('.ts-monitoring-widget__launcher').click();
  await expect(page.locator('[data-activity-user-id]')).toHaveCount(2);
});
