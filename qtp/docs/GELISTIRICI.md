# QTP Geliştirici Rehberi

Bu belge, QTP v2.1.0 tek dosya masaüstü uygulamasının mimarisini, kısayol alt sistemini, canlı dosya izleyiciyi, test altyapısını ve derleme sürecini açıklar.

---

## 1. Mimari Genel Bakış, Mod Adaptörleri ve İşlem Kayıt Defteri

QTP, tüm iş mantığını Qt'den bağımsız [engine.py](../qtp_app/core/engine.py) ve tek doğruluk kaynağı olan [operations.py](../qtp_app/core/operations.py) içinde toplar (`--gui`, `--tui`, `--cli`, `--web`).

```text
qtp_app/
├── __init__.py               # Sürüm, derleme tarihi ve uygulama adı
├── cli.py                    # Ata-PID AttachConsole, -v/-q, --completion ve argparse
├── main.py                   # GUI adaptörü (Overlay + Tray + Kısayollar + Canlı Yenileme + qtp.lock)
├── web.py & web/             # 127.0.0.1 stdlib HTTP sunucusu + çevrimdışı UI + /api/revision
├── tui/                      # curses + Windows ANSI/Win32 API (_win_console.py) terminal arayüzü
├── core/
│   ├── engine.py             # UI-bağımsız tek motor (QtpEngine, canlı izleyici eşgüdümü)
│   ├── operations.py         # Kanonsal OperationSpec kayıt defteri (22 işlem)
│   ├── watcher.py            # Sıfır bağımlılıklı ConfigFileWatcher (debounce + self-write bastırma)
│   ├── hotkeys.py            # Win32 RegisterHotKey + pynput, 15 değiştirici bileşimi, çakışma algılama
│   ├── settings.py           # qtp_settings.json (auto_reload, özel yuvalar, güvenli v2.0->v2.1 göçü)
│   ├── ini_parser.py         # Çoklu kodlama algılama ve kayıpsız INI ayrıştırıcı
│   ├── json_store.py         # data.json, INI<->JSON dönüşümü, backups/, prefer_source desteği
│   ├── paster.py             # Sıfır dış bağımlılıklı pano ve tuş simülasyonu
│   ├── logging_setup.py      # Dönen günlük kurulumu (qtp.log, 1 MB x 3)
│   └── EXTERNAL_CALLS.md     # Harici çağrı denetim raporu
├── ui/                       # Overlay, Theme, Search, Tray, HotkeyRow/HotkeyEdit, SettingsWindow, HelpDialog
├── assets/                   # İkonlar, gömülü Inter TTF yazı tipleri ve defaults/
├── build/                    # PyInstaller qtp.spec / qtp_win7.spec + Windows/Unix derleme betikleri
└── tests/                    # Birim, eşleme, taşınabilirlik, UI, izleyici ve altın anlık görüntü testleri
```

### Yeni Bir İşlemi Dört Moda Birden Ekleme
1. `qtp_app/core/operations.py` içindeki `OPERATIONS` listesine `OperationSpec` ekleyin.
2. `qtp_app/core/engine.py` içinde `op_<id>()` yöntemini yazın.
3. `cli.py`, `tui/app.py`, `web.py`, `main.py` ve `test_mode_parity.py` içine bağlayın.
4. Tüm hata mesajlarını `docs/SSS.md` içine ve işlemi `docs/KULLANIM.md` matrisine ekleyin.

---

## 2. Esnek Kısayol Modeli ve Dinamik Özel Yuvalar

- **Ayrıştırıcı (`hotkeys.py`):** `parse_hotkey()` / `normalize_hotkey()` her sıradaki değiştiricileri kanonsal `("Win", "Ctrl", "Alt", "Shift")` sırasına ve büyük harfli tetik tuşuna (`A–Z`, `0–9`, `F1–F24`, `Space`, vb.) çevirir. `apply_modifier_combo()` tüm yuvaların değiştiricilerini korunan tetik tuşlarıyla toplu değiştirir.
- **Win32 `RegisterHotKey`:** `ctypes` üzerinden 64-bit güvenli `argtypes`/`restype` ile `WM_HOTKEY` döngüsü işletir; `ERROR_HOTKEY_ALREADY_REGISTERED (1409)` durumunda `self.conflicts` sözlüğüne Türkçe uyarı yazar ve `WM_QUIT` ile sızıntısız kapanır.
- **Özel Yuvalar:** `settings.py` hem yerleşik (`all`, `A`, `Z`, `X`, `Q`) hem de kullanıcı tanımlı (`hotkeys.W`, `hotkeys.1` vb.) yuvaları kabul eder (`SettingsWindow` üzerinde **+ Özel Kısayol Ekle**).

---

## 3. Canlı Dosya İzleyici (`core/watcher.py`)

`ConfigFileWatcher`, SHA-256 + `mtime_ns` + boyut parmak izleriyle `qtp_settings.json`, etkin `QuickTextPaste.ini` ve `data.json` dosyalarını izler (`auto_reload_interval_ms=500`, `debounce_ms=250`), atomik `os.replace()` yazımlarını kaçırmaz ve `mark_internal_write`/`suppress_write` ile kendi yazımlarını yankılamaz. Geçici yarı-yazılmış dosyalarda 2 × 150 ms yeniden dener; kalıcı bozuk dosyalarda önceki geçerli durumu koruyarak Türkçe uyarı kaydeder. Ephemeral CLI modlarında (`--selftest`, `--version`, `--completion`) kesinlikle başlatılmaz.

---

## 4. Testler, Kapsam ve Çapraz Platform Kuralları

```bash
QT_QPA_PLATFORM=offscreen .venv\Scripts\python.exe -m pytest -q --cov=qtp_app.core --cov=qtp_app.ui.search --cov=qtp_app.tui --cov=qtp_app.web --cov=qtp_app.cli --cov-report=term-missing --cov-fail-under=90
.venv\Scripts\python.exe -m unittest discover -s tests -v
cmd /c make.bat test
```

- `test_no_unnecessary_comments`: Tüm `.py`, `.spec`, `.html`, `.css`, `.yml`, `Makefile`, `make.bat`, `.gitignore` dosyalarında gereksiz yorum (`#`, `//`, `/* */`, `<!-- -->`) olmadığını denetler (ilk satır `#!` hariç).
- `test_portability.py`: `core/**`, `cli.py`, `tui/**`, `web.py` ve `ui/search.py` üzerinde Python 3.8+ sözdizimi ve sıfır `PyQt6` zorunluluğunu denetler.
- `test_platform_parity.py`: `ui/theme.py` ve `ui/overlay.py` üzerinde `sys.platform` görsel dallanma yasağını ve dokümantasyon/hata senkronunu denetler.
