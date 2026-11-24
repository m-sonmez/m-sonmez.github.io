const CACHE_NAME = 'qtp-pwa-cache-v3.5.1';
const APP_SHELL = [
  './',
  './index.html',
  './qtp.html',
  './theme.css',
  './legacy/cevaplar.html',
  './manifest.webmanifest',
  './data.json',
  './QuickTextPaste.ini',
  './docs/KULLANIM.md',
  './docs/KURULUM.md',
  './docs/KISAYOLLAR.md',
  './docs/SSS.md',
  './icon.svg',
  './icon-192.png',
  './icon-512.png'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll(APP_SHELL))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(
        keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))
      ))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;

  const url = new URL(req.url);
  const isSameOrigin = url.origin === self.location.origin;

  if (isSameOrigin && url.pathname.includes('/api/')) {
    return;
  }

  const isCdnAsset =
    url.hostname === 'cdn.tailwindcss.com' ||
    url.hostname === 'cdn.jsdelivr.net';

  if (isSameOrigin) {
    const isFreshJsonOrHtml =
      req.mode === 'navigate' ||
      url.pathname.endsWith('/data.json') ||
      url.pathname.endsWith('/QuickTextPaste.ini') ||
      url.pathname.endsWith('/theme.css') ||
      url.pathname.endsWith('/index.html') ||
      url.pathname.endsWith('/qtp.html') ||
      url.pathname.endsWith('/cevaplar.html') ||
      url.pathname.endsWith('.md') ||
      url.pathname.endsWith('/');

    const networkPromise = isFreshJsonOrHtml && req.cache === 'default'
      ? fetch(new Request(req, { cache: 'no-cache' })).catch(() => fetch(req))
      : fetch(req);

    event.respondWith(
      networkPromise
        .then((res) => {
          if (res && res.ok) {
            const copy = res.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(req, copy));
          }
          return res;
        })
        .catch(() => caches.match(req).then((cached) => {
          if (cached) return cached;
          if (req.mode === 'navigate') return caches.match('./index.html');
          return new Response('', { status: 503, statusText: 'Offline' });
        }))
    );
  } else if (isCdnAsset) {
    event.respondWith(
      caches.match(req).then((cached) => {
        if (cached) return cached;
        return fetch(req)
          .then((res) => {
            if (res && (res.ok || res.type === 'opaque')) {
              const copy = res.clone();
              caches.open(CACHE_NAME).then((cache) => cache.put(req, copy));
            }
            return res;
          })
          .catch(() => new Response('', { status: 503 }));
      })
    );
  }
});
