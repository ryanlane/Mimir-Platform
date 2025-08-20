// Display Registration component for registering new display clients
import React, { useState } from 'react';
import { Monitor, MapPin, Tag, Settings } from 'lucide-react';
import { api } from '../../services/api';

const DisplayRegistration = ({ onClose, onSuccess }) => {
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    location: '',
    capabilities: {
      resolution: [1920, 1080],
      supported_formats: ['jpg', 'png'],
      orientation: 'landscape',
      refresh_rate_hz: 60
    },
    tags: [],
    client_version: '1.0.0'
  });
  
  const [tagInput, setTagInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleInputChange = (field, value) => {
    if (field.includes('.')) {
      const [parent, child] = field.split('.');
      setFormData(prev => ({
        ...prev,
        [parent]: {
          ...prev[parent],
          [child]: value
        }
      }));
    } else {
      setFormData(prev => ({
        ...prev,
        [field]: value
      }));
    }
  };

  const handleResolutionChange = (index, value) => {
    const newResolution = [...formData.capabilities.resolution];
    newResolution[index] = parseInt(value) || 0;
    handleInputChange('capabilities.resolution', newResolution);
  };

  const addTag = () => {
    if (tagInput.trim() && !formData.tags.includes(tagInput.trim())) {
      setFormData(prev => ({
        ...prev,
        tags: [...prev.tags, tagInput.trim()]
      }));
      setTagInput('');
    }
  };

  const removeTag = (tagToRemove) => {
    setFormData(prev => ({
      ...prev,
      tags: prev.tags.filter(tag => tag !== tagToRemove)
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!formData.name.trim()) {
      setError('Display name is required');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const response = await api.registerDisplay(formData);
      console.log('✅ Display registered successfully:', response.data);
      onSuccess(response.data);
    } catch (error) {
      console.error('Error registering display:', error);
      setError(error.response?.data?.detail || error.message || 'Failed to register display');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content registration-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>
            <Monitor size={24} />
            Register New Display Client
          </h2>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="modal-body">
            {error && (
              <div className="error-message">
                {error}
              </div>
            )}

            <div className="form-section">
              <h3>Basic Information</h3>
              <div className="form-group">
                <label>Display Name *</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => handleInputChange('name', e.target.value)}
                  placeholder="e.g., Conference Room Display"
                  required
                />
              </div>

              <div className="form-group">
                <label>Description</label>
                <textarea
                  value={formData.description}
                  onChange={(e) => handleInputChange('description', e.target.value)}
                  placeholder="Brief description of the display purpose"
                  rows={3}
                />
              </div>

              <div className="form-group">
                <label>
                  <MapPin size={16} />
                  Location
                </label>
                <input
                  type="text"
                  value={formData.location}
                  onChange={(e) => handleInputChange('location', e.target.value)}
                  placeholder="e.g., Building A - Room 203"
                />
              </div>
            </div>

            <div className="form-section">
              <h3>
                <Settings size={18} />
                Display Capabilities
              </h3>
              
              <div className="form-row">
                <div className="form-group">
                  <label>Resolution Width</label>
                  <input
                    type="number"
                    value={formData.capabilities.resolution[0]}
                    onChange={(e) => handleResolutionChange(0, e.target.value)}
                    min="1"
                    step="1"
                  />
                </div>
                <div className="form-group">
                  <label>Resolution Height</label>
                  <input
                    type="number"
                    value={formData.capabilities.resolution[1]}
                    onChange={(e) => handleResolutionChange(1, e.target.value)}
                    min="1"
                    step="1"
                  />
                </div>
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>Orientation</label>
                  <select
                    value={formData.capabilities.orientation}
                    onChange={(e) => handleInputChange('capabilities.orientation', e.target.value)}
                  >
                    <option value="landscape">Landscape</option>
                    <option value="portrait">Portrait</option>
                  </select>
                </div>
                <div className="form-group">
                  <label>Refresh Rate (Hz)</label>
                  <input
                    type="number"
                    value={formData.capabilities.refresh_rate_hz}
                    onChange={(e) => handleInputChange('capabilities.refresh_rate_hz', parseInt(e.target.value) || 60)}
                    min="1"
                    step="1"
                  />
                </div>
              </div>

              <div className="form-group">
                <label>Supported Formats</label>
                <div className="checkbox-group">
                  {['jpg', 'png', 'gif', 'webp'].map(format => (
                    <label key={format} className="checkbox-label">
                      <input
                        type="checkbox"
                        checked={formData.capabilities.supported_formats.includes(format)}
                        onChange={(e) => {
                          if (e.target.checked) {
                            handleInputChange('capabilities.supported_formats', [...formData.capabilities.supported_formats, format]);
                          } else {
                            handleInputChange('capabilities.supported_formats', formData.capabilities.supported_formats.filter(f => f !== format));
                          }
                        }}
                      />
                      {format.toUpperCase()}
                    </label>
                  ))}
                </div>
              </div>
            </div>

            <div className="form-section">
              <h3>
                <Tag size={18} />
                Tags
              </h3>
              <div className="form-group">
                <div className="tag-input">
                  <input
                    type="text"
                    value={tagInput}
                    onChange={(e) => setTagInput(e.target.value)}
                    placeholder="Add a tag"
                    onKeyPress={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault();
                        addTag();
                      }
                    }}
                  />
                  <button 
                    type="button" 
                    className="btn btn-sm btn-secondary" 
                    onClick={addTag}
                  >
                    Add
                  </button>
                </div>
                {formData.tags.length > 0 && (
                  <div className="tags-list">
                    {formData.tags.map(tag => (
                      <span key={tag} className="tag">
                        {tag}
                        <button 
                          type="button" 
                          onClick={() => removeTag(tag)}
                          className="tag-remove"
                        >
                          ×
                        </button>
                      </span>
                    ))}
                  </div>
                )}
              </div>

              <div className="form-group">
                <label>Client Version</label>
                <input
                  type="text"
                  value={formData.client_version}
                  onChange={(e) => handleInputChange('client_version', e.target.value)}
                  placeholder="e.g., 1.0.0"
                />
              </div>
            </div>
          </div>

          <div className="modal-footer">
            <button 
              type="button" 
              className="btn btn-secondary" 
              onClick={onClose}
              disabled={loading}
            >
              Cancel
            </button>
            <button 
              type="submit" 
              className="btn btn-primary" 
              disabled={loading}
            >
              {loading ? 'Registering...' : 'Register Display'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default DisplayRegistration;
