# Değişiklik Günlüğü (CHANGELOG)

Tüm kayda değer QTP sürümleri bu dosyada Türkçe olarak belgelenir.

---

## [2.0.0] - 2026-11-23

### Eklenenler ve Büyük Yenilikler
- **Tek Dosya Bağımsız Masaüstü Uygulaması:** Windows için taşınabilir `qtp.exe` ve Linux/macOS için taşınabilir `qtp.bin` (`PyInstaller --onefile` + gömülü `Inter` yazı tipleri ve Türkçe yardım belgeleri).
- **`QuickTextPaste.exe` Bağımlılığı Kaldırıldı:** Global kısayollar (`Win+A`, `Win+Z`, `Win+X`, `Win+Q`, `Ctrl+Shift+Space`), pano kopyalama, önceki pencere odağını geri yükleme ve otomatik yapıştırma (`Ctrl+V` / `Cmd+V` / `wtype` / `ydotool` + `<E<N<D|` sonrası `Enter`) artık tamamen yerleşiktir.
- **Modern Katman (Overlay) Arayüzü (PyQt6):** `720×520` px çerçevesiz, yarı saydam, 180 ms yumuşak açılış/kapanış animasyonlu pencere; sanallaştırılmış `QListView` (527+ kayıt), kategori sekmeleri (`Tümü`, `A · İş Ortağı`, `Z · Kurye`, `X · Canlı Yardım`, `Q · Turkcell`), sağ tık menüsü, satır içi kopyala düğmesi ve 1,2 sn bildirim (toast).
- **Türkçe Yerel Ayar Uyumlu Bulanık Arama (`FuzzyMatcher`):** `İ/i`, `I/ı`, `Ş/ş`, `Ğ/ğ`, `Ç/ç`, `Ö/ö`, `Ü/ü` harf kurallarını koruyan deterministik alt-dizi puanlama ve eşleşme vurgulama.
- **Çapraz Platform UI/UX Eşitliği:** Windows, Linux ve macOS üzerinde birebir aynı renk paleti, yarıçaplar, boşluklar, yazı tipi boyutları, animasyon süreleri ve klavye kısayolları (`test_platform_parity.py` ile statik olarak doğrulanır).
- **Taşınabilir Ayarlar ve Dönen Günlük:** `qtp_settings.json` (salt-okunur klasörde işletim sistemi dizinine otomatik geri dönüş), `qtp.log` (1 MB × 3 rotasyon) ve `qtp.lock` tek örnek kilidi.
- **Kayıpsız INI ve JSON Motoru:** `UTF-16 LE BOM`, `UTF-16 BE BOM`, `UTF-8 BOM`, `UTF-8` ve `cp1254` otomatik kodlama algılama; `QuickTextPaste.ini` birebir gidiş-dönüş (round-trip) garantisi; `.bak` yedekleme; `qtp-tam-yedek-*.json` desteği.
- **Komut Satırı (CLI) ve Otomatik Doğrulama:** `--selftest`, `--version`, `--export-ini`, `--import-ini`, `--work-dir` ve `--help`.
- **Kapsamlı Türkçe Dokümantasyon ve Uygulama İçi Yardım (`F1`):** `docs/KURULUM.md`, `docs/KULLANIM.md`, `docs/KISAYOLLAR.md`, `docs/SSS.md`, `docs/GELISTIRICI.md` ve güncellenmiş `README.md`.
- **Kapsamlı Test Paketi:** `qtp_app/core/**` ve `qtp_app/ui/search.py` üzerinde ≥ %90 satır kapsamı (`pytest-cov` + `pytest-qt`).

---

## [1.x] - Önceki Sürümler
- Tarayıcı tabanlı çevrimdışı PWA (`index.html`, `cevaplar.html`, `sw.js`, `manifest.webmanifest`), yerel Python HTTP köprüsü (`qtp_server.py`) ve Tkinter masaüstü yöneticisi (`qtp_manager.py`).
