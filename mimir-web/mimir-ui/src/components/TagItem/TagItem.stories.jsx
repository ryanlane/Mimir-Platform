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
import TagItem from './TagItem';

export default {
  title: 'Components/TagItem',
  component: TagItem,
  tags: ['autodocs'],
  argTypes: {
    onClick: { action: 'clicked' },
    onRemove: { action: 'removed' }
  }
};

const SelectableTemplate = (args) => {
  const [selected, setSelected] = useState(args.selected || false);
  return (
    <TagItem
      {...args}
      selectable
      selected={selected}
      onClick={(e) => { setSelected(!selected); args.onClick?.(e); }}
    />
  );
};

export const DisplayOnly = () => <TagItem label="Static Tag" />;

export const Selectable = SelectableTemplate.bind({});
Selectable.args = { label: 'Selectable Tag' };

export const Selected = SelectableTemplate.bind({});
Selected.args = { label: 'Selected Tag', selected: true };

export const Removable = SelectableTemplate.bind({});
Removable.args = { label: 'Removable Tag', removable: true };

export const Variants = () => (
  <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
    <TagItem label="Default" />
    <TagItem label="Accent" variant="accent" />
    <TagItem label="Success" variant="success" />
    <TagItem label="Warning" variant="warning" />
    <TagItem label="Error" variant="error" />
    <TagItem label="Selectable Selected" selectable selected />
  </div>
);

export const Sizes = () => (
  <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
    <TagItem label="Small" size="sm" />
    <TagItem label="Medium" size="md" />
    <TagItem label="Selectable Small" size="sm" selectable />
  </div>
);

export const Disabled = () => (
  <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
    <TagItem label="Disabled" disabled />
    <TagItem label="Disabled Selectable" disabled selectable />
    <TagItem label="Disabled Selectable Selected" disabled selectable selected />
    <TagItem label="Disabled Removable" disabled removable onRemove={() => {}} />
  </div>
);
