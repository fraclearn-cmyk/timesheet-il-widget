# 🎯 ПОЛНЫЙ CODE REVIEW: Timesheet IL - ALL FILES
**Дата:** 11.08.2026
**Проект:** Full Stack система учёта рабочего времени для amoCRM
**Цель:** Comprehensive code review ВСЕГО проекта

---

## 📋 CRAFT ПРОМПТ ДЛЯ DEEPSEEK

```
Ты - Senior Full Stack разработчик + эксперт по amoCRM.

ЗАДАЧА: Полный code review проекта Timesheet IL.

Ниже предоставлен ВЕСЬ код проекта:
- Widget для amoCRM (manifest.json + script.js + styles.css + i18n)
- Backend FastAPI (models, API, services, schemas)
- Frontend (5 HTML страниц + JS + CSS)

ФОКУС АНАЛИЗА:
1. ✅ Совместимость с amoCRM API
2. ✅ Безопасность (XSS, CSRF, SQL injection)
3. ✅ Performance & Memory leaks
4. ✅ Best practices Python/JavaScript
5. ✅ Production readiness
6. ✅ Конфликты с amoCRM UI

ФОРМАТ ОТВЕТА:
Для КАЖДОГО файла с проблемами дай:

```
FILE: путь/к/файлу.ext
ISSUES:
🔴 КРИТИЧНО: Описание проблемы
🟠 ВАЖНО: Описание проблемы
🟡 ЖЕЛАТЕЛЬНО: Рекомендация

FIX:
[ПОЛНЫЙ ИСПРАВЛЕННЫЙ КОД ФАЙЛА]
```

ВАЖНО: Предоставь ГОТОВЫЙ код для копирования в VS Code!
```

---

## 📊 СТАТИСТИКА ПРОЕКТА

**Файлов для review:** 47

**Структура:**
- Widget: 5 файлов (manifest, script, styles, i18n)
- Backend: 25 файлов (models, API, services, schemas)
- Frontend: 14 файлов (HTML, JS, CSS)
- **ИТОГО:** ~6,000 строк кода

---

## 📄 ВЕСЬ КОД ПРОЕКТА

### Widget Config

**File:** `widget/manifest.json` (41 lines)

```json
﻿{
    "widget":  {
                   "name":  "widget.name",
                   "description":  "widget.description",
                   "short_description":  "widget.short_description",
                   "version":  "3.0.2",
                   "interface_version":  2,
                   "init_once":  false,
                   "locale":  [
                                  "ru",
                                  "en"
                              ],
                   "installation":  true,
                   "support":  {
                                   "link":  "https://example.com/support",
                                   "email":  "support@example.com"
                               }
               },
    "locations":  [
                      "advancedSettings"
                  ],
    "settings":  {
                     "api_url":  {
                                     "name":  "settings.api_url",
                                     "type":  "text",
                                     "required":  false
                                 }
                 },
    "tour":  {
                 "is_tour":  true,
                 "tour_images":  {
                                     "ru":  [
                                                "/images/tour_ru.png"
                                            ],
                                     "en":  [
                                                "/images/tour_en.png"
                                            ]
                                 },
                 "tour_description":  "widget.tour_description"
             }
}

```

---

### Widget Main Code (655 lines)

**File:** `widget/script.js` (655 lines)

```javascript
﻿define(['jquery'], function($) {
    var CustomWidget = function() {
        var widget = this;
        
        // API Configuration
        this.API_URL = 'https://storage-turkey-multitask.ngrok-free.dev/api/v1';
        this.currentSession = null;
        this.updateTimer = null;
        this.sessionStart = null;
        this.overlayShown = false;
        
        this.callbacks = {
            render: function() {
                return true;
            },
            init: function() {
                console.log('Timesheet Widget v3.0.2 initializing...');
                
                // Get current user info from amoCRM
                try {
                    widget.accountId = AMOCRM.constant('account').id;
                    widget.userId = AMOCRM.constant('user').id;
                    widget.userName = AMOCRM.constant('user').name;
                    console.log('User:', widget.userName, 'ID:', widget.userId);
                } catch (e) {
                    console.error('Failed to get user info:', e);
                    widget.accountId = 'demo_account';
                    widget.userId = 1;
                    widget.userName = 'Demo User';
                }
                
                // Load custom settings if provided
                var settings = widget.get_settings();
                if (settings && settings.api_url) {
                    widget.API_URL = settings.api_url;
                }
                
                // Load current session from API
                $.ajax({
                    url: widget.API_URL + '/sessions/current',
                    method: 'GET',
                    data: {
                        account_id: widget.accountId,
                        user_id: widget.userId
                    },
                    success: function(response) {
                        if (response && response.session_id && response.status !== 'finished') {
                            widget.currentSession = response;
                            widget.sessionStart = new Date(response.start_time);
                            console.log('Session loaded:', response.status);
                        } else {
                            widget.currentSession = null;
                            console.log('No active session');
                        }
                        // Create overlay after session loaded
                        widget.createOverlay();
                        widget.updateOverlayState();
                    },
                    error: function(xhr, status, error) {
                        console.log('No session loaded (backend may be offline)');
                        widget.currentSession = null;
                        // Create overlay even if backend fails
                        widget.createOverlay();
                        widget.updateOverlayState();
                    }
                });
                
                // Start update timer
                widget.startUpdateTimer();
                
                return true;
            },
            bind_actions: function() {
                return true;
            },
            settings: function() {
                return true;
            },
            onSave: function() {
                return true;
            },
            destroy: function() {
                if (widget.updateTimer) {
                    clearInterval(widget.updateTimer);
                }
                if (widget.removeOverlay) {
                    widget.removeOverlay();
                }
                return true;
            }
        };
    };

    // Get current user from amoCRM
    CustomWidget.prototype.getCurrentUser = function() {
        try {
            this.accountId = AMOCRM.constant('account').id;
            this.userId = AMOCRM.constant('user').id;
            this.userName = AMOCRM.constant('user').name;
            console.log('User:', this.userName, 'ID:', this.userId);
        } catch (e) {
            console.error('Failed to get user info:', e);
            this.accountId = 'demo_account';
            this.userId = 1;
            this.userName = 'Demo User';
        }
    };

    // Load current session from API
    CustomWidget.prototype.loadCurrentSession = function(callback) {
        var self = this;
        
        $.ajax({
            url: self.API_URL + '/sessions/current',
            method: 'GET',
            data: {
                account_id: self.accountId,
                user_id: self.userId
            },
            success: function(response) {
                if (response && response.session_id && response.status !== 'finished') {
                    self.currentSession = response;
                    self.sessionStart = new Date(response.start_time);
                    console.log('Session loaded:', response.status);
                } else {
                    self.currentSession = null;
                    console.log('No active session');
                }
                if (callback) callback();
            },
            error: function(xhr, status, error) {
                console.log('No session loaded (backend may be offline)');
                self.currentSession = null;
                if (callback) callback();
            }
        });
    };

    // Create full-screen overlay
    CustomWidget.prototype.createOverlay = function() {
        var self = this;
        
        if ($('#timesheet-overlay').length > 0) {
            return; // Already exists
        }
        
        var overlayHTML = `
            <!-- Fullscreen dark overlay (блокирует всё) -->
            <div id="timesheet-overlay" class="timesheet-overlay" style="display:none;"></div>
            
            <!-- Start button (top right corner) -->
            <div id="timesheet-start-button" class="timesheet-start-button" style="display:none;">
                <button class="start-btn" id="btn-start-shift">
                    <span class="btn-icon">▶️</span> Начать смену
                </button>
            </div>
            
            <!-- Compact widget when working (top right corner) -->
            <div id="timesheet-compact" class="timesheet-compact" style="display:none;">
                <div class="compact-header">
                    <span class="compact-title">⏰ Табель</span>
                    <span class="compact-status" id="compact-status">Работаю</span>
                </div>
                <div class="compact-timer" id="compact-timer">00:00:00</div>
                <div class="compact-buttons">
                    <button class="compact-btn compact-btn-break" id="btn-compact-break" title="Перерыв">
                        <span>⏸️</span>
                    </button>
                    <button class="compact-btn compact-btn-end" id="btn-compact-end" title="Завершить">
                        <span>⏹️</span>
                    </button>
                </div>
            </div>
            
            <!-- Break overlay (when on break) -->
            <div id="timesheet-break-overlay" class="timesheet-break-overlay" style="display:none;">
                <div class="break-content">
                    <div class="break-icon">⏸️</div>
                    <div class="break-title">Перерыв</div>
                    <div class="break-timer" id="break-timer">00:00:00</div>
                    <div class="break-buttons">
                        <button class="break-btn break-btn-resume" id="btn-break-resume">
                            <span>▶️</span> Продолжить
                        </button>
                        <button class="break-btn break-btn-end" id="btn-break-end">
                            <span>⏹️</span> Завершить день
                        </button>
                    </div>
                </div>
            </div>
        `;
        
        // Add CSS
        var css = `
<style>
/* Fullscreen dark overlay - блокирует ВСЁ */
.timesheet-overlay {
    position: fixed;
    top: 0;
    left: 0;
    width: 100vw;
    height: 100vh;
    background: rgba(0, 0, 0, 0.7);
    z-index: 999999;
    backdrop-filter: blur(4px);
    pointer-events: all;
}

/* Start button - top right corner */
.timesheet-start-button {
    position: fixed;
    top: 20px;
    right: 20px;
    z-index: 1000000;
    animation: pulse-glow 2s ease-in-out infinite;
}

@keyframes pulse-glow {
    0%, 100% {
        transform: scale(1);
        box-shadow: 0 0 20px rgba(17, 153, 142, 0.5);
    }
    50% {
        transform: scale(1.05);
        box-shadow: 0 0 40px rgba(17, 153, 142, 0.8);
    }
}

.start-btn {
    padding: 18px 35px;
    font-size: 18px;
    font-weight: 700;
    background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
    color: white;
    border: none;
    border-radius: 50px;
    cursor: pointer;
    box-shadow: 0 8px 25px rgba(0,0,0,0.3);
    transition: all 0.3s ease;
    display: flex;
    align-items: center;
    gap: 12px;
}

.start-btn:hover {
    transform: translateY(-3px);
    box-shadow: 0 12px 35px rgba(17, 153, 142, 0.4);
}

.start-btn .btn-icon {
    font-size: 22px;
}

/* Compact widget when working - top right corner */
.timesheet-compact {
    position: fixed;
    top: 20px;
    right: 20px;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    padding: 20px 25px;
    border-radius: 15px;
    box-shadow: 0 8px 25px rgba(0,0,0,0.3);
    z-index: 1000000;
    color: white;
    min-width: 280px;
    animation: slideInRight 0.3s ease-out;
}

@keyframes slideInRight {
    from {
        transform: translateX(100px);
        opacity: 0;
    }
    to {
        transform: translateX(0);
        opacity: 1;
    }
}

.compact-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
    padding-bottom: 10px;
    border-bottom: 1px solid rgba(255,255,255,0.2);
}

.compact-title {
    font-size: 16px;
    font-weight: 700;
}

.compact-status {
    font-size: 13px;
    padding: 4px 12px;
    background: rgba(56, 239, 125, 0.3);
    border-radius: 20px;
    animation: pulse-status 2s ease-in-out infinite;
}

@keyframes pulse-status {
    0%, 100% { opacity: 0.8; }
    50% { opacity: 1; }
}

.compact-timer {
    font-size: 32px;
    font-weight: 700;
    font-family: 'Courier New', monospace;
    text-align: center;
    margin: 12px 0;
    text-shadow: 0 2px 8px rgba(0,0,0,0.3);
}

.compact-buttons {
    display: flex;
    gap: 10px;
    justify-content: center;
    margin-top: 15px;
}

.compact-btn {
    flex: 1;
    padding: 10px;
    border: none;
    border-radius: 10px;
    background: rgba(255,255,255,0.15);
    color: white;
    font-size: 20px;
    cursor: pointer;
    transition: all 0.2s ease;
    display: flex;
    align-items: center;
    justify-content: center;
}

.compact-btn:hover {
    background: rgba(255,255,255,0.25);
    transform: translateY(-2px);
}

.compact-btn-break:hover {
    background: rgba(240, 147, 251, 0.4);
}

.compact-btn-end:hover {
    background: rgba(250, 112, 154, 0.4);
}

/* Break overlay - full screen */
.timesheet-break-overlay {
    position: fixed;
    top: 0;
    left: 0;
    width: 100vw;
    height: 100vh;
    background: rgba(0, 0, 0, 0.75);
    z-index: 999999;
    display: flex;
    justify-content: center;
    align-items: center;
    backdrop-filter: blur(5px);
}

.break-content {
    background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
    padding: 60px;
    border-radius: 25px;
    box-shadow: 0 20px 60px rgba(0,0,0,0.5);
    text-align: center;
    color: white;
    animation: slideIn 0.4s ease-out;
}

@keyframes slideIn {
    from {
        transform: scale(0.8);
        opacity: 0;
    }
    to {
        transform: scale(1);
        opacity: 1;
    }
}

.break-icon {
    font-size: 80px;
    margin-bottom: 20px;
    animation: rotate-pause 3s ease-in-out infinite;
}

@keyframes rotate-pause {
    0%, 100% { transform: rotate(-10deg); }
    50% { transform: rotate(10deg); }
}

.break-title {
    font-size: 42px;
    font-weight: 700;
    margin-bottom: 25px;
    text-shadow: 0 3px 15px rgba(0,0,0,0.4);
}

.break-timer {
    font-size: 56px;
    font-weight: 700;
    font-family: 'Courier New', monospace;
    margin: 30px 0;
    text-shadow: 0 3px 15px rgba(0,0,0,0.4);
}

.break-buttons {
    display: flex;
    gap: 20px;
    margin-top: 35px;
}

.break-btn {
    flex: 1;
    padding: 20px 40px;
    font-size: 18px;
    font-weight: 700;
    border: none;
    border-radius: 50px;
    cursor: pointer;
    transition: all 0.3s ease;
    box-shadow: 0 5px 20px rgba(0,0,0,0.2);
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 12px;
}

.break-btn:hover {
    transform: translateY(-3px);
    box-shadow: 0 8px 25px rgba(0,0,0,0.3);
}

.break-btn-resume {
    background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
    color: white;
}

.break-btn-end {
    background: linear-gradient(135deg, #fa709a 0%, #fee140 100%);
    color: white;
}

.break-btn span {
    font-size: 22px;
}
</style>
        `;
        
        $('head').append(css);
        $('body').append(overlayHTML);
        
        // Bind events - NEW structure
        $('#btn-start-shift').on('click', function() { self.startSession(); });
        $('#btn-compact-break').on('click', function() { self.toggleBreak(); });
        $('#btn-compact-end').on('click', function() { self.endSession(); });
        $('#btn-break-resume').on('click', function() { self.toggleBreak(); });
        $('#btn-break-end').on('click', function() { self.endSession(); });
        
        console.log('Overlay v3.0.1 created');
    };

    // Show overlay with start button
    CustomWidget.prototype.showOverlay = function() {
        $('#timesheet-overlay').fadeIn(300);
        $('#timesheet-start-button').fadeIn(300);
        $('#timesheet-compact').hide();
        $('#timesheet-break-overlay').hide();
        this.overlayShown = true;
    };

    // Hide overlay (show compact widget when working)
    CustomWidget.prototype.hideOverlay = function() {
        $('#timesheet-overlay').fadeOut(300);
        $('#timesheet-start-button').fadeOut(300);
        $('#timesheet-break-overlay').fadeOut(300);
        $('#timesheet-compact').fadeIn(300);
        this.overlayShown = false;
    };

    // Show break overlay
    CustomWidget.prototype.showBreakOverlay = function() {
        $('#timesheet-overlay').hide();
        $('#timesheet-start-button').hide();
        $('#timesheet-compact').hide();
        $('#timesheet-break-overlay').fadeIn(300);
    };

    // Remove all overlays
    CustomWidget.prototype.removeOverlay = function() {
        $('#timesheet-overlay').remove();
        $('#timesheet-start-button').remove();
        $('#timesheet-compact').remove();
        $('#timesheet-break-overlay').remove();
    };

    // Update overlay state based on session
    CustomWidget.prototype.updateOverlayState = function() {
        var self = this;
        
        if (!self.currentSession || self.currentSession.status === 'finished') {
            // No session - show dark overlay + start button (top right)
            self.showOverlay();
            console.log('State: No session - showing overlay + start button');
        } else if (self.currentSession.status === 'working') {
            // Working - hide overlay, show compact widget (top right)
            self.hideOverlay();
            $('#compact-timer').text(self.formatTime(self.getElapsedTime()));
            $('#compact-status').text('Работаю');
            console.log('State: Working - compact widget visible');
        } else if (self.currentSession.status === 'break') {
            // Break - show break overlay with big pause screen
            self.showBreakOverlay();
            $('#break-timer').text(self.formatTime(self.getElapsedTime()));
            console.log('State: Break - break overlay visible');
        }
    };

    // Start work session
    CustomWidget.prototype.startSession = function() {
        var self = this;
        
        $.ajax({
            url: self.API_URL + '/sessions/start',
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({
                account_id: self.accountId,
                user_id: self.userId,
                user_name: self.userName
            }),
            success: function(response) {
                self.currentSession = response;
                self.sessionStart = new Date();
                self.updateOverlayState();
                console.log('Session started:', response.session_id);
            },
            error: function(xhr, status, error) {
                // Even if backend fails, start locally
                self.currentSession = {
                    session_id: 'local_' + Date.now(),
                    status: 'working',
                    start_time: new Date().toISOString()
                };
                self.sessionStart = new Date();
                self.updateOverlayState();
                console.log('Session started locally');
            }
        });
    };

    // Toggle break
    CustomWidget.prototype.toggleBreak = function() {
        var self = this;
        var endpoint = self.currentSession.status === 'break' ? 'resume' : 'break';
        
        $.ajax({
            url: self.API_URL + '/sessions/' + endpoint,
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({
                session_id: self.currentSession.session_id,
                account_id: self.accountId
            }),
            success: function(response) {
                self.currentSession.status = response.status;
                self.updateOverlayState();
            },
            error: function(xhr, status, error) {
                // Toggle locally if backend fails
                self.currentSession.status = endpoint === 'break' ? 'break' : 'working';
                self.updateOverlayState();
            }
        });
    };

    // End session
    CustomWidget.prototype.endSession = function() {
        var self = this;
        
        $.ajax({
            url: self.API_URL + '/sessions/end',
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({
                session_id: self.currentSession.session_id,
                account_id: self.accountId
            }),
            success: function(response) {
                self.currentSession = null;
                self.sessionStart = null;
                setTimeout(function() {
                    self.updateOverlayState();
                }, 1500);
            },
            error: function(xhr, status, error) {
                // End locally
                self.currentSession = null;
                self.sessionStart = null;
                setTimeout(function() {
                    self.updateOverlayState();
                }, 1500);
            }
        });
    };

    // Start update timer
    CustomWidget.prototype.startUpdateTimer = function() {
        var self = this;
        
        if (self.updateTimer) {
            clearInterval(self.updateTimer);
        }
        
        self.updateTimer = setInterval(function() {
            if (self.currentSession && self.sessionStart) {
                var elapsed = self.getElapsedTime();
                var timeStr = self.formatTime(elapsed);
                
                if (self.currentSession.status === 'working') {
                    $('#compact-timer').text(timeStr);
                } else if (self.currentSession.status === 'break') {
                    $('#break-timer').text(timeStr);
                }
            }
        }, 1000);
    };

    // Get elapsed time
    CustomWidget.prototype.getElapsedTime = function() {
        if (!this.sessionStart) return 0;
        return Math.floor((new Date() - this.sessionStart) / 1000);
    };

    // Format time as HH:MM:SS
    CustomWidget.prototype.formatTime = function(seconds) {
        var hours = Math.floor(seconds / 3600);
        var minutes = Math.floor((seconds % 3600) / 60);
        var secs = seconds % 60;
        
        return String(hours).padStart(2, '0') + ':' +
               String(minutes).padStart(2, '0') + ':' +
               String(secs).padStart(2, '0');
    };

    return CustomWidget;
});



```

---

### Widget Styles

**File:** `widget/styles.css` (337 lines)

```css
/**
 * Timesheet IL Widget - Styles
 * amoCRM Widget для учёта рабочего времени
 */

/* Widget Container */
.timesheet-widget {
    font-family: 'Open Sans', Arial, sans-serif;
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
    font-family: 'Courier New', monospace;
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
    content: '...';
    animation: loading 1.5s infinite;
}

@keyframes loading {
    0%, 20% {
        content: '.';
    }
    40% {
        content: '..';
    }
    60%, 100% {
        content: '...';
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
    content: '';
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
    content: '';
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

```

---

### Widget RU Localization

**File:** `widget/i18n/ru.json` (63 lines)

```json
{
  "api_key": "API ключ (необязательно)",
  "enable_widget": "Включить виджет",
  "backend_url": "URL сервера",
  "widget": {
    "name": "Табель IL",
    "short_description": "Учёт рабочего времени",
    "description": "Виджет для учёта рабочего времени с автоматическим отслеживанием активности в карточках amoCRM",
    "tour_description": "Виджет для автоматического учёта рабочего времени сотрудников с отслеживанием активности в карточках"
  },
  "session": {
    "title": "Рабочее время",
    "status_idle": "Рабочий день не начат",
    "status_working": "Работаю",
    "status_break": "На перерыве",
    "status_finished": "День завершён",
    "start_button": "Начать рабочий день",
    "break_button": "Перерыв",
    "resume_button": "Продолжить работу",
    "finish_button": "Завершить день",
    "timer_label": "Время работы:",
    "breaks_label": "Перерывы:",
    "loading": "Загрузка..."
  },
  "activity": {
    "current_card": "Текущая карточка:",
    "entity_lead": "Сделка",
    "entity_contact": "Контакт",
    "entity_company": "Компания",
    "entity_task": "Задача"
  },
  "messages": {
    "session_started": "Рабочий день начат!",
    "break_started": "Перерыв начат",
    "work_resumed": "Работа возобновлена",
    "session_finished": "Рабочий день завершён!",
    "work_time": "Время работы:",
    "error_loading": "Ошибка загрузки данных",
    "error_starting": "Ошибка начала рабочего дня",
    "error_break": "Ошибка начала перерыва",
    "error_resume": "Ошибка возобновления работы",
    "error_finish": "Ошибка завершения рабочего дня",
    "confirm_finish": "Завершить рабочий день?"
  },
  "settings": {
    "title": "Настройки виджета",
    "api_url": "URL API сервера (необязательно)",
    "enable_widget": "Включить виджет",
    "backend_url": "URL сервера",
    "login": "API ключ или логин",
    "api_url": "URL API:",
    "api_url_placeholder": "http://your-server.com/api/v1",
    "auto_pause": "Автопауза при закрытии карточки",
    "require_category": "Требовать категорию активности",
    "track_idle": "Отслеживать неактивность",
    "idle_threshold": "Порог неактивности (минут):",
    "show_team_stats": "Показывать статистику команды",
    "enable_reports": "Включить отчёты",
    "save_button": "Сохранить",
    "cancel_button": "Отмена",
    "reset_button": "Сбросить"
  }
}

```

---

### Widget EN Localization

**File:** `widget/i18n/en.json` (63 lines)

```json
{
  "api_key": "API key (optional)",
  "enable_widget": "Enable widget",
  "backend_url": "Backend URL",
  "widget": {
    "name": "Timesheet IL",
    "short_description": "Time tracking",
    "description": "Widget for time tracking with automatic activity tracking in amoCRM cards",
    "tour_description": "Widget for automatic employee time tracking with activity monitoring in cards"
  },
  "session": {
    "title": "Work Time",
    "status_idle": "Work day not started",
    "status_working": "Working",
    "status_break": "On break",
    "status_finished": "Day finished",
    "start_button": "Start work day",
    "break_button": "Take break",
    "resume_button": "Resume work",
    "finish_button": "Finish day",
    "timer_label": "Work time:",
    "breaks_label": "Breaks:",
    "loading": "Loading..."
  },
  "activity": {
    "current_card": "Current card:",
    "entity_lead": "Lead",
    "entity_contact": "Contact",
    "entity_company": "Company",
    "entity_task": "Task"
  },
  "messages": {
    "session_started": "Work day started!",
    "break_started": "Break started",
    "work_resumed": "Work resumed",
    "session_finished": "Work day finished!",
    "work_time": "Work time:",
    "error_loading": "Error loading data",
    "error_starting": "Error starting work day",
    "error_break": "Error starting break",
    "error_resume": "Error resuming work",
    "error_finish": "Error finishing work day",
    "confirm_finish": "Finish work day?"
  },
  "settings": {
    "title": "Widget Settings",
    "api_url": "API Server URL (optional)",
    "enable_widget": "Enable widget",
    "backend_url": "Backend URL",
    "login": "API key or login",
    "api_url": "API URL:",
    "api_url_placeholder": "http://your-server.com/api/v1",
    "auto_pause": "Auto-pause when closing card",
    "require_category": "Require activity category",
    "track_idle": "Track idle time",
    "idle_threshold": "Idle threshold (minutes):",
    "show_team_stats": "Show team statistics",
    "enable_reports": "Enable reports",
    "save_button": "Save",
    "cancel_button": "Cancel",
    "reset_button": "Reset"
  }
}

```

---

### FastAPI Main App

**File:** `backend/app/main.py` (50 lines)

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings

# Create FastAPI app
app = FastAPI(
    title="Timesheet IL Widget API",
    description="amoCRM timesheet widget with activity tracking",
    version="1.0.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Timesheet IL Widget API",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}


# Include routers
from app.api.v1 import sessions, team, activity, categories, settings, reports
from app.api.v1.endpoints import departments, excel, kpi

app.include_router(sessions.router, prefix="/api/v1/sessions", tags=["sessions"])
app.include_router(team.router, prefix="/api/v1/team", tags=["team"])
app.include_router(activity.router, prefix="/api/v1/activity", tags=["activity"])
app.include_router(categories.router, prefix="/api/v1/categories", tags=["categories"])
app.include_router(settings.router, prefix="/api/v1/settings", tags=["settings"])
app.include_router(reports.router, prefix="/api/v1", tags=["reports"])
app.include_router(departments.router, prefix="/api/v1/departments", tags=["departments"])
app.include_router(excel.router, prefix="/api/v1/excel", tags=["excel"])
app.include_router(kpi.router, prefix="/api/v1/kpi", tags=["kpi"])

```

---

### Backend Config

**File:** `backend/app/core/config.py` (30 lines)

```python
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings"""
    
    # Database
    DATABASE_URL: str
    
    # amoCRM
    AMOCRM_CLIENT_ID: str
    AMOCRM_CLIENT_SECRET: str
    AMOCRM_REDIRECT_URI: str
    
    # Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Application
    POLLING_INTERVAL: int = 15
    INACTIVITY_TIMEOUT: int = 300
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()

```

---

### Database Connection

**File:** `backend/app/core/database.py` (22 lines)

```python
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# Create database engine
engine = create_engine(settings.DATABASE_URL)

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create Base class for models
Base = declarative_base()


def get_db():
    """Dependency for getting database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

```

---

### RBAC System

**File:** `backend/app/core/rbac.py` (187 lines)

```python
"""Role-Based Access Control (RBAC) system"""
from typing import List, Optional
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.user import User, UserRole
from app.models.rop_permission import RopPermission


class RBACService:
    """Service for Role-Based Access Control"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_user_by_amocrm_id(self, amocrm_user_id: int, amocrm_account_id: int) -> Optional[User]:
        """Get user by amoCRM ID"""
        return self.db.query(User).filter(
            User.amocrm_user_id == amocrm_user_id,
            User.amocrm_account_id == amocrm_account_id,
            User.is_active == True
        ).first()
    
    def get_or_create_user(
        self, 
        amocrm_user_id: int, 
        amocrm_account_id: int, 
        name: str, 
        email: Optional[str] = None
    ) -> User:
        """Get existing user or create new one with EMPLOYEE role"""
        user = self.get_user_by_amocrm_id(amocrm_user_id, amocrm_account_id)
        
        if not user:
            user = User(
                amocrm_user_id=amocrm_user_id,
                amocrm_account_id=amocrm_account_id,
                name=name,
                email=email,
                role=UserRole.EMPLOYEE
            )
            self.db.add(user)
            self.db.commit()
            self.db.refresh(user)
        
        return user
    
    def get_user_role(self, amocrm_user_id: int, amocrm_account_id: int) -> Optional[UserRole]:
        """Get user role"""
        user = self.get_user_by_amocrm_id(amocrm_user_id, amocrm_account_id)
        return user.role if user else None
    
    def is_admin(self, user: User) -> bool:
        """Check if user is admin"""
        return user.role == UserRole.ADMIN
    
    def is_rop(self, user: User) -> bool:
        """Check if user is ROP"""
        return user.role == UserRole.ROP
    
    def is_employee(self, user: User) -> bool:
        """Check if user is employee"""
        return user.role == UserRole.EMPLOYEE
    
    def get_rop_departments(self, user_id: int) -> List[int]:
        """Get list of department IDs that ROP can manage"""
        permissions = self.db.query(RopPermission).filter(
            RopPermission.user_id == user_id
        ).all()
        return [p.department_id for p in permissions]
    
    def can_view_department(self, user: User, department_id: int) -> bool:
        """Check if user can view department data"""
        # Admin can view all departments
        if self.is_admin(user):
            return True
        
        # ROP can only view allowed departments
        if self.is_rop(user):
            allowed_departments = self.get_rop_departments(user.id)
            return department_id in allowed_departments
        
        # Employees cannot view department data
        return False
    
    def can_view_employee(self, user: User, employee_department_id: Optional[int]) -> bool:
        """Check if user can view employee data"""
        # Admin can view all employees
        if self.is_admin(user):
            return True
        
        # ROP can only view employees from allowed departments
        if self.is_rop(user) and employee_department_id:
            allowed_departments = self.get_rop_departments(user.id)
            return employee_department_id in allowed_departments
        
        # Employees can only view their own data
        return False
    
    def can_force_finish(self, user: User) -> bool:
        """Check if user can force finish work sessions"""
        # Only admin can force finish
        return self.is_admin(user)
    
    def can_add_comment(self, user: User) -> bool:
        """Check if user can add comments to work sessions"""
        # ROP and Admin can add comments
        return self.is_rop(user) or self.is_admin(user)
    
    def can_export_excel(self, user: User) -> bool:
        """Check if user can export Excel reports"""
        # ROP and Admin can export
        return self.is_rop(user) or self.is_admin(user)
    
    def can_manage_departments(self, user: User) -> bool:
        """Check if user can manage departments (schedules, etc)"""
        # Only admin can manage departments
        return self.is_admin(user)
    
    def can_restart_session(self, user: User) -> bool:
        """Check if user can restart work session on the same day"""
        return user.allow_restart_session
    
    def get_accessible_departments(self, user: User) -> Optional[List[int]]:
        """
        Get list of department IDs accessible to user.
        Returns None for Admin (can access all), list of IDs for ROP, empty list for Employee
        """
        if self.is_admin(user):
            return None  # None means "all departments"
        
        if self.is_rop(user):
            return self.get_rop_departments(user.id)
        
        return []  # Employee has no access to departments


# Dependency for FastAPI
def get_rbac_service(db: Session = Depends(get_db)) -> RBACService:
    """FastAPI dependency to get RBAC service"""
    return RBACService(db)


def require_admin(
    amocrm_user_id: int,
    amocrm_account_id: int,
    rbac: RBACService = Depends(get_rbac_service)
) -> User:
    """Require admin role"""
    user = rbac.get_user_by_amocrm_id(amocrm_user_id, amocrm_account_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if not rbac.is_admin(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required"
        )
    
    return user


def require_rop_or_admin(
    amocrm_user_id: int,
    amocrm_account_id: int,
    rbac: RBACService = Depends(get_rbac_service)
) -> User:
    """Require ROP or Admin role"""
    user = rbac.get_user_by_amocrm_id(amocrm_user_id, amocrm_account_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if not (rbac.is_rop(user) or rbac.is_admin(user)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="ROP or Admin role required"
        )
    
    return user

```

---

### Models Init

**File:** `backend/app/models/__init__.py` (30 lines)

```python
"""Database models"""
from app.models.user import User, UserRole
from app.models.department import Department
from app.models.rop_permission import RopPermission
from app.models.work_session import WorkSession, WorkStatus
from app.models.status_transition import StatusTransition
from app.models.activity_session import ActivitySession
from app.models.activity_event import ActivityEvent
from app.models.activity_category import ActivityCategory
from app.models.widget_settings import WidgetSettings
from app.models.report import Report
from app.models.work_comment import WorkComment
from app.models.dashboard_settings import DashboardSettings

__all__ = [
    "User",
    "UserRole",
    "Department",
    "RopPermission",
    "WorkSession",
    "WorkStatus",
    "StatusTransition",
    "ActivitySession",
    "ActivityEvent",
    "ActivityCategory",
    "WidgetSettings",
    "Report",
    "WorkComment",
    "DashboardSettings",
]

```

---

### User Model

**File:** `backend/app/models/user.py` (42 lines)

```python
from sqlalchemy import Column, Integer, String, DateTime, Enum as SQLEnum, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from app.core.database import Base


class UserRole(str, enum.Enum):
    """User role enum"""
    EMPLOYEE = "employee"  # Обычный сотрудник
    ROP = "rop"  # Руководитель отдела продаж
    ADMIN = "admin"  # Администратор


class User(Base):
    """User model - represents amoCRM users with roles and permissions"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    amocrm_user_id = Column(Integer, unique=True, nullable=False, index=True)
    amocrm_account_id = Column(Integer, nullable=False, index=True)
    
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)
    
    role = Column(SQLEnum(UserRole), nullable=False, default=UserRole.EMPLOYEE)
    department_id = Column(Integer, nullable=True)  # Foreign key to departments
    
    # Settings
    allow_restart_session = Column(Boolean, default=False)  # Разрешение повторного запуска в тот же день
    
    is_active = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    rop_permissions = relationship("RopPermission", back_populates="user", cascade="all, delete-orphan")
    dashboard_settings = relationship("DashboardSettings", back_populates="user", uselist=False, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(id={self.id}, amocrm_id={self.amocrm_user_id}, role={self.role})>"

```

---

### Department Model

**File:** `backend/app/models/department.py` (24 lines)

```python
from sqlalchemy import Column, Integer, String, Time, Boolean, DateTime
from datetime import datetime
from app.core.database import Base


class Department(Base):
    """Department model - represents company departments with work schedule"""
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, unique=True)
    
    # Work schedule
    work_start_time = Column(Time, nullable=False)  # Например: 09:00:00
    work_end_time = Column(Time, nullable=False)    # Например: 18:00:00
    
    # Settings
    is_active = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Department(id={self.id}, name={self.name}, schedule={self.work_start_time}-{self.work_end_time})>"

```

---

### Work Session Model

**File:** `backend/app/models/work_session.py` (52 lines)

```python
from sqlalchemy import Column, Integer, String, DateTime, Enum as SQLEnum, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from app.core.database import Base


class WorkStatus(str, enum.Enum):
    """Work status enum"""
    WORKING = "working"
    BREAK = "break"
    FINISHED = "finished"


class WorkSession(Base):
    """Work session model - tracks employee work sessions"""
    __tablename__ = "work_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)  # amoCRM user ID
    user_name = Column(String(255), nullable=False)
    department = Column(String(255), nullable=True)
    
    start_time = Column(DateTime, nullable=False, default=datetime.utcnow)
    end_time = Column(DateTime, nullable=True)
    
    current_status = Column(SQLEnum(WorkStatus), nullable=False, default=WorkStatus.WORKING)
    
    # Calculated fields
    total_work_time = Column(Integer, default=0)  # seconds
    total_break_time = Column(Integer, default=0)  # seconds
    break_count = Column(Integer, default=0)
    
    # Late arrival tracking
    is_late = Column(Boolean, default=False)
    late_minutes = Column(Integer, nullable=True)  # Количество минут опоздания
    late_reason = Column(String(500), nullable=True)  # Причина опоздания
    
    # Forced finish tracking
    forced_finish = Column(Boolean, default=False)
    forced_finish_by = Column(Integer, nullable=True)  # User ID администратора
    forced_finish_reason = Column(String(500), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    status_transitions = relationship("StatusTransition", back_populates="work_session", cascade="all, delete-orphan")
    activity_sessions = relationship("ActivitySession", back_populates="work_session", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<WorkSession(id={self.id}, user_id={self.user_id}, status={self.current_status})>"

```

---

### Work Comment Model

**File:** `backend/app/models/work_comment.py` (23 lines)

```python
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base


class WorkComment(Base):
    """Work Comment model - comments from ROP/Admin on work sessions"""
    __tablename__ = "work_comments"

    id = Column(Integer, primary_key=True, index=True)
    work_session_id = Column(Integer, ForeignKey("work_sessions.id", ondelete="CASCADE"), nullable=False)
    
    author_id = Column(Integer, nullable=False)  # User ID РОП или Администратора
    author_name = Column(String(255), nullable=False)
    
    comment = Column(Text, nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<WorkComment(id={self.id}, session={self.work_session_id}, author={self.author_name})>"

```

---

### ROP Permission Model

**File:** `backend/app/models/rop_permission.py` (21 lines)

```python
from sqlalchemy import Column, Integer, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base


class RopPermission(Base):
    """ROP Permission model - links ROPs to departments they can manage"""
    __tablename__ = "rop_permissions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    department_id = Column(Integer, ForeignKey("departments.id", ondelete="CASCADE"), nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="rop_permissions")

    def __repr__(self):
        return f"<RopPermission(user_id={self.user_id}, department_id={self.department_id})>"

```

---

### Dashboard Settings Model

**File:** `backend/app/models/dashboard_settings.py` (28 lines)

```python
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base


class DashboardSettings(Base):
    """Dashboard Settings model - personal KPI and chart settings for ROP/Admin"""
    __tablename__ = "dashboard_settings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    
    # Selected KPIs (array of KPI names)
    selected_kpis = Column(JSON, default=list)  # ["employees_working", "on_break", "finished", "total_hours"]
    
    # Chart settings
    chart_metric = Column(String(50), default="work_time")  # work_time, breaks, activity, employees, late
    chart_period = Column(String(20), default="day")  # day, week, month
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="dashboard_settings")

    def __repr__(self):
        return f"<DashboardSettings(user_id={self.user_id}, kpis={len(self.selected_kpis or [])})>"

```

---

### API V1 Init

**File:** `backend/app/api/v1/__init__.py` (1 lines)

```python
"""API v1 routes"""

```

---

### Sessions API

**File:** `backend/app/api/v1/sessions.py` (114 lines)

```python
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional, List

from app.core.database import get_db
from app.services.session_service import SessionService
from app.schemas.work_session import (
    WorkSessionCreate,
    WorkSessionResponse,
    WorkSessionWithDetails
)

router = APIRouter()


@router.post("/start", response_model=WorkSessionResponse, status_code=201)
def start_session(
    data: WorkSessionCreate,
    db: Session = Depends(get_db)
):
    """Start new work session"""
    service = SessionService(db)
    try:
        session = service.start_session(data)
        return WorkSessionResponse.from_orm(session)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/break/{user_id}", response_model=WorkSessionResponse)
def take_break(
    user_id: int,
    db: Session = Depends(get_db)
):
    """Take a break"""
    service = SessionService(db)
    try:
        session = service.take_break(user_id)
        return WorkSessionResponse.from_orm(session)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/resume/{user_id}", response_model=WorkSessionResponse)
def resume_work(
    user_id: int,
    db: Session = Depends(get_db)
):
    """Resume work from break"""
    service = SessionService(db)
    try:
        session = service.resume_work(user_id)
        return WorkSessionResponse.from_orm(session)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/finish/{user_id}", response_model=WorkSessionResponse)
def finish_session(
    user_id: int,
    db: Session = Depends(get_db)
):
    """Finish work session"""
    service = SessionService(db)
    try:
        session = service.finish_session(user_id)
        return WorkSessionResponse.from_orm(session)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/current/{user_id}", response_model=Optional[WorkSessionWithDetails])
def get_current_session(
    user_id: int,
    db: Session = Depends(get_db)
):
    """Get user's current active session"""
    service = SessionService(db)
    session = service.get_current_session(user_id)
    
    if not session:
        return None
    
    return WorkSessionWithDetails.from_orm(session)


@router.get("/history/{user_id}", response_model=List[WorkSessionResponse])
def get_session_history(
    user_id: int,
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """Get user's session history"""
    service = SessionService(db)
    sessions = service.get_session_history(user_id, date_from, date_to, limit)
    return [WorkSessionResponse.from_orm(s) for s in sessions]


@router.get("/{session_id}", response_model=WorkSessionWithDetails)
def get_session(
    session_id: int,
    db: Session = Depends(get_db)
):
    """Get session by ID with details"""
    service = SessionService(db)
    session = service.get_session_by_id(session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return WorkSessionWithDetails.from_orm(session)

```

---

### Team API

**File:** `backend/app/api/v1/team.py` (226 lines)

```python
from fastapi import APIRouter, Depends, Query, Header, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

from app.core.database import get_db
from app.core.rbac import RBACService, get_rbac_service
from app.services.team_service import TeamService

router = APIRouter()


class TeamMemberStatus(BaseModel):
    """Team member status response"""
    user_id: int
    user_name: str
    department: str | None
    department_id: int | None
    current_status: str
    session_id: int | None
    session_start: datetime | None
    work_time: int
    break_time: int
    break_count: int
    last_activity: datetime | None
    last_activity_time: datetime | None  # Real CRM activity time
    is_online: bool  # Activity < 5 minutes


class TeamStats(BaseModel):
    """Team statistics response"""
    total_members: int
    working: int
    on_break: int
    not_working: int
    total_work_time: int
    total_break_time: int
    avg_work_time: float
    avg_break_time: float


@router.get("/status", response_model=List[TeamMemberStatus])
def get_team_status(
    user_id: int = Header(..., alias="X-User-Id"),
    account_id: int = Header(..., alias="X-Account-Id"),
    department_id: Optional[int] = Query(None),
    status_filter: Optional[str] = Query(None),
    online_only: bool = Query(False),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    rbac: RBACService = Depends(get_rbac_service)
):
    """
    Get current status of team members with RBAC filtering.
    - Admin: all employees
    - ROP: only employees from allowed departments
    - Employee: forbidden
    """
    user = rbac.get_user_by_amocrm_id(user_id, account_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Only ROP and Admin can view team
    if rbac.is_employee(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Get accessible departments
    accessible_dept_ids = rbac.get_accessible_departments(user)
    
    service = TeamService(db)
    return service.get_team_status_with_rbac(
        accessible_dept_ids=accessible_dept_ids,
        department_id=department_id,
        status_filter=status_filter,
        online_only=online_only,
        search=search
    )


@router.get("/stats", response_model=TeamStats)
def get_team_stats(
    department: str | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    db: Session = Depends(get_db)
):
    """Get team statistics"""
    service = TeamService(db)
    return service.get_team_stats(department, date_from, date_to)


@router.get("/activity", response_model=List[Dict[str, Any]])
def get_team_activity(
    date: datetime | None = Query(None),
    department: str | None = Query(None),
    db: Session = Depends(get_db)
):
    """Get team activity for specific date"""
    service = TeamService(db)
    if not date:
        date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    
    return service.get_team_activity(date, department)


# Import team schemas
from app.schemas.team import (
    ActivityTimelineResponse,
    ActivityHistoryResponse,
    ForceFinishRequest,
    ForceFinishResponse
)


@router.get("/{target_user_id}/timeline", response_model=ActivityTimelineResponse)
def get_user_timeline(
    target_user_id: int,
    date: Optional[str] = Query(None),
    user_id: int = Header(..., alias="X-User-Id"),
    account_id: int = Header(..., alias="X-Account-Id"),
    db: Session = Depends(get_db),
    rbac: RBACService = Depends(get_rbac_service)
):
    """
    Get user CRM activity timeline for specific date.
    Timeline shows 15-minute intervals with activity counts.
    Only ROP/Admin can view.
    """
    user = rbac.get_user_by_amocrm_id(user_id, account_id)
    
    if not user or rbac.is_employee(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Check if user can view this employee
    from app.models.user import User
    target_user = db.query(User).filter(User.amocrm_user_id == target_user_id).first()
    
    if target_user and not rbac.can_view_employee(user, target_user.department_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot view this employee"
        )
    
    service = TeamService(db)
    return service.get_user_timeline(target_user_id, date)


@router.get("/{target_user_id}/timeline/history", response_model=ActivityHistoryResponse)
def get_user_timeline_history(
    target_user_id: int,
    user_id: int = Header(..., alias="X-User-Id"),
    account_id: int = Header(..., alias="X-Account-Id"),
    db: Session = Depends(get_db),
    rbac: RBACService = Depends(get_rbac_service)
):
    """
    Get user CRM activity history for last 7 days.
    Only ROP/Admin can view.
    """
    user = rbac.get_user_by_amocrm_id(user_id, account_id)
    
    if not user or rbac.is_employee(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Check if user can view this employee
    from app.models.user import User
    target_user = db.query(User).filter(User.amocrm_user_id == target_user_id).first()
    
    if target_user and not rbac.can_view_employee(user, target_user.department_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot view this employee"
        )
    
    service = TeamService(db)
    return service.get_user_timeline_history(target_user_id)


@router.post("/{target_user_id}/force-finish", response_model=ForceFinishResponse)
def force_finish_session(
    target_user_id: int,
    request: ForceFinishRequest,
    user_id: int = Header(..., alias="X-User-Id"),
    account_id: int = Header(..., alias="X-Account-Id"),
    db: Session = Depends(get_db),
    rbac: RBACService = Depends(get_rbac_service)
):
    """
    Force finish work session for employee.
    Only Admin can force finish.
    """
    user = rbac.get_user_by_amocrm_id(user_id, account_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if not rbac.can_force_finish(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Admin can force finish sessions"
        )
    
    service = TeamService(db)
    return service.force_finish_session(
        target_user_id=target_user_id,
        admin_id=user.id,
        admin_name=user.name,
        reason=request.reason
    )

```

---

### Activity API

**File:** `backend/app/api/v1/activity.py` (128 lines)

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional

from app.core.database import get_db
from app.services.activity_service import ActivityService
from app.models.activity_session import EntityType
from app.models.activity_event import EventType
from app.schemas.activity_session import ActivitySessionResponse, ActivitySessionWithEvents
from app.schemas.activity_event import ActivityEventResponse

router = APIRouter()


@router.post("/start", response_model=ActivitySessionResponse, status_code=201)
def start_activity(
    work_session_id: int,
    entity_type: EntityType,
    entity_id: int,
    entity_name: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Start new activity session (открыть карточку)"""
    service = ActivityService(db)
    try:
        session = service.start_activity(work_session_id, entity_type, entity_id, entity_name)
        return ActivitySessionResponse.from_orm(session)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/stop/{activity_session_id}", response_model=ActivitySessionResponse)
def stop_activity(
    activity_session_id: int,
    db: Session = Depends(get_db)
):
    """Stop activity session (закрыть карточку)"""
    service = ActivityService(db)
    try:
        session = service.stop_activity(activity_session_id)
        return ActivitySessionResponse.from_orm(session)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/switch", response_model=ActivitySessionResponse)
def switch_activity(
    work_session_id: int,
    entity_type: EntityType,
    entity_id: int,
    entity_name: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Switch to another entity (переключиться на другую карточку)"""
    service = ActivityService(db)
    try:
        session = service.switch_activity(work_session_id, entity_type, entity_id, entity_name)
        return ActivitySessionResponse.from_orm(session)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/event", response_model=ActivityEventResponse, status_code=201)
def track_event(
    activity_session_id: int,
    event_type: EventType,
    description: Optional[str] = None,
    event_data: Optional[Dict[str, Any]] = None,
    category_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Track event in activity session (зафиксировать событие)"""
    service = ActivityService(db)
    try:
        event = service.track_event(
            activity_session_id, event_type, event_data, description, category_id
        )
        return ActivityEventResponse.from_orm(event)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/current/{work_session_id}", response_model=Optional[ActivitySessionWithEvents])
def get_current_activity(
    work_session_id: int,
    db: Session = Depends(get_db)
):
    """Get current active activity session"""
    service = ActivityService(db)
    session = service.get_current_activity(work_session_id)
    
    if not session:
        return None
    
    return ActivitySessionWithEvents.from_orm(session)


@router.get("/history/{work_session_id}", response_model=List[ActivitySessionResponse])
def get_activity_history(
    work_session_id: int,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get activity history for work session"""
    service = ActivityService(db)
    sessions = service.get_activity_history(work_session_id, limit)
    return [ActivitySessionResponse.from_orm(s) for s in sessions]


@router.get("/events/{activity_session_id}", response_model=List[ActivityEventResponse])
def get_activity_events(
    activity_session_id: int,
    db: Session = Depends(get_db)
):
    """Get all events for activity session"""
    service = ActivityService(db)
    events = service.get_events(activity_session_id)
    return [ActivityEventResponse.from_orm(e) for e in events]


@router.get("/stats/{work_session_id}", response_model=Dict[str, Any])
def get_activity_stats(
    work_session_id: int,
    db: Session = Depends(get_db)
):
    """Get activity statistics for work session"""
    service = ActivityService(db)
    return service.get_activity_stats(work_session_id)

```

---

### Categories API

**File:** `backend/app/api/v1/categories.py` (81 lines)

```python
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.services.category_service import CategoryService
from app.schemas.activity_category import (
    ActivityCategoryCreate,
    ActivityCategoryUpdate,
    ActivityCategoryResponse
)

router = APIRouter()


@router.post("", response_model=ActivityCategoryResponse, status_code=201)
def create_category(
    account_id: str,
    data: ActivityCategoryCreate,
    db: Session = Depends(get_db)
):
    """Create new activity category"""
    service = CategoryService(db)
    category = service.create_category(account_id, data)
    return ActivityCategoryResponse.from_orm(category)


@router.get("", response_model=List[ActivityCategoryResponse])
def get_categories(
    account_id: str,
    active_only: bool = Query(False),
    db: Session = Depends(get_db)
):
    """Get all categories for account"""
    service = CategoryService(db)
    categories = service.get_categories(account_id, active_only)
    return [ActivityCategoryResponse.from_orm(c) for c in categories]


@router.get("/{category_id}", response_model=ActivityCategoryResponse)
def get_category(
    category_id: int,
    db: Session = Depends(get_db)
):
    """Get category by ID"""
    service = CategoryService(db)
    category = service.get_category(category_id)
    
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    return ActivityCategoryResponse.from_orm(category)


@router.put("/{category_id}", response_model=ActivityCategoryResponse)
def update_category(
    category_id: int,
    data: ActivityCategoryUpdate,
    db: Session = Depends(get_db)
):
    """Update category"""
    service = CategoryService(db)
    try:
        category = service.update_category(category_id, data)
        return ActivityCategoryResponse.from_orm(category)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{category_id}", status_code=204)
def delete_category(
    category_id: int,
    db: Session = Depends(get_db)
):
    """Delete category (soft delete)"""
    service = CategoryService(db)
    try:
        service.delete_category(category_id)
        return None
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

```

---

### Settings API

**File:** `backend/app/api/v1/settings.py` (56 lines)

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.settings_service import SettingsService
from app.schemas.widget_settings import WidgetSettingsResponse, WidgetSettingsUpdate

router = APIRouter()


@router.get("/{account_id}", response_model=WidgetSettingsResponse)
def get_settings(
    account_id: str,
    db: Session = Depends(get_db)
):
    """Get widget settings for account"""
    service = SettingsService(db)
    settings = service.get_settings(account_id)
    
    if not settings:
        # Return defaults if not found
        return WidgetSettingsResponse(
            account_id=account_id,
            auto_pause_on_close=True,
            require_category=False,
            track_idle_time=False,
            idle_threshold_minutes=5,
            show_team_stats=True,
            enable_reports=True,
            config={}
        )
    
    return WidgetSettingsResponse.from_orm(settings)


@router.put("/{account_id}", response_model=WidgetSettingsResponse)
def update_settings(
    account_id: str,
    data: WidgetSettingsUpdate,
    db: Session = Depends(get_db)
):
    """Create or update widget settings"""
    service = SettingsService(db)
    settings = service.create_or_update_settings(account_id, data)
    return WidgetSettingsResponse.from_orm(settings)


@router.post("/{account_id}/reset", response_model=WidgetSettingsResponse)
def reset_settings(
    account_id: str,
    db: Session = Depends(get_db)
):
    """Reset settings to defaults"""
    service = SettingsService(db)
    settings = service.reset_settings(account_id)
    return WidgetSettingsResponse.from_orm(settings)

```

---

### Reports API

**File:** `backend/app/api/v1/reports.py` (331 lines)

```python
"""
Reports API
API endpoints для отчётов
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date, datetime

from app.core.database import get_db
from app.services.report_service import ReportService
from app.models.report import ReportType, ReportFormat
from app.schemas.report import (
    DailyReportRequest,
    WeeklyReportRequest,
    MonthlyReportRequest,
    DailySummary,
    WeeklySummary,
    MonthlySummary,
    EmployeeReport,
    PeriodStatistics,
    ReportResponse,
    ReportListResponse,
    ReportGenerateRequest
)

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/daily", response_model=DailySummary)
def get_daily_report(
    account_id: str = Query(..., description="ID аккаунта amoCRM"),
    date: date = Query(..., description="Дата отчёта"),
    user_id: Optional[int] = Query(None, description="ID пользователя (опционально)"),
    department: Optional[str] = Query(None, description="Отдел (опционально)"),
    db: Session = Depends(get_db)
):
    """
    Получить дневной отчёт
    
    - **account_id**: ID аккаунта
    - **date**: Дата (YYYY-MM-DD)
    - **user_id**: Фильтр по пользователю (опционально)
    - **department**: Фильтр по отделу (опционально)
    """
    return ReportService.get_daily_report(
        db=db,
        account_id=account_id,
        target_date=date,
        user_id=user_id,
        department=department
    )


@router.get("/weekly", response_model=WeeklySummary)
def get_weekly_report(
    account_id: str = Query(..., description="ID аккаунта amoCRM"),
    week_start: date = Query(..., description="Начало недели (понедельник)"),
    user_id: Optional[int] = Query(None, description="ID пользователя"),
    department: Optional[str] = Query(None, description="Отдел"),
    db: Session = Depends(get_db)
):
    """
    Получить недельный отчёт
    
    - **week_start**: Дата начала недели (желательно понедельник)
    """
    return ReportService.get_weekly_report(
        db=db,
        account_id=account_id,
        week_start=week_start,
        user_id=user_id,
        department=department
    )


@router.get("/monthly", response_model=MonthlySummary)
def get_monthly_report(
    account_id: str = Query(..., description="ID аккаунта amoCRM"),
    year: int = Query(..., description="Год"),
    month: int = Query(..., ge=1, le=12, description="Месяц (1-12)"),
    user_id: Optional[int] = Query(None, description="ID пользователя"),
    department: Optional[str] = Query(None, description="Отдел"),
    db: Session = Depends(get_db)
):
    """
    Получить месячный отчёт
    
    - **year**: Год (например, 2026)
    - **month**: Месяц (1-12)
    """
    return ReportService.get_monthly_report(
        db=db,
        account_id=account_id,
        year=year,
        month=month,
        user_id=user_id,
        department=department
    )


@router.get("/employee/{user_id}", response_model=EmployeeReport)
def get_employee_report(
    user_id: int,
    account_id: str = Query(..., description="ID аккаунта amoCRM"),
    start_date: date = Query(..., description="Начало периода"),
    end_date: date = Query(..., description="Конец периода"),
    db: Session = Depends(get_db)
):
    """
    Получить детальный отчёт по сотруднику
    
    - **user_id**: ID пользователя
    - **start_date**: Начало периода
    - **end_date**: Конец периода
    """
    report = ReportService.get_employee_report(
        db=db,
        account_id=account_id,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date
    )
    
    if not report:
        raise HTTPException(status_code=404, detail="Данные не найдены")
    
    return report


@router.get("/statistics", response_model=PeriodStatistics)
def get_period_statistics(
    account_id: str = Query(..., description="ID аккаунта amoCRM"),
    start_date: date = Query(..., description="Начало периода"),
    end_date: date = Query(..., description="Конец периода"),
    department: Optional[str] = Query(None, description="Отдел"),
    db: Session = Depends(get_db)
):
    """
    Получить статистику за произвольный период
    
    - **start_date**: Начало периода
    - **end_date**: Конец периода
    - **department**: Фильтр по отделу (опционально)
    """
    return ReportService.get_period_statistics(
        db=db,
        account_id=account_id,
        start_date=start_date,
        end_date=end_date,
        department=department
    )


@router.post("/generate", response_model=ReportResponse, status_code=201)
def generate_report(
    request: ReportGenerateRequest,
    account_id: str = Query(..., description="ID аккаунта amoCRM"),
    generated_by: int = Query(..., description="ID пользователя, создающего отчёт"),
    db: Session = Depends(get_db)
):
    """
    Сгенерировать и сохранить отчёт
    
    - Создаёт отчёт и сохраняет его в БД
    - Возвращает ID отчёта для последующего скачивания
    """
    # Generate report data based on type
    if request.report_type == ReportType.DAILY:
        data = ReportService.get_daily_report(
            db=db,
            account_id=account_id,
            target_date=request.start_date,
            user_id=request.user_id,
            department=request.department
        ).dict()
        title = f"Дневной отчёт {request.start_date}"
        
    elif request.report_type == ReportType.WEEKLY:
        data = ReportService.get_weekly_report(
            db=db,
            account_id=account_id,
            week_start=request.start_date,
            user_id=request.user_id,
            department=request.department
        ).dict()
        title = f"Недельный отчёт {request.start_date}"
        
    elif request.report_type == ReportType.MONTHLY:
        data = ReportService.get_monthly_report(
            db=db,
            account_id=account_id,
            year=request.start_date.year,
            month=request.start_date.month,
            user_id=request.user_id,
            department=request.department
        ).dict()
        title = f"Месячный отчёт {request.start_date.strftime('%B %Y')}"
        
    elif request.report_type == ReportType.EMPLOYEE:
        if not request.user_id:
            raise HTTPException(status_code=400, detail="user_id обязателен для employee report")
        data = ReportService.get_employee_report(
            db=db,
            account_id=account_id,
            user_id=request.user_id,
            start_date=request.start_date,
            end_date=request.end_date
        ).dict()
        title = f"Отчёт сотрудника {request.start_date} - {request.end_date}"
        
    else:  # CUSTOM
        data = ReportService.get_period_statistics(
            db=db,
            account_id=account_id,
            start_date=request.start_date,
            end_date=request.end_date,
            department=request.department
        ).dict()
        title = f"Отчёт {request.start_date} - {request.end_date}"
    
    # Create summary
    summary = {
        "report_type": request.report_type.value,
        "generated_at": datetime.now().isoformat(),
        "period": f"{request.start_date} - {request.end_date}"
    }
    
    # Save report
    report = ReportService.save_report(
        db=db,
        account_id=account_id,
        report_type=request.report_type,
        report_format=request.report_format,
        title=title,
        start_date=datetime.combine(request.start_date, datetime.min.time()),
        end_date=datetime.combine(request.end_date, datetime.max.time()),
        data=data,
        generated_by=generated_by,
        user_id=request.user_id,
        department=request.department,
        summary=summary
    )
    
    return report


@router.get("", response_model=ReportListResponse)
def get_reports_list(
    account_id: str = Query(..., description="ID аккаунта amoCRM"),
    skip: int = Query(0, ge=0, description="Пропустить записей"),
    limit: int = Query(100, ge=1, le=1000, description="Лимит записей"),
    report_type: Optional[ReportType] = Query(None, description="Фильтр по типу"),
    db: Session = Depends(get_db)
):
    """
    Получить список сохранённых отчётов
    
    - **skip**: Пагинация - пропустить записей
    - **limit**: Пагинация - лимит записей
    - **report_type**: Фильтр по типу отчёта
    """
    reports = ReportService.get_reports(
        db=db,
        account_id=account_id,
        skip=skip,
        limit=limit,
        report_type=report_type
    )
    
    # Count total (simple approach, can be optimized)
    total = len(ReportService.get_reports(db=db, account_id=account_id, skip=0, limit=10000))
    
    return ReportListResponse(
        total=total,
        reports=reports
    )


@router.get("/{report_id}", response_model=ReportResponse)
def get_report(
    report_id: int,
    db: Session = Depends(get_db)
):
    """
    Получить отчёт по ID
    """
    report = ReportService.get_report_by_id(db=db, report_id=report_id)
    
    if not report:
        raise HTTPException(status_code=404, detail="Отчёт не найден")
    
    return report


@router.delete("/{report_id}", status_code=204)
def delete_report(
    report_id: int,
    db: Session = Depends(get_db)
):
    """
    Удалить отчёт
    """
    success = ReportService.delete_report(db=db, report_id=report_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Отчёт не найден")
    
    return None


@router.get("/{report_id}/download")
def download_report(
    report_id: int,
    format: ReportFormat = Query(ReportFormat.EXCEL, description="Формат скачивания"),
    db: Session = Depends(get_db)
):
    """
    Скачать отчёт в выбранном формате
    
    - **format**: Формат (excel, pdf, csv)
    
    TODO: Реализовать Excel/PDF export
    """
    report = ReportService.get_report_by_id(db=db, report_id=report_id)
    
    if not report:
        raise HTTPException(status_code=404, detail="Отчёт не найден")
    
    # TODO: Implement Excel/PDF generation
    raise HTTPException(status_code=501, detail="Excel/PDF export в разработке")

```

---

### Departments Endpoint

**File:** `backend/app/api/v1/endpoints/departments.py` (194 lines)

```python
"""Department endpoints"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.rbac import RBACService, get_rbac_service
from app.models.department import Department
from app.schemas.department import (
    DepartmentResponse,
    DepartmentCreate,
    DepartmentUpdate,
    DepartmentScheduleResponse
)

router = APIRouter()


@router.get("/", response_model=List[DepartmentResponse])
def get_departments(
    user_id: int = Header(..., alias="X-User-Id"),
    account_id: int = Header(..., alias="X-Account-Id"),
    db: Session = Depends(get_db),
    rbac: RBACService = Depends(get_rbac_service)
):
    """
    Get list of departments.
    - Admin: all departments
    - ROP: only allowed departments
    - Employee: forbidden
    """
    user = rbac.get_user_by_amocrm_id(user_id, account_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Only ROP and Admin can view departments
    if rbac.is_employee(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Get accessible departments
    accessible_dept_ids = rbac.get_accessible_departments(user)
    
    # Admin (None) - get all departments
    if accessible_dept_ids is None:
        departments = db.query(Department).filter(
            Department.is_active == True
        ).all()
    # ROP - get only allowed departments
    elif accessible_dept_ids:
        departments = db.query(Department).filter(
            Department.id.in_(accessible_dept_ids),
            Department.is_active == True
        ).all()
    else:
        departments = []
    
    return departments


@router.get("/{department_id}/schedule", response_model=DepartmentScheduleResponse)
def get_department_schedule(
    department_id: int,
    user_id: int = Header(..., alias="X-User-Id"),
    account_id: int = Header(..., alias="X-Account-Id"),
    db: Session = Depends(get_db),
    rbac: RBACService = Depends(get_rbac_service)
):
    """
    Get department schedule.
    Used by widget to check if employee is late.
    """
    user = rbac.get_user_by_amocrm_id(user_id, account_id)
    
    if not user:
        # If user not found, create with EMPLOYEE role
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    department = db.query(Department).filter(
        Department.id == department_id,
        Department.is_active == True
    ).first()
    
    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found"
        )
    
    return DepartmentScheduleResponse(
        department_id=department.id,
        department_name=department.name,
        work_start_time=department.work_start_time,
        work_end_time=department.work_end_time
    )


@router.post("/", response_model=DepartmentResponse, status_code=status.HTTP_201_CREATED)
def create_department(
    department_data: DepartmentCreate,
    user_id: int = Header(..., alias="X-User-Id"),
    account_id: int = Header(..., alias="X-Account-Id"),
    db: Session = Depends(get_db),
    rbac: RBACService = Depends(get_rbac_service)
):
    """
    Create new department (Admin only).
    """
    user = rbac.get_user_by_amocrm_id(user_id, account_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if not rbac.can_manage_departments(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required"
        )
    
    # Check if department with this name already exists
    existing = db.query(Department).filter(
        Department.name == department_data.name
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Department with this name already exists"
        )
    
    department = Department(**department_data.dict())
    db.add(department)
    db.commit()
    db.refresh(department)
    
    return department


@router.put("/{department_id}/schedule", response_model=DepartmentResponse)
def update_department_schedule(
    department_id: int,
    update_data: DepartmentUpdate,
    user_id: int = Header(..., alias="X-User-Id"),
    account_id: int = Header(..., alias="X-Account-Id"),
    db: Session = Depends(get_db),
    rbac: RBACService = Depends(get_rbac_service)
):
    """
    Update department schedule (Admin only).
    """
    user = rbac.get_user_by_amocrm_id(user_id, account_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if not rbac.can_manage_departments(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required"
        )
    
    department = db.query(Department).filter(
        Department.id == department_id
    ).first()
    
    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found"
        )
    
    # Update fields
    update_dict = update_data.dict(exclude_unset=True)
    for field, value in update_dict.items():
        setattr(department, field, value)
    
    db.commit()
    db.refresh(department)
    
    return department

```

---

### Excel Export Endpoint

**File:** `backend/app/api/v1/endpoints/excel.py` (202 lines)

```python
"""Excel export endpoints"""
from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from datetime import date

from app.core.database import get_db
from app.core.rbac import RBACService, get_rbac_service
from app.schemas.excel import ExcelExportRequest
from app.services.excel_service import ExcelService

router = APIRouter()


@router.post("/department")
async def export_department_report(
    request: ExcelExportRequest,
    user_id: int = Header(..., alias="X-User-Id"),
    account_id: int = Header(..., alias="X-Account-Id"),
    db: Session = Depends(get_db),
    rbac: RBACService = Depends(get_rbac_service)
):
    """
    Export department report to Excel.
    Only ROP and Admin can export.
    ROP can only export their accessible departments.
    """
    user = rbac.get_user_by_amocrm_id(user_id, account_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Only ROP and Admin can export
    if rbac.is_employee(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Get accessible departments
    accessible_dept_ids = rbac.get_accessible_departments(user)
    
    # Filter by RBAC
    if accessible_dept_ids is not None:  # Not Admin
        if request.department_ids:
            # Check if requested departments are accessible
            if not all(d in accessible_dept_ids for d in request.department_ids):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cannot access some departments"
                )
            dept_ids = request.department_ids
        else:
            dept_ids = accessible_dept_ids
    else:
        dept_ids = request.department_ids
    
    # Generate report
    service = ExcelService(db)
    excel_file = service.generate_department_report(
        date_from=request.date_from,
        date_to=request.date_to,
        department_ids=dept_ids,
        late_only=request.late_only,
        include_comments=request.include_comments
    )
    
    filename = f"department_report_{request.date_from}_{request.date_to}.xlsx"
    
    return StreamingResponse(
        excel_file,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.post("/employee/{employee_id}")
async def export_employee_report(
    employee_id: int,
    request: ExcelExportRequest,
    user_id: int = Header(..., alias="X-User-Id"),
    account_id: int = Header(..., alias="X-Account-Id"),
    db: Session = Depends(get_db),
    rbac: RBACService = Depends(get_rbac_service)
):
    """
    Export employee report to Excel.
    ROP and Admin can export.
    ROP can only export employees from accessible departments.
    """
    user = rbac.get_user_by_amocrm_id(user_id, account_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Only ROP and Admin can export
    if rbac.is_employee(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Check if user can view this employee
    from app.models.user import User
    target_user = db.query(User).filter(User.id == employee_id).first()
    
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found"
        )
    
    if not rbac.can_view_employee(user, target_user.department_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access this employee"
        )
    
    # Generate report
    service = ExcelService(db)
    excel_file = service.generate_employee_report(
        user_id=employee_id,
        date_from=request.date_from,
        date_to=request.date_to,
        include_comments=request.include_comments
    )
    
    filename = f"employee_{target_user.name}_{request.date_from}_{request.date_to}.xlsx"
    
    return StreamingResponse(
        excel_file,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.post("/late-arrivals")
async def export_late_arrivals_report(
    request: ExcelExportRequest,
    user_id: int = Header(..., alias="X-User-Id"),
    account_id: int = Header(..., alias="X-Account-Id"),
    db: Session = Depends(get_db),
    rbac: RBACService = Depends(get_rbac_service)
):
    """
    Export late arrivals report to Excel.
    Only ROP and Admin can export.
    ROP can only export their accessible departments.
    """
    user = rbac.get_user_by_amocrm_id(user_id, account_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Only ROP and Admin can export
    if rbac.is_employee(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Get accessible departments
    accessible_dept_ids = rbac.get_accessible_departments(user)
    
    # Filter by RBAC
    if accessible_dept_ids is not None:  # Not Admin
        if request.department_ids:
            if not all(d in accessible_dept_ids for d in request.department_ids):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cannot access some departments"
                )
            dept_ids = request.department_ids
        else:
            dept_ids = accessible_dept_ids
    else:
        dept_ids = request.department_ids
    
    # Generate report
    service = ExcelService(db)
    excel_file = service.generate_late_arrivals_report(
        date_from=request.date_from,
        date_to=request.date_to,
        department_ids=dept_ids
    )
    
    filename = f"late_arrivals_{request.date_from}_{request.date_to}.xlsx"
    
    return StreamingResponse(
        excel_file,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

```

---

### KPI Endpoint

**File:** `backend/app/api/v1/endpoints/kpi.py` (198 lines)

```python
"""KPI and dashboard endpoints"""
from fastapi import APIRouter, Depends, Header, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import RBACService, get_rbac_service
from app.schemas.kpi import KPIMetrics, ChartData, DashboardSettingsUpdate
from app.services.kpi_service import KPIService
from app.models.dashboard_settings import DashboardSettings

router = APIRouter()


@router.get("/my", response_model=KPIMetrics)
async def get_my_kpi(
    user_id: int = Header(..., alias="X-User-Id"),
    account_id: int = Header(..., alias="X-Account-Id"),
    db: Session = Depends(get_db),
    rbac: RBACService = Depends(get_rbac_service)
):
    """Get my KPI metrics (all roles)"""
    user = rbac.get_user_by_amocrm_id(user_id, account_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    service = KPIService(db)
    return service.calculate_user_kpi(user.id, user.amocrm_user_id)


@router.get("/user/{target_user_id}", response_model=KPIMetrics)
async def get_user_kpi(
    target_user_id: int,
    user_id: int = Header(..., alias="X-User-Id"),
    account_id: int = Header(..., alias="X-Account-Id"),
    db: Session = Depends(get_db),
    rbac: RBACService = Depends(get_rbac_service)
):
    """Get user KPI (ROP/Admin only)"""
    user = rbac.get_user_by_amocrm_id(user_id, account_id)
    if not user or rbac.is_employee(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    from app.models.user import User
    target = db.query(User).filter(User.id == target_user_id).first()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    if not rbac.can_view_employee(user, target.department_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot access this user")
    
    service = KPIService(db)
    return service.calculate_user_kpi(target.id, target.amocrm_user_id)


@router.get("/department/{dept_id}", response_model=KPIMetrics)
async def get_department_kpi(
    dept_id: int,
    user_id: int = Header(..., alias="X-User-Id"),
    account_id: int = Header(..., alias="X-Account-Id"),
    db: Session = Depends(get_db),
    rbac: RBACService = Depends(get_rbac_service)
):
    """Get department KPI (ROP/Admin only)"""
    user = rbac.get_user_by_amocrm_id(user_id, account_id)
    if not user or rbac.is_employee(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    if not rbac.can_view_department(user, dept_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot access this department")
    
    service = KPIService(db)
    return service.calculate_department_kpi(dept_id)


@router.get("/chart/my", response_model=ChartData)
async def get_my_chart(
    days: int = Query(7, ge=1, le=30),
    user_id: int = Header(..., alias="X-User-Id"),
    account_id: int = Header(..., alias="X-Account-Id"),
    db: Session = Depends(get_db),
    rbac: RBACService = Depends(get_rbac_service)
):
    """Get my chart data"""
    user = rbac.get_user_by_amocrm_id(user_id, account_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    service = KPIService(db)
    return service.get_chart_data(user.amocrm_user_id, days)


@router.get("/chart/user/{target_user_id}", response_model=ChartData)
async def get_user_chart(
    target_user_id: int,
    days: int = Query(7, ge=1, le=30),
    user_id: int = Header(..., alias="X-User-Id"),
    account_id: int = Header(..., alias="X-Account-Id"),
    db: Session = Depends(get_db),
    rbac: RBACService = Depends(get_rbac_service)
):
    """Get user chart data (ROP/Admin only)"""
    user = rbac.get_user_by_amocrm_id(user_id, account_id)
    if not user or rbac.is_employee(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    from app.models.user import User
    target = db.query(User).filter(User.id == target_user_id).first()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    if not rbac.can_view_employee(user, target.department_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot access this user")
    
    service = KPIService(db)
    return service.get_chart_data(target.amocrm_user_id, days)


@router.get("/chart/department/{dept_id}", response_model=ChartData)
async def get_department_chart(
    dept_id: int,
    days: int = Query(7, ge=1, le=30),
    user_id: int = Header(..., alias="X-User-Id"),
    account_id: int = Header(..., alias="X-Account-Id"),
    db: Session = Depends(get_db),
    rbac: RBACService = Depends(get_rbac_service)
):
    """Get department chart data (ROP/Admin only)"""
    user = rbac.get_user_by_amocrm_id(user_id, account_id)
    if not user or rbac.is_employee(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    if not rbac.can_view_department(user, dept_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot access this department")
    
    service = KPIService(db)
    return service.get_department_chart_data(dept_id, days)


@router.get("/dashboard/settings")
async def get_dashboard_settings(
    user_id: int = Header(..., alias="X-User-Id"),
    account_id: int = Header(..., alias="X-Account-Id"),
    db: Session = Depends(get_db),
    rbac: RBACService = Depends(get_rbac_service)
):
    """Get dashboard settings"""
    user = rbac.get_user_by_amocrm_id(user_id, account_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    settings = db.query(DashboardSettings).filter(DashboardSettings.user_id == user.id).first()
    if not settings:
        # Return defaults
        return {
            "show_online": True,
            "show_late_arrivals": True,
            "show_team_stats": not rbac.is_employee(user),
            "default_period": "week",
            "chart_type": "line"
        }
    
    return settings


@router.put("/dashboard/settings")
async def update_dashboard_settings(
    updates: DashboardSettingsUpdate,
    user_id: int = Header(..., alias="X-User-Id"),
    account_id: int = Header(..., alias="X-Account-Id"),
    db: Session = Depends(get_db),
    rbac: RBACService = Depends(get_rbac_service)
):
    """Update dashboard settings"""
    user = rbac.get_user_by_amocrm_id(user_id, account_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    settings = db.query(DashboardSettings).filter(DashboardSettings.user_id == user.id).first()
    if not settings:
        settings = DashboardSettings(user_id=user.id)
        db.add(settings)
    
    # Update fields
    if updates.show_online is not None:
        settings.show_online = updates.show_online
    if updates.show_late_arrivals is not None:
        settings.show_late_arrivals = updates.show_late_arrivals
    if updates.show_team_stats is not None:
        settings.show_team_stats = updates.show_team_stats
    if updates.default_period is not None:
        settings.default_period = updates.default_period
    if updates.chart_type is not None:
        settings.chart_type = updates.chart_type
    
    db.commit()
    db.refresh(settings)
    
    return settings

```

---

### KPI Service

**File:** `backend/app/services/kpi_service.py` (233 lines)

```python
"""KPI calculation service"""
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta, date
from typing import Dict, List

from app.models.work_session import WorkSession
from app.models.user import User
from app.schemas.kpi import KPIMetrics, ChartData


class KPIService:
    """Service for calculating KPI metrics"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def calculate_user_kpi(self, user_id: int, amocrm_user_id: str) -> KPIMetrics:
        """Calculate KPI for a user"""
        now = datetime.now()
        today_start = datetime.combine(now.date(), datetime.min.time())
        week_start = today_start - timedelta(days=now.weekday())
        month_start = datetime(now.year, now.month, 1)
        
        # Today hours
        today_sessions = self.db.query(WorkSession).filter(
            WorkSession.user_id == amocrm_user_id,
            WorkSession.start_time >= today_start
        ).all()
        hours_today = sum(s.total_work_time for s in today_sessions) / 3600
        
        # Week hours
        week_sessions = self.db.query(WorkSession).filter(
            WorkSession.user_id == amocrm_user_id,
            WorkSession.start_time >= week_start
        ).all()
        hours_week = sum(s.total_work_time for s in week_sessions) / 3600
        
        # Month hours
        month_sessions = self.db.query(WorkSession).filter(
            WorkSession.user_id == amocrm_user_id,
            WorkSession.start_time >= month_start
        ).all()
        hours_month = sum(s.total_work_time for s in month_sessions) / 3600
        
        # Average per day (month)
        days_in_month = (now - month_start).days + 1
        avg_hours = hours_month / days_in_month if days_in_month > 0 else 0
        
        # Late counts
        late_week = sum(1 for s in week_sessions if s.is_late)
        late_month = sum(1 for s in month_sessions if s.is_late)
        
        # Completion % (assuming 8h norm)
        completion = (avg_hours / 8) * 100 if avg_hours > 0 else 0
        
        # Current status
        current_session = self.db.query(WorkSession).filter(
            WorkSession.user_id == amocrm_user_id,
            WorkSession.end_time == None
        ).first()
        
        if current_session:
            status = current_session.status.value
            is_online = (now - current_session.last_activity).seconds < 300 if current_session.last_activity else False
        else:
            status = "offline"
            is_online = False
        
        return KPIMetrics(
            hours_today=round(hours_today, 2),
            hours_week=round(hours_week, 2),
            hours_month=round(hours_month, 2),
            avg_hours_per_day=round(avg_hours, 2),
            late_count_week=late_week,
            late_count_month=late_month,
            completion_percentage=round(completion, 1),
            current_status=status,
            is_online=is_online
        )
    
    def calculate_department_kpi(self, department_id: int) -> KPIMetrics:
        """Calculate KPI for a department"""
        now = datetime.now()
        today_start = datetime.combine(now.date(), datetime.min.time())
        week_start = today_start - timedelta(days=now.weekday())
        month_start = datetime(now.year, now.month, 1)
        
        # Get all users in department
        users = self.db.query(User).filter(User.department_id == department_id).all()
        user_ids = [u.amocrm_user_id for u in users]
        
        if not user_ids:
            return KPIMetrics(
                hours_today=0, hours_week=0, hours_month=0, avg_hours_per_day=0,
                late_count_week=0, late_count_month=0, completion_percentage=0,
                current_status="offline", is_online=False,
                total_employees=0, online_now=0
            )
        
        # Aggregate sessions
        week_sessions = self.db.query(WorkSession).filter(
            WorkSession.user_id.in_(user_ids),
            WorkSession.start_time >= week_start
        ).all()
        
        month_sessions = self.db.query(WorkSession).filter(
            WorkSession.user_id.in_(user_ids),
            WorkSession.start_time >= month_start
        ).all()
        
        today_sessions = self.db.query(WorkSession).filter(
            WorkSession.user_id.in_(user_ids),
            WorkSession.start_time >= today_start
        ).all()
        
        hours_today = sum(s.total_work_time for s in today_sessions) / 3600
        hours_week = sum(s.total_work_time for s in week_sessions) / 3600
        hours_month = sum(s.total_work_time for s in month_sessions) / 3600
        
        days_in_month = (now - month_start).days + 1
        avg_hours = hours_month / (len(users) * days_in_month) if users else 0
        
        late_week = sum(1 for s in week_sessions if s.is_late)
        late_month = sum(1 for s in month_sessions if s.is_late)
        
        completion = (avg_hours / 8) * 100 if avg_hours > 0 else 0
        
        # Online count
        online = self.db.query(WorkSession).filter(
            WorkSession.user_id.in_(user_ids),
            WorkSession.end_time == None,
            WorkSession.last_activity >= now - timedelta(minutes=5)
        ).count()
        
        return KPIMetrics(
            hours_today=round(hours_today / len(users) if users else 0, 2),
            hours_week=round(hours_week / len(users) if users else 0, 2),
            hours_month=round(hours_month / len(users) if users else 0, 2),
            avg_hours_per_day=round(avg_hours, 2),
            late_count_week=late_week,
            late_count_month=late_month,
            completion_percentage=round(completion, 1),
            current_status="department",
            is_online=online > 0,
            total_employees=len(users),
            online_now=online
        )
    
    def get_chart_data(self, user_id: str, days: int = 7) -> ChartData:
        """Get chart data for user (last N days)"""
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days - 1)
        
        # Get sessions for period
        sessions = self.db.query(WorkSession).filter(
            WorkSession.user_id == user_id,
            WorkSession.start_time >= datetime.combine(start_date, datetime.min.time()),
            WorkSession.start_time <= datetime.combine(end_date, datetime.max.time())
        ).all()
        
        # Group by date
        data_by_date: Dict[date, float] = {}
        for session in sessions:
            session_date = session.start_time.date()
            hours = session.total_work_time / 3600
            data_by_date[session_date] = data_by_date.get(session_date, 0) + hours
        
        # Generate all dates in range
        labels = []
        values = []
        current_date = start_date
        while current_date <= end_date:
            labels.append(current_date.strftime("%Y-%m-%d"))
            values.append(round(data_by_date.get(current_date, 0), 2))
            current_date += timedelta(days=1)
        
        # Chart.js format
        datasets = [{
            "label": "Рабочие часы",
            "data": values,
            "borderColor": "rgb(75, 192, 192)",
            "backgroundColor": "rgba(75, 192, 192, 0.2)",
            "tension": 0.1
        }]
        
        return ChartData(labels=labels, datasets=datasets)
    
    def get_department_chart_data(self, department_id: int, days: int = 7) -> ChartData:
        """Get chart data for department"""
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days - 1)
        
        # Get users
        users = self.db.query(User).filter(User.department_id == department_id).all()
        user_ids = [u.amocrm_user_id for u in users]
        
        if not user_ids:
            return ChartData(labels=[], datasets=[])
        
        # Get sessions
        sessions = self.db.query(WorkSession).filter(
            WorkSession.user_id.in_(user_ids),
            WorkSession.start_time >= datetime.combine(start_date, datetime.min.time()),
            WorkSession.start_time <= datetime.combine(end_date, datetime.max.time())
        ).all()
        
        # Group by date
        data_by_date: Dict[date, float] = {}
        for session in sessions:
            session_date = session.start_time.date()
            hours = session.total_work_time / 3600
            data_by_date[session_date] = data_by_date.get(session_date, 0) + hours
        
        # Generate labels and values
        labels = []
        values = []
        current_date = start_date
        while current_date <= end_date:
            labels.append(current_date.strftime("%Y-%m-%d"))
            avg = data_by_date.get(current_date, 0) / len(users) if users else 0
            values.append(round(avg, 2))
            current_date += timedelta(days=1)
        
        datasets = [{
            "label": "Средние часы",
            "data": values,
            "borderColor": "rgb(54, 162, 235)",
            "backgroundColor": "rgba(54, 162, 235, 0.2)",
            "tension": 0.1
        }]
        
        return ChartData(labels=labels, datasets=datasets)

```

---

### Excel Service

**File:** `backend/app/services/excel_service.py` (275 lines)

```python
"""Excel export service"""
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.utils import get_column_letter
from sqlalchemy.orm import Session
from datetime import datetime, date
from typing import List, Optional
from io import BytesIO

from app.models.work_session import WorkSession, WorkStatus
from app.models.user import User
from app.models.department import Department
from app.models.work_comment import WorkComment


class ExcelService:
    """Service for generating Excel reports"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def generate_department_report(
        self,
        date_from: date,
        date_to: date,
        department_ids: Optional[List[int]] = None,
        late_only: bool = False,
        include_comments: bool = True
    ) -> BytesIO:
        """Generate department report"""
        wb = Workbook()
        ws = wb.active
        ws.title = "Отчёт по подразделениям"
        
        # Header
        self._add_header(ws, "Отчёт по подразделениям", date_from, date_to)
        
        # Table headers
        headers = [
            "Подразделение", "Сотрудник", "Дата", "Начало", "Конец",
            "Работа (ч)", "Перерывы (ч)", "Опоздание (мин)"
        ]
        if include_comments:
            headers.append("Комментарий РОП")
        
        row = 4
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=row, column=col, value=header)
            cell.font = Font(bold=True)
            cell.fill = PatternFill(start_color="CCCCCC", end_color="CCCCCC", fill_type="solid")
        
        # Data
        query = self.db.query(WorkSession).join(User).join(Department).filter(
            WorkSession.start_time >= datetime.combine(date_from, datetime.min.time()),
            WorkSession.start_time <= datetime.combine(date_to, datetime.max.time())
        )
        
        if department_ids:
            query = query.filter(User.department_id.in_(department_ids))
        
        if late_only:
            query = query.filter(WorkSession.is_late == True)
        
        sessions = query.order_by(Department.name, User.name, WorkSession.start_time).all()
        
        row = 5
        for session in sessions:
            ws.cell(row=row, column=1, value=session.user.department.name if session.user.department else "N/A")
            ws.cell(row=row, column=2, value=session.user.name)
            ws.cell(row=row, column=3, value=session.start_time.strftime("%Y-%m-%d"))
            ws.cell(row=row, column=4, value=session.start_time.strftime("%H:%M"))
            ws.cell(row=row, column=5, value=session.end_time.strftime("%H:%M") if session.end_time else "-")
            ws.cell(row=row, column=6, value=round(session.total_work_time / 3600, 2))
            ws.cell(row=row, column=7, value=round(session.total_break_time / 3600, 2))
            ws.cell(row=row, column=8, value=session.late_minutes if session.is_late else 0)
            
            if include_comments:
                comment = self.db.query(WorkComment).filter(
                    WorkComment.session_id == session.id
                ).first()
                ws.cell(row=row, column=9, value=comment.comment if comment else "")
            
            row += 1
        
        # Totals
        total_sessions = len(sessions)
        total_work = sum(s.total_work_time for s in sessions) / 3600
        total_breaks = sum(s.total_break_time for s in sessions) / 3600
        total_late = sum(s.late_minutes for s in sessions if s.is_late)
        
        row += 1
        ws.cell(row=row, column=1, value="ИТОГО:").font = Font(bold=True)
        ws.cell(row=row, column=2, value=f"{total_sessions} сессий")
        ws.cell(row=row, column=6, value=round(total_work, 2))
        ws.cell(row=row, column=7, value=round(total_breaks, 2))
        ws.cell(row=row, column=8, value=total_late)
        
        # Auto-width
        self._auto_width(ws)
        
        # Save to BytesIO
        output = BytesIO()
        wb.save(output)
        output.seek(0)
        return output
    
    def generate_employee_report(
        self,
        user_id: int,
        date_from: date,
        date_to: date,
        include_comments: bool = True
    ) -> BytesIO:
        """Generate employee report"""
        wb = Workbook()
        ws = wb.active
        ws.title = "Отчёт по сотруднику"
        
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("User not found")
        
        # Header
        ws.cell(row=1, column=1, value=f"Отчёт: {user.name}").font = Font(bold=True, size=14)
        ws.cell(row=2, column=1, value=f"Период: {date_from} - {date_to}")
        
        # Table headers
        headers = [
            "Дата", "День", "Начало", "Конец", "Работа", "Перерывы",
            "Опоздание", "Принуд. завершение"
        ]
        if include_comments:
            headers.append("Комментарий")
        
        row = 4
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=row, column=col, value=header)
            cell.font = Font(bold=True)
            cell.fill = PatternFill(start_color="CCCCCC", end_color="CCCCCC", fill_type="solid")
        
        # Data
        sessions = self.db.query(WorkSession).filter(
            WorkSession.user_id == user.amocrm_user_id,
            WorkSession.start_time >= datetime.combine(date_from, datetime.min.time()),
            WorkSession.start_time <= datetime.combine(date_to, datetime.max.time())
        ).order_by(WorkSession.start_time).all()
        
        row = 5
        weekdays = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
        
        for session in sessions:
            ws.cell(row=row, column=1, value=session.start_time.strftime("%Y-%m-%d"))
            ws.cell(row=row, column=2, value=weekdays[session.start_time.weekday()])
            ws.cell(row=row, column=3, value=session.start_time.strftime("%H:%M"))
            ws.cell(row=row, column=4, value=session.end_time.strftime("%H:%M") if session.end_time else "-")
            ws.cell(row=row, column=5, value=self._format_time(session.total_work_time))
            ws.cell(row=row, column=6, value=self._format_time(session.total_break_time))
            ws.cell(row=row, column=7, value=f"{session.late_minutes} мин" if session.is_late else "-")
            ws.cell(row=row, column=8, value="Да" if session.forced_finish else "Нет")
            
            if include_comments:
                comment = self.db.query(WorkComment).filter(
                    WorkComment.session_id == session.id
                ).first()
                ws.cell(row=row, column=9, value=comment.comment if comment else "")
            
            row += 1
        
        # Totals
        total_work = sum(s.total_work_time for s in sessions)
        total_breaks = sum(s.total_break_time for s in sessions)
        late_count = sum(1 for s in sessions if s.is_late)
        
        row += 1
        ws.cell(row=row, column=1, value="ИТОГО:").font = Font(bold=True)
        ws.cell(row=row, column=2, value=f"{len(sessions)} дней")
        ws.cell(row=row, column=5, value=self._format_time(total_work))
        ws.cell(row=row, column=6, value=self._format_time(total_breaks))
        ws.cell(row=row, column=7, value=f"{late_count} опозданий")
        
        self._auto_width(ws)
        
        output = BytesIO()
        wb.save(output)
        output.seek(0)
        return output
    
    def generate_late_arrivals_report(
        self,
        date_from: date,
        date_to: date,
        department_ids: Optional[List[int]] = None
    ) -> BytesIO:
        """Generate late arrivals report"""
        wb = Workbook()
        ws = wb.active
        ws.title = "Опоздания"
        
        self._add_header(ws, "Отчёт по опозданиям", date_from, date_to)
        
        headers = [
            "Дата", "Сотрудник", "Подразделение", "Начало работы",
            "Опоздание (мин)", "Причина", "Комментарий РОП"
        ]
        
        row = 4
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=row, column=col, value=header)
            cell.font = Font(bold=True)
            cell.fill = PatternFill(start_color="FFCCCC", end_color="FFCCCC", fill_type="solid")
        
        query = self.db.query(WorkSession).join(User).join(Department).filter(
            WorkSession.is_late == True,
            WorkSession.start_time >= datetime.combine(date_from, datetime.min.time()),
            WorkSession.start_time <= datetime.combine(date_to, datetime.max.time())
        )
        
        if department_ids:
            query = query.filter(User.department_id.in_(department_ids))
        
        sessions = query.order_by(WorkSession.start_time.desc()).all()
        
        row = 5
        for session in sessions:
            ws.cell(row=row, column=1, value=session.start_time.strftime("%Y-%m-%d"))
            ws.cell(row=row, column=2, value=session.user.name)
            ws.cell(row=row, column=3, value=session.user.department.name if session.user.department else "N/A")
            ws.cell(row=row, column=4, value=session.start_time.strftime("%H:%M"))
            ws.cell(row=row, column=5, value=session.late_minutes)
            ws.cell(row=row, column=6, value=session.late_reason or "-")
            
            comment = self.db.query(WorkComment).filter(
                WorkComment.session_id == session.id
            ).first()
            ws.cell(row=row, column=7, value=comment.comment if comment else "")
            
            row += 1
        
        row += 1
        ws.cell(row=row, column=1, value="ИТОГО опозданий:").font = Font(bold=True)
        ws.cell(row=row, column=2, value=len(sessions))
        ws.cell(row=row, column=5, value=sum(s.late_minutes for s in sessions))
        
        self._auto_width(ws)
        
        output = BytesIO()
        wb.save(output)
        output.seek(0)
        return output
    
    def _add_header(self, ws, title: str, date_from: date, date_to: date):
        """Add report header"""
        ws.cell(row=1, column=1, value=title).font = Font(bold=True, size=14)
        ws.cell(row=2, column=1, value=f"Период: {date_from} - {date_to}")
        ws.cell(row=3, column=1, value=f"Сформирован: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    
    def _format_time(self, seconds: int) -> str:
        """Format seconds to HH:MM"""
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}:{minutes:02d}"
    
    def _auto_width(self, ws):
        """Auto-adjust column widths"""
        for column in ws.columns:
            max_length = 0
            column_letter = get_column_letter(column[0].column)
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(cell.value)
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            ws.column_dimensions[column_letter].width = adjusted_width

```

---

### Team Service

**File:** `backend/app/services/team_service.py` (415 lines)

```python
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from app.models.work_session import WorkSession, WorkStatus


class TeamService:
    """Service for team monitoring"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_team_status(self, department: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get current status of all team members"""
        query = self.db.query(WorkSession)\
            .filter(WorkSession.current_status != WorkStatus.FINISHED)
        
        if department:
            query = query.filter(WorkSession.department == department)
        
        sessions = query.all()
        
        # Get unique users from all sessions (including finished today)
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        all_users_query = self.db.query(
            WorkSession.user_id,
            WorkSession.user_name,
            WorkSession.department
        ).filter(WorkSession.start_time >= today_start)
        
        if department:
            all_users_query = all_users_query.filter(WorkSession.department == department)
        
        all_users = all_users_query.distinct().all()
        
        # Build status list
        status_list = []
        active_users = {s.user_id: s for s in sessions}
        
        for user_id, user_name, dept in all_users:
            if user_id in active_users:
                session = active_users[user_id]
                status_list.append({
                    "user_id": session.user_id,
                    "user_name": session.user_name,
                    "department": session.department,
                    "current_status": session.current_status.value,
                    "session_id": session.id,
                    "session_start": session.start_time,
                    "work_time": session.total_work_time,
                    "break_time": session.total_break_time,
                    "break_count": session.break_count,
                    "last_activity": session.updated_at
                })
            else:
                status_list.append({
                    "user_id": user_id,
                    "user_name": user_name,
                    "department": dept,
                    "current_status": "not_working",
                    "session_id": None,
                    "session_start": None,
                    "work_time": 0,
                    "break_time": 0,
                    "break_count": 0,
                    "last_activity": None
                })
        
        return status_list
    
    def get_team_stats(
        self, 
        department: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get team statistics"""
        if not date_from:
            date_from = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        
        if not date_to:
            date_to = datetime.utcnow()
        
        query = self.db.query(WorkSession)\
            .filter(
                and_(
                    WorkSession.start_time >= date_from,
                    WorkSession.start_time <= date_to
                )
            )
        
        if department:
            query = query.filter(WorkSession.department == department)
        
        sessions = query.all()
        
        # Calculate stats
        total_members = len(set(s.user_id for s in sessions))
        working = sum(1 for s in sessions if s.current_status == WorkStatus.WORKING)
        on_break = sum(1 for s in sessions if s.current_status == WorkStatus.BREAK)
        not_working = total_members - working - on_break
        
        total_work_time = sum(s.total_work_time for s in sessions)
        total_break_time = sum(s.total_break_time for s in sessions)
        
        avg_work_time = total_work_time / total_members if total_members > 0 else 0
        avg_break_time = total_break_time / total_members if total_members > 0 else 0
        
        return {
            "total_members": total_members,
            "working": working,
            "on_break": on_break,
            "not_working": not_working,
            "total_work_time": total_work_time,
            "total_break_time": total_break_time,
            "avg_work_time": round(avg_work_time, 2),
            "avg_break_time": round(avg_break_time, 2)
        }
    
    def get_team_activity(
        self, 
        date: datetime,
        department: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get team activity for specific date"""
        date_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        date_end = date_start + timedelta(days=1)
        
        query = self.db.query(WorkSession)\
            .filter(
                and_(
                    WorkSession.start_time >= date_start,
                    WorkSession.start_time < date_end
                )
            )
        
        if department:
            query = query.filter(WorkSession.department == department)
        
        sessions = query.all()
        
        activity = []
        for session in sessions:
            activity.append({
                "user_id": session.user_id,
                "user_name": session.user_name,
                "department": session.department,
                "start_time": session.start_time,
                "end_time": session.end_time,
                "status": session.current_status.value,
                "work_time": session.total_work_time,
                "break_time": session.total_break_time,
                "break_count": session.break_count
            })
        
        return activity
    
    def get_team_status_with_rbac(
        self,
        accessible_dept_ids: Optional[List[int]],
        department_id: Optional[int] = None,
        status_filter: Optional[str] = None,
        online_only: bool = False,
        search: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get team status with RBAC filtering.
        accessible_dept_ids: None = all (Admin), List = allowed (ROP), [] = none
        """
        from app.models.user import User
        from app.models.crm_activity import CRMActivity
        
        # Base query for users
        query = self.db.query(User).filter(User.is_active == True)
        
        # RBAC filtering by department
        if accessible_dept_ids is not None:  # Not Admin
            if not accessible_dept_ids:  # Empty list - no access
                return []
            query = query.filter(User.department_id.in_(accessible_dept_ids))
        
        # Filter by specific department
        if department_id:
            query = query.filter(User.department_id == department_id)
        
        # Search by name
        if search:
            query = query.filter(User.name.ilike(f"%{search}%"))
        
        users = query.all()
        
        # Get active sessions
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        sessions_query = self.db.query(WorkSession).filter(
            WorkSession.start_time >= today_start,
            WorkSession.current_status != WorkStatus.FINISHED
        )
        sessions = {s.user_id: s for s in sessions_query.all()}
        
        # Get last CRM activity (last 5 minutes for online check)
        five_min_ago = datetime.utcnow() - timedelta(minutes=5)
        
        status_list = []
        for user in users:
            session = sessions.get(user.amocrm_user_id)
            
            # Get last activity from CRM
            last_crm_activity = self.db.query(CRMActivity).filter(
                CRMActivity.user_id == user.amocrm_user_id
            ).order_by(CRMActivity.created_at.desc()).first()
            
            last_activity_time = last_crm_activity.created_at if last_crm_activity else None
            is_online = last_activity_time and last_activity_time >= five_min_ago
            
            # Online filter
            if online_only and not is_online:
                continue
            
            if session:
                current_status = session.current_status.value
                
                # Status filter
                if status_filter and current_status != status_filter:
                    continue
                
                status_list.append({
                    "user_id": user.amocrm_user_id,
                    "user_name": user.name,
                    "department": user.department.name if user.department else None,
                    "department_id": user.department_id,
                    "current_status": current_status,
                    "session_id": session.id,
                    "session_start": session.start_time,
                    "work_time": session.total_work_time,
                    "break_time": session.total_break_time,
                    "break_count": session.break_count,
                    "last_activity": session.updated_at,
                    "last_activity_time": last_activity_time,
                    "is_online": is_online
                })
            else:
                current_status = "not_working"
                
                # Status filter
                if status_filter and current_status != status_filter:
                    continue
                
                status_list.append({
                    "user_id": user.amocrm_user_id,
                    "user_name": user.name,
                    "department": user.department.name if user.department else None,
                    "department_id": user.department_id,
                    "current_status": current_status,
                    "session_id": None,
                    "session_start": None,
                    "work_time": 0,
                    "break_time": 0,
                    "break_count": 0,
                    "last_activity": None,
                    "last_activity_time": last_activity_time,
                    "is_online": is_online
                })
        
        return status_list
    
    def get_user_timeline(self, user_id: int, date: Optional[str] = None) -> Dict[str, Any]:
        """Get user CRM activity timeline for specific date"""
        from app.models.crm_activity import CRMActivity
        from app.models.user import User
        
        if not date:
            target_date = datetime.utcnow().date()
        else:
            target_date = datetime.strptime(date, "%Y-%m-%d").date()
        
        date_start = datetime.combine(target_date, datetime.min.time())
        date_end = datetime.combine(target_date, datetime.max.time())
        
        # Get user
        user = self.db.query(User).filter(User.amocrm_user_id == user_id).first()
        user_name = user.name if user else f"User {user_id}"
        
        # Get CRM activities
        activities = self.db.query(CRMActivity).filter(
            CRMActivity.user_id == user_id,
            CRMActivity.created_at >= date_start,
            CRMActivity.created_at <= date_end
        ).all()
        
        # Create 15-minute intervals (96 intervals per day)
        intervals = []
        current_time = date_start
        
        for _ in range(96):  # 24 * 4 = 96 intervals
            interval_end = current_time + timedelta(minutes=15)
            
            # Count activities in this interval
            interval_activities = [a for a in activities 
                                 if current_time <= a.created_at < interval_end]
            
            deals = sum(1 for a in interval_activities if a.entity_type == 'lead')
            contacts = sum(1 for a in interval_activities if a.entity_type == 'contact')
            companies = sum(1 for a in interval_activities if a.entity_type == 'company')
            tasks = sum(1 for a in interval_activities if a.entity_type == 'task')
            calls = sum(1 for a in interval_activities if a.activity_type == 'call')
            
            intervals.append({
                "start_time": current_time.strftime("%H:%M"),
                "end_time": interval_end.strftime("%H:%M"),
                "deals": deals,
                "contacts": contacts,
                "companies": companies,
                "tasks": tasks,
                "calls": calls,
                "total_events": len(interval_activities)
            })
            
            current_time = interval_end
        
        return {
            "user_id": user_id,
            "user_name": user_name,
            "date": target_date.strftime("%Y-%m-%d"),
            "intervals": intervals,
            "total_events": len(activities)
        }
    
    def get_user_timeline_history(self, user_id: int) -> Dict[str, Any]:
        """Get user CRM activity history for last 7 days"""
        from app.models.crm_activity import CRMActivity
        from app.models.user import User
        
        user = self.db.query(User).filter(User.amocrm_user_id == user_id).first()
        user_name = user.name if user else f"User {user_id}"
        
        days = []
        for i in range(7):
            target_date = datetime.utcnow().date() - timedelta(days=i)
            date_start = datetime.combine(target_date, datetime.min.time())
            date_end = datetime.combine(target_date, datetime.max.time())
            
            activities = self.db.query(CRMActivity).filter(
                CRMActivity.user_id == user_id,
                CRMActivity.created_at >= date_start,
                CRMActivity.created_at <= date_end
            ).all()
            
            deals = sum(1 for a in activities if a.entity_type == 'lead')
            contacts = sum(1 for a in activities if a.entity_type == 'contact')
            companies = sum(1 for a in activities if a.entity_type == 'company')
            tasks = sum(1 for a in activities if a.entity_type == 'task')
            calls = sum(1 for a in activities if a.activity_type == 'call')
            
            days.append({
                "date": target_date.strftime("%Y-%m-%d"),
                "total_events": len(activities),
                "deals": deals,
                "contacts": contacts,
                "companies": companies,
                "tasks": tasks,
                "calls": calls
            })
        
        return {
            "user_id": user_id,
            "user_name": user_name,
            "days": days
        }
    
    def force_finish_session(
        self,
        target_user_id: int,
        admin_id: int,
        admin_name: str,
        reason: str
    ) -> Dict[str, Any]:
        """Force finish work session for employee"""
        # Find active session
        session = self.db.query(WorkSession).filter(
            WorkSession.user_id == target_user_id,
            WorkSession.current_status != WorkStatus.FINISHED
        ).first()
        
        if not session:
            return {
                "success": False,
                "message": "No active session found",
                "session_id": 0
            }
        
        # Calculate total time
        now = datetime.utcnow()
        if session.current_status == WorkStatus.WORKING:
            session.total_work_time += int((now - session.last_status_change).total_seconds())
        elif session.current_status == WorkStatus.BREAK:
            session.total_break_time += int((now - session.last_status_change).total_seconds())
        
        # Update session
        session.current_status = WorkStatus.FINISHED
        session.end_time = now
        session.forced_finish = True
        session.forced_finish_by = admin_id
        session.forced_finish_reason = reason
        session.updated_at = now
        
        self.db.commit()
        self.db.refresh(session)
        
        return {
            "success": True,
            "message": f"Session force finished by {admin_name}",
            "session_id": session.id
        }

```

---

### Department Schema

**File:** `backend/app/schemas/department.py` (45 lines)

```python
"""Department schemas"""
from pydantic import BaseModel, Field
from datetime import time, datetime
from typing import Optional


class DepartmentBase(BaseModel):
    """Base department schema"""
    name: str = Field(..., min_length=1, max_length=255)
    work_start_time: time = Field(..., description="Work start time, e.g. 09:00:00")
    work_end_time: time = Field(..., description="Work end time, e.g. 18:00:00")


class DepartmentCreate(DepartmentBase):
    """Schema for creating department"""
    pass


class DepartmentUpdate(BaseModel):
    """Schema for updating department schedule"""
    work_start_time: Optional[time] = None
    work_end_time: Optional[time] = None
    is_active: Optional[bool] = None


class DepartmentResponse(DepartmentBase):
    """Department response schema"""
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class DepartmentScheduleResponse(BaseModel):
    """Department schedule response"""
    department_id: int
    department_name: str
    work_start_time: time
    work_end_time: time
    
    class Config:
        from_attributes = True

```

---

### Excel Schema

**File:** `backend/app/schemas/excel.py` (21 lines)

```python
"""Excel export schemas"""
from pydantic import BaseModel
from datetime import date
from typing import Optional, List


class ExcelExportRequest(BaseModel):
    """Request for Excel export"""
    date_from: date
    date_to: date
    department_ids: Optional[List[int]] = None  # None = all accessible
    user_ids: Optional[List[int]] = None  # None = all
    late_only: bool = False
    include_comments: bool = True


class ExcelExportResponse(BaseModel):
    """Response with Excel file"""
    filename: str
    content_type: str = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    # File будет возвращен через StreamingResponse

```

---

### KPI Schema

**File:** `backend/app/schemas/kpi.py` (53 lines)

```python
"""KPI and charts schemas"""
from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional


class KPIMetrics(BaseModel):
    """User or department KPI metrics"""
    # Time metrics
    hours_today: float
    hours_week: float
    hours_month: float
    avg_hours_per_day: float
    
    # Performance
    late_count_week: int
    late_count_month: int
    completion_percentage: float  # % of norm
    
    # Status
    current_status: str  # working, break, finished, offline
    is_online: bool
    
    # Optional for department
    total_employees: Optional[int] = None
    online_now: Optional[int] = None


class ChartDataPoint(BaseModel):
    """Single data point for chart"""
    date: str  # YYYY-MM-DD
    value: float
    label: Optional[str] = None


class ChartData(BaseModel):
    """Chart data with multiple series"""
    labels: List[str]  # X-axis labels (dates)
    datasets: List[dict]  # Chart.js format datasets
    

class DashboardSettingsUpdate(BaseModel):
    """Update dashboard settings"""
    show_online: Optional[bool] = None
    show_late_arrivals: Optional[bool] = None
    show_team_stats: Optional[bool] = None
    default_period: Optional[str] = None  # week, month
    chart_type: Optional[str] = None  # line, bar


class KPIPeriodRequest(BaseModel):
    """Request for KPI with period"""
    days: int = 7  # 7 or 30

```

---

### Team Schema

**File:** `backend/app/schemas/team.py` (55 lines)

```python
"""Team schemas"""
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Dict, List


class ForceFinishRequest(BaseModel):
    """Request to force finish work session"""
    reason: str


class ForceFinishResponse(BaseModel):
    """Response for force finish"""
    success: bool
    message: str
    session_id: int


class ActivityTimelineInterval(BaseModel):
    """Activity timeline interval (15 minutes)"""
    start_time: str  # "09:00"
    end_time: str    # "09:15"
    deals: int = 0
    contacts: int = 0
    companies: int = 0
    tasks: int = 0
    calls: int = 0
    total_events: int = 0


class ActivityTimelineResponse(BaseModel):
    """Activity timeline for a day"""
    user_id: int
    user_name: str
    date: str  # "2026-08-11"
    intervals: List[ActivityTimelineInterval]
    total_events: int
    
    
class ActivityHistoryDay(BaseModel):
    """Activity history for one day"""
    date: str
    total_events: int
    deals: int
    contacts: int
    companies: int
    tasks: int
    calls: int


class ActivityHistoryResponse(BaseModel):
    """Activity history for last 7 days"""
    user_id: int
    user_name: str
    days: List[ActivityHistoryDay]

```

---

### Login Page

**File:** `frontend/index.html` (487 lines)

```html
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Табель учёта рабочего времени</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }

        .container {
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            padding: 40px;
            max-width: 600px;
            width: 100%;
        }

        h1 {
            color: #333;
            text-align: center;
            margin-bottom: 10px;
            font-size: 28px;
        }

        .subtitle {
            text-align: center;
            color: #666;
            margin-bottom: 30px;
            font-size: 14px;
        }

        .status {
            background: #f8f9fa;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 30px;
            text-align: center;
        }

        .status-badge {
            display: inline-block;
            padding: 8px 20px;
            border-radius: 20px;
            font-weight: 600;
            font-size: 14px;
            margin-bottom: 10px;
        }

        .status-badge.working {
            background: #d4edda;
            color: #155724;
        }

        .status-badge.paused {
            background: #fff3cd;
            color: #856404;
        }

        .status-badge.stopped {
            background: #f8d7da;
            color: #721c24;
        }

        .timer {
            font-size: 48px;
            font-weight: 700;
            color: #667eea;
            margin: 20px 0;
        }

        .user-info {
            background: #e3f2fd;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 20px;
        }

        .user-info input {
            width: 100%;
            padding: 12px;
            border: 2px solid #90caf9;
            border-radius: 8px;
            font-size: 16px;
            transition: border-color 0.3s;
        }

        .user-info input:focus {
            outline: none;
            border-color: #667eea;
        }

        .button-group {
            display: grid;
            gap: 15px;
            margin-bottom: 20px;
        }

        button {
            padding: 16px 32px;
            border: none;
            border-radius: 12px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
            color: white;
        }

        button:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(0,0,0,0.2);
        }

        button:active {
            transform: translateY(0);
        }

        button:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            transform: none !important;
        }

        .btn-start {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }

        .btn-pause {
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        }

        .btn-end {
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
        }

        .stats {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 15px;
            margin-top: 30px;
        }

        .stat-card {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 12px;
            text-align: center;
        }

        .stat-value {
            font-size: 32px;
            font-weight: 700;
            color: #667eea;
            margin-bottom: 5px;
        }

        .stat-label {
            color: #666;
            font-size: 14px;
        }

        .api-status {
            padding: 10px;
            border-radius: 8px;
            text-align: center;
            margin-bottom: 20px;
            font-size: 14px;
        }

        .api-status.online {
            background: #d4edda;
            color: #155724;
        }

        .api-status.offline {
            background: #f8d7da;
            color: #721c24;
        }

        .alert {
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            display: none;
        }

        .alert.success {
            background: #d4edda;
            color: #155724;
            display: block;
        }

        .alert.error {
            background: #f8d7da;
            color: #721c24;
            display: block;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>⏰ Табель учёта времени</h1>
        <p class="subtitle">Система контроля рабочего времени</p>

        <div id="apiStatus" class="api-status offline">
            🔴 Проверка связи с сервером...
        </div>

        <div id="alert" class="alert"></div>

        <div class="user-info">
            <input type="text" id="userName" placeholder="Введите ваше имя" value="Иван Иванов">
        </div>

        <div class="status">
            <div id="statusBadge" class="status-badge stopped">
                ⭕ Смена не начата
            </div>
            <div id="timer" class="timer">00:00:00</div>
            <div id="sessionInfo" style="color: #666; font-size: 14px;">
                Нажмите "Начать смену" для старта
            </div>
        </div>

        <div class="button-group">
            <button id="btnStart" class="btn-start" onclick="startSession()">
                ▶️ Начать смену
            </button>
            <button id="btnPause" class="btn-pause" onclick="toggleBreak()" disabled>
                ⏸️ Перерыв
            </button>
            <button id="btnEnd" class="btn-end" onclick="endSession()" disabled>
                ⏹️ Завершить смену
            </button>
        </div>

        <div class="stats">
            <div class="stat-card">
                <div id="workTime" class="stat-value">0:00</div>
                <div class="stat-label">Время работы</div>
            </div>
            <div class="stat-card">
                <div id="breakTime" class="stat-value">0:00</div>
                <div class="stat-label">Время перерыва</div>
            </div>
        </div>
    </div>

    <script>
        const API_URL = 'https://storage-turkey-multitask.ngrok-free.dev/api/v1';
        
        let sessionData = {
            sessionId: null,
            startTime: null,
            isWorking: false,
            isPaused: false,
            workSeconds: 0,
            breakSeconds: 0
        };

        let timerInterval = null;

        // Проверка API при загрузке
        async function checkAPI() {
            try {
                const response = await fetch(`${API_URL.replace('/api/v1', '')}/health`);
                if (response.ok) {
                    document.getElementById('apiStatus').className = 'api-status online';
                    document.getElementById('apiStatus').textContent = '✅ Сервер подключен';
                    return true;
                }
            } catch (error) {
                console.error('API недоступен:', error);
            }
            document.getElementById('apiStatus').className = 'api-status offline';
            document.getElementById('apiStatus').textContent = '🔴 Сервер недоступен';
            return false;
        }

        // Начать смену
        async function startSession() {
            const userName = document.getElementById('userName').value.trim();
            if (!userName) {
                showAlert('Введите ваше имя', 'error');
                return;
            }

            try {
                const response = await fetch(`${API_URL}/sessions/start`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        account_id: 'demo_account',
                        user_id: Math.floor(Math.random() * 10000),
                        user_name: userName
                    })
                });

                if (response.ok) {
                    const data = await response.json();
                    sessionData.sessionId = data.session_id;
                    sessionData.startTime = new Date();
                    sessionData.isWorking = true;
                    sessionData.isPaused = false;
                    
                    updateUI();
                    startTimer();
                    showAlert('Смена началась!', 'success');
                } else {
                    showAlert('Ошибка при запуске смены', 'error');
                }
            } catch (error) {
                console.error('Ошибка:', error);
                showAlert('Не удалось связаться с сервером', 'error');
            }
        }

        // Перерыв
        async function toggleBreak() {
            if (!sessionData.sessionId) return;

            try {
                const endpoint = sessionData.isPaused ? 'resume' : 'break';
                const response = await fetch(`${API_URL}/sessions/${endpoint}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        session_id: sessionData.sessionId,
                        account_id: 'demo_account'
                    })
                });

                if (response.ok) {
                    sessionData.isPaused = !sessionData.isPaused;
                    updateUI();
                    showAlert(sessionData.isPaused ? 'Перерыв начат' : 'Работа возобновлена', 'success');
                }
            } catch (error) {
                console.error('Ошибка:', error);
                showAlert('Ошибка при изменении статуса', 'error');
            }
        }

        // Завершить смену
        async function endSession() {
            if (!sessionData.sessionId) return;

            try {
                const response = await fetch(`${API_URL}/sessions/end`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        session_id: sessionData.sessionId,
                        account_id: 'demo_account'
                    })
                });

                if (response.ok) {
                    stopTimer();
                    const workHours = Math.floor(sessionData.workSeconds / 3600);
                    const workMinutes = Math.floor((sessionData.workSeconds % 3600) / 60);
                    showAlert(`Смена завершена! Отработано: ${workHours}ч ${workMinutes}м`, 'success');
                    
                    // Сброс
                    sessionData = {
                        sessionId: null,
                        startTime: null,
                        isWorking: false,
                        isPaused: false,
                        workSeconds: 0,
                        breakSeconds: 0
                    };
                    updateUI();
                }
            } catch (error) {
                console.error('Ошибка:', error);
                showAlert('Ошибка при завершении смены', 'error');
            }
        }

        // Таймер
        function startTimer() {
            if (timerInterval) clearInterval(timerInterval);
            
            timerInterval = setInterval(() => {
                if (sessionData.isPaused) {
                    sessionData.breakSeconds++;
                } else {
                    sessionData.workSeconds++;
                }
                updateTimer();
            }, 1000);
        }

        function stopTimer() {
            if (timerInterval) {
                clearInterval(timerInterval);
                timerInterval = null;
            }
        }

        function updateTimer() {
            const totalSeconds = sessionData.workSeconds + sessionData.breakSeconds;
            const hours = Math.floor(totalSeconds / 3600);
            const minutes = Math.floor((totalSeconds % 3600) / 60);
            const seconds = totalSeconds % 60;
            
            document.getElementById('timer').textContent = 
                `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
            
            // Обновить статистику
            const workHours = Math.floor(sessionData.workSeconds / 3600);
            const workMinutes = Math.floor((sessionData.workSeconds % 3600) / 60);
            document.getElementById('workTime').textContent = `${workHours}:${String(workMinutes).padStart(2, '0')}`;
            
            const breakHours = Math.floor(sessionData.breakSeconds / 3600);
            const breakMinutes = Math.floor((sessionData.breakSeconds % 3600) / 60);
            document.getElementById('breakTime').textContent = `${breakHours}:${String(breakMinutes).padStart(2, '0')}`;
        }

        // Обновить интерфейс
        function updateUI() {
            const btnStart = document.getElementById('btnStart');
            const btnPause = document.getElementById('btnPause');
            const btnEnd = document.getElementById('btnEnd');
            const badge = document.getElementById('statusBadge');
            const info = document.getElementById('sessionInfo');

            if (sessionData.isWorking) {
                btnStart.disabled = true;
                btnPause.disabled = false;
                btnEnd.disabled = false;
                
                if (sessionData.isPaused) {
                    badge.className = 'status-badge paused';
                    badge.textContent = '⏸️ Перерыв';
                    btnPause.textContent = '▶️ Продолжить';
                    info.textContent = 'Вы на перерыве';
                } else {
                    badge.className = 'status-badge working';
                    badge.textContent = '✅ Работаю';
                    btnPause.textContent = '⏸️ Перерыв';
                    info.textContent = 'Смена идёт';
                }
            } else {
                btnStart.disabled = false;
                btnPause.disabled = true;
                btnEnd.disabled = true;
                badge.className = 'status-badge stopped';
                badge.textContent = '⭕ Смена не начата';
                info.textContent = 'Нажмите "Начать смену" для старта';
            }
        }

        // Показать уведомление
        function showAlert(message, type) {
            const alert = document.getElementById('alert');
            alert.textContent = message;
            alert.className = `alert ${type}`;
            setTimeout(() => {
                alert.className = 'alert';
            }, 3000);
        }

        // Инициализация при загрузке
        window.addEventListener('load', async () => {
            await checkAPI();
            updateUI();
        });
    </script>
</body>
</html>

```

---

### Personal Dashboard

**File:** `frontend/personal.html` (182 lines)

```html
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Табель - Личный кабинет</title>
    <link rel="stylesheet" href="assets/css/personal.css">
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
</head>
<body>
    <!-- OVERLAY: Before Workday -->
    <div id="overlay-before-workday" class="overlay hidden">
        <div class="overlay-content">
            <div class="icon-large">🌅</div>
            <h1>Начните рабочий день</h1>
            <div class="current-time" id="current-time"></div>
            <div class="schedule-info" id="schedule-info">
                <p>Начало рабочего дня: <span id="work-start-time">09:00</span></p>
            </div>
            <button class="btn btn-primary btn-large" id="btn-start-work">
                НАЧАТЬ РАБОТУ
            </button>
        </div>
    </div>

    <!-- OVERLAY: Late -->
    <div id="overlay-late" class="overlay hidden">
        <div class="overlay-content">
            <div class="icon-large warning">⚠️</div>
            <h1>Вы опоздали</h1>
            <p class="late-info">Опоздание: <span id="late-minutes">0</span> минут</p>
            <div class="form-group">
                <label for="late-reason">Причина опоздания *</label>
                <textarea 
                    id="late-reason" 
                    placeholder="Укажите причину опоздания (минимум 10 символов)" 
                    rows="4"
                    required
                ></textarea>
                <div class="char-counter">
                    <span id="reason-length">0</span> / 10 символов
                </div>
            </div>
            <button class="btn btn-primary btn-large" id="btn-start-late">
                НАЧАТЬ РАБОТУ
            </button>
        </div>
    </div>

    <!-- OVERLAY: Working (Compact Widget) -->
    <div id="overlay-working" class="widget-compact hidden">
        <div class="widget-header">
            <span class="status-badge status-working">Работаю</span>
            <span class="timer" id="work-timer">00:00:00</span>
        </div>
        <div class="widget-body">
            <div class="crm-status" id="crm-status">
                <span class="indicator"></span>
                <span class="label">CRM активность</span>
            </div>
            <div class="widget-actions">
                <button class="btn btn-sm btn-warning" id="btn-take-break">
                    ☕ Перерыв
                </button>
                <button class="btn btn-sm btn-danger" id="btn-finish-work">
                    🏁 Завершить
                </button>
            </div>
        </div>
    </div>

    <!-- OVERLAY: Break -->
    <div id="overlay-break" class="overlay hidden">
        <div class="overlay-content">
            <div class="icon-large">☕</div>
            <h1>Перерыв</h1>
            <div class="timer-large" id="break-timer">00:00:00</div>
            <div class="break-warning" id="break-warning">
                <p>⚠️ Перерыв более 15 минут</p>
            </div>
            <div class="break-stats">
                <p>Перерывов сегодня: <span id="break-count">0</span></p>
                <p>Общее время перерывов: <span id="total-break-time">00:00</span></p>
            </div>
            <button class="btn btn-success btn-large" id="btn-resume-work">
                ВЕРНУТЬСЯ К РАБОТЕ
            </button>
        </div>
    </div>

    <!-- OVERLAY: Finished -->
    <div id="overlay-finished" class="overlay hidden">
        <div class="overlay-content">
            <div class="icon-large success">✅</div>
            <h1>Рабочий день завершён</h1>
            <div class="day-summary">
                <div class="summary-item">
                    <div class="label">Отработано времени</div>
                    <div class="value" id="total-work-time">0:00</div>
                </div>
                <div class="summary-item">
                    <div class="label">Перерывов</div>
                    <div class="value" id="total-breaks">0</div>
                </div>
                <div class="summary-item">
                    <div class="label">Время перерывов</div>
                    <div class="value" id="summary-break-time">0:00</div>
                </div>
            </div>
            <button class="btn btn-primary btn-large hidden" id="btn-restart-work">
                НАЧАТЬ ЗАНОВО
            </button>
            <p class="info-text">Хорошего отдыха! До завтра! 👋</p>
        </div>
    </div>

    <!-- Main Dashboard (visible when working) -->
    <div id="dashboard" class="dashboard hidden">
        <header class="dashboard-header">
            <h1>Мой табель</h1>
            <div class="user-info" id="user-info">
                <span id="user-name">Загрузка...</span>
            </div>
        </header>

        <main class="dashboard-main">
            <!-- KPI Cards -->
            <section class="kpi-section">
                <h2>Мои показатели</h2>
                <div class="kpi-grid">
                    <div class="kpi-card">
                        <div class="kpi-label">Сегодня</div>
                        <div class="kpi-value" id="kpi-today">0.0ч</div>
                        <div class="kpi-sublabel">из 8ч нормы</div>
                    </div>
                    <div class="kpi-card">
                        <div class="kpi-label">Эта неделя</div>
                        <div class="kpi-value" id="kpi-week">0.0ч</div>
                    </div>
                    <div class="kpi-card">
                        <div class="kpi-label">Этот месяц</div>
                        <div class="kpi-value" id="kpi-month">0.0ч</div>
                    </div>
                    <div class="kpi-card">
                        <div class="kpi-label">Опоздания</div>
                        <div class="kpi-value warning" id="kpi-late">0</div>
                        <div class="kpi-sublabel">за неделю</div>
                    </div>
                    <div class="kpi-card">
                        <div class="kpi-label">Средний день</div>
                        <div class="kpi-value" id="kpi-avg">0.0ч</div>
                    </div>
                    <div class="kpi-card">
                        <div class="kpi-label">Выполнение</div>
                        <div class="kpi-value" id="kpi-completion">0%</div>
                        <div class="kpi-sublabel">от нормы</div>
                    </div>
                </div>
            </section>

            <!-- Chart Section -->
            <section class="chart-section">
                <div class="section-header">
                    <h2>График работы</h2>
                    <div class="period-switcher">
                        <button class="btn btn-sm active" data-period="7">7 дней</button>
                        <button class="btn btn-sm" data-period="30">30 дней</button>
                    </div>
                </div>
                <div class="chart-container">
                    <canvas id="work-chart"></canvas>
                </div>
            </section>
        </main>
    </div>

    <!-- Scripts -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.js"></script>
    <script src="assets/js/api-client.js"></script>
    <script src="assets/js/personal.js"></script>
</body>
</html>

```

---

### ROP Dashboard

**File:** `frontend/rop.html` (147 lines)

```html
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Табель - Командный мониторинг (РОП)</title>
    <link rel="stylesheet" href="assets/css/rop.css">
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
</head>
<body>
    <!-- Header -->
    <header class="header">
        <h1>📊 Командный мониторинг</h1>
        <div class="header-info">
            <span id="department-name">Загрузка...</span>
            <span id="last-update">Обновлено: --:--</span>
        </div>
    </header>

    <!-- Filters -->
    <section class="filters">
        <div class="filter-buttons">
            <button class="filter-btn active" data-filter="all">Все <span class="count" id="count-all">0</span></button>
            <button class="filter-btn" data-filter="working">Работают <span class="count" id="count-working">0</span></button>
            <button class="filter-btn" data-filter="break">На перерыве <span class="count" id="count-break">0</span></button>
            <button class="filter-btn" data-filter="finished">Завершили <span class="count" id="count-finished">0</span></button>
            <button class="filter-btn" data-filter="not-started">Не начали <span class="count" id="count-not-started">0</span></button>
        </div>
        <div class="search-box">
            <input type="text" id="search-input" placeholder="🔍 Поиск по имени...">
        </div>
    </section>

    <!-- Stats Summary -->
    <section class="stats-summary">
        <div class="stat-card">
            <div class="stat-label">Онлайн</div>
            <div class="stat-value" id="stat-online">0</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Средние часы</div>
            <div class="stat-value" id="stat-avg-hours">0.0ч</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Опоздали сегодня</div>
            <div class="stat-value warning" id="stat-late">0</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Выполнение нормы</div>
            <div class="stat-value" id="stat-completion">0%</div>
        </div>
    </section>

    <!-- Employees Grid -->
    <section class="employees-section">
        <h2>Сотрудники</h2>
        <div class="employees-grid" id="employees-grid">
            <!-- Employee cards will be inserted here -->
        </div>
    </section>

    <!-- KPI Section -->
    <section class="kpi-section">
        <h2>KPI подразделения</h2>
        <div class="kpi-grid">
            <div class="kpi-card">
                <div class="kpi-label">Часы сегодня</div>
                <div class="kpi-value" id="kpi-today">0.0ч</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Часы неделя</div>
                <div class="kpi-value" id="kpi-week">0.0ч</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Часы месяц</div>
                <div class="kpi-value" id="kpi-month">0.0ч</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Опозданий неделя</div>
                <div class="kpi-value warning" id="kpi-late">0</div>
            </div>
        </div>
    </section>

    <!-- Chart Section -->
    <section class="chart-section">
        <div class="section-header">
            <h2>График работы команды</h2>
            <div class="period-switcher">
                <button class="btn btn-sm active" data-period="7">7 дней</button>
                <button class="btn btn-sm" data-period="30">30 дней</button>
            </div>
        </div>
        <div class="chart-container">
            <canvas id="team-chart"></canvas>
        </div>
    </section>

    <!-- Timeline Modal -->
    <div id="timeline-modal" class="modal hidden">
        <div class="modal-content">
            <div class="modal-header">
                <h2>Timeline: <span id="timeline-user-name"></span></h2>
                <button class="close-btn" id="close-timeline">&times;</button>
            </div>
            <div class="modal-body">
                <div class="timeline-info">
                    <p>Дата: <span id="timeline-date"></span></p>
                    <p>Всего: <span id="timeline-total">0ч</span></p>
                    <p>Перерывов: <span id="timeline-breaks">0</span></p>
                </div>
                <div class="timeline-grid" id="timeline-grid">
                    <!-- 96 intervals will be generated here -->
                </div>
                <div class="timeline-legend">
                    <div class="legend-item"><span class="legend-color working"></span> Работа</div>
                    <div class="legend-item"><span class="legend-color break"></span> Перерыв</div>
                    <div class="legend-item"><span class="legend-color inactive"></span> Не начато</div>
                    <div class="legend-item"><span class="legend-dot"></span> CRM активность</div>
                </div>
            </div>
        </div>
    </div>

    <!-- Force Finish Confirmation Modal -->
    <div id="confirm-modal" class="modal hidden">
        <div class="modal-content small">
            <div class="modal-header">
                <h2>Подтверждение</h2>
                <button class="close-btn" id="close-confirm">&times;</button>
            </div>
            <div class="modal-body">
                <p>Завершить рабочий день для <strong id="confirm-user-name"></strong>?</p>
                <div class="modal-actions">
                    <button class="btn btn-danger" id="confirm-force-finish">Да, завершить</button>
                    <button class="btn btn-secondary" id="cancel-force-finish">Отмена</button>
                </div>
            </div>
        </div>
    </div>

    <!-- Scripts -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.js"></script>
    <script src="assets/js/api-client.js"></script>
    <script src="assets/js/rop.js"></script>
</body>
</html>

```

---

### Admin Panel

**File:** `frontend/admin.html` (248 lines)

```html
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Табель - Администрирование</title>
    <link rel="stylesheet" href="assets/css/admin.css">
</head>
<body>
    <!-- Header -->
    <header class="header">
        <h1>⚙️ Администрирование системы</h1>
        <div class="header-info">
            <span id="admin-name">Админ</span>
        </div>
    </header>

    <!-- Tabs Navigation -->
    <nav class="tabs">
        <button class="tab-btn active" data-tab="departments">📋 Подразделения</button>
        <button class="tab-btn" data-tab="users">👥 Пользователи</button>
        <button class="tab-btn" data-tab="settings">⚙️ Настройки</button>
        <button class="tab-btn" data-tab="stats">📊 Статистика</button>
    </nav>

    <!-- Tab: Departments -->
    <section class="tab-content active" id="tab-departments">
        <div class="section-header">
            <h2>Подразделения</h2>
            <button class="btn btn-primary" id="add-department">+ Добавить подразделение</button>
        </div>
        <div class="table-container">
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Название</th>
                        <th>РОП</th>
                        <th>Сотрудников</th>
                        <th>График</th>
                        <th>Действия</th>
                    </tr>
                </thead>
                <tbody id="departments-tbody">
                    <tr><td colspan="5" style="text-align:center;">Загрузка...</td></tr>
                </tbody>
            </table>
        </div>
    </section>

    <!-- Tab: Users -->
    <section class="tab-content" id="tab-users">
        <div class="section-header">
            <h2>Пользователи</h2>
            <div class="filters">
                <select id="filter-department">
                    <option value="">Все подразделения</option>
                </select>
                <select id="filter-role">
                    <option value="">Все роли</option>
                    <option value="admin">Admin</option>
                    <option value="rop">ROP</option>
                    <option value="employee">Employee</option>
                </select>
                <input type="text" id="search-user" placeholder="🔍 Поиск...">
            </div>
        </div>
        <div class="table-container">
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Имя</th>
                        <th>Подразделение</th>
                        <th>Роль</th>
                        <th>Статус</th>
                        <th>Действия</th>
                    </tr>
                </thead>
                <tbody id="users-tbody">
                    <tr><td colspan="5" style="text-align:center;">Загрузка...</td></tr>
                </tbody>
            </table>
        </div>
    </section>

    <!-- Tab: Settings -->
    <section class="tab-content" id="tab-settings">
        <div class="section-header">
            <h2>Настройки системы</h2>
        </div>
        <div class="settings-container">
            <div class="settings-group">
                <h3>График работы</h3>
                <div class="form-group">
                    <label>Начало рабочего дня:</label>
                    <input type="time" id="setting-work-start" value="09:00">
                </div>
                <div class="form-group">
                    <label>Опоздание после:</label>
                    <input type="time" id="setting-late-after" value="09:15">
                </div>
                <div class="form-group">
                    <label>Норма часов в день:</label>
                    <input type="number" id="setting-norm-hours" value="8" min="1" max="12">
                </div>
                <div class="form-group">
                    <label>Макс. время перерыва (мин):</label>
                    <input type="number" id="setting-max-break" value="60" min="15" max="120">
                </div>
                <div class="form-group">
                    <label>Предупреждение перерыва (мин):</label>
                    <input type="number" id="setting-break-warn" value="15" min="5" max="30">
                </div>
            </div>
            <div class="settings-group">
                <h3>Уведомления</h3>
                <div class="form-group">
                    <label>
                        <input type="checkbox" id="setting-email-notify">
                        Email уведомления РОПам
                    </label>
                </div>
                <div class="form-group">
                    <label>Частота отчётов:</label>
                    <select id="setting-report-freq">
                        <option value="daily">Ежедневно</option>
                        <option value="weekly" selected>Еженедельно</option>
                        <option value="monthly">Ежемесячно</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Webhook URL:</label>
                    <input type="url" id="setting-webhook" placeholder="https://...">
                </div>
            </div>
            <button class="btn btn-primary btn-large" id="save-settings">💾 Сохранить настройки</button>
        </div>
    </section>

    <!-- Tab: Stats -->
    <section class="tab-content" id="tab-stats">
        <div class="section-header">
            <h2>Глобальная статистика</h2>
        </div>
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-label">Всего пользователей</div>
                <div class="stat-value" id="stat-total-users">0</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Всего подразделений</div>
                <div class="stat-value" id="stat-total-depts">0</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Активных сессий</div>
                <div class="stat-value" id="stat-active-sessions">0</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Средние часы</div>
                <div class="stat-value" id="stat-avg-hours">0.0ч</div>
            </div>
        </div>
        <div class="top-departments">
            <h3>Топ 5 подразделений по часам</h3>
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Место</th>
                        <th>Подразделение</th>
                        <th>Средние часы</th>
                        <th>Процент нормы</th>
                    </tr>
                </thead>
                <tbody id="top-departments-tbody">
                    <tr><td colspan="4" style="text-align:center;">Загрузка...</td></tr>
                </tbody>
            </table>
        </div>
    </section>

    <!-- Modal: Add/Edit Department -->
    <div id="department-modal" class="modal hidden">
        <div class="modal-content small">
            <div class="modal-header">
                <h2 id="department-modal-title">Добавить подразделение</h2>
                <button class="close-btn" id="close-department-modal">&times;</button>
            </div>
            <div class="modal-body">
                <form id="department-form">
                    <div class="form-group">
                        <label>Название:</label>
                        <input type="text" id="department-name" required>
                    </div>
                    <div class="form-group">
                        <label>РОП:</label>
                        <select id="department-rop">
                            <option value="">Не назначен</option>
                        </select>
                    </div>
                    <div class="modal-actions">
                        <button type="submit" class="btn btn-primary">Сохранить</button>
                        <button type="button" class="btn btn-secondary" id="cancel-department">Отмена</button>
                    </div>
                </form>
            </div>
        </div>
    </div>

    <!-- Modal: Edit User -->
    <div id="user-modal" class="modal hidden">
        <div class="modal-content small">
            <div class="modal-header">
                <h2>Редактировать пользователя</h2>
                <button class="close-btn" id="close-user-modal">&times;</button>
            </div>
            <div class="modal-body">
                <form id="user-form">
                    <div class="form-group">
                        <label>Имя:</label>
                        <input type="text" id="user-name" readonly>
                    </div>
                    <div class="form-group">
                        <label>Роль:</label>
                        <select id="user-role" required>
                            <option value="employee">Employee</option>
                            <option value="rop">ROP</option>
                            <option value="admin">Admin</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Подразделение:</label>
                        <select id="user-department" required>
                        </select>
                    </div>
                    <div class="modal-actions">
                        <button type="submit" class="btn btn-primary">Сохранить</button>
                        <button type="button" class="btn btn-secondary" id="cancel-user">Отмена</button>
                    </div>
                </form>
            </div>
        </div>
    </div>

    <!-- Scripts -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.js"></script>
    <script src="assets/js/api-client.js"></script>
    <script src="assets/js/admin.js"></script>
</body>
</html>

```

---

### Reports Page

**File:** `frontend/reports.html` (172 lines)

```html
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Табель - Отчёты</title>
    <link rel="stylesheet" href="assets/css/reports.css">
</head>
<body>
    <!-- Header -->
    <header class="header">
        <h1>📊 Генерация отчётов</h1>
        <div class="header-info">
            <span id="user-name">Пользователь</span>
        </div>
    </header>

    <!-- Filters Section -->
    <section class="filters-section">
        <div class="filters-container">
            <!-- Period Section -->
            <div class="filter-group">
                <h3>Период</h3>
                <div class="quick-select">
                    <button class="quick-btn" data-period="today">Сегодня</button>
                    <button class="quick-btn" data-period="week">Неделя</button>
                    <button class="quick-btn" data-period="month">Месяц</button>
                </div>
                <div class="date-inputs">
                    <div class="date-group">
                        <label>От:</label>
                        <input type="date" id="date-from">
                    </div>
                    <div class="date-group">
                        <label>До:</label>
                        <input type="date" id="date-to">
                    </div>
                </div>
            </div>

            <!-- Report Type -->
            <div class="filter-group">
                <h3>Тип отчёта</h3>
                <select id="report-type" class="form-select">
                    <option value="summary">Сводный отчёт</option>
                    <option value="detailed">Детальный отчёт</option>
                    <option value="timeline">Таймлайн отчёт</option>
                </select>
            </div>

            <!-- Department -->
            <div class="filter-group">
                <h3>Подразделение</h3>
                <select id="department" class="form-select">
                    <option value="">Все подразделения</option>
                </select>
            </div>

            <!-- User (for detailed/timeline) -->
            <div class="filter-group" id="user-filter-group">
                <h3>Пользователь</h3>
                <select id="user" class="form-select">
                    <option value="">Выберите пользователя</option>
                </select>
            </div>

            <!-- Actions -->
            <div class="filter-group actions-group">
                <button class="btn btn-primary" id="generate-report">
                    📋 Сгенерировать отчёт
                </button>
                <button class="btn btn-success" id="export-excel" disabled>
                    📥 Экспорт в Excel
                </button>
            </div>
        </div>
    </section>

    <!-- Preview Section -->
    <section class="preview-section">
        <div class="preview-header">
            <h2>Предпросмотр отчёта</h2>
            <span id="report-info"></span>
        </div>

        <!-- Loading State -->
        <div class="loading-state hidden" id="loading">
            <div class="spinner"></div>
            <p>Генерация отчёта...</p>
        </div>

        <!-- Empty State -->
        <div class="empty-state" id="empty-state">
            <div class="empty-icon">📊</div>
            <h3>Выберите параметры отчёта</h3>
            <p>Укажите период и тип отчёта, затем нажмите "Сгенерировать отчёт"</p>
        </div>

        <!-- Preview Table: Summary -->
        <div class="preview-content hidden" id="preview-summary">
            <div class="table-container">
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Сотрудник</th>
                            <th>Подразделение</th>
                            <th>Всего часов</th>
                            <th>Среднее/день</th>
                            <th>Опозданий</th>
                            <th>Перерывов</th>
                            <th>Выполнение нормы</th>
                        </tr>
                    </thead>
                    <tbody id="summary-tbody">
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Preview Table: Detailed -->
        <div class="preview-content hidden" id="preview-detailed">
            <div class="table-container">
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Дата</th>
                            <th>Начало</th>
                            <th>Конец</th>
                            <th>Всего часов</th>
                            <th>Перерывов</th>
                            <th>Опоздание</th>
                            <th>CRM активность</th>
                        </tr>
                    </thead>
                    <tbody id="detailed-tbody">
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Preview Table: Timeline -->
        <div class="preview-content hidden" id="preview-timeline">
            <div class="timeline-info">
                <p><strong>Пользователь:</strong> <span id="timeline-user"></span></p>
                <p><strong>Дата:</strong> <span id="timeline-date"></span></p>
            </div>
            <div class="timeline-grid" id="timeline-grid">
                <!-- Timeline будет сгенерирован в JS -->
            </div>
            <div class="timeline-legend">
                <div class="legend-item">
                    <span class="legend-color work"></span>
                    <span>Работа</span>
                </div>
                <div class="legend-item">
                    <span class="legend-color break"></span>
                    <span>Перерыв</span>
                </div>
                <div class="legend-item">
                    <span class="legend-color idle"></span>
                    <span>Не начато</span>
                </div>
            </div>
        </div>
    </section>

    <!-- Scripts -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.js"></script>
    <script src="assets/js/api-client.js"></script>
    <script src="assets/js/reports.js"></script>
</body>
</html>

```

---

### API Client

**File:** `frontend/assets/js/api-client.js` (165 lines)

```javascript
/**
 * API Client for Timesheet Backend
 */

class APIClient {
    constructor(baseURL = 'http://localhost:8000') {
        this.baseURL = baseURL;
        this.userId = null;
        this.accountId = null;
    }

    /**
     * Initialize with amoCRM credentials
     */
    init(userId, accountId) {
        this.userId = userId;
        this.accountId = accountId;
    }

    /**
     * Get headers for API requests
     */
    getHeaders() {
        return {
            'Content-Type': 'application/json',
            'X-User-Id': this.userId || '0',
            'X-Account-Id': this.accountId || '0'
        };
    }

    /**
     * Make API request
     */
    async request(endpoint, options = {}) {
        const url = `${this.baseURL}${endpoint}`;
        const config = {
            ...options,
            headers: {
                ...this.getHeaders(),
                ...options.headers
            }
        };

        try {
            const response = await fetch(url, config);
            
            if (!response.ok) {
                const error = await response.json().catch(() => ({}));
                throw new Error(error.detail || `HTTP ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error('API Error:', error);
            throw error;
        }
    }

    // ===== Session Endpoints =====

    /**
     * Get current work session
     */
    async getCurrentSession() {
        return this.request('/api/v1/sessions/current');
    }

    /**
     * Start work session
     */
    async startWork(lateReason = null) {
        return this.request('/api/v1/sessions/start', {
            method: 'POST',
            body: JSON.stringify({ late_reason: lateReason })
        });
    }

    /**
     * Take a break
     */
    async takeBreak() {
        return this.request('/api/v1/sessions/break', {
            method: 'POST'
        });
    }

    /**
     * Resume work from break
     */
    async resumeWork() {
        return this.request('/api/v1/sessions/resume', {
            method: 'POST'
        });
    }

    /**
     * Finish work day
     */
    async finishWork() {
        return this.request('/api/v1/sessions/finish', {
            method: 'POST'
        });
    }

    /**
     * Update activity
     */
    async updateActivity() {
        return this.request('/api/v1/activity/update', {
            method: 'POST'
        });
    }

    // ===== KPI Endpoints =====

    /**
     * Get my KPI metrics
     */
    async getMyKPI() {
        return this.request('/api/v1/kpi/my');
    }

    /**
     * Get chart data
     */
    async getMyChart(days = 7) {
        return this.request(`/api/v1/kpi/chart/my?days=${days}`);
    }

    /**
     * Get dashboard settings
     */
    async getDashboardSettings() {
        return this.request('/api/v1/kpi/dashboard/settings');
    }

    /**
     * Update dashboard settings
     */
    async updateDashboardSettings(settings) {
        return this.request('/api/v1/kpi/dashboard/settings', {
            method: 'PUT',
            body: JSON.stringify(settings)
        });
    }

    // ===== Settings Endpoints =====

    /**
     * Get user settings
     */
    async getSettings() {
        return this.request('/api/v1/settings');
    }

    /**
     * Get schedule
     */
    async getSchedule() {
        return this.request('/api/v1/settings/schedule');
    }
}

// Create global instance
window.api = new APIClient();

```

---

### Personal Dashboard JS

**File:** `frontend/assets/js/personal.js` (464 lines)

```javascript
/**
 * Personal Dashboard Logic
 */

class PersonalDashboard {
    constructor() {
        this.currentState = null;
        this.session = null;
        this.timers = {};
        this.chart = null;
        this.chartPeriod = 7;
        
        this.init();
    }

    /**
     * Initialize dashboard
     */
    async init() {
        // Init API with test credentials (replace with amoCRM data)
        api.init(1, 1);
        
        // Setup event listeners
        this.setupEventListeners();
        
        // Load initial state
        await this.loadCurrentState();
        
        // Start activity tracking
        this.startActivityTracking();
    }

    /**
     * Setup all event listeners
     */
    setupEventListeners() {
        // Start work buttons
        document.getElementById('btn-start-work')?.addEventListener('click', () => this.handleStartWork());
        document.getElementById('btn-start-late')?.addEventListener('click', () => this.handleStartLate());
        
        // Working state buttons
        document.getElementById('btn-take-break')?.addEventListener('click', () => this.handleTakeBreak());
        document.getElementById('btn-finish-work')?.addEventListener('click', () => this.handleFinishWork());
        
        // Break buttons
        document.getElementById('btn-resume-work')?.addEventListener('click', () => this.handleResumeWork());
        
        // Restart button
        document.getElementById('btn-restart-work')?.addEventListener('click', () => this.handleRestartWork());
        
        // Late reason textarea
        document.getElementById('late-reason')?.addEventListener('input', (e) => {
            document.getElementById('reason-length').textContent = e.target.value.length;
        });
        
        // Chart period switcher
        document.querySelectorAll('.period-switcher .btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const period = parseInt(e.target.dataset.period);
                this.switchChartPeriod(period);
            });
        });
        
        // Update time every second
        setInterval(() => this.updateCurrentTime(), 1000);
    }

    /**
     * Load current work session state
     */
    async loadCurrentState() {
        try {
            this.session = await api.getCurrentSession();
            
            if (!this.session) {
                this.showState('before-workday');
            } else {
                const status = this.session.status;
                
                if (status === 'working') {
                    this.showState('working');
                    this.startWorkTimer();
                } else if (status === 'break') {
                    this.showState('break');
                    this.startBreakTimer();
                } else if (status === 'finished') {
                    this.showState('finished');
                    this.showDaySummary();
                }
            }
            
            // Load KPI and chart if working
            if (this.session && this.session.status !== 'finished') {
                await this.loadKPI();
                await this.loadChart();
            }
        } catch (error) {
            console.error('Failed to load state:', error);
            this.showState('before-workday');
        }
    }

    /**
     * Show specific state overlay
     */
    showState(state) {
        this.currentState = state;
        
        // Hide all overlays
        document.querySelectorAll('.overlay, .widget-compact, .dashboard').forEach(el => {
            el.classList.add('hidden');
        });
        
        // Show requested state
        if (state === 'before-workday') {
            document.getElementById('overlay-before-workday').classList.remove('hidden');
        } else if (state === 'late') {
            document.getElementById('overlay-late').classList.remove('hidden');
        } else if (state === 'working') {
            document.getElementById('overlay-working').classList.remove('hidden');
            document.getElementById('dashboard').classList.remove('hidden');
        } else if (state === 'break') {
            document.getElementById('overlay-break').classList.remove('hidden');
        } else if (state === 'finished') {
            document.getElementById('overlay-finished').classList.remove('hidden');
        }
    }

    /**
     * Handle start work (normal)
     */
    async handleStartWork() {
        try {
            this.session = await api.startWork();
            
            if (this.session.is_late) {
                // Show late overlay
                const minutes = Math.floor(this.session.late_minutes);
                document.getElementById('late-minutes').textContent = minutes;
                this.showState('late');
            } else {
                this.showState('working');
                this.startWorkTimer();
                await this.loadKPI();
                await this.loadChart();
            }
        } catch (error) {
            alert('Ошибка при начале работы: ' + error.message);
        }
    }

    /**
     * Handle start work (late)
     */
    async handleStartLate() {
        const reason = document.getElementById('late-reason').value.trim();
        
        if (reason.length < 10) {
            alert('Причина опоздания должна быть не менее 10 символов');
            return;
        }
        
        try {
            this.session = await api.startWork(reason);
            this.showState('working');
            this.startWorkTimer();
            await this.loadKPI();
            await this.loadChart();
        } catch (error) {
            alert('Ошибка при начале работы: ' + error.message);
        }
    }

    /**
     * Handle take break
     */
    async handleTakeBreak() {
        try {
            this.session = await api.takeBreak();
            this.stopWorkTimer();
            this.showState('break');
            this.startBreakTimer();
        } catch (error) {
            alert('Ошибка при переходе на перерыв: ' + error.message);
        }
    }

    /**
     * Handle resume work
     */
    async handleResumeWork() {
        try {
            this.session = await api.resumeWork();
            this.stopBreakTimer();
            this.showState('working');
            this.startWorkTimer();
            await this.loadKPI();
        } catch (error) {
            alert('Ошибка при возврате к работе: ' + error.message);
        }
    }

    /**
     * Handle finish work
     */
    async handleFinishWork() {
        if (!confirm('Завершить рабочий день?')) return;
        
        try {
            this.session = await api.finishWork();
            this.stopWorkTimer();
            this.showState('finished');
            this.showDaySummary();
        } catch (error) {
            alert('Ошибка при завершении работы: ' + error.message);
        }
    }

    /**
     * Handle restart work
     */
    async handleRestartWork() {
        await this.handleStartWork();
    }

    /**
     * Start work timer
     */
    startWorkTimer() {
        this.stopWorkTimer();
        
        const updateTimer = () => {
            if (!this.session) return;
            
            const start = new Date(this.session.start_time);
            const now = new Date();
            const diff = Math.floor((now - start) / 1000);
            
            document.getElementById('work-timer').textContent = this.formatTime(diff);
        };
        
        updateTimer();
        this.timers.work = setInterval(updateTimer, 1000);
    }

    /**
     * Stop work timer
     */
    stopWorkTimer() {
        if (this.timers.work) {
            clearInterval(this.timers.work);
            delete this.timers.work;
        }
    }

    /**
     * Start break timer
     */
    startBreakTimer() {
        this.stopBreakTimer();
        
        const updateTimer = () => {
            if (!this.session || !this.session.current_break_start) return;
            
            const start = new Date(this.session.current_break_start);
            const now = new Date();
            const diff = Math.floor((now - start) / 1000);
            
            document.getElementById('break-timer').textContent = this.formatTime(diff);
            
            // Show warning if > 15 min
            const warning = document.getElementById('break-warning');
            if (diff > 900) {
                warning.classList.remove('hidden');
            } else {
                warning.classList.add('hidden');
            }
        };
        
        updateTimer();
        this.timers.break = setInterval(updateTimer, 1000);
        
        // Update break stats
        this.updateBreakStats();
    }

    /**
     * Stop break timer
     */
    stopBreakTimer() {
        if (this.timers.break) {
            clearInterval(this.timers.break);
            delete this.timers.break;
        }
    }

    /**
     * Update break statistics
     */
    updateBreakStats() {
        if (!this.session) return;
        
        document.getElementById('break-count').textContent = this.session.break_count || 0;
        document.getElementById('total-break-time').textContent = 
            this.formatTime(this.session.total_break_time || 0);
    }

    /**
     * Show day summary
     */
    showDaySummary() {
        if (!this.session) return;
        
        document.getElementById('total-work-time').textContent = 
            this.formatHours(this.session.total_work_time / 3600);
        document.getElementById('total-breaks').textContent = this.session.break_count || 0;
        document.getElementById('summary-break-time').textContent = 
            this.formatTime(this.session.total_break_time || 0);
        
        // Show restart button if before 23:00
        const hour = new Date().getHours();
        if (hour < 23) {
            document.getElementById('btn-restart-work').classList.remove('hidden');
        }
    }

    /**
     * Load KPI metrics
     */
    async loadKPI() {
        try {
            const kpi = await api.getMyKPI();
            
            document.getElementById('kpi-today').textContent = kpi.hours_today.toFixed(1) + 'ч';
            document.getElementById('kpi-week').textContent = kpi.hours_week.toFixed(1) + 'ч';
            document.getElementById('kpi-month').textContent = kpi.hours_month.toFixed(1) + 'ч';
            document.getElementById('kpi-late').textContent = kpi.late_count_week;
            document.getElementById('kpi-avg').textContent = kpi.avg_hours_per_day.toFixed(1) + 'ч';
            document.getElementById('kpi-completion').textContent = kpi.completion_percentage.toFixed(0) + '%';
        } catch (error) {
            console.error('Failed to load KPI:', error);
        }
    }

    /**
     * Load chart
     */
    async loadChart() {
        try {
            const data = await api.getMyChart(this.chartPeriod);
            this.renderChart(data);
        } catch (error) {
            console.error('Failed to load chart:', error);
        }
    }

    /**
     * Render Chart.js chart
     */
    renderChart(data) {
        const ctx = document.getElementById('work-chart');
        if (!ctx) return;
        
        if (this.chart) {
            this.chart.destroy();
        }
        
        this.chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.labels,
                datasets: data.datasets
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Часы'
                        }
                    }
                }
            }
        });
    }

    /**
     * Switch chart period
     */
    async switchChartPeriod(days) {
        this.chartPeriod = days;
        
        // Update button states
        document.querySelectorAll('.period-switcher .btn').forEach(btn => {
            if (parseInt(btn.dataset.period) === days) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });
        
        await this.loadChart();
    }

    /**
     * Start activity tracking
     */
    startActivityTracking() {
        // Update activity every 30 seconds
        setInterval(async () => {
            if (this.session && this.session.status === 'working') {
                try {
                    await api.updateActivity();
                } catch (error) {
                    console.error('Activity update failed:', error);
                }
            }
        }, 30000);
    }

    /**
     * Update current time display
     */
    updateCurrentTime() {
        const now = new Date();
        const timeStr = now.toLocaleTimeString('ru-RU');
        const el = document.getElementById('current-time');
        if (el) {
            el.textContent = timeStr;
        }
    }

    /**
     * Format seconds to HH:MM:SS
     */
    formatTime(seconds) {
        const h = Math.floor(seconds / 3600);
        const m = Math.floor((seconds % 3600) / 60);
        const s = seconds % 60;
        return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
    }

    /**
     * Format hours to H:MM
     */
    formatHours(hours) {
        const h = Math.floor(hours);
        const m = Math.floor((hours % 1) * 60);
        return `${h}:${m.toString().padStart(2, '0')}`;
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.dashboard = new PersonalDashboard();
});

```

---

### ROP Dashboard JS

**File:** `frontend/assets/js/rop.js` (313 lines)

```javascript
/**
 * ROP Dashboard Logic
 */

class ROPDashboard {
    constructor() {
        this.employees = [];
        this.currentFilter = 'all';
        this.searchQuery = '';
        this.chart = null;
        this.chartPeriod = 7;
        this.selectedUserId = null;
        
        this.init();
    }

    async init() {
        // Init API with ROP credentials
        api.init(1, 1); // Replace with real ROP user
        
        this.setupEventListeners();
        await this.loadData();
        this.startAutoRefresh();
    }

    setupEventListeners() {
        // Filter buttons
        document.querySelectorAll('.filter-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                this.currentFilter = e.currentTarget.dataset.filter;
                document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
                e.currentTarget.classList.add('active');
                this.renderEmployees();
            });
        });

        // Search
        document.getElementById('search-input').addEventListener('input', (e) => {
            this.searchQuery = e.target.value.toLowerCase();
            this.renderEmployees();
        });

        // Chart period
        document.querySelectorAll('.period-switcher .btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                this.chartPeriod = parseInt(e.target.dataset.period);
                document.querySelectorAll('.period-switcher .btn').forEach(b => b.classList.remove('active'));
                e.target.classList.add('active');
                this.loadChart();
            });
        });

        // Modal close
        document.getElementById('close-timeline').addEventListener('click', () => {
            document.getElementById('timeline-modal').classList.add('hidden');
        });
        document.getElementById('close-confirm').addEventListener('click', () => {
            document.getElementById('confirm-modal').classList.add('hidden');
        });
        document.getElementById('cancel-force-finish').addEventListener('click', () => {
            document.getElementById('confirm-modal').classList.add('hidden');
        });
        document.getElementById('confirm-force-finish').addEventListener('click', () => {
            this.forceFinishUser(this.selectedUserId);
        });
    }

    async loadData() {
        try {
            await Promise.all([
                this.loadEmployees(),
                this.loadStats(),
                this.loadKPI(),
                this.loadChart()
            ]);
            this.updateLastUpdate();
        } catch (error) {
            console.error('Failed to load data:', error);
        }
    }

    async loadEmployees() {
        try {
            const data = await api.request('/api/v1/team/status');
            this.employees = data.employees || [];
            this.renderEmployees();
            this.updateCounts();
        } catch (error) {
            console.error('Failed to load employees:', error);
        }
    }

    async loadStats() {
        try {
            const stats = await api.request('/api/v1/team/stats');
            document.getElementById('stat-online').textContent = stats.online_count || 0;
            document.getElementById('stat-avg-hours').textContent = (stats.avg_hours || 0).toFixed(1) + 'ч';
            document.getElementById('stat-late').textContent = stats.late_today || 0;
            document.getElementById('stat-completion').textContent = (stats.completion_percent || 0).toFixed(0) + '%';
        } catch (error) {
            console.error('Failed to load stats:', error);
        }
    }

    async loadKPI() {
        try {
            const kpi = await api.request('/api/v1/kpi/department/1'); // Replace with real dept ID
            document.getElementById('kpi-today').textContent = (kpi.hours_today || 0).toFixed(1) + 'ч';
            document.getElementById('kpi-week').textContent = (kpi.hours_week || 0).toFixed(1) + 'ч';
            document.getElementById('kpi-month').textContent = (kpi.hours_month || 0).toFixed(1) + 'ч';
            document.getElementById('kpi-late').textContent = kpi.late_count_week || 0;
        } catch (error) {
            console.error('Failed to load KPI:', error);
        }
    }

    async loadChart() {
        try {
            const data = await api.request(`/api/v1/kpi/chart/department/1?days=${this.chartPeriod}`);
            this.renderChart(data);
        } catch (error) {
            console.error('Failed to load chart:', error);
        }
    }

    renderEmployees() {
        const grid = document.getElementById('employees-grid');
        const filtered = this.getFilteredEmployees();
        
        if (filtered.length === 0) {
            grid.innerHTML = '<p style="grid-column: 1/-1; text-align:center; color: #999;">Нет сотрудников</p>';
            return;
        }

        grid.innerHTML = filtered.map(emp => this.createEmployeeCard(emp)).join('');
        
        // Attach event listeners
        filtered.forEach(emp => {
            document.querySelector(`[data-timeline="${emp.id}"]`)?.addEventListener('click', () => {
                this.showTimeline(emp.id, emp.name);
            });
            document.querySelector(`[data-force-finish="${emp.id}"]`)?.addEventListener('click', () => {
                this.confirmForceFinish(emp.id, emp.name);
            });
        });
    }

    createEmployeeCard(emp) {
        const status = emp.status || 'not-started';
        const statusText = {
            'working': 'Работает',
            'break': 'Перерыв',
            'finished': 'Завершил',
            'not-started': 'Не начал'
        }[status] || 'Неизвестно';

        return `
            <div class="employee-card status-${status}">
                <div class="employee-header">
                    <div class="employee-name">👤 ${emp.name}</div>
                    <div class="status-indicator ${status}">${statusText}</div>
                </div>
                <div class="employee-info">
                    <p>⏱️ ${emp.work_time || '0:00'}</p>
                    <p>📊 Сегодня: ${(emp.hours_today || 0).toFixed(1)}ч / 8ч</p>
                    ${emp.is_late ? '<p style="color: #D0021B;">⚠️ Опоздал</p>' : ''}
                </div>
                <div class="employee-actions">
                    <button class="btn btn-sm btn-primary" data-timeline="${emp.id}">Timeline</button>
                    ${status === 'working' || status === 'break' ? 
                        `<button class="btn btn-sm btn-danger" data-force-finish="${emp.id}">Force Finish</button>` : ''}
                </div>
            </div>
        `;
    }

    getFilteredEmployees() {
        return this.employees.filter(emp => {
            // Filter by status
            if (this.currentFilter !== 'all' && emp.status !== this.currentFilter) {
                return false;
            }
            
            // Filter by search
            if (this.searchQuery && !emp.name.toLowerCase().includes(this.searchQuery)) {
                return false;
            }
            
            return true;
        });
    }

    updateCounts() {
        const counts = {
            all: this.employees.length,
            working: this.employees.filter(e => e.status === 'working').length,
            break: this.employees.filter(e => e.status === 'break').length,
            finished: this.employees.filter(e => e.status === 'finished').length,
            'not-started': this.employees.filter(e => e.status === 'not-started').length
        };

        Object.entries(counts).forEach(([key, value]) => {
            const el = document.getElementById(`count-${key}`);
            if (el) el.textContent = value;
        });
    }

    async showTimeline(userId, userName) {
        this.selectedUserId = userId;
        document.getElementById('timeline-user-name').textContent = userName;
        document.getElementById('timeline-date').textContent = new Date().toLocaleDateString('ru-RU');
        
        try {
            const data = await api.request(`/api/v1/team/timeline/${userId}`);
            this.renderTimeline(data);
            document.getElementById('timeline-modal').classList.remove('hidden');
        } catch (error) {
            alert('Ошибка загрузки timeline: ' + error.message);
        }
    }

    renderTimeline(data) {
        const grid = document.getElementById('timeline-grid');
        const intervals = data.intervals || [];
        
        // Create 96 cells (24 hours * 4 intervals per hour)
        grid.innerHTML = Array.from({length: 96}, (_, i) => {
            const interval = intervals[i] || {status: 'inactive', has_activity: false};
            const classes = ['timeline-cell', interval.status];
            if (interval.has_activity) classes.push('has-activity');
            
            return `<div class="${classes.join(' ')}" title="${this.getIntervalTime(i)}"></div>`;
        }).join('');

        document.getElementById('timeline-total').textContent = (data.total_hours || 0).toFixed(1) + 'ч';
        document.getElementById('timeline-breaks').textContent = data.break_count || 0;
    }

    getIntervalTime(index) {
        const hour = Math.floor(index / 4);
        const minute = (index % 4) * 15;
        return `${hour.toString().padStart(2, '0')}:${minute.toString().padStart(2, '0')}`;
    }

    confirmForceFinish(userId, userName) {
        this.selectedUserId = userId;
        document.getElementById('confirm-user-name').textContent = userName;
        document.getElementById('confirm-modal').classList.remove('hidden');
    }

    async forceFinishUser(userId) {
        try {
            await api.request(`/api/v1/team/force-finish/${userId}`, {method: 'POST'});
            document.getElementById('confirm-modal').classList.add('hidden');
            await this.loadEmployees();
            alert('Рабочий день завершён');
        } catch (error) {
            alert('Ошибка: ' + error.message);
        }
    }

    renderChart(data) {
        const ctx = document.getElementById('team-chart');
        if (!ctx) return;
        
        if (this.chart) {
            this.chart.destroy();
        }
        
        this.chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.labels || [],
                datasets: data.datasets || []
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: true
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Часы'
                        }
                    }
                }
            }
        });
    }

    updateLastUpdate() {
        const now = new Date();
        document.getElementById('last-update').textContent = 
            `Обновлено: ${now.toLocaleTimeString('ru-RU')}`;
    }

    startAutoRefresh() {
        setInterval(() => {
            this.loadData();
        }, 30000); // Refresh every 30 seconds
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.ropDashboard = new ROPDashboard();
});

```

---

### Admin Panel JS

**File:** `frontend/assets/js/admin.js` (381 lines)

```javascript
/**
 * Admin Dashboard Logic
 */

class AdminDashboard {
    constructor() {
        this.departments = [];
        this.users = [];
        this.currentTab = 'departments';
        this.currentDepartmentId = null;
        this.currentUserId = null;
        
        this.init();
    }

    async init() {
        api.init(1, 1); // Admin user
        
        this.setupEventListeners();
        await this.loadData();
    }

    setupEventListeners() {
        // Tabs
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                this.switchTab(e.target.dataset.tab);
            });
        });

        // Departments
        document.getElementById('add-department').addEventListener('click', () => this.showDepartmentModal());
        document.getElementById('department-form').addEventListener('submit', (e) => this.saveDepartment(e));
        document.getElementById('close-department-modal').addEventListener('click', () => this.hideDepartmentModal());
        document.getElementById('cancel-department').addEventListener('click', () => this.hideDepartmentModal());

        // Users
        document.getElementById('filter-department').addEventListener('change', () => this.renderUsers());
        document.getElementById('filter-role').addEventListener('change', () => this.renderUsers());
        document.getElementById('search-user').addEventListener('input', () => this.renderUsers());
        document.getElementById('user-form').addEventListener('submit', (e) => this.saveUser(e));
        document.getElementById('close-user-modal').addEventListener('click', () => this.hideUserModal());
        document.getElementById('cancel-user').addEventListener('click', () => this.hideUserModal());

        // Settings
        document.getElementById('save-settings').addEventListener('click', () => this.saveSettings());
    }

    switchTab(tabName) {
        this.currentTab = tabName;
        
        // Update buttons
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.classList.remove('active');
            if (btn.dataset.tab === tabName) btn.classList.add('active');
        });
        
        // Update content
        document.querySelectorAll('.tab-content').forEach(content => {
            content.classList.remove('active');
        });
        document.getElementById(`tab-${tabName}`).classList.add('active');
        
        // Load data if needed
        if (tabName === 'users') this.loadUsers();
        if (tabName === 'stats') this.loadStats();
    }

    async loadData() {
        await this.loadDepartments();
    }

    async loadDepartments() {
        try {
            const data = await api.request('/api/v1/departments');
            this.departments = data || [];
            this.renderDepartments();
            this.updateDepartmentSelects();
        } catch (error) {
            console.error('Failed to load departments:', error);
            // Mock data for MVP
            this.departments = [
                {id: 1, name: 'Отдел продаж', rop_name: 'Иванов И.И.', employee_count: 12, schedule: '09:00-18:00'},
                {id: 2, name: 'Отдел поддержки', rop_name: 'Петров П.П.', employee_count: 8, schedule: '09:00-18:00'},
                {id: 3, name: 'IT отдел', rop_name: 'Сидоров С.С.', employee_count: 5, schedule: '10:00-19:00'}
            ];
            this.renderDepartments();
            this.updateDepartmentSelects();
        }
    }

    renderDepartments() {
        const tbody = document.getElementById('departments-tbody');
        
        if (this.departments.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;">Нет подразделений</td></tr>';
            return;
        }

        tbody.innerHTML = this.departments.map(dept => `
            <tr>
                <td><strong>${dept.name}</strong></td>
                <td>${dept.rop_name || 'Не назначен'}</td>
                <td>${dept.employee_count || 0}</td>
                <td>${dept.schedule || '09:00-18:00'}</td>
                <td class="table-actions">
                    <button class="action-btn edit" onclick="adminDashboard.editDepartment(${dept.id})">✏️ Изменить</button>
                    <button class="action-btn delete" onclick="adminDashboard.deleteDepartment(${dept.id})">🗑️ Удалить</button>
                </td>
            </tr>
        `).join('');
    }

    showDepartmentModal(id = null) {
        this.currentDepartmentId = id;
        const modal = document.getElementById('department-modal');
        const title = document.getElementById('department-modal-title');
        
        if (id) {
            const dept = this.departments.find(d => d.id === id);
            if (dept) {
                title.textContent = 'Редактировать подразделение';
                document.getElementById('department-name').value = dept.name;
                document.getElementById('department-rop').value = dept.rop_id || '';
            }
        } else {
            title.textContent = 'Добавить подразделение';
            document.getElementById('department-form').reset();
        }
        
        modal.classList.remove('hidden');
    }

    hideDepartmentModal() {
        document.getElementById('department-modal').classList.add('hidden');
        this.currentDepartmentId = null;
    }

    async saveDepartment(e) {
        e.preventDefault();
        
        const name = document.getElementById('department-name').value;
        const ropId = document.getElementById('department-rop').value;
        
        try {
            if (this.currentDepartmentId) {
                await api.request(`/api/v1/departments/${this.currentDepartmentId}`, {
                    method: 'PUT',
                    body: {name, rop_id: ropId || null}
                });
            } else {
                await api.request('/api/v1/departments', {
                    method: 'POST',
                    body: {name, rop_id: ropId || null}
                });
            }
            
            this.hideDepartmentModal();
            await this.loadDepartments();
            alert('Подразделение сохранено');
        } catch (error) {
            alert('Ошибка: ' + error.message);
        }
    }

    editDepartment(id) {
        this.showDepartmentModal(id);
    }

    async deleteDepartment(id) {
        if (!confirm('Удалить подразделение?')) return;
        
        try {
            await api.request(`/api/v1/departments/${id}`, {method: 'DELETE'});
            await this.loadDepartments();
            alert('Подразделение удалено');
        } catch (error) {
            alert('Ошибка: ' + error.message);
        }
    }

    async loadUsers() {
        try {
            const data = await api.request('/api/v1/users');
            this.users = data || [];
            this.renderUsers();
        } catch (error) {
            console.error('Failed to load users:', error);
            // Mock data for MVP
            this.users = [
                {id: 1, name: 'Иванов Иван', department: 'Отдел продаж', department_id: 1, role: 'rop', status: 'Работает'},
                {id: 2, name: 'Петров Петр', department: 'Отдел продаж', department_id: 1, role: 'employee', status: 'Перерыв'},
                {id: 3, name: 'Сидоров Сергей', department: 'IT отдел', department_id: 3, role: 'rop', status: 'Работает'},
                {id: 4, name: 'Козлов Кирилл', department: 'Отдел поддержки', department_id: 2, role: 'employee', status: 'Не начал'},
                {id: 5, name: 'Админов Админ', department: 'IT отдел', department_id: 3, role: 'admin', status: 'Активен'}
            ];
            this.renderUsers();
        }
    }

    renderUsers() {
        const tbody = document.getElementById('users-tbody');
        const deptFilter = document.getElementById('filter-department').value;
        const roleFilter = document.getElementById('filter-role').value;
        const searchQuery = document.getElementById('search-user').value.toLowerCase();
        
        let filtered = this.users.filter(user => {
            if (deptFilter && user.department_id != deptFilter) return false;
            if (roleFilter && user.role !== roleFilter) return false;
            if (searchQuery && !user.name.toLowerCase().includes(searchQuery)) return false;
            return true;
        });
        
        if (filtered.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;">Нет пользователей</td></tr>';
            return;
        }

        tbody.innerHTML = filtered.map(user => `
            <tr>
                <td><strong>${user.name}</strong></td>
                <td>${user.department}</td>
                <td><span class="badge badge-${this.getRoleBadge(user.role)}">${this.getRoleText(user.role)}</span></td>
                <td><span class="badge badge-${this.getStatusBadge(user.status)}">${user.status}</span></td>
                <td class="table-actions">
                    <button class="action-btn edit" onclick="adminDashboard.editUser(${user.id})">✏️ Изменить</button>
                </td>
            </tr>
        `).join('');
    }

    getRoleBadge(role) {
        const badges = {admin: 'danger', rop: 'warning', employee: 'primary'};
        return badges[role] || 'gray';
    }

    getRoleText(role) {
        const texts = {admin: 'Admin', rop: 'ROP', employee: 'Employee'};
        return texts[role] || role;
    }

    getStatusBadge(status) {
        if (status.includes('Работает')) return 'success';
        if (status.includes('Перерыв')) return 'warning';
        if (status.includes('Не начал')) return 'gray';
        return 'primary';
    }

    editUser(id) {
        const user = this.users.find(u => u.id === id);
        if (!user) return;
        
        this.currentUserId = id;
        document.getElementById('user-name').value = user.name;
        document.getElementById('user-role').value = user.role;
        document.getElementById('user-department').value = user.department_id;
        document.getElementById('user-modal').classList.remove('hidden');
    }

    hideUserModal() {
        document.getElementById('user-modal').classList.add('hidden');
        this.currentUserId = null;
    }

    async saveUser(e) {
        e.preventDefault();
        
        const role = document.getElementById('user-role').value;
        const deptId = document.getElementById('user-department').value;
        
        try {
            await api.request(`/api/v1/users/${this.currentUserId}`, {
                method: 'PUT',
                body: {role, department_id: deptId}
            });
            
            this.hideUserModal();
            await this.loadUsers();
            alert('Пользователь обновлен');
        } catch (error) {
            alert('Ошибка: ' + error.message);
        }
    }

    updateDepartmentSelects() {
        const selects = [
            document.getElementById('filter-department'),
            document.getElementById('department-rop'),
            document.getElementById('user-department')
        ];
        
        selects.forEach(select => {
            if (!select) return;
            const currentValue = select.value;
            const isFilter = select.id === 'filter-department';
            
            select.innerHTML = isFilter ? '<option value="">Все подразделения</option>' : '<option value="">Не назначен</option>';
            this.departments.forEach(dept => {
                select.innerHTML += `<option value="${dept.id}">${dept.name}</option>`;
            });
            
            if (currentValue) select.value = currentValue;
        });
    }

    async saveSettings() {
        const settings = {
            work_start: document.getElementById('setting-work-start').value,
            late_after: document.getElementById('setting-late-after').value,
            norm_hours: parseInt(document.getElementById('setting-norm-hours').value),
            max_break: parseInt(document.getElementById('setting-max-break').value),
            break_warn: parseInt(document.getElementById('setting-break-warn').value),
            email_notify: document.getElementById('setting-email-notify').checked,
            report_freq: document.getElementById('setting-report-freq').value,
            webhook: document.getElementById('setting-webhook').value
        };
        
        try {
            await api.request('/api/v1/settings', {
                method: 'POST',
                body: settings
            });
            alert('Настройки сохранены');
        } catch (error) {
            console.log('Settings saved (mock):', settings);
            alert('Настройки сохранены (mock)');
        }
    }

    async loadStats() {
        try {
            const stats = await api.request('/api/v1/admin/stats');
            this.renderStats(stats);
        } catch (error) {
            console.error('Failed to load stats:', error);
            // Mock data for MVP
            this.renderStats({
                total_users: 25,
                total_departments: 3,
                active_sessions: 18,
                avg_hours: 7.2,
                top_departments: [
                    {name: 'Отдел продаж', avg_hours: 7.8, percent: 97.5},
                    {name: 'IT отдел', avg_hours: 7.5, percent: 93.8},
                    {name: 'Отдел поддержки', avg_hours: 7.2, percent: 90.0},
                    {name: 'Отдел маркетинга', avg_hours: 6.9, percent: 86.3},
                    {name: 'Отдел HR', avg_hours: 6.5, percent: 81.3}
                ]
            });
        }
    }

    renderStats(stats) {
        document.getElementById('stat-total-users').textContent = stats.total_users || 0;
        document.getElementById('stat-total-depts').textContent = stats.total_departments || 0;
        document.getElementById('stat-active-sessions').textContent = stats.active_sessions || 0;
        document.getElementById('stat-avg-hours').textContent = (stats.avg_hours || 0).toFixed(1) + 'ч';
        
        const tbody = document.getElementById('top-departments-tbody');
        const topDepts = stats.top_departments || [];
        
        if (topDepts.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;">Нет данных</td></tr>';
            return;
        }
        
        tbody.innerHTML = topDepts.map((dept, index) => `
            <tr>
                <td><strong>${index + 1}</strong></td>
                <td>${dept.name}</td>
                <td>${dept.avg_hours.toFixed(1)}ч</td>
                <td><span class="badge badge-${dept.percent >= 90 ? 'success' : dept.percent >= 75 ? 'warning' : 'danger'}">${dept.percent.toFixed(1)}%</span></td>
            </tr>
        `).join('');
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.adminDashboard = new AdminDashboard();
});

```

---

### Reports JS

**File:** `frontend/assets/js/reports.js` (339 lines)

```javascript
/**
 * Reports Page Logic
 */

class ReportsManager {
    constructor() {
        this.currentReportType = 'summary';
        this.dateFrom = null;
        this.dateTo = null;
        this.departmentId = null;
        this.userId = null;
        this.departments = [];
        this.users = [];
        
        this.init();
    }

    async init() {
        api.init(1, 1); // Admin/ROP user
        
        this.setupEventListeners();
        this.setDefaultDates();
        await this.loadDepartments();
        this.updateUserFilterVisibility();
    }

    setupEventListeners() {
        // Quick select buttons
        document.querySelectorAll('.quick-btn').forEach(btn => {
            btn.addEventListener('click', (e) => this.handleQuickSelect(e.target.dataset.period));
        });

        // Report type change
        document.getElementById('report-type').addEventListener('change', (e) => {
            this.currentReportType = e.target.value;
            this.updateUserFilterVisibility();
        });

        // Generate report
        document.getElementById('generate-report').addEventListener('click', () => this.generateReport());

        // Export Excel
        document.getElementById('export-excel').addEventListener('click', () => this.exportExcel());

        // Department change (load users)
        document.getElementById('department').addEventListener('change', (e) => {
            this.departmentId = e.target.value || null;
            this.loadUsers();
        });
    }

    setDefaultDates() {
        const today = new Date().toISOString().split('T')[0];
        document.getElementById('date-from').value = today;
        document.getElementById('date-to').value = today;
        this.dateFrom = today;
        this.dateTo = today;
    }

    handleQuickSelect(period) {
        const today = new Date();
        let from, to;

        // Remove active class from all buttons
        document.querySelectorAll('.quick-btn').forEach(btn => btn.classList.remove('active'));
        event.target.classList.add('active');

        switch(period) {
            case 'today':
                from = to = today;
                break;
            case 'week':
                from = new Date(today);
                from.setDate(today.getDate() - 7);
                to = today;
                break;
            case 'month':
                from = new Date(today);
                from.setMonth(today.getMonth() - 1);
                to = today;
                break;
        }

        const fromStr = from.toISOString().split('T')[0];
        const toStr = to.toISOString().split('T')[0];
        
        document.getElementById('date-from').value = fromStr;
        document.getElementById('date-to').value = toStr;
        this.dateFrom = fromStr;
        this.dateTo = toStr;
    }

    updateUserFilterVisibility() {
        const userGroup = document.getElementById('user-filter-group');
        if (this.currentReportType === 'summary') {
            userGroup.style.display = 'none';
        } else {
            userGroup.style.display = 'flex';
        }
    }

    async loadDepartments() {
        try {
            const data = await api.request('/api/v1/departments');
            this.departments = data || [];
            this.renderDepartmentSelect();
        } catch (error) {
            console.error('Failed to load departments:', error);
            // Mock data
            this.departments = [
                {id: 1, name: 'Отдел продаж'},
                {id: 2, name: 'Отдел поддержки'},
                {id: 3, name: 'IT отдел'}
            ];
            this.renderDepartmentSelect();
        }
    }

    renderDepartmentSelect() {
        const select = document.getElementById('department');
        select.innerHTML = '<option value="">Все подразделения</option>';
        this.departments.forEach(dept => {
            select.innerHTML += `<option value="${dept.id}">${dept.name}</option>`;
        });
    }

    async loadUsers() {
        const select = document.getElementById('user');
        select.innerHTML = '<option value="">Выберите пользователя</option>';
        
        if (!this.departmentId) {
            this.users = [];
            return;
        }

        try {
            const data = await api.request(`/api/v1/team/status?department_id=${this.departmentId}`);
            this.users = data || [];
            this.renderUserSelect();
        } catch (error) {
            console.error('Failed to load users:', error);
            // Mock data
            this.users = [
                {id: 1, name: 'Иванов Иван'},
                {id: 2, name: 'Петров Петр'},
                {id: 3, name: 'Сидоров Сергей'}
            ];
            this.renderUserSelect();
        }
    }

    renderUserSelect() {
        const select = document.getElementById('user');
        this.users.forEach(user => {
            select.innerHTML += `<option value="${user.id}">${user.name}</option>`;
        });
    }

    async generateReport() {
        this.dateFrom = document.getElementById('date-from').value;
        this.dateTo = document.getElementById('date-to').value;
        this.userId = document.getElementById('user').value || null;

        if (!this.dateFrom || !this.dateTo) {
            alert('Укажите период отчёта');
            return;
        }

        // Show loading
        this.showLoading();

        // Simulate API delay
        await new Promise(resolve => setTimeout(resolve, 1000));

        // Generate preview based on type
        switch(this.currentReportType) {
            case 'summary':
                this.generateSummaryPreview();
                break;
            case 'detailed':
                this.generateDetailedPreview();
                break;
            case 'timeline':
                this.generateTimelinePreview();
                break;
        }

        // Enable export button
        document.getElementById('export-excel').disabled = false;
    }

    showLoading() {
        document.getElementById('empty-state').classList.add('hidden');
        document.getElementById('preview-summary').classList.add('hidden');
        document.getElementById('preview-detailed').classList.add('hidden');
        document.getElementById('preview-timeline').classList.add('hidden');
        document.getElementById('loading').classList.remove('hidden');
    }

    generateSummaryPreview() {
        // Mock data
        const mockData = [
            {name: 'Иванов Иван', dept: 'Отдел продаж', hours: 41.5, avg: 8.3, lates: 0, breaks: 10, norm: 98},
            {name: 'Петров Петр', dept: 'Отдел продаж', hours: 38.0, avg: 7.6, lates: 2, breaks: 12, norm: 90},
            {name: 'Сидоров Сергей', dept: 'IT отдел', hours: 42.0, avg: 8.4, lates: 1, breaks: 8, norm: 100},
            {name: 'Козлов Кирилл', dept: 'Отдел поддержки', hours: 39.5, avg: 7.9, lates: 0, breaks: 11, norm: 95},
            {name: 'Смирнов Алексей', dept: 'Отдел продаж', hours: 37.0, avg: 7.4, lates: 3, breaks: 15, norm: 87}
        ];

        const tbody = document.getElementById('summary-tbody');
        tbody.innerHTML = mockData.map(row => `
            <tr>
                <td><strong>${row.name}</strong></td>
                <td>${row.dept}</td>
                <td>${row.hours.toFixed(1)}ч</td>
                <td>${row.avg.toFixed(1)}ч</td>
                <td>${row.lates}</td>
                <td>${row.breaks}</td>
                <td><span class="badge badge-${row.norm >= 95 ? 'success' : row.norm >= 85 ? 'warning' : 'danger'}">${row.norm}%</span></td>
            </tr>
        `).join('');

        this.showPreview('summary');
    }

    generateDetailedPreview() {
        // Mock data
        const mockData = [
            {date: '2026-08-11', start: '09:00', end: '18:05', hours: 8.1, breaks: 2, late: false, crm: 45},
            {date: '2026-08-10', start: '09:15', end: '17:50', hours: 7.6, breaks: 3, late: true, crm: 38},
            {date: '2026-08-09', start: '09:00', end: '18:10', hours: 8.2, breaks: 2, late: false, crm: 52},
            {date: '2026-08-08', start: '09:05', end: '18:00', hours: 7.9, breaks: 2, late: false, crm: 41},
            {date: '2026-08-07', start: '09:00', end: '18:15', hours: 8.3, breaks: 1, late: false, crm: 48}
        ];

        const tbody = document.getElementById('detailed-tbody');
        tbody.innerHTML = mockData.map(row => `
            <tr>
                <td>${row.date}</td>
                <td>${row.start}</td>
                <td>${row.end}</td>
                <td><strong>${row.hours.toFixed(1)}ч</strong></td>
                <td>${row.breaks}</td>
                <td><span class="badge badge-${row.late ? 'danger' : 'success'}">${row.late ? 'Да' : 'Нет'}</span></td>
                <td>${row.crm}</td>
            </tr>
        `).join('');

        this.showPreview('detailed');
    }

    generateTimelinePreview() {
        // Mock timeline data (24 hours)
        const mockTimeline = [
            'idle', 'idle', 'idle', 'idle', 'idle', 'idle', 'idle', 'idle', 'idle',
            'work', 'work', 'work', 'work', 'break', 'work', 'work', 'work', 'break',
            'work', 'work', 'work', 'idle', 'idle', 'idle'
        ];

        const grid = document.getElementById('timeline-grid');
        grid.innerHTML = mockTimeline.map((status, i) => 
            `<div class="timeline-cell ${status}" title="${i}:00"></div>`
        ).join('');

        document.getElementById('timeline-user').textContent = 'Иванов Иван';
        document.getElementById('timeline-date').textContent = this.dateFrom;

        this.showPreview('timeline');
    }

    showPreview(type) {
        document.getElementById('loading').classList.add('hidden');
        document.getElementById('empty-state').classList.add('hidden');
        document.getElementById('preview-summary').classList.add('hidden');
        document.getElementById('preview-detailed').classList.add('hidden');
        document.getElementById('preview-timeline').classList.add('hidden');
        
        document.getElementById(`preview-${type}`).classList.remove('hidden');
        
        // Update report info
        const reportInfo = document.getElementById('report-info');
        reportInfo.textContent = `${this.dateFrom} — ${this.dateTo}`;
    }

    async exportExcel() {
        const params = new URLSearchParams({
            start_date: this.dateFrom,
            end_date: this.dateTo
        });

        if (this.departmentId) params.append('department_id', this.departmentId);
        if (this.userId) params.append('user_id', this.userId);

        let endpoint;
        switch(this.currentReportType) {
            case 'summary':
                endpoint = `/api/v1/excel/export/summary?${params}`;
                break;
            case 'detailed':
                endpoint = `/api/v1/excel/export/detailed?${params}`;
                break;
            case 'timeline':
                endpoint = `/api/v1/excel/export/timeline?date=${this.dateFrom}&user_id=${this.userId || 1}`;
                break;
        }

        try {
            // Download file
            const response = await fetch(`http://localhost:8000${endpoint}`, {
                headers: {
                    'X-User-Id': '1',
                    'X-Account-Id': '1'
                }
            });

            if (!response.ok) throw new Error('Export failed');

            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `report_${this.currentReportType}_${this.dateFrom}.xlsx`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            a.remove();

            alert('Отчёт успешно экспортирован!');
        } catch (error) {
            console.error('Export failed:', error);
            alert('Ошибка экспорта. Проверьте, что backend запущен.');
        }
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.reportsManager = new ReportsManager();
});

```

---

### Personal CSS

**File:** `frontend/assets/css/personal.css` (464 lines)

```css
/* Personal Dashboard Styles */
:root {
    --primary: #4A90E2;
    --success: #7ED321;
    --warning: #F5A623;
    --danger: #D0021B;
    --gray: #9B9B9B;
    --dark: #333;
    --light: #F5F5F5;
    --white: #FFF;
}

* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: var(--light);
    color: var(--dark);
}

.hidden {
    display: none !important;
}

/* Buttons */
.btn {
    padding: 12px 24px;
    border: none;
    border-radius: 8px;
    font-size: 16px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.3s ease;
}

.btn-primary {
    background: var(--primary);
    color: var(--white);
}

.btn-primary:hover {
    background: #357ABD;
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(74, 144, 226, 0.3);
}

.btn-success {
    background: var(--success);
    color: var(--white);
}

.btn-warning {
    background: var(--warning);
    color: var(--white);
}

.btn-danger {
    background: var(--danger);
    color: var(--white);
}

.btn-large {
    padding: 16px 48px;
    font-size: 18px;
}

.btn-sm {
    padding: 8px 16px;
    font-size: 14px;
}

/* Overlays */
.overlay {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.95);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    animation: fadeIn 0.3s ease;
}

.overlay-content {
    background: var(--white);
    padding: 48px;
    border-radius: 16px;
    max-width: 500px;
    width: 90%;
    text-align: center;
    animation: slideUp 0.4s ease;
}

.icon-large {
    font-size: 80px;
    margin-bottom: 24px;
}

.icon-large.warning {
    animation: pulse 2s infinite;
}

.icon-large.success {
    animation: bounce 1s ease;
}

.overlay-content h1 {
    font-size: 32px;
    margin-bottom: 16px;
    color: var(--dark);
}

.current-time {
    font-size: 48px;
    font-weight: bold;
    color: var(--primary);
    margin: 24px 0;
}

.schedule-info {
    margin: 24px 0;
    padding: 16px;
    background: var(--light);
    border-radius: 8px;
}

/* Late Overlay */
.late-info {
    font-size: 20px;
    color: var(--danger);
    font-weight: bold;
    margin: 16px 0;
}

.form-group {
    margin: 24px 0;
    text-align: left;
}

.form-group label {
    display: block;
    margin-bottom: 8px;
    font-weight: 600;
}

.form-group textarea {
    width: 100%;
    padding: 12px;
    border: 2px solid #ddd;
    border-radius: 8px;
    font-family: inherit;
    font-size: 14px;
    resize: vertical;
}

.form-group textarea:focus {
    outline: none;
    border-color: var(--primary);
}

.char-counter {
    text-align: right;
    font-size: 12px;
    color: var(--gray);
    margin-top: 4px;
}

/* Working Widget (Compact) */
.widget-compact {
    position: fixed;
    top: 20px;
    right: 20px;
    background: var(--white);
    border-radius: 12px;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
    min-width: 280px;
    z-index: 999;
    animation: slideInRight 0.4s ease;
}

.widget-header {
    padding: 16px;
    border-bottom: 1px solid #eee;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.status-badge {
    padding: 6px 12px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 600;
}

.status-working {
    background: var(--success);
    color: var(--white);
}

.timer {
    font-size: 18px;
    font-weight: bold;
    color: var(--primary);
}

.widget-body {
    padding: 16px;
}

.crm-status {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 12px;
    font-size: 14px;
}

.crm-status .indicator {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: var(--success);
    animation: blink 2s infinite;
}

.crm-status.inactive .indicator {
    background: var(--gray);
}

.widget-actions {
    display: flex;
    gap: 8px;
}

.widget-actions .btn {
    flex: 1;
}

/* Break Overlay */
.timer-large {
    font-size: 64px;
    font-weight: bold;
    color: var(--primary);
    margin: 24px 0;
}

.break-warning {
    background: #FFF3CD;
    border: 2px solid var(--warning);
    border-radius: 8px;
    padding: 12px;
    margin: 16px 0;
}

.break-warning.hidden {
    display: none;
}

.break-stats {
    margin: 24px 0;
    padding: 16px;
    background: var(--light);
    border-radius: 8px;
}

.break-stats p {
    margin: 8px 0;
}

/* Finished Overlay */
.day-summary {
    margin: 32px 0;
    display: grid;
    gap: 16px;
}

.summary-item {
    padding: 16px;
    background: var(--light);
    border-radius: 8px;
}

.summary-item .label {
    font-size: 14px;
    color: var(--gray);
    margin-bottom: 4px;
}

.summary-item .value {
    font-size: 32px;
    font-weight: bold;
    color: var(--primary);
}

.info-text {
    margin-top: 24px;
    color: var(--gray);
    font-size: 16px;
}

/* Dashboard */
.dashboard {
    padding: 20px;
    max-width: 1400px;
    margin: 0 auto;
}

.dashboard-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 32px;
}

.dashboard-header h1 {
    font-size: 32px;
}

.user-info {
    font-size: 16px;
    color: var(--gray);
}

/* KPI Section */
.kpi-section {
    margin-bottom: 32px;
}

.kpi-section h2 {
    margin-bottom: 16px;
}

.kpi-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 16px;
}

.kpi-card {
    background: var(--white);
    padding: 24px;
    border-radius: 12px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.kpi-label {
    font-size: 14px;
    color: var(--gray);
    margin-bottom: 8px;
}

.kpi-value {
    font-size: 36px;
    font-weight: bold;
    color: var(--primary);
}

.kpi-value.warning {
    color: var(--warning);
}

.kpi-sublabel {
    font-size: 12px;
    color: var(--gray);
    margin-top: 4px;
}

/* Chart Section */
.chart-section {
    background: var(--white);
    padding: 24px;
    border-radius: 12px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.section-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 24px;
}

.period-switcher {
    display: flex;
    gap: 8px;
}

.period-switcher .btn.active {
    background: var(--primary);
    color: var(--white);
}

.chart-container {
    position: relative;
    height: 300px;
}

/* Animations */
@keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
}

@keyframes slideUp {
    from { transform: translateY(50px); opacity: 0; }
    to { transform: translateY(0); opacity: 1; }
}

@keyframes slideInRight {
    from { transform: translateX(100px); opacity: 0; }
    to { transform: translateX(0); opacity: 1; }
}

@keyframes pulse {
    0%, 100% { transform: scale(1); }
    50% { transform: scale(1.1); }
}

@keyframes bounce {
    0%, 20%, 50%, 80%, 100% { transform: translateY(0); }
    40% { transform: translateY(-20px); }
    60% { transform: translateY(-10px); }
}

@keyframes blink {
    0%, 50% { opacity: 1; }
    25%, 75% { opacity: 0.3; }
}

/* Responsive */
@media (max-width: 768px) {
    .overlay-content {
        padding: 32px;
    }
    
    .widget-compact {
        right: 10px;
        top: 10px;
        min-width: 240px;
    }
    
    .kpi-grid {
        grid-template-columns: repeat(2, 1fr);
    }
    
    .section-header {
        flex-direction: column;
        gap: 16px;
    }
}

@media (max-width: 480px) {
    .kpi-grid {
        grid-template-columns: 1fr;
    }
}

```

---

### ROP CSS

**File:** `frontend/assets/css/rop.css` (548 lines)

```css
/* ROP Dashboard Styles */
:root {
    --primary: #4A90E2;
    --success: #7ED321;
    --warning: #F5A623;
    --danger: #D0021B;
    --gray: #9B9B9B;
    --dark: #333;
    --light: #F5F5F5;
    --white: #FFF;
}

* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: var(--light);
    color: var(--dark);
}

.hidden {
    display: none !important;
}

/* Header */
.header {
    background: var(--white);
    padding: 20px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.header h1 {
    font-size: 24px;
}

.header-info {
    display: flex;
    gap: 20px;
    font-size: 14px;
    color: var(--gray);
}

/* Filters */
.filters {
    background: var(--white);
    padding: 16px 20px;
    margin: 16px 0;
    display: flex;
    justify-content: space-between;
    gap: 16px;
    flex-wrap: wrap;
}

.filter-buttons {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
}

.filter-btn {
    padding: 8px 16px;
    border: 2px solid #ddd;
    background: var(--white);
    border-radius: 8px;
    cursor: pointer;
    font-size: 14px;
    transition: all 0.3s;
}

.filter-btn:hover {
    border-color: var(--primary);
}

.filter-btn.active {
    background: var(--primary);
    color: var(--white);
    border-color: var(--primary);
}

.filter-btn .count {
    background: rgba(0,0,0,0.1);
    padding: 2px 8px;
    border-radius: 12px;
    margin-left: 4px;
    font-size: 12px;
}

.filter-btn.active .count {
    background: rgba(255,255,255,0.3);
}

.search-box input {
    padding: 8px 16px;
    border: 2px solid #ddd;
    border-radius: 8px;
    font-size: 14px;
    min-width: 250px;
}

.search-box input:focus {
    outline: none;
    border-color: var(--primary);
}

/* Stats Summary */
.stats-summary {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 16px;
    padding: 0 20px;
    margin-bottom: 24px;
}

.stat-card {
    background: var(--white);
    padding: 20px;
    border-radius: 12px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    text-align: center;
}

.stat-label {
    font-size: 14px;
    color: var(--gray);
    margin-bottom: 8px;
}

.stat-value {
    font-size: 32px;
    font-weight: bold;
    color: var(--primary);
}

.stat-value.warning {
    color: var(--warning);
}

/* Employees Section */
.employees-section {
    padding: 0 20px;
    margin-bottom: 32px;
}

.employees-section h2 {
    margin-bottom: 16px;
}

.employees-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap: 16px;
}

.employee-card {
    background: var(--white);
    padding: 16px;
    border-radius: 12px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    border-left: 4px solid var(--gray);
}

.employee-card.status-working {
    border-left-color: var(--success);
}

.employee-card.status-break {
    border-left-color: var(--warning);
}

.employee-card.status-finished {
    border-left-color: var(--primary);
}

.employee-card.status-inactive {
    border-left-color: var(--danger);
}

.employee-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
}

.employee-name {
    font-size: 18px;
    font-weight: 600;
}

.status-indicator {
    padding: 4px 12px;
    border-radius: 12px;
    font-size: 12px;
    font-weight: 600;
}

.status-indicator.working {
    background: var(--success);
    color: var(--white);
}

.status-indicator.break {
    background: var(--warning);
    color: var(--white);
}

.status-indicator.finished {
    background: var(--primary);
    color: var(--white);
}

.status-indicator.not-started {
    background: var(--gray);
    color: var(--white);
}

.status-indicator.inactive {
    background: var(--danger);
    color: var(--white);
}

.employee-info {
    margin-bottom: 12px;
}

.employee-info p {
    margin: 4px 0;
    font-size: 14px;
    color: var(--gray);
}

.employee-actions {
    display: flex;
    gap: 8px;
}

.btn {
    padding: 8px 16px;
    border: none;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.3s;
}

.btn-sm {
    padding: 6px 12px;
    font-size: 12px;
}

.btn-primary {
    background: var(--primary);
    color: var(--white);
}

.btn-danger {
    background: var(--danger);
    color: var(--white);
}

.btn-secondary {
    background: var(--gray);
    color: var(--white);
}

.btn:hover {
    opacity: 0.9;
    transform: translateY(-1px);
}

/* KPI Section */
.kpi-section {
    padding: 0 20px;
    margin-bottom: 32px;
}

.kpi-section h2 {
    margin-bottom: 16px;
}

.kpi-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 16px;
}

.kpi-card {
    background: var(--white);
    padding: 20px;
    border-radius: 12px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    text-align: center;
}

.kpi-label {
    font-size: 14px;
    color: var(--gray);
    margin-bottom: 8px;
}

.kpi-value {
    font-size: 32px;
    font-weight: bold;
    color: var(--primary);
}

.kpi-value.warning {
    color: var(--warning);
}

/* Chart Section */
.chart-section {
    padding: 0 20px;
    margin-bottom: 32px;
}

.chart-section > div {
    background: var(--white);
    padding: 24px;
    border-radius: 12px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.section-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 24px;
}

.period-switcher {
    display: flex;
    gap: 8px;
}

.period-switcher .btn.active {
    background: var(--primary);
    color: var(--white);
}

.chart-container {
    position: relative;
    height: 300px;
}

/* Modal */
.modal {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0,0,0,0.7);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    animation: fadeIn 0.3s;
}

.modal-content {
    background: var(--white);
    border-radius: 16px;
    max-width: 900px;
    width: 90%;
    max-height: 90vh;
    overflow-y: auto;
    animation: slideUp 0.4s;
}

.modal-content.small {
    max-width: 400px;
}

.modal-header {
    padding: 20px 24px;
    border-bottom: 1px solid #eee;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.close-btn {
    background: none;
    border: none;
    font-size: 32px;
    cursor: pointer;
    color: var(--gray);
    line-height: 1;
}

.close-btn:hover {
    color: var(--dark);
}

.modal-body {
    padding: 24px;
}

.modal-actions {
    display: flex;
    gap: 12px;
    margin-top: 20px;
}

.modal-actions .btn {
    flex: 1;
}

/* Timeline */
.timeline-info {
    margin-bottom: 20px;
    padding: 16px;
    background: var(--light);
    border-radius: 8px;
}

.timeline-info p {
    margin: 4px 0;
}

.timeline-grid {
    display: grid;
    grid-template-columns: repeat(24, 1fr);
    gap: 2px;
    margin: 20px 0;
}

.timeline-cell {
    aspect-ratio: 1;
    border-radius: 4px;
    position: relative;
    cursor: help;
}

.timeline-cell.working {
    background: var(--success);
}

.timeline-cell.break {
    background: var(--warning);
}

.timeline-cell.inactive {
    background: var(--light);
}

.timeline-cell.has-activity::after {
    content: '•';
    position: absolute;
    top: 2px;
    right: 2px;
    color: var(--white);
    font-size: 8px;
}

.timeline-legend {
    display: flex;
    gap: 16px;
    justify-content: center;
    margin-top: 16px;
}

.legend-item {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 14px;
}

.legend-color {
    width: 16px;
    height: 16px;
    border-radius: 4px;
}

.legend-color.working {
    background: var(--success);
}

.legend-color.break {
    background: var(--warning);
}

.legend-color.inactive {
    background: var(--light);
    border: 1px solid #ddd;
}

.legend-dot {
    width: 16px;
    height: 16px;
    border-radius: 4px;
    background: var(--success);
    position: relative;
}

.legend-dot::after {
    content: '•';
    position: absolute;
    top: 0;
    right: 2px;
    color: var(--white);
    font-size: 12px;
}

/* Animations */
@keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
}

@keyframes slideUp {
    from { transform: translateY(50px); opacity: 0; }
    to { transform: translateY(0); opacity: 1; }
}

/* Responsive */
@media (max-width: 768px) {
    .header {
        flex-direction: column;
        gap: 12px;
    }
    
    .filters {
        flex-direction: column;
    }
    
    .search-box input {
        width: 100%;
    }
    
    .employees-grid {
        grid-template-columns: 1fr;
    }
    
    .timeline-grid {
        grid-template-columns: repeat(12, 1fr);
    }
}

```

---

### Admin CSS

**File:** `frontend/assets/css/admin.css` (481 lines)

```css
/* Admin Dashboard Styles */
:root {
    --primary: #4A90E2;
    --success: #7ED321;
    --warning: #F5A623;
    --danger: #D0021B;
    --gray: #9B9B9B;
    --dark: #333;
    --light: #F5F5F5;
    --white: #FFF;
    --border: #E0E0E0;
}

* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: var(--light);
    color: var(--dark);
}

.hidden {
    display: none !important;
}

/* Header */
.header {
    background: var(--white);
    padding: 20px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.header h1 {
    font-size: 24px;
}

.header-info {
    font-size: 14px;
    color: var(--gray);
}

/* Tabs */
.tabs {
    background: var(--white);
    display: flex;
    border-bottom: 2px solid var(--border);
    padding: 0 20px;
}

.tab-btn {
    padding: 16px 24px;
    border: none;
    background: none;
    font-size: 16px;
    font-weight: 600;
    cursor: pointer;
    border-bottom: 3px solid transparent;
    margin-bottom: -2px;
    transition: all 0.3s;
    color: var(--gray);
}

.tab-btn:hover {
    color: var(--primary);
    background: rgba(74, 144, 226, 0.05);
}

.tab-btn.active {
    color: var(--primary);
    border-bottom-color: var(--primary);
}

/* Tab Content */
.tab-content {
    display: none;
    padding: 20px;
}

.tab-content.active {
    display: block;
}

/* Section Header */
.section-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
    flex-wrap: wrap;
    gap: 16px;
}

.section-header h2 {
    font-size: 20px;
}

/* Filters */
.filters {
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
}

.filters select,
.filters input {
    padding: 8px 12px;
    border: 1px solid var(--border);
    border-radius: 6px;
    font-size: 14px;
}

.filters input {
    min-width: 200px;
}

/* Buttons */
.btn {
    padding: 10px 20px;
    border: none;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.3s;
}

.btn-primary {
    background: var(--primary);
    color: var(--white);
}

.btn-secondary {
    background: var(--gray);
    color: var(--white);
}

.btn-danger {
    background: var(--danger);
    color: var(--white);
}

.btn-success {
    background: var(--success);
    color: var(--white);
}

.btn:hover {
    opacity: 0.9;
    transform: translateY(-1px);
}

.btn-large {
    padding: 14px 28px;
    font-size: 16px;
    margin-top: 20px;
}

/* Tables */
.table-container {
    background: var(--white);
    border-radius: 12px;
    overflow: hidden;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.data-table {
    width: 100%;
    border-collapse: collapse;
}

.data-table thead {
    background: var(--light);
}

.data-table th {
    padding: 16px;
    text-align: left;
    font-weight: 600;
    color: var(--dark);
    border-bottom: 2px solid var(--border);
}

.data-table td {
    padding: 16px;
    border-bottom: 1px solid var(--border);
}

.data-table tbody tr:hover {
    background: rgba(74, 144, 226, 0.05);
}

.data-table tbody tr:last-child td {
    border-bottom: none;
}

/* Table Actions */
.table-actions {
    display: flex;
    gap: 8px;
}

.action-btn {
    padding: 6px 12px;
    border: 1px solid var(--border);
    background: var(--white);
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.3s;
    font-size: 14px;
}

.action-btn:hover {
    background: var(--light);
}

.action-btn.edit {
    color: var(--primary);
    border-color: var(--primary);
}

.action-btn.delete {
    color: var(--danger);
    border-color: var(--danger);
}

/* Settings */
.settings-container {
    background: var(--white);
    padding: 24px;
    border-radius: 12px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.settings-group {
    margin-bottom: 32px;
}

.settings-group h3 {
    margin-bottom: 16px;
    font-size: 18px;
}

.form-group {
    margin-bottom: 16px;
}

.form-group label {
    display: block;
    margin-bottom: 8px;
    font-weight: 600;
    color: var(--dark);
}

.form-group input[type="text"],
.form-group input[type="time"],
.form-group input[type="number"],
.form-group input[type="url"],
.form-group select {
    width: 100%;
    max-width: 400px;
    padding: 10px 12px;
    border: 1px solid var(--border);
    border-radius: 6px;
    font-size: 14px;
}

.form-group input[type="checkbox"] {
    margin-right: 8px;
}

/* Stats */
.stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 16px;
    margin-bottom: 32px;
}

.stat-card {
    background: var(--white);
    padding: 24px;
    border-radius: 12px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    text-align: center;
}

.stat-label {
    font-size: 14px;
    color: var(--gray);
    margin-bottom: 12px;
}

.stat-value {
    font-size: 36px;
    font-weight: bold;
    color: var(--primary);
}

/* Top Departments */
.top-departments {
    background: var(--white);
    padding: 24px;
    border-radius: 12px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.top-departments h3 {
    margin-bottom: 16px;
    font-size: 18px;
}

/* Modal */
.modal {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0,0,0,0.7);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    animation: fadeIn 0.3s;
}

.modal-content {
    background: var(--white);
    border-radius: 16px;
    max-width: 600px;
    width: 90%;
    max-height: 90vh;
    overflow-y: auto;
    animation: slideUp 0.4s;
}

.modal-content.small {
    max-width: 450px;
}

.modal-header {
    padding: 20px 24px;
    border-bottom: 1px solid var(--border);
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.modal-header h2 {
    font-size: 20px;
}

.close-btn {
    background: none;
    border: none;
    font-size: 32px;
    cursor: pointer;
    color: var(--gray);
    line-height: 1;
}

.close-btn:hover {
    color: var(--dark);
}

.modal-body {
    padding: 24px;
}

.modal-actions {
    display: flex;
    gap: 12px;
    margin-top: 20px;
}

.modal-actions .btn {
    flex: 1;
}

/* Badges */
.badge {
    padding: 4px 12px;
    border-radius: 12px;
    font-size: 12px;
    font-weight: 600;
    display: inline-block;
}

.badge-success {
    background: var(--success);
    color: var(--white);
}

.badge-warning {
    background: var(--warning);
    color: var(--white);
}

.badge-danger {
    background: var(--danger);
    color: var(--white);
}

.badge-gray {
    background: var(--gray);
    color: var(--white);
}

.badge-primary {
    background: var(--primary);
    color: var(--white);
}

/* Animations */
@keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
}

@keyframes slideUp {
    from { transform: translateY(50px); opacity: 0; }
    to { transform: translateY(0); opacity: 1; }
}

/* Responsive */
@media (max-width: 768px) {
    .header {
        flex-direction: column;
        gap: 12px;
    }
    
    .tabs {
        overflow-x: auto;
        flex-wrap: nowrap;
    }
    
    .tab-btn {
        white-space: nowrap;
        padding: 12px 16px;
        font-size: 14px;
    }
    
    .section-header {
        flex-direction: column;
        align-items: flex-start;
    }
    
    .filters {
        width: 100%;
        flex-direction: column;
    }
    
    .filters select,
    .filters input {
        width: 100%;
    }
    
    .table-container {
        overflow-x: auto;
    }
    
    .data-table {
        min-width: 600px;
    }
    
    .stats-grid {
        grid-template-columns: 1fr;
    }
    
    .form-group input,
    .form-group select {
        max-width: 100%;
    }
}

```

---

### Reports CSS

**File:** `frontend/assets/css/reports.css` (452 lines)

```css
/* Reports Page Styles */
:root {
    --primary: #4A90E2;
    --success: #7ED321;
    --warning: #F5A623;
    --danger: #D0021B;
    --gray: #9B9B9B;
    --dark: #333;
    --light: #F5F5F5;
    --white: #FFF;
    --border: #E0E0E0;
}

* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: var(--light);
    color: var(--dark);
}

.hidden {
    display: none !important;
}

/* Header */
.header {
    background: var(--white);
    padding: 20px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
}

.header h1 {
    font-size: 24px;
}

.header-info {
    font-size: 14px;
    color: var(--gray);
}

/* Filters Section */
.filters-section {
    background: var(--white);
    padding: 24px;
    margin: 0 20px 20px;
    border-radius: 12px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.filters-container {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 20px;
}

.filter-group {
    display: flex;
    flex-direction: column;
}

.filter-group h3 {
    font-size: 14px;
    font-weight: 600;
    margin-bottom: 12px;
    color: var(--dark);
}

/* Quick Select Buttons */
.quick-select {
    display: flex;
    gap: 8px;
    margin-bottom: 12px;
}

.quick-btn {
    flex: 1;
    padding: 8px;
    border: 1px solid var(--border);
    background: var(--white);
    border-radius: 6px;
    font-size: 13px;
    cursor: pointer;
    transition: all 0.3s;
}

.quick-btn:hover {
    background: var(--primary);
    color: var(--white);
    border-color: var(--primary);
}

.quick-btn.active {
    background: var(--primary);
    color: var(--white);
    border-color: var(--primary);
}

/* Date Inputs */
.date-inputs {
    display: flex;
    gap: 12px;
}

.date-group {
    flex: 1;
    display: flex;
    flex-direction: column;
}

.date-group label {
    font-size: 12px;
    margin-bottom: 4px;
    color: var(--gray);
}

.date-group input {
    padding: 8px;
    border: 1px solid var(--border);
    border-radius: 6px;
    font-size: 14px;
}

/* Form Select */
.form-select {
    padding: 10px 12px;
    border: 1px solid var(--border);
    border-radius: 6px;
    font-size: 14px;
    background: var(--white);
    cursor: pointer;
}

/* Action Buttons */
.actions-group {
    display: flex;
    gap: 12px;
    align-items: flex-end;
}

.btn {
    padding: 12px 20px;
    border: none;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.3s;
    flex: 1;
}

.btn-primary {
    background: var(--primary);
    color: var(--white);
}

.btn-success {
    background: var(--success);
    color: var(--white);
}

.btn:hover:not(:disabled) {
    opacity: 0.9;
    transform: translateY(-1px);
}

.btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}

/* Preview Section */
.preview-section {
    background: var(--white);
    margin: 0 20px 20px;
    border-radius: 12px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    padding: 24px;
}

.preview-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
    padding-bottom: 16px;
    border-bottom: 2px solid var(--border);
}

.preview-header h2 {
    font-size: 20px;
}

#report-info {
    font-size: 14px;
    color: var(--gray);
}

/* Loading State */
.loading-state {
    text-align: center;
    padding: 60px 20px;
}

.spinner {
    width: 50px;
    height: 50px;
    margin: 0 auto 20px;
    border: 4px solid var(--light);
    border-top-color: var(--primary);
    border-radius: 50%;
    animation: spin 1s linear infinite;
}

@keyframes spin {
    to { transform: rotate(360deg); }
}

.loading-state p {
    color: var(--gray);
    font-size: 16px;
}

/* Empty State */
.empty-state {
    text-align: center;
    padding: 60px 20px;
}

.empty-icon {
    font-size: 64px;
    margin-bottom: 20px;
}

.empty-state h3 {
    font-size: 20px;
    margin-bottom: 12px;
    color: var(--dark);
}

.empty-state p {
    color: var(--gray);
    font-size: 14px;
}

/* Preview Content */
.preview-content {
    animation: fadeIn 0.3s;
}

/* Table */
.table-container {
    overflow-x: auto;
}

.data-table {
    width: 100%;
    border-collapse: collapse;
}

.data-table thead {
    background: var(--light);
}

.data-table th {
    padding: 12px;
    text-align: left;
    font-weight: 600;
    color: var(--dark);
    border-bottom: 2px solid var(--border);
    font-size: 13px;
}

.data-table td {
    padding: 12px;
    border-bottom: 1px solid var(--border);
    font-size: 14px;
}

.data-table tbody tr:hover {
    background: rgba(74, 144, 226, 0.05);
}

.data-table tbody tr:last-child td {
    border-bottom: none;
}

/* Timeline Specific */
.timeline-info {
    margin-bottom: 20px;
    padding: 16px;
    background: var(--light);
    border-radius: 8px;
}

.timeline-info p {
    margin: 4px 0;
    font-size: 14px;
}

.timeline-grid {
    display: grid;
    grid-template-columns: repeat(24, 1fr);
    gap: 2px;
    margin-bottom: 20px;
    padding: 12px;
    background: var(--light);
    border-radius: 8px;
}

.timeline-cell {
    aspect-ratio: 1;
    border-radius: 4px;
    cursor: pointer;
    transition: transform 0.2s;
    position: relative;
}

.timeline-cell:hover {
    transform: scale(1.1);
    z-index: 10;
}

.timeline-cell.work {
    background: var(--success);
}

.timeline-cell.break {
    background: var(--warning);
}

.timeline-cell.idle {
    background: var(--gray);
}

/* Timeline Legend */
.timeline-legend {
    display: flex;
    gap: 20px;
    justify-content: center;
    padding: 16px;
    background: var(--light);
    border-radius: 8px;
}

.legend-item {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 14px;
}

.legend-color {
    width: 20px;
    height: 20px;
    border-radius: 4px;
}

.legend-color.work {
    background: var(--success);
}

.legend-color.break {
    background: var(--warning);
}

.legend-color.idle {
    background: var(--gray);
}

/* Badges */
.badge {
    padding: 4px 10px;
    border-radius: 12px;
    font-size: 12px;
    font-weight: 600;
    display: inline-block;
}

.badge-success {
    background: var(--success);
    color: var(--white);
}

.badge-warning {
    background: var(--warning);
    color: var(--white);
}

.badge-danger {
    background: var(--danger);
    color: var(--white);
}

/* Animations */
@keyframes fadeIn {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
}

/* Responsive */
@media (max-width: 768px) {
    .header {
        flex-direction: column;
        gap: 12px;
    }
    
    .filters-container {
        grid-template-columns: 1fr;
    }
    
    .actions-group {
        flex-direction: column;
    }
    
    .btn {
        width: 100%;
    }
    
    .date-inputs {
        flex-direction: column;
    }
    
    .quick-select {
        flex-direction: column;
    }
    
    .table-container {
        overflow-x: auto;
    }
    
    .data-table {
        min-width: 600px;
    }
    
    .timeline-grid {
        grid-template-columns: repeat(12, 1fr);
    }
    
    .timeline-legend {
        flex-direction: column;
        align-items: flex-start;
    }
}

```

---

## ✅ ИТОГО

**Файлов прочитано:** 47/47
**Строк кода:** 9,139

---

## 🚀 НАЧИНАЙ CODE REVIEW!

Жду детальный анализ с готовыми исправлениями для каждого файла! 🎉
