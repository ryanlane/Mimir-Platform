import React, { useState, useEffect, useRef } from 'react';
import { Plus, RefreshCw } from 'lucide-react';
import { api } from '../../services/api';
import { persistentCache } from '../../services/persistentCache';
import { useEnsureFreshState, useSceneEvents } from '../../hooks/useWebSocket';
import DistributionManager from '../../components/DistributionManager/DistributionManager';
import './Scenes.css';
import SceneLiveStatus from './components/SceneLiveStatus';
import Header from '../../components/Header/Header';
import Button from '../../components/Button/Button';
import SceneCard from '../../components/SceneCard/SceneCard';
import Modal from '../../components/Modal/Modal';
import { SkeletonProgramCard } from '../../components/Skeleton/Skeleton';
import { ProgramDetailPanel } from './components/ProgramDetailPanel';
import { ProgramEditorPanel } from './components/ProgramEditorPanel';

const Scenes = () => {
  const [scenes, setScenes] = useState([]);
  const [channels, setChannels] = useState([]);
  // Refs to hold stable latest values to avoid adding to useCallback deps
  const channelsRef = useRef([]);
  const scenesRef = useRef([]);
  const [channelManifests, setChannelManifests] = useState({}); // Cache for channel manifests
  const [displayStatus, setDisplayStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [panelMode, setPanelMode] = useState(null); // null | 'detail' | 'editor'
  const [panelScene, setPanelScene] = useState(null);
  const [showImageModal, setShowImageModal] = useState(false);
  const [currentImageData, setCurrentImageData] = useState(null);
  const [imageLoading, setImageLoading] = useState(false);
  const [showDistributionManager, setShowDistributionManager] = useState(false);
  const [selectedSceneForDistribution, setSelectedSceneForDistribution] = useState(null);
  const [sceneSchedules, setSceneSchedules] = useState({}); // Cache for scene schedules

  // Initialize WebSocket connection with automatic state sync on mount
  const { currentState, requestStateSync } = useEnsureFreshState();

  const loadSceneSchedules = async (scenesList) => {
    // Fetch ALL scheduler jobs for every scene rather than only the first assignment
    try {
      const schedulePromises = scenesList.map(async (scene) => {
        try {
          const response = await api.getSceneSchedules(scene.id);
          const assignments = Array.isArray(response.data) ? response.data : [];

          if (assignments.length === 0) {
            return { sceneId: scene.id, schedules: [] };
          }

            // Fetch each referenced job id (dedupe in case of duplicates)
          const uniqueJobIds = [...new Set(assignments.map(a => a.job_id).filter(Boolean))];
          const jobResults = await Promise.all(uniqueJobIds.map(async (jobId) => {
            try {
              const jobResponse = await api.getSchedulerJob(jobId);
              return jobResponse.data;
            } catch (e) {
              console.warn(`Failed to fetch job ${jobId} for scene ${scene.id}:`, e.message);
              return null;
            }
          }));

          const jobs = jobResults.filter(Boolean);
          // Fallback: if we could not resolve job objects, retain lightweight assignment markers
          if (jobs.length === 0) {
            return { sceneId: scene.id, schedules: assignments.map(a => ({ __assignment: true, job_id: a.job_id, scene_id: a.scene_id, enabled: true })) };
          }
          return { sceneId: scene.id, schedules: jobs };
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
      console.log('[Scenes] Loaded scene schedules map:', schedulesMap);
    } catch (error) {
      console.error('Error loading scene schedules:', error);
    }
  };

  const loadData = async () => {
    // Ensure loading indicator shows anytime we (re)fetch data
    setLoading(true);
    try {
      // Small internal helpers to normalize payloads and aid debugging
      const extractArray = (label, payload) => {
        if (!payload) return [];
        // Direct array
        if (Array.isArray(payload)) return payload;
        // Top-level named arrays
        if (Array.isArray(payload.scenes)) return payload.scenes;
        if (Array.isArray(payload.channels)) return payload.channels;
        if (Array.isArray(payload.items)) return payload.items;
        if (Array.isArray(payload.data)) return payload.data;
        // Nested axios-like shapes { data: { scenes: [...] }}
        if (payload.data) {
          const d = payload.data;
          if (Array.isArray(d)) return d;
          if (Array.isArray(d.scenes)) return d.scenes;
          if (Array.isArray(d.channels)) return d.channels;
          if (Array.isArray(d.items)) return d.items;
        }
        // Development debug once per session on unexpected shape
        if (process.env.NODE_ENV !== 'production') {
          console.debug(`[extractArray] Unrecognized ${label} payload shape`, payload);
        }
        return [];
      };

      // Use persistent cache with SWR; immediate cached data (if any) then background update
      const scenesPromise = persistentCache.getScenes({
        onUpdate: (fresh) => {
          // fresh can be either { scenes: [...] } or an array depending on backend response
          if (fresh) {
            if (Array.isArray(fresh.scenes)) {
              setScenes(fresh.scenes);
            } else if (Array.isArray(fresh)) {
              setScenes(fresh);
            }
          }
        }
      });
      const channelsPromise = persistentCache.getChannels({
        onUpdate: (fresh) => {
          // fresh can be either { channels: [...] } or an array
            if (fresh) {
              if (Array.isArray(fresh.channels)) {
                setChannels(fresh.channels);
              } else if (Array.isArray(fresh)) {
                setChannels(fresh);
              }
            }
        }
      });

    // Await raw (flexibly shaped) results from cache helper. They may be:
    // 1) axios response-like: { data: [...] }
    // 2) plain array: [...]
    // 3) object with key { scenes: [...] } / { channels: [...] }
    // 4) (unexpected) undefined while onUpdate callback will later supply data
    const [scenesResolved, channelsResolved] = await Promise.all([scenesPromise, channelsPromise]);

    const unwrapScenes = (val) => {
      if (!val) return undefined; // distinguish from explicit empty []
      if (Array.isArray(val)) return val;
      if (Array.isArray(val.scenes)) return val.scenes;
      if (val.data) {
        if (Array.isArray(val.data)) return val.data;
        if (Array.isArray(val.data.scenes)) return val.data.scenes;
      }
      return undefined;
    };
    const unwrapChannels = (val) => {
      if (!val) return undefined;
      if (Array.isArray(val)) return val;
      if (Array.isArray(val.channels)) return val.channels;
      if (val.data) {
        if (Array.isArray(val.data)) return val.data;
        if (Array.isArray(val.data.channels)) return val.data.channels;
      }
      return undefined;
    };

    const rawScenes = unwrapScenes(scenesResolved);
    const rawChannels = unwrapChannels(channelsResolved);

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

      // Normalize / defensively extract scenes list. rawScenes may be undefined when the
      // persistentCache has not yet delivered data (onUpdate will later). Avoid clearing existing
      // scenes in that ambiguous case to prevent the intermittent "No scenes created yet" flicker.
      let scenesList = extractArray('scenes', rawScenes);
  // NOTE: we intentionally avoid using scenes.length directly below to prevent unnecessary re-renders.
      const ambiguousScenes = rawScenes === undefined && scenesList.length === 0;
      if (scenesList.length === 0) {
        if (ambiguousScenes) {
          console.debug('[Scenes] Scenes unresolved (ambiguous) – retaining prior state to avoid flicker');
        } else {
          console.warn('[Scenes] No scenes extracted. Raw payload shape (explicit empty or empty array):', rawScenes);
        }
      }
      // Normalize backend field names (camelCase) to the keys other components might already rely on (snake_case or legacy)
      const normalizedScenes = scenesList.map(s => {
        // Channels array may store items with "channel_id" already; ensure uniform shape
        const channelsNorm = Array.isArray(s.channels) ? s.channels.map(ch => {
          if (typeof ch === 'string') return { channel_id: ch };
          return {
            channel_id: ch.channel_id || ch.id || ch.channelId,
            subchannel_id: ch.subchannel_id || ch.subchannelId || ch.subchannel || null,
            position: ch.position || null,
            config: ch.config || null
          };
        }) : [];
        return {
          ...s,
          id: s.id,
            // Provide both naming styles to avoid downstream assumptions
          name: s.name,
          channels: channelsNorm,
          overlay: s.overlay || s.overlays || null,
          overlays: s.overlays || s.overlay || null,
          schedule: s.schedule || s.timingConfig || null,
          timing_config: s.timingConfig || s.schedule || null,
          distribution_mode: s.distribution_mode || s.distributionMode || 'SEQUENTIAL',
          distributionMode: s.distributionMode || s.distribution_mode || 'SEQUENTIAL',
          is_active: s.is_active ?? s.isActive ?? false,
          isActive: s.isActive ?? s.is_active ?? false,
          update_strategy: s.update_strategy || s.updateStrategy || s.update_strategy || 'scheduler',
          updateStrategy: s.updateStrategy || s.update_strategy || 'scheduler',
          push_fallback_poll_seconds: s.push_fallback_poll_seconds || s.pushFallbackPollSeconds || null,
          pushFallbackPollSeconds: s.pushFallbackPollSeconds || s.push_fallback_poll_seconds || null,
        };
      });
      if (normalizedScenes.length && process.env.NODE_ENV !== 'production') {
        console.debug('[Scenes] Normalized scenes sample:', normalizedScenes[0]);
      }
      if (!ambiguousScenes) {
        // Only overwrite state if we have concrete data (even if empty) to avoid transient empty UI.
        if (normalizedScenes.length > 0 || Array.isArray(rawScenes)) {
          setScenes(normalizedScenes);
          scenesRef.current = normalizedScenes;
        } else {
          console.debug('[Scenes] Skipping setScenes due to ambiguous empty payload.');
        }
      }

      // Normalize / defensively extract channels list
      let channelList = extractArray('channels', rawChannels);
      const ambiguousChannels = rawChannels === undefined && channelList.length === 0;
      if (channelList.length === 0) {
        if (ambiguousChannels) {
          console.debug('[Scenes] Channels unresolved (ambiguous) – retaining prior state.');
          channelList = channels; // keep existing
        } else {
          console.warn('[Scenes] No channels extracted. Raw payload shape (explicit empty or empty array):', rawChannels);
        }
      }
      if (!ambiguousChannels) {
        setChannels(channelList);
        channelsRef.current = channelList;
      }
      
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
      // If data was ambiguous (cache not yet resolved) and we previously had scenes, keep spinner a hair longer
      // to allow onUpdate to populate, mitigating UI flash of empty state.
      const shouldDelay = scenesRef.current.length > 0 && document.visibilityState === 'visible';
      if (shouldDelay) {
        setTimeout(() => setLoading(false), 120);
      } else {
        setLoading(false);
      }
    }
  };

  // Keep refs in sync (outside callback to avoid expanding deps)
  useEffect(() => { scenesRef.current = scenes; }, [scenes]);
  useEffect(() => { channelsRef.current = channels; }, [channels]);

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
    loadData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentState]);

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
    setPanelScene(null);
    setPanelMode('editor');
  };

  const handleEditScene = (scene) => {
    setPanelScene(scene);
    setPanelMode('editor');
  };

  const handleCardClick = (scene, e) => {
    if (e.target.closest('button, a, input')) return;
    if (panelMode === 'detail' && panelScene?.id === scene.id) {
      setPanelMode(null);
      setPanelScene(null);
    } else {
      setPanelScene(scene);
      setPanelMode('detail');
    }
  };

  const handleEditorClose = () => {
    setPanelMode(panelScene ? 'detail' : null);
    loadData();
  };

  const handleEditorSaved = () => {
    setPanelMode(null);
    setPanelScene(null);
    loadData();
  };

  const handleDeleteScene = async (sceneId) => {
    if (window.confirm('Are you sure you want to delete this program?')) {
      try {
        await api.deleteScene(sceneId);
        if (panelScene?.id === sceneId) {
          setPanelMode(null);
          setPanelScene(null);
        }
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
    const schedules = sceneSchedules[sceneId];
    if (!Array.isArray(schedules) || schedules.length === 0) {
      return { hasSchedule: false, status: 'No schedule', count: 0 };
    }

    // Determine enabled schedules & earliest next run (treat missing flags as enabled)
    const isEnabled = (s) => {
      if (s?.enabled === undefined && s?.active === undefined && s?.status === undefined) return true; // assignment stub
      return s?.enabled === true || s?.active === true || s?.status === 'enabled';
    };
    const enabledSchedules = schedules.filter(isEnabled);
    const primary = enabledSchedules[0] || schedules[0];
    const enabled = isEnabled(primary);

    // Earliest next run among enabled, else among all
    const parseDate = (val) => (val ? new Date(val) : null);
    const allForNext = (enabledSchedules.length > 0 ? enabledSchedules : schedules)
      .map(s => ({ raw: s, dt: parseDate(s.next_run_at || s.nextRunAt || s.next_run) }))
      .filter(x => x.dt instanceof Date && !isNaN(x.dt.getTime()))
      .sort((a, b) => a.dt - b.dt);
    const earliest = allForNext[0]?.raw;

    let statusText;
    if (primary.freq_value && primary.freq_unit) {
      statusText = `Every ${primary.freq_value} ${primary.freq_unit}${primary.freq_value > 1 ? 's' : ''}`;
    } else if (primary.description) {
      statusText = primary.description;
    } else if (primary.name) {
      statusText = primary.name;
    } else {
      statusText = 'Scheduled';
    }

    return {
      hasSchedule: true,
      status: statusText,
      count: schedules.length,
      enabled,
      enabledCount: enabledSchedules.length,
      nextRun: (earliest?.next_run_at || earliest?.nextRunAt || earliest?.next_run) || null
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

  // Sync panelScene reference when scenes refresh (e.g. after WS event)
  useEffect(() => {
    if (panelScene) {
      const fresh = scenes.find(s => s.id === panelScene.id);
      if (fresh) setPanelScene(fresh);
    }
  }, [scenes]); // eslint-disable-line react-hooks/exhaustive-deps


  const activePanel = panelMode === 'editor'
    ? (
      <ProgramEditorPanel
        scene={panelScene}
        channels={channels}
        onClose={handleEditorClose}
        onSaved={handleEditorSaved}
      />
    )
    : panelMode === 'detail' && panelScene
    ? (
      <ProgramDetailPanel
        scene={panelScene}
        channels={channels}
        channelManifests={channelManifests}
        isLive={panelScene.id === (displayStatus?.currentScene || displayStatus?.current_scene)}
        scheduleStatus={getSceneScheduleStatus(panelScene.id)}
        onClose={() => { setPanelMode(null); setPanelScene(null); }}
        onEdit={handleEditScene}
        onDelete={handleDeleteScene}
      />
    )
    : null;

  return (
    <div className="scenes">
      <div className="scenes-header">
        <Header
          title="Programs"
          icon="layers"
          iconSize={36}
          description="Build and manage display programs from your sources"
          actions={[
            <Button
              key="sync"
              variant="secondary"
              icon={<RefreshCw size={18} aria-hidden="true" />}
              onClick={() => {
                requestStateSync();
              }}
            >
              Sync State
            </Button>,
            <Button
              key="create"
              variant="primary"
              icon={<Plus size={18} aria-hidden="true" />}
              onClick={handleCreateScene}
            >
              New Program
            </Button>
          ]}
        />
      </div>
      <div style={{ marginTop: '12px', marginBottom: '16px' }}>
        <SceneLiveStatus
          initialSceneId={displayStatus?.currentScene || displayStatus?.current_scene}
          initialSceneName={displayStatus?.currentSceneName || displayStatus?.current_scene_name}
        />
      </div>

      <div className="programs-split-layout">
        <div className="programs-list-pane">
          {loading ? (
            <div className="scenes-grid">
              {[1, 2, 3].map(i => <SkeletonProgramCard key={i} />)}
            </div>
          ) : scenes.length > 0 ? (
            <div className="scenes-grid">
              {scenes.map(scene => {
                const isSelected = panelScene?.id === scene.id && panelMode !== null;
                return (
                  <div
                    key={scene.id}
                    className={`program-card-wrapper${isSelected ? ' program-card-wrapper--selected' : ''}`}
                    onClick={(e) => handleCardClick(scene, e)}
                  >
                    <SceneCard
                      scene={scene}
                      channels={channels}
                      channelManifests={channelManifests}
                      scheduleStatus={getSceneScheduleStatus(scene.id)}
                      onChangeDistribution={handleDistributionModeChange}
                      onDisplay={handleDisplayScene}
                      onEdit={handleEditScene}
                      onDelete={handleDeleteScene}
                      loadingDisplay={imageLoading}
                    />
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="empty-state">
              <h3>No programs yet</h3>
              <p className="text-tertiary">
                Programs define what plays on your screens. Create your first one to get started.
              </p>
              <Button
                variant="primary"
                icon={<Plus size={18} aria-hidden="true" />}
                onClick={handleCreateScene}
              >
                New Program
              </Button>
            </div>
          )}
        </div>

        {activePanel}
      </div>

      {showImageModal && currentImageData && (
        <Modal
          isOpen={showImageModal}
          onClose={() => setShowImageModal(false)}
          title={`Scene Preview: ${currentImageData.scene_name}`}
          size="large"
        >
          <div className="image-modal">
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
        </Modal>
      )}

      {showDistributionManager && selectedSceneForDistribution && (
        <Modal
          isOpen={showDistributionManager}
          onClose={handleCloseDistributionManager}
          title={`Distribution: ${selectedSceneForDistribution?.name || ''}`}
          size="large"
        >
          <DistributionManager
            sceneId={selectedSceneForDistribution.id}
            sceneName={selectedSceneForDistribution.name}
            onClose={handleCloseDistributionManager}
          />
        </Modal>
      )}
    </div>
  );
};

export default Scenes;
