import Button from './Button';

export default {
  title: 'Components/Button',
  component: Button,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
  argTypes: {
    variant: {
      control: 'select',
      options: ['default', 'primary', 'secondary', 'danger', 'ghost'],
    },
    size: {
      control: 'select',
      options: ['sm', 'md', 'lg'],
    },
    disabled: {
      control: 'boolean',
    },
    loading: {
      control: 'boolean',
    },
    onClick: { action: 'clicked' },
  },
};

// Default button
export const Default = {
  args: {
    children: 'Button',
  },
};

// Primary button (for main actions)
export const Primary = {
  args: {
    children: 'Primary Button',
    variant: 'primary',
  },
};

// Secondary button
export const Secondary = {
  args: {
    children: 'Secondary Button',
    variant: 'secondary',
  },
};

// Danger button (for delete actions)
export const Danger = {
  args: {
    children: 'Delete Scene',
    variant: 'danger',
  },
};

// Ghost button (for subtle actions)
export const Ghost = {
  args: {
    children: 'Cancel',
    variant: 'ghost',
  },
};

// Loading state
export const Loading = {
  args: {
    children: 'Loading...',
    loading: true,
    variant: 'primary',
  },
};

// Disabled state
export const Disabled = {
  args: {
    children: 'Disabled Button',
    disabled: true,
  },
};

// Different sizes
export const Small = {
  args: {
    children: 'Small Button',
    size: 'sm',
    variant: 'primary',
  },
};

export const Large = {
  args: {
    children: 'Large Button',
    size: 'lg',
    variant: 'primary',
  },
};

// Mimir-specific use cases
export const DisplayButton = {
  args: {
    children: 'Display',
    variant: 'primary',
    size: 'sm',
  },
  parameters: {
    docs: {
      description: {
        story: 'Display button used in scene cards to show current scene image',
      },
    },
  },
};

export const EditScene = {
  args: {
    children: 'Edit',
    variant: 'secondary',
    size: 'sm',
  },
  parameters: {
    docs: {
      description: {
        story: 'Edit button used in scene cards for scene modification',
      },
    },
  },
};

export const DeleteScene = {
  args: {
    children: 'Delete',
    variant: 'danger',
    size: 'sm',
  },
  parameters: {
    docs: {
      description: {
        story: 'Delete button used in scene cards for scene removal',
      },
    },
  },
};

// Button group example for scene cards
export const SceneCardButtons = {
  render: () => (
    <div style={{ display: 'flex', gap: '8px' }}>
      <Button variant="primary" size="sm">Display</Button>
      <Button variant="secondary" size="sm">Edit</Button>
      <Button variant="danger" size="sm">Delete</Button>
    </div>
  ),
  parameters: {
    docs: {
      description: {
        story: 'Button group as used in scene cards',
      },
    },
  },
};
