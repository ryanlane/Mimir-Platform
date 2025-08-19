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
