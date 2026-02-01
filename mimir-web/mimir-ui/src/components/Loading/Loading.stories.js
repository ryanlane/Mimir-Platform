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
