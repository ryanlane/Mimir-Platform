import React from 'react';
import PropTypes from 'prop-types';
import { AlertCircle, Heart, Settings } from 'lucide-react';
import Button from '../../components/Button/Button';
import './ChannelCard.css';

/**
 * ChannelCard component
 * Displays summary information for a channel including status, health, manifest info, and actions.
 *
 * Props:
 *  - channel (object) channel data
 *  - statusInfo ({ type: 'success'|'warning'|'error', text: string }) computed status display
 *  - health (object|undefined) health object { healthy: bool, ... }
 *  - manifestData (object|undefined) manifest details for v2.1
 *  - v21Supported (boolean) whether UI should show v2.1 badges/sections
 *  - channelHealthSupported (boolean) whether to display health indicator
 *  - onOpenSettings (function) handler to open settings dialog
 */
const ChannelCard = ({
  channel,
  statusInfo,
  health,
  manifestData,
  v21Supported,
  channelHealthSupported,
  onOpenSettings
}) => {
  return (
    <div className="channel-card">
      <div className="channel-card-header">
        <div className="channel-info">
          <h3>
            {channel.name}
            {v21Supported && manifestData?.schemaVersion === '2.1' && (
              <span className="v21-badge">v2.1</span>
            )}
          </h3>
            <div className="channel-id">ID: {channel.id}</div>
            <p className="text-tertiary">{channel.description}</p>
        </div>
        <div className="status-indicators">
          <div className={`status-indicator status-${statusInfo.type}`}>
            {statusInfo.text}
          </div>
          {channelHealthSupported && health && (
            <div className={`health-indicator ${health.healthy ? 'healthy' : 'unhealthy'}`}>
              <Heart size={16} />
              {health.healthy ? 'Healthy' : 'Issues'}
            </div>
          )}
        </div>
      </div>

      <div className="channel-card-body">
        <div className="channel-details">
          {channel.version && (
            <div className="detail-item">
              <span>Version:</span>
              <span>{channel.version || 'Unknown'}</span>
            </div>
          )}
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
        <Button
          variant="accent"
          size="sm"
          onClick={() => onOpenSettings(channel)}
          icon={<Settings />}
          type="button"
        >
          Settings
        </Button>
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
    version: PropTypes.string,
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
};

ChannelCard.defaultProps = {
  health: undefined,
  manifestData: undefined,
  v21Supported: false,
  channelHealthSupported: false,
};
