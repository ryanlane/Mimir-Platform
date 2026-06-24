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

const LS_KEY = 'mimir-a2hs-dismissed-at';
const SUPPRESS_MS = 30 * 24 * 60 * 60 * 1000; // 30 days

function isDismissedRecently() {
  const ts = localStorage.getItem(LS_KEY);
  if (!ts) return false;
  return Date.now() - Number(ts) < SUPPRESS_MS;
}

export function useInstallPrompt() {
  const [deferredEvent, setDeferredEvent] = useState(null);
  const [installed, setInstalled] = useState(false);
  const [dismissed, setDismissed] = useState(() => isDismissedRecently());

  useEffect(() => {
    const handleBeforeInstall = (e) => {
      e.preventDefault();
      setDeferredEvent(e);
      window.dispatchEvent(new CustomEvent('mimir:a2hs-available'));
    };

    const handleInstalled = () => {
      setInstalled(true);
      setDeferredEvent(null);
      localStorage.removeItem(LS_KEY);
      window.dispatchEvent(new CustomEvent('mimir:a2hs-installed'));
    };

    window.addEventListener('beforeinstallprompt', handleBeforeInstall);
    window.addEventListener('appinstalled', handleInstalled);
    return () => {
      window.removeEventListener('beforeinstallprompt', handleBeforeInstall);
      window.removeEventListener('appinstalled', handleInstalled);
    };
  }, []);

  const dismiss = useCallback(() => {
    localStorage.setItem(LS_KEY, String(Date.now()));
    setDismissed(true);
  }, []);

  const promptInstall = useCallback(async () => {
    if (!deferredEvent) return { outcome: 'unavailable' };
    deferredEvent.prompt();
    const choice = await deferredEvent.userChoice;
    if (choice.outcome === 'dismissed') {
      dismiss();
    }
    if (choice.outcome === 'accepted') {
      setInstalled(true);
    }
    return choice;
  }, [deferredEvent, dismiss]);

  const resetDismissed = useCallback(() => {
    localStorage.removeItem(LS_KEY);
    setDismissed(false);
  }, []);

  return {
    canInstall: !!deferredEvent && !installed && !dismissed,
    installed,
    dismissed,
    promptInstall,
    dismiss,
    resetDismissed,
  };
}

export default useInstallPrompt;
