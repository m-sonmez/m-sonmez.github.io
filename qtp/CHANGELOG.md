# Değişiklik Günlüğü (CHANGELOG)

Tüm kayda değer QTP sürümleri bu dosyada Türkçe olarak belgelenir.

---

## [2.1.0] - 2026-11-23

### Mod Eşitliği ve Sıfır Bağımlılık Güncellemeleri
- **Dört Çalışma Modu Tek Çekirdekte Birleştirildi (`--gui`, `--tui`, `--cli`, `--web`):** Tüm modlar UI-bağımsız `core/engine.py` ve kanonsal 18 işlemli `core/operations.py` kayıt defteri üzerinden aynı özellik kümesini, çıkış kodlarını ve Türkçe hata/başarı mesajlarını sunar.
- **Yeni Terminal Arayüzü (`--tui`):** Linux/macOS'ta standart `curses`, Windows'ta harici paket gerektirmeyen gömülü `_win_console.py` ANSI/VT100 + `msvcrt` katmanı; GUI ile birebir arama/kategori/liste/kısayol yerleşimi.
- **Genişletilmiş Başsız CLI (`--cli`):** `--modes`, `--list-categories`, `--list-items`, `--search`, `--show-ini`, `--copy`, `--paste`, `--export-backup`, `--restore`, `--backup`, `--reload`, `--get`, `--set`, `--json` desteği ve Windows konsol (`AttachConsole`/`AllocConsole`) bağlantısı.
- **Yerel Çevrimdışı Web Sunucusu (`--web`):** Yalnızca `127.0.0.1` üzerinde çalışan `ThreadingHTTPServer`, `ui/theme.py` renkleriyle uyumlu harici bağlantısız HTML/CSS arayüz ve eksiksiz `/api/*` JSON uç noktaları.
- **Sıfır Çalışma Zamanı Bağımlılığı (`core/paster.py`, `core/hotkeys.py`):** `pyperclip`, `xclip`, `xsel`, `xdotool`, `wmctrl` kaldırıldı; Windows `ctypes` Win32 pano/odak, macOS `AppKit`/`osascript` ve Linux `libX11`/Qt/OSC-52 desteği getirildi. Wayland ve macOS Erişilebilirlik kısıtları başlangıcı bloklamadan zarif Türkçe uyarılarla ele alındı (`EXTERNAL_CALLS.md`).
- **Kapsamlı Eşitlik ve Taşınabilirlik Testleri + Çoklu OS CI Matrisi:** `test_mode_parity.py` (altın anlık görüntüler dahil), `test_portability.py` (temiz klasör, sıyrılmış `PATH`/`HOME`, yerel ayar matrisi, statik tarama), `test_web_ui.py`, `test_gui_offscreen_parity.py` ve `.github/workflows/ci.yml` temiz konteyner işleri eklendi.
- **Doğrulanan Yayın Metrikleri:** `89/89` `pytest` testi (**%93** satır kapsamı, tüm 7 hedef modül grubu ≥ %90), `12/12` `unittest` tam-yığın testi ve `36.31 MB` tek dosya `dist/qtp.exe` boş klasör doğrulamasından geçti.

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
