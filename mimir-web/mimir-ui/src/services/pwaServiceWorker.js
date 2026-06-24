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

// PWA / Service Worker management for Mimir UI

const PREF_KEY = 'mimir-pwa-enabled';

export function getPwaEnabledPreference() {
  try {
    return localStorage.getItem(PREF_KEY) === 'true';
  } catch {
    return false;
  }
}

export function setPwaEnabledPreference(enabled) {
  try {
    localStorage.setItem(PREF_KEY, String(!!enabled));
  } catch {
    // Best-effort
  }
}

export function canUseServiceWorker() {
  return typeof navigator !== 'undefined' && 'serviceWorker' in navigator;
}

export function shouldEnablePwa() {
  // Only enable in production builds to avoid dev caching problems.
  if (process.env.NODE_ENV !== 'production') return false;

  // Allow either a deployment-wide opt-in (env) or user opt-in (localStorage).
  if (process.env.REACT_APP_ENABLE_PWA === 'true') return true;
  return getPwaEnabledPreference();
}

export async function unregisterMimirServiceWorkers({ clearCaches = true } = {}) {
  if (!canUseServiceWorker()) return;

  try {
    const regs = await navigator.serviceWorker.getRegistrations();
    await Promise.all(regs.map(r => r.unregister()));
  } catch {
    // Best-effort
  }

  if (clearCaches && typeof caches !== 'undefined') {
    try {
      const keys = await caches.keys();
      // Only clear caches created by this app
      await Promise.all(keys.filter(k => k.startsWith('mimir')).map(k => caches.delete(k)));
    } catch {
      // Best-effort
    }
  }
}

export async function registerMimirServiceWorker() {
  if (!canUseServiceWorker()) return null;

  // CRA + Workbox InjectManifest outputs the custom SW at the root as /service-worker.js
  const swUrl = '/service-worker.js';

  const reg = await navigator.serviceWorker.register(swUrl);

  // Listen for updates to the service worker.
  reg.onupdatefound = () => {
    const installing = reg.installing;
    if (!installing) return;
    installing.onstatechange = () => {
      if (installing.state === 'installed') {
        if (navigator.serviceWorker.controller) {
          // New content is available; prompt for reload
          const detail = { type: 'SW_UPDATE_AVAILABLE' };
          window.dispatchEvent(new CustomEvent('mimir:sw-update', { detail }));
          console.log('[SW] Update available. Dispatching mimir:sw-update event.');
        } else {
          console.log('[SW] Content cached for offline use.');
        }
      }
    };
  };

  return reg;
}

export async function applyPwaModeOnLoad() {
  if (!canUseServiceWorker()) return;

  if (shouldEnablePwa()) {
    try {
      const reg = await registerMimirServiceWorker();
      if (reg) console.log('[SW] registered', reg.scope);
    } catch (err) {
      console.warn('[SW] registration failed', err);
    }

    // Optional: Listen for custom event to auto-update when user accepts.
    window.addEventListener('mimir:sw-skip-waiting', () => {
      if (navigator.serviceWorker?.controller) {
        navigator.serviceWorker.controller.postMessage({ type: 'SKIP_WAITING' });
      }
    });
  } else {
    // Ensure older registrations from previous builds don't break refresh.
    try {
      await unregisterMimirServiceWorkers({ clearCaches: true });
      console.log('[SW] disabled');
    } catch {
      // Best-effort
    }
  }
}
