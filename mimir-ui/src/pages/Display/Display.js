import React, { useState, useEffect, useCallback } from 'react';
import { Monitor, RefreshCw, Square, Image } from 'lucide-react';
import { api } from '../../services/api';
import { useWebSocket } from '../../hooks/useWebSocket';
import './Display.css';

const Display = () => {
  const [displayStatus, setDisplayStatus] = useState(null);
  const [loading, setLoading] = useState(true);

  // WebSocket integration for real-time display updates
  const { isConnected } = useWebSocket();

  const loadDisplayStatus = useCallback(async () => {
    try {
      const response = await api.getDisplayStatus();
      setDisplayStatus(response.data);
    } catch (error) {
      console.error('Error loading display status:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDisplayStatus();
  }, [loadDisplayStatus]);

  // Listen for display-related events
  useEffect(() => {
    const handleDisplayUpdate = (event) => {
      if (event.data?.type === 'display_update') {
        // Reload display status when display changes
        loadDisplayStatus();
      } else if (event.data?.type === 'scene_activated' || event.data?.type === 'scene_deactivated') {
        // Reload display status when scenes change
        loadDisplayStatus();
      }
    };

    window.addEventListener('websocket-message', handleDisplayUpdate);
    return () => window.removeEventListener('websocket-message', handleDisplayUpdate);
  }, [loadDisplayStatus]);

  const handleClearDisplay = async () => {
    try {
      await api.clearDisplay();
      await loadDisplayStatus();
    } catch (error) {
      console.error('Error clearing display:', error);
    }
  };

  const formatImageSize = (width, height) => {
    return `${width} × ${height}`;
  };

  if (loading) {
    return (
      <div className="loading">
        <div className="loading-spinner"></div>
        <span>Loading display status...</span>
      </div>
    );
  }

  return (
    <div className="display">
      <div className="display-header">
        <div>
          <h1>Display Control</h1>
          <p className="text-tertiary">
            Monitor and control your e-ink display hardware
            {isConnected && <span className="connection-status"> • Live updates enabled</span>}
          </p>
        </div>
        <button className="btn btn-primary" onClick={loadDisplayStatus}>
          <RefreshCw size={18} />
          Refresh
        </button>
      </div>

      <div className="display-grid">
        {/* Hardware Status */}
        <div className="display-card">
          <div className="card-header">
            <div className="flex items-center gap-sm">
              <Monitor size={20} />
              <h3>Hardware Status</h3>
            </div>
          </div>
          <div className="card-body">
            {displayStatus?.hardware ? (
              <div className="hardware-info">
                <div className="info-row">
                  <span>Type:</span>
                  <span className="hardware-type">{displayStatus.hardware.type}</span>
                </div>
                <div className="info-row">
                  <span>Available:</span>
                  <span className={`status-indicator ${
                    displayStatus.hardware.available ? 'status-success' : 'status-error'
                  }`}>
                    {displayStatus.hardware.available ? 'Yes' : 'No'}
                  </span>
                </div>
                <div className="info-row">
                  <span>Resolution:</span>
                  <span className="resolution">
                    {displayStatus.hardware.resolution ? 
                      formatImageSize(...displayStatus.hardware.resolution) : 
                      'Unknown'
                    }
                  </span>
                </div>
                <div className="info-row">
                  <span>Current Resolution:</span>
                  <span className="resolution">
                    {displayStatus.resolution ? 
                      formatImageSize(...displayStatus.resolution) : 
                      'Unknown'
                    }
                  </span>
                </div>
              </div>
            ) : (
              <p className="text-tertiary">No hardware information available</p>
            )}
          </div>
        </div>

        {/* Current Scene */}
        <div className="display-card">
          <div className="card-header">
            <div className="flex items-center gap-sm">
              <Image size={20} />
              <h3>Current Scene</h3>
            </div>
          </div>
          <div className="card-body">
            {displayStatus?.currentScene ? (
              <div className="scene-info">
                <div className="info-row">
                  <span>Active Scene:</span>
                  <span className="scene-name">{displayStatus.currentScene}</span>
                </div>
                {displayStatus.currentImage && (
                  <>
                    <div className="info-row">
                      <span>Image:</span>
                      <span className="image-name">{displayStatus.currentImage.filename}</span>
                    </div>
                    <div className="info-row">
                      <span>Dimensions:</span>
                      <span className="image-dimensions">
                        {formatImageSize(displayStatus.currentImage.width, displayStatus.currentImage.height)}
                      </span>
                    </div>
                    <div className="info-row">
                      <span>Last Updated:</span>
                      <span className="last-update">
                        {new Date(displayStatus.currentImage.uploadedAt).toLocaleString()}
                      </span>
                    </div>
                  </>
                )}
              </div>
            ) : (
              <div className="no-scene">
                <p className="text-tertiary">No scene currently active</p>
              </div>
            )}
          </div>
        </div>

        {/* Current Image Preview */}
        {displayStatus?.currentImage && (
          <div className="display-card image-preview-card">
            <div className="card-header">
              <h3>Current Image</h3>
            </div>
            <div className="card-body">
              <div className="image-preview">
                <img 
                  src={`http://172.31.79.107:5000${displayStatus.currentImage.path}${displayStatus.currentImage.filename}`}
                  alt="Current display content"
                  className="preview-image"
                  onError={(e) => {
                    e.target.style.display = 'none';
                    e.target.nextSibling.style.display = 'block';
                  }}
                />
                <div className="image-error" style={{ display: 'none' }}>
                  <p>Image preview not available</p>
                </div>
              </div>
              <div className="image-details">
                <p className="image-path">{displayStatus.currentImage.path}{displayStatus.currentImage.filename}</p>
              </div>
            </div>
          </div>
        )}

        {/* Display Controls */}
        <div className="display-card">
          <div className="card-header">
            <h3>Display Controls</h3>
          </div>
          <div className="card-body">
            <div className="control-buttons">
              <button 
                className="btn btn-warning btn-lg"
                onClick={handleClearDisplay}
              >
                <Square size={18} />
                Clear Display
              </button>
            </div>
            <p className="control-description">
              Clear the display to remove all current content. The display will show a blank screen until a new scene is activated.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Display;
