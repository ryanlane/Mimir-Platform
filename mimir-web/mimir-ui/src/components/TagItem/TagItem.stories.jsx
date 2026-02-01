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
