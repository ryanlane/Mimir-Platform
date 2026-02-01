import React from 'react';
import PropTypes from 'prop-types';
import './TagItem.css';

/**
 * TagItem
 * Small interactive tag/chip element that can be selectable and optionally removable.
 * Accessibility: renders as a button (role=option when part of a listbox-like group) to ensure
 * keyboard focus & interaction. Remove action is a separate button with aria-label.
 */
const TagItem = ({
  label,
  selected = false,
  selectable = false,
  disabled = false,
  onClick,
  onRemove,
  removable = false,
  size = 'md', // sm | md
  variant = 'default', // default | accent | success | warning | error
  icon = null,
  className = '',
  id,
  'aria-label': ariaLabel,
  role: explicitRole,
  ...rest
}) => {
  // Determine role: if selectable treat as button (toggle) unless provided as option; otherwise presentational span
  const role = selectable ? (explicitRole || 'button') : (explicitRole || undefined);
  const handleClick = (e) => {
    if (!selectable) return; // ignore clicks in display-only mode
    if (disabled) return;
    if (onClick) onClick(e);
  };

  const handleRemove = (e) => {
    e.stopPropagation();
    if (disabled) return;
    if (onRemove) onRemove(e);
  };

  const classes = [
    'tag-item',
    selectable && 'is-selectable',
    selectable && selected && 'is-selected',
    disabled && 'is-disabled',
    variant !== 'default' && `tag-${variant}`,
    size === 'sm' && 'tag-sm',
    className
  ].filter(Boolean).join(' ');

  // Determine aria-pressed if acting as toggle button
  const isToggleButton = selectable && role === 'button' && typeof selected === 'boolean';

  return (
    <span
      id={id}
      className={classes}
      role={role}
      tabIndex={selectable && !disabled ? 0 : -1}
      aria-label={ariaLabel || label}
      aria-disabled={disabled || undefined}
      aria-selected={selectable && role === 'option' ? selected : undefined}
      aria-pressed={isToggleButton ? selected : undefined}
      onClick={handleClick}
      onKeyDown={(e) => {
        if (!selectable) return;
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          handleClick(e);
        }
        if (removable && onRemove && (e.key === 'Backspace' || e.key === 'Delete')) {
          handleRemove(e);
        }
      }}
      {...rest}
    >
      {icon && <span className="tag-icon" aria-hidden="true">{icon}</span>}
      <span className="tag-label">{label}</span>
      {removable && onRemove && (
        <button
          type="button"
            className="tag-remove"
          onClick={handleRemove}
          aria-label={`Remove ${label}`}
          disabled={disabled}
        >
          ×
        </button>
      )}
    </span>
  );
};

TagItem.propTypes = {
  label: PropTypes.string.isRequired,
  selected: PropTypes.bool,
  selectable: PropTypes.bool,
  disabled: PropTypes.bool,
  onClick: PropTypes.func,
  onRemove: PropTypes.func,
  removable: PropTypes.bool,
  size: PropTypes.oneOf(['sm', 'md']),
  variant: PropTypes.oneOf(['default', 'accent', 'success', 'warning', 'error']),
  icon: PropTypes.node,
  className: PropTypes.string,
  id: PropTypes.string,
  role: PropTypes.string,
  'aria-label': PropTypes.string
};

export default TagItem;
