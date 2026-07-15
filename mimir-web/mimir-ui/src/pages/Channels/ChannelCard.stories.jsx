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
import ChannelCard from './ChannelCard';

// Helper builders
const baseChannel = (overrides = {}) => ({
  id: 'weather',
  name: 'Weather Channel',
  description: 'Provides daily and hourly forecast imagery.',
  icon: 'cloud',
  version: '1.4.2',
  status: {
    lastUpdate: new Date().toISOString(),
    usingFallback: false,
    ...overrides.status,
  },
  ...overrides,
});

const mkStatus = (type, text) => ({ type, text });

const healthy = { healthy: true };
const unhealthy = { healthy: false, error: 'Timeout contacting upstream API' };

const manifestV21 = {
  schemaVersion: '2.1',
  hasUI: true,
  ui: [{ id: 'config' }, { id: 'advanced' }],
  permissions: ['network', 'cache'],
};

/**
 * Stories for ChannelCard component.
 */
const meta = {
  title: 'Components/ChannelCard',
  component: ChannelCard,
  tags: ['autodocs'],
  parameters: {
    docs: {
      description: {
        component: 'Displays a single channel with status, optional health indicator, v2.1 manifest details, and actions.',
      },
    },
  },
  argTypes: {
    v21Supported: { control: 'boolean', description: 'Whether to render v2.1 manifest-related UI.' },
    channelHealthSupported: { control: 'boolean', description: 'Enable health indicator display.' },
    statusInfo: { control: false },
    manifestData: { control: false },
    health: { control: false },
    onOpenSettings: { action: 'open-settings', description: 'Called when the Settings button is clicked.' },
  },
  decorators: [
    (Story) => (
      <div style={{ maxWidth: 420 }}>
        <Story />
      </div>
    ),
  ],
};
export default meta;

export const Active = {
  args: {
    channel: baseChannel(),
    statusInfo: mkStatus('success', 'Active'),
    health: healthy,
    manifestData: manifestV21,
    v21Supported: true,
    channelHealthSupported: true,
  },
};

export const WithError = {
  args: {
    channel: baseChannel({
      status: {
        lastUpdate: new Date(Date.now() - 15 * 60 * 1000).toISOString(),
        lastError: 'HTTP 503 from upstream provider',
      },
    }),
    statusInfo: mkStatus('error', 'Error occurred'),
    health: unhealthy,
    manifestData: manifestV21,
    v21Supported: true,
    channelHealthSupported: true,
  },
  parameters: {
    docs: { description: { story: 'Shows an error state with health failing and manifest data visible.' } },
  },
};

export const UsingFallbackImage = {
  args: {
    channel: baseChannel({
      status: {
        lastUpdate: new Date(Date.now() - 2 * 60 * 1000).toISOString(),
        usingFallback: true,
      },
    }),
    statusInfo: mkStatus('warning', 'Using fallback image'),
    health: healthy,
    manifestData: manifestV21,
    v21Supported: true,
    channelHealthSupported: true,
  },
};

export const WithoutV21Support = {
  args: {
    channel: baseChannel({ version: '1.3.0' }),
    statusInfo: mkStatus('success', 'Active'),
    health: healthy,
    manifestData: undefined,
    v21Supported: false,
    channelHealthSupported: true,
  },
  parameters: { docs: { description: { story: 'Channel displayed without v2.1 manifest enhancements.' } } },
};

export const NoHealthInfo = {
  args: {
    channel: baseChannel(),
    statusInfo: mkStatus('success', 'Active'),
    health: undefined,
    manifestData: manifestV21,
    v21Supported: true,
    channelHealthSupported: false,
  },
  parameters: { docs: { description: { story: 'Health section suppressed when health support disabled or unavailable.' } } },
};

export const Disabled = {
  args: {
    channel: baseChannel({ enabled: false }),
    statusInfo: mkStatus('success', 'Active'),
    health: healthy,
    manifestData: manifestV21,
    v21Supported: true,
    channelHealthSupported: true,
  },
  parameters: { docs: { description: { story: 'Disabled source: dimmed card with a gray status dot.' } } },
};

export const DevChannel = {
  args: {
    channel: baseChannel({
      id: 'com.example.dev-weather',
      name: 'Weather (local)',
      dev: true,
      dev_path: '/home/dev/mimir-source-weather',
    }),
    statusInfo: mkStatus('success', 'Active'),
    health: healthy,
    manifestData: undefined,
    v21Supported: false,
    channelHealthSupported: true,
    onReloadDev: () => {},
    onUnlinkDev: () => {},
  },
  parameters: { docs: { description: { story: 'Dev-linked source with Dev badge, source path, and reload/unlink actions.' } } },
};
