// noinspection DuplicatedCode

const CACHE_NAME = 'medilog_2026-07-21_23-55-39';
const STATIC_ASSETS = ['/panel.html', '/rapor.html', '/dist/output.css', '/dist/output.js', '/app.js', '/dist/icons/manifest.json', '/dist/icons/browserconfig.xml', '/dist/icons/favicon.ico'];

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

const DATA_FILES = ['/data/hospitals.json', '/data/medication_changes.json', '/data/medication_logs.json', '/data/medications.json', '/data/pressures.json', '/data/reports.json', '/data/test_items.json', '/data/tests.json', '/data/users.json', '/data/weights.json'];

const CACHE_URLS = STATIC_ASSETS.concat(ICON_FILES, DATA_FILES);

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

self.addEventListener('fetch', (event) => {
    const request = event.request;

    if (request.method !== 'GET' || !request.url.startsWith(self.location.origin)) {
        event.respondWith(fetch(request));
        return;
    }

    event.respondWith(
        caches.match(request).then((cachedResponse) => {
            if (cachedResponse) {
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
                    return new Response('Offline – content not available', { status: 503 });
                });
        }),
    );
});
