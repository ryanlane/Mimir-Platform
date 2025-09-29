import React from 'react';
import './Header.css';
import Icon from '../Icon/Icon';

/**
 * Header component
 * Renders a page section header with optional icon and description.
 *
 * Props:
 *  - title (string, required)
 *  - description (string, optional)
 *  - icon (string | ReactElement) icon name (lucide) or custom element
 *  - iconSize (number) size of icon (default 32)
 *  - className (string)
 */
export function Header({ title, description, icon, iconSize = 32, className = '', ...rest }) {
  const descId = description ? `header-desc-${title?.toLowerCase().replace(/[^a-z0-9]+/g,'-')}` : undefined;

  const iconNode = React.isValidElement(icon)
    ? React.cloneElement(icon, { size: iconSize, 'aria-hidden': true })
    : (typeof icon === 'string' ? <Icon name={icon} size={iconSize} aria-hidden="true" /> : null);

  return (
    <div className={`header ${className}`} {...rest}>
      <div className="header-content">
        {iconNode && <div className="header-icon">{iconNode}</div>}
        <div>
          <h1 className="header-title" {...(descId ? { 'aria-describedby': descId } : {})}>{title}</h1>
          {description && <p id={descId} className="header-description text-tertiary">{description}</p>}
        </div>
      </div>
    </div>
  );
}

export default Header;
