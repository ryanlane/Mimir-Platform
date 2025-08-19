import React from 'react';
import './Button.css';

const Button = ({ 
  children, 
  variant = 'default', 
  size = 'md', 
  disabled = false, 
  loading = false, 
  onClick, 
  type = 'button',
  className = '',
  ...props 
}) => {
  const baseClass = 'btn';
  const variantClass = variant !== 'default' ? `btn-${variant}` : '';
  const sizeClass = size !== 'md' ? `btn-${size}` : '';
  const loadingClass = loading ? 'btn-loading' : '';
  
  const classes = [baseClass, variantClass, sizeClass, loadingClass, className]
    .filter(Boolean)
    .join(' ');

  return (
    <button
      type={type}
      className={classes}
      disabled={disabled || loading}
      onClick={onClick}
      {...props}
    >
      {loading && <div className="btn-spinner" />}
      <span className={loading ? 'btn-content-loading' : ''}>{children}</span>
    </button>
  );
};

export default Button;
