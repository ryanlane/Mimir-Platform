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
import './Header.css';
import Icon from '../Icon/Icon';

/**
 * Header component
 * Renders a page/section header with optional icon, description and right-aligned action button(s).
 *
 * Props:
 *  - title (string, required)
 *  - description (string, optional)
 *  - icon (string | ReactElement) icon name (lucide) or custom element
 *  - iconSize (number) size of icon (default 32)
 *  - actions (ReactElement | ReactElement[] | function): optional single element, array (max 2) or render fn returning element(s)
 *  - rightSlot (ReactElement): optional arbitrary content rendered on the far right (e.g., DebugPanel or status widgets)
 *      Example: actions={[<Button key="add" />, <Button key="refresh" variant="ghost" />]}
 *  - className (string)
 *
 * Accessibility:
 *  - When description is present it is associated via aria-describedby.
 *  - Action buttons should each have discernible text or aria-label.
 */
export function Header({ title, description, icon, iconSize = 32, actions, rightSlot, className = '', ...rest }) {
  const descId = description ? `header-desc-${title?.toLowerCase().replace(/[^a-z0-9]+/g,'-')}` : undefined;

  const iconNode = React.isValidElement(icon)
    ? React.cloneElement(icon, { size: iconSize, 'aria-hidden': true })
    : (typeof icon === 'string' ? <Icon name={icon} size={iconSize} aria-hidden="true" /> : null);

  // Normalize actions: allow function for lazy evaluation.
  let actionNodes = undefined;
  if (typeof actions === 'function') {
    try {
      actionNodes = actions();
    } catch (e) {
      // Fail silently; could optionally log
      actionNodes = undefined;
    }
  } else if (Array.isArray(actions)) {
    actionNodes = actions.slice(0, 2); // enforce max 2
  } else if (actions) {
    actionNodes = [actions];
  }

  return (
    <div className={`header ${className}`} {...rest}>
      <div className="header-bar">
        <div className="header-main">
          {iconNode && <div className="header-icon">{iconNode}</div>}
          <div className="header-text">
            <h1 className="header-title" {...(descId ? { 'aria-describedby': descId } : {})}>{title}</h1>
            {description && <p id={descId} className="header-description text-tertiary">{description}</p>}
          </div>
        </div>
        {(actionNodes || rightSlot) && (
          <div className="header-right-cluster">
            {actionNodes && (
              <div className={`header-actions header-actions-count-${Array.isArray(actionNodes) ? actionNodes.length : 1}`}>
                {Array.isArray(actionNodes) ? actionNodes.map((node, idx) => (
                  <div key={idx} className="header-action-item">{node}</div>
                )) : actionNodes}
              </div>
            )}
            {rightSlot && (
              <div className="header-slot" data-slot>
                {rightSlot}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default Header;
