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
