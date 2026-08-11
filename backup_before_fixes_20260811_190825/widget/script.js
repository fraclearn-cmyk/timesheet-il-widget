define(['jquery'], function($) {
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


