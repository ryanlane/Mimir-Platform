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

// Pure utility functions for SceneForm related logic.
// Keep these stateless for easy unit testing.

/**
 * Normalize scene object from API (legacy/new formats) into internal formData shape subset.
 */
export function normalizeScene(scene) {
  if (!scene) {
    return {
      name: '',
      channels: [],
      distribution_mode: 'MIRROR',
      overlay: {
        overlays: [],
        position: ['top', 'right'],
        background: true,
        backgroundColor: { red: 0, green: 0, blue: 0, alpha: 10 }
      },
      schedule: null,
      update_strategy: 'scheduler',
      push_fallback_poll_seconds: 120
    };
  }
  // Normalize channels array into assignment objects; old format may be string ids
  const normalizedChannels = Array.isArray(scene.channels)
    ? scene.channels.map(ch => {
        if (typeof ch === 'string') return { channel_id: ch, subchannel_id: null };
        if (ch && typeof ch === 'object') {
          return {
            channel_id: ch.channel_id || ch.id || String(ch),
            subchannel_id: ch.subchannel_id || null
          };
        }
        return { channel_id: String(ch), subchannel_id: null };
      })
    : [];

  return {
    name: scene.name || '',
    channels: normalizedChannels.slice(0, 1), // current UI supports one channel
    distribution_mode: scene.distributionMode || scene.distribution_mode || 'MIRROR',
    overlay: scene.overlay || {
      overlays: [],
      position: ['top', 'right'],
      background: true,
      backgroundColor: { red: 0, green: 0, blue: 0, alpha: 10 }
    },
    schedule: scene.schedule || null,
    update_strategy: scene.update_strategy || scene.updateStrategy || 'scheduler',
    push_fallback_poll_seconds: scene.push_fallback_poll_seconds || scene.pushFallbackPollSeconds || 120
  };
}

/**
 * Build API payload from formData. Drops push fallback poll seconds when not using push strategy.
 */
export function buildPayload(formData) {
  const payload = { ...formData };
  if (payload.update_strategy !== 'push') {
    delete payload.push_fallback_poll_seconds;
  }
  return payload;
}

/**
 * Evaluate push strategy selectability based on assignments and capability map.
 * Returns boolean.
 */
export function evaluatePushSelectable(assignments, capabilityMap) {
  if (!assignments || assignments.length === 0) return false;
  return assignments.every(a => capabilityMap[a.channel_id]?.supportsPush);
}

/**
 * Validate formData against subchannel requirements; returns array of error messages.
 */
export function validateForm(formData, subChannelRequirements, availableSubChannels, channels) {
  const errors = [];
  if (!formData.name.trim()) errors.push('Scene name is required');
  if (formData.channels.length === 0) errors.push('At least one channel must be selected');
  for (const assignment of formData.channels) {
    const channelId = assignment.channel_id;
    const requirements = subChannelRequirements[channelId];
    if (requirements?.requires_subchannel_selection && !assignment.subchannel_id) {
      const channel = channels.find(ch => ch.id === channelId);
      const subOptions = (availableSubChannels[channelId] || []).map(sc => sc.name).join(', ');
      errors.push(`Channel "${channel?.name || channelId}" requires a gallery/subchannel selection. Available options: ${subOptions || 'None available'}`);
    }
  }
  return errors;
}
