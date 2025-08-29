// Display Card component for individual display clients
import React, { useState } from 'react';
import { Monitor, Wifi, WifiOff, MapPin, Tag, Calendar, Settings, Eye, Trash2, RotateCcw, Image, Play } from 'lucide-react';
import { api } from '../../services/api';

const DisplayCard = ({ display, onAssignScene, onEdit, onDelete, onRefresh }) => {
  const [imageLoading, setImageLoading] = useState(false);
  const [showImagePreview, setShowImagePreview] = useState(false);
  const [imageError, setImageError] = useState(false);

  const handleRefreshImage = async () => {
    setImageLoading(true);
    try {
      // Force refresh by calling the display image endpoint
      await api.getDisplayImage(display.id);
      onRefresh();
    } catch (error) {
      console.error('Error refreshing display image:', error);
    } finally {
      setImageLoading(false);
    }
  };

  const handleViewImage = () => {
    if (display.current_image_url) {
      setShowImagePreview(true);
    }
  };

  const formatLastSeen = (lastSeen) => {
    if (!lastSeen) return 'Never';
    const date = new Date(lastSeen);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    return `${diffDays}d ago`;
  };

  const getStatusColor = () => {
    if (display.is_online) return 'status-online';
    return 'status-offline';
  };

  return (
    <>
      <div className={`display-card ${getStatusColor()} ${display.source === 'discovered' ? 'discovered-display' : 'registered-display'}`}>
        <div className="display-card-header">
          <div className="display-info">
            <div className="display-title">
              <Monitor size={20} />
              <h3>{display.name}</h3>
              <div className={`status-indicator ${display.is_online ? 'online' : 'offline'}`}>
                {display.is_online ? <Wifi size={14} /> : <WifiOff size={14} />}
              </div>
              {display.source === 'discovered' && (
                <div className="source-badge discovered">
                  <span>Discovered</span>
                </div>
              )}
              {display.source === 'registered' && (
                <div className="source-badge registered">
                  <span>Registered</span>
                </div>
              )}
            </div>
            {display.description && (
              <p className="display-description">{display.description}</p>
            )}
          </div>

          <div className="display-actions">
            {display.source === 'registered' ? (
              <>
                <button 
                  className="btn btn-sm btn-tertiary" 
                  onClick={() => onEdit(display)}
                  title="Edit Display"
                >
                  <Settings size={16} />
                </button>
                <button 
                  className="btn btn-sm btn-tertiary" 
                  onClick={() => onDelete(display.id)}
                  title="Delete Display"
                >
                  <Trash2 size={16} />
                </button>
              </>
            ) : (
              <button 
                className="btn btn-sm btn-primary" 
                onClick={() => onEdit(display, 'register')}
                title="Register This Display"
              >
                Register
              </button>
            )}
          </div>
        </div>

        <div className="display-details">
          {display.location && (
            <div className="detail-item">
              <MapPin size={14} />
              <span>{display.location}</span>
            </div>
          )}

          <div className="detail-item">
            <Monitor size={14} />
            <span>{display.resolution[0]}×{display.resolution[1]} • {display.orientation}</span>
          </div>

          {display.refresh_rate_hz && (
            <div className="detail-item">
              <RotateCcw size={14} />
              <span>{display.refresh_rate_hz}Hz</span>
            </div>
          )}

          <div className="detail-item">
            <Calendar size={14} />
            <span>Last seen: {formatLastSeen(display.last_seen)}</span>
          </div>

          {display.tags && display.tags.length > 0 && (
            <div className="detail-item">
              <Tag size={14} />
              <div className="tags">
                {display.tags.map(tag => (
                  <span key={tag} className="tag">{tag}</span>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="display-scene-info">
          {display.source === 'registered' ? (
            display.assigned_scene_id ? (
              <div className="scene-assigned">
                <div className="scene-info">
                  <Play size={14} />
                  <span>Scene: <strong>{display.assigned_scene_name}</strong></span>
                </div>
                <button 
                  className="btn btn-sm btn-secondary" 
                  onClick={() => onAssignScene(display)}
                >
                  Change Scene
                </button>
              </div>
            ) : (
              <div className="scene-unassigned">
                <span className="no-scene">No scene assigned</span>
                <button 
                  className="btn btn-sm btn-primary" 
                  onClick={() => onAssignScene(display)}
                >
                  Assign Scene
                </button>
              </div>
            )
          ) : (
            <div className="scene-unassigned">
              <span className="no-scene">Register display to assign scenes</span>
            </div>
          )}
        </div>

        {display.current_image_url && (
          <div className="display-image-section">
            <div className="image-info">
              <div className="image-status">
                <Image size={14} />
                <span>Current Image Available</span>
              </div>
              <div className="image-actions">
                <button 
                  className="btn btn-sm btn-tertiary" 
                  onClick={handleViewImage}
                  title="View Current Image"
                >
                  <Eye size={14} />
                </button>
                <button 
                  className="btn btn-sm btn-tertiary" 
                  onClick={handleRefreshImage}
                  disabled={imageLoading}
                  title="Refresh Image"
                >
                  <RotateCcw size={14} className={imageLoading ? 'spinning' : ''} />
                </button>
              </div>
            </div>
          </div>
        )}

        <div className="display-capabilities">
          <h4>Capabilities</h4>
          <div className="capabilities-list">
            <div className="capability">
              <strong>Formats:</strong> {display.supported_formats?.join(', ') || 'N/A'}
            </div>
            <div className="capability">
              <strong>Version:</strong> {display.client_version || 'Unknown'}
            </div>
          </div>
        </div>
      </div>

      {/* Image Preview Modal */}
      {showImagePreview && (
        <div className="modal-overlay" onClick={() => setShowImagePreview(false)}>
          <div className="modal-content image-preview-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Current Display Image - {display.name}</h3>
              <button 
                className="modal-close" 
                onClick={() => setShowImagePreview(false)}
              >
                ×
              </button>
            </div>
            <div className="modal-body">
              <img
                src={api.getDisplayImageUrl(display.id)}
                alt={`Current display for ${display.name}`}
                onError={() => setImageError(true)}
                style={{
                  maxWidth: '100%',
                  maxHeight: '70vh',
                  objectFit: 'contain'
                }}
              />
              {imageError && (
                <p className="error-message">Failed to load image</p>
              )}
            </div>
            <div className="modal-footer">
              <button 
                className="btn btn-secondary" 
                onClick={() => setShowImagePreview(false)}
              >
                Close
              </button>
              <a 
                href={api.getDisplayImageUrl(display.id)}
                download={`display-${display.name}-current.jpg`}
                className="btn btn-primary"
              >
                Download
              </a>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default DisplayCard;
