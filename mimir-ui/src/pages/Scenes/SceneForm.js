import React, { useState, useEffect } from 'react';
import { X, Save } from 'lucide-react';
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

  useEffect(() => {
    if (scene) {
      setFormData({
        name: scene.name || '',
        channels: scene.channels || [],
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

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      if (scene) {
        await api.updateScene(scene.id, formData);
      } else {
        await api.createScene(formData);
      }
      onClose();
    } catch (error) {
      console.error('Error saving scene:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleChannelToggle = (channelId) => {
    setFormData(prev => ({
      ...prev,
      channels: prev.channels.includes(channelId)
        ? prev.channels.filter(id => id !== channelId)
        : [...prev.channels, channelId]
    }));
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

          <div className="form-group">
            <label className="form-label">Channels</label>
            <div className="checkbox-grid">
              {channels.map((channel) => (
                <label key={channel.id} className="checkbox-item">
                  <input
                    type="checkbox"
                    checked={formData.channels.includes(channel.id)}
                    onChange={() => handleChannelToggle(channel.id)}
                  />
                  <span>{channel.name}</span>
                </label>
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
