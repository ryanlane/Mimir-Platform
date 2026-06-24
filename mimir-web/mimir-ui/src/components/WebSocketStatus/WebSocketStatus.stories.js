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
import WebSocketStatus from './WebSocketStatus';

export default {
  title: 'Components/WebSocketStatus',
  component: WebSocketStatus,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
  decorators: [
    (Story) => (
      <div style={{ maxWidth: '400px', padding: '20px' }}>
        <Story />
      </div>
    ),
  ],
};

// Connected state with enhanced features
export const Connected = {
  render: () => (
    <div style={{ padding: '16px', backgroundColor: '#f9f9f9', borderRadius: '8px' }}>
      <div className="websocket-status enhanced">
        <div className="status-header">
          <div className="status-indicator">
            <span style={{ color: '#10b981', marginRight: '8px' }}>📶</span>
            <span>WebSocket Connected</span>
          </div>
          <button className="btn btn-sm btn-tertiary">
            🔄 Refresh
          </button>
        </div>
        
        <div className="status-details">
          <div className="detail-grid" style={{ display: 'grid', gap: '8px', margin: '12px 0' }}>
            <div className="detail-item" style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span className="label">Connected Clients:</span>
              <span className="value">3</span>
            </div>
            <div className="detail-item" style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span className="label">Current Sequence:</span>
              <span className="value">1234</span>
            </div>
            <div className="detail-item" style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span className="label">WebSocket URL:</span>
              <span className="value" style={{ fontFamily: 'monospace', fontSize: '0.8em' }}>ws://localhost:8000/ws</span>
            </div>
          </div>

          <div className="features-list">
            <h4 style={{ margin: '12px 0 8px 0', fontSize: '0.9em' }}>Enhanced Features:</h4>
            <div className="features-grid" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '4px', color: '#10b981' }}>
                <span>✓</span>
                <span style={{ fontSize: '0.8em' }}>enhanced websocket</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '4px', color: '#10b981' }}>
                <span>✓</span>
                <span style={{ fontSize: '0.8em' }}>real time updates</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '4px', color: '#10b981' }}>
                <span>✓</span>
                <span style={{ fontSize: '0.8em' }}>connection pooling</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '4px', color: '#f59e0b' }}>
                <span>⚠</span>
                <span style={{ fontSize: '0.8em' }}>message queuing</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  ),
  parameters: {
    docs: {
      description: {
        story: 'WebSocket status showing connected state with enhanced features enabled',
      },
    },
  },
};

// Disconnected state
export const Disconnected = {
  render: () => (
    <div style={{ padding: '16px', backgroundColor: '#f9f9f9', borderRadius: '8px' }}>
      <div className="websocket-status enhanced">
        <div className="status-header">
          <div className="status-indicator">
            <span style={{ color: '#ef4444', marginRight: '8px' }}>📵</span>
            <span>WebSocket Disconnected</span>
          </div>
          <button className="btn btn-sm btn-tertiary">
            🔄 Refresh
          </button>
        </div>
        
        <div style={{ 
          padding: '12px', 
          backgroundColor: '#fee2e2', 
          border: '1px solid #fecaca', 
          borderRadius: '4px',
          color: '#dc2626',
          fontSize: '0.875rem'
        }}>
          Connection lost. Attempting to reconnect...
        </div>
      </div>
    </div>
  ),
  parameters: {
    docs: {
      description: {
        story: 'WebSocket status showing disconnected state',
      },
    },
  },
};

// Basic mode (no enhanced features)
export const BasicMode = {
  render: () => (
    <div style={{ padding: '16px', backgroundColor: '#f9f9f9', borderRadius: '8px' }}>
      <div className="websocket-status basic">
        <div className="status-indicator">
          <span style={{ color: '#10b981', marginRight: '8px' }}>📶</span>
          <span>Connected</span>
        </div>
      </div>
    </div>
  ),
  parameters: {
    docs: {
      description: {
        story: 'Basic WebSocket status without enhanced features',
      },
    },
  },
};

// Loading state
export const Loading = {
  render: () => (
    <div style={{ padding: '16px', backgroundColor: '#f9f9f9', borderRadius: '8px' }}>
      <div className="websocket-status enhanced">
        <div className="status-header">
          <div className="status-indicator">
            <span style={{ color: '#10b981', marginRight: '8px' }}>📶</span>
            <span>WebSocket Connected</span>
          </div>
          <button className="btn btn-sm btn-tertiary" disabled>
            <span style={{ marginRight: '4px' }}>⟳</span>
            Refresh
          </button>
        </div>
        
        <div style={{ 
          padding: '12px', 
          textAlign: 'center',
          color: '#6b7280'
        }}>
          Loading WebSocket status...
        </div>
      </div>
    </div>
  ),
  parameters: {
    docs: {
      description: {
        story: 'WebSocket status in loading state',
      },
    },
  },
};

// Multiple clients connected
export const ManyClients = {
  render: () => (
    <div style={{ padding: '16px', backgroundColor: '#f9f9f9', borderRadius: '8px' }}>
      <div className="websocket-status enhanced">
        <div className="status-header">
          <div className="status-indicator">
            <span style={{ color: '#10b981', marginRight: '8px' }}>📶</span>
            <span>WebSocket Connected</span>
          </div>
          <button className="btn btn-sm btn-tertiary">
            🔄 Refresh
          </button>
        </div>
        
        <div className="status-details">
          <div className="detail-grid" style={{ display: 'grid', gap: '8px', margin: '12px 0' }}>
            <div className="detail-item" style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span className="label">Connected Clients:</span>
              <span className="value" style={{ fontWeight: 'bold', color: '#059669' }}>12</span>
            </div>
            <div className="detail-item" style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span className="label">Current Sequence:</span>
              <span className="value">5678</span>
            </div>
            <div className="detail-item" style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span className="label">WebSocket URL:</span>
              <span className="value" style={{ fontFamily: 'monospace', fontSize: '0.8em' }}>wss://mimir.example.com/ws</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  ),
  parameters: {
    docs: {
      description: {
        story: 'WebSocket status with many connected clients',
      },
    },
  },
};
