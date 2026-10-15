(function(root, factory) {
    if (typeof define === 'function') define(factory);
    else if (typeof module === 'object' && module.exports) module.exports = factory();
    else root.TimesheetOverlay = factory();
})(this, function() {
    var actions = {
        not_started: [['start-work', 'Начать рабочий день']],
        working: [['start-break', 'Перерыв'], ['finish-work', 'Завершить день']],
        on_break: [['end-break', 'Продолжить работу'], ['finish-work', 'Завершить день']],
        finished: []
    };
    var reasonSequence = 0;
    function createOverlay(doc) {
        var host = null, trap = null, command = null, reasonInput = null, reasonContext = null, listeners = [];
        function listen(node, type, handler) {
            node.addEventListener(type, handler);
            listeners.push(function() { node.removeEventListener(type, handler); });
        }
        function clear() {
            if (trap) ['keydown', 'keyup', 'keypress'].forEach(function(type) {
                doc.removeEventListener(type, trap, true);
            });
            trap = null;
            listeners.forEach(function(remove) { remove(); });
            listeners = [];
            if (reasonInput) reasonInput.value = '';
            reasonInput = null;
            reasonContext = null;
            if (host) host.remove();
            host = null;
            command = null;
        }
        function render(snapshot, onCommand) {
            var context = snapshot ? JSON.stringify([snapshot.session_id, snapshot.status,
                snapshot.late_reason_kind, snapshot.break_sequence]) : null;
            var draft = reasonInput && context === reasonContext ? reasonInput.value : '';
            clear();
            if (!snapshot || !snapshot.track_time || snapshot.hide_widget || !actions[snapshot.status]) return;
            command = onCommand;
            var blocked = snapshot.status !== 'working';
            host = doc.createElement('div');
            host.className = blocked ? 'timesheet-overlay timesheet-overlay--blocked' : 'timesheet-actions';
            if (blocked) {
                host.setAttribute('role', 'dialog');
                host.setAttribute('aria-modal', 'true');
                host.setAttribute('aria-label', 'Учёт рабочего времени');
                var shade = doc.createElement('div');
                shade.className = 'timesheet-overlay__shade';
                host.appendChild(shade);
            }
            var panel = doc.createElement('div');
            panel.className = 'timesheet-overlay__panel';
            var permitted = snapshot.status === 'finished' && snapshot.restart_allowed ?
                [['start-work', 'Начать рабочий день']] : actions[snapshot.status];
            var reasonAction = snapshot.late_reason_required ?
                (snapshot.late_reason_kind === 'break_return' ? 'end-break' : 'start-work') : null;
            var counter = null;
            if (reasonAction) {
                panel.classList.add('timesheet-overlay__panel--reason');
                var prefix = 'timesheet-late-reason-' + (++reasonSequence);
                var explanation = doc.createElement('p');
                explanation.id = prefix + '-message';
                explanation.className = 'timesheet-overlay__message';
                explanation.textContent = (snapshot.late_reason_kind === 'break_return' ?
                    'Опоздание с перерыва №' + snapshot.break_sequence : 'Опоздание к началу дня') +
                    ': ' + snapshot.late_minutes + ' мин.';
                panel.appendChild(explanation);
                var label = doc.createElement('label');
                label.htmlFor = prefix;
                label.textContent = 'Причина опоздания';
                panel.appendChild(label);
                reasonInput = doc.createElement('textarea');
                reasonInput.id = prefix;
                reasonInput.className = 'timesheet-overlay__reason';
                reasonInput.maxLength = 1000;
                reasonInput.rows = 4;
                reasonInput.required = true;
                reasonInput.value = draft;
                reasonInput.setAttribute('aria-describedby', explanation.id + ' ' + prefix + '-count');
                reasonContext = context;
                panel.appendChild(reasonInput);
                counter = doc.createElement('p');
                counter.id = prefix + '-count';
                counter.className = 'timesheet-overlay__reason-count';
                panel.appendChild(counter);
            }
            if (blocked && snapshot.status === 'finished' && !permitted.length) {
                var message = doc.createElement('p');
                message.className = 'timesheet-overlay__message';
                message.textContent = 'Рабочий день завершён. Для повторного начала требуется разрешение администратора.';
                panel.appendChild(message);
            }
            permitted.forEach(function(item) {
                var button = doc.createElement('button');
                button.type = 'button';
                button.className = 'timesheet-action';
                button.dataset.action = item[0];
                button.textContent = item[1];
                if (item[0] === reasonAction) {
                    var update = function() {
                        button.disabled = !reasonInput.value.trim() || reasonInput.value.length > 1000;
                        counter.textContent = reasonInput.value.length + ' / 1000';
                    };
                    listen(reasonInput, 'input', update);
                    update();
                }
                listen(button, 'click', function() {
                    if (command && !button.disabled) command(item[0], item[0] === reasonAction ? reasonInput.value : undefined);
                });
                panel.appendChild(button);
            });
            if (blocked && !permitted.length) panel.tabIndex = -1;
            host.appendChild(panel);
            doc.body.appendChild(host);
            if (blocked) {
                trap = function(event) {
                    if (!host) return;
                    if (event.target && typeof event.target.closest === 'function' &&
                        event.target.closest('.ts-monitoring-widget, .ts-reports-widget')) return;
                    event.stopImmediatePropagation();
                    var controls = panel.querySelectorAll('textarea, button:not(:disabled)');
                    var first = controls[0] || panel;
                    var last = controls[controls.length - 1] || panel;
                    if (event.type === 'keydown' && event.key === 'Tab' &&
                        (!host.contains(doc.activeElement) ||
                         (!event.shiftKey && doc.activeElement === last) ||
                         (event.shiftKey && doc.activeElement === first))) {
                        event.preventDefault();
                        (event.shiftKey ? last : first).focus();
                    } else if (event.key !== 'Tab' && !(panel.contains(event.target) && event.target === reasonInput) &&
                               !(panel.contains(event.target) && event.target.tagName === 'BUTTON' &&
                                 (event.key === 'Enter' || event.key === ' '))) {
                        event.preventDefault();
                        if (!host.contains(doc.activeElement)) first.focus();
                    }
                };
                ['keydown', 'keyup', 'keypress'].forEach(function(type) {
                    doc.addEventListener(type, trap, true);
                });
                (panel.querySelector('textarea, button:not(:disabled)') || panel).focus();
            }
        }
        return { render: render, clear: clear };
    }
    return { createOverlay: createOverlay };
});
