# QTP Kurulum ve Sistem Gereksinimleri

**QTP (QuickTextPaste / Hazır Cevaplar)**, üçüncü parti `QuickTextPaste.exe` veya herhangi bir sistem kurucusu (installer) gerektirmeyen, tek dosya olarak çalışan taşınabilir bir masaüstü uygulamasıdır. Yönetici yetkisi, kayıt defteri değişikliği veya `PATH` düzenlemesi gerektirmez.

---

## 1. İkili Dosyalar ve İşletim Sistemi Geriye Dönük Uyumluluk Matrisi

| İşletim Sistemi | Hedef Çıktı | Mimari / Sürüm | Desteklenen Modlar ve Öne Çıkan Özellikler |
| :--- | :--- | :--- | :--- |
| **Windows 10 / 11** | `dist/qtp.exe` | Windows 10/11 (x64), Python 3.12 + PyQt6 | Tüm 4 mod (`--gui`, `--tui`, `--cli`, `--web`), VT100/Win32 konsol, çift tık taşınabilir tek dosya |
| **Windows 7 / 8 / 8.1** | `dist/qtp-win7.exe` | Windows 7 SP1 / 8 / 8.1 (x64), Python 3.8 hedefi | `build_windows_legacy` + `requirements-win7.txt`; TUI'de raw ANSI yerine otomatik Win32 Console API geri dönüşü (`SetConsoleMode` başarısızlığında bozuk kaçış karakteri basılmaz); Python 3.9+ ve Qt6 üst akışta Win7 çekirdek ABI desteğini kaldırdığı için `--tui`/`--cli`/`--web` odaklıdır (isteğe bağlı `PyQt5==5.15.10`) |
| **Linux** | `dist/qtp.bin` | Ubuntu 20.04+/22.04+/24.04, Debian 10+/11/12, Fedora, Arch (x64/arm64) | X11 (`libX11` / Qt / OSC-52) ve Wayland (`wtype` / `ydotool`); Alpine/musl için PyQt6 gerektirmeyen `--cli`/`--tui`/`--web` çalışma zamanı |
| **macOS** | `dist/qtp.bin` | macOS 10.15 – 15 (x86_64, arm64, `universal2`) | `MACOSX_DEPLOYMENT_TARGET` desteği, bozucu `strip` olmadan ad-hoc `codesign`, `NSPasteboardTypeString` → `NSStringPboardType` → `pbcopy` + `osascript` |
| **Unix-like / BSD** | Kaynak / `qtp.bin` | FreeBSD, OpenBSD, NetBSD, illumos/SunOS | Genel POSIX algılama, `libX11.so` + `$XDG_CONFIG_HOME` / `~/.config/qtp` geri dönüşü, `curses` yoksa veya `TERM=dumb` ise `termios`/düz metin TUI geri dönüşü |

> **Önemli Windows 7 / 8 / 8.1 ABI Notu:** Üst akış Python 3.9+ ve Qt6/PyQt6, Windows 7/8/8.1 sistem API'lerini resmi olarak sonlandırmıştır. Bu nedenle birincil `dist/qtp.exe` Windows 10/11 (x64) hedefler; Windows 7 SP1 / 8 / 8.1 (x64) makineler için `requirements-win7.txt` ve `python -m qtp_app.build.build_windows_legacy` komutuyla **Python 3.8 x64** üzerinde `dist/qtp-win7.exe` üretilir.

### 1.1 Windows 7 / 8 / 8.1 (`qtp-win7.exe`) Özel Derleme

```cmd
py -3.8 -m venv .venv_win7
.venv_win7\Scripts\activate
pip install -r requirements-win7.txt
python -m qtp_app.build.build_windows_legacy
```

---

## 2. İşletim Sistemine Göre Çalıştırma Adımları

### 2.1 Windows (`qtp.exe`)

1. `qtp.exe` dosyasını yazılabilir herhangi bir klasöre (örneğin `C:\Araclar\QTP\` veya Masaüstü/Belgeler altındaki bir klasöre) kopyalayın.
2. İsteğe bağlı olarak mevcut `QuickTextPaste.ini` ve/veya `data.json` dosyanızı `qtp.exe` ile **aynı klasöre** yerleştirin. Dosya yoksa QTP gömülü varsayılan 527 hazır cevabı otomatik yükler.
3. `qtp.exe` dosyasına çift tıklayın.
4. **Windows Defender SmartScreen Uyarısı (İlk Çalıştırma):** İmzalanmamış taşınabilir ikili dosyalar için Windows ilk açılışta *"Windows bilgisayarınızı korudu"* penceresi gösterebilir. Çalıştırmak için **Ek bilgi** → **Yine de çalıştır** bağlantısına tıklayın.
5. Açılışta sağ altta *"QTP hazır. Win+Z / Win+A / Win+X / Win+Q"* bildirimi görünür ve uygulama sistem tepsisine yerleşir.

### 2.2 Linux — X11 (`qtp.bin`)

1. `qtp.bin` dosyasını istediğiniz klasöre (örneğin `~/Uygulamalar/qtp/`) taşıyın.
2. Çalıştırma izni verin ve başlatın:
   ```bash
   chmod +x qtp.bin
   ./qtp.bin
   ```
3. **Sıfır Harici Paket (X11):** QTP; X11 oturumunda `libX11`, Qt panosu veya etkileşimli terminalde OSC 52 kullanarak pano ve odak geri yüklemeyi harici `xclip`, `xsel`, `xdotool` veya `wmctrl` paketlerine ihtiyaç duymadan yerel olarak gerçekleştirir.
4. **GNOME Sistem Tepsisi Notu:** GNOME masaüstü ortamında sistem tepsisi simgesini görmek için `AppIndicator and KStatusNotifierItem Support` uzantısının etkin olması gerekir.

### 2.3 Linux — Wayland (`qtp.bin`)

Wayland güvenlik modeli nedeniyle uygulamalar arası yapay tuş basımı (`Ctrl+V` / `Enter`) için compositor desteği gerekir:

1. `wtype` (Sway, Hyprland, wlroots tabanlı ortamlar) veya `ydotool` (GNOME / KDE Wayland) kurun:
   ```bash
   # wlroots / Sway / Hyprland
   sudo apt install wtype   # veya: sudo pacman -S wtype
   # Genel Wayland (ydotoold servisi ile)
   sudo apt install ydotool
   ```
2. `qtp.bin` dosyasına izin verip başlatın:
   ```bash
   chmod +x qtp.bin
   ./qtp.bin
   ```
3. `wtype` veya `ydotool` yoksa QTP günlüğe uyarı yazar ve `pynput` (XWayland/Xlib) geri dönüşünü dener; XWayland dışındaki pencerelere yapıştırma için metin panoya kopyalanmış olarak hazır tutulur.

### 2.4 macOS 10.15–15 (`qtp.bin`)

1. `qtp.bin` dosyasını `/Applications` veya `~/Applications/QTP/` gibi bir klasöre koyun (`MACOSX_DEPLOYMENT_TARGET` varsayılan `11.0`, `x86_64` / `arm64` / `universal2` derleme bayrağıyla özelleştirilebilir).
2. Terminal üzerinden çalıştırma izni verin:
   ```bash
   chmod +x qtp.bin
   ```
3. **Gatekeeper Uyarısı (Ad-Hoc İmzalı İkili):** İndirilen dosyada karantina özniteliği varsa ilk açılışta *"geliştiricisi doğrulanamadığı için açılamıyor"* uyarısı çıkabilir. Kaldırmak için:
   ```bash
   xattr -d com.apple.quarantine qtp.bin
   ./qtp.bin
   ```
   Alternatif olarak **Sistem Ayarları → Gizlilik ve Güvenlik** altından *"Yine de Aç"* düğmesini kullanabilirsiniz.
4. **Erişilebilirlik (Accessibility) İzni — Zorunlu:** Global kısayolların (`Win/Cmd+A/Z/X/Q`, `Ctrl+Shift+Space`) ve otomatik `Cmd+V` yapıştırmanın çalışması için macOS sizden izin ister:
   - **Sistem Ayarları → Gizlilik ve Güvenlik → Erişilebilirlik** menüsünü açın.
   - Kilidi açın ve `+` düğmesiyle `qtp.bin` (veya Terminal üzerinden çalıştırıyorsanız Terminal/iTerm) uygulamasını listeye ekleyip anahtarı **Açık** konuma getirin.
   - Uygulamayı yeniden başlatın.

### 2.5 Unix-benzeri / BSD (FreeBSD, OpenBSD, NetBSD)

1. Python 3.8+ ile (PyQt6 kurulu değilse `--cli`, `--tui`, `--web` modları tam çalışır) doğrudan çalıştırın veya `python3 -m qtp_app.build.build_unix` ile tek dosya ikili oluşturun.
2. X11 panosu için `libX11.so` / `libX11.so.6`, Wayland için `wtype`/`ydotool`, yapılandırma için `$XDG_CONFIG_HOME/qtp` (`~/.config/qtp`) otomatik kullanılır; `curses` modülü veya `terminfo` yoksa `--tui` otomatik `termios`/düz metin moduna geçer.

---

## 3. Ayar, Günlük ve Veri Dosyalarının Konumu

QTP **taşınabilir-öncelikli** çalışır: ikili dosyanın bulunduğu klasör yazılabilirse tüm dosyalar doğrudan ikilinin yanında tutulur. Klasör salt-okunursa (örneğin `/usr/local/bin` veya `C:\Program Files`) işletim sistemine özgü kullanıcı dizinine düşer:

| Dosya | Taşınabilir Konum (Varsayılan) | Salt-Okunur Geri Dönüş (Windows) | Salt-Okunur Geri Dönüş (Linux) | Salt-Okunur Geri Dönüş (macOS) |
| :--- | :--- | :--- | :--- | :--- |
| `qtp_settings.json` | İkili dosyanın yanı | `%APPDATA%\QTP\qtp_settings.json` | `~/.config/qtp/qtp_settings.json` | `~/Library/Application Support/QTP/qtp_settings.json` |
| `qtp.log` (1 MB × 3) | İkili dosyanın yanı | `%APPDATA%\QTP\qtp.log` | `~/.config/qtp/qtp.log` | `~/Library/Application Support/QTP/qtp.log` |
| `qtp.lock` | İkili dosyanın yanı | `%APPDATA%\QTP\qtp.lock` | `~/.config/qtp/qtp.lock` | `~/Library/Application Support/QTP/qtp.lock` |
| `QuickTextPaste.ini` | `./QuickTextPaste.ini` | Ayardaki `data_path` yolu | Ayardaki `data_path` yolu | Ayardaki `data_path` yolu |
| `data.json` | Çalışma dizini | Çalışma dizini | Çalışma dizini | Çalışma dizini |
| `backups/` | Çalışma dizini | Çalışma dizini | Çalışma dizini | Çalışma dizini |

---

## 4. Kaldırma

QTP sisteminize hiçbir servis, sürücü veya kayıt defteri girdisi kurmaz:

1. Sistem tepsisinden **Çıkış** seçeneği ile uygulamayı kapatın.
2. `qtp.exe` (veya `qtp.bin`) dosyasını, `qtp_settings.json`, `qtp.log*`, `qtp.lock` ve isteğe bağlı `backups/` klasörünü silin.
3. Salt-okunur geri dönüş dizini kullanıldıysa yukarıdaki tablodaki ilgili klasörü de silebilirsiniz.

---

## 5. Kaynak Koddan Derleme

Python **3.10 veya üzeri** (tam GUI ve birincil `qtp.exe`/`qtp.bin` için `3.12` önerilir; başsız `--cli`/`--tui`/`--web` ve Windows 7 `qtp-win7.exe` derlemesi **Python 3.8+** destekler) gereklidir:

```bash
# 1. Sanal ortam oluşturun ve etkinleştirin
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate

# 2. Bağımlılıkları yükleyin
pip install --upgrade pip
pip install -r requirements-dev.txt

# 3. Testleri çalıştırın
pytest -q --cov=qtp_app/core --cov=qtp_app/ui/search --cov-report=term-missing

# 4. Hedef platform ikilisini üretin
# Windows:
python -m qtp_app.build.build_windows
# Linux / macOS:
python -m qtp_app.build.build_unix
```

Üretilen dosya `dist/qtp.exe` (Windows) veya `dist/qtp.bin` (Linux/macOS) konumunda oluşur ve derleme sonunda `--selftest` ile otomatik doğrulanır.

---

## 6. Sıfır Bağımlılık Kanıtı ve İşletim Sistemi Notları

QTP ikili dosyaları **tek başına kopyalanarak** boş bir klasörde çalışacak şekilde tasarlanmıştır:

- **İkili İçinde Gömülenler:** Python 3.12 çalışma zamanı, PyQt6 + Qt6 kitaplıkları, `Inter` yazı tipleri, SVG/PNG simgeler, gömülü varsayılan 527 kayıt (`QuickTextPaste.ini` ve `data.json`), Türkçe `docs/*.md` yardım dosyaları, Windows TUI ANSI/VT100 katmanı (`_win_console.py`) ve çevrimdışı Web arayüzü (`index.html` + `theme.css`).
- **Bağımlılık OLMAYAN Araçlar:** Hedef makinede Python, Qt kurulumu, `QuickTextPaste.exe`, `xclip`, `xsel`, `xdotool`, `wmctrl`, `Homebrew` veya harici `VC++` kurucusu gerekmez.
- **İşletim Sistemine Göre Kanıt Adımları:**
  - **Windows (`qtp.exe`):** Temiz bir Windows 10/11 makinesinde boş bir klasöre yalnızca `qtp.exe` kopyalayın; çift tıkladığınızda yanına `qtp_settings.json`, `qtp.log`, `QuickTextPaste.ini` ve `data.json` oluşturulur, tepsi simgesi açılır ve `--gui`/`--tui`/`--cli`/`--web` modlarının tamamı çalışır. (`--cli`/`--tui` modları GUI alt sisteminden çalıştırıldığında `AttachConsole`/`AllocConsole` ile konsola otomatik bağlanır. Sürüm etiketlemesi öncesi Windows Sandbox / temiz VM üzerinde tekrar doğrulanmalıdır.)
  - **Linux (`qtp.bin`):** Ubuntu 22.04+ (glibc 2.35 tabanı), Ubuntu 24.04 ve Debian 12+ üzerinde yalnızca `./qtp.bin` + `chmod +x` ile çalışır (`PATH=/usr/bin:/bin` sıyrılmış temiz konteyner CI işiyle doğrulanır). *Not:* Alpine/musl ortamlarında Qt GUI yerine musl uyumlu TUI/CLI/Web çalıştırma modeli belgelenmiştir.
  - **macOS (`qtp.bin`):** macOS 12/13/14 (x64 ve arm64) üzerinde `chmod +x qtp.bin` ve `xattr -d com.apple.quarantine qtp.bin` sonrası tüm dört mod doğrudan çalışır.
- **Yalnızca İsteğe Bağlı OS Önkoşulları (Engelleyici Değil):**
  - Wayland oturumunda arka plan global kısayol/otomatik tuş basımı için isteğe bağlı `wtype` veya `ydotool` (yoksa başlangıç bloklanmaz, Türkçe uyarı basılır ve tüm 4 mod çalışır).
  - macOS global kısayolları için tek seferlik kullanıcı Erişilebilirlik izni.

