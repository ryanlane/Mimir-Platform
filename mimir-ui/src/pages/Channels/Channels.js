import React, { useState, useEffect, useCallback } from 'react';
import { RefreshCw, Info } from 'lucide-react';
import { api } from '../../services/api';
import { persistentCache } from '../../services/persistentCache';
import { useFeatureDetection } from '../../hooks/useFeatureDetection';
import featureDetection from '../../services/featureDetection';
import Header from '../../components/Header/Header';
import Button from '../../components/Button/Button';
import ChannelSettings from './ChannelSettings';
import ChannelCard from './ChannelCard';
import './Channels.css';

// Legacy in-memory cache removed; persistent IndexedDB cache now used.

const Channels = () => {
    const [channels, setChannels] = useState([]);
    const [loading, setLoading] = useState(true);
    const [showSettings, setShowSettings] = useState(false);
    const [selectedChannel, setSelectedChannel] = useState(null);

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
        console.log('📋 Loaded channel manifest (aggregated):', manifestsMap);
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
        const channelsData = data.channels || [];
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
        // eslint-disable-next-line no-console
        console.log('💚 Loaded channel health:', healthMap);
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
        if (event.data?.type === 'channel_status_update') {
          const { channelId, status } = event.data;
          setChannels(prev => prev.map(channel => (
            channel.id === channelId
              ? { ...channel, status: { ...channel.status, ...status } }
              : channel
          )));
        }
      };
      window.addEventListener('websocket-message', handleChannelUpdate);
      return () => window.removeEventListener('websocket-message', handleChannelUpdate);
    }, []);

    const handleSettings = (channel) => {
      setSelectedChannel(channel);
      setShowSettings(true);
    };

    const getStatusInfo = (channel) => {
      if (channel.status?.usingFallback) {
        return { type: 'warning', text: 'Using fallback image' };
      }
      if (channel.status?.lastError) {
        return { type: 'error', text: 'Error occurred' };
      }
      return { type: 'success', text: 'Active' };
    };

    if (loading) {
      return (
        <div className="loading">
          <div className="loading-spinner" />
          <span>Loading channels...</span>
        </div>
      );
    }

    return (
      <div className="channels">
        <div className="channels-header">
          <Header
            title="Channels"
              icon="tv"
              iconSize={36}
              description="Manage channel configurations and settings"
              actions={[
                supportsPluginSystem() && (
                  <Button
                    key="manifest"
                    variant="secondary"
                    onClick={loadManifest}
                    icon={<Info />}
                    type="button"
                  >
                    Manifest
                  </Button>
                ),
                <Button
                  key="refresh"
                  variant="primary"
                  onClick={refreshChannels}
                  icon={<RefreshCw />}
                  type="button"
                >
                  Refresh
                </Button>
              ].filter(Boolean)}
          />
        </div>

        {channels.length > 0 ? (
          <div className="channels-grid">
            {channels.map(channel => {
              const statusInfo = getStatusInfo(channel);
              const health = channelHealth[channel.id];
              const manifestData = manifest.find(m => m.id === channel.id);
              return (
                <ChannelCard
                  key={channel.id}
                  channel={channel}
                  statusInfo={statusInfo}
                  health={health}
                  manifestData={manifestData}
                  v21Supported={supportsV21()}
                  channelHealthSupported={supportsChannelHealth()}
                  onOpenSettings={handleSettings}
                />
              );
            })}
          </div>
        ) : (
          <div className="empty-state">
            <h3>No channels available</h3>
            <p className="text-tertiary">
              No channels were discovered. Make sure channels are properly installed in the channels directory.
            </p>
            <Button
              variant="primary"
              onClick={refreshChannels}
              icon={<RefreshCw />}
              type="button"
            >
              Refresh Channels
            </Button>
          </div>
        )}

        {showSettings && selectedChannel && (
          <ChannelSettings
            channel={selectedChannel}
            onClose={() => {
              setShowSettings(false);
              setSelectedChannel(null);
              loadChannels();
            }}
          />
        )}
      </div>
    );
  };

export default Channels;
