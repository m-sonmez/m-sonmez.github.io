# QTP — QuickTextPaste & Universal Snippet Manager (`v2.5.0`)

**QTP v2.5.0** is a **100 % config- and data-driven, globally usable quick-paste & snippet manager** for any user, any language, any domain, any categories, any groups, and any keybindings. It ships as a standalone zero-runtime-dependency single-file portable binary (`qtp.exe` for Windows, `qtp.bin` for Linux x64) and a responsive 320 px–1920 px offline-capable Web/PWA (`qtp.html` + `index.html`), while remaining **100 % backward-compatible** with any existing `QuickTextPaste.ini` or `data.json`.

---

## Highlights (`v2.5.0`)

- **100 % Config-Driven Categories & Hotkeys:** Only virtual `All` (`Tümü`) is built in. Define custom categories (`code`, `label`, `hotkey_prefix`) in `qtp_settings.json`, GUI **Settings**, or Web **Categories** — or drop any existing `QuickTextPaste.ini` / `data.json` into the folder and QTP automatically discovers every distinct category prefix in order of first appearance.
- **Universal Default Hotkey (`Win+Alt+Space`) & Dynamic Presets:** Starts with a minimal, conflict-free `{"all": "Win+Alt+Space"}` binding and lets you bind any category or custom slot across all 15 modifier combinations and 6 dynamic presets (`recommended`, `win_ctrl`, `ctrl_alt`, `ctrl_shift_alt`, `function_keys`, `legacy_win`), with live OS/KDE/GNOME/AltGr conflict detection.
- **Built-in EN / TR i18n + Custom `qtp_locale.json`:** Defaults to `language: "auto"` (English globally, Turkish automatically on `tr*` OS locales) with live 1-click EN/TR switching across GUI, TUI, CLI, and Web (`qtp.html`, `index.html`, `legacy/cevaplar.html`). Place an optional `qtp_locale.json` in your config directory to translate or customize any UI string in any language without recompiling.
- **Four Full-Parity Modes (`--gui`, `--tui`, `--cli`, `--web`):**
  - **`--gui`:** Light-first WCAG-verified Spotlight overlay with dark toggle, List/Grid/Table views, dynamic category pills, multi-select & Bulk Edit, Group Manager, Emoji strip/chips, 30-step Undo/Redo, 8-edge frameless resize/drag, Wayland `XDG_ACTIVATION_TOKEN` IPC raising, `hide_on_blur`, and tray single-click toggle.
  - **`--tui`:** Pure-stdlib terminal interface (Linux/macOS `curses`, Windows VT100/Win32 Console) with dynamic `Tab`/`1–9` category switching, `N` notes-only toggle, `F` favorites filter, `a`/`E`/`d` CRUD, `Space`/`U`/`X` bulk edit/delete, `g`/`G` groups, `u`/`y` undo/redo, and `F1` help.
  - **`--cli`:** Machine-readable `--json`, PowerShell/bash/zsh/fish `--completion`, full CRUD, bulk operations, `--only-favorites`, `--only-notes`, `--group`, `--sort {order,usage,alpha,keys,favorites}`, `--strip-emoji`, `--get`/`--set`, and `--check-hotkeys`.
  - **`--web` & Offline PWA (`qtp.html`):** Identical UI in local loopback (`127.0.0.1` with DNS-rebinding/CSRF protection) and zero-backend GitHub Pages static mode (`localStorage` + `sw.js` `qtp-pwa-cache-v4.0.0` offline routing with query-string support).

---

## 1. Live GitHub Pages & Single-File Downloads

- **Unified Web App (Offline PWA):** [https://m-sonmez.github.io/qtp/qtp.html](https://m-sonmez.github.io/qtp/qtp.html) ([qtp.html](qtp.html))
- **Classic PWA (Root URL):** [https://m-sonmez.github.io/qtp/](https://m-sonmez.github.io/qtp/) ([index.html](index.html)) & [Quick Board](legacy/cevaplar.html)
- **Windows x64 Portable Binary (`≤ 50 MB`, Authenticode-signed `CN=Murat Sönmez`):** [https://m-sonmez.github.io/qtp/qtp.exe](https://m-sonmez.github.io/qtp/qtp.exe) ([Public Certificate `.cer`](certs/MuratSonmez-QTP.cer))
- **Linux x64 ELF Portable Binary (`≤ 60 MB`, cross-distro):** [https://m-sonmez.github.io/qtp/qtp.bin](https://m-sonmez.github.io/qtp/qtp.bin)

---

## 2. Documentation

| Document | Contents |
| :--- | :--- |
| [Installation & Requirements (`KURULUM.md`)](docs/KURULUM.md) | Windows 7–11, Linux (X11/Wayland), macOS, BSD, code signing & source builds |
| [Usage Guide (`KULLANIM.md`)](docs/KULLANIM.md) | All 4 modes, dynamic categories, EN/TR/`qtp_locale.json`, CRUD, settings & [Mode Parity Matrix](docs/KULLANIM.md#12-modlar-arası-eşitlik-matrisi) |
| [Keyboard Shortcuts (`KISAYOLLAR.md`)](docs/KISAYOLLAR.md) | Dynamic hotkeys, 6 presets, 15 modifier combos, conflict checks & overlay/TUI/Web keys |
| [FAQ & Error Reference (`SSS.md`)](docs/SSS.md) | Exact error/warning catalog, Wayland/Windows troubleshooting, theme & CRUD tips |
| [Developer Guide (`GELISTIRICI.md`)](docs/GELISTIRICI.md) | `standalone/` vs `legacy/` architecture, `OPERATIONS`, i18n, live watcher & test/CI gates |

---

## 3. Quick Settings Reference (`qtp_settings.json`)

Default configuration (`qtp_settings.json`):
- `language`: `"auto"` (`"auto"` / `"en"` / `"tr"` or custom code from `qtp_locale.json`)
- `categories`: `[]` (custom `[{"code": "1", "label": "General", "hotkey_prefix": "L-Win+1"}]` merged with auto-discovered data categories)
- `hotkeys`: `{"all": "Win+Alt+Space"}` (extendable with any category or custom slot `hotkeys.<slot>`)
- `theme`: `"light"`, `view_mode`: `"list"`, `strip_emoji`: `false`, `sort_by`: `"order"`, `hide_on_blur`: `true`, `auto_reload`: `true` (`500 ms`), `paste_method`: `"auto"`, `enter_after_paste`: `true`, `backup_count`: `15`, `web.port`: `8765`.

---

## 4. Türkçe Özet

**QTP v2.5.0**, herhangi bir alan adına, sabit kategoriye veya dile bağlı kalmadan tamamen yapılandırma ve veri odaklı çalışan taşınabilir hızlı yapıştırma ve metin şablonu yöneticisidir. Tek dosya Windows (`qtp.exe`, `CN=Murat Sönmez` Authenticode imzalı) ve Linux (`qtp.bin`) ikilileri ile çevrimdışı PWA web arayüzü (`qtp.html`, `index.html`, `legacy/cevaplar.html`) sunar. `qtp_settings.json` içinde kendi kategorilerinizi ve `hotkeys.*` kısayollarınızı tanımlayabilir ya da mevcut `QuickTextPaste.ini` / `data.json` dosyanızı doğrudan klasöre bırakarak tüm eski kategorilerinizi %100 geriye dönük uyumlulukla otomatik keşfedebilirsiniz. Yerleşik İngilizce/Türkçe (`language: "auto" | "en" | "tr"`) dil desteği ve isteğe bağlı `qtp_locale.json` ile her dilde özelleştirilebilir.
