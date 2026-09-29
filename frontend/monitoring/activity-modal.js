(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory(require('./timeline'));
  } else if (typeof define === 'function' && define.amd) {
    define(['./timeline'], factory);
  } else {
    root.TimesheetActivityModal = factory(root.TimesheetTimeline);
  }
}(typeof self !== 'undefined' ? self : this, function (Timeline) {
  'use strict';

  function create(options) {
    const settings = options || {};
    const document = settings.document || (typeof window !== 'undefined' ? window.document : null);
    if (!document || !Timeline) throw new TypeError('Document and Timeline are required');
    const mount = settings.mount || document.body;
    const overlay = document.createElement('div');
    overlay.className = 'ts-activity-modal';
    overlay.hidden = true;

    const panel = document.createElement('section');
    panel.className = 'ts-activity-modal__panel';
    panel.setAttribute('role', 'dialog');
    panel.setAttribute('aria-modal', 'true');
    panel.setAttribute('aria-labelledby', 'ts-activity-modal-title');
    overlay.appendChild(panel);

    const header = document.createElement('header');
    header.className = 'ts-activity-modal__header';
    const title = document.createElement('h2');
    title.id = 'ts-activity-modal-title';
    title.className = 'ts-activity-modal__title';
    const closeButton = document.createElement('button');
    closeButton.type = 'button';
    closeButton.className = 'ts-activity-modal__close';
    closeButton.setAttribute('aria-label', 'Закрыть');
    closeButton.textContent = '×';
    header.append(title, closeButton);
    panel.appendChild(header);

    const controls = document.createElement('div');
    controls.className = 'ts-activity-modal__controls';
    const zoomLabel = document.createElement('span');
    zoomLabel.textContent = 'Масштаб:';
    controls.appendChild(zoomLabel);
    const zoomButtons = [1, 2, 4].map((value) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.dataset.zoom = String(value);
      button.textContent = `${value}×`;
      button.setAttribute('aria-label', `Масштаб ${value}`);
      controls.appendChild(button);
      return button;
    });
    panel.appendChild(controls);

    const totals = document.createElement('div');
    totals.className = 'ts-activity-modal__totals';
    panel.appendChild(totals);
    const content = document.createElement('div');
    content.className = 'ts-activity-modal__content';
    panel.appendChild(content);
    const state = document.createElement('div');
    state.className = 'ts-activity-modal__state';
    state.setAttribute('role', 'status');
    panel.appendChild(state);

    const footer = document.createElement('footer');
    footer.className = 'ts-activity-modal__footer';
    const fullscreenButton = document.createElement('button');
    fullscreenButton.type = 'button';
    fullscreenButton.className = 'ts-activity-modal__fullscreen';
    fullscreenButton.setAttribute('aria-pressed', 'false');
    fullscreenButton.textContent = 'На весь экран';
    footer.appendChild(fullscreenButton);
    panel.appendChild(footer);
    mount.appendChild(overlay);

    let opened = false;
    let destroyed = false;
    let payload = null;
    let zoom = 1;
    let previousFocus = null;
    let previousOverflow = '';
    let fullscreen = false;
    let timelines = [];

    function formatDuration(seconds) {
      const value = Math.max(0, Number(seconds) || 0);
      const hours = Math.floor(value / 3600);
      const minutes = Math.floor((value % 3600) / 60);
      if (hours && minutes) return `${hours} ч ${minutes} мин`;
      if (hours) return `${hours} ч`;
      return `${minutes} мин`;
    }

    function clearTimelines() {
      for (const timeline of timelines) timeline.destroy();
      timelines = [];
      content.replaceChildren();
    }

    function render() {
      clearTimelines();
      const target = payload && payload.target;
      title.textContent = target && target.name ? String(target.name) : 'Активность сотрудника';
      for (const button of zoomButtons) button.setAttribute('aria-pressed', String(Number(button.dataset.zoom) === zoom));
      totals.textContent = '';
      state.textContent = '';
      state.hidden = true;
      content.hidden = true;
      totals.hidden = true;

      if (!payload || payload.state === 'loading') {
        state.textContent = 'Загрузка активности…';
        state.hidden = false;
        return;
      }
      if (payload.state === 'error') {
        state.textContent = 'Не удалось загрузить активность. Попробуйте ещё раз.';
        state.hidden = false;
        return;
      }
      const days = Array.isArray(payload.days) ? payload.days : [];
      if (!days.length) {
        state.textContent = 'За выбранные дни нет данных.';
        state.hidden = false;
        return;
      }

      const summary = payload.totals || {};
      totals.textContent = `Подтверждено: ${formatDuration(summary.confirmed_seconds)} · Событий: ${Number(summary.confirmed_events) || 0}`;
      totals.hidden = false;
      content.hidden = false;
      for (const item of days) {
        const row = document.createElement('section');
        row.className = 'ts-activity-modal__day';
        content.appendChild(row);
        timelines.push(Timeline.render(row, item, { zoom, timezone: payload.timezone }));
      }
    }

    function setFullscreen(active) {
      fullscreen = Boolean(active);
      panel.classList.toggle('ts-activity-modal__panel--fullscreen', fullscreen);
      fullscreenButton.setAttribute('aria-pressed', String(fullscreen));
      fullscreenButton.textContent = fullscreen ? 'Свернуть' : 'На весь экран';
    }

    function onFullscreenChange() {
      if (document.fullscreenElement !== panel && fullscreen) setFullscreen(false);
    }

    async function toggleFullscreen() {
      if (!fullscreen) {
        setFullscreen(true);
        if (typeof panel.requestFullscreen === 'function') {
          try { await panel.requestFullscreen(); } catch (_error) { /* CSS fallback stays active. */ }
        }
      } else {
        if (document.fullscreenElement === panel && typeof document.exitFullscreen === 'function') {
          try { await document.exitFullscreen(); } catch (_error) { /* CSS state still closes. */ }
        }
        setFullscreen(false);
      }
    }

    function focusable() {
      return Array.from(panel.querySelectorAll('button:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])'))
        .filter((element) => !element.hidden);
    }

    function onKeydown(event) {
      if (!opened) return;
      if (event.key === 'Escape') {
        event.preventDefault();
        close();
        return;
      }
      if (event.key !== 'Tab') return;
      const nodes = focusable();
      if (!nodes.length) return;
      const first = nodes[0];
      const last = nodes[nodes.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    function open(nextPayload, openOptions) {
      if (destroyed) throw new Error('Activity modal is destroyed');
      payload = nextPayload || { state: 'loading' };
      if (!opened) {
        const trigger = openOptions && openOptions.trigger;
        previousFocus = trigger && typeof trigger.focus === 'function' ? trigger : document.activeElement;
        previousOverflow = document.body.style.overflow;
        document.body.style.overflow = 'hidden';
        document.body.classList.add('ts-modal-open');
        overlay.hidden = false;
        opened = true;
        document.addEventListener('keydown', onKeydown);
      }
      render();
      closeButton.focus();
    }

    function update(nextPayload) {
      if (destroyed) return;
      payload = nextPayload;
      if (opened) render();
    }

    function close() {
      if (!opened) return;
      if (document.fullscreenElement === panel && typeof document.exitFullscreen === 'function') {
        Promise.resolve(document.exitFullscreen()).catch(() => {});
      }
      setFullscreen(false);
      clearTimelines();
      overlay.hidden = true;
      opened = false;
      document.removeEventListener('keydown', onKeydown);
      document.body.style.overflow = previousOverflow;
      document.body.classList.remove('ts-modal-open');
      if (previousFocus && typeof previousFocus.focus === 'function' && previousFocus.isConnected) previousFocus.focus();
      previousFocus = null;
    }

    function destroy() {
      if (destroyed) return;
      close();
      closeButton.removeEventListener('click', close);
      fullscreenButton.removeEventListener('click', toggleFullscreen);
      for (const button of zoomButtons) button.removeEventListener('click', onZoomClick);
      document.removeEventListener('fullscreenchange', onFullscreenChange);
      overlay.remove();
      destroyed = true;
    }

    closeButton.addEventListener('click', close);
    fullscreenButton.addEventListener('click', toggleFullscreen);
    document.addEventListener('fullscreenchange', onFullscreenChange);
    function onZoomClick(event) {
      zoom = Number(event.currentTarget.dataset.zoom);
      if (opened) render();
    }
    for (const button of zoomButtons) button.addEventListener('click', onZoomClick);

    return { open, update, close, destroy, isOpen: () => opened };
  }

  return { create };
}));
