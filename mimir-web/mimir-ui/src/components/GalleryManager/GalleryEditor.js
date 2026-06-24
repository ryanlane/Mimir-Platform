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
import { Check, X, Plus } from 'lucide-react';

const GalleryEditor = ({ gallery, isCreating, onSave, onCancel }) => {
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    tags: []
  });
  const [newTag, setNewTag] = useState('');
  const [saving, setSaving] = useState(false);

  // Initialize form data
  useEffect(() => {
    if (gallery) {
      setFormData({
        name: gallery.name || '',
        description: gallery.description || '',
        tags: gallery.tags || []
      });
    } else {
      setFormData({
        name: '',
        description: '',
        tags: []
      });
    }
  }, [gallery]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!formData.name.trim()) {
      alert('Gallery name is required');
      return;
    }

    setSaving(true);
    try {
      await onSave(formData);
    } catch (err) {
      console.error('Error saving gallery:', err);
    } finally {
      setSaving(false);
    }
  };

  const handleAddTag = () => {
    const tag = newTag.trim();
    if (tag && !formData.tags.includes(tag)) {
      setFormData({
        ...formData,
        tags: [...formData.tags, tag]
      });
      setNewTag('');
    }
  };

  const handleRemoveTag = (tagToRemove) => {
    setFormData({
      ...formData,
      tags: formData.tags.filter(tag => tag !== tagToRemove)
    });
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleAddTag();
    }
  };

  return (
    <div className="gallery-editor">
      <div className="editor-header">
        <h3>{isCreating ? 'Create New Gallery' : 'Edit Gallery'}</h3>
        <p className="editor-description">
          {isCreating 
            ? 'Create a new gallery to organize your photos into themed collections.'
            : 'Update the gallery information and organization.'
          }
        </p>
      </div>

      <form onSubmit={handleSubmit} className="gallery-form">
        {/* Gallery Name */}
        <div className="form-group">
          <label htmlFor="gallery-name" className="form-label">
            Gallery Name *
          </label>
          <input
            id="gallery-name"
            type="text"
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            placeholder="e.g., Family Photos, Vacation 2024, Nature"
            className="form-input"
            required
            disabled={saving}
          />
          <div className="form-help">
            Choose a descriptive name that helps you identify this collection.
          </div>
        </div>

        {/* Gallery Description */}
        <div className="form-group">
          <label htmlFor="gallery-description" className="form-label">
            Description
          </label>
          <textarea
            id="gallery-description"
            value={formData.description}
            onChange={(e) => setFormData({ ...formData, description: e.target.value })}
            placeholder="Describe what kind of photos are in this gallery..."
            className="form-textarea"
            rows={3}
            disabled={saving}
          />
          <div className="form-help">
            Optional description to help you remember what this gallery contains.
          </div>
        </div>

        {/* Tags */}
        <div className="form-group">
          <label className="form-label">Tags</label>
          <div className="tags-input-container">
            <div className="tag-input-row">
              <input
                type="text"
                value={newTag}
                onChange={(e) => setNewTag(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="Add a tag..."
                className="tag-input"
                disabled={saving}
              />
              <button
                type="button"
                onClick={handleAddTag}
                className="add-tag-btn"
                disabled={!newTag.trim() || saving}
              >
                <Plus size={16} />
              </button>
            </div>
            
            {formData.tags.length > 0 && (
              <div className="tags-list">
                {formData.tags.map((tag, index) => (
                  <span key={index} className="tag">
                    {tag}
                    <button
                      type="button"
                      onClick={() => handleRemoveTag(tag)}
                      className="remove-tag-btn"
                      disabled={saving}
                    >
                      <X size={12} />
                    </button>
                  </span>
                ))}
              </div>
            )}
          </div>
          <div className="form-help">
            Tags help categorize and search for galleries (e.g., "family", "outdoor", "portraits").
          </div>
        </div>

        {/* Action Buttons */}
        <div className="form-actions">
          <button
            type="submit"
            className="btn btn-primary"
            disabled={saving || !formData.name.trim()}
          >
            <Check size={16} />
            {saving ? 'Saving...' : (isCreating ? 'Create Gallery' : 'Update Gallery')}
          </button>
          <button
            type="button"
            onClick={onCancel}
            className="btn btn-secondary"
            disabled={saving}
          >
            <X size={16} />
            Cancel
          </button>
        </div>
      </form>

      {/* Additional Info */}
      {!isCreating && gallery && (
        <div className="gallery-metadata">
          <h4>Gallery Information</h4>
          <div className="metadata-grid">
            <div className="metadata-item">
              <span className="metadata-label">ID:</span>
              <code className="metadata-value">{gallery.id}</code>
            </div>
            <div className="metadata-item">
              <span className="metadata-label">Created:</span>
              <span className="metadata-value">
                {new Date(gallery.created).toLocaleString()}
              </span>
            </div>
            <div className="metadata-item">
              <span className="metadata-label">Last Modified:</span>
              <span className="metadata-value">
                {new Date(gallery.modified).toLocaleString()}
              </span>
            </div>
            <div className="metadata-item">
              <span className="metadata-label">Images:</span>
              <span className="metadata-value">{gallery.imageCount || 0}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default GalleryEditor;
