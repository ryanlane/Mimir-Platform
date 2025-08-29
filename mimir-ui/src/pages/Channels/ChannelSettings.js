import React, { useState, useEffect } from 'react';
import { X, Save } from 'lucide-react';
import { api } from '../../services/api';
import './ChannelSettings.css';

// Import the getApiBaseUrl function from api service
const getApiBaseUrl = () => {
  const raw =
    (typeof window !== 'undefined' && window.mimirApiBaseUrl) ||
    localStorage.getItem('mimir-api-base-url');

  if (raw) {
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
  }

  // Smart fallback based on current environment
  if (typeof window !== 'undefined') {
    const currentHost = window.location.hostname;
    const currentProtocol = window.location.protocol;
    
    // If we're running on localhost (development), use localhost
    if (currentHost === 'localhost' || currentHost === '127.0.0.1') {
      return 'http://localhost:5000/api';
    }
    
    // If we're running on the same host as the UI, use the same host
    if (currentHost && currentHost !== 'localhost') {
      return `${currentProtocol}//${currentHost}:5000/api`;
    }
  }

  // Final fallback for specific deployment
  return 'http://172.31.79.107:5000/api';
};

// Helper function to get server base URL (without /api suffix)
const getServerBaseUrl = () => {
  const raw =
    (typeof window !== 'undefined' && window.mimirApiBaseUrl) ||
    localStorage.getItem('mimir-api-base-url');

  if (raw) {
    try {
      // Handle absolute or relative bases
      const u = new URL(raw, window.location.origin);
      // Normalize trailing slashes and remove /api if present
      u.pathname = u.pathname.replace(/\/+$/, '').replace(/\/api$/, '') || '/';
      return u.toString().replace(/\/$/, '');
    } catch {
      // Fallback for unusual inputs
      const t = String(raw).replace(/\/+$/, '').replace(/\/api$/, '');
      return t;
    }
  }

  // Smart fallback based on current environment
  if (typeof window !== 'undefined') {
    const currentHost = window.location.hostname;
    const currentProtocol = window.location.protocol;
    
    // If we're running on localhost (development), use localhost
    if (currentHost === 'localhost' || currentHost === '127.0.0.1') {
      return 'http://localhost:5000';
    }
    
    // If we're running on the same host as the UI, use the same host
    if (currentHost && currentHost !== 'localhost') {
      return `${currentProtocol}//${currentHost}:5000`;
    }
  }

  // Final fallback for specific deployment
  return 'http://172.31.79.107:5000';
};

const ChannelSettings = ({ channel, onClose }) => {
  const [config, setConfig] = useState(null);
  const [settings, setSettings] = useState({});
  const [settingsSchema, setSettingsSchema] = useState(null);
  const [settingsType, setSettingsType] = useState('simple');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const loadManagementComponent = async (configData) => {
      try {
        // Find management component from manifest UI structure
        const managementModuleUrl = configData?.ui?.components?.manager;
        
        if (managementModuleUrl) {
          // Construct full URL for the module
          const serverBaseUrl = getServerBaseUrl();
          let fullModuleUrl = managementModuleUrl.startsWith('http') 
            ? managementModuleUrl 
            : `${serverBaseUrl}${managementModuleUrl}`;
          
          // Add cache-busting parameter to ensure fresh module loading
          const cacheBuster = Date.now();
          fullModuleUrl += fullModuleUrl.includes('?') ? `&v=${cacheBuster}` : `?v=${cacheBuster}`;
          
          console.log(`Loading Management Component from ${fullModuleUrl}`);
          
          // Check if component is already loaded
          if (!customElements.get('photo-frame-manager')) {
            // Set global API configuration for the Web Component
            window.mimirApiBaseUrl = getApiBaseUrl();
            window.mimirServerBaseUrl = getServerBaseUrl();
            
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
                  credentials: 'include',
                  headers: {
                    ...options.headers,
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
            console.log(`✅ Management Component loaded successfully`);
          }
          
          return { element: 'photo-frame-manager', moduleUrl: managementModuleUrl };
        } else {
          console.log(`No management component found for ${channel.id}`);
          return null;
        }
      } catch (error) {
        console.error('Error loading Management Component:', error);
        return null;
      }
    };

    const loadChannelData = async () => {
      try {
        // Set global API configuration early for any Web Components
        window.mimirApiBaseUrl = getApiBaseUrl();
        window.mimirServerBaseUrl = getServerBaseUrl();
        console.log('🔧 Set global API config:', {
          mimirApiBaseUrl: window.mimirApiBaseUrl,
          mimirServerBaseUrl: window.mimirServerBaseUrl
        });

        const configResponse = await api.getChannelManifest(channel.id);

        setConfig(configResponse.data);
        
        // Extract settings information from manifest
        const manifestData = configResponse.data;
        if (manifestData) {
          // Check if this is a simple settings channel with a settings schema
          // For now, assume advanced if it has UI components
          const hasManagementUI = manifestData.ui?.components?.manager;
          setSettingsType(hasManagementUI ? 'advanced' : 'simple');
          
          // For advanced channels, we don't need a settings schema
          // For simple channels, we'd need to define one or get it from the manifest
          setSettingsSchema(null);
          setSettings({});
        }

        // Auto-load management component if available
        if (configResponse.data?.ui?.components?.manager) {
          await loadManagementComponent(configResponse.data);
        }
      } catch (error) {
        console.error('Error loading channel data:', error);
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

  const hasManagementInterface = () => {
    return config?.ui?.components?.manager || false;
  };

  const renderManagementComponent = () => {
    if (!config?.ui?.components?.manager) return null;

    const managementComponent = {
      element: 'photo-frame-manager', // Default web component name
      moduleUrl: config.ui.components.manager
    };
    
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
      onClose: onClose
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
          {/* Inject channel UI component directly if available */}
          {hasManagementInterface() ? (
            renderManagementComponent()
          ) : settingsType === 'simple' && settingsSchema?.properties ? (
            /* Show simple settings form for channels with settingsType: simple */
            <div className="settings-form">
              {Object.entries(settingsSchema.properties).map(([key, setting]) => (
                <div key={key} className="form-group">
                  <label className="form-label">
                    {setting.title || setting.label || key}
                    {setting.required && <span className="required">*</span>}
                  </label>
                  {setting.description && (
                    <p className="setting-description">{setting.description}</p>
                  )}
                  {renderSettingField(key, setting)}
                </div>
              ))}
            </div>
          ) : (
            /* Fallback for channels with no settings or unrecognized type */
            <div className="no-settings">
              <p className="text-tertiary">
                {settingsType === 'advanced' ? 
                  'This channel uses a custom settings interface.' :
                  'No configurable settings available for this channel.'
                }
              </p>
            </div>
          )}
        </div>

        {settingsType === 'simple' && settingsSchema?.properties && (
          <div className="channel-settings-footer">
            <button className="btn" onClick={onClose}>
              Cancel
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

        {(settingsType !== 'simple' || !settingsSchema?.properties) && (
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
