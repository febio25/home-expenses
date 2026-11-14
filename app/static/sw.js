// Service worker: keeps the app shell (HTML, CSS, JS, icons) in a local cache
// so the app opens instantly. Data is never cached: every API call goes to
// the server. This is not an offline mode.
//
// The two placeholders below are filled in by the server when it serves this
// file: a build id that changes whenever any static file changes, and the
// list of files to cache. A new build id means a new worker, which swaps the
// cache; the next launch then runs the new version.

const BUILD = '__BUILD_ID__';
const SHELL_FILES = __SHELL_FILES__;
const CACHE = `spese-shell-${BUILD}`;

self.addEventListener('install', (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE);
    // cache: 'reload' bypasses the HTTP cache, so the new shell is really new.
    await cache.addAll(SHELL_FILES.map((url) => new Request(url, { cache: 'reload' })));
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const names = await caches.keys();
    await Promise.all(names
      .filter((name) => name.startsWith('spese-shell-') && name !== CACHE)
      .map((name) => caches.delete(name)));
    await self.clients.claim();
  })());
});

self.addEventListener('fetch', (event) => {
  const request = event.request;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith('/api/') || url.pathname === '/healthz' || url.pathname === '/sw.js') return;

  event.respondWith((async () => {
    const cache = await caches.open(CACHE);
    // Every in-app route (/, /movimenti, ...) is the same HTML shell.
    const cached = await cache.match(request.mode === 'navigate' ? '/' : request, { ignoreSearch: true });
    if (cached) return cached;
    return fetch(request);
  })());
});
