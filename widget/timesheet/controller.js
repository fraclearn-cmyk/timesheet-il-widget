(function(root, factory) {
    if (typeof define === 'function') define(factory);
    else if (typeof module === 'object' && module.exports) module.exports = factory();
})(this, function() {
    var paths = { 'start-work': true, 'start-break': true, 'end-break': true, 'finish-work': true };
    function validLateness(value) {
        if (typeof value.late_reason_required !== 'boolean' || !Number.isSafeInteger(value.late_minutes) ||
            value.late_minutes < 0 || !(value.break_sequence === null ||
            (Number.isSafeInteger(value.break_sequence) && value.break_sequence > 0))) return false;
        if (value.late_reason_kind === null) return !value.late_reason_required &&
            value.late_minutes === 0 && value.break_sequence === null;
        if (value.late_minutes === 0) return false;
        if (value.late_reason_kind === 'shift_start') return value.break_sequence === null &&
            (value.status === 'not_started' || (value.status === 'finished' && value.restart_allowed));
        return value.late_reason_kind === 'break_return' && value.status === 'on_break' && value.break_sequence !== null;
    }
    function valid(value) {
        return value && typeof value === 'object' &&
            ['not_started', 'working', 'on_break', 'finished'].indexOf(value.status) !== -1 &&
            (value.session_id === null || Number.isInteger(value.session_id)) &&
            typeof value.track_time === 'boolean' && typeof value.hide_widget === 'boolean' &&
            typeof value.restart_allowed === 'boolean' && typeof value.break_seconds === 'number' &&
            (value.started_at === null || typeof value.started_at === 'string') &&
            (value.ended_at === null || typeof value.ended_at === 'string') && validLateness(value);
    }
    function createTimesheetController(options) {
        var confirmed = null, pending = null, inFlight = null, cancelRetry = null, destroyed = false, generation = 0;
        var loading = null, loadGeneration = 0;
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
        function failOpen() {
            confirmed = null;
            if (typeof options.onSnapshot === 'function') options.onSnapshot(null);
            options.clear();
            retry();
        }
        function accept(snapshot) {
            if (!valid(snapshot)) { failOpen(); return false; }
            confirmed = snapshot;
            if (typeof options.onSnapshot === 'function') options.onSnapshot(snapshot);
            if (snapshot.track_time && !snapshot.hide_widget) options.render(snapshot);
            else options.clear();
            retry(30000);
            return true;
        }
        function load() {
            if (destroyed) return Promise.resolve();
            // A focus/health refresh must never supersede an unconfirmed command.
            if (pending) return command(pending.action);
            // Share the active GET so focus cannot renew its availability deadline.
            if (loading && loadGeneration === generation) return loading;
            clearRetry();
            var currentGeneration = ++generation;
            loadGeneration = currentGeneration;
            loading = request({ url: '/timesheet/my-status', method: 'GET', dataType: 'json' })
            .then(function(snapshot) { if (!destroyed && currentGeneration === generation) accept(snapshot); }, function() {
                if (!destroyed && currentGeneration === generation) failOpen();
            }).finally(function() {
                if (currentGeneration === loadGeneration) loading = null;
            });
            return loading;
        }
        function command(action, reason) {
            if (destroyed || !paths[action] || (!confirmed && !pending) ||
                (confirmed && (!confirmed.track_time || confirmed.hide_widget))) return Promise.resolve();
            if (inFlight) return inFlight;
            if (pending && pending.action !== action) return Promise.resolve();
            clearRetry();
            if (!pending) pending = { action: action, key: options.uuid(),
                reason: (action === 'start-work' || action === 'end-break') && typeof reason === 'string' ? reason.trim() : '' };
            var current = pending;
            var payload = { idempotency_key: current.key };
            if (current.reason) payload.reason = current.reason;
            var currentGeneration = ++generation;
            inFlight = request({ url: '/timesheet/' + action, method: 'POST', dataType: 'json',
                    contentType: 'application/json', data: JSON.stringify(payload) })
            .then(function(snapshot) {
                if (destroyed || currentGeneration !== generation) return;
                if (accept(snapshot)) pending = null;
            }, function(error) {
                if (destroyed || currentGeneration !== generation) return;
                if (error && error.status === 409) {
                    pending = null;
                    var body = error.responseJSON || error;
                    // A requirement may appear between GET and POST. Keep the owned
                    // draft during this refresh; a failed GET still clears all UI.
                    if (!(body.error && body.error.code === 'LATE_REASON_REQUIRED')) failOpen();
                    return load();
                }
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
