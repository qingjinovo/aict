/**
 * CT 医学影像标注 API 客户端
 * 提供与后端 annotation_api.py 的通信接口
 */

class APIError extends Error {
    constructor(code, message, statusCode) {
        super(message);
        this.name = 'APIError';
        this.code = code;
        this.statusCode = statusCode;
    }
}

const CTApiClient = {
    baseUrl: '/api/annotation',

    async request(endpoint, options = {}) {
        const url = `${this.baseUrl}${endpoint}`;
        const config = {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        };

        if (config.body && typeof config.body === 'object') {
            config.body = JSON.stringify(config.body);
        }

        try {
            const response = await fetch(url, config);
            const data = await response.json();

            if (!response.ok) {
                throw new APIError(
                    data.error || 'UNKNOWN_ERROR',
                    data.message || '请求失败',
                    response.status
                );
            }

            return data;
        } catch (e) {
            if (e instanceof APIError) {
                throw e;
            }
            throw new APIError('NETWORK_ERROR', '网络连接失败', 0);
        }
    },

    async listAnnotationSets() {
        return this.request('/sets');
    },

    async getAnnotationSet(setId) {
        return this.request(`/sets/${setId}`);
    },

    async createAnnotationSet(data) {
        return this.request('/sets', {
            method: 'POST',
            body: data
        });
    },

    async deleteAnnotationSet(setId) {
        return this.request(`/sets/${setId}`, {
            method: 'DELETE'
        });
    },

    async createAnnotation(setId, data) {
        return this.request(`/sets/${setId}/annotations`, {
            method: 'POST',
            body: data
        });
    },

    async getAnnotation(setId, annoId) {
        return this.request(`/sets/${setId}/annotations/${annoId}`);
    },

    async updateAnnotation(setId, annoId, updates) {
        return this.request(`/sets/${setId}/annotations/${annoId}`, {
            method: 'PUT',
            body: updates
        });
    },

    async deleteAnnotation(setId, annoId) {
        return this.request(`/sets/${setId}/annotations/${annoId}`, {
            method: 'DELETE'
        });
    },

    async confirmAnnotation(setId, annoId) {
        return this.request(`/sets/${setId}/annotations/${annoId}/confirm`, {
            method: 'POST'
        });
    },

    async getAnnotationsBySlice(setId, sliceIndex) {
        return this.request(`/sets/${setId}/slices/${sliceIndex}`);
    },

    async exportAnnotationSet(setId, format = 'json') {
        return this.request(`/sets/${setId}/export?format=${format}`);
    },

    async importAnnotationSet(setId, data) {
        return this.request(`/sets/${setId}/import`, {
            method: 'POST',
            body: data
        });
    },

    async getVisualPresets() {
        return this.request('/presets');
    },

    async getAnnotationTypes() {
        return this.request('/types');
    },

    async calculateMeasurement(data) {
        return this.request('/measurement/calculate', {
            method: 'POST',
            body: data
        });
    }
};

window.CTApiClient = CTApiClient;
