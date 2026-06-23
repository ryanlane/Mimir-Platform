import React from 'react';
import PropTypes from 'prop-types';

/**
 * ScheduleEditor
 * Encapsulates auto-refresh schedule create/update/delete UI.
 * Props:
 *  - currentSchedule: existing schedule job or null
 *  - scheduleData: {freq_unit, freq_value, enabled}
 *  - scheduleModified: bool (local edits unsaved)
 *  - loading: bool (API operation in flight)
 *  - sceneId: string|number|undefined (disables create if absent)
 *  - onChange: (field, value) => void
 *  - onCreate: () => void
 *  - onUpdate: () => void
 *  - onDelete: () => void
 */
const ScheduleEditor = ({
  currentSchedule,
  scheduleData,
  scheduleModified,
  loading,
  sceneId,
  onChange,
  onCreate,
  onUpdate,
  onDelete
}) => {
  return (
    <div className="form-group">
      <label className="form-label">Auto-Refresh Schedule</label>
      <div className="schedule-controls">
        {currentSchedule ? (
          <div className="current-schedule">
            <div className="schedule-info">
              <span className="schedule-text">
                Current: Every {currentSchedule.freq_value} {currentSchedule.freq_unit}(s)
              </span>
              <span className={`schedule-status ${currentSchedule.enabled ? 'enabled' : 'disabled'}`}>
                {currentSchedule.enabled ? 'Enabled' : 'Disabled'}
              </span>
            </div>
            <div className="schedule-form">
              <div className="schedule-inputs">
                <span className="schedule-prefix">Every</span>
                <input
                  type="number"
                  min="1"
                  className="form-input schedule-value"
                  value={scheduleData.freq_value}
                  onChange={(e) => onChange('freq_value', e.target.value)}
                  required
                />
                <select
                  className="form-select schedule-unit"
                  value={scheduleData.freq_unit}
                  onChange={(e) => onChange('freq_unit', e.target.value)}
                >
                  <option value="second">Second(s)</option>
                  <option value="minute">Minute(s)</option>
                  <option value="hour">Hour(s)</option>
                  <option value="day">Day(s)</option>
                  <option value="week">Week(s)</option>
                </select>
              </div>
              {scheduleData.freq_unit === 'second' && (
                <p className="schedule-hint">Minimum effective interval is 30s (scheduler tick rate). Jitter is disabled for second-based schedules.</p>
              )}
              <div className="schedule-actions">
                <label className="schedule-enabled">
                  <input
                    type="checkbox"
                    checked={scheduleData.enabled}
                    onChange={(e) => onChange('enabled', e.target.checked)}
                  />
                  <span>Enabled</span>
                </label>
                <button
                  type="button"
                  className={`btn btn-sm ${scheduleModified ? 'btn-primary' : 'btn-secondary'}`}
                  onClick={onUpdate}
                  disabled={loading || !scheduleData.freq_value || scheduleData.freq_value < 1}
                >
                  {loading ? 'Updating...' : scheduleModified ? 'Save Changes' : 'Update'}
                </button>
                <button
                  type="button"
                  className="btn btn-sm btn-error"
                  onClick={onDelete}
                  disabled={loading}
                >
                  {loading ? 'Removing...' : 'Remove'}
                </button>
              </div>
            </div>
          </div>
        ) : (
          <div className="no-schedule">
            <p className="schedule-description">
              Set up automatic content refresh for this scene. The system will periodically update the scene's content.
            </p>
            <div className="schedule-form">
              <div className="schedule-inputs">
                <span className="schedule-prefix">Every</span>
                <input
                  type="number"
                  min="1"
                  className="form-input schedule-value"
                  value={scheduleData.freq_value}
                  onChange={(e) => onChange('freq_value', e.target.value)}
                  required
                />
                <select
                  className="form-select schedule-unit"
                  value={scheduleData.freq_unit}
                  onChange={(e) => onChange('freq_unit', e.target.value)}
                >
                  <option value="second">Second(s)</option>
                  <option value="minute">Minute(s)</option>
                  <option value="hour">Hour(s)</option>
                  <option value="day">Day(s)</option>
                  <option value="week">Week(s)</option>
                </select>
              </div>
              {scheduleData.freq_unit === 'second' && (
                <p className="schedule-hint">Minimum effective interval is 30s (scheduler tick rate). Jitter is disabled for second-based schedules.</p>
              )}
              <div className="schedule-actions">
                <button
                  type="button"
                  className="btn btn-sm btn-primary"
                  onClick={onCreate}
                  disabled={loading || !sceneId || !scheduleData.freq_value || scheduleData.freq_value < 1}
                >
                  {loading ? 'Creating...' : 'Add Schedule'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default ScheduleEditor;

ScheduleEditor.propTypes = {
  currentSchedule: PropTypes.shape({
    id: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
    freq_unit: PropTypes.string,
    freq_value: PropTypes.number,
    enabled: PropTypes.bool
  }),
  scheduleData: PropTypes.shape({
    freq_unit: PropTypes.string.isRequired,
    freq_value: PropTypes.oneOfType([PropTypes.string, PropTypes.number]).isRequired,
    enabled: PropTypes.bool.isRequired
  }).isRequired,
  scheduleModified: PropTypes.bool.isRequired,
  loading: PropTypes.bool.isRequired,
  sceneId: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
  onChange: PropTypes.func.isRequired,
  onCreate: PropTypes.func.isRequired,
  onUpdate: PropTypes.func.isRequired,
  onDelete: PropTypes.func.isRequired
};
