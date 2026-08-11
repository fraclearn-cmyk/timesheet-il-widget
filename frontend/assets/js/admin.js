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
