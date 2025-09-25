import React, { useState, useEffect, useCallback } from 'react';
import { Plus, Monitor, Edit, Trash2, RefreshCw } from 'lucide-react';
import { api } from '../../services/api';
import { persistentCache } from '../../services/persistentCache';
import { useEnsureFreshState, useSceneEvents } from '../../hooks/useWebSocket';
import SceneForm from './SceneForm';
import DistributionManager from '../../components/DistributionManager/DistributionManager';
import './Scenes.css';
import SceneLiveStatus from './components/SceneLiveStatus';

const Scenes = () => {
  const [scenes, setScenes] = useState([]);
  const [channels, setChannels] = useState([]);
  const [channelManifests, setChannelManifests] = useState({}); // Cache for channel manifests
  const [displayStatus, setDisplayStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingScene, setEditingScene] = useState(null);
  const [showImageModal, setShowImageModal] = useState(false);
  const [currentImageData, setCurrentImageData] = useState(null);
  const [imageLoading, setImageLoading] = useState(false);
  const [showDistributionManager, setShowDistributionManager] = useState(false);
  const [selectedSceneForDistribution, setSelectedSceneForDistribution] = useState(null);
  const [sceneSchedules, setSceneSchedules] = useState({}); // Cache for scene schedules

  // Initialize WebSocket connection with automatic state sync on mount
  const { isConnected, currentState, requestStateSync } = useEnsureFreshState();

  const loadSceneSchedules = useCallback(async (scenesList) => {
    try {
      const schedulePromises = scenesList.map(async (scene) => {
        try {
          const response = await api.getSceneSchedules(scene.id);
          const assignments = response.data || [];
          
          // If there are assignments, get the job details for the first one
          if (assignments.length > 0) {
            const jobResponse = await api.getSchedulerJob(assignments[0].job_id);
            return { sceneId: scene.id, schedules: [jobResponse.data] };
          } else {
            return { sceneId: scene.id, schedules: [] };
          }
        } catch (error) {
          console.log(`Could not load schedules for scene ${scene.id}:`, error.message);
          return { sceneId: scene.id, schedules: [] };
        }
      });
      
      const scheduleResults = await Promise.all(schedulePromises);
      const schedulesMap = scheduleResults.reduce((acc, result) => {
        acc[result.sceneId] = result.schedules;
        return acc;
      }, {});
      
      setSceneSchedules(schedulesMap);
    } catch (error) {
      console.error('Error loading scene schedules:', error);
    }
  }, []);

  const loadData = useCallback(async () => {
    try {
      // Use persistent cache with SWR; immediate cached data (if any) then background update
      const scenesPromise = persistentCache.getScenes({
        onUpdate: (fresh) => {
          if (Array.isArray(fresh.scenes)) {
            setScenes(fresh.scenes);
          }
        }
      });
      const channelsPromise = persistentCache.getChannels({
        onUpdate: (fresh) => {
          if (Array.isArray(fresh.channels)) {
            setChannels(fresh.channels);
          }
        }
      });

      const [{ data: scenesData }, { data: channelsData }] = await Promise.all([scenesPromise, channelsPromise]);

      const scenesResponse = { data: scenesData };
      const channelsResponse = { data: channelsData };

      // Handle display status separately to gracefully handle "no displays" case
      let displayResponse = null;
      try {
        displayResponse = await api.getDisplayStatus();
        console.log('Display response:', displayResponse.data);
      } catch (displayError) {
        // If 404 or "Display client not found", that's expected when no displays are connected
        if (displayError.response?.status === 404 || displayError.message?.includes('Display client not found')) {
          console.log('No displays currently connected');
          displayResponse = { data: null }; // Set to null to indicate no displays
        } else {
          // Re-throw other errors
          throw displayError;
        }
      }

      console.log('Current scene from API:', displayResponse?.data?.currentScene);

      const scenesList = scenesResponse.data.scenes || [];
      setScenes(scenesList);
      const channelList = channelsResponse.data.channels || [];
      setChannels(channelList);
      
      // Load channel manifests for better subchannel display
      const manifestPromises = channelList.map(async (channel) => {
        try {
          const manifestResponse = await api.getChannelManifest(channel.id);
          return { channelId: channel.id, manifest: manifestResponse.data };
        } catch (error) {
          console.log(`Could not load manifest for ${channel.id}:`, error.response?.data?.detail || error.message);
          return { channelId: channel.id, manifest: null };
        }
      });
      
      const manifestResults = await Promise.all(manifestPromises);
      const manifestsMap = manifestResults.reduce((acc, result) => {
        acc[result.channelId] = result.manifest;
        return acc;
      }, {});
      
      setChannelManifests(manifestsMap);
      
      // Load schedules for all scenes
      await loadSceneSchedules(scenesList);
      
      // Only set display status if we don't have WebSocket state
      if (!currentState?.displayStatus) {
        setDisplayStatus(displayResponse?.data || null);
        console.log('Set displayStatus from API to:', displayResponse?.data || null);
      } else {
        console.log('🚫 Skipping display status update - using WebSocket state');
      }
    } catch (error) {
      console.error('Error loading data:', error);
    } finally {
      setLoading(false);
    }
  }, [currentState, loadSceneSchedules]);

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

  useEffect(() => {
    // Load data immediately when component mounts
    // Don't wait for WebSocket - it will update state when available
    loadData();
  }, [loadData]);

  // Handle WebSocket state updates when they arrive
  useEffect(() => {
    if (currentState?.displayStatus) {
      console.log('🚀 Updating from WebSocket state:', currentState.displayStatus);
      setDisplayStatus(currentState.displayStatus);
      
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
    }
  }, [currentState]);

  // Debug useEffect to monitor activeScene changes
  useEffect(() => {
    console.log('🎯 Active scene changed to:', displayStatus?.currentScene);
    console.log('🎯 Full displayStatus:', displayStatus);
  }, [displayStatus]);

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

  const handleDistributionModeChange = async (sceneId, newMode) => {
    try {
      await api.updateSceneDistributionMode(sceneId, newMode);
      // Update local state immediately - handle both field naming conventions
      setScenes(prevScenes => 
        prevScenes.map(scene => 
          scene.id === sceneId 
            ? { ...scene, distribution_mode: newMode, distributionMode: newMode }
            : scene
        )
      );
    } catch (error) {
      console.error('Error updating distribution mode:', error);
    }
  };

  // const handleManageDistribution = (scene) => {
  //   setSelectedSceneForDistribution(scene);
  //   setShowDistributionManager(true);
  // };

  const handleCloseDistributionManager = () => {
    setShowDistributionManager(false);
    setSelectedSceneForDistribution(null);
  };

  const getSceneScheduleStatus = (sceneId) => {
    const schedules = sceneSchedules[sceneId] || [];
    const activeSchedules = schedules.filter(s => s.enabled);
    
    if (activeSchedules.length === 0) {
      return { hasSchedule: false, status: 'No schedule', count: 0 };
    }
    
    const schedule = activeSchedules[0]; // Get first active schedule
    return {
      hasSchedule: true,
      status: `Every ${schedule.freq_value} ${schedule.freq_unit}${schedule.freq_value > 1 ? 's' : ''}`,
      count: activeSchedules.length,
      enabled: schedule.enabled,
      nextRun: schedule.next_run_at
    };
  };

  const handleDisplayScene = async (sceneId) => {
    try {
      setImageLoading(true);
      
      // First, get displays to find one with this scene assigned
      const displaysResponse = await api.getDisplays();
      const displays = Array.isArray(displaysResponse.data) ? displaysResponse.data : [];
      
      // Find a display that has this scene assigned
      const displayWithScene = displays.find(display => 
        display.assigned_scene_id === sceneId
      );
      
      if (!displayWithScene) {
        // If no display has this scene, let's try to get the first channel's image directly
        const scene = scenes.find(s => s.id === sceneId);
        if (scene?.channels && scene.channels.length > 0) {
          const firstChannel = scene.channels[0];
          const channelId = typeof firstChannel === 'string' ? firstChannel : firstChannel.channel_id;
          
          // Try to get channel image
          const baseUrl = window.location.protocol + '//' + window.location.hostname + ':5000';
          const imageUrl = `${baseUrl}/api/channels/${channelId}/current/800x480/current.jpg`;
          setCurrentImageData({
            scene_name: scene.name,
            scene_id: sceneId,
            image_url: imageUrl,
            channels: [channelId],
            source: 'channel'
          });
          setShowImageModal(true);
        } else {
          alert('No displays are assigned to this scene and no channels found to preview.');
        }
        return;
      }
      
      // Get the current image for this display
      const imageResponse = await api.getDisplayImage(displayWithScene.id);
      setCurrentImageData(imageResponse.data);
      setShowImageModal(true);
      
    } catch (error) {
      console.error('Error getting scene image:', error);
      alert('Could not load scene image. Scene may not be assigned to any display.');
    } finally {
      setImageLoading(false);
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
        <span>Loading scenes...</span>
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
      <div style={{ marginTop: '12px', marginBottom: '16px' }}>
        <SceneLiveStatus
          initialSceneId={displayStatus?.currentScene || displayStatus?.current_scene}
          initialSceneName={displayStatus?.currentSceneName || displayStatus?.current_scene_name}
        />
      </div>

      {scenes.length > 0 ? (
        <div className="scenes-grid">
          {scenes.map((scene) => {
            return (
              <div key={scene.id} className="scene-card">
                <div className="scene-card-header">
                  <h3>{scene.name} {' '}
                    {(() => {
                      // Determine strategy badge (prefer new field names)
                      const strategy = scene.update_strategy || scene.updateStrategy || 'scheduler';
                      const isPush = strategy === 'push';
                      const badgeClass = isPush ? 'strategy-badge push' : 'strategy-badge scheduler';
                      // If push but fallback poll not present, still fine. If scheduler but scene has push_fallback_poll_seconds it implies downgrade.
                      const downgraded = !isPush && (scene.push_fallback_poll_seconds || scene.pushFallbackPollSeconds);
                      return (
                        <span className={badgeClass} title={downgraded ? 'Originally configured for push but downgraded due to channel capability change' : (isPush ? 'Push update strategy (websocket events trigger refresh)' : 'Scheduler update strategy (periodic refresh)')}>
                          {isPush ? 'Push' : 'Scheduled'}
                          {downgraded && <span className="downgrade-indicator" aria-label="Downgraded to scheduler">⚠</span>}
                        </span>
                      );
                    })()}
                  </h3>
                </div>

                <div className="scene-card-body">                  
                  
                  {scene.channels && scene.channels.length > 0 && (
                    <div className="scene-channels">
                      <span className="channels-label">Channels:</span>
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
                          
                          // Get subchannel display name from manifest
                          let subChannelDisplayName = subChannelId;
                          if (subChannelId && channelManifests[channelId]) {
                            const manifest = channelManifests[channelId];
                            // Check for galleries (photo frame channel)
                            if (manifest.galleries) {
                              const gallery = manifest.galleries.find(g => g.id === subChannelId);
                              if (gallery) {
                                subChannelDisplayName = `${gallery.name} (${gallery.image_count || 0} images)`;
                              }
                            }
                            // Future: Add support for other subchannel types
                            // else if (manifest.subchannels) {
                            //   const subchannel = manifest.subchannels.find(s => s.id === subChannelId);
                            //   if (subchannel) {
                            //     subChannelDisplayName = subchannel.name;
                            //   }
                            // }
                          }
                          
                          return (
                            <span key={`${channelId}-${subChannelId || 'all'}-${index}`} className="channel-tag">
                              {displayName}
                              {subChannelId && (
                                <span className="subchannel-indicator">
                                  → {subChannelDisplayName}
                                </span>
                              )}
                            </span>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  <div className="scene-distribution-mode">
                    <span className="distribution-label">Distribution:</span>
                    <select
                      value={scene.distributionMode || scene.distribution_mode || 'MIRROR'}
                      onChange={(e) => handleDistributionModeChange(scene.id, e.target.value)}
                      className="distribution-mode-select"
                    >
                      <option value="MIRROR">Mirror</option>
                      <option value="SEQUENTIAL">Sequential</option>
                      <option value="RANDOM_UNIQUE">Random Unique</option>
                    </select>
                  </div>
                  
                  <div className="scene-schedule">
                    <span className="schedule-label">Schedule:</span>
                    {(() => {
                      const scheduleStatus = getSceneScheduleStatus(scene.id);
                      return (
                        <div className="schedule-info">
                          <span className={`schedule-status ${scheduleStatus.hasSchedule ? 'active' : 'inactive'}`}>
                            {scheduleStatus.hasSchedule ? (
                              <>
                                {scheduleStatus.status}
                                {scheduleStatus.count > 1 && (
                                  <span className="schedule-count"> (+{scheduleStatus.count - 1} more)</span>
                                )}
                              </>
                            ) : (
                              'No schedule'
                            )}
                          </span>
                        </div>
                      );
                    })()}
                  </div>
                </div>

                <div className="scene-card-footer">
                  <button
                    className="btn btn-sm btn-accent"
                    onClick={() => handleDisplayScene(scene.id)}
                    disabled={imageLoading}
                  >
                    <Monitor size={16} />
                    {imageLoading ? 'Loading...' : 'Display'}
                  </button>
                  {/* <button
                    className="btn btn-sm btn-info"
                    onClick={() => handleManageDistribution(scene)}
                    title="Manage Distribution"
                  >
                    <Settings size={16} />
                    Distribution
                  </button> */}
                  <button
                    className="btn btn-sm btn-secondary"
                    onClick={() => handleEditScene(scene)}
                  >
                    <Edit size={16} />
                    Edit
                  </button>
                  <button
                    className="btn btn-sm btn-error"
                    onClick={() => handleDeleteScene(scene.id)}
                  >
                    <Trash2 size={16} />
                    Delete
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
          onClose={handleFormClose}
        />
      )}

      {showImageModal && currentImageData && (
        <div className="modal-overlay" onClick={() => setShowImageModal(false)}>
          <div className="image-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Scene Preview: {currentImageData.scene_name}</h3>
              <button 
                className="btn btn-sm btn-secondary"
                onClick={() => setShowImageModal(false)}
              >
                ×
              </button>
            </div>
            <div className="modal-body">
              <div className="scene-image-container">
                <img 
                  src={currentImageData.image_url} 
                  alt={`Preview of ${currentImageData.scene_name}`}
                  className="scene-preview-image"
                  onError={(e) => {
                    e.target.style.display = 'none';
                    e.target.nextSibling.style.display = 'block';
                  }}
                />
                <div className="image-error" style={{ display: 'none' }}>
                  <p>Image preview not available</p>
                  <p className="text-tertiary">The scene may not have generated content yet.</p>
                </div>
              </div>
              <div className="scene-details">
                <p><strong>Scene ID:</strong> {currentImageData.scene_id}</p>
                {currentImageData.channels && (
                  <p><strong>Channels:</strong> {currentImageData.channels.join(', ')}</p>
                )}
                {currentImageData.resolution && (
                  <p><strong>Resolution:</strong> {currentImageData.resolution.join(' × ')}</p>
                )}
                {currentImageData.generated_at && (
                  <p><strong>Generated:</strong> {new Date(currentImageData.generated_at).toLocaleString()}</p>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {showDistributionManager && selectedSceneForDistribution && (
        <div className="modal-overlay" onClick={handleCloseDistributionManager}>
          <div onClick={(e) => e.stopPropagation()}>
            <DistributionManager
              sceneId={selectedSceneForDistribution.id}
              sceneName={selectedSceneForDistribution.name}
              onClose={handleCloseDistributionManager}
            />
          </div>
        </div>
      )}
    </div>
  );
};

export default Scenes;
