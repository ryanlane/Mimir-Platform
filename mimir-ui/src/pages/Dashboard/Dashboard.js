import React, { useState, useEffect } from 'react';
import { Monitor, Layers, Settings, Activity } from 'lucide-react';
import { api } from '../../services/api';
import { useWebSocket, useSceneEvents } from '../../hooks/useWebSocket';
import './Dashboard.css';

const Dashboard = () => {
  const [displayStatus, setDisplayStatus] = useState(null);
  const [scenes, setScenes] = useState([]);
  const [channels, setChannels] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activityLog, setActivityLog] = useState([]);

  // Initialize WebSocket connection
  useWebSocket();

  // Listen to scene events for real-time activity updates
  useSceneEvents({
    onActivated: (data) => {
      console.log('Scene activated via WebSocket:', data);
      // Update display status and add to activity log
      setDisplayStatus(prev => prev ? { ...prev, currentScene: data.sceneId } : null);
      addToActivityLog(`Scene "${data.sceneName || data.sceneId}" activated`);
    },
    onDeactivated: (data) => {
      console.log('Scene deactivated via WebSocket:', data);
      setDisplayStatus(prev => prev ? { ...prev, currentScene: null } : null);
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
    loadDashboardData();
  }, []);

  const loadDashboardData = async () => {
    try {
      const [displayResponse, scenesResponse, channelsResponse] = await Promise.all([
        api.getDisplayStatus(),
        api.getScenes({ limit: 5 }),
        api.getChannels({ limit: 5 })
      ]);

      setDisplayStatus(displayResponse.data);
      setScenes(scenesResponse.data.scenes || []);
      setChannels(channelsResponse.data.channels || []);
    } catch (error) {
      console.error('Error loading dashboard data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleActivateScene = async (sceneId) => {
    try {
      const isCurrentlyActive = displayStatus?.currentScene === sceneId;
      if (isCurrentlyActive) {
        await api.deactivateScene(sceneId);
      } else {
        await api.activateScene(sceneId);
      }
      await loadDashboardData(); // Refresh all data to update the current scene
    } catch (error) {
      console.error('Error toggling scene activation:', error);
    }
  };

  const handleDisplayScene = async (sceneId) => {
    try {
      await api.displayScene(sceneId);
      await loadDashboardData(); // Refresh data
    } catch (error) {
      console.error('Error displaying scene:', error);
    }
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
        <p className="text-tertiary">Monitor and control your Mimir display platform</p>
      </div>

      <div className="dashboard-grid">
        {/* Display Status */}
        <div className="dashboard-card">
          <div className="card-header">
            <div className="flex items-center gap-sm">
              <Monitor size={20} />
              <h3 className="card-title">Display Status</h3>
            </div>
          </div>
          <div className="card-body">
            {displayStatus && (
              <div className="display-status">
                <div className="status-row">
                  <span>Hardware:</span>
                  <span className={`status-indicator ${displayStatus.hardware?.available ? 'status-success' : 'status-error'}`}>
                    {displayStatus.hardware?.type || 'Unknown'}
                  </span>
                </div>
                <div className="status-row">
                  <span>Resolution:</span>
                  <span>{displayStatus.resolution ? displayStatus.resolution.join(' × ') : 'Unknown'}</span>
                </div>
                <div className="status-row">
                  <span>Current Scene:</span>
                  <span>{displayStatus.currentScene || 'None'}</span>
                </div>
                {displayStatus.currentImage && (
                  <div className="status-row">
                    <span>Last Update:</span>
                    <span>{new Date(displayStatus.currentImage.uploadedAt).toLocaleString()}</span>
                  </div>
                )}
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
                  const isActive = displayStatus?.currentScene === scene.id;
                  return (
                    <div key={scene.id} className={`scene-item ${isActive ? 'scene-item-active' : ''}`}>
                      <div className="scene-info">
                        <h4>
                          {scene.name}
                          {isActive && <span className="active-badge">Active</span>}
                        </h4>
                        <p className="text-tertiary">
                          {scene.channels?.length || 0} channels
                        </p>
                      </div>
                      <div className="scene-actions">
                        <button 
                          className={`btn btn-sm ${isActive ? 'btn-warning' : 'btn-primary'}`}
                          onClick={() => handleActivateScene(scene.id)}
                        >
                          {isActive ? 'Deactivate' : 'Activate'}
                        </button>
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
