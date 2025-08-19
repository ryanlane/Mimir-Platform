import React, { useState, useEffect } from 'react';
import { Plus, Play, Square, Monitor, Edit, Trash2 } from 'lucide-react';
import { api } from '../../services/api';
import SceneForm from './SceneForm';
import './Scenes.css';

const Scenes = () => {
  const [scenes, setScenes] = useState([]);
  const [channels, setChannels] = useState([]);
  const [overlays, setOverlays] = useState([]);
  const [activeScene, setActiveScene] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingScene, setEditingScene] = useState(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [scenesResponse, channelsResponse, overlaysResponse, displayResponse] = await Promise.all([
        api.getScenes(),
        api.getChannels(),
        api.getOverlays(),
        api.getDisplayStatus()
      ]);

      setScenes(scenesResponse.data.scenes || []);
      setChannels(channelsResponse.data.channels || []);
      setOverlays(overlaysResponse.data.overlays || []);
      setActiveScene(displayResponse.data.currentScene || null);
    } catch (error) {
      console.error('Error loading data:', error);
    } finally {
      setLoading(false);
    }
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

  const handleActivateScene = async (sceneId) => {
    try {
      if (activeScene === sceneId) {
        // If this scene is already active, deactivate it
        await api.deactivateScene(sceneId);
        setActiveScene(null);
      } else {
        // Activate this scene (this will automatically deactivate any other active scene)
        await api.activateScene(sceneId);
        setActiveScene(sceneId);
      }
      // Refresh data to ensure consistency
      await loadData();
    } catch (error) {
      console.error('Error toggling scene activation:', error);
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
        <span>Loading scenes...</span>
      </div>
    );
  }

  return (
    <div className="scenes">
      <div className="scenes-header">
        <div>
          <h1>Scenes</h1>
          <p className="text-tertiary">Manage your display scenes and configurations</p>
        </div>
        <button className="btn btn-primary" onClick={handleCreateScene}>
          <Plus size={18} />
          Create Scene
        </button>
      </div>

      {scenes.length > 0 ? (
        <div className="scenes-grid">
          {scenes.map((scene) => {
            const isActive = activeScene === scene.id;
            return (
              <div key={scene.id} className={`scene-card ${isActive ? 'scene-card-active' : ''}`}>
                <div className="scene-card-header">
                  <div className="scene-title-container">
                    <h3>{scene.name}</h3>
                    {isActive && (
                      <span className="status-indicator status-success">
                        Active
                      </span>
                    )}
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
                        {scene.channels.map((channelId) => {
                          const channel = channels.find(c => c.id === channelId);
                          return (
                            <span key={channelId} className="channel-tag">
                              {channel?.name || channelId}
                            </span>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>

                <div className="scene-card-footer">
                  <button
                    className="btn btn-sm btn-accent"
                    onClick={() => handleDisplayScene(scene.id)}
                  >
                    <Monitor size={16} />
                    Display Now
                  </button>
                  <button
                    className={`btn btn-sm ${isActive ? 'btn-warning' : 'btn-success'}`}
                    onClick={() => handleActivateScene(scene.id)}
                  >
                    {isActive ? (
                      <>
                        <Square size={16} />
                        Deactivate
                      </>
                    ) : (
                      <>
                        <Play size={16} />
                        Activate
                      </>
                    )}
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
