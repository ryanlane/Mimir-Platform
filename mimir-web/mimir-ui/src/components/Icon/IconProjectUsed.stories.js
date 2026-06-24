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
