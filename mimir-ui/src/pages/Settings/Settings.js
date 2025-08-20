import React, { useState, useEffect, useCallback } from 'react';
import { Settings as SettingsIcon, Monitor, RefreshCw, Square, Volume2, VolumeX } from 'lucide-react';
import { api } from '../../services/api';
import { useWebSocket } from '../../hooks/useWebSocket';
import { logger } from '../../utils/logger';
import './Settings.css';

const Settings = () => {
  const [displayStatus, setDisplayStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  
  // Console verbosity settings
  const [consoleSettings, setConsoleSettings] = useState({
    verbosity: localStorage.getItem('mimir-console-verbosity') || 'normal',
    showWebSocketEvents: localStorage.getItem('mimir-show-websocket-events') !== 'false',
    showAPIRequests: localStorage.getItem('mimir-show-api-requests') !== 'false',
    showSceneEvents: localStorage.getItem('mimir-show-scene-events') !== 'false',
    showDisplayEvents: localStorage.getItem('mimir-show-display-events') !== 'false'
  });

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

  const handleRefreshImage = async () => {
    try {
      await api.refreshDisplayImage();
      await loadDisplayStatus();
    } catch (error) {
      console.error('Error refreshing display image:', error);
    }
  };

  // Console verbosity handlers
  const handleVerbosityChange = (setting, value) => {
    const newSettings = { ...consoleSettings, [setting]: value };
    setConsoleSettings(newSettings);
    
    // Store in localStorage with proper kebab-case
    const kebabKey = setting.replace(/([A-Z])/g, '-$1').toLowerCase();
    localStorage.setItem(`mimir-${kebabKey}`, value.toString());
    
    // Apply console verbosity settings globally
    window.mimirConsoleSettings = newSettings;
    
    console.log(`Console setting changed: ${setting} = ${value}`);
  };

  const handleVerbosityLevelChange = (level) => {
    const newSettings = { ...consoleSettings, verbosity: level };
    setConsoleSettings(newSettings);
    localStorage.setItem('mimir-console-verbosity', level);
    window.mimirConsoleSettings = newSettings;
    
    console.log(`Console verbosity level changed to: ${level}`);
  };

  const clearAllLogs = () => {
    console.clear();
    logger.info('Console cleared by user');
  };

  const testLogging = () => {
    logger.debug('This is a debug message');
    logger.info('This is an info message');
    logger.warning('This is a warning message');
    logger.error('This is an error message');
    logger.websocket('WebSocket test message');
    logger.api('API test message');
    logger.scene('Scene test message');
    logger.display('Display test message');
  };

  // Set global console settings on mount
  useEffect(() => {
    window.mimirConsoleSettings = consoleSettings;
  }, [consoleSettings]);

  if (loading) {
    return (
      <div className="loading">
        <div className="loading-spinner"></div>
        <span>Loading settings...</span>
      </div>
    );
  }

  return (
    <div className="settings">
      <div className="settings-header">
        <div className="header-content">
          <div className="header-icon">
            <SettingsIcon size={32} />
          </div>
          <div>
            <h1>Settings</h1>
            <p className="text-tertiary">Configure display settings and console verbosity</p>
          </div>
        </div>
      </div>

      <div className="settings-grid">
        {/* Display Control Section */}
        <div className="settings-card">
          <div className="card-header">
            <div className="flex items-center gap-sm">
              <Monitor size={20} />
              <h3 className="card-title">Display Control</h3>
            </div>
            <div className="connection-status">
              <span className={`status-badge ${isConnected ? 'status-connected' : 'status-disconnected'}`}>
                {isConnected ? 'Connected' : 'Disconnected'}
              </span>
            </div>
          </div>
          
          <div className="card-body">
            {displayStatus && (
              <div className="display-status">
                <div className="status-row">
                  <span>Hardware:</span>
                  <span className={`status-indicator ${displayStatus.hardware?.available ? 'status-success' : 'status-error'}`}>
                    {displayStatus.hardware?.type || 'Unknown'}
                  </span>
                </div>
                <div className="status-row">
                  <span>Resolution:</span>
                  <span>{displayStatus.resolution ? displayStatus.resolution.join(' × ') : 'Unknown'}</span>
                </div>
                <div className="status-row">
                  <span>Current Scene:</span>
                  <span>{displayStatus.currentScene || 'None'}</span>
                </div>
                {displayStatus.currentImage && (
                  <>
                    <div className="status-row">
                      <span>Last Update:</span>
                      <span>{new Date(displayStatus.currentImage.uploadedAt).toLocaleString()}</span>
                    </div>
                    <div className="status-row">
                      <span>Image Size:</span>
                      <span>{displayStatus.currentImage.size} bytes</span>
                    </div>
                  </>
                )}
              </div>
            )}
            
            <div className="display-actions">
              <button className="btn btn-warning" onClick={handleClearDisplay}>
                <Square size={16} />
                Clear Display
              </button>
              <button className="btn btn-primary" onClick={handleRefreshImage}>
                <RefreshCw size={16} />
                Refresh Image
              </button>
            </div>
          </div>
        </div>

        {/* Console Verbosity Settings */}
        <div className="settings-card">
          <div className="card-header">
            <div className="flex items-center gap-sm">
              <Volume2 size={20} />
              <h3 className="card-title">Console Verbosity</h3>
            </div>
          </div>
          
          <div className="card-body">
            <div className="form-section">
              <div className="form-group">
                <label>Verbosity Level</label>
                <select 
                  value={consoleSettings.verbosity} 
                  onChange={(e) => handleVerbosityLevelChange(e.target.value)}
                  className="form-control"
                >
                  <option value="silent">Silent - No debug output</option>
                  <option value="error">Error - Only errors</option>
                  <option value="warning">Warning - Errors and warnings</option>
                  <option value="normal">Normal - Standard output</option>
                  <option value="verbose">Verbose - Detailed logging</option>
                  <option value="debug">Debug - All output</option>
                </select>
                <small className="form-help">
                  Controls the overall amount of console output
                </small>
              </div>
            </div>

            <div className="form-section">
              <h4>Event Categories</h4>
              <div className="checkbox-group">
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={consoleSettings.showWebSocketEvents}
                    onChange={(e) => handleVerbosityChange('showWebSocketEvents', e.target.checked)}
                  />
                  WebSocket Events
                </label>
                
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={consoleSettings.showAPIRequests}
                    onChange={(e) => handleVerbosityChange('showAPIRequests', e.target.checked)}
                  />
                  API Requests
                </label>
                
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={consoleSettings.showSceneEvents}
                    onChange={(e) => handleVerbosityChange('showSceneEvents', e.target.checked)}
                  />
                  Scene Events
                </label>
                
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={consoleSettings.showDisplayEvents}
                    onChange={(e) => handleVerbosityChange('showDisplayEvents', e.target.checked)}
                  />
                  Display Events
                </label>
              </div>
            </div>

            <div className="console-actions">
              <button className="btn btn-secondary" onClick={clearAllLogs}>
                <VolumeX size={16} />
                Clear Console
              </button>
              <button 
                className="btn btn-outline" 
                onClick={testLogging}
              >
                Test Logging
              </button>
            </div>
          </div>
        </div>

        {/* System Information */}
        <div className="settings-card">
          <div className="card-header">
            <div className="flex items-center gap-sm">
              <SettingsIcon size={20} />
              <h3 className="card-title">System Information</h3>
            </div>
          </div>
          
          <div className="card-body">
            <div className="system-info">
              <div className="info-row">
                <span>User Agent:</span>
                <span className="info-value">{navigator.userAgent.split(' ')[0]}</span>
              </div>
              <div className="info-row">
                <span>Platform:</span>
                <span className="info-value">{navigator.platform}</span>
              </div>
              <div className="info-row">
                <span>Language:</span>
                <span className="info-value">{navigator.language}</span>
              </div>
              <div className="info-row">
                <span>Viewport:</span>
                <span className="info-value">{window.innerWidth} × {window.innerHeight}</span>
              </div>
              <div className="info-row">
                <span>Local Storage:</span>
                <span className="info-value">
                  {Object.keys(localStorage).filter(key => key.startsWith('mimir-')).length} settings stored
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Settings;
