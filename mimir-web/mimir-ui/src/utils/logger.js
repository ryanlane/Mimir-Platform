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

// Console logging utility that respects verbosity settings
// Usage: import { logger } from './utils/logger'; logger.debug('message');

class Logger {
  constructor() {
    this.verbosityLevels = {
      'silent': 0,
      'error': 1,
      'warning': 2,
      'normal': 3,
      'verbose': 4,
      'debug': 5
    };
  }

  getSettings() {
    return window.mimirConsoleSettings || {
      verbosity: 'normal',
      showWebSocketEvents: true,
      showAPIRequests: true,
      showSceneEvents: true,
      showDisplayEvents: true
    };
  }

  shouldLog(level, category = null) {
    const settings = this.getSettings();
    const currentLevel = this.verbosityLevels[settings.verbosity] || 3;
    const messageLevel = this.verbosityLevels[level] || 3;

    // Check verbosity level
    if (messageLevel > currentLevel) {
      return false;
    }

    // Check category-specific settings
    if (category && settings[category] === false) {
      return false;
    }

    return true;
  }

  log(level, message, category = null, ...args) {
    if (!this.shouldLog(level, category)) {
      return;
    }

    const prefix = category ? `[${category.replace('show', '').replace('Events', '')}]` : '';
    const timestamp = new Date().toLocaleTimeString();
    
    switch (level) {
      case 'error':
        console.error(`${timestamp} 🔴 ${prefix}`, message, ...args);
        break;
      case 'warning':
        console.warn(`${timestamp} 🟡 ${prefix}`, message, ...args);
        break;
      case 'debug':
        console.debug(`${timestamp} 🔍 ${prefix}`, message, ...args);
        break;
      case 'verbose':
        console.log(`${timestamp} 📝 ${prefix}`, message, ...args);
        break;
      default:
        console.log(`${timestamp} ℹ️ ${prefix}`, message, ...args);
    }
  }

  // Convenience methods
  error(message, category = null, ...args) {
    this.log('error', message, category, ...args);
  }

  warning(message, category = null, ...args) {
    this.log('warning', message, category, ...args);
  }

  info(message, category = null, ...args) {
    this.log('normal', message, category, ...args);
  }

  debug(message, category = null, ...args) {
    this.log('debug', message, category, ...args);
  }

  verbose(message, category = null, ...args) {
    this.log('verbose', message, category, ...args);
  }

  // Category-specific logging methods
  websocket(message, ...args) {
    this.log('normal', message, 'showWebSocketEvents', ...args);
  }

  api(message, ...args) {
    this.log('normal', message, 'showAPIRequests', ...args);
  }

  scene(message, ...args) {
    this.log('normal', message, 'showSceneEvents', ...args);
  }

  display(message, ...args) {
    this.log('normal', message, 'showDisplayEvents', ...args);
  }
}

export const logger = new Logger();

// Also export individual methods for convenience
export const { error, warning, info, debug, verbose, websocket, api, scene, display } = logger;
