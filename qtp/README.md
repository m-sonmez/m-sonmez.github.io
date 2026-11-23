# QTP — QuickTextPaste & Hazır Cevaplar (Bağımsız Uygulama + Klasik PWA)

**QTP v2.3.0**, ek harici bağımlılık gerektirmeyen, tek taşınabilir yürütülebilir dosya (`qtp.exe` / `qtp.bin`) ve sıfır arka uçlu statik Web arayüzü (`qtp.html` + `index.html`) olarak çalışan gelişmiş hazır cevap, snippet yöneticisi ve otomatik yapıştırma aracıdır. Windows ikilisi (`qtp.exe`), `CompanyName = Murat Sönmez` PE sürüm bilgisini ve `CN=Murat Sönmez` SHA-256 Authenticode dijital imzasını taşır.

---

## Dört Mod (`--gui`, `--tui`, `--cli`, `--web`) & Tam Güçlü Yönetim

- **`--gui`:** Varsayılan **Açık (Light)** tema (üst çubukta `🌙 Koyu` / `☀️ Açık`), **`☰ Liste` / `▦ Kart` / `▤ Tablo`** görünümleri, çoklu seçim ve **`✏️ Toplu Düzenle`**, **`📁 Grup Yöneticisi`**, **`⭐ Favoriler`**, **`😊/🚫 Emoji Temizle & Ekle`**, **`Ctrl+Z` / `Ctrl+Y` Geri Al/Yinele**, **`Ctrl+S` Kaydet**, sistem tepsisi ve `Win+Alt+*` kısayollar.
- **`--tui`:** Renkli VT / eski Windows 7 Console uyumlu tam terminal arayüzü (`a`/`E`/`d` CRUD, `Space` çoklu seçim, `U`/`X` toplu işlem, `D`/`K`/`J` çoğalt/taşı, `f`/`F` favoriler, `m` emoji temizleme, `g`/`G` gruplar, `u`/`y` geri/yinele, `w` kaydet).
- **`--cli`:** PowerShell / bash / zsh / fish otomatik tamamlama (`--completion`), `--json`, `--bulk-edit` / `--bulk-delete`, `--duplicate-item`, `--move-item`, `--toggle-favorite`, `--rename-group` / `--delete-group`, `--undo` / `--redo`, `--save`, `--only-favorites` / `--only-notes` / `--sort` / `--strip-emoji`.
- **`--web` ve `qtp.html`:** Yerelde `127.0.0.1` loopback veya GitHub Pages `localStorage`: Liste/Kart/Tablo görünümleri, sürükle-bırak İçe Aktarım, UTF-16 LE/UTF-8/ANSI/JSON/Word `.doc`/Yazdır dışa aktarımı, Toplu Düzenleme, Grup Yöneticisi, Emoji yongaları, Geri Al/Yinele ve yerel Anlık Kayıt Geçmişi.

---

## 1. Tek Dosya Uygulama ve Canlı GitHub Pages Dağıtımı

- **Klasik PWA (Ana URL):** [https://m-sonmez.github.io/qtp/](https://m-sonmez.github.io/qtp/) ([index.html](index.html)) — Klasik QuickTextPaste kılavuzu, [legacy/cevaplar.html](legacy/cevaplar.html) görüntüleyici, **📲 PWA Yükle** ve akıllı OS indirme düğmesi.
- **Birleşik Web Uygulaması:** [https://m-sonmez.github.io/qtp/qtp.html](https://m-sonmez.github.io/qtp/qtp.html) ([qtp.html](qtp.html)) — `--web` ile birebir özdeş çevrimdışı/statik CRUD arayüzü.
- **Windows x64 Taşınabilir İkili (`≤ 50 MB`, İmzalı):** [https://m-sonmez.github.io/qtp/qtp.exe](https://m-sonmez.github.io/qtp/qtp.exe) ([Ortak Sertifika `.cer`](certs/MuratSonmez-QTP.cer))
- **Linux x64 ELF Taşınabilir İkili (`≤ 60 MB`):** [https://m-sonmez.github.io/qtp/qtp.bin](https://m-sonmez.github.io/qtp/qtp.bin)

---

## 2. Çakışmasız Kısayollar ve Tam Özelleştirme

- Varsayılan `recommended` profili Windows sistem kısayolları ve Türkçe-Q `AltGr` (`@`) ile çakışmaz: `Win+Alt+Space` (Tümü), `Win+Alt+A`, `Win+Alt+Z`, `Win+Alt+X`, `Win+Alt+Q`.
- Altı hazır profil (`recommended`, `win_ctrl`, `ctrl_alt`, `ctrl_shift_alt`, `function_keys`, `legacy_win`), tüm 15 değiştirici bileşimi ve `hotkeys.<özel>` dinamik yuvaları.
- Ayrıntılar için [Klavye Kısayolları Rehberi](docs/KISAYOLLAR.md) belgesine bakın.

---

## 3. Kurulum, Kullanım, SSS ve Geliştirici Belgeleri

| Belge | İçerik |
| :--- | :--- |
| [Kurulum ve Sistem Gereksinimleri](docs/KURULUM.md) | Windows 7–11, Linux (X11/Wayland), macOS, BSD ve kaynaktan derleme adımları |
| [Kullanım Kılavuzu](docs/KULLANIM.md) | 4 kipin kullanımı, tam CRUD rehberi, JSON API örnekleri ve [Modlar Arası Eşitlik Matrisi](docs/KULLANIM.md#12-modlar-arası-eşitlik-matrisi) |
| [Klavye Kısayolları Rehberi](docs/KISAYOLLAR.md) | Global profiller, 15 değiştirici, `AltGr`, katman/TUI/Web kısayolları |
| [Sıkça Sorulan Sorular (SSS)](docs/SSS.md) | Birebir Türkçe hata/uyarı kataloğu, tema ve CRUD çözümleri |
| [Geliştirici Rehberi](docs/GELISTIRICI.md) | `legacy/` ve `standalone/` mimarisi, `OPERATIONS`, canlı izleyici ve CI/test kuralları |

---

## 4. Dizin Yapısı ve Ayarlar (`qtp_settings.json`)

- `qtp/standalone/` → Bağımsız uygulama kaynakları (`qtp_app/`), PyInstaller yapılandırmaları ve `pytest` takımı.
- `qtp/legacy/` → Klasik HTML/Python/PowerShell betikleri (`cevaplar.html`, `qtp_manager.py`, `qtp_core.py`, `qtp_server.py`, `kurulum.ps1`, `tests/test_qtp.py`).
- `qtp_settings.json` varsayılan değerleri: `theme: "light"`, `view_mode: "list"`, `strip_emoji: false`, `sort_by: "order"`, `auto_reload: true` (`500 ms`), `paste_method: "auto"`, `enter_after_paste: true`, `backup_count: 15`, `web.port: 8765`.

---

## 5. English Summary

**QTP v2.3.0** is a standalone, zero-runtime-dependency snippet & quick-paste manager shipping portable single-file binaries (Authenticode-signed `qtp.exe` for Windows with `CN=Murat Sönmez` & PE version metadata, `qtp.bin` for Linux x64) and a unified browser UI (`qtp.html`) alongside the preserved classic PWA (`index.html`, `legacy/`). It delivers full power-user parity across GUI, TUI, CLI, and Web/Static modes: List/Grid/Table views, multi-select & bulk edit/delete, Unicode emoji strip & quick chips, favorites, usage tracking & sorting, duplicate & reorder, group manager, 30-step Undo/Redo, drag-and-drop INI/JSON import, multi-encoding INI / JSON / Word `.doc` / Print export, and local/disk snapshots with a WCAG-verified light-first UI.
