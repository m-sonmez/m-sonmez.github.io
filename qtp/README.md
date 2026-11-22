# QTP — QuickTextPaste & Hazır Cevaplar Full-Stack Yöneticisi

[![QTP Full-Stack CI](https://github.com/m-sonmez/qtp/actions/workflows/ci.yml/badge.svg)](https://github.com/m-sonmez/qtp/actions/workflows/ci.yml)

**QuickTextPaste** (`QuickTextPaste.ini`) ve **`data.json`** dosyalarını ister doğrudan tarayıcıda ([`https://m-sonmez.github.io/qtp`](https://m-sonmez.github.io/qtp)), ister yerel Full-Stack Web/API sunucusuyla, ister Python Tkinter masaüstü uygulamasıyla tam uyum içinde düzenlemenizi, ekleme/çıkarma yapmanızı ve yedeklemenizi sağlayan çok arayüzlü yönetim aracıdır.

> **Önemli Gereksinim:** Windows üzerinde sistem geneli kısayolların (`L-Win+Z` vb.) çalışması ve uygulamanın tam verimle kullanılması için **QuickTextPaste** uygulamasının bilgisayarınızda kurulu ve sistem tepsisinde çalışıyor olması gerekir.

---

## Öne Çıkan Özellikler

- **GitHub Pages Üzerinden Kurulumsuz Yerel Düzenleme (`https://m-sonmez.github.io/qtp`):**
  - Sunucuya hiçbir veri göndermeden kendi `QuickTextPaste.ini`, `data.json` veya tam yedek (`qtp-tam-yedek-*.json`) dosyanızı tarayıcıda açın.
  - **Doğrudan Disk Üzerine Kaydetme (Chrome / Edge File System Access API):** `🔗 Diskten Aç` ile yerel `QuickTextPaste.ini` dosyanızı açıp düzenledikten sonra `Ctrl+S` / `💾 Üzerine Kaydet` ile doğrudan aynı dosyanın üzerine (UTF-16 LE BOM dahil) yazın.
  - Sürükle-bırak, çoklu dosya birleştirme, `QTP Panoya Kopyala`, anlık IndexedDB yedek geçmişi (son 15 sürüm) ve çevrimdışı PWA desteği (`sw.js` + `manifest.webmanifest`).
- **Full-Stack Yerel Python Sunucusu & REST API (`qtp_server.py`):**
  - Web arayüzü ile yerel disk (`data.json` + `QuickTextPaste.ini`), `backups/` klasörü ve `QuickTextPaste_x64_p.exe` arasında gerçek zamanlı köprü kurar.
  - İsteğe bağlı olarak GitHub Pages (`https://m-sonmez.github.io/qtp`) üzerinden de `127.0.0.1:8765` yerel köprüsüne bağlanabilir.
- **Python Masaüstü Arayüzü (`qtp_manager.py`):**
  - Çoklu seçim, toplu düzenleme, grup yeniden adlandırma, `QuickTextPaste` canlı durum rozeti, tek tıkla **QTP'ye Uygula & Yeniden Başlat**, Word (`.docx` / `.doc`) ve tam yedek desteği.
- **Kayıpsız `QuickTextPaste.ini` Dönüştürücü (`qtp_core.py` & `index.html`):**
  - **Otomatik Kodlama Algılama:** UTF-16 LE BOM, UTF-16 BE BOM, BOM'suz UTF-16, UTF-8 BOM, UTF-8 ve Türkçe Windows-1254 (`cp1254`).
  - Kullanıcının yüklediği `.ini` dosyasındaki tüm `[Program]` ayarlarını (`WinRC`, `lng`, `start_tray`, `m_show_tree` vb.), ek INI bölümlerini ve iç içe `/` alt menü gruplarını kayıpsız korur.

---

## QuickTextPaste Kurulumu ve Çalıştırılması

Yerel başlatıcılar (`baslat.bat`, `baslat.sh`, `kurulum.ps1`) QuickTextPaste'in kurulu ve çalışıyor olup olmadığını otomatik kontrol eder; eksikse resmi **SoftwareOK** adresinden indirip kurar ve `-bg` parametresiyle sistem tepsisinde başlatır:

1. **Otomatik Tek Satır PowerShell (Windows):**
   ```powershell
   irm https://m-sonmez.github.io/qtp/kurulum.ps1 | iex
   ```
2. **Manuel Resmi Taşınabilir İndirme:**
   - 64-bit: [QuickTextPaste_x64_Portable.zip](https://www.softwareok.com/Download/QuickTextPaste_x64_Portable.zip)
   - 32-bit: [QuickTextPaste_Portable.zip](https://www.softwareok.com/Download/QuickTextPaste_Portable.zip)
   - Resmi Sayfa: [SoftwareOK QuickTextPaste](https://www.softwareok.com/?Download=QuickTextPaste)

> **Taşınabilir Mod İpucu:** `QuickTextPaste_x64_p.exe` ile aynı klasörde `QuickTextPaste.ini` dosyası bulunduğunda program tüm kısayol ve ayarları otomatik olarak o `.ini` dosyasından okur.

---

## Yerel Full-Stack Kullanım

### Windows (`baslat.bat`)
```bat
baslat.bat          :: QuickTextPaste'i kurar/başlatır + Full-Stack Web/API sunucusunu açar (http://127.0.0.1:8765)
baslat.bat gui      :: QuickTextPaste'i kurar/başlatır + Python Tkinter masaüstü uygulamasını açar
baslat.bat qtp      :: Yalnızca QuickTextPaste kurulumunu ve başlatılmasını doğrular
baslat.bat check    :: Kurulu dosyalar ve çalışan QuickTextPaste durumunu JSON olarak gösterir
```

### Linux / macOS / Git Bash / WSL (`baslat.sh`)
```bash
./baslat.sh         # Full-Stack Web/API sunucusunu başlatır (Windows Bash/WSL'de QuickTextPaste'i de başlatır)
./baslat.sh gui     # Python Tkinter masaüstü arayüzünü başlatır
./baslat.sh sync    # data.json ve QuickTextPaste.ini dosyalarını disk üzerinde senkronize eder
./baslat.sh check   # Sistem ve QuickTextPaste durumunu kontrol eder
```

### Python CLI (`qtp_server.py`)
```bash
python qtp_server.py --ensure-qtp --open-browser
python qtp_server.py --status
python qtp_server.py --sync
```

---

## Dosya Yapısı

| Dosya | Açıklama |
| --- | --- |
| `index.html` | Ana Web / PWA düzenleme, yedekleme ve GitHub Pages yönetim paneli |
| `cevaplar.html` | Hafif hızlı arama ve tek tıkla kopyalama panosu (`.ini` & `.json` destekli) |
| `manifest.webmanifest`, `sw.js`, `icon*` | Çevrimdışı PWA kurulum ve önbellek bileşenleri |
| `qtp_core.py` | Ortak INI/JSON dönüştürücü, yedekleme ve QuickTextPaste yaşam döngüsü çekirdeği |
| `qtp_server.py` | Full-Stack statik + REST API sunucusu (`127.0.0.1:8765`, CORS & PNA destekli) |
| `qtp_manager.py` | Python Tkinter masaüstü yönetim uygulaması |
| `baslat.bat`, `baslat.sh`, `kurulum.ps1` | Windows Batch, Bash ve PowerShell kurulum/başlatma betikleri |
| `data.json`, `QuickTextPaste.ini` | Örnek 73 hazır cevap ve senkronize QTP INI dosyası |
| `tests/test_qtp.py` | Birim, INI/JSON döngü ve Full-Stack HTTP API testleri |

---

## GitHub ve GitHub Pages Yayını

1. Depoyu GitHub'a (`https://github.com/m-sonmez/qtp`) yükleyin:
   ```bash
   git init -b main
   git add .
   git commit -m "Initial commit: QTP full-stack manager and PWA"
   git remote add origin https://github.com/m-sonmez/qtp.git
   git push -u origin main
   ```
2. GitHub depo ayarlarından **Settings → Pages → Build and deployment**:
   - **Source:** `Deploy from a branch`
   - **Branch:** `main` / `/ (root)` seçin.
3. Kısa süre içinde uygulama **`https://m-sonmez.github.io/qtp`** adresinden yayına alınacaktır.

---

## Testleri Çalıştırma

```bash
python -m unittest discover -s tests -v
```

---

## Notlar ve Telif

- Bu projedeki yönetim arayüzü ve dönüştürme araçları açık kaynaklıdır.
- **QuickTextPaste**, Nenad Hrg ([SoftwareOK.com](https://www.softwareok.com/?Download=QuickTextPaste)) tarafından geliştirilen ücretsiz bir Windows yardımcı programıdır.
