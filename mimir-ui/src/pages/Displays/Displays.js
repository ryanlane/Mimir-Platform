// Multi-Display Management page for v2.3 API
import React, { useState, useEffect, useCallback } from 'react';
import { Monitor, Plus, Search, Filter, MapPin, Wifi, WifiOff, RotateCcw } from 'lucide-react';
import { api } from '../../services/api';
import { useFeatureDetection } from '../../hooks/useFeatureDetection';
import { useWebSocket } from '../../hooks/useWebSocket';
import featureDetection from '../../services/featureDetection';
import DisplayCard from './DisplayCard';
import DisplayRegistration from './DisplayRegistration';
import SceneAssignment from './SceneAssignment';
import DebugPanel from '../../components/DebugPanel/DebugPanel';
import './Displays.css';

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
  const [showRegistration, setShowRegistration] = useState(false);
  const [showSceneAssignment, setShowSceneAssignment] = useState(false);
  const [selectedDisplay, setSelectedDisplay] = useState(null);
  
  // Filtering and search
  const [searchTerm, setSearchTerm] = useState('');
  const [locationFilter, setLocationFilter] = useState('');
  const [onlineFilter, setOnlineFilter] = useState('all'); // 'all', 'online', 'offline'
  const [tagFilter, setTagFilter] = useState('');
  const [includeDiscovered, setIncludeDiscovered] = useState(true);
  
  // Discovery service status
  const [discoveryStatus, setDiscoveryStatus] = useState(null);

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
      const [displaysResponse, discoveryResponse] = await Promise.all([
        api.getDisplays(params),
        api.getDiscoveryStatus().catch(err => {
          console.warn('Discovery status not available:', err);
          return null;
        })
      ]);

      const allDisplays = displaysResponse.data?.data || displaysResponse.data || [];
      const discoveryData = discoveryResponse?.data || null;

      // Normalize the display data and set source based on displayType
      const normalizedDisplays = allDisplays.map(display => ({
        ...display,
        source: display.displayType || 'registered', // Use displayType as source
        is_online: display.isOnline !== undefined ? display.isOnline : display.is_online,
        last_seen: display.lastSeen || display.last_seen,
        resolution: display.resolution || (display.width && display.height ? [display.width, display.height] : null)
      }));

      console.log('🔍 Debug - Total displays from API:', allDisplays.length);
      console.log('🔍 Debug - Normalized displays:', normalizedDisplays.length);
      console.log('🔍 Debug - Displays by type:', {
        discovered: normalizedDisplays.filter(d => d.displayType === 'discovered').length,
        registered: normalizedDisplays.filter(d => d.displayType === 'registered').length
      });

      // Update cache
      displaysCache = { displays: normalizedDisplays, discoveryStatus: discoveryData };
      displaysCacheTime = Date.now();

      console.log('🎯 About to set displays state with:', normalizedDisplays.length, 'displays');
      setDisplays(normalizedDisplays);
      setDiscoveryStatus(discoveryData);
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
    displaysCache = null;
    displaysCacheTime = null;
    setLoading(true);
    await loadDisplays();
  }, [loadDisplays]);

  // Trigger discovery
  const triggerDiscovery = useCallback(async () => {
    try {
      console.log('🔍 Triggering display discovery...');
      await api.discoverDisplays();
      // Refresh displays after discovery
      await refreshDisplays();
    } catch (error) {
      console.error('Error triggering discovery:', error);
      setError('Discovery failed: ' + error.message);
    }
  }, [refreshDisplays]);

  useEffect(() => {
    loadDisplays();
  }, [loadDisplays]);

  // WebSocket event handlers for real-time updates
  useEffect(() => {
    const handleDisplayEvent = (event) => {
      if (!event.data) return;
      
      switch (event.data.type) {
        case 'display_client_registered':
          console.log('🖥️ New display registered:', event.data);
          refreshDisplays();
          break;
        case 'display_scene_assigned':
        case 'display_scene_unassigned':
          console.log('🎬 Display scene assignment changed:', event.data);
          refreshDisplays();
          break;
        case 'display_image_updated':
          console.log('🖼️ Display image updated:', event.data);
          // Update specific display without full refresh
          setDisplays(prev => prev.map(display => 
            display.id === event.data.displayId 
              ? { ...display, current_image_url: event.data.imageUrl }
              : display
          ));
          break;
        default:
          break;
      }
    };

    window.addEventListener('websocket-message', handleDisplayEvent);
    return () => window.removeEventListener('websocket-message', handleDisplayEvent);
  }, [refreshDisplays]);

  // Handle display actions
  const handleDisplayRegistered = (newDisplay) => {
    setShowRegistration(false);
    refreshDisplays();
  };

  const handleSceneAssigned = (displayId, sceneId) => {
    setShowSceneAssignment(false);
    setSelectedDisplay(null);
    refreshDisplays();
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
        <div className="page-header">
          <h1 className="page-title">
            <Monitor size={24} />
            Displays
          </h1>
        </div>
        
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
    <div className="page-container">
      <div className="page-header">
        <div className="page-title-section">
          <h1 className="page-title">
            <Monitor size={24} />
            Displays
            {isConnected && <span className="connection-status connected">Live</span>}
          </h1>
          <p className="page-subtitle">
            Manage display clients and scene assignments
          </p>
        </div>
        
        <div className="page-actions">
          <button 
            className="btn btn-secondary" 
            onClick={triggerDiscovery}
            disabled={loading}
            title="Discover displays on network"
          >
            <Search size={18} />
            Discover
          </button>
          <button 
            className="btn btn-secondary" 
            onClick={refreshDisplays}
            disabled={loading}
          >
            <RotateCcw size={18} />
            Refresh
          </button>
          <button 
            className="btn btn-primary" 
            onClick={() => setShowRegistration(true)}
          >
            <Plus size={18} />
            Register Display
          </button>
        </div>
      </div>

      {/* Discovery Status */}
      {discoveryStatus && (
        <div className="discovery-status">
          <div className="discovery-info">
            <div className="discovery-indicator">
              {discoveryStatus.service_status?.is_running ? (
                <>
                  <div className="status-dot online"></div>
                  <span>mDNS Discovery Active</span>
                </>
              ) : (
                <>
                  <div className="status-dot offline"></div>
                  <span>mDNS Discovery Inactive</span>
                </>
              )}
            </div>
            {discoveryStatus.service_status?.is_running && (
              <div className="discovery-stats">
                <span>{discoveryStatus.service_status.total_discovered} discovered</span>
                <span>{discoveryStatus.service_status.online_displays} online</span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Search and Filters */}
      <div className="displays-controls">
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
        </div>

        <div className="filters-section">
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
          <button className="btn btn-primary" onClick={() => setShowRegistration(true)}>
            <Plus size={18} />
            Register First Display
          </button>
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
                if (action === 'register' && display.displayType === 'discovered') {
                  // Optional registration for discovered display
                  setSelectedDisplay({
                    ...display,
                    // Convert discovered display to registration format
                    name: display.name || display.service_name,
                    ip_address: display.addresses?.[0] || display.ip_address,
                    port: display.webhook_port || display.port,
                    resolution: display.resolution || [display.width, display.height],
                    orientation: display.orientation || 'landscape'
                  });
                  setShowRegistration(true);
                } else if (display.displayType === 'registered') {
                  // Edit registered display
                  console.log('Edit registered display:', display);
                  // TODO: Implement display editing for registered displays
                } else {
                  // Direct interaction with discovered display (no registration needed)
                  console.log('Interact with discovered display:', display);
                  // TODO: Implement direct display interaction
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
      {showRegistration && (
        <DisplayRegistration
          onClose={() => setShowRegistration(false)}
          onSuccess={handleDisplayRegistered}
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
      
      <DebugPanel />
    </div>
  );
};

export default Displays;
