import React, { useState, useEffect } from 'react';
import { AlertCircle, Check, X, RefreshCw, Bug, EyeOff } from 'lucide-react';
import { api } from '../../services/api';
import './DebugPanel.css';

const DebugPanel = () => {
  const initialEnabled = localStorage.getItem('mimir-show-debug-panel') !== 'false';
  const [debugEnabled, setDebugEnabled] = useState(initialEnabled);
  const [isVisible, setIsVisible] = useState(false);
  const [tests, setTests] = useState({});
  const [loading, setLoading] = useState(false);
  
  const runTests = async () => {
    setLoading(true);
    const results = {};
    
    // Test API base URL
    try {
      const baseUrl = api.getApiBaseUrl();
      results.apiBaseUrl = {
        status: 'success',
        message: `API Base URL: ${baseUrl}`,
        data: baseUrl
      };
    } catch (error) {
      results.apiBaseUrl = {
        status: 'error',
        message: `API Base URL Error: ${error.message}`
      };
    }
    
    // Test health endpoint
    try {
      const response = await fetch(`${api.getApiBaseUrl()}/health`);
      if (response.ok) {
        const data = await response.json();
        results.health = {
          status: 'success',
          message: 'Health endpoint accessible',
          data: data
        };
      } else {
        results.health = {
          status: 'error',
          message: `Health endpoint failed: ${response.status} ${response.statusText}`
        };
      }
    } catch (error) {
      results.health = {
        status: 'error',
        message: `Health endpoint error: ${error.message}`
      };
    }
    
    // Test channels endpoint
    try {
      const response = await api.getChannels();
      results.channels = {
        status: 'success',
        message: `Channels loaded: ${response.data?.channels?.length || 0} channels`,
        data: response.data
      };
    } catch (error) {
      results.channels = {
        status: 'error',
        message: `Channels error: ${error.message}`,
        data: error
      };
    }
    
    // Test displays endpoint
    try {
      const response = await api.getDisplays();
      results.displays = {
        status: 'success',
        message: `Displays loaded: ${response.data?.length || 0} displays`,
        data: response.data
      };
    } catch (error) {
      results.displays = {
        status: 'error',
        message: `Displays error: ${error.message}`,
        data: error
      };
    }
    
    // Test scenes endpoint
    try {
      const response = await api.getScenes();
      results.scenes = {
        status: 'success',
        message: `Scenes loaded: ${response.data?.scenes?.length || 0} scenes`,
        data: response.data
      };
    } catch (error) {
      results.scenes = {
        status: 'error',
        message: `Scenes error: ${error.message}`,
        data: error
      };
    }
    
    // Test network info
    results.network = {
      status: 'info',
      message: 'Network Information',
      data: {
        currentUrl: window.location.href,
        hostname: window.location.hostname,
        protocol: window.location.protocol,
        port: window.location.port,
        userAgent: navigator.userAgent,
        online: navigator.onLine,
        connection: navigator.connection ? {
          effectiveType: navigator.connection.effectiveType,
          downlink: navigator.connection.downlink,
          rtt: navigator.connection.rtt
        } : 'Not available'
      }
    };
    
    setTests(results);
    setLoading(false);
  };
  
  useEffect(() => {
    // Auto-run tests on mobile devices
    if (window.mimirDebug?.isMobile) {
      runTests();
    }
    const handler = (e) => {
      const enabled = e.detail?.enabled;
      if (typeof enabled === 'boolean') {
        setDebugEnabled(enabled);
        if (!enabled) setIsVisible(false);
      }
    };
    const storageHandler = (e) => {
      if (e.key === 'mimir-show-debug-panel') {
        const enabled = e.newValue !== 'false';
        setDebugEnabled(enabled);
        if (!enabled) setIsVisible(false);
      }
    };
    window.addEventListener('mimir:debug-visibility-changed', handler);
    window.addEventListener('storage', storageHandler);
    return () => {
      window.removeEventListener('mimir:debug-visibility-changed', handler);
      window.removeEventListener('storage', storageHandler);
    };
  }, []);
  
  const getStatusIcon = (status) => {
    switch (status) {
      case 'success': return <Check size={16} className="text-success" />;
      case 'error': return <X size={16} className="text-error" />;
      default: return <AlertCircle size={16} className="text-info" />;
    }
  };
  
  if (!debugEnabled) {
    return null;
  }

  if (!isVisible) {
    return (
      <div className="debug-panel-toggle">
        <button 
          className="btn btn-sm btn-tertiary"
          onClick={() => setIsVisible(true)}
          title="Show Debug Panel"
        >
          <Bug size={16} />
          Debug
        </button>
      </div>
    );
  }
  
  return (
    <div className="debug-panel">
      <div className="debug-panel-header">
        <div className="debug-title">
          <Bug size={18} />
          <h3>Debug Panel</h3>
        </div>
        <div className="debug-actions">
          <button 
            className="btn btn-sm btn-secondary"
            onClick={runTests}
            disabled={loading}
          >
            <RefreshCw size={14} className={loading ? 'spinning' : ''} />
            Run Tests
          </button>
          <button 
            className="btn btn-sm btn-tertiary"
            onClick={() => setIsVisible(false)}
          >
            <EyeOff size={14} />
            Hide
          </button>
        </div>
      </div>
      
      <div className="debug-panel-content">
        {Object.keys(tests).length === 0 ? (
          <div className="debug-empty">
            <p>Click "Run Tests" to diagnose connection issues</p>
          </div>
        ) : (
          <div className="debug-tests">
            {Object.entries(tests).map(([testName, result]) => (
              <div key={testName} className={`debug-test debug-test-${result.status}`}>
                <div className="debug-test-header">
                  {getStatusIcon(result.status)}
                  <strong>{testName}</strong>
                </div>
                <div className="debug-test-message">
                  {result.message}
                </div>
                {result.data && (
                  <details className="debug-test-data">
                    <summary>View Data</summary>
                    <pre>{JSON.stringify(result.data, null, 2)}</pre>
                  </details>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
      
      <div className="debug-panel-footer">
        <div className="debug-instructions">
          <h4>📱 iOS Safari Troubleshooting:</h4>
          <ul>
            <li>• Check if API health endpoint shows "success"</li>
            <li>• Verify channels/displays show data (not empty arrays)</li>
            <li>• Look for CORS or network errors</li>
            <li>• Ensure you're on the same WiFi network as the server</li>
            <li>• Try opening Safari DevTools (via Mac Safari → Develop)</li>
          </ul>
        </div>
      </div>
    </div>
  );
};

export default DebugPanel;
