import React, { useState, useEffect, useCallback } from 'react';
import { X, Save, ChevronDown } from 'lucide-react';
import { api } from '../../services/api';
import './SceneForm.css';

const SceneForm = ({ scene, channels, overlays, onClose }) => {
  const [formData, setFormData] = useState({
    name: '',
    channels: [],
    overlay: {
      overlays: [],
      position: ['top', 'right'],
      background: true,
      backgroundColor: { red: 0, green: 0, blue: 0, alpha: 10 }
    },
    schedule: null
  });
  const [loading, setLoading] = useState(false);
  
  // Sub-channel support
  const [subChannelSupport, setSubChannelSupport] = useState({});
  const [subChannelRequirements, setSubChannelRequirements] = useState({});
  const [availableSubChannels, setAvailableSubChannels] = useState({});
  const [loadingSubChannels, setLoadingSubChannels] = useState(false);
  const [validationErrors, setValidationErrors] = useState([]);

  // Load sub-channel support for all channels
  const loadSubChannelData = useCallback(async () => {
    if (!channels.length) return;
    
    setLoadingSubChannels(true);
    const supportInfo = {};
    const requirementsInfo = {};
    const subChannelsData = {};
    
    for (const channel of channels) {
      try {
        // Check if channel supports sub-channels
        const configResponse = await api.getSubChannelConfig(channel.id);
        supportInfo[channel.id] = configResponse.data?.supports_subchannels || false;
        
        if (supportInfo[channel.id]) {
          // Get subchannel requirements using new API
          const requirementsResponse = await api.getSubChannelRequirements(channel.id);
          requirementsInfo[channel.id] = requirementsResponse.data;
          
          // Get available sub-channels
          const subChannelsResponse = await api.getSubChannels(channel.id);
          subChannelsData[channel.id] = subChannelsResponse.data || [];
        }
      } catch (error) {
        // Channel doesn't support sub-channels or error occurred
        supportInfo[channel.id] = false;
        requirementsInfo[channel.id] = { requires_subchannel_selection: false };
        subChannelsData[channel.id] = [];
      }
    }
    
    setSubChannelSupport(supportInfo);
    setSubChannelRequirements(requirementsInfo);
    setAvailableSubChannels(subChannelsData);
    setLoadingSubChannels(false);
  }, [channels]);

  useEffect(() => {
    if (scene) {
      // Normalize channels to new format
      const normalizedChannels = scene.channels.map(channel => {
        if (typeof channel === 'string') {
          // Old format: just channel ID
          return { channel_id: channel, subchannel_id: null };
        } else if (channel && typeof channel === 'object') {
          // New format: channel assignment object
          return {
            channel_id: channel.channel_id,
            subchannel_id: channel.subchannel_id || null
          };
        }
        return { channel_id: String(channel), subchannel_id: null };
      });

      setFormData({
        name: scene.name || '',
        channels: normalizedChannels,
        overlay: scene.overlay || {
          overlays: [],
          position: ['top', 'right'],
          background: true,
          backgroundColor: { red: 0, green: 0, blue: 0, alpha: 10 }
        },
        schedule: scene.schedule || null
      });
    }
  }, [scene]);

  useEffect(() => {
    loadSubChannelData();
  }, [loadSubChannelData]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setValidationErrors([]);

    // Validate subchannel requirements
    const errors = [];
    for (const assignment of formData.channels) {
      const channelId = assignment.channel_id;
      const requirements = subChannelRequirements[channelId];
      
      if (requirements?.requires_subchannel_selection && !assignment.subchannel_id) {
        const channel = channels.find(ch => ch.id === channelId);
        const availableSubchannels = availableSubChannels[channelId] || [];
        const subchannelNames = availableSubchannels.map(sc => sc.name).join(', ');
        
        errors.push(
          `Channel "${channel?.name || channelId}" requires a subchannel selection. ` +
          `Available options: ${subchannelNames || 'None available'}`
        );
      }
    }

    if (errors.length > 0) {
      setValidationErrors(errors);
      setLoading(false);
      return;
    }

    try {
      if (scene) {
        await api.updateScene(scene.id, formData);
      } else {
        await api.createScene(formData);
      }
      onClose();
    } catch (error) {
      console.error('Error saving scene:', error);
      // Handle API validation errors
      if (error.response?.data?.detail) {
        if (Array.isArray(error.response.data.detail)) {
          setValidationErrors(error.response.data.detail);
        } else {
          setValidationErrors([error.response.data.detail]);
        }
      } else {
        setValidationErrors(['An error occurred while saving the scene']);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleChannelToggle = (channelId) => {
    setFormData(prev => {
      const existingAssignment = prev.channels.find(ch => ch.channel_id === channelId);
      
      if (existingAssignment) {
        // Remove channel assignment
        return {
          ...prev,
          channels: prev.channels.filter(ch => ch.channel_id !== channelId)
        };
      } else {
        // Add new channel assignment
        return {
          ...prev,
          channels: [...prev.channels, { channel_id: channelId, subchannel_id: null }]
        };
      }
    });
  };

  const handleSubChannelChange = (channelId, subChannelId) => {
    setFormData(prev => ({
      ...prev,
      channels: prev.channels.map(ch => 
        ch.channel_id === channelId 
          ? { ...ch, subchannel_id: subChannelId || null }
          : ch
      )
    }));
  };

  const isChannelSelected = (channelId) => {
    return formData.channels.some(ch => ch.channel_id === channelId);
  };

  const getSelectedSubChannel = (channelId) => {
    const assignment = formData.channels.find(ch => ch.channel_id === channelId);
    return assignment?.subchannel_id || '';
  };

  const handleOverlayToggle = (overlayId) => {
    setFormData(prev => ({
      ...prev,
      overlay: {
        ...prev.overlay,
        overlays: prev.overlay.overlays.includes(overlayId)
          ? prev.overlay.overlays.filter(id => id !== overlayId)
          : [...prev.overlay.overlays, overlayId]
      }
    }));
  };

  const handleScheduleChange = (field, value) => {
    setFormData(prev => ({
      ...prev,
      schedule: prev.schedule ? 
        { ...prev.schedule, [field]: value } :
        { days: ['mon', 'tue', 'wed', 'thu', 'fri'], start: '09:00', end: '17:00', [field]: value }
    }));
  };

  const removeSchedule = () => {
    setFormData(prev => ({ ...prev, schedule: null }));
  };

  return (
    <div className="scene-form-overlay">
      <div className="scene-form">
        <div className="scene-form-header">
          <h2>{scene ? 'Edit Scene' : 'Create Scene'}</h2>
          <button className="btn btn-sm" onClick={onClose}>
            <X size={16} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="scene-form-body">
          <div className="form-group">
            <label className="form-label">Scene Name</label>
            <input
              type="text"
              className="form-input"
              value={formData.name}
              onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
              required
            />
          </div>

          {validationErrors.length > 0 && (
            <div className="validation-errors">
              <h4>Validation Errors:</h4>
              <ul>
                {validationErrors.map((error, index) => (
                  <li key={index}>{error}</li>
                ))}
              </ul>
            </div>
          )}

          <div className="form-group">
            <label className="form-label">Channels</label>
            <div className="channels-selection">
              {channels.map((channel) => (
                <div key={channel.id} className="channel-assignment-group">
                  <label className="checkbox-item">
                    <input
                      type="checkbox"
                      checked={isChannelSelected(channel.id)}
                      onChange={() => handleChannelToggle(channel.id)}
                    />
                    <span>{channel.name}</span>
                  </label>
                  
                  {isChannelSelected(channel.id) && subChannelSupport[channel.id] && availableSubChannels[channel.id]?.length > 0 && (
                    <div className="subchannel-selection">
                      <label className="subchannel-label">Sub-Channel:</label>
                      <select
                        value={getSelectedSubChannel(channel.id)}
                        onChange={(e) => handleSubChannelChange(channel.id, e.target.value)}
                        className="subchannel-select"
                      >
                        {!subChannelRequirements[channel.id]?.requires_subchannel_selection && (
                          <option value="">All Content</option>
                        )}
                        {subChannelRequirements[channel.id]?.requires_subchannel_selection && !getSelectedSubChannel(channel.id) && (
                          <option value="">Select a subchannel...</option>
                        )}
                        {availableSubChannels[channel.id].map(subChannel => (
                          <option key={subChannel.id} value={subChannel.id}>
                            {subChannel.name}
                          </option>
                        ))}
                      </select>
                      {subChannelRequirements[channel.id]?.requires_subchannel_selection && (
                        <div className="subchannel-requirement-note">
                          * Subchannel selection required
                        </div>
                      )}
                    </div>
                  )}
                  
                  {isChannelSelected(channel.id) && loadingSubChannels && (
                    <div className="subchannel-loading">Loading sub-channels...</div>
                  )}
                </div>
              ))}
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">Overlays</label>
            <div className="checkbox-grid">
              {overlays.map((overlay) => (
                <label key={overlay.id} className="checkbox-item">
                  <input
                    type="checkbox"
                    checked={formData.overlay.overlays.includes(overlay.id)}
                    onChange={() => handleOverlayToggle(overlay.id)}
                  />
                  <span>{overlay.name}</span>
                </label>
              ))}
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">
              <input
                type="checkbox"
                checked={!!formData.schedule}
                onChange={(e) => {
                  if (e.target.checked) {
                    handleScheduleChange('days', ['mon', 'tue', 'wed', 'thu', 'fri']);
                  } else {
                    removeSchedule();
                  }
                }}
              />
              <span>Enable Schedule</span>
            </label>
          </div>

          {formData.schedule && (
            <div className="schedule-section">
              <div className="form-group">
                <label className="form-label">Start Time</label>
                <input
                  type="time"
                  className="form-input"
                  value={formData.schedule.start || '09:00'}
                  onChange={(e) => handleScheduleChange('start', e.target.value)}
                />
              </div>

              <div className="form-group">
                <label className="form-label">End Time</label>
                <input
                  type="time"
                  className="form-input"
                  value={formData.schedule.end || '17:00'}
                  onChange={(e) => handleScheduleChange('end', e.target.value)}
                />
              </div>

              <div className="form-group">
                <label className="form-label">Days</label>
                <div className="days-grid">
                  {[
                    { value: 'mon', label: 'Mon' },
                    { value: 'tue', label: 'Tue' },
                    { value: 'wed', label: 'Wed' },
                    { value: 'thu', label: 'Thu' },
                    { value: 'fri', label: 'Fri' },
                    { value: 'sat', label: 'Sat' },
                    { value: 'sun', label: 'Sun' }
                  ].map((day) => (
                    <label key={day.value} className="day-item">
                      <input
                        type="checkbox"
                        checked={formData.schedule.days?.includes(day.value)}
                        onChange={(e) => {
                          const days = formData.schedule.days || [];
                          const newDays = e.target.checked
                            ? [...days, day.value]
                            : days.filter(d => d !== day.value);
                          handleScheduleChange('days', newDays);
                        }}
                      />
                      <span>{day.label}</span>
                    </label>
                  ))}
                </div>
              </div>
            </div>
          )}

          <div className="scene-form-footer">
            <button type="button" className="btn" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={loading}>
              <Save size={16} />
              {loading ? 'Saving...' : 'Save Scene'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default SceneForm;
