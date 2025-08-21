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
        setSettings(settingsResponse.data.settings || {});
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
    const value = settings[key] || setting.default || '';

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
            onChange={(e) => handleSettingChange(key, parseFloat(e.target.value))}
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
        return (
          <select
            className="form-select"
            value={value}
            onChange={(e) => handleSettingChange(key, e.target.value)}
          >
            <option value="">Select {setting.label || key}</option>
            {options?.map((option) => (
              <option key={option.value} value={option.value}>
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
        </div>

        {config?.settings && (
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
