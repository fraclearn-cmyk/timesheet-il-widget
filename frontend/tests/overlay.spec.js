const { test, expect } = require('@playwright/test');
const { resolve } = require('node:path');
test.use({ channel: 'chrome' });

const source = resolve(__dirname, '../../widget/overlay.js');
const style = resolve(__dirname, '../../widget/styles.css');
const base = { session_id: 1, started_at: '2026-09-22T08:00:00Z', ended_at: null,
  break_seconds: 0, track_time: true, hide_widget: false, restart_allowed: false };

test.beforeEach(async ({ page }) => {
  await page.setContent('<button id="crm-action" onclick="window.crmClicks=(window.crmClicks||0)+1">CRM action</button>');
  await page.addStyleTag({ path: style });
  await page.addScriptTag({ path: source });
  await page.evaluate(() => { window.overlay = window.TimesheetOverlay.createOverlay(document); });
});

test('confirmed break blocks mouse and keyboard until clear', async ({ page }) => {
  await page.evaluate((snapshot) => window.overlay.render(snapshot), { ...base, status: 'on_break' });
  await expect(page.locator('.timesheet-overlay')).toHaveCount(1);
  await expect(page.locator('.timesheet-action')).toHaveCount(2);
  await page.locator('#crm-action').click({ force: true });
  await page.keyboard.press('Tab');
  await page.keyboard.press('Tab');
  await page.keyboard.press('Tab');
  await page.keyboard.press('Enter');
  expect(await page.evaluate(() => window.crmClicks || 0)).toBe(0);
  await page.evaluate(() => window.overlay.clear());
  await expect(page.locator('.timesheet-overlay')).toHaveCount(0);
  await page.locator('#crm-action').click();
  await page.locator('#crm-action').focus();
  await page.keyboard.press('Enter');
  expect(await page.evaluate(() => window.crmClicks)).toBe(2);
});

test('unknown and opted-out states leave amoCRM clear', async ({ page }) => {
  for (const snapshot of [null, { ...base, status: 'on_break', track_time: false },
    { ...base, status: 'on_break', hide_widget: true }]) {
    await page.evaluate((value) => window.overlay.render(value), snapshot);
    await expect(page.locator('.timesheet-overlay, .timesheet-actions')).toHaveCount(0);
  }
});

test('status actions are only those allowed by server snapshot', async ({ page }) => {
  const cases = [
    ['not_started', false, ['start-work']],
    ['working', false, ['start-break', 'finish-work']],
    ['on_break', false, ['end-break', 'finish-work']],
    ['finished', false, []],
    ['finished', true, ['start-work']],
  ];
  for (const [status, restart_allowed, expected] of cases) {
    await page.evaluate((value) => window.overlay.render(value), { ...base, status, restart_allowed });
    expect(await page.locator('.timesheet-action').evaluateAll((nodes) => nodes.map((node) => node.dataset.action))).toEqual(expected);
  }
});
