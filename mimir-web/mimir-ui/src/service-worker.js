/* eslint-disable no-restricted-globals */
// Mimir UI Service Worker (Workbox InjectManifest compatible)
// Uses CRA's built-in Workbox pipeline. The placeholder self.__WB_MANIFEST MUST remain.
// Provides:
//  - Precache of build assets + offline.html
//  - Navigation route with offline fallback
//  - Runtime caching for API, images, and static assets
//  - SW update (skipWaiting via postMessage)

import { clientsClaim } from 'workbox-core';
import { precacheAndRoute, cleanupOutdatedCaches } from 'workbox-precaching';
import { registerRoute, setCatchHandler } from 'workbox-routing';
import { NetworkFirst, StaleWhileRevalidate, CacheFirst } from 'workbox-strategies';
import { ExpirationPlugin } from 'workbox-expiration';

// Placeholder injected at build time (DO NOT REMOVE)
// eslint-disable-next-line no-undef
const WB_MANIFEST = self.__WB_MANIFEST || [];

// Add explicit offline page to precache (revision null => no hash; update filename to bust)
const OFFLINE_URL = '/offline.html';
const EXTRA_PRECACHE = [{ url: OFFLINE_URL, revision: null }];

precacheAndRoute(WB_MANIFEST.concat(EXTRA_PRECACHE));
cleanupOutdatedCaches();
self.skipWaiting();
clientsClaim();

// Navigation requests: network first with offline fallback
registerRoute(
  ({ request }) => request.mode === 'navigate',
  async ({ event }) => {
    try {
      return await new NetworkFirst({ cacheName: 'mimir-pages', networkTimeoutSeconds: 5 }).handle({ event });
    } catch (e) {
      const cache = await caches.open('mimir-pages');
      const offline = await cache.match(OFFLINE_URL) || await caches.match(OFFLINE_URL);
      return offline || new Response('Offline', { status: 503, headers: { 'Content-Type': 'text/plain' } });
    }
  }
);

// API runtime caching (NetworkFirst; fallback to cache)
registerRoute(
  ({ url }) => url.pathname.startsWith('/api/'),
  new NetworkFirst({
    cacheName: 'mimir-api',
    networkTimeoutSeconds: 8,
    plugins: [
      new ExpirationPlugin({ maxEntries: 150, maxAgeSeconds: 5 * 60 })
    ]
  })
);

// Images: CacheFirst with expiration
registerRoute(
  ({ request }) => request.destination === 'image',
  new CacheFirst({
    cacheName: 'mimir-images',
    plugins: [
      new ExpirationPlugin({ maxEntries: 200, maxAgeSeconds: 24 * 60 * 60 })
    ]
  })
);

// Scripts, styles, fonts: StaleWhileRevalidate
registerRoute(
  ({ request }) => ['script', 'style', 'font'].includes(request.destination),
  new StaleWhileRevalidate({ cacheName: 'mimir-static' })
);

// Generic catch handler for route failures
setCatchHandler(async ({ event }) => {
  if (event.request.mode === 'navigate') {
    return caches.match(OFFLINE_URL);
  }
  return Response.error();
});

// Listen for skip waiting
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});

// --- Background Sync Outbox Handling ---
// Lightweight outbox flush inside SW (separate from page-level helper). We store queued
// mutations in IndexedDB 'outbox' store. SW cannot import page modules directly (no bundler here),
// so we implement minimal IDB helpers again (duplicated intentionally to avoid coupling).

async function openOutboxDb() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open('mimir-cache', 2);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains('outbox')) {
        db.createObjectStore('outbox', { keyPath: 'id' });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function outboxTx(mode, fn) {
  const db = await openOutboxDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('outbox', mode);
    const store = tx.objectStore('outbox');
    let result;
    tx.oncomplete = () => resolve(result);
    tx.onerror = () => reject(tx.error);
    result = fn(store);
  });
}

async function getAllOutbox() {
  return outboxTx('readonly', s => s.getAll());
}
async function putOutbox(item) {
  return outboxTx('readwrite', s => s.put(item));
}
async function deleteOutbox(id) {
  return outboxTx('readwrite', s => s.delete(id));
}

function calcNextAttempt(attemptCount) {
  const base = 2000;
  const expo = Math.min(attemptCount - 1, 6);
  return Date.now() + base * Math.pow(2, expo);
}

async function flushOutbox() {
  const all = await getAllOutbox();
  const now = Date.now();
  const eligible = all.filter(i => i.status === 'pending' && i.next_attempt_at <= now).sort((a,b)=>a.created_at-b.created_at).slice(0, 25);
  for (const item of eligible) {
    let updated = { ...item, status: 'sending', last_attempt_at: Date.now() };
    await putOutbox(updated);
    try {
      const res = await fetch(item.url, {
        method: item.method || 'POST',
        headers: { 'Content-Type': 'application/json', ...(item.headers||{}) },
        body: item.body ? JSON.stringify(item.body) : undefined
      });
      if (!res.ok) {
        if (res.status >= 400 && res.status < 500 && res.status !== 429) {
          await putOutbox({ ...updated, status: 'dead-letter', http_status: res.status });
          continue;
        }
        throw new Error('HTTP '+res.status);
      }
      await deleteOutbox(item.id);
      const clientsList = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
      clientsList.forEach(c => c.postMessage({ type: 'OUTBOX_ITEM_SENT', id: item.id }));
    } catch (e) {
      const attempts = (item.attempt_count || 0) + 1;
      if (attempts >= 8) {
        await putOutbox({ ...updated, status: 'dead-letter', attempt_count: attempts, error: e.message });
      } else {
        await putOutbox({ ...updated, status: 'pending', attempt_count: attempts, next_attempt_at: calcNextAttempt(attempts) });
      }
    }
  }
  const clientsList = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
  clientsList.forEach(c => c.postMessage({ type: 'OUTBOX_UPDATED' }));
}

self.addEventListener('sync', event => {
  if (event.tag === 'mimir-outbox') {
    event.waitUntil(flushOutbox());
  }
});

// Fallback: try flush when we regain connectivity
self.addEventListener('online', () => {
  flushOutbox();
});

// Listen for manual flush command from client
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'OUTBOX_FLUSH') {
    flushOutbox();
  }
});

console.log('[SW] Mimir UI Workbox service worker loaded');
/* eslint-disable no-restricted-globals */
// Basic service worker implementing app-shell caching + runtime strategies.
// Generated for Mimir UI. Adjust cache version when deploying new releases.

const APP_VERSION = 'v1';
const APP_SHELL_CACHE = `mimir-app-shell-${APP_VERSION}`;
const RUNTIME_CACHE = 'mimir-runtime';
const OFFLINE_FALLBACK_PAGE = '/offline.html';

// Resources to precache (app shell). Build tool will inject hashed bundle files dynamically if configured.
const APP_SHELL_ASSETS = [
  '/',
  '/index.html',
  OFFLINE_FALLBACK_PAGE,
  '/manifest.json',
  '/favicon.ico'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(APP_SHELL_CACHE).then(cache => cache.addAll(APP_SHELL_ASSETS)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys => Promise.all(
      keys.filter(k => k.startsWith('mimir-app-shell-') && k !== APP_SHELL_CACHE).map(k => caches.delete(k))
    )).then(() => self.clients.claim())
  );
});

// Utility: network with cache fallback for API JSON
async function networkFirst(request) {
  try {
    const networkResponse = await fetch(request);
    const cache = await caches.open(RUNTIME_CACHE);
    cache.put(request, networkResponse.clone());
    return networkResponse;
  } catch (err) {
    const cache = await caches.open(RUNTIME_CACHE);
    const cached = await cache.match(request);
    if (cached) return cached;
    throw err;
  }
}

// Utility: cache-first for static immutable assets
async function cacheFirst(request) {
  const cache = await caches.open(APP_SHELL_CACHE);
  const cached = await cache.match(request);
  if (cached) return cached;
  const response = await fetch(request);
  if (response.ok) cache.put(request, response.clone());
  return response;
}

self.addEventListener('fetch', event => {
  const { request } = event;
  const url = new URL(request.url);

  // Bypass non-GET
  if (request.method !== 'GET') return;

  // Same-origin navigation requests -> App Shell (SPA) strategy
  if (request.mode === 'navigate') {
    event.respondWith(
      (async () => {
        try {
          const preload = await event.preloadResponse;
          if (preload) return preload;
          const networkResponse = await fetch(request);
          const cache = await caches.open(APP_SHELL_CACHE);
          cache.put('/index.html', networkResponse.clone());
          return networkResponse;
        } catch (e) {
          const cache = await caches.open(APP_SHELL_CACHE);
          const offline = await cache.match(OFFLINE_FALLBACK_PAGE);
          if (offline) return offline;
          return new Response('Offline', { status: 503, headers: { 'Content-Type': 'text/plain' } });
        }
      })()
    );
    return;
  }

  // API calls (heuristic: /api/) -> network first
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(networkFirst(request));
    return;
  }

  // Static assets (images, css, js, fonts) -> cache first
  if (/\.(?:png|jpg|jpeg|svg|gif|webp|ico|css|js|woff2?)$/i.test(url.pathname)) {
    event.respondWith(cacheFirst(request));
    return;
  }

  // Default: try network then cache
  event.respondWith(
    (async () => {
      try {
        return await fetch(request);
      } catch {
        const cache = await caches.open(RUNTIME_CACHE);
        const match = await cache.match(request);
        return match || new Response('', { status: 204 });
      }
    })()
  );
});

// Listen for skipWaiting message to activate updated SW immediately
self.addEventListener('message', event => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});
