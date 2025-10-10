// Display Card component for individual display clients
import React, { useState, useEffect } from 'react';
import './DisplayCard.css';
import { Monitor, Wifi, WifiOff, MapPin, Tag, Calendar, RotateCcw, Play, Globe } from 'lucide-react';
import { api } from '../../services/api';
import Button from '../../components/Button/Button';
import Icon from '../../components/Icon/Icon';
import Modal from '../../components/Modal/Modal';

const DisplayCard = ({ display, onAssignScene, onEdit, onDelete, onRefresh, apiClient = api }) => {
  // const [imageLoading, setImageLoading] = useState(false); // (unused after image section commented out)
  const [showImagePreview, setShowImagePreview] = useState(false);
  const [imageError, setImageError] = useState(false);
  const [thumbLoading, setThumbLoading] = useState(false);
  const [thumbError, setThumbError] = useState(false);
  const [persisted, setPersisted] = useState({ loading: false, error: null, thumb: null, image: null, updated_ts: null });
  // Scheduler-related state for manual update button
  const [sceneInfo, setSceneInfo] = useState(null); // scene details
  const [sceneAssignment, setSceneAssignment] = useState(null); // first scene assignment (contains job_id)
  const [jobDetails, setJobDetails] = useState(null); // fetched scheduler job details (freq / enabled)
  const [manualUpdateLoading, setManualUpdateLoading] = useState(false);
  const [manualUpdateError, setManualUpdateError] = useState(null);
  const [manualUpdateSuccess, setManualUpdateSuccess] = useState(false);

  // Lightweight cache (module scoped via closure) - fallback if window-scoped not desired
  if (!window.__sceneScheduleCache) {
    window.__sceneScheduleCache = { jobsByScene: {}, ts: 0 };
  }

  const SCHEDULE_CACHE_TTL_MS = 30_000; // 30s


  // Fetch persisted last-image (per display+scene) if a scene is assigned
  useEffect(() => {
    let cancelled = false;
    // Some display objects may carry complex assigned_scene_id structure; normalize to primitive
    const assignedSceneId = typeof display.assigned_scene_id === 'object' && display.assigned_scene_id?.id
      ? display.assigned_scene_id.id
      : display.assigned_scene_id;
    if (!assignedSceneId) {
      setPersisted(p => ({ ...p, thumb: null, image: null }));
      return () => { cancelled = true; };
    }
    setPersisted(p => ({ ...p, loading: true, error: null }));
  apiClient.getPersistedLastImage(display.id, assignedSceneId)
      .then(resp => {
        if (cancelled) return;
        const data = resp?.data || {};
        setPersisted({
          loading: false,
          error: null,
          thumb: data.thumbnail_url || data.image_url || null,
          image: data.image_url || null,
          updated_ts: data.updated_at || data.updated_ts || data.ts || null
        });
      })
      .catch(err => {
        if (cancelled) return;
        // 404 simply means no persisted record yet; treat silently
        if (err?.response?.status === 404) {
          setPersisted(p => ({ ...p, loading: false }));
        } else {
            setPersisted(p => ({ ...p, loading: false, error: err?.message || 'persisted fetch failed' }));
        }
      });
    return () => { cancelled = true; };
  }, [display.id, display.assigned_scene_id, display.current_image_url, apiClient]);

  // Note: we include display.current_image_url so that when a realtime MQTT
  // 'display_image' event updates the display object in parent state, this card
  // re-runs the persisted image fetch to obtain the latest stored full-size
  // image & thumb (if the backend generated a new persisted record). This keeps
  // modal + thumb in sync with live distribution without forcing a full page refresh.

  // Fetch scene details & scheduler job mapping when assigned scene changes
  useEffect(() => {
    let cancelled = false;
    const assignedSceneId = typeof display.assigned_scene_id === 'object' && display.assigned_scene_id?.id
      ? display.assigned_scene_id.id
      : display.assigned_scene_id;
    if (!assignedSceneId) {
      setSceneInfo(null);
      setSceneAssignment(null);
      setJobDetails(null);
      return () => { cancelled = true; };
    }

    // Helper to decide if we should fetch schedule jobs again
    const now = Date.now();
    const cache = window.__sceneScheduleCache;
    const cacheFresh = (now - cache.ts) < SCHEDULE_CACHE_TTL_MS;

    // Fetch scene details first
  apiClient.getScene(assignedSceneId)
      .then(resp => {
        if (cancelled) return;
        setSceneInfo(resp.data);
      })
      .catch(err => {
        if (cancelled) return;
        console.warn('Failed to fetch scene info', err?.message);
        setSceneInfo(null);
      });

    // If cache fresh and job list for this scene already resolved, reuse
    if (cacheFresh && cache.jobsByScene[assignedSceneId]) {
      const cached = cache.jobsByScene[assignedSceneId];
      setSceneAssignment(cached.assignment || null);
      setJobDetails(cached.jobDetails || null);
      return () => { cancelled = true; };
    }

    // Fetch scene assignments (NOT full jobs)
  apiClient.getSceneSchedules(assignedSceneId)
      .then(async resp => {
        if (cancelled) return;
        const assignments = resp?.data || [];
        if (!Array.isArray(assignments) || assignments.length === 0) {
          setSceneAssignment(null);
          setJobDetails(null);
          cache.jobsByScene[assignedSceneId] = { assignment: null, jobDetails: null };
          cache.ts = Date.now();
          return;
        }
        const firstAssignment = assignments[0];
        setSceneAssignment(firstAssignment);
        // Fetch job details so we can verify enabled & interval
        try {
          const jobResp = await apiClient.getSchedulerJob(firstAssignment.job_id);
          if (cancelled) return;
            setJobDetails(jobResp?.data || null);
            cache.jobsByScene[assignedSceneId] = { assignment: firstAssignment, jobDetails: jobResp?.data || null };
            cache.ts = Date.now();
        } catch (e) {
          if (cancelled) return;
          console.warn('Failed to fetch scheduler job details', e?.message);
          setJobDetails(null);
          cache.jobsByScene[assignedSceneId] = { assignment: firstAssignment, jobDetails: null };
          cache.ts = Date.now();
        }
      })
      .catch(err => {
        if (cancelled) return;
        console.warn('Failed to fetch scene schedules', err?.message);
        setSceneAssignment(null);
        setJobDetails(null);
      });

    return () => { cancelled = true; };
  }, [display.assigned_scene_id, apiClient]);

  const canManualUpdate = (() => {
    // Need at least an assigned scene
    if (!sceneInfo) return false;
    // We consider anything NOT explicitly 'realtime' as eligible
    const notRealtime = sceneInfo.update_strategy !== 'realtime';
    // If we have at least one assignment (thus a job_id) we can attempt manual trigger
    const hasAssignment = !!sceneAssignment;
    // If job details exist, ensure it's not disabled; if we don't have details, assume enabled (optimistic)
    const enabled = jobDetails ? jobDetails.enabled !== false : true;
    // Broader schedule detection: any of (scene.schedule present, job freq fields, approx_interval_seconds, or simply an assignment)
    const hasSchedule = !!sceneInfo.schedule || !!jobDetails?.freq_unit || !!jobDetails?.approx_interval_seconds || hasAssignment;
    const result = notRealtime && enabled && hasSchedule;
    if (process.env.NODE_ENV !== 'production') {
      // Helpful debug once per render group (can be noisy; guard on scene id)
      try {
        // eslint-disable-next-line no-console
        console.debug('ManualUpdateCheck', {
          sceneId: sceneInfo?.id,
          update_strategy: sceneInfo?.update_strategy,
          hasAssignment,
          jobEnabled: jobDetails?.enabled,
          freq_unit: jobDetails?.freq_unit,
          approx_interval_seconds: jobDetails?.approx_interval_seconds,
          hasSchedule,
          result
        });
      } catch {}
    }
    return result;
  })();

  const handleManualUpdate = async () => {
    if (!sceneAssignment) return;
    setManualUpdateLoading(true);
    setManualUpdateError(null);
    setManualUpdateSuccess(false);
    try {
      const jobId = sceneAssignment.job_id || jobDetails?.id;
      if (!jobId) throw new Error('Missing job id for manual trigger');
  await apiClient.triggerSchedulerJob(jobId, 'Manual display card update');
      setManualUpdateSuccess(true);
      // After triggering the job, attempt a refresh of current image (slight delay may be needed externally)
      onRefresh && onRefresh();
      // Auto-hide success after short duration
      setTimeout(() => setManualUpdateSuccess(false), 4000);
    } catch (e) {
      setManualUpdateError(e?.response?.data?.detail || e.message || 'Manual update failed');
    } finally {
      setManualUpdateLoading(false);
    }
  };

  const fallbackThumb = display.current_image_url
    ? `${apiClient.getDisplayImageUrl(display.id)}?thumb=1&ts=${Date.now()}`
    : null;
  const thumbnailUrl = persisted.thumb || fallbackThumb;

  // Image action handlers removed (image section currently commented out)

  // robust date normalizer + relative formatter
  const normalizeTs = (ts) => {
    if (!ts && ts !== 0) return null;
    // number or numeric string
    if (typeof ts === 'number' || (typeof ts === 'string' && /^\d+$/.test(ts))) {
      const n = Number(ts);
      return new Date(n < 1e12 ? n * 1000 : n); // seconds -> ms
    }
    const d = new Date(ts);                     // ISO string, etc.
    return isNaN(d.getTime()) ? null : d;
  };

  const formatRelative = (ts) => {
    const date = normalizeTs(ts);
    if (!date) return '';
    const diffMs = Date.now() - date.getTime();
    const mins = Math.floor(diffMs / 60000);
    const hours = Math.floor(mins / 60);
    const days = Math.floor(hours / 24);
    if (mins < 1)  return 'Just now';
    if (mins < 60) return `${mins}m ago`;
    if (hours < 24) return `${hours}h ago`;
    return `${days}d ago`;
  };

  const getStatusColor = () => {
    if (display.is_online) return 'status-online';
    return 'status-offline';
  };

  // Stable local timestamp so transient persisted fetch states don't clear display
  const [lastImageUpdateTs, setLastImageUpdateTs] = useState(null);
  // Consolidate sources: prefer persisted.updated_ts if present, else display.last_image_update_ts
  useEffect(() => {
    if (persisted.updated_ts) {
      setLastImageUpdateTs(persisted.updated_ts);
    } else if (display.last_image_update_ts) {
      setLastImageUpdateTs(display.last_image_update_ts);
    }
  }, [persisted.updated_ts, display.last_image_update_ts]);

  // Ticking re-render to keep relative time fresh without altering timestamp.
  const [timeTick, setTimeTick] = useState(0); // value not used directly, only triggers render
  useEffect(() => {
    if (!lastImageUpdateTs) return; // no ticking until we have a timestamp
    const interval = setInterval(() => setTimeTick(t => t + 1), 60 * 1000); // update every minute
    return () => clearInterval(interval);
  }, [lastImageUpdateTs]);

  return (
    <>
      <div className={`display-card ${getStatusColor()} ${display.displayType === 'discovered' ? 'discovered-display' : 'registered-display'}`}>
        <div className="display-card-header">
          <div className="display-info">
            <div className="display-title">
              <Icon name="Monitor" size={20} color="var(--color-text)" />              
              <h3>{display.name}</h3>
              <div className={`display-status-indicator ${display.is_online ? 'online' : 'offline'}`}>
                {display.is_online ? (
                  <Icon name="Link" size={14} color="var(--color-mimir-dark-green)" />
                ) : (
                  <Icon name="Unlink" size={14} color="var(--color-mimir-dark-green)" />
                )}
              </div>
              {display.displayType === 'discovered' && (
                <span className="source-dot discovered" title="Discovered" />
              )}
              {display.displayType === 'registered' && (
                <span className="source-dot registered" title="Registered" />
              )}
            </div>
            {display.description && (
              <p className="display-description">{display.description}</p>
            )}
          </div>

        </div>
        {/* {display.cap || display.capabilities ? (
          <div className="capabilities-row">
            {(() => { const cap = display.cap || display.capabilities || {}; return (
              <>
                {Array.isArray(cap.res) && cap.res.length === 2 && (
                  <span className="cap-badge" title="Resolution">{cap.res[0]}×{cap.res[1]}</span>
                )}
                {cap.ori && (
                  <span className="cap-badge" title="Orientation">{cap.ori}</span>
                )}
                {cap.client_version && (
                  <span className="cap-badge" title="Client Version">v{cap.client_version}</span>
                )}
                {cap.redis_distribution && (
                  <span className="cap-flag" title="Redis Distribution Enabled">redis</span>
                )}
                {cap.content_claiming && (
                  <span className="cap-flag" title="Content Claiming Enabled">claim</span>
                )}
              </>
            ); })()}
          </div>
        ) : null} */}

        {/* Inline Thumbnail */}
        <div className="display-thumbnail-wrapper">
          {thumbnailUrl ? (
            <div
              className={`display-thumbnail ${thumbLoading ? 'loading' : ''} ${thumbError ? 'error' : ''} ${!display.is_online ? 'offline' : ''}`}
              onClick={() => {
                if (!thumbError) {
                  setShowImagePreview(true);
                }
              }}
              title={thumbError ? 'Image failed to load' : 'Click to view current image'}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  if (!thumbError) setShowImagePreview(true);
                }
              }}
            >
              {thumbnailUrl && (
                <img
                  src={thumbnailUrl}
                  alt={`Thumbnail for ${display.name}`}
                  loading="lazy"
                  onLoad={() => setThumbLoading(false)}
                  onError={() => {
                    setThumbLoading(false);
                    setThumbError(true);
                  }}
                  style={{ display: thumbError ? 'none' : 'block' }}
                />
              )}
              {thumbError && (
                <div className="thumb-placeholder">Image Error</div>
              )}
              {!thumbnailUrl && (
                <div className="thumb-placeholder">No Image</div>
              )}
              <div className="reload-hint">View</div>
            </div>
          ) : (
            <div className={`display-thumbnail ${!display.is_online ? 'offline' : ''}`}>
              <div className="thumb-placeholder">No Image</div>
            </div>
          )}
        </div>

        <div className="display-details">
          {display.location && (
            <div className="detail-item">
              <MapPin size={14} />
              <span>{display.location}</span>
            </div>
          )}

          {(display.ip || display.ip_address || display.ipAddress || (Array.isArray(display.ip_addresses) && display.ip_addresses.length > 0) || (Array.isArray(display.ipAddresses) && display.ipAddresses.length > 0)) && (
            <div className="detail-item" title={Array.isArray(display.ip_addresses) ? display.ip_addresses.join(', ') : (Array.isArray(display.ipAddresses) ? display.ipAddresses.join(', ') : (display.ip || display.ip_address || display.ipAddress))}>
              <Globe size={14} />
              <span>
                {display.ip || display.ip_address || display.ipAddress || (Array.isArray(display.ip_addresses) ? display.ip_addresses[0] : (Array.isArray(display.ipAddresses) ? display.ipAddresses[0] : ''))}
              </span>
            </div>
          )}

          <div className="detail-item">
            <Monitor size={14} />
            <span>
              {display.resolution && Array.isArray(display.resolution) && display.resolution.length >= 2
                ? `${display.resolution[0]}×${display.resolution[1]}`
                : display.width && display.height
                ? `${display.width}×${display.height}`
                : 'Unknown resolution'
              } • {display.orientation || 'landscape'}
            </span>
          </div>

          {display.refresh_rate_hz && (
            <div className="detail-item">
              <RotateCcw size={14} />
              <span>{display.refresh_rate_hz}Hz</span>
            </div>
          )}

          <div className="detail-item" data-reltime-tick={timeTick}>
            <Calendar size={14} />
            <span>
              Last updated:{' '}
              {lastImageUpdateTs ? formatRelative(lastImageUpdateTs) : ''}
            </span>
          </div>

          {display.tags && display.tags.length > 0 && (
            <div className="detail-item">
              <Tag size={14} />
              <div className="tags">
                {display.tags.map(tag => (
                  <span key={tag} className="tag">{tag}</span>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="display-scene-info">
          {display.assigned_scene_id ? (
            <div className="scene-assigned">
              <div className="scene-info">
                <Play size={14} />
                <span>Scene: <strong>{display.assigned_scene_name}</strong></span>
              </div>
              <div className="scene-buttons">
                <Button
                  icon="Edit"
                  iconSize={14}
                  variant='primary'
                  onClick={() => onAssignScene(display)}
                >
                  Edit
                </Button>
                
                {canManualUpdate && (
                  <Button
                    icon="Zap"
                    iconSize={14}                    
                    onClick={handleManualUpdate}
                    disabled={manualUpdateLoading || manualUpdateSuccess}
                    loading={manualUpdateLoading}
                    variant={manualUpdateSuccess ? 'success' : 'secondary'}
                    className={manualUpdateSuccess ? 'btn-active' : ''}
                  >
                    {manualUpdateLoading ? 'Updating...' : (manualUpdateSuccess ? 'Triggered' : 'Update')}
                  </Button>
                )}
                {/* {!canManualUpdate && (
                  <button
                    className="btn btn-sm btn-tertiary"
                    onClick={handleManualUpdate}
                    disabled={manualUpdateLoading}
                    title={manualUpdateLoading ? 'Triggering update...' : 'Trigger scheduled scene now'}
                    style={{ marginLeft: '0.5rem' }}
                  >
                    <Zap size={14} className={manualUpdateLoading ? 'spinning' : ''} />
                    {!manualUpdateLoading && 'Update Now'}
                  </button>
                )} */}
              </div>
            </div>
          ) : (
            <div className="scene-unassigned">
              <div className="no-scene">No scene assigned</div>
              <Button
                icon="Plus"
                iconSize={14}
                size="md"
                variant='primary'
                onClick={() => onAssignScene(display)}
              >
                Assign Scene
              </Button>           
             
            </div>
          )}
          {canManualUpdate && (manualUpdateError || manualUpdateSuccess) && (
            <div style={{ marginTop: '0.35rem', fontSize: '0.7rem' }}>
              {manualUpdateError && (
                <span style={{ color: '#d9534f' }}>⚠ {manualUpdateError}</span>
              )}
              {manualUpdateSuccess && !manualUpdateError && (
                <span style={{ color: '#28a745' }}>Triggered</span>
              )}
            </div>
          )}
        </div>



      </div>

      <Modal
        isOpen={showImagePreview}
        onClose={() => setShowImagePreview(false)}
        title={`Current Display Image - ${display.name}`}
        size="large"
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          <img
            src={persisted.image || apiClient.getDisplayImageUrl(display.id)}
            alt={`Current display for ${display.name}`}
            onError={() => setImageError(true)}
            style={{
              maxWidth: '100%',
              maxHeight: '70vh',
              objectFit: 'contain',
              border: '1px solid var(--color-border)',
              borderRadius: '4px'
            }}
          />
          {imageError && (
            <p className="error-message" style={{ color: 'var(--color-error)', fontSize: '0.75rem' }}>Failed to load image</p>
          )}
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem', marginTop: '0.25rem' }}>
            <Button
              icon="X"
              iconSize={14}
              size="sm"
              onClick={() => setShowImagePreview(false)}
            >
              Close
            </Button>
            <Button
              icon="Download"
              iconSize={14}
              size="sm"
              onClick={() => {
                const link = document.createElement('a');
                link.href = persisted.image || apiClient.getDisplayImageUrl(display.id);
                link.download = `display-${display.name}-current.jpg`;
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
              }}
            >
              Download
            </Button>

          </div>
        </div>
      </Modal>
    </>
  );
};

export default DisplayCard;
