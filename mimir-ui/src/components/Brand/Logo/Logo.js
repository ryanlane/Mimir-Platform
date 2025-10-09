import React from 'react';
import { ReactComponent as MimirLogoSvg } from '../../../assets/branding/mimir_circle.svg';
import './Logo.css';

/**
 * Brand Logo component.
 * Provides flexible sizing, monochrome/themed variants, and accessible labeling.
 */
const Logo = ({ size = 36, title = 'Mimir', decorative = false, className = '', variant = 'default' }) => {
  const ariaProps = decorative
    ? { 'aria-hidden': true }
    : { role: 'img', 'aria-label': title };

  return (
    <span
      className={`mimir-logo-wrapper variant-${variant} ${className}`.trim()}
      style={{ width: size, height: size }}
    >
      <MimirLogoSvg width={size} height={size} {...ariaProps} />
    </span>
  );
};

export default Logo;
