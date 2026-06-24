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
import { Clock, Play, Pause, Trash2, Save, X, RefreshCw } from 'lucide-react';
import { api } from '../../services/api';
import './ScheduleManager.css';

const ScheduleManager = ({ sceneId, sceneName, onClose }) => {
  const [schedules, setSchedules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [newSchedule, setNewSchedule] = useState({
    name: '',
    description: '',
    freq_unit: 'hour',
    freq_value: 1,
    timezone_name: Intl.DateTimeFormat().resolvedOptions().timeZone,
    enabled: true,
    jitter_seconds: 0
  });
  const [error, setError] = useState(null);

  const loadSchedules = useCallback(async () => {
    try {
      setLoading(true);
      const response = await api.getSceneSchedules(sceneId);
      setSchedules(response.data.jobs || []);
      setError(null);
    } catch (err) {
      console.error('Error loading schedules:', err);
      setError('Failed to load schedules');
    } finally {
      setLoading(false);
    }
  }, [sceneId]);

  useEffect(() => {
    loadSchedules();
  }, [loadSchedules]);

  const handleCreateSchedule = async () => {
    try {
      setCreating(true);
      setError(null);
      
      const scheduleData = {
        ...newSchedule,
        name: newSchedule.name || `${sceneName} - ${newSchedule.freq_value} ${newSchedule.freq_unit}(s)`,
        description: newSchedule.description || `Auto-refresh ${sceneName} every ${newSchedule.freq_value} ${newSchedule.freq_unit}(s)`
      };
      
      await api.createSceneSchedule(sceneId, scheduleData);
      
      // Reset form
      setNewSchedule({
        name: '',
        description: '',
        freq_unit: 'hour',
        freq_value: 1,
        timezone_name: Intl.DateTimeFormat().resolvedOptions().timeZone,
        enabled: true,
        jitter_seconds: 0
      });
      
      // Reload schedules
      await loadSchedules();
    } catch (err) {
      console.error('Error creating schedule:', err);
      setError('Failed to create schedule: ' + (err.response?.data?.detail || err.message));
    } finally {
      setCreating(false);
    }
  };

  const handleToggleSchedule = async (jobId, currentEnabled) => {
    try {
      if (currentEnabled) {
        await api.disableSchedulerJob(jobId);
      } else {
        await api.enableSchedulerJob(jobId);
      }
      await loadSchedules();
    } catch (err) {
      console.error('Error toggling schedule:', err);
      setError('Failed to toggle schedule');
    }
  };

  const handleDeleteSchedule = async (jobId) => {
    if (!window.confirm('Are you sure you want to delete this schedule?')) {
      return;
    }
    
    try {
      await api.deleteSchedulerJob(jobId);
      await loadSchedules();
    } catch (err) {
      console.error('Error deleting schedule:', err);
      setError('Failed to delete schedule');
    }
  };

  const handleTriggerNow = async (jobId) => {
    try {
      await api.triggerSchedulerJob(jobId, 'Manual trigger from schedule manager');
      // Show success message (you could add a toast notification here)
      alert('Schedule triggered successfully!');
    } catch (err) {
      console.error('Error triggering schedule:', err);
      setError('Failed to trigger schedule');
    }
  };

  const formatNextRun = (nextRunAt) => {
    if (!nextRunAt) return 'Not scheduled';
    const date = new Date(nextRunAt);
    return date.toLocaleString();
  };

  const formatFrequency = (freqUnit, freqValue) => {
    const unit = freqValue === 1 ? freqUnit : `${freqUnit}s`;
    return `Every ${freqValue} ${unit}`;
  };

  const getFrequencyOptions = () => [
    { value: 'minute', label: 'Minutes' },
    { value: 'hour', label: 'Hours' },
    { value: 'day', label: 'Days' },
    { value: 'week', label: 'Weeks' }
  ];

  const isFormValid = () => {
    return newSchedule.freq_value > 0;
  };

  if (loading) {
    return (
      <div className="schedule-manager">
        <div className="schedule-manager-header">
          <h2>Schedule Manager</h2>
          <button className="btn btn-sm btn-secondary" onClick={onClose}>
            <X size={16} />
          </button>
        </div>
        <div className="loading">
          <div className="loading-spinner"></div>
          <span>Loading schedules...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="schedule-manager">
      <div className="schedule-manager-header">
        <div>
          <h2>Schedule Manager</h2>
          <p className="text-tertiary">Manage automatic refresh schedules for "{sceneName}"</p>
        </div>
        <button className="btn btn-sm btn-secondary" onClick={onClose}>
          <X size={16} />
        </button>
      </div>

      {error && (
        <div className="error-message">
          {error}
          <button onClick={() => setError(null)}>×</button>
        </div>
      )}

      <div className="schedule-manager-body">
        {/* Existing Schedules */}
        <div className="schedules-section">
          <h3>Current Schedules</h3>
          {schedules.length > 0 ? (
            <div className="schedules-list">
              {schedules.map((schedule) => (
                <div key={schedule.id} className={`schedule-item ${schedule.enabled ? 'enabled' : 'disabled'}`}>
                  <div className="schedule-info">
                    <div className="schedule-title">
                      <Clock size={16} />
                      <span>{schedule.name}</span>
                      <span className={`status-badge ${schedule.enabled ? 'active' : 'paused'}`}>
                        {schedule.enabled ? 'Active' : 'Paused'}
                      </span>
                    </div>
                    <div className="schedule-details">
                      <span className="frequency">
                        {formatFrequency(schedule.freq_unit, schedule.freq_value)}
                      </span>
                      <span className="next-run">
                        Next: {formatNextRun(schedule.next_run_at)}
                      </span>
                      {schedule.consecutive_failures > 0 && (
                        <span className="failures-badge">
                          {schedule.consecutive_failures} failures
                        </span>
                      )}
                    </div>
                    {schedule.description && (
                      <p className="schedule-description">{schedule.description}</p>
                    )}
                  </div>
                  <div className="schedule-actions">
                    <button
                      className="btn btn-sm btn-accent"
                      onClick={() => handleTriggerNow(schedule.id)}
                      title="Trigger now"
                    >
                      <RefreshCw size={14} />
                    </button>
                    <button
                      className={`btn btn-sm ${schedule.enabled ? 'btn-warning' : 'btn-success'}`}
                      onClick={() => handleToggleSchedule(schedule.id, schedule.enabled)}
                      title={schedule.enabled ? 'Pause schedule' : 'Resume schedule'}
                    >
                      {schedule.enabled ? <Pause size={14} /> : <Play size={14} />}
                    </button>
                    <button
                      className="btn btn-sm btn-error"
                      onClick={() => handleDeleteSchedule(schedule.id)}
                      title="Delete schedule"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="empty-schedules">
              <p className="text-tertiary">No schedules configured for this scene.</p>
            </div>
          )}
        </div>

        {/* Create New Schedule */}
        <div className="create-schedule-section">
          <h3>Create New Schedule</h3>
          <div className="schedule-form">
            <div className="form-row">
              <div className="form-group">
                <label className="form-label">Name (optional)</label>
                <input
                  type="text"
                  className="form-input"
                  value={newSchedule.name}
                  onChange={(e) => setNewSchedule(prev => ({ ...prev, name: e.target.value }))}
                  placeholder={`${sceneName} - Auto refresh`}
                />
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label className="form-label">Description (optional)</label>
                <input
                  type="text"
                  className="form-input"
                  value={newSchedule.description}
                  onChange={(e) => setNewSchedule(prev => ({ ...prev, description: e.target.value }))}
                  placeholder="Describe when and why this schedule runs"
                />
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label className="form-label">Frequency</label>
                <div className="frequency-inputs">
                  <input
                    type="number"
                    className="form-input frequency-value"
                    value={newSchedule.freq_value}
                    onChange={(e) => setNewSchedule(prev => ({ 
                      ...prev, 
                      freq_value: Math.max(1, parseInt(e.target.value) || 1) 
                    }))}
                    min="1"
                    max="999"
                  />
                  <select
                    className="form-select frequency-unit"
                    value={newSchedule.freq_unit}
                    onChange={(e) => setNewSchedule(prev => ({ ...prev, freq_unit: e.target.value }))}
                  >
                    {getFrequencyOptions().map(option => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label className="form-label">Timezone</label>
                <input
                  type="text"
                  className="form-input"
                  value={newSchedule.timezone_name}
                  onChange={(e) => setNewSchedule(prev => ({ ...prev, timezone_name: e.target.value }))}
                  placeholder="UTC"
                />
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label className="form-label">
                  <input
                    type="checkbox"
                    checked={newSchedule.enabled}
                    onChange={(e) => setNewSchedule(prev => ({ ...prev, enabled: e.target.checked }))}
                  />
                  <span>Enable immediately</span>
                </label>
              </div>
            </div>

            <div className="form-actions">
              <button
                type="button"
                className="btn btn-primary"
                onClick={handleCreateSchedule}
                disabled={creating || !isFormValid()}
              >
                <Save size={16} />
                {creating ? 'Creating...' : 'Create Schedule'}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ScheduleManager;