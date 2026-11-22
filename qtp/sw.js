const CACHE_NAME = 'qtp-pwa-cache-v3.0.0';
const APP_SHELL = [
  './',
  './index.html',
  './cevaplar.html',
  './manifest.webmanifest',
  './data.json',
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

  // Full-stack API isteklerini hiçbir zaman önbelleğe alma
  if (isSameOrigin && url.pathname.includes('/api/')) {
    return;
  }

  const isCdnAsset =
    url.hostname === 'cdn.tailwindcss.com' ||
    url.hostname === 'cdn.jsdelivr.net';

  if (isSameOrigin) {
    // Ağ öncelikli (çevrimdışıysa önbellekten döndür) -> Güncel data.json / index.html her zaman görünür
    event.respondWith(
      fetch(req)
        .then((res) => {
          if (res && res.ok) {
            const copy = res.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(req, copy));
          }
          return res;
        })
        .catch(() => caches.match(req).then((cached) => cached || caches.match('./index.html')))
    );
  } else if (isCdnAsset) {
    // Tailwind ve Alpine.js CDN betikleri için önbellek öncelikli (hızlı ve çevrimdışı destekli)
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
