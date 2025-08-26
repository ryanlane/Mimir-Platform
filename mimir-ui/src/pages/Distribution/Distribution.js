import React, { useState, useEffect } from 'react';
import { Database, Activity, BarChart3, Settings, RefreshCw, Zap } from 'lucide-react';
import { api } from '../../services/api';
import { useWebSocket, useWebSocketEvent } from '../../hooks/useWebSocket';
import DistributionMonitor from '../../components/DistributionMonitor/DistributionMonitor';
import './Distribution.css';

const Distribution = () => {
  const { isConnected } = useWebSocket();
  const [distributionStatus, setDistributionStatus] = useState(null);
  const [scenes, setScenes] = useState([]);
  const [displays, setDisplays] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [refreshing, setRefreshing] = useState(false);

  // Load distribution data
  const loadDistributionData = async () => {
    try {
      setError(null);
      
      const [distributionResponse, scenesResponse, displaysResponse] = await Promise.all([
        api.getDistributionOverview().catch(err => {
          console.warn('❌ getDistributionOverview failed:', err);
          return { data: null };
        }),
        api.getScenes().catch(err => {
          console.warn('❌ getScenes failed:', err);
          return { data: { scenes: [] } };
        }),
        api.getDisplays().catch(err => {
          console.warn('❌ getDisplays failed:', err);
          return { data: [] };
        })
      ]);

      setDistributionStatus(distributionResponse.data);
      setScenes(scenesResponse.data.scenes || []);
      setDisplays(Array.isArray(displaysResponse.data) ? displaysResponse.data : []);
    } catch (error) {
      console.error('❌ Error loading distribution data:', error);
      setError('Failed to load distribution data');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  // Manual refresh
  const handleRefresh = async () => {
    setRefreshing(true);
    await loadDistributionData();
  };

  // Refresh scene content
  const handleRefreshSceneContent = async (sceneId) => {
    try {
      await api.refreshSceneContent(sceneId);
      // Reload data to see updated queue status
      await loadDistributionData();
    } catch (error) {
      console.error('❌ Error refreshing scene content:', error);
    }
  };

  // Reset distribution queues
  const handleResetDistribution = async (sceneId) => {
    try {
      await api.resetSceneDistribution(sceneId);
      await loadDistributionData();
    } catch (error) {
      console.error('❌ Error resetting distribution:', error);
    }
  };

  // Listen for distribution performance updates via WebSocket
  useWebSocketEvent('distribution_performance', (data) => {
    console.log('📊 Distribution performance update:', data);
    setDistributionStatus(prev => ({
      ...prev,
      ...data
    }));
  });

  // Listen for scene content refresh events
  useWebSocketEvent('scene_content_refreshed', (data) => {
    console.log('🔄 Scene content refreshed:', data);
    // Refresh the distribution data to see updated queue status
    loadDistributionData();
  });

  useEffect(() => {
    loadDistributionData();
  }, []);

  if (loading && !refreshing) {
    return (
      <div className="loading">
        <div className="loading-spinner"></div>
        <span>Loading distribution system...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="error-state">
        <div className="error-content">
          <h2>Failed to Load Distribution Data</h2>
          <p>{error}</p>
          <button className="btn btn-primary" onClick={loadDistributionData}>
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="distribution-page">
      <div className="page-header">
        <div className="header-content">
          <h1>Distribution System</h1>
          <p className="text-tertiary">
            Monitor and manage Redis-powered content distribution across displays
            {isConnected && <span className="connection-status"> • Live updates enabled</span>}
          </p>
        </div>
        <div className="header-actions">
          <button 
            className={`btn btn-secondary ${refreshing ? 'loading' : ''}`}
            onClick={handleRefresh}
            disabled={refreshing}
          >
            <RefreshCw size={16} className={refreshing ? 'spinning' : ''} />
            {refreshing ? 'Refreshing...' : 'Refresh'}
          </button>
        </div>
      </div>

      <div className="distribution-grid">
        {/* Real-time Distribution Monitor */}
        <div className="distribution-section full-width">
          <DistributionMonitor compact={false} />
        </div>

        {/* Distribution Overview */}
        <div className="distribution-card">
          <div className="card-header">
            <div className="flex items-center gap-sm">
              <BarChart3 size={20} />
              <h3>Distribution Overview</h3>
            </div>
            <button 
              className="btn btn-xs btn-secondary"
              onClick={() => api.getRedisStatus().then(r => console.log('Redis status:', r.data))}
              title="Check Redis status"
            >
              Redis Status
            </button>
          </div>
          <div className="card-body">
            {distributionStatus ? (
              <div className="overview-stats">
                <div className="stat-item">
                  <div className="stat-label">Total Scenes</div>
                  <div className="stat-value">{distributionStatus.total_scenes || 0}</div>
                </div>
                <div className="stat-item">
                  <div className="stat-label">Active Displays</div>
                  <div className="stat-value">{distributionStatus.total_displays || 0}</div>
                </div>
                <div className="stat-item">
                  <div className="stat-label">Active Leases</div>
                  <div className="stat-value">{distributionStatus.active_leases || 0}</div>
                </div>
                <div className="stat-item">
                  <div className="stat-label">Queue Items</div>
                  <div className="stat-value">{distributionStatus.total_queue_items || 0}</div>
                </div>
                <div className="stat-item">
                  <div className="stat-label">Redis Status</div>
                  <div className={`stat-status ${distributionStatus.redis_available ? 'success' : 'error'}`}>
                    {distributionStatus.redis_available ? 'Connected' : 'Disconnected'}
                  </div>
                </div>
                <div className="stat-item">
                  <div className="stat-label">Distribution System</div>
                  <div className={`stat-status ${distributionStatus.distribution_available ? 'success' : 'error'}`}>
                    {distributionStatus.distribution_available ? 'Active' : 'Inactive'}
                  </div>
                </div>
              </div>
            ) : (
              <div className="empty-state">
                <p className="text-tertiary">Distribution overview not available</p>
              </div>
            )}
          </div>
        </div>

        {/* Scene Distribution Status */}
        <div className="distribution-card">
          <div className="card-header">
            <div className="flex items-center gap-sm">
              <Database size={20} />
              <h3>Scene Distribution</h3>
            </div>
          </div>
          <div className="card-body">
            {scenes.length > 0 ? (
              <div className="scenes-distribution-list">
                {scenes.map((scene) => {
                  const connectedDisplays = displays.filter(d => 
                    d.assigned_scene_id === scene.id || d.assignedSceneId === scene.id
                  ).length;
                  
                  return (
                    <div key={scene.id} className="scene-distribution-item">
                      <div className="scene-info">
                        <h4>{scene.name}</h4>
                        <p className="text-tertiary">
                          Mode: {scene.distribution_mode || 'MIRROR'} • 
                          {scene.channels?.length || 0} channels • 
                          {connectedDisplays} displays
                        </p>
                      </div>
                      <div className="scene-actions">
                        <button 
                          className="btn btn-xs btn-secondary"
                          onClick={() => handleRefreshSceneContent(scene.id)}
                          title="Refresh content"
                        >
                          <RefreshCw size={14} />
                        </button>
                        <button 
                          className="btn btn-xs btn-warning"
                          onClick={() => handleResetDistribution(scene.id)}
                          title="Reset distribution queues"
                        >
                          <Settings size={14} />
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="empty-state">
                <p className="text-tertiary">No scenes with distribution available</p>
              </div>
            )}
          </div>
        </div>

        {/* Display Assignment Status */}
        <div className="distribution-card">
          <div className="card-header">
            <div className="flex items-center gap-sm">
              <Activity size={20} />
              <h3>Display Assignments</h3>
            </div>
          </div>
          <div className="card-body">
            {displays.length > 0 ? (
              <div className="displays-assignment-list">
                {displays.map((display) => (
                  <div key={display.id} className="display-assignment-item">
                    <div className="display-info">
                      <h4>{display.name}</h4>
                      <p className="text-tertiary">
                        {display.location || 'No location'} • 
                        {display.assigned_scene_name || 'No scene assigned'}
                      </p>
                    </div>
                    <div className="assignment-status">
                      <div className={`status-indicator ${display.is_online !== false ? 'success' : 'error'}`}>
                        {display.is_online !== false ? 'Online' : 'Offline'}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="empty-state">
                <p className="text-tertiary">No displays registered</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default Distribution;
