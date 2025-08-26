import axios from 'axios';
import { apiCache, CACHE_CONFIGS, invalidateCache } from './apiCache';

// API base URL with intelligent defaults
function getApiBaseUrl() {
  // 1. Check for explicit configuration
  const raw =
    (typeof window !== 'undefined' && window.mimirApiBaseUrl) ||
    localStorage.getItem('mimir-api-base-url');

  if (raw) {
    return ensureApiSuffix(raw);
  }

  // 2. Smart fallback based on current environment
  if (typeof window !== 'undefined') {
    const currentHost = window.location.hostname;
    const currentProtocol = window.location.protocol;
    
    // If we're running on localhost (development), use localhost
    if (currentHost === 'localhost' || currentHost === '127.0.0.1') {
      return 'http://localhost:5000/api';
    }
    
    // If we're running on the same host as the UI, use the same host
    if (currentHost && currentHost !== 'localhost') {
      return `${currentProtocol}//${currentHost}:5000/api`;
    }
  }

  // 3. Final fallback for specific deployment
  return 'http://172.31.79.107:5000/api';
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

  // Channels with caching
  getChannels: async (params = {}) => {
    const key = apiCache.generateKey('/channels', params);
    const cached = apiCache.get(key);
    if (cached) {
      console.log(`📋 Cache hit: ${key}`);
      return cached;
    }
    
    const result = await apiClient.get('/channels', { params });
    apiCache.set(key, result, CACHE_CONFIGS.CHANNELS.ttl);
    console.log(`💾 Cached: ${key}`);
    return result;
  },

  getChannelConfig: async (channelId) => {
    const key = apiCache.generateKey(`/channels/${channelId}/config`);
    const cached = apiCache.get(key);
    if (cached) {
      console.log(`📋 Cache hit: ${key}`);
      return cached;
    }
    
    const result = await apiClient.get(`/channels/${channelId}/config`);
    apiCache.set(key, result, CACHE_CONFIGS.CHANNELS.ttl);
    console.log(`💾 Cached: ${key}`);
    return result;
  },
  getChannelSettings: (channelId) => apiClient.get(`/channels/${channelId}/settings`),
  updateChannelSettings: (channelId, settings) => apiClient.post(`/channels/${channelId}/settings`, settings),
  requestChannelImage: (channelId, requestData, subchannelId = null) => {
    const params = subchannelId ? { subchannel_id: subchannelId } : {};
    return apiClient.post(`/channels/${channelId}/image_request`, requestData, { params });
  },

  // Sub-Channels (NEW) with Performance Caching
  getSubChannelConfig: async (channelId, includeSubchannels = false) => {
    const params = includeSubchannels ? '?include_subchannels=true' : '';
    const key = apiCache.generateKey(`/channels/${channelId}/subchannels/config${params}`);
    const cached = apiCache.get(key);
    if (cached) {
      console.log(`📋 Cache hit: ${key}`);
      return cached;
    }
    
    const result = await apiClient.get(`/channels/${channelId}/subchannels/config${params}`);
    apiCache.set(key, result, CACHE_CONFIGS.SUB_CHANNEL_CONFIG.ttl);
    console.log(`💾 Cached: ${key}`);
    return result;
  },

  getSubChannels: async (channelId) => {
    const key = apiCache.generateKey(`/channels/${channelId}/subchannels`);
    const cached = apiCache.get(key);
    if (cached) {
      console.log(`📋 Cache hit: ${key}`);
      return cached;
    }
    
    const result = await apiClient.get(`/channels/${channelId}/subchannels`);
    apiCache.set(key, result, CACHE_CONFIGS.SUB_CHANNELS.ttl);
    console.log(`💾 Cached: ${key}`);
    return result;
  },

  getSubChannelDetails: async (channelId, subChannelId) => {
    const key = apiCache.generateKey(`/channels/${channelId}/subchannels/${subChannelId}`);
    const cached = apiCache.get(key);
    if (cached) {
      console.log(`📋 Cache hit: ${key}`);
      return cached;
    }
    
    const result = await apiClient.get(`/channels/${channelId}/subchannels/${subChannelId}`);
    apiCache.set(key, result, CACHE_CONFIGS.SUB_CHANNEL_DETAILS.ttl);
    console.log(`💾 Cached: ${key}`);
    return result;
  },

  createSubChannel: async (channelId, data) => {
    const result = await apiClient.post(`/channels/${channelId}/subchannels`, data);
    // Invalidate related caches
    invalidateCache([
      `/channels/${channelId}/subchannels`,
      `/channels/${channelId}/subchannels/config`
    ]);
    return result;
  },

  updateSubChannel: async (channelId, subChannelId, data) => {
    const result = await apiClient.put(`/channels/${channelId}/subchannels/${subChannelId}`, data);
    // Invalidate related caches
    invalidateCache([
      `/channels/${channelId}/subchannels`,
      `/channels/${channelId}/subchannels/${subChannelId}`
    ]);
    return result;
  },

  deleteSubChannel: async (channelId, subChannelId) => {
    const result = await apiClient.delete(`/channels/${channelId}/subchannels/${subChannelId}`);
    // Invalidate related caches
    invalidateCache([
      `/channels/${channelId}/subchannels`,
      `/channels/${channelId}/subchannels/${subChannelId}`
    ]);
    return result;
  },

  assignContentToSubChannel: async (channelId, subChannelId, contentIds, action = 'add') => {
    const result = await apiClient.post(`/channels/${channelId}/subchannels/${subChannelId}/content`, {
      contentIds,
      action
    });
    // Invalidate sub-channel details cache as content assignment changes
    invalidateCache([
      `/channels/${channelId}/subchannels/${subChannelId}`,
      `/channels/${channelId}/subchannels`
    ]);
    return result;
  },

  getSubChannelContent: async (channelId, subChannelId) => {
    const key = apiCache.generateKey(`/channels/${channelId}/subchannels/${subChannelId}/content`);
    const cached = apiCache.get(key);
    if (cached) {
      console.log(`📋 Cache hit: ${key}`);
      return cached;
    }
    
    const result = await apiClient.get(`/channels/${channelId}/subchannels/${subChannelId}/content`);
    apiCache.set(key, result, CACHE_CONFIGS.CONTENT.ttl);
    console.log(`💾 Cached: ${key}`);
    return result;
  },

  reorderSubChannelImages: async (channelId, subChannelId, draggedId, targetId) => {
    const result = await apiClient.post(`/channels/${channelId}/subchannels/${subChannelId}/images/reorder`, {
      dragged_id: draggedId,
      target_id: targetId
    });
    // Invalidate sub-channel content cache as order changes
    const contentKey = apiCache.generateKey(`/channels/${channelId}/subchannels/${subChannelId}/content`);
    const subChannelKey = apiCache.generateKey(`/channels/${channelId}/subchannels/${subChannelId}`);
    apiCache.delete(contentKey);
    apiCache.delete(subChannelKey);
    console.log(`🗑️ Cache invalidated: ${contentKey}, ${subChannelKey}`);
    return result;
  },

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
  getChannelImageUrl: (channelId, imagePath = 'image') => `${getApiBaseUrl()}/channels/${channelId}/${imagePath}?t=${Date.now()}`,
  
  // Helper function to get API base URL (useful for components)
  getApiBaseUrl: () => getApiBaseUrl(),

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

  // Distribution System Operations
  getDistributionOverview: () => apiClient.get('/admin/distribution/overview'),
  refreshSceneContent: (sceneId) => apiClient.post(`/scenes/${sceneId}/refresh_content`),
  resetSceneDistribution: (sceneId) => apiClient.post(`/scenes/${sceneId}/reset_distribution`),
  getSceneContentInfo: (sceneId) => apiClient.get(`/scenes/${sceneId}/content_info`),
  getRedisStatus: () => apiClient.get('/admin/redis/status'),
  cleanupRedis: () => apiClient.post('/admin/redis/cleanup'),

  // Display Content Claims (for testing distribution)
  claimContent: (displayId) => apiClient.post(`/displays/${displayId}/claim_content`),
  acknowledgeCompletion: (displayId, assignmentId) => 
    apiClient.post(`/displays/${displayId}/acknowledge_completion`, { assignment_id: assignmentId }),

  // Cache Management Utilities
  cache: {
    clear: () => {
      apiCache.clear();
      console.log('🗑️ All API cache cleared');
    },
    invalidate: (patterns) => {
      invalidateCache(patterns);
      console.log('🗑️ Cache invalidated for patterns:', patterns);
    },
    stats: () => apiCache.getStats(),
    get: (key) => apiCache.get(key),
    delete: (key) => {
      apiCache.delete(key);
      console.log('🗑️ Cache deleted for key:', key);
    }
  }
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
