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
