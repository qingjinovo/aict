/**
 * 统一 API 客户端
 * 处理前后端通信、认证、数据模型映射
 */

const API_BASE_URL = window.API_BASE_URL || '';

class APIError extends Error {
    constructor(code, message, statusCode, data = null) {
        super(message);
        this.name = 'APIError';
        this.code = code;
        this.statusCode = statusCode;
        this.data = data;
    }
}

class AuthManager {
    constructor() {
        this.tokenKey = 'ctai_auth_token';
        this.userKey = 'ctai_user';
    }

    getToken() {
        return localStorage.getItem(this.tokenKey);
    }

    setToken(token) {
        localStorage.setItem(this.tokenKey, token);
    }

    removeToken() {
        localStorage.removeItem(this.tokenKey);
        localStorage.removeItem(this.userKey);
    }

    getUser() {
        const userStr = localStorage.getItem(this.userKey);
        return userStr ? JSON.parse(userStr) : null;
    }

    setUser(user) {
        localStorage.setItem(this.userKey, JSON.stringify(user));
    }

    isAuthenticated() {
        return !!this.getToken();
    }

    clear() {
        this.removeToken();
    }
}

const authManager = new AuthManager();

const API = {
    baseUrl: API_BASE_URL,

    async request(endpoint, options = {}) {
        const url = `${this.baseUrl}${endpoint}`;
        const token = authManager.getToken();

        const defaultHeaders = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        };

        if (token) {
            defaultHeaders['Authorization'] = `Bearer ${token}`;
        }

        const config = {
            headers: {
                ...defaultHeaders,
                ...options.headers
            },
            ...options
        };

        if (config.body && typeof config.body === 'object' && !(config.body instanceof FormData)) {
            config.body = JSON.stringify(config.body);
        }

        if (config.body instanceof FormData) {
            delete config.headers['Content-Type'];
        }

        try {
            const response = await fetch(url, config);
            const contentType = response.headers.get('content-type');

            let data;
            if (contentType && contentType.includes('application/json')) {
                data = await response.json();
            } else {
                data = await response.text();
            }

            if (!response.ok) {
                const errorCode = data?.error || 'UNKNOWN_ERROR';
                const errorMessage = data?.message || data || '请求失败';

                if (response.status === 401) {
                    authManager.clear();
                    window.dispatchEvent(new CustomEvent('auth:expired'));
                }

                throw new APIError(errorCode, errorMessage, response.status, data);
            }

            return data;
        } catch (e) {
            if (e instanceof APIError) {
                throw e;
            }

            if (e instanceof TypeError && e.message.includes('fetch')) {
                throw new APIError('NETWORK_ERROR', '网络连接失败，请检查网络', 0);
            }

            throw new APIError('UNKNOWN_ERROR', e.message || '未知错误', 0);
        }
    },

    get(endpoint, params = {}) {
        const queryString = new URLSearchParams(params).toString();
        const url = queryString ? `${endpoint}?${queryString}` : endpoint;
        return this.request(url, { method: 'GET' });
    },

    post(endpoint, data = {}) {
        return this.request(endpoint, { method: 'POST', body: data });
    },

    put(endpoint, data = {}) {
        return this.request(endpoint, { method: 'PUT', body: data });
    },

    delete(endpoint, data = {}) {
        return this.request(endpoint, { method: 'DELETE', body: data });
    },

    async uploadFile(endpoint, file, additionalData = {}) {
        const formData = new FormData();
        formData.append('file', file);

        for (const [key, value] of Object.entries(additionalData)) {
            formData.append(key, value);
        }

        const token = authManager.getToken();
        const headers = {};
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        const response = await fetch(`${this.baseUrl}${endpoint}`, {
            method: 'POST',
            headers,
            body: formData
        });

        const data = await response.json();

        if (!response.ok) {
            throw new APIError(data.error || 'UPLOAD_ERROR', data.message || '上传失败', response.status);
        }

        return data;
    }
};

API.Auth = {
    async loginDoctor(employeeId, password) {
        const response = await API.post('/api/auth/login', {
            login_type: 'doctor',
            employee_id: employeeId,
            password: password
        });

        if (response.success && response.token) {
            authManager.setToken(response.token);
            authManager.setUser(response.user);
        }

        return response;
    },

    async loginPatient(phone, verifyCode) {
        const response = await API.post('/api/auth/login', {
            login_type: 'patient',
            phone: phone,
            verify_code: verifyCode
        });

        if (response.success && response.token) {
            authManager.setToken(response.token);
            authManager.setUser(response.user);
        }

        return response;
    },

    logout() {
        authManager.clear();
        window.location.href = '/login';
    },

    getUser() {
        return authManager.getUser();
    },

    isAuthenticated() {
        return authManager.isAuthenticated();
    }
};

API.CTImages = {
    async upload(file, checkPart) {
        return API.uploadFile('/api/ct-images', file, { check_part: checkPart });
    },

    async list() {
        return API.get('/api/ct-images');
    },

    async get(id) {
        return API.get(`/api/ct-images/${id}`);
    },

    async getProgress(id) {
        return API.get(`/api/ct-images/${id}/progress`);
    },

    async delete(id) {
        return API.delete(`/api/ct-images/${id}`);
    }
};

API.Annotations = {
    async createSet(data) {
        return API.post('/api/annotation/sets', data);
    },

    async getSet(setId) {
        return API.get(`/api/annotation/sets/${setId}`);
    },

    async listSets() {
        return API.get('/api/annotation/sets');
    },

    async deleteSet(setId) {
        return API.delete(`/api/annotation/sets/${setId}`);
    },

    async createAnnotation(setId, data) {
        return API.post(`/api/annotation/sets/${setId}/annotations`, data);
    },

    async updateAnnotation(setId, annoId, data) {
        return API.put(`/api/annotation/sets/${setId}/annotations/${annoId}`, data);
    },

    async deleteAnnotation(setId, annoId) {
        return API.delete(`/api/annotation/sets/${setId}/annotations/${annoId}`);
    },

    async confirmAnnotation(setId, annoId) {
        return API.post(`/api/annotation/sets/${setId}/annotations/${annoId}/confirm`);
    },

    async getBySlice(setId, sliceIndex) {
        return API.get(`/api/annotation/sets/${setId}/slices/${sliceIndex}`);
    },

    async export(setId, format = 'json') {
        return API.get(`/api/annotation/sets/${setId}/export?format=${format}`);
    }
};

API.SAM3D = {
    async healthCheck() {
        return API.get('/api/sam3d/health');
    },

    async getModelInfo() {
        return API.get('/api/sam3d/model-info');
    },

    async infer(data) {
        return API.post('/api/sam3d/infer', data);
    },

    async inferSimple(data) {
        return API.post('/api/sam3d/infer-simple', data);
    },

    async batchInfer(tasks) {
        return API.post('/api/sam3d/batch-infer', { tasks });
    },

    async setup(checkpointPath) {
        return API.post('/api/sam3d/setup', { checkpoint_path: checkpointPath });
    }
};

API.Messages = {
    async list() {
        return API.get('/api/messages');
    },

    async send(toUserId, content) {
        return API.post('/api/messages', { to_user_id: toUserId, content });
    },

    async getConversation(userId) {
        return API.get(`/api/messages/${userId}`);
    }
};

const CTApiClient = {
    async createAnnotation(setId, data) {
        return API.Annotations.createAnnotation(setId, data);
    },

    async getAnnotationSet(setId) {
        return API.Annotations.getSet(setId);
    },

    async updateAnnotation(setId, annoId, data) {
        return API.Annotations.updateAnnotation(setId, annoId, data);
    },

    async deleteAnnotation(setId, annoId) {
        return API.Annotations.deleteAnnotation(setId, annoId);
    },

    async confirmAnnotation(setId, annoId) {
        return API.Annotations.confirmAnnotation(setId, annoId);
    },

    async exportAnnotationSet(setId, format) {
        return API.Annotations.export(setId, format);
    },

    async listAnnotationSets() {
        return API.Annotations.listSets();
    },

    async createAnnotationSet(data) {
        return API.Annotations.createSet(data);
    },

    async deleteAnnotationSet(setId) {
        return API.Annotations.deleteSet(setId);
    }
};

window.API = API;
window.APIError = APIError;
window.authManager = authManager;
window.CTApiClient = CTApiClient;
