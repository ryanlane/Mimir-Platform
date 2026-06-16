import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { RefreshCw, Plus, FolderOpen, Store } from 'lucide-react';
import { api } from '../../services/api';
import { persistentCache } from '../../services/persistentCache';
import { useFeatureDetection } from '../../hooks/useFeatureDetection';
import featureDetection from '../../services/featureDetection';
import Header from '../../components/Header/Header';
import Button from '../../components/Button/Button';
import ChannelCard from './ChannelCard';
import InstallChannel from './InstallChannel';
import LinkDevChannel from './LinkDevChannel';
import PluginStore from './PluginStore';
import { SourceDetailPanel } from './SourceDetailPanel';
import { SkeletonSourceCard } from '../../components/Skeleton/Skeleton';
import './Channels.css';

// Legacy in-memory cache removed; persistent IndexedDB cache now used.

const Channels = () => {
    const navigate = useNavigate();
    const [channels, setChannels] = useState([]);
    const [loading, setLoading] = useState(true);
    const [panelChannel, setPanelChannel] = useState(null);
    const [showInstallModal, setShowInstallModal] = useState(false);
    const [showLinkDevModal, setShowLinkDevModal] = useState(false);
    const [showPluginStore, setShowPluginStore] = useState(false);
    const [storeUpdateCount, setStoreUpdateCount] = useState(0);

    const devModeEnabled = localStorage.getItem('mimir-developer-mode') === 'true';

    const { supportsV21, supportsChannelHealth, supportsPluginSystem } = useFeatureDetection();
    const [channelHealth, setChannelHealth] = useState({});
    const [manifest, setManifest] = useState([]);
  // const { isConnected: _isConnected } = useWebSocket(); // reserved for future realtime UI indicators

    const loadManifest = useCallback(async () => {
      if (!featureDetection.supportsPluginSystem()) return;
      try {
        const response = await api.getChannelsManifest();
        const manifestsMap = response.data || {};
        const manifestData = Object.values(manifestsMap).filter(Boolean);
        setManifest(manifestData);
        // eslint-disable-next-line no-console
        console.log('Loaded channel manifest (aggregated):', manifestsMap);
      } catch (error) {
        // eslint-disable-next-line no-console
        console.error('Error loading channel manifest:', error);
      }
    }, []);

    const loadChannels = useCallback(async () => {
      try {
        const { data } = await persistentCache.getChannels({
          onUpdate: (fresh) => {
            if (Array.isArray(fresh.channels)) {
              setChannels(fresh.channels);
              if (featureDetection.supportsChannelHealth()) {
                loadAllChannelHealth(fresh.channels);
              }
            }
          }
        });
        const channelsData = data?.channels || [];
        setChannels(channelsData);
        if (featureDetection.supportsChannelHealth()) {
          loadAllChannelHealth(channelsData);
        }
      } catch (error) {
        // eslint-disable-next-line no-console
        console.error('Error loading channels:', error);
      } finally {
        setLoading(false);
      }
    }, []);

    const refreshChannels = useCallback(async () => {
      setLoading(true);
      try {
        const resp = await api.getChannels();
        const fresh = resp.data;
        setChannels(fresh.channels || []);
      } catch (e) {
        // eslint-disable-next-line no-console
        console.error('Manual refresh failed:', e);
      } finally {
        setLoading(false);
      }
    }, []);

    // health loader separated to avoid re-definition each render of loadChannels
    const loadAllChannelHealth = async (channelList) => {
      try {
        const healthPromises = channelList.map(async (channel) => {
          try {
            const health = await api.getChannelHealth(channel.id);
            return { [channel.id]: health.data };
          } catch (error) {
            // eslint-disable-next-line no-console
            console.warn(`Health check failed for ${channel.id}:`, error);
            return { [channel.id]: { healthy: false, error: error.message } };
          }
        });
        const healthResults = await Promise.all(healthPromises);
        const healthMap = healthResults.reduce((acc, result) => ({ ...acc, ...result }), {});
        setChannelHealth(healthMap);
      } catch (error) {
        // eslint-disable-next-line no-console
        console.error('Error loading channel health:', error);
      }
    };

    useEffect(() => {
      const init = async () => {
        await loadChannels();
        await loadManifest();
      };
      init();
    }, [loadChannels, loadManifest]);

    useEffect(() => {
      const handleChannelUpdate = (event) => {
        const msg = event.detail || {};
        if (msg.type === 'channel_status_update') {
          const { channelId, status } = msg.data || {};
          setChannels(prev => prev.map(channel => (
            channel.id === channelId
              ? { ...channel, status: { ...channel.status, ...status } }
              : channel
          )));
        } else if (msg.type === 'sources_changed') {
          persistentCache.invalidateChannels().catch(() => {});
          refreshChannels();
          loadManifest();
        }
      };
      window.addEventListener('websocket-message', handleChannelUpdate);
      return () => window.removeEventListener('websocket-message', handleChannelUpdate);
    }, [refreshChannels, loadManifest]);

    // Sync panelChannel when list refreshes (health updates, enable/disable, etc.)
    useEffect(() => {
      if (panelChannel) {
        const fresh = channels.find(c => c.id === panelChannel.id);
        if (fresh) setPanelChannel(fresh);
        else setPanelChannel(null); // uninstalled
      }
    }, [channels]); // eslint-disable-line react-hooks/exhaustive-deps

    const handleCardClick = (channel, e) => {
      if (e.target.closest('button, a, input')) return;
      if (panelChannel?.id === channel.id) {
        setPanelChannel(null);
      } else {
        setPanelChannel(channel);
      }
    };

    const handleSettings = (channel) => {
      navigate(`/sources/${encodeURIComponent(channel.id)}`);
    };

    const handleToggleEnabled = useCallback(async (channel) => {
      try {
        const isCurrentlyEnabled = channel.enabled !== false;
        if (isCurrentlyEnabled) {
          await api.disableChannel(channel.id);
        } else {
          await api.enableChannel(channel.id);
        }
        await refreshChannels();
      } catch (error) {
        // eslint-disable-next-line no-console
        console.error('Failed to toggle channel:', error);
      }
    }, [refreshChannels]);

    const handleUninstall = useCallback(async (channel) => {
      try {
        await api.uninstallChannel(channel.id);
        setPanelChannel(prev => prev?.id === channel.id ? null : prev);
        await persistentCache.invalidateChannels();
        await refreshChannels();
      } catch (error) {
        // eslint-disable-next-line no-console
        console.error('Failed to uninstall channel:', error);
      }
    }, [refreshChannels]);

    const handleReloadDev = useCallback(async (channel) => {
      try {
        await api.reloadDevChannel(channel.id);
        await refreshChannels();
      } catch (error) {
        // eslint-disable-next-line no-console
        console.error('Failed to reload dev channel:', error);
      }
    }, [refreshChannels]);

    const handleUnlinkDev = useCallback(async (channel) => {
      try {
        await api.unlinkDevChannel(channel.id);
        setPanelChannel(prev => prev?.id === channel.id ? null : prev);
        await refreshChannels();
      } catch (error) {
        // eslint-disable-next-line no-console
        console.error('Failed to unlink dev channel:', error);
      }
    }, [refreshChannels]);

    const handleInstalled = useCallback(async () => {
      await persistentCache.invalidateChannels();
      await refreshChannels();
      loadManifest();
    }, [refreshChannels, loadManifest]);

    // Poll store for available updates badge (once per page load)
    useEffect(() => {
      api.getStoreUpdates()
        .then(r => setStoreUpdateCount(r.data?.pending_count || 0))
        .catch(() => {});
    }, [channels]);

    const handleDevLinked = useCallback(() => {
      refreshChannels();
      loadManifest();
    }, [refreshChannels, loadManifest]);

    const getStatusInfo = (channel) => {
      if (channel.status?.usingFallback) {
        return { type: 'warning', text: 'Using fallback image' };
      }
      if (channel.status?.lastError) {
        return { type: 'error', text: 'Error occurred' };
      }
      return { type: 'success', text: 'Active' };
    };

    const panelChannelHealth = panelChannel ? channelHealth[panelChannel.id] : null;
    const panelManifest = panelChannel ? manifest.find(m => m.id === panelChannel.id) : null;
    const panelStatusInfo = panelChannel ? getStatusInfo(panelChannel) : null;

    return (
      <div className="channels">
        <div className="channels-header">
          <Header
            title="Sources"
            icon="database"
            iconSize={36}
            description="Manage content sources and their configurations"
            actions={[
              <Button
                key="store"
                variant="secondary"
                onClick={() => setShowPluginStore(true)}
                icon={<Store size={16} />}
                type="button"
              >
                Browse Store
                {storeUpdateCount > 0 && (
                  <span className="store-update-badge">{storeUpdateCount}</span>
                )}
              </Button>,
              <Button
                key="install"
                variant="primary"
                onClick={() => setShowInstallModal(true)}
                icon={<Plus />}
                type="button"
              >
                Install Source
              </Button>,
              devModeEnabled && (
                <Button
                  key="link-dev"
                  variant="secondary"
                  onClick={() => setShowLinkDevModal(true)}
                  icon={<FolderOpen />}
                  type="button"
                >
                  Link Dev Source
                </Button>
              ),
              <Button
                key="refresh"
                variant="secondary"
                onClick={refreshChannels}
                icon={<RefreshCw />}
                type="button"
              >
                Refresh
              </Button>
            ].filter(Boolean)}
          />
        </div>

        <div className="sources-split-layout">
          <div className="sources-list-pane">
            {loading ? (
              <div className="channels-grid">
                {[1, 2, 3].map(i => <SkeletonSourceCard key={i} />)}
              </div>
            ) : channels.length > 0 ? (
              <div className="channels-grid">
                {channels.map(channel => {
                  const statusInfo = getStatusInfo(channel);
                  const health = channelHealth[channel.id];
                  const manifestData = manifest.find(m => m.id === channel.id);
                  const isSelected = panelChannel?.id === channel.id;
                  return (
                    <div
                      key={channel.id}
                      className={`source-card-wrapper${isSelected ? ' source-card-wrapper--selected' : ''}`}
                      onClick={(e) => handleCardClick(channel, e)}
                    >
                      <ChannelCard
                        channel={channel}
                        statusInfo={statusInfo}
                        health={health}
                        manifestData={manifestData}
                        v21Supported={supportsV21()}
                        channelHealthSupported={supportsChannelHealth()}
                        onOpenSettings={handleSettings}
                        onToggleEnabled={handleToggleEnabled}
                        onUninstall={handleUninstall}
                        onReloadDev={handleReloadDev}
                        onUnlinkDev={handleUnlinkDev}
                      />
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="empty-state">
                <h3>No sources installed</h3>
                <p className="text-tertiary">
                  Sources are the content plugins that feed your programs. Install one to begin.
                </p>
                <Button
                  variant="primary"
                  onClick={() => setShowInstallModal(true)}
                  icon={<Plus />}
                  type="button"
                >
                  Install Source
                </Button>
              </div>
            )}
          </div>

          {panelChannel && (
            <SourceDetailPanel
              channel={panelChannel}
              health={panelChannelHealth}
              manifestData={panelManifest}
              statusInfo={panelStatusInfo}
              v21Supported={supportsV21()}
              channelHealthSupported={supportsChannelHealth()}
              onClose={() => setPanelChannel(null)}
              onOpenSettings={handleSettings}
              onToggleEnabled={handleToggleEnabled}
              onUninstall={handleUninstall}
              onUnlinkDev={handleUnlinkDev}
              onReloadDev={handleReloadDev}
            />
          )}
        </div>

        <PluginStore
          isOpen={showPluginStore}
          onClose={() => setShowPluginStore(false)}
          installedChannels={channels}
          onInstalled={() => { handleInstalled(); setStoreUpdateCount(0); }}
        />

        <InstallChannel
          isOpen={showInstallModal}
          onClose={() => setShowInstallModal(false)}
          onInstalled={handleInstalled}
        />

        {devModeEnabled && (
          <LinkDevChannel
            isOpen={showLinkDevModal}
            onClose={() => setShowLinkDevModal(false)}
            onLinked={handleDevLinked}
          />
        )}
      </div>
    );
  };

export default Channels;
