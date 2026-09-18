/* noinspection DuplicatedCode */

/* Service Worker Template */
/* This file is processed by bump-sw.js to generate a versioned sw.js. */
/* The medilog_2026-09-18_21-13-21 placeholder is replaced with a timestamp. */

const CACHE_NAME = 'medilog_2026-09-18_21-13-21';

/* ========================================================================== */
/* AŞAMA 1: KRİTİK DOSYALAR (Uygulamanın açılması için zorunlu olanlar)       */
/* ========================================================================== */

/* 1. App Shell & HTML Sayfaları */
const APP_SHELL = ['/', '/index.html', '/panel.html', '/ai/index.html', '/dist/output.css', '/dist/output.js', '/app.js'];

/* 1.1. İkincil Sayfalar ve Dizin Rotaları */
const APP_SECONDARY = ['/panel/', '/rapor.html', '/rapor/', '/calc.html', '/calc/', '/hesap.html', '/hesap/', '/ai/'];

/* 2. Klinik Veri Dosyaları (18 JSON Dosyası) */
const DATA_FILES = ['/data/appointments.json', '/data/clinical_context.json', '/data/glucose.json', '/data/hospitals.json', '/data/medication_changes.json', '/data/medication_logs.json', '/data/medications.json', '/data/pressures.json', '/data/pulse.json', '/data/reports.json', '/data/saturation.json', '/data/sleep.json', '/data/symptoms.json', '/data/temperatures.json', '/data/test_items.json', '/data/tests.json', '/data/users.json', '/data/weights.json'];

/* 1. AŞAMA BİRLEŞİMİ: Uygulamanın anında açılması için indirilecekler */
const PRIORITY_URLS = [...APP_SHELL, ...APP_SECONDARY, ...DATA_FILES, '/dist/icons/manifest.json', '/dist/icons/favicon.ico'];

/* ========================================================================== */
/* AŞAMA 2: ARKA PLAN DOSYALARI (Uygulama açıldıktan sonra çekilecekler)     */
/* ========================================================================== */

/* 3. Tüm PWA İkon Dosyaları */
const ICON_FILES = [
  '/dist/icons/browserconfig.xml',
  '/dist/icons/favicon-16x16.png',
  '/dist/icons/favicon-32x32.png',
  '/dist/icons/favicon-96x96.png',
  '/dist/icons/android-icon-36x36.png',
  '/dist/icons/android-icon-48x48.png',
  '/dist/icons/android-icon-72x72.png',
  '/dist/icons/android-icon-96x96.png',
  '/dist/icons/android-icon-144x144.png',
  '/dist/icons/android-icon-192x192.png',
  '/dist/icons/android-icon-512x512.png',
  '/dist/icons/apple-icon.png',
  '/dist/icons/apple-icon-precomposed.png',
  '/dist/icons/apple-icon-57x57.png',
  '/dist/icons/apple-icon-60x60.png',
  '/dist/icons/apple-icon-72x72.png',
  '/dist/icons/apple-icon-76x76.png',
  '/dist/icons/apple-icon-114x114.png',
  '/dist/icons/apple-icon-120x120.png',
  '/dist/icons/apple-icon-144x144.png',
  '/dist/icons/apple-icon-152x152.png',
  '/dist/icons/apple-icon-180x180.png',
  '/dist/icons/ms-icon-70x70.png',
  '/dist/icons/ms-icon-144x144.png',
  '/dist/icons/ms-icon-150x150.png',
  '/dist/icons/ms-icon-310x310.png',
];

/* 4. Tüm AI Raporları (PDF, DOCX, MD) */
const AI_REPORTS = ['/ai/_data/claude_rapor.docx', '/ai/_data/claude_rapor.md', '/ai/_data/claude_rapor.pdf', '/ai/_data/claude_rapor.v2.docx', '/ai/_data/claude_rapor.v3.docx', '/ai/_data/deepseek_rapor.docx', '/ai/_data/deepseek_rapor.md', '/ai/_data/deepseek_rapor.pdf', '/ai/_data/gemini_rapor.docx', '/ai/_data/gemini_rapor.md', '/ai/_data/gemini_rapor.pdf', '/ai/_data/gpt_rapor.docx', '/ai/_data/gpt_rapor.md', '/ai/_data/gpt_rapor.pdf'];

/* 5. Proje Dokümantasyonu ve Geliştirici Dosyaları */
const PROJECT_DOCS = ['/PROJECT.md', '/README.md', '/package.json', '/input.css', '/input.js', '/bump-sw.js', '/tests/app.test.js'];

/* 2. AŞAMA BİRLEŞİMİ: Arka planda eşzamanlı indirilecekler */
const DEFERRED_URLS = [...ICON_FILES, ...AI_REPORTS, ...PROJECT_DOCS];

/* ========================================================================== */
/* EŞZAMANLI (CONCURRENT) VE DAYANIKLI İNDİRME MOTORU                         */
/* ========================================================================== */

/**
 * Belirtilen URL listesini belirlenen eşzamanlılık limitiyle (worker pool) indirir.
 * Hata toleranslıdır: Tek bir dosyanın 404 vermesi diğerlerini engellemez.
 */
async function cacheConcurrently(cacheName, urls, concurrencyLimit = 6) {
  const cache = await caches.open(cacheName);
  let currentIndex = 0;

  async function worker() {
    while (currentIndex < urls.length) {
      const url = urls[currentIndex++];
      try {
        const response = await fetch(url, {cache: 'no-cache'});
        if (response.ok) {
          await cache.put(url, response);
        } else {
          console.warn(`[SW] Atlandı (${response.status}): ${url}`);
        }
      } catch (error) {
        console.warn(`[SW] İndirme başarısız (${url}):`, error);
      }
    }
  }

  const workers = Array.from({length: Math.min(concurrencyLimit, urls.length)}, () => worker());

  return Promise.all(workers);
}

/* ========================================================================== */
/* SERVICE WORKER YAŞAM DÖNGÜSÜ (LIFECYCLE)                                    */
/* ========================================================================== */

/* 1. INSTALL: Yalnızca öncelikli çekirdek dosyaları indir ve hemen aktifleş */
self.addEventListener('install', (event) => {
  event.waitUntil(
    cacheConcurrently(CACHE_NAME, PRIORITY_URLS, 6).then(() => {
      console.log('[SW] 1. Aşama tamamlandı: Çekirdek uygulama hazır.');
      return self.skipWaiting();
    }),
  );
});

/* 2. ACTIVATE: Eski önbelleği temizle, kontrolü al ve arka plan indirmesini başlat */
self.addEventListener('activate', (event) => {
  event.waitUntil(
    (async () => {
      /* Eski önbellekleri temizle */
      const cacheNames = await caches.keys();
      await Promise.all(cacheNames.filter((name) => name !== CACHE_NAME).map((name) => caches.delete(name)));

      /* Sayfaların kontrolünü anında devral */
      await self.clients.claim();
      console.log('[SW] Aktifleşti. 2. Aşama: Arka plan indirmesi başlıyor...');

      /* 2. Aşamayı (PDF, DOCX, ikonlar, dokümanlar) arka planda eşzamanlı çek */
      await cacheConcurrently(CACHE_NAME, DEFERRED_URLS, 6);
      console.log('[SW] 2. Aşama tamamlandı: Tüm rapor ve dokümanlar çevrimdışı hazır.');
    })(),
  );
});

/* ========================================================================== */
/* FETCH & CACHE STRATEJİSİ                                                   */
/* ========================================================================== */

self.addEventListener('fetch', (event) => {
  const request = event.request;

  /* Yalnızca aynı kökenden (origin) gelen GET isteklerini yakala */
  if (request.method !== 'GET' || !request.url.startsWith(self.location.origin)) {
    event.respondWith(fetch(request));
    return;
  }

  event.respondWith(
    caches.match(request).then(async (cachedResponse) => {
      /* 1. Önbellekte birebir eşleşme varsa sun */
      if (cachedResponse) {
        /* /data/ altındaki JSON dosyaları için arka planda güncelle (Stale-While-Revalidate) */
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

      /* 2. Dizin / Clean URL eşleme kontrolü (/panel -> /panel.html ya da /panel/) */
      if (request.mode === 'navigate') {
        const url = new URL(request.url);
        const path = url.pathname;
        const fallback = (await caches.match(path + '.html')) || (await caches.match(path + '/')) || (await caches.match(path + '/index.html'));
        if (fallback) {
          return fallback;
        }
      }

      /* 3. Önbellekte yoksa ağdan çek ve dinamik olarak önbelleğe ekle */
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
          console.error('[SW] Çevrimdışı erişim hatası:', error);
          return new Response('Offline – içerik bulunamadı', {status: 503});
        });
    }),
  );
});

/* 4. CLEAR_CACHE Mesaj Dinleyicisi */
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
