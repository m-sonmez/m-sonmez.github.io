# QTP Kurulum ve Sistem Gereksinimleri / Installation (`v2.5.0`)

QTP v2.5.0 **kurulum gerektirmez**, ek harici paket veya ayrı bir komut satırı aracına bağımlı değildir ve dört farklı çalışma kipini (`--gui`, `--tui`, `--cli`, `--web`) tek bir taşınabilir dosya veya çevrimdışı PWA web arayüzü içinde sunar. Varsayılan olarak evrensel İngilizce/Türkçe (`language: "auto"`) ve dinamik kategori/kısayol mimarisiyle çalışır.

---

## 1. Doğrudan İndirme / Canlı GitHub Pages Bağlantıları ve İkili Matris

| Platform / Dağıtım | Çıktı / Adres | Mimari / Çalışma Zamanı | Not |
| :--- | :--- | :--- | :--- |
| **Canlı PWA (Klasik QTP)** | [https://m-sonmez.github.io/qtp/](https://m-sonmez.github.io/qtp/) (`index.html`) | Tüm Modern Tarayıcılar + Çevrimdışı PWA | Klasik QuickTextPaste kılavuzu, kategorize cevaplar (`legacy/cevaplar.html`), **PWA Yükle** ve işletim sistemine özel tek-tık indirme düğmesi. |
| **Canlı Birleşik Web Arayüzü** | [https://m-sonmez.github.io/qtp/qtp.html](https://m-sonmez.github.io/qtp/qtp.html) | Tarayıcı (Statik `localStorage`) veya `--web` | `--web` sunucusuyla birebir aynı arayüz: Varsayılan **Açık (Light)** tema + Koyu geçişi, tam Cevap CRUD (`+ Yeni Cevap` / `Düzenle` / `Sil`), 6 sekmeli `F1` Yardım, **PWA Yükle** ve OS indirme düğmesi. |
| **Windows 10 / 11 (x64)** | [https://m-sonmez.github.io/qtp/qtp.exe](https://m-sonmez.github.io/qtp/qtp.exe) (`≤ 50 MB`) | Tek Dosya Taşınabilir PE64 (`console=False`) | `CompanyName = Murat Sönmez` PE sürüm bilgisi + SHA-256 Authenticode imzalı (`CN=Murat Sönmez`, RFC 3161 zaman damgalı). Çift tık ile sistem tepsisinde GUI açılır; PowerShell/cmd üzerinden `--help`, `--cli`, `--tui`, `--web` parent-console bağlantısıyla çalışır. |
| **Genel Sertifika (Windows)** | [https://m-sonmez.github.io/qtp/certs/MuratSonmez-QTP.cer](https://m-sonmez.github.io/qtp/certs/MuratSonmez-QTP.cer) | Yalnızca Ortak Anahtar (Public `.cer`) | Diğer Windows cihazlarında yayıncı güvenini tek komutta eklemek için kullanılır (özel anahtar içermez). |
| **Windows 7 / 8 / 8.1 (x64)** | `qtp-win7.exe` (kaynaktan `build_windows_legacy`) | Python 3.8 x64 + `requirements-win7.txt` | Eski Windows Console (Win32 API VT fallback) ile tam `--tui`, `--cli` ve `--web` desteği. |
| **Linux x64 (X11 & Wayland)** | [https://m-sonmez.github.io/qtp/qtp.bin](https://m-sonmez.github.io/qtp/qtp.bin) (`≤ 60 MB`) | Tek Dosya Taşınabilir ELF (Ubuntu 22.04+ / glibc 2.35+) | GitHub Actions Ubuntu derlemesi; harici sistem Python'u gerektirmez. |
| **macOS 10.15–15 / BSD** | `qtp.bin` (yerel `build_unix`) | Intel/Apple Silicon veya FreeBSD/OpenBSD | Wayland/macOS/BSD üzerinde `standalone/` altından kaynak veya yerel derleme. |

> **Akıllı OS İndirme & PWA:** Hem `qtp/index.html` hem de `qtp/qtp.html`, ziyaretçinin işletim sistemini algılayarak Windows kullanıcılarına doğrudan **`qtp.exe`**, Linux kullanıcılarına **`qtp.bin`**, macOS/BSD kullanıcılarına kaynak/kurulum yönergesi bağlantısını otomatik sunar ve **📲 PWA Yükle** ile masaüstüne kurulabilir.

---

## 2. İşletim Sistemine Göre Çalıştırma Adımları

### 2.1 Windows (`qtp.exe`)
1. [qtp.exe](https://m-sonmez.github.io/qtp/qtp.exe) dosyasını boş veya mevcut `QuickTextPaste.ini` dosyanızın bulunduğu bir klasöre indirin (`C:\QTP\qtp.exe` gibi).
2. Çift tıkladığınızda sistem tepsisinde QTP simgesi ve katmanı varsayılan **Açık (Light)** tema ile açılır. İlk çalıştırmada yanında örnek `QuickTextPaste.ini`, `data.json` ve `qtp_settings.json` yoksa otomatik oluşturulur.
3. Komut satırı (`PowerShell` veya `cmd`) üzerinden çalıştırma örnekleri:
   ```powershell
   .\qtp.exe --version
   .\qtp.exe --selftest
   .\qtp.exe --web --open-browser
   .\qtp.exe --tui
   .\qtp.exe --cli --list-items --category 1 --json
   ```
4. **Dijital İmza, PE Bilgisi ve Diğer Windows Cihazlarında Güven:**
   - `qtp.exe`, PE sürüm metadata bilgisi (`CompanyName = Murat Sönmez`) ile derlenir ve **SHA-256 + RFC 3161 zaman damgalı** Authenticode dijital imzası (`CN=Murat Sönmez`) taşır.
   - Bu imza varsayılan olarak kendinden imzalı (self-signed) bir yayıncı sertifikası kullandığından (ticari Microsoft Güvenilir Kök CA / Azure Trusted Signing sertifikasına geçilene kadar), başka bir Windows bilgisayarında Windows SmartScreen veya yayıncı uyarısı görürseniz yönetici izni gerekmeden ortak sertifikayı (`certs/MuratSonmez-QTP.cer`, özel anahtar içermez) tek seferde güvenebilirsiniz:
     ```powershell
     irm https://m-sonmez.github.io/qtp/certs/MuratSonmez-QTP.cer -OutFile MuratSonmez-QTP.cer; Import-Certificate -FilePath .\MuratSonmez-QTP.cer -CertStoreLocation Cert:\CurrentUser\Root; Import-Certificate -FilePath .\MuratSonmez-QTP.cer -CertStoreLocation Cert:\CurrentUser\TrustedPublisher
     ```
   - Alternatif olarak **Windows Gezgini** üzerinden `qtp.exe` → **Özellikler** → **Dijital İmzalar** → **Murat Sönmez** → **Ayrıntılar** → **Sertifikayı Göster** → **Sertifika Yükle** → **Geçerli Kullanıcı** → **Tüm sertifikaları aşağıdaki depoya yerleştir** → **Güvenilen Kök Sertifika Yetkilileri** adımlarını izleyebilirsiniz.
   - Ticari OV/EV veya Azure Trusted Signing `.pfx` sertifikası ile derleme için `QTP_SIGN_PFX` ve `QTP_SIGN_PFX_PASSWORD` (veya `QTP_SIGN_THUMBPRINT`) ortam değişkenleri doğrudan desteklenir.

### 2.2 Linux — X11 ve Wayland (`qtp.bin`)
1. [qtp.bin](https://m-sonmez.github.io/qtp/qtp.bin) dosyasını indirin ve çalıştırma izni verin:
   ```bash
   chmod +x ./qtp.bin
   ./qtp.bin --selftest
   ./qtp.bin --gui
   ```
2. **Sıfır Zorunlu Bağımlılık & Çoklu Dağıtım İsteğe Bağlı Yardımcılar:** `qtp.bin` ek sistem paketi olmadan doğrudan çalışır; PyInstaller ikilisi `fontconfig`, `xkbcommon`, `Mesa/EGL/GL`, `Wayland` ve `X11` gibi dağıtım yapılandırmasına bağlı kütüphaneleri bilgisayarınızdaki yerel sistemden kullandığı için **Arch/CachyOS, Ubuntu/Debian, Fedora, openSUSE** gibi modern Linux dağıtımlarında sürüm çakışması oluşturmaz (`--tui`, `--cli` ve `--web` modları ise hiçbir masaüstü kütüphanesi gerektirmeden başsız sunucularda bile çalışır).
   Çok minimal kurulumlarda `--gui` için eksik Qt/pencere kütüphanesi görürseniz veya Wayland oturumunda isteğe bağlı otomatik yapıştırma / pano yardımcıları (`wl-clipboard`, `wtype`, `ydotool`) kurmak isterseniz kendi dağıtımınızın yerel paket yöneticisini kullanın:
   - **Arch Linux / CachyOS / Manjaro (`pacman`):**
     ```bash
     # Minimal GUI kütüphaneleri (zaten çoğunlukla kurulu):
     sudo pacman -S --needed mesa libxkbcommon libxkbcommon-x11 xcb-util-cursor fontconfig dbus
     # İsteğe bağlı Wayland pano & otomatik yapıştırma yardımcıları:
     sudo pacman -S --needed wl-clipboard wtype ydotool
     ```
   - **Debian / Ubuntu / Linux Mint (`apt`):**
     ```bash
     sudo apt update && sudo apt install -y \
       libegl1 libgl1 libglx-mesa0 libxkbcommon0 libxkbcommon-x11-0 libdbus-1-3 \
       libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 \
       libxcb-render-util0 libxcb-shape0 libxcb-xinerama0 libxcb-xkb1 libxcb-xfixes0 \
       libfontconfig1 libfreetype6
     # İsteğe bağlı Wayland yardımcıları:
     sudo apt install -y wl-clipboard wtype ydotool
     ```
   - **Fedora / RHEL (`dnf`):**
     ```bash
     sudo dnf install -y mesa-libEGL mesa-libGL libxkbcommon libxkbcommon-x11 xcb-util-cursor dbus-libs fontconfig
     # İsteğe bağlı Wayland yardımcıları:
     sudo dnf install -y wl-clipboard wtype ydotool
     ```
   - **openSUSE (`zypper`):**
     ```bash
     sudo zypper install -y libEGL1 libGL1 libxkbcommon0 libxkbcommon-x11-0 libxcb-cursor0 dbus-1 fontconfig
     # İsteğe bağlı Wayland yardımcıları:
     sudo zypper install -y wl-clipboard wtype ydotool
     ```
   - **Alpine Linux (`apk`) & FreeBSD (`pkg`) & macOS (`brew`):**
     - Alpine Linux (`apk` — `--tui`/`--cli`/`--web` kaynak çalıştırma): `apk add python3 py3-pip` (Wayland masaüstü için isteğe bağlı: `apk add wl-clipboard wtype`)
     - FreeBSD (`pkg`): `pkg install python3 py311-qt6 xcb-util-cursor libxkbcommon` (veya sıfır bağımlılıkla `python3 -m qtp_app --tui`)
     - macOS (`brew`): `qtp.bin` sıfır bağımlılıkla çalışır; kaynaktan geliştirme için `brew install python uv` yeterlidir.
3. **Wayland Notu (KDE Plasma & Diğer Compositor'lar):** Wayland oturumlarında (`KDE Plasma`/`GNOME`/`Sway`/`Hyprland`) `pynput` tabanlı arka plan X11 global tuş yakalama compositor tarafından kısıtlanır; bu nedenle **Sistem Ayarları → Klavye → Kısayollar → Özel Ekle** altından doğrudan `./qtp.bin --gui` komutuna bir kısayol atayabilirsiniz (zaten çalışan QTP varsa tek-örnek IPC `SHOW` sinyali katmanı anında açar; tepsi simgesi sol tıkı da katmanı açıp kapatır). Pencere kenarından yeniden boyutlandırma/sürükleme, `--web` ve `--tui` kesintisiz çalışır. QTP önce seçili metni pencere gizlenmeden önce güvenli biçimde panoya yazar (`Ctrl+V` veya terminalde `Ctrl+Shift+V` / `--set paste_method ctrl_shift_v`; `wtype`/`ydotool` kuruluysa otomatik tuş simülasyonu da denenir).

### 2.3 macOS 10.15–15 ve Unix-benzeri / BSD (`qtp.bin`)
1. **macOS Gatekeeper & Erişilebilirlik İzni:**
   - Karantina özniteliğini kaldırmak ve çalıştırmak için:
     ```bash
     chmod +x ./qtp.bin
     xattr -d com.apple.quarantine ./qtp.bin 2>/dev/null || true
     ./qtp.bin --gui
     ```
   - Global kısayollar ve aktif pencereye otomatik yapıştırma için **Sistem Ayarları → Gizlilik ve Güvenlik → Erişilebilirlik** altından `qtp.bin` (veya Terminal) iznini etkinleştirin.
2. **FreeBSD / OpenBSD / NetBSD:**
   - Python 3.8+ ortamında `qtp/standalone/` klasöründen standart kütüphaneyle ek bağımlılık olmadan `--tui`, `--cli` ve `--web` kiplerini çalıştırabilirsiniz:
     ```bash
     cd qtp/standalone
     python3 -m qtp_app --tui
     python3 -m qtp_app --web --open-browser
     ```

---

## 3. Taşınabilir Konumlar, Kaldırma ve Kaynak Koddan Derleme

### Dizin Düzeni (`qtp/`)
- `qtp/qtp.exe` & `qtp/qtp.bin`: Kök taşınabilir yürütülebilir dosyalar.
- `qtp/certs/MuratSonmez-QTP.cer`: Yalnızca ortak anahtar içeren Authenticode yayıncı sertifikası.
- `qtp/qtp.html` & `qtp/theme.css`: Birleşik modern Web UI (Açık/Koyu tema + tam CRUD + 6 sekmeli F1 Yardım).
- `qtp/index.html`, `qtp/sw.js`, `qtp/manifest.webmanifest`: Klasik QuickTextPaste PWA.
- `qtp/legacy/`: Klasik Windows HTML/Python/PowerShell betikleri (`cevaplar.html`, `qtp_manager.py`, `qtp_core.py`, `qtp_server.py`, `kurulum.ps1`, `tests/test_qtp.py`).
- `qtp/standalone/`: Bağımsız QTP çekirdeği (`qtp_app/`), PyInstaller yapılandırmaları (`qtp_app/build/`) ve test takımı.

### Yapılandırma ve Veri Konumları
- **Taşınabilir Kip (Öncelikli):** Yürütülebilir dosyanın yanında `QuickTextPaste.ini` veya `--work-dir` varsa tüm dosyalar (`qtp_settings.json`, `data.json`, `qtp.log`, `backups/`) o klasörde tutulur. `--version`, `--help`, `--selftest` salt-okunurdur ve **hiçbir dosya oluşturmaz**.
- **Sistem Profili Yolu (Yedek):**
  - Windows: `%APPDATA%\QTP\`
  - Linux / BSD: `$XDG_CONFIG_HOME/qtp/` (varsayılan `~/.config/qtp/`)
  - macOS: `~/Library/Application Support/QTP/`

### Kaynak Koddan Geliştirme ve Derleme (`qtp/standalone/`)
```bash
cd qtp/standalone
uv venv --python 3.12 .venv
uv pip install --python .venv -r requirements-dev.txt
```
- **Windows Test & Derleme:** `make.bat test` ve `.venv\Scripts\python.exe -m qtp_app.build.build_windows`
- **Linux / macOS Test & Derleme:** `make test` ve `make build` (`qtp/standalone/dist/qtp.bin` üretir)
- **Windows 7 Legacy Derleme:** Python 3.8 x64 + `requirements-win7.txt` → `python -m qtp_app.build.build_windows_legacy`

### Tam Kaldırma
Kayıt defteri girdisi (Registry) tutulmaz. Yalnızca çalışma klasöründeki `qtp.exe` / `qtp.bin` ve isteğe bağlı `qtp_settings.json`, `backups/`, `qtp.log` dosyalarını silmeniz yeterlidir.
