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

import React, { useContext } from 'react';
import './ThemeSelector.css';
import { Sun, Moon, Monitor } from 'lucide-react';
import { ThemeContext } from '../../App';

/**
 * ThemeSelector component
 * Provides UI to pick between Light, Dark, or System theme modes.
 */
export function ThemeSelector() {
  const ctx = useContext(ThemeContext);
  const { preference, resolvedTheme, setThemePreference } = ctx || {};

  if (!ctx) {
    return <div style={{ fontSize: '0.8rem', opacity: 0.7 }}>Theme context unavailable</div>;
  }

  const options = [
    { value: 'system', label: 'System', icon: <Monitor size={16} /> },
    { value: 'light', label: 'Light', icon: <Sun size={16} /> },
    { value: 'dark', label: 'Dark', icon: <Moon size={16} /> }
  ];

  return (
    <fieldset className="theme-selector" aria-label="Color Theme">
      <legend className="theme-legend">Theme</legend>
      <div className="theme-options" role="radiogroup" aria-label="Theme mode">
        {options.map(opt => {
          const active = preference === opt.value;
          return (
            <label key={opt.value} className={`theme-option ${active ? 'active' : ''}`}>
              <input
                type="radio"
                name="theme-mode"
                value={opt.value}
                checked={active}
                onChange={() => setThemePreference(opt.value)}
                aria-checked={active}
                aria-label={opt.label + (opt.value === resolvedTheme ? ' (applied)' : '')}
              />
              <span className="option-icon">{opt.icon}</span>
              <span className="option-label">{opt.label}</span>
              {opt.value === preference && opt.value !== 'system' && (
                <span className="applied-indicator" aria-hidden="true">•</span>
              )}
            </label>
          );
        })}
      </div>
      <p className="theme-help text-tertiary">
        Current: <strong>{resolvedTheme}</strong>{preference === 'system' ? ' (following system)' : ''}
      </p>
    </fieldset>
  );
}

export default ThemeSelector;
