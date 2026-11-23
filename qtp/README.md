# QTP — QuickTextPaste & Hazır Cevaplar (Bağımsız Masaüstü Uygulaması)

**QTP v2.1.0**, artık üçüncü parti `QuickTextPaste.exe` dosyasına veya herhangi bir harici çalışma zamanı aracına (`xclip`, `xsel`, `xdotool`, `wmctrl`, `pyperclip`, Python, Qt kurulumu vb.) **hiçbir bağımlılığı olmadan**, Windows, Linux ve macOS üzerinde **dört çalışma modunun (`--gui`, `--tui`, `--cli`, `--web`) tamamında birebir özellik eşitliği** sunan **tek dosya** taşınabilir uygulamadır.

---

## Dört Mod (`--gui`, `--tui`, `--cli`, `--web`)

| Mod | Örnek Komut | Açıklama |
| :--- | :--- | :--- |
| **GUI** | `qtp --gui` (veya çift tık) | PyQt6 animasyonlu katman penceresi, yerel `RegisterHotKey` kısayolları ve sistem tepsisi |
| **TUI** | `qtp --tui` | Sıfır bağımlılıklı terminal arayüzü (`curses` / Windows ANSI + Win32 Console katmanı) |
| **CLI** | `qtp --cli --search "şifre" --json` | Betikler ve CI için başsız alt komutlar, `-v/-q`, `--completion` ve kararlı çıkış kodları |
| **Web** | `qtp --web --port 8765 --open-browser` | Yalnızca `127.0.0.1` üzerinde çalışan çevrimdışı HTTP/JSON sunucusu |

Tüm modların tam karşılaştırması için: [Modlar Arası Eşitlik Matrisi](docs/KULLANIM.md#12-modlar-arası-eşitlik-matrisi). `--verbose` (`-v`/`-vv`), `--quiet` (`-q`), `--help`, `F1` yardım modalı ve `--category` / `--query` başlangıç filtreleri dört modda da aynı şekilde çalışır.

---

## 1. Tek Dosya Uygulama ve Canlı Web Dağıtımı (GitHub Pages)

- **Canlı Web Arayüzü (GitHub Pages / Çevrimdışı):** [https://m-sonmez.github.io/qtp/](https://m-sonmez.github.io/qtp/) (`index.html` — `--web` arayüzüyle birebir, sıfır arka uçla statik çalışır ve yerel `--web` modunu otomatik algılar)
- **Taşınabilir Windows Uygulaması (`qtp.exe`):** [https://m-sonmez.github.io/qtp/qtp.exe](https://m-sonmez.github.io/qtp/qtp.exe) (`dist/qtp.exe` ile birebir) — Çift tıklayıp doğrudan çalıştırın; yerel Win32 `RegisterHotKey` ve PowerShell/Terminal konsol eki (`--help`, `--verbose`, `--completion`) yerleşiktir. *(Windows 7 / 8 / 8.1 x64 için Python 3.8 + `requirements-win7.txt` + `python -m qtp_app.build.build_windows_legacy` hedefini kullanın.)*
- **Taşınabilir Linux x64 Uygulaması (`qtp.bin`):** [https://m-sonmez.github.io/qtp/qtp.bin](https://m-sonmez.github.io/qtp/qtp.bin) — `chmod +x qtp.bin && ./qtp.bin` (`--tui`, `--cli` ve `--web` modları PyQt6 olmadan Alpine/musl ve BSD sistemlerde de çalışır).
- **Eski QuickTextPaste Web Arayüzü (`old.html`):** [https://m-sonmez.github.io/qtp/old.html](https://m-sonmez.github.io/qtp/old.html) — Önceki 3. parti QuickTextPaste yapılandırma ve hızlı kullanım PWA sayfasının korunan yedeği.
- **Tamamen Çevrimdışı, Taşınabilir ve Canlı Yenilemeli:** Ayarlar (`qtp_settings.json`), `QuickTextPaste.ini` (`data_path`) ve `data.json` harici düzenlemelerde `ConfigFileWatcher` ile **yeniden başlatma olmadan** otomatik yenilenir (kısayollar ve tema dahil).

---

## 2. Çakışmasız Kısayollar ve Tam Özelleştirme

Windows 10/11 sistem kısayollarıyla (`Win+A/Z/X/Q`) ve Türkçe-Q `AltGr` (`Ctrl+Alt+Q=@`) ile çakışmaması için varsayılan kısayollar **`Win+Alt+*`** olarak belirlenmiştir; ayrıca **15 değiştirici bileşiminin tamamı**, 6 hazır profil ve özel yuvalar desteklenir:

| Olay | Varsayılan (`recommended`) | Açıklama |
| :--- | :--- | :--- |
| Tüm Kategoriler | `Win+Alt+Space` | Katmanı tüm kategorilerle açar |
| İş Ortağı | `Win+Alt+A` | **A · İş Ortağı** (`L-Win+A` INI önekli) kategorisiyle açar |
| Kurye | `Win+Alt+Z` | **Z · Kurye** (`L-Win+Z` INI önekli) kategorisiyle açar |
| Canlı Yardım | `Win+Alt+X` | **X · Canlı Yardım** (`L-Win+X` INI önekli) kategorisiyle açar |
| Turkcell | `Win+Alt+Q` | **Q · Turkcell** (`L-Win+Q` INI önekli) kategorisiyle açar |
| Gezinme / Yapıştır / Kopyala | `↑↓` / `⏎` / `Ctrl+⏎` | Listede gezinir, yapıştırır veya katmanı kapatmadan panoya kopyalar |
| Arama / Ayar / Yardım | `Ctrl+K` / `Ctrl+,` / `F1` | Arama kutusu, Ayarlar ve Türkçe Yardım (`F1`) |

Ayrıntılı tablo, profiller ve Türkçe-Q `AltGr` notları için: [docs/KISAYOLLAR.md](docs/KISAYOLLAR.md)

---

## 3. Kurulum, Kullanım, SSS ve Geliştirici Belgeleri

- Kurulum, sistem gereksinimleri ve Win7/Linux/macOS/BSD notları: ➡️ [docs/KURULUM.md](docs/KURULUM.md)
- Kullanım, `--verbose`, `--completion`, canlı yenileme ve modlar matrisi: ➡️ [docs/KULLANIM.md](docs/KULLANIM.md)
- Sıkça sorulan sorular, kısayol çakışma ve hata mesajları: ➡️ [docs/SSS.md](docs/SSS.md)
- Mimari, geliştirme ve kapsam testi rehberi: ➡️ [docs/GELISTIRICI.md](docs/GELISTIRICI.md)

---

## 4. Ayarlar (`qtp_settings.json`)

| Alan | Varsayılan | Açıklama |
| :--- | :--- | :--- |
| `theme` | `"dark"` | Renk teması (`auto`, `dark`, `light`) |
| `hotkeys` | `Win+Alt+Space/A/Z/X/Q` | Esnek global kısayollar (`all`, `A`, `Z`, `X`, `Q` + özel yuvalar) |
| `last_category` | `"ALL"` | Genel açılışta son seçili kategori |
| `window_size` | `[720, 520]` | Katman penceresi `[genişlik, yükseklik]` boyutu |
| `paste_method` | `"auto"` | Yapıştırma yöntemi (`auto`, `ctrl_v`, `shift_insert`, `type`) |
| `enter_after_paste` | `true` | `<E<N<D|` işaretli kayıtlardan sonra otomatik `Enter` |
| `start_minimized` | `false` | Başlangıçta katmanı göstermeden sistem tepsisinde bekle |
| `tray_icon` | `true` | Sistem tepsisi simgesini göster/gizle |
| `data_path` | `"./QuickTextPaste.ini"` | Etkin `QuickTextPaste.ini` dosya yolu |
| `backup_count` | `15` | `backups/` dizininde tutulacak yedek sayısı |
| `auto_reload` | `true` | Harici dosya değişikliklerini yeniden başlatmadan canlı yükle |
| `auto_reload_interval_ms` | `500` | Disk denetleme aralığı (`100–10000 ms`) |
| `log_level` | `"info"` | `qtp.log` günlük düzeyi (`debug`, `info`, `warn`, `error`) |
| `language` | `"tr"` | Arayüz dili (`tr`) |
| `web.port` | `8765` | `--web` sunucusu yerel `127.0.0.1` bağlantı noktası (`0–65535`) |

---

## 5. Miras / Legacy & Web PWA Notu

Mevcut `QuickTextPaste.ini` biçimi (`UTF-16 LE BOM`, `UTF-16 BE BOM`, `UTF-8 BOM`, `cp1254`, `[Program]`, `[list_text]`, `[list_order]`, `[list_label]`, `<E<N<D|` ve `L-Win+A/Z/X/Q/W/1` önekleri) **tam ve kayıpsız** korunmuştur. Unified `index.html` (`theme.css` ile) hem GitHub Pages üzerinde statik çevrimdışı olarak hem de yerel `qtp --web` API sunucusuyla otomatik mod algılayarak birebir çalışır; önceki 3. parti QuickTextPaste PWA sayfası [old.html](old.html) olarak, diğer PWA bileşenleri ise `cevaplar.html`, `sw.js` ve `manifest.webmanifest` olarak korunmaktadır.

---

## 6. English Summary

**QTP v2.1.0** is a standalone, single-file, offline cross-platform desktop quick-paste app (`dist/qtp.exe` for Windows, `dist/qtp.bin` for Linux/macOS) supporting `--gui`, `--tui`, `--cli`, and `--web` modes with zero external runtime dependencies.
1. Uses conflict-free default global hotkeys (`Win+Alt+Space`, `Win+Alt+A/Z/X/Q`) via native Win32 `RegisterHotKey` on Windows (keystroke-consuming, zero Windows shell leaks, Turkish-Q `AltGr` safe), supports all 15 modifier combinations, 6 preset profiles, custom slots, and live conflict detection.
2. Features `ConfigFileWatcher` for live hot-reload of `qtp_settings.json`, `QuickTextPaste.ini`, and `data.json` without restart, plus parent-PID Windows console attachment for `--help`, `--verbose`, and `--completion` (`powershell`, `bash`, `zsh`, `fish`).
