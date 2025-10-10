import axios from 'axios';
import { apiCache, CACHE_CONFIGS, invalidateCache } from './apiCache';

// API base URL with intelligent defaults
function getApiBaseUrl() {
  // 1) Explicit configuration via global/window or localStorage
  const raw =
    (typeof window !== 'undefined' && window.mimirApiBaseUrl) ||
    (typeof localStorage !== 'undefined' && localStorage.getItem('mimir-api-base-url'));

  if (raw) {
    return ensureApiSuffix(raw);
  }

  // 2) Smart fallback based on current environment
  if (typeof window !== 'undefined' && window.location) {
    const { hostname, origin, port, protocol } = window.location;
    const isLocalhost = hostname === 'localhost' || hostname === '127.0.0.1';
    const devPorts = new Set(['3000', '5173', '8080']); // common dev servers

    // Prefer same-origin /api ONLY when we're on HTTPS (avoids mixed-content and supports reverse proxy)
    if (!isLocalhost && !devPorts.has(port)) {
      if (protocol === 'https:') {
        return ensureApiSuffix(origin);
      }
      // On plain HTTP with no explicit dev port, default to backend :5000
      return `http://${hostname}:5000/api`;
    }

    // If on dev ports but not localhost (e.g., phone hitting http://<LAN-IP>:3000), use that host on :5000 (http)
    if (!isLocalhost && devPorts.has(port)) {
      return 'http://' + hostname + ':5000/api';
    }

    // Localhost dev
    return 'http://localhost:5000/api';
  }

  // 3) Final static fallback (can be overridden in Settings)
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
  // NOTE: deactivateScene / displayScene endpoints do not exist in current API.
  // Provide graceful fallbacks so existing callers don't break.
  deactivateScene: (sceneId) => {
    console.warn('deactivateScene endpoint not implemented on server; no-op');
    return Promise.resolve({ data: { message: 'deactivate not implemented' } });
  },
  // Treat displayScene as activateScene for now (legacy alias in UI code)
  displayScene: (sceneId) => apiClient.post(`/scenes/${sceneId}/activate`),

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
  
  getChannelManifest: async (channelId) => {
    const key = apiCache.generateKey(`/channels/${channelId}/manifest`);
    const cached = apiCache.get(key);
    if (cached) {
      console.log(`📋 Cache hit: ${key}`);
      return cached;
    }
    
    const result = await apiClient.get(`/channels/${channelId}/manifest`);
    apiCache.set(key, result, CACHE_CONFIGS.CHANNELS.ttl);
    console.log(`💾 Cached: ${key}`);
    return result;
  },
  
  // Convenience helper (plural) requested by some callers: aggregate manifests for supplied or all channels
  // If channelIds omitted, will first fetch channel list then resolve each manifest.
  getChannelsManifest: async (channelIds = null) => {
    try {
      let ids = channelIds;
      if (!ids) {
        const listResp = await api.getChannels();
        ids = (listResp.data?.channels || []).map(c => c.id || c.channel_id || c.identifier).filter(Boolean);
      }
      const manifests = {};
      for (const id of ids) {
        try {
          const resp = await api.getChannelManifest(id);
            // Use .data fallback; axios response holds payload in data
          manifests[id] = resp.data || resp;
        } catch (e) {
          console.warn(`⚠️ Failed to fetch manifest for channel ${id}:`, e?.response?.status, e?.message);
          manifests[id] = { error: true, message: 'manifest_unavailable', detail: e?.message };
        }
      }
      return { data: manifests };
    } catch (outer) {
      console.error('Failed aggregating channel manifests', outer);
      throw outer;
    }
  },
  
  getChannelSettings: (channelId) => apiClient.get(`/channels/${channelId}/settings`),
  updateChannelSettings: (channelId, settings) => apiClient.post(`/channels/${channelId}/settings`, settings),
  requestChannelImage: async (channelId, requestData = {}) => {
    // Prefer hyphenated endpoint; backend accepts both hyphen and underscore for compatibility
    const resp = await apiClient.post(`/channels/${channelId}/request-image`, requestData || {});
    // Normalize response so callers always have an imageUrl and optional dataUrl
    const payload = resp.data || {};
    const { imageUrl, imageId, contentType, legacyBase64 } = payload;
    let dataUrl = null;
    if (legacyBase64) {
      // Provide a proper data URL for components that expect embeddable image
      dataUrl = `data:${contentType || 'image/jpeg'};base64,${legacyBase64}`;
    }
    return {
      raw: resp,
      imageId,
      imageUrl: imageUrl ? `${imageUrl}${imageUrl.includes('?') ? '&' : '?'}t=${Date.now()}` : null,
      contentType: contentType || 'image/jpeg',
      dataUrl,
    };
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

  // Display
  getDisplayStatus: () => apiClient.get('/displays/status'),
  clearDisplay: () => apiClient.post('/display/clear'),

  // v2.1 Channel System (Updated for embedded plugin architecture)
  // Note: /channels/manifest endpoint doesn't exist - use individual channel manifests
  // Unsupported / legacy channel endpoints retained as safe warnings
  testChannel: (() => {
    let warned = false;
    return (channelId) => {
      if (!warned) {
        console.warn('testChannel endpoint not implemented for embedded plugins (suppressing further warnings)');
        warned = true;
      }
      return Promise.resolve({ data: { message: 'testChannel not implemented' } });
    };
  })(),
  getChannelHealth: (channelId) => apiClient.get(`/channels/${channelId}/health`),
  getChannelToken: (channelId) => {
    console.warn('getChannelToken endpoint not implemented');
    return Promise.resolve({ data: { token: null } });
  },

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
  getChannelImageUrl: (channelId, imagePath = 'image') => {
    // If caller accidentally passes raw base64 (or data URI), convert to a usable data URL instead of generating a gigantic path.
    if (typeof imagePath === 'string') {
      const trimmed = imagePath.trim();
      const looksBase64 = /^[A-Za-z0-9+/]+=*$/.test(trimmed.slice(0, 120)) && trimmed.length > 200; // heuristic
      const isDataUri = trimmed.startsWith('data:image');
      if (isDataUri) {
        return trimmed; // already data URI
      }
      if (looksBase64) {
        // Assume JPEG if we cannot sniff. Provide data URL.
        return `data:image/jpeg;base64,${trimmed}`;
      }
    }
    return `${getApiBaseUrl()}/channels/${channelId}/${imagePath}?t=${Date.now()}`;
  },
  
  // Helper function to get API base URL (useful for components)
  getApiBaseUrl: () => getApiBaseUrl(),

  // v2.3: Display Management API endpoints
  registerDisplay: (displayData) => apiClient.post('/displays/register', displayData),
  getDisplays: (params = {}) => apiClient.get('/displays', { params }),
  unassignSceneFromDisplay: (displayId) => apiClient.delete(`/displays/${encodeURIComponent(displayId)}/scene`),
  getUnassignedDisplays: (includeDiscovered = true) => apiClient.get('/displays/unassigned', { params: { include_discovered: includeDiscovered } }),
  getDisplayDetails: (displayId) => apiClient.get(`/displays/${displayId}`),
  getDiscoveredDisplayAssignments: (displayId) => apiClient.get(`/displays/${displayId}/scene`),
  assignSceneToDisplay: (displayId, sceneId, subchannelId = null) => {
    const payload = { scene_id: sceneId };
    if (subchannelId) {
      payload.subchannel_id = subchannelId;
    }
    return apiClient.post(`/displays/${encodeURIComponent(displayId)}/scene`, payload);
  },

  // Enhanced Display Scene Management (handles both registered and discovered)
  getDisplaysForScene: (sceneId) => apiClient.get(`/display-scene/scenes/${sceneId}/displays`),
  getSceneDisplayStats: (sceneId) => apiClient.get(`/display-scene/scene/${sceneId}/stats`),
  getScenesWithDisplayStats: () => apiClient.get('/display-scene/scenes/with-displays'),
  getAssignmentStatus: (sceneId) =>  apiClient.get('/display-scene/assignments/status', { params: { scene_id: sceneId } }),
  
  // Discovery API endpoints
  getDiscoveryStatus: () => apiClient.get('/displays/discovery/status'),
  startDiscovery: () => apiClient.post('/displays/discovery/start'),
  stopDiscovery:  () => apiClient.post('/displays/discovery/stop'),
  getLiveDiscoveredDisplays: () => apiClient.get('/displays/discovery/live'),
  getDiscoveredDisplays: () => apiClient.get('/displays/discover'),
  getDisplayImage: (displayId, headers = {}) => apiClient.get(`/displays/${displayId}/current-image`, { headers }),
  getDisplayImageFile: (displayId) => apiClient.get(`/displays/${displayId}/current_image_file`, { responseType: 'blob' }),
  // Persisted last-image endpoints (v2.5 persistence layer)
  getPersistedLastImage: (displayId, sceneId, subchannelId = null) => {
    const params = {};
    if (subchannelId) params.subchannel_id = subchannelId;
    return apiClient.get(`/displays/${encodeURIComponent(displayId)}/scenes/${encodeURIComponent(sceneId)}/last-image`, { params });
  },
  getPersistedLastImagesForDisplay: (displayId, limitPerScene = 1) =>
    apiClient.get(`/displays/${encodeURIComponent(displayId)}/last-images`, { params: { limit_per_scene: limitPerScene } }),
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
  // Discovery approval actions
  approveDiscoveredDisplay: (deviceId) => apiClient.post(`/displays/discovery/${encodeURIComponent(deviceId)}/approve`),
  rejectDiscoveredDisplay: (deviceId) => apiClient.post(`/displays/discovery/${encodeURIComponent(deviceId)}/reject`),

  // Helper function for display image URLs
  getDisplayImageUrl: (displayId) => `${getApiBaseUrl()}/displays/${displayId}/current_image_file`,

  // v2.4: Admin Operations
  reloadChannels: () => apiClient.post('/admin/channels/reload'),
  getOrphanedChannels: () => apiClient.get('/admin/channels/orphaned'),
  removeChannelFromDatabase: (channelId) => apiClient.delete(`/admin/channels/${channelId}`),
  resetChannelsDatabase: () => apiClient.post('/admin/channels/reset'),

  // Distribution System Operations
  getDistributionOverview: () => apiClient.get('/admin/distribution/overview'),
  refreshSceneContent: (sceneId) => apiClient.post(`/scenes/${sceneId}/refresh_content`),
  resetSceneDistribution: (sceneId) => apiClient.post(`/scenes/${sceneId}/reset_distribution`),
  getSceneContentInfo: (sceneId) => apiClient.get(`/scenes/${sceneId}/content_info`),
  updateSceneDistributionMode: async (sceneId, distributionMode) => {
    // Get current scene data first
    const sceneResponse = await apiClient.get(`/scenes/${sceneId}`);
    const currentScene = sceneResponse.data;
    
    // Update the scene with new distribution mode
    return apiClient.put(`/scenes/${sceneId}`, {
      ...currentScene,
      distribution_mode: distributionMode
    });
  },
  getRedisStatus: () => apiClient.get('/admin/redis/status'),
  cleanupRedis: () => apiClient.post('/admin/redis/cleanup'),

  // Overlays (newly wired to backend overlays router)
  listOverlays: (params = {}) => apiClient.get('/overlays', { params }),
  getOverlay: (overlayId) => apiClient.get(`/overlays/${overlayId}`),
  createOverlay: (overlay) => apiClient.post('/overlays', overlay),
  updateOverlay: (overlayId, data) => apiClient.put(`/overlays/${overlayId}`, data),
  deleteOverlay: (overlayId) => apiClient.delete(`/overlays/${overlayId}`),

  // Health & metrics helpers
  getHealth: () => apiClient.get('/health'),
  getPrometheusMetrics: () => apiClient.get('/admin/metrics'),

  // Display Content Claims (for testing distribution)
  claimContent: (displayId) => apiClient.post(`/displays/${displayId}/claim_content`),
  acknowledgeCompletion: (displayId, assignmentId) => 
    apiClient.post(`/displays/${displayId}/acknowledge_completion`, { assignment_id: assignmentId }),

  // Scheduler API endpoints
  getSchedulerJobs: (params = {}) => apiClient.get('/scheduler/jobs', { params }),
  getSchedulerJob: (jobId) => apiClient.get(`/scheduler/jobs/${jobId}`),
  createSchedulerJob: (jobData) => apiClient.post('/scheduler/jobs', jobData),
  updateSchedulerJob: (jobId, updates) => apiClient.put(`/scheduler/jobs/${jobId}`, updates),
  deleteSchedulerJob: (jobId) => apiClient.delete(`/scheduler/jobs/${jobId}`),
  triggerSchedulerJob: (jobId, reason = 'Manual trigger') => 
    apiClient.post(`/scheduler/jobs/${jobId}/trigger`, { reason }),
  enableSchedulerJob: (jobId) => apiClient.post(`/scheduler/jobs/${jobId}/enable`),
  disableSchedulerJob: (jobId) => apiClient.post(`/scheduler/jobs/${jobId}/disable`),
  getSchedulerStats: () => apiClient.get('/scheduler/stats'),
  getSchedulerExecutions: (params = {}) => apiClient.get('/scheduler/executions', { params }),
  
  // Scene-specific scheduler helpers
  getSceneSchedules: (sceneId) => apiClient.get(`/scheduler/scenes/${sceneId}/jobs`),
  createSceneSchedule: (sceneId, scheduleData) => {
    const jobData = {
      ...scheduleData,
      action_type: 'refresh_scene',
      scene_ids: [sceneId]
    };
    return apiClient.post('/scheduler/jobs', jobData);
  },
  updateSceneSchedule: (jobId, scheduleData) => {
    return apiClient.put(`/scheduler/jobs/${jobId}`, scheduleData);
  },
  deleteSceneSchedule: (jobId) => apiClient.delete(`/scheduler/jobs/${jobId}`),

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
