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

import Loading from './Loading';

export default {
  title: 'Components/Loading',
  component: Loading,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
  argTypes: {
    message: {
      control: 'text',
    },
  },
};

// Default loading
export const Default = {
  args: {
    message: 'Loading...',
  },
};

// Custom message
export const CustomMessage = {
  args: {
    message: 'Fetching scenes...',
  },
};

// Mimir-specific loading states
export const LoadingDisplays = {
  args: {
    message: 'Loading connected displays...',
  },
  parameters: {
    docs: {
      description: {
        story: 'Loading state for fetching connected displays',
      },
    },
  },
};

export const LoadingScenes = {
  args: {
    message: 'Loading scenes...',
  },
  parameters: {
    docs: {
      description: {
        story: 'Loading state for fetching scenes',
      },
    },
  },
};

export const LoadingChannels = {
  args: {
    message: 'Loading available channels...',
  },
  parameters: {
    docs: {
      description: {
        story: 'Loading state for fetching channels',
      },
    },
  },
};

export const LoadingImage = {
  args: {
    message: 'Loading scene preview...',
  },
  parameters: {
    docs: {
      description: {
        story: 'Loading state for scene image preview',
      },
    },
  },
};

// In a container (for page-level loading)
export const PageLoading = {
  render: (args) => (
    <div style={{ 
      height: '400px', 
      display: 'flex', 
      alignItems: 'center', 
      justifyContent: 'center',
      border: '1px dashed #ddd',
      borderRadius: '8px'
    }}>
      <Loading {...args} />
    </div>
  ),
  args: {
    message: 'Loading dashboard...',
  },
  parameters: {
    docs: {
      description: {
        story: 'Loading component used for full page or section loading',
      },
    },
  },
};
