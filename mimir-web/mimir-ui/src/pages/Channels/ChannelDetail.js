import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft, Heart, Power, RefreshCw, Trash2, Unlink, AlertCircle,
} from 'lucide-react';
import { api } from '../../services/api';
import { persistentCache } from '../../services/persistentCache';
import featureDetection from '../../services/featureDetection';
import Button from '../../components/Button/Button';
import './ChannelDetail.css';

// ── URL helpers (same logic as ChannelSettings) ───────────────────────────────

const getApiBaseUrl = () => {
  const raw =
    (typeof window !== 'undefined' && window.mimirApiBaseUrl) ||
    localStorage.getItem('mimir-api-base-url');
  if (raw) {
    try {
      const u = new URL(raw, window.location.origin);
      u.pathname = u.pathname.replace(/\/+$/, '') || '/';
      if (!/^\/api(\/|$)/i.test(u.pathname)) {
        u.pathname = (u.pathname === '/' ? '' : u.pathname) + '/api';
      }
      return u.toString();
    } catch {
      const t = String(raw).replace(/\/+$/, '');
      return /\/api(\/|$)/i.test(t) ? t : `${t}/api`;
    }
  }
  if (typeof window !== 'undefined') {
    const h = window.location.hostname;
    const p = window.location.protocol;
    if (h === 'localhost' || h === '127.0.0.1') return 'http://localhost:5000/api';
    if (h) return `${p}//${h}:5000/api`;
  }
  return 'http://localhost:5000/api';
};

const getServerBaseUrl = () => {
  const raw =
    (typeof window !== 'undefined' && window.mimirApiBaseUrl) ||
    localStorage.getItem('mimir-api-base-url');
  if (raw) {
    try {
      const u = new URL(raw, window.location.origin);
      u.pathname = u.pathname.replace(/\/+$/, '').replace(/\/api$/, '') || '/';
      return u.toString().replace(/\/$/, '');
    } catch {
      return String(raw).replace(/\/+$/, '').replace(/\/api$/, '');
    }
  }
  if (typeof window !== 'undefined') {
    const h = window.location.hostname;
    const p = window.location.protocol;
    if (h === 'localhost' || h === '127.0.0.1') return 'http://localhost:5000';
    if (h) return `${p}//${h}:5000`;
  }
  return 'http://localhost:5000';
};

// ── Web Component loader (extracted from ChannelSettings) ────────────────────

async function loadWebComponent(channelId, configData) {
  const managementModuleUrl = configData?.ui?.components?.manager;
  if (!managementModuleUrl) return null;

  const serverBaseUrl = getServerBaseUrl();
  let fullModuleUrl = managementModuleUrl.startsWith('http')
    ? managementModuleUrl
    : `${serverBaseUrl}${managementModuleUrl}`;
  fullModuleUrl += fullModuleUrl.includes('?') ? `&v=${Date.now()}` : `?v=${Date.now()}`;

  const manifestElementName = configData?.ui?.elements?.manager || null;
  const expectedElement =
    manifestElementName ||
    (channelId === 'com.spotify.status'
      ? 'x-spotify-status-manager'
      : channelId === 'com.epaperframe.photoframe'
      ? 'x-photo-frame-manager'
      : null);

  if (!expectedElement) return null;

  if (!customElements.get(expectedElement)) {
    window.mimirApiBaseUrl = getApiBaseUrl();
    window.mimirServerBaseUrl = getServerBaseUrl();

    const originalFetch = window.fetch;
    window.fetch = function (input, init = {}) {
      let url = input instanceof Request ? input.url : input;
      if (typeof url === 'string' && url.startsWith('/api/')) {
        url = `${getServerBaseUrl()}${url}`;
        const isAsset = url.includes('/assets/') || url.includes('/uploads/');
        const needsCreds =
          !isAsset &&
          (url.includes('/upload') ||
            url.includes('/settings') ||
            url.includes('/delete') ||
            (init.method && init.method !== 'GET'));
        init = { ...init, ...(needsCreds && { credentials: 'include' }) };
      }
      return originalFetch.call(this, url, init);
    };

    window.mimirAPI = {
      baseUrl: getApiBaseUrl(),
      async fetch(endpoint, options = {}) {
        const url = endpoint.startsWith('http')
          ? endpoint
          : `${getServerBaseUrl()}${endpoint}`;
        return fetch(url, { ...options, credentials: 'include' });
      },
      uploadFiles: async (cid, files) => {
        const formData = new FormData();
        files.forEach((f) => formData.append('files', f));
        return window.mimirAPI.fetch(`/api/channels/${cid}/upload`, {
          method: 'POST',
          body: formData,
        });
      },
    };

    try {
      await import(/* webpackIgnore: true */ fullModuleUrl);
    } catch (err) {
      if (!(err.name === 'NotSupportedError' && err.message.includes('already been used'))) {
        throw err;
      }
    }
  }

  return expectedElement;
}

// ── Component ────────────────────────────────────────────────────────────────

const ChannelDetail = () => {
  const { channelId } = useParams();
  const navigate = useNavigate();

  const [channel, setChannel] = useState(null);
  const [config, setConfig] = useState(null);
  const [health, setHealth] = useState(null);
  const [elementName, setElementName] = useState(null);
  const [loading, setLoading] = useState(true);
  const [componentError, setComponentError] = useState(null);
  const [confirmRemove, setConfirmRemove] = useState(false);
  const [actionPending, setActionPending] = useState(false);

  // Load everything needed for the detail page
  const load = useCallback(async () => {
    setLoading(true);
    setComponentError(null);
    try {
      // Channel list (from cache so it's fast)
      const { data } = await persistentCache.getChannels({});
      const found = (data?.channels || []).find((c) => c.id === channelId);
      if (!found) {
        navigate('/channels', { replace: true });
        return;
      }
      setChannel(found);

      // Manifest
      const manifestRes = await api.getChannelManifest(channelId);
      const configData = manifestRes.data;
      setConfig(configData);

      // Health (best-effort)
      if (featureDetection.supportsChannelHealth()) {
        try {
          const h = await api.getChannelHealth(channelId);
          setHealth(h.data);
        } catch {
          /* non-fatal */
        }
      }

      // Web Component
      if (configData?.ui?.components?.manager) {
        try {
          const el = await loadWebComponent(channelId, configData);
          setElementName(el);
        } catch (err) {
          setComponentError(err.message || 'Failed to load plugin UI');
        }
      }
    } catch (err) {
      console.error('ChannelDetail load error:', err);
    } finally {
      setLoading(false);
    }
  }, [channelId, navigate]);

  useEffect(() => {
    load();
  }, [load]);

  // Actions
  const handleToggleEnabled = async () => {
    if (!channel) return;
    setActionPending(true);
    try {
      if (channel.enabled !== false) {
        await api.disableChannel(channelId);
      } else {
        await api.enableChannel(channelId);
      }
      await load();
    } finally {
      setActionPending(false);
    }
  };

  const handleReloadDev = async () => {
    setActionPending(true);
    try {
      await api.reloadDevChannel(channelId);
      await load();
    } finally {
      setActionPending(false);
    }
  };

  const handleUninstall = async () => {
    setActionPending(true);
    try {
      await api.uninstallChannel(channelId);
      navigate('/channels', { replace: true });
    } finally {
      setActionPending(false);
      setConfirmRemove(false);
    }
  };

  const handleUnlinkDev = async () => {
    setActionPending(true);
    try {
      await api.unlinkDevChannel(channelId);
      navigate('/channels', { replace: true });
    } finally {
      setActionPending(false);
      setConfirmRemove(false);
    }
  };

  // Render Web Component
  const renderPlugin = () => {
    if (componentError) {
      return (
        <div className="cd-plugin-error">
          <AlertCircle size={20} />
          <p>{componentError}</p>
          <Button variant="secondary" onClick={load} icon={<RefreshCw size={14} />} size="sm">
            Retry
          </Button>
        </div>
      );
    }

    if (!config?.ui?.components?.manager) {
      return (
        <div className="cd-no-plugin">
          <p>This channel has no management interface.</p>
        </div>
      );
    }

    if (!elementName) {
      return (
        <div className="cd-no-plugin">
          <p>Plugin UI unavailable.</p>
        </div>
      );
    }

    const hostProps = {
      channel,
      config,
      apiBaseUrl: getApiBaseUrl(),
      api: {
        uploadFiles: (files) => {
          const formData = new FormData();
          files.forEach((f) => formData.append('files', f));
          return api.callChannelAPI(channelId, 'upload', 'POST', formData);
        },
        getImages: () => api.callChannelAPI(channelId, 'images', 'GET'),
        updateImage: (id, d) => api.callChannelAPI(channelId, `images/${id}`, 'PUT', d),
        toggleImage: (id) => api.callChannelAPI(channelId, `images/${id}/toggle`, 'POST'),
        deleteImage: (id) => api.callChannelAPI(channelId, `images/${id}`, 'DELETE'),
        getSettings: () => api.callChannelAPI(channelId, 'settings', 'GET'),
        updateSettings: (d) => api.callChannelAPI(channelId, 'settings', 'PUT', d),
        getHardwareStatus: () => api.callChannelAPI(channelId, 'hardware', 'GET'),
      },
      onSettingsChange: () => {},
      onSave: () => {},
      onClose: () => navigate('/channels'),
    };

    return React.createElement(elementName, {
      'data-hostprops': JSON.stringify(hostProps),
      key: `${channelId}-${elementName}`,
    });
  };

  if (loading) {
    return (
      <div className="cd-loading">
        <div className="loading-spinner" />
        <span>Loading channel…</span>
      </div>
    );
  }

  if (!channel) return null;

  const isEnabled = channel.enabled !== false;
  const isDev = channel.dev === true;

  return (
    <div className="channel-detail">
      {/* Breadcrumb */}
      <div className="cd-breadcrumb">
        <button className="cd-back" onClick={() => navigate('/channels')}>
          <ArrowLeft size={16} />
          Channels
        </button>
        <span className="cd-breadcrumb-sep">/</span>
        <span className="cd-breadcrumb-current">
          {config?.name || channel.name}
        </span>
      </div>

      <div className="cd-layout">
        {/* ── Sidebar ────────────────────────────────────────────────── */}
        <aside className="cd-sidebar">
          <div className="cd-sidebar-header">
            <h1 className="cd-channel-name">
              {config?.name || channel.name}
              {isDev && <span className="badge badge-dev">DEV</span>}
              {!isEnabled && <span className="badge badge-disabled">Disabled</span>}
            </h1>
            {(config?.description || channel.description) && (
              <p className="cd-channel-desc">
                {config?.description || channel.description}
              </p>
            )}
          </div>

          {/* Meta */}
          <div className="cd-meta">
            {channel.version && (
              <div className="cd-meta-row">
                <span className="cd-meta-label">Version</span>
                <span>{channel.version}</span>
              </div>
            )}
            <div className="cd-meta-row">
              <span className="cd-meta-label">ID</span>
              <span className="cd-mono">{channel.id}</span>
            </div>
            {isDev && channel.dev_path && (
              <div className="cd-meta-row">
                <span className="cd-meta-label">Path</span>
                <span className="cd-mono cd-dev-path">{channel.dev_path}</span>
              </div>
            )}
            {channel.status?.lastUpdate && (
              <div className="cd-meta-row">
                <span className="cd-meta-label">Last update</span>
                <span>{new Date(channel.status.lastUpdate).toLocaleString()}</span>
              </div>
            )}
          </div>

          {/* Status / Health */}
          <div className="cd-status-block">
            <div className={`cd-status-pill cd-status-${isEnabled ? (channel.status?.lastError ? 'error' : channel.status?.usingFallback ? 'warning' : 'success') : 'disabled'}`}>
              {isEnabled
                ? channel.status?.lastError
                  ? 'Error'
                  : channel.status?.usingFallback
                  ? 'Fallback'
                  : 'Active'
                : 'Disabled'}
            </div>
            {health && isEnabled && (
              <div className={`cd-health-pill ${health.healthy ? 'healthy' : 'unhealthy'}`}>
                <Heart size={13} />
                {health.healthy ? 'Healthy' : 'Issues'}
              </div>
            )}
          </div>

          {channel.status?.lastError && (
            <div className="cd-error-msg">
              <AlertCircle size={14} />
              <span>{channel.status.lastError}</span>
            </div>
          )}

          {/* Actions */}
          <div className="cd-actions">
            {isDev && (
              <Button
                variant="secondary"
                onClick={handleReloadDev}
                icon={<RefreshCw size={14} />}
                size="sm"
                disabled={actionPending}
              >
                Reload
              </Button>
            )}

            {!isDev && (
              <Button
                variant={isEnabled ? 'secondary' : 'primary'}
                onClick={handleToggleEnabled}
                icon={<Power size={14} />}
                size="sm"
                disabled={actionPending}
              >
                {isEnabled ? 'Disable' : 'Enable'}
              </Button>
            )}

            {confirmRemove ? (
              <div className="cd-confirm-remove">
                <span>{isDev ? 'Unlink' : 'Uninstall'}?</span>
                <Button
                  variant="danger"
                  onClick={isDev ? handleUnlinkDev : handleUninstall}
                  size="sm"
                  disabled={actionPending}
                >
                  Yes
                </Button>
                <Button
                  variant="secondary"
                  onClick={() => setConfirmRemove(false)}
                  size="sm"
                >
                  No
                </Button>
              </div>
            ) : (
              <Button
                variant="danger"
                onClick={() => setConfirmRemove(true)}
                icon={isDev ? <Unlink size={14} /> : <Trash2 size={14} />}
                size="sm"
                disabled={actionPending}
              >
                {isDev ? 'Unlink' : 'Uninstall'}
              </Button>
            )}
          </div>
        </aside>

        {/* ── Plugin content area ─────────────────────────────────────── */}
        <main className="cd-content">
          {renderPlugin()}
        </main>
      </div>
    </div>
  );
};

export default ChannelDetail;
