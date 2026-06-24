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
import SceneCard from './SceneCard';

export default {
  title: 'Components/SceneCard',
  component: SceneCard,
  tags: ['autodocs'],
  argTypes: {
    loadingDisplay: { control: 'boolean' }
  },
  parameters: {
    layout: 'centered',
    docs: {
      description: {
        component: 'Card representation of a Scene with channels, distribution controls, schedule status, and actions.'
      }
    }
  }
};

const Template = (args) => <div style={{ maxWidth: 380 }}><SceneCard {...args} /></div>;

const baseScene = {
  id: 'scene-1',
  name: 'Living Room Display',
  channels: [
    'photo-frame',
    { channel_id: 'weather', subchannel_id: 'regional' },
    { channel_id: 'news', subchannel_id: 'world' }
  ],
  distribution_mode: 'MIRROR',
  update_strategy: 'push'
};

const channels = [
  { id: 'photo-frame', name: 'Photo Frame' },
  { id: 'weather', name: 'Weather' },
  { id: 'news', name: 'News Feed' }
];

const channelManifests = {
  weather: { galleries: [{ id: 'regional', name: 'Regional Weather', image_count: 12 }] },
  news: { galleries: [{ id: 'world', name: 'World Headlines', image_count: 32 }] }
};

export const Default = {
  render: Template,
  args: {
    scene: baseScene,
    channels,
    channelManifests,
    scheduleStatus: { hasSchedule: true, status: 'Every 5 minutes', count: 1 },
    loadingDisplay: false
  }
};

export const NoSchedule = {
  render: Template,
  args: {
    scene: { ...baseScene, id: 'scene-2', name: 'Kitchen Display' },
    channels,
    channelManifests,
    scheduleStatus: { hasSchedule: false },
    loadingDisplay: false
  },
  parameters: { docs: { description: { story: 'Scene without any active schedule.' } } }
};

export const LoadingDisplay = {
  render: Template,
  args: {
    scene: { ...baseScene, id: 'scene-3', name: 'Bedroom Display' },
    channels,
    channelManifests,
    scheduleStatus: { hasSchedule: true, status: 'Every 10 minutes', count: 1 },
    loadingDisplay: true
  },
  parameters: { docs: { description: { story: 'Display button is in loading state (e.g., fetching preview).' } } }
};

export const ManyChannels = {
  render: Template,
  args: {
    scene: {
      ...baseScene,
      id: 'scene-4',
      name: 'Operations Wall',
      channels: [
        'photo-frame',
        { channel_id: 'weather', subchannel_id: 'regional' },
        { channel_id: 'news', subchannel_id: 'world' },
        'metrics',
        'alerts'
      ]
    },
    channels: [
      ...channels,
      { id: 'metrics', name: 'Metrics' },
      { id: 'alerts', name: 'Alerts' }
    ],
    channelManifests,
    scheduleStatus: { hasSchedule: true, status: 'Every 30 minutes', count: 2 },
    loadingDisplay: false
  },
  parameters: { docs: { description: { story: 'Example with more channels to test wrapping and layout.' } } }
};
