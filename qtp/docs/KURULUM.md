# QTP Kurulum ve Sistem Gereksinimleri

**QTP (QuickTextPaste / Hazır Cevaplar)**, üçüncü parti `QuickTextPaste.exe` veya herhangi bir sistem kurucusu (installer) gerektirmeyen, tek dosya olarak çalışan taşınabilir bir masaüstü uygulamasıdır. Yönetici yetkisi, kayıt defteri değişikliği veya `PATH` düzenlemesi gerektirmez.

---

## 1. İkili Dosyalar ve Desteklenen Sistemler

| İşletim Sistemi | Dosya Adı | Mimari / Sürüm | Kurulum Türü |
| :--- | :--- | :--- | :--- |
| **Windows** | `qtp.exe` | Windows 10 / 11 (x64) | Taşınabilir tek dosya (kurulum gerektirmez) |
| **Linux** | `qtp.bin` | x86_64 (X11 veya Wayland) | Taşınabilir tek dosya (`chmod +x`) |
| **macOS** | `qtp.bin` | macOS 12 Monterey ve üzeri | Taşınabilir tek dosya (`chmod +x` + Erişilebilirlik izni) |

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

### 2.4 macOS 12+ (`qtp.bin`)

1. `qtp.bin` dosyasını `/Applications` veya `~/Applications/QTP/` gibi bir klasöre koyun.
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

Python **3.10 veya üzeri** (önerilen 3.12) gereklidir:

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

