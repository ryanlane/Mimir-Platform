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
import './NeoButton.css';
import Icon from '../Icon/Icon';

/**
 * NeoButton - neumorphic styled button with optional indicator dot.
 *
 * Props:
 * - label: string (text label if children not provided)
 * - hasDot: boolean (shows indicator dot)
 * - isActive: boolean (applies active styling + aria-pressed)
 * - onClick: function
 * - disabled: boolean
 * - className: string (additional classes)
 * - children: optional custom content to replace the label span contents
 */
const NeoButton = ({
  label,
  hasDot = false,
  isActive = false,
  icon, // string icon name or React element
  iconSize = 16,
  onClick,
  disabled = false,
  className = '',
  children,
  type = 'button',
  ...rest
}) => {
  const classes = [
    'neo-btn',
    hasDot ? 'has-dot' : '',
    isActive ? 'is-active' : '',
    className
  ].filter(Boolean).join(' ');

  const iconNode = icon
    ? (React.isValidElement(icon)
        ? React.cloneElement(icon, { size: icon.props?.size || iconSize, className: 'neo-btn-icon', 'aria-hidden': true })
        : <Icon name={icon} size={iconSize} className="neo-btn-icon" aria-hidden="true" />)
    : null;

  return (
    <button
      type={type}
      className={classes}
      aria-pressed={isActive}
      onClick={onClick}
      disabled={disabled}
      {...rest}
    >
      <span className="well" />
      <div className="contents">      
        {iconNode}
        <span className="label">{children || label}</span>
        <span className="dot" />
      </div>
    </button>
  );
};

export default NeoButton;
