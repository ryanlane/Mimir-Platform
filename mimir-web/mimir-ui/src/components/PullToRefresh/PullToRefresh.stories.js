import React, { useState } from 'react';
import PullToRefresh from './PullToRefresh';

export default {
  title: 'Components/PullToRefresh',
  component: PullToRefresh,
  parameters: {
    layout: 'fullscreen',
    docs: {
      description: {
        component: `Mobile pull-to-refresh wrapper. Only actively engages on touch / coarse pointer devices and when the window is scrolled to the very top (scrollY === 0).\n\nThe component translates its children downward while pulling and exposes states via data-ptr-state attribute: idle | pulling | ready | refreshing.`
      }
    }
  },
  argTypes: {
    threshold: { control: { type: 'number', min: 20, max: 160, step: 5 } },
    maxPull: { control: { type: 'number', min: 60, max: 260, step: 10 } },
    disabled: { control: 'boolean' },
    onRefresh: { action: 'refresh-called' }
  }
};

const DemoContent = ({ count }) => (
  <div style={{ padding: '1rem' }}>
    <h3 style={{ marginTop: 0 }}>Demo Content ({count})</h3>
    <p>Scroll the page to the very top on a touch device / emulated mobile and pull down to test.</p>
    <ul>
      {Array.from({ length: 12 }).map((_, i) => (
        <li key={i}>List item #{i + 1}</li>
      ))}
    </ul>
    <p style={{ fontSize: 12, opacity: .7 }}>States exposed: data-ptr-state=&quot;idle|pulling|ready|refreshing&quot;.</p>
  </div>
);

// Template for stories using internal refresh simulation
const Template = (args) => {
  const [count, setCount] = useState(0);
  const handleRefresh = async () => {
    // optional external action log
    if (args.onRefresh) args.onRefresh();
    await new Promise(r => setTimeout(r, 800));
    setCount(c => c + 1);
  };
  return (
    <PullToRefresh {...args} onRefresh={handleRefresh}>
      <DemoContent count={count} />
    </PullToRefresh>
  );
};

export const Default = {
  render: Template,
  args: {
    threshold: 70,
    maxPull: 140,
    disabled: false
  },
  parameters: {
    docs: {
      description: {
        story: 'Standard configuration (threshold 70px, maxPull 140px). Pull distance beyond threshold triggers refresh when released.'
      }
    }
  }
};

export const CustomThreshold = {
  render: Template,
  args: {
    threshold: 40,
    maxPull: 120
  },
  parameters: {
    docs: {
      description: { story: 'Lower threshold makes it easier to trigger. Smaller maxPull for tighter feel.' }
    }
  }
};

export const LargeMaxPull = {
  render: Template,
  args: {
    threshold: 90,
    maxPull: 200
  },
  parameters: {
    docs: {
      description: { story: 'Higher maxPull value allows a more elastic feel; threshold increased accordingly.' }
    }
  }
};

export const Disabled = {
  render: Template,
  args: {
    disabled: true
  },
  parameters: {
    docs: {
      description: { story: 'Interaction disabled; component renders children without pull behavior.' }
    }
  }
};

export const ExternalAsyncRefresh = {
  render: (args) => {
    const [count, setCount] = useState(0);
    const handleRefresh = async () => {
      args.onRefresh && args.onRefresh();
      await new Promise(r => setTimeout(r, 1250));
      setCount(c => c + 1);
    };
    return (
      <PullToRefresh {...args} onRefresh={handleRefresh}>
        <DemoContent count={count} />
      </PullToRefresh>
    );
  },
  args: {
    threshold: 70,
    maxPull: 150
  },
  parameters: {
    docs: {
      description: { story: 'Simulates a slower external data fetch (1.25s) before releasing content back.' }
    }
  }
};
