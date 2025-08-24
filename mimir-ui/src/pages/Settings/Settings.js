import React, { useState, useEffect, useCallback } from 'react';
import { Settings as SettingsIcon, Volume2, VolumeX, Wifi } from 'lucide-react';
import { api } from '../../services/api';
import { logger } from '../../utils/logger';
import './Settings.css';
import WebSocketStatus from '../../components/WebSocketStatus/WebSocketStatus';
import MobileConnectionGuide from '../../components/MobileConnectionGuide/MobileConnectionGuide';
import AdminOperations from '../../components/AdminOperations/AdminOperations';

const Settings = () => {
  const [loading, setLoading] = useState(true);
  
  // Console verbosity settings
  const [consoleSettings, setConsoleSettings] = useState({
    verbosity: localStorage.getItem('mimir-console-verbosity') || 'normal',
    showWebSocketEvents: localStorage.getItem('mimir-show-websocket-events') !== 'false',
    showAPIRequests: localStorage.getItem('mimir-show-api-requests') !== 'false',
    showSceneEvents: localStorage.getItem('mimir-show-scene-events') !== 'false',
    showDisplayEvents: localStorage.getItem('mimir-show-display-events') !== 'false'
  });

  const [apiBaseUrl, setApiBaseUrl] = useState(localStorage.getItem('mimir-api-base-url') || '');
  const [wsBaseUrl, setWsBaseUrl] = useState(localStorage.getItem('mimir-websocket-url') || '');
  const [apiConnectionStatus, setApiConnectionStatus] = useState(null);
  const [testingApi, setTestingApi] = useState(false);
  const [testingWs, setTestingWs] = useState(false);

  // Remove display status loading since Display Control section is removed
  useEffect(() => {
    setLoading(false);
  }, []);

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
    if (!wsBaseUrl || !wsBaseUrl.trim()) {
      setApiConnectionStatus({ success: false, error: 'WebSocket URL is required' });
      return;
    }

    setTestingWs(true);
    console.log('Testing WebSocket connection to:', `${wsBaseUrl}/ws`);
    
    try {
      const testWs = new WebSocket(`${wsBaseUrl}/ws`);
      
      testWs.onopen = () => {
        setApiConnectionStatus({ success: true, message: 'WebSocket connection successful!' });
        console.log('WebSocket connection test successful');
        testWs.close();
        setTestingWs(false);
      };
      
      testWs.onerror = (error) => {
        setApiConnectionStatus({ success: false, error: 'WebSocket connection failed' });
        console.log('WebSocket connection test failed:', error);
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
          console.log('WebSocket connection test timed out');
          setTestingWs(false);
        }
      }, 5000);
    } catch (error) {
      setApiConnectionStatus({ success: false, error: `WebSocket test failed: ${error.message}` });
      console.log('WebSocket test failed with error:', error.message);
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
    if (!apiBaseUrl || !apiBaseUrl.trim()) {
      setApiConnectionStatus({ success: false, error: 'API Base URL is required' });
      return;
    }

    setTestingApi(true);
    setApiConnectionStatus(null);
    try {
      const url = `${apiBaseUrl.replace(/\/$/, '')}/api/health`;
      console.log('Testing API connection to:', url);
      
      const res = await fetch(url, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
        // Add timeout to prevent hanging requests
        signal: AbortSignal.timeout(5000)
      });
      
      if (res.ok) {
        const data = await res.json();
        // Accept both 'ok' and 'healthy' status - any response means API is reachable
        if (data.status === 'ok' || data.status === 'healthy') {
          setApiConnectionStatus({ success: true, message: 'API connection successful!' });
          console.log('API connection test successful - API is healthy');
        } else if (data.status === 'unhealthy') {
          setApiConnectionStatus({ success: true, message: 'API connected but reports unhealthy status (check database)' });
          console.log('API connection test successful - API reachable but unhealthy:', data);
        } else {
          setApiConnectionStatus({ success: false, error: 'API responded but with unexpected status' });
          console.log('API responded but with unexpected data:', data);
        }
      } else {
        setApiConnectionStatus({ success: false, error: `API connection failed (Status: ${res.status})` });
        console.log('API connection test failed with status:', res.status);
      }
    } catch (error) {
      setApiConnectionStatus({ success: false, error: `Connection failed: ${error.message}` });
      console.log('API connection test failed with error:', error.message);
    } finally {
      setTestingApi(false);
    }
  }, [apiBaseUrl]);

  // Don't auto-test API connection on load to prevent console errors
  // Users can manually test using the "Test Connection" button
  /*
  useEffect(() => {
    if (apiBaseUrl) {
      testApiConnection();
    }
  }, [apiBaseUrl, testApiConnection]);
  */

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

      {/* Connection Configuration */}
      <div className="settings-card">
        <div className="card-header">
          <div className="flex items-center gap-sm">
            <Wifi size={20} />
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
        <AdminOperations />

        {/* Mobile Connection Guide */}
        <MobileConnectionGuide />

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
