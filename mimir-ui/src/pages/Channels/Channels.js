import React, { useState, useEffect, useCallback } from 'react';
import { Settings, RefreshCw, Image, AlertCircle, TestTube, Heart, Info } from 'lucide-react';
import { api } from '../../services/api';
import { useWebSocket } from '../../hooks/useWebSocket';
import { useFeatureDetection } from '../../hooks/useFeatureDetection';
import featureDetection from '../../services/featureDetection';
import ChannelSettings from './ChannelSettings';
import SubChannelManager from './SubChannelManager';
import DebugPanel from '../../components/DebugPanel/DebugPanel';
import './Channels.css';

// Global cache for channels data to prevent excessive API requests
let channelsCache = null;
let channelsCacheTime = null;
const CHANNELS_CACHE_TIMEOUT = 30 * 1000; // 30 seconds

const Channels = () => {
  const [channels, setChannels] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showSettings, setShowSettings] = useState(false);
  const [selectedChannel, setSelectedChannel] = useState(null);

  // v2.1 Feature detection and new state
  const { 
    supportsV21, 
    supportsChannelHealth, 
    supportsChannelTesting, 
    supportsPluginSystem,
    apiVersion
  } = useFeatureDetection();
  
  const [channelHealth, setChannelHealth] = useState({});
  const [testResults, setTestResults] = useState({});
  const [manifest, setManifest] = useState([]);

  // Sub-channel support (NEW)
  const [subChannelSupport, setSubChannelSupport] = useState({});
  const [subChannelCounts, setSubChannelCounts] = useState({});
  const [showSubChannelManager, setShowSubChannelManager] = useState(false);
  const [selectedChannelForSubChannels, setSelectedChannelForSubChannels] = useState(null);

  // WebSocket integration for real-time updates
  const { isConnected } = useWebSocket();

  // v2.1: Load channel manifest
  const loadManifest = useCallback(async () => {
    if (!featureDetection.supportsPluginSystem()) {
      return;
    }
    
    try {
      const response = await api.getChannelsManifest();
      setManifest(response.data || []);
      console.log('📋 Loaded channel manifest:', response.data);
    } catch (error) {
      console.error('Error loading channel manifest:', error);
    }
  }, []);

  // Load sub-channel support information
  const loadSubChannelSupport = useCallback(async () => {
    const supportInfo = {};
    const counts = {};
    
    for (const channel of channels) {
      try {
        // Check if channel supports sub-channels
        const configResponse = await api.getSubChannelConfig(channel.id);
        supportInfo[channel.id] = configResponse.data?.supports_subchannels || false;
        
        if (supportInfo[channel.id]) {
          // Get sub-channel count
          const subChannelsResponse = await api.getSubChannels(channel.id);
          counts[channel.id] = subChannelsResponse.data?.length || 0;
        }
      } catch (error) {
        // Channel doesn't support sub-channels or error occurred
        supportInfo[channel.id] = false;
        counts[channel.id] = 0;
      }
    }
    
    setSubChannelSupport(supportInfo);
    setSubChannelCounts(counts);
  }, [channels]);

  const loadChannels = useCallback(async () => {
    try {
      // Check cache first
      const now = Date.now();
      if (channelsCache && channelsCacheTime && (now - channelsCacheTime) < CHANNELS_CACHE_TIMEOUT) {
        console.log('🚀 Using cached channels data');
        setChannels(channelsCache);
        
        // Load health for cached channels if supported
        if (featureDetection.supportsChannelHealth()) {
          loadAllChannelHealth(channelsCache);
        }
        setLoading(false);
        return;
      }
      
      console.log('📡 Fetching fresh channels data');
      const response = await api.getChannels();
      const channelsData = response.data.channels || [];
      
      // Update cache
      channelsCache = channelsData;
      channelsCacheTime = now;
      
      setChannels(channelsData);
      
      // Load health for all channels if supported
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
    // Clear cache to force fresh data
    channelsCache = null;
    channelsCacheTime = null;
    setLoading(true);
    await loadChannels();
  }, [loadChannels]);

  useEffect(() => {
    const initializeChannels = async () => {
      await loadChannels();
      // Load v2.1 features if supported
      await loadManifest();
      // Load sub-channel support after channels are loaded
      if (channels.length > 0) {
        await loadSubChannelSupport();
      }
    };
    
    initializeChannels();
  }, [loadChannels, loadManifest, loadSubChannelSupport, channels.length]);
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

  // v2.1: Test a specific channel
  const testChannel = async (channelId) => {
    try {
      console.log(`🧪 Testing channel: ${channelId}`);
      const result = await api.testChannel(channelId);
      setTestResults(prev => ({ ...prev, [channelId]: result.data }));
      console.log(`✅ Test result for ${channelId}:`, result.data);
      
      // Refresh health after test
      if (supportsChannelHealth()) {
        const health = await api.getChannelHealth(channelId);
        setChannelHealth(prev => ({ ...prev, [channelId]: health.data }));
      }
    } catch (error) {
      console.error(`Error testing channel ${channelId}:`, error);
      setTestResults(prev => ({ 
        ...prev, 
        [channelId]: { 
          success: false, 
          error: error.message,
          timestamp: new Date().toISOString()
        }
      }));
    }
  };

  // v2.1: Refresh health for a specific channel
  const refreshChannelHealth = async (channelId) => {
    try {
      const health = await api.getChannelHealth(channelId);
      setChannelHealth(prev => ({ ...prev, [channelId]: health.data }));
      console.log(`💚 Refreshed health for ${channelId}:`, health.data);
    } catch (error) {
      console.error(`Error refreshing health for ${channelId}:`, error);
    }
  };

  const handleSettings = (channel) => {
    setSelectedChannel(channel);
    setShowSettings(true);
  };

  const handleManageSubChannels = (channel) => {
    setSelectedChannelForSubChannels(channel);
    setShowSubChannelManager(true);
  };

  const handleTestImage = async (channelId) => {
    try {
      await api.requestChannelImage(channelId, {
        resolution: [800, 600],
        orientation: 'landscape'
      });
      console.log('Test image requested successfully');
    } catch (error) {
      console.error('Error requesting test image:', error);
    }
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
            const testResult = testResults[channel.id];
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
                    <div className="detail-item">
                      <span>Version:</span>
                      <span>{channel.version || 'Unknown'}</span>
                    </div>
                    <div className="detail-item">
                      <span>Settings Type:</span>
                      <span className="settings-type">
                        {channel.settingsType || 'simple'}
                      </span>
                    </div>
                    {subChannelSupport[channel.id] && (
                      <div className="detail-item">
                        <span>Sub-Channels:</span>
                        <span className="subchannel-count">
                          {subChannelCounts[channel.id] || 0} configured
                        </span>
                      </div>
                    )}
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

                  {testResult && (
                    <div className={`test-result ${testResult.success ? 'success' : 'error'}`}>
                      <TestTube size={16} />
                      <span>
                        Test {testResult.success ? 'passed' : 'failed'}: {testResult.message || testResult.error}
                      </span>
                    </div>
                  )}
                </div>

                <div className="channel-card-footer">
                  <button
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
                  )}
                  
                  {subChannelSupport[channel.id] && (
                    <button
                      className="btn btn-sm btn-secondary"
                      onClick={() => handleManageSubChannels(channel)}
                    >
                      <Info size={16} />
                      Manage Sub-Channels
                    </button>
                  )}
                  
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

      {showSubChannelManager && selectedChannelForSubChannels && (
        <SubChannelManager
          channel={selectedChannelForSubChannels}
          onClose={() => {
            setShowSubChannelManager(false);
            setSelectedChannelForSubChannels(null);
            loadSubChannelSupport(); // Refresh sub-channel data
          }}
        />
      )}
      
      <DebugPanel />
    </div>
  );
};

export default Channels;
