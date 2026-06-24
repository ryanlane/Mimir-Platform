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

import React, { useState, useRef, useCallback } from 'react';
import { Upload, GitBranch, AlertCircle, CheckCircle } from 'lucide-react';
import { api } from '../../services/api';
import Modal from '../../components/Modal/Modal';
import Button from '../../components/Button/Button';
import './InstallChannel.css';

const InstallChannel = ({ isOpen, onClose, onInstalled }) => {
  const [mode, setMode] = useState('zip'); // 'zip' | 'git'
  const [gitUrl, setGitUrl] = useState('');
  const [dragActive, setDragActive] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [installing, setInstalling] = useState(false);
  const [result, setResult] = useState(null); // { success: bool, message: string }
  const fileInputRef = useRef(null);

  const resetState = useCallback(() => {
    setGitUrl('');
    setSelectedFile(null);
    setDragActive(false);
    setInstalling(false);
    setResult(null);
  }, []);

  const handleClose = useCallback(() => {
    resetState();
    onClose();
  }, [resetState, onClose]);

  const handleDrag = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    const files = e.dataTransfer.files;
    if (files && files.length > 0) {
      const file = files[0];
      if (file.name.toLowerCase().endsWith('.zip')) {
        setSelectedFile(file);
        setResult(null);
      } else {
        setResult({ success: false, message: 'Please drop a .zip file' });
      }
    }
  }, []);

  const handleFileSelect = useCallback((e) => {
    const file = e.target.files[0];
    if (file) {
      setSelectedFile(file);
      setResult(null);
    }
  }, []);

  const handleInstallZip = useCallback(async () => {
    if (!selectedFile) return;
    setInstalling(true);
    setResult(null);
    try {
      const formData = new FormData();
      formData.append('file', selectedFile);
      const response = await api.installChannelFromZip(formData);
      const data = response.data;
      setResult({
        success: true,
        message: `Installed "${data.name || data.plugin_id}" successfully`,
      });
      if (onInstalled) onInstalled();
    } catch (error) {
      const detail = error.response?.data?.detail || error.message;
      setResult({ success: false, message: `Installation failed: ${detail}` });
    } finally {
      setInstalling(false);
    }
  }, [selectedFile, onInstalled]);

  const handleInstallGit = useCallback(async () => {
    if (!gitUrl.trim()) return;
    setInstalling(true);
    setResult(null);
    try {
      const response = await api.installChannelFromGit(gitUrl.trim());
      const data = response.data;
      setResult({
        success: true,
        message: `Installed "${data.name || data.plugin_id}" successfully`,
      });
      if (onInstalled) onInstalled();
    } catch (error) {
      const detail = error.response?.data?.detail || error.message;
      setResult({ success: false, message: `Installation failed: ${detail}` });
    } finally {
      setInstalling(false);
    }
  }, [gitUrl, onInstalled]);

  return (
    <Modal isOpen={isOpen} onClose={handleClose} title="Install Channel" size="medium">
      <div className="install-channel">
        {/* Tab Switcher */}
        <div className="install-tabs">
          <button
            className={`install-tab ${mode === 'zip' ? 'active' : ''}`}
            onClick={() => { setMode('zip'); setResult(null); }}
            type="button"
          >
            <Upload size={16} />
            Upload ZIP
          </button>
          <button
            className={`install-tab ${mode === 'git' ? 'active' : ''}`}
            onClick={() => { setMode('git'); setResult(null); }}
            type="button"
          >
            <GitBranch size={16} />
            Git URL
          </button>
        </div>

        {/* ZIP Upload */}
        {mode === 'zip' && (
          <div className="install-body">
            <div
              className={`drop-zone ${dragActive ? 'drag-active' : ''} ${selectedFile ? 'has-file' : ''}`}
              onDragEnter={handleDrag}
              onDragLeave={handleDrag}
              onDragOver={handleDrag}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => { if (e.key === 'Enter') fileInputRef.current?.click(); }}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".zip"
                onChange={handleFileSelect}
                className="file-input-hidden"
              />
              {selectedFile ? (
                <>
                  <Upload size={24} />
                  <span className="drop-zone-file">{selectedFile.name}</span>
                  <span className="drop-zone-hint">
                    {(selectedFile.size / 1024).toFixed(1)} KB — Click or drop to change
                  </span>
                </>
              ) : (
                <>
                  <Upload size={32} />
                  <span className="drop-zone-text">Drop a .zip file here or click to browse</span>
                  <span className="drop-zone-hint">
                    The archive should contain a plugin directory with channel.py and plugin.json
                  </span>
                </>
              )}
            </div>
            <div className="install-actions">
              <Button
                variant="primary"
                onClick={handleInstallZip}
                disabled={!selectedFile || installing}
                loading={installing}
                icon={<Upload />}
              >
                {installing ? 'Installing...' : 'Install'}
              </Button>
            </div>
          </div>
        )}

        {/* Git URL */}
        {mode === 'git' && (
          <div className="install-body">
            <div className="git-input-group">
              <label htmlFor="git-url-input" className="git-label">
                Git Repository URL
              </label>
              <input
                id="git-url-input"
                type="text"
                className="git-url-input"
                placeholder="https://github.com/user/mimir-channel-plugin.git"
                value={gitUrl}
                onChange={(e) => { setGitUrl(e.target.value); setResult(null); }}
                disabled={installing}
              />
              <span className="git-hint">
                The repository will be cloned with --depth 1. It should contain
                channel.py and plugin.json at the root or in a subdirectory.
              </span>
            </div>
            <div className="install-actions">
              <Button
                variant="primary"
                onClick={handleInstallGit}
                disabled={!gitUrl.trim() || installing}
                loading={installing}
                icon={<GitBranch />}
              >
                {installing ? 'Cloning...' : 'Clone & Install'}
              </Button>
            </div>
          </div>
        )}

        {/* Result message */}
        {result && (
          <div className={`install-result ${result.success ? 'success' : 'error'}`}>
            {result.success ? <CheckCircle size={16} /> : <AlertCircle size={16} />}
            <span>{result.message}</span>
          </div>
        )}
      </div>
    </Modal>
  );
};

export default InstallChannel;
