define(['jquery', './settings/settings', './timesheet/controller', './overlay'], function($, SettingsController, TimesheetController, Overlay) {
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
        this.removeFocusRefresh = null;
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
        function renderWorkingUi(snapshot) {
            if (typeof widget.renderTimesheetStatus === 'function') {
                widget.renderTimesheetStatus(snapshot, function(action) { return widget.timesheetController.command(action); });
            }
        }
        function stopTimesheet() {
            if (widget.removeFocusRefresh) widget.removeFocusRefresh();
            widget.removeFocusRefresh = null;
            if (widget.timesheetController) widget.timesheetController.destroy();
            widget.timesheetController = null;
            clearWorkingUi();
        }
        function startTimesheet() {
            var baseUrl = apiUrl(widget);
            stopTimesheet();
            if (!baseUrl || typeof widget.$authorizedAjax !== 'function') return;
            widget.timesheetController = TimesheetController.createTimesheetController({
                request: function(request) {
                    var options = { url: baseUrl + request.url, method: request.method, dataType: request.dataType };
                    if (request.contentType) options.contentType = request.contentType;
                    if (request.data) options.data = request.data;
                    return toPromise(widget.$authorizedAjax(options));
                },
                render: renderWorkingUi,
                clear: clearWorkingUi,
                schedule: function(fn) { var timer = setTimeout(fn, 5000); return function() { clearTimeout(timer); }; },
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
                if (area === 'settings' || area === 'advanced_settings') return true;
                startTimesheet();
                return true;
            },
            bind_actions: function() { return true; },
            settings: function() { return true; },
            advancedSettings: function() {
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
