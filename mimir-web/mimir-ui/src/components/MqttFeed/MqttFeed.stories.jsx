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

import MqttFeed from './MqttFeed';

// Helper to build Date objects consistently
const now = Date.now();
const mkTs = (offsetMs) => new Date(now - offsetMs);

// Sample payload variants
const sampleFeed = [
  {
    ts: mkTs(1_000),
    type: 'mqtt',
    payload: { topic: 'mimir/displays/display-01/status', payload: { online: true, scene: 'Welcome' } }
  },
  {
    ts: mkTs(5_000),
    type: 'mqtt',
    payload: { topic: 'mimir/displays/display-02/heartbeat', payload: { uptime: 512340, temp_c: 41.2 } }
  },
  {
    ts: mkTs(7_000),
    type: 'mqtt',
    payload: { topic: 'mimir/scenes/rotation/evt', payload: { scene: 'Announcements', action: 'activated' } }
  },
  {
    ts: mkTs(7_000),
    type: 'mqtt',
    payload: { topic: 'mimir/display-03/cmd', payload: {"type": "display_image", "image_url": "http://mimir.local:5000/media/swap/45510da1-68cc-4c30-b66d-fe21a9a988ae/display-pi-01/ac669a8cc2d94d99a6aa85bbb4a13746.jpg", "assignment_id": "display-colorf-1759423369", "timestamp": "2025-10-02T16:42:49.416536+00:00", "image_format": "jpeg"}
 }
  },
  {
    ts: mkTs(12_000),
    type: 'mqtt',
    payload: { topic: 'mimir/displays/display-03/status', payload: { online: false, last_seen: new Date(now - 65_000).toISOString() } }
  },
  {
    ts: mkTs(15_000),
    type: 'mqtt',
    payload: { topic: 'mimir/system/metrics/heartbeat', payload: { cpu: 0.31, mem: 0.55 } }
  },
];

/**
 * Stories for the MqttFeed component.
 * The component is stateful internally (filter / toggles) but receives a static `feed` array.
 * Use the Controls panel or code to adjust `maxItems` prop.
 */
const meta = {
  title: 'Realtime/MqttFeed',
  component: MqttFeed,
  tags: ['autodocs'],
  parameters: {
    docs: {
      description: {
        component: 'Live streaming view of forwarded MQTT -> WebSocket events with filtering, heartbeat toggle, and JSON collapsing.',
      },
    },
  },
  argTypes: {
    feed: {
      description: 'Array of feed entries: { ts: Date, type: string, payload: { topic, payload } }',
      control: false,
    },
    maxItems: {
      description: 'Hard cap on rendered items after filtering',
      control: { type: 'number' },
      defaultValue: 200,
    },
  },
};
export default meta;

export const Default = {
  name: 'Default (sample data)',
  args: {
    feed: sampleFeed,
    maxItems: 200,
  },
};

export const ManyItems = {
  name: 'Large feed (truncates)',
  args: {
    feed: Array.from({ length: 400 }).map((_, i) => ({
      ts: mkTs(i * 500),
      type: 'mqtt',
      payload: {
        topic: i % 5 === 0
          ? `mimir/displays/display-${(i%10)+1}/heartbeat`
          : i % 7 === 0
            ? `mimir/scenes/scene-${(i%6)+1}/evt`
            : i % 3 === 0
              ? `mimir/scenes/scene-${(i%6)+1}/cmd`
              : `mimir/displays/display-${(i%4)+1}/status`,
        payload: { index: i, value: Math.random(), flag: i % 3 === 0 }
      }
    })),
    maxItems: 200,
  },
  parameters: {
    docs: {
      description: {
        story: 'Demonstrates rendering cap and alternating topic classification across a larger generated dataset.'
      }
    }
  }
};

export const HeartbeatsOnly = {
  name: 'Heartbeats heavy feed',
  args: {
    feed: Array.from({ length: 40 }).map((_, i) => ({
      ts: mkTs(i * 1000),
      type: 'mqtt',
      payload: {
        topic: i % 2 === 0
          ? `mimir/displays/lobby-panel/heartbeat`
          : `mimir/system/metrics/heartbeat`,
        payload: { uptime: 1000 + i * 15, cpu: +(0.2 + (i % 10) * 0.01).toFixed(2) }
      }
    })),
    maxItems: 100,
  },
  parameters: {
    docs: {
      description: { story: 'Useful for testing the Heartbeats toggle and filter behavior.' }
    }
  }
};
