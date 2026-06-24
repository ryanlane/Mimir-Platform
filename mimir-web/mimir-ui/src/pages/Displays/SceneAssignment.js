// Scene Assignment component for assigning scenes to displays
import React, { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import { Monitor, Play, CheckCircle, X, ChevronDown } from 'lucide-react';
import Modal from '../../components/Modal/Modal';
import { formatOrientationLabel } from './orientationOptions';
import { api } from '../../services/api';
import './Displays.css';
import './SceneAssignment.css';

const SceneAssignment = ({ display, onClose, onSuccess }) => {
  const [scenes, setScenes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [assigning, setAssigning] = useState(false);
  const [selectedScene, setSelectedScene] = useState(display.assigned_scene_id || '');
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1); // keyboard navigation
  const inputRef = useRef(null);
  const listRef = useRef(null);
  const [error, setError] = useState('');
  const [contentVariants, setContentVariants] = useState([]);
  const [selectedVariant, setSelectedVariant] = useState(display.content_variant || display.contentVariant || '');
  const publicHostHint = (() => {
    const host = window.location.hostname;
    if (!host || host === 'localhost' || host === '127.0.0.1') return null;
    return host;
  })();

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

  // Fetch content variants whenever the selected scene changes
  useEffect(() => {
    if (!selectedScene) {
      setContentVariants([]);
      setSelectedVariant('');
      return;
    }
    const scene = scenes.find(s => s.id === selectedScene);
    if (!scene || !scene.channels || scene.channels.length === 0) {
      setContentVariants([]);
      setSelectedVariant('');
      return;
    }
    let cancelled = false;
    const fetchVariants = async () => {
      try {
        const variantMap = [];
        for (const ch of scene.channels) {
          const channelId = ch.channel_id || ch;
          if (typeof channelId !== 'string') continue;
          try {
            const resp = await api.getChannelManifest(channelId);
            const variants = resp?.data?.capabilities?.content_variants;
            if (Array.isArray(variants) && variants.length > 0) {
              for (const v of variants) {
                if (!variantMap.find(x => x.id === v.id)) variantMap.push(v);
              }
            }
          } catch (_) { /* channel manifest unavailable — skip */ }
        }
        if (!cancelled) {
          setContentVariants(variantMap);
          if (variantMap.length > 0 && !variantMap.find(v => v.id === selectedVariant)) {
            setSelectedVariant(variantMap[0].id);
          }
        }
      } catch (_) { /* ignore */ }
    };
    fetchVariants();
    return () => { cancelled = true; };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedScene, scenes]);

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

        const variantToSend = contentVariants.length > 0 ? (selectedVariant || contentVariants[0].id) : null;
        await api.assignSceneToDisplay(display.id, sceneId, subchannelId, publicHostHint, variantToSend);
        console.log(`✅ Scene assigned: ${sceneId} -> ${display.name}${subchannelId ? ` (sub: ${subchannelId})` : ''}${variantToSend ? ` (variant: ${variantToSend})` : ''}`);
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

  // Derived filtered scenes based on query
  const filteredScenes = useMemo(() => {
    if (!query) return scenes;
    const q = query.toLowerCase();
    return scenes.filter(s => s.name?.toLowerCase().includes(q));
  }, [scenes, query]);

  const selectedSceneObj = useMemo(() => scenes.find(s => s.id === selectedScene), [scenes, selectedScene]);

  const commitSelection = useCallback((sceneId) => {
    setSelectedScene(sceneId);
    setOpen(false);
    // Keep query synced with chosen label (except unassign)
    if (sceneId) {
      const sc = scenes.find(s => s.id === sceneId);
      if (sc) setQuery(sc.name);
    } else {
      setQuery('');
    }
  }, [scenes]);

  const handleKeyDown = (e) => {
    if (!open && (e.key === 'ArrowDown' || e.key === 'ArrowUp')) {
      setOpen(true);
      setActiveIndex(0);
      return;
    }
    if (!open) return;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveIndex(i => Math.min(filteredScenes.length, i + 1)); // +1 for unassign option at index 0
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIndex(i => Math.max(0, i - 1));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (activeIndex === 0) {
        commitSelection('');
      } else {
        const item = filteredScenes[activeIndex - 1];
        if (item && isSceneCompatible(item).compatible) commitSelection(item.id);
      }
    } else if (e.key === 'Escape') {
      setOpen(false);
    }
  };

  useEffect(() => {
    if (open && listRef.current && activeIndex >= 0) {
      const el = listRef.current.querySelector(`[data-index="${activeIndex}"]`);
      if (el) {
        el.scrollIntoView({ block: 'nearest' });
      }
    }
  }, [open, activeIndex]);

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
      title={`Assign Program to ${display.name}`}
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
                  {display.resolution[0]}×{display.resolution[1]} • {formatOrientationLabel(display.orientation)}
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
            <form onSubmit={handleSubmit} autoComplete="off">
              <div className="scene-selection">
                <h3 style={{ marginBottom: '0.5rem' }}>Select Program</h3>
                <div className="scene-combobox-wrapper">
                  <label className="scene-combobox-label" id="scene-combobox-label">Program</label>
                  <div
                    className="scene-combobox"
                    role="combobox"
                    aria-haspopup="listbox"
                    aria-expanded={open}
                    aria-owns="scene-combobox-list"
                    aria-controls="scene-combobox-list"
                  >
                    <input
                      ref={inputRef}
                      type="text"
                      placeholder="Search programs..."
                      value={query}
                      aria-labelledby="scene-combobox-label"
                      onChange={(e) => {
                        setQuery(e.target.value);
                        setOpen(true);
                        setActiveIndex(0);
                      }}
                      onFocus={() => setOpen(true)}
                      onKeyDown={handleKeyDown}
                    />
                    {query && (
                      <button
                        type="button"
                        className="clear-btn"
                        aria-label="Clear search"
                        onClick={() => {
                          setQuery('');
                          inputRef.current?.focus();
                        }}
                      >
                        <X size={14} />
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={() => {
                        if (open) {
                          setOpen(false);
                        } else {
                          setOpen(true);
                          inputRef.current?.focus();
                        }
                      }}
                      aria-label={open ? 'Collapse list' : 'Expand list'}
                      style={{ background: 'none', border: 'none', padding: '2px', cursor: 'pointer', color: 'var(--color-text-tertiary, var(--color-text-secondary))' }}
                    >
                      <ChevronDown size={16} style={{ transform: open ? 'rotate(180deg)' : 'none', transition: 'transform 0.15s ease' }} />
                    </button>
                  </div>
                  {open && (
                    <ul
                      id="scene-combobox-list"
                      role="listbox"
                      ref={listRef}
                      className="scene-combobox-dropdown"
                      aria-label="Program options"
                    >
                      {/* Unassign option at index 0 */}
                      <li
                        role="option"
                        data-index={0}
                        className={`scene-combobox-option ${activeIndex === 0 ? 'active' : ''} ${selectedScene === '' ? 'selected' : ''}`}
                        aria-selected={selectedScene === ''}
                        onMouseEnter={() => setActiveIndex(0)}
                        onMouseDown={(e) => { e.preventDefault(); commitSelection(''); }}
                      >
                        <span className="scene-name">No Program (Unassign)</span>
                        <span className="scene-combobox-meta">Remove assignment</span>
                      </li>
                      {filteredScenes.map((scene, idx) => {
                        const compatibility = isSceneCompatible(scene);
                        const itemIndex = idx + 1; // account for unassign at 0
                        return (
                          <li
                            key={scene.id}
                            role="option"
                            data-index={itemIndex}
                            aria-selected={selectedScene === scene.id}
                            className={`scene-combobox-option ${selectedScene === scene.id ? 'selected' : ''} ${activeIndex === itemIndex ? 'active' : ''} ${!compatibility.compatible ? 'incompatible' : ''}`}
                            onMouseEnter={() => setActiveIndex(itemIndex)}
                            onMouseDown={(e) => {
                              e.preventDefault();
                              if (compatibility.compatible) commitSelection(scene.id);
                            }}
                          >
                            <Play size={16} />
                            <span className="scene-name" style={{ fontWeight: 500 }}>{scene.name}</span>
                            {compatibility.compatible && (
                              <CheckCircle size={14} className="compatible-icon" />
                            )}
                            {!compatibility.compatible && (
                              <span className="compatibility-badge" title={compatibility.reason}>⚠ {compatibility.reason}</span>
                            )}
                            <span className="scene-combobox-meta">
                              {(scene.channels?.length || 0)} ch
                              {scene.overlay && scene.overlay.overlays?.length > 0 && ` • ${scene.overlay.overlays.length} ov`}
                            </span>
                          </li>
                        );
                      })}
                      {filteredScenes.length === 0 && (
                        <li className="scene-combobox-empty">No programs match "{query}"</li>
                      )}
                    </ul>
                  )}
                </div>
                {scenes.length === 0 && !loading && (
                  <div className="empty-state">
                    <p>No programs available. Create a program first to assign it to displays.</p>
                  </div>
                )}
              </div>

              {contentVariants.length > 0 && (
                <div className="form-group" style={{ marginTop: '1rem' }}>
                  <label className="form-label">Content</label>
                  <select
                    className="form-select"
                    value={selectedVariant}
                    onChange={e => setSelectedVariant(e.target.value)}
                  >
                    {contentVariants.map(v => (
                      <option key={v.id} value={v.id}>{v.label}</option>
                    ))}
                  </select>
                  <p style={{ fontSize: '0.75rem', color: 'var(--color-text-secondary)', marginTop: '0.25rem' }}>
                    Choose what this display shows from the program.
                  </p>
                </div>
              )}

              <div className="assignment-preview">
                {selectedScene && selectedSceneObj && (
                  <div className="preview-info">
                    <h4>Assignment Preview</h4>
                    <p>
                      Program "<strong>{selectedSceneObj?.name}</strong>"
                      will be assigned to "<strong>{display.name}</strong>"
                    </p>
                    <div className="preview-details">
                      <span>Resolution: {display.resolution[0]}×{display.resolution[1]}</span>
                      <span>Orientation: {formatOrientationLabel(display.orientation)}</span>
                      {contentVariants.length > 0 && selectedVariant && (
                        <span>Content: {contentVariants.find(v => v.id === selectedVariant)?.label || selectedVariant}</span>
                      )}
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
                  {assigning ? 'Assigning...' : selectedScene ? 'Assign Program' : 'Unassign Program'}
                </button>
              </div>
            </form>
          )}
      </div>
    </Modal>
  );
};

export default SceneAssignment;
