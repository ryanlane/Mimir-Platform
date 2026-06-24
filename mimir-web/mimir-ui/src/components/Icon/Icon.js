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
import * as LucideIcons from 'lucide-react';

// Export a curated list of icons currently used in the project (update as needed)
export const PROJECT_ICON_NAMES = [
  // Navigation
  'Home', 'Layers', 'Tv', 'MonitorSpeaker', 'Settings',
  // Data / system actions
  'Database', 'Download', 'RefreshCw', 'Send', 'Trash2', 'Wifi',
  // Links
  'Link', 'Link2', 'Unlink',
  // Media / volume
  'Volume2', 'VolumeX',
  // Misc / feature pages
  'Rocket', 'Globe2'
];

/**
 * Icon component - lightweight wrapper over lucide-react icons.
 * Defaults to CSS variable driven color for theme consistency.
 *
 * Props:
 *  - name (string): icon name matching exported lucide icon (case-insensitive convenience)
 *  - size (number): icon size (default 24)
 *  - color (string): stroke color; defaults to `var(--color-icon, currentColor)` if not provided
 *  - strokeWidth (number): stroke width (default 2)
 *  - className (string)
 *  - icon (ReactNode): optional direct element override (if provided, name is ignored)
 */
export function Icon({ name, size = 24, color, strokeWidth = 2, className = '', icon, ...rest }) {
  const effectiveColor = color || 'var(--color-icon, currentColor)';
  if (icon) {
    return React.cloneElement(icon, { size, color: effectiveColor, strokeWidth, className, ...rest });
  }
  if (!name) return null;
  // Support kebab-case or snake_case names by converting to PascalCase
  const toPascal = (str) => str
    .replace(/[-_]+/g, ' ')      // separators to spaces
    .replace(/\s+(.)/g, (_, c) => c.toUpperCase()) // capitalize after space
    .replace(/^(.)/, (m) => m.toUpperCase())        // capitalize first
    .replace(/\s/g, '');
  const normalized = toPascal(name);
  const IconComponent = LucideIcons[name] || LucideIcons[normalized];
  const Fallback = LucideIcons.HelpCircle || (() => <span style={{fontSize:size}}>?</span>);
  const Render = IconComponent || Fallback;
  return <Render size={size} color={effectiveColor} strokeWidth={strokeWidth} className={className} {...rest} />;
}

export default Icon;
