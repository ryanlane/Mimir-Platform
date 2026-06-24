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

import React, { useState, useEffect, useCallback } from 'react';
import { Trash2, Eye, Download, Grid, List, Search, CheckSquare, Square, ArrowLeft, RefreshCw, Move } from 'lucide-react';
import { api } from '../../services/api';
import { LazyImage, usePerformanceMonitoring } from '../../hooks/usePerformance';
import { LoadingState } from '../ErrorHandling/ErrorHandling';
import './GalleryManager.css';

const GalleryImages = ({ gallery, channel, onBack, onRemoveImages }) => {
  const [images, setImages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [viewMode, setViewMode] = useState('grid');
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedImages, setSelectedImages] = useState(new Set());
  const [draggedImage, setDraggedImage] = useState(null);
  const [dragOverImage, setDragOverImage] = useState(null);
  const [isReordering, setIsReordering] = useState(false);
  
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

  // Drag and drop handlers
  const handleDragStart = (e, image) => {
    setDraggedImage(image);
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', image.id);
    
    // Add visual feedback - use setTimeout to allow class to be applied after drag starts
    setTimeout(() => {
      e.target.classList.add('dragging');
    }, 0);
  };

  const handleDragEnd = (e) => {
    setDraggedImage(null);
    setDragOverImage(null);
    e.target.classList.remove('dragging');
  };

  const handleDragOver = (e, targetImage) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    setDragOverImage(targetImage);
  };

  const handleDragLeave = (e) => {
    // Only clear drag over if leaving the image container entirely
    if (!e.currentTarget.contains(e.relatedTarget)) {
      setDragOverImage(null);
    }
  };

  const handleDrop = async (e, targetImage) => {
    e.preventDefault();
    
    if (!draggedImage || draggedImage.id === targetImage.id) {
      setDraggedImage(null);
      setDragOverImage(null);
      return;
    }

    try {
      setIsReordering(true);
      setError(null);

      // Call the reorder API
      await api.reorderSubChannelImages(
        channel.id,
        gallery.id,
        draggedImage.id,
        targetImage.id
      );

      // Reload the gallery to show the new order
      await loadGalleryImages();
      
    } catch (err) {
      setError(`Failed to reorder images: ${err.message}`);
      console.error('Error reordering images:', err);
    } finally {
      setIsReordering(false);
      setDraggedImage(null);
      setDragOverImage(null);
    }
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
            <span className="image-count">
              {filteredImages().length} images
              {isReordering && <span className="reorder-status"> • Reordering...</span>}
            </span>
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
          
          {filteredImages().length > 1 && (
            <div className="reorder-hint">
              <Move size={14} />
              <span>Drag to reorder</span>
            </div>
          )}
          
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
              const isDragOver = dragOverImage?.id === image.id;
              
              return (
                <div
                  key={image.id}
                  className={`gallery-image-item ${selected ? 'selected' : ''} ${isDragOver ? 'drag-over' : ''}`}
                  draggable="true"
                  onDragStart={(e) => handleDragStart(e, image)}
                  onDragEnd={handleDragEnd}
                  onDragOver={(e) => handleDragOver(e, image)}
                  onDragLeave={handleDragLeave}
                  onDrop={(e) => handleDrop(e, image)}
                  style={{
                    cursor: draggedImage ? 'move' : 'default'
                  }}
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
