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
    icon: { control: 'text', description: 'Lucide icon name or ignored if using children element' },
    iconPosition: { control: 'inline-radio', options: ['left', 'right'] },
    iconSize: { control: { type: 'number', min: 12, max: 32, step: 2 } }
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



// Icon variations
export const IconLeft = {
  args: {
    children: 'Settings',
    icon: 'Settings',
    iconPosition: 'left'
  },
  parameters: { docs: { description: { story: 'Button with left-aligned icon (default).' } } }
};

export const IconRight = {
  args: {
    children: 'Add Item',
    icon: 'Plus',
    iconPosition: 'right',
    variant: 'primary'
  },
  parameters: { docs: { description: { story: 'Right-aligned icon useful for forward / next actions.' } } }
};

export const IconOnly = {
  args: {
    icon: 'Trash2',
    variant: 'danger',
    'aria-label': 'Delete item'
  },
  parameters: { docs: { description: { story: 'Icon-only button; MUST provide aria-label for accessibility.' } } }
};
