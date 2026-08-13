/* noinspection DuplicatedCode */

/* Service Worker Template */
/* This file is processed by bump-sw.js to generate a versioned sw.js. */
/* The medilog_2026-08-13_21-41-47 placeholder is replaced with a timestamp. */

const CACHE_NAME = 'medilog_2026-08-13_21-41-47';

/* Static assets that are part of the app shell. */
const STATIC_ASSETS = ['/panel.html', '/rapor.html', '/dist/output.css', '/dist/output.js', '/app.js', '/dist/icons/manifest.json', '/dist/icons/browserconfig.xml', '/dist/icons/favicon.ico'];

/* All icon files (various sizes and formats). */
const ICON_FILES = [
    '/dist/icons/android-icon-36x36.png',
    '/dist/icons/android-icon-48x48.png',
    '/dist/icons/android-icon-72x72.png',
    '/dist/icons/android-icon-96x96.png',
    '/dist/icons/android-icon-144x144.png',
    '/dist/icons/android-icon-192x192.png',
    '/dist/icons/apple-icon-57x57.png',
    '/dist/icons/apple-icon-60x60.png',
    '/dist/icons/apple-icon-72x72.png',
    '/dist/icons/apple-icon-76x76.png',
    '/dist/icons/apple-icon-114x114.png',
    '/dist/icons/apple-icon-120x120.png',
    '/dist/icons/apple-icon-144x144.png',
    '/dist/icons/apple-icon-152x152.png',
    '/dist/icons/apple-icon-180x180.png',
    '/dist/icons/apple-icon-precomposed.png',
    '/dist/icons/apple-icon.png',
    '/dist/icons/favicon-16x16.png',
    '/dist/icons/favicon-32x32.png',
    '/dist/icons/favicon-96x96.png',
    '/dist/icons/ms-icon-70x70.png',
    '/dist/icons/ms-icon-144x144.png',
    '/dist/icons/ms-icon-150x150.png',
    '/dist/icons/ms-icon-310x310.png',
];

/* Data files (JSON) that are cached for offline access. */
const DATA_FILES = ['/data/hospitals.json', '/data/medication_changes.json', '/data/medication_logs.json', '/data/medications.json', '/data/pressures.json', '/data/reports.json', '/data/test_items.json', '/data/tests.json', '/data/users.json', '/data/weights.json'];

/* Combine all URLs to be cached. */
const CACHE_URLS = STATIC_ASSETS.concat(ICON_FILES, DATA_FILES);

/* Install event: cache all static assets and data files. */
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches
            .open(CACHE_NAME)
            .then((cache) => {
                console.log('Caching app shell and data');
                return cache.addAll(CACHE_URLS);
            })
            .then(() => self.skipWaiting()),
    );
});

/* Activate event: remove old caches and claim clients. */
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches
            .keys()
            .then((cacheNames) => {
                return Promise.all(cacheNames.filter((name) => name !== CACHE_NAME).map((name) => caches.delete(name)));
            })
            .then(() => self.clients.claim()),
    );
});

/* Fetch event: serve from cache if available, with network fallback and */
/* background updates for data files. */
self.addEventListener('fetch', (event) => {
    const request = event.request;

    /* Only handle GET requests for same-origin resources. */
    if (request.method !== 'GET' || !request.url.startsWith(self.location.origin)) {
        event.respondWith(fetch(request));
        return;
    }

    event.respondWith(
        caches.match(request).then((cachedResponse) => {
            if (cachedResponse) {
                /* For data files, attempt a background network update. */
                if (request.url.includes('/data/')) {
                    event.waitUntil(
                        fetch(request)
                            .then((networkResponse) => {
                                if (networkResponse.ok) {
                                    caches.open(CACHE_NAME).then((cache) => {
                                        cache.put(request, networkResponse.clone());
                                    });
                                }
                            })
                            .catch(() => {}),
                    );
                }
                return cachedResponse;
            }

            /* Not in cache: fetch from network and cache the response. */
            return fetch(request)
                .then((networkResponse) => {
                    if (!networkResponse.ok) {
                        return networkResponse;
                    }
                    const responseToCache = networkResponse.clone();
                    caches.open(CACHE_NAME).then((cache) => {
                        cache.put(request, responseToCache);
                    });
                    return networkResponse;
                })
                .catch((error) => {
                    console.error('Fetch failed:', error);
                    return new Response('Offline – content not available', {status: 503});
                });
        }),
    );
});

/* Message event: listen for 'CLEAR_CACHE' messages to delete all caches. */
/* Used by the app to force a refresh after clearing the service worker cache. */
self.addEventListener('message', (event) => {
    if (event.data && event.data.type === 'CLEAR_CACHE') {
        event.waitUntil(
            caches
                .keys()
                .then((keys) => Promise.all(keys.map((key) => caches.delete(key))))
                .then(() => {
                    if (event.ports && event.ports.length) {
                        event.ports[0].postMessage({status: 'cleared'});
                    }
                }),
        );
    }
});
