import React from 'react';
import { X, Save } from 'lucide-react';
import './SceneForm.css';
// Extracted presentational components
import ValidationErrors from './components/ValidationErrors';
import DistributionModeSelector from './components/DistributionModeSelector';
import UpdateStrategySelector from './components/UpdateStrategySelector';
import ChannelSelector from './components/ChannelSelector';
import ScheduleEditor from './components/ScheduleEditor';
import { useSceneFormLogic } from './useSceneFormLogic';

const SceneForm = ({ scene, channels, onClose }) => {
  const {
    formData,
    setFormData,
    validationErrors,
    loading,
    subChannelSupport,
    subChannelRequirements,
    availableSubChannels,
    loadingSubChannels,
    pushSelectable,
    scheduleData,
    currentSchedule,
    scheduleLoading,
    scheduleModified,
    handleScheduleChange,
    createSchedule,
    updateSchedule,
    deleteSchedule,
    isFormValid,
    save
  } = useSceneFormLogic({ scene, channels, onClose });

  const handleSubmit = (e) => { e.preventDefault(); save(); };

  /* Schedule functions temporarily disabled
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
  */

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

          <ValidationErrors errors={validationErrors} />

          <ChannelSelector
            channels={channels}
            assignments={formData.channels}
            subChannelSupport={subChannelSupport}
            availableSubChannels={availableSubChannels}
            subChannelRequirements={subChannelRequirements}
            loadingSubChannels={loadingSubChannels}
            onChange={(assignments) => setFormData(prev => ({ ...prev, channels: assignments }))}
          />

          <DistributionModeSelector
            value={formData.distribution_mode}
            onChange={(newMode) => setFormData(prev => ({ ...prev, distribution_mode: newMode }))}
          />

          <UpdateStrategySelector
            strategy={formData.update_strategy}
            fallbackSeconds={formData.push_fallback_poll_seconds}
            pushAllowed={pushSelectable}
            hasChannelSelected={formData.channels.length > 0}
            onChange={({ strategy, fallbackSeconds }) =>
              setFormData(prev => ({
                ...prev,
                update_strategy: strategy,
                // Only persist fallback value if push; remove when switching away
                ...(strategy === 'push'
                  ? { push_fallback_poll_seconds: fallbackSeconds }
                  : { push_fallback_poll_seconds: prev.push_fallback_poll_seconds })
              }))
            }
          />

          <ScheduleEditor
            currentSchedule={currentSchedule}
            scheduleData={scheduleData}
            scheduleModified={scheduleModified}
            loading={scheduleLoading}
            sceneId={scene?.id}
            onChange={handleScheduleChange}
            onCreate={createSchedule}
            onUpdate={updateSchedule}
            onDelete={deleteSchedule}
          />

          {/* Overlays section temporarily hidden
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
          */}

          {/* Schedule section temporarily hidden - will be replaced with frequency-based scheduler UI
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
          */}

          <div className="scene-form-footer">
            <button type="button" className="btn" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={loading || !isFormValid()}>
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
