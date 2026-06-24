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

import { useEffect, useState, useCallback } from 'react';

/**
 * useSystemTheme
 * Manages theme preference with three modes: 'light' | 'dark' | 'system'.
 * Persists user choice in localStorage under 'mimir-theme-preference'.
 * Exposes resolvedTheme (actual applied) and preference (user selection).
 */
export function useSystemTheme() {
  const STORAGE_KEY = 'mimir-theme-preference';
  const VALID = ['light', 'dark', 'system'];

  const getSystem = () => (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');

  const getInitialPreference = () => {
    if (typeof window === 'undefined') return 'system';
    const stored = localStorage.getItem(STORAGE_KEY);
    return VALID.includes(stored) ? stored : 'system';
  };

  const [preference, setPreference] = useState(getInitialPreference);
  const [resolvedTheme, setResolvedTheme] = useState(() => (preference === 'system' ? getSystem() : preference));

  // Update resolved theme whenever preference changes or system changes (if preference is system)
  const recompute = useCallback(() => {
    const next = preference === 'system' ? getSystem() : preference;
    setResolvedTheme(next);
  }, [preference]);

  useEffect(() => {
    if (preference === 'system') {
      const media = window.matchMedia('(prefers-color-scheme: dark)');
      const handler = () => recompute();
      media.addEventListener('change', handler);
      return () => media.removeEventListener('change', handler);
    }
  }, [preference, recompute]);

  useEffect(() => {
    recompute();
  }, [preference, recompute]);

  // Persist preference
  useEffect(() => {
    try { localStorage.setItem(STORAGE_KEY, preference); } catch {}
  }, [preference]);

  // Reflect on documentElement for CSS overrides and UA styling hints
  useEffect(() => {
    if (preference === 'system') {
      delete document.documentElement.dataset.theme;
    } else {
      document.documentElement.dataset.theme = resolvedTheme;
    }
  }, [resolvedTheme, preference]);

  const setThemePreference = (value) => {
    if (!VALID.includes(value)) return;
    setPreference(value);
  };

  const clearPreference = () => {
    setPreference('system');
  };

  return { preference, resolvedTheme, setThemePreference, clearPreference };
}
