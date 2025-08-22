import React, { useState, useEffect } from 'react';
import { X, Save } from 'lucide-react';
import { api } from '../../services/api';
import './ChannelSettings.css';

// Get API base URL for constructing management interface URLs
const getApiBaseUrl = () => {
  const raw =
    (typeof window !== 'undefined' && window.mimirApiBaseUrl) ||
    localStorage.getItem('mimir-api-base-url');
  
  // Fallback without /api suffix for UI routes
  if (!raw) return 'http://172.31.79.107:5000';
  // Remove /api suffix if present for UI routes
  return raw.replace(/\/api$/, '');
};

const ChannelSettings = ({ channel, onClose }) => {
  const [config, setConfig] = useState(null);
  const [settings, setSettings] = useState({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [channelManifest, setChannelManifest] = useState(null);
  const [webComponentLoaded, setWebComponentLoaded] = useState(false);
  const [webComponentError, setWebComponentError] = useState(null);
  const [managementComponentLoaded, setManagementComponentLoaded] = useState(false);
  const [showManagementInterface, setShowManagementInterface] = useState(false);

  useEffect(() => {
    const loadChannelData = async () => {
      try {
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
        console.log(`Loading Web Component: ${component.element} from ${component.moduleUrl}`);
        
        // Check if component is already loaded
        if (!customElements.get(component.element)) {
          await import(/* webpackIgnore: true */ component.moduleUrl);
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
        console.log(`Loading Management Component: ${managementComponent.element} from ${managementComponent.moduleUrl}`);
        
        // Check if component is already loaded
        if (!customElements.get(managementComponent.element)) {
          await import(/* webpackIgnore: true */ managementComponent.moduleUrl);
          console.log(`✅ Management Component ${managementComponent.element} loaded successfully`);
        }
        
        setManagementComponentLoaded(true);
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
                  Basic settings can be configured below, or use the full management interface for advanced features.
                </small>
              </div>
            </div>
          ) : null}

          {/* Always show basic settings if available, even for channels with custom UI */}
          {config?.settings ? (
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

        {config?.settings && (
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

        {!config?.settings && (
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
