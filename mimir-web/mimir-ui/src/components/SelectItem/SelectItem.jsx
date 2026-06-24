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
import './SelectItem.css';

/**
 * SelectItem
 * Accessible custom-styled radio (or checkbox-like) option block.
 * Uses an underlying input type="radio" for native semantics and keyboard support.
 */
const SelectItem = ({
  name,
  value,
  checked,
  onChange,
  title,
  description,
  icon = null,
  disabled = false,
  'aria-describedby': ariaDescribedBy
}) => {
  const id = `${name}-${value}`;

  return (
    <label className={`select-item ${checked ? 'is-checked' : ''} ${disabled ? 'is-disabled' : ''}`}> 
      <input
        id={id}
        className="select-item-input"
        type="radio"
        name={name}
        value={value}
        checked={checked}
        disabled={disabled}
        onChange={(e) => !disabled && onChange && onChange(e.target.value)}
        aria-checked={checked}
        aria-describedby={ariaDescribedBy}
      />
      <div className="select-item-content">
        <div className="select-item-header">
          {icon && <span className="select-item-icon" aria-hidden="true">{icon}</span>}
          <span className="select-item-title">{title}</span>
        </div>
        {description && <div className="select-item-description">{description}</div>}
      </div>
      <span className="select-item-indicator" aria-hidden="true" />
    </label>
  );
};

SelectItem.propTypes = {
  name: PropTypes.string.isRequired,
  value: PropTypes.string.isRequired,
  checked: PropTypes.bool,
  onChange: PropTypes.func,
  title: PropTypes.string.isRequired,
  description: PropTypes.string,
  icon: PropTypes.node,
  disabled: PropTypes.bool,
  'aria-describedby': PropTypes.string
};

export default SelectItem;
