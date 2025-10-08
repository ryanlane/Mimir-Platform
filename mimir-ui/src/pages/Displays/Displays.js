// Multi-Display Management page for v2.3 API
import React, { useState, useEffect, useCallback } from 'react';
import { Monitor, Search, Filter, MapPin, Wifi, WifiOff, RotateCcw } from 'lucide-react';
import { api } from '../../services/api';
import { useFeatureDetection } from '../../hooks/useFeatureDetection';
import { useWebSocket } from '../../hooks/useWebSocket';
import featureDetection from '../../services/featureDetection';
import DisplayCard from './DisplayCard';
import PullToRefresh from '../../components/PullToRefresh/PullToRefresh';
import SceneAssignment from './SceneAssignment';
import DebugPanel from '../../components/DebugPanel/DebugPanel';
import './Displays.css';
import Header from '../../components/Header/Header';
import Button from '../../components/Button/Button';

// Global cache for displays data to prevent excessive API requests
let displaysCache = null;
let displaysCacheTime = null;
const DISPLAYS_CACHE_TIMEOUT = 30 * 1000; // 30 seconds

const Displays = () => {
  console.log('🚀 Displays component is rendering!');
  
  const { supportsDisplayManagement, isLoading, apiVersion, supportedFeatures } = useFeatureDetection();
  const { isConnected } = useWebSocket();
  
  const [displays, setDisplays] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  // Image update activity indicator state – toggles true briefly on any image update WS event
  const [imageActivity, setImageActivity] = useState(false);
  // Auto fade-out for image activity indicator
  useEffect(() => {
    if (!imageActivity) return;
    const timeout = setTimeout(() => setImageActivity(false), 3500); // matches CSS fade duration
    return () => clearTimeout(timeout);
  }, [imageActivity]);
  
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
      const [displaysResponse, discoveryResponse, statsResponse] = await Promise.all([
        api.getDisplays(params),
        api.getDiscoveryStatus().catch(err => {
          console.warn('Discovery status not available:', err);
          return null;
        }),
        api.getDiscoveryStatus().catch(err => {
          console.warn('Discovered display stats not available:', err);
          return null;
        })
      ]);

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
        const normalized = {
          ...display,
          source: display.displayType || 'registered', // Use displayType as source
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

    const mergeDisplayUpdate = (deviceId, partial) => {
      setDisplays(prev => {
        let found = false;
        let changed = false;
        const updated = prev.map(d => {
          const idMatch = d.id === deviceId || d.device_id === deviceId;
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
            setDisplays(prev => prev.map(display => display.id === payload.displayId ? (display.current_image_url === payload.imageUrl ? display : { ...display, current_image_url: payload.imageUrl, last_image_update_ts: new Date().toISOString() }) : display));
            setImageActivity(true); // legacy event still counts
            return;
          case 'mqtt_message': {
            // Normalize nested mqtt message shape so existing topic-based parser can run
            const topic = payload.data?.topic;
            const mqttInner = payload.data?.payload;
            if (topic && mqttInner) {
              // Directly handle image display commands so we don't rely solely on generic parsing
              // Expect topics like mimir/<device>/cmd with payload.type === 'display_image'
              const cmdMatch = /^mimir\/(.+?)\/cmd$/.exec(topic);
              if (cmdMatch && mqttInner?.type === 'display_image' && mqttInner.image_url) {
                const deviceId = cmdMatch[1];
                console.log('🖼️ Incoming display_image for device', deviceId, mqttInner.image_url);
                setDisplays(prev => prev.map(d => {
                  if (d.id === deviceId || d.device_id === deviceId) {
                    // Only update timestamp if the image actually changed to avoid perpetual 'Just now'
                    if (d.current_image_url === mqttInner.image_url) {
                      return d; // no change; do NOT pulse activity
                    }
                    return {
                      ...d,
                      current_image_url: mqttInner.image_url,
                      last_image_update_ts: mqttInner.timestamp || new Date().toISOString()
                    };
                  }
                  return d;
                }));
                setImageActivity(true); // pulse only on actual new image
                return; // handled
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
                  // treat rendered ack as activity pulse
                  // 'rendered' evt no longer pulses image activity to reduce noise
                  return;
                }
              } catch (e) {
                console.warn('Failed inner mqtt_message normalization', e);
              }
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
  }, [refreshDisplays]);


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
    if (!window.confirm('Are you sure you want to delete this display client?')) {
      return;
    }

    try {
      await api.deleteDisplay(displayId);
      refreshDisplays();
    } catch (error) {
      console.error('Error deleting display:', error);
      alert('Failed to delete display: ' + error.message);
    }
  };

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

  return (
    <PullToRefresh onRefresh={refreshDisplays}>
    <div className="page-container">
        <Header
          title="Displays"
          icon="MonitorSpeaker"
          iconSize={36}
          description="Manage display clients and scene assignments"
          actions={[
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
              placeholder="Search displays..."
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
              <option value="all">All Displays</option>
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
          {filteredDisplays.length} display{filteredDisplays.length !== 1 ? 's' : ''}
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
        <div className="loading-state">
          <div className="spinner" />
          <p>Loading displays...</p>
        </div>
      ) : error ? (
        <div className="error-state">
          <h3>Error Loading Displays</h3>
          <p>{error}</p>
          <button className="btn btn-primary" onClick={refreshDisplays}>
            Try Again
          </button>
        </div>
      ) : filteredDisplays.length === 0 ? (
        <div className="empty-state">
          <h3>No Displays Found</h3>
          <p className="text-tertiary">
            {displays.length === 0 
              ? "No display clients have been registered yet."
              : "No displays match your current filters."
            }
          </p>
        </div>
      ) : (
        <div className="displays-grid">
          {console.log('🔍 About to render', filteredDisplays.length, 'display cards')}
          {filteredDisplays.map((display, index) => {
            console.log(`🔍 Rendering DisplayCard ${index} for:`, display.name, 'with ID:', display.id);
            return (
              <DisplayCard
                key={display.id}
                display={display}
                onAssignScene={(display) => {
                  setSelectedDisplay(display);
                  setShowSceneAssignment(true);
                }}
                onEdit={(display, action) => {
                  if (action === 'approve' && display.displayType === 'discovered') {
                    // Optimistic state update
                    setDisplays(prev => prev.map(d => d.id === display.id ? { ...d, approving: true } : d));
                    api.approveDiscoveredDisplay(display.id)
                      .then(() => refreshDisplays())
                      .catch(err => {
                        console.error('Approve failed', err);
                        setDisplays(prev => prev.map(d => d.id === display.id ? { ...d, approving: false, approve_error: err.message } : d));
                      });
                  } else if (action === 'reject' && display.displayType === 'discovered') {
                    // Optimistic removal
                    const original = displays;
                    setDisplays(prev => prev.filter(d => d.id !== display.id));
                    api.rejectDiscoveredDisplay(display.id)
                      .then(() => refreshDisplays())
                      .catch(err => {
                        console.error('Reject failed', err);
                        // Revert on failure
                        setDisplays(original);
                      });
                  } else if (action === 'register' && display.displayType === 'discovered') {
                    setSelectedDisplay({
                      ...display,
                      name: display.name || display.service_name,
                      ip_address: display.addresses?.[0] || display.ip_address,
                      port: display.webhook_port || display.port,
                      resolution: display.resolution || [display.width, display.height],
                      orientation: display.orientation || 'landscape'
                    });
                  } else if (display.displayType === 'registered') {
                    console.log('Edit registered display:', display);
                  } else {
                    console.log('Interact with discovered display:', display);
                  }
                }}
                onDelete={handleDeleteDisplay}
                onRefresh={refreshDisplays}
              />
            );
          })}
        </div>
      )}

      {/* Modals */}
      

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
      
  {/* DebugPanel now rendered inside Header via rightSlot */}
    </div>
    </PullToRefresh>
  );
};

export default Displays;
