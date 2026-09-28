(function(root, factory) {
    if (typeof define === 'function' && define.amd) define(factory);
    else if (typeof module === 'object' && module.exports) module.exports = factory();
    else root.ActivityTracker = factory();
})(this, function() {
    var BATCH_DELAY = 60000;
    var MAX_SIGNALS = 100000;

    function createActivityTracker(options) {
        var target = options.document || document;
        var active = false;
        var destroyed = false;
        var current = null;
        var pending = null;
        var inFlight = null;
        var cancelTimer = null;
        var generation = 0;
        var lastSendAt = null;

        function clearTimer() {
            if (cancelTimer) cancelTimer();
            cancelTimer = null;
        }

        function scheduleFlush(delay) {
            if (cancelTimer || destroyed || !active || (!current && !pending)) return;
            cancelTimer = options.schedule(function() {
                cancelTimer = null;
                if (pending) sendPending(); else flush();
            }, delay === undefined ? BATCH_DELAY : delay);
        }

        function delayUntilSendAllowed() {
            if (lastSendAt === null) return 0;
            return Math.max(0, BATCH_DELAY - (options.now().getTime() - lastSendAt));
        }

        function sendPending() {
            if (destroyed || !active || !pending || inFlight) return;
            var delay = delayUntilSendAllowed();
            if (delay > 0) {
                scheduleFlush(delay);
                return;
            }
            var batch = pending;
            var requestGeneration = generation;
            lastSendAt = options.now().getTime();
            inFlight = Promise.resolve().then(function() {
                return options.request(batch);
            }).then(function() {
                if (destroyed || !active || requestGeneration !== generation) return;
                if (pending === batch) pending = null;
                if (current) scheduleFlush();
            }, function() {
                if (destroyed || !active || requestGeneration !== generation) return;
                scheduleFlush(delayUntilSendAllowed());
            }).finally(function() {
                if (requestGeneration === generation) inFlight = null;
            });
        }

        function flush() {
            clearTimer();
            if (destroyed || !active) return;
            if (!pending && current) {
                pending = {
                    command_id: options.uuid(),
                    window_started_at: current.window_started_at,
                    last_seen_at: current.last_seen_at,
                    signal_count: current.signal_count
                };
                current = null;
            }
            if (pending && !inFlight) sendPending();
        }

        function recordSignal() {
            if (destroyed || !active) return;
            var observedAt = options.now().toISOString();
            if (!current) current = { window_started_at: observedAt, last_seen_at: observedAt, signal_count: 0 };
            current.last_seen_at = observedAt;
            current.signal_count = Math.min(MAX_SIGNALS, current.signal_count + 1);
            scheduleFlush();
        }

        function visibilityChanged() {
            if (target.visibilityState === 'hidden') flush();
        }

        function updateSnapshot(snapshot) {
            var nextActive = !!snapshot && snapshot.track_time === true && snapshot.status === 'working';
            if (nextActive) {
                active = true;
                return;
            }
            active = false;
            generation += 1;
            clearTimer();
            current = null;
            pending = null;
            inFlight = null;
        }

        function destroy() {
            if (destroyed) return;
            destroyed = true;
            active = false;
            generation += 1;
            clearTimer();
            current = null;
            pending = null;
            inFlight = null;
            target.removeEventListener('pointerdown', recordSignal);
            target.removeEventListener('keydown', recordSignal);
            target.removeEventListener('visibilitychange', visibilityChanged);
        }

        target.addEventListener('pointerdown', recordSignal);
        target.addEventListener('keydown', recordSignal);
        target.addEventListener('visibilitychange', visibilityChanged);
        return { updateSnapshot: updateSnapshot, destroy: destroy };
    }

    return { createActivityTracker: createActivityTracker };
});
