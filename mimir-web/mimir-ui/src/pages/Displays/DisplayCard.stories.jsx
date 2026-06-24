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

import React from 'react';
import DisplayCard from './DisplayCard';

export default {
  title: 'Pages/Displays/DisplayCard',
  component: DisplayCard,
  parameters: {
    layout: 'centered'
  },
  tags: ['autodocs'],
  argTypes: {
    // Hide internal implementation prop so users only tweak display data
    apiClient: { table: { disable: true } }
  }
};

// Internal mock API client (not exposed as a controllable arg)
const mockApi = {
  getPersistedLastImage: async () => ({ data: { thumbnail_url: null, image_url: null } }),
  getScene: async (id) => ({ data: { id, name: 'Sample Scene', update_strategy: 'interval', schedule: '*/5 * * * *' } }),
  getSceneSchedules: async () => ({ data: [{ job_id: 'job-1' }] }),
  getSchedulerJob: async () => ({ data: { id: 'job-1', enabled: true, freq_unit: 'minutes', approx_interval_seconds: 300 } }),
  triggerSchedulerJob: async () => ({}),
  getDisplayImageUrl: (id) => `https://picsum.photos/seed/${id}/600/400`
};

const baseDisplay = {
  id: 1,
  name: 'Lobby Panel',
  is_online: true,
  displayType: 'registered',
  description: 'Primary lobby status panel',
  assigned_scene_id: 22,
  assigned_scene_name: 'Rotating Highlights',
  resolution: [1920, 1080],
  orientation: 'landscape',
  refresh_rate_hz: 60,
  last_seen: new Date().toISOString(),
  tags: ['lobby', 'public'],
  current_image_url: true
};

// Template always injects mockApi so story consumers don't need to know about it
const Template = (args) => (
  <div style={{ maxWidth: 420 }}>
    <DisplayCard {...args} apiClient={mockApi} />
  </div>
);

export const Online = Template.bind({});
Online.args = {
  display: baseDisplay,
  onAssignScene: () => {},
  onRefresh: () => {}
};

export const Offline = Template.bind({});
Offline.args = {
  display: { ...baseDisplay, is_online: false, last_seen: new Date(Date.now() - 3600 * 1000).toISOString() },
  onAssignScene: () => {},
  onRefresh: () => {}
};

export const NoScene = Template.bind({});
NoScene.args = {
  display: { ...baseDisplay, assigned_scene_id: null, assigned_scene_name: null },
  onAssignScene: () => {},
  onRefresh: () => {}
};

export const ManualUpdateInProgress = Template.bind({});
ManualUpdateInProgress.args = {
  display: baseDisplay,
  // Override behavior via a local wrapper; DisplayCard only receives apiClient internally
  apiClient: {
    ...mockApi,
    triggerSchedulerJob: async () => new Promise(res => setTimeout(res, 1500))
  },
  onAssignScene: () => {},
  onRefresh: () => {}
};

// Variant: Registered display styling
export const RegisteredDisplay = Template.bind({});
RegisteredDisplay.args = {
  display: { ...baseDisplay, displayType: 'registered' },
  onAssignScene: () => {},
  onRefresh: () => {}
};

// Variant: Discovered display styling
export const DiscoveredDisplay = Template.bind({});
DiscoveredDisplay.args = {
  display: { ...baseDisplay, displayType: 'discovered' },
  onAssignScene: () => {},
  onRefresh: () => {}
};
