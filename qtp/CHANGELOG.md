# Değişiklik Günlüğü (CHANGELOG)

Tüm kayda değer QTP sürümleri bu dosyada Türkçe olarak belgelenir.

---

## [2.1.0] - 2026-11-23

### Esnek Kısayollar, Win32 `RegisterHotKey`, Konsol Düzeltmesi ve Canlı Otomatik Yenileme
- **Çakışmasız Varsayılan Kısayollar (`Win+Alt+*`), 15 Değiştirici Bileşimi ve Özel Yuvalar (`core/hotkeys.py`, `core/settings.py`):**
  - Windows 10/11 sistem kısayolları (`Win+A/Z/X/Q`) ve Türkçe-Q `AltGr` (`Ctrl+Alt+Q=@`, `Ctrl+Alt+A=æ`) ile çakışmayı önlemek için varsayılan global kısayollar `Win+Alt+Space`, `Win+Alt+A`, `Win+Alt+Z`, `Win+Alt+X`, `Win+Alt+Q` olarak güncellendi; el değmemiş eski `Win+A/Z/X/Q` varsayılanları tek seferlik güvenli şekilde otomatik geçirilir (özel kullanıcı kısayolları korunur).
  - Tüm 15 değiştirici bileşimi (`Ctrl`, `Alt`, `Shift`, `Win` alt kümeleri), kanonsal ayrıştırma (`parse_hotkey`/`normalize_hotkey`), toplu değiştirici güncellemesi (`apply_modifier_combo` / `--hotkey-modifiers`), 6 hazır profil (`recommended`, `win_ctrl`, `ctrl_alt`, `ctrl_shift_alt`/`triple_mod`, `function_keys`, `legacy_win`) ve özel kategori yuvaları (`hotkeys.W` vb.) eklendi.
  - Windows 7–11 x64 üzerinde 64-bit `ctypes` ile yerel **Win32 `user32.RegisterHotKey`** arka ucu eklendi (`MOD_NOREPEAT`, `ERROR_HOTKEY_ALREADY_REGISTERED / 1409` algılama, sıfır tuş sızıntısı) ve canlı Türkçe çakışma analizcisi (`detect_hotkey_conflicts` / `--check-hotkeys`) getirildi.
- **Dinamik Canlı Otomatik Yenileme (`core/watcher.py`, `--gui`/`--web`/`--tui`):**
  - Sıfır bağımlılıklı `ConfigFileWatcher` ile `qtp_settings.json`, `QuickTextPaste.ini` (`data_path`) ve `data.json` dosyalarındaki harici/atomik (`os.replace`) değişiklikler yeniden başlatma olmadan canlı yüklenir (`auto_reload`, `auto_reload_interval_ms`, `250 ms` debounce, kendi yazımını bastırma, bozuk dosya koruması).
  - Ayar değişikliğinde `OverlayWindow` listesi, tema, pencere boyutu, tepsi etiketi ve işletim sistemine kayıtlı global kısayollar anında yeniden bağlanır.
- **Windows PowerShell/Terminal Konsol Eki, `-v`/`--verbose`/`-q` ve `--completion` (`cli.py`, `engine.py`):**
  - PyInstaller `--onefile` (`console=False`) önyükleyicisini aşarak `PowerShell`/`pwsh`/`cmd`/Terminal ata sürecine `argparse` öncesinde UTF-8 (`65001`) ile bağlanan `_iter_windows_ancestor_pids` + `AttachConsole` / TUI `AllocConsole` düzeltmesi yapıldı.
  - `--verbose` (`-v` / `-vv`) / `--quiet` (`-q`) ve yan etkisiz dinamik `--completion [powershell|bash|zsh|fish|auto]` dört mod eşitliğiyle (`operations.py`, `web.py`, `tui/app.py`) eklendi.
- **Geliştirilmiş Ayarlar Penceresi (`ui/settings_window.py`) ve Dinamik Tepsi/Web Arayüzü:**
  - `HotkeyRow` (4 değiştirici onay kutusu + doğrudan tuş yakalayabilen `HotkeyEdit`), **+ Özel Kısayol Ekle**, hazır profil ve toplu değiştirici çubuğu, canlı Türkçe çakışma etiketi ve `auto_reload` kontrolleri eklendi.
- **Modlar Arası Birebir Entegrasyon Eşitliği (`cli.py`, `logging_setup.py`, `main.py`, `web.py`, `tui/app.py`, `ui/help_dialog.py`):**
  - `-v`/`--verbose`/`-vv` ve `-q`/`--quiet` tüm modlara (`--cli`, `--web`, `--tui`, `--gui`) birleşik canlı `stderr` tanılama akışı (`_DynamicStderrHandler`) ile bağlandı; `--web --verbose` HTTP isteklerini (`METHOD /path -> STATUS`) ve yaşam döngüsü olaylarını canlı akıtır, Windows ebeveyn konsolu `--web --verbose`, `--gui --verbose` ve tüm `--<mode> --help` çağrılarında bağlanırken çift tık / sessiz `--gui` penceresiz kalır.
  - `--cli/--web/--tui/--gui --help` ve `--verbose --help` bayrak sırasından bağımsız olarak her modda `0` ile çıkıp diske sıfır dosya yazar; kanonsal `engine.op_help(verbose=...)` (`usage`, `usage_verbose`, `kullanim`, `kisayollar`, `sss`) GUI `HelpDialog` **CLI & Parametreler** sekmesi, kaydırılabilir eksiksiz TUI `F1` modalı ve Web `/api/help?verbose=1` + `F1` modalında birleştirildi.
  - `--category` ve `--query` başlangıç filtreleri `--cli`, `--tui`, `--gui` (`OverlayWindow`) ve `--web` (`/api/revision` + `index.html`) için tek tip hale getirildi.
- **Mod Eşitliği, Çapraz-OS Geriye Dönük Uyumluluk ve Sıfır Yorum Kilidi:**
  - `--gui`, `--tui`, `--cli`, `--web` modları 22 kanonsal `operations.py` işlemiyle birleştirildi; Windows 7/8/8.1 x64 (`qtp-win7.exe`), Python 3.8+ çekirdeği, Linux X11/Wayland, macOS 10.15–15, BSD ve sözdizimi güvenli sıfır yorum (`test_no_unnecessary_comments`) korundu.

---

## [2.0.0] - 2026-11-23

### Eklenenler ve Büyük Yenilikler
- **Tek Dosya Bağımsız Masaüstü Uygulaması:** Windows için taşınabilir `qtp.exe` ve Linux/macOS için taşınabilir `qtp.bin` (`PyInstaller --onefile` + gömülü `Inter` yazı tipleri ve Türkçe yardım belgeleri).
- **`QuickTextPaste.exe` Bağımlılığı Kaldırıldı:** Global kısayollar, pano kopyalama, önceki pencere odağını geri yükleme ve otomatik yapıştırma (`<E<N<D|` sonrası `Enter`) artık tamamen yerleşiktir.
- **Modern Katman (Overlay) Arayüzü (PyQt6), Türkçe Bulanık Arama ve Kayıpsız INI↔JSON Motoru.**

---

## [1.x] - Önceki Sürümler
- Tarayıcı tabanlı çevrimdışı PWA (`index.html`, `cevaplar.html`, `sw.js`, `manifest.webmanifest`), yerel Python HTTP köprüsü (`qtp_server.py`) ve Tkinter masaüstü yöneticisi (`qtp_manager.py`).
