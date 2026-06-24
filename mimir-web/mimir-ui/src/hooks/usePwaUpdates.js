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

// usePwaUpdates.js
// Centralized PWA update detection & prompting logic.
// Signals: visibility change, online, manual check, interval polling, optional version.json diff.
// Exposes: checkForUpdate(force), currentVersion ref on window.

import { useEffect, useRef, useCallback } from 'react';

const VERSION_POLL_INTERVAL = 3 * 60 * 1000; // 3 minutes
const REG_UPDATE_INTERVAL = 5 * 60 * 1000; // 5 minutes

export function usePwaUpdates({ onUpdateAvailable, onCritical }) {
  const lastRegUpdateRef = useRef(0);
  const inFlightRef = useRef(null);

  const fetchVersion = useCallback(async () => {
    try {
      const res = await fetch('/version.json', { cache: 'no-store' });
      if (!res.ok) return null;
      return res.json();
    } catch {
      return null;
    }
  }, []);

  const handlePotentialUpdate = useCallback((data) => {
    if (!data) return;
    const prev = window.__APP_VERSION__;
    const next = data.appVersion;
    if (!prev) {
      window.__APP_VERSION__ = next;
      return;
    }
    if (prev !== next) {
      window.__APP_VERSION__ = next; // Update stored version early
      if (data.critical) {
        onCritical?.(data);
      } else {
        onUpdateAvailable?.(data);
      }
    }
  }, [onCritical, onUpdateAvailable]);

  const runRegistrationUpdate = useCallback(async (force = false) => {
    if (!('serviceWorker' in navigator)) return;
    const now = Date.now();
    if (!force && now - lastRegUpdateRef.current < REG_UPDATE_INTERVAL) return;
    lastRegUpdateRef.current = now;
    try {
      const reg = await navigator.serviceWorker.getRegistration();
      await reg?.update();
    } catch {}
  }, []);

  const checkForUpdate = useCallback(async (force = false) => {
    if (inFlightRef.current) return inFlightRef.current;
    inFlightRef.current = (async () => {
      await runRegistrationUpdate(force);
      const versionData = await fetchVersion();
      handlePotentialUpdate(versionData);
      inFlightRef.current = null;
    })();
    return inFlightRef.current;
  }, [fetchVersion, handlePotentialUpdate, runRegistrationUpdate]);

  useEffect(() => {
    if (!('serviceWorker' in navigator)) return;

    // SW install/update detection
    navigator.serviceWorker.getRegistration().then(reg => {
      if (!reg) return;
      reg.addEventListener('updatefound', () => {
        const sw = reg.installing;
        if (!sw) return;
        sw.addEventListener('statechange', () => {
          if (sw.state === 'installed' && navigator.serviceWorker.controller) {
            // Dispatch global event consumed elsewhere for UI
            window.dispatchEvent(new Event('mimir:sw-update'));
          }
        });
      });
    });

    const onVis = () => {
      if (document.visibilityState === 'visible') checkForUpdate();
    };
    const onOnline = () => checkForUpdate(true);

    window.addEventListener('visibilitychange', onVis);
    window.addEventListener('online', onOnline);

    // Initial eager check
    checkForUpdate(true);

    // Version polling
    const pollId = setInterval(() => checkForUpdate(), VERSION_POLL_INTERVAL);

    return () => {
      window.removeEventListener('visibilitychange', onVis);
      window.removeEventListener('online', onOnline);
      clearInterval(pollId);
    };
  }, [checkForUpdate]);

  return { checkForUpdate };
}

export default usePwaUpdates;
