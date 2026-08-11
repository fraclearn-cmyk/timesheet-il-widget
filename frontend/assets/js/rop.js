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
