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
