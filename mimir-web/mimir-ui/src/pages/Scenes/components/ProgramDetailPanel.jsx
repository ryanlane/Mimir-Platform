import React from 'react';
import { X, Layers, Edit, Trash2, Image, Music2, Globe, Package, Radio } from 'lucide-react';
import Button from '../../../components/Button/Button';
import './ProgramDetailPanel.css';

function getChannelType(channel) {
  const s = [channel?.name, channel?.id, channel?.plugin_id, channel?.type]
    .filter(Boolean).join(' ').toLowerCase();
  if (/photo|gallery|frame|image/.test(s)) return 'photo';
  if (/spotify|music|audio|sound/.test(s)) return 'music';
  if (/web|browser|url|http/.test(s)) return 'web';
  if (/radio|stream|live/.test(s)) return 'stream';
  return 'generic';
}

const TYPE_ICONS = {
  photo: Image,
  music: Music2,
  web: Globe,
  stream: Radio,
  generic: Package,
};

function SourceCompositionPreview({ assignments, channels, channelManifests = {} }) {
  if (!assignments?.length) {
    return <div className="composition-empty">No sources configured</div>;
  }

  return (
    <div className="composition-strip">
      {assignments.map((assignment, i) => {
        const chId = typeof assignment === 'string' ? assignment : assignment.channel_id;
        const subId = typeof assignment === 'object' ? assignment.subchannel_id : null;
        const ch = channels.find(c => c.id === chId);
        const type = getChannelType(ch);
        const Icon = TYPE_ICONS[type] || Package;

        let subLabel = null;
        if (subId && channelManifests[chId]?.galleries) {
          const gallery = channelManifests[chId].galleries.find(g => g.id === subId);
          subLabel = gallery?.name || subId;
        }

        return (
          <React.Fragment key={`${chId}-${subId || 'all'}-${i}`}>
            {i > 0 && <span className="composition-arrow" aria-hidden="true">→</span>}
            <div className="composition-tile" title={ch?.name || chId}>
              <Icon size={13} />
              <span className="composition-tile-name">{ch?.name || chId}</span>
              {subLabel && <span className="composition-tile-sub">{subLabel}</span>}
            </div>
          </React.Fragment>
        );
      })}
    </div>
  );
}

export function ProgramDetailPanel({
  scene,
  channels = [],
  channelManifests = {},
  isLive = false,
  scheduleStatus,
  onClose,
  onEdit,
  onDelete,
}) {
  if (!scene) return null;

  const strategy = scene.update_strategy || scene.updateStrategy || 'scheduler';
  const isPush = strategy === 'push';
  const channelCount = scene.channels?.length || 0;

  return (
    <aside className="program-detail-panel">
      <div className="pdp-header">
        <div className="pdp-title-row">
          {isLive && <span className="pdp-live-dot" title="Currently live" />}
          <h2 className="pdp-name">{scene.name}</h2>
          <button className="pdp-close" onClick={onClose} aria-label="Close panel">
            <X size={14} />
          </button>
        </div>
        <div className="pdp-meta-row">
          <span className={`pdp-strategy-badge ${isPush ? 'push' : 'scheduled'}`}>
            {isPush ? 'Push' : 'Scheduled'}
          </span>
          <span className="pdp-source-count">
            <Layers size={12} />
            {channelCount} source{channelCount !== 1 ? 's' : ''}
          </span>
        </div>
      </div>

      <div className="pdp-section">
        <div className="pdp-section-label">COMPOSITION</div>
        <SourceCompositionPreview
          assignments={scene.channels}
          channels={channels}
          channelManifests={channelManifests}
        />
      </div>

      {scheduleStatus?.hasSchedule && (
        <div className="pdp-section">
          <div className="pdp-section-label">SCHEDULE</div>
          <div className="pdp-detail-row">
            <span>{scheduleStatus.status}</span>
            {scheduleStatus.nextRun && (
              <span className="pdp-detail-secondary">
                next: {new Date(scheduleStatus.nextRun).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </span>
            )}
          </div>
        </div>
      )}

      <div className="pdp-section">
        <div className="pdp-section-label">SETTINGS</div>
        <div className="pdp-rows">
          <div className="pdp-row">
            <span>Distribution</span>
            <span>{scene.distribution_mode || scene.distributionMode || 'MIRROR'}</span>
          </div>
          <div className="pdp-row">
            <span>Update</span>
            <span style={{ textTransform: 'capitalize' }}>{strategy}</span>
          </div>
        </div>
      </div>

      <div className="pdp-actions">
        <Button variant="primary" onClick={() => onEdit(scene)} className="pdp-action-btn">
          <Edit size={14} /> Edit Program
        </Button>
        <Button
          variant="danger"
          onClick={() => onDelete(scene.id)}
          className="pdp-action-btn pdp-action-btn--ghost"
        >
          <Trash2 size={14} /> Delete
        </Button>
      </div>
    </aside>
  );
}

export default ProgramDetailPanel;
