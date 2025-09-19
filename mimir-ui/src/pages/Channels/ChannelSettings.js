import React, { useState, useEffect } from 'react';
import { X } from 'lucide-react';
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
  const [loading, setLoading] = useState(true);

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
          
          // Check if component is already loaded (check multiple possible names)
          const possibleNames = [
            'x-spotify-status-manager',
            'spotify-status-manager',
            // legacy / other channel managers
            'x-photo-frame-manager',
            'photo-frame-manager'
          ];
          const alreadyRegistered = possibleNames.some(name => customElements.get(name));
          
          if (!alreadyRegistered) {
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
            
            try {
              await import(/* webpackIgnore: true */ fullModuleUrl);
              console.log(`✅ Management Component loaded successfully`);
            } catch (importError) {
              // Handle duplicate registration error gracefully
              if (importError.name === 'NotSupportedError' && importError.message.includes('already been used')) {
                console.log(`⚠️ Management Component already registered, skipping import`);
              } else {
                throw importError; // Re-throw other errors
              }
            }
          } else {
            console.log(`✅ Management Component already loaded`);
          }
          
          // Determine which element name is actually registered
          const registeredName = possibleNames.find(name => customElements.get(name)) || 'x-spotify-status-manager';
          
          return { element: registeredName, moduleUrl: managementModuleUrl };
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
    // Settings are now handled entirely by the channel plugin UI
    onClose();
  };

  const handleSettingChange = (key, value) => {
    // Settings are now handled entirely by the channel plugin UI
    console.log('Settings handled by plugin UI:', key, value);
  };

  const hasManagementInterface = () => {
    return config?.ui?.components?.manager || false;
  };

  const renderManagementComponent = () => {
    if (!config?.ui?.components?.manager) return null;

    // Dynamically detect which element name is registered
    const possibleNames = [
      'x-spotify-status-manager',
      'spotify-status-manager',
      'x-photo-frame-manager',
      'photo-frame-manager'
    ];
    const registeredName = possibleNames.find(name => customElements.get(name)) || 'x-spotify-status-manager';

    // Allow manifest to explicitly define element names (e.g., ui.elements.manager)
  const manifestElementName = (config.ui.elements && config.ui.elements.manager) || null;
    const managementComponent = {
      element: manifestElementName || registeredName,
      moduleUrl: config.ui.components.manager
    };
    
    if (!managementComponent) return null;

    const hostProps = {
      channel: channel,
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
          ) : (
            /* Fallback for channels with no management interface */
            <div className="no-settings">
              <p className="text-tertiary">
                This channel manages its own settings through its interface.
              </p>
            </div>
          )}
        </div>

        <div className="channel-settings-footer">
          <button className="btn" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
};

export default ChannelSettings;
