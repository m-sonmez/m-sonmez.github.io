# QTP Geliştirici Rehberi

Bu rehber `qtp/` alt ağacının dosya yapısını, ortak işlem kayıt defterini, tam CRUD akışını, canlı dosya izleyici mimarisini ve çapraz-platform kalite kapılarını açıklar.

---

## 1. Mimari Genel Bakış, Mod Adaptörleri ve İşlem Kayıt Defteri

### Dizin Yapısı (`qtp/`)
- **Kök (Yayın & PWA Katmanı):** `index.html` (Klasik QuickTextPaste PWA), `qtp.html` & `theme.css` (`standalone/qtp_app/web/` ile bayt-birebir eşit Birleşik Web UI), `sw.js`, `manifest.webmanifest`, `data.json`, `QuickTextPaste.ini`, `icon*.{png,svg}`, `qtp.exe`, `qtp.bin`, `docs/*.md`.
- **`qtp/legacy/`:** Klasik PWA betikleri ve eski Windows otomasyonu (`cevaplar.html`, `qtp_core.py`, `qtp_manager.py`, `qtp_server.py`, `baslat.bat`, `baslat.sh`, `kurulum.ps1`, `QuickTextPaste_x64_p.exe`, `tests/test_qtp.py`). `qtp/standalone/qtp_app/**` içinden bu modüllere **sıfır çalışma zamanı bağımlılığı** vardır.
- **`qtp/standalone/`:** Bağımsız QTP masaüstü/CLI/TUI/Web uygulaması (`qtp_app/`) ve `pytest` test takımı (`qtp_app/tests/`).

### İşlem Kayıt Defteri ve Yeni İşlem Ekleme
QTP'de tek doğruluk kaynağı [operations.py](../standalone/qtp_app/core/operations.py) (`OPERATIONS`) ve [engine.py](../standalone/qtp_app/core/engine.py) (`QtpEngine`) ikilisidir:
- Dört adaptör aynı çekirdek katmanına bağlanır:
  - CLI (`qtp_app/cli.py`)
  - TUI (`qtp_app/tui/app.py`, `qtp_app/tui/_win_console.py`)
  - Web (`qtp_app/web.py` + `qtp_app/web/qtp.html`)
  - GUI (`qtp_app/main.py` + `qtp_app/ui/{overlay,settings_window,help_dialog,icons}.py`)
- Her yeni işlem (`op_id`, örneğin `add_item`, `bulk_edit`, `rename_group`, `undo`):
  1. `OPERATIONS` içine (`cli_flag`, `tui_key`, `web_route`, `gui_binding`, `error_msgs_tr`, `exit_codes`) ile eklenir (v2.3.1 ile toplam 35 kanonsal işlem).
  2. `QtpEngine` üzerinde `op_<ad>` metodu ve gerekirse `_persist_items_change()` gibi atomik INI+JSON kalıcılık adımı yazılır (UTF-16 LE BOM + otomatik `.bak` yedek + 30 adımlı `_undo_stack`/`_redo_stack`).
  3. CLI bayrağı (`cli.py`), HTTP rotası (`web.py`), TUI tuşu/komutu (`tui/app.py`) ve GUI eylemi (`ui/overlay.py`) bağlanır.
  4. Birebir hata mesajları [SSS.md](SSS.md) içine, parite satırı ise [KULLANIM.md](KULLANIM.md#12-modlar-arası-eşitlik-matrisi) tablosuna eklenir.

---

## 2. Esnek Kısayol Modeli ve Dinamik Özel Yuvalar

- Tüm kısayol ayrıştırma, normalleştirme (`Ctrl+Alt+Shift+Win` sırası), 6 hazır profil, 15 değiştirici kümesi, Türkçe-Q `AltGr` tespiti ve OS rezerve kısayol kontrolleri `qtp_app/core/hotkeys.py` içindedir.
- Windows üzerinde `ctypes` + `user32.dll` (`RegisterHotKey` / `UnregisterHotKey`) 64-bit güvenli `argtypes`/`restype` imzalarıyla çağrılır.
- `QtpEngine.op_set_setting`, `hotkeys.<özel_ad>` anahtarlarını kabul ederek hem varsayılan `all`, `A`, `Z`, `X`, `Q` hem de dinamik kullanıcı yuvalarını canlı kaydeder ve çakışma denetiminden geçirir.

---

## 3. Canlı Dosya İzleyici (`core/watcher.py`) ve Web/PWA Çift Modu

- `ConfigFileWatcher` (`mtime_ns + size` yoklaması + `debounce_ms` yumuşatma) `qtp_settings.json` ile etkin veri dosyasını (`QuickTextPaste.ini` veya `data.json`) izler; dışarıdan bozuk kayıt geldiğinde son geçerli bellek durumunu korur ve `SSS.md` uyarı mesajlarını `qtp.log`'a yazar.
- `qtp/standalone/qtp_app/web/qtp.html` (ve kökteki kopyası `qtp/qtp.html`), açılışta `GET /api/revision` sorgusu başarısız olursa otomatik olarak **Statik GitHub Pages** moduna geçer: `data.json`, `QuickTextPaste.ini` ve `docs/*.md` varlıklarını göreceli yollardan okur, kullanıcı CRUD işlemlerini ise tarayıcı `localStorage` hafızasında saklar.

---

## 4. Testler, Kapsam, Derleme ve CI Süreçleri

- **Sıfır Harici Bağımlılık & Yorum Kuralı:** `qtp_app/**` içindeki `.py`, `.html`, `.css` dosyalarında ve `qtp/qtp.html` / `qtp/theme.css` üzerinde gereksiz yorum (`#`, `//`, `/* */`, `<!-- -->`) bulunmamalıdır (`test_no_unnecessary_comments`).
- **Python 3.8 Sözdizimi & Başsız Güvenlik:** `qtp_app/core/`, `qtp_app/tui/`, `qtp_app/cli.py`, `qtp_app/web.py`, `qtp_app/ui/search.py` modülleri Python 3.8 uyumlu yazılır ve `PyQt6` içe aktarmaz.
- **Test Komutları:**
  ```powershell
  # Bağımsız testler & %90+ kapsama kapısı (qtp/standalone/ içinden)
  $env:QT_QPA_PLATFORM = "offscreen"
  .venv\Scripts\python.exe -m pytest -q --cov=qtp_app.core --cov=qtp_app.ui.search --cov=qtp_app.tui --cov=qtp_app.web --cov=qtp_app.cli --cov-report=term-missing --cov-fail-under=90

  # Klasik / Legacy test takımı (qtp/ içinden)
  standalone\.venv\Scripts\python.exe -m unittest discover -s legacy/tests -v
  ```
- **Otomatik Linux `qtp.bin` CI & Çapraz Dağıtım Politikası:** `.github/workflows/qtp-publish-linux.yml`, `main` dalındaki `qtp/**` (`!qtp/qtp.bin`) değişikliklerinde Ubuntu 22.04 üzerinde `xvfb-run` altında tüm testleri geçirip ELF `qtp/qtp.bin` çıktısını yayımlar; `build/qtp.spec` üzerinde konak yapılandırmasına bağlı `libfontconfig`/`libxkbcommon`/`Mesa`/`Wayland`/`X11` kitaplıkları dışlanarak Arch/CachyOS/Fedora/Ubuntu/openSUSE arasında uyumluluk korunur.
