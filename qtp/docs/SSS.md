# QTP Sıkça Sorulan Sorular (SSS) ve Hata Mesajları

Bu belge, QTP'nin üretebileceği **tüm Türkçe hata/uyarı mesajlarını birebir metinleriyle**, olası nedenlerini ve çözüm adımlarını içerir.

---

## 1. Hata ve Uyarı Mesajları Referansı

### 1.1 INI Ayrıştırma ve Kodlama Hataları

| Birebir Mesaj | Olası Neden | Çözüm |
| :--- | :--- | :--- |
| `INI dosyası okunamadı: boş veya bozuk ikili veri` / `INI dosyası okunamadı: bozuk veya eksik UTF-16 LE bayt dizisi.` / `INI dosyası okunamadı: bozuk veya eksik UTF-16 BE bayt dizisi.` | Dosya UTF-16 BOM (`FF FE` veya `FE FF`) taşıyor ancak veri uzunluğu tek bayt (kesilmiş/bozuk dosya). | Yedekten (`QuickTextPaste.ini.bak` veya `backups/`) dosyayı geri yükleyin ya da metin düzenleyicide UTF-16 LE BOM olarak yeniden kaydedin. |
| `INI dosyası okunamadı: geçersiz ikili (null) bayt içeriği.` / `INI dosyası okunamadı: geçersiz ikili (null) karakter içeriyor.` | UTF-16 olmayan bir dosyanın içine `0x00` ikili baytları veya yanlış biçimli bir ikili dosya (`.exe`, `.zip`, `.png`) verilmiş. | Geçerli bir metin tabanlı `QuickTextPaste.ini` dosyası seçtiğinizden emin olun. |
| `INI dosyası çözümlenemedi: metin türü geçersiz.` / `INI dosyası çözümlenemedi: desteklenmeyen karakter kodlaması veya bozuk veri.` / `HATA: INI okunamadı:` | Ayrıştırıcıya metin dışı veri aktarılmış veya dosya okunamıyor. | Dosyayı UTF-8 BOM veya UTF-16 LE BOM kodlamasına çevirin ve okuma izinlerini doğrulayın. |
| `INI dosyası biçimi geçersiz (satır N): Bölüm başlığı düzgün kapatılmamış.` | N. satırda `[` ile başlayan ama `]` ile bitmeyen bozuk bir bölüm başlığı var. | Satırı `[list_text]` gibi köşeli parantezlerle düzgün kapatın. |
| `INI dosyası biçimi geçersiz (satır N): Boş bölüm adı kullanılamaz.` | N. satırda `[]` biçiminde boş bölüm başlığı bulunuyor. | Geçerli bir bölüm adı yazın veya hatalı satırı silin. |
| `INI dosyası biçimi geçersiz (satır N): Bölüm ([...]) başlığı dışında içerik bulundu.` | Dosyanın başında `[Program]` veya `[list_text]` başlığı olmadan düz metin/JSON bulunuyor. | Dosyanın ilk aktif satırının `[Program]` veya `[list_text]` olduğundan emin olun; JSON dosyası açıyorsanız `.json` uzantısı kullanın. |
| `INI dosyası biçimi geçersiz (satır N): Anahtar=değer biçimi bekleniyor.` | Bölüm içindeki bir satırda `=` işareti eksik. | Satırı `anahtar=değer` biçimine getirin veya başına `;` koyarak yorum satırı yapın. |
| `INI dosyası biçimi geçersiz (satır N): [list_text] satırı 'kimlik=kısayol=metin' biçiminde değil.` | `[list_text]` bölümündeki satırda iki adet `=` ayıracı yok. | Satırı `text_000=L-Win+A=Metin<E<N<D|` biçimine düzeltin (kısayol yoksa `text_000==Metin<E<N<D|`). |
| `INI dosyası biçimi geçersiz (satır N): Geçersiz öğe kimliği '...'.` | `[list_text]` içindeki satır kimliği boş veya geçersiz karakter içeriyor. | `text_000` biçiminde alfasayısal + `_` kimlik kullanın. |
| `INI dosyası biçimi geçersiz (satır N): [list_order] sayısal değer bekliyor.` | `[list_order]` satırında `text_000=abc` gibi tamsayı olmayan bir değer var. | Sıra değerini tam sayıya (`1`, `2`, ...) çevirin. |

### 1.2 JSON, Yedekleme, Ayar ve Canlı Yenileme Hataları

| Birebir Mesaj | Olası Neden | Çözüm |
| :--- | :--- | :--- |
| `data.json çözümlenemedi: geçersiz JSON biçimi (...)` / `JSON dosyası ayrıştırılamadı: ...` | `data.json` veya tam yedek dosyasında sözdizimi hatası var. | `backups/` klasöründeki son sağlıklı yedeği geri yükleyin veya JSON doğrulayıcı ile düzeltin. |
| `data.json biçimi geçersiz: kök eleman bir JSON dizisi ([...]) olmalıdır.` | `data.json` nesne (`{...}`) veya metin içeriyor; dizi (`[...]`) bekleniyor. | Kök yapının `[{"keys": ..., "group": ..., "text": ...}]` dizisi olduğundan emin olun. |
| `Desteklenmeyen dosya biçimi: Geçerli INI, JSON listesi ([...]) veya QTP Tam Yedek bekleniyor.` | Yüklenen JSON dosyası ne dizi ne de `type: "qtp-pwa-backup"` yapısında. | Doğru `data.json`, `qtp-tam-yedek-*.json` veya `QuickTextPaste.ini` dosyasını seçin. |
| `Yedek bulunamadı: ...` | İstenen yedek kimliği `backups/` klasöründe mevcut değil. | Tepsi → `Yedekler…` listesinden güncel bir yedek kimliği seçin. |
| `Bozuk ayar dosyası (...) algılandı; varsayılan ayarlarla yeniden oluşturuldu (...)` | `qtp_settings.json` açılışta bozuk veya geçersiz JSON içeriyor. | QTP otomatik olarak varsayılan ayarları geri yazar; özelleştirilmiş kısayollarınız varsa Ayarlar penceresinden yeniden girin. |
| `Otomatik ayar yenileme başarısız (mevcut ayarlar korundu): ...` | `auto_reload` etkin iken `qtp_settings.json` dışarıdan bozuk JSON biçiminde kaydedildi. | QTP çalışan ayarları bozmadan korur; `qtp_settings.json` içindeki sözdizimi hatasını düzeltip kaydedin. |
| `Otomatik veri yenileme başarısız (önceki geçerli kayıtlar korundu): ...` | `auto_reload` etkin iken `QuickTextPaste.ini` veya `data.json` dışarıdan eksik/bozuk biçimde kaydedildi. | QTP bellekteki son geçerli listeyi korur ve çökmez; dosyayı geçerli biçime getirip kaydedin. |

### 1.3 Platform, Yapıştırma, Kısayol, Tamamlama ve CLI Hataları

| Birebir Mesaj | Olası Neden | Çözüm |
| :--- | :--- | :--- |
| `Wayland oturumunda 'wtype' veya 'ydotool' bulunamadı; yapay yapıştırma gerçekleştirilemedi.` | Linux Wayland üzerinde yapay tuş basımı için isteğe bağlı `wtype` veya `ydotool` kurulu değil. | Metin yine de panoya kopyalanır; otomatik `Ctrl+V` için `wtype`/`ydotool` kurun. |
| `Wayland oturumunda global kısayollar kısıtlıdır (...); uygulama tepsi/TUI/CLI/Web ile kullanılabilir.` | Wayland güvenlik modeli arka plan X11 global tuş dinlemeyi engelledi. | Başlangıç bloklanmaz; sistem tepsisinden veya `--tui`/`--cli`/`--web` ile kullanın. |
| `macOS Erişilebilirlik izni verilmemiş! Sistem Ayarları -> Gizlilik ve Güvenlik -> Erişilebilirlik altından QTP'ye izin verin.` | macOS `qtp.bin` için klavye iznini henüz onaylamamış. | Sistem Ayarları → Gizlilik ve Güvenlik → Erişilebilirlik altından izin verip yeniden başlatın. |
| `Global kısayol kaydedilemedi: ... (ERROR_HOTKEY_ALREADY_REGISTERED / 1409)` / `Global kısayol kaydedilemedi: ...` | Başka bir uygulama, ikinci bir QTP örneği veya Windows sistem kısayolu (`Win+A`, `Win+X` vb.) bu tuş bileşimini zaten kilitlemiş. | Çakışan programı kapatın veya **Ayarlar → Global Kısayollar** üzerinden `recommended` (`Win+Alt+*`) veya `function_keys` (`Ctrl+Shift+F1–F5`) seçin. |
| `Türkçe-Q klavyede AltGr+Q (@ işareti) yazımını engelleyebilir.` / `Türkçe-Q klavyede AltGr+...` | Windows Türkçe-Q klavyede `Ctrl+Alt+<tuş>`, `AltGr` karakteriyle aynı tuş kodunu üretir. | `@`, `æ`, `€`, `ß` yazabilmek için `Win+Alt+*`, `Win+Ctrl+*` veya `Ctrl+Alt+Shift+*` bileşimlerini kullanın. |
| `Çift atama: '...' başka bir kategoride de kullanılıyor` | İki ayrı yuvaya aynı kısayol bileşimi girilmiş. | Kısayollardan birini farklı bir tetik tuşuyla değiştirin. |
| `Geçersiz kısayol profili: ...` / `Geçersiz değiştirici bileşimi` | `--hotkey-preset` veya `--hotkey-modifiers` için geçersiz ad verildi. | Profiller: `recommended`, `win_ctrl`, `ctrl_alt`, `ctrl_shift_alt`, `function_keys`, `legacy_win`. Değiştiriciler: `Win`, `Ctrl`, `Alt`, `Shift` bileşimleri. |
| `Boş kısayol dizesi kullanılamaz.` / `Geçersiz kısayol tanımı (...): değiştirici tuşlar tek başına kullanılamaz; A–Z, F1–F12 veya Space gibi bir tetik tuşu ekleyin.` / `Geçersiz kısayol bileşeni (...): bilinmeyen tuş ...` / `Geçersiz kısayol tanımı (...): en az bir değiştirici tuş (Ctrl, Alt, Shift veya Win) gereklidir.` / `Geçersiz kısayol tanımı (...): birden fazla tetik tuşu kullanılamaz.` | `--set hotkeys.<yuva>` veya ayar penceresine tetik tuşsuz (`Ctrl+Alt`), değiştiricisiz (`A`) ya da tanınmayan tuş bileşimi girildi. | En az bir değiştirici (`Ctrl`, `Alt`, `Shift`, `Win`) ve tek bir geçerli tetik tuşu (`Win+Alt+A`, `Ctrl+Shift+F2` vb.) kullanın. |
| `Desteklenmeyen kabuk türü: ...` | `--completion <kabuk>` veya `GET /api/completion?shell=...` için desteklenmeyen kabuk adı girildi. | `powershell`, `bash`, `zsh`, `fish` veya `auto` kullanın. |
| `Pano erişimi başarısız: grafik oturumu veya pano desteği bulunamadı.` | Başsız Linux oturumunda DISPLAY/Qt/TTY yoksa panoya yazılamadı. | X11/GUI oturumu veya etkileşimli TTY (OSC 52) üzerinden çalıştırın. |
| `Tuş simülasyonu başarısız (yalnızca panoya kopyalandı): ...` | Hedef pencereye tuş gönderimi işletim sistemi tarafından engellendi. | Metin panoya alınmıştır; `Ctrl+V` / `Cmd+V` ile yapıştırın. |
| `Öğe bulunamadı: ...` | `--copy`, `--paste` veya `--show-ini` için verilen `raw_key` veya metin kayıtlar arasında yok. | `--list-items` çıktısındaki geçerli `text_NNN` anahtarını kullanın. |
| `Geçersiz ayar anahtarı: ...` / `Geçersiz ayar değeri ...` | `--set` veya `--get` ile desteklenmeyen alan adı ya da aralık dışı değer girildi. | `theme`, `web.port`, `auto_reload`, `auto_reload_interval_ms` (`100–10000`), `hotkeys.*` için geçerli değerler kullanın. |
| `HATA: Etkileşimsiz ortamda/CI içinde açıkça --mode {gui,tui,cli,web} belirtilmelidir.` | Pipe/CI ortamında hiçbir bayrak veya `--mode` verilmeden çalıştırıldı. | Betiklerde `--mode cli`, `--mode tui` veya `--mode web` belirtin. |
| `Güvenlik kuralı: Web sunucusu yalnızca 127.0.0.1 üzerinde çalışabilir` | Yerel web sunucusu LAN/0.0.0.0 arayüzüne bağlanmaya çalışırsa reddedilir. | Yalnızca `127.0.0.1` veya `localhost` üzerinden bağlanın. |
| `HATA: Web sunucusu başlatılamadı (port kullanımda olabilir): ...` | Seçilen `web.port` başka bir süreç tarafından kullanılıyor. | `--port 0` veya farklı bir port numarası kullanın. |
| `Bilinmeyen API uç noktası: ...` | `--web` modunda tanımsız bir `/api/...` rotası çağrıldı. | Geçerli rotalar için `GET /api` uç noktasını sorgulayın. |
| `HATA: Yedek oluşturulamadı: ...` / `HATA: Tam yedek dışa aktarılamadı: ...` / `HATA: INI dışa aktarılamadı:` / `HATA: Kayıtlar yeniden yüklenemedi: ...` / `HATA: Yedek geri yüklenemedi: ...` / `HATA: Yedek okunamadı:` | Disk yazma izni yok veya kaynak yedek/INI dosyası bozuk. | Çalışma klasörünün yazılabilir olduğunu ve dosyanın geçerli JSON/INI olduğunu doğrulayın. |
| `QTP zaten çalışıyor; mevcut pencere gösterildi ve ikinci örnek kapatıldı.` | Arka planda zaten bir QTP örneği açık (`qtp.lock`). | Normal davranıştır; çalışan katman otomatik olarak öne getirilir. |
| `HATA: Bilinmeyen komut satırı seçeneği: ...` / `Bilinmeyen TUI işlemi:` | CLI veya TUI üzerinden tanımlı olmayan bir seçenek/işlem çağrıldı. | `qtp --help` çıktısındaki geçerli bayrakları ve TUI kısayollarını kullanın. |
| `HATA: İçe aktarılacak INI dosyası bulunamadı: ...` | `--import-ini` ile verilen dosya yolu diskte mevcut değil. | Dosya yolunu ve yazımını kontrol edin. |
| `HATA: Dışa aktarılacak hazır cevap kaydı bulunamadı.` | Dışa aktarılacak liste boş. | En az bir geçerli `QuickTextPaste.ini` veya `data.json` bulunduğundan emin olun. |
| `HATA: Paketlenmiş INI örneği bulunamadı:` / `HATA: Paketlenmiş QuickTextPaste.ini gidiş-dönüş (round-trip) doğrulaması başarısız.` / `HATA: Öğe sayısı uyuşmuyor` / `HATA: Otomatik test sırasında beklenmeyen hata:` | `--selftest` sırasında gömülü varsayılan INI varlığı bozuk veya okunamadı. | Paket bütünlüğünü doğrulayıp uygulamayı yeniden derleyin. |
| `HATA: Katman beklenen ... yerine ... satır listeledi.` / `HATA: Enter tuşu yapıştırma geri çağrısını tetiklemedi.` | `--selftest` sırasında arayüz modeli beklenen kayıtları veya Enter olayını işleyemedi. | Qt platform eklentisini kontrol edip `--selftest` komutunu tekrar çalıştırın. |
| `HATA: Arama kutusu otomatik odaklanamadı.` | `--selftest` sırasında arama alanı odak alamadı. | Qt platform eklentisini (`QT_QPA_PLATFORM=offscreen`) kontrol edin. |
| `Belge dosyası bulunamadı:` | İstenen Markdown yardım dosyası pakette veya `docs/` klasöründe yer almıyor. | İkili dosyanın `docs/*.md` verilerini içerdiğinden emin olun. |
| `Metin alanı boş olamaz.` | `--add-item`, `--update-item` (`POST /api/items/add`, `POST /api/items/update`, TUI `a`/`E` veya GUI Düzenleyici) işleminde metin alanı boş bırakılmış. | En az bir görünür karakter içeren hazır cevap metni yazıp tekrar kaydedin. |
| `HATA: Kayıt ve ayarlar diske yazılamadı:` | `--save` (`POST /api/save`, TUI `w` veya GUI `Ctrl+S`) sırasında disk yazma hatası oluştu. | Çalışma dizininin yazılabilir olduğunu ve dosyaların kilitli olmadığını doğrulayın. |
| `Geçersiz taşıma yönü:` / `Kayıt zaten sınırda, taşınamadı.` | `--move-item` (`POST /api/items/move`, TUI `K`/`J`) için yön `up`/`down` dışında verildi veya kayıt zaten ilk/son sırada. | Yönü `up` veya `down` olarak girin ve orta konumdaki bir öğeyi seçin. |
| `Toplu işlem için en az bir hedef kayıt seçilmelidir.` / `Toplu düzenleme için en az bir değişiklik seçeneği belirtilmelidir.` | `--bulk-edit` / `--bulk-delete` (`POST /api/items/bulk-*`, TUI `U`/`X` veya GUI Toplu Düzenle) boş seçimle ya da değişiklik alanı olmadan çağrıldı. | En az bir hedef kayıt seçin ve kısayol, grup, bul/değiştir, önek/sonek, emoji veya favori alanlarından en az birini doldurun. |
| `Eski ve yeni grup adı boş olamaz.` / `Grup adı boş olamaz.` / `Grup bulunamadı:` | `--rename-group` veya `--delete-group` (`POST /api/groups/*`, TUI `g`/`G`) için boş ya da mevcut olmayan grup adı verildi. | Mevcut grup adlarından birini eksiksiz girin. |
| `Geri alınacak işlem yok.` / `Yinelenecek işlem yok.` | `--undo` / `--redo` (`POST /api/undo`, `POST /api/redo`, `Ctrl+Z` / `Ctrl+Y`) geçmiş veya ileri alma yığını boşken çağrıldı. | Önce geri alınabilir bir ekleme, düzenleme, silme veya grup işlemi gerçekleştirin. |

---

## 2. Sık Karşılaşılan Sorunlar ve Çözümler

### Kısayollar Windows'ta Sistem Menüsünü Açıyorsa veya `1409` Hatası Alınıyorsa
QTP varsayılan olarak çakışmasız **`Win+Alt+Space / A / Z / X / Q`** kısayollarını yerel Win32 `RegisterHotKey` üzerinden kaydeder ve basılan tuşları aktif pencereye sızdırmadan tüketir. Eski ayar dosyanızda `Win+A/Z/X/Q` kaldıysa veya başka bir araç kısayolu tutuyorsa:
1. Ayarlar (`Ctrl+,`) penceresini açın (veya `qtp --hotkey-preset recommended` çalıştırın).
2. `recommended` (`Win+Alt+*`) veya `Win` tuşsuz `function_keys` (`Ctrl+Shift+F1–F5`) / `ctrl_shift_alt` profilini seçip kaydedin; yeniden başlatma gerekmez.

### PowerShell'de `--help` Çıktısı Neden Ekstra Bayrak Olmadan Önemlidir?
Windows `qtp.exe` çift tıklandığında siyah komut penceresi açmamak için GUI alt sisteminde (`console=False`) paketlenir. `--help`, `-v --help`, `--completion`, `--cli` veya `--tui` gibi bir bayrakla çalıştırıldığında QTP üst süreç zincirini (`AttachConsole` ile PowerShell/cmd/Terminal) yürüyüp `UTF-8 (65001)` kod sayfasıyla `argparse` öncesinde bağlanır.

### Wayland / GNOME / `qtp.lock` / Türkçe INI Kodlamaları
- **Wayland:** Yapay `Ctrl+V` için isteğe bağlı `wtype` (Sway/Hyprland) veya `ydotool` kurulabilir; kopyalama (`Ctrl+Enter` / `--copy`) yerleşik çalışır.
- **GNOME Tepsisi:** Tepsi simgesi için `gnome-shell-extension-appindicator` etkinleştirin; gizliyken de global kısayollarla katmanı açabilirsiniz.
- **`qtp.lock` & Türkçe Kodlama:** Bayat `qtp.lock` sonraki açılışta otomatik temizlenir; `cp1254` ve BOM'suz INI'ler kayıpsız `UTF-16 LE BOM` olarak okunur.

### Açık / Koyu Tema Nasıl Değiştirilir?
- QTP v2.3.0 sürümünden itibaren tüm arayüzlerde (`--gui`, `--web`, `qtp.html`, `index.html`, `legacy/cevaplar.html`) varsayılan tema **Açık (Light)** olarak başlar ve tüm bileşenler (kartlar, bağlam menüleri, tablolar, açılır listeler, kaydırma çubukları, bildirim balonları, yardım sekmeleri) WCAG 2.1 kontrast standartlarına göre tam yalıtılmıştır.
- **Tek Tıkla Açık / Koyu Moda Geçiş:**
  - **GUI (`--gui`):** Üst çubuktaki `🌙 Koyu` / `☀️ Açık` düğmesine tıklayın veya Ayarlar (`Ctrl+,`) penceresindeki Tema (`light` / `dark` / `auto`) seçeneğini değiştirin; değişiklik anında canlı olarak katmana, tepsi menüsüne ve tüm açılır pencerelere uygulanır.
  - **Web / GitHub Pages (`qtp.html` / `index.html`):** Üst sağdaki `🌙 Koyu` / `☀️ Açık` tema düğmesine tıklayın; canlı `--web` modunda `qtp_settings.json` güncellenir, statik GitHub Pages üzerinde ise tarayıcı `localStorage` hafızasına kaydedilir.
  - **CLI / TUI:** `qtp --set theme dark` veya TUI içinde `s` → `theme` → `dark`.

### Windows "Bilinmeyen Yayıncı" veya SmartScreen Uyarısı Nasıl Giderilir?
- `qtp.exe`, `CompanyName = Murat Sönmez` PE sürüm bilgisini ve `CN=Murat Sönmez` (`SHA-256`, RFC 3161 zaman damgalı) Authenticode dijital imzasını içerir.
- Kendinden imzalı sertifika Microsoft'un ön tanımlı kök listesinde yer almadığından, başka bir Windows cihazında ilk kullanımda tek seferlik sertifika güveni ekleyebilirsiniz (yönetici izni gerekmez):
  ```powershell
  irm https://m-sonmez.github.io/qtp/certs/MuratSonmez-QTP.cer -OutFile MuratSonmez-QTP.cer
  Import-Certificate -FilePath .\MuratSonmez-QTP.cer -CertStoreLocation Cert:\CurrentUser\Root
  Import-Certificate -FilePath .\MuratSonmez-QTP.cer -CertStoreLocation Cert:\CurrentUser\TrustedPublisher
  ```
- Grafik arayüzle: `qtp.exe` sağ tık → **Özellikler** → **Dijital İmzalar** → **Sertifikayı Göster** → **Sertifika Yükle** → **Geçerli Kullanıcı** → **Güvenilen Kök Sertifika Yetkilileri**. Ticari/Azure Trusted Signing sertifikası kullanacaksanız `QTP_SIGN_PFX` ve `QTP_SIGN_PFX_PASSWORD` ortam değişkenleriyle `build_windows` doğrudan imzalar.

### Yeni Cevap Ekleme, Düzenleme ve Silme (CRUD) Nasıl Çalışır?
- **GUI:** Üst çubuktaki `+ Yeni Cevap` düğmesiyle yeni kayıt ekleyin; listede herhangi bir satıra sağ tıklayıp **Düzenle** veya **Sil** seçin. Değişiklikler hem `QuickTextPaste.ini` hem de `data.json` dosyasına eşzamanlı yazılır ve otomatik yedek (`backups/`) alınır.
- **TUI:** `a` (Yeni Cevap Ekle), `E` (Seçili Kaydı Düzenle), `d` (Seçili Kaydı Sil).
- **CLI:** `--add-item "<metin>" [--item-keys K] [--item-group G] [--item-label E] [--no-end-marker]`, `--update-item <hedef> ...`, `--delete-item <hedef>`.
- **Web (`--web` & Statik `qtp.html`):** `+ Yeni Cevap` ve satır içi `Düzenle` / `Sil` düğmeleri yerel `--web` sunucusunda diski günceller (`/api/items/add`, `/api/items/update`, `/api/items/delete`); internet üzerindeki `https://m-sonmez.github.io/qtp/qtp.html` adresinde ise tarayıcı `localStorage` üzerinde kalıcı olarak çalışır ve `Dışa Aktar` ile indirilebilir.

### `index.html`, `qtp.html` ve `legacy/` Arasındaki Fark Nedir?
- **`index.html` + `legacy/`:** Klasik QuickTextPaste PWA rehberi, kategorize cevap görüntüleyici (`legacy/cevaplar.html`) ve Windows yönetici betikleri (`legacy/qtp_manager.py`, `legacy/kurulum.ps1`).
- **`qtp.html` + `standalone/`:** QTP'nin harici bağımlılıksız, kendi kendine yeten tek dosya masaüstü uygulaması (`qtp.exe` / `qtp.bin`) ve `--web` arayüzünün statik GitHub Pages karşılığıdır. Her iki HTML sayfası da işletim sistemine özel taşınabilir indirme düğmesi ve **PWA Yükle** desteği sunar.
