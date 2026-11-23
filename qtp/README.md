# QTP — QuickTextPaste & Hazır Cevaplar (Bağımsız Uygulama + Klasik PWA)

**QTP v2.2.0**, ek harici bağımlılık gerektirmeyen, tek taşınabilir yürütülebilir dosya (`qtp.exe` / `qtp.bin`) ve sıfır arka uçlu statik Web arayüzü (`qtp.html` + `index.html`) olarak çalışan gelişmiş hazır cevap, snippet yöneticisi ve otomatik yapıştırma aracıdır.

---

## Dört Mod (`--gui`, `--tui`, `--cli`, `--web`) & Tam CRUD

- **`--gui`:** Varsayılan **Açık (Light)** tema (`Ctrl+,` Ayarlar'dan Açık/Koyu seçimi), anlık Türkçe-duyarlı bulanık arama, **`+ Yeni Cevap` / Sağ Tık `Düzenle` & `Sil`**, sistem tepsisi, `F1` (5 sekmeli Yardım) ve çakışmasız global kısayollar (`Win+Alt+*`).
- **`--tui`:** Renkli VT / eski Windows 7 Console uyumlu tam terminal arayüzü (`a`/`E`/`d` CRUD, `F1` tam Markdown kılavuz, `P`/`O`/`k` kısayol yönetimi).
- **`--cli`:** PowerShell / bash / zsh / fish otomatik tamamlama (`--completion`), `--json`, `--add-item` / `--update-item` / `--delete-item`, `-v`/`-vv` tanılama ve `-q` sessiz kip.
- **`--web` ve `qtp.html`:** Yerelde `127.0.0.1` loopback sunucusu; canlı ve statik modda Açık/Koyu tema geçişi, tam Cevap CRUD (`POST /api/items/*` veya tarayıcı `localStorage`), 6 sekmeli `F1` Yardım ve `Ctrl+K` / `/` hızlı arama.

---

## 1. Tek Dosya Uygulama ve Canlı GitHub Pages Dağıtımı

- **Klasik PWA (Ana URL):** [https://m-sonmez.github.io/qtp/](https://m-sonmez.github.io/qtp/) ([index.html](index.html)) — Klasik QuickTextPaste kılavuzu, [legacy/cevaplar.html](legacy/cevaplar.html) görüntüleyici, **📲 PWA Yükle** ve akıllı OS indirme düğmesi.
- **Birleşik Web Uygulaması:** [https://m-sonmez.github.io/qtp/qtp.html](https://m-sonmez.github.io/qtp/qtp.html) ([qtp.html](qtp.html)) — `--web` ile birebir özdeş çevrimdışı/statik CRUD arayüzü.
- **Windows x64 Taşınabilir İkili (`≤ 50 MB`):** [https://m-sonmez.github.io/qtp/qtp.exe](https://m-sonmez.github.io/qtp/qtp.exe)
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
- `qtp_settings.json` varsayılan değerleri: `theme: "light"`, `auto_reload: true` (`500 ms`), `paste_method: "auto"`, `enter_after_paste: true`, `backup_count: 15`, `web.port: 8765`.

---

## 5. English Summary

**QTP v2.2.0** is a standalone, zero-runtime-dependency snippet & quick-paste manager shipping portable single-file binaries (`qtp.exe` for Windows, `qtp.bin` for Linux x64) and a unified browser UI (`qtp.html`) alongside the preserved classic PWA (`index.html`, `legacy/`). It features a light-first UI with 1-click dark mode toggle, full snippet CRUD (Add/Edit/Delete) across GUI/TUI/CLI/Live-Web (plus offline `localStorage` CRUD on GitHub Pages), conflict-free `Win+Alt+*` Win32 global hotkeys, lossless UTF-16 LE BOM INI round-tripping, live reload, OS-aware download buttons, and PWA install support.
