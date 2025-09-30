import React, { useEffect, useState } from 'react';
import { Download, X } from 'lucide-react';
import { useInstallPrompt } from '../../hooks/useInstallPrompt';
import './AddToHomeScreenNudge.css';
import Button from '../Button/Button';

/**
 * A2HS Nudge Component
 * Appears when beforeinstallprompt fires (captured by hook) and user hasn't dismissed.
 */
export const AddToHomeScreenNudge = ({ onInstalled }) => {
  const { canInstall, promptInstall, installed, dismissed, resetDismissed } = useInstallPrompt();
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (canInstall) {
      setVisible(true);
    }
  }, [canInstall]);

  useEffect(() => {
    if (installed) {
      setVisible(false);
      if (onInstalled) onInstalled();
    }
  }, [installed, onInstalled]);

  if (!visible || dismissed) return null;

  return (
    <div className="a2hs-nudge" role="dialog" aria-label="Install Mimir app">
      <div className="a2hs-content">
        <div className="a2hs-text">
          <strong>Install Mimir</strong>
          <span className="a2hs-sub">Get faster access & offline support</span>
        </div>
        <div className="a2hs-actions">
          <Button variant="primary" size="sm" onClick={async () => {
              const result = await promptInstall();
              if (result.outcome === 'dismissed') {
                // Re-hide but allow future trigger after manual reset/interval
                setVisible(false);
                setTimeout(resetDismissed, 7 * 24 * 60 * 60 * 1000); // allow again in a week
              }
            }}>
            Install
          </Button>

          <Button variant="ghost" size="sm" aria-label="Dismiss install" onClick={() => {
              setVisible(false);
              // Reset after some time
              setTimeout(resetDismissed, 3 * 24 * 60 * 60 * 1000);
            }}
          >
            <X size={16} />
          </Button>
        </div>
      </div>
    </div>
  );
};

export default AddToHomeScreenNudge;
