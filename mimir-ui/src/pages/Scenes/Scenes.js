import React, { useState, useEffect, useCallback } from 'react';
import { Plus, Monitor, Edit, Trash2, RefreshCw } from 'lucide-react';
import { api } from '../../services/api';
import { useEnsureFreshState, useSceneEvents } from '../../hooks/useWebSocket';
import SceneForm from './SceneForm';
import './Scenes.css';

const Scenes = () => {
  const [scenes, setScenes] = useState([]);
  const [channels, setChannels] = useState([]);
  const [overlays, setOverlays] = useState([]);
  const [displayStatus, setDisplayStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingScene, setEditingScene] = useState(null);

  // Initialize WebSocket connection with automatic state sync on mount
  const { isConnected, currentState, requestStateSync } = useEnsureFreshState();

  const loadData = useCallback(async () => {
    try {
      const [scenesResponse, channelsResponse, overlaysResponse, displayResponse] = await Promise.all([
        api.getScenes(),
        api.getChannels(),
        api.getOverlays(),
        api.getDisplayStatus()
      ]);

      console.log('Display response:', displayResponse.data);
      console.log('Current scene from API:', displayResponse.data.currentScene);

      setScenes(scenesResponse.data.scenes || []);
      setChannels(channelsResponse.data.channels || []);
      setOverlays(overlaysResponse.data.overlays || []);
      
      // Only set display status if we don't have WebSocket state
      if (!currentState?.displayStatus) {
        setDisplayStatus(displayResponse.data);
        console.log('Set displayStatus from API to:', displayResponse.data);
      } else {
        console.log('🚫 Skipping display status update - using WebSocket state');
      }
    } catch (error) {
      console.error('Error loading data:', error);
    } finally {
      setLoading(false);
    }
  }, [currentState]);

  // Listen to scene events via WebSocket
  useSceneEvents({
    onActivated: (data) => {
      console.log('🟢 Scene activated via WebSocket:', data);
      // Use enhanced event data
      const sceneId = data?.sceneId || data?.scene_id || data?.id;
      const sceneName = data?.sceneName || data?.scene_name;
      if (sceneId) {
        const newDisplayStatus = { 
          ...displayStatus,
          currentScene: sceneId,
          currentSceneName: sceneName 
        };
        console.log('🔄 Setting new display status:', newDisplayStatus);
        setDisplayStatus(newDisplayStatus);
        console.log('✅ Set active scene to:', sceneId, sceneName);
      } else {
        console.warn('❌ Scene activated but no scene ID found in data:', data);
      }
    },
    onDeactivated: (data) => {
      console.log('🔴 Scene deactivated via WebSocket:', data);
      const newDisplayStatus = { 
        ...displayStatus,
        currentScene: null,
        currentSceneName: null 
      };
      console.log('🔄 Setting new display status (deactivated):', newDisplayStatus);
      setDisplayStatus(newDisplayStatus);
      console.log('✅ Set active scene to null');
    },
    onCreated: (data) => {
      console.log('➕ Scene created via WebSocket:', data);
      loadData(); // Refresh the list
    },
    onUpdated: (data) => {
      console.log('✏️ Scene updated via WebSocket:', data);
      loadData(); // Refresh the list
    },
    onDeleted: (data) => {
      console.log('🗑️ Scene deleted via WebSocket:', data);
      loadData(); // Refresh the list
    },
    onDisplayed: (data) => {
      console.log('📺 Scene displayed via WebSocket:', data);
      // Could show a notification here
    }
  });

  // Handle full state received on connection
  useEffect(() => {
    if (currentState?.displayStatus) {
      console.log('🚀 Initializing from full state:', currentState.displayStatus);
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
      
      // Force re-render to ensure UI updates
      console.log('🔄 Forcing component re-render after WebSocket state update');
    }
  }, [currentState]);

  useEffect(() => {
    // Wait a bit for WebSocket to potentially connect and provide state
    const timer = setTimeout(() => {
      if (!currentState && !isConnected) {
        console.log('⏰ WebSocket not connected after timeout, loading via API as fallback');
        loadData();
      } else if (!currentState && isConnected) {
        console.log('⏰ WebSocket connected but no state received, loading via API');
        loadData();
      } else {
        console.log('✅ Using WebSocket state, skipping API load');
      }
    }, 1000); // Give WebSocket 1 second to connect and send state

    return () => clearTimeout(timer);
  }, [currentState, isConnected, loadData]);

  // Debug useEffect to monitor activeScene changes
  useEffect(() => {
    console.log('🎯 Active scene changed to:', displayStatus?.currentScene);
    console.log('🎯 Full displayStatus:', displayStatus);
  }, [displayStatus]);

  const getChannelThumbnail = (channelId) => {
    const channel = channels.find(c => c.id === channelId);
    if (!channel) return null;
    
    // For photo frame channels, try to get the current image
    if (channel.id === 'com.epaperframe.photoframe' || channel.name?.toLowerCase().includes('photo')) {
      return api.getChannelImageUrl(channelId, 'image');
    }
    
    // For other channels, check if they have a thumbnail or current image endpoint
    if (channel.config?.current_image) {
      return api.getChannelImageUrl(channelId, channel.config.current_image);
    }
    
    return null;
  };

  const handleCreateScene = () => {
    setEditingScene(null);
    setShowForm(true);
  };

  const handleEditScene = (scene) => {
    setEditingScene(scene);
    setShowForm(true);
  };

  const handleDeleteScene = async (sceneId) => {
    if (window.confirm('Are you sure you want to delete this scene?')) {
      try {
        await api.deleteScene(sceneId);
        await loadData();
      } catch (error) {
        console.error('Error deleting scene:', error);
      }
    }
  };

  const handleDisplayScene = async (sceneId) => {
    try {
      await api.displayScene(sceneId);
    } catch (error) {
      console.error('Error displaying scene:', error);
    }
  };

  const handleFormClose = () => {
    setShowForm(false);
    setEditingScene(null);
    loadData();
  };

  if (loading) {
    return (
      <div className="loading">
        <div className="loading-spinner"></div>
        <span>
          {isConnected ? 'Loading from WebSocket...' : 'Connecting and loading...'}
        </span>
      </div>
    );
  }

  return (
    <div className="scenes">
      <div className="scenes-header">
        <div>
          <h1>Scenes</h1>
          <p className="text-tertiary">
            Manage your display scenes and configurations
            {isConnected && <span className="connection-status"> • Live updates enabled</span>}
          </p>
        </div>
        <div className="scenes-header-actions">
          <button className="btn btn-secondary" onClick={() => {
            console.log('🔄 Manual state sync requested');
            requestStateSync();
          }}>
            <RefreshCw size={18} />
            Sync State
          </button>
          <button className="btn btn-primary" onClick={handleCreateScene}>
            <Plus size={18} />
            Create Scene
          </button>
        </div>
      </div>

      {scenes.length > 0 ? (
        <div className="scenes-grid">
          {scenes.map((scene) => {
            // Get thumbnail from first channel if available
            const firstChannelAssignment = scene.channels && scene.channels.length > 0 
              ? scene.channels[0] 
              : null;
            
            // Handle both old format (string) and new format (object)
            const firstChannelId = firstChannelAssignment 
              ? (typeof firstChannelAssignment === 'string' 
                  ? firstChannelAssignment 
                  : firstChannelAssignment.channel_id)
              : null;
              
            const thumbnailUrl = firstChannelId ? getChannelThumbnail(firstChannelId) : null;
              
            return (
              <div key={scene.id} className="scene-card">
                <div className="scene-card-header">
                  <div className="scene-title-container">
                    <h3>{scene.name}</h3>
                  </div>
                  <div className="scene-actions">
                    <button
                      className="btn btn-sm"
                      onClick={() => handleEditScene(scene)}
                    >
                      <Edit size={16} />
                    </button>
                    <button
                      className="btn btn-sm btn-error"
                      onClick={() => handleDeleteScene(scene.id)}
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                </div>

                <div className="scene-card-body">
                  {thumbnailUrl && (
                    <div className="scene-thumbnail">
                      <img 
                        src={thumbnailUrl} 
                        alt={`${scene.name} preview`}
                        onError={(e) => e.target.style.display = 'none'}
                      />
                    </div>
                  )}
                  
                  <div className="scene-info">
                    <div className="info-item">
                      <span>Channels:</span>
                      <span>{scene.channels?.length || 0}</span>
                    </div>
                    <div className="info-item">
                      <span>Overlays:</span>
                      <span>{scene.overlay?.overlays?.length || 0}</span>
                    </div>
                    {scene.schedule && (
                      <div className="info-item">
                        <span>Schedule:</span>
                        <span>
                          {scene.schedule.start} - {scene.schedule.end}
                        </span>
                      </div>
                    )}
                  </div>

                  {scene.channels && scene.channels.length > 0 && (
                    <div className="scene-channels">
                      <h4>Channels:</h4>
                      <div className="channel-tags">
                        {scene.channels.map((channelAssignment, index) => {
                          // Handle both old format (string) and new format (object)
                          const channelId = typeof channelAssignment === 'string' 
                            ? channelAssignment 
                            : channelAssignment.channel_id;
                          const subChannelId = typeof channelAssignment === 'object' 
                            ? channelAssignment.subchannel_id 
                            : null;
                          
                          const channel = channels.find(c => c.id === channelId);
                          const displayName = channel?.name || channelId;
                          
                          return (
                            <span key={`${channelId}-${subChannelId || 'all'}-${index}`} className="channel-tag">
                              {displayName}
                              {subChannelId && (
                                <span className="subchannel-indicator">
                                  → {subChannelId}
                                </span>
                              )}
                            </span>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>

                <div className="scene-card-footer">
                  <button
                    className="btn btn-primary"
                    onClick={() => handleDisplayScene(scene.id)}
                  >
                    <Monitor size={16} />
                    Display Now
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="empty-state">
          <h3>No scenes created yet</h3>
          <p className="text-tertiary">
            Create your first scene to start displaying content on your Mimir device.
          </p>
          <button className="btn btn-primary" onClick={handleCreateScene}>
            <Plus size={18} />
            Create Your First Scene
          </button>
        </div>
      )}

      {showForm && (
        <SceneForm
          scene={editingScene}
          channels={channels}
          overlays={overlays}
          onClose={handleFormClose}
        />
      )}
    </div>
  );
};

export default Scenes;
