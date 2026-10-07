define(['jquery', './settings/settings.js', './timesheet/controller.js', './overlay.js', './activity-tracker.js', './monitoring/timeline.js', './monitoring/activity-modal.js', './monitoring/dashboard.js', './reports/controller.js'], function($, SettingsController, TimesheetController, Overlay, ActivityTracker, Timeline, ActivityModal, MonitoringDashboard, ReportsController) {
    if (ActivityModal && typeof ActivityModal.setTimeline === 'function') ActivityModal.setTimeline(Timeline);
    if (MonitoringDashboard && typeof MonitoringDashboard.setActivityModal === 'function') MonitoringDashboard.setActivityModal(ActivityModal);

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

    var reportPanelSequence = 0;
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
        this.reportController = null;
        this.reportHost = null;
        this.reportStyle = null;
        this.reportStyleTimer = null;
        this.reportRoleAbort = null;
        this.reportGeneration = 0;
        this.removeReportToggle = null;
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
        function reportError(error) {
            var body = error && error.responseJSON && error.responseJSON.error;
            var message = body && body.message;
            var requestId = body && body.request_id;
            var safeMessage = typeof message === 'string' && message.trim() && message.length <= 250 && !/[\r\n]/.test(message)
                ? message.trim() : undefined;
            if (safeMessage && typeof requestId === 'string' &&
                /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(requestId)) {
                safeMessage += ' Код обращения: ' + requestId + '.';
            }
            return { publicMessage: safeMessage };
        }
        function reportRequest(options, signal, onRequest) {
            if (signal && signal.aborted) return Promise.reject({ publicMessage: undefined });
            var request;
            try { request = widget.$authorizedAjax(options); }
            catch (error) { return Promise.reject(reportError(error)); }
            if (onRequest) onRequest(request);
            return new Promise(function(resolve, reject) {
                var settled = false;
                function finish(callback, value) {
                    if (settled) return;
                    settled = true;
                    if (signal) signal.removeEventListener('abort', onAbort);
                    callback(value);
                }
                function onAbort() {
                    if (request && typeof request.abort === 'function') request.abort();
                    finish(reject, { publicMessage: undefined });
                }
                if (signal) signal.addEventListener('abort', onAbort, { once: true });
                if (signal && signal.aborted) { onAbort(); return; }
                Promise.resolve(request).then(function(value) { finish(resolve, value); }, function(error) { finish(reject, reportError(error)); });
            });
        }
        function safeReportDate(value) {
            return /^\d{4}-\d{2}-\d{2}$/.test(String(value || '')) ? value : '0000-00-00';
        }
        function reportFilename(request, body) {
            var header = request && typeof request.getResponseHeader === 'function'
                ? request.getResponseHeader('Content-Disposition') : null;
            var match = typeof header === 'string' && /^attachment\s*;\s*filename="(timesheet_\d{4}-\d{2}-\d{2}_\d{4}-\d{2}-\d{2}\.xlsx)"\s*$/i.exec(header);
            return match ? match[1] : 'timesheet_' + safeReportDate(body.date_from) + '_' + safeReportDate(body.date_to) + '.xlsx';
        }
        function stopReports() {
            ++widget.reportGeneration;
            if (widget.reportRoleAbort) widget.reportRoleAbort.abort();
            widget.reportRoleAbort = null;
            clearTimeout(widget.reportStyleTimer);
            widget.reportStyleTimer = null;
            if (widget.reportController) widget.reportController.destroy();
            widget.reportController = null;
            if (widget.removeReportToggle) widget.removeReportToggle();
            widget.removeReportToggle = null;
            if (widget.reportHost) widget.reportHost.remove();
            widget.reportHost = null;
            if (widget.reportStyle) {
                widget.reportStyle.onload = widget.reportStyle.onerror = null;
                widget.reportStyle.remove();
            }
            widget.reportStyle = null;
        }
        function startReports(baseUrl, settings) {
            stopReports();
            if (!ReportsController || typeof ReportsController.mount !== 'function' || !settings.path) return;
            var generation = widget.reportGeneration;
            var roleAbort = new AbortController();
            widget.reportRoleAbort = roleAbort;
            reportRequest({ url: baseUrl + '/team/status', method: 'GET', dataType: 'json', timeout: 10000 }, roleAbort.signal).then(function(status) {
                if (roleAbort.signal.aborted || generation !== widget.reportGeneration ||
                    !status || !status.viewer || ['admin', 'manager'].indexOf(status.viewer.role) === -1 ||
                    (typeof widget.system === 'function' && ['settings', 'advanced_settings'].indexOf(widget.system().area) !== -1)) return;
                widget.reportRoleAbort = null;
                var style = document.createElement('link');
                style.rel = 'stylesheet';
                style.href = String(settings.path).replace(/\/?$/, '/') + 'reports/styles.css?v=' + encodeURIComponent(settings.version || '');
                widget.reportStyle = style;
                function finishStyleLoad() {
                    clearTimeout(widget.reportStyleTimer);
                    widget.reportStyleTimer = null;
                    style.onload = style.onerror = null;
                }
                style.onload = finishStyleLoad;
                style.onerror = finishStyleLoad;
                widget.reportStyleTimer = setTimeout(finishStyleLoad, 10000);
                document.head.appendChild(style);
                var host = document.createElement('aside');
                host.className = 'ts-reports-widget';
                var launcher = document.createElement('button');
                launcher.type = 'button';
                launcher.className = 'ts-reports-widget__launcher';
                launcher.textContent = 'Табель';
                launcher.setAttribute('aria-expanded', 'false');
                var panel = document.createElement('div');
                panel.className = 'ts-reports-widget__panel';
                do { panel.id = 'ts-reports-widget-panel-' + (++reportPanelSequence); }
                while (document.getElementById(panel.id));
                launcher.setAttribute('aria-controls', panel.id);
                panel.hidden = true;
                var toggle = function() {
                    panel.hidden = !panel.hidden;
                    launcher.setAttribute('aria-expanded', String(!panel.hidden));
                };
                launcher.addEventListener('click', toggle);
                widget.removeReportToggle = function() { launcher.removeEventListener('click', toggle); };
                host.appendChild(launcher);
                host.appendChild(panel);
                document.body.appendChild(host);
                widget.reportHost = host;
                var firstDirectory = status;
                widget.reportController = ReportsController.mount(panel, {
                    document: document,
                    transport: {
                        directory: function(signal) {
                            if (firstDirectory) {
                                var result = firstDirectory;
                                firstDirectory = null;
                                return signal && signal.aborted ? Promise.reject({ publicMessage: undefined }) : Promise.resolve(result);
                            }
                            return reportRequest({ url: baseUrl + '/team/status', method: 'GET', dataType: 'json', timeout: 10000 }, signal);
                        },
                        report: function(params, signal) {
                            return reportRequest({ url: baseUrl + '/reports/detailed', method: 'GET', dataType: 'json', timeout: 10000, data: params }, signal);
                        },
                        export: function(body, signal) {
                            var request;
                            var options = { url: baseUrl + '/reports/export-excel', method: 'POST', contentType: 'application/json',
                                data: JSON.stringify(body), xhrFields: { responseType: 'blob' }, timeout: 10000 };
                            return reportRequest(options, signal, function(value) { request = value; }).then(function(blob) {
                                return { blob: blob, filename: reportFilename(request, body) };
                            });
                        }
                    },
                    now: function() { return new Date(); }
                });
                if (widget.reportController.ready) widget.reportController.ready.catch(function() {});
            }).catch(function() {
                if (generation === widget.reportGeneration) stopReports();
            });
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
            stopReports();
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
                startReports(baseUrl, settings);
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
        return this;
    };
    return CustomWidget;
});
