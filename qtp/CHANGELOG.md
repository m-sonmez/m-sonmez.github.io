# Değişiklik Günlüğü (CHANGELOG)

Tüm kayda değer QTP sürümleri bu dosyada Türkçe olarak belgelenir.

---

## [2.4.4] - 2026-11-24

### Sıralama Eşitliği, TUI Not Filtresi, Çevrimdışı PWA Sorgu Yönlendirmesi, Erişilebilirlik & Belge Güncellemesi
- **Çapraz Mod `sort_by="keys"` & `"alpha"` Sıralama Eşitliği (`ui/search.py`, `core/engine.py`, `ui/overlay.py`):**
  - Ortak `tr_sort_key()` yardımcı işlevi eklenerek `--cli`/`--tui`/`--web` (`QtpEngine.op_list_items`), `--gui` (`OverlayWindow._refresh_list`) ve statik `qtp.html` arasında Türkçe alfabe sıralaması (`a..z + ç,ğ,ı,ö,ş,ü`) eşitlendi ve `sort_by="keys"` kipinde kısayolsuz notların (`keys=""`) tüm modlarda deterministik olarak sona konması sağlandı.
- **TUI Yalnızca Notlar Anahtarı (`tui/app.py`):**
  - `N` tuşu `self.only_notes` filtresini açıp kapatacak şekilde bağlandı (`F` favori filtresiyle eşlenik).
- **PWA Çevrimdışı Sorgu Parametresi Yönlendirmesi (`sw.js` `qtp-pwa-cache-v3.5.5`):**
  - `caches.match(req, { ignoreSearch: true })` ve `pathname.endsWith('/qtp.html')` / `'/cevaplar.html'` gezinme yedeği eklenerek çevrimdışı `/qtp/qtp.html?category=A` açılışlarının yanlışlıkla klasik `index.html`'e düşmesi giderildi.
- **Erişilebilirlik & Belge Senkronizasyonu (`web/qtp.html`, `qtp.html`, `index.html`, `docs/KULLANIM.md`, `docs/KISAYOLLAR.md`):**
  - Açık modallarda `Tab` / `Shift+Tab` odak tuzağı eklendi ve klasik `index.html` arama/onay/favori kontrollerine `aria-label` öznitelikleri tamamlandı.
  - `docs/KULLANIM.md` Bölüm 1 (tepsi sol tek tık), Bölüm 5 (10 eylemli sağ tık menüsü) ve Bölüm 7 (`view_mode`, `strip_emoji`, `sort_by`, `hide_on_blur` ayarları) ile `docs/KISAYOLLAR.md` güncellendi; `qtp/.gitattributes` içine `.gitattributes text eol=lf` eklendi.

---

## [2.4.3] - 2026-11-24

### Windows Uyumluluğu, LF CSS Varlık Tutarlılığı & Sürüm Eşitleme
- **`qtp/.gitattributes` (`*.css text eol=lf`):** Windows üzerinde `core.autocrlf=true` nedeniyle `qtp/theme.css` ve `qtp/standalone/qtp_app/web/theme.css` dosyalarının CRLF (`29.216` bayt) olarak çıkarılıp `qtp.exe` içine farklı baytlarla gömülmesi giderildi; CSS dosyaları tüm işletim sistemlerinde LF (`27.532` bayt) olarak korunur.
- **Windows Test Eşitliği (`tests/test_smoke_ui.py`, `tests/test_web_ui.py`, `tests/test_mode_parity.py`):**
  - `test_settings_window_hotkeys_presets_checkboxes_custom_slots_and_conflicts` içinde Windows'a özgü `Win+Ctrl+Space` sistem kısayolu çakışma uyarısının (`QMessageBox.warning`) `offscreen` çalıştırmada engellenmesi için onay diyaloğu sahtelendi ve `test_overlay_focus_loss_initial_category_ipc_and_conflict_confirm` içinde `launch_gui` `QTimer` çıkışı `app.exec` sarmalayıcısına alındı.
  - `test_web_ui.py` ve `test_mode_parity.py` içindeki uzun JavaScript VM doğrulamaları Windows `CreateProcess` `32.767` karakter komut satırı sınırına (`WinError 206`) takılmamak için geçici `.js` dosyası üzerinden çalıştırıldı.
- **İmzalı Windows İkilisi & PWA Önbelleği:** İmzalı Windows x64 `qtp.exe` (`2.4.3.0`, `CN=Murat Sönmez`, RFC 3161 zaman damgalı) güncellendi ve `qtp/sw.js` önbellek adı `qtp-pwa-cache-v3.5.4` olarak artırıldı.

## [2.4.2] - 2026-11-24

### Web Arayüzü, Tasarım Sistemi ve Görünüm Tutarlılığı
- **Çevrimdışı Derlenmiş Tailwind CSS v3.4.19 (`theme.css`):** `qtp.html` yerleşim, esnek/ızgara düzen, boşluk, tipografi ve duyarlı stilleri elle yazılmış ~1.400 satırlık `@media` kurallarından sıfır CDN ve sıfır `!important` içeren gerçek derlenmiş Tailwind CSS (`theme.css`, Light/Dark `:root` renk değişkenleri korunarak) altyapısına geçirildi ve `qtp/theme.css` ile bayt-özdeş eşitlendi.
- **4 px Boşluk Ölçeği ve Kalıcı Yoğunluk Tercihi (`compact` / `default` / `metro`):** `qtp_ui_density_v1` anahtarıyla tüm 3 web görünümünde (`qtp.html`, `index.html`, `legacy/cevaplar.html`) Sıkı (`compact`), Standart (`default`) ve Rahat (`metro`) yoğunluk kipleri ile tek tip kontrol yüksekliği standartlaştırıldı; mobil (`320×568`) başlık katlanması ve kompakt alt çubuk düzenlendi.
- **Kart Eylem Düğmeleri ve 3 Bölümlü Pencereler:** Grid görünümündeki `.row-actions` kesilmesi giderildi; tüm modal pencereler sabit başlık / kaydırılabilir gövde / sabit alt çubuk düzenine geçirildi, `toast` üzerine `pointer-events-none` eklendi ve masaüstü/mobil tüm görünümlerde Chromium ve Firefox Playwright Ata-Kırpma / `elementFromPoint` denetimleri sıfır hata ile doğrulandı.
- **Klasik PWA Önbellek Güncellemesi:** `qtp/sw.js` önbellek adı `qtp-pwa-cache-v3.5.3` olarak güncellendi.

## [2.4.1] - 2026-11-24

### Linux/KDE Wayland Katman Davranışı, KDE Kısayol Çakışma Algılama & Yüksek Yoğunluklu Spotlight Web/GUI Arayüzü
- **Odak Kaybında Otomatik Gizlenme (`core/settings.py`, `ui/overlay.py`, `ui/settings_window.py`, `main.py`):**
  - `hide_on_blur: true` varsayılan ayarı ve **Ayarlar → Genel** altında *"Odağı kaybedince katmanı otomatik gizle"* kutusu eklendi; katman dışındaki bir pencereye tıklandığında `90 ms` gecikmeli etkin pencere denetimiyle otomatik gizlenir (iç iletişim kutuları, bağlam menüleri, sürükle/boyutlandır ve `0.25 s` açılış koruma süresi hariç).
- **Yinelemeli Tetiklemede Daima Üstte Kalma & Wayland `XDG_ACTIVATION_TOKEN` (`main.py`, `ui/overlay.py`, `core/paster.py`):**
  - `SingleInstanceGuard` ikinci örnekten gelen `XDG_ACTIVATION_TOKEN` belirtecini JSON `{"cmd": "SHOW", "activation_token": ...}` IPC yüküyle canlı sürece iletir; `show_overlay()` `WindowStaysOnTopHint` bayrağını koruyarak görünür ama etkin olmayan pencereyi gizle+yeniden göster akışıyla ve `requestActivate()` + Win32 `bring_window_to_top()` ile en öne taşır.
- **Açılış & Genel Tetiklemede Deterministik `"ALL"` Kategorisi (`main.py`):**
  - Eski `last_category: "Z"` / `last_category_by_hotkey.all` kalıntılarını göz ardı ederek ilk başlatmada (`--category` verilmedikçe) ve `all` kısayolu / tepsi / IPC tetiklemelerinde katmanın daima **`ALL` (Tümü)** kategorisiyle açılması sağlandı (`A`/`Z`/`X`/`Q` kısayolları ilgili kategoriyi `force_category=True` ile deterministik açar).
- **Gerçek KDE Plasma & Linux Masaüstü Kısayol Çakışma Denetimi (`core/hotkeys.py`, `ui/settings_window.py`, `web/qtp.html`):**
  - `read_kde_global_shortcuts()` (`~/.config/kglobalshortcutsrc`, `Meta+Q = Etkinlikler` dahil) ve `_LINUX_DESKTOP_RESERVED_SHORTCUTS` (`Win+Q/W/E/D/L/V/A/S/T/G`, `Alt+F2/F4/Tab/Space`, `Ctrl+Alt+L/T/Delete`, `Ctrl+Esc`) eklendi; Ayarlar penceresinde ciddi OS/DE çakışmalarında kırmızı vurgu + kaydetme öncesi `QMessageBox.warning` onayı getirildi.
- **Yüksek Yoğunluklu Simge Öncelikli Web UI (`web/qtp.html`, `web/theme.css`, `qtp.html`, `theme.css`, `sw.js` `v3.5.1`):**
  - Masaüstünde yapay `max-height: 440px` sınırı kaldırılıp viewport dolduran tek satır Spotlight listesi (`15–20+` görünür kayıt), mobilde yatay yoğun satır düzeni (`8–12+` kayıt, `.snippet-text >= 240px`), SVG simge düğmeleri, kompakt kategori hapları ve düzenleme modalı içinde tam **Hızlı İşlemler Çubuğu** (`Kopyala`, `Yapıştır`, `Favori`, `Çoğalt`, `Yukarı/Aşağı`, `INI Göster`, `Sil`) eklendi; GUI `SnippetItemDelegate` satır yüksekliği `58 px` yapıldı.

---

## [2.4.0] - 2026-11-24

### Güvenlik, Mobil/Masaüstü Düzen Sertleştirme, Veri Koruma & Wayland İyileştirmeleri
- **`--web` CSRF, DNS Rebinding ve İstek Boyutu Koruması (`qtp_app/web.py`, `docs/SSS.md`):**
  - Tüm `/api/*` uç noktalarında `Host` (`127.0.0.1`/`localhost`/`[::1]`), `Origin` ve `Sec-Fetch-Site` (`cross-site` engelli) doğrulamaları zorunlu kılındı; çapraz köken istekleri ve `OPTIONS` preflight çağrıları HTTP `403 Forbidden` JSON yanıtıyla reddedildi.
  - `Content-Length` başlığı doğrulandı (bozuk değerde HTTP `400`, `25 MiB` üstünde HTTP `413` + `SSS.md` hata mesajı), `/manifest.webmanifest` sunucu üzerinden servis edildi ve yanıtlara `X-Content-Type-Options: nosniff`, `Referrer-Policy`, `X-Frame-Options: DENY` ve sıkı `Content-Security-Policy` başlıkları eklendi.
  - Canlı web modunda satır tıklama/Enter yalnızca tarayıcı panosuna kopyalamaya ayrıldı (`POST /api/copy`); aktif uygulamaya yapıştırma yalnızca açık `Yapıştır` düğmesi üzerinden `delay_s: 3` gecikmesiyle çalışır duruma getirildi. `/api/revision` yanıtına `warning` alanı eklendi.
- **Veri Dirilişi & Git Kirliliği Koruması (`core/engine.py`, `core/json_store.py`, `core/watcher.py`, `core/settings.py`, `qtp/.gitignore`):**
  - `engine.reload_data()` içinde diskteki `QuickTextPaste.ini` veya `data.json` boş ya da bozuksa 527 gömülü varsayılanın kullanıcı verisi üzerine diriltilmesi engellendi; bozuk açılışta bir kez `corrupt_load` yedeği alınıp tüm arayüzlerde `startup_warning` bildirildi.
  - `save_data_json` bayt-eşitliği kontrolleriyle gereksiz yazımları atladı; `compute_file_fingerprint` 1 MB SHA-256 öncesinde `(mtime_ns, size)` kısa devre kontrolü ekledi; `window_size` alt sınırı `560×400` ile eşitlendi; `.qtp_history.json` `.gitignore` içine eklendi; GUI/Web/Engine/CLI/TUI arasında `"Notlar"` filtresi `is_note_item()` (`not keys` veya `[DAHİLİ NOT]`) ile hizalandı.
- **320 px–1920 px Web & Klasik PWA Duyarlılığı (`web/qtp.html`, `web/theme.css`, `qtp/index.html`, `qtp/legacy/cevaplar.html`, `sw.js` `v3.5.0`):**
  - `.overlay-card` ve klasik konteynerlerde `min-width: 0; overflow-x: clip`, sarmalanan `#categoryPills`, `minmax(min(290px, 100%), 1fr)` kart ızgarası, `<details>` tabanlı kompakt araçlar menüsü, satır içi `.row-more`, sabit konumlu açılır menüler (`fixed inset-x-3`), `16px` mobil girdiler (`autofocus` kaldırıldı) ve `>= 36px` dokunma hedefleri uygulandı.
  - `renderList` sessiz 200 satır sınırı kaldırılarak `100` adımlı artımlı `Daha Fazla Göster` + tam `beforeprint` yazdırma, tam filtreli `Tümünü Seç`, DOM yamalı satır güncellemeleri, index sıfırlamayan `loadItems`, Türkçe `Intl.Collator('tr')` sıralaması ve odak korumalı `aria-modal` iletişim kutuları getirildi.
- **PyQt6 Masaüstü Esnekliği, Performans & Wayland Deneyimi (`ui/flow_layout.py`, `ui/overlay.py`, `ui/tray.py`, `ui/icons.py`, `ui/help_dialog.py`, `ui/settings_window.py`, `main.py`):**
  - `FlowLayout` ile haplar, araç çubukları, grup satırları, ayar kısayol satırları ve yedekleme düğmeleri `560 px` altına kadar taşmadan akar; `< 640 px` genişlikte ikincil düğmeler `⋯` menüsüne katlanır, alt ipucu `ElideRight` ile kırpılır, tüm 7 iletişim kutusu yeniden boyutlandırılabilir.
  - Hayalet kopyala tıklama alanı (`mousePressEvent` durum yakalama + `grid_mode` boş `copy_button_rect`), ızgarada `Movement.Static`, Wayland/offscreen `raise_()` bastırma + `requestActivate()`, 400 ms gecikmeli pencere boyutu kaydı, yapıştırma/uyarı bildirimleri (`notify()`), Plasma Wayland tek-tık `Trigger` tepsi aç/kapat, HiDPI SVG DPR ölçekleme, Markdown bağlantı dönüşümü, macOS Cocoa `Ctrl`/`Meta` ayrımı ve 6 katmanlı önbellekli `paintEvent` gölge ile LRU belge/yazıtipi önbelleği uygulandı.
- **TUI Ekran & Geniş Karakter Sertleştirmesi (`tui/app.py`):**
  - `display_width()` ve `clip_to_width()` ile emoji/CJK genişliği ve birleştirme karakterleri hesaba katılarak tüm satırlar terminal genişliğine kırpıldı, `inner_w < 100` / taşma durumunda kompakt kategori çubuğuna geçildi, `ESCDELAY=25` ve `KEY_RESIZE` eklendi.

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
