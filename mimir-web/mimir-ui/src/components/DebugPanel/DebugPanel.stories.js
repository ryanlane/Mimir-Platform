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
import DebugPanel from './DebugPanel';

/**
 * DebugPanel Stories
 *
 * Refactored DebugPanel now uses a Modal and supports controlled/uncontrolled patterns.
 * Stories demonstrate:
 *  - Uncontrolled toggle (default closed)
 *  - Auto run tests when opening
 *  - Controlled open state managed by parent
 *
 * Autodocs is enabled via the `tags: ['autodocs']` metadata so Storybook Docs
 * will extract this description and any component JSDoc.
 */
export default {
  title: 'Diagnostics/DebugPanel',
  component: DebugPanel,
  tags: ['autodocs'],
  parameters: {
    layout: 'fullscreen',
    docs: {
      description: {
        component: 'Diagnostic & connectivity aid for quickly validating API and network conditions.'
      }
    }
  }
};

export const Uncontrolled = {
  name: 'Uncontrolled Toggle',
  render: () => <DebugPanel showToggle toggleLabel="Debug" />
};

// Open state: automatically clicks the toggle button after mount
export const AutoRunOnOpen = {
  render: () => <DebugPanel showToggle toggleLabel="Diagnostics" autoRunOnOpen />,
  parameters: { docs: { description: { story: 'Automatically runs tests the first time the panel is opened.' } } }
};

export const Controlled = {
  render: () => {
    const [open, setOpen] = useState(true);
    useEffect(() => {
      // ensure persistence flag for demo
      localStorage.setItem('mimir-show-debug-panel', 'true');
    }, []);
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        <div>
          <button className="btn btn-sm" onClick={() => setOpen(o => !o)}>
            {open ? 'Close Panel' : 'Open Panel'}
          </button>
        </div>
        <DebugPanel open={open} onOpenChange={setOpen} showToggle={false} autoRunOnOpen />
      </div>
    );
  },
  parameters: { docs: { description: { story: 'Parent fully controls visibility using open/onOpenChange.' } } }
};
