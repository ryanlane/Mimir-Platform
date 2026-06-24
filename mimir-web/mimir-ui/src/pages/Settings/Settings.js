// Copyright (C) 2026 Ryan Lane
//
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU Affero General Public License as published
// by the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
// GNU Affero General Public License for more details.
//
// You should have received a copy of the GNU Affero General Public License
// along with this program. If not, see <https://www.gnu.org/licenses/>.

import React, { useState, useEffect, useCallback } from 'react';
import { Settings as SettingsIcon, Volume2, VolumeX, Wifi, Download, Database, Trash2, RefreshCw, Send, Code } from 'lucide-react';
import { logger } from '../../utils/logger';
import './Settings.css';
import { useInstallPrompt } from '../../hooks/useInstallPrompt';
import { idb } from '../../services/idb';
import { outbox } from '../../services/outbox';
import { persistentCache } from '../../services/persistentCache';
import WebSocketStatus from '../../components/WebSocketStatus/WebSocketStatus';
import MobileConnectionGuide from '../../components/MobileConnectionGuide/MobileConnectionGuide';
import AdminOperations from '../../components/AdminOperations/AdminOperations';
import { ThemeSelector } from '../../components/ThemeSelector/ThemeSelector';
import Header from '../../components/Header/Header';
import {
  getPwaEnabledPreference,
  setPwaEnabledPreference,
  registerMimirServiceWorker,
  unregisterMimirServiceWorkers,
} from '../../services/pwaServiceWorker';

const Settings = () => {
  const [loading, setLoading] = useState(true);
  // Install prompt hook
  const { canInstall, promptInstall, installed } = useInstallPrompt();
  const [installing, setInstalling] = useState(false);

  // PWA enablement (opt-in; persisted locally)
  const [pwaEnabled, setPwaEnabled] = useState(getPwaEnabledPreference());
  const isProdBuild = process.env.NODE_ENV === 'production';
  const isPwaForcedOn = process.env.REACT_APP_ENABLE_PWA === 'true';

  // Cache management state
  const [idbStats, setIdbStats] = useState({ scenes: 0, channels: 0, distribution: 0 });
  const [swCacheStats, setSwCacheStats] = useState({ mipages: 0, api: 0, images: 0, static: 0, legacyApp: 0, runtime: 0 });
  const [outboxCount, setOutboxCount] = useState(0);
  const [cacheLoading, setCacheLoading] = useState(false);
  const [forceUpdating, setForceUpdating] = useState(false);

  const loadCacheStats = useCallback(async () => {
    setCacheLoading(true);
    try {
      // IDB stats (count keys per store)
      const [scenesKeys, channelKeys, distKeys] = await Promise.all([
        idb.keys(idb.STORES.SCENES),
        idb.keys(idb.STORES.CHANNELS),
        idb.keys(idb.STORES.DISTRIBUTION)
      ]);
      setIdbStats({
        scenes: scenesKeys.length,
        channels: channelKeys.length,
        distribution: distKeys.length
      });

      // SW caches
      const cacheNames = await caches.keys();
      const statObj = { mipages: 0, api: 0, images: 0, static: 0, legacyApp: 0, runtime: 0 };
      await Promise.all(cacheNames.map(async (cn) => {
        const cache = await caches.open(cn);
        const requests = await cache.keys();
        if (cn === 'mimir-pages') statObj.mipages = requests.length;
        else if (cn === 'mimir-api') statObj.api = requests.length;
        else if (cn === 'mimir-images') statObj.images = requests.length;
        else if (cn === 'mimir-static') statObj.static = requests.length;
        else if (cn.startsWith('mimir-app-shell-')) statObj.legacyApp += requests.length;
        else if (cn === 'mimir-runtime') statObj.runtime = requests.length;
      }));
      setSwCacheStats(statObj);
      // Outbox count
      try {
        const queued = await outbox.list();
        setOutboxCount(queued.filter(i => i.status === 'pending' || i.status === 'sending').length);
      } catch {}
    } catch (e) {
      console.warn('Failed to load cache stats', e);
    } finally {
      setCacheLoading(false);
    }
  }, []);

  useEffect(() => {
    const handler = () => {
      outbox.list().then(items => {
        setOutboxCount(items.filter(i => i.status === 'pending' || i.status === 'sending').length);
      });
    };
    window.addEventListener('mimir:outbox-updated', handler);
    return () => window.removeEventListener('mimir:outbox-updated', handler);
  }, []);

  const retryOutbox = async () => {
    if (navigator.serviceWorker?.controller) {
      navigator.serviceWorker.controller.postMessage({ type: 'OUTBOX_FLUSH' });
    } else {
      await outbox.forceFlush();
    }
  };

  useEffect(() => {
    loadCacheStats();
  }, [loadCacheStats]);

  const clearIdbCaches = async () => {
    await persistentCache.clearAll();
    await loadCacheStats();
    console.log('IndexedDB caches cleared');
  };

  const clearSwCaches = async () => {
    const names = await caches.keys();
    await Promise.all(names.map(n => caches.delete(n)));
    await loadCacheStats();
    console.log('Service Worker caches cleared');
  };

  const forceServiceWorkerUpdate = async () => {
    if (!navigator.serviceWorker?.controller) return;
    setForceUpdating(true);
    try {
      const regs = await navigator.serviceWorker.getRegistrations();
      await Promise.all(regs.map(r => r.update()));
      // Ask current waiting worker to skip waiting if present
      if (navigator.serviceWorker.controller) {
        navigator.serviceWorker.controller.postMessage({ type: 'SKIP_WAITING' });
      }
      // trigger reload after a short delay
      setTimeout(() => window.location.reload(), 600);
    } finally {
      setForceUpdating(false);
    }
  };

  const applyPwaToggle = async (enabled) => {
    if (isPwaForcedOn) return;
    setPwaEnabled(enabled);
    setPwaEnabledPreference(enabled);

    // In non-prod builds we keep SW off to avoid dev caching issues.
    if (!isProdBuild) return;

    try {
      if (enabled) {
        await registerMimirServiceWorker();
      } else {
        await unregisterMimirServiceWorkers({ clearCaches: true });
      }
    } finally {
      // Make behavior deterministic: reload so the SW (if enabled) can take control,
      // or (if disabled) so we fully stop using cached shell.
      setTimeout(() => window.location.reload(), 300);
    }
  };
  
  // Console verbosity settings
  const [consoleSettings, setConsoleSettings] = useState({
    verbosity: localStorage.getItem('mimir-console-verbosity') || 'normal',
    showWebSocketEvents: localStorage.getItem('mimir-show-websocket-events') !== 'false',
    showAPIRequests: localStorage.getItem('mimir-show-api-requests') !== 'false',
    showSceneEvents: localStorage.getItem('mimir-show-scene-events') !== 'false',
    showDisplayEvents: localStorage.getItem('mimir-show-display-events') !== 'false',
    showDebugPanel: localStorage.getItem('mimir-show-debug-panel') !== 'false'
  });

  const [apiBaseUrl, setApiBaseUrl] = useState(localStorage.getItem('mimir-api-base-url') || '');
  const [wsBaseUrl, setWsBaseUrl] = useState(localStorage.getItem('mimir-websocket-url') || '');
  const [mqttBrokerUrl, setMqttBrokerUrl] = useState(localStorage.getItem('mimir-mqtt-broker-url') || '');
  const [apiConnectionStatus, setApiConnectionStatus] = useState(null);
  const [testingApi, setTestingApi] = useState(false);
  const [testingWs, setTestingWs] = useState(false);
  const [testingMqtt, setTestingMqtt] = useState(false);
  const [mqttConnectionStatus, setMqttConnectionStatus] = useState(null);

  // Developer mode
  const [developerMode, setDeveloperMode] = useState(
    localStorage.getItem('mimir-developer-mode') === 'true'
  );

  const handleDeveloperModeToggle = () => {
    const newValue = !developerMode;
    setDeveloperMode(newValue);
    localStorage.setItem('mimir-developer-mode', String(newValue));
  };

  // Collapsible sections (all collapsed by default)
  const [sectionsExpanded, setSectionsExpanded] = useState({
    connection: false,
    appearance: false,
    console: false,
    developer: false,
    install: false,
    cache: false,
    system: false,
  });

  const toggleSection = (key) => {
    setSectionsExpanded(prev => ({ ...prev, [key]: !prev[key] }));
  };

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

    // Notify listeners (e.g., DebugPanel) if debug panel visibility changes
    if (setting === 'showDebugPanel') {
      window.dispatchEvent(new CustomEvent('mimir:debug-visibility-changed', { detail: { enabled: value } }));
    }
    
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
    window.dispatchEvent(new CustomEvent('mimir:api-base-url-changed', { detail: { baseUrl: url } }));
  };

  const handleWsUrlChange = (url) => {
    setWsBaseUrl(url);
    if (url) {
      localStorage.setItem('mimir-websocket-url', url);
    } else {
      localStorage.removeItem('mimir-websocket-url');
    }
  };

  const handleMqttUrlChange = (url) => {
    setMqttBrokerUrl(url);
    if (url) {
      localStorage.setItem('mimir-mqtt-broker-url', url);
    } else {
      localStorage.removeItem('mimir-mqtt-broker-url');
    }
    setMqttConnectionStatus(null);
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
    const mqttUrl = mqttBrokerUrl || 'Default (bundled broker)';
    return { apiUrl, wsUrl, mqttUrl };
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
    window.dispatchEvent(new CustomEvent('mimir:api-base-url-changed', { detail: { baseUrl: apiBaseUrl } }));
  }, [apiBaseUrl]);

  useEffect(() => {
    window.mimirMqttBrokerUrl = mqttBrokerUrl;
  }, [mqttBrokerUrl]);

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

  const testMqttConnection = useCallback(async () => {
    setTestingMqtt(true);
    setMqttConnectionStatus(null);
    try {
      const base = apiBaseUrl?.trim() ? apiBaseUrl.replace(/\/$/, '') : '';
      const url = `${base}/api/admin/mqtt/test`;
      const res = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ url: mqttBrokerUrl?.trim() || null }),
        signal: AbortSignal.timeout(5000)
      });

      if (!res.ok) {
        setMqttConnectionStatus({ success: false, error: `MQTT test failed (Status: ${res.status})` });
        return;
      }
      const data = await res.json();
      if (data?.success) {
        setMqttConnectionStatus({ success: true, message: data.message || 'MQTT broker reachable' });
      } else {
        setMqttConnectionStatus({ success: false, error: data?.message || 'MQTT broker not reachable' });
      }
    } catch (error) {
      setMqttConnectionStatus({ success: false, error: `MQTT test failed: ${error.message}` });
    } finally {
      setTestingMqtt(false);
    }
  }, [apiBaseUrl, mqttBrokerUrl]);

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
      <Header title="Settings" icon="settings" iconSize={36} description="Configure application settings" />

      {/* WebSocket Status Component */}
      <WebSocketStatus />

      {/* Connection Configuration */}
      <div className="settings-card">
        <div
          className="card-header"
          role="button"
          tabIndex={0}
          onClick={() => toggleSection('connection')}
          onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggleSection('connection'); } }}
        >
          <div className="flex items-center gap-sm">
            <Wifi size={20} />
            <h3 className="card-title">Connection Configuration</h3>
          </div>
          <button type="button" className="expand-button" aria-label={sectionsExpanded.connection ? 'Collapse section' : 'Expand section'}>
            {sectionsExpanded.connection ? '−' : '+'}
          </button>
        </div>
        {sectionsExpanded.connection && (
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

            <div className="config-group">
              <label htmlFor="mqtt-url">MQTT Broker URL:</label>
              <div className="url-input-group">
                <input
                  id="mqtt-url"
                  type="text"
                  value={mqttBrokerUrl}
                  onChange={(e) => handleMqttUrlChange(e.target.value)}
                  placeholder="e.g., mqtt://192.168.1.50:1883 (leave blank for default)"
                  className="url-input"
                />
                <button 
                  className="btn btn-outline" 
                  type="button" 
                  onClick={testMqttConnection} 
                  disabled={testingMqtt}
                >
                  {testingMqtt ? 'Testing...' : 'Test'}
                </button>
              </div>
              <small className="input-help">
                Current: {getCurrentUrls().mqttUrl}
              </small>
              {mqttConnectionStatus && (
                <div className={`connection-status-message ${mqttConnectionStatus.success ? 'success' : 'error'}`}>
                  {mqttConnectionStatus.message || mqttConnectionStatus.error}
                </div>
              )}
            </div>

            {apiConnectionStatus && (
              <div className={`connection-status-message ${apiConnectionStatus.success ? 'success' : 'error'}`}>
                {apiConnectionStatus.message || apiConnectionStatus.error}
              </div>
            )}
          </div>
          </div>
        )}
      </div>

      <div className="settings-grid">
        {/* Theme Selection */}
        <div className="settings-card">
          <div
            className="card-header"
            role="button"
            tabIndex={0}
            onClick={() => toggleSection('appearance')}
            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggleSection('appearance'); } }}
          >
            <div className="flex items-center gap-sm">
              <SettingsIcon size={20} />
              <h3 className="card-title">Appearance</h3>
            </div>
            <button type="button" className="expand-button" aria-label={sectionsExpanded.appearance ? 'Collapse section' : 'Expand section'}>
              {sectionsExpanded.appearance ? '−' : '+'}
            </button>
          </div>
          {sectionsExpanded.appearance && (
            <div className="card-body">
            <p className="text-tertiary" style={{ marginTop: 0 }}>
              Choose your preferred theme or follow the system setting.
            </p>
            <ThemeSelector />
            <small className="form-help" style={{ marginTop: '0.75rem' }}>
              Changing theme updates colors instantly. Components should use CSS variables (e.g., var(--color-background)).
            </small>
            </div>
          )}
        </div>

        {/* Console Verbosity Settings */}
        <div className="settings-card">
          <div
            className="card-header"
            role="button"
            tabIndex={0}
            onClick={() => toggleSection('console')}
            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggleSection('console'); } }}
          >
            <div className="flex items-center gap-sm">
              <Volume2 size={20} />
              <h3 className="card-title">Console Verbosity</h3>
            </div>
            <button type="button" className="expand-button" aria-label={sectionsExpanded.console ? 'Collapse section' : 'Expand section'}>
              {sectionsExpanded.console ? '−' : '+'}
            </button>
          </div>
          {sectionsExpanded.console && (
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

                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={consoleSettings.showDebugPanel}
                    onChange={(e) => handleVerbosityChange('showDebugPanel', e.target.checked)}
                  />
                  Show Debug Panel
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
          )}
        </div>

        {/* Developer Mode */}
        <div className="settings-card">
          <div
            className="card-header"
            role="button"
            tabIndex={0}
            onClick={() => toggleSection('developer')}
            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggleSection('developer'); } }}
          >
            <div className="flex items-center gap-sm">
              <Code size={20} />
              <h3 className="card-title">Developer</h3>
            </div>
            <button type="button" className="expand-button" aria-label={sectionsExpanded.developer ? 'Collapse section' : 'Expand section'}>
              {sectionsExpanded.developer ? '−' : '+'}
            </button>
          </div>
          {sectionsExpanded.developer && (
            <div className="card-body">
              <div className="setting-row">
                <div className="setting-label">
                  <strong>Developer Mode</strong>
                  <p className="text-tertiary">
                    Enables developer tools for channel plugin development. When enabled,
                    the Channels page shows a "Link Dev Channel" option that lets you load
                    a plugin from a local directory with automatic file-watching and reload.
                  </p>
                </div>
                <label className="toggle-switch" htmlFor="dev-mode-toggle">
                  <input
                    id="dev-mode-toggle"
                    type="checkbox"
                    checked={developerMode}
                    onChange={handleDeveloperModeToggle}
                  />
                  <span className="toggle-slider"></span>
                </label>
              </div>
            </div>
          )}
        </div>

        {/* Install App (PWA) */}
        <div className="settings-card">
          <div
            className="card-header"
            role="button"
            tabIndex={0}
            onClick={() => toggleSection('install')}
            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggleSection('install'); } }}
          >
            <div className="flex items-center gap-sm">
              <Download size={20} />
              <h3 className="card-title">Install App</h3>
            </div>
            <button type="button" className="expand-button" aria-label={sectionsExpanded.install ? 'Collapse section' : 'Expand section'}>
              {sectionsExpanded.install ? '−' : '+'}
            </button>
          </div>
          {sectionsExpanded.install && (
            <div className="card-body">
            <p className="text-tertiary" style={{ marginBottom: '0.75rem' }}>
              Install this web app for faster launch, offline support, and a more native experience.
            </p>

            <div className="setting-row" style={{ marginBottom: '0.75rem' }}>
              <div className="setting-label">
                <strong>Enable Offline Mode (PWA)</strong>
                <p className="text-tertiary">
                  When enabled, Mimir registers a service worker to cache the app shell and allow limited offline use.
                  This can improve reliability on spotty networks, but may cause stale assets if your browser caches aggressively.
                </p>
                {!isProdBuild && (
                  <p className="text-tertiary" style={{ marginTop: '0.25rem' }}>
                    Note: disabled in development builds.
                  </p>
                )}
                {isPwaForcedOn && (
                  <p className="text-tertiary" style={{ marginTop: '0.25rem' }}>
                    This instance has offline mode forced on by the administrator.
                  </p>
                )}
              </div>
              <label className="toggle-switch" htmlFor="pwa-enable-toggle">
                <input
                  id="pwa-enable-toggle"
                  type="checkbox"
                  checked={isProdBuild ? (isPwaForcedOn ? true : pwaEnabled) : false}
                  onChange={(e) => applyPwaToggle(e.target.checked)}
                  disabled={!isProdBuild || isPwaForcedOn}
                />
                <span className="toggle-slider"></span>
              </label>
            </div>

            <div className="install-status" style={{ marginBottom: '0.75rem', fontSize: '14px' }}>
              {installed ? (
                <span className="status-installed" style={{ color: 'var(--color-success)', fontWeight: 500 }}>
                  Installed on this device
                </span>
              ) : canInstall ? (
                <span style={{ color: 'var(--color-text-secondary)' }}>
                  Ready to install
                </span>
              ) : (
                <span style={{ color: 'var(--color-text-tertiary)' }}>
                  {window.matchMedia('(display-mode: standalone)').matches ? 'Running in standalone mode' : 'Install prompt not currently available'}
                </span>
              )}
            </div>
            <div className="install-actions" style={{ display: 'flex', gap: '0.5rem' }}>
              <button
                type="button"
                className="btn btn-primary"
                disabled={!canInstall || installing}
                onClick={async () => {
                  if (!canInstall) return;
                  setInstalling(true);
                  const result = await promptInstall();
                  setInstalling(false);
                  if (result?.outcome === 'accepted') {
                    console.log('PWA install accepted');
                  } else {
                    console.log('PWA install dismissed');
                  }
                }}
              >
                <Download size={16} /> {installing ? 'Installing...' : installed ? 'Installed' : 'Install App'}
              </button>
              {window.matchMedia('(display-mode: standalone)').matches && !installed && (
                <span style={{ fontSize: '12px', color: 'var(--color-text-tertiary)' }}>
                  (Standalone mode detected)
                </span>
              )}
            </div>
            {!canInstall && !installed && (
              <small className="form-help" style={{ display: 'block', marginTop: '0.75rem' }}>
                Tip: Use the browser share/menu and choose "Add to Home Screen" if supported.
              </small>
            )}
            </div>
          )}
        </div>

        {/* Cache Management */}
        <div className="settings-card">
          <div
            className="card-header"
            role="button"
            tabIndex={0}
            onClick={() => toggleSection('cache')}
            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggleSection('cache'); } }}
          >
            <div className="flex items-center gap-sm">
              <Database size={20} />
              <h3 className="card-title">Cache Management</h3>
            </div>
            <button type="button" className="expand-button" aria-label={sectionsExpanded.cache ? 'Collapse section' : 'Expand section'}>
              {sectionsExpanded.cache ? '−' : '+'}
            </button>
          </div>
          {sectionsExpanded.cache && (
            <div className="card-body">
            <p className="text-tertiary" style={{ marginBottom: '0.75rem' }}>
              View and manage local caches used for offline support and faster loads.
            </p>
            <div className="cache-stats-grid" style={{ display: 'grid', gap: '0.75rem', gridTemplateColumns: 'repeat(auto-fit,minmax(160px,1fr))', marginBottom: '1rem' }}>
              <div className="cache-stat-box">
                <strong>{idbStats.scenes}</strong>
                <span>Scenes (IDB)</span>
              </div>
              <div className="cache-stat-box">
                <strong>{idbStats.channels}</strong>
                <span>Channels (IDB)</span>
              </div>
              <div className="cache-stat-box">
                <strong>{idbStats.distribution}</strong>
                <span>Distribution (IDB)</span>
              </div>
              <div className="cache-stat-box">
                <strong>{swCacheStats.mipages}</strong>
                <span>Pages (SW)</span>
              </div>
              <div className="cache-stat-box">
                <strong>{swCacheStats.api}</strong>
                <span>API (SW)</span>
              </div>
              <div className="cache-stat-box">
                <strong>{swCacheStats.images}</strong>
                <span>Images (SW)</span>
              </div>
              <div className="cache-stat-box">
                <strong>{swCacheStats.static}</strong>
                <span>Static (SW)</span>
              </div>
              {swCacheStats.legacyApp > 0 && (
                <div className="cache-stat-box">
                  <strong>{swCacheStats.legacyApp}</strong>
                  <span>Legacy Shell</span>
                </div>
              )}
              <div className="cache-stat-box">
                <strong>{outboxCount}</strong>
                <span>Outbox Pending</span>
              </div>
            </div>
            <div className="cache-actions" style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
              <button type="button" className="btn btn-outline" disabled={cacheLoading} onClick={loadCacheStats}>
                <RefreshCw size={14} /> {cacheLoading ? 'Refreshing...' : 'Refresh Stats'}
              </button>
              <button type="button" className="btn btn-secondary" onClick={clearIdbCaches}>
                <Trash2 size={14} /> Clear Data Caches
              </button>
              <button type="button" className="btn btn-secondary" onClick={clearSwCaches}>
                <Trash2 size={14} /> Clear SW Caches
              </button>
              <button type="button" className="btn btn-primary" disabled={forceUpdating} onClick={forceServiceWorkerUpdate}>
                <RefreshCw size={14} /> {forceUpdating ? 'Updating...' : 'Force SW Update'}
              </button>
              <button type="button" className="btn btn-secondary" onClick={retryOutbox}>
                <Send size={14} /> Retry Outbox
              </button>
            </div>
            <small className="form-help" style={{ display: 'block', marginTop: '0.75rem' }}>
              Clearing caches may temporarily slow loads until data is refetched. Force Update checks for a new service worker and applies it immediately.
            </small>
            </div>
          )}
        </div>

        {/* Admin Operations */}
        <AdminOperations />

        {/* Mobile Connection Guide */}
        <MobileConnectionGuide />

        {/* System Information */}
        <div className="settings-card">
          <div
            className="card-header"
            role="button"
            tabIndex={0}
            onClick={() => toggleSection('system')}
            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggleSection('system'); } }}
          >
            <div className="flex items-center gap-sm">
              <SettingsIcon size={20} />
              <h3 className="card-title">System Information</h3>
            </div>
            <button type="button" className="expand-button" aria-label={sectionsExpanded.system ? 'Collapse section' : 'Expand section'}>
              {sectionsExpanded.system ? '−' : '+'}
            </button>
          </div>
          {sectionsExpanded.system && (
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
          )}
        </div>
      </div>
    </div>
  );
};

export default Settings;
