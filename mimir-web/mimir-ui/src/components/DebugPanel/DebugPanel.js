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
import { AlertCircle, Check, X, RefreshCw, Bug } from 'lucide-react';
import { api } from '../../services/api';
import Modal from '../Modal/Modal';
import Button from '../Button/Button';
import './DebugPanel.css';

/**
 * DebugPanel
 * Refactored to use the shared Modal component instead of a fixed positioned container.
 * The toggle button can now be rendered anywhere by the parent. Component supports
 * both uncontrolled (defaultOpen) and controlled (open/onOpenChange) modes.
 *
 * Props:
 *  - open (boolean, optional): controlled visibility
 *  - onOpenChange (fn, optional): called with boolean when visibility toggled
 *  - defaultOpen (boolean, optional): initial open state in uncontrolled mode
 *  - autoRunOnOpen (boolean, default false): automatically run tests when opened
 *  - showToggle (boolean, default true): if true and component is uncontrolled, renders an inline toggle button
 *  - toggleLabel (string, default 'Debug'): label for the inline toggle button
 *  - className (string): optional class for wrapper span when showToggle
 */
const DebugPanel = ({
  open,
  onOpenChange,
  defaultOpen = false,
  autoRunOnOpen = false,
  showToggle = true,
  toggleLabel = 'Debug',
  className = ''
}) => {
  const initialEnabled = localStorage.getItem('mimir-show-debug-panel') !== 'false';
  const [debugEnabled, setDebugEnabled] = useState(initialEnabled);
  const uncontrolled = open === undefined;
  const [internalOpen, setInternalOpen] = useState(defaultOpen);
  const isOpen = uncontrolled ? internalOpen : open;
  const [tests, setTests] = useState({});
  const [loading, setLoading] = useState(false);
  
  const runTests = useCallback(async () => {
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
  }, []);
  
  useEffect(() => {
    // Auto-run tests on mobile devices
    if (window.mimirDebug?.isMobile) {
      runTests();
    }
    const handler = (e) => {
      const enabled = e.detail?.enabled;
      if (typeof enabled === 'boolean') {
        setDebugEnabled(enabled);
        if (!enabled) {
          if (uncontrolled) setInternalOpen(false);
          onOpenChange && onOpenChange(false);
        }
      }
    };
    const storageHandler = (e) => {
      if (e.key === 'mimir-show-debug-panel') {
        const enabled = e.newValue !== 'false';
        setDebugEnabled(enabled);
        if (!enabled) {
          if (uncontrolled) setInternalOpen(false);
          onOpenChange && onOpenChange(false);
        }
      }
    };
    window.addEventListener('mimir:debug-visibility-changed', handler);
    window.addEventListener('storage', storageHandler);
    return () => {
      window.removeEventListener('mimir:debug-visibility-changed', handler);
      window.removeEventListener('storage', storageHandler);
    };
  }, [runTests, uncontrolled, onOpenChange]);

  // Auto run when opened if configured
  useEffect(() => {
    if (isOpen && autoRunOnOpen && Object.keys(tests).length === 0 && !loading) {
      runTests();
    }
  }, [isOpen, autoRunOnOpen, tests, loading, runTests]);
  
  const getStatusIcon = (status) => {
    switch (status) {
      case 'success': return <Check size={16} className="text-success" />;
      case 'error': return <X size={16} className="text-error" />;
      default: return <AlertCircle size={16} className="text-info" />;
    }
  };
  
  if (!debugEnabled) return null;

  const handleToggle = () => {
    if (uncontrolled) {
      setInternalOpen(o => !o);
    }
    onOpenChange && onOpenChange(!isOpen);
  };

  const closePanel = () => {
    if (uncontrolled) {
      setInternalOpen(false);
    }
    onOpenChange && onOpenChange(false);
  };

  const renderToggle = () => {
    if (!showToggle) return null;
    return (
      <span className={`debug-inline-toggle ${className}`}>        
        <Button size="sm" variant="tertiary" onClick={handleToggle} aria-expanded={isOpen} aria-controls="debug-panel-modal">
          <Bug size={14} />
          {toggleLabel}
        </Button>
      </span>
    );
  };

  // Only render toggle if uncontrolled or if parent explicitly wants it in controlled mode
  const toggleNode = renderToggle();
  
  return (
    <>
      {toggleNode}
      <Modal
        isOpen={!!isOpen}
        onClose={closePanel}
        title="Debug Panel"
        size="large"
      >
        <div className="debug-modal-body">
          <div className="debug-actions-bar" style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.75rem', flexWrap: 'wrap' }}>
            <Button size="sm" variant="secondary" onClick={runTests} disabled={loading}>
              <RefreshCw size={14} className={loading ? 'spinning' : ''} />
              Run Tests
            </Button>
            <Button size="sm" variant="ghost" onClick={closePanel}>
              <X size={14} />
              Close
            </Button>
          </div>
          <div className="debug-panel-content in-modal">
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
          <div className="debug-modal-footer" style={{ marginTop: '1rem' }}>
            <h4 style={{ margin: '0 0 8px 0', fontSize: '0.85rem' }}>📱 iOS Safari Troubleshooting:</h4>
            <ul style={{ margin: 0, paddingLeft: '16px', fontSize: '0.7rem' }}>
              <li>• Check if API health endpoint shows "success"</li>
              <li>• Verify channels/displays show data (not empty arrays)</li>
              <li>• Look for CORS or network errors</li>
              <li>• Ensure you're on the same WiFi network as the server</li>
              <li>• Try opening Safari DevTools (via Mac Safari → Develop)</li>
            </ul>
          </div>
        </div>
      </Modal>
    </>
  );
};

export default DebugPanel;
