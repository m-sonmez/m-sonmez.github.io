# QTP Kurulum ve Sistem Gereksinimleri

**QTP (QuickTextPaste / Hazır Cevaplar)**, üçüncü parti `QuickTextPaste.exe` veya herhangi bir sistem kurucusu (installer) gerektirmeyen, tek dosya olarak çalışan taşınabilir bir masaüstü uygulamasıdır. Yönetici yetkisi, kayıt defteri değişikliği veya `PATH` düzenlemesi gerektirmez.

---

## 1. Doğrudan İndirme / Canlı GitHub Pages Bağlantıları ve İkili Matris

- **Canlı Web Arayüzü:** `https://m-sonmez.github.io/qtp/` (`index.html`, `--web` ile birebir, sıfır arka uçla statik çalışır)
- **Windows (Win 10/11 x64 birincil):** `https://m-sonmez.github.io/qtp/qtp.exe` *(Win 7/8/8.1 x64 için `python -m qtp_app.build.build_windows_legacy` ile `qtp-win7.exe` üretin)*
- **Linux x64:** `https://m-sonmez.github.io/qtp/qtp.bin`
- **Eski 3. Parti QuickTextPaste Sayfası:** `https://m-sonmez.github.io/qtp/old.html`

| İşletim Sistemi | Hedef Çıktı | Mimari / Sürüm | Desteklenen Modlar ve Öne Çıkan Özellikler |
| :--- | :--- | :--- | :--- |
| **Windows 10 / 11** | `dist/qtp.exe` | Windows 10/11 (x64), Python 3.12 + PyQt6 | Tüm 4 mod (`--gui`, `--tui`, `--cli`, `--web`), yerel Win32 `RegisterHotKey` (çakışmasız `Win+Alt+*`), ata süreç zincirli UTF-8 konsol eki, canlı `ConfigFileWatcher` |
| **Windows 7 / 8 / 8.1** | `dist/qtp-win7.exe` | Windows 7 SP1 / 8 / 8.1 (x64), Python 3.8 hedefi | `build_windows_legacy` + `requirements-win7.txt`; `MOD_NOREPEAT` destekli Win32 `RegisterHotKey` + Win32 Console API TUI geri dönüşü |
| **Linux** | `dist/qtp.bin` | Ubuntu 20.04+/22.04+/24.04, Debian 10+/11/12, Fedora, Arch (x64/arm64) | X11 (`libX11` / Qt / OSC-52) ve Wayland (`wtype` / `ydotool`); Alpine/musl için PyQt6 gerektirmeyen `--cli`/`--tui`/`--web` çalışma zamanı |
| **macOS** | `dist/qtp.bin` | macOS 10.15 – 15 (x86_64, arm64, `universal2`) | `MACOSX_DEPLOYMENT_TARGET` desteği, bozucu `strip` olmadan ad-hoc `codesign`, `NSPasteboardTypeString` → `NSStringPboardType` → `pbcopy` + `osascript` |
| **Unix-like / BSD** | Kaynak / `qtp.bin` | FreeBSD, OpenBSD, NetBSD, illumos/SunOS | Genel POSIX algılama, `libX11.so` + `$XDG_CONFIG_HOME` / `~/.config/qtp` geri dönüşü, `curses` yoksa `termios`/düz metin TUI geri dönüşü |

---

## 2. İşletim Sistemine Göre Çalıştırma Adımları

### 2.1 Windows (`qtp.exe`)
1. `qtp.exe` dosyasını yazılabilir herhangi bir klasöre kopyalayın (isteğe bağlı olarak mevcut `QuickTextPaste.ini` / `data.json` dosyanızı yanına koyun).
2. Çift tıklayın (SmartScreen çıkarsa **Ek bilgi** → **Yine de çalıştır**).
3. Sağ altta *"QTP hazır. Win+Alt+Space / Win+Alt+A / Win+Alt+Z / Win+Alt+X / Win+Alt+Q"* bildirimi görünür; `RegisterHotKey` basılan kısayolları Windows kabuğuna sızdırmadan tüketir.
4. PowerShell'de sekme tamamlama için:
   ```powershell
   .\qtp.exe --completion powershell | Out-String | Invoke-Expression
   ```

### 2.2 Linux — X11 ve Wayland (`qtp.bin`)
1. `chmod +x qtp.bin && ./qtp.bin` komutunu çalıştırın (X11'de harici `xclip`/`xsel`/`xdotool` gerekmez; Wayland'da isteğe bağlı `wtype` veya `ydotool` kullanılabilir).
2. Bash/Zsh/Fish otomatik tamamlama için `./qtp.bin --completion bash|zsh|fish` çıktısını kabuk profilinize ekleyin.

### 2.3 macOS 10.15–15 ve Unix-benzeri / BSD (`qtp.bin`)
- **macOS:** `chmod +x qtp.bin && xattr -d com.apple.quarantine qtp.bin`, ardından **Sistem Ayarları → Gizlilik ve Güvenlik → Erişilebilirlik** altından `qtp.bin` uygulamasına izin verin. `Win+Shift+Q` yerine önerilen veya `function_keys` (`Ctrl+Shift+F1–F5`) profilini seçebilirsiniz.
- **BSD:** Python 3.8+ ile tüm başsız modlar (`--cli`, `--tui`, `--web`) doğrudan çalışır.

---

## 3. Taşınabilir Konumlar, Kaldırma ve Kaynak Koddan Derleme

- İkili yanındaki klasör yazılabilirse `qtp_settings.json`, `qtp.log*`, `qtp.lock`, `QuickTextPaste.ini`, `data.json` ve `backups/` burada tutulur; salt-okunursa Windows'ta `%APPDATA%\QTP\`, Linux/BSD'de `~/.config/qtp/`, macOS'ta `~/Library/Application Support/QTP/` kullanılır.
- Kaldırmak için tepsi → **Çıkış** sonrası dosyaları silmeniz yeterlidir (kayıt defterine yazılmaz).
- Derleme:
  ```bash
  pip install -r requirements-dev.txt
  pytest -q --cov=qtp_app.core --cov=qtp_app.ui.search --cov=qtp_app.tui --cov=qtp_app.web --cov=qtp_app.cli --cov-report=term-missing --cov-fail-under=90
  python -m qtp_app.build.build_windows   # Windows 7 için: build_windows_legacy | Unix için: build_unix
  ```
