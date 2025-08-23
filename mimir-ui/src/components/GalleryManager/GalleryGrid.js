import React from 'react';
import { Image, Edit, Trash2, Eye, TestTube } from 'lucide-react';

const GalleryGrid = ({ 
  galleries, 
  onViewGallery, 
  onEditGallery, 
  onDeleteGallery, 
  onTestGallery 
}) => {
  if (galleries.length === 0) {
    return (
      <div className="empty-state">
        <div className="empty-icon">
          <Image size={48} />
        </div>
        <h3>No Galleries Yet</h3>
        <p>Create your first gallery to organize your photos into collections.</p>
        <p>Galleries help you group related images together, like "Family Photos", "Vacation 2024", or "Nature".</p>
      </div>
    );
  }

  return (
    <div className="galleries-grid">
      {galleries.map(gallery => (
        <div key={gallery.id} className="gallery-card">
          {/* Cover Image */}
          <div className="gallery-cover">
            {gallery.coverImageId ? (
              <img 
                src={`/api/channels/photo_frame/data/thumbs/image_${gallery.coverImageId}.jpg`}
                alt={gallery.name}
                className="cover-image"
                onError={(e) => {
                  e.target.style.display = 'none';
                  e.target.nextSibling.style.display = 'flex';
                }}
              />
            ) : null}
            <div 
              className="cover-placeholder" 
              style={{ display: gallery.coverImageId ? 'none' : 'flex' }}
            >
              <Image size={32} />
              <span>No Cover</span>
            </div>
            
            {/* Overlay with image count */}
            <div className="gallery-overlay">
              <span className="image-count">
                <Image size={14} />
                {gallery.imageCount || 0}
              </span>
            </div>
          </div>

          {/* Gallery Info */}
          <div className="gallery-info">
            <h4 className="gallery-name">{gallery.name}</h4>
            {gallery.description && (
              <p className="gallery-description">{gallery.description}</p>
            )}
            
            <div className="gallery-meta">
              <span className="meta-item">
                ID: <code>{gallery.id}</code>
              </span>
              <span className="meta-item">
                Created: {new Date(gallery.created).toLocaleDateString()}
              </span>
              {gallery.modified !== gallery.created && (
                <span className="meta-item">
                  Updated: {new Date(gallery.modified).toLocaleDateString()}
                </span>
              )}
            </div>

            {/* Tags */}
            {gallery.tags && gallery.tags.length > 0 && (
              <div className="gallery-tags">
                {gallery.tags.map((tag, index) => (
                  <span key={index} className="tag">{tag}</span>
                ))}
              </div>
            )}
          </div>

          {/* Actions */}
          <div className="gallery-actions">
            <button
              className="action-btn primary"
              onClick={() => onViewGallery(gallery)}
              title="View gallery contents"
            >
              <Eye size={16} />
              View
            </button>
            <button
              className="action-btn"
              onClick={() => onEditGallery(gallery)}
              title="Edit gallery"
            >
              <Edit size={16} />
              Edit
            </button>
            <button
              className="action-btn"
              onClick={() => onTestGallery(gallery.id)}
              title="Test image generation"
            >
              <TestTube size={16} />
              Test
            </button>
            <button
              className="action-btn danger"
              onClick={() => onDeleteGallery(gallery.id)}
              title="Delete gallery"
            >
              <Trash2 size={16} />
              Delete
            </button>
          </div>
        </div>
      ))}
    </div>
  );
};

export default GalleryGrid;
