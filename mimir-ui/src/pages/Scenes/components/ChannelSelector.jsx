import React from 'react';
import PropTypes from 'prop-types';

/**
 * ChannelSelector
 * Handles single channel selection plus optional subchannel/gallery selection.
 * Props:
 *  - channels: array of channel objects {id, name}
 *  - assignments: [{channel_id, subchannel_id|null}]
 *  - subChannelSupport: map[channelId] => bool
 *  - availableSubChannels: map[channelId] => [{id,name,image_count?,type}]
 *  - subChannelRequirements: map[channelId] => { requires_subchannel_selection: bool }
 *  - loadingSubChannels: boolean
 *  - onChange: (newAssignmentsArray) => void (always array, single selection semantics here)
 */
const ChannelSelector = ({
  channels,
  assignments,
  subChannelSupport,
  availableSubChannels,
  subChannelRequirements,
  loadingSubChannels,
  onChange
}) => {
  const isSelected = (channelId) => assignments.some(a => a.channel_id === channelId);
  const getSelectedSubChannel = (channelId) => {
    const a = assignments.find(x => x.channel_id === channelId);
    return a?.subchannel_id || '';
  };

  const toggleChannel = (channelId) => {
    if (isSelected(channelId)) {
      onChange([]); // deselect (single selection logic)
    } else {
      onChange([{ channel_id: channelId, subchannel_id: null }]);
    }
  };

  const changeSubChannel = (channelId, subChannelId) => {
    onChange(assignments.map(a => a.channel_id === channelId ? { ...a, subchannel_id: subChannelId || null } : a));
  };

  return (
    <div className="form-group">
      <label className="form-label">Channel</label>
      <div className="channels-selection">
        {channels.map(channel => (
          <div key={channel.id} className="channel-assignment-group">
            <label className="radio-item">
              <input
                type="radio"
                name="channel"
                checked={isSelected(channel.id)}
                onChange={() => toggleChannel(channel.id)}
              />
              <span>{channel.name}</span>
            </label>
            {isSelected(channel.id) && subChannelSupport[channel.id] && (
              <div className="subchannel-selection">
                <label className="subchannel-label">Gallery/Sub-Channel:</label>
                {availableSubChannels[channel.id]?.length > 0 ? (
                  <select
                    value={getSelectedSubChannel(channel.id)}
                    onChange={(e) => changeSubChannel(channel.id, e.target.value)}
                    className="subchannel-select"
                  >
                    {!subChannelRequirements[channel.id]?.requires_subchannel_selection && (
                      <option value="">All Content (Random from all galleries)</option>
                    )}
                    {subChannelRequirements[channel.id]?.requires_subchannel_selection && !getSelectedSubChannel(channel.id) && (
                      <option value="">Select a gallery...</option>
                    )}
                    {availableSubChannels[channel.id].map(sc => (
                      <option key={sc.id} value={sc.id}>
                        {sc.name}{sc.image_count !== undefined && ` (${sc.image_count || 0} images)`}
                      </option>
                    ))}
                  </select>
                ) : (
                  <div className="subchannel-loading">No galleries available</div>
                )}
                {subChannelRequirements[channel.id]?.requires_subchannel_selection && (
                  <div className="subchannel-requirement-note">* Gallery selection required</div>
                )}
              </div>
            )}
            {isSelected(channel.id) && loadingSubChannels && (
              <div className="subchannel-loading">Loading sub-channels...</div>
            )}
            {isSelected(channel.id) && !subChannelSupport[channel.id] && !loadingSubChannels && (
              <div className="subchannel-loading">This channel does not support galleries or sub-channels</div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

export default ChannelSelector;

ChannelSelector.propTypes = {
  channels: PropTypes.arrayOf(PropTypes.shape({
    id: PropTypes.oneOfType([PropTypes.string, PropTypes.number]).isRequired,
    name: PropTypes.string
  })).isRequired,
  assignments: PropTypes.arrayOf(PropTypes.shape({
    channel_id: PropTypes.oneOfType([PropTypes.string, PropTypes.number]).isRequired,
    subchannel_id: PropTypes.oneOfType([PropTypes.string, PropTypes.number, PropTypes.null])
  })).isRequired,
  subChannelSupport: PropTypes.object.isRequired,
  availableSubChannels: PropTypes.object.isRequired,
  subChannelRequirements: PropTypes.object.isRequired,
  loadingSubChannels: PropTypes.bool.isRequired,
  onChange: PropTypes.func.isRequired
};
