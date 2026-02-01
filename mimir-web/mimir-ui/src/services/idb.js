// Lightweight IndexedDB helper (no external deps) for Mimir UI
// Provides simple get/set/delete and store version upgrades.

const DB_NAME = 'mimir-cache';
const DB_VERSION = 2; // bump for outbox store
const STORES = {
  GENERIC: 'generic', // key-value JSON blobs
  SCENES: 'scenes',
  CHANNELS: 'channels',
  DISTRIBUTION: 'distribution',
  OUTBOX: 'outbox'
};

let dbPromise = null;

function openDb() {
  if (dbPromise) return dbPromise;
  dbPromise = new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = (e) => {
      const db = req.result;
      Object.values(STORES).forEach(store => {
        if (!db.objectStoreNames.contains(store)) {
          db.createObjectStore(store, { keyPath: store === STORES.OUTBOX ? 'id' : undefined });
        }
      });
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
  return dbPromise;
}

async function withStore(storeName, mode, fn) {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(storeName, mode);
    const store = tx.objectStore(storeName);
    let result;
    tx.oncomplete = () => resolve(result);
    tx.onerror = () => reject(tx.error);
    result = fn(store);
  });
}

export const idb = {
  STORES,
  async get(store, key) {
    return withStore(store, 'readonly', s => s.get(key));
  },
  async set(store, key, value) {
    return withStore(store, 'readwrite', s => s.put({ ...value, _ts: Date.now() }, key));
  },
  async delete(store, key) {
    return withStore(store, 'readwrite', s => s.delete(key));
  },
  async keys(store) {
    return withStore(store, 'readonly', s => s.getAllKeys());
  },
  async clear(store) {
    return withStore(store, 'readwrite', s => s.clear());
  },
  async getAll(store) {
    return withStore(store, 'readonly', s => s.getAll());
  },
  async add(store, value) {
    return withStore(store, 'readwrite', s => s.add({ ...value, _ts: Date.now() }));
  }
};

export default idb;
