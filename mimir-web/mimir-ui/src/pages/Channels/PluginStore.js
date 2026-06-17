import React, { useState, useEffect, useCallback } from 'react';
import { Download, RefreshCw, CheckCircle, AlertCircle, ArrowUpCircle, ExternalLink } from 'lucide-react';
import { api } from '../../services/api';
import Modal from '../../components/Modal/Modal';
import Button from '../../components/Button/Button';
import './PluginStore.css';

const TAG_COLORS = {
  video: 'tag-blue',
  movie: 'tag-blue',
  movies: 'tag-blue',
  posters: 'tag-blue',
  cinema: 'tag-blue',
  photo: 'tag-green',
  gallery: 'tag-green',
  slideshow: 'tag-green',
  spotify: 'tag-purple',
  music: 'tag-purple',
  weather: 'tag-cyan',
  forecast: 'tag-cyan',
  live: 'tag-cyan',
  openweathermap: 'tag-cyan',
  comics: 'tag-orange',
  art: 'tag-orange',
  display: 'tag-orange',
  epaper: 'tag-orange',
  rendered: 'tag-orange',
};

const PluginTag = ({ tag }) => (
  <span className={`plugin-tag ${TAG_COLORS[tag.toLowerCase()] || 'tag-default'}`}>{tag}</span>
);

const PluginStore = ({ isOpen, onClose, installedChannels = [], onInstalled }) => {
  const [plugins, setPlugins] = useState([]);
  const [updates, setUpdates] = useState({});   // { pluginId: { update_available, latest_version } }
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [actionState, setActionState] = useState({}); // { pluginId: 'installing'|'updating'|'done'|'error' }
  const [actionMsg, setActionMsg] = useState({});     // { pluginId: string }
  const [registryMeta, setRegistryMeta] = useState(null);

  const installedIds = new Set(installedChannels.map(c => c.id));
  const installedVersions = Object.fromEntries(installedChannels.map(c => [c.id, c.version]));

  const loadRegistry = useCallback(async () => {
    setLoading(true);
    try {
      const [regResp, updResp] = await Promise.all([
        api.getStoreRegistry(),
        api.getStoreUpdates().catch(() => ({ data: { updates: [] } })),
      ]);

      const reg = regResp.data;
      setPlugins(reg.plugins || []);
      setRegistryMeta({ version: reg.version, updated: reg.updated });

      // Build updates map
      const updMap = {};
      for (const u of (updResp.data?.updates || [])) {
        updMap[u.plugin_id] = u;
      }
      setUpdates(updMap);
    } catch (err) {
      console.error('Store load failed:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isOpen) loadRegistry();
  }, [isOpen, loadRegistry]);

  const handleRefresh = async () => {
    setLoading(true);
    try {
      await api.refreshStoreRegistry();
      await loadRegistry();
    } finally {
      setLoading(false);
    }
  };

  const handleInstall = async (plugin) => {
    setActionState(s => ({ ...s, [plugin.id]: 'installing' }));
    setActionMsg(m => ({ ...m, [plugin.id]: '' }));
    try {
      await api.installChannelFromGit(plugin.git_url);
      setActionState(s => ({ ...s, [plugin.id]: 'done' }));
      setActionMsg(m => ({ ...m, [plugin.id]: `Installed v${plugin.version}` }));
      if (onInstalled) onInstalled();
    } catch (err) {
      const detail = err.response?.data?.detail || err.message;
      setActionState(s => ({ ...s, [plugin.id]: 'error' }));
      setActionMsg(m => ({ ...m, [plugin.id]: detail }));
    }
  };

  const handleUpdate = async (plugin) => {
    setActionState(s => ({ ...s, [plugin.id]: 'updating' }));
    setActionMsg(m => ({ ...m, [plugin.id]: '' }));
    try {
      await api.updateChannel(plugin.id, plugin.git_url);
      setActionState(s => ({ ...s, [plugin.id]: 'done' }));
      setActionMsg(m => ({ ...m, [plugin.id]: `Updated to v${plugin.version}` }));
      if (onInstalled) onInstalled();
      await loadRegistry();
    } catch (err) {
      const detail = err.response?.data?.detail || err.message;
      setActionState(s => ({ ...s, [plugin.id]: 'error' }));
      setActionMsg(m => ({ ...m, [plugin.id]: detail }));
    }
  };

  const filtered = plugins.filter(p => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (
      p.name?.toLowerCase().includes(q) ||
      p.description?.toLowerCase().includes(q) ||
      p.tags?.some(t => t.toLowerCase().includes(q)) ||
      p.author?.toLowerCase().includes(q)
    );
  });

  const pendingUpdates = Object.values(updates).filter(u => u.update_available).length;

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Source Store" size="large">
      <div className="plugin-store">
        {/* Toolbar */}
        <div className="store-toolbar">
          <input
            className="store-search"
            type="text"
            placeholder="Search sources…"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
          <Button
            variant="secondary"
            onClick={handleRefresh}
            icon={<RefreshCw size={14} />}
            disabled={loading}
            size="sm"
          >
            Refresh
          </Button>
        </div>

        {pendingUpdates > 0 && (
          <div className="store-update-banner">
            <ArrowUpCircle size={16} />
            {pendingUpdates} update{pendingUpdates > 1 ? 's' : ''} available
          </div>
        )}

        {/* Registry meta */}
        {registryMeta && (
          <p className="store-meta">
            Registry v{registryMeta.version} · last updated {registryMeta.updated}
          </p>
        )}

        {/* Plugin grid */}
        {loading ? (
          <div className="store-loading">
            <RefreshCw size={24} className="spin" />
            <span>Loading sources…</span>
          </div>
        ) : filtered.length === 0 ? (
          <div className="store-empty">
            {search ? `No sources match "${search}"` : 'No sources in registry'}
          </div>
        ) : (
          <div className="store-grid">
            {filtered.map(plugin => {
              const installed = installedIds.has(plugin.id);
              const updateInfo = updates[plugin.id];
              const hasUpdate = updateInfo?.update_available;
              const state = actionState[plugin.id];
              const msg = actionMsg[plugin.id];
              const installedVersion = installedVersions[plugin.id];

              return (
                <div key={plugin.id} className={`store-card${installed ? ' store-card--installed' : ''}`}>
                  <div className="store-card-header">
                    <div className="store-card-icon">{iconFor(plugin.icon)}</div>
                    <div className="store-card-title-block">
                      <h3 className="store-card-name">{plugin.name}</h3>
                      <span className="store-card-author">{plugin.author}</span>
                    </div>
                    <div className="store-card-badges">
                      {installed && (
                        <span className="badge badge-installed">
                          <CheckCircle size={11} /> Installed
                        </span>
                      )}
                      {hasUpdate && (
                        <span className="badge badge-update">
                          <ArrowUpCircle size={11} /> Update
                        </span>
                      )}
                    </div>
                  </div>

                  <p className="store-card-desc">{plugin.description}</p>

                  {plugin.tags?.length > 0 && (
                    <div className="store-card-tags">
                      {plugin.tags.map(t => <PluginTag key={t} tag={t} />)}
                    </div>
                  )}

                  <div className="store-card-footer">
                    <div className="store-card-version">
                      {installed && installedVersion ? (
                        hasUpdate
                          ? <span className="version-outdated">v{installedVersion} → <strong>v{plugin.version}</strong></span>
                          : <span className="version-current">v{installedVersion}</span>
                      ) : (
                        <span className="version-latest">v{plugin.version}</span>
                      )}
                    </div>

                    <div className="store-card-actions">
                      {plugin.homepage && (
                        <a
                          href={plugin.homepage}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="store-link-btn"
                          title="View on GitHub"
                        >
                          <ExternalLink size={14} />
                        </a>
                      )}

                      {state === 'done' ? (
                        <span className="action-success"><CheckCircle size={14} /> {msg}</span>
                      ) : state === 'error' ? (
                        <span className="action-error" title={msg}><AlertCircle size={14} /> Failed</span>
                      ) : hasUpdate ? (
                        <Button
                          variant="accent"
                          size="sm"
                          onClick={() => handleUpdate(plugin)}
                          disabled={state === 'updating'}
                          icon={<ArrowUpCircle size={14} />}
                        >
                          {state === 'updating' ? 'Updating…' : 'Update'}
                        </Button>
                      ) : installed ? (
                        <span className="action-installed"><CheckCircle size={14} /> Up to date</span>
                      ) : (
                        <Button
                          variant="primary"
                          size="sm"
                          onClick={() => handleInstall(plugin)}
                          disabled={state === 'installing'}
                          icon={<Download size={14} />}
                        >
                          {state === 'installing' ? 'Installing…' : 'Install'}
                        </Button>
                      )}
                    </div>
                  </div>

                  {state === 'error' && msg && (
                    <p className="store-card-error">{msg}</p>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </Modal>
  );
};

function iconFor(icon) {
  const map = {
    film: '🎬',
    photo: '🖼️',
    image: '🖼️',
    music: '🎵',
    spotify: '🎵',
    display: '🖥️',
    database: '🗄️',
    globe: '🌐',
    cloud: '☁️',
    'book-open': '📚',
    book: '📚',
  };
  return map[icon] || '🔌';
}

export default PluginStore;
