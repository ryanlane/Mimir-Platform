import React, { useState, useEffect, useCallback } from 'react';
import { Settings as SettingsIcon, Monitor, RefreshCw, Square, Volume2, VolumeX, AlertTriangle, Database } from 'lucide-react';
import { api } from '../../services/api';
import { useWebSocket } from '../../hooks/useWebSocket';
import { logger } from '../../utils/logger';
import './Settings.css';
import WebSocketStatus from '../../components/WebSocketStatus/WebSocketStatus';
import DisplayClientManager from '../../components/Settings/DisplayClientManager';
import MobileConnectionGuide from '../../components/MobileConnectionGuide/MobileConnectionGuide';

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
  const [apiBaseUrl, setApiBaseUrl] = useState(localStorage.getItem('mimir-api-base-url') || '');
  const [wsBaseUrl, setWsBaseUrl] = useState(localStorage.getItem('mimir-websocket-url') || '');
  const [apiConnectionStatus, setApiConnectionStatus] = useState(null);
  const [testingApi, setTestingApi] = useState(false);
  const [testingWs, setTestingWs] = useState(false);

  // Admin operations state
  const [showResetConfirmation, setShowResetConfirmation] = useState(false);
  const [resetStep, setResetStep] = useState(0); // 0: initial, 1: warning, 2: final confirmation
  const [resetLoading, setResetLoading] = useState(false);
  const [resetResults, setResetResults] = useState(null);
  const [orphanedChannels, setOrphanedChannels] = useState(null);
  const [checkingOrphaned, setCheckingOrphaned] = useState(false);

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

  // Connection configuration handlers
  const handleApiUrlChange = (url) => {
    setApiBaseUrl(url);
    if (url) {
      localStorage.setItem('mimir-api-base-url', url);
    } else {
      localStorage.removeItem('mimir-api-base-url');
    }
    // Clear previous test results
    setApiConnectionStatus(null);
  };

  const handleWsUrlChange = (url) => {
    setWsBaseUrl(url);
    if (url) {
      localStorage.setItem('mimir-websocket-url', url);
    } else {
      localStorage.removeItem('mimir-websocket-url');
    }
  };

  const testWebSocketConnection = () => {
    if (!wsBaseUrl) {
      return;
    }

    setTestingWs(true);
    try {
      const testWs = new WebSocket(`${wsBaseUrl}/ws`);
      
      testWs.onopen = () => {
        setApiConnectionStatus({ success: true, message: 'WebSocket connection successful!' });
        testWs.close();
        setTestingWs(false);
      };
      
      testWs.onerror = () => {
        setApiConnectionStatus({ success: false, error: 'WebSocket connection failed' });
        setTestingWs(false);
      };
      
      testWs.onclose = () => {
        setTestingWs(false);
      };
      
      // Timeout after 5 seconds
      setTimeout(() => {
        if (testWs.readyState === WebSocket.CONNECTING) {
          testWs.close();
          setApiConnectionStatus({ success: false, error: 'WebSocket connection timeout' });
          setTestingWs(false);
        }
      }, 5000);
    } catch (error) {
      setApiConnectionStatus({ success: false, error: `WebSocket test failed: ${error.message}` });
      setTestingWs(false);
    }
  };

  const getCurrentUrls = () => {
    const apiUrl = apiBaseUrl || 'Auto-detected';
    const wsUrl = wsBaseUrl || 'Auto-detected';
    return { apiUrl, wsUrl };
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

  useEffect(() => {
    window.mimirApiBaseUrl = apiBaseUrl;
    localStorage.setItem('mimir-api-base-url', apiBaseUrl);
  }, [apiBaseUrl]);

  const testApiConnection = useCallback(async () => {
    setTestingApi(true);
    setApiConnectionStatus(null);
    try {
      const url = `${apiBaseUrl.replace(/\/$/, '')}/api/health`;
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        if (data.status === 'ok' && data.message === 'Mimir API service is healthy') {
          setApiConnectionStatus('success');
        } else {
          setApiConnectionStatus('error');
        }
      } else {
        setApiConnectionStatus('error');
      }
    } catch {
      setApiConnectionStatus('error');
    } finally {
      setTestingApi(false);
    }
  }, [apiBaseUrl]);

  useEffect(() => {
    if (apiBaseUrl) {
      testApiConnection();
    }
  }, [apiBaseUrl, testApiConnection]);

  // Admin Operations Handlers
  const handleCheckOrphanedChannels = async () => {
    setCheckingOrphaned(true);
    try {
      const response = await api.getOrphanedChannels();
      setOrphanedChannels(response.data);
    } catch (error) {
      console.error('Error checking orphaned channels:', error);
      setOrphanedChannels({ error: 'Failed to check orphaned channels' });
    } finally {
      setCheckingOrphaned(false);
    }
  };

  const handleResetChannelsDatabase = async () => {
    if (resetStep === 0) {
      // First step: show initial warning
      setShowResetConfirmation(true);
      setResetStep(1);
      return;
    }

    if (resetStep === 1) {
      // Second step: final confirmation
      setResetStep(2);
      return;
    }

    // Final step: actually perform the reset
    setResetLoading(true);
    try {
      const response = await api.resetChannelsDatabase();
      setResetResults(response.data);
      setResetStep(0);
      setShowResetConfirmation(false);
      
      // Refresh any cached data
      if (orphanedChannels) {
        await handleCheckOrphanedChannels();
      }
      
      console.log('✅ Channels database reset successfully:', response.data);
    } catch (error) {
      console.error('❌ Error resetting channels database:', error);
      setResetResults({ 
        error: 'Failed to reset channels database', 
        details: error.response?.data?.detail || error.message 
      });
    } finally {
      setResetLoading(false);
    }
  };

  const handleCancelReset = () => {
    setShowResetConfirmation(false);
    setResetStep(0);
  };

  const handleDismissResults = () => {
    setResetResults(null);
  };

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
      {/* WebSocket Status Component */}
      <WebSocketStatus />
      <DisplayClientManager />

      {/* Mobile Connection Guide */}
      <MobileConnectionGuide />

      {/* Connection Configuration */}
      <div className="settings-card">
        <div className="card-header">
          <div className="flex items-center gap-sm">
            <Database size={20} />
            <h3 className="card-title">Connection Configuration</h3>
          </div>
        </div>
        
        <div className="card-body">
          <p className="text-tertiary" style={{ marginBottom: '1rem' }}>
            Configure API and WebSocket connections. Leave blank to use auto-detection based on current page URL.
          </p>
          
          <div className="connection-config">
            <div className="config-group">
              <label htmlFor="api-url">API Base URL:</label>
              <div className="url-input-group">
                <input
                  id="api-url"
                  type="url"
                  value={apiBaseUrl}
                  onChange={(e) => handleApiUrlChange(e.target.value)}
                  placeholder="e.g., http://192.168.1.100:5000 (leave blank for auto-detect)"
                  className="url-input"
                />
                <button 
                  className="btn btn-outline" 
                  type="button" 
                  onClick={testApiConnection} 
                  disabled={testingApi}
                >
                  {testingApi ? 'Testing...' : 'Test'}
                </button>
              </div>
              <small className="input-help">
                Current: {getCurrentUrls().apiUrl}
              </small>
            </div>

            <div className="config-group">
              <label htmlFor="ws-url">WebSocket Base URL:</label>
              <div className="url-input-group">
                <input
                  id="ws-url"
                  type="url"
                  value={wsBaseUrl}
                  onChange={(e) => handleWsUrlChange(e.target.value)}
                  placeholder="e.g., ws://192.168.1.100:5000 (leave blank for auto-detect)"
                  className="url-input"
                />
                <button 
                  className="btn btn-outline" 
                  type="button" 
                  onClick={testWebSocketConnection} 
                  disabled={testingWs}
                >
                  {testingWs ? 'Testing...' : 'Test'}
                </button>
              </div>
              <small className="input-help">
                Current: {getCurrentUrls().wsUrl}
              </small>
            </div>

            {apiConnectionStatus && (
              <div className={`connection-status-message ${apiConnectionStatus.success ? 'success' : 'error'}`}>
                {apiConnectionStatus.message || apiConnectionStatus.error}
              </div>
            )}
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

        {/* Admin Operations */}
        <div className="settings-card">
          <div className="card-header">
            <div className="flex items-center gap-sm">
              <Database size={20} />
              <h3 className="card-title">Admin Operations</h3>
            </div>
            <div className="warning-badge">
              <AlertTriangle size={16} />
              <span>Destructive Operations</span>
            </div>
          </div>
          
          <div className="card-body">
            <div className="admin-section">
              <div className="admin-operation">
                <div className="operation-info">
                  <h4>Check Orphaned Channels</h4>
                  <p className="operation-description">
                    Find channels in the database that no longer exist in the filesystem.
                  </p>
                </div>
                <button 
                  className="btn btn-secondary"
                  onClick={handleCheckOrphanedChannels}
                  disabled={checkingOrphaned}
                >
                  {checkingOrphaned ? 'Checking...' : 'Check Orphaned'}
                </button>
              </div>

              {orphanedChannels && (
                <div className="orphaned-results">
                  {orphanedChannels.error ? (
                    <div className="error-message">
                      <AlertTriangle size={16} />
                      <span>{orphanedChannels.error}</span>
                    </div>
                  ) : (
                    <div className="orphaned-channels">
                      <h5>Orphaned Channels Found: {orphanedChannels.length}</h5>
                      {orphanedChannels.length > 0 ? (
                        <ul className="orphaned-list">
                          {orphanedChannels.map((channel, index) => (
                            <li key={index} className="orphaned-item">
                              <strong>{channel.id}</strong>
                              {channel.name && <span> - {channel.name}</span>}
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p className="no-orphaned">✅ No orphaned channels found</p>
                      )}
                    </div>
                  )}
                </div>
              )}

              <div className="admin-operation danger-operation">
                <div className="operation-info">
                  <h4>Reset Channels Database</h4>
                  <p className="operation-description">
                    <strong>⚠️ DESTRUCTIVE:</strong> Clears the channels database and rebuilds it from the filesystem. 
                    This will resolve channel ID mismatches but may break scene assignments.
                  </p>
                </div>
                <button 
                  className="btn btn-danger"
                  onClick={handleResetChannelsDatabase}
                  disabled={resetLoading}
                >
                  {resetLoading ? 'Resetting...' : 'Reset Database'}
                </button>
              </div>

              {/* Reset Confirmation Modal */}
              {showResetConfirmation && (
                <div className="modal-overlay">
                  <div className="modal reset-confirmation-modal">
                    <div className="modal-header">
                      <h3>
                        <AlertTriangle size={24} />
                        {resetStep === 1 ? 'Confirm Database Reset' : 'Final Confirmation Required'}
                      </h3>
                    </div>
                    
                    <div className="modal-body">
                      {resetStep === 1 ? (
                        <div className="warning-content">
                          <div className="warning-icon">
                            <AlertTriangle size={48} />
                          </div>
                          <div className="warning-text">
                            <h4>This operation will:</h4>
                            <ul className="warning-list">
                              <li>🗑️ Delete ALL channel data from the database</li>
                              <li>📂 Rebuild from current filesystem channels</li>
                              <li>🔄 Update channel IDs to match config.json files</li>
                              <li>⚠️ May break existing scene assignments</li>
                            </ul>
                            <p><strong>This action cannot be undone.</strong></p>
                          </div>
                        </div>
                      ) : (
                        <div className="final-confirmation">
                          <p className="final-warning">
                            <strong>Are you absolutely sure?</strong>
                          </p>
                          <p>Type "RESET" to confirm:</p>
                          <input 
                            type="text" 
                            id="reset-confirmation-input"
                            placeholder="Type RESET here"
                            className="confirmation-input"
                          />
                        </div>
                      )}
                    </div>
                    
                    <div className="modal-footer">
                      <button className="btn btn-secondary" onClick={handleCancelReset}>
                        Cancel
                      </button>
                      {resetStep === 1 ? (
                        <button className="btn btn-warning" onClick={handleResetChannelsDatabase}>
                          I Understand, Continue
                        </button>
                      ) : (
                        <button 
                          className="btn btn-danger"
                          onClick={() => {
                            const input = document.getElementById('reset-confirmation-input');
                            if (input?.value === 'RESET') {
                              handleResetChannelsDatabase();
                            } else {
                              alert('Please type "RESET" to confirm');
                            }
                          }}
                        >
                          Reset Database Now
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {/* Reset Results */}
              {resetResults && (
                <div className="reset-results">
                  <div className="results-header">
                    <h4>Reset Results</h4>
                    <button className="btn btn-sm btn-secondary" onClick={handleDismissResults}>
                      Dismiss
                    </button>
                  </div>
                  
                  {resetResults.error ? (
                    <div className="error-message">
                      <AlertTriangle size={16} />
                      <div>
                        <strong>Error:</strong> {resetResults.error}
                        {resetResults.details && <p>{resetResults.details}</p>}
                      </div>
                    </div>
                  ) : (
                    <div className="success-results">
                      <div className="success-summary">
                        <h5>✅ Database Reset Successful</h5>
                        <div className="results-stats">
                          <div className="stat-item">
                            <span className="stat-number">{resetResults.removed?.length || 0}</span>
                            <span className="stat-label">Removed</span>
                          </div>
                          <div className="stat-item">
                            <span className="stat-number">{resetResults.added?.length || 0}</span>
                            <span className="stat-label">Added</span>
                          </div>
                          <div className="stat-item">
                            <span className="stat-number">{resetResults.kept?.length || 0}</span>
                            <span className="stat-label">Kept</span>
                          </div>
                        </div>
                      </div>
                      
                      {resetResults.scene_warnings && resetResults.scene_warnings.length > 0 && (
                        <div className="scene-warnings">
                          <h6>⚠️ Scene Assignment Warnings</h6>
                          <ul>
                            {resetResults.scene_warnings.map((warning, index) => (
                              <li key={index}>{warning}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
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
