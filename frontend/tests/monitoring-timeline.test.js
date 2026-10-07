const test = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { resolve } = require('node:path');
const { JSDOM } = require('jsdom');

const Timeline = require('../monitoring/timeline');
const ActivityModal = require('../monitoring/activity-modal');

function interval(overrides = {}) {
  return {
    id: 1,
    started_at: '2026-03-29T01:00:00Z',
    ended_at: '2026-03-29T02:00:00Z',
    duration_seconds: 3600,
    kind: 'confirmed',
    source: 'crm_event',
    duration_source: 'calculated',
    event_type: 'lead_status_changed',
    object_type: 'lead',
    object_id: 42,
    description: 'Карточка клиента',
    card_url: 'https://tenant.amocrm.ru/leads/detail/42',
    call_direction: null,
    call_duration_seconds: null,
    message: null,
    ...overrides,
  };
}

function day(overrides = {}) {
  return {
    date: '2026-03-29',
    started_at: '2026-03-29T00:00:00Z',
    ended_at: '2026-03-29T23:00:00Z',
    shift_started_at: '2026-03-29T07:00:00Z',
    shift_ended_at: '2026-03-29T16:00:00Z',
    confirmed_seconds: 3600,
    confirmed_events: 1,
    unconfirmed_seconds: 0,
    intervals: [interval()],
    ...overrides,
  };
}

function payload(overrides = {}) {
  const firstDay = day();
  return {
    target: { id: 2, amocrm_user_id: 102, name: 'Анна', avatar_url: null },
    group: { id: 10, name: 'Продажи' },
    timezone: 'Europe/Berlin',
    from: '2026-03-29',
    to: '2026-03-29',
    totals: { confirmed_seconds: 3600, confirmed_events: 1, unconfirmed_seconds: 0 },
    days: [firstDay],
    ...overrides,
  };
}

test('runtime modules register through AMD as well as CommonJS', () => {
  const dom = new JSDOM('', { runScripts: 'outside-only' });
  let timeline;
  dom.window.define = (dependencies, factory) => {
    assert.deepEqual(Array.from(dependencies), []);
    timeline = factory();
  };
  dom.window.define.amd = {};
  dom.window.eval(readFileSync(resolve(__dirname, '../monitoring/timeline.js'), 'utf8'));
  assert.equal(typeof timeline.layoutDay, 'function');

  let modal;
  dom.window.define = (dependencies, factory) => {
    assert.deepEqual(Array.from(dependencies), []);
    modal = factory();
  };
  dom.window.define.amd = {};
  dom.window.eval(readFileSync(resolve(__dirname, '../monitoring/activity-modal.js'), 'utf8'));
  modal.setTimeline(timeline);
  assert.equal(typeof modal.create, 'function');
  dom.window.close();
});

test('normalizeDay clips intervals, preserves empty time, and assigns overlap lanes', () => {
  const normalized = Timeline.normalizeDay(day({
    intervals: [
      interval({ id: 1, started_at: '2026-03-28T23:30:00Z', ended_at: '2026-03-29T01:00:00Z', duration_seconds: 5400 }),
      interval({ id: 2, started_at: '2026-03-29T00:30:00Z', ended_at: '2026-03-29T01:30:00Z' }),
      interval({ id: 3, started_at: '2026-03-29T04:00:00Z', ended_at: '2026-03-29T04:00:00Z', duration_seconds: 0, duration_source: 'point' }),
      interval({ id: 4, started_at: '2026-03-29T22:00:00Z', ended_at: '2026-03-30T02:00:00Z', kind: 'unconfirmed', source: 'unconfirmed_input' }),
    ],
  }));

  assert.equal(normalized.durationMinutes, 23 * 60);
  assert.equal(normalized.items[0].startMs, Date.parse('2026-03-29T00:00:00Z'));
  assert.equal(normalized.items[0].endMs, Date.parse('2026-03-29T01:00:00Z'));
  assert.equal(normalized.items[0].lane, 0);
  assert.equal(normalized.items[1].lane, 1);
  assert.equal(normalized.items[2].isPoint, true);
  assert.equal(normalized.items[2].endMs, normalized.items[2].startMs);
  assert.equal(normalized.items[3].endMs, Date.parse('2026-03-29T23:00:00Z'));
  assert.equal(normalized.laneCount, 2);
});

test('layoutDay supports only zoom 1, 2, 4 without changing data durations', () => {
  const one = Timeline.layoutDay(day(), 1);
  const four = Timeline.layoutDay(day(), 4);
  assert.equal(one.width, 23 * 60);
  assert.equal(four.width, one.width * 4);
  assert.equal(one.items[0].width, 60);
  assert.equal(four.items[0].width, 240);
  assert.equal(one.items[0].durationSeconds, four.items[0].durationSeconds);
  assert.throws(() => Timeline.layoutDay(day(), 3), /zoom/i);
});

test('render reserves green for confirmed spans and uses accessible point markers', () => {
  const dom = new JSDOM('<main id="root"></main>');
  const root = dom.window.document.querySelector('#root');
  const result = Timeline.render(root, day({
    intervals: [
      interval({ id: 1 }),
      interval({ id: 2, started_at: '2026-03-29T03:00:00Z', ended_at: '2026-03-29T03:00:00Z', duration_seconds: 0, duration_source: 'point' }),
      interval({ id: 3, started_at: '2026-03-29T05:00:00Z', ended_at: '2026-03-29T06:00:00Z', kind: 'unconfirmed', source: 'unconfirmed_input', message: 'Нет подтверждённой активности' }),
    ],
  }), { zoom: 1, timezone: 'Europe/Berlin' });

  assert.equal(root.querySelectorAll('.ts-timeline__item--confirmed').length, 1);
  assert.equal(root.querySelectorAll('.ts-timeline__item--point').length, 1);
  assert.equal(root.querySelectorAll('.ts-timeline__item--unconfirmed').length, 1);
  assert.equal(root.querySelector('.ts-timeline__item--point').style.width, '6px');
  assert.equal(root.querySelector('.ts-timeline__item--point').getAttribute('role'), 'button');
  assert.equal(root.querySelector('.ts-timeline__track').style.width, '1380px');
  assert.equal(result.destroy instanceof Function, true);
  result.destroy();
});

test('tooltip renders hostile CRM text as text and allows only safe card links', () => {
  const dom = new JSDOM('<main id="root"></main>');
  const root = dom.window.document.querySelector('#root');
  Timeline.render(root, day({ intervals: [interval({
    description: '<img src=x onerror="globalThis.pwned=1">',
    event_type: '<script>bad()</script>',
  })] }), { zoom: 1, timezone: 'Europe/Berlin' });
  root.querySelector('.ts-timeline__item').click();
  const tooltip = root.querySelector('.ts-timeline__tooltip');
  assert.match(tooltip.textContent, /<img src=x/);
  assert.equal(tooltip.querySelector('img'), null);
  assert.equal(tooltip.querySelector('script'), null);
  const link = tooltip.querySelector('a');
  assert.equal(link.target, '_blank');
  assert.equal(link.rel, 'noopener noreferrer');

  const unsafe = day({ intervals: [interval({ card_url: 'javascript:alert(1)' })] });
  Timeline.render(root, unsafe, { zoom: 1 });
  root.querySelector('.ts-timeline__item').click();
  assert.equal(root.querySelector('.ts-timeline__tooltip a'), null);
});

test('tooltip opens on hover and keyboard focus and includes every safe activity field', () => {
  const dom = new JSDOM('<main id="root"></main>');
  const root = dom.window.document.querySelector('#root');
  Timeline.render(root, day({ intervals: [interval({
    source: 'call',
    event_type: 'call_finished',
    object_type: 'contact',
    object_id: 731,
    description: 'Разговор с клиентом',
    duration_seconds: 125,
    duration_source: 'observed',
    call_direction: 'incoming',
    call_duration_seconds: 125,
  })] }), { zoom: 1, timezone: 'Europe/Berlin' });
  const marker = root.querySelector('.ts-timeline__item');

  marker.dispatchEvent(new dom.window.MouseEvent('mouseenter'));
  let tooltip = root.querySelector('.ts-timeline__tooltip');
  assert.equal(marker.getAttribute('aria-expanded'), 'true');
  for (const expected of [
    'Дата: 29.03.2026',
    'Время: 03:00–04:00',
    'Тип: call_finished',
    'Объект: contact #731',
    'Описание: Разговор с клиентом',
    'Источник: Звонок',
    'Длительность: 125 сек.',
    'Способ определения: Наблюдаемая',
    'Направление звонка: Входящий',
    'Длительность звонка: 125 сек.',
  ]) assert.match(tooltip.textContent, new RegExp(expected));

  marker.focus();
  marker.dispatchEvent(new dom.window.MouseEvent('mouseleave'));
  assert.notEqual(root.querySelector('.ts-timeline__tooltip'), null, 'focus keeps tooltip open');
  marker.blur();
  assert.equal(root.querySelector('.ts-timeline__tooltip'), null);
  assert.equal(marker.getAttribute('aria-expanded'), 'false');

  marker.focus();
  tooltip = root.querySelector('.ts-timeline__tooltip');
  assert.notEqual(tooltip, null, 'focus alone opens tooltip');
  marker.blur();
  assert.equal(root.querySelector('.ts-timeline__tooltip'), null, 'blur closes tooltip');
});

test('click pin composes with hover without stale aria-expanded state', () => {
  const dom = new JSDOM('<main id="root"></main>');
  const root = dom.window.document.querySelector('#root');
  Timeline.render(root, day(), { zoom: 1 });
  const marker = root.querySelector('.ts-timeline__item');
  marker.click();
  assert.equal(marker.getAttribute('aria-expanded'), 'true');
  marker.dispatchEvent(new dom.window.MouseEvent('mouseenter'));
  marker.dispatchEvent(new dom.window.MouseEvent('mouseleave'));
  assert.notEqual(root.querySelector('.ts-timeline__tooltip'), null);
  marker.click();
  assert.equal(root.querySelector('.ts-timeline__tooltip'), null);
  assert.equal(marker.getAttribute('aria-expanded'), 'false');
});

test('call without a direction uses a neutral label', () => {
  const dom = new JSDOM('<main id="root"></main>');
  const root = dom.window.document.querySelector('#root');
  Timeline.render(root, day({ intervals: [interval({
    source: 'call',
    call_direction: null,
    description: null,
  })] }), { zoom: 1 });
  const marker = root.querySelector('.ts-timeline__item');
  assert.match(marker.getAttribute('aria-label'), /^Звонок,/);
  marker.focus();
  assert.equal(root.querySelector('.ts-timeline__tooltip-title').textContent, 'Звонок');
});

test('render labels a 23-hour local day from explicit UTC bounds', () => {
  const dom = new JSDOM('<main id="root"></main>');
  const root = dom.window.document.querySelector('#root');
  Timeline.render(root, day(), { zoom: 1, timezone: 'Europe/Berlin' });
  assert.equal(root.querySelector('.ts-timeline__day-label').textContent, '29.03.2026');
  assert.match(root.querySelector('.ts-timeline__duration-label').textContent, /23 ч/);
});

test('modal renders totals and seven rows, updates in place, and preserves zoom', () => {
  const dom = new JSDOM('<button id="opener">Открыть</button><main id="host"></main>');
  const { document } = dom.window;
  const opener = document.querySelector('#opener');
  opener.focus();
  const modal = ActivityModal.create({ document, mount: document.querySelector('#host') });
  const sevenDays = Array.from({ length: 7 }, (_, index) => day({
    date: `2026-03-${String(23 + index).padStart(2, '0')}`,
    started_at: `2026-03-${String(23 + index).padStart(2, '0')}T00:00:00Z`,
    ended_at: `2026-03-${String(24 + index).padStart(2, '0')}T00:00:00Z`,
  }));
  modal.open(payload({ days: sevenDays }), { trigger: opener });
  assert.equal(document.querySelectorAll('.ts-activity-modal__day').length, 7);
  assert.match(document.querySelector('.ts-activity-modal__totals').textContent, /1 ч/);
  document.querySelector('[data-zoom="4"]').click();
  modal.update(payload({ target: { id: 2, amocrm_user_id: 102, name: 'Анна Обновлённая', avatar_url: null }, days: sevenDays }));
  assert.equal(document.querySelector('.ts-activity-modal__title').textContent, 'Анна Обновлённая');
  assert.equal(document.querySelector('[data-zoom="4"]').getAttribute('aria-pressed'), 'true');
  assert.equal(document.body.classList.contains('ts-modal-open'), true);
  modal.destroy();
});

test('modal Escape closes, returns focus, and restores original body overflow', () => {
  const dom = new JSDOM('<button id="opener">Открыть</button><main id="host"></main>');
  const { document } = dom.window;
  document.body.style.overflow = 'scroll';
  const opener = document.querySelector('#opener');
  opener.focus();
  const modal = ActivityModal.create({ document, mount: document.querySelector('#host') });
  modal.open(payload(), { trigger: opener });
  assert.equal(modal.isOpen(), true);
  document.dispatchEvent(new dom.window.KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
  assert.equal(modal.isOpen(), false);
  assert.equal(document.activeElement, opener);
  assert.equal(document.body.style.overflow, 'scroll');
  assert.equal(document.body.classList.contains('ts-modal-open'), false);
  modal.destroy();
});

test('modal traps focus and fullscreen toggle keeps class and aria state in sync', async () => {
  const dom = new JSDOM('<button id="opener">Открыть</button><main id="host"></main>');
  const { document } = dom.window;
  const modal = ActivityModal.create({ document, mount: document.querySelector('#host') });
  modal.open(payload(), { trigger: document.querySelector('#opener') });
  const panel = document.querySelector('.ts-activity-modal__panel');
  let requested = 0;
  let exited = 0;
  panel.requestFullscreen = async () => { requested += 1; Object.defineProperty(document, 'fullscreenElement', { value: panel, configurable: true }); };
  document.exitFullscreen = async () => { exited += 1; Object.defineProperty(document, 'fullscreenElement', { value: null, configurable: true }); };
  const toggle = document.querySelector('.ts-activity-modal__fullscreen');
  toggle.click();
  await new Promise(setImmediate);
  assert.equal(requested, 1);
  assert.equal(panel.classList.contains('ts-activity-modal__panel--fullscreen'), true);
  assert.equal(toggle.getAttribute('aria-pressed'), 'true');
  toggle.click();
  await new Promise(setImmediate);
  assert.equal(exited, 1);
  assert.equal(toggle.getAttribute('aria-pressed'), 'false');

  const close = document.querySelector('.ts-activity-modal__close');
  const last = document.querySelector('.ts-activity-modal__fullscreen');
  last.focus();
  document.dispatchEvent(new dom.window.KeyboardEvent('keydown', { key: 'Tab', bubbles: true }));
  assert.equal(document.activeElement, close);
  modal.destroy();
  assert.equal(document.querySelector('.ts-activity-modal'), null);
});

test('modal has safe loading, error and empty states without HTML interpretation', () => {
  const dom = new JSDOM('<main id="host"></main>');
  const { document } = dom.window;
  const modal = ActivityModal.create({ document, mount: document.querySelector('#host') });
  modal.open({ state: 'loading', target: { name: 'Анна' } });
  assert.match(document.querySelector('.ts-activity-modal__state').textContent, /Загрузка/);
  modal.update({ state: 'error', message: '<img src=x>', target: { name: 'Анна' } });
  assert.equal(document.querySelector('.ts-activity-modal img'), null);
  assert.match(document.querySelector('.ts-activity-modal__state').textContent, /Не удалось/);
  modal.update(payload({ days: [] }));
  assert.match(document.querySelector('.ts-activity-modal__state').textContent, /нет данных/i);
  modal.destroy();
});

test('modal destroy explicitly removes every zoom click handler', () => {
  const dom = new JSDOM('<main id="host"></main>');
  const { document, EventTarget } = dom.window;
  const removed = [];
  const originalRemove = EventTarget.prototype.removeEventListener;
  EventTarget.prototype.removeEventListener = function (type, listener, options) {
    removed.push({ target: this, type, listener });
    return originalRemove.call(this, type, listener, options);
  };
  const modal = ActivityModal.create({ document, mount: document.querySelector('#host') });
  modal.open(payload());
  const zoomButtons = Array.from(document.querySelectorAll('[data-zoom]'));
  modal.destroy();
  for (const button of zoomButtons) {
    assert.equal(removed.some((entry) => entry.target === button && entry.type === 'click' && typeof entry.listener === 'function'), true);
  }
  EventTarget.prototype.removeEventListener = originalRemove;
});
