import React from 'react';
import './SceneCard.css';
import Button from '../Button/Button';
import { Monitor, Edit, Trash2 } from 'lucide-react';

/**
 * SceneCard component
 * Displays a scene with channels, distribution mode selector, schedule info and action buttons.
 *
 * Props:
 *  - scene: Scene object (id, name, channels, distribution_mode / distributionMode, update_strategy, ...)
 *  - channels: array of channel objects (id, name, ...)
 *  - channelManifests: map of channelId -> manifest object
 *  - scheduleStatus: object from parent getSceneScheduleStatus(scene.id)
 *  - onChangeDistribution(mode)
 *  - onDisplay(sceneId)
 *  - onEdit(scene)
 *  - onDelete(sceneId)
 *  - loadingDisplay: boolean for display button loading state
 */
export function SceneCard({
  scene,
  channels = [],
  channelManifests = {},
  scheduleStatus,
  onChangeDistribution,
  onDisplay,
  onEdit,
  onDelete,
  loadingDisplay = false,
}) {
  if (!scene) return null;

  const strategy = scene.update_strategy || scene.updateStrategy || 'scheduler';
  const isPush = strategy === 'push';
  const downgraded = !isPush && (scene.push_fallback_poll_seconds || scene.pushFallbackPollSeconds);
  const badgeClass = isPush ? 'strategy-badge push' : 'strategy-badge scheduler';

  const distributionValue = scene.distributionMode || scene.distribution_mode || 'MIRROR';

  const renderChannelTag = (channelAssignment, index) => {
    const channelId = typeof channelAssignment === 'string' ? channelAssignment : channelAssignment.channel_id;
    const subChannelId = typeof channelAssignment === 'object' ? channelAssignment.subchannel_id : null;
    const channel = channels.find(c => c.id === channelId);
    const displayName = channel?.name || channelId;

    let subChannelDisplayName = subChannelId;
    if (subChannelId && channelManifests[channelId]) {
      const manifest = channelManifests[channelId];
      if (manifest.galleries) {
        const gallery = manifest.galleries.find(g => g.id === subChannelId);
        if (gallery) {
          subChannelDisplayName = `${gallery.name} (${gallery.image_count || 0} images)`;
        }
      } else if (manifest.subchannels) {
        const sc = manifest.subchannels.find(s => s.id === subChannelId);
        if (sc) subChannelDisplayName = sc.name;
      }
    }

    return (
      <span key={`${channelId}-${subChannelId || 'all'}-${index}`} className="channel-tag">
        {displayName}
        {subChannelId && (
          <span className="subchannel-indicator">→ {subChannelDisplayName}</span>
        )}
      </span>
    );
  };

  return (
    <div className="scene-card">
      <div className="scene-card-header">
        <h3>
          {scene.name}{' '}
          
        </h3>
        <span
            className={badgeClass}
            title={downgraded ? 'Originally configured for push but downgraded due to channel capability change' : (isPush ? 'Push update strategy (websocket events trigger refresh)' : 'Scheduler update strategy (periodic refresh)')}
          >
            {isPush ? 'Push' : 'Scheduled'}
            {downgraded && <span className="downgrade-indicator" aria-label="Downgraded to scheduler">⚠</span>}
          </span>
      </div>

      <div className="scene-card-body">
        {scene.channels && scene.channels.length > 0 && (
          <div className="scene-channels">
            <span className="channels-label">Channels:</span>
            <div className="channel-tags">
              {scene.channels.map(renderChannelTag)}
            </div>
          </div>
        )}

        <div className="scene-distribution-mode">
          <span className="distribution-label">Distribution:</span>
          <select
            value={distributionValue}
            onChange={(e) => onChangeDistribution && onChangeDistribution(scene.id, e.target.value)}
            className="distribution-mode-select"
          >
            <option value="MIRROR">Mirror</option>
            <option value="SEQUENTIAL">Sequential</option>
            <option value="RANDOM_UNIQUE">Random Unique</option>
          </select>
        </div>

        <div className="scene-schedule">
          <span className="schedule-label">Schedule:</span>
          {scheduleStatus && (
            <div className="schedule-info">
              <span className={`schedule-status ${scheduleStatus.hasSchedule ? 'active' : 'inactive'}`}>
                {scheduleStatus.hasSchedule ? (
                  <>
                    {scheduleStatus.status}
                    {scheduleStatus.count > 1 && (
                      <span className="schedule-count"> (+{scheduleStatus.count - 1} more)</span>
                    )}
                  </>
                ) : (
                  'No schedule'
                )}
              </span>
            </div>
          )}
        </div>
      </div>

      <div className="scene-card-footer">
        <Button
          size="sm"
          variant="accent"
          icon={<Monitor size={16} aria-hidden="true" />}
          onClick={() => onDisplay && onDisplay(scene.id)}
          loading={loadingDisplay}
          disabled={loadingDisplay}
          aria-label={loadingDisplay ? 'Loading scene preview' : 'Display scene'}
        >
          Display
        </Button>
        <Button
          size="sm"
          variant="secondary"
          icon={<Edit size={16} aria-hidden="true" />}
          onClick={() => onEdit && onEdit(scene)}
        >
          Edit
        </Button>
        <Button
          size="sm"
          variant="error"
          icon={<Trash2 size={16} aria-hidden="true" />}
          onClick={() => onDelete && onDelete(scene.id)}
        >
          Delete
        </Button>
      </div>
    </div>
  );
}

export default SceneCard;
