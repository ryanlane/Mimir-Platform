import React from 'react';
import PropTypes from 'prop-types';
import SelectItem from '../../../components/SelectItem/SelectItem.jsx';

/**
 * UpdateStrategySelector
 * Handles selection between 'push' and 'scheduler' update strategies and optional fallback interval.
 * Props:
 *  - strategy: current strategy string ('push' | 'scheduler')
 *  - fallbackSeconds: number | undefined
 *  - pushAllowed: boolean (whether push can be selected)
 *  - hasChannelSelected: boolean (informational hint for description)
 *  - onChange: ({ strategy, fallbackSeconds }) => void
 */
const UpdateStrategySelector = ({ strategy, fallbackSeconds, pushAllowed, hasChannelSelected, onChange, disabledReason }) => {
  const handleStrategyChange = (value) => {
    if (value === 'push') {
      onChange({ strategy: 'push', fallbackSeconds: fallbackSeconds || 120 });
    } else {
      onChange({ strategy: 'scheduler', fallbackSeconds: undefined });
    }
  };

  return (
    <div className="form-group">
      <label className="form-label">Update Strategy</label>
      <div className="update-strategy-options">
        <SelectItem
          name="update_strategy"
          value="push"
          checked={strategy === 'push'}
          disabled={!pushAllowed}
          onChange={handleStrategyChange}
          title="Real-time Push"
          description={`Instant updates driven by channel events.${!pushAllowed ? ' ' + (disabledReason || 'Not supported by selected channel') : ''}`}
        />
        <SelectItem
          name="update_strategy"
            value="scheduler"
            checked={strategy !== 'push'}
            onChange={handleStrategyChange}
            title="Scheduled (Polling)"
            description="Refreshes follow configured schedule or manual triggers"
        />
      </div>
      {strategy === 'push' && (
        <div className="fallback-config">
          <label className="form-label small">Fallback Poll Interval (seconds)</label>
          <input
            type="number"
            min={30}
            step={10}
            className="form-input"
            value={fallbackSeconds}
            onChange={(e) => {
              const val = Math.max(30, parseInt(e.target.value) || 30);
              onChange({ strategy: 'push', fallbackSeconds: val });
            }}
          />
          <p className="help-text">If no push events arrive within this interval, a refresh is triggered automatically.</p>
        </div>
      )}
    </div>
  );
};

export default UpdateStrategySelector;

UpdateStrategySelector.propTypes = {
  strategy: PropTypes.string.isRequired,
  fallbackSeconds: PropTypes.number,
  pushAllowed: PropTypes.bool.isRequired,
  hasChannelSelected: PropTypes.bool.isRequired,
  onChange: PropTypes.func.isRequired,
  disabledReason: PropTypes.string
};
