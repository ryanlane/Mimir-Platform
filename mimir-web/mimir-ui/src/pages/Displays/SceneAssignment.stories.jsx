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
import SceneAssignment from './SceneAssignment';

export default {
  title: 'Pages/Displays/SceneAssignment',
  component: SceneAssignment,
  tags: ['autodocs'],
  parameters: {
    layout: 'centered',
    docs: {
      description: {
        component: 'Modal component for assigning (or unassigning) a scene to a display. This story uses a mocked API layer so it can run without a backend.'
      }
    }
  },
  argTypes: {
    onClose: { action: 'close', description: 'Called when user clicks Cancel or closes modal' },
    onSuccess: { action: 'success', description: 'Called with (displayId, sceneId) after successful assignment/unassignment' }
  }
};

// --- Mock API ---------------------------------------------------------------
// We shallow patch the imported api module used inside the component.
const mockScenes = [
  { id: '100', name: 'Sales Loop', channels: [{ channel_id: 'spotify' }] },
  { id: '101', name: 'Lobby Loop', channels: [{ channel_id: 'earth-images' }, { channel_id: 'spotify' }] },
  { id: '102', name: 'Metrics', channels: [{ channel_id: 'stats' }] },
  { id: '103', name: 'Highlights', channels: [{ channel_id: 'photos' }], overlay: { overlays: [{ id: 'clock' }] } }
];

const delay = (ms) => new Promise(r => setTimeout(r, ms));

const mockApi = {
  getScenes: async () => { await delay(300); return { data: { scenes: mockScenes } }; },
  assignSceneToDisplay: async (displayId, sceneId) => { await delay(500); return { data: { displayId, sceneId } }; },
  unassignSceneFromDisplay: async (displayId) => { await delay(300); return { data: { displayId } }; }
};

try {
  // eslint-disable-next-line global-require
  const realApiModule = require('../../services/api');
  if (realApiModule?.api) {
    Object.assign(realApiModule.api, mockApi);
  }
} catch (e) {
  // ignore; SB env might not allow patching
}

// Base display stub matching required fields used by component
const baseDisplay = {
  id: 'disp-1',
  name: 'Lobby Panel',
  displayType: 'registered',
  resolution: [1920, 1080],
  orientation: 'landscape',
  location: 'Lobby',
  assigned_scene_id: '100',
  assigned_scene_name: 'Sales Loop'
};

const Template = (args) => <SceneAssignment {...args} />;

export const Default = Template.bind({});
Default.args = {
  display: baseDisplay
};

export const Unassigned = Template.bind({});
Unassigned.args = {
  display: { ...baseDisplay, assigned_scene_id: null, assigned_scene_name: null }
};

export const DiscoveredDisplay = Template.bind({});
DiscoveredDisplay.args = {
  display: { ...baseDisplay, displayType: 'discovered', name: 'New Device', assigned_scene_id: null, assigned_scene_name: null }
};

export const LoadingState = (args) => {
  // For loading state we temporarily replace getScenes with a slower promise
  const slowApi = {
    getScenes: async () => { await delay(2500); return { data: { scenes: mockScenes } }; },
    assignSceneToDisplay: mockApi.assignSceneToDisplay,
    unassignSceneFromDisplay: mockApi.unassignSceneFromDisplay
  };
  try {
    const realApiModule = require('../../services/api');
    if (realApiModule?.api) Object.assign(realApiModule.api, slowApi);
  } catch {}
  return <SceneAssignment {...args} />;
};
LoadingState.args = {
  display: baseDisplay
};
LoadingState.parameters = {
  docs: { description: { story: 'Shows the loading spinner for an extended period (2.5s simulated).' } }
};

export const ErrorState = (args) => {
  const errorApi = {
    getScenes: async () => { await delay(300); throw new Error('Backend unreachable'); },
    assignSceneToDisplay: mockApi.assignSceneToDisplay,
    unassignSceneFromDisplay: mockApi.unassignSceneFromDisplay
  };
  try {
    const realApiModule = require('../../services/api');
    if (realApiModule?.api) Object.assign(realApiModule.api, errorApi);
  } catch {}
  return <SceneAssignment {...args} />;
};
ErrorState.args = {
  display: baseDisplay
};
ErrorState.parameters = {
  docs: { description: { story: 'Demonstrates error banner when scenes fail to load.' } }
};
