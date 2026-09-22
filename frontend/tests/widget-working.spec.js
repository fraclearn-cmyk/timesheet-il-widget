const { test, expect } = require('@playwright/test');
const { readFileSync } = require('node:fs');
const { resolve } = require('node:path');
test.use({ channel: 'chrome' });

const sources = Object.fromEntries([
  ['settings', 'frontend/settings/settings.js'],
  ['controller', 'widget/timesheet/controller.js'],
  ['overlay', 'widget/overlay.js'], ['widget', 'widget/script.js'],
].map(([key, file]) => [key, readFileSync(resolve(__dirname, '../..', file), 'utf8')]));
const css = readFileSync(resolve(__dirname, '../../widget/styles.css'), 'utf8');

async function boot(page, cssHandler) {
  await page.route('https://widget.test/**', async (route) => {
    if (route.request().url().includes('/styles.css')) return cssHandler(route);
    return route.fulfill({ contentType: 'text/html', body: '<button id="crm">CRM</button><div id="list_page_holder"></div>' });
  });
  await page.goto('https://widget.test/');
  await page.evaluate((code) => {
    const modules = {};
    for (const name of ['settings', 'controller', 'overlay']) {
      window.define = (factory) => { modules[name] = factory(); };
      window.define.amd = {};
      (0, eval)(code[name]);
    }
    window.define = (_ids, factory) => { window.Widget = factory({}, modules.settings, modules.controller, modules.overlay); };
    (0, eval)(code.widget);
    window.widget = new window.Widget();
    window.area = 'lcard'; window.calls = [];
    window.widget.system = () => ({ area: window.area });
    window.widget.get_settings = () => ({ api_url: 'https://api.test/api/v1/', path: 'https://widget.test/assets/', version: '3.0.2' });
    window.widget.$authorizedAjax = (request) => {
      window.calls.push(request);
      if (request.url.includes('/settings/')) return new Promise(() => {});
      return Promise.resolve({ session_id: 7, status: 'on_break', started_at: '2026-09-22T08:00:00Z',
        ended_at: null, break_seconds: 0, track_time: true, hide_widget: false, restart_allowed: false });
    };
    window.widget.callbacks.init();
  }, sources);
}

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
    await expect(page.locator('.timesheet-overlay, .timesheet-action, link[href*="/styles.css"]')).toHaveCount(0);
    expect(await page.evaluate(() => window.widget.timesheetController === null && window.widget.removeFocusRefresh === null)).toBe(true);
    expect(await page.evaluate(() => window.calls.filter((call) => call.url.includes('/timesheet/')).length)).toBe(1);
  });
}
