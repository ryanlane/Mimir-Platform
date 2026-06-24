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
import { Sun, Moon, Monitor } from 'lucide-react';
import { useWebSocket } from '../../hooks/useWebSocket';
import { ThemeContext } from '../../App';
import './StatusBar.css';

const THEME_CYCLE = ['system', 'light', 'dark'];
const THEME_ICONS = { system: Monitor, light: Sun, dark: Moon };

const StatusBar = () => {
  const { isConnected } = useWebSocket();
  const themeCtx = useContext(ThemeContext);
  const { preference = 'system', setThemePreference } = themeCtx || {};

  const cycleTheme = () => {
    if (!setThemePreference) return;
    const idx = THEME_CYCLE.indexOf(preference);
    setThemePreference(THEME_CYCLE[(idx + 1) % THEME_CYCLE.length]);
  };

  const ThemeIcon = THEME_ICONS[preference] || Monitor;

  return (
    <div className="status-bar">
      <div className="status-bar-left">
        <span
          className={`status-bar-dot ${isConnected ? 'status-bar-dot--live' : 'status-bar-dot--offline'}`}
          title={isConnected ? 'WebSocket connected' : 'WebSocket disconnected'}
        />
        <span className="status-bar-ws-label">
          {isConnected ? 'Live' : 'Reconnecting…'}
        </span>
      </div>

      <div className="status-bar-center">
        <span className="status-bar-brand">mimir</span>
      </div>

      <div className="status-bar-right">
        <button
          className="status-bar-theme-btn"
          onClick={cycleTheme}
          title={`Theme: ${preference}`}
          aria-label={`Current theme: ${preference}. Click to cycle.`}
        >
          <ThemeIcon size={13} />
        </button>
      </div>
    </div>
  );
};

export default StatusBar;
