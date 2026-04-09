/* eslint-disable no-restricted-globals */
// Service Worker for Mimir UI (public/ version)
// Notes:
// - Served verbatim from /service-worker.js (CRA copies public assets)
// - Version is injected at build time via /sw-version.js to trigger fresh caches on deploy
// - Keep APP_SHELL_ASSETS lean (index + offline + manifest + favicon). Hashed build files are runtime-cached.

try {
  importScripts('/sw-version.js');
} catch {
  // Fall back to a static cache namespace if version injection is unavailable.
}

const APP_VERSION = self.__MIMIR_SW_VERSION__ || 'v1';
const APP_SHELL_CACHE = `mimir-app-shell-${APP_VERSION}`;
const RUNTIME_CACHE = `mimir-runtime-${APP_VERSION}`;
const OFFLINE_FALLBACK_PAGE = '/offline.html';

const APP_SHELL_ASSETS = [
  '/',
  '/index.html',
  OFFLINE_FALLBACK_PAGE,
  '/manifest.json',
  '/favicon.ico'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(APP_SHELL_CACHE)
      .then(cache => cache.addAll(APP_SHELL_ASSETS))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys => Promise.all(
      keys
        .filter(k => (k.startsWith('mimir-app-shell-') || k.startsWith('mimir-runtime-')) && k !== APP_SHELL_CACHE && k !== RUNTIME_CACHE)
        .map(k => caches.delete(k))
    )).then(() => self.clients.claim())
  );
});

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

self.addEventListener('fetch', event => {
  const { request } = event;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);

  if (request.mode === 'navigate') {
    event.respondWith((async () => {
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
    })());
    return;
  }

  if (url.pathname.startsWith('/api/')) {
    event.respondWith(networkFirst(request));
    return;
  }

  if (/\.(?:png|jpg|jpeg|svg|gif|webp|ico|css|js|woff2?)$/i.test(url.pathname)) {
    event.respondWith(networkFirst(request));
    return;
  }

  event.respondWith((async () => {
    try {
      return await fetch(request);
    } catch {
      const cache = await caches.open(RUNTIME_CACHE);
      const match = await cache.match(request);
      return match || new Response('', { status: 204 });
    }
  })());
});

self.addEventListener('message', event => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});

console.log('[SW] Mimir UI service worker loaded', APP_VERSION);
