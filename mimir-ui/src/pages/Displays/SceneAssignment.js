// Scene Assignment component for assigning scenes to displays
import React, { useState, useEffect } from 'react';
import { Monitor, Play, X, Image, CheckCircle } from 'lucide-react';
import { api } from '../../services/api';
import './Displays.css';

const SceneAssignment = ({ display, onClose, onSuccess }) => {
  const [scenes, setScenes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [assigning, setAssigning] = useState(false);
  const [selectedScene, setSelectedScene] = useState(display.assigned_scene_id || '');
  const [error, setError] = useState('');

  useEffect(() => {
    const loadScenes = async () => {
      try {
        const response = await api.getScenes();
        setScenes(response.data.scenes || []);
      } catch (error) {
        console.error('Error loading scenes:', error);
        setError('Failed to load scenes');
      } finally {
        setLoading(false);
      }
    };

    loadScenes();
  }, []);

  const handleAssignScene = async (sceneId) => {
    setAssigning(true);
    setError('');

    try {
      if (sceneId) {
        // Use appropriate assignment endpoint based on display type
        if (display.displayType === 'discovered') {
          await api.assignSceneToDisplay(display.id, sceneId);
          console.log(`✅ Scene assigned to discovered display: ${sceneId} -> ${display.name}`);
        } else {
          await api.assignSceneToDisplay(display.id, sceneId);
          console.log(`✅ Scene assigned to registered display: ${sceneId} -> ${display.name}`);
        }
      } else {
        // Unassign scene
        if (display.displayType === 'discovered') {
          await api.unassignSceneFromDisplay(display.id);
          console.log(`✅ Scene unassigned from discovered display: ${display.name}`);
        } else {
          await api.unassignSceneFromDisplay(display.id);
          console.log(`✅ Scene unassigned from registered display: ${display.name}`);
        }
      }
      onSuccess(display.id, sceneId);
    } catch (error) {
      console.error('Error assigning scene:', error);
      setError(error.response?.data?.detail || error.message || 'Failed to assign scene');
    } finally {
      setAssigning(false);
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    handleAssignScene(selectedScene);
  };

  const isSceneCompatible = (scene) => {
    // Basic compatibility check - could be enhanced with more logic
    if (!scene.channels || scene.channels.length === 0) {
      return { compatible: false, reason: 'No channels configured' };
    }
    
    // Check if scene has any issues
    // Now scene.channels is an array of objects with channel_id, not strings
    if (scene.channels.some(channelAssignment => {
      const channelId = channelAssignment.channel_id || channelAssignment;
      return typeof channelId === 'string' && channelId.includes('unavailable');
    })) {
      return { compatible: false, reason: 'Contains unavailable channels' };
    }

    return { compatible: true, reason: null };
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content scene-assignment-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>
            <Play size={24} />
            Assign Scene to {display.name}
          </h2>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>

        <div className="modal-body">
          {error && (
            <div className="error-message">
              {error}
            </div>
          )}

          <div className="display-info">
            <div className="display-summary">
              <Monitor size={20} />
              <div>
                <div className="display-title-row">
                  <strong>{display.name}</strong>
                  {display.displayType === 'discovered' && (
                    <span className="display-type-badge discovered">Discovered</span>
                  )}
                  {display.displayType === 'registered' && (
                    <span className="display-type-badge registered">Registered</span>
                  )}
                </div>
                <div className="display-specs">
                  {display.resolution[0]}×{display.resolution[1]} • {display.orientation}
                  {display.location && ` • ${display.location}`}
                </div>
              </div>
            </div>

            {display.assigned_scene_name && (
              <div className="current-assignment">
                <span>Currently assigned: <strong>{display.assigned_scene_name}</strong></span>
              </div>
            )}
          </div>

          {loading ? (
            <div className="loading-state">
              <div className="spinner" />
              <p>Loading scenes...</p>
            </div>
          ) : (
            <form onSubmit={handleSubmit}>
              <div className="scene-selection">
                <h3>Select Scene</h3>
                
                {/* Unassign option */}
                <div className="scene-option">
                  <label className="scene-card unassign-option">
                    <input
                      type="radio"
                      name="scene"
                      value=""
                      checked={selectedScene === ''}
                      onChange={(e) => setSelectedScene(e.target.value)}
                    />
                    <div className="scene-info">
                      <div className="scene-header">
                        <X size={20} />
                        <span className="scene-name">No Scene (Unassign)</span>
                      </div>
                      <p className="scene-description">Remove any assigned scene from this display</p>
                    </div>
                  </label>
                </div>

                {/* Available scenes */}
                {scenes.map(scene => {
                  const compatibility = isSceneCompatible(scene);
                  return (
                    <div key={scene.id} className="scene-option">
                      <label className={`scene-card ${!compatibility.compatible ? 'incompatible' : ''}`}>
                        <input
                          type="radio"
                          name="scene"
                          value={scene.id}
                          checked={selectedScene === scene.id}
                          onChange={(e) => setSelectedScene(e.target.value)}
                          disabled={!compatibility.compatible}
                        />
                        <div className="scene-info">
                          <div className="scene-header">
                            <Play size={20} />
                            <span className="scene-name">{scene.name}</span>
                            {compatibility.compatible && (
                              <CheckCircle size={16} className="compatible-icon" />
                            )}
                          </div>
                          
                          {scene.description && (
                            <p className="scene-description">{scene.description}</p>
                          )}
                          
                          <div className="scene-details">
                            <div className="scene-channels">
                              <strong>Channels:</strong> {
                                scene.channels?.map(ch => ch.channel_id || ch).join(', ') || 'None'
                              }
                            </div>
                            
                            {scene.overlay && scene.overlay.overlays?.length > 0 && (
                              <div className="scene-overlays">
                                <strong>Overlays:</strong> {scene.overlay.overlays.join(', ')}
                              </div>
                            )}
                          </div>

                          {!compatibility.compatible && (
                            <div className="compatibility-warning">
                              ⚠️ {compatibility.reason}
                            </div>
                          )}
                        </div>

                        <div className="scene-preview">
                          <div className="preview-placeholder">
                            <Image size={24} />
                            <span>Preview</span>
                          </div>
                          {/* In a real implementation, this would show actual preview */}
                        </div>
                      </label>
                    </div>
                  );
                })}

                {scenes.length === 0 && (
                  <div className="empty-state">
                    <p>No scenes available. Create a scene first to assign it to displays.</p>
                  </div>
                )}
              </div>

              <div className="assignment-preview">
                {selectedScene && (
                  <div className="preview-info">
                    <h4>Assignment Preview</h4>
                    <p>
                      Scene "<strong>{scenes.find(s => s.id === selectedScene)?.name}</strong>" 
                      will be assigned to "<strong>{display.name}</strong>"
                    </p>
                    <div className="preview-details">
                      <span>Resolution: {display.resolution[0]}×{display.resolution[1]}</span>
                      <span>Orientation: {display.orientation}</span>
                    </div>
                  </div>
                )}
              </div>

              <div className="modal-footer">
                <button 
                  type="button" 
                  className="btn btn-secondary" 
                  onClick={onClose}
                  disabled={assigning}
                >
                  Cancel
                </button>
                <button 
                  type="submit" 
                  className="btn btn-primary" 
                  disabled={assigning || loading}
                >
                  {assigning ? 'Assigning...' : selectedScene ? 'Assign Scene' : 'Unassign Scene'}
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
};

export default SceneAssignment;
