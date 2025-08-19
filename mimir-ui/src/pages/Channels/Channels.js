import React, { useState, useEffect } from 'react';
import { Settings, RefreshCw, Image, AlertCircle } from 'lucide-react';
import { api } from '../../services/api';
import ChannelSettings from './ChannelSettings';
import './Channels.css';

const Channels = () => {
  const [channels, setChannels] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showSettings, setShowSettings] = useState(false);
  const [selectedChannel, setSelectedChannel] = useState(null);

  useEffect(() => {
    loadChannels();
  }, []);

  const loadChannels = async () => {
    try {
      const response = await api.getChannels();
      setChannels(response.data.channels || []);
    } catch (error) {
      console.error('Error loading channels:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSettings = (channel) => {
    setSelectedChannel(channel);
    setShowSettings(true);
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
          <p className="text-tertiary">Manage channel configurations and settings</p>
        </div>
        <button className="btn btn-primary" onClick={loadChannels}>
          <RefreshCw size={18} />
          Refresh
        </button>
      </div>

      {channels.length > 0 ? (
        <div className="channels-grid">
          {channels.map((channel) => {
            const status = getStatusInfo(channel);
            return (
              <div key={channel.id} className="channel-card">
                <div className="channel-card-header">
                  <div className="channel-info">
                    <h3>{channel.name}</h3>
                    <p className="text-tertiary">{channel.description}</p>
                  </div>
                  <div className={`status-indicator status-${status.type}`}>
                    {status.text}
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
                  <button
                    className="btn btn-sm"
                    onClick={() => handleTestImage(channel.id)}
                  >
                    <Image size={16} />
                    Test Image
                  </button>
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
          <button className="btn btn-primary" onClick={loadChannels}>
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
    </div>
  );
};

export default Channels;
