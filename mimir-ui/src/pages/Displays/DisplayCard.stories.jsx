import React from 'react';
import DisplayCard from './DisplayCard';

export default {
  title: 'Pages/Displays/DisplayCard',
  component: DisplayCard,
  parameters: {
    layout: 'centered'
  },
  tags: ['autodocs'],
  argTypes: {}
};

// Simple mock api client matching methods used in component
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

const Template = (args) => <div style={{ maxWidth: 420 }}><DisplayCard {...args} /></div>;

export const Online = Template.bind({});
Online.args = {
  display: baseDisplay,
  apiClient: mockApi,
  onAssignScene: () => {},
  onRefresh: () => {}
};

export const Offline = Template.bind({});
Offline.args = {
  display: { ...baseDisplay, is_online: false, last_seen: new Date(Date.now() - 3600 * 1000).toISOString() },
  apiClient: mockApi,
  onAssignScene: () => {},
  onRefresh: () => {}
};

export const NoScene = Template.bind({});
NoScene.args = {
  display: { ...baseDisplay, assigned_scene_id: null, assigned_scene_name: null },
  apiClient: mockApi,
  onAssignScene: () => {},
  onRefresh: () => {}
};

export const ManualUpdateInProgress = Template.bind({});
ManualUpdateInProgress.args = {
  display: baseDisplay,
  apiClient: {
    ...mockApi,
    triggerSchedulerJob: async () => new Promise(res => setTimeout(res, 1500))
  },
  onAssignScene: () => {},
  onRefresh: () => {}
};
