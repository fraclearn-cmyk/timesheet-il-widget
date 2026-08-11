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
