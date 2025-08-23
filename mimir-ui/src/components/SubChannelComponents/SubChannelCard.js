import React from 'react';
import { Eye, Edit, Trash2, TestTube, Image, Calendar, Tag } from 'lucide-react';
import './SubChannelCard.css';

const SubChannelCard = ({ 
  subChannel, 
  channelConfig,
  onView, 
  onEdit, 
  onDelete, 
  onTest,
  showActions = true,
  compact = false,
  selectable = false,
  selected = false,
  onSelect
}) => {
  const {
    name,
    description,
    imageCount = 0,
    contentIds = [],
    coverImageId,
    tags = [],
    created,
    metadata = {}
  } = subChannel;

  const getContentLabel = () => {
    if (channelConfig?.contentType === 'image') {
      return imageCount === 1 ? 'image' : 'images';
    }
    return 'items';
  };

  const handleCardClick = () => {
    if (selectable && onSelect) {
      onSelect(subChannel);
    } else if (onView) {
      onView(subChannel);
    }
  };

  return (
    <div 
      className={`subchannel-card ${compact ? 'compact' : ''} ${selectable ? 'selectable' : ''} ${selected ? 'selected' : ''}`}
      onClick={handleCardClick}
    >
      {/* Cover/Thumbnail */}
      <div className="subchannel-cover">
        {coverImageId && channelConfig?.contentType === 'image' ? (
          <img 
            src={`/api/channels/${subChannel.channelId || 'photo_frame'}/data/thumbs/image_${coverImageId}.jpg`}
            alt={name}
            className="cover-image"
            onError={(e) => {
              e.target.style.display = 'none';
              e.target.nextSibling.style.display = 'flex';
            }}
          />
        ) : null}
        <div 
          className="cover-placeholder" 
          style={{ display: coverImageId ? 'none' : 'flex' }}
        >
          <Image size={compact ? 24 : 32} />
          <span>{channelConfig?.label || 'Sub-Channel'}</span>
        </div>
        
        {/* Content count overlay */}
        <div className="content-overlay">
          <span className="content-count">
            <Image size={12} />
            {imageCount || contentIds.length}
          </span>
        </div>

        {/* Selection indicator */}
        {selectable && (
          <div className="selection-indicator">
            <div className={`selection-checkbox ${selected ? 'checked' : ''}`}>
              {selected && '✓'}
            </div>
          </div>
        )}
      </div>

      {/* Content */}
      <div className="subchannel-content">
        <div className="subchannel-header">
          <h4 className="subchannel-name" title={name}>{name}</h4>
          {!compact && showActions && (
            <div className="subchannel-actions">
              {onView && (
                <button
                  className="action-btn"
                  onClick={(e) => {
                    e.stopPropagation();
                    onView(subChannel);
                  }}
                  title="View contents"
                >
                  <Eye size={14} />
                </button>
              )}
              {onEdit && (
                <button
                  className="action-btn"
                  onClick={(e) => {
                    e.stopPropagation();
                    onEdit(subChannel);
                  }}
                  title="Edit"
                >
                  <Edit size={14} />
                </button>
              )}
              {onTest && (
                <button
                  className="action-btn"
                  onClick={(e) => {
                    e.stopPropagation();
                    onTest(subChannel);
                  }}
                  title="Test"
                >
                  <TestTube size={14} />
                </button>
              )}
              {onDelete && (
                <button
                  className="action-btn danger"
                  onClick={(e) => {
                    e.stopPropagation();
                    onDelete(subChannel);
                  }}
                  title="Delete"
                >
                  <Trash2 size={14} />
                </button>
              )}
            </div>
          )}
        </div>

        {!compact && description && (
          <p className="subchannel-description" title={description}>
            {description}
          </p>
        )}

        {/* Stats */}
        <div className="subchannel-stats">
          <span className="stat-item">
            <Image size={12} />
            {imageCount || contentIds.length} {getContentLabel()}
          </span>
          {!compact && created && (
            <span className="stat-item">
              <Calendar size={12} />
              {new Date(created).toLocaleDateString()}
            </span>
          )}
        </div>

        {/* Tags */}
        {!compact && tags.length > 0 && (
          <div className="subchannel-tags">
            {tags.slice(0, 3).map((tag, index) => (
              <span key={index} className="tag">
                <Tag size={10} />
                {tag}
              </span>
            ))}
            {tags.length > 3 && (
              <span className="tag more">+{tags.length - 3}</span>
            )}
          </div>
        )}

        {/* Metadata info */}
        {!compact && Object.keys(metadata).length > 0 && (
          <div className="subchannel-metadata">
            {Object.entries(metadata).slice(0, 2).map(([key, value]) => (
              <span key={key} className="metadata-item">
                <span className="metadata-key">{key}:</span>
                <span className="metadata-value">{String(value)}</span>
              </span>
            ))}
          </div>
        )}

        {/* Compact actions */}
        {compact && showActions && (
          <div className="compact-actions">
            {onView && (
              <button
                className="compact-action-btn"
                onClick={(e) => {
                  e.stopPropagation();
                  onView(subChannel);
                }}
              >
                <Eye size={12} />
              </button>
            )}
            {onEdit && (
              <button
                className="compact-action-btn"
                onClick={(e) => {
                  e.stopPropagation();
                  onEdit(subChannel);
                }}
              >
                <Edit size={12} />
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default SubChannelCard;
