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

import React, { useState } from 'react';
import Displays from './Displays';

// Storybook meta configuration
export default {
  title: 'Pages/Displays/DisplaysPage',
  component: Displays,
  tags: ['autodocs'],
  parameters: {
    layout: 'fullscreen',
    docs: {
      description: {
        component: 'Full Displays management page with filters, real-time websocket simulation (mock), and display cards. This story uses a mocked API layer so no backend is required.'
      }
    }
  }
};

// --- Mocking Layer ---------------------------------------------------------
// We intercept the global api import used inside the page by providing a mock via globalThis.
// If the real code references imported `api`, this story relies on that module supporting
// an override (if not, you can adapt by adjusting the module resolution or refactoring
// the page to accept an injected api client prop).
// For now we just ensure minimal endpoints exist that the page calls.

// Generate deterministic mock displays
const makeDisplay = (id, overrides = {}) => ({
  id: id,
  name: `Display ${id}`,
  displayType: 'registered',
  is_online: id % 4 !== 0, // every 4th offline
  description: id % 3 === 0 ? 'Edge-mounted panel' : 'Standard panel',
  assigned_scene_id: id % 5 === 0 ? null : 100 + (id % 4),
  assigned_scene_name: id % 5 === 0 ? null : ['Sales Loop', 'Lobby Loop', 'Metrics', 'Highlights'][id % 4],
  resolution: [1920, 1080],
  orientation: 'landscape',
  refresh_rate_hz: 60,
  last_seen: new Date(Date.now() - (id * 65000)).toISOString(),
  tags: id % 2 === 0 ? ['primary'] : ['secondary'],
  current_image_url: id % 2 === 0 ? true : false
, ...overrides });

const MOCK_SCENES = [
  { id: 100, name: 'Sales Loop' },
  { id: 101, name: 'Lobby Loop' },
  { id: 102, name: 'Metrics' },
  { id: 103, name: 'Highlights' }
];

// Basic in-memory data set
let MOCK_DISPLAYS = Array.from({ length: 8 }, (_, i) => makeDisplay(i + 1));

// Simple mock API implementation used by the page
const mockApi = {
  getDisplays: async () => ({ data: MOCK_DISPLAYS }),
  getDiscoveryStatus: async () => ({ data: { running: true } }),
  getAssignmentStatus: async () => ({ data: { assignments: {} } }),
  getScenes: async () => ({ data: MOCK_SCENES }),
  approveDiscoveredDisplay: async () => ({}),
  rejectDiscoveredDisplay: async () => ({}),
  getPersistedLastImage: async (displayId) => ({ data: { image_url: `https://picsum.photos/seed/${displayId}/800/480`, thumbnail_url: `https://picsum.photos/seed/${displayId}/320/180` } }),
  getScene: async (id) => ({ data: { id, name: MOCK_SCENES.find(s => s.id === id)?.name || 'Scene', update_strategy: 'interval', schedule: '*/5 * * * *' } }),
  getSceneSchedules: async () => ({ data: [{ job_id: 'job-1' }] }),
  getSchedulerJob: async () => ({ data: { id: 'job-1', enabled: true, freq_unit: 'minutes', approx_interval_seconds: 300 } }),
  triggerSchedulerJob: async () => ({}),
  getDisplayImageUrl: (id) => `https://picsum.photos/seed/${id}/1024/640`,
  cache: { invalidate: () => {} }
};

// Patch the imported api module if possible (depends on bundler behavior in SB env)
try {
  // eslint-disable-next-line global-require
  const realApiModule = require('../../services/api');
  if (realApiModule && realApiModule.api) {
    Object.assign(realApiModule.api, mockApi); // shallow override methods
  }
} catch (e) {
  // silent: story fallback still renders because Displays imports already resolved
  // console.warn('Could not patch real api module for story', e);
}

// --- WebSocket Simulation ---------------------------------------------------
// We emit custom events periodically to simulate image update activity.
const startImageSimulation = () => {
  let counter = 0;
  const interval = setInterval(() => {
    counter += 1;
    const target = MOCK_DISPLAYS[(counter % MOCK_DISPLAYS.length)];
    if (!target) return;
    const newUrl = `https://picsum.photos/seed/${target.id}-${Date.now()}/800/480`;
    target.current_image_url = true; // mark available
    const eventDetail = {
      type: 'mqtt_message',
      data: {
        topic: `mimir/${target.id}/cmd`,
        payload: {
          type: 'display_image',
          image_url: newUrl,
          timestamp: new Date().toISOString()
        }
      }
    };
    window.dispatchEvent(new CustomEvent('websocket-message', { detail: eventDetail }));
  }, 5000);
  return () => clearInterval(interval);
};

// Template story wrapper that sets up simulation
const StoryWrapper = () => {
  const [simStarted, setSimStarted] = useState(false);
  React.useEffect(() => {
    if (!simStarted) {
      const stop = startImageSimulation();
      setSimStarted(true);
      return () => stop();
    }
  }, [simStarted]);
  return <Displays />;
};

export const Default = () => <StoryWrapper />;
Default.parameters = {
  docs: {
    description: {
      story: 'Default view of the Displays page with eight mocked displays. A simulated websocket pushes a new image update to a rotating display every 5 seconds to drive the activity indicator and timestamp updates.'
    }
  }
};

export const WithOfflineAndUnassigned = () => {
  // Mutate mock data for this story only (clone to avoid leaking to other stories)
  const original = MOCK_DISPLAYS;
  MOCK_DISPLAYS = original.map(d => ({ ...d }));
  MOCK_DISPLAYS[2].is_online = false; // third display offline
  MOCK_DISPLAYS[4].assigned_scene_id = null;
  MOCK_DISPLAYS[4].assigned_scene_name = null;
  return <StoryWrapper />;
};
WithOfflineAndUnassigned.parameters = {
  docs: {
    description: {
      story: 'Variant with an offline display and one unassigned to exercise filtering and conditional rendering paths.'
    }
  }
};
