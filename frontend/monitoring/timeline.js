(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else if (typeof define === 'function' && define.amd) {
    define([], factory);
  } else {
    root.TimesheetTimeline = factory();
  }
}(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  const ALLOWED_ZOMS = new Set([1, 2, 4]);
  const MINUTE_MS = 60000;

  function timestamp(value, label) {
    const result = Date.parse(value);
    if (!Number.isFinite(result)) throw new TypeError(`Invalid ${label || 'timestamp'}`);
    return result;
  }

  function normalizeDay(day) {
    if (!day || typeof day !== 'object') throw new TypeError('Day is required');
    const startMs = timestamp(day.started_at, 'day start');
    const endMs = timestamp(day.ended_at, 'day end');
    if (endMs <= startMs) throw new RangeError('Day end must be after its start');

    const candidates = [];
    for (const source of Array.isArray(day.intervals) ? day.intervals : []) {
      let itemStart = timestamp(source.started_at, 'interval start');
      let itemEnd = timestamp(source.ended_at, 'interval end');
      const isPoint = source.duration_source === 'point' || itemStart === itemEnd;
      if (isPoint) {
        if (itemStart < startMs || itemStart >= endMs) continue;
        itemEnd = itemStart;
      } else {
        if (itemEnd <= startMs || itemStart >= endMs || itemEnd < itemStart) continue;
        itemStart = Math.max(itemStart, startMs);
        itemEnd = Math.min(itemEnd, endMs);
      }
      candidates.push({
        ...source,
        startMs: itemStart,
        endMs: itemEnd,
        isPoint,
        presentationDurationSeconds: isPoint ? 0 : Math.max(0, (itemEnd - itemStart) / 1000),
      });
    }

    candidates.sort((left, right) => left.startMs - right.startMs || left.endMs - right.endMs || String(left.id).localeCompare(String(right.id)));
    const laneEnds = [];
    const items = candidates.map((item) => {
      let lane = laneEnds.findIndex((laneEnd) => item.startMs >= laneEnd);
      if (lane === -1) lane = laneEnds.length;
      laneEnds[lane] = Math.max(laneEnds[lane] || startMs, item.isPoint ? item.startMs + 1 : item.endMs);
      return { ...item, lane };
    });

    return {
      ...day,
      startMs,
      endMs,
      durationMinutes: (endMs - startMs) / MINUTE_MS,
      laneCount: Math.max(1, laneEnds.length),
      items,
    };
  }

  function layoutDay(day, zoom) {
    const scale = zoom === undefined ? 1 : Number(zoom);
    if (!ALLOWED_ZOMS.has(scale)) throw new RangeError('zoom must be 1, 2, or 4');
    const normalized = day && Array.isArray(day.items) && Number.isFinite(day.startMs) ? day : normalizeDay(day);
    return {
      ...normalized,
      zoom: scale,
      width: normalized.durationMinutes * scale,
      items: normalized.items.map((item) => ({
        ...item,
        left: ((item.startMs - normalized.startMs) / MINUTE_MS) * scale,
        width: item.isPoint ? 6 : ((item.endMs - item.startMs) / MINUTE_MS) * scale,
      })),
    };
  }

  function appendText(document, parent, className, text) {
    if (text === null || text === undefined || text === '') return null;
    const node = document.createElement('div');
    node.className = className;
    node.textContent = String(text);
    parent.appendChild(node);
    return node;
  }

  function safeCardUrl(document, value) {
    if (typeof value !== 'string' || !value) return null;
    try {
      const url = new document.defaultView.URL(value);
      return url.protocol === 'https:' || url.protocol === 'http:' ? url.href : null;
    } catch (_error) {
      return null;
    }
  }

  function formatClock(milliseconds, timezone) {
    try {
      return new Intl.DateTimeFormat('ru-RU', {
        hour: '2-digit', minute: '2-digit', hour12: false, timeZone: timezone || 'UTC',
      }).format(new Date(milliseconds));
    } catch (_error) {
      return new Date(milliseconds).toISOString().slice(11, 16);
    }
  }

  function formatDate(value) {
    const parts = String(value || '').split('-');
    return parts.length === 3 ? `${parts[2]}.${parts[1]}.${parts[0]}` : String(value || '');
  }

  function sourceLabel(item) {
    if (item.kind !== 'confirmed') return item.message || 'Нет подтверждённой активности';
    if (item.source === 'call') {
      if (item.call_direction === 'incoming') return 'Входящий звонок';
      if (item.call_direction === 'outgoing') return 'Исходящий звонок';
      return 'Звонок';
    }
    return item.description || item.event_type || 'Действие в CRM';
  }

  function sourceName(value) {
    return ({ crm_event: 'Действие в CRM', call: 'Звонок', unconfirmed_input: 'Неподтверждённая активность' })[value] || String(value || 'Не указан');
  }

  function durationSourceName(value) {
    return ({ point: 'Точечное событие', observed: 'Наблюдаемая', calculated: 'Расчётная' })[value] || String(value || 'Не указан');
  }

  function callDirectionName(value) {
    return ({ incoming: 'Входящий', outgoing: 'Исходящий' })[value] || String(value || 'Не указано');
  }

  function render(root, day, options) {
    if (!root || !root.ownerDocument) throw new TypeError('A DOM root is required');
    const settings = options || {};
    const document = root.ownerDocument;
    const layout = layoutDay(day, settings.zoom || 1);
    root.replaceChildren();
    root.classList.add('ts-timeline');

    const heading = document.createElement('div');
    heading.className = 'ts-timeline__heading';
    appendText(document, heading, 'ts-timeline__day-label', formatDate(layout.date));
    appendText(document, heading, 'ts-timeline__duration-label', `${layout.durationMinutes / 60} ч`);
    root.appendChild(heading);

    const viewport = document.createElement('div');
    viewport.className = 'ts-timeline__viewport';
    const track = document.createElement('div');
    track.className = 'ts-timeline__track';
    track.style.width = `${layout.width}px`;
    track.style.height = `${Math.max(34, layout.laneCount * 30 + 4)}px`;
    viewport.appendChild(track);
    root.appendChild(viewport);

    let tooltip = null;
    let activeAnchor = null;
    let activeState = null;
    const listenerCleanup = [];
    function hideTooltip() {
      if (activeAnchor) activeAnchor.setAttribute('aria-expanded', 'false');
      if (tooltip) tooltip.remove();
      tooltip = null;
      activeAnchor = null;
      activeState = null;
    }
    function showTooltip(item, anchor, interactionState) {
      if (activeAnchor === anchor && tooltip) return;
      if (activeState && activeState !== interactionState) activeState.pinned = false;
      hideTooltip();
      tooltip = document.createElement('div');
      tooltip.className = 'ts-timeline__tooltip';
      tooltip.setAttribute('role', 'status');
      appendText(document, tooltip, 'ts-timeline__tooltip-title', sourceLabel(item));
      const endLabel = item.isPoint ? '' : `–${formatClock(item.endMs, settings.timezone)}`;
      appendText(document, tooltip, 'ts-timeline__tooltip-date', `Дата: ${formatDate(layout.date)}`);
      appendText(document, tooltip, 'ts-timeline__tooltip-time', `Время: ${formatClock(item.startMs, settings.timezone)}${endLabel}`);
      appendText(document, tooltip, 'ts-timeline__tooltip-type', `Тип: ${item.event_type || 'Не указан'}`);
      if (item.object_type || item.object_id !== null && item.object_id !== undefined) {
        const identifier = item.object_id === null || item.object_id === undefined ? '' : ` #${item.object_id}`;
        appendText(document, tooltip, 'ts-timeline__tooltip-object', `Объект: ${item.object_type || 'Не указан'}${identifier}`);
      }
      appendText(document, tooltip, 'ts-timeline__tooltip-description', `Описание: ${item.description || item.message || 'Нет описания'}`);
      appendText(document, tooltip, 'ts-timeline__tooltip-source', `Источник: ${sourceName(item.source)}`);
      appendText(document, tooltip, 'ts-timeline__tooltip-duration', `Длительность: ${Math.max(0, Number(item.duration_seconds) || 0)} сек.`);
      appendText(document, tooltip, 'ts-timeline__tooltip-duration-source', `Способ определения: ${durationSourceName(item.duration_source)}`);
      if (item.call_direction) {
        appendText(document, tooltip, 'ts-timeline__tooltip-call-direction', `Направление звонка: ${callDirectionName(item.call_direction)}`);
      }
      if (item.call_duration_seconds !== null && item.call_duration_seconds !== undefined) {
        appendText(document, tooltip, 'ts-timeline__tooltip-call', `Длительность звонка: ${item.call_duration_seconds} сек.`);
      }
      const href = safeCardUrl(document, item.card_url);
      if (href) {
        const link = document.createElement('a');
        link.href = href;
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
        link.textContent = 'Открыть карточку';
        tooltip.appendChild(link);
      }
      anchor.setAttribute('aria-expanded', 'true');
      activeAnchor = anchor;
      activeState = interactionState;
      root.appendChild(tooltip);
    }

    for (const item of layout.items) {
      const element = document.createElement('button');
      element.type = 'button';
      element.setAttribute('role', 'button');
      element.className = 'ts-timeline__item';
      if (item.isPoint) {
        element.classList.add('ts-timeline__item--point', `ts-timeline__item--${item.kind}-point`);
      } else {
        element.classList.add(`ts-timeline__item--${item.kind === 'confirmed' ? 'confirmed' : 'unconfirmed'}`);
      }
      element.style.left = `${item.left}px`;
      element.style.width = `${item.width}px`;
      element.style.top = `${item.lane * 30 + 2}px`;
      element.setAttribute('aria-expanded', 'false');
      element.setAttribute('aria-label', `${sourceLabel(item)}, ${formatClock(item.startMs, settings.timezone)}`);
      const interactionState = { hovered: false, focused: false, pinned: false };
      function refreshTooltip() {
        if (interactionState.hovered || interactionState.focused || interactionState.pinned) {
          showTooltip(item, element, interactionState);
        } else if (activeAnchor === element) {
          hideTooltip();
        }
      }
      function onMouseEnter() { interactionState.hovered = true; refreshTooltip(); }
      function onMouseLeave() { interactionState.hovered = false; refreshTooltip(); }
      function onFocus() { interactionState.focused = true; refreshTooltip(); }
      function onBlur() { interactionState.focused = false; refreshTooltip(); }
      function onClick() { interactionState.pinned = !interactionState.pinned; refreshTooltip(); }
      element.addEventListener('mouseenter', onMouseEnter);
      element.addEventListener('mouseleave', onMouseLeave);
      element.addEventListener('focus', onFocus);
      element.addEventListener('blur', onBlur);
      element.addEventListener('click', onClick);
      listenerCleanup.push(() => {
        element.removeEventListener('mouseenter', onMouseEnter);
        element.removeEventListener('mouseleave', onMouseLeave);
        element.removeEventListener('focus', onFocus);
        element.removeEventListener('blur', onBlur);
        element.removeEventListener('click', onClick);
      });
      track.appendChild(element);
    }

    return { layout, destroy: () => { for (const cleanup of listenerCleanup) cleanup(); hideTooltip(); root.replaceChildren(); } };
  }

  return { normalizeDay, layoutDay, render };
}));
