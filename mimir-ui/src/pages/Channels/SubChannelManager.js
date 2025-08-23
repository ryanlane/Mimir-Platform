import React, { useState, useEffect, useCallback } from 'react';
import { X, Plus, Edit, Trash2, Image, AlertCircle, Check } from 'lucide-react';
import { api } from '../../services/api';
import './SubChannelManager.css';

const SubChannelManager = ({ channel, onClose }) => {
  const [subChannels, setSubChannels] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [editingSubChannel, setEditingSubChannel] = useState(null);

  // Form state for creating/editing sub-channels
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    metadata: {}
  });

  const loadSubChannels = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await api.getSubChannels(channel.id);
      setSubChannels(response.data || []);
    } catch (err) {
      setError(`Failed to load sub-channels: ${err.message}`);
      console.error('Error loading sub-channels:', err);
    } finally {
      setLoading(false);
    }
  }, [channel.id]);

  useEffect(() => {
    loadSubChannels();
  }, [loadSubChannels]);

  const handleCreateSubChannel = async (e) => {
    e.preventDefault();
    try {
      await api.createSubChannel(channel.id, formData);
      setFormData({ name: '', description: '', metadata: {} });
      setShowCreateForm(false);
      await loadSubChannels();
    } catch (err) {
      setError(`Failed to create sub-channel: ${err.message}`);
    }
  };

  const handleUpdateSubChannel = async (e) => {
    e.preventDefault();
    try {
      await api.updateSubChannel(channel.id, editingSubChannel.id, formData);
      setFormData({ name: '', description: '', metadata: {} });
      setEditingSubChannel(null);
      await loadSubChannels();
    } catch (err) {
      setError(`Failed to update sub-channel: ${err.message}`);
    }
  };

  const handleDeleteSubChannel = async (subChannelId) => {
    if (!window.confirm('Are you sure you want to delete this sub-channel? This action cannot be undone.')) {
      return;
    }

    try {
      await api.deleteSubChannel(channel.id, subChannelId);
      await loadSubChannels();
    } catch (err) {
      setError(`Failed to delete sub-channel: ${err.message}`);
    }
  };

  const startEdit = (subChannel) => {
    setFormData({
      name: subChannel.name,
      description: subChannel.description || '',
      metadata: subChannel.metadata || {}
    });
    setEditingSubChannel(subChannel);
    setShowCreateForm(false);
  };

  const cancelEdit = () => {
    setFormData({ name: '', description: '', metadata: {} });
    setEditingSubChannel(null);
    setShowCreateForm(false);
  };

  const handleTestSubChannelImage = async (subChannelId) => {
    try {
      await api.requestChannelImage(channel.id, {
        resolution: [800, 600],
        orientation: 'landscape'
      }, subChannelId);
      alert('Test image generated successfully for sub-channel!');
    } catch (err) {
      alert(`Failed to generate test image: ${err.message}`);
    }
  };

  if (loading) {
    return (
      <div className="subchannel-manager-overlay">
        <div className="subchannel-manager">
          <div className="subchannel-manager-header">
            <h2>Loading Sub-Channels...</h2>
            <button className="close-btn" onClick={onClose}>
              <X size={20} />
            </button>
          </div>
          <div className="loading">Loading sub-channels for {channel.name}...</div>
        </div>
      </div>
    );
  }

  return (
    <div className="subchannel-manager-overlay">
      <div className="subchannel-manager">
        <div className="subchannel-manager-header">
          <h2>Manage Sub-Channels - {channel.name}</h2>
          <button className="close-btn" onClick={onClose}>
            <X size={20} />
          </button>
        </div>

        {error && (
          <div className="error-message">
            <AlertCircle size={16} />
            <span>{error}</span>
          </div>
        )}

        <div className="subchannel-manager-body">
          {/* Create/Edit Form */}
          {(showCreateForm || editingSubChannel) && (
            <form 
              className="subchannel-form"
              onSubmit={editingSubChannel ? handleUpdateSubChannel : handleCreateSubChannel}
            >
              <h3>{editingSubChannel ? 'Edit Sub-Channel' : 'Create New Sub-Channel'}</h3>
              
              <div className="form-group">
                <label>Name *</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="Enter sub-channel name"
                  required
                />
              </div>

              <div className="form-group">
                <label>Description</label>
                <textarea
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  placeholder="Enter sub-channel description"
                  rows={3}
                />
              </div>

              <div className="form-actions">
                <button type="submit" className="btn btn-primary">
                  <Check size={16} />
                  {editingSubChannel ? 'Update' : 'Create'}
                </button>
                <button type="button" className="btn btn-secondary" onClick={cancelEdit}>
                  Cancel
                </button>
              </div>
            </form>
          )}

          {/* Sub-Channels List */}
          <div className="subchannels-section">
            <div className="section-header">
              <h3>Sub-Channels ({subChannels.length})</h3>
              {!showCreateForm && !editingSubChannel && (
                <button 
                  className="btn btn-primary"
                  onClick={() => setShowCreateForm(true)}
                >
                  <Plus size={16} />
                  Add Sub-Channel
                </button>
              )}
            </div>

            {subChannels.length === 0 ? (
              <div className="empty-state">
                <p>No sub-channels configured for this channel.</p>
                <p>Sub-channels allow you to organize content within a channel.</p>
              </div>
            ) : (
              <div className="subchannels-grid">
                {subChannels.map(subChannel => (
                  <div key={subChannel.id} className="subchannel-card">
                    <div className="subchannel-header">
                      <h4>{subChannel.name}</h4>
                      <div className="subchannel-actions">
                        <button
                          className="action-btn"
                          onClick={() => handleTestSubChannelImage(subChannel.id)}
                          title="Test image generation"
                        >
                          <Image size={16} />
                        </button>
                        <button
                          className="action-btn"
                          onClick={() => startEdit(subChannel)}
                          title="Edit sub-channel"
                        >
                          <Edit size={16} />
                        </button>
                        <button
                          className="action-btn delete"
                          onClick={() => handleDeleteSubChannel(subChannel.id)}
                          title="Delete sub-channel"
                        >
                          <Trash2 size={16} />
                        </button>
                      </div>
                    </div>
                    
                    {subChannel.description && (
                      <p className="subchannel-description">{subChannel.description}</p>
                    )}
                    
                    <div className="subchannel-details">
                      <div className="detail-item">
                        <span>ID:</span>
                        <code>{subChannel.id}</code>
                      </div>
                      {subChannel.metadata && Object.keys(subChannel.metadata).length > 0 && (
                        <div className="detail-item">
                          <span>Content Items:</span>
                          <span>{Object.keys(subChannel.metadata).length}</span>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default SubChannelManager;
