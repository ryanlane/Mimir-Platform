import React, { useState } from 'react';
import Button from '../components/Button/Button';
import Modal from '../components/Modal/Modal';

// Mock Scene Card component for Storybook
const SceneCard = ({ scene, onDisplay, onEdit, onDelete }) => {
  return (
    <div style={{
      border: '1px solid #e1e5e9',
      borderRadius: '8px',
      padding: '16px',
      backgroundColor: 'white',
      boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
      maxWidth: '300px'
    }}>
      <div style={{ marginBottom: '12px' }}>
        <h3 style={{ margin: '0 0 8px 0', fontSize: '1.125rem', fontWeight: '500' }}>
          {scene.name}
        </h3>
        <div style={{ marginBottom: '8px' }}>
          <span style={{ fontSize: '0.875rem', color: '#6b7280' }}>Channel: </span>
          <span style={{
            display: 'inline-block',
            backgroundColor: '#dbeafe',
            color: '#1e40af',
            padding: '2px 8px',
            borderRadius: '4px',
            fontSize: '0.75rem',
            fontWeight: '500'
          }}>
            {scene.channel}
          </span>
        </div>
        {scene.displayCount !== undefined && (
          <div style={{ fontSize: '0.875rem', color: '#6b7280' }}>
            Connected displays: {scene.displayCount}
          </div>
        )}
      </div>
      
      <div style={{
        display: 'flex',
        gap: '8px',
        justifyContent: 'flex-start'
      }}>
        <Button variant="primary" size="sm" onClick={() => onDisplay(scene)}>
          Display
        </Button>
        <Button variant="secondary" size="sm" onClick={() => onEdit(scene)}>
          Edit
        </Button>
        <Button variant="danger" size="sm" onClick={() => onDelete(scene)}>
          Delete
        </Button>
      </div>
    </div>
  );
};

// Wrapper with modal functionality
const SceneCardWithModal = ({ scene, ...args }) => {
  const [showImageModal, setShowImageModal] = useState(false);
  const [currentImageData, setCurrentImageData] = useState(null);
  const [imageLoading, setImageLoading] = useState(false);

  const handleDisplay = async (scene) => {
    setImageLoading(true);
    setShowImageModal(true);
    
    // Simulate API call
    setTimeout(() => {
      setCurrentImageData({
        imageUrl: 'https://via.placeholder.com/400x300/4A90E2/ffffff?text=Scene+Preview',
        sceneName: scene.name,
        channel: scene.channel,
        displayCount: scene.displayCount || 0
      });
      setImageLoading(false);
    }, 1000);
  };

  const handleEdit = (scene) => {
    alert(`Edit scene: ${scene.name}`);
  };

  const handleDelete = (scene) => {
    if (window.confirm(`Are you sure you want to delete "${scene.name}"?`)) {
      alert(`Deleted scene: ${scene.name}`);
    }
  };

  return (
    <>
      <SceneCard 
        scene={scene} 
        onDisplay={handleDisplay}
        onEdit={handleEdit}
        onDelete={handleDelete}
        {...args}
      />
      
      <Modal
        isOpen={showImageModal}
        onClose={() => setShowImageModal(false)}
        title="Scene Preview"
        size="medium"
      >
        {imageLoading ? (
          <div style={{ textAlign: 'center', padding: '40px' }}>
            <div style={{ marginBottom: '16px' }}>Loading scene preview...</div>
          </div>
        ) : currentImageData ? (
          <div style={{ textAlign: 'center' }}>
            <div style={{
              border: '1px solid #ddd',
              borderRadius: '8px',
              padding: '20px',
              marginBottom: '16px',
              backgroundColor: '#f9f9f9'
            }}>
              <img
                src={currentImageData.imageUrl}
                alt="Scene preview"
                style={{ maxWidth: '100%', height: 'auto', borderRadius: '4px' }}
              />
            </div>
            <div style={{
              backgroundColor: '#f5f5f5',
              padding: '12px',
              borderRadius: '4px',
              fontSize: '0.875rem',
              textAlign: 'left'
            }}>
              <p style={{ margin: '4px 0' }}><strong>Scene:</strong> {currentImageData.sceneName}</p>
              <p style={{ margin: '4px 0' }}><strong>Channel:</strong> {currentImageData.channel}</p>
              <p style={{ margin: '4px 0' }}><strong>Connected Displays:</strong> {currentImageData.displayCount}</p>
            </div>
          </div>
        ) : null}
      </Modal>
    </>
  );
};

export default {
  title: 'Mimir/SceneCard',
  component: SceneCard,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
};

// Default scene card
export const Default = {
  render: (args) => <SceneCardWithModal {...args} />,
  args: {
    scene: {
      name: 'Living Room Display',
      channel: 'Photo Frame',
      displayCount: 2
    }
  },
};

// Scene with no connected displays
export const NoDisplays = {
  render: (args) => <SceneCardWithModal {...args} />,
  args: {
    scene: {
      name: 'Kitchen Display',
      channel: 'Weather',
      displayCount: 0
    }
  },
};

// Scene with many displays
export const ManyDisplays = {
  render: (args) => <SceneCardWithModal {...args} />,
  args: {
    scene: {
      name: 'Office Dashboard',
      channel: 'News Feed',
      displayCount: 5
    }
  },
};

// Different channel types
export const WeatherChannel = {
  render: (args) => <SceneCardWithModal {...args} />,
  args: {
    scene: {
      name: 'Weather Station',
      channel: 'Weather',
      displayCount: 1
    }
  },
};

export const NewsChannel = {
  render: (args) => <SceneCardWithModal {...args} />,
  args: {
    scene: {
      name: 'News Feed',
      channel: 'RSS News',
      displayCount: 3
    }
  },
};

// Scene grid layout
export const SceneGrid = {
  render: () => (
    <div style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
      gap: '16px',
      padding: '16px',
      maxWidth: '800px'
    }}>
      <SceneCardWithModal scene={{ name: 'Living Room', channel: 'Photo Frame', displayCount: 2 }} />
      <SceneCardWithModal scene={{ name: 'Kitchen', channel: 'Weather', displayCount: 1 }} />
      <SceneCardWithModal scene={{ name: 'Office', channel: 'News Feed', displayCount: 0 }} />
      <SceneCardWithModal scene={{ name: 'Bedroom', channel: 'Clock', displayCount: 1 }} />
    </div>
  ),
  parameters: {
    layout: 'fullscreen',
    docs: {
      description: {
        story: 'Multiple scene cards in a grid layout as seen in the Scenes page',
      },
    },
  },
};
