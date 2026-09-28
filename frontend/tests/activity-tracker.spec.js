const { test, expect } = require('@playwright/test');
const { readFileSync } = require('node:fs');
const { resolve } = require('node:path');
test.use({ channel: 'chrome' });

const sources = Object.fromEntries([
  ['settings', 'frontend/settings/settings.js'],
  ['controller', 'widget/timesheet/controller.js'],
  ['overlay', 'widget/overlay.js'],
  ['tracker', 'widget/activity-tracker.js'],
  ['widget', 'widget/script.js'],
].filter(([, file]) => {
  try { readFileSync(resolve(__dirname, '../..', file)); return true; } catch { return false; }
}).map(([key, file]) => [key, readFileSync(resolve(__dirname, '../..', file), 'utf8')]));
const css = readFileSync(resolve(__dirname, '../../widget/styles.css'), 'utf8');

async function boot(page) {
  await page.route('https://widget.test/**', (route) => route.request().url().includes('/styles.css')
    ? route.fulfill({ contentType: 'text/css', body: css })
    : route.fulfill({ contentType: 'text/html', body: '<input id="private" value="Client secret note"><button id="crm">CRM</button><div id="list_page_holder"></div>' }));
  await page.goto('https://widget.test/');
  await page.evaluate((code) => {
    if (!code.tracker) throw new Error('activity tracker module is missing');
    const modules = {};
    for (const name of ['settings', 'controller', 'overlay', 'tracker']) {
      window.define = (factory) => { modules[name] = factory(); };
      window.define.amd = {};
      (0, eval)(code[name]);
    }
    window.define = (_ids, factory) => { window.Widget = factory({}, modules.settings, modules.controller, modules.overlay, modules.tracker); };
    (0, eval)(code.widget);
    window.widget = new window.Widget();
    window.calls = [];
    window.area = 'lcard';
    window.widget.system = () => ({ area: window.area });
    window.widget.get_settings = () => ({ api_url: 'https://api.test/api/v1', path: 'https://widget.test/assets/', version: '3.0.2', account_id: 108, user_id: 42 });
    window.widget.$authorizedAjax = (request) => {
      window.calls.push({ ...request });
      if (request.url.includes('/activity/presence')) return Promise.reject(new Error('backend unavailable'));
      return Promise.resolve({ session_id: 7, status: 'working', started_at: '2026-09-23T08:00:00Z', ended_at: null,
        break_seconds: 0, track_time: true, hide_widget: true, restart_allowed: false });
    };
    window.widget.callbacks.init();
  }, sources);
  await expect.poll(() => page.evaluate(() => window.calls.filter((call) => call.url.includes('/timesheet/my-status')).length)).toBe(1);
}

test('real widget sends privacy-safe authorized aggregate and stays invisible on failure', async ({ page }) => {
  await boot(page);
  await page.locator('#private').focus();
  await page.keyboard.type('SecretText');
  await page.mouse.click(713, 419);
  await page.evaluate(() => {
    Object.defineProperty(document, 'visibilityState', { value: 'hidden', configurable: true });
    document.dispatchEvent(new Event('visibilitychange'));
  });
  await expect.poll(() => page.evaluate(() => window.calls.filter((call) => call.url.includes('/activity/presence')).length)).toBe(1);
  const request = await page.evaluate(() => window.calls.find((call) => call.url.includes('/activity/presence')));
  expect(request.method).toBe('POST');
  expect(request.contentType).toBe('application/json');
  const payload = JSON.parse(request.data);
  expect(Object.keys(payload).sort()).toEqual(['command_id', 'last_seen_at', 'signal_count', 'window_started_at']);
  expect(payload.signal_count).toBeGreaterThan(0);
  for (const forbidden of ['SecretText', 'Client secret note', 'account_id', 'user_id']) {
    expect(request.data).not.toContain(forbidden);
  }
  await expect(page.locator('.timesheet-overlay, .timesheet-action')).toHaveCount(0);
});

test('settings transition and destroy remove tracker listeners and timers', async ({ page }) => {
  await boot(page);
  await page.keyboard.press('x');
  await page.evaluate(() => { window.area = 'settings'; window.widget.callbacks.settings(); });
  await page.evaluate(() => {
    Object.defineProperty(document, 'visibilityState', { value: 'hidden', configurable: true });
    document.dispatchEvent(new Event('visibilitychange'));
  });
  await page.waitForTimeout(50);
  expect(await page.evaluate(() => window.calls.filter((call) => call.url.includes('/activity/presence')).length)).toBe(0);

  await page.evaluate(() => {
    Object.defineProperty(document, 'visibilityState', { value: 'visible', configurable: true });
    window.area = 'lcard';
    window.widget.callbacks.init();
  });
  await expect.poll(() => page.evaluate(() => window.calls.filter((call) => call.url.includes('/timesheet/my-status')).length)).toBe(2);
  await page.keyboard.press('y');
  await page.evaluate(() => window.widget.callbacks.destroy());
  await page.evaluate(() => {
    Object.defineProperty(document, 'visibilityState', { value: 'hidden', configurable: true });
    document.dispatchEvent(new Event('visibilitychange'));
  });
  await page.waitForTimeout(50);
  expect(await page.evaluate(() => window.calls.filter((call) => call.url.includes('/activity/presence')).length)).toBe(0);
});
