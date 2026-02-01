import React, { useState, useCallback } from 'react';
import { FolderOpen, AlertCircle, CheckCircle } from 'lucide-react';
import { api } from '../../services/api';
import Modal from '../../components/Modal/Modal';
import Button from '../../components/Button/Button';
import './LinkDevChannel.css';

const LinkDevChannel = ({ isOpen, onClose, onLinked }) => {
  const [path, setPath] = useState('');
  const [linking, setLinking] = useState(false);
  const [result, setResult] = useState(null);

  const resetState = useCallback(() => {
    setPath('');
    setLinking(false);
    setResult(null);
  }, []);

  const handleClose = useCallback(() => {
    resetState();
    onClose();
  }, [resetState, onClose]);

  const handleLink = useCallback(async () => {
    if (!path.trim()) return;
    setLinking(true);
    setResult(null);
    try {
      const response = await api.linkDevChannel(path.trim());
      const data = response.data;
      setResult({
        success: true,
        message: `Linked "${data.name || data.plugin_id}" from ${data.path}`,
      });
      if (onLinked) onLinked();
    } catch (error) {
      const detail = error.response?.data?.detail || error.message;
      setResult({ success: false, message: `Failed: ${detail}` });
    } finally {
      setLinking(false);
    }
  }, [path, onLinked]);

  const handleKeyDown = useCallback((e) => {
    if (e.key === 'Enter' && path.trim() && !linking) {
      handleLink();
    }
  }, [handleLink, path, linking]);

  return (
    <Modal isOpen={isOpen} onClose={handleClose} title="Link Dev Channel" size="medium">
      <div className="link-dev-channel">
        <p className="link-dev-description">
          Enter the absolute filesystem path to a channel plugin directory.
          This path is resolved on the API server filesystem (so if the API is running in Docker,
          the path must exist inside the API container).
          The directory will be loaded in-place and a file watcher will automatically
          reload the channel when you make changes.
        </p>

        <div className="link-dev-input-group">
          <label htmlFor="dev-path-input" className="link-dev-label">
            Plugin Directory Path
          </label>
          <input
            id="dev-path-input"
            type="text"
            className="link-dev-input"
            placeholder="/plugins/image-frame-channel-mimir/channels/photo_frame"
            value={path}
            onChange={(e) => { setPath(e.target.value); setResult(null); }}
            onKeyDown={handleKeyDown}
            disabled={linking}
          />
          <span className="link-dev-hint">
            Must contain channel.py and plugin.json (or config.json). Example (Docker dev): /plugins/...
          </span>
        </div>

        <div className="link-dev-actions">
          <Button
            variant="primary"
            onClick={handleLink}
            disabled={!path.trim() || linking}
            loading={linking}
            icon={<FolderOpen />}
          >
            {linking ? 'Linking...' : 'Link Channel'}
          </Button>
        </div>

        {result && (
          <div className={`link-dev-result ${result.success ? 'success' : 'error'}`}>
            {result.success ? <CheckCircle size={16} /> : <AlertCircle size={16} />}
            <span>{result.message}</span>
          </div>
        )}
      </div>
    </Modal>
  );
};

export default LinkDevChannel;
