import axios from 'axios';

// API base URL
function getApiBaseUrl() {
  const raw =
    (typeof window !== 'undefined' && window.mimirApiBaseUrl) ||
    localStorage.getItem('mimir-api-base-url');

  // Fallback includes /api already
  if (!raw) return 'http://172.31.79.107:5000/api';
  return ensureApiSuffix(raw);
}

function ensureApiSuffix(base) {
  try {
    // Handle absolute or relative bases
    const u = new URL(base, window.location.origin);

    // Normalize trailing slashes
    u.pathname = u.pathname.replace(/\/+$/, '') || '/';

    // If path doesn't already start with /api, append it
    if (!/^\/api(\/|$)/i.test(u.pathname)) {
      u.pathname = (u.pathname === '/' ? '' : u.pathname) + '/api';
    }
    return u.toString();
  } catch {
    // Fallback for unusual inputs
    const t = String(base).replace(/\/+$/, '');
    return /\/api(\/|$)/i.test(t) ? t : `${t}/api`;
  }
}

// Create axios instance with default config
let apiClient = axios.create({
  baseURL: getApiBaseUrl(),
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 10000,
});

// Listen for changes to API base URL and update axios instance
window.addEventListener('storage', (e) => {
  if (e.key === 'mimir-api-base-url') {
    apiClient = axios.create({
      baseURL: getApiBaseUrl(),
      headers: { 'Content-Type': 'application/json' },
      timeout: 10000,
    });
  }
});

// API service methods
export const api = {
  // Scenes
  getScenes: (params = {}) => apiClient.get('/scenes', { params }),
  getScene: (sceneId) => apiClient.get(`/scenes/${sceneId}`),
  createScene: (sceneData) => apiClient.post('/scenes', sceneData),
  updateScene: (sceneId, sceneData) => apiClient.put(`/scenes/${sceneId}`, sceneData),
  deleteScene: (sceneId) => apiClient.delete(`/scenes/${sceneId}`),
  activateScene: (sceneId) => apiClient.post(`/scenes/${sceneId}/activate`),
  deactivateScene: (sceneId) => apiClient.post(`/scenes/${sceneId}/deactivate`),
  displayScene: (sceneId) => apiClient.post(`/scenes/${sceneId}/display`),

  // Channels
  getChannels: (params = {}) => apiClient.get('/channels', { params }),
  getChannelConfig: (channelId) => apiClient.get(`/channels/${channelId}/config`),
  getChannelSettings: (channelId) => apiClient.get(`/channels/${channelId}/settings`),
  updateChannelSettings: (channelId, settings) => apiClient.post(`/channels/${channelId}/settings`, settings),
  requestChannelImage: (channelId, requestData) => apiClient.post(`/channels/${channelId}/image_request`, requestData),

  // Overlays
  getOverlays: (params = {}) => apiClient.get('/overlays', { params }),

  // Display
  getDisplayStatus: () => apiClient.get('/display/status'),
  clearDisplay: () => apiClient.post('/display/clear'),

  // v2.1 Channel System
  getChannelsManifest: () => apiClient.get('/channels/manifest'),
  testChannel: (channelId) => apiClient.post(`/channels/${channelId}/test`),
  getChannelHealth: (channelId) => apiClient.get(`/channels/${channelId}/health`),
  getChannelToken: (channelId) => apiClient.get(`/channels/${channelId}/token`),

  // v2.1 WebSocket Status
  getWebSocketStatus: () => apiClient.get('/websocket/status'),

  // v2.1 Dynamic Channel APIs
  callChannelAPI: (channelId, endpoint, method = 'GET', data = null, params = {}) => {
    const url = `/channels/${channelId}/${endpoint}`;
    const config = { params };
    
    switch (method.toUpperCase()) {
      case 'GET':
        return apiClient.get(url, config);
      case 'POST':
        return apiClient.post(url, data, config);
      case 'PUT':
        return apiClient.put(url, data, config);
      case 'DELETE':
        return apiClient.delete(url, config);
      default:
        throw new Error(`Unsupported HTTP method: ${method}`);
    }
  },

  // v2.1 Channel Static Assets
  getChannelUIAsset: (channelId, assetPath) => `${getApiBaseUrl()}/channels/${channelId}/ui/${assetPath}`,
  getChannelAsset: (channelId, assetPath) => `${getApiBaseUrl()}/channels/${channelId}/assets/${assetPath}`,

  // v2.3: Display Management API endpoints
  registerDisplay: (displayData) => apiClient.post('/displays/register', displayData),
  getDisplays: (params = {}) => apiClient.get('/displays', { params }),
  assignSceneToDisplay: (displayId, sceneId) => apiClient.post(`/displays/${displayId}/assign_scene`, { scene_id: sceneId }),
  unassignSceneFromDisplay: (displayId) => apiClient.delete(`/displays/${displayId}/assign_scene`),
  getDisplayImage: (displayId, headers = {}) => apiClient.get(`/displays/${displayId}/current-image`, { headers }),
  getDisplayImageFile: (displayId) => apiClient.get(`/displays/${displayId}/current_image_file`, { responseType: 'blob' }),
  // Enhanced display image polling with ETag support
  pollDisplayImage: async (displayId, currentETag = null) => {
    const headers = {};
    if (currentETag) {
      headers['If-None-Match'] = currentETag;
    }
    
    try {
      const response = await apiClient.get(`/displays/${displayId}/current-image`, { headers });
      return {
        changed: true,
        data: response.data,
        etag: response.headers['etag'] || response.headers['ETag'],
        status: response.status
      };
    } catch (error) {
      if (error.response?.status === 304) {
        return {
          changed: false,
          etag: currentETag,
          status: 304
        };
      }
      throw error;
    }
  },
  generateDisplayImage: (displayId) => apiClient.post(`/displays/${displayId}/generate-image`),
  updateDisplay: (displayId, updates) => apiClient.put(`/displays/${displayId}`, updates),
  deleteDisplay: (displayId) => apiClient.delete(`/displays/${displayId}`),

  // Helper function for display image URLs
  getDisplayImageUrl: (displayId) => `${getApiBaseUrl()}/displays/${displayId}/current_image_file`,

  // v2.4: Admin Operations
  reloadChannels: () => apiClient.post('/admin/reload-channels'),
  getOrphanedChannels: () => apiClient.get('/admin/channels/orphaned'),
  removeChannelFromDatabase: (channelId) => apiClient.delete(`/admin/channels/${channelId}`),
  resetChannelsDatabase: () => apiClient.post('/admin/channels/reset'),
};

// Request interceptor for logging
apiClient.interceptors.request.use(
  (config) => {
    console.log(`🚀 API Request: ${config.method?.toUpperCase()} ${config.url}`);
    return config;
  },
  (error) => {
    console.error('❌ Request Error:', error);
    return Promise.reject(error);
  }
);

// Response interceptor for error handling
apiClient.interceptors.response.use(
  (response) => {
    console.log(`✅ API Response: ${response.status} ${response.config.url}`);
    return response;
  },
  (error) => {
    console.error('❌ Response Error:', error.response?.data || error.message);
    return Promise.reject(error);
  }
);

export default api;
