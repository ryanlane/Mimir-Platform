// Scene Assignment component for assigning scenes to displays
import React, { useState, useEffect } from 'react';
import { Monitor, Play, CheckCircle } from 'lucide-react';
import Modal from '../../components/Modal/Modal';
import { api } from '../../services/api';
import './Displays.css';
import './SceneAssignment.css';

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
        // Find the selected scene to extract subchannel info
        const selectedSceneObj = scenes.find(s => s.id === sceneId);
        let subchannelId = null;
        
        // Extract subchannel_id from the scene's channels if available
        if (selectedSceneObj && selectedSceneObj.channels && selectedSceneObj.channels.length > 0) {
          // Look for subchannel_id in the channel assignments
          const channelWithSubchannel = selectedSceneObj.channels.find(ch => 
            ch.subchannel_id || (typeof ch === 'object' && ch.subchannel_id)
          );
          if (channelWithSubchannel) {
            subchannelId = channelWithSubchannel.subchannel_id;
          }
        }

        // Use appropriate assignment endpoint based on display type
        if (display.displayType === 'discovered') {
          await api.assignSceneToDisplay(display.id, sceneId, subchannelId);
          console.log(`✅ Scene assigned to discovered display: ${sceneId} -> ${display.name}${subchannelId ? ` (subchannel: ${subchannelId})` : ''}`);
        } else {
          await api.assignSceneToDisplay(display.id, sceneId, subchannelId);
          console.log(`✅ Scene assigned to registered display: ${sceneId} -> ${display.name}${subchannelId ? ` (subchannel: ${subchannelId})` : ''}`);
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
    <Modal
      isOpen={true}
      onClose={onClose}
      title={`Assign Scene to ${display.name}`}
      size="large"
    >
      <div className="scene-assignment-modal">
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
                    <div className="scene-main">
                      <span className="scene-name">No Scene (Unassign)</span>
                      <span className="scene-meta">Remove assignment</span>
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
                        <div className="scene-main">
                          <Play size={18} />
                          <span className="scene-name">{scene.name}</span>
                          {compatibility.compatible && (
                            <CheckCircle size={16} className="compatible-icon" />
                          )}
                          {!compatibility.compatible && (
                            <span className="compatibility-badge" title={compatibility.reason}>⚠ {compatibility.reason}</span>
                          )}
                          <span className="scene-meta">
                            {(scene.channels?.length || 0)} channel{(scene.channels?.length || 0) === 1 ? '' : 's'}
                            {scene.overlay && scene.overlay.overlays?.length > 0 && ` • ${scene.overlay.overlays.length} overlay${scene.overlay.overlays.length === 1 ? '' : 's'}`}
                          </span>
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

              <div className="modal-footer" style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end', marginTop: '1rem' }}>
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
    </Modal>
  );
};

export default SceneAssignment;
