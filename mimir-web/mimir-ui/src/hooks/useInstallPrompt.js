import { useEffect, useState, useCallback } from 'react';

/**
 * useInstallPrompt
 * Captures the beforeinstallprompt event, defers it, and exposes a UI-friendly API.
 * Provides: canInstall, promptInstall(), dismissed, installed.
 */
export function useInstallPrompt() {
  const [deferredEvent, setDeferredEvent] = useState(null);
  const [installed, setInstalled] = useState(false);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    const handleBeforeInstall = (e) => {
      // Prevent the mini-infobar on mobile Chrome
      e.preventDefault();
      // Save the event for triggering later
      setDeferredEvent(e);
      window.dispatchEvent(new CustomEvent('mimir:a2hs-available'));
    };

    const handleInstalled = () => {
      setInstalled(true);
      setDeferredEvent(null);
      window.dispatchEvent(new CustomEvent('mimir:a2hs-installed'));
    };

    window.addEventListener('beforeinstallprompt', handleBeforeInstall);
    window.addEventListener('appinstalled', handleInstalled);
    return () => {
      window.removeEventListener('beforeinstallprompt', handleBeforeInstall);
      window.removeEventListener('appinstalled', handleInstalled);
    };
  }, []);

  const promptInstall = useCallback(async () => {
    if (!deferredEvent) return { outcome: 'unavailable' };
    deferredEvent.prompt();
    const choice = await deferredEvent.userChoice;
    if (choice.outcome === 'dismissed') {
      setDismissed(true);
    }
    if (choice.outcome === 'accepted') {
      setInstalled(true);
    }
    return choice;
  }, [deferredEvent]);

  const resetDismissed = () => setDismissed(false);

  return {
    canInstall: !!deferredEvent && !installed && !dismissed,
    installed,
    dismissed,
    promptInstall,
    resetDismissed
  };
}

export default useInstallPrompt;
