import axios from 'axios';

// API base URL
const API_BASE_URL = 'http://172.31.79.107:5000/api';

// Create axios instance with default config
const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 10000,
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
  getChannelUIAsset: (channelId, assetPath) => `${API_BASE_URL}/channels/${channelId}/ui/${assetPath}`,
  getChannelAsset: (channelId, assetPath) => `${API_BASE_URL}/channels/${channelId}/assets/${assetPath}`,

  // v2.3: Display Management API endpoints
  registerDisplay: (displayData) => apiClient.post('/displays/register', displayData),
  getDisplays: (params = {}) => apiClient.get('/displays', { params }),
  assignSceneToDisplay: (displayId, sceneId) => apiClient.post(`/displays/${displayId}/assign_scene`, { scene_id: sceneId }),
  unassignSceneFromDisplay: (displayId) => apiClient.delete(`/displays/${displayId}/assign_scene`),
  getDisplayImage: (displayId) => apiClient.get(`/displays/${displayId}/current_image`),
  getDisplayImageFile: (displayId) => apiClient.get(`/displays/${displayId}/current_image_file`, { responseType: 'blob' }),
  updateDisplay: (displayId, updates) => apiClient.put(`/displays/${displayId}`, updates),
  deleteDisplay: (displayId) => apiClient.delete(`/displays/${displayId}`),

  // Helper function for display image URLs
  getDisplayImageUrl: (displayId) => `${API_BASE_URL}/displays/${displayId}/current_image_file`,
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
