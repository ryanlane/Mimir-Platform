// Display Card component for individual display clients
import React, { useState, useEffect } from 'react';
import './DisplayCard.css';
import { Monitor, Wifi, WifiOff, MapPin, Tag, Calendar, RotateCcw, Play, Globe, Package, Settings as SettingsIcon } from 'lucide-react';
import { api, normalizeMediaUrl } from '../../services/api';
import Button from '../../components/Button/Button';
import Icon from '../../components/Icon/Icon';
import Modal from '../../components/Modal/Modal';
import { formatOrientationLabel } from './orientationOptions';

// Desired client version from the server's release cache — fetched once and
// shared across all cards (module-level cache; 404 = no release cached yet).
let _latestReleasePromise = null;
function fetchDesiredClientVersion() {
  if (!_latestReleasePromise) {
    _latestReleasePromise = api
      .getLatestClientRelease()
      .then((resp) => resp?.data?.version || null)
      .catch(() => null);
  }
  return _latestReleasePromise;
}

// Loose semver-ish comparison: true when `desired` is newer than `current`.
function isVersionBehind(current, desired) {
  if (!current || !desired) return false;
  const parse = (v) => String(v).replace(/^v/, '').split(/[.+-]/).map((p) => parseInt(p, 10) || 0);
  const a = parse(current);
  const b = parse(desired);
  for (let i = 0; i < Math.max(a.length, b.length); i++) {
    if ((b[i] || 0) > (a[i] || 0)) return true;
    if ((b[i] || 0) < (a[i] || 0)) return false;
  }
  return false;
}

const DisplayCard = ({ display, onAssignScene, onEdit, onDelete, onRefresh, onConfigure, configureStatus, apiClient = api }) => {
  // const [imageLoading, setImageLoading] = useState(false); // (unused after image section commented out)
  const [showImagePreview, setShowImagePreview] = useState(false);
  const [imageError, setImageError] = useState(false);
  const [thumbLoading, setThumbLoading] = useState(false);
  const [thumbError, setThumbError] = useState(false);
  const [desiredClientVersion, setDesiredClientVersion] = useState(null);

  useEffect(() => {
    let cancelled = false;
    fetchDesiredClientVersion().then((v) => {
      if (!cancelled) setDesiredClientVersion(v);
    });
    return () => { cancelled = true; };
  }, []);
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

  const appendCacheBuster = (url) => {
    if (!url) return null;
    const separator = url.includes('?') ? '&' : '?';
    return `${url}${separator}ts=${Date.now()}`;
  };


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
    const displayIdentifiers = [...new Set([
      display.id,
      display.hostname,
      display.device_id,
      display.deviceId,
    ].filter(Boolean))];

    const fetchPersisted = async () => {
      for (const identifier of displayIdentifiers) {
        try {
          const resp = await apiClient.getPersistedLastImage(identifier, assignedSceneId);
          if (cancelled) return;
          const data = resp?.data || {};
          setPersisted({
            loading: false,
            error: null,
            thumb: normalizeMediaUrl(data.thumbnail_url || data.image_url || null),
            image: normalizeMediaUrl(data.image_url || null),
            updated_ts: data.updated_at || data.updated_ts || data.created_at || data.ts || null
          });
          return;
        } catch (err) {
          if (cancelled) return;
          if (err?.response?.status !== 404) {
            setPersisted(p => ({ ...p, loading: false, error: err?.message || 'persisted fetch failed' }));
            return;
          }
        }
      }

      setPersisted(p => ({ ...p, loading: false, thumb: null, image: null }));
    };

    fetchPersisted();
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

  const assignedSceneId = typeof display.assigned_scene_id === 'object' && display.assigned_scene_id?.id
    ? display.assigned_scene_id.id
    : display.assigned_scene_id;

  const publicHostHint = (() => {
    const host = window.location.hostname;
    if (!host || host === 'localhost' || host === '127.0.0.1') return null;
    return host;
  })();

  const canManualUpdate = (() => {
    // Need at least an assigned scene
    if (!assignedSceneId) return false;
    // We consider anything NOT explicitly 'realtime' as eligible
    const notRealtime = sceneInfo ? sceneInfo.update_strategy !== 'realtime' : true;
    // If we have at least one assignment (thus a job_id) we can attempt manual trigger
    const hasAssignment = !!sceneAssignment;
    // If job details exist, ensure it's not disabled; if we don't have details, assume enabled (optimistic)
    const enabled = jobDetails ? jobDetails.enabled !== false : true;
    // Broader schedule detection: any of (scene.schedule present, job freq fields, approx_interval_seconds, or simply an assignment)
    const hasSchedule = !!sceneInfo?.schedule || !!jobDetails?.freq_unit || !!jobDetails?.approx_interval_seconds || hasAssignment;
    const result = enabled && (notRealtime || !hasSchedule);
    if (process.env.NODE_ENV !== 'production') {
      // Helpful debug once per render group (can be noisy; guard on scene id)
      try {
        // eslint-disable-next-line no-console
        console.debug('ManualUpdateCheck', {
          sceneId: sceneInfo?.id || assignedSceneId,
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

  const canConfigure = display.displayType === 'discovered' && display.webhook_port;
  const canEditSettings = Boolean(onEdit);
  const configureLoading = configureStatus?.loading;
  const configureError = configureStatus?.error;
  const configureSuccess = configureStatus?.success;

  const handleManualUpdate = async () => {
    if (!assignedSceneId) return;
    setManualUpdateLoading(true);
    setManualUpdateError(null);
    setManualUpdateSuccess(false);
    try {
      // 1) Pre-flight: call channel request_image with correct payload (matches Postman)
      try {
        const channelEntry = Array.isArray(sceneInfo?.channels) ? sceneInfo.channels.find(c => c && typeof c === 'object' && (c.channel_id || c.id)) : null;
        const channelId = channelEntry?.channel_id || channelEntry?.id || null;
        if (channelId) {
          // Derive resolution from display
          let w = null, h = null;
          if (Array.isArray(display.resolution) && display.resolution.length >= 2) {
            w = Number(display.resolution[0]);
            h = Number(display.resolution[1]);
          } else if (display.width && display.height) {
            w = Number(display.width);
            h = Number(display.height);
          }
          // Fallback sane defaults
          if (!(w > 0 && h > 0)) {
            const ori = (display.orientation || 'landscape').toLowerCase();
            if (ori === 'portrait') { w = 600; h = 800; }
            else if (ori === 'square') { w = 600; h = 600; }
            else { w = 800; h = 600; }
          }
          // Orientation
          const inferred = w === h ? 'square' : (h > w ? 'portrait' : 'landscape');
          const orientation = (display.orientation || inferred || 'landscape').toLowerCase();
          // Optional subchannel (gallery)
          const subChannelId = channelEntry?.subchannel_id || channelEntry?.subChannelId || null;
          const payload = {
            settings: {
              resolution: [w, h],
              orientation,
              distribution: 'new',
              ...(subChannelId ? { subChannelId } : {}),
            },
          };
          // Fire-and-forget the image request (does not distribute, but validates correct generation path)
          await apiClient.requestChannelImage(channelId, payload);
        }
      } catch (preflightErr) {
        // Non-fatal: proceed to trigger scheduler distribution anyway
        console.warn('Channel preflight request_image failed (continuing to trigger job):', preflightErr?.message || preflightErr);
      }

      // 2) Targeted refresh for just this display
      const deviceId = display.hostname || display.id;
      if (!assignedSceneId || !deviceId) {
        throw new Error('Missing scene or device for targeted refresh');
      }
      await apiClient.refreshSceneTargeted(assignedSceneId, {
        target_devices: [deviceId],
        reason: 'manual-ui',
        force: false,
        public_host_hint: publicHostHint,
      });
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

  const liveImageUrl = appendCacheBuster(normalizeMediaUrl(display.current_image_url || null));
  const fallbackThumb = liveImageUrl;
  const thumbnailUrl = persisted.thumb || fallbackThumb;

  useEffect(() => {
    setThumbError(false);
    setThumbLoading(Boolean(thumbnailUrl));
  }, [thumbnailUrl]);

  useEffect(() => {
    setImageError(false);
  }, [persisted.image, liveImageUrl, display.id]);

  // Image action handlers removed (image section currently commented out)

  // robust date normalizer + relative formatter
  const normalizeTs = (ts) => {
    if (!ts && ts !== 0) return null;
    // number or numeric string
    if (typeof ts === 'number' || (typeof ts === 'string' && /^\d+$/.test(ts))) {
      const n = Number(ts);
      return new Date(n < 1e12 ? n * 1000 : n); // seconds -> ms
    }
    if (typeof ts === 'string') {
      const trimmed = ts.trim();
      const looksIsoWithoutZone = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?$/.test(trimmed);
      const d = new Date(looksIsoWithoutZone ? `${trimmed}Z` : trimmed);
      return isNaN(d.getTime()) ? null : d;
    }
    const d = new Date(ts);                     // Date-like object, etc.
    return isNaN(d.getTime()) ? null : d;
  };

  const formatRelative = (ts) => {
    const date = normalizeTs(ts);
    if (!date) return '';
    const diffMs = date.getTime() - Date.now();
    const isFuture = diffMs > 0;
    const absMs = Math.abs(diffMs);
    const totalMinutes = Math.round(absMs / 60000);
    const totalHours = Math.floor(totalMinutes / 60);
    const totalDays = Math.floor(totalHours / 24);

    if (absMs < 90 * 1000 || (isFuture && absMs < 5 * 60 * 1000)) {
      return 'just now';
    }

    const formatUnit = (value, unit) => `${value} ${unit}${value === 1 ? '' : 's'}`;

    if (totalMinutes < 60) {
      return isFuture
        ? `in ${formatUnit(totalMinutes, 'minute')}`
        : `${formatUnit(totalMinutes, 'minute')} ago`;
    }

    if (totalHours < 24) {
      const remainingMinutes = totalMinutes % 60;
      const hourPart = formatUnit(totalHours, 'hour');
      const minutePart = remainingMinutes ? ` ${formatUnit(remainingMinutes, 'minute')}` : '';
      return isFuture
        ? `in ${hourPart}${minutePart}`
        : `${hourPart}${minutePart} ago`;
    }

    const remainingHours = totalHours % 24;
    const dayPart = formatUnit(totalDays, 'day');
    const hourPart = remainingHours ? ` ${formatUnit(remainingHours, 'hour')}` : '';
    return isFuture
      ? `in ${dayPart}${hourPart}`
      : `${dayPart}${hourPart} ago`;
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
    } else if (display.updated_at) {
      setLastImageUpdateTs(display.updated_at);
    }
  }, [persisted.updated_ts, display.last_image_update_ts, display.updated_at]);

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
              } • {formatOrientationLabel(display.orientation)}
            </span>
          </div>

          {display.refresh_rate_hz && (
            <div className="detail-item">
              <RotateCcw size={14} />
              <span>{display.refresh_rate_hz}Hz</span>
            </div>
          )}

          {display.client_version && display.client_version !== 'unknown' && (
            <div
              className="detail-item"
              title={
                display.update_status === 'failed'
                  ? `Update to v${display.update_target || '?'} failed${display.update_error ? `: ${display.update_error}` : ''}`
                  : display.update_status === 'in_progress'
                  ? `Updating to v${display.update_target || '?'}…`
                  : isVersionBehind(display.client_version, desiredClientVersion)
                  ? `Update available: v${String(desiredClientVersion).replace(/^v/, '')}`
                  : 'Client version'
              }
            >
              <Package size={14} />
              <span>
                v{String(display.client_version).replace(/^v/, '')}
                {display.canary && (
                  <span style={{ color: 'var(--color-accent)', marginLeft: '0.35rem' }}>canary</span>
                )}
                {display.update_status === 'failed' ? (
                  <span style={{ color: 'var(--color-error)', marginLeft: '0.35rem' }}>
                    update failed
                  </span>
                ) : display.update_status === 'in_progress' ? (
                  <span style={{ color: 'var(--color-accent)', marginLeft: '0.35rem' }}>
                    updating…
                  </span>
                ) : isVersionBehind(display.client_version, desiredClientVersion) ? (
                  <span style={{ color: 'var(--color-warning)', marginLeft: '0.35rem' }}>
                    → v{String(desiredClientVersion).replace(/^v/, '')} queued
                  </span>
                ) : null}
              </span>
            </div>
          )}

          <div className="detail-item" data-reltime-tick={timeTick}>
            <Calendar size={14} />
            <span title={lastImageUpdateTs ? normalizeTs(lastImageUpdateTs)?.toLocaleString() || '' : ''}>
              Last updated:{' '}
              {lastImageUpdateTs ? formatRelative(lastImageUpdateTs) : 'Unknown'}
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
                {canEditSettings && (
                  <Button
                    icon={<RotateCcw size={14} />}
                    iconSize={14}
                    variant="ghost"
                    onClick={() => onEdit && onEdit(display, 'settings')}
                    title="Display settings"
                  >
                    Settings
                  </Button>
                )}
                <Button
                  icon="Edit"
                  iconSize={14}
                  variant='primary'
                  onClick={() => onAssignScene(display)}
                >
                  Edit
                </Button>
                {canConfigure && (
                  <Button
                    icon={<SettingsIcon size={14} />}
                    iconSize={14}
                    variant="ghost"
                    onClick={() => onConfigure && onConfigure(display)}
                    loading={configureLoading}
                    disabled={configureLoading}
                    title="Re-pair display"
                  >
                    Re-pair
                  </Button>
                )}
                
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
                    {manualUpdateLoading ? 'Requesting...' : (manualUpdateSuccess ? 'Triggered' : 'Request Image')}
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
              <div className="scene-buttons">
                {canEditSettings && (
                  <Button
                    icon={<RotateCcw size={14} />}
                    iconSize={14}
                    size="md"
                    variant={canConfigure ? 'secondary' : 'ghost'}
                    onClick={() => onEdit && onEdit(display, 'settings')}
                  >
                    Settings
                  </Button>
                )}
                {canConfigure && (
                  <Button
                    icon={<SettingsIcon size={14} />}
                    iconSize={14}
                    size="md"
                    variant='primary'
                    onClick={() => onConfigure && onConfigure(display)}
                    loading={configureLoading}
                    disabled={configureLoading}
                  >
                    Pair
                  </Button>
                )}
                <Button
                  icon="Plus"
                  iconSize={14}
                  size="md"
                  variant={canConfigure ? 'secondary' : 'primary'}
                  onClick={() => onAssignScene(display)}
                >
                  Assign Scene
                </Button>
              </div>
             
            </div>
          )}
          {(configureError || configureSuccess) && (
            <div style={{ marginTop: '0.35rem', fontSize: '0.7rem' }}>
              {configureError && (
                <span style={{ color: '#d9534f' }}>⚠ {configureError}</span>
              )}
              {configureSuccess && !configureError && (
                <span style={{ color: '#28a745' }}>Pairing started</span>
              )}
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
            src={persisted.image || liveImageUrl || ''}
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
                link.href = persisted.image || liveImageUrl || '';
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
