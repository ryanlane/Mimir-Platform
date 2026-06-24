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

import React, { useState, useEffect } from 'react';
import { RefreshCw, Settings, Info, Activity, Database } from 'lucide-react';
import { api } from '../../services/api';
import { useWebSocketEvent } from '../../hooks/useWebSocket';
import './DistributionManager.css';

const DistributionManager = ({ sceneId, sceneName, onClose }) => {
  const [contentInfo, setContentInfo] = useState(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(null);
  const [lastRefresh, setLastRefresh] = useState(null);

  // Listen for content refresh events
  useWebSocketEvent('scene_content_refreshed', (data) => {
    if (data.scene_id === sceneId) {
      console.log('🔄 Scene content refreshed for scene:', sceneId);
      loadContentInfo();
      setLastRefresh(new Date());
    }
  });

  const loadContentInfo = async () => {
    try {
      const response = await api.getSceneContentInfo(sceneId);
      setContentInfo(response.data);
    } catch (error) {
      console.error('Error loading content info:', error);
      setContentInfo(null);
    } finally {
      setLoading(false);
    }
  };

  const handleRefreshContent = async () => {
    setActionLoading('refresh');
    try {
      await api.refreshSceneContent(sceneId);
      // The WebSocket event will trigger a reload
    } catch (error) {
      console.error('Error refreshing content:', error);
    } finally {
      setActionLoading(null);
    }
  };

  const handleResetDistribution = async () => {
    if (window.confirm('Are you sure you want to reset the distribution queues? This will clear all active assignments.')) {
      setActionLoading('reset');
      try {
        await api.resetSceneDistribution(sceneId);
        await loadContentInfo();
      } catch (error) {
        console.error('Error resetting distribution:', error);
      } finally {
        setActionLoading(null);
      }
    }
  };

  useEffect(() => {
    loadContentInfo();
  }, [sceneId]); // eslint-disable-line react-hooks/exhaustive-deps

  if (loading) {
    return (
      <div className="distribution-manager">
        <div className="distribution-header">
          <h3>Distribution Manager</h3>
          <button className="btn btn-sm btn-secondary" onClick={onClose}>×</button>
        </div>
        <div className="loading">
          <div className="loading-spinner"></div>
          <span>Loading distribution info...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="distribution-manager">
      <div className="distribution-header">
        <div>
          <h3>Distribution Manager</h3>
          <p className="text-tertiary">Scene: {sceneName}</p>
        </div>
        <button className="btn btn-sm btn-secondary" onClick={onClose}>×</button>
      </div>

      <div className="distribution-content">
        {contentInfo ? (
          <>
            <div className="content-overview">
              <div className="stat-grid">
                <div className="stat-item">
                  <div className="stat-icon">
                    <Database size={16} />
                  </div>
                  <div className="stat-info">
                    <div className="stat-label">Total Content</div>
                    <div className="stat-value">{contentInfo.total_content_items || 0}</div>
                  </div>
                </div>
                <div className="stat-item">
                  <div className="stat-icon">
                    <Activity size={16} />
                  </div>
                  <div className="stat-info">
                    <div className="stat-label">Distribution Mode</div>
                    <div className="stat-value">{contentInfo.distribution_mode || 'MIRROR'}</div>
                  </div>
                </div>
                <div className="stat-item">
                  <div className="stat-icon">
                    <RefreshCw size={16} />
                  </div>
                  <div className="stat-info">
                    <div className="stat-label">Content Epoch</div>
                    <div className="stat-value">{contentInfo.content_epoch || 'N/A'}</div>
                  </div>
                </div>
              </div>
            </div>

            {contentInfo.distribution_mode !== 'MIRROR' && (
              <div className="queue-status">
                <h4>Queue Status</h4>
                <div className="queue-info">
                  <div className="queue-stat">
                    <span className="queue-label">Sequential Queue:</span>
                    <span className="queue-value">{contentInfo.sequential_queue_size || 0} items</span>
                  </div>
                  <div className="queue-stat">
                    <span className="queue-label">Shuffle Bag:</span>
                    <span className="queue-value">{contentInfo.shuffle_bag_size || 0} items</span>
                  </div>
                  <div className="queue-stat">
                    <span className="queue-label">Active Leases:</span>
                    <span className="queue-value">{contentInfo.active_leases || 0}</span>
                  </div>
                </div>
              </div>
            )}

            <div className="distribution-actions">
              <button
                className={`btn btn-primary ${actionLoading === 'refresh' ? 'loading' : ''}`}
                onClick={handleRefreshContent}
                disabled={actionLoading}
              >
                <RefreshCw size={16} className={actionLoading === 'refresh' ? 'spinning' : ''} />
                {actionLoading === 'refresh' ? 'Refreshing...' : 'Refresh Content'}
              </button>
              
              <button
                className={`btn btn-warning ${actionLoading === 'reset' ? 'loading' : ''}`}
                onClick={handleResetDistribution}
                disabled={actionLoading}
              >
                <Settings size={16} />
                {actionLoading === 'reset' ? 'Resetting...' : 'Reset Distribution'}
              </button>
            </div>

            {lastRefresh && (
              <div className="last-refresh">
                <Info size={14} />
                <span>Last refreshed: {lastRefresh.toLocaleTimeString()}</span>
              </div>
            )}

            {contentInfo.channels && contentInfo.channels.length > 0 && (
              <div className="content-channels">
                <h4>Content Channels</h4>
                <div className="channel-list">
                  {contentInfo.channels.map((channel, index) => (
                    <div key={index} className="channel-item">
                      <span className="channel-name">{channel.channel_id}</span>
                      {channel.subchannel_id && (
                        <span className="subchannel-name">→ {channel.subchannel_id}</span>
                      )}
                      <span className="channel-items">{channel.content_count || 0} items</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        ) : (
          <div className="empty-state">
            <Info size={24} />
            <p>No distribution information available</p>
            <p className="text-tertiary">This scene may not have Redis distribution enabled.</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default DistributionManager;
