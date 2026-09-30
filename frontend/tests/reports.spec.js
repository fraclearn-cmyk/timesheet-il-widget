const { test, expect } = require('@playwright/test');
const { readFileSync } = require('node:fs');
const { resolve } = require('node:path');

test.use({ channel: 'chrome' });

const source = readFileSync(resolve(__dirname, '../reports/controller.js'), 'utf8');
const css = readFileSync(resolve(__dirname, '../reports/styles.css'), 'utf8');

async function boot(page, role = 'admin') {
  await page.setContent('<main id="root"></main>');
  await page.addStyleTag({ content: css });
  await page.addScriptTag({ content: source });
  await page.evaluate((viewerRole) => {
    window.fetch = () => { throw new Error('direct fetch forbidden'); };
    window.reportCalls = []; window.exportCalls = []; window.downloads = []; window.revocations = [];
    window.reportMode = 'normal'; window.exportMode = 'normal';
    URL.createObjectURL = () => 'blob:report-test';
    URL.revokeObjectURL = (url) => window.revocations.push(url);
    HTMLAnchorElement.prototype.click = function () {
      window.downloads.push({ filename: this.download, href: this.href, attached: document.body.contains(this) });
    };
    const directory = { generated_at: '2026-09-29T09:00:00Z', viewer: { role: viewerRole, can_view_activity: false },
      groups: [{ id: 10, name: 'Продажи' }, { id: 20, name: 'Поддержка' }],
      employees: [{ id: 2, name: 'Анна', group_id: 10, report_filter_allowed: true },
        { id: 3, name: 'Борис', group_id: 20, report_filter_allowed: false }],
      totals: { employees: 2, working: 1, on_break: 0, finished: 1, not_started: 0 } };
    const row = (index) => ({ user_id: index + 1, amocrm_user_id: index + 101, employee_name: index === 0 ? '<b>Анна</b>' : `Сотрудник ${index}`,
      group_id: 10, group_name: 'Продажи', group_timezone: 'Europe/Moscow', date: '2026-09-29',
      started_at: '2026-09-29T06:00:00Z', ended_at: '2026-09-29T15:00:00Z',
      break_seconds: 60, work_seconds: 3600, late_seconds: 0, status: 'finished',
      activity: 'secret activity', crm_url: 'https://secret.invalid' });
    const transport = {
      directory: () => Promise.resolve(directory),
      report(params, signal) {
        window.reportCalls.push({ params, aborted: signal.aborted });
        if (window.reportMode === 'error') return Promise.reject({ publicMessage: 'Период недоступен', detail: 'private' });
        if (window.reportMode === 'unsafe-error') return Promise.reject({ message: 'Ошибка: token=secret' });
        const items = window.reportMode === 'empty' ? [] : params.page === 1 ? Array.from({ length: 10 }, (_, i) => row(i)) : [row(10)];
        return Promise.resolve({ items, page: params.page, page_size: 10, total: window.reportMode === 'empty' ? 0 : 11,
          totals: { work_seconds: 3600, break_seconds: 60, late_seconds: 0, days: 11, employees: 11 } });
      },
      export(body, signal) {
        window.exportCalls.push({ body, aborted: signal.aborted });
        if (window.exportMode === 'error') return Promise.reject({ publicMessage: 'Экспорт недоступен', detail: 'private' });
        if (window.exportMode === 'unsafe-error') return Promise.reject({ message: 'Ошибка: token=secret' });
        return Promise.resolve({ blob: new Blob(['xlsx']), filename: 'точный-файл.xlsx' });
      },
    };
    window.reportController = TimesheetReports.mount(document.querySelector('#root'), {
      document, transport, now: () => new Date('2026-09-29T12:00:00Z'),
    });
  }, role);
  await page.evaluate(() => window.reportController.ready);
}

for (const role of ['admin', 'manager']) {
  test(`${role} filters authorized employees and paginates ten rows`, async ({ page }) => {
    await boot(page, role);
    await expect(page.locator('tbody tr')).toHaveCount(10);
    await expect(page.locator('tbody td').first()).toHaveText('<b>Анна</b>');
    await expect(page.locator('tbody b')).toHaveCount(0);
    await expect(page.locator('.ts-reports')).not.toContainText('secret activity');
    await expect(page.locator('[data-filter="employee"] option')).toHaveCount(2);
    await page.locator('[data-filter="date-from"]').fill('2026-09-01');
    await page.locator('[data-filter="group"]').selectOption('10');
    await expect(page.locator('[data-filter="employee"] option')).toHaveCount(2);
    await page.locator('[data-filter="employee"]').selectOption('2');
    await page.locator('[data-action="show"]').click();
    await expect.poll(() => page.evaluate(() => window.reportCalls.at(-1).params)).toEqual({
      date_from: '2026-09-01', date_to: '2026-09-29', page: 1, group_id: 10, user_id: 2,
    });
    await page.locator('[data-action="next"]').click();
    await expect(page.locator('tbody tr')).toHaveCount(1);
    await expect(page.locator('[data-action="next"]')).toBeDisabled();
    await expect.poll(() => page.evaluate(() => window.reportCalls.at(-1).params.page)).toBe(2);
    await page.locator('[data-action="previous"]').click();
    await expect(page.locator('tbody tr')).toHaveCount(10);
    await page.locator('[data-action="clear"]').click();
    await expect.poll(() => page.evaluate(() => window.reportCalls.at(-1).params)).toEqual({
      date_from: '2026-09-29', date_to: '2026-09-29', page: 1,
    });
  });
}

test('empty, safe error and retry states recover in the browser', async ({ page }) => {
  await boot(page);
  await page.evaluate(() => { window.reportMode = 'empty'; });
  await page.locator('[data-action="show"]').click();
  await expect(page.locator('.ts-reports__message')).toHaveText('За выбранный период данных нет.');
  await page.evaluate(() => { window.reportMode = 'error'; });
  await page.locator('[data-action="show"]').click();
  await expect(page.locator('.ts-reports__message')).toHaveText('Период недоступен');
  await expect(page.locator('.ts-reports')).not.toContainText('private');
  await page.evaluate(() => { window.reportMode = 'normal'; });
  await page.locator('[data-action="retry"]').click();
  await expect(page.locator('tbody tr')).toHaveCount(10);
  await expect(page.locator('[data-action="retry"]')).toBeHidden();
  await page.evaluate(() => { window.reportMode = 'unsafe-error'; });
  await page.locator('[data-action="show"]').click();
  await expect(page.locator('.ts-reports__message')).toHaveText('Не удалось загрузить табель. Повторите попытку.');
  await expect(page.locator('.ts-reports')).not.toContainText('token=secret');
});

test('selected Excel columns download once and release the temporary URL; failure remains retryable', async ({ page }) => {
  await boot(page);
  await page.locator('[data-filter="group"]').selectOption('10');
  await page.locator('[data-column="start"]').uncheck();
  await page.locator('[data-action="export"]').click();
  await expect.poll(() => page.evaluate(() => window.downloads.length)).toBe(1);
  expect(await page.evaluate(() => window.exportCalls[0].body)).toEqual({
    date_from: '2026-09-29', date_to: '2026-09-29', group_id: 10,
    columns: ['employee', 'date', 'end', 'break', 'work', 'lateness', 'status'],
  });
  expect(await page.evaluate(() => window.downloads)).toEqual([
    { filename: 'точный-файл.xlsx', href: 'blob:report-test', attached: true },
  ]);
  await expect(page.locator('a[download]')).toHaveCount(0);
  expect(await page.evaluate(() => window.revocations)).toEqual(['blob:report-test']);
  await page.evaluate(() => { window.exportMode = 'error'; });
  await page.locator('[data-action="export"]').click();
  await expect(page.locator('.ts-reports__export-message')).toHaveText('Экспорт недоступен');
  await expect(page.locator('[data-action="export"]')).toBeEnabled();
  await expect(page.locator('.ts-reports')).not.toContainText('private');
  expect(await page.evaluate(() => window.downloads.length)).toBe(1);
  await page.evaluate(() => { window.exportMode = 'unsafe-error'; });
  await page.locator('[data-action="export"]').click();
  await expect(page.locator('.ts-reports__export-message')).toHaveText('Не удалось скачать Excel. Повторите попытку.');
  await expect(page.locator('.ts-reports')).not.toContainText('token=secret');
});

test('employee role never gets preview or download controls', async ({ page }) => {
  await boot(page, 'employee');
  await expect(page.locator('.ts-reports__message')).toHaveText('У вас нет доступа к этому разделу.');
  await expect(page.locator('[data-action="export"]')).toHaveCount(0);
  expect(await page.evaluate(() => window.reportCalls.length)).toBe(0);
});
