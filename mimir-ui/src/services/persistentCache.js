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
  if (cached) {
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

export const persistentCache = {
  async getScenes({ onUpdate } = {}) {
    return staleWhileRevalidate({
      store: idb.STORES.SCENES,
      key: 'list',
      ttl: TTL.SCENES,
      fetcher: async () => {
        const resp = await api.getScenes();
        return resp.data; // axios response
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
        return resp.data;
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
  async clearAll() {
    await Promise.all([
      idb.clear(idb.STORES.SCENES),
      idb.clear(idb.STORES.CHANNELS),
      idb.clear(idb.STORES.DISTRIBUTION)
    ]);
  }
};

export default persistentCache;
