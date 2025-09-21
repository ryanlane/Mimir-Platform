import React from 'react';
import PropTypes from 'prop-types';

/**
 * DistributionModeSelector
 * Encapsulates selection of scene distribution mode.
 * Props:
 *  - value: current mode string
 *  - onChange: (newMode) => void
 */
const modes = [
  { value: 'MIRROR', title: 'Mirror Mode', desc: 'All displays show the same content simultaneously' },
  { value: 'SEQUENTIAL', title: 'Sequential Mode', desc: 'Displays cycle through content in order' },
  { value: 'RANDOM_UNIQUE', title: 'Random Unique Mode', desc: 'Displays get randomized content without duplication' }
];

const DistributionModeSelector = ({ value, onChange }) => {
  return (
    <div className="form-group">
      <label className="form-label">Distribution Mode</label>
      <div className="distribution-mode-selection">
        {modes.map(mode => (
          <label key={mode.value} className="radio-item">
            <input
              type="radio"
              name="distribution_mode"
              value={mode.value}
              checked={value === mode.value}
              onChange={(e) => onChange(e.target.value)}
            />
            <div className="mode-info">
              <span className="mode-name">{mode.title}</span>
              <span className="mode-description">{mode.desc}</span>
            </div>
          </label>
        ))}
      </div>
    </div>
  );
};

export default DistributionModeSelector;

DistributionModeSelector.propTypes = {
  value: PropTypes.string.isRequired,
  onChange: PropTypes.func.isRequired
};
