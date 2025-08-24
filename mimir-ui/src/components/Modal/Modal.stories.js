import React, { useState } from 'react';
import Modal from './Modal';
import Button from '../Button/Button';

export default {
  title: 'Components/Modal',
  component: Modal,
  parameters: {
    layout: 'fullscreen',
  },
  tags: ['autodocs'],
  argTypes: {
    size: {
      control: 'select',
      options: ['small', 'medium', 'large'],
    },
    showCloseButton: {
      control: 'boolean',
    },
    closeOnOverlayClick: {
      control: 'boolean',
    },
  },
};

// Modal wrapper for stories
const ModalWrapper = ({ children, ...args }) => {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div style={{ padding: '20px' }}>
      <Button onClick={() => setIsOpen(true)} variant="primary">
        Open Modal
      </Button>
      <Modal {...args} isOpen={isOpen} onClose={() => setIsOpen(false)}>
        {children}
      </Modal>
    </div>
  );
};

// Basic modal
export const Default = {
  render: (args) => (
    <ModalWrapper {...args}>
      <p>This is a basic modal with some content.</p>
    </ModalWrapper>
  ),
  args: {
    title: 'Default Modal',
  },
};

// Modal with title
export const WithTitle = {
  render: (args) => (
    <ModalWrapper {...args}>
      <p>This modal has a title in the header.</p>
    </ModalWrapper>
  ),
  args: {
    title: 'Modal with Title',
  },
};

// Modal without close button
export const NoCloseButton = {
  render: (args) => (
    <ModalWrapper {...args}>
      <p>This modal doesn't have a close button. You can still close it by clicking outside or pressing Escape.</p>
    </ModalWrapper>
  ),
  args: {
    title: 'No Close Button',
    showCloseButton: false,
  },
};

// Small modal
export const Small = {
  render: (args) => (
    <ModalWrapper {...args}>
      <p>This is a small modal.</p>
    </ModalWrapper>
  ),
  args: {
    title: 'Small Modal',
    size: 'small',
  },
};

// Large modal
export const Large = {
  render: (args) => (
    <ModalWrapper {...args}>
      <div>
        <p>This is a large modal with more content.</p>
        <p>It can contain multiple paragraphs, forms, or other components.</p>
        <ul>
          <li>List item 1</li>
          <li>List item 2</li>
          <li>List item 3</li>
        </ul>
      </div>
    </ModalWrapper>
  ),
  args: {
    title: 'Large Modal',
    size: 'large',
  },
};

// Scene Image Preview Modal (Mimir-specific)
export const SceneImagePreview = {
  render: (args) => (
    <ModalWrapper {...args}>
      <div style={{ textAlign: 'center' }}>
        <div style={{ 
          border: '1px solid #ddd', 
          borderRadius: '8px', 
          padding: '20px', 
          marginBottom: '16px',
          backgroundColor: '#f9f9f9'
        }}>
          <img 
            src="https://via.placeholder.com/400x300/4A90E2/ffffff?text=Scene+Preview" 
            alt="Scene preview" 
            style={{ maxWidth: '100%', height: 'auto', borderRadius: '4px' }}
          />
        </div>
        <div style={{ 
          backgroundColor: '#f5f5f5', 
          padding: '12px', 
          borderRadius: '4px',
          fontSize: '0.875rem'
        }}>
          <p><strong>Scene:</strong> Living Room Display</p>
          <p><strong>Channel:</strong> Photo Frame</p>
          <p><strong>Connected Displays:</strong> 2</p>
        </div>
      </div>
    </ModalWrapper>
  ),
  args: {
    title: 'Scene Preview',
    size: 'medium',
  },
  parameters: {
    docs: {
      description: {
        story: 'Modal used to preview scene images in the Mimir system',
      },
    },
  },
};

// Form Modal Example
export const FormModal = {
  render: (args) => (
    <ModalWrapper {...args}>
      <form style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        <div>
          <label htmlFor="scene-name" style={{ display: 'block', marginBottom: '4px' }}>
            Scene Name
          </label>
          <input 
            id="scene-name"
            type="text" 
            placeholder="Enter scene name"
            style={{ 
              width: '100%', 
              padding: '8px', 
              border: '1px solid #ddd', 
              borderRadius: '4px' 
            }}
          />
        </div>
        <div>
          <label htmlFor="channel-select" style={{ display: 'block', marginBottom: '4px' }}>
            Channel
          </label>
          <select 
            id="channel-select"
            style={{ 
              width: '100%', 
              padding: '8px', 
              border: '1px solid #ddd', 
              borderRadius: '4px' 
            }}
          >
            <option>Photo Frame</option>
            <option>Weather Display</option>
            <option>News Feed</option>
          </select>
        </div>
        <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
          <Button variant="ghost">Cancel</Button>
          <Button variant="primary">Save Scene</Button>
        </div>
      </form>
    </ModalWrapper>
  ),
  args: {
    title: 'Create New Scene',
    size: 'medium',
    closeOnOverlayClick: false,
  },
  parameters: {
    docs: {
      description: {
        story: 'Modal with a form for creating/editing scenes',
      },
    },
  },
};
