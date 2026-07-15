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

import React, { useState } from 'react';
import PropTypes from 'prop-types';
import { AlertCircle, Heart, Settings, Power, Trash2, RefreshCw, Unlink } from 'lucide-react';
import Button from '../../components/Button/Button';
import Icon from '../../components/Icon/Icon';
import './ChannelCard.css';

// API icon names that don't map 1:1 to a lucide icon
const SOURCE_ICON_ALIASES = { photo: 'image' };

/**
 * ChannelCard component
 * Displays summary information for a channel including status, health, manifest info, and actions.
 */
const ChannelCard = ({
  channel,
  statusInfo,
  health,
  manifestData,
  v21Supported,
  channelHealthSupported,
  onOpenSettings,
  onToggleEnabled,
  onUninstall,
  onReloadDev,
  onUnlinkDev,
}) => {
  const [confirmRemove, setConfirmRemove] = useState(false);
  const isEnabled = channel.enabled !== false;
  const isDev = channel.dev === true;
  const iconName = SOURCE_ICON_ALIASES[channel.icon] || channel.icon || 'database';

  return (
    <div className={`channel-card ${!isEnabled ? 'channel-card-disabled' : ''} ${isDev ? 'channel-card-dev' : ''}`}>
      <div className="channel-card-header">
        <div className="channel-icon-tile" aria-hidden="true">
          <Icon name={iconName} size={22} />
        </div>
        <div className="channel-info">
          <h3>
            {channel.name}
            {isDev && <span className="channel-badge channel-badge--dev">Dev</span>}
            {v21Supported && manifestData?.schemaVersion === '2.1' && (
              <span className="channel-badge">v2.1</span>
            )}
          </h3>
          <div className="channel-meta">
            <span className="channel-id">{channel.id}</span>
            {channel.version && <span className="version-chip">v{channel.version}</span>}
          </div>
        </div>
        <div className="status-indicators">
          <div className={`status-pill status-pill--${isEnabled ? statusInfo.type : 'disabled'}`}>
            <span className="status-dot" />
            {isEnabled ? statusInfo.text : 'Disabled'}
          </div>
          {channelHealthSupported && health && isEnabled && !health.healthy && (
            <div className="health-indicator unhealthy">
              <Heart size={14} />
              Issues
            </div>
          )}
        </div>
      </div>

      <p className="channel-description">{channel.description}</p>
      {isDev && channel.dev_path && (
        <div className="dev-path">{channel.dev_path}</div>
      )}

      <div className="channel-card-body">
        <div className="channel-details">
          {v21Supported && manifestData && (
            <>
              {manifestData.hasUI && (
                <div className="detail-item">
                  <span>UI Components:</span>
                  <span className="ui-badge">{manifestData.ui?.length || 0} components</span>
                </div>
              )}
              {manifestData.permissions && (
                <div className="detail-item">
                  <span>Permissions:</span>
                  <span className="permissions">{manifestData.permissions.join(', ')}</span>
                </div>
              )}
            </>
          )}
          {channel.status?.lastUpdate && (
            <div className="detail-item">
              <span>Last Update:</span>
              <span className="last-update">{new Date(channel.status.lastUpdate).toLocaleString()}</span>
            </div>
          )}
        </div>

        {channel.status?.lastError && (
          <div className="error-message">
            <AlertCircle size={16} />
            <span>{channel.status.lastError}</span>
          </div>
        )}
      </div>

      <div className="channel-card-footer">
        {/* Dev channel actions */}
        {isDev && onReloadDev && (
          <Button
            variant="secondary"
            onClick={() => onReloadDev(channel)}
            icon={<RefreshCw />}
            type="button"
            size="sm"
          >
            Reload
          </Button>
        )}

        {/* Enable/Disable toggle (not for dev channels) */}
        {!isDev && onToggleEnabled && (
          <Button
            variant={isEnabled ? 'secondary' : 'primary'}
            onClick={() => onToggleEnabled(channel)}
            icon={<Power />}
            type="button"
            size="sm"
          >
            {isEnabled ? 'Disable' : 'Enable'}
          </Button>
        )}

        {/* Settings button */}
        {isEnabled && (
          <Button
            variant="accent"
            onClick={() => onOpenSettings(channel)}
            icon={<Settings />}
            type="button"
            size="sm"
          >
            Settings
          </Button>
        )}

        {/* Unlink (dev) or Uninstall (regular) */}
        {isDev && onUnlinkDev && (
          confirmRemove ? (
            <div className="uninstall-confirm">
              <span className="uninstall-confirm-text">Unlink?</span>
              <Button
                variant="danger"
                onClick={() => { onUnlinkDev(channel); setConfirmRemove(false); }}
                type="button"
                size="sm"
              >
                Yes
              </Button>
              <Button
                variant="secondary"
                onClick={() => setConfirmRemove(false)}
                type="button"
                size="sm"
              >
                No
              </Button>
            </div>
          ) : (
            <Button
              variant="danger"
              onClick={() => setConfirmRemove(true)}
              icon={<Unlink />}
              type="button"
              size="sm"
            >
              Unlink
            </Button>
          )
        )}

        {!isDev && onUninstall && (
          confirmRemove ? (
            <div className="uninstall-confirm">
              <span className="uninstall-confirm-text">Remove?</span>
              <Button
                variant="danger"
                onClick={() => { onUninstall(channel); setConfirmRemove(false); }}
                type="button"
                size="sm"
              >
                Yes
              </Button>
              <Button
                variant="secondary"
                onClick={() => setConfirmRemove(false)}
                type="button"
                size="sm"
              >
                No
              </Button>
            </div>
          ) : (
            <Button
              variant="danger"
              onClick={() => setConfirmRemove(true)}
              icon={<Trash2 />}
              type="button"
              size="sm"
            >
              Uninstall
            </Button>
          )
        )}
      </div>
    </div>
  );
};

export default ChannelCard;

ChannelCard.propTypes = {
  channel: PropTypes.shape({
    id: PropTypes.string.isRequired,
    name: PropTypes.string.isRequired,
    description: PropTypes.string,
    icon: PropTypes.string,
    version: PropTypes.string,
    enabled: PropTypes.bool,
    dev: PropTypes.bool,
    dev_path: PropTypes.string,
    status: PropTypes.shape({
      lastUpdate: PropTypes.oneOfType([PropTypes.string, PropTypes.number, PropTypes.instanceOf(Date)]),
      lastError: PropTypes.string,
      usingFallback: PropTypes.bool,
    }),
  }).isRequired,
  statusInfo: PropTypes.shape({
    type: PropTypes.oneOf(['success', 'warning', 'error']).isRequired,
    text: PropTypes.string.isRequired,
  }).isRequired,
  health: PropTypes.shape({
    healthy: PropTypes.bool,
    error: PropTypes.string,
  }),
  manifestData: PropTypes.shape({
    schemaVersion: PropTypes.string,
    hasUI: PropTypes.bool,
    ui: PropTypes.arrayOf(PropTypes.any),
    permissions: PropTypes.arrayOf(PropTypes.string),
  }),
  v21Supported: PropTypes.bool,
  channelHealthSupported: PropTypes.bool,
  onOpenSettings: PropTypes.func.isRequired,
  onToggleEnabled: PropTypes.func,
  onUninstall: PropTypes.func,
  onReloadDev: PropTypes.func,
  onUnlinkDev: PropTypes.func,
};

ChannelCard.defaultProps = {
  health: undefined,
  manifestData: undefined,
  v21Supported: false,
  channelHealthSupported: false,
  onToggleEnabled: undefined,
  onUninstall: undefined,
  onReloadDev: undefined,
  onUnlinkDev: undefined,
};
