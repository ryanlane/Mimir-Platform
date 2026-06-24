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
      options: ['small', 'medium', 'large', 'xlarge'],
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

// Extra Large (edge-to-edge-ish) modal
export const XLarge = {
  render: (args) => (
    <ModalWrapper {...args}>
      <div style={{ display: 'grid', gap: '12px' }}>
        <p>This is an extra large modal intended for wide / immersive content like previews or complex configuration forms.</p>
        <p>Use this size sparingly—prefer large or medium for most use-cases.</p>
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))',
          gap: '8px',
          background: '#f7f7f7',
          padding: '12px',
          borderRadius: '6px'
        }}>
          {Array.from({ length: 12 }).map((_, i) => (
            <div key={i} style={{
              background: 'white',
              border: '1px solid #e2e2e2',
              borderRadius: '4px',
              padding: '8px',
              fontSize: '.75rem',
              textAlign: 'center'
            }}>
              Item {i + 1}
            </div>
          ))}
        </div>
      </div>
    </ModalWrapper>
  ),
  args: {
    title: 'Extra Large Modal',
    size: 'xlarge',
  },
  parameters: {
    docs: {
      description: {
        story: 'The xlarge size maps to .modal-xlarge (100% max-width) for scenarios needing near full-width layouts.'
      }
    }
  }
};

// All sizes preview (non-interactive showcase)
export const AllSizes = {
  render: () => {
    const sizes = ['small', 'medium', 'large', 'xlarge'];
    return (
      <div style={{ display: 'grid', gap: '32px', padding: '24px' }}>
        {sizes.map(sz => (
          <div key={sz} style={{ border: '1px solid #ddd', borderRadius: '8px', padding: '16px' }}>
            <h3 style={{ marginTop: 0 }}>Size: {sz}</h3>
            <p>Class: <code>.modal-{sz}</code></p>
            <p>This is a static showcase. Open the interactive stories to test behavior.</p>
          </div>
        ))}
      </div>
    );
  },
  parameters: {
    controls: { disable: true },
    docs: {
      description: {
        story: 'Reference of all modal size tokens available via the size prop.'
      }
    }
  }
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
