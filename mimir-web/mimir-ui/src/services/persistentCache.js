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

import { idb } from './idb';
import { api } from './api';

// TTLs (ms)
const TTL = {
  SCENES: 5 * 60 * 1000,
  CHANNELS: 5 * 60 * 1000,
  DISTRIBUTION: 2 * 60 * 1000
};

function isFresh(entry, ttl) {
  if (!entry) return false;
  return Date.now() - (entry._ts || 0) < ttl;
}

async function staleWhileRevalidate({ store, key, ttl, fetcher, onUpdate }) {
  // 1. Try cached first
  const cached = await idb.get(store, key);
  let served = null;
  // Guard against stale cache entries from older code that didn't wrap in { data: ... }
  if (cached && cached.data !== undefined) {
    served = { data: cached.data, fromCache: true, stale: !isFresh(cached, ttl) };
  }
  // 2. Always kick off network fetch in background
  (async () => {
    try {
      const fresh = await fetcher();
      await idb.set(store, key, { data: fresh });
      if (onUpdate && (!served || JSON.stringify(fresh) !== JSON.stringify(served.data))) {
        onUpdate(fresh);
      }
    } catch (e) {
      if (!served) throw e; // only surface if nothing to show
      // else silent network failure while offline
    }
  })();
  if (served) return served;
  // 3. No cache – await network directly
  const fresh = await fetcher();
  await idb.set(store, key, { data: fresh });
  return { data: fresh, fromCache: false, stale: false };
}

// Helper to unwrap common API response shapes into a plain array (for list endpoints)
function unwrapList(raw) {
  if (!raw) return raw;
  // Already an array
  if (Array.isArray(raw)) return raw;
  // Common shapes: { scenes: [...] }, { channels: [...] }
  if (Array.isArray(raw.scenes)) return raw.scenes;
  if (Array.isArray(raw.channels)) return raw.channels;
  // Nested axios pattern some backends use: { data: { scenes: [...] }} or double wrapped
  if (raw.data) {
    if (Array.isArray(raw.data)) return raw.data;
    if (Array.isArray(raw.data.scenes)) return raw.data.scenes;
    if (Array.isArray(raw.data.channels)) return raw.data.channels;
  }
  return raw; // Fallback – caller will attempt its own extraction
}

export const persistentCache = {
  async getScenes({ onUpdate } = {}) {
    return staleWhileRevalidate({
      store: idb.STORES.SCENES,
      key: 'list',
      ttl: TTL.SCENES,
      fetcher: async () => {
        const resp = await api.getScenes();
        // Normalize so callers always see either an array or an object containing scenes
        const unwrapped = unwrapList(resp.data);
        // If we unwrapped to a bare array, return an object with scenes to preserve legacy expectations elsewhere
        return Array.isArray(unwrapped) ? { scenes: unwrapped } : unwrapped;
      },
      onUpdate
    });
  },
  async getChannels({ onUpdate } = {}) {
    return staleWhileRevalidate({
      store: idb.STORES.CHANNELS,
      key: 'list',
      ttl: TTL.CHANNELS,
      fetcher: async () => {
        const resp = await api.getChannels();
        const unwrapped = unwrapList(resp.data);
        return Array.isArray(unwrapped) ? { channels: unwrapped } : unwrapped;
      },
      onUpdate
    });
  },
  async getDistributionOverview({ onUpdate } = {}) {
    return staleWhileRevalidate({
      store: idb.STORES.DISTRIBUTION,
      key: 'overview',
      ttl: TTL.DISTRIBUTION,
      fetcher: async () => {
        const resp = await api.getDistributionOverview();
        return resp.data;
      },
      onUpdate
    });
  },
  async invalidateChannels() {
    await idb.delete(idb.STORES.CHANNELS, 'list');
  },
  async clearAll() {
    await Promise.all([
      idb.clear(idb.STORES.SCENES),
      idb.clear(idb.STORES.CHANNELS),
      idb.clear(idb.STORES.DISTRIBUTION)
    ]);
  }
};

export default persistentCache;
