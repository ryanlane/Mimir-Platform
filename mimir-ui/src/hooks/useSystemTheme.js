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
    document.documentElement.dataset.theme = resolvedTheme;
  }, [resolvedTheme]);

  const setThemePreference = (value) => {
    if (!VALID.includes(value)) return;
    setPreference(value);
  };

  const clearPreference = () => {
    setPreference('system');
  };

  return { preference, resolvedTheme, setThemePreference, clearPreference };
}
