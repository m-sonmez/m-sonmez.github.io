# QTP — QuickTextPaste & Hazır Cevaplar (Bağımsız Masaüstü Uygulaması)

**QTP v2.1.0**, artık üçüncü parti `QuickTextPaste.exe` dosyasına veya herhangi bir harici çalışma zamanı aracına (`xclip`, `xdotool`, `pyperclip`, Python, Qt kurulumu vb.) **hiçbir bağımlılığı olmadan**, Windows, Linux ve macOS üzerinde **dört çalışma modunun (`--gui`, `--tui`, `--cli`, `--web`) tamamında birebir özellik eşitliği** sunan **tek dosya** taşınabilir uygulamadır.

---

## Dört Mod (`--gui`, `--tui`, `--cli`, `--web`)

| Mod | Örnek Komut | Açıklama |
| :--- | :--- | :--- |
| **GUI** | `qtp --gui` (veya çift tık) | PyQt6 animasyonlu katman penceresi, global kısayollar ve sistem tepsisi |
| **TUI** | `qtp --tui` | Sıfır bağımlılıklı terminal arayüzü (`curses` / Windows ANSI katmanı) |
| **CLI** | `qtp --cli --search "şifre" --json` | Betikler ve CI için başsız alt komutlar ve kararlı çıkış kodları |
| **Web** | `qtp --web --port 8765 --open-browser` | Yalnızca `127.0.0.1` üzerinde çalışan çevrimdışı HTTP/JSON sunucusu |

Tüm modların tam karşılaştırması için: [Modlar Arası Eşitlik Matrisi](docs/KULLANIM.md#14-modlar-arası-eşitlik-matrisi)

---

## 1. Tek Dosya Uygulama (Önerilen)

- **Windows (x64):** `dist/qtp.exe` — Çift tıklayıp doğrudan çalıştırın; kurulum veya yönetici izni gerekmez.
- **Linux & macOS:** `dist/qtp.bin` — Çalıştırma izni verin (`chmod +x qtp.bin`) ve doğrudan çalıştırın.
- **Tamamen Çevrimdışı ve Taşınabilir:** Tüm ayarlar (`qtp_settings.json`), günlükler (`qtp.log`), yedekler (`backups/`) ve veri dosyaları (`QuickTextPaste.ini` / `data.json`) ikili dosyanın hemen yanında saklanır.
- **Modern Katman (Overlay) Arayüzü:** `720×520` px, yuvarlatılmış koyu/açık tema, gömülü Inter yazı tipi, 180 ms akıcı animasyonlar, kategori sekmeleri, Türkçe uyumlu bulanık arama (`FuzzyMatcher`) ve tek tuşla önceki uygulamaya yapıştırma (`<E<N<D|` işaretinde otomatik `Enter`).

---

## 2. Kısayollar

Tüm kısayollar Windows, Linux ve macOS üzerinde **birebir aynı** çalışır (macOS'ta ek olarak `⌘` eş-kısayolları da desteklenir):

| Olay | Windows | Linux | macOS | Açıklama |
| :--- | :--- | :--- | :--- | :--- |
| Tüm Kategoriler | `Ctrl+Shift+Space` | `Ctrl+Shift+Space` | `Ctrl+Shift+Space` | Katmanı tüm kategorilerle açar |
| İş Ortağı | `Win+A` | `Win+A` | `Win+A` | **A · İş Ortağı** kategorisiyle açar |
| Kurye | `Win+Z` | `Win+Z` | `Win+Z` | **Z · Kurye** kategorisiyle açar |
| Canlı Yardım | `Win+X` | `Win+X` | `Win+X` | **X · Canlı Yardım** kategorisiyle açar |
| Turkcell | `Win+Q` | `Win+Q` | `Win+Q` | **Q · Turkcell** kategorisiyle açar |
| Gezinme / Yapıştır | `↑↓` / `⏎` | `↑↓` / `⏎` | `↑↓` / `⏎` | Seçim yapar ve aktif uygulamaya yapıştırır |
| Yalnızca Kopyala | `Ctrl+⏎` | `Ctrl+⏎` | `Ctrl+⏎` / `⌘+⏎` | Katmanı kapatmadan panoya kopyalar |
| Arama / Ayar / Yardım | `Ctrl+K` / `Ctrl+,` / `F1` | `Ctrl+K` / `Ctrl+,` / `F1` | `Ctrl+K` / `Ctrl+,` / `F1` | Arama kutusu, Ayarlar ve Türkçe Yardım (`F1`) |

Ayrıntılı tablo için: [docs/KISAYOLLAR.md](docs/KISAYOLLAR.md)

---

## 3. Kurulum

İşletim sisteminize göre (Windows taşınabilir, Linux X11, Linux Wayland `wtype`/`ydotool`, macOS Gatekeeper + Erişilebilirlik izni ve salt-okunur klasör yolları) ayrıntılı kurulum adımları:  
➡️ [docs/KURULUM.md](docs/KURULUM.md)

---

## 4. Kullanım

Kategori filtreleme, Türkçe bulanık arama (`İ/i`, `I/ı`), sağ tık menüsü (`Yapıştır / Kopyala / INI'de Göster / Yardım`), sistem tepsisi menüsü, INI↔JSON dönüşümü, `.bak` yedeklemeleri ve CLI bayrakları (`--selftest`, `--version`, `--export-ini`, `--import-ini`, `--help`):  
➡️ [docs/KULLANIM.md](docs/KULLANIM.md)

---

## 5. Ayarlar (`qtp_settings.json`)

| Alan | Varsayılan | Açıklama |
| :--- | :--- | :--- |
| `theme` | `"dark"` | Renk teması (`auto`, `dark`, `light`) |
| `hotkeys` | `all`, `A`, `Z`, `X`, `Q` | Sistem geneli global kısayol haritası |
| `last_category` | `"ALL"` | Genel açılışta son seçili kategori |
| `window_size` | `[720, 520]` | Katman penceresi `[genişlik, yükseklik]` boyutu |
| `paste_method` | `"auto"` | Yapıştırma yöntemi (`auto`, `ctrl_v`, `shift_insert`, `type`) |
| `enter_after_paste` | `true` | `<E<N<D|` işaretli kayıtlardan sonra otomatik `Enter` |
| `start_minimized` | `false` | Başlangıçta katmanı göstermeden sistem tepsisinde bekle |
| `tray_icon` | `true` | Sistem tepsisi simgesini göster/gizle |
| `data_path` | `"./QuickTextPaste.ini"` | Etkin `QuickTextPaste.ini` dosya yolu |
| `backup_count` | `15` | `backups/` dizininde tutulacak yedek sayısı |
| `log_level` | `"info"` | `qtp.log` günlük düzeyi (`debug`, `info`, `warn`, `error`) |
| `language` | `"tr"` | Arayüz dili (`tr`) |

---

## 6. Sıkça Sorulan Sorular (SSS) ve Hata Mesajları

Tüm Türkçe hata mesajları, Wayland/macOS izin sorunları, `Win+*` kısayol çakışmaları ve `QuickTextPaste.ini` kodlama çözümleri:  
➡️ [docs/SSS.md](docs/SSS.md)

---

## 7. Geliştirici Rehberi

Modül mimarisi, `pytest --cov` test çalıştırma, statik çapraz platform eşitlik denetimi (`test_platform_parity.py`) ve `make` / `make.bat` derleme komutları:  
➡️ [docs/GELISTIRICI.md](docs/GELISTIRICI.md)

---

## 8. Miras / Legacy Notu

Mevcut `QuickTextPaste.ini` biçimi (`UTF-16 LE BOM`, `UTF-16 BE BOM`, `UTF-8 BOM`, `cp1254`, `[Program]`, `[list_text]`, `[list_order]`, `[list_label]`, `<E<N<D|` bitiş işaretleri) **tam ve kayıpsız** olarak desteklenmeye devam etmektedir. Artık **`QuickTextPaste.exe` zorunlu değildir**; ancak ikili dosyanın yanında halihazırda `QuickTextPaste.ini` bulunuyorsa QTP bu dosyayı otomatik olarak okur ve düzenlemelerde `.bak` yedeğiyle günceller.

---

## 9. Web PWA Bileşenleri

Depodaki mevcut `index.html`, `cevaplar.html`, `sw.js` ve `manifest.webmanifest` dosyaları tarayıcı tabanlı bağımsız Web PWA çıktıları olarak korunmuş ve değiştirilmemiştir.

---

## 10. English Summary

**QTP v2.0.0** is a standalone, single-file, offline cross-platform desktop quick-paste app (`dist/qtp.exe` for Windows, `dist/qtp.bin` for Linux/macOS) with zero dependency on `QuickTextPaste.exe`.
1. Download or build the portable binary (`make build` / `make.bat`), and optionally place your `QuickTextPaste.ini` next to it.
2. Run `qtp.exe` (or `chmod +x qtp.bin && ./qtp.bin`) — press `Win+A/Z/X/Q` or `Ctrl+Shift+Space` to open the animated overlay.
3. Type to fuzzy-search (Turkish-locale aware), press `Enter` to paste into your previous active app (or `Ctrl+Enter` to copy only), and press `F1` for built-in documentation.
4. Run `--selftest`, `--version`, `--help`, `--export-ini`, or `--import-ini` for CLI automation, or `pytest -q --cov` to verify tests (≥ 90% coverage).
