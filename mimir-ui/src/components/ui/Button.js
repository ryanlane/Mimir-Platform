import React from 'react';

const Button = ({ 
  children, 
  variant = 'default', 
  size = 'md', 
  disabled = false, 
  onClick, 
  type = 'button',
  className = '',
  ...props 
}) => {
  const baseClasses = 'btn';
  const variantClasses = {
    default: '',
    primary: 'btn-primary',
    accent: 'btn-accent',
    success: 'btn-success',
    warning: 'btn-warning',
    error: 'btn-error'
  };
  const sizeClasses = {
    sm: 'btn-sm',
    md: '',
    lg: 'btn-lg'
  };

  const classes = [
    baseClasses,
    variantClasses[variant] || '',
    sizeClasses[size] || '',
    className
  ].filter(Boolean).join(' ');

  return (
    <button
      type={type}
      className={classes}
      disabled={disabled}
      onClick={onClick}
      {...props}
    >
      {children}
    </button>
  );
};

export default Button;
