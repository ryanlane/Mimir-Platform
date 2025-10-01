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
            : `mimir/displays/display-${(i%10)+1}/status`,
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
