import React from 'react';
import './Button.css';
import Icon from '../Icon/Icon';

const Button = ({ 
  children, 
  variant = 'default', 
  size = 'md', 
  disabled = false, 
  loading = false, 
  onClick, 
  type = 'button',
  className = '',
  icon, // string icon name or React element
  iconPosition = 'left', // 'left' | 'right'
  iconSize = 16,
  'aria-label': ariaLabel,
  ...props 
}) => {
  const baseClass = 'btn';
  const variantClass = variant !== 'default' ? `btn-${variant}` : '';
  const sizeClass = size !== 'md' ? `btn-${size}` : '';
  const loadingClass = loading ? 'btn-loading' : '';
  const hasIcon = !!icon;
  const iconOnly = hasIcon && !children;
  
  const classes = [baseClass, variantClass, sizeClass, loadingClass, hasIcon ? 'btn-with-icon' : '', iconOnly ? 'btn-icon-only' : '', className]
    .filter(Boolean)
    .join(' ');

  let iconNode = null;
  if (hasIcon) {
    if (React.isValidElement(icon)) {
      iconNode = React.cloneElement(icon, { size: icon.props.size || iconSize, 'aria-hidden': true });
    } else if (typeof icon === 'string') {
      iconNode = <Icon name={icon} size={iconSize} aria-hidden="true" />;
    }
  }

  // Accessibility: if icon only, require aria-label
  if (process.env.NODE_ENV !== 'production') {
    if (iconOnly && !ariaLabel) {
      // eslint-disable-next-line no-console
      console.warn('[Button] Icon-only button should have an accessible label via aria-label.');
    }
  }

  return (
    <button
      type={type}
      className={classes}
      disabled={disabled || loading}
      onClick={onClick}
      aria-label={ariaLabel}
      {...props}
    >
      {loading && <div className="btn-spinner" />}
      {iconNode && iconPosition === 'left' && (
        <span className={`btn-icon btn-icon-left ${loading ? 'btn-content-loading' : ''}`}>{iconNode}</span>
      )}
      {children && <span className={loading ? 'btn-content-loading' : ''}>{children}</span>}
      {iconNode && iconPosition === 'right' && (
        <span className={`btn-icon btn-icon-right ${loading ? 'btn-content-loading' : ''}`}>{iconNode}</span>
      )}
    </button>
  );
};

export default Button;
