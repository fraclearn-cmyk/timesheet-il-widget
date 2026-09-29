define(['jquery', './settings/settings', './timesheet/controller', './overlay', './activity-tracker', './monitoring/timeline', './monitoring/activity-modal', './monitoring/dashboard'], function($, SettingsController, TimesheetController, Overlay, ActivityTracker, Timeline, ActivityModal, MonitoringDashboard) {
    function apiUrl(widget) {
        var settings = widget.get_settings();
        return settings && settings.api_url ? String(settings.api_url).replace(/\/+$/, '') : null;
    }

    function toPromise(request) {
        return Promise.resolve(request).catch(function(error) {
            if (error && typeof error.getResponseHeader === 'function') error.retryAfter = error.getResponseHeader('Retry-After');
            throw error;
        });
    }

    function createSettingsTransport(widget) {
        return {
            load: function() { return toPromise(widget.$authorizedAjax({ url: apiUrl(widget) + '/settings/snapshot', method: 'GET', dataType: 'json' })); },
            save: function(payload) { return toPromise(widget.$authorizedAjax({ url: apiUrl(widget) + '/settings/snapshot', method: 'PUT', contentType: 'application/json', dataType: 'json', data: JSON.stringify(payload) })); }
        };
    }

    function uuid() {
        if (typeof crypto !== 'undefined' && crypto.randomUUID) return crypto.randomUUID();
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
            var r = Math.random() * 16 | 0;
            return (c === 'x' ? r : (r & 3 | 8)).toString(16);
        });
    }

    var CustomWidget = function() {
        var widget = this;
        this.settingsController = null;
        this.settingsMount = null;
        this.settingsStyle = null;
        this.timesheetController = null;
        this.activityTracker = null;
        this.workingStyle = null;
        this.workingStyleTimer = null;
        this.removeFocusRefresh = null;
        this.monitoringController = null;
        this.monitoringHost = null;
        this.monitoringStyle = null;
        this.monitoringStyleTimer = null;
        this.timesheetOverlay = Overlay.createOverlay(document);

        this.clearTimesheetStatus = function() { widget.timesheetOverlay.clear(); };
        this.renderTimesheetStatus = function(snapshot, command) { widget.timesheetOverlay.render(snapshot, command); };

        function removeSettings() {
            if (widget.settingsController) widget.settingsController.destroy();
            if (widget.settingsMount) widget.settingsMount.remove();
            if (widget.settingsStyle) widget.settingsStyle.remove();
            widget.settingsController = null;
            widget.settingsMount = null;
            widget.settingsStyle = null;
        }
        function clearWorkingUi() { if (typeof widget.clearTimesheetStatus === 'function') widget.clearTimesheetStatus(); }
        function stopMonitoring() {
            clearTimeout(widget.monitoringStyleTimer);
            widget.monitoringStyleTimer = null;
            if (widget.monitoringController) widget.monitoringController.destroy();
            widget.monitoringController = null;
            if (widget.monitoringHost) widget.monitoringHost.remove();
            widget.monitoringHost = null;
            if (widget.monitoringStyle) {
                widget.monitoringStyle.onload = widget.monitoringStyle.onerror = null;
                widget.monitoringStyle.remove();
            }
            widget.monitoringStyle = null;
        }
        function monitoringRequest(options, signal) {
            if (signal && signal.aborted) return Promise.reject(new DOMException('Aborted', 'AbortError'));
            var request = widget.$authorizedAjax(options);
            if (signal && request && typeof request.abort === 'function') {
                var abort = function() { request.abort(); };
                signal.addEventListener('abort', abort, { once: true });
            }
            return toPromise(request);
        }
        function startMonitoring(baseUrl, settings) {
            stopMonitoring();
            if (!MonitoringDashboard || typeof MonitoringDashboard.mount !== 'function' || !settings.path) return;
            var style = document.createElement('link');
            style.rel = 'stylesheet';
            style.href = String(settings.path).replace(/\/?$/, '/') + 'monitoring/styles.css?v=' + encodeURIComponent(settings.version || '');
            widget.monitoringStyle = style;
            function finishStyleLoad() {
                clearTimeout(widget.monitoringStyleTimer);
                widget.monitoringStyleTimer = null;
                style.onload = style.onerror = null;
            }
            style.onload = finishStyleLoad;
            style.onerror = finishStyleLoad;
            widget.monitoringStyleTimer = setTimeout(finishStyleLoad, 10000);
            document.head.appendChild(style);

            var host = document.createElement('aside');
            host.className = 'ts-monitoring-widget';
            var launcher = document.createElement('button');
            launcher.type = 'button';
            launcher.className = 'ts-monitoring-widget__launcher';
            launcher.textContent = 'Сотрудники';
            launcher.setAttribute('aria-expanded', 'false');
            var panel = document.createElement('div');
            panel.className = 'ts-monitoring-widget__panel';
            panel.hidden = true;
            launcher.addEventListener('click', function() {
                panel.hidden = !panel.hidden;
                launcher.setAttribute('aria-expanded', String(!panel.hidden));
            });
            host.appendChild(launcher);
            host.appendChild(panel);
            document.body.appendChild(host);
            widget.monitoringHost = host;
            widget.monitoringController = MonitoringDashboard.mount(panel, {
                document: document,
                transport: {
                    status: function(params, signal) {
                        return monitoringRequest({ url: baseUrl + '/team/status', method: 'GET', dataType: 'json', timeout: 10000, data: params }, signal);
                    },
                    activity: function(userId, fromDate, toDate, signal) {
                        return monitoringRequest({ url: baseUrl + '/team/' + encodeURIComponent(userId) + '/activity', method: 'GET', dataType: 'json', timeout: 10000,
                            data: { from: fromDate, to: toDate } }, signal);
                    }
                },
                schedule: function(fn, delay) { var timer = setTimeout(fn, delay); return function() { clearTimeout(timer); }; },
                now: function() { return new Date(); },
                random: Math.random
            });
        }
        function renderWorkingUi(snapshot) {
            if (typeof widget.renderTimesheetStatus === 'function') {
                widget.renderTimesheetStatus(snapshot, function(action) { return widget.timesheetController.command(action); });
            }
        }
        function stopTimesheet() {
            stopMonitoring();
            clearTimeout(widget.workingStyleTimer);
            widget.workingStyleTimer = null;
            if (widget.workingStyle) {
                widget.workingStyle.onload = widget.workingStyle.onerror = null;
                widget.workingStyle.remove();
            }
            widget.workingStyle = null;
            if (widget.removeFocusRefresh) widget.removeFocusRefresh();
            widget.removeFocusRefresh = null;
            if (widget.timesheetController) widget.timesheetController.destroy();
            widget.timesheetController = null;
            if (widget.activityTracker) widget.activityTracker.destroy();
            widget.activityTracker = null;
            clearWorkingUi();
        }
        function startTimesheet() {
            var baseUrl = apiUrl(widget);
            stopTimesheet();
            if (!baseUrl || typeof widget.$authorizedAjax !== 'function') return;
            var settings = widget.get_settings();
            if (!settings.path) return;
            var style = document.createElement('link');
            style.rel = 'stylesheet';
            style.href = String(settings.path).replace(/\/?$/, '/') + 'styles.css?v=' + encodeURIComponent(settings.version || '');
            widget.workingStyle = style;
            style.onerror = stopTimesheet;
            widget.workingStyleTimer = setTimeout(stopTimesheet, 10000);
            style.onload = function() {
                if (widget.workingStyle !== style) return;
                clearTimeout(widget.workingStyleTimer);
                widget.workingStyleTimer = null;
                style.onload = style.onerror = null;
                startMonitoring(baseUrl, settings);
                startController(baseUrl);
            };
            document.head.appendChild(style);
        }
        function startController(baseUrl) {
            if (ActivityTracker && typeof ActivityTracker.createActivityTracker === 'function') {
                widget.activityTracker = ActivityTracker.createActivityTracker({
                    document: document,
                    request: function(payload) {
                        return toPromise(widget.$authorizedAjax({
                            url: baseUrl + '/activity/presence', method: 'POST', dataType: 'json',
                            contentType: 'application/json', timeout: 10000, data: JSON.stringify(payload)
                        }));
                    },
                    schedule: function(fn, delay) { var timer = setTimeout(fn, delay); return function() { clearTimeout(timer); }; },
                    now: function() { return new Date(); },
                    uuid: uuid
                });
            }
            widget.timesheetController = TimesheetController.createTimesheetController({
                request: function(request) {
                    var options = { url: baseUrl + request.url, method: request.method, dataType: request.dataType, timeout: 10000 };
                    if (request.contentType) options.contentType = request.contentType;
                    if (request.data) options.data = request.data;
                    return toPromise(widget.$authorizedAjax(options));
                },
                render: renderWorkingUi,
                clear: clearWorkingUi,
                onSnapshot: function(snapshot) {
                    if (widget.activityTracker) widget.activityTracker.updateSnapshot(snapshot);
                },
                schedule: function(fn, delay) { var timer = setTimeout(fn, delay); return function() { clearTimeout(timer); }; },
                uuid: uuid
            });
            widget.timesheetController.load();
            var refresh = function() { widget.timesheetController.load(); };
            window.addEventListener('focus', refresh);
            widget.removeFocusRefresh = function() { window.removeEventListener('focus', refresh); };
        }

        this.callbacks = {
            render: function() { return true; },
            init: function() {
                var area = typeof widget.system === 'function' && widget.system().area;
                if (area === 'settings' || area === 'advanced_settings') { stopTimesheet(); return true; }
                startTimesheet();
                return true;
            },
            bind_actions: function() { return true; },
            settings: function() { stopTimesheet(); return true; },
            advancedSettings: function() {
                stopTimesheet();
                if (typeof widget.system !== 'function' || widget.system().area !== 'advanced_settings') return false;
                removeSettings();
                var holder = document.getElementById('list_page_holder');
                if (!holder) return false;
                var mount = document.createElement('div');
                mount.className = 'timesheet-settings__host';
                holder.appendChild(mount);
                widget.settingsMount = mount;
                var url = apiUrl(widget);
                if (!url) { mount.textContent = 'Укажите URL API в настройках установки виджета.'; return true; }
                var settings = widget.get_settings();
                if (settings.path) {
                    var style = document.createElement('link');
                    style.rel = 'stylesheet';
                    style.href = String(settings.path).replace(/\/?$/, '/') + 'settings/settings.css?v=' + encodeURIComponent(settings.version || '');
                    document.head.appendChild(style);
                    widget.settingsStyle = style;
                }
                widget.settingsController = SettingsController.mount(mount, createSettingsTransport(widget));
                widget.settingsController.ready.catch(function() {});
                return true;
            },
            onSave: function() {
                if (typeof widget.system !== 'function' || widget.system().area !== 'advanced_settings') return true;
                var controller = widget.settingsController;
                return !controller ? true : (controller.snapshot ? controller.save() : controller.ready.then(function() { return controller.save(); }));
            },
            destroy: function() {
                removeSettings();
                stopTimesheet();
                return true;
            }
        };
    };
    return CustomWidget;
});
