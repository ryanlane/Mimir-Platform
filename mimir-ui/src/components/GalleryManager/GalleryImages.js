import React, { useState, useEffect, useCallback } from 'react';
import { Trash2, Eye, Download, Grid, List, Search, CheckSquare, Square, ArrowLeft, RefreshCw } from 'lucide-react';
import { api } from '../../services/api';
import { LazyImage, usePerformanceMonitoring } from '../../hooks/usePerformance';
import { LoadingState } from '../ErrorHandling/ErrorHandling';

const GalleryImages = ({ gallery, channel, onBack, onRemoveImages }) => {
  const [images, setImages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [viewMode, setViewMode] = useState('grid');
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedImages, setSelectedImages] = useState(new Set());
  
  // Performance monitoring
  const { measureOperation } = usePerformanceMonitoring('GalleryImages');

  // Filter images based on search
  function filteredImages() {
    return measureOperation('filter-images', () => {
      if (!searchTerm) return images;
      return images.filter(image => 
        image.filename?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        image.name?.toLowerCase().includes(searchTerm.toLowerCase())
      );
    });
  }

  // Load gallery images
  const loadGalleryImages = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      
      const response = await api.getSubChannelContent(channel.id, gallery.id);
      setImages(response.data?.content || []);
      
    } catch (err) {
      setError(`Failed to load gallery images: ${err.message}`);
      console.error('Error loading gallery images:', err);
    } finally {
      setLoading(false);
    }
  }, [channel.id, gallery.id]);

  useEffect(() => {
    loadGalleryImages();
  }, [loadGalleryImages]);

  const handleToggleImage = (imageId) => {
    const newSelected = new Set(selectedImages);
    if (newSelected.has(imageId)) {
      newSelected.delete(imageId);
    } else {
      newSelected.add(imageId);
    }
    setSelectedImages(newSelected);
  };

  const handleSelectAll = () => {
    const filtered = filteredImages();
    if (selectedImages.size === filtered.length) {
      setSelectedImages(new Set());
    } else {
      setSelectedImages(new Set(filtered.map(img => img.id)));
    }
  };

  const handleRemoveSelected = async () => {
    if (selectedImages.size === 0) return;
    
    const imageIds = Array.from(selectedImages);
    if (!window.confirm(`Remove ${imageIds.length} image${imageIds.length !== 1 ? 's' : ''} from this gallery? The images will not be deleted, just removed from the gallery.`)) {
      return;
    }

    try {
      await onRemoveImages(gallery.id, imageIds);
      await loadGalleryImages();
      setSelectedImages(new Set());
    } catch (err) {
      setError(`Failed to remove images: ${err.message}`);
    }
  };

  const handleViewImage = (image) => {
    // Open image in new tab
    window.open(image.uploadUrl, '_blank');
  };

  if (loading) {
    return (
      <LoadingState 
        type="spinner"
        message="Loading gallery images..."
        size="large"
      />
    );
  }

  if (error) {
    return (
      <div className="gallery-images-error">
        <p>{error}</p>
        <button onClick={loadGalleryImages} className="btn btn-primary">
          <RefreshCw size={16} />
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="gallery-images">
      {/* Header Controls */}
      <div className="gallery-images-header">
        <div className="header-left">
          <button onClick={onBack} className="back-btn">
            <ArrowLeft size={16} />
            Back to Galleries
          </button>
          <div className="gallery-title">
            <h3>{gallery.name}</h3>
            <span className="image-count">{filteredImages().length} images</span>
          </div>
        </div>
        
        <div className="header-controls">
          <div className="search-box">
            <Search size={16} />
            <input
              type="text"
              placeholder="Search images..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>
          
          <div className="view-controls">
            <button
              className={`view-btn ${viewMode === 'grid' ? 'active' : ''}`}
              onClick={() => setViewMode('grid')}
            >
              <Grid size={16} />
            </button>
            <button
              className={`view-btn ${viewMode === 'list' ? 'active' : ''}`}
              onClick={() => setViewMode('list')}
            >
              <List size={16} />
            </button>
          </div>
        </div>
      </div>

      {/* Selection Controls */}
      {filteredImages().length > 0 && (
        <div className="selection-controls">
          <div className="selection-info">
            <button onClick={handleSelectAll} className="select-all-btn">
              {selectedImages.size === filteredImages().length && filteredImages().length > 0 ? (
                <CheckSquare size={16} />
              ) : (
                <Square size={16} />
              )}
              {selectedImages.size === filteredImages().length && filteredImages().length > 0 
                ? 'Deselect All' 
                : 'Select All'
              }
            </button>
            <span className="selection-count">
              {selectedImages.size} of {filteredImages().length} selected
            </span>
          </div>
          
          {selectedImages.size > 0 && (
            <div className="selection-actions">
              <button
                className="btn btn-danger"
                onClick={handleRemoveSelected}
              >
                <Trash2 size={16} />
                Remove from Gallery
              </button>
            </div>
          )}
        </div>
      )}

      {/* Images Display */}
      <div className={`gallery-images-content ${viewMode}`}>
        {filteredImages().length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon">
              <Grid size={48} />
            </div>
            <h3>No Images in Gallery</h3>
            <p>This gallery doesn't contain any images yet.</p>
            <button onClick={onBack} className="btn btn-primary">
              Add Images to Gallery
            </button>
          </div>
        ) : (
          <div className={`images-${viewMode}`}>
            {filteredImages().map(image => {
              const selected = selectedImages.has(image.id);
              
              return (
                <div
                  key={image.id}
                  className={`gallery-image-item ${selected ? 'selected' : ''}`}
                >
                  {viewMode === 'grid' ? (
                    <>
                      <div className="image-thumbnail">
                        <LazyImage
                          src={image.thumbnailUrl}
                          alt={image.name}
                          className="gallery-thumbnail-image"
                          placeholder={
                            <div className="image-placeholder">
                              <Grid size={24} />
                              <span>Loading...</span>
                            </div>
                          }
                          errorFallback={
                            <div className="image-error">
                              <Grid size={24} />
                              <span>Failed to load</span>
                            </div>
                          }
                        />
                        <div className="image-overlay">
                          <div className="overlay-actions">
                            <button
                              className="overlay-btn"
                              onClick={() => handleViewImage(image)}
                              title="View full image"
                            >
                              <Eye size={16} />
                            </button>
                            <button
                              className="overlay-btn"
                              onClick={() => window.open(image.uploadUrl, '_blank')}
                              title="Download image"
                            >
                              <Download size={16} />
                            </button>
                          </div>
                          <div className="selection-overlay">
                            <button
                              className="selection-btn"
                              onClick={() => handleToggleImage(image.id)}
                            >
                              {selected ? <CheckSquare size={20} /> : <Square size={20} />}
                            </button>
                          </div>
                        </div>
                      </div>
                      <div className="image-info">
                        <div className="image-name">{image.name}</div>
                        {image.description && (
                          <div className="image-description">{image.description}</div>
                        )}
                      </div>
                    </>
                  ) : (
                    <>
                      <div className="list-selection">
                        <button
                          className="selection-btn"
                          onClick={() => handleToggleImage(image.id)}
                        >
                          {selected ? <CheckSquare size={16} /> : <Square size={16} />}
                        </button>
                      </div>
                      <div className="list-thumbnail">
                        <img
                          src={image.thumbnailUrl}
                          alt={image.name}
                          loading="lazy"
                        />
                      </div>
                      <div className="list-info">
                        <div className="image-name">{image.name}</div>
                        {image.description && (
                          <div className="image-description">{image.description}</div>
                        )}
                        <div className="image-meta">
                          Added: {new Date(image.uploaded).toLocaleDateString()}
                        </div>
                      </div>
                      <div className="list-actions">
                        <button
                          className="action-btn"
                          onClick={() => handleViewImage(image)}
                          title="View full image"
                        >
                          <Eye size={16} />
                        </button>
                        <button
                          className="action-btn"
                          onClick={() => window.open(image.uploadUrl, '_blank')}
                          title="Download image"
                        >
                          <Download size={16} />
                        </button>
                      </div>
                    </>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

export default GalleryImages;
