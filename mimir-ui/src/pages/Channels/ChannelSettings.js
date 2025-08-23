import React, { useState, useEffect } from 'react';
import { X, Save } from 'lucide-react';
import { api } from '../../services/api';
import './ChannelSettings.css';

// Import the getApiBaseUrl function from api service
const getApiBaseUrl = () => {
  const raw =
    (typeof window !== 'undefined' && window.mimirApiBaseUrl) ||
    localStorage.getItem('mimir-api-base-url');

  // Fallback includes /api already
  if (!raw) return 'http://oak:5000/api';
  
  try {
    // Handle absolute or relative bases
    const u = new URL(raw, window.location.origin);
    // Normalize trailing slashes
    u.pathname = u.pathname.replace(/\/+$/, '') || '/';
    // If path doesn't already start with /api, append it
    if (!/^\/api(\/|$)/i.test(u.pathname)) {
      u.pathname = (u.pathname === '/' ? '' : u.pathname) + '/api';
    }
    return u.toString();
  } catch {
    // Fallback for unusual inputs
    const t = String(raw).replace(/\/+$/, '');
    return /\/api(\/|$)/i.test(t) ? t : `${t}/api`;
  }
};

// Helper function to get server base URL (without /api suffix)
const getServerBaseUrl = () => {
  const raw =
    (typeof window !== 'undefined' && window.mimirApiBaseUrl) ||
    localStorage.getItem('mimir-api-base-url');

  // Fallback without /api suffix for UI routes
  if (!raw) return 'http://oak:5000';
  
  try {
    // Handle absolute or relative bases
    const u = new URL(raw, window.location.origin);
    // Normalize trailing slashes and remove /api if present
    u.pathname = u.pathname.replace(/\/+$/, '').replace(/\/api$/, '') || '/';
    return u.toString().replace(/\/$/, '');
  } catch {
    // Fallback for unusual inputs
    const t = String(raw).replace(/\/+$/, '').replace(/\/api$/, '');
    return t || 'http://oak:5000';
  }
};

const ChannelSettings = ({ channel, onClose }) => {
  const [config, setConfig] = useState(null);
  const [settings, setSettings] = useState({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [channelManifest, setChannelManifest] = useState(null);
  const [webComponentLoaded, setWebComponentLoaded] = useState(false);
  const [webComponentError, setWebComponentError] = useState(null);
  const [showManagementInterface, setShowManagementInterface] = useState(false);

  useEffect(() => {
    const loadChannelData = async () => {
      try {
        // Set global API configuration early for any Web Components
        window.mimirApiBaseUrl = getApiBaseUrl();
        window.mimirServerBaseUrl = getServerBaseUrl();
        console.log('🔧 Set global API config:', {
          mimirApiBaseUrl: window.mimirApiBaseUrl,
          mimirServerBaseUrl: window.mimirServerBaseUrl
        });

        const [configResponse, settingsResponse, manifestsResponse] = await Promise.all([
          api.getChannelConfig(channel.id),
          api.getChannelSettings(channel.id),
          api.getChannelsManifest()
        ]);

        setConfig(configResponse.data);
        
        // Initialize settings state with current values from settings response
        // Note: Settings endpoint returns simple key-value pairs, not detailed schema
        const currentSettings = {};
        if (settingsResponse.data) {
          // Handle simple key-value response format
          Object.entries(settingsResponse.data).forEach(([key, value]) => {
            currentSettings[key] = value;
          });
        }
        
        setSettings(currentSettings);

        // Find the manifest for this channel
        const manifest = manifestsResponse.data.find(m => m.id === channel.id);
        setChannelManifest(manifest);

        // If channel has Web Components, try to load them
        if (manifest?.ui && manifest.ui.length > 0) {
          await loadWebComponents(manifest);
        }
      } catch (error) {
        console.error('Error loading channel data:', error);
        setWebComponentError('Failed to load channel components');
      } finally {
        setLoading(false);
      }
    };

    loadChannelData();
  }, [channel]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await api.updateChannelSettings(channel.id, settings);
      onClose();
    } catch (error) {
      console.error('Error saving settings:', error);
    } finally {
      setSaving(false);
    }
  };

  const handleSettingChange = (key, value) => {
    setSettings(prev => ({
      ...prev,
      [key]: value
    }));
  };

  const loadWebComponents = async (manifest) => {
    try {
      // For photo frame channel, we don't have settings-specific components
      // The channel uses a separate management route (/photo-frame)
      // So we'll skip Web Component loading for now and use the fallback
      console.log(`Channel ${manifest.id} has UI components but no settings-specific components available`);
      
      // Look for any components that might be suitable for settings
      const settingsComponents = manifest.ui.filter(ui => 
        ui.slots?.includes('dashboard.settings') || 
        ui.slots?.includes('channel.settings') ||
        ui.element?.includes('config') ||
        ui.element?.includes('settings')
      );

      if (settingsComponents.length > 0) {
        // Load the first settings component if available
        const component = settingsComponents[0];
        
        // Construct full URL for the module
        const serverBaseUrl = getServerBaseUrl(); // Use dynamic server URL
        const fullModuleUrl = component.moduleUrl.startsWith('http') 
          ? component.moduleUrl 
          : `${serverBaseUrl}${component.moduleUrl}`;
        
        console.log(`Loading Web Component: ${component.element} from ${fullModuleUrl}`);
        
        // Check if component is already loaded
        if (!customElements.get(component.element)) {
          // Set global API configuration for the Web Component
          window.mimirApiBaseUrl = getApiBaseUrl();
          window.mimirServerBaseUrl = getServerBaseUrl(); // Provide server base URL for Web Components
          
          // Store original fetch before overriding
          const originalFetch = window.fetch;
          
          // Override global fetch to redirect API calls to the correct server
          window.fetch = function(input, init = {}) {
            let url = input;
            
            // Handle Request objects
            if (input instanceof Request) {
              url = input.url;
            }
            
            // If it's a relative URL starting with /api, redirect to the server
            if (typeof url === 'string' && url.startsWith('/api/')) {
              url = `${getServerBaseUrl()}${url}`;
              
              // Only include credentials for specific endpoints that require authentication
              // Asset URLs (like uploaded images) don't need credentials for CORS compatibility
              const isAssetUrl = url.includes('/assets/') || url.includes('/uploads/');
              const needsCredentials = !isAssetUrl && (url.includes('/upload') || url.includes('/settings') || url.includes('/delete') || (init.method && init.method !== 'GET'));
              
              init = {
                ...init,
                ...(needsCredentials && { credentials: 'include' }),
                headers: {
                  ...init.headers,
                }
              };
            }
            
            return originalFetch.call(this, url, init);
          };
          
          // Provide a global API client for Web Components to use
          window.mimirAPI = {
            baseUrl: getApiBaseUrl(),
            async fetch(endpoint, options = {}) {
              const url = endpoint.startsWith('http') ? endpoint : `${getServerBaseUrl()}${endpoint}`;
              return fetch(url, {
                ...options,
                credentials: 'include', // As required by the integration guide
                headers: {
                  ...options.headers,
                  // Add any additional required headers
                }
              });
            },
            // Channel-specific API helpers
            uploadFiles: async (channelId, files) => {
              const formData = new FormData();
              files.forEach(file => formData.append('files', file));
              return window.mimirAPI.fetch(`/api/channels/${channelId}/upload`, {
                method: 'POST',
                body: formData
              });
            }
          };
          
          await import(/* webpackIgnore: true */ fullModuleUrl);
          console.log(`✅ Web Component ${component.element} loaded successfully`);
        }
        
        setWebComponentLoaded(true);
      } else {
        // No settings components available, use fallback
        console.log(`No settings-specific Web Components found for ${manifest.id}`);
        setWebComponentError('No settings interface available - using fallback');
      }
    } catch (error) {
      console.error('Error loading Web Components:', error);
      setWebComponentError(`Failed to load component: ${error.message}`);
    }
  };

  const loadManagementComponent = async (manifest) => {
    try {
      // Find management component with route
      const managementComponent = manifest.ui?.find(ui => ui.route);
      
      if (managementComponent) {
        // Construct full URL for the module
        // The moduleUrl from manifest is relative like "/api/channels/..."
        // We need to prepend the server base URL
        const serverBaseUrl = getServerBaseUrl(); // Use dynamic server URL
        let fullModuleUrl = managementComponent.moduleUrl.startsWith('http') 
          ? managementComponent.moduleUrl 
          : `${serverBaseUrl}${managementComponent.moduleUrl}`;
        
        // Add cache-busting parameter to ensure fresh module loading
        const cacheBuster = Date.now();
        fullModuleUrl += fullModuleUrl.includes('?') ? `&v=${cacheBuster}` : `?v=${cacheBuster}`;
        
        console.log(`Loading Management Component: ${managementComponent.element} from ${fullModuleUrl}`);
        
        // Check if component is already loaded
        if (!customElements.get(managementComponent.element)) {
          // Set global API configuration for the Web Component
          window.mimirApiBaseUrl = getApiBaseUrl();
          window.mimirServerBaseUrl = getServerBaseUrl(); // Provide server base URL for Web Components
          
          // Store original fetch before overriding
          const originalFetch = window.fetch;
          
          // Override global fetch to redirect API calls to the correct server
          window.fetch = function(input, init = {}) {
            let url = input;
            
            // Handle Request objects
            if (input instanceof Request) {
              url = input.url;
            }
            
            // If it's a relative URL starting with /api, redirect to the server
            if (typeof url === 'string' && url.startsWith('/api/')) {
              url = `${getServerBaseUrl()}${url}`;
              
              // Asset URLs (like uploaded images) don't need credentials for CORS compatibility
              const isAssetUrl = url.includes('/assets/') || url.includes('/uploads/');
              const needsCredentials = !isAssetUrl && (url.includes('/upload') || url.includes('/settings') || url.includes('/delete') || (init.method && init.method !== 'GET'));
              
              init = {
                ...init,
                ...(needsCredentials && { credentials: 'include' }),
                headers: {
                  ...init.headers,
                }
              };
            }
            
            return originalFetch.call(this, url, init);
          };
          
          // Provide a global API client for Web Components to use
          window.mimirAPI = {
            baseUrl: getApiBaseUrl(),
            async fetch(endpoint, options = {}) {
              const url = endpoint.startsWith('http') ? endpoint : `${getServerBaseUrl()}${endpoint}`;
              return fetch(url, {
                ...options,
                credentials: 'include', // As required by the integration guide
                headers: {
                  ...options.headers,
                  // Add any additional required headers
                }
              });
            },
            // Channel-specific API helpers
            uploadFiles: async (channelId, files) => {
              const formData = new FormData();
              files.forEach(file => formData.append('files', file));
              return window.mimirAPI.fetch(`/api/channels/${channelId}/upload`, {
                method: 'POST',
                body: formData
              });
            }
          };
          
          await import(/* webpackIgnore: true */ fullModuleUrl);
          console.log(`✅ Management Component ${managementComponent.element} loaded successfully`);
          
          // Restore original fetch after component is loaded (optional)
          // window.fetch = originalFetch;
        }
        
        return managementComponent;
      } else {
        console.log(`No management component found for ${manifest.id}`);
        return null;
      }
    } catch (error) {
      console.error('Error loading Management Component:', error);
      return null;
    }
  };

  const hasManagementInterface = () => {
    return channelManifest?.ui?.some(ui => ui.route) || false;
  };

  const renderWebComponent = () => {
    if (!channelManifest?.ui) return null;

    // Find settings-related components
    const settingsComponents = channelManifest.ui.filter(ui => 
      ui.slots?.includes('dashboard.settings') || 
      ui.slots?.includes('channel.settings') ||
      ui.element?.includes('config') ||
      ui.element?.includes('settings')
    );

    if (settingsComponents.length === 0) return null;

    const component = settingsComponents[0];
    const hostProps = {
      channel: channel,
      settings: settings,
      config: config,
      apiBaseUrl: getApiBaseUrl(), // Use dynamic API base URL
      // Provide API helper functions for the Web Component
      api: {
        uploadFiles: (files) => {
          const formData = new FormData();
          files.forEach(file => formData.append('files', file));
          return api.callChannelAPI(channel.id, 'upload', 'POST', formData);
        },
        getImages: () => api.callChannelAPI(channel.id, 'images', 'GET'),
        updateImage: (imageId, data) => api.callChannelAPI(channel.id, `images/${imageId}`, 'PUT', data),
        toggleImage: (imageId) => api.callChannelAPI(channel.id, `images/${imageId}/toggle`, 'POST'),
        deleteImage: (imageId) => api.callChannelAPI(channel.id, `images/${imageId}`, 'DELETE'),
        getSettings: () => api.callChannelAPI(channel.id, 'settings', 'GET'),
        updateSettings: (settingsData) => api.callChannelAPI(channel.id, 'settings', 'PUT', settingsData),
        getHardwareStatus: () => api.callChannelAPI(channel.id, 'hardware', 'GET')
      },
      onSettingsChange: handleSettingChange,
      onSave: handleSave,
      onClose: onClose
    };

    // Create the Web Component element
    return React.createElement(component.element, {
      'data-hostprops': JSON.stringify(hostProps),
      key: `${channel.id}-${component.element}`
    });
  };

  const renderManagementComponent = () => {
    if (!channelManifest?.ui || !showManagementInterface) return null;

    // Find management component with route
    const managementComponent = channelManifest.ui.find(ui => ui.route);
    
    if (!managementComponent) return null;

    const hostProps = {
      channel: channel,
      settings: settings,
      config: config,
      apiBaseUrl: getApiBaseUrl(), // Use dynamic API base URL
      // Provide API helper functions for the Web Component
      api: {
        uploadFiles: (files) => {
          const formData = new FormData();
          files.forEach(file => formData.append('files', file));
          return api.callChannelAPI(channel.id, 'upload', 'POST', formData);
        },
        getImages: () => api.callChannelAPI(channel.id, 'images', 'GET'),
        updateImage: (imageId, data) => api.callChannelAPI(channel.id, `images/${imageId}`, 'PUT', data),
        toggleImage: (imageId) => api.callChannelAPI(channel.id, `images/${imageId}/toggle`, 'POST'),
        deleteImage: (imageId) => api.callChannelAPI(channel.id, `images/${imageId}`, 'DELETE'),
        getSettings: () => api.callChannelAPI(channel.id, 'settings', 'GET'),
        updateSettings: (settingsData) => api.callChannelAPI(channel.id, 'settings', 'PUT', settingsData),
        getHardwareStatus: () => api.callChannelAPI(channel.id, 'hardware', 'GET')
      },
      onSettingsChange: handleSettingChange,
      onSave: handleSave,
      onClose: () => setShowManagementInterface(false)
    };

    // Create the Management Web Component element
    return React.createElement(managementComponent.element, {
      'data-hostprops': JSON.stringify(hostProps),
      key: `${channel.id}-${managementComponent.element}-management`
    });
  };

  const renderSettingField = (key, setting) => {
    // Use current value from settings state, fallback to default
    let value = settings[key] !== undefined ? settings[key] : (setting.default || '');

    // If enum is present, render dropdown regardless of type
    if (Array.isArray(setting.enum)) {
      // Always use string for dropdown value
      const stringValue = value !== undefined && value !== null ? String(value) : '';
      return (
        <select
          className="form-select"
          value={stringValue}
          onChange={(e) => {
            let selected = e.target.value;
            // If original type is number, convert back
            if (setting.type === 'number') {
              selected = selected === '' ? '' : Number(selected);
            }
            handleSettingChange(key, selected);
          }}
        >
          {setting.enum.map(opt => (
            <option key={opt} value={String(opt)}>{opt}</option>
          ))}
        </select>
      );
    }

    switch (setting.type) {
      case 'string':
        return (
          <input
            type={setting.secret ? 'password' : 'text'}
            className="form-input"
            value={setting.secret && value ? '***hidden***' : value}
            onChange={(e) => handleSettingChange(key, e.target.value)}
            placeholder={setting.label || key}
            readOnly={setting.secret && value && value.includes('***')}
            onFocus={(e) => {
              if (setting.secret && e.target.value.includes('***')) {
                e.target.value = '';
                handleSettingChange(key, '');
              }
            }}
          />
        );

      case 'number':
        return (
          <input
            type="number"
            className="form-input"
            value={value}
            onChange={(e) => {
              const val = e.target.value;
              handleSettingChange(key, val === '' ? '' : parseFloat(val));
            }}
            placeholder={setting.label || key}
          />
        );

      case 'boolean':
        return (
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={!!value}
              onChange={(e) => handleSettingChange(key, e.target.checked)}
            />
            <span>{setting.label || key}</span>
          </label>
        );

      case 'select':
        // Support both array of objects and array of strings for options
        let options = setting.options;
        if (Array.isArray(options) && typeof options[0] === 'string') {
          options = options.map(opt => ({ value: opt, label: opt }));
        }
        const selectValue = value !== undefined && value !== null ? String(value) : '';
        return (
          <select
            className="form-select"
            value={selectValue}
            onChange={(e) => {
              let selected = e.target.value;
              // If original type is number, convert back
              if (setting.value !== undefined && typeof setting.value === 'number') {
                selected = selected === '' ? '' : Number(selected);
              }
              handleSettingChange(key, selected);
            }}
          >
            <option value="">Select {setting.label || key}</option>
            {options?.map((option) => (
              <option key={option.value} value={String(option.value)}>
                {option.label}
              </option>
            ))}
          </select>
        );

      default:
        return (
          <input
            type="text"
            className="form-input"
            value={value}
            onChange={(e) => handleSettingChange(key, e.target.value)}
            placeholder={setting.label || key}
          />
        );
    }
  };

  if (loading) {
    return (
      <div className="channel-settings-overlay">
        <div className="channel-settings">
          <div className="loading">
            <div className="loading-spinner"></div>
            <span>Loading settings...</span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="channel-settings-overlay">
      <div className="channel-settings">
        <div className="channel-settings-header">
          <div>
            <h2>{config?.name || channel.name}</h2>
            <p className="text-tertiary">{config?.description || channel.description}</p>
          </div>
          <button className="btn btn-sm" onClick={onClose}>
            <X size={16} />
          </button>
        </div>

        <div className="channel-settings-body">
          {/* Show management interface if loaded */}
          {showManagementInterface ? (
            <div className="management-interface">
              <div className="management-header">
                <h3>Management Interface</h3>
                <button 
                  className="btn btn-sm" 
                  onClick={() => setShowManagementInterface(false)}
                >
                  ← Back to Settings
                </button>
              </div>
              <div className="management-content">
                {renderManagementComponent()}
              </div>
            </div>
          ) : (
            <>
              {channel.hasUI && webComponentLoaded && !webComponentError ? (
            <div className="web-component-container">
              <div className="web-component-header">
                <p className="text-tertiary">
                  Using channel's custom configuration interface
                </p>
              </div>
              {renderWebComponent()}
            </div>
          ) : channel.hasUI ? (
            <div className="custom-ui-info">
              <p className="text-tertiary">
                This channel has a custom management interface with advanced features.
              </p>
              <div className="channel-features">
                <ul className="feature-list">
                  <li>📷 Image upload and management</li>
                  <li>✂️ Intelligent crop editing</li>
                  <li>🎬 Slideshow configuration</li>
                  <li>⚙️ Hardware settings</li>
                </ul>
              </div>
              <div className="custom-ui-actions">
                <button
                  className="btn btn-primary"
                  onClick={async () => {
                    // Load and show the management component
                    const managementComponent = await loadManagementComponent(channelManifest);
                    if (managementComponent) {
                      setShowManagementInterface(true);
                    }
                  }}
                >
                  Open Management Interface
                </button>
              </div>
              <div className="basic-settings-note">
                <small className="text-tertiary">
                  Use the management interface above for all channel configuration and advanced features.
                </small>
              </div>
            </div>
          ) : null}

          {/* Show basic settings only if no management interface is available */}
          {config?.settings && !hasManagementInterface() ? (
            <div className="settings-form">
              {Object.entries(config.settings).map(([key, setting]) => (
                <div key={key} className="form-group">
                  <label className="form-label">
                    {setting.label || key}
                    {setting.required && <span className="required">*</span>}
                  </label>
                  {setting.description && (
                    <p className="setting-description">{setting.description}</p>
                  )}
                  {renderSettingField(key, setting)}
                </div>
              ))}
            </div>
          ) : config?.settings && hasManagementInterface() ? (
            <div className="management-only-notice">
              <p className="text-tertiary">
                Settings for this channel are managed through the custom management interface above.
              </p>
            </div>
          ) : (
            <div className="no-settings">
              <p className="text-tertiary">
                {config?.settingsType === 'complex' ? 
                  'This channel uses a custom settings interface.' :
                  'No configurable settings available for this channel.'
                }
              </p>
            </div>
          )}
            </>
          )}
        </div>

        {config?.settings && !hasManagementInterface() && (
          <div className="channel-settings-footer">
            <button className="btn" onClick={onClose}>
              {channel.hasUI ? 'Close' : 'Cancel'}
            </button>
            <button 
              className="btn btn-primary" 
              onClick={handleSave}
              disabled={saving}
            >
              <Save size={16} />
              {saving ? 'Saving...' : 'Save Settings'}
            </button>
          </div>
        )}

        {(!config?.settings || hasManagementInterface()) && (
          <div className="channel-settings-footer">
            <button className="btn" onClick={onClose}>
              Close
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default ChannelSettings;
