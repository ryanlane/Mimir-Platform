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

import React from 'react';
import { X, Settings, Power, RefreshCw, Trash2, Unlink, AlertCircle, Heart, CheckCircle } from 'lucide-react';
import Button from '../../components/Button/Button';
import './SourceDetailPanel.css';

function StatusDot({ enabled, statusInfo }) {
  if (!enabled) {
    return <span className="sdp-status-dot sdp-status-dot--disabled" title="Disabled" />;
  }
  const cls = statusInfo?.type === 'error'
    ? 'sdp-status-dot--error'
    : statusInfo?.type === 'warning'
    ? 'sdp-status-dot--warning'
    : 'sdp-status-dot--ok';
  return <span className={`sdp-status-dot ${cls}`} title={statusInfo?.text || 'Active'} />;
}

export function SourceDetailPanel({
  channel,
  health,
  manifestData,
  v21Supported,
  channelHealthSupported,
  statusInfo,
  onClose,
  onOpenSettings,
  onToggleEnabled,
  onUninstall,
  onUnlinkDev,
  onReloadDev,
}) {
  if (!channel) return null;

  const isEnabled = channel.enabled !== false;
  const isDev = channel.dev === true;
  const isHealthy = health?.healthy;
  const hasError = !!channel.status?.lastError;
  const lastUpdate = channel.status?.lastUpdate;
  const permissions = manifestData?.permissions;

  return (
    <aside className="source-detail-panel">
      {/* Header */}
      <div className="sdp-header">
        <div className="sdp-title-row">
          <StatusDot enabled={isEnabled} statusInfo={statusInfo} />
          <h2 className="sdp-name">{channel.name}</h2>
          <button className="sdp-close" onClick={onClose} aria-label="Close panel">
            <X size={14} />
          </button>
        </div>
        <div className="sdp-badges">
          {!isEnabled && <span className="sdp-badge sdp-badge--disabled">Disabled</span>}
          {isDev && <span className="sdp-badge sdp-badge--dev">DEV</span>}
          {v21Supported && manifestData?.schemaVersion === '2.1' && (
            <span className="sdp-badge sdp-badge--v21">v2.1</span>
          )}
          {channelHealthSupported && health && isEnabled && (
            <span className={`sdp-badge ${isHealthy ? 'sdp-badge--healthy' : 'sdp-badge--unhealthy'}`}>
              {isHealthy ? <CheckCircle size={11} /> : <Heart size={11} />}
              {isHealthy ? 'Healthy' : 'Issues'}
            </span>
          )}
        </div>
      </div>

      {/* Description */}
      {channel.description && (
        <div className="sdp-section">
          <p className="sdp-description">{channel.description}</p>
        </div>
      )}

      {/* Details */}
      <div className="sdp-section">
        <div className="sdp-section-label">DETAILS</div>
        <div className="sdp-rows">
          <div className="sdp-row">
            <span>ID</span>
            <span className="sdp-mono">{channel.id}</span>
          </div>
          {channel.version && (
            <div className="sdp-row">
              <span>Version</span>
              <span>{channel.version}</span>
            </div>
          )}
          {lastUpdate && (
            <div className="sdp-row">
              <span>Last update</span>
              <span>{new Date(lastUpdate).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' })}</span>
            </div>
          )}
          {isDev && channel.dev_path && (
            <div className="sdp-row sdp-row--full">
              <span>Path</span>
              <span className="sdp-mono sdp-dev-path">{channel.dev_path}</span>
            </div>
          )}
        </div>
      </div>

      {/* Permissions */}
      {permissions?.length > 0 && (
        <div className="sdp-section">
          <div className="sdp-section-label">PERMISSIONS</div>
          <div className="sdp-permission-list">
            {permissions.map(p => (
              <span key={p} className="sdp-permission-tag">{p}</span>
            ))}
          </div>
        </div>
      )}

      {/* Error */}
      {hasError && (
        <div className="sdp-section">
          <div className="sdp-section-label sdp-section-label--error">LAST ERROR</div>
          <div className="sdp-error-row">
            <AlertCircle size={13} className="sdp-error-icon" />
            <span className="sdp-error-text">{channel.status.lastError}</span>
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="sdp-actions">
        {isEnabled && (
          <Button
            variant="primary"
            onClick={() => onOpenSettings(channel)}
            className="sdp-action-btn"
          >
            <Settings size={14} /> Open Settings
          </Button>
        )}
        {isDev && onReloadDev && (
          <Button
            variant="secondary"
            onClick={() => onReloadDev(channel)}
            className="sdp-action-btn"
          >
            <RefreshCw size={14} /> Reload
          </Button>
        )}
        {!isDev && onToggleEnabled && (
          <Button
            variant="secondary"
            onClick={() => onToggleEnabled(channel)}
            className="sdp-action-btn"
          >
            <Power size={14} /> {isEnabled ? 'Disable' : 'Enable'}
          </Button>
        )}
        {isDev && onUnlinkDev ? (
          <Button
            variant="danger"
            onClick={() => { if (window.confirm(`Unlink dev channel "${channel.name}"?`)) onUnlinkDev(channel); }}
            className="sdp-action-btn"
          >
            <Unlink size={14} /> Unlink
          </Button>
        ) : onUninstall ? (
          <Button
            variant="danger"
            onClick={() => { if (window.confirm(`Uninstall "${channel.name}"?`)) onUninstall(channel); }}
            className="sdp-action-btn"
          >
            <Trash2 size={14} /> Uninstall
          </Button>
        ) : null}
      </div>
    </aside>
  );
}

export default SourceDetailPanel;
