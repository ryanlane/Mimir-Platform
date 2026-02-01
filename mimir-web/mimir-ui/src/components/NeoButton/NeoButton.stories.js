import NeoButton from './NeoButton';

export default {
  title: 'Components/NeoButton',
  component: NeoButton,
  parameters: { layout: 'centered' },
  tags: ['autodocs'],
  argTypes: {
    hasDot: { control: 'boolean' },
    isActive: { control: 'boolean' },
    label: { control: 'text' }
  }
};

export const WithDot = {
  args: {
    label: 'Option A',
    hasDot: true,
    isActive: false
  }
};

export const WithoutDot = {
  args: {
    label: 'Option B',
    hasDot: false,
    isActive: false
  }
};

export const ActiveWithDot = {
  args: {
    label: 'Selected',
    hasDot: true,
    isActive: true
  }
};

export const ActiveNoDot = {
  args: {
    label: 'Option D',
    hasDot: false,
    isActive: true
  }
};

export const ButtonRow = {
  render: (args) => (
    <div className="neo-btn-row" style={{ width: '520px' }}>
      <NeoButton label="Option A" hasDot />
      <NeoButton label="Option B" />
      <NeoButton label="Selected" hasDot isActive />
      <NeoButton label="Option D" />
    </div>
  )
};

export const IconWithDot = {
  args: {
    label: 'Music',
    hasDot: true,
    icon: 'Volume2'
  }
};

export const IconNoDot = {
  args: {
    label: 'Settings',
    hasDot: false,
    icon: 'Settings'
  }
};
