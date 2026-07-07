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

import React, { useState, useEffect } from 'react';
import { X } from 'lucide-react';
import { api } from '../../services/api';
import { getApiBaseUrl, getServerBaseUrl } from '../../services/runtimeUrls';
import './ChannelSettings.css';

const ChannelSettings = ({ channel, onClose }) => {
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadManagementComponent = async (configData) => {
      try {
  // Determine the management module + target custom element explicitly from manifest
  const managementModuleUrl = configData?.ui?.components?.manager;
  const manifestElementName = configData?.ui?.elements?.manager || null;
        
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
          
          // Choose the expected element strictly for THIS channel to prevent cross-channel collisions
          const expectedElement = manifestElementName || (channel.id === 'com.spotify.status'
            ? 'x-spotify-status-manager'
            : channel.id === 'com.epaperframe.photoframe'
              ? 'x-photo-frame-manager'
              : 'x-spotify-status-manager'); // fallback if unknown

          const alreadyRegistered = !!customElements.get(expectedElement);
          
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
          const finalElement = customElements.get(expectedElement) ? expectedElement : expectedElement; // explicit
          return { element: finalElement, moduleUrl: managementModuleUrl };
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
    const manifestElementName = (config.ui?.elements && config.ui.elements.manager) || null;
    const expectedElement = manifestElementName || (channel.id === 'com.spotify.status'
      ? 'x-spotify-status-manager'
      : channel.id === 'com.epaperframe.photoframe'
        ? 'x-photo-frame-manager'
        : 'x-spotify-status-manager');
    const managementComponent = { element: expectedElement, moduleUrl: config.ui.components.manager };
    
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
