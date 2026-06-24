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

import React, { useState } from 'react';
import { Monitor, Shuffle, Layers } from 'lucide-react';
import SelectItem from './SelectItem.jsx';

export default {
  title: 'Components/SelectItem',
  component: SelectItem,
  parameters: {
    layout: 'centered'
  },
  tags: ['autodocs'],
  argTypes: {
    onChange: { action: 'changed' }
  }
};

const Template = (args) => {
  const [current, setCurrent] = useState(args.value || 'one');
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', width: '360px' }}>
      <SelectItem
        {...args}
        name={args.name || 'example'}
        value="one"
        title="First Option"
        description="This is the first selectable option."
        checked={current === 'one'}
        onChange={(v) => { setCurrent(v); args.onChange?.(v); }}
      />
      <SelectItem
        {...args}
        name={args.name || 'example'}
        value="two"
        title="Second Option"
        description="Another descriptive block for selection."
        checked={current === 'two'}
        onChange={(v) => { setCurrent(v); args.onChange?.(v); }}
      />
      <SelectItem
        {...args}
        name={args.name || 'example'}
        value="three"
        title="Third Option"
        description="Yet another choice in the group."
        checked={current === 'three'}
        onChange={(v) => { setCurrent(v); args.onChange?.(v); }}
        disabled={args.disabledGroup}
      />
    </div>
  );
};

export const Default = Template.bind({});
Default.args = {
  name: 'default-group'
};

export const WithIcons = () => {
  const [current, setCurrent] = useState('mirror');
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', width: '420px' }}>
      <SelectItem
        name="dist"
        value="mirror"
        title="Mirror Mode"
        description="All displays show same content"
        icon={<Monitor size={16} />}
        checked={current === 'mirror'}
        onChange={setCurrent}
      />
      <SelectItem
        name="dist"
        value="sequential"
        title="Sequential Mode"
        description="Displays cycle through content"
        icon={<Layers size={16} />}
        checked={current === 'sequential'}
        onChange={setCurrent}
      />
      <SelectItem
        name="dist"
        value="random_unique"
        title="Random Unique"
        description="Randomized without duplication"
        icon={<Shuffle size={16} />}
        checked={current === 'random_unique'}
        onChange={setCurrent}
      />
    </div>
  );
};

export const Disabled = () => (
  <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', width: '360px' }}>
    <SelectItem name="disabled" value="a" title="Disabled A" description="Cannot select" checked icon={<Monitor size={16} />} disabled />
    <SelectItem name="disabled" value="b" title="Disabled B" description="Inactive state" disabled />
  </div>
);
