(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else if (typeof define === 'function') {
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
    const items = candidates.map((item) => ({ ...item, lane: 0 }));

    return {
      ...day,
      startMs,
      endMs,
      durationMinutes: (endMs - startMs) / MINUTE_MS,
      laneCount: 1,
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

  function groupRenderItems(items) {
    const result = [];
    for (const item of items) {
      const left = item.left;
      const right = item.left + item.width;
      const existing = result[result.length - 1];
      if (existing && left < existing.renderRight && right > existing.left) {
        existing.members.push(item);
        existing.renderRight = Math.max(existing.renderRight, right);
        existing.width = existing.renderRight - existing.left;
        existing.endMs = Math.max(existing.endMs, item.endMs);
        existing.isPoint = existing.members.every((member) => member.isPoint);
        existing.kind = existing.members.every((member) => member.kind === existing.members[0].kind)
          ? existing.members[0].kind
          : 'mixed';
      } else {
        result.push({ ...item, members: [item], renderRight: right });
      }
    }
    return result;
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
    track.style.height = '34px';
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
      const members = item.members || [item];
      if (members.length > 1) {
        appendText(document, tooltip, 'ts-timeline__tooltip-title', `${members.length} события в CRM`);
        appendText(document, tooltip, 'ts-timeline__tooltip-date', `Дата: ${formatDate(layout.date)}`);
      }
      for (const member of members) {
        const container = members.length > 1 ? document.createElement('div') : tooltip;
        if (members.length > 1) {
          container.className = 'ts-timeline__tooltip-event';
          tooltip.appendChild(container);
        }
        appendText(document, container, members.length > 1 ? 'ts-timeline__tooltip-event-title' : 'ts-timeline__tooltip-title', sourceLabel(member));
        const endLabel = member.isPoint ? '' : `–${formatClock(member.endMs, settings.timezone)}`;
        if (members.length === 1) {
          appendText(document, container, 'ts-timeline__tooltip-date', `Дата: ${formatDate(layout.date)}`);
        }
        appendText(document, container, 'ts-timeline__tooltip-time', `Время: ${formatClock(member.startMs, settings.timezone)}${endLabel}`);
        appendText(document, container, 'ts-timeline__tooltip-type', `Тип: ${member.event_type || 'Не указан'}`);
        if (member.object_type || member.object_id !== null && member.object_id !== undefined) {
          const identifier = member.object_id === null || member.object_id === undefined ? '' : ` #${member.object_id}`;
          appendText(document, container, 'ts-timeline__tooltip-object', `Объект: ${member.object_type || 'Не указан'}${identifier}`);
        }
        appendText(document, container, 'ts-timeline__tooltip-description', `Описание: ${member.description || member.message || 'Нет описания'}`);
        appendText(document, container, 'ts-timeline__tooltip-source', `Источник: ${sourceName(member.source)}`);
        appendText(document, container, 'ts-timeline__tooltip-duration', `Длительность: ${Math.max(0, Number(member.duration_seconds) || 0)} сек.`);
        appendText(document, container, 'ts-timeline__tooltip-duration-source', `Способ определения: ${durationSourceName(member.duration_source)}`);
        if (member.call_direction) {
          appendText(document, container, 'ts-timeline__tooltip-call-direction', `Направление звонка: ${callDirectionName(member.call_direction)}`);
        }
        if (member.call_duration_seconds !== null && member.call_duration_seconds !== undefined) {
          appendText(document, container, 'ts-timeline__tooltip-call', `Длительность звонка: ${member.call_duration_seconds} сек.`);
        }
        const href = safeCardUrl(document, member.card_url);
        if (href) {
          const link = document.createElement('a');
          link.href = href;
          link.target = '_blank';
          link.rel = 'noopener noreferrer';
          link.textContent = 'Открыть карточку';
          container.appendChild(link);
        }
      }
      anchor.setAttribute('aria-expanded', 'true');
      activeAnchor = anchor;
      activeState = interactionState;
      root.appendChild(tooltip);
    }

    for (const item of groupRenderItems(layout.items)) {
      const element = document.createElement('button');
      element.type = 'button';
      element.setAttribute('role', 'button');
      element.className = 'ts-timeline__item';
      if (item.isPoint) {
        element.classList.add('ts-timeline__item--point', `ts-timeline__item--${item.kind}-point`);
        if (item.members.length > 1) element.classList.add('ts-timeline__item--cluster');
      } else {
        element.classList.add(`ts-timeline__item--${item.kind === 'confirmed' ? 'confirmed' : item.kind === 'mixed' ? 'mixed' : 'unconfirmed'}`);
        if (item.members.length > 1) element.classList.add('ts-timeline__item--cluster');
      }
      element.style.left = `${item.left}px`;
      element.style.width = `${item.width}px`;
      element.style.top = '5px';
      element.setAttribute('aria-expanded', 'false');
      const itemLabel = item.members.length > 1 ? `${item.members.length} события` : sourceLabel(item);
      element.setAttribute('aria-label', `${itemLabel}, ${formatClock(item.startMs, settings.timezone)}`);
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
