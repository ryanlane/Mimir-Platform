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

import React from 'react';
import PropTypes from 'prop-types';
import SelectItem from '../../../components/SelectItem/SelectItem.jsx';

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
          <SelectItem
            key={mode.value}
            name="distribution_mode"
            value={mode.value}
            checked={value === mode.value}
            onChange={onChange}
            title={mode.title}
            description={mode.desc}
          />
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
