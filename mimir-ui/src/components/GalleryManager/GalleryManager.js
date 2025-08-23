import React, { useState, useEffect, useCallback } from 'react';
import { X, Plus, Grid, List, Search } from 'lucide-react';
import { api } from '../../services/api';
import ImageSelector from './ImageSelector';
import GalleryGrid from './GalleryGrid';
import GalleryEditor from './GalleryEditor';
import GalleryImages from './GalleryImages';
import './GalleryManager.css';

const GalleryManager = ({ channel, onClose }) => {
  // State management
  const [galleries, setGalleries] = useState([]);
  const [allImages, setAllImages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  // UI state
  const [activeView, setActiveView] = useState('galleries'); // 'galleries' | 'images' | 'editor'
  const [selectedGallery, setSelectedGallery] = useState(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [editingGallery, setEditingGallery] = useState(null);
  const [showImageSelector, setShowImageSelector] = useState(false);
  
  // Search and filter state
  const [searchTerm, setSearchTerm] = useState('');
  const [viewMode, setViewMode] = useState('grid'); // 'grid' | 'list'

  // Load galleries data
  const loadGalleries = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      
      const [galleriesResponse, imagesResponse] = await Promise.all([
        api.getSubChannels(channel.id),
        api.get(`/api/channels/${channel.id}/images`)
      ]);
      
      setGalleries(galleriesResponse.data || []);
      setAllImages(imagesResponse.data || []);
      
    } catch (err) {
      setError(`Failed to load gallery data: ${err.message}`);
      console.error('Error loading galleries:', err);
    } finally {
      setLoading(false);
    }
  }, [channel.id]);

  useEffect(() => {
    loadGalleries();
  }, [loadGalleries]);

  // Gallery CRUD operations
  const handleCreateGallery = async (galleryData) => {
    try {
      await api.createSubChannel(channel.id, galleryData);
      setShowCreateForm(false);
      await loadGalleries();
    } catch (err) {
      setError(`Failed to create gallery: ${err.message}`);
    }
  };

  const handleUpdateGallery = async (galleryId, galleryData) => {
    try {
      await api.updateSubChannel(channel.id, galleryId, galleryData);
      setEditingGallery(null);
      await loadGalleries();
    } catch (err) {
      setError(`Failed to update gallery: ${err.message}`);
    }
  };

  const handleDeleteGallery = async (galleryId) => {
    if (!window.confirm('Are you sure you want to delete this gallery? Images will not be deleted, only the gallery organization.')) {
      return;
    }

    try {
      await api.deleteSubChannel(channel.id, galleryId);
      if (selectedGallery?.id === galleryId) {
        setSelectedGallery(null);
        setActiveView('galleries');
      }
      await loadGalleries();
    } catch (err) {
      setError(`Failed to delete gallery: ${err.message}`);
    }
  };

  // Image assignment operations
  const handleAssignImages = async (galleryId, imageIds, action = 'add') => {
    try {
      await api.assignContentToSubChannel(channel.id, galleryId, imageIds, action);
      await loadGalleries();
      
      // Update selected gallery if it's currently being viewed
      if (selectedGallery?.id === galleryId) {
        const updatedGallery = galleries.find(g => g.id === galleryId);
        setSelectedGallery(updatedGallery);
      }
    } catch (err) {
      setError(`Failed to assign images: ${err.message}`);
    }
  };

  const handleRemoveImages = async (galleryId, imageIds) => {
    try {
      await api.assignContentToSubChannel(channel.id, galleryId, imageIds, 'remove');
      await loadGalleries();
      
      // Update selected gallery if it's currently being viewed
      if (selectedGallery?.id === galleryId) {
        const updatedGallery = galleries.find(g => g.id === galleryId);
        setSelectedGallery(updatedGallery);
      }
    } catch (err) {
      setError(`Failed to remove images: ${err.message}`);
    }
  };

  // UI event handlers
  const handleViewGallery = (gallery) => {
    setSelectedGallery(gallery);
    setActiveView('images');
  };

  const handleEditGallery = (gallery) => {
    setEditingGallery(gallery);
    setActiveView('editor');
  };

  const handleBackToGalleries = () => {
    setSelectedGallery(null);
    setEditingGallery(null);
    setActiveView('galleries');
  };

  const handleTestGalleryImage = async (galleryId) => {
    try {
      await api.requestChannelImage(channel.id, {
        resolution: [800, 600],
        orientation: 'landscape'
      }, galleryId);
      alert('Test image generated successfully for gallery!');
    } catch (err) {
      alert(`Failed to generate test image: ${err.message}`);
    }
  };

  // Filter galleries based on search
  const filteredGalleries = galleries.filter(gallery =>
    gallery.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    (gallery.description || '').toLowerCase().includes(searchTerm.toLowerCase())
  );

  if (loading) {
    return (
      <div className="gallery-manager-overlay">
        <div className="gallery-manager">
          <div className="gallery-manager-header">
            <h2>Loading Galleries...</h2>
            <button className="close-btn" onClick={onClose}>
              <X size={20} />
            </button>
          </div>
          <div className="loading">Loading gallery data for {channel.name}...</div>
        </div>
      </div>
    );
  }

  return (
    <div className="gallery-manager-overlay">
      <div className="gallery-manager">
        {/* Header */}
        <div className="gallery-manager-header">
          <div className="header-content">
            <div className="header-title">
              {activeView === 'galleries' && <h2>Gallery Manager - {channel.name}</h2>}
              {activeView === 'images' && selectedGallery && (
                <div className="breadcrumb">
                  <button onClick={handleBackToGalleries} className="breadcrumb-link">
                    Gallery Manager
                  </button>
                  <span className="breadcrumb-separator">/</span>
                  <h2>{selectedGallery.name}</h2>
                </div>
              )}
              {activeView === 'editor' && (
                <div className="breadcrumb">
                  <button onClick={handleBackToGalleries} className="breadcrumb-link">
                    Gallery Manager
                  </button>
                  <span className="breadcrumb-separator">/</span>
                  <h2>{editingGallery ? 'Edit Gallery' : 'Create Gallery'}</h2>
                </div>
              )}
            </div>
            
            {/* View controls */}
            {activeView === 'galleries' && (
              <div className="header-controls">
                <div className="search-box">
                  <Search size={16} />
                  <input
                    type="text"
                    placeholder="Search galleries..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                  />
                </div>
                <button 
                  className="btn btn-primary"
                  onClick={() => {
                    setShowCreateForm(true);
                    setActiveView('editor');
                  }}
                >
                  <Plus size={16} />
                  New Gallery
                </button>
              </div>
            )}
            
            {activeView === 'images' && selectedGallery && (
              <div className="header-controls">
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
                <button 
                  className="btn btn-primary"
                  onClick={() => setShowImageSelector(true)}
                >
                  <Plus size={16} />
                  Add Images
                </button>
              </div>
            )}
          </div>
          
          <button className="close-btn" onClick={onClose}>
            <X size={20} />
          </button>
        </div>

        {/* Error message */}
        {error && (
          <div className="error-message">
            <span>{error}</span>
            <button onClick={() => setError(null)}>×</button>
          </div>
        )}

        {/* Content */}
        <div className="gallery-manager-body">
          {activeView === 'galleries' && (
            <GalleryGrid
              galleries={filteredGalleries}
              onViewGallery={handleViewGallery}
              onEditGallery={handleEditGallery}
              onDeleteGallery={handleDeleteGallery}
              onTestGallery={handleTestGalleryImage}
            />
          )}
          
          {activeView === 'images' && selectedGallery && (
            <GalleryImages
              gallery={selectedGallery}
              channel={channel}
              onBack={handleBackToGalleries}
              onRemoveImages={handleRemoveImages}
            />
          )}
          
          {activeView === 'editor' && (
            <GalleryEditor
              gallery={editingGallery}
              isCreating={showCreateForm}
              onSave={editingGallery ? 
                (data) => handleUpdateGallery(editingGallery.id, data) :
                handleCreateGallery
              }
              onCancel={handleBackToGalleries}
            />
          )}
        </div>

        {/* Image Selector Modal */}
        {showImageSelector && selectedGallery && (
          <ImageSelector
            images={allImages}
            galleryImages={selectedGallery.contentIds || []}
            onAssign={(imageIds) => handleAssignImages(selectedGallery.id, imageIds)}
            onClose={() => setShowImageSelector(false)}
          />
        )}
      </div>
    </div>
  );
};

export default GalleryManager;
