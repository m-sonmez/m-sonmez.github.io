# QTP Geliştirici Rehberi

Bu belge, QTP v2.0.0 tek dosya masaüstü uygulamasının mimarisini, test altyapısını, çapraz platform UI/UX eşitlik denetimlerini ve derleme sürecini açıklar.

---

## 1. Mimari Genel Bakış ve Modül Haritası

```text
qtp_app/
├── __init__.py               # Sürüm (__version__), derleme tarihi ve uygulama adı
├── main.py                   # CLI (--selftest, --version, --export-ini, --import-ini, --help), qtp.lock, GUI orkestrasyonu
├── core/
│   ├── ini_parser.py         # Çoklu kodlama algılama (UTF-16 LE/BE, UTF-8 BOM, cp1254) ve kayıpsız INI ayrıştırıcı
│   ├── json_store.py         # data.json, INI<->JSON dönüşümü, backups/, qtp-tam-yedek-*.json (v2)
│   ├── hotkeys.py            # pynput.GlobalHotKeys + Windows keyboard fallback + macOS Accessibility denetimi
│   ├── paster.py             # pyperclip/Qt pano, odak geri yükleme, Ctrl+V/Cmd+V/wtype/ydotool, <E<N<D| -> Enter
│   ├── settings.py           # qtp_settings.json taşınabilir + salt-okunur geri dönüş dizinleri
│   └── logging_setup.py      # Dönen günlük kurulumu (qtp.log, 1 MB x 3)
├── ui/
│   ├── theme.py              # Renk paletleri, sabit boyutlar/yarıçaplar/animasyon süreleri, Inter yazı tipi yükleyici
│   ├── search.py             # FuzzyMatcher (Türkçe İ/i ve I/ı uyumlu alt-dizi puanlama)
│   ├── overlay.py            # Çerçevesiz katman penceresi, sanal QListView + QStyledItemDelegate, toast, animasyonlar
│   ├── tray.py               # QSystemTrayIcon ve Türkçe sağ tık menüsü
│   ├── settings_window.py    # Tüm qtp_settings.json alanları için Türkçe ayar penceresi
│   └── help_dialog.py        # docs/*.md için çevrimdışı Markdown->HTML yardım penceresi (F1)
├── assets/
│   ├── icon.svg, icon-192.png, icon-512.png
│   ├── fonts/Inter-*.ttf     # Çapraz platform birebir yazı tipi tutarlılığı için gömülü Inter yazı tipleri
│   └── defaults/             # Gömülü QuickTextPaste.ini ve data.json örnekleri
├── build/
│   ├── qtp.spec              # PyInstaller onefile/windowed yapılandırması (UPX kapalı)
│   ├── build_windows.py      # Windows -> dist/qtp.exe üretici ve --selftest doğrulayıcı
│   └── build_unix.py         # Linux/macOS -> dist/qtp.bin üretici (+strip, +codesign)
└── tests/                    # Kapsamlı pytest + pytest-qt test paketi
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
