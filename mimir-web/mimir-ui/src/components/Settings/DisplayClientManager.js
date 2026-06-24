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
import { Monitor, RefreshCw, Square, CheckCircle, XCircle } from 'lucide-react';
import { api } from '../../services/api';
import './DisplayClientManager.css';

// Display Client Manager based on DISPLAY_CLIENT_SPECIFICATION.md
const DisplayClientManager = () => {
  const [client, setClient] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [form, setForm] = useState({
    name: '',
    description: '',
    location: '',
    capabilities: {
      resolution: [1920, 1080],
      supported_formats: ['jpg', 'png', 'gif'],
      orientation: 'landscape',
      refresh_rate_hz: 60,
    },
    tags: [],
    client_version: '1.0.0',
  });
  const [registered, setRegistered] = useState(false);

  useEffect(() => {
    // Optionally, load existing client info from localStorage or API
    const saved = localStorage.getItem('mimir-display-client');
    if (saved) {
      setClient(JSON.parse(saved));
      setRegistered(true);
    }
  }, []);

  // Helper for tags input
  const handleTagsChange = (e) => {
    setForm({ ...form, tags: e.target.value.split(',').map(t => t.trim()).filter(Boolean) });
  };

  // Helper for supported_formats
  const handleFormatsChange = (e) => {
    const options = Array.from(e.target.selectedOptions).map(opt => opt.value);
    setForm({ ...form, capabilities: { ...form.capabilities, supported_formats: options } });
  };

  // Helper for resolution
  const handleResolutionChange = (idx, value) => {
    const res = [...form.capabilities.resolution];
    res[idx] = Number(value);
    setForm({ ...form, capabilities: { ...form.capabilities, resolution: res } });
  };

  // Helper for capabilities
  const handleCapabilitiesChange = (field, value) => {
    setForm({ ...form, capabilities: { ...form.capabilities, [field]: field === 'refresh_rate_hz' ? Number(value) : value } });
  };

  const handleChange = (e) => {
    setForm({ ...form, [e.target.name]: e.target.value });
  };

  const handleRegister = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const payload = {
        name: form.name,
        description: form.description,
        location: form.location,
        capabilities: {
          resolution: form.capabilities.resolution,
          supported_formats: form.capabilities.supported_formats,
          orientation: form.capabilities.orientation,
          refresh_rate_hz: form.capabilities.refresh_rate_hz,
        },
        tags: form.tags,
        client_version: form.client_version,
      };
      const res = await api.registerDisplay(payload);
      setClient(res.data);
      setRegistered(true);
      localStorage.setItem('mimir-display-client', JSON.stringify(res.data));
    } catch (err) {
      setError(err.message || 'Registration failed');
    } finally {
      setLoading(false);
    }
  };

  const handleClear = () => {
    setClient(null);
    setRegistered(false);
    localStorage.removeItem('mimir-display-client');
  };

  return (
    <div className="display-client-manager">
      <h2><Monitor size={20} /> Display Client Management</h2>
      <p className="text-tertiary">Register and manage this display client with the Mimir Platform.</p>
      {registered && client ? (
        <div className="client-status-card">
          <div className="status-row">
            <span>Display Name:</span>
            <span>{form.name || client.name}</span>
          </div>
          <div className="status-row">
            <span>Client Version:</span>
            <span>{form.client_version || client.client_version}</span>
          </div>
          <div className="status-row">
            <span>Client ID:</span>
            <span>{client.id}</span>
          </div>
          <div className="status-row">
            <span>Current Image URL:</span>
            <span>{client.current_image_url || 'None'}</span>
          </div>
          <div className="status-row">
            <span>Status:</span>
            <span className="status-indicator status-success"><CheckCircle size={16} /> Registered</span>
          </div>
          <div className="client-actions">
            <button className="btn btn-warning" onClick={handleClear}><XCircle size={16} /> Unregister</button>
            <button className="btn btn-primary" onClick={() => window.location.reload()}><RefreshCw size={16} /> Reload</button>
          </div>
        </div>
      ) : (
        <form className="client-registration-form" onSubmit={handleRegister}>
          <div className="form-group">
            <label htmlFor="name">Display Name</label>
            <input type="text" name="name" id="name" value={form.name} onChange={handleChange} required />
          </div>
          <div className="form-group">
            <label htmlFor="description">Description</label>
            <input type="text" name="description" id="description" value={form.description} onChange={handleChange} required />
          </div>
          <div className="form-group">
            <label htmlFor="location">Location</label>
            <input type="text" name="location" id="location" value={form.location} onChange={handleChange} required />
          </div>
          <div className="form-group">
            <label>Resolution</label>
            <div style={{ display: 'flex', gap: '1rem' }}>
              <input type="number" min="1" value={form.capabilities.resolution[0]} onChange={e => handleResolutionChange(0, e.target.value)} required placeholder="Width" />
              <input type="number" min="1" value={form.capabilities.resolution[1]} onChange={e => handleResolutionChange(1, e.target.value)} required placeholder="Height" />
            </div>
          </div>
          <div className="form-group">
            <label>Supported Formats</label>
            <select multiple value={form.capabilities.supported_formats} onChange={handleFormatsChange}>
              <option value="jpg">jpg</option>
              <option value="png">png</option>
              <option value="gif">gif</option>
              <option value="bmp">bmp</option>
              <option value="webp">webp</option>
            </select>
          </div>
          <div className="form-group">
            <label>Orientation</label>
            <select value={form.capabilities.orientation} onChange={e => handleCapabilitiesChange('orientation', e.target.value)}>
              <option value="landscape">Landscape</option>
              <option value="portrait">Portrait</option>
            </select>
          </div>
          <div className="form-group">
            <label>Refresh Rate (Hz)</label>
            <input type="number" min="1" value={form.capabilities.refresh_rate_hz} onChange={e => handleCapabilitiesChange('refresh_rate_hz', e.target.value)} required />
          </div>
          <div className="form-group">
            <label>Tags (comma separated)</label>
            <input type="text" value={form.tags.join(', ')} onChange={handleTagsChange} placeholder="e.g. lobby, main, touchscreen" />
          </div>
          <div className="form-group">
            <label htmlFor="client_version">Client Version</label>
            <input type="text" name="client_version" id="client_version" value={form.client_version} onChange={handleChange} required />
          </div>
          <button className="btn btn-primary" type="submit" disabled={loading}>
            {loading ? 'Registering...' : 'Register Display Client'}
          </button>
          {error && <div className="error-message">{error}</div>}
        </form>
      )}
    </div>
  );
};

export default DisplayClientManager;
