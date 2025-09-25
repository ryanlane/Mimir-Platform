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
