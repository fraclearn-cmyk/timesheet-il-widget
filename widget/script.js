/**
 * Timesheet IL Widget - Main Script
 * amoCRM Widget для учёта рабочего времени с Activity Tracking
 */

define(['jquery'], function($) {
    
    var CustomWidget = function() {
        var self = this;
        
        // Configuration
        this.config = {
            apiBaseUrl: 'https://storage-turkey-multitask.ngrok-free.dev/api/v1',
            pollInterval: 30000, // 30 seconds
            idleThreshold: 300000 // 5 minutes
        };
        
        // State
        this.state = {
            currentSession: null,
            currentActivity: null,
            timer: null,
            lastActivity: Date.now()
        };
        
        // Initialize widget
        this.callbacks = {
            render: function() {
                console.log('Timesheet IL Widget: render');
                self.render();
                return true;
            },
            
            init: function() {
                console.log('Timesheet IL Widget: init');
                self.init();
                return true;
            },
            
            bind_actions: function() {
                console.log('Timesheet IL Widget: bind_actions');
                self.bindActions();
                return true;
            },
            
            settings: function() {
                console.log('Timesheet IL Widget: settings');
                return true;
            },
            
            onSave: function() {
                console.log('Timesheet IL Widget: onSave');
                return true;
            },
            
            destroy: function() {
                console.log('Timesheet IL Widget: destroy');
                self.destroy();
            },
            
            contacts: {
                selected: function() {
                    console.log('Contact/Lead selected');
                    self.onEntityOpen('contact');
                }
            },
            
            leads: {
                selected: function() {
                    console.log('Lead selected');
                    self.onEntityOpen('lead');
                }
            },
            
            companies: {
                selected: function() {
                    console.log('Company selected');
                    self.onEntityOpen('company');
                }
            },
            
            tasks: {
                selected: function() {
                    console.log('Task selected');
                    self.onEntityOpen('task');
                }
            }
        };
        
        return this;
    };
    
    // Render widget HTML
    CustomWidget.prototype.render = function() {
        var self = this;
        var widget_code = 
            '<div class="timesheet-widget">' +
                '<div class="timesheet-header">' +
                    '<h3>⏱️ Рабочее время</h3>' +
                '</div>' +
                '<div class="timesheet-content">' +
                    '<div class="session-status" id="session-status">' +
                        '<p>Загрузка...</p>' +
                    '</div>' +
                    '<div class="session-controls" id="session-controls"></div>' +
                    '<div class="session-timer" id="session-timer"></div>' +
                    '<div class="activity-tracker" id="activity-tracker"></div>' +
                '</div>' +
            '</div>';
        
        this._render({
            caption: {
                class_name: 'timesheet-caption'
            },
            body: widget_code,
            render: ''
        });
    };
    
    // Initialize widget
    CustomWidget.prototype.init = function() {
        var self = this;
        
                        // Load CSS
    CustomWidget.prototype.loadCSS = function() {
        if ($('#timesheet-inline-styles').length) return;
        
        var styles = `/**
 * Timesheet IL Widget - Styles
 * amoCRM Widget для учёта рабочего времени
 */

/* Widget Container */
.timesheet-widget {
    font-family: \'Open Sans\', Arial, sans-serif;
    padding: 15px;
    background: #fff;
    border-radius: 8px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.timesheet-header {
    margin-bottom: 15px;
    padding-bottom: 10px;
    border-bottom: 2px solid #e0e0e0;
}

.timesheet-header h3 {
    margin: 0;
    font-size: 18px;
    font-weight: 600;
    color: #333;
}

.timesheet-content {
    display: flex;
    flex-direction: column;
    gap: 15px;
}

/* Session Status */
.session-status {
    text-align: center;
    padding: 10px;
    border-radius: 6px;
    background: #f5f5f5;
}

.session-status p {
    margin: 0;
    font-size: 16px;
    font-weight: 600;
}

.status-idle {
    color: #666;
}

.status-working {
    color: #27ae60;
    background: #d4edda;
    padding: 8px;
    border-radius: 4px;
}

.status-break {
    color: #f39c12;
    background: #fff3cd;
    padding: 8px;
    border-radius: 4px;
}

.status-finished {
    color: #2c3e50;
    background: #e2e3e5;
    padding: 8px;
    border-radius: 4px;
}

/* Session Controls */
.session-controls {
    display: flex;
    gap: 10px;
    justify-content: center;
    flex-wrap: wrap;
}

.session-controls button {
    padding: 10px 20px;
    font-size: 14px;
    font-weight: 600;
    border: none;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.3s ease;
    min-width: 140px;
}

.btn-primary {
    background: #3498db;
    color: #fff;
}

.btn-primary:hover {
    background: #2980b9;
    transform: translateY(-2px);
    box-shadow: 0 4px 8px rgba(52, 152, 219, 0.3);
}

.btn-success {
    background: #27ae60;
    color: #fff;
}

.btn-success:hover {
    background: #229954;
    transform: translateY(-2px);
    box-shadow: 0 4px 8px rgba(39, 174, 96, 0.3);
}

.btn-warning {
    background: #f39c12;
    color: #fff;
}

.btn-warning:hover {
    background: #e67e22;
    transform: translateY(-2px);
    box-shadow: 0 4px 8px rgba(243, 156, 18, 0.3);
}

.btn-danger {
    background: #e74c3c;
    color: #fff;
}

.btn-danger:hover {
    background: #c0392b;
    transform: translateY(-2px);
    box-shadow: 0 4px 8px rgba(231, 76, 60, 0.3);
}

/* Timer */
.timer {
    text-align: center;
    padding: 15px;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    border-radius: 8px;
    color: #fff;
}

.timer-label {
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 5px;
    opacity: 0.9;
}

.timer-value {
    font-size: 32px;
    font-weight: 700;
    font-family: \'Courier New\', monospace;
    margin: 10px 0;
    text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.2);
}

.timer-stats {
    font-size: 13px;
    margin-top: 10px;
    opacity: 0.95;
    padding-top: 10px;
    border-top: 1px solid rgba(255, 255, 255, 0.2);
}

/* Activity Tracker */
.activity-tracker {
    padding: 12px;
    background: #f8f9fa;
    border-radius: 6px;
    border-left: 4px solid #3498db;
}

.activity-current {
    display: flex;
    flex-direction: column;
    gap: 6px;
}

.activity-label {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: #666;
    font-weight: 600;
}

.activity-name {
    font-size: 15px;
    font-weight: 600;
    color: #2c3e50;
}

.activity-type {
    font-size: 12px;
    color: #7f8c8d;
    padding: 4px 8px;
    background: #ecf0f1;
    border-radius: 4px;
    display: inline-block;
    width: fit-content;
}

/* Loading State */
.loading {
    text-align: center;
    padding: 20px;
    color: #7f8c8d;
}

.loading::after {
    content: \'...\';
    animation: loading 1.5s infinite;
}

@keyframes loading {
    0%, 20% {
        content: \'.\';
    }
    40% {
        content: \'..\';
    }
    60%, 100% {
        content: \'...\';
    }
}

/* Error Message */
.error-message {
    padding: 10px;
    background: #f8d7da;
    color: #721c24;
    border: 1px solid #f5c6cb;
    border-radius: 4px;
    font-size: 13px;
    margin-top: 10px;
}

/* Success Message */
.success-message {
    padding: 10px;
    background: #d4edda;
    color: #155724;
    border: 1px solid #c3e6cb;
    border-radius: 4px;
    font-size: 13px;
    margin-top: 10px;
}

/* Responsive */
@media (max-width: 480px) {
    .timesheet-widget {
        padding: 10px;
    }
    
    .session-controls button {
        min-width: 100%;
    }
    
    .timer-value {
        font-size: 24px;
    }
}

/* Animation */
@keyframes fadeIn {
    from {
        opacity: 0;
        transform: translateY(-10px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}

.timesheet-content > * {
    animation: fadeIn 0.3s ease-in-out;
}

/* Button Disabled State */
button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}

button:disabled:hover {
    transform: none !important;
    box-shadow: none !important;
}

/* Pulse Animation for Active Status */
.status-working::before {
    content: \'\';
    display: inline-block;
    width: 8px;
    height: 8px;
    background: #27ae60;
    border-radius: 50%;
    margin-right: 8px;
    animation: pulse 2s infinite;
}

@keyframes pulse {
    0%, 100% {
        opacity: 1;
        transform: scale(1);
    }
    50% {
        opacity: 0.5;
        transform: scale(1.2);
    }
}

/* Break Status Blinking */
.status-break::before {
    content: \'\';
    display: inline-block;
    width: 8px;
    height: 8px;
    background: #f39c12;
    border-radius: 50%;
    margin-right: 8px;
    animation: blink 1s infinite;
}

@keyframes blink {
    0%, 50%, 100% {
        opacity: 1;
    }
    25%, 75% {
        opacity: 0.3;
    }
}
`;
        
        $('<style>')
            .attr('id', 'timesheet-inline-styles')
            .html(styles)
            .appendTo('head');
    };
    
    // Get current user
    CustomWidget.prototype.getCurrentUser = function() {
        var self = this;
        var account = AMOCRM.constant('account');
        var user = AMOCRM.constant('user');
        
        this.state.user = {
            id: user.id,
            name: user.name,
            account_id: account.subdomain,
            department: user.group || 'Default'
        };
        
        console.log('Current user:', this.state.user);
    };
    
    // Load current session
    CustomWidget.prototype.loadCurrentSession = function() {
        var self = this;
        
        $.ajax({
            url: this.config.apiBaseUrl + '/sessions/current/' + this.state.user.id,
            method: 'GET',
            success: function(response) {
                self.state.currentSession = response;
                self.updateSessionUI();
            },
            error: function(xhr) {
                if (xhr.status === 404) {
                    // No active session
                    self.state.currentSession = null;
                    self.updateSessionUI();
                } else {
                    console.error('Error loading session:', xhr);
                    self.showError('Ошибка загрузки сессии');
                }
            }
        });
    };
    
    // Update session UI
    CustomWidget.prototype.updateSessionUI = function() {
        var statusEl = $('#session-status');
        var controlsEl = $('#session-controls');
        var timerEl = $('#session-timer');
        
        if (!this.state.currentSession) {
            // No active session - show start button
            statusEl.html('<p class="status-idle">Рабочий день не начат</p>');
            controlsEl.html(
                '<button class="btn-primary" id="btn-start-session">' +
                    '▶️ Начать рабочий день' +
                '</button>'
            );
            timerEl.html('');
        } else {
            var session = this.state.currentSession;
            var statusText = this.getStatusText(session.status);
            var statusClass = 'status-' + session.status;
            
            statusEl.html('<p class="' + statusClass + '">' + statusText + '</p>');
            
            // Controls based on status
            if (session.status === 'working') {
                controlsEl.html(
                    '<button class="btn-warning" id="btn-take-break">⏸️ Перерыв</button>' +
                    '<button class="btn-danger" id="btn-finish-session">⏹️ Завершить день</button>'
                );
            } else if (session.status === 'break') {
                controlsEl.html(
                    '<button class="btn-success" id="btn-resume-work">▶️ Продолжить работу</button>' +
                    '<button class="btn-danger" id="btn-finish-session">⏹️ Завершить день</button>'
                );
            }
            
            // Timer
            this.updateTimer();
        }
    };
    
    // Get status text
    CustomWidget.prototype.getStatusText = function(status) {
        var texts = {
            'working': '✅ Работаю',
            'break': '⏸️ На перерыве',
            'finished': '✔️ День завершён'
        };
        return texts[status] || status;
    };
    
    // Update timer
    CustomWidget.prototype.updateTimer = function() {
        if (!this.state.currentSession) return;
        
        var session = this.state.currentSession;
        var now = new Date();
        var startTime = new Date(session.start_time);
        var elapsed = Math.floor((now - startTime) / 1000);
        
        var hours = Math.floor(elapsed / 3600);
        var minutes = Math.floor((elapsed % 3600) / 60);
        var seconds = elapsed % 60;
        
        var timerText = this.formatTime(hours) + ':' + 
                       this.formatTime(minutes) + ':' + 
                       this.formatTime(seconds);
        
        $('#session-timer').html(
            '<div class="timer">' +
                '<div class="timer-label">Время работы:</div>' +
                '<div class="timer-value">' + timerText + '</div>' +
                '<div class="timer-stats">' +
                    'Перерывы: ' + session.break_count + ' (' + 
                    this.formatSeconds(session.total_break_time) + ')' +
                '</div>' +
            '</div>'
        );
    };
    
    // Format time
    CustomWidget.prototype.formatTime = function(value) {
        return value < 10 ? '0' + value : value;
    };
    
    // Format seconds to HH:MM
    CustomWidget.prototype.formatSeconds = function(seconds) {
        var hours = Math.floor(seconds / 3600);
        var minutes = Math.floor((seconds % 3600) / 60);
        return hours + 'ч ' + minutes + 'м';
    };
    
    // Bind actions
    CustomWidget.prototype.bindActions = function() {
        var self = this;
        
        // Start session
        $(document).on('click', '#btn-start-session', function() {
            self.startSession();
        });
        
        // Take break
        $(document).on('click', '#btn-take-break', function() {
            self.takeBreak();
        });
        
        // Resume work
        $(document).on('click', '#btn-resume-work', function() {
            self.resumeWork();
        });
        
        // Finish session
        $(document).on('click', '#btn-finish-session', function() {
            self.finishSession();
        });
    };
    
    // Start session
    CustomWidget.prototype.startSession = function() {
        var self = this;
        
        $.ajax({
            url: this.config.apiBaseUrl + '/sessions/start',
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(this.state.user),
            success: function(response) {
                self.state.currentSession = response;
                self.updateSessionUI();
                self.showSuccess('Рабочий день начат!');
            },
            error: function(xhr) {
                console.error('Error starting session:', xhr);
                self.showError('Ошибка начала рабочего дня');
            }
        });
    };
    
    // Take break
    CustomWidget.prototype.takeBreak = function() {
        var self = this;
        
        $.ajax({
            url: this.config.apiBaseUrl + '/sessions/break/' + this.state.user.id,
            method: 'POST',
            success: function(response) {
                self.state.currentSession = response;
                self.updateSessionUI();
                self.showSuccess('Перерыв начат');
            },
            error: function(xhr) {
                console.error('Error taking break:', xhr);
                self.showError('Ошибка начала перерыва');
            }
        });
    };
    
    // Resume work
    CustomWidget.prototype.resumeWork = function() {
        var self = this;
        
        $.ajax({
            url: this.config.apiBaseUrl + '/sessions/resume/' + this.state.user.id,
            method: 'POST',
            success: function(response) {
                self.state.currentSession = response;
                self.updateSessionUI();
                self.showSuccess('Работа возобновлена');
            },
            error: function(xhr) {
                console.error('Error resuming work:', xhr);
                self.showError('Ошибка возобновления работы');
            }
        });
    };
    
    // Finish session
    CustomWidget.prototype.finishSession = function() {
        var self = this;
        
        if (!confirm('Завершить рабочий день?')) {
            return;
        }
        
        $.ajax({
            url: this.config.apiBaseUrl + '/sessions/finish/' + this.state.user.id,
            method: 'POST',
            success: function(response) {
                self.state.currentSession = null;
                self.updateSessionUI();
                self.showSuccess('Рабочий день завершён! Время работы: ' + 
                                self.formatSeconds(response.total_work_time));
            },
            error: function(xhr) {
                console.error('Error finishing session:', xhr);
                self.showError('Ошибка завершения рабочего дня');
            }
        });
    };
    
    // Setup activity tracking
    CustomWidget.prototype.setupActivityTracking = function() {
        var self = this;
        console.log('Activity tracking setup complete');
    };
    
    // On entity open
    CustomWidget.prototype.onEntityOpen = function(entityType) {
        var self = this;
        
        if (!this.state.currentSession || this.state.currentSession.status !== 'working') {
            return; // Only track when working
        }
        
        var cardData = AMOCRM.widgets.system.card;
        if (!cardData) return;
        
        var entityId = cardData.id;
        var entityName = cardData.name || 'Без названия';
        
        // Start activity
        this.startActivity(entityType, entityId, entityName);
    };
    
    // Start activity
    CustomWidget.prototype.startActivity = function(entityType, entityId, entityName) {
        var self = this;
        
        var data = {
            work_session_id: this.state.currentSession.id,
            entity_type: entityType,
            entity_id: entityId,
            entity_name: entityName
        };
        
        $.ajax({
            url: this.config.apiBaseUrl + '/activity/start',
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(data),
            success: function(response) {
                self.state.currentActivity = response;
                self.updateActivityUI();
                console.log('Activity started:', response);
            },
            error: function(xhr) {
                console.error('Error starting activity:', xhr);
            }
        });
    };
    
    // Update activity UI
    CustomWidget.prototype.updateActivityUI = function() {
        if (!this.state.currentActivity) return;
        
        var activity = this.state.currentActivity;
        var activityEl = $('#activity-tracker');
        
        activityEl.html(
            '<div class="activity-current">' +
                '<div class="activity-label">🎯 Текущая карточка:</div>' +
                '<div class="activity-name">' + activity.entity_name + '</div>' +
                '<div class="activity-type">' + this.getEntityTypeName(activity.entity_type) + '</div>' +
            '</div>'
        );
    };
    
    // Get entity type name
    CustomWidget.prototype.getEntityTypeName = function(type) {
        var names = {
            'lead': 'Сделка',
            'contact': 'Контакт',
            'company': 'Компания',
            'task': 'Задача'
        };
        return names[type] || type;
    };
    
    // Start update timer
    CustomWidget.prototype.startUpdateTimer = function() {
        var self = this;
        
        this.state.timer = setInterval(function() {
            self.updateTimer();
            // Periodic sync
            if (self.state.currentSession) {
                self.loadCurrentSession();
            }
        }, 1000); // Update every second
    };
    
    // Track user activity
    CustomWidget.prototype.trackUserActivity = function() {
        var self = this;
        
        $(document).on('mousemove keypress click', function() {
            self.state.lastActivity = Date.now();
        });
    };
    
    // Show success message
    CustomWidget.prototype.showSuccess = function(message) {
        AMOCRM.notifications.show_message({
            header: 'Успешно',
            text: message,
            date: Math.floor(Date.now() / 1000)
        });
    };
    
    // Show error message
    CustomWidget.prototype.showError = function(message) {
        AMOCRM.notifications.show_message_error({
            header: 'Ошибка',
            text: message,
            date: Math.floor(Date.now() / 1000)
        });
    };
    
    // Destroy widget
    CustomWidget.prototype.destroy = function() {
        if (this.state.timer) {
            clearInterval(this.state.timer);
        }
    };
    
    return CustomWidget;
});




