(function(root, factory) {
    if (typeof define === 'function' && define.amd) define(factory);
    else if (typeof module === 'object' && module.exports) module.exports = factory();
    else root.TimesheetOverlay = factory();
})(this, function() {
    var actions = {
        not_started: [['start-work', 'Начать рабочий день']],
        working: [['start-break', 'Перерыв'], ['finish-work', 'Завершить день']],
        on_break: [['end-break', 'Продолжить'], ['finish-work', 'Завершить день']],
        finished: []
    };
    function createOverlay(doc) {
        var host = null, trap = null, command = null;
        function clear() {
            if (trap) doc.removeEventListener('keydown', trap, true);
            trap = null;
            if (host) host.remove();
            host = null;
            command = null;
        }
        function render(snapshot, onCommand) {
            clear();
            if (!snapshot || !snapshot.track_time || snapshot.hide_widget || !actions[snapshot.status]) return;
            command = onCommand;
            var blocked = snapshot.status !== 'working';
            host = doc.createElement('div');
            host.className = blocked ? 'timesheet-overlay timesheet-overlay--blocked' : 'timesheet-actions';
            if (blocked) {
                host.setAttribute('role', 'dialog');
                host.setAttribute('aria-modal', 'true');
                var shade = doc.createElement('div');
                shade.className = 'timesheet-overlay__shade';
                host.appendChild(shade);
            }
            var panel = doc.createElement('div');
            panel.className = 'timesheet-overlay__panel';
            var permitted = snapshot.status === 'finished' && snapshot.restart_allowed ?
                [['start-work', 'Начать рабочий день']] : actions[snapshot.status];
            permitted.forEach(function(item) {
                var button = doc.createElement('button');
                button.type = 'button';
                button.className = 'timesheet-action';
                button.dataset.action = item[0];
                button.textContent = item[1];
                button.addEventListener('click', function() { if (command) command(item[0]); });
                panel.appendChild(button);
            });
            host.appendChild(panel);
            doc.body.appendChild(host);
            if (blocked) {
                trap = function(event) {
                    if (host && !host.contains(doc.activeElement) &&
                        (event.key === 'Tab' || event.key === 'Enter' || event.key === ' ')) {
                        event.preventDefault();
                        event.stopPropagation();
                        var first = panel.querySelector('button');
                        if (first) first.focus();
                    }
                };
                doc.addEventListener('keydown', trap, true);
                var first = panel.querySelector('button');
                if (first) first.focus();
            }
        }
        return { render: render, clear: clear };
    }
    return { createOverlay: createOverlay };
});
