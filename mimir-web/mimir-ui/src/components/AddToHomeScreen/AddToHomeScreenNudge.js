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

import React, { useEffect, useState } from 'react';
import { Download, X } from 'lucide-react';
import { useInstallPrompt } from '../../hooks/useInstallPrompt';
import './AddToHomeScreenNudge.css';
import Button from '../Button/Button';

export const AddToHomeScreenNudge = ({ onInstalled }) => {
  const { canInstall, promptInstall, installed, dismissed, dismiss } = useInstallPrompt();
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (canInstall) setVisible(true);
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
          <span className="a2hs-sub">Get faster access &amp; offline support</span>
        </div>
        <div className="a2hs-actions">
          <Button variant="primary" size="sm" onClick={async () => {
            const result = await promptInstall();
            if (result.outcome === 'dismissed') setVisible(false);
          }}>
            <Download size={14} /> Install
          </Button>
          <Button variant="ghost" size="sm" aria-label="Dismiss install prompt" onClick={() => {
            dismiss();
            setVisible(false);
          }}>
            <X size={16} />
          </Button>
        </div>
      </div>
    </div>
  );
};

export default AddToHomeScreenNudge;
