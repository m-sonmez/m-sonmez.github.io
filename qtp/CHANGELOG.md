# Değişiklik Günlüğü (CHANGELOG)

Tüm kayda değer QTP sürümleri bu dosyada Türkçe olarak belgelenir.

---

## [2.3.1] - 2026-11-23

### Linux (Arch/CachyOS/Wayland/X11) Düzeltmeleri, Gömülü SVG Simgeler, 8-Kenar Boyutlandırma & Mobil Web Uyumluluğu
- **Çapraz Dağıtım Linux `qtp.bin` Kütüphane Uyumluluğu (`build/qtp.spec`):** Ubuntu 22.04 CI ortamından Arch/CachyOS, Fedora ve openSUSE üzerine taşınabilirliği bozan konak yapılandırmasına bağlı paylaşılan kütüphaneler (`libfontconfig.so`, `libfreetype.so`, `libharfbuzz.so`, `libexpat.so`, `libxkbcommon*.so`, `Mesa`/`EGL`/`GL`, `libwayland-*`, `libX11`/`libxcb*`, `libglib`/`libdbus`/`libstdc++` vb.) PyInstaller paketinden dışlanarak `Fontconfig error` (`48-guessfamily.conf`) ve `xkbcommon: ERROR` hataları kökten giderildi (`libQt6*`, `PyQt6`, platform/SVG eklentileri gömülü kalır).
- **Wayland Pencere Opaklık Uyarısı Giderildi (`ui/overlay.py`):** Wayland ve `offscreen` arka uçlarında `windowOpacity` animasyonu/çağrısı kapatılarak konsola yüzlerce kez basılan `"This plugin does not support setting window opacity"` uyarısı sıfırlandı; tüm platformlarda `180 ms` / `8 px` kaydırma animasyonu korundu.
- **8-Kenar Çerçevesiz Yeniden Boyutlandırma, Başlık Sürükleme & Büyüt/Küçült (`ui/overlay.py`, `main.py`):** Linux/POSIX masaüstlerinde pencere türü `Tool` yerine yeniden boyutlandırılabilir `Window` (`FramelessWindowHint | WindowStaysOnTopHint`) yapıldı; üst sürükleme başlığı (`startSystemMove`), 8 kenar/köşeden dinamik boyutlandırma (`startSystemResize` + geometri yedeği + `QSizeGrip`) ve tam ekran/geri yükle düğmesi eklenip `window_size` ayar kalıcılığı bağlandı.
- **Wayland Odak-Öncesi Pano & Terminal Farkındalıklı Yapıştırma (`core/paster.py`, `core/engine.py`, `ui/overlay.py`):** `OverlayWindow.paste_row()` içinde gizleme (`hide_overlay`) öncesi kopyalama (`pre_copied` → `already_copied`) uygulanarak Wayland `wl_data_device.set_selection` yüzey odağı reddi giderildi; eskimiş X10 `XStoreBytes` kaldırılıp Qt `QClipboard` + X11 `Selection` → `wl-copy` → `xclip`/`xsel` → `pyperclip` → `OSC 52` zincirine geçildi. `wtype -M ctrl -k v -m ctrl` anahtar bayrağı düzeltildi, XWayland `pynput` geçişinde çıplak `v` sızıntısı önlendi ve Linux uçbirimlerinde (`Konsole`, `Alacritty`, `Kitty`, `Ghostty` vb.) otomatik/elle `ctrl_shift_v` yapıştırma desteği eklendi.
- **Temiz `Ctrl+C` (`SIGINT`) / `SIGTERM` Çıkışı (`main.py`):** Yinelenmeye karşı koruyucu idempotent `quit_app()`, `SIGINT`/`SIGTERM` sinyal işleyicisi ve `250 ms` Python uyandırma zamanlayıcısı eklenerek uçbirimden `Ctrl+C` ile çekirdek dökümü (`Aborted`) yerine temiz `0` çıkışı sağlandı.
- **Gömülü Tema-Renkli SVG Arayüz Simgeleri (`ui/icons.py`, `ui/tray.py`, `ui/settings_window.py`, `ui/overlay.py`):** Eksik sistem emoji yazıtiplerinden etkilenmeyen satır içi SVG `QIcon` üreticisi eklendi (Açık/Koyu temaya göre canlı renklenir); tepsi simgesi `16..64 px` çoklu çözünürlüklü duruma getirildi.
- **Mobil / Android Duyarlı Web Arayüzü (`web/theme.css`, `web/qtp.html`, `qtp.html`, `theme.css`, `sw.js`):** Dar ekranlarda `.snippet-row` öğelerini tek karaktere sıkıştıran masaüstü esnek satır yapısı `flex-wrap`, `@media (max-width: 768px)` / `@media (max-width: 520px)` sütun dizilimi, yatay kaydırılabilir kategori hapları ve `.table-wrap` ile düzeltildi (`sw.js` `v3.4.1`).
- **Çoklu Dağıtım Linux/BSD/macOS Belgeleri (`docs/KURULUM.md`, `docs/SSS.md`, `README.md`):** Yalnızca `apt-get` gösteren yönergeler yerine `pacman`, `apt`, `dnf`, `zypper`, `apk`, `pkg` ve `brew` komutları sıfır zorunlu bağımlılık vurgusuyla belgelendi.

---

## [2.3.0] - 2026-11-23

### Tam Güçlü Yönetim Paritesi (`legacy/` → GUI/Web/TUI/CLI) & `qtp_manager.py` Sözdizimi Düzeltmesi
- **Klasik Yöneticideki Sözdizimi Hatası Giderildi (`legacy/qtp_manager.py:492`):** `open_web_panel` içinde `subprocess.Popen(...)` argümanlarının içine yazılmış `if not srv_script.is_file():` bloğu çağrı öncesine alınarak `SyntaxError` kökten çözüldü; `legacy/tests/test_qtp.py` içine tüm `legacy/*.py` dosyalarını derleyen `test_legacy_python_files_compile_cleanly` kapısı eklendi.
- **Çoklu Seçim, Toplu Düzenleme & Toplu Silme (`bulk_edit`, `bulk_delete`):** GUI/Web/TUI/CLI katmanlarında çoklu seçim (`Space`, onay kutusu, `Shift+Tık`, tümünü seç/temizle), kısayol/grup atama, büyük-küçük harf duyarsız Türkçe bul-değiştir, önek/sonek, toplu emoji ekleme/temizleme ve favori durumu güncelleme getirildi.
- **Unicode Emoji Temizleme & Hızlı Emoji Yongaları (`strip_emoji`, `strip_emojis`):** Kopyalama/yapıştırma sırasında depolanmış metni bozmadan emojileri kaldıran genel `😊 Emojili / 🚫 Emojisiz` anahtarı ve düzenleyici/toplu işlem içinde tek-tık emoji yongaları eklendi.
- **Liste / Kart / Tablo Görünümleri (`view_mode: "list" | "grid" | "table"`):** Hem PyQt6 `OverlayWindow` (`QListView` Liste & `IconMode` Kart + `QTableView`) hem de Web (`qtp.html`) arayüzüne `view_mode` kalıcılığıyla eklendi.
- **Favoriler (`⭐`), Kullanım Sayacı (`copyCount`), Sıralama (`sort_by`), Çoğalt (`duplicate_item`), Yukarı/Aşağı Taşı (`move_item`), Grup Yöneticisi (`rename_group`, `delete_group`), 30 Adımlı Geri Al/Yinele (`undo`, `redo`) & Anlık Kayıt (`save_all`):** Tüm yeni işlemler `operations.py` ve `QtpEngine` üzerinde birleştirilip 4 modda eşitlendi; Web modunda sürükle-bırak içe aktarım, UTF-16/UTF-8/ANSI/JSON/Word `.doc`/Yazdır dışa aktarımı ve yerel/disk anlık kayıt geçmişi sunuldu (`sw.js` `v3.4.0`).

---

## [2.2.1] - 2026-11-23

### Açık/Koyu Tema Kök Düzeltmesi, WCAG Kontrast Kapısı, PE Sürüm Bilgisi & Authenticode İmzalama
- **GUI Açık Tema Siyah Kart & OS Palet Sızıntısı Düzeltmesi (`ui/theme.py`, `overlay.py`, `settings_window.py`, `help_dialog.py`, `tray.py`, `main.py`):**
  - `SnippetItemDelegate` içinde PyQt6 `QColor("rgba(...)")` çağrısının `(0, 0, 0, 255)` saf siyah döndürmesinden kaynaklanan siyah seçili/vurgulu kart ve rozet hatası, CSS `rgb/rgba` + hex çözümleyen `parse_qcolor` ve tam semantik `ThemePalette` jetonlarıyla kökten giderildi.
  - `build_qpalette` ile tüm `QApplication` ve açılır pencerelere (`QMenu`, `QComboBox QAbstractItemView`, `QPlainTextEdit`, `QListWidget`, `QScrollArea`, `QGroupBox`, `QMessageBox`, `QToolTip`, `QScrollBar`) işletim sistemi koyu/açık mod sızıntısını engelleyen tam `QPalette` ve QSS bağlandı.
  - `HelpDialog` başlık ve kod blokları, `SettingsWindow` çakışma uyarıları (`success_text` / `warning_text`) ve `LIGHT_PALETTE` bildirim balonu açık temada yüksek okunurluğa getirildi; `OverlayWindow` üst çubuğuna 1-tık `🌙 Koyu` / `☀️ Açık` tema düğmesi eklendi.
- **Web (`theme.css`, `qtp.html`) ve Klasik PWA (`index.html`, `legacy/cevaplar.html`) Tema Yalıtımı:**
  - `theme.css` içine `:root { color-scheme: light; }` ve `:root[data-theme="dark"] { color-scheme: dark; }` eklendi; bileşen seçicilerindeki tüm sabit renkler `var(--...)` jetonlarına taşındı. `index.html` ve `legacy/cevaplar.html` koyu/açık sızıntıları giderildi; `sw.js` önbelleği `v3.3.1` sürümüne yükseltildi.
- **Windows PE Sürüm Bilgisi & Authenticode Kod İmzalama (`CN=Murat Sönmez`):**
  - `qtp_app/build/version_info.txt` (`CompanyName = Murat Sönmez`, `ProductVersion = 2.2.1.0`) `qtp.spec` ve `qtp_win7.spec` içine eklendi.
  - `qtp_app/build/sign_windows.ps1` ile RSA-4096 / SHA-256 `CN=Murat Sönmez` kod imzalama sertifikası üretilip RFC 3161 zaman damgalı Authenticode imzalama `build_windows.py` akışına bağlandı; yalnızca ortak sertifika `qtp/certs/MuratSonmez-QTP.cer` yayımlandı (`.pfx`/`.p12`/`.key` `.gitignore` ile kalıcı dışlandı).
- **Otomatik Kontrast, Statik Renk Taraması & Piksel Parlaklık Testleri:**
  - `test_platform_parity.py`, `test_smoke_ui.py` ve `test_web_ui.py` içine WCAG 2.1 kontrast denetimi (≥ 4.5:1 metin, ≥ 3.0:1 kontroller), sabit renk sızıntı taraması ve offscreen piksel parlaklık + canlı geçiş testleri eklendi.

---

## [2.2.0] - 2026-11-23

### Mimari Düzenleme (`legacy/` vs `standalone/`), Varsayılan Açık Tema, Tam CRUD & Kapsamlı Türkçe Belgeler
- **Temiz Dizin Ayrımı:** Klasik PWA betikleri ve eski Windows otomasyonu `qtp/legacy/` altına (`cevaplar.html`, `qtp_manager.py`, `qtp_core.py`, `qtp_server.py`, `kurulum.ps1`, `tests/test_qtp.py`), bağımsız uygulama çekirdeği ise `qtp/standalone/` altına taşındı. Kökte yalnızca yayın/PWA varlıkları (`index.html`, `qtp.html`, `theme.css`, `sw.js`, `manifest.webmanifest`, `data.json`, `QuickTextPaste.ini`, `icon*`, `docs/`, `qtp.exe`, `qtp.bin`) tutuldu.
- **Klasik PWA Kök URL'de Korundu:** `qtp/index.html` klasik QuickTextPaste PWA olarak geri yüklendi (`old.html` kaldırıldı); yeni tek-dosya Web arayüzü `qtp/qtp.html` olarak yayınlandı (`--web` yerel sunucusu `/`, `/qtp.html` ve `/index.html` rotalarında `qtp.html` sunar).
- **Varsayılan Açık (Light) Tema + Tek-Tık Koyu Geçişi:** `DEFAULT_SETTINGS["theme"] = "light"` ile `--gui`, `--web`, `qtp.html`, `index.html` ve `legacy/cevaplar.html` varsayılan Açık temaya geçti; GUI ve Web arayüzlerine anlık `🌗` tema değiştirici eklendi.
- **Tam Hazır Cevap CRUD (`add_item`, `update_item`, `delete_item`):**
  - **Core / CLI:** Atomik INI + `data.json` kalıcılığı ve yedekleme; `--add-item`, `--update-item`, `--delete-item` ve `--item-{keys,group,label,text}` / `--no-end-marker`.
  - **Web (`--web` & Statik `qtp.html`):** `POST /api/items/{add,update,delete}` uç noktaları ile tam CRUD modalı ve silme onayı; statik GitHub Pages modunda tarayıcı `localStorage` kalıcılığı.
  - **GUI & TUI:** GUI `+ Yeni Cevap` / sağ-tık `Düzenle` & `Sil` (`SnippetEditorDialog`); TUI `a`, `E`, `d` komutları.
- **Akıllı OS İndirme & PWA Yükle:** Hem `qtp.html` hem `index.html` üzerinde işletim sistemini tanıyan tek-tık `qtp.exe` / `qtp.bin` indirme düğmeleri, çapraz sayfa linkleri ve `beforeinstallprompt` destekli **📲 PWA Yükle** düğmesi eklendi.
- **Kapsamlı Türkçe Yardım & Belgeler:** `docs/{KULLANIM,KURULUM,KISAYOLLAR,SSS,GELISTIRICI}.md` ve `README.md` yenilendi; GUI `HelpDialog` 5 sekmeye (`Kurulum & İndirme` dahil), Web `F1` Yardım modalı 6 sekmeye, TUI `F1` ve `/docs/KURULUM.md` desteğine çıkarıldı.
- **CI ve Paketleme İyileştirmeleri:** `.github/workflows/qtp-publish-linux.yml` `xvfb-run` + Ubuntu Qt6/X11 bağımlılıkları + `actions/checkout@v6` + `astral-sh/setup-uv@v10.4.0` + `qtp/standalone` çalışma dizini ile güncellendi; `qtp.spec` kullanılmayan ağır PyQt6 alt modüllerini dışlayacak biçimde sadeleştirildi.

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
- **Birleşik GitHub Pages Web Arayüzü & Taşınabilir Dağıtım (`qtp/index.html`, `qtp/old.html`, `qtp/qtp.exe`, `qtp/qtp.bin`):**
  - `qtp_app/web/index.html` ve `theme.css` hem yerel `--web` sunucusu (`/api/revision` otomatik algılama) hem de GitHub Pages statik barındırması (`./data.json` + `./QuickTextPaste.ini` + `localStorage` geri dönüşü, birebir Türkçe bulanık arama, kategori hapları, pano kopyalama, `INI'de Göster`, v2 JSON/UTF-16 INI yedek dışa aktarımı, `Kısayollar` ve `Yardım (F1)` modalları) için çift modlu olarak birleştirilip `qtp/index.html` + `qtp/theme.css` ile birebir eşitlendi.
  - Önceki 3. parti QuickTextPaste PWA sayfası `qtp/old.html` olarak korundu, `qtp/sw.js` (`v3.2.0`) güncellendi ve taşınabilir `qtp/qtp.exe` (ve Ubuntu 22.04 CI ile `qtp/qtp.bin`) yayınlandı.
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
