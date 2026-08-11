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
