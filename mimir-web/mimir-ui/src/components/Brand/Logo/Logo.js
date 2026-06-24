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
