const { test, expect } = require('@playwright/test');
const { readFileSync } = require('node:fs');
const { resolve } = require('node:path');

test.use({ channel: 'chrome' });

const sources = ['timeline.js', 'activity-modal.js', 'dashboard.js']
  .map((name) => readFileSync(resolve(__dirname, '../monitoring', name), 'utf8'));
const css = readFileSync(resolve(__dirname, '../monitoring/styles.css'), 'utf8');

async function loadMonitoring(page) {
  await page.setContent('<main id="root"></main>');
  await page.addStyleTag({ content: css });
  for (const source of sources) await page.addScriptTag({ content: source });
}

test('admin dashboard renders seven-day activity, safe tooltip, gaps, zoom, fullscreen and Escape', async ({ page }) => {
  await loadMonitoring(page);
  await page.evaluate(() => {
    window.fetch = () => { throw new Error('direct fetch is forbidden'); };
    window.transportCalls = [];
    const employees = [
      { id: 2, amocrm_user_id: 102, account_id: 1, name: 'Анна', avatar_url: null, group_id: 10,
        group_name: 'Продажи', timezone: 'Europe/Moscow', workday_started_at: '2026-09-29T06:00:00Z',
        workday_ended_at: '2026-09-29T15:00:00Z', status: 'working', status_since: '2026-09-29T06:00:00Z',
        session_started_at: '2026-09-29T06:00:00Z', session_ended_at: null, work_seconds: 3600,
        break_seconds: 60, confirmed_seconds: 1800, confirmed_events: 1, activity_detail_allowed: true },
      { id: 3, amocrm_user_id: 103, account_id: 1, name: 'Борис', avatar_url: null, group_id: 20,
        group_name: 'Поддержка', timezone: 'Europe/Moscow', workday_started_at: '2026-09-29T06:00:00Z',
        workday_ended_at: '2026-09-29T15:00:00Z', status: 'not_started', status_since: null,
        session_started_at: null, session_ended_at: null, work_seconds: 0,
        break_seconds: 0, confirmed_seconds: 0, confirmed_events: 0, activity_detail_allowed: false },
    ];
    const status = { generated_at: '2026-09-29T09:00:00Z', viewer: { role: 'admin', can_view_activity: true },
      groups: [{ id: 10, name: 'Продажи' }, { id: 20, name: 'Поддержка' }], employees,
      totals: { employees: 2, working: 1, on_break: 0, finished: 0, not_started: 1 } };
    const days = Array.from({ length: 7 }, (_, index) => {
      const day = String(23 + index).padStart(2, '0');
      const next = String(24 + index).padStart(2, '0');
      return { date: `2026-09-${day}`, started_at: `2026-09-${day}T00:00:00Z`, ended_at: `2026-09-${next}T00:00:00Z`,
        shift_started_at: `2026-09-${day}T06:00:00Z`, shift_ended_at: `2026-09-${day}T15:00:00Z`,
        confirmed_seconds: index === 0 ? 1800 : 0, confirmed_events: index === 0 ? 1 : 0, unconfirmed_seconds: 0,
        intervals: index === 0 ? [{ id: 1, started_at: `2026-09-${day}T08:00:00Z`, ended_at: `2026-09-${day}T08:30:00Z`,
          duration_seconds: 1800, kind: 'confirmed', source: 'crm_event', duration_source: 'calculated',
          event_type: 'lead_status_changed', object_type: 'lead', object_id: 42, description: '<b>Сделка</b>',
          card_url: 'https://example.amocrm.ru/leads/detail/42', call_direction: null, call_duration_seconds: null, message: null }] : [] };
    });
    const transport = {
      status(params) { window.transportCalls.push({ kind: 'status', params }); return Promise.resolve(status); },
      activity(userId, from, to) {
        window.transportCalls.push({ kind: 'activity', userId, from, to });
        return Promise.resolve({ target: employees[0], group: { id: 10, name: 'Продажи' }, timezone: 'Europe/Moscow',
          from, to, totals: { confirmed_seconds: 1800, confirmed_events: 1, unconfirmed_seconds: 0 }, days });
      },
    };
    window.dashboard = TimesheetMonitoringDashboard.mount(document.querySelector('#root'), {
      document, transport, now: () => new Date('2026-09-29T12:00:00Z'), random: () => 0.5,
    });
  });

  await expect(page.locator('.ts-monitoring__group-title')).toHaveText(['Продажи', 'Поддержка']);
  await expect(page.locator('[data-activity-user-id]')).toHaveCount(1);
  await page.locator('[data-activity-user-id="2"]').click();
  await expect(page.locator('.ts-activity-modal__day')).toHaveCount(7);
  const segment = page.locator('.ts-timeline__item--confirmed');
  await expect(segment).toHaveCount(1);
  expect(await segment.evaluate((node) => parseFloat(node.style.left))).toBeGreaterThan(0);
  await segment.hover();
  await expect(page.locator('.ts-timeline__tooltip')).toContainText('<b>Сделка</b>');
  await expect(page.locator('.ts-timeline__tooltip b')).toHaveCount(0);
  const widthBefore = await page.locator('.ts-timeline__track').first().evaluate((node) => parseFloat(node.style.width));
  await page.locator('[data-zoom="4"]').click();
  const widthAfter = await page.locator('.ts-timeline__track').first().evaluate((node) => parseFloat(node.style.width));
  expect(widthAfter).toBe(widthBefore * 4);
  await page.locator('.ts-activity-modal__fullscreen').click();
  await expect(page.locator('.ts-activity-modal__fullscreen')).toHaveAttribute('aria-pressed', 'true');
  await page.keyboard.press('Escape');
  await expect(page.locator('.ts-activity-modal')).toBeHidden();
  expect(await page.evaluate(() => window.transportCalls.find((call) => call.kind === 'activity')))
    .toMatchObject({ userId: 2, from: '2026-09-23', to: '2026-09-29' });
});

test('server-scoped manager and employee views render only delivered rows and permissions', async ({ page }) => {
  await loadMonitoring(page);
  const result = await page.evaluate(async () => {
    function employee(id, name, allowed) {
      return { id, amocrm_user_id: 100 + id, account_id: 1, name, avatar_url: null, group_id: 10, group_name: 'Продажи',
        timezone: 'Europe/Moscow', workday_started_at: '2026-09-29T06:00:00Z', workday_ended_at: '2026-09-29T15:00:00Z',
        status: 'working', status_since: null, session_started_at: null, session_ended_at: null, work_seconds: 0,
        break_seconds: 0, confirmed_seconds: 0, confirmed_events: 0, activity_detail_allowed: allowed };
    }
    async function render(role, employees) {
      const root = document.querySelector('#root'); root.replaceChildren();
      const dashboard = TimesheetMonitoringDashboard.mount(root, { document,
        transport: { status: () => Promise.resolve({ generated_at: '2026-09-29T09:00:00Z',
          viewer: { role, can_view_activity: role !== 'employee' }, groups: [{ id: 10, name: 'Продажи' }], employees,
          totals: { employees: employees.length, working: employees.length, on_break: 0, finished: 0, not_started: 0 } }),
          activity: () => Promise.reject(new Error('not used')) },
        now: () => new Date('2026-09-29T12:00:00Z'), random: () => 0.5 } );
      await dashboard.ready;
      const snapshot = { names: Array.from(root.querySelectorAll('.ts-monitoring__name'), (node) => node.textContent),
        buttons: root.querySelectorAll('[data-activity-user-id]').length };
      dashboard.destroy(); return snapshot;
    }
    return { manager: await render('manager', [employee(1, 'Руководитель', false), employee(2, 'Анна', true)]),
      employee: await render('employee', [employee(3, 'Борис', false)]) };
  });
  expect(result.manager).toEqual({ names: ['Руководитель', 'Анна'], buttons: 1 });
  expect(result.employee).toEqual({ names: ['Борис'], buttons: 0 });
});

test('filters and manual refresh stay inside the injected authorized transport', async ({ page }) => {
  await loadMonitoring(page);
  await page.evaluate(() => {
    window.calls = [];
    const response = { generated_at: '2026-09-29T09:00:00Z', viewer: { role: 'admin', can_view_activity: true },
      groups: [{ id: 10, name: 'Продажи' }], employees: [],
      totals: { employees: 0, working: 0, on_break: 0, finished: 0, not_started: 0 } };
    window.dashboard = TimesheetMonitoringDashboard.mount(document.querySelector('#root'), { document,
      transport: { status: (params) => { window.calls.push(params); return Promise.resolve(response); },
        activity: () => Promise.reject(new Error('not used')) }, random: () => 0.5 });
  });
  await expect(page.locator('.ts-monitoring__empty')).toBeVisible();
  await page.locator('[data-filter="search"]').fill('Анна');
  await page.locator('[data-filter="search"]').dispatchEvent('change');
  await page.locator('[data-filter="status"]').selectOption('working');
  await page.locator('[data-filter="group"]').selectOption('10');
  await page.locator('[data-action="refresh"]').click();
  await expect.poll(() => page.evaluate(() => window.calls.at(-1))).toEqual({ search: 'Анна', status: 'working', group_id: 10 });
});

test('browser polling preserves selected employee and zoom, then applies bounded failure backoff', async ({ page }) => {
  await loadMonitoring(page);
  await page.evaluate(() => {
    window.pollJobs = [];
    window.statusCalls = 0;
    window.failStatus = false;
    function schedule(fn, delay) {
      const job = { delay, cancelled: false, run() { if (job.cancelled) return; job.cancelled = true; fn(); } };
      window.pollJobs.push(job);
      return () => { job.cancelled = true; };
    }
    function employee() {
      return { id: 2, amocrm_user_id: 102, account_id: 1, name: `Анна ${window.statusCalls}`, avatar_url: null,
        group_id: 10, group_name: 'Продажи', timezone: 'Europe/Moscow', workday_started_at: '2026-09-29T06:00:00Z',
        workday_ended_at: '2026-09-29T15:00:00Z', status: 'working', status_since: null,
        session_started_at: null, session_ended_at: null, work_seconds: 0, break_seconds: 0,
        confirmed_seconds: 0, confirmed_events: 0, activity_detail_allowed: true };
    }
    const days = Array.from({ length: 7 }, (_, index) => ({ date: `2026-09-${String(23 + index).padStart(2, '0')}`,
      started_at: `2026-09-${String(23 + index).padStart(2, '0')}T00:00:00Z`,
      ended_at: `2026-09-${String(24 + index).padStart(2, '0')}T00:00:00Z`,
      shift_started_at: null, shift_ended_at: null, confirmed_seconds: 0, confirmed_events: 0,
      unconfirmed_seconds: 0, intervals: [] }));
    const transport = {
      status() {
        window.statusCalls += 1;
        if (window.failStatus) return Promise.reject(new Error('offline'));
        const own = employee();
        return Promise.resolve({ generated_at: '2026-09-29T09:00:00Z', viewer: { role: 'admin', can_view_activity: true },
          groups: [{ id: 10, name: 'Продажи' }], employees: [own],
          totals: { employees: 1, working: 1, on_break: 0, finished: 0, not_started: 0 } });
      },
      activity(_id, from, to) {
        return Promise.resolve({ target: employee(), group: { id: 10, name: 'Продажи' }, timezone: 'Europe/Moscow',
          from, to, totals: { confirmed_seconds: 0, confirmed_events: 0, unconfirmed_seconds: 0 }, days });
      },
    };
    window.dashboard = TimesheetMonitoringDashboard.mount(document.querySelector('#root'), {
      document, transport, schedule, random: () => 0.5, now: () => new Date('2026-09-29T12:00:00Z'),
    });
  });
  await expect(page.locator('.ts-monitoring__name')).toHaveText('Анна 1');
  await page.locator('[data-activity-user-id="2"]').click();
  await page.locator('[data-zoom="4"]').click();
  expect(await page.evaluate(() => window.pollJobs.filter((job) => !job.cancelled).at(-1).delay)).toBe(30000);

  await page.evaluate(() => window.pollJobs.filter((job) => !job.cancelled).at(-1).run());
  await expect(page.locator('.ts-monitoring__name')).toHaveText('Анна 2');
  await expect(page.locator('.ts-activity-modal__title')).toHaveText('Анна 2');
  await expect(page.locator('[data-zoom="4"]')).toHaveAttribute('aria-pressed', 'true');

  await page.evaluate(() => { window.failStatus = true; window.pollJobs.filter((job) => !job.cancelled).at(-1).run(); });
  await expect(page.locator('.ts-monitoring__message')).toContainText('Не удалось обновить');
  expect(await page.evaluate(() => window.pollJobs.filter((job) => !job.cancelled).at(-1).delay)).toBe(30000);
  await page.evaluate(() => window.pollJobs.filter((job) => !job.cancelled).at(-1).run());
  await expect.poll(() => page.evaluate(() => window.pollJobs.filter((job) => !job.cancelled).at(-1).delay)).toBe(60000);
  await expect(page.locator('.ts-activity-modal__title')).toHaveText('Анна 2');
  await expect(page.locator('[data-zoom="4"]')).toHaveAttribute('aria-pressed', 'true');
});
