// Multi-Display Management page for v2.3 API
import React, { useState, useEffect, useCallback } from 'react';
import { Monitor, Plus, Search, Filter, MapPin, Wifi, WifiOff, RotateCcw } from 'lucide-react';
import { api } from '../../services/api';
import { useFeatureDetection } from '../../hooks/useFeatureDetection';
import { useWebSocket } from '../../hooks/useWebSocket';
import DisplayCard from './DisplayCard';
import DisplayRegistration from './DisplayRegistration';
import SceneAssignment from './SceneAssignment';
import './Displays.css';

// Global cache for displays data to prevent excessive API requests
let displaysCache = null;
let displaysCacheTime = null;
const DISPLAYS_CACHE_TIMEOUT = 30 * 1000; // 30 seconds

const Displays = () => {
  console.log('🚀 Displays component is rendering!');
  
  const { supportsDisplayManagement } = useFeatureDetection();
  const { isConnected } = useWebSocket();
  
  const [displays, setDisplays] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  // UI state
  const [showRegistration, setShowRegistration] = useState(false);
  const [showSceneAssignment, setShowSceneAssignment] = useState(false);
  const [selectedDisplay, setSelectedDisplay] = useState(null);
  
  // Filtering and search
  const [searchTerm, setSearchTerm] = useState('');
  const [locationFilter, setLocationFilter] = useState('');
  const [onlineFilter, setOnlineFilter] = useState('all'); // 'all', 'online', 'offline'
  const [tagFilter, setTagFilter] = useState('');

  const loadDisplays = useCallback(async () => {
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
        setDisplays(displaysCache);
        setLoading(false);
        return;
      }

      console.log('📡 Fetching fresh displays data');
      const params = {};
      if (onlineFilter !== 'all') {
        params.online_only = onlineFilter === 'online';
      }
      if (locationFilter) {
        params.location = locationFilter;
      }
      if (tagFilter) {
        params.tag = tagFilter;
      }

      const response = await api.getDisplays(params);
      const displaysData = response.data || [];

      // Update cache
      displaysCache = displaysData;
      displaysCacheTime = now;

      setDisplays(displaysData);
    } catch (error) {
      console.error('Error loading displays:', error);
      setError(error.message);
    } finally {
      setLoading(false);
    }
  }, [supportsDisplayManagement, onlineFilter, locationFilter, tagFilter]);

  // Manual refresh that bypasses cache
  const refreshDisplays = useCallback(async () => {
    displaysCache = null;
    displaysCacheTime = null;
    setLoading(true);
    await loadDisplays();
  }, [loadDisplays]);

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
  const filteredDisplays = displays.filter(display => {
    if (searchTerm && !display.name.toLowerCase().includes(searchTerm.toLowerCase()) &&
        !display.description?.toLowerCase().includes(searchTerm.toLowerCase())) {
      return false;
    }
    return true;
  });

  // Get unique locations and tags for filter options
  const locations = [...new Set(displays.map(d => d.location).filter(Boolean))];
  const tags = [...new Set(displays.flatMap(d => d.tags || []))];

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
        </div>
      </div>

      {/* Display Count */}
      <div className="displays-stats">
        <span className="stats-item">
          {filteredDisplays.length} display{filteredDisplays.length !== 1 ? 's' : ''}
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
          {filteredDisplays.map(display => (
            <DisplayCard
              key={display.id}
              display={display}
              onAssignScene={(display) => {
                setSelectedDisplay(display);
                setShowSceneAssignment(true);
              }}
              onEdit={(display) => {
                // TODO: Implement display editing
                console.log('Edit display:', display);
              }}
              onDelete={handleDeleteDisplay}
              onRefresh={refreshDisplays}
            />
          ))}
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
    </div>
  );
};

export default Displays;
