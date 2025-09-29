import React from 'react';
import Icon from './Icon';
import * as LucideIcons from 'lucide-react';

const iconNames = Object.keys(LucideIcons).filter(k => /^[A-Z]/.test(k)).slice(0, 120); // limit for gallery

export default {
  title: 'Components/Icon',
  component: Icon,
  tags: ['autodocs'],
  argTypes: {
    name: { control: 'text' },
    size: { control: { type: 'number', min: 8, max: 128, step: 2 } },
    color: { control: 'color' },
    strokeWidth: { control: { type: 'number', min: 1, max: 4, step: 0.25 } }
  },
  args: { name: 'Settings', size: 32 }
};

export const Basic = {};

export const Gallery = {
  render: (args) => (
    <div style={{ maxHeight: '70vh', overflow: 'auto', display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(90px,1fr))', gap: '12px' }}>
      {iconNames.map(n => (
        <div key={n} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', fontSize: 11 }}>
          <Icon name={n} size={28} />
          <span style={{ marginTop: 4 }}>{n}</span>
        </div>
      ))}
    </div>
  ),
  parameters: {
    controls: { exclude: ['name', 'size', 'color', 'strokeWidth'] },
    docs: { description: { story: 'Preview subset of available Lucide icons (capped at 120 for performance).' } }
  }
};
