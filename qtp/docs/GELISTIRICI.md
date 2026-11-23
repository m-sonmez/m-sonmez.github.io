# QTP Geliştirici Rehberi

Bu belge, QTP v2.1.0 tek dosya masaüstü uygulamasının mimarisini, test altyapısını, çapraz platform UI/UX eşitlik denetimlerini ve derleme sürecini açıklar.

---

## 1. Mimari Genel Bakış, Mod Adaptörleri ve İşlem Kayıt Defteri

QTP v2.1.0, tüm iş mantığını Qt'den bağımsız [engine.py](../qtp_app/core/engine.py) ve tek doğruluk kaynağı olan [operations.py](../qtp_app/core/operations.py) içinde toplar. Dört çalışma modu (`--gui`, `--tui`, `--cli`, `--web`) aynı `QtpEngine` sınıfını kullanan ince adaptörlerdir.

```text
qtp_app/
├── __init__.py               # Sürüm (2.1.0), derleme tarihi ve uygulama adı
├── cli.py                    # Birleşik argparse (--mode gui|tui|cli|web) ve headless CLI alt komutları
├── main.py                   # GUI adaptörü (Overlay + Tray + Kısayollar + qtp.lock)
├── web.py & web/             # 127.0.0.1 stdlib HTTP sunucusu + çevrimdışı HTML/CSS/JSON API
├── tui/                      # curses + Windows ANSI/msvcrt (_win_console.py) terminal arayüzü
├── core/
│   ├── engine.py             # UI-bağımsız tek motor (QtpEngine & OperationResult)
│   ├── operations.py         # 18 kanonsal OperationSpec tanımı (tek doğruluk kaynağı)
│   ├── ini_parser.py         # Çoklu kodlama algılama ve kayıpsız INI ayrıştırıcı
│   ├── json_store.py         # data.json, INI<->JSON dönüşümü, backups/, qtp-tam-yedek-*.json
│   ├── hotkeys.py            # pynput.GlobalHotKeys + Wayland/macOS zarif geri dönüşü
│   ├── paster.py             # Sıfır dış bağımlılıklı Win32 ctypes / macOS AppKit / Linux X11-OSC52 pano
│   ├── settings.py           # qtp_settings.json (web.port dahil) ve taşınabilir yol çözümü
│   ├── logging_setup.py      # Dönen günlük kurulumu (qtp.log, 1 MB x 3)
│   └── EXTERNAL_CALLS.md     # Harici çağrı denetim raporu
├── ui/                       # PyQt6 Overlay, Theme, Search, Tray, SettingsWindow, HelpDialog
├── assets/                   # İkonlar, gömülü Inter TTF yazı tipleri ve defaults/
├── build/                    # PyInstaller onefile/windowed spec + Windows/Unix derleme betikleri
└── tests/                    # test_mode_parity, test_portability, test_web_ui, golden/ vb.
```

### Yeni Bir İşlemi Dört Moda Birden Ekleme
1. `qtp_app/core/operations.py` içindeki `OPERATIONS` listesine yeni `OperationSpec` kaydını ekleyin.
2. `qtp_app/core/engine.py` içinde ilgili `op_<id>()` yöntemini `OperationResult` döndürecek şekilde yazın.
3. İnce adaptörlere bağlayın: `cli.py` (bayrak), `tui/app.py` (`execute_operation`), `web.py` (`/api/...`), `main.py` (GUI menü/kısayol).
4. `test_mode_parity.py` yeni işlemi otomatik olarak tüm modlarda ve çıkış kodlarıyla test edecektir.

### Altın Anlık Görüntüleri (Golden Snapshots) Yenileme
TUI ve Web altın çıktıları `qtp_app/tests/golden/{tui,web}/<op_id>.txt` altında tutulur. Bilinçli görsel/çıktı güncellemesi sonrası yeniden üretmek için:
```bash
UPDATE_GOLDEN=1 pytest qtp_app/tests/test_mode_parity.py -q
```

> Not: Kök dizindeki `index.html`, `cevaplar.html`, `sw.js`, `manifest.webmanifest`, `qtp_core.py`, `qtp_server.py`, `qtp_manager.py` ve `tests/test_qtp.py` mevcut Web PWA / miras bileşenleri olarak korunmuştur.

---

## 2. Yeni Bir Kısayol Kategorisi Ekleme

Örneğin `W` (`L-Win+W`) için ayrı bir kategori sekmesi eklemek isterseniz şu dört noktayı güncelleyin:

1. **`qtp_app/core/settings.py`:** `DEFAULT_HOTKEYS` sözlüğüne `"W": "Win+W"` girdisini ekleyin.
2. **`qtp_app/core/hotkeys.py`:** `HOTKEY_CATEGORY_ORDER` demetine `"W"` ekleyin.
3. **`qtp_app/ui/theme.py`:** `CATEGORY_TABS` demetine `("W", "W · Başlık", "L-Win+W")` satırını ekleyin.
4. **`qtp_app/ui/settings_window.py`:** `hk_edits` döngüsüne `("W", "Kategori W (Başlık)")` ve `last_cat_cb` listesine `"W"` ekleyin.

---

## 3. Gelecek Diller İçin Yerelleştirme (i18n) Ekleme

`qtp_settings.json` içinde `language` alanı halihazırda ayrılmıştır (şu an `"tr"`):
- UI dizelerini `ui/theme.py` ve `ui/overlay.py` içinden bir sözlük kataloğuna (`STRINGS["tr"]`, `STRINGS["en"]`) taşıyın.
- `core/settings.py` içindeki `language` doğrulamasını yeni dil kodunu kabul edecek biçimde genişletin.
- `ui/help_dialog.py` içinde dil koduna göre `docs/<lang>/` klasöründen Markdown yükleyin.

---

## 4. Testleri ve Kapsam (Coverage) Kontrolünü Çalıştırma

Katman testi `qtp_app/core/**` ve `qtp_app/ui/search.py` üzerinde **en az %90 satır kapsamı** hedefler:

```bash
# Pytest + kapsam raporu
QT_QPA_PLATFORM=offscreen pytest -q --cov=qtp_app/core --cov=qtp_app/ui/search --cov-report=term-missing

# Eski tam yığın (PWA + qtp_core) testlerini de çalıştırma
python -m unittest discover -s tests -v
```

---

## 5. Statik Çapraz Platform Eşitlik Testi (`test_platform_parity.py`)

`qtp_app/tests/test_platform_parity.py`, `ui/theme.py` ve `ui/overlay.py` dosyalarını kaynak kod düzeyinde (AST / metin taraması) denetler:
- Renk, yarıçap, dolgu (padding), yazı tipi boyutu veya animasyon süresini `sys.platform` değerine göre değiştiren dallanma bulunmadığını doğrular.
- Tüm yazı tipi boyut sabitlerinin ve `FOOTER_HINTS_TEXT` dizesinin platformdan bağımsız tek bir kaynaktan geldiğini garanti eder.
- Yeni bir görsel sabit eklerken her zaman `qtp_app/ui/theme.py` içinde platformdan bağımsız tanımlayın.

---

## 6. Tek Dosya İkili Derleme

- **Windows:** `make build` veya `make.bat` → `dist/qtp.exe` (PyInstaller + Pillow PNG→ICO dönüşümü, UPX kapalı).
- **Linux / macOS:** `make build` → `dist/qtp.bin` (`chmod +x`, Linux'ta `strip`, macOS'ta `codesign --force --deep --sign -`).
- Hedef dosya boyutu 60 MB altı tutulur; testler (`tests/`), `tkinter`, `matplotlib` ve `numpy` `excludes` listesindedir.
- Çapraz derleme (örneğin Windows üzerinde Wine ile Linux ikilisi derleme) kullanılmaz; her platform ikilisi kendi hedef işletim sisteminde derlenir.
