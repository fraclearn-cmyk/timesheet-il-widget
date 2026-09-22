(function(root, factory) {
    if (typeof define === 'function' && define.amd) define(factory);
    else if (typeof module === 'object' && module.exports) module.exports = factory();
})(this, function() {
    var paths = { 'start-work': true, 'start-break': true, 'end-break': true, 'finish-work': true };
    function valid(value) {
        return value && typeof value === 'object' &&
            ['not_started', 'working', 'on_break', 'finished'].indexOf(value.status) !== -1 &&
            (value.session_id === null || Number.isInteger(value.session_id)) &&
            typeof value.track_time === 'boolean' && typeof value.hide_widget === 'boolean' &&
            typeof value.restart_allowed === 'boolean' && typeof value.break_seconds === 'number' &&
            (value.started_at === null || typeof value.started_at === 'string') &&
            (value.ended_at === null || typeof value.ended_at === 'string');
    }
    function createTimesheetController(options) {
        var confirmed = null, pending = null, inFlight = null, cancelRetry = null, destroyed = false, generation = 0;
        var deadlines = new Set();
        function clearRetry() { if (cancelRetry) cancelRetry(); cancelRetry = null; }
        function retry(delay) {
            clearRetry();
            if (!destroyed) cancelRetry = options.schedule(function() {
                cancelRetry = null; if (pending) command(pending.action); else load();
            }, delay || 5000);
        }
        function request(optionsForRequest) {
            return new Promise(function(resolve, reject) {
                var settled = false;
                function finish(error, value) {
                    if (settled) return;
                    settled = true;
                    cancelDeadline();
                    deadlines.delete(cancel);
                    if (error) reject(error); else resolve(value);
                }
                function cancel() { finish(new Error('Request cancelled')); }
                var cancelDeadline = options.schedule(function() { finish(new Error('Request timeout')); }, 10000);
                deadlines.add(cancel);
                Promise.resolve().then(function() { return options.request(optionsForRequest); })
                    .then(function(value) { finish(null, value); }, function(error) { finish(error || new Error('Request failed')); });
            });
        }
        function failOpen() { confirmed = null; options.clear(); retry(); }
        function accept(snapshot) {
            if (!valid(snapshot)) { failOpen(); return false; }
            confirmed = snapshot;
            options.clear();
            if (snapshot.track_time && !snapshot.hide_widget) options.render(snapshot);
            retry(30000);
            return true;
        }
        function load() {
            if (destroyed) return Promise.resolve();
            // A focus/health refresh must never supersede an unconfirmed command.
            if (pending) return command(pending.action);
            clearRetry();
            var currentGeneration = ++generation;
            return request({ url: '/timesheet/my-status', method: 'GET', dataType: 'json' })
            .then(function(snapshot) { if (!destroyed && currentGeneration === generation) accept(snapshot); }, function() {
                if (!destroyed && currentGeneration === generation) failOpen();
            });
        }
        function command(action) {
            if (destroyed || !paths[action] || (!confirmed && !pending) ||
                (confirmed && (!confirmed.track_time || confirmed.hide_widget))) return Promise.resolve();
            if (inFlight) return inFlight;
            if (pending && pending.action !== action) return Promise.resolve();
            clearRetry();
            if (!pending) pending = { action: action, key: options.uuid() };
            var current = pending;
            var currentGeneration = ++generation;
            inFlight = request({ url: '/timesheet/' + action, method: 'POST', dataType: 'json',
                    contentType: 'application/json', data: JSON.stringify({ idempotency_key: current.key }) })
            .then(function(snapshot) {
                if (destroyed || currentGeneration !== generation) return;
                if (accept(snapshot)) pending = null;
            }, function(error) {
                if (destroyed || currentGeneration !== generation) return;
                if (error && error.status === 409) { pending = null; failOpen(); return load(); }
                failOpen();
            }).finally(function() { inFlight = null; });
            return inFlight;
        }
        function destroy() {
            destroyed = true; generation++; clearRetry();
            deadlines.forEach(function(cancel) { cancel(); });
            confirmed = null; pending = null; options.clear();
        }
        return { load: load, command: command, destroy: destroy };
    }
    return { createTimesheetController: createTimesheetController };
});
