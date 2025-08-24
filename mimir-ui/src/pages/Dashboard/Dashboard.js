import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Monitor, Layers, Settings, Activity } from 'lucide-react';
import { api } from '../../services/api';
import { useEnsureFreshState, useSceneEvents } from '../../hooks/useWebSocket';
// import WebSocketStatus from '../../components/WebSocketStatus/WebSocketStatus';
import './Dashboard.css';

const Dashboard = () => {
  const [displayStatus, setDisplayStatus] = useState(null);
  const [displays, setDisplays] = useState([]);
  const [scenes, setScenes] = useState([]);
  const [channels, setChannels] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activityLog, setActivityLog] = useState([]);

  // Initialize WebSocket connection with automatic state sync on mount
  const { isConnected, currentState } = useEnsureFreshState();

  // Listen to scene events for real-time activity updates
  useSceneEvents({
    onActivated: (data) => {
      console.log('🟢 Dashboard: Scene activated via WebSocket:', data);
      // Update display status and add to activity log
      const sceneId = data?.sceneId || data?.scene_id || data?.id;
      const sceneName = data?.sceneName || data?.scene_name;
      console.log('🔄 Dashboard: Current display status before update:', displayStatus);
      console.log('🔄 Dashboard: Updating with scene ID:', sceneId);
      setDisplayStatus(prev => {
        const newStatus = prev ? { ...prev, currentScene: sceneId, currentSceneName: sceneName } : { currentScene: sceneId, currentSceneName: sceneName };
        console.log('🔄 Dashboard: New display status after activation:', newStatus);
        return newStatus;
      });
      addToActivityLog(`Scene "${sceneName || sceneId}" activated`);
    },
    onDeactivated: (data) => {
      console.log('🔴 Dashboard: Scene deactivated via WebSocket:', data);
      console.log('🔄 Dashboard: Current display status before deactivation:', displayStatus);
      setDisplayStatus(prev => {
        const newStatus = prev ? { ...prev, currentScene: null, currentSceneName: null } : null;
        console.log('🔄 Dashboard: New display status after deactivation:', newStatus);
        return newStatus;
      });
      addToActivityLog(`Scene "${data.sceneName || data.sceneId}" deactivated`);
    },
    onDisplayed: (data) => {
      console.log('Scene displayed via WebSocket:', data);
      addToActivityLog(`Scene "${data.sceneName || data.sceneId}" displayed`);
    },
    onCreated: (data) => {
      console.log('Scene created via WebSocket:', data);
      addToActivityLog(`Scene "${data.sceneName || data.sceneId}" created`);
      loadDashboardData(); // Refresh scenes list
    },
    onDeleted: (data) => {
      console.log('Scene deleted via WebSocket:', data);
      addToActivityLog(`Scene "${data.sceneName || data.sceneId}" deleted`);
      loadDashboardData(); // Refresh scenes list
    }
  });

  const addToActivityLog = (message) => {
    const newActivity = {
      timestamp: new Date().toLocaleTimeString(),
      message
    };
    setActivityLog(prev => [newActivity, ...prev.slice(0, 9)]); // Keep last 10 items
  };

  useEffect(() => {
    // Wait a bit for WebSocket to potentially connect and provide state
    const timer = setTimeout(() => {
      if (!currentState && !isConnected) {
        console.log('⏰ WebSocket not connected after timeout, loading via API as fallback');
        loadDashboardData();
      } else if (!currentState && isConnected) {
        console.log('⏰ WebSocket connected but no state received, loading via API');
        loadDashboardData();
      } else {
        console.log('✅ Using WebSocket state, skipping API load');
      }
    }, 1000); // Give WebSocket 1 second to connect and send state

    return () => clearTimeout(timer);
  }, [currentState, isConnected]);

  // Handle full state received on connection
  useEffect(() => {
    if (currentState?.displayStatus) {
      console.log('🚀 Dashboard initializing from full state:', currentState.displayStatus);
      setDisplayStatus(currentState.displayStatus);
      setLoading(false); // Mark as loaded from WebSocket
      
      // Also update scenes if provided
      if (currentState.allScenes) {
        console.log('📋 Setting scenes from WebSocket:', currentState.allScenes);
        setScenes(currentState.allScenes);
      }
      
      // Update channels if provided
      if (currentState.channels) {
        console.log('🔌 Setting channels from WebSocket:', currentState.channels);
        setChannels(currentState.channels);
      }

      // Update displays if provided
      if (currentState.displays) {
        console.log('📺 Setting displays from WebSocket:', currentState.displays);
        setDisplays(currentState.displays);
      }
      
      // Add activity log entry for connection
      addToActivityLog('WebSocket connected with live state');
    }
  }, [currentState]);

  const loadDashboardData = async () => {
    try {
      const [displayResponse, scenesResponse, channelsResponse, displaysResponse] = await Promise.all([
        api.getDisplayStatus(),
        api.getScenes({ limit: 5 }),
        api.getChannels({ limit: 5 }),
        api.getDisplays({ limit: 10 })
      ]);

      setDisplayStatus(displayResponse.data);
      setScenes(scenesResponse.data.scenes || []);
      setChannels(channelsResponse.data.channels || []);
      setDisplays(displaysResponse.data || []);
    } catch (error) {
      console.error('Error loading dashboard data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleDisplayScene = async (sceneId) => {
    try {
      console.log(`📺 Dashboard: Displaying scene ${sceneId}`);
      await api.displayScene(sceneId);
      console.log('📺 Dashboard: Display action completed');
    } catch (error) {
      console.error('Error displaying scene:', error);
    }
  };

  // Helper to count displays connected to a scene
  const getDisplaysConnectedToScene = (sceneId) => {
    return displays.filter(display => 
      display.assigned_scene_id === sceneId || 
      display.assignedSceneId === sceneId
    ).length;
  };

  // Helper to get connected displays that have scenes assigned
  const getConnectedDisplays = () => {
    return displays.filter(display => 
      display.isOnline !== false && 
      (display.assigned_scene_id || display.assignedSceneId)
    );
  };

  if (loading) {
    return (
      <div className="loading">
        <div className="loading-spinner"></div>
        <span>Loading dashboard...</span>
      </div>
    );
  }

  return (
    <div className="dashboard">
      <div className="dashboard-header">
        <h1>Dashboard</h1>
        <p className="text-tertiary">
          Monitor and control your Mimir display platform
          {isConnected && <span className="connection-status"> • Live updates enabled</span>}
        </p>
      </div>

      {/* WebSocket Status Component */}
      {/* <WebSocketStatus /> */}

      <div className="dashboard-grid">
        {/* Display Status */}
        <div className="dashboard-card">
          <div className="card-header">
            <div className="flex items-center gap-sm">
              <Monitor size={20} />
              <h3 className="card-title">
                <Link to="/displays" className="display-status-header-link">
                  Display Status
                </Link>
              </h3>
            </div>
          </div>
          <div className="card-body">
            {getConnectedDisplays().length > 0 ? (
              <div className="displays-list">
                {getConnectedDisplays().map((display) => (
                  <div key={display.id} className="display-item">
                    <div className="display-info">
                      <h4>{display.name}</h4>
                      <p className="text-tertiary">
                        {display.location || 'No location set'}
                      </p>
                    </div>
                    <div className="display-status">
                      <div className="status-row">
                        <span>Scene:</span>
                        <span>{display.assigned_scene_name || display.assignedSceneName || 'None'}</span>
                      </div>
                      <div className="status-row">
                        <span>Status:</span>
                        <span className={`status-indicator ${display.isOnline !== false ? 'status-success' : 'status-error'}`}>
                          {display.isOnline !== false ? 'Online' : 'Offline'}
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="empty-state">
                <p className="text-tertiary">No displays connected to scenes</p>
                <Link to="/displays" className="btn btn-sm btn-primary">
                  Manage Displays
                </Link>
              </div>
            )}
          </div>
        </div>

        {/* Recent Scenes */}
        <div className="dashboard-card">
          <div className="card-header">
            <div className="flex items-center gap-sm">
              <Layers size={20} />
              <h3 className="card-title">Recent Scenes</h3>
            </div>
          </div>
          <div className="card-body">
            {scenes.length > 0 ? (
              <div className="scenes-list">
                {scenes.map((scene) => {
                  const connectedDisplays = getDisplaysConnectedToScene(scene.id);
                  return (
                    <div key={scene.id} className="scene-item">
                      <div className="scene-info">
                        <h4>{scene.name}</h4>
                        <p className="text-tertiary">
                          {scene.channels?.length || 0} channels • {connectedDisplays} {connectedDisplays === 1 ? 'display' : 'displays'} connected
                        </p>
                      </div>
                      <div className="scene-actions">
                        <button 
                          className="btn btn-sm btn-accent"
                          onClick={() => handleDisplayScene(scene.id)}
                        >
                          Display
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <p className="text-tertiary">No scenes available</p>
            )}
          </div>
        </div>

        {/* Channel Status */}
        <div className="dashboard-card">
          <div className="card-header">
            <div className="flex items-center gap-sm">
              <Settings size={20} />
              <h3 className="card-title">Channel Status</h3>
            </div>
          </div>
          <div className="card-body">
            {channels.length > 0 ? (
              <div className="channels-list">
                {channels.map((channel) => (
                  <div key={channel.id} className="channel-item">
                    <div className="channel-info">
                      <h4>{channel.name}</h4>
                      <p className="text-tertiary">{channel.description}</p>
                    </div>
                    <div className="channel-status">
                      <span className={`status-indicator ${
                        channel.status?.usingFallback ? 'status-warning' : 'status-success'
                      }`}>
                        {channel.status?.usingFallback ? 'Fallback' : 'Active'}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-tertiary">No channels available</p>
            )}
          </div>
        </div>

        {/* System Activity */}
        <div className="dashboard-card">
          <div className="card-header">
            <div className="flex items-center gap-sm">
              <Activity size={20} />
              <h3 className="card-title">System Activity</h3>
            </div>
          </div>
          <div className="card-body">
            <div className="activity-list">
              <div className="activity-item">
                <span className="activity-time">
                  {new Date().toLocaleTimeString()}
                </span>
                <span>Dashboard loaded</span>
              </div>
              {activityLog.map((activity, index) => (
                <div key={index} className="activity-item">
                  <span className="activity-time">
                    {activity.timestamp}
                  </span>
                  <span>{activity.message}</span>
                </div>
              ))}
              {displayStatus?.currentScene && (
                <div className="activity-item">
                  <span className="activity-time">
                    {displayStatus.currentImage?.uploadedAt ? 
                      new Date(displayStatus.currentImage.uploadedAt).toLocaleTimeString() : 
                      'Unknown'
                    }
                  </span>
                  <span>Scene "{displayStatus.currentScene}" displayed</span>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
