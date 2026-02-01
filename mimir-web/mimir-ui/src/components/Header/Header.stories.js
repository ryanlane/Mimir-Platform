import React from 'react';
import Header from './Header';
import Button from '../Button/Button';
import { Rocket, Settings, Globe2 } from 'lucide-react';

export default {
  title: 'Components/Header',
  component: Header,
  tags: ['autodocs'],
  argTypes: {
    title: { control: 'text' },
    description: { control: 'text' },
    icon: { control: false },
    iconSize: { control: { type: 'number', min: 16, max: 96, step: 4 } },
    actions: { control: false, table: { category: 'layout' } },
    rightSlot: { control: false, table: { category: 'layout', type: { summary: 'ReactElement' }, description: 'Arbitrary content rendered on the far right (e.g., debug toggle, status badges, environment indicator)'} }
  },
  args: {
    title: 'Header Title Text',
    description: 'Optional description text',
    icon: 'Settings',
    iconSize: 32
  },
  parameters: {
    docs: {
      description: {
        component: 'Page or section header with optional Lucide icon and description. Pass a string icon name or a custom React element.'
      }
    }
  }
};

// Helper to map icon string to rendered header for controls story
const ControlledTemplate = ({ icon, ...args }) => {
  let iconProp = icon;
  if (typeof icon === 'string') {
    iconProp = icon; // Header will convert string via Icon component
  }
  return <Header {...args} icon={iconProp} />;
};

export const Basic = { render: ControlledTemplate };

export const WithDescription = {
  render: ControlledTemplate,
  args: {
    description: 'Short contextual explanation displayed under the title.'
  }
};

export const CustomIconComponent = {
  render: (args) => <Header {...args} icon={<Rocket />} />,
  args: {
    title: 'Launch Center',
    description: 'Manage deployment pipelines and release cadence.'
  },
  parameters: {
    docs: { description: { story: 'Provides a custom React element for icon instead of passing a name.' } }
  }
};

export const AlternateIcons = {
  render: () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
      <Header title="Settings" description="Configure application preferences" icon={<Settings />} />
      <Header title="Global Overview" description="Cross-region status and metrics" icon={<Globe2 />} />
      <Header title="Mission Control" description="Space launch operations and telemetry" icon={<Rocket />} />
    </div>
  ),
  parameters: {
    controls: { hideNoControlsWarning: true },
    docs: { description: { story: 'Multiple examples demonstrating varied icon usage.' } }
  }
};

export const NoIcon = {
  render: ControlledTemplate,
  args: { icon: undefined }
};

// Action Button Examples

export const WithSingleAction = {
  render: (args) => (
    <Header
      {...args}
      actions={<Button variant="primary">Create</Button>}
      title="Projects"
      description="Overview of active projects and their statuses"
      icon={<Settings />}
    />
  ),
  parameters: {
    docs: { description: { story: 'Header with a single primary action button aligned to the right.' } }
  }
};

export const WithTwoActions = {
  render: (args) => (
    <Header
      {...args}
      actions={[
        <Button key="refresh" variant="ghost">Refresh</Button>,
        <Button key="new" variant="primary">New Item</Button>
      ]}
      title="Inventory"
      description="Real-time stock levels across all warehouses"
      icon={<Globe2 />}
    />
  ),
  parameters: {
    docs: { description: { story: 'Header with two actions. The rightmost should be the primary action per common UX heuristics.' } }
  }
};

export const WithRenderFunctionActions = {
  render: (args) => (
    <Header
      {...args}
      actions={() => [
        <Button key="filter" variant="ghost">Filter</Button>,
        <Button key="export" variant="secondary">Export</Button>
      ]}
      title="Analytics"
      description="Engagement metrics for the last 30 days"
      icon={<Rocket />}
    />
  ),
  parameters: {
    docs: { description: { story: 'Demonstrates using a render function for deferred action creation (e.g., if computing state). Limited to max two items.' } }
  }
};

export const WithRightSlot = {
  render: () => (
    <Header
      title="Operations"
      description="Deployment window & environment status"
      icon={<Globe2 />}
      actions={<Button variant="primary">Deploy</Button>}
      rightSlot={(
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', fontSize: '0.7rem' }}>
          <span style={{ opacity: 0.65 }}>Env:</span>
          <span style={{ background: 'var(--color-surface-hover)', padding: '2px 6px', borderRadius: '10px', fontWeight: 600 }}>Prod</span>
          <span style={{ background: 'var(--color-success)', color: 'var(--color-background)', padding: '2px 6px', borderRadius: '10px', fontWeight: 600 }}>Healthy</span>
        </div>
      )}
    />
  ),
  parameters: {
    docs: { description: { story: 'Demonstrates the new rightSlot prop used alongside actions to surface arbitrary status widgets (environment + health) without constraining action button count.' } }
  }
};
