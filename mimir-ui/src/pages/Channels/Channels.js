import React, { useState, useEffect, useCallback } from 'react';
import { Settings, RefreshCw, AlertCircle, Heart, Info } from 'lucide-react';
import { api } from '../../services/api';
import { persistentCache } from '../../services/persistentCache';
import { useWebSocket } from '../../hooks/useWebSocket';
import { useFeatureDetection } from '../../hooks/useFeatureDetection';
import featureDetection from '../../services/featureDetection';
import ChannelSettings from './ChannelSettings';
import DebugPanel from '../../components/DebugPanel/DebugPanel';
import './Channels.css';

// Legacy in-memory cache removed; persistent IndexedDB cache now used.

const Channels = () => {
  const [channels, setChannels] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showSettings, setShowSettings] = useState(false);
  const [selectedChannel, setSelectedChannel] = useState(null);

  // v2.1 Feature detection and new state
  const { 
    supportsV21, 
    supportsChannelHealth, 
    supportsPluginSystem,
    apiVersion
  } = useFeatureDetection();
  
  const [channelHealth, setChannelHealth] = useState({});
  const [manifest, setManifest] = useState([]);

  // WebSocket integration for real-time updates
  const { isConnected } = useWebSocket();

  // v2.1: Load channel manifest
  const loadManifest = useCallback(async () => {
    if (!featureDetection.supportsPluginSystem()) {
      return;
    }
    
    try {
      const response = await api.getChannelsManifest();
      // New aggregated map structure: { data: { channelId: manifestObj } }
      const manifestsMap = response.data || {};
      const manifestData = Object.values(manifestsMap).filter(Boolean);
      setManifest(manifestData);
      console.log('📋 Loaded channel manifest (aggregated):', manifestsMap);
    } catch (error) {
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
      console.error('Error loading channels:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  // Manual refresh function that bypasses cache
  const refreshChannels = useCallback(async () => {
    // Force bypass: directly call API then update persistent cache
    setLoading(true);
    try {
      const resp = await api.getChannels();
      const fresh = resp.data;
      setChannels(fresh.channels || []);
      // Write through to IDB for next load
      // Reuse persistentCache internals by setting directly
      // (Import idb if needed for fine control; here we rely on background refresh next visit.)
    } catch (e) {
      console.error('Manual refresh failed:', e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const initializeChannels = async () => {
      await loadChannels();
      // Load v2.1 features if supported
      await loadManifest();
    };
    
    initializeChannels();
  }, [loadChannels, loadManifest, channels.length]);
  useEffect(() => {
    const handleChannelUpdate = (event) => {
      if (event.data?.type === 'channel_status_update') {
        const { channelId, status } = event.data;
        setChannels(prev => prev.map(channel => 
          channel.id === channelId 
            ? { ...channel, status: { ...channel.status, ...status } }
            : channel
        ));
      }
    };

    window.addEventListener('websocket-message', handleChannelUpdate);
    return () => window.removeEventListener('websocket-message', handleChannelUpdate);
  }, []);

  // v2.1: Load health for all channels
  const loadAllChannelHealth = async (channelList) => {
    try {
      const healthPromises = channelList.map(async (channel) => {
        try {
          const health = await api.getChannelHealth(channel.id);
          return { [channel.id]: health.data };
        } catch (error) {
          console.warn(`Health check failed for ${channel.id}:`, error);
          return { [channel.id]: { healthy: false, error: error.message } };
        }
      });
      
      const healthResults = await Promise.all(healthPromises);
      const healthMap = healthResults.reduce((acc, result) => ({ ...acc, ...result }), {});
      setChannelHealth(healthMap);
      console.log('💚 Loaded channel health:', healthMap);
    } catch (error) {
      console.error('Error loading channel health:', error);
    }
  };

  const handleSettings = (channel) => {
    setSelectedChannel(channel);
    setShowSettings(true);
  };

  const getStatusInfo = (channel) => {
    if (channel.status?.usingFallback) {
      return {
        type: 'warning',
        text: 'Using fallback image'
      };
    }
    if (channel.status?.lastError) {
      return {
        type: 'error',
        text: 'Error occurred'
      };
    }
    return {
      type: 'success',
      text: 'Active'
    };
  };

  if (loading) {
    return (
      <div className="loading">
        <div className="loading-spinner"></div>
        <span>Loading channels...</span>
      </div>
    );
  }

  return (
    <div className="channels">
      <div className="channels-header">
        <div>
          <h1>Channels</h1>
          <p className="text-tertiary">
            Manage channel configurations and settings
            {isConnected && <span className="connection-status"> • Live updates enabled</span>}
            {apiVersion && <span className="api-version"> • API v{apiVersion}</span>}
          </p>
        </div>
        <div className="header-actions">
          {supportsPluginSystem() && (
            <button className="btn btn-secondary" onClick={loadManifest}>
              <Info size={18} />
              Load Manifest
            </button>
          )}
          <button className="btn btn-primary" onClick={refreshChannels}>
            <RefreshCw size={18} />
            Refresh
          </button>
        </div>
      </div>


      {channels.length > 0 ? (
        <div className="channels-grid">
          {channels.map((channel) => {
            const status = getStatusInfo(channel);
            const health = channelHealth[channel.id];
            const manifestData = manifest.find(m => m.id === channel.id);
            
            return (
              <div key={channel.id} className="channel-card">
                <div className="channel-card-header">
                  <div className="channel-info">
                    <h3>
                      {channel.name}
                      {supportsV21() && manifestData?.schemaVersion === '2.1' && (
                        <span className="v21-badge">v2.1</span>
                      )}
                    </h3>
                    <div className="channel-id">ID: {channel.id}</div>
                    <p className="text-tertiary">{channel.description}</p>
                  </div>
                  <div className="status-indicators">
                    <div className={`status-indicator status-${status.type}`}>
                      {status.text}
                    </div>
                    {supportsChannelHealth() && health && (
                      <div className={`health-indicator ${health.healthy ? 'healthy' : 'unhealthy'}`}>
                        <Heart size={16} />
                        {health.healthy ? 'Healthy' : 'Issues'}
                      </div>
                    )}
                  </div>
                </div>

                <div className="channel-card-body">
                  <div className="channel-details">
                    {channel.version && (
                    <div className="detail-item">
                      <span>Version:</span>
                      <span>{channel.version || 'Unknown'}</span>
                    </div>
                    )}
                    {/* <div className="detail-item">
                      <span>Settings Type:</span>
                      <span className="settings-type">
                        {channel.settingsType || 'simple'}
                      </span>
                    </div> */}
                    {supportsV21() && manifestData && (
                      <>
                        {manifestData.hasUI && (
                          <div className="detail-item">
                            <span>UI Components:</span>
                            <span className="ui-badge">
                              {manifestData.ui?.length || 0} components
                            </span>
                          </div>
                        )}
                        {manifestData.permissions && (
                          <div className="detail-item">
                            <span>Permissions:</span>
                            <span className="permissions">
                              {manifestData.permissions.join(', ')}
                            </span>
                          </div>
                        )}
                      </>
                    )}
                    {channel.status?.lastUpdate && (
                      <div className="detail-item">
                        <span>Last Update:</span>
                        <span className="last-update">
                          {new Date(channel.status.lastUpdate).toLocaleString()}
                        </span>
                      </div>
                    )}
                  </div>

                  {channel.status?.lastError && (
                    <div className="error-message">
                      <AlertCircle size={16} />
                      <span>{channel.status.lastError}</span>
                    </div>
                  )}
                </div>

                <div className="channel-card-footer">
                  {/* <button
                    className="btn btn-sm"
                    onClick={() => handleTestImage(channel.id)}
                  >
                    <Image size={16} />
                    Test Image
                  </button>
                  
                  {supportsChannelTesting() && (
                    <button
                      className="btn btn-sm btn-secondary"
                      onClick={() => testChannel(channel.id)}
                    >
                      <TestTube size={16} />
                      Test Channel
                    </button>
                  )}
                  
                  {supportsChannelHealth() && (
                    <button
                      className="btn btn-sm btn-tertiary"
                      onClick={() => refreshChannelHealth(channel.id)}
                    >
                      <Heart size={16} />
                      Health Check
                    </button>
                  )} */}
                  
                  <button
                    className="btn btn-sm btn-accent"
                    onClick={() => handleSettings(channel)}
                  >
                    <Settings size={16} />
                    Settings
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="empty-state">
          <h3>No channels available</h3>
          <p className="text-tertiary">
            No channels were discovered. Make sure channels are properly installed in the channels directory.
          </p>
          <button className="btn btn-primary" onClick={refreshChannels}>
            <RefreshCw size={18} />
            Refresh Channels
          </button>
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
      
      <DebugPanel />
    </div>
  );
};

export default Channels;
