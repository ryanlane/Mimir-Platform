import React, { useState, useEffect } from 'react';
import { X, Save } from 'lucide-react';
import { api } from '../../services/api';
import './ChannelSettings.css';

const ChannelSettings = ({ channel, onClose }) => {
  const [config, setConfig] = useState(null);
  const [settings, setSettings] = useState({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const loadChannelData = async () => {
      try {
        const [configResponse, settingsResponse] = await Promise.all([
          api.getChannelConfig(channel.id),
          api.getChannelSettings(channel.id)
        ]);

        setConfig(configResponse.data);
        
        // Initialize settings state with current values from settings response
        const currentSettings = {};
        if (settingsResponse.data) {
          Object.entries(settingsResponse.data).forEach(([key, setting]) => {
            if (setting.value !== undefined) {
              currentSettings[key] = setting.value;
            }
          });
        }
        
        setSettings(currentSettings);
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
          {channel.hasUI ? (
            <div className="custom-ui-info">
              <p className="text-tertiary">
                This channel has a custom user interface for advanced configuration and management.
              </p>
              <div className="custom-ui-actions">
                <button 
                  className="btn btn-primary"
                  onClick={() => {
                    // For photo_frame channel, use the specific route from the specification
                    // Handle both old and new channel IDs for backwards compatibility
                    if (channel.id === 'photo_frame' || channel.id === 'com.epaperframe.photoframe') {
                      window.open('/photo-frame', '_blank', 'noopener,noreferrer');
                    } else {
                      // Generic pattern for other channels with custom UI
                      const uiUrl = `/api/channels/${channel.id}/ui/`;
                      window.open(uiUrl, '_blank', 'noopener,noreferrer');
                    }
                  }}
                >
                  Open Management Interface
                </button>
              </div>
              <div className="custom-ui-note">
                <small className="text-tertiary">
                  The management interface provides image upload, crop editing, slideshow settings, and hardware configuration.
                </small>
              </div>
            </div>
          ) : config?.settings ? (
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
        </div>

        {!channel.hasUI && config?.settings && (
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
      </div>
    </div>
  );
};

export default ChannelSettings;
