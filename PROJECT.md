# PROJECT.md – Klinik Takip Dashboard (Güncel v1.2)

## 1. Proje Genel Bakış

Bu proje, bir hastanın (örnek olarak Alaattin Sönmez) ameliyat sonrası klinik verilerini izlemek için geliştirilmiş kapsamlı bir **tek sayfa dashboard** uygulamasıdır. Tansiyon, kilo, ilaç kullanımı, laboratuvar sonuçları, raporlar ve klinik olaylar kronolojik olarak takip edilir.

**Temel Özellikler:**

- Tüm veri dosyaları (`data/` klasörü) statik JSON’dır ve `fetch` ile yüklenir.
- **Zero hard-coding** prensibi: Hasta adı, ID’si, tarihler veya klinik olaylar kod içinde sabitlenmemiştir; her şey JSON verilerinden dinamik olarak okunur.
- Gerçek bir API olmadığı için veriler `data/` klasöründen okunur. `corsError` yakalanıp yerleşik (boş) verilerle çalışılabilir.
- **PWA** desteği (Service Worker) ile offline çalışma ve cache yönetimi.

**Teknoloji Yığını:**

- **Frontend Framework**: Alpine.js 3.15.12 (reaktif state yönetimi)
- **Grafik Kütüphanesi**: Chart.js 4.5.1 + date-fns adapter
- **CSS**: Tailwind CSS 4.3.0 (derlenmiş `dist/output.css`)
- **Build Araçları**: esbuild, PostCSS/Tailwind CLI, concurrently
- **Service Worker**: PWA desteği, offline cache (versiyonlama `bump-sw.js` ile)
- **Test**: Node.js test runner (`node:test` + `assert`)

**Kullanıcı Arayüzü:**

- Sol tarafta genişletilebilir/daraltılabilir sidebar
- Sağda ana içerik alanı
- Tarih filtreleri (preset’ler, özel aralık, önceki/sonraki dönem butonları)
- 9 ana bölüm (özet, grafikler, zaman akışı, ilaç matrisi, takvim, tahlil trendleri, tetkik & bulgular, raporlar, klinik analiz)
- Animasyon: tarih aralığını otomatik ilerleterek zaman içindeki değişimi gösterir.
- Veri indirme: tüm veriyi veya seçili dönemi JSON olarak dışa aktarabilir.

---

## 2. Dosya Yapısı ve Açıklamaları

```
├── panel.html                   # Ana HTML sayfası (tüm UI)
├── app.js                       # Alpine.js dashboardApp bileşeni ve utility fonksiyonlar
├── input.js                     # Alpine ve Chart.js kurulumu, dashboardApp kaydı
├── input.css                    # Tailwind giriş dosyası ve özel stiller
├── bump-sw.js                   # Service Worker versiyon oluşturucu (timestamp)
├── sw.template.js               # Service Worker şablonu ({{CACHE_VERSION}})
├── sw.js                        # Derlenmiş Service Worker (bump ile üretilir)
├── package.json                 # NPM betikleri ve bağımlılıklar
├── tests/                       # Test dosyaları
│   └── app.test.js              # Unit testler (utility fonksiyonlar)
├── data/                        # Statik JSON veri kaynakları
│   ├── users.json               # Kullanıcı bilgisi (hasta)
│   ├── hospitals.json           # Hastane listesi
│   ├── clinical_context.json    # Klinik özet, cerrahi detaylar, zaman çizelgesi
│   ├── medications.json         # İlaç tanımları (doz, tip, renk, vs.)
│   ├── medication_changes.json  # İlaç başlama/bitirme/doz değişimleri
│   ├── medication_logs.json     # Günlük ilaç alım logları
│   ├── pressures.json           # Kan basıncı ölçümleri
│   ├── weights.json             # Vücut ağırlığı ölçümleri
│   ├── tests.json               # Tahlil seansları
│   ├── test_items.json          # Tahlil parametreleri (sonuç, referans aralığı)
│   ├── reports.json             # Raporlar (epikriz, radyoloji, ameliyat)
│   ├── temperatures.json        # (boş) – ateş ölçümleri – yapısal şablon
│   ├── glucose.json             # (boş) – kan şekeri – yapısal şablon
│   ├── pulse.json               # (boş) – nabız – yapısal şablon
│   ├── saturation.json          # (boş) – oksijen satürasyonu – yapısal şablon
│   ├── sleep.json               # (boş) – uyku verileri – yapısal şablon
│   ├── symptoms.json            # (boş) – semptom kayıtları – yapısal şablon
│   └── appointments.json        # (boş) – randevular – yapısal şablon
├── dist/                        # Derlenmiş çıktılar
│   ├── output.css               # Tailwind derlenmiş CSS
│   ├── output.js                # Alpine + Chart.js bundle (esbuild)
│   └── icons/                   # PWA ikonları ve manifest
│       ├── manifest.json
│       ├── browserconfig.xml
│       ├── favicon.ico
│       └── ... (png dosyaları)
└── (diğer dosyalar)
```

### 2.1. HTML: `panel.html`

- **Meta / PWA**: Apple Touch Icons, manifest, theme-color, service worker kaydı (app.js içinde)
- **x-data="dashboardApp()"** – Alpine bileşenini bağlar.
- **Ekran çok küçük uyarısı** (`max-[384px]:flex`) – 384px altında kullanıcıya telefonu yan çevirmesini söyler.
- **CORS Hatası Uyarısı** – `corsError` true olduğunda gösterilir.
- **Sidebar**:
    - Logo, tarih filtreleri (preset select, önceki/sonraki dönem butonları, başlangıç/bitiş date input)
    - Navigasyon menüsü (bölüm linkleri ve toggle switch’ler)
    - Animasyon kontrolleri (kapsam, hız, oynat/duraklat/durdur)
    - Veri indirme butonları
    - Versiyon bilgisi
    - Daraltılmış halde ikonlar (animasyon, indirme)
- **Ana İçerik**:
    - Mobil menü açma butonu (fixed)
    - 9 bölüm (`#summary`, `#charts`, `#prescriptions`, `#flowsheet`, `#calendar`, `#lab-trends`, `#lab-findings`, `#reports`, `#clinical-report`)
    - Her bölüm `x-show="sections.<key>"` ile kontrol edilir.
    - Her bölümde grafikler, tablolar, listeler, kartlar bulunur.
- **Yukarı çık butonu** – `window.scrollY > 300` olduğunda görünür, 3 saniye sonra kaybolur.
- **Tüm UI** Alpine reactive verilere bağlıdır.

### 2.2. CSS: `input.css` ve `output.css`

- `input.css` Tailwind `@import` ile başlar, özel temalar tanımlar (`--font-*`, container breakpoints).
- `html { scroll-behavior: smooth; }`
- `[x-cloak] { display: none !important; }` – Alpine cloak.
- Özel scrollbar stilleri.
- `.glass-card` ve `.glass-card-hover` – kart görünümü.
- `.app-card`, `.app-card-hover`, `.app-card-header`, `.app-card-title`, `.btn-toggle-label`, `.switch-slider` gibi utility sınıfları `@apply` ile tanımlanmış.
- Durum badge’leri için (`bg-emerald-50`, `text-amber-700` vb.) özel override’lar.
- `input[type='date']` hizalama düzeltmeleri.
- Sidebar geçişleri için `lg:w-64` / `lg:w-14` width transition.
- CSS değişkenleri (`--bp-target-*`, `--notification-*`) tanımlanmış.

### 2.3. JavaScript: `app.js`

Bu dosya, Alpine bileşenini (`dashboardApp`) ve global utility fonksiyonlarını içerir.

#### 2.3.1. Global Utility Fonksiyonlar (diğer dosyalarda kullanılabilir)

- `debounce(func, wait)` – basit debounce.
- `getBPStatusText(sys, dia)` – Normal / Prehipertansiyon / Hipertansiyon döndürür.
- `getBPBadgeClass(sys, dia)` – badge CSS sınıfı döndürür.
- `getLabItemStatus(item)` – Normal / Düşük / Yüksek.
- `formatTurkishDate(isoDate)` – `YYYY-MM-DD` → `DD.MM.YYYY`.
- `formatFullDate(dateInput)` – `YYYY-MM-DD` → `D MMMM YYYY` (Türkçe).

#### 2.3.2. Alpine Bileşeni: `dashboardApp()`

**State (reaktif veriler):**

```javascript
{
  flowsheetMode: 'grid', // 'grid' | 'chart'
  corsError: false,      // JSON yüklenemezse true
  datePreset: 'all',     // 'all' | '3' | '7' | ... | 'custom'
  startDate: '', endDate: '',
  firstD: '', lastD: '', // global veri aralığı
  dateFiltersOpen: true,
  calendarYear: null, calendarMonth: null,
  selectedCalendarDayStr: null,
  showOnlyOutOfBoundsTests: false, // tahlil filtresi
  hideSpecialTests: true,          // AKG & Crossmatch gizle
  user: {}, hospitals: [], medications: [], medicationChanges: [], medicationLogs: [],
  pressures: [], weights: [], tests: [], testItems: [],
  metrics: { avgSys, avgDia, currentWeight, startWeight, weightDelta, adherenceRate, outOfBoundsCount, outOfBoundsList, latestInr, latestHgb, bpStatusText, bpStatusClass },
  flowsheetDays: [], allFlowsheetMeds: [], uniqueMeds: [],
  onlyMeds: false, // takvim gün detayında sadece ilaçları göster
  tooltip: { show, x, y, med, date, count, times },
  selectedTestId: null, selectedTestObj: {}, selectedTestItems: [],
  medTimeline: [], detailedMeds: [], selectedMed: [], onlyActive: true,
  activeTooltip: null, activeCellTooltip: null,
  medConversions: {}, medConfig: {}, medColors: {}, medGroups: {},
  bpViewMode: 'trend', // 'trend' | 'raw'
  sections: { summary: true, charts: true, prescriptions: false, flowsheet: false, calendar: true, labTrends: true, labFindings: false, reports: false, clinicalReport: false },
  refreshing: false,
  animStatus: 'idle', // 'idle' | 'playing' | 'paused'
  animScope: 'all',   // 'all' | 'period'
  animTargetDate: null,
  animSpeedIndex: 2,
  isInitializing: true,
  clinicalContext: {},
  // computed getter'lar ve metotlar...
}
```

**Computed Getter’lar (Alpine’in reactive hesaplamaları):**

- `animSpeedLabel` – hız seviyesi metni (x1/2, x1, x2, x4, x8)
- `isMobile` – `window.innerWidth < 1024`
- `isAtTop` – scroll pozisyonu
- `toolbarOpen` – (kullanılmıyor)
- `loadingMetrics`, `loadingTimeline`, `loadingBpChart`, `loadingLabCharts`, `loadingFlowsheet`, `loadingInsights` – yükleme bayrakları
- `_loaded` – (kullanılmıyor)
- `sidebarOpen`, `sidebarCollapsed`, `userMenuOpen` – UI state
- `testPage`, `reportPage`, `itemsPerPage` – sayfalama
- `paginatedTests`, `totalTestPages` – tahlil sayfalama
- `paginatedReports`, `totalReportPages` – rapor sayfalama
- `userInitials` – kullanıcı adının baş harfleri
- `activeMeds`, `passiveMeds` – aktif/pasif ilaçlar (endDate bazında)
- `filteredMedTimeline`, `filteredTimeline` – ilaç değişimleri ve olay akışı (filtrelenmiş)
- `filteredTests` – tahliller (sınır dışı, gizleme, tarih aralığı)
- `sortedReports` – raporlar tarihe göre sıralı
- `calendarMonthName`, `calendarDays`, `getDailyEvents(dateStr)` – takvim işlemleri
- `latestKilo`, `previousKilo`, `latestBp`, `previousBp`, `previousAvgBp`, `latestInr`, `previousInr`, `latestHgb`, `previousHgb` – metrik kartları için hesaplamalar
- `getFilteredPressures()`, `getFilteredWeights()` – tarih aralığına göre filtreleme
- `visibleMeds` – zaman akışı grafiğinde gösterilecek ilaçlar (segmentlerle)
- `timelineLabels` – zaman akışı X ekseni etiketleri

**Metotlar:**

- `initDashboard()` – asenkron veri yükleme, başlangıç ayarları, watcher’lar.
- `loadAllData(cacheBust)` – tüm JSON dosyalarını fetch eder.
- `loadBackupData()` – CORS hatasında boş verilerle çalışır.
- `determineGlobalDateLimits()` – tüm verilerden ilk ve son tarihi hesaplar, `firstD`, `lastD`, `validDatesPool` doldurur.
- `applyDatePreset()` – seçili preset’e göre `startDate`/`endDate` günceller.
- `shiftDatePeriod(direction)` – seçili aralığı öne/geri kaydırır.
- `updateFilters()` – debounce ile filtreleri günceller ve ilgili bölümleri yeniden yükler.
- `snapDateToValid(dateStr)` – geçerli veri tarihlerine yakın olanı bulur.
- `calculateMetrics()` – tansiyon ortalaması, kilo değişimi, ilaç uyumu (dinamik hospital exclusion ile), anormal tahliller vb. hesaplar.
- `populateMedTimeline()` – `medicationChanges`’ten `medTimeline` oluşturur.
- `updateVisibleMeds()` – `detailedMeds`’i günceller (ilaç segmentleri).
- `setupFlowsheet()` – `flowsheetDays` ve `uniqueMeds`’i günceller.
- `getMedLogForDay(medName, dayStr)` – belirli bir gün ve ilaç için log’ları döndürür.
- `toggleMed(medName)`, `clearMedSelection()`, `toggleGroup(groupName)`, `isGroupActive(groupName)` – ilaç seçimleri.
- `toggleAnimation()`, `stopAnimation()` – animasyon kontrolü (global `window.startAnimation` / `endAnimation`).
- `renderMainCharts()`, `renderFocusChart()`, `renderLabTrendCharts()` – Chart.js grafiklerini çizer.
- `destroyAllCharts()` – tüm chart instance’larını yok eder.
- `selectLabSession(id)`, `selectReport(protocolNo)` – detay seçimi.
- `getHospitalName(id)`, `getMedicationName(id)`, `getMedicationUnit(id)`, `getMedicationUnitByName(name)`, `getMedicationUnitOnlyByName(name)` – yardımcılar.
- `formatTurkishDate`, `formatFullDate`, `getBPStatusText`, `getBPBadgeClass`, `getLabItemStatus`, `getLabItemClass`, `getLabPointerClass`, `getRangeZoneStyle`, `getPointerPositionStyle`, `calculateIndividualWeightDiff`, `getWeightDiffClass` – UI yardımcıları.
- `getDailyEvents(dateStr)` – takvim için günün olaylarını toplar.
- `generateDynamicInsight(startDate, endDate)` – yapay zeka benzeri klinik yorum metni oluşturur (detaylı analiz).
- `downloadRawMedicalData(mode)` – tüm veriyi veya seçili dönemi JSON olarak indirir.
- `refreshApp()` – service worker cache temizleme + verileri yeniden yükler.
- Yaşam döngüsü watcher’ları: `$watch('sections', ...)` ile bölüm görünür olduğunda içeriği yükler.

**Global Animasyon Fonksiyonları (window seviyesinde):**

- `window.endAnimation(isPaused)`: interval temizler, animasyon durumunu günceller.
- `window.runTimelineStep()`: `endDate` bir gün ilerletir, filtreleri günceller.
- `window.startAnimation(customStart, customEnd, isResume)`: animasyonu başlatır (interval).
- `window.updateAnimationSpeed()`: hız değiştiğinde interval yeniden oluşturur.

#### 2.3.3. Service Worker Kaydı

`app.js` içinde `'serviceWorker' in navigator` kontrolü ile `sw.js` kaydedilir.

### 2.4. JavaScript: `input.js`

- Import Alpine, collapse plugin, Chart, date-fns adapter.
- `window.Alpine = Alpine; window.Chart = Chart;`
- Alpine.plugin(collapse);
- Dinamik import ile `app.js`’den `registerDashboard` fonksiyonunu alıp Alpine’a kaydeder.
- `Alpine.start();`

### 2.5. Service Worker: `sw.template.js` ve `bump-sw.js`

- `sw.template.js` bir şablondur; `{{CACHE_VERSION}}` placeholder’ı içerir.
- `bump-sw.js` çalıştırıldığında timestamp (`medilog_YYYY-MM-DD_HH-MM-SS`) oluşturur ve placeholder’ı değiştirerek `sw.js` dosyasını oluşturur.
- `sw.js` – statik dosyaları, ikonları ve JSON verilerini cache’ler. Data dosyaları için background update yapar.
- `install` ve `activate` event’leri ile eski cache’leri temizler.
- `fetch` event’i – önce cache’ten döner, network’e fallback yapar.
- `message` event – `CLEAR_CACHE` mesajı alırsa tüm cache’leri siler (refresh için).

### 2.6. Build ve Bağımlılıklar: `package.json`

Scripts:

- `build`: `bump` → `build:css` → `build:js`
- `build:css`: `tailwindcss -i ./input.css -o dist/output.css --minify`
- `build:js`: `esbuild input.js --bundle --outfile=dist/output.js --minify --format=esm`
- `bump`: `node bump-sw.js`
- `dev`: concurrently CSS ve JS watch
- `dev:serve`: concurrently watch + Python http.server 3333
- `ready`: `npm install && npm run build && npm run format`
- `serve`: `npm run bump && npm install && npm run build && npm run format && npm run dev:serve`
- **Test**: `npm test` – `node --test tests/*.test.js`

Bağımlılıklar:

- `alpinejs`, `@alpinejs/collapse` – frontend
- `chart.js`, `chartjs-adapter-date-fns` – grafik
- `date-fns` – tarih işlemleri
- `@tailwindcss/cli`, `tailwindcss` – CSS derleme
- `esbuild` – JS bundle
- `concurrently` – paralel çalıştırma
- `prettier`, `prettier-plugin-tailwindcss` – kod formatlama

### 2.7. Veri Dosyaları (JSON)

Tüm veriler `user_id=1` (örnek hasta) içindir. **Zero hard-coding** prensibi gereği, kod içinde hiçbir hasta adı veya ID sabitlenmemiştir; veriler dinamik olarak okunur.

#### `users.json`

Kullanıcı bilgileri: `id`, `name`, `gender`, `dob`, `birth_place`, `home`, `phone`, `email`, `insurance`, `height_cm`.
target_bp_sys_max

#### `hospitals.json`

`id`, `name`.

#### `clinical_context.json`

Hastanın klinik özeti, cerrahi detaylar, acil sevk zinciri, zaman çizelgesi. İçerir:

- `surgery_type`, `valve_type`, `target_bp_sys_max`, `target_bp_sys_min`, `target_bp_dia_max`, `target_bp_dia_min`
- `patient_summary` – uzun metin özet
- `anatomical_surgical_modifications` – yapılan cerrahi işlemler
- `clinical_timeline` – olay listesi (tarih, tip, hastane, açıklama). Buradaki `"Yatış"` ve `"Taburcu"` olayları, ilaç uyumu hesaplamasında dinamik olarak hospital exclusion aralıklarını belirlemek için kullanılır.
- `emergency_referral_pathway` – acil sevk basamakları

#### `medications.json`

İlaç tanımları: `id`, `name`, `type`, `form`, `unit`, `base_dose`, `is_emergency`, `color`.

**Güncel ilaç envanteri (18 adet):**

- Evde idame: Panto (ID 11), Dilatrend (5), Warfmadin (14), Apikobal (1), EcopirinPro (6), BelocZOK (2), Cordarone (4), Kapril (8)
- Dönemsel tedaviler: Tavanic (13), Cipro (3), Stafine (12), Levopront (9), Mikostatin (10), GeralginePlus (7), Augmentin (15)
- Yatarak tedavi (hastane sürecinde kullanılan): **Coraspin (16)**, **Oksapar (17)**, **Sulcid (18)**

#### `medication_changes.json`

İlaç değişimleri: `medication_id`, `at`, `type` (Started, Changed, Paused, Resumed, Ended, Taken), `amount`, `timespan` (saat), `reason`.

**Önemli güncelleme:** 30-31 Mart 2026 yatış dönemi için `Paused` ve `Resumed` kayıtları eksiksiz tamamlanmış, tüm kayıtların `reason` (gerekçe) alanları klinik olaylarla tam uyumlu hale getirilmiştir.

#### `medication_logs.json`

Günlük alım logları: `at`, `med`, `dose`.

#### `pressures.json`

Kan basıncı: `at`, `sys`, `dia`.

#### `weights.json`

Kilo: `at`, `weight`.

#### `tests.json`

Tahlil seansları: `id`, `at`, `hospital_id`, `title`, `description`.

#### `test_items.json`

Tahlil parametreleri: `test_id`, `code`, `name`, `result`, `unit`, `reference_min`, `reference_max`, `description`.

#### `reports.json`

Raporlar: `at`, `hospital_id`, `report_type`, `title`, `protocol_no`, `clinical_details`, `radiology_findings`, `conclusions`, `implants`, `doctor_name`, `doctor_title`, `doctor_reg_no`.

#### Boş dosyalar (temperatures, glucose, pulse, saturation, sleep, symptoms, appointments)

Bu dosyalar şu anda boş JSON dizisi (`[]`) içermektedir. Projede **yapısal şablon** olarak yer alırlar; ileride bu veri türleri eklendiğinde aynı formatta doldurulmaya hazırdırlar. `symptoms.json` ve `appointments.json` dosyaları, ilaç takibi ve klinik zaman çizelgesi ile entegre çalışacak şekilde tasarlanmıştır (örneğin randevu hatırlatmaları veya semptom günlüğü).

---

## 3. UI Bölümleri ve İşlevleri

### 3.1. Sidebar

- **Logo**: "Klinik Takip"
- **Tarih Filtresi**: Preset dropdown (`all`, `3`, `7`, ... `custom`), önceki/sonraki butonları, başlangıç/bitiş input’ları.
- **Navigasyon**: Her bölüm için link (scroll yapar) ve toggle switch (gizle/göster). Ayrıca "Tümünü Göster/Gizle" butonu.
- **Yenile Butonu**: Verileri yeniden yükler (service worker cache temizleme ile).
- **Animasyon Kontrolleri**:
    - Kapsam (Tümü / Dönem)
    - Hız kaydırıcı (x1/2, x1, x2, x4, x8)
    - Oynat/Duraklat/Durdur butonları
- **Veri İndirme**: "Tümünü İndir" ve "Dönemi İndir" butonları.
- **Versiyon**: v1.1
- Daraltılmış modda sadece ikonlar gösterilir.

### 3.2. Bölüm 1: Özet & Metrikler (`#summary`)

8 kart:

- Haftalık Tansiyon (son 7 gün ortalaması, önceki hafta ile karşılaştırma)
- Son Kilo (en son ölçüm, önceki ölçüm, tarih)
- Son INR (en son INR değeri, önceki ile karşılaştırma)
- Son HGB (en son hemoglobin, önceki ile karşılaştırma)
- Ortalama Tansiyon (seçili dönem ortalaması, önceki dönem ile karşılaştırma)
- Kilo Değişimi (dönem başı-sonu farkı)
- İlaç Uyumu (% olarak, progress bar)
- Anormal Tahliller (referans dışı parametre sayısı ve liste)

Tüm metrikler `calculateMetrics()` ile güncellenir.

### 3.3. Bölüm 2: Tansiyon & Kilo Grafikleri (`#charts`)

- Tansiyon grafiği (Line chart) – `bpViewMode` ile anlık veri veya 7 günlük hareketli ortalama (trend) gösterimi.
- Ağırlık grafiği (Line chart)
- Her iki grafiğin altında tablolar (son 10 veya tümü) ile detay listesi.

Grafikler `renderMainCharts()` ile çizilir.

### 3.4. Bölüm 3: Zaman Akışı & Reçeteler (`#prescriptions`)

- **İlaç Filtresi**: Grup butonları (Kan Sulandırıcılar, Tansiyon & Kalp, vb.) ve ilaç isim butonları.
- **Sadece Güncel** switch – sadece aktif ilaçları göster.
- **İlaç Zaman Akışı Grafiği**: Her ilaç için yatay çubuk segmentleri (başlangıç-bitış). Fareyle üzerine gelince tooltip.
- **Tedavi Kronolojisi**: Olay listesi (başlangıç, bitiş, doz değişimi, vb.) tarih sırasıyla.
- **Sağ Panel**: Aktif ve pasif ilaç listeleri (doz bilgileriyle).

Veriler `medicationChanges` ve `medicationLogs`’tan türetilir.

### 3.5. Bölüm 4: İlaç Matrisi (`#flowsheet`)

- **Grid Modu**: Tablo – satırlar ilaç, sütunlar günler (son 14 gün). Hücrelerde o gün alınan toplam doz (tablet sayısı) gösterilir. Hücreye tıklayınca tooltip’te saatler ve dozlar.
- **Grafik Karşılaştır Modu**: Seçili ilaçların günlük dozlarını bar chart olarak gösterir. İlaç seçimi yapılabilir.

`setupFlowsheet()` verileri hazırlar, `renderFocusChart()` grafiği çizer.

### 3.6. Bölüm 5: İnteraktif Takvim (`#calendar`)

- Aylık takvim görünümü (Pazartesi’den başlar). Her gün hücresinde o güne ait olay sayısını küçük noktalarla gösterir (renkler türe göre).
- Tıklanan günün detayları sağ panelde listelenir (tansiyon, ilaç, kilo, tahlil, rapor, ilaç değişimi). **Sadece İlaçlar** switch’i ile filtreleme.
- Önceki/sonraki işlem günü butonları.

Veriler `medicationLogs`, `pressures`, `weights`, `tests`, `reports`, `medicationChanges` birleştirilerek `getDailyEvents()` ile elde edilir.

### 3.7. Bölüm 6: Tahlil Trendleri (`#lab-trends`)

- Her bir laboratuvar parametresi için ayrı mini grafik (INR, PT, aPTT, HGB, HCT, RBC, PLT, WBC, CRP, Lenfosit, NEU, CREA, BUN, ALT, GLU, Sodyum, Potasyum, Kalsiyum). Grafikte referans aralığı şerit olarak gösterilir, nokta ile mevcut değer işaretlenir.

`renderLabTrendCharts()` ile çizilir.

### 3.8. Bölüm 7: Tetkik & Bulgular (`#lab-findings`)

- Sol tarafta tahlil seansları listesi (tarihe göre sıralı). Filtreler: Sadece Sınır Dışı, Gizle: AKG & Crossmatch.
- Sağ tarafta seçili tahlilin parametreleri tablosu (parametre, değer, birim, referans aralığı, durum). Durum renkli badge ile gösterilir.

`filteredTests` ve `selectedTestItems` kullanılır.

### 3.9. Bölüm 8: Raporlar (`#reports`)

- Sol tarafta rapor listesi (tarihe göre sıralı).
- Sağ tarafta seçili raporun detayları: başlık, tip, doktor bilgisi, klinik bilgiler, radyoloji bulguları, sonuçlar, implantlar, vb.

`reports` verisi kullanılır.

### 3.10. Bölüm 9: Klinik Analiz (`#clinical-report`)

- `generateDynamicInsight(startDate, endDate)` ile oluşturulan uzun metinli analiz raporu. Tansiyon, kilo, laboratuvar, ilaç uyumu ve acil durum ilaç kullanımlarını yorumlar. Metin HTML olarak döndürülür ve `x-html` ile gösterilir.

---

## 4. Veri Akışı ve Önemli Mantık

### 4.1. Tarih Filtreleme

- Tüm veriler `at` alanına göre filtrelenir (tarih kısmı `YYYY-MM-DD`).
- `startDate` ve `endDate` reaktif değişkenlerdir.
- `updateFilters()` debounce ile çağrılır ve ilgili bölümler yeniden yüklenir.
- `snapDateToValid()` geçerli veri tarihlerine en yakın olanı seçer (input’lara girilen tarihleri düzeltmek için).

### 4.2. İlaç Uyumu Hesaplaması (Dinamik Hospital Exclusion & Multi-Day Rolling)

`calculateMetrics()` içinde yapılır.

**Algoritma Özeti:**

1. `clinical_context.json` içindeki `clinical_timeline` taranarak `"Yatış"` ve `"Taburcu"` olayları dinamik olarak tespit edilir. Her bir yatış aralığı (`{start, end}`) kaydedilir.
2. İlaç uyumu hesaplanırken, her ilaç ve her gün için:
    - `medicationChanges` geçmişinden o gün geçerli doz ve sıklık (`timespan`) belirlenir.
    - Günlük ilaçlarda (`timespan <= 24`): Beklenen günlük doz ile `medicationLogs` kayıtları karşılaştırılır.
    - Haftalık ilaçlarda (`timespan = 168`, örn. Warfmadin): 7 günlük kayan pencere içindeki toplam alım mg miktarı, haftalık reçete hedefiyle karşılaştırılır. Eğer hasta yatışta ise o günler %100 uyum kredisi alır.
    - **Eğer gün yatış aralığına denk geliyorsa**, `actual = expected` kabul edilir (%100 uyum kredisi). Bu, hastane ortamında ilaçların hemşire tarafından düzenli verildiğini varsayar.
    - Yatışın son günü (taburcu günü) özel olarak işlenir: evde alınması gereken doz ile hastane dozu ayrıştırılır.
3. **N-Günlük Uyum Oranları (3, 7, 10 Günlük):**  
   Hedef gün dahil geçmiş N günün günlük uyum yüzdelerinin basit aritmetik ortalaması alınarak hesaplanır:

    $$\text{Uyum}_N(\text{hedefGün}) = \frac{1}{N} \sum_{k=0}^{N-1} \text{GünlükUyum}(\text{hedefGün} - k \text{ gün})$$

    Bu formül, 3, 7 ve 10 günlük uyum kartlarında (dashboard’da gösterilen) kullanılır.

4. Toplam başarılı, fazla ve eksik doz birimleri hesaplanır; genel uyum yüzdesi (`adherenceRate`) bulunur.

**Not:** Bu algoritma, 30-31 Mart 2026 ve 23-28 Temmuz 2026 yatış dönemlerini doğru şekilde kapsar. `medication_changes.json` içindeki `Paused` ve `Resumed` kayıtları bu dönemlerle uyumlu hale getirilmiş ve tüm kayıtlara `reason` alanı eklenmiştir.

### 4.3. Anormal Tahliller

- En son tahlil seansı (`endDate`’e göre) baz alınır.
- `getLabItemStatus()` ile her parametrenin referans aralığına göre durumu belirlenir.
- Sınır dışı olanlar `outOfBoundsList`’e eklenir.

### 4.4. İlaç Zaman Akışı (Segmentler)

- `detailedMeds` her ilaç için `medicationChanges`’ten başlangıç, bitiş, duraklama, devam etme olaylarına göre segmentler oluşturur.
- `visibleMeds` bu segmentleri seçili filtre ve aktiflik durumuna göre filtreler ve yüzde konumları hesaplar (görsel çubuk grafik).

### 4.5. Animasyon

- `startAnimation()` `endDate`’i adım adım ilerletir (`runTimelineStep`).
- Her adımda `updateFilters()` çağrılır, böylece tüm grafikler ve metrikler güncellenir.
- Hız ayarı interval süresini değiştirir.
- Kapsam "Tümü" ise başlangıç `firstD`’den, "Dönem" ise mevcut `startDate`’den başlar.

### 4.6. Veri İndirme

- `downloadRawMedicalData(mode)` tüm verileri veya seçili dönemi JSON olarak dışa aktarır.
- İçinde `clinical_insights` bölümünde, seçili dönem ve tüm zamanlar için `generateDynamicInsight` çıktıları da bulunur.
- Dosya adı `timestamp_hastaAdi_all-data/period_... .json` şeklinde oluşturulur.

### 4.7. Service Worker ve Refresh

- `refreshApp()` çalıştırıldığında service worker’a `CLEAR_CACHE` mesajı gönderilir, ardından tüm veriler cache-bust (timestamp query) ile yeniden yüklenir.
- Cache temizleme başarısız olursa doğrudan fetch yapılır.

---

## 5. Test Kapsamı (`app.test.js`)

- `test` ve `assert` kullanılarak unit testler yazılmıştır.
- Test edilen fonksiyonlar:
    - `getBPStatusText` – tansiyon kategorisi
    - `getBPBadgeClass` – badge CSS sınıfı
    - `getLabItemStatus` – laboratuvar parametre durumu (Normal/Düşük/Yüksek)
    - `formatTurkishDate` – tarih formatlama
    - `formatFullDate` – uzun tarih formatı
    - `debounce` – debounce davranışı (`this` context, argümanlar, gecikme)

Testler `npm test` ile çalıştırılabilir (package.json’da `test` betiği tanımlıdır).

---

## 6. Önemli Notlar ve Güncelleme Geçmişi

### 6.1. Genel Notlar

- Tüm tarihler `YYYY-MM-DD` formatındadır, `at` alanı `YYYY-MM-DD HH:MM` şeklindedir.
- `medicationChanges`’de `timespan` saat cinsindendir (24, 12, 8, 168 = haftalık, 72 = 3 günde bir).
- `medication_logs`’daki `dose` ilacın `base_dose` birimindedir. Tablet sayısı `dose / base_dose` ile hesaplanır.
- Renk eşleştirmeleri `medColors` ve `medConfig` nesnelerinde tanımlıdır.
- `clinical_context.json` doğrudan `users.json` içinde de olabilir, uygulama her iki durumu da destekler (önce `clinical_context.json` yükler, yoksa `user.clinical_context` kullanır).
- `temperatures.json`, `glucose.json` vb. boş dosyalar ileride kullanılmak üzere yapısal şablonlardır.

### 6.2. Güncelleme Notları (v1.2 – Temmuz 2026)

1. **Dynamic Hospital Exclusion Algorithm**  
   İlaç uyum oranı hesaplamasında hastane yatış günleri (`clinical_timeline` verisinden dinamik olarak tespit edilerek) %100 uyum kredisi ile hesaplanmaktadır. Bu sayede hastane ortamında hemşire tarafından verilen ilaçların uyuma etkisi doğru şekilde modellenmiştir.

2. **Haftalık İlaç (Warfmadin) Doz Hesaplama**  
   `timespan = 168` olan ilaçlar (örn. Warfmadin) için 7 günlük kayan pencere içinde alınan toplam mg miktarı, reçete edilen haftalık toplam mg ile karşılaştırılır. Bu, haftalık dozajın doğru şekilde değerlendirilmesini sağlar.

3. **N-Günlük Kayan Ortalama Uyum Formülü**  
   3, 7 ve 10 günlük uyum oranları, hedef gün dahil geçmiş N günün günlük uyum yüzdelerinin basit aritmetik ortalaması olarak hesaplanır:

    $$\text{Uyum}_N(\text{hedefGün}) = \frac{1}{N} \sum_{k=0}^{N-1} \text{GünlükUyum}(\text{hedefGün} - k \text{ gün})$$

4. **Zero Hard-Coding**  
   `app.js` ve `panel.html` içerisindeki tüm hasta/tarih bağımlılıkları kaldırılmış, tamamen `data/*.json` kaynaklı dinamik mimariye geçilmiştir. Herhangi bir hasta verisi yüklendiğinde dashboard otomatik olarak doğru sonuçları üretmektedir.

5. **Yatarak Tedavi İlaçları**  
   `medications.json` envanterine hastane sürecinde uygulanan Coraspin (ID: 16), Oksapar (ID: 17) ve Sulcid (ID: 18) enjeksiyon/yatarak tedavi ilaçları eklenmiştir. Bu ilaçlar, hastane yatış dönemlerinde `Paused`/`Resumed` mekanizması ile yönetilmektedir.

6. **Test Runner**  
   `package.json` içine `npm test` betiği eklenmiştir (`node --test tests/*.test.js`). Böylece unit testler tek komutla çalıştırılabilir.

7. **Boş Dosyaların Amaçları**  
   `temperatures.json`, `glucose.json`, `pulse.json`, `saturation.json`, `sleep.json`, `symptoms.json`, `appointments.json` dosyaları, ileride eklenecek veri türleri için yapısal JSON şablonları olarak projede tutulmaktadır. `symptoms.json` ve `appointments.json` özellikle ilaç takibi ve klinik zaman çizelgesi ile entegre çalışacak şekilde tasarlanmıştır.

---

## 7. Derleme ve Çalıştırma

1. Bağımlılıkları yükleyin: `npm install`
2. Geliştirme modunda çalıştırın: `npm run serve` (CSS/JS watch + Python HTTP sunucusu 3333 portunda)
3. Üretim build’i: `npm run build` (bump, CSS, JS)
4. Uygulama `http://localhost:3333/panel.html` adresinden erişilebilir.
5. Testleri çalıştırın: `npm test`

---

## 8. Özet

Bu proje, karmaşık bir klinik veri setini görselleştiren, filtreleyen ve analiz eden zengin bir dashboard’dur. Alpine.js reaktivitesi, Chart.js grafikleri, Tailwind CSS ile hızlı bir şekilde geliştirilmiş ve PWA yetenekleri kazanmıştır. Tüm veri akışı, tarih filtreleme, metrik hesaplamalar, animasyon ve dışa aktarma özellikleri kapsamlı bir şekilde ele alınmıştır. **Zero hard-coding** ve **dinamik hospital exclusion** prensipleri ile gerçek dünya klinik verilerine uygun, esnek ve sürdürülebilir bir yapı hedeflenmiştir. Bu doküman, projeyi sıfırdan yeniden oluşturmak için gereken tüm bilgileri içermektedir.
