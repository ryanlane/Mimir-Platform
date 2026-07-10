// Copyright (C) 2026 Ryan Lane
//
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU Affero General Public License as published
// by the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
// GNU Affero General Public License for more details.
//
// You should have received a copy of the GNU Affero General Public License
// along with this program. If not, see <https://www.gnu.org/licenses/>.

// Multi-Display Management page for v2.3 API
import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { Monitor, Search, Filter, MapPin, Wifi, WifiOff, RotateCcw, X, Layers, Link2, Plus, Globe } from 'lucide-react';
import { api } from '../../services/api';
import { getApiBaseUrl, getServerBaseUrlFromApiBase } from '../../services/runtimeUrls';

import { useFeatureDetection } from '../../hooks/useFeatureDetection';
import { useWebSocket } from '../../hooks/useWebSocket';
import featureDetection from '../../services/featureDetection';
import DisplayCard from './DisplayCard';
import PullToRefresh from '../../components/PullToRefresh/PullToRefresh';
import SceneAssignment from './SceneAssignment';
import DisplayPairing from '../../components/DisplayPairing/DisplayPairing';
import DebugPanel from '../../components/DebugPanel/DebugPanel';
import Modal from '../../components/Modal/Modal';
import './Displays.css';
import Header from '../../components/Header/Header';
import { SkeletonScreenCard } from '../../components/Skeleton/Skeleton';
import Button from '../../components/Button/Button';
import { formatOrientationLabel, getOrientationOptionsForDisplay, normalizeOrientationValue } from './orientationOptions';

// Web Screen pages are served by the API (and proxied by nginx in prod) —
// never by the React dev server, so the URL must use the server origin,
// not window.location.origin.
const webScreenUrl = (webPath) => `${getServerBaseUrlFromApiBase(getApiBaseUrl())}${webPath}`;

// Global cache for displays data to prevent excessive API requests
let displaysCache = null;
let displaysCacheTime = null;
const DISPLAYS_CACHE_TIMEOUT = 30 * 1000; // 30 seconds

function formatRelativeTs(ts) {
  if (!ts) return null;
  const n = typeof ts === 'number' ? (ts < 1e12 ? ts * 1000 : ts) : Date.parse(ts);
  if (isNaN(n)) return null;
  const diff = Math.round((Date.now() - n) / 1000);
  if (diff < 5) return 'just now';
  if (diff < 60) return `${diff}s ago`;
  const m = Math.round(diff / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.round(h / 24)}d ago`;
}

const ScreenDetailPanel = ({ display, onClose, onAssignScene, onOpenSettings }) => {
  const sceneName = display.assigned_scene_name || display.assignedSceneName;
  const resolution = display.resolution && Array.isArray(display.resolution) && display.resolution.length >= 2
    ? `${display.resolution[0]}×${display.resolution[1]}`
    : display.width && display.height
    ? `${display.width}×${display.height}`
    : null;

  return (
    <aside className="screen-detail-panel">
      <div className="screen-detail-header">
        <div className="screen-detail-title-row">
          <span className={`screen-detail-status-dot ${display.is_online ? 'online' : 'offline'}`} />
          <h2 className="screen-detail-name">{display.name}</h2>
          <button className="screen-detail-close" onClick={onClose} aria-label="Close panel">
            <X size={14} />
          </button>
        </div>
        {display.location && (
          <div className="screen-detail-location">
            <MapPin size={12} />
            {display.location}
          </div>
        )}
      </div>

      <div className="screen-detail-section">
        <div className="screen-detail-section-label">PROGRAM</div>
        {sceneName ? (
          <div className="screen-detail-program">
            <Layers size={14} />
            <span className="screen-detail-program-name">{sceneName}</span>
          </div>
        ) : (
          <div className="screen-detail-no-program">No program assigned</div>
        )}
        <Button
          variant="primary"
          onClick={onAssignScene}
          className="screen-detail-assign-btn"
        >
          {sceneName ? 'Change Program →' : 'Assign Program →'}
        </Button>
      </div>

      <div className="screen-detail-section">
        <div className="screen-detail-section-label">DETAILS</div>
        <div className="screen-detail-rows">
          <div className="screen-detail-row">
            <span>Status</span>
            <span className={display.is_online ? 'screen-detail-val--online' : 'screen-detail-val--offline'}>
              {display.is_online ? 'Online' : 'Offline'}
            </span>
          </div>
          {resolution && (
            <div className="screen-detail-row">
              <span>Resolution</span>
              <span>{resolution}</span>
            </div>
          )}
          {display.orientation && (
            <div className="screen-detail-row">
              <span>Orientation</span>
              <span style={{ textTransform: 'capitalize' }}>{display.orientation}</span>
            </div>
          )}
          {display.last_seen && (
            <div className="screen-detail-row">
              <span>Last seen</span>
              <span>{formatRelativeTs(display.last_seen)}</span>
            </div>
          )}
          {display.displayType && (
            <div className="screen-detail-row">
              <span>Type</span>
              <span style={{ textTransform: 'capitalize' }}>{display.displayType}</span>
            </div>
          )}
        </div>
      </div>

      <div className="screen-detail-footer">
        <Button variant="secondary" onClick={() => onOpenSettings(display)}>
          Display Settings
        </Button>
      </div>
    </aside>
  );
};

const Displays = () => {
  console.log('🚀 Displays component is rendering!');
  
  const { supportsDisplayManagement, isLoading, apiVersion, supportedFeatures } = useFeatureDetection();
  const { isConnected } = useWebSocket();
  
  const [displays, setDisplays] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  // Image update activity indicator state – toggles true briefly on any image update WS event
  // Pulse hook for image activity indicator so animation restarts every event
  const usePulse = (durationMs = 3500) => {
    const [active, setActive] = useState(false);
    const timeoutRef = useRef(null);
    const trigger = useCallback(() => {
      // Reset first so re-adding class restarts CSS keyframes reliably
      setActive(false);
      requestAnimationFrame(() => {
        setActive(true);
        if (timeoutRef.current) clearTimeout(timeoutRef.current);
        timeoutRef.current = setTimeout(() => setActive(false), durationMs);
      });
    }, [durationMs]);
    useEffect(() => () => { if (timeoutRef.current) clearTimeout(timeoutRef.current); }, []);
    return { active, trigger };
  };
  const { active: imageActivity, trigger: triggerImageActivity } = usePulse(3500);
  
  console.log('🔍 Current displays state:', displays?.length || 0, 'displays');
  console.log('🔍 Loading state:', loading);
  console.log('🔍 Error state:', error);
  console.log('🔍 Feature detection state:', {
    isLoading: isLoading,
    apiVersion: apiVersion,
    hasDisplayManagement: supportsDisplayManagement(),
    supportedFeatures: supportedFeatures
  });
  
  // UI state
  const [showSceneAssignment, setShowSceneAssignment] = useState(false);
  const [selectedDisplay, setSelectedDisplay] = useState(null);
  const [showDisplaySettings, setShowDisplaySettings] = useState(false);
  const [settingsDisplay, setSettingsDisplay] = useState(null);
  const [settingsOrientation, setSettingsOrientation] = useState('landscape');
  const [savingDisplaySettings, setSavingDisplaySettings] = useState(false);
  const [removingDisplay, setRemovingDisplay] = useState(false);
  const [displaySettingsError, setDisplaySettingsError] = useState(null);
  const [configStatus, setConfigStatus] = useState({});
  const [showPairing, setShowPairing] = useState(false);
  // Web Screen creation (browser-only displays)
  const [showAddWeb, setShowAddWeb] = useState(false);
  const [webName, setWebName] = useState('');
  const [webLocation, setWebLocation] = useState('');
  const [addingWeb, setAddingWeb] = useState(false);
  const [webError, setWebError] = useState(null);
  const [createdWebPath, setCreatedWebPath] = useState(null);

  // Developer mode — virtual display creation
  const [devMode, setDevMode] = useState(false);
  const [showAddVirtual, setShowAddVirtual] = useState(false);
  const [virtualName, setVirtualName] = useState('');
  const [virtualPreset, setVirtualPreset] = useState('landscape_800x480');
  const [virtualLocation, setVirtualLocation] = useState('Virtual');
  const [addingVirtual, setAddingVirtual] = useState(false);
  const [virtualError, setVirtualError] = useState(null);
  // Pre-fill pairing code from ?pair=ABC123 query param (QR code flow)
  const [initialPairCode] = useState(() => {
    const params = new URLSearchParams(window.location.search);
    return params.get('pair') || '';
  });

  // Auto-open pairing modal when ?pair= is present in URL
  useEffect(() => {
    if (initialPairCode) setShowPairing(true);
  }, [initialPairCode]);
  
  // Filtering and search
  const [searchTerm, setSearchTerm] = useState('');
  const [locationFilter, setLocationFilter] = useState('');
  const [onlineFilter, setOnlineFilter] = useState('all'); // 'all', 'online', 'offline'
  const [tagFilter, setTagFilter] = useState('');
  const [includeDiscovered, setIncludeDiscovered] = useState(true);
  // Mobile filters collapsed by default (decide after first render via effect to avoid hydration mismatch if SSR ever added)
  const [filtersCollapsed, setFiltersCollapsed] = useState(false);
  const [isMobile, setIsMobile] = useState(false);

  // Determine initial mobile state & listen for resize
  useEffect(() => {
    const mq = window.matchMedia('(max-width: 640px)');
    const apply = () => {
      const mobile = mq.matches;
      setIsMobile(mobile);
      setFiltersCollapsed(mobile); // collapse when entering mobile
    };
    apply();
    mq.addEventListener('change', apply);
    return () => mq.removeEventListener('change', apply);
  }, []);
  
  // Detail panel — display currently focused in the split-pane right panel
  const [panelDisplay, setPanelDisplay] = useState(null);

  // Discovery service status
  const [discoveryStatus, setDiscoveryStatus] = useState(null);
  // Reference discoveryStatus to avoid lint unused var (could be shown later in UI)
  const _hasDiscoveryData = !!discoveryStatus; // eslint-disable-line no-unused-vars
  const [discoveredDisplayStats, setDiscoveredDisplayStats] = useState(null);

  // Clear feature detection cache on fresh page loads to avoid stale errors
  useEffect(() => {
    // Clear expired cache on component mount
    featureDetection.clearExpiredCache();
  }, []);

  // Keep detail panel in sync with latest display data
  useEffect(() => {
    if (panelDisplay) {
      const updated = displays.find(d => d.id === panelDisplay.id);
      if (updated) setPanelDisplay(updated);
    }
  }, [displays]); // eslint-disable-line react-hooks/exhaustive-deps

  // Debug state changes
  useEffect(() => {
    console.log('🔄 Displays state changed to:', displays.length, 'displays');
    console.log('🔄 Displays data:', displays);
  }, [displays]);

  const loadDisplays = useCallback(async () => {
    // Wait for feature detection to complete
    if (isLoading) {
      console.log('🔄 Feature detection still loading, waiting...');
      return;
    }
    
    if (!supportsDisplayManagement()) {
      setError('Display management is not available in this API version');
      setLoading(false);
      return;
    }

    try {
      setError(null);
      // Check cache first
      const now = Date.now();
      if (displaysCache && displaysCacheTime && (now - displaysCacheTime) < DISPLAYS_CACHE_TIMEOUT) {
        console.log('🚀 Using cached displays data');
        setDisplays(displaysCache.displays || []);
        setDiscoveryStatus(displaysCache.discoveryStatus);
        setDiscoveredDisplayStats(displaysCache.stats);
        setLoading(false);
        return;
      }

      console.log('📡 Fetching displays data from unified endpoint');
      
      // Build query parameters
      const params = {
        include_discovered: includeDiscovered
      };
      if (onlineFilter !== 'all') {
        params.online_only = onlineFilter === 'online';
      }
      if (locationFilter) {
        params.location = locationFilter;
      }
      if (tagFilter) {
        params.tag = tagFilter;
      }

      // Fetch displays and discovery status
      const [displaysResponse, discoveryResponse, statsResponse, displayStatusResponse] = await Promise.all([
        api.getDisplays(params),
        api.getDiscoveryStatus().catch(err => {
          console.warn('Discovery status not available:', err);
          return null;
        }),
        api.getDiscoveryStatus().catch(err => {
          console.warn('Discovered display stats not available:', err);
          return null;
        }),
        api.getDisplayStatus().catch(() => null),
      ]);
      if (displayStatusResponse?.data?.dev_mode) {
        setDevMode(true);
      }

      // Normalize displays payload to an array regardless of server shape or errors
      const payload = displaysResponse?.data;
      let allDisplays = [];
      if (Array.isArray(payload)) {
        allDisplays = payload;
      } else if (Array.isArray(payload?.displays)) {
        allDisplays = payload.displays;
      } else if (Array.isArray(payload?.data)) {
        allDisplays = payload.data;
      } else if (Array.isArray(payload?.items)) {
        allDisplays = payload.items;
      } else {
        allDisplays = [];
      }
      const discoveryData = discoveryResponse?.data || null;
      const statsData = statsResponse?.data || null;

      // Get discovered display assignments
  let discoveredAssignments = {};
      try {
        const assignmentsResponse = await api.getAssignmentStatus();
        discoveredAssignments = assignmentsResponse.data?.assignments || {};
        console.log('🔍 Debug - Discovered assignments:', discoveredAssignments);
      } catch (err) {
        console.warn('Could not fetch discovered display assignments:', err);
      }

      // Fetch scene information for displays that have assignments
      let sceneNames = {};
      try {
        // Get all unique scene IDs from both registered and discovered displays
        const allSceneIds = new Set();
        
        // Add scene IDs from registered displays
        allDisplays.forEach(display => {
          if (display.assignedSceneId || display.assigned_scene_id) {
            allSceneIds.add(display.assignedSceneId || display.assigned_scene_id);
          }
        });
        
        // Add scene IDs from discovered display assignments
        if (discoveredAssignments && typeof discoveredAssignments === 'object') {
          Object.values(discoveredAssignments).forEach(assignment => {
            if (assignment && assignment.scene_id) {
              allSceneIds.add(assignment.scene_id);
            }
          });
        }

        // Fetch scene names for all unique scene IDs
        if (allSceneIds.size > 0) {
          const scenesResponse = await api.getScenes();
          const sd = scenesResponse?.data;
          const scenes = Array.isArray(sd?.scenes) ? sd.scenes : (Array.isArray(sd) ? sd : []);
          sceneNames = scenes.reduce((acc, scene) => {
            acc[scene.id] = scene.name;
            return acc;
          }, {});
          console.log('🔍 Debug - Scene names fetched:', sceneNames);
        }
      } catch (err) {
        console.warn('Could not fetch scene names:', err);
      }

      // Normalize the display data and set source based on displayType
      const normalizedDisplays = allDisplays.map(display => {
        const displayType = display.displayType || display.display_type || display.source || 'registered';
        const webhookPort = display.webhook_port ?? display.webhookPort ?? null;
        const normalized = {
          ...display,
          displayType,
          webhook_port: webhookPort,
          source: displayType, // Use displayType as source
          is_online: display.isOnline !== undefined ? display.isOnline : display.is_online,
          last_seen: display.lastSeen || display.last_seen,
          resolution: display.resolution || (display.width && display.height ? [display.width, display.height] : null)
        };

        // Handle assigned scene ID - could be string or object format
        let sceneId = null;
        if (display.assignedSceneId) {
          if (typeof display.assignedSceneId === 'object' && display.assignedSceneId.id) {
            // New nested format: { id: "scene-id", subchannelId: "subchannel" }
            sceneId = display.assignedSceneId.id;
            normalized.assigned_subchannel_id = display.assignedSceneId.subchannelId;
          } else if (typeof display.assignedSceneId === 'string') {
            // Old string format
            sceneId = display.assignedSceneId;
          }
        }
        
        // Also check legacy format
        if (!sceneId && display.assigned_scene_id) {
          sceneId = display.assigned_scene_id;
        }

        // For discovered displays, check in-memory assignments
        if (display.displayType === 'discovered' && discoveredAssignments[display.id]) {
          const assignment = discoveredAssignments[display.id];
          sceneId = assignment.scene_id;
          normalized.assigned_at = assignment.assigned_at;
          console.log(`🔍 Debug - Found assignment for ${display.id}: ${assignment.scene_id}`);
        }

        // Set normalized scene ID fields
        if (sceneId) {
          normalized.assigned_scene_id = sceneId;
          normalized.assignedSceneId = sceneId; // Keep both formats for compatibility
        }

        // Add scene name for any display with an assigned scene
        if (sceneId && sceneNames[sceneId]) {
          normalized.assigned_scene_name = sceneNames[sceneId];
          console.log(`🔍 Debug - Added scene name for ${display.id}: ${sceneNames[sceneId]}`);
        }

        return normalized;
      });

      console.log('🔍 Debug - Total displays from API:', allDisplays.length);
      console.log('🔍 Debug - Normalized displays:', normalizedDisplays.length);
      console.log('🔍 Debug - Displays by type:', {
        discovered: normalizedDisplays.filter(d => d.displayType === 'discovered').length,
        registered: normalizedDisplays.filter(d => d.displayType === 'registered').length
      });

      // Update cache
      displaysCache = { displays: normalizedDisplays, discoveryStatus: discoveryData, stats: statsData };
      displaysCacheTime = Date.now();

      console.log('🎯 About to set displays state with:', normalizedDisplays.length, 'displays');
      setDisplays(normalizedDisplays);
      setDiscoveryStatus(discoveryData);
      setDiscoveredDisplayStats(statsData);
      console.log('✅ Displays state set complete');
    } catch (error) {
      console.error('Error loading displays:', error);
      setError(error.message);
    } finally {
      setLoading(false);
    }
  }, [supportsDisplayManagement, onlineFilter, locationFilter, tagFilter, includeDiscovered, isLoading]);

  const handleAddWebDisplay = useCallback(async () => {
    if (!webName.trim()) {
      setWebError('Name is required');
      return;
    }
    setAddingWeb(true);
    setWebError(null);
    try {
      const resp = await api.createWebDisplay({
        name: webName.trim(),
        location: webLocation.trim() || null,
      });
      // Keep the modal open showing the URL — the user needs it for the device.
      setCreatedWebPath(resp.data.web_path);
      displaysCache = null;
      displaysCacheTime = null;
      await loadDisplays();
    } catch (err) {
      setWebError(err?.response?.data?.detail || err.message || 'Failed to create web screen');
    } finally {
      setAddingWeb(false);
    }
  }, [webName, webLocation, loadDisplays]);

  const closeWebModal = useCallback(() => {
    setShowAddWeb(false);
    setWebError(null);
    setCreatedWebPath(null);
    setWebName('');
    setWebLocation('');
  }, []);

  const handleAddVirtualDisplay = useCallback(async () => {
    if (!virtualName.trim()) {
      setVirtualError('Name is required');
      return;
    }
    setAddingVirtual(true);
    setVirtualError(null);
    try {
      await api.createVirtualDisplay({
        name: virtualName.trim(),
        location: virtualLocation.trim() || 'Virtual',
        preset: virtualPreset,
      });
      setShowAddVirtual(false);
      setVirtualName('');
      setVirtualLocation('Virtual');
      setVirtualPreset('landscape_800x480');
      displaysCache = null;
      displaysCacheTime = null;
      await loadDisplays();
    } catch (err) {
      setVirtualError(err?.response?.data?.detail || err.message || 'Failed to create virtual display');
    } finally {
      setAddingVirtual(false);
    }
  }, [virtualName, virtualLocation, virtualPreset, loadDisplays]);

  const handleDeleteVirtualDisplay = useCallback(async (displayId) => {
    try {
      await api.deleteVirtualDisplay(displayId);
      displaysCache = null;
      displaysCacheTime = null;
      await loadDisplays();
    } catch (err) {
      console.error('Failed to delete virtual display:', err);
    }
  }, [loadDisplays]);

  const handlePairDisplay = useCallback(async (display) => {
    if (!display?.id) return;
    const browserHost = typeof window !== 'undefined' && window.location
      ? window.location.hostname
      : '';
    setConfigStatus(prev => ({
      ...prev,
      [display.id]: { loading: true, error: null, success: false }
    }));
    try {
      await api.bootstrapDisplay(display.id, {
        display_name: display.name || undefined,
        display_location: display.location || undefined,
        public_host_hint: browserHost || undefined,
      });
      setConfigStatus(prev => ({
        ...prev,
        [display.id]: { loading: false, error: null, success: true }
      }));
      setTimeout(() => {
        setConfigStatus(prev => {
          const next = { ...prev };
          if (next[display.id]?.success) {
            next[display.id] = { loading: false, error: null, success: false };
          }
          return next;
        });
      }, 5000);
    } catch (e) {
      const message = e?.response?.data?.detail || e?.message || 'Pairing failed';
      setConfigStatus(prev => ({
        ...prev,
        [display.id]: { loading: false, error: message, success: false }
      }));
    }
  }, []);

  // Load displays when feature detection completes or filters change
  useEffect(() => {
    if (!isLoading) {
      console.log('🔄 Feature detection completed, loading displays...');
      loadDisplays();
    }
  }, [loadDisplays, isLoading]);

  // Manual refresh that bypasses cache
  const refreshDisplays = useCallback(async () => {
    // Clear API cache for display-related endpoints
    if (api.cache) {
      api.cache.invalidate(['/displays', '/display-scene', '/scenes']);
    }
    
    displaysCache = null;
    displaysCacheTime = null;
    setLoading(true);
    await loadDisplays();
  }, [loadDisplays]);


  // WebSocket event handlers for real-time updates
  useEffect(() => {
    const HEARTBEAT_TOPIC_REGEX = /^mimir\/(.+?)\/heartbeat$/;
    const STATUS_TOPIC_REGEX = /^mimir\/(.+?)\/status$/;
    const EVENT_TOPIC_REGEX = /^mimir\/(.+?)\/evt$/;

    const matchesDisplayIdentifier = (display, deviceId) => (
      display.id === deviceId ||
      display.device_id === deviceId ||
      display.deviceId === deviceId ||
      display.hostname === deviceId
    );

    const mergeDisplayUpdate = (deviceId, partial) => {
      setDisplays(prev => {
        let found = false;
        let changed = false;
        const updated = prev.map(d => {
          const idMatch = matchesDisplayIdentifier(d, deviceId);
          if (!idMatch) return d;
          found = true;
          // Determine if any field in partial differs
          for (const k in partial) {
            if (Object.prototype.hasOwnProperty.call(partial, k)) {
              if (d[k] !== partial[k]) {
                changed = true;
                break;
              }
            }
          }
          if (!changed) return d; // skip object spread to avoid re-render
          return { ...d, ...partial };
        });
        if (!found) {
          // New provisional discovered display only if update contains meaningful data
          changed = true;
          updated.push({
            id: deviceId,
            device_id: deviceId,
            name: deviceId,
            displayType: 'discovered',
            is_online: partial.is_online ?? true,
            last_seen: partial.last_seen || partial.timestamp || new Date().toISOString(),
            ...partial
          });
        }
        return changed ? updated : prev;
      });
    };

    const handleDisplayEvent = (event) => {
      if (!event.detail && !event.data) return;
      const payload = event.detail || event.data; // Some dispatchers use detail
      // If this is a structured internal event (legacy types)
      if (payload?.type) {
        switch (payload.type) {
          case 'display_client_registered':
            console.log('🖥️ New display registered:', payload);
            refreshDisplays();
            return;
          case 'display_scene_assigned':
          case 'display_scene_unassigned':
            console.log('🎬 Display scene assignment changed:', payload);
            refreshDisplays();
            return;
          case 'display_image_updated':
            console.log('🖼️ (legacy) Display image updated:', payload);
            setDisplays(prev => prev.map(display => matchesDisplayIdentifier(display, payload.displayId)
              ? (display.current_image_url === payload.imageUrl
                ? { ...display, last_image_update_ts: new Date().toISOString() }
                : { ...display, current_image_url: payload.imageUrl, last_image_update_ts: new Date().toISOString() })
              : display));
            triggerImageActivity(); // legacy event still counts
            return;
          case 'mqtt_message': {
            // Normalize nested mqtt message shape so existing topic-based parser can run
            const topic = payload.data?.topic;
            const mqttInner = payload.data?.payload;
            const cmdMatch = topic ? /^mimir\/(.+?)\/cmd$/.exec(topic) : null;
            if (cmdMatch && mqttInner?.type === 'display_image' && mqttInner.image_url) {
              const deviceId = cmdMatch[1];
              const tsRaw = mqttInner.updated_at ?? mqttInner.timestamp; // accept either
              const tsIso = tsRaw
                ? new Date(typeof tsRaw === 'number' && tsRaw < 1e12 ? tsRaw * 1000 : tsRaw).toISOString()
                : new Date().toISOString();

              setDisplays(prev => prev.map(d => {
                if (!matchesDisplayIdentifier(d, deviceId)) return d;

                // If your backend reuses the same URL for new content,
                // you STILL want to bump the "last updated" time:
                if (d.current_image_url === mqttInner.image_url) {
                  return { ...d, last_image_update_ts: tsIso };
                }
                return {
                  ...d,
                  current_image_url: mqttInner.image_url,
                  last_image_update_ts: tsIso
                };
              }));
              triggerImageActivity();
              return;
            }
            // Heartbeat / status / evt fallback via synthetic forwarding variables
            // Reuse existing regex logic below by constructing variables
            try {
              const obj = mqttInner;
              let match;
              if ((match = /^mimir\/(.+?)\/heartbeat$/.exec(topic))) {
                const deviceId = match[1];
                const cap = obj.cap || obj.capabilities || {};
                const resolution = Array.isArray(cap.res) ? cap.res : (obj.res || null);
                const orientation = cap.ori || obj.ori || obj.rotation || null;
                // We intentionally do NOT update last_seen to avoid UI churn; only structural changes
                mergeDisplayUpdate(deviceId, {
                  cap,
                  capabilities: cap,
                  resolution,
                  orientation,
                  is_online: true,
                  displayType: obj.display_id ? 'registered' : 'discovered'
                });
                return;
              }
              if ((match = /^mimir\/(.+?)\/status$/.exec(topic))) {
                const deviceId = match[1];
                const statusOnline = obj.status === 'online';
                mergeDisplayUpdate(deviceId, { is_online: statusOnline });
                return;
              }
              if ((match = /^mimir\/(.+?)\/evt$/.exec(topic))) {
                const deviceId = match[1];
                if (obj.type === 'error') {
                  mergeDisplayUpdate(deviceId, {
                    last_error: { code: obj.error || obj.code, detail: obj.detail || obj.message, ts: obj.timestamp || obj.t }
                  });
                }
                // rendered ack intentionally does not pulse image activity
                return;
              }
            } catch (e) {
              console.warn('Failed inner mqtt_message normalization', e);
            }
            break; // allow fallthrough to generic handling if any later additions
          }
          default:
            break; // fall through to topic-based parsing if available
        }
      }

      // Topic-based forwarding (WS layer should include mqttTopic + mqttPayload)
      const mqttTopic = payload.mqttTopic || payload.topic;
      const mqttPayload = payload.mqttPayload || payload.payload;
      if (!mqttTopic || !mqttPayload) return;

      try {
        // mqttPayload may already be an object
        const obj = typeof mqttPayload === 'string' ? JSON.parse(mqttPayload) : mqttPayload;
        let match;
        if ((match = HEARTBEAT_TOPIC_REGEX.exec(mqttTopic))) {
          const deviceId = match[1];
          const cap = obj.cap || obj.capabilities || {};
          const resolution = Array.isArray(cap.res) ? cap.res : (obj.res || null);
          const orientation = cap.ori || obj.ori || obj.rotation || null;
          const registration_state = obj.registration_state;
          const display_id = obj.display_id || null;
          const last_seen = obj.timestamp || obj.t || new Date().toISOString();
          mergeDisplayUpdate(deviceId, {
            cap: cap,
            capabilities: cap,
            resolution,
            orientation,
            registration_state,
            display_id,
            last_seen,
            is_online: true,
            hardware_fingerprint: obj.hardware_fingerprint || undefined,
            displayType: display_id ? 'registered' : 'discovered'
          });
          return;
        }
        if ((match = STATUS_TOPIC_REGEX.exec(mqttTopic))) {
          const deviceId = match[1];
          const statusOnline = obj.status === 'online';
          mergeDisplayUpdate(deviceId, {
            is_online: statusOnline,
            last_seen: obj.timestamp || obj.time || new Date().toISOString(),
          });
          return;
        }
        if ((match = EVENT_TOPIC_REGEX.exec(mqttTopic))) {
          const deviceId = match[1];
          if (obj.type === 'finalize_ack') {
            mergeDisplayUpdate(deviceId, {
              registration_state: 'finalized',
              // display_id will appear in subsequent heartbeat; keep provisional
            });
          }
          if (obj.type === 'error') {
            mergeDisplayUpdate(deviceId, {
              last_error: { code: obj.error || obj.code, detail: obj.detail || obj.message, ts: obj.timestamp || obj.t }
            });
          }
          return;
        }
      } catch (e) {
        console.warn('WS payload parse failed', e);
      }
    };

    window.addEventListener('websocket-message', handleDisplayEvent);
    return () => window.removeEventListener('websocket-message', handleDisplayEvent);
  }, [refreshDisplays, triggerImageActivity]);


  // Auto-retry when in error state — recovers from transient server restarts or network blips
  // without requiring a manual browser refresh.
  useEffect(() => {
    if (!error) return;
    const timer = setTimeout(() => refreshDisplays(), 30_000);
    return () => clearTimeout(timer);
  }, [error, refreshDisplays]);

  const handleSceneAssigned = async (displayId, sceneId) => {
    setShowSceneAssignment(false);
    setSelectedDisplay(null);
    
    // Immediately update the display in the local state to show assignment
    setDisplays(prev => prev.map(display => {
      if (display.id === displayId) {
        return {
          ...display,
          assigned_scene_id: sceneId,
          assignedSceneId: sceneId,
          assigned_scene_name: sceneId ? 'Loading...' : null // Will be updated by refresh
        };
      }
      return display;
    }));
    
    // Then refresh to get the full updated data including scene name
    await refreshDisplays();
  };

  const handleDeleteDisplay = async (displayId) => {
    const display = displays.find(d => d.id === displayId);
    const isVirtual = display?.discovery_method === 'virtual';
    const label = isVirtual ? 'Remove this virtual display?' : 'Are you sure you want to delete this display client?';
    if (!window.confirm(label)) {
      return;
    }
    try {
      if (isVirtual) {
        await api.deleteVirtualDisplay(displayId);
      } else {
        await api.deleteDisplay(displayId);
      }
      refreshDisplays();
    } catch (error) {
      console.error('Error deleting display:', error);
      alert('Failed to delete display: ' + error.message);
    }
  };

  const openDisplaySettings = useCallback((display) => {
    setSettingsDisplay(display);
    setSettingsOrientation(normalizeOrientationValue(display.orientation));
    setDisplaySettingsError(null);
    setShowDisplaySettings(true);
  }, []);

  const closeDisplaySettings = useCallback(() => {
    if (savingDisplaySettings || removingDisplay) return;
    setShowDisplaySettings(false);
    setSettingsDisplay(null);
    setDisplaySettingsError(null);
  }, [savingDisplaySettings, removingDisplay]);

  const handleUnpairDisplay = useCallback(async () => {
    if (!settingsDisplay) return;
    const isVirtual = settingsDisplay.discovery_method === 'virtual';
    const confirmed = window.confirm(
      isVirtual
        ? `Remove virtual display "${settingsDisplay.name}"?`
        : `Unpair "${settingsDisplay.name}"? The display will be removed from Mimir and must be paired again before it can show scenes.`
    );
    if (!confirmed) return;

    setRemovingDisplay(true);
    setDisplaySettingsError(null);
    try {
      if (isVirtual) {
        await api.deleteVirtualDisplay(settingsDisplay.id);
      } else {
        await api.deleteDisplay(settingsDisplay.id);
      }
      setShowDisplaySettings(false);
      setSettingsDisplay(null);
      await refreshDisplays();
    } catch (err) {
      setDisplaySettingsError(err?.response?.data?.detail || err?.message || 'Failed to unpair display');
    } finally {
      setRemovingDisplay(false);
    }
  }, [refreshDisplays, settingsDisplay]);

  const handleSaveDisplaySettings = useCallback(async () => {
    if (!settingsDisplay) return;

    setSavingDisplaySettings(true);
    setDisplaySettingsError(null);
    try {
      const response = await api.updateDisplay(settingsDisplay.id, {
        orientation: settingsOrientation,
      });

      setDisplays((prev) => prev.map((display) => {
        if (display.id !== settingsDisplay.id) return display;
        return {
          ...display,
          ...response.data,
        };
      }));

      closeDisplaySettings();
      await refreshDisplays();
    } catch (err) {
      setDisplaySettingsError(err?.response?.data?.detail || err?.message || 'Failed to update display settings');
    } finally {
      setSavingDisplaySettings(false);
    }
  }, [closeDisplaySettings, refreshDisplays, settingsDisplay, settingsOrientation]);

  // Filter displays based on search and filters
  const filteredDisplays = (Array.isArray(displays) ? displays : []).filter(display => {
    // Search term filter
    if (searchTerm && !display.name.toLowerCase().includes(searchTerm.toLowerCase()) &&
        !display.description?.toLowerCase().includes(searchTerm.toLowerCase())) {
      return false;
    }

    // Online status filter
    if (onlineFilter === 'online' && !display.is_online) {
      return false;
    }
    if (onlineFilter === 'offline' && display.is_online) {
      return false;
    }

    // Location filter
    if (locationFilter && display.location !== locationFilter) {
      return false;
    }

    // Tag filter
    if (tagFilter && (!display.tags || !display.tags.includes(tagFilter))) {
      return false;
    }

    return true;
  });

  // Compute content-paired groups: displays sharing a scene where ≥1 has a content_variant
  const { pairedGroups, unpairedDisplays } = useMemo(() => {
    const byScene = {};
    filteredDisplays.forEach(d => {
      const sid = d.assigned_scene_id;
      if (!sid) return;
      if (!byScene[sid]) byScene[sid] = [];
      byScene[sid].push(d);
    });
    const pairedIds = new Set();
    const pairedGroups = [];
    Object.entries(byScene).forEach(([sceneId, group]) => {
      if (group.length >= 2 && group.some(d => d.content_variant || d.contentVariant)) {
        pairedGroups.push({ sceneId, displays: group, sceneName: group[0].assigned_scene_name || group[0].assignedSceneName || 'Program' });
        group.forEach(d => pairedIds.add(d.id));
      }
    });
    return { pairedGroups, unpairedDisplays: filteredDisplays.filter(d => !pairedIds.has(d.id)) };
  }, [filteredDisplays]);

  // Get unique locations and tags for filter options
  const locations = [...new Set((Array.isArray(displays) ? displays : []).map(d => d.location).filter(Boolean))];
  const tags = [...new Set((Array.isArray(displays) ? displays : []).flatMap(d => d.tags || []))];

  console.log('🔍 Debug - Total displays:', displays.length);
  console.log('🔍 Debug - Filtered displays:', filteredDisplays.length);
  console.log('🔍 Debug - Displays array:', displays);
  console.log('🔍 Debug - Individual displays:');
  displays.forEach((display, index) => {
    console.log(`  Display ${index}:`, {
      id: display.id,
      name: display.name,
      source: display.source,
      is_online: display.is_online
    });
  });
  if (!supportsDisplayManagement()) {
    return (
      <div className="page-container">
        <Header 
          title="Displays" 
          icon="MonitorSpeaker" 
          iconSize={36} 
          description="Manage display clients and scene assignments"
          rightSlot={<DebugPanel showToggle toggleLabel="Debug" />}
        />

        
        <div className="empty-state">
          <h3>Display Management Not Available</h3>
          <p className="text-tertiary">
            Display management requires API v2.3 or higher. Your current API version does not support multi-display features.
          </p>
        </div>
      </div>
    );
  }

  const renderCard = (display, paired) => (
    <div
      key={display.id}
      className={`display-card-wrapper ${panelDisplay?.id === display.id ? 'display-card-wrapper--active' : ''}`}
      onClick={(e) => {
        if (!e.target.closest('button, a, input, .display-thumbnail')) {
          setPanelDisplay(prev => prev?.id === display.id ? null : display);
        }
      }}
    >
      <DisplayCard
        display={display}
        paired={paired}
        onAssignScene={(d) => {
          setSelectedDisplay(d);
          setShowSceneAssignment(true);
        }}
        onConfigure={handlePairDisplay}
        configureStatus={configStatus[display.id]}
        onEdit={(d, action) => {
          if (action === 'approve' && d.displayType === 'discovered') {
            setDisplays(prev => prev.map(x => x.id === d.id ? { ...x, approving: true } : x));
            api.approveDiscoveredDisplay(d.id)
              .then(() => refreshDisplays())
              .catch(err => {
                console.error('Approve failed', err);
                setDisplays(prev => prev.map(x => x.id === d.id ? { ...x, approving: false, approve_error: err.message } : x));
              });
          } else if (action === 'reject' && d.displayType === 'discovered') {
            const original = displays;
            setDisplays(prev => prev.filter(x => x.id !== d.id));
            api.rejectDiscoveredDisplay(d.id)
              .then(() => refreshDisplays())
              .catch(err => {
                console.error('Reject failed', err);
                setDisplays(original);
              });
          } else if (action === 'register' && d.displayType === 'discovered') {
            setSelectedDisplay({
              ...d,
              name: d.name || d.service_name,
              ip_address: d.addresses?.[0] || d.ip_address,
              port: d.webhook_port || d.port,
              resolution: d.resolution || [d.width, d.height],
              orientation: d.orientation || 'landscape'
            });
          } else if (action === 'settings') {
            openDisplaySettings(d);
          }
        }}
        onDelete={handleDeleteDisplay}
        onRefresh={refreshDisplays}
      />
    </div>
  );

  return (
    <PullToRefresh onRefresh={refreshDisplays}>
    <div className={`screens-split-layout ${panelDisplay ? 'screens-split-layout--open' : ''}`}>
    <div className="screens-list-pane">
        <Header
          title="Screens"
          icon="MonitorSpeaker"
          iconSize={36}
          description="Manage display clients and scene assignments"
          actions={[
            devMode && (
              <Button
                key="virtual"
                variant="secondary"
                onClick={() => { setShowAddVirtual(true); setVirtualError(null); }}
              >
                + Virtual Display
              </Button>
            ),
            <Button
              key="web"
              variant="secondary"
              onClick={() => { setShowAddWeb(true); setWebError(null); }}
            >
              + Web Screen
            </Button>,
            <Button
              key="pair"
              variant="primary"
              onClick={() => setShowPairing(true)}
            >
              + Add Screen
            </Button>,
            <Button
              key="refresh"
              variant="secondary"
              className="desktop-only-refresh"
              icon={<RotateCcw size={18} aria-hidden="true" />}
              onClick={refreshDisplays}
              disabled={loading}
            >
              {loading ? 'Refreshing…' : 'Refresh'}
            </Button>
          ]}
        />
   
    
      {/* Discovered Display Assignment Stats */}
      {false && discoveredDisplayStats && (
        <div className="assignment-stats">
          <div className="assignment-info">
            <div className="stats-header">
              <h3>Assignment Status</h3>
            </div>
            <div className="assignment-stats-grid">
              <div className="stat-item">
                <span className="stat-value">{discoveredDisplayStats.total_assignments}</span>
                <span className="stat-label">Total Assignments</span>
              </div>
              <div className="stat-item">
                <span className="stat-value">{discoveredDisplayStats.online_discovered_displays}</span>
                <span className="stat-label">Online Discovered</span>
              </div>
              <div className="stat-item">
                <span className="stat-value">{discoveredDisplayStats.unassigned_discovered_displays}</span>
                <span className="stat-label">Unassigned</span>
              </div>
              <div className="stat-item">
                <span className="stat-value">{discoveredDisplayStats.scenes_with_discovered_displays}</span>
                <span className="stat-label">Scenes with Displays</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Search and Filters */}
      <div className={`displays-controls ${isMobile ? 'mobile-controls' : ''}`}>
        <div className="search-section">
          <div className="search-input">
            <Search size={18} />
            <input
              type="text"
              placeholder="Search screens..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>
          {isMobile && (
            <button
              type="button"
              className="btn btn-tertiary mobile-filters-toggle"
              aria-expanded={!filtersCollapsed}
              aria-controls="display-filters-panel"
              onClick={() => setFiltersCollapsed(c => !c)}
            >
              {filtersCollapsed ? 'Show Filters' : 'Hide Filters'}
              {/* Active filter count (exclude defaults) */}
              {(() => {
                const active = [
                  onlineFilter !== 'all',
                  !!locationFilter,
                  !!tagFilter,
                  !includeDiscovered === true // if unchecked differs from default true
                ].filter(Boolean).length;
                return active > 0 ? <span className="filter-count-badge">{active}</span> : null;
              })()}
            </button>
          )}
        </div>

        <div
          id="display-filters-panel"
          className={`filters-section ${filtersCollapsed && isMobile ? 'collapsed' : 'expanded'}`}
          style={filtersCollapsed && isMobile ? { display: 'none' } : undefined}
        >
          <div className="filter-group">
            <Filter size={16} />
            <select 
              value={onlineFilter} 
              onChange={(e) => setOnlineFilter(e.target.value)}
            >
              <option value="all">All Screens</option>
              <option value="online">Online Only</option>
              <option value="offline">Offline Only</option>
            </select>
          </div>

          {locations.length > 0 && (
            <div className="filter-group">
              <MapPin size={16} />
              <select 
                value={locationFilter} 
                onChange={(e) => setLocationFilter(e.target.value)}
              >
                <option value="">All Locations</option>
                {locations.map(location => (
                  <option key={location} value={location}>{location}</option>
                ))}
              </select>
            </div>
          )}

          {tags.length > 0 && (
            <div className="filter-group">
              <select 
                value={tagFilter} 
                onChange={(e) => setTagFilter(e.target.value)}
              >
                <option value="">All Tags</option>
                {tags.map(tag => (
                  <option key={tag} value={tag}>{tag}</option>
                ))}
              </select>
            </div>
          )}

          <div className="filter-group">
            <label className="checkbox-filter">
              <input
                type="checkbox"
                checked={includeDiscovered}
                onChange={(e) => setIncludeDiscovered(e.target.checked)}
              />
              <span>Include Discovered</span>
            </label>
          </div>
        </div>
      </div>

      {/* Display Count */}
      <div className="displays-stats">
        <span className="stats-item">
          {filteredDisplays.length} screen{filteredDisplays.length !== 1 ? 's' : ''}
        </span>
        <span className="stats-item">
          <Monitor size={14} />
          {filteredDisplays.filter(d => d.displayType === 'registered').length} registered
        </span>
        <span className="stats-item">
          <Search size={14} />
          {filteredDisplays.filter(d => d.displayType === 'discovered').length} discovered
        </span>
        <span className="stats-item">
          <Wifi size={14} />
          {filteredDisplays.filter(d => d.is_online).length} online
        </span>
        <span className="stats-item">
          <WifiOff size={14} />
          {filteredDisplays.filter(d => !d.is_online).length} offline
        </span>
        <span className="stats-item image-activity-wrapper" title="Recent image activity">
          <span className={`image-activity-indicator ${imageActivity ? 'active' : ''}`}></span>
          <span style={{ fontSize: '12px' }}>image activity</span>
        </span>
      </div>

      {/* Main Content */}
      {loading ? (
        <div className="displays-grid">
          {[1, 2, 3, 4].map(i => <SkeletonScreenCard key={i} />)}
        </div>
      ) : error ? (
        <div className="error-state">
          <h3>Error Loading Screens</h3>
          <p>{error}</p>
          <button className="btn btn-primary" onClick={refreshDisplays}>
            Try Again
          </button>
        </div>
      ) : filteredDisplays.length === 0 ? (
        <div className="empty-state">
          <h3>{displays.length === 0 ? 'No screens connected' : 'No screens match your filters'}</h3>
          <p className="text-tertiary">
            {displays.length === 0
              ? 'Screens are the physical displays connected to Mimir. Add a screen to get started.'
              : 'Try adjusting your filters to see more screens.'
            }
          </p>
          {displays.length === 0 && (
            <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'center', flexWrap: 'wrap' }}>
              <Button
                variant="primary"
                icon={<Plus size={18} aria-hidden="true" />}
                onClick={() => { setShowPairing(true); }}
              >
                Add Screen
              </Button>
              <Button
                variant="secondary"
                icon={<Globe size={18} aria-hidden="true" />}
                onClick={() => { setShowAddWeb(true); setWebError(null); }}
              >
                Web Screen
              </Button>
            </div>
          )}
        </div>
      ) : (
        <div className="displays-grid">
          {pairedGroups.map(group => (
            <div key={group.sceneId} className="paired-group">
              <div className="paired-group-header">
                <Link2 size={11} />
                <span className="paired-group-scene">{group.sceneName}</span>
                <span className="paired-group-label">Content Paired</span>
              </div>
              <div className="paired-group-cards">
                {group.displays.map(display => renderCard(display, true))}
              </div>
            </div>
          ))}
          {unpairedDisplays.map(display => renderCard(display, false))}
        </div>
      )}

      {/* Modals */}
      

      {showPairing && (
        <DisplayPairing
          initialCode={initialPairCode}
          onClose={() => setShowPairing(false)}
          onPaired={(display) => {
            setShowPairing(false);
            refreshDisplays();
          }}
        />
      )}

      {showSceneAssignment && selectedDisplay && (
        <SceneAssignment
          display={selectedDisplay}
          onClose={() => {
            setShowSceneAssignment(false);
            setSelectedDisplay(null);
          }}
          onSuccess={handleSceneAssigned}
        />
      )}

      <Modal
        isOpen={showDisplaySettings && !!settingsDisplay}
        onClose={closeDisplaySettings}
        title={settingsDisplay ? `Display Settings - ${settingsDisplay.name}` : 'Display Settings'}
        size="medium"
      >
        {settingsDisplay && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div style={{ color: 'var(--color-text-secondary)' }}>
              Change how this display is oriented without editing the hardware `.env` file.
            </div>

            <div style={{ padding: '0.75rem', border: '1px solid var(--color-border)', borderRadius: '8px', background: 'var(--color-surface-secondary)' }}>
              <div style={{ fontWeight: 600 }}>{settingsDisplay.name}</div>
              <div style={{ fontSize: '0.9rem', color: 'var(--color-text-secondary)', marginTop: '0.25rem' }}>
                Current orientation: {formatOrientationLabel(settingsDisplay.orientation)}
              </div>
            </div>

            <label style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
              <span style={{ fontWeight: 600 }}>Orientation</span>
              <select
                className="form-select"
                value={settingsOrientation}
                onChange={(e) => setSettingsOrientation(e.target.value)}
                disabled={savingDisplaySettings}
                style={{ padding: '0.75rem', borderRadius: '8px' }}
              >
                {getOrientationOptionsForDisplay(settingsDisplay).map((option) => (
                  <option key={option.value} value={option.value}>{option.label}</option>
                ))}
              </select>
            </label>

            <div style={{ fontSize: '0.85rem', color: 'var(--color-text-secondary)' }}>
              Landscape upside-down and the two portrait rotations are supported for rectangular displays. Square is only shown for square hardware.
            </div>

            {displaySettingsError && (
              <div style={{ color: 'var(--color-error)' }}>{displaySettingsError}</div>
            )}

            <div style={{ borderTop: '1px solid var(--color-border)', paddingTop: '0.75rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.75rem' }}>
              <div style={{ fontSize: '0.85rem', color: 'var(--color-text-secondary)' }}>
                Unpairing removes this display from Mimir. If it is still on the network it will reappear as an unpaired discovered display.
              </div>
              <Button
                variant="danger"
                onClick={handleUnpairDisplay}
                loading={removingDisplay}
                disabled={savingDisplaySettings}
              >
                {settingsDisplay?.discovery_method === 'virtual' ? 'Remove Virtual Display' : 'Unpair Display'}
              </Button>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem' }}>
              <Button variant="secondary" onClick={closeDisplaySettings} disabled={savingDisplaySettings || removingDisplay}>
                Cancel
              </Button>
              <Button variant="primary" onClick={handleSaveDisplaySettings} loading={savingDisplaySettings} disabled={removingDisplay}>
                Save Settings
              </Button>
            </div>
          </div>
        )}
      </Modal>
      
      {/* Web Screen creation modal */}
      <Modal
        isOpen={showAddWeb}
        onClose={closeWebModal}
        title="Add Web Screen"
        size="small"
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {!createdWebPath ? (
            <>
              <div style={{ fontSize: '0.85rem', color: 'var(--color-text-secondary)' }}>
                A Web Screen is a display that lives at a unique URL — open it in any
                browser (old tablets, spare monitors, TVs) and that device becomes a
                Mimir screen. No app install needed.
              </div>
              <label style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                <span style={{ fontWeight: 600 }}>Screen Name</span>
                <input
                  className="form-input"
                  type="text"
                  placeholder="e.g. Kitchen Tablet"
                  value={webName}
                  onChange={(e) => setWebName(e.target.value)}
                  disabled={addingWeb}
                  autoFocus
                />
              </label>
              <label style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                <span style={{ fontWeight: 600 }}>Location</span>
                <input
                  className="form-input"
                  type="text"
                  placeholder="e.g. Kitchen"
                  value={webLocation}
                  onChange={(e) => setWebLocation(e.target.value)}
                  disabled={addingWeb}
                />
              </label>
              {webError && (
                <div style={{ color: 'var(--color-error)', fontSize: '0.9rem' }}>{webError}</div>
              )}
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem' }}>
                <Button variant="secondary" onClick={closeWebModal} disabled={addingWeb}>
                  Cancel
                </Button>
                <Button variant="primary" onClick={handleAddWebDisplay} loading={addingWeb}>
                  Create
                </Button>
              </div>
            </>
          ) : (
            <>
              <div style={{ fontSize: '0.9rem' }}>
                <strong>{webName}</strong> is ready. Open this URL on the device and
                tap the screen for fullscreen:
              </div>
              <div style={{
                fontFamily: 'var(--font-family-mono, monospace)', fontSize: '0.85rem',
                background: 'var(--color-background-alt)', border: '1px solid var(--color-border)',
                borderRadius: 'var(--radius-sm)', padding: '0.6rem 0.8rem',
                wordBreak: 'break-all', userSelect: 'all',
              }}>
                {webScreenUrl(createdWebPath)}
              </div>
              <div style={{ fontSize: '0.8rem', color: 'var(--color-text-tertiary)' }}>
                The URL is this screen's key — anyone with it can view the content.
                Deleting the screen revokes the URL. Assign a program to it from the
                Screens list like any other display.
              </div>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem' }}>
                <Button
                  variant="secondary"
                  onClick={() => navigator.clipboard?.writeText(webScreenUrl(createdWebPath))}
                >
                  Copy URL
                </Button>
                <Button variant="primary" onClick={closeWebModal}>
                  Done
                </Button>
              </div>
            </>
          )}
        </div>
      </Modal>

      {/* Virtual display creation modal — dev mode only */}
      <Modal
        isOpen={showAddVirtual}
        onClose={() => { setShowAddVirtual(false); setVirtualError(null); }}
        title="Add Virtual Display"
        size="small"
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div style={{ fontSize: '0.85rem', color: 'var(--color-text-secondary)' }}>
            Virtual displays appear in the Screens view and can be assigned programs, but have no physical hardware. Only available in developer mode (DEBUG=true).
          </div>
          <label style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
            <span style={{ fontWeight: 600 }}>Display Name</span>
            <input
              className="form-input"
              type="text"
              placeholder="e.g. Dev Screen 1"
              value={virtualName}
              onChange={(e) => setVirtualName(e.target.value)}
              disabled={addingVirtual}
              autoFocus
            />
          </label>
          <label style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
            <span style={{ fontWeight: 600 }}>Location</span>
            <input
              className="form-input"
              type="text"
              placeholder="Virtual"
              value={virtualLocation}
              onChange={(e) => setVirtualLocation(e.target.value)}
              disabled={addingVirtual}
            />
          </label>
          <label style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
            <span style={{ fontWeight: 600 }}>Resolution</span>
            <select
              className="form-select"
              value={virtualPreset}
              onChange={(e) => setVirtualPreset(e.target.value)}
              disabled={addingVirtual}
            >
              <option value="landscape_800x480">Landscape 800×480 (7.5" e-paper)</option>
              <option value="portrait_480x800">Portrait 480×800</option>
              <option value="landscape_1280x720">Landscape 1280×720 (HD)</option>
              <option value="portrait_720x1280">Portrait 720×1280</option>
              <option value="square_600x600">Square 600×600</option>
              <option value="landscape_1872x1404">Landscape 1872×1404 (10.3" e-paper)</option>
              <option value="landscape_960x540">Landscape 960×540</option>
            </select>
          </label>
          {virtualError && (
            <div style={{ color: 'var(--color-error)', fontSize: '0.9rem' }}>{virtualError}</div>
          )}
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem' }}>
            <Button variant="secondary" onClick={() => { setShowAddVirtual(false); setVirtualError(null); }} disabled={addingVirtual}>
              Cancel
            </Button>
            <Button variant="primary" onClick={handleAddVirtualDisplay} loading={addingVirtual}>
              Create
            </Button>
          </div>
        </div>
      </Modal>

  {/* DebugPanel now rendered inside Header via rightSlot */}
    </div>{/* end screens-list-pane */}

      {panelDisplay && (
        <ScreenDetailPanel
          display={panelDisplay}
          onClose={() => setPanelDisplay(null)}
          onAssignScene={() => {
            setSelectedDisplay(panelDisplay);
            setShowSceneAssignment(true);
          }}
          onOpenSettings={openDisplaySettings}
        />
      )}
    </div>{/* end screens-split-layout */}
    </PullToRefresh>
  );
};

export default Displays;
