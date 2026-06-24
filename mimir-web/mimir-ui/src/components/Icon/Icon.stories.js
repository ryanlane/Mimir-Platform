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
