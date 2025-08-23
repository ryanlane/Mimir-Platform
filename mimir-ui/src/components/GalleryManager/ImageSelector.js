import React, { useState, useMemo } from 'react';
import { X, Check, Search, Grid, List, CheckSquare, Square, Image as ImageIcon } from 'lucide-react';

const ImageSelector = ({ images, galleryImages, onAssign, onClose }) => {
  const [selectedImages, setSelectedImages] = useState(new Set());
  const [searchTerm, setSearchTerm] = useState('');
  const [viewMode, setViewMode] = useState('grid');
  const [showOnlyUnassigned, setShowOnlyUnassigned] = useState(false);

  // Filter images based on search and assignment status
  const filteredImages = useMemo(() => {
    return images.filter(image => {
      // Search filter
      const matchesSearch = searchTerm === '' || 
        image.original_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        image.title?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        image.description?.toLowerCase().includes(searchTerm.toLowerCase());

      // Assignment filter
      const isInGallery = galleryImages.includes(String(image.id));
      const matchesAssignment = !showOnlyUnassigned || !isInGallery;

      return matchesSearch && matchesAssignment;
    });
  }, [images, searchTerm, showOnlyUnassigned, galleryImages]);

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
    if (selectedImages.size === filteredImages.length) {
      setSelectedImages(new Set());
    } else {
      setSelectedImages(new Set(filteredImages.map(img => img.id)));
    }
  };

  const handleAssign = () => {
    if (selectedImages.size > 0) {
      onAssign(Array.from(selectedImages).map(String));
      onClose();
    }
  };

  const isImageInGallery = (imageId) => {
    return galleryImages.includes(String(imageId));
  };

  const isImageSelected = (imageId) => {
    return selectedImages.has(imageId);
  };

  return (
    <div className="image-selector-overlay">
      <div className="image-selector">
        {/* Header */}
        <div className="image-selector-header">
          <div className="header-content">
            <h2>Add Images to Gallery</h2>
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
              
              <div className="filter-controls">
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={showOnlyUnassigned}
                    onChange={(e) => setShowOnlyUnassigned(e.target.checked)}
                  />
                  Show only unassigned
                </label>
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
          
          <button className="close-btn" onClick={onClose}>
            <X size={20} />
          </button>
        </div>

        {/* Selection Controls */}
        <div className="selection-controls">
          <div className="selection-info">
            <button onClick={handleSelectAll} className="select-all-btn">
              {selectedImages.size === filteredImages.length && filteredImages.length > 0 ? (
                <CheckSquare size={16} />
              ) : (
                <Square size={16} />
              )}
              {selectedImages.size === filteredImages.length && filteredImages.length > 0 
                ? 'Deselect All' 
                : 'Select All'
              }
            </button>
            <span className="selection-count">
              {selectedImages.size} of {filteredImages.length} images selected
            </span>
          </div>
          
          <div className="selection-actions">
            <button
              className="btn btn-primary"
              onClick={handleAssign}
              disabled={selectedImages.size === 0}
            >
              <Check size={16} />
              Add {selectedImages.size} Image{selectedImages.size !== 1 ? 's' : ''}
            </button>
            <button className="btn btn-secondary" onClick={onClose}>
              Cancel
            </button>
          </div>
        </div>

        {/* Images Grid/List */}
        <div className={`images-container ${viewMode}`}>
          {filteredImages.length === 0 ? (
            <div className="empty-state">
              <ImageIcon size={48} />
              <h3>No Images Found</h3>
              <p>
                {searchTerm ? (
                  <>No images match your search criteria.</>
                ) : showOnlyUnassigned ? (
                  <>All images are already assigned to this gallery.</>
                ) : (
                  <>No images available to assign.</>
                )}
              </p>
            </div>
          ) : (
            <div className={`images-${viewMode}`}>
              {filteredImages.map(image => {
                const inGallery = isImageInGallery(image.id);
                const selected = isImageSelected(image.id);
                
                return (
                  <div
                    key={image.id}
                    className={`image-item ${selected ? 'selected' : ''} ${inGallery ? 'in-gallery' : ''}`}
                    onClick={() => !inGallery && handleToggleImage(image.id)}
                  >
                    {viewMode === 'grid' ? (
                      <>
                        <div className="image-thumbnail">
                          <img
                            src={`/api/channels/photo_frame/data/thumbs/${image.filename}`}
                            alt={image.title || image.original_name}
                            loading="lazy"
                          />
                          <div className="image-overlay">
                            <div className="selection-indicator">
                              {inGallery ? (
                                <div className="already-assigned">Already in gallery</div>
                              ) : (
                                <div className="checkbox">
                                  {selected ? <CheckSquare size={20} /> : <Square size={20} />}
                                </div>
                              )}
                            </div>
                          </div>
                        </div>
                        <div className="image-info">
                          <div className="image-name">
                            {image.title || image.original_name}
                          </div>
                          {image.description && (
                            <div className="image-description">{image.description}</div>
                          )}
                        </div>
                      </>
                    ) : (
                      <>
                        <div className="list-checkbox">
                          {inGallery ? (
                            <div className="already-assigned-indicator">✓</div>
                          ) : (
                            <div className="checkbox">
                              {selected ? <CheckSquare size={16} /> : <Square size={16} />}
                            </div>
                          )}
                        </div>
                        <div className="list-thumbnail">
                          <img
                            src={`/api/channels/photo_frame/data/thumbs/${image.filename}`}
                            alt={image.title || image.original_name}
                            loading="lazy"
                          />
                        </div>
                        <div className="list-info">
                          <div className="image-name">
                            {image.title || image.original_name}
                          </div>
                          {image.description && (
                            <div className="image-description">{image.description}</div>
                          )}
                          <div className="image-meta">
                            Uploaded: {new Date(image.upload_time).toLocaleDateString()}
                            {inGallery && <span className="in-gallery-badge">In Gallery</span>}
                          </div>
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
    </div>
  );
};

export default ImageSelector;
