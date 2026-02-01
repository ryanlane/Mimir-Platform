import React from 'react';
import { PROJECT_ICON_NAMES, Icon } from './Icon';

export default {
  title: 'Components/Icon',
  component: Icon,
  tags: ['autodocs'],
  parameters: {
    docs: {
      description: {
        component: 'Icons currently referenced within the project codebase. Update the exported PROJECT_ICON_NAMES list in Icon.js as usage evolves.'
      }
    }
  }
};

export const UsedIcons = () => (
  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(90px,1fr))', gap: '12px', maxWidth: 860 }}>
    {PROJECT_ICON_NAMES.map(n => (
      <div key={n} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', fontSize: 11 }}>
        <Icon name={n} size={28} />
        <span style={{ marginTop: 4 }}>{n}</span>
      </div>
    ))}
  </div>
);
