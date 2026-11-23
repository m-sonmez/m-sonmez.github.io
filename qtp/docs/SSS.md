# QTP Sıkça Sorulan Sorular (SSS) ve Hata Mesajları

Bu belge, QTP'nin üretebileceği **tüm Türkçe hata/uyarı mesajlarını birebir metinleriyle**, olası nedenlerini ve çözüm adımlarını içerir.

---

## 1. Hata ve Uyarı Mesajları Referansı

### 1.1 INI Ayrıştırma ve Kodlama Hataları

| Birebir Mesaj | Olası Neden | Çözüm |
| :--- | :--- | :--- |
| `INI dosyası okunamadı: boş veya bozuk ikili veri` / `INI dosyası okunamadı: bozuk veya eksik UTF-16 LE bayt dizisi.` / `INI dosyası okunamadı: bozuk veya eksik UTF-16 BE bayt dizisi.` | Dosya UTF-16 BOM (`FF FE` veya `FE FF`) taşıyor ancak veri uzunluğu tek bayt (kesilmiş/bozuk dosya). | Yedekten (`QuickTextPaste.ini.bak` veya `backups/`) dosyayı geri yükleyin ya da metin düzenleyicide UTF-16 LE BOM olarak yeniden kaydedin. |
| `INI dosyası okunamadı: geçersiz ikili (null) bayt içeriği.` / `INI dosyası okunamadı: geçersiz ikili (null) karakter içeriyor.` | UTF-16 olmayan bir dosyanın içine `0x00` ikili baytları veya yanlış biçimli bir ikili dosya (`.exe`, `.zip`, `.png`) verilmiş. | Geçerli bir metin tabanlı `QuickTextPaste.ini` dosyası seçtiğinizden emin olun. |
| `INI dosyası çözümlenemedi: metin türü geçersiz.` / `INI dosyası çözümlenemedi: desteklenmeyen karakter kodlaması veya bozuk veri.` | Ayrıştırıcıya metin dışı veri aktarılmış veya dosya desteklenmeyen bozuk kodlama içeriyor. | Dosyayı UTF-8 BOM veya UTF-16 LE BOM kodlamasına çevirin. |
| `INI dosyası biçimi geçersiz (satır N): Bölüm başlığı düzgün kapatılmamış.` | N. satırda `[` ile başlayan ama `]` ile bitmeyen bozuk bir bölüm başlığı var. | Satırı `[list_text]` gibi köşeli parantezlerle düzgün kapatın. |
| `INI dosyası biçimi geçersiz (satır N): Boş bölüm adı kullanılamaz.` | N. satırda `[]` biçiminde boş bölüm başlığı bulunuyor. | Geçerli bir bölüm adı yazın veya hatalı satırı silin. |
| `INI dosyası biçimi geçersiz (satır N): Bölüm ([...]) başlığı dışında içerik bulundu.` | Dosyanın başında `[Program]` veya `[list_text]` başlığı olmadan düz metin/JSON bulunuyor. | Dosyanın ilk aktif satırının `[Program]` veya `[list_text]` olduğundan emin olun; JSON dosyası açıyorsanız `.json` uzantısı kullanın. |
| `INI dosyası biçimi geçersiz (satır N): Anahtar=değer biçimi bekleniyor.` | Bölüm içindeki bir satırda `=` işareti eksik. | Satırı `anahtar=değer` biçimine getirin veya başına `;` koyarak yorum satırı yapın. |
| `INI dosyası biçimi geçersiz (satır N): [list_text] satırı 'kimlik=kısayol=metin' biçiminde değil.` | `[list_text]` bölümündeki satırda iki adet `=` ayıracı yok (örneğin yalnızca `text_000=metin` yazılmış). | Satırı `text_000=L-Win+A=Metin<E<N<D|` biçimine düzeltin (kısayol yoksa `text_000==Metin<E<N<D|`). |
| `INI dosyası biçimi geçersiz (satır N): Geçersiz öğe kimliği '...'.` | `[list_text]` içindeki satır kimliği boş veya geçersiz karakter içeriyor. | `text_000` biçiminde alfasayısal + `_` kimlik kullanın. |
| `INI dosyası biçimi geçersiz (satır N): [list_order] sayısal değer bekliyor.` | `[list_order]` satırında `text_000=abc` gibi tamsayı olmayan bir değer var. | Sıra değerini tam sayıya (`1`, `2`, ...) çevirin. |

### 1.2 JSON, Yedekleme ve Ayar Hataları

| Birebir Mesaj | Olası Neden | Çözüm |
| :--- | :--- | :--- |
| `data.json çözümlenemedi: geçersiz JSON biçimi (...)` / `JSON dosyası ayrıştırılamadı: ...` | `data.json` veya tam yedek dosyasında sözdizimi hatası (eksik virgül, kapanmamış tırnak/parantez) var. | `backups/` klasöründeki son sağlıklı yedeği geri yükleyin veya JSON doğrulayıcı ile düzeltin. |
| `data.json biçimi geçersiz: kök eleman bir JSON dizisi ([...]) olmalıdır.` | `data.json` nesne (`{...}`) veya metin içeriyor; dizi (`[...]`) bekleniyor. | Kök yapının `[{"keys": ..., "group": ..., "text": ...}]` dizisi olduğundan emin olun. |
| `Desteklenmeyen dosya biçimi: Geçerli INI, JSON listesi ([...]) veya QTP Tam Yedek bekleniyor.` | Yüklenen JSON dosyası ne dizi ne de `type: "qtp-pwa-backup"` yapısında. | Doğru `data.json`, `qtp-tam-yedek-*.json` veya `QuickTextPaste.ini` dosyasını seçin. |
| `Yedek bulunamadı: ...` | İstenen yedek kimliği `backups/` klasöründe mevcut değil. | Tepsi → `Yedekler…` listesinden güncel bir yedek kimliği seçin. |
| `Bozuk ayar dosyası (...) algılandı; varsayılan ayarlarla yeniden oluşturuldu (...)` | `qtp_settings.json` bozulmuş veya geçersiz JSON içeriyor. | QTP otomatik olarak varsayılan ayarları geri yazar; özelleştirilmiş kısayollarınız varsa Ayarlar penceresinden yeniden girin. |

### 1.3 Platform, Yapıştırma, Kısayol ve CLI Hataları

| Birebir Mesaj | Olası Neden | Çözüm |
| :--- | :--- | :--- |
| `Wayland oturumunda 'wtype' veya 'ydotool' bulunamadı; yapay yapıştırma gerçekleştirilemedi.` | Linux Wayland üzerinde yapay tuş basımı için isteğe bağlı `wtype` veya `ydotool` kurulu değil. | Metin yine de panoya kopyalanır; otomatik `Ctrl+V` için `wtype`/`ydotool` kurabilir veya `Ctrl+V` ile elle yapıştırabilirsiniz (TUI/CLI/Web normal çalışmaya devam eder). |
| `Wayland oturumunda global kısayollar kısıtlıdır (...); uygulama tepsi/TUI/CLI/Web ile kullanılabilir.` | Wayland güvenlik modeli arka plan X11 global tuş dinlemeyi engelledi. | Başlangıç bloklanmaz; sistem tepsisinden katmanı açabilir veya `--tui`/`--cli`/`--web` modlarını kullanabilirsiniz. |
| `macOS Erişilebilirlik izni verilmemiş! Sistem Ayarları -> Gizlilik ve Güvenlik -> Erişilebilirlik altından QTP'ye izin verin.` | macOS güvenlik duvarı `qtp.bin` için klavye dinleme ve yapıştırma iznini henüz onaylamamış. | **Sistem Ayarları → Gizlilik ve Güvenlik → Erişilebilirlik** içinden `qtp.bin` uygulamasına izin verip yeniden başlatın. |
| `Global kısayol kaydedilemedi: ...` | Başka bir uygulama veya işletim sistemi (örneğin Windows `Win+A` / `Win+X`) aynı kısayolu kilitliyor. | Çakışan programı kapatın veya Ayarlar → Global Kısayollar altından alternatif tuş bileşimi (`Ctrl+Alt+A` vb.) tanımlayın. |
| `Pano erişimi başarısız: grafik oturumu veya pano desteği bulunamadı.` | Başsız Linux oturumunda DISPLAY/Qt/TTY yoksa panoya yazılamadı. | X11/GUI oturumu veya etkileşimli TTY (OSC 52) üzerinden çalıştırın. |
| `Tuş simülasyonu başarısız (yalnızca panoya kopyalandı): ...` | Hedef pencereye tuş gönderimi işletim sistemi tarafından engellendi. | Metin panoya alınmıştır; hedef uygulamada `Ctrl+V` / `Cmd+V` ile yapıştırın. |
| `Öğe bulunamadı: ...` | `--copy`, `--paste` veya `--show-ini` için verilen `raw_key` veya metin kayıtlar arasında yok. | `--list-items` veya `--search` çıktısındaki geçerli `text_NNN` anahtarını kullanın. |
| `Geçersiz ayar anahtarı: ...` / `Geçersiz ayar değeri ...` | `--set` veya `--get` ile desteklenmeyen alan adı ya da aralık dışı değer girildi. | `theme` (`auto/dark/light`), `web.port` (`0-65535`), `backup_count` (`1-100`) gibi geçerli değerler kullanın. |
| `HATA: Etkileşimsiz ortamda/CI içinde açıkça --mode {gui,tui,cli,web} belirtilmelidir.` | Pipe/CI ortamında hiçbir bayrak veya `--mode` verilmeden çalıştırıldı. | Betiklerde `--mode cli`, `--mode tui` veya `--mode web` belirtin. |
| `Güvenlik kuralı: Web sunucusu yalnızca 127.0.0.1 üzerinde çalışabilir` | Yerel web sunucusu LAN/0.0.0.0 arayüzüne bağlanmaya çalışırsa reddedilir. | Yalnızca `127.0.0.1` veya `localhost` üzerinden bağlanın (LAN yayını güvenlik gereği desteklenmez). |
| `HATA: Web sunucusu başlatılamadı (port kullanımda olabilir): ...` | Seçilen `web.port` (varsayılan `8765`) başka bir süreç tarafından kullanılıyor. | `--port 0` (otomatik port) veya başka bir port numarası (`--port 8877`) deneyin. |
| `Bilinmeyen API uç noktası: ...` | `--web` modunda tanımsız bir `/api/...` rotası çağrıldı. | Geçerli rotalar için `GET /api` uç noktasını sorgulayın. |
| `HATA: Yedek oluşturulamadı: ...` / `HATA: Tam yedek dışa aktarılamadı: ...` / `HATA: Kayıtlar yeniden yüklenemedi: ...` / `HATA: Yedek geri yüklenemedi: ...` | Disk yazma izni yok veya kaynak yedek dosyası bozuk. | Çalışma klasörünün yazılabilir olduğunu ve yedek dosyasının geçerli JSON/INI olduğunu doğrulayın. |
| `QTP zaten çalışıyor; mevcut pencere gösterildi ve ikinci örnek kapatıldı.` | Arka planda zaten bir QTP örneği açık (`qtp.lock`). | Normal davranıştır; çalışan katman otomatik olarak öne getirilir. |
| `HATA: Bilinmeyen komut satırı seçeneği: ...` | CLI üzerinden tanımlı olmayan bir bayrak geçirildi. | `qtp --help` çıktısındaki geçerli bayrakları kullanın. |
| `HATA: İçe aktarılacak INI dosyası bulunamadı: ...` | `--import-ini` ile verilen dosya yolu diskte mevcut değil. | Dosya yolunu ve yazımını kontrol edin. |
| `HATA: Dışa aktarılacak hazır cevap kaydı bulunamadı.` | Dışa aktarılacak liste boş. | En az bir geçerli `QuickTextPaste.ini` veya `data.json` bulunduğundan emin olun. |
| `HATA: Katman beklenen ... yerine ... satır listeledi.` | `--selftest` sırasında arayüz modeli beklenen kayıt sayısını yükleyemedi. | Paket bütünlüğünü kontrol edip uygulamayı yeniden derleyin. |
| `HATA: Arama kutusu otomatik odaklanamadı.` | `--selftest` sırasında arama alanı odak alamadı. | Qt platform eklentisini (`QT_QPA_PLATFORM=offscreen`) kontrol edin. |

---

## 2. Sık Karşılaşılan Sorunlar ve Çözümler

### Kısayollar Windows'ta Sistem Menüsünü Açıyor (`Win+A`, `Win+X`, `Win+Q`)
Windows 10/11 üzerinde `Win+A` (Hızlı Ayarlar), `Win+X` (Hızlı Bağlantı) ve `Win+Q` (Arama) sistem tarafından ayrılmış olabilir. QTP `pynput` başarısız olduğunda `keyboard` geri dönüşünü dener; yine de sistem menüsü açılıyorsa:
1. Ayarlar (`Ctrl+,`) penceresini açın.
2. Global Kısayollar bölümünde ilgili kısayolu örneğin `Ctrl+Alt+A` veya `Ctrl+Shift+A` olarak güncelleyin.

### Wayland Üzerinde Yapıştırma Çalışmıyor
- Sway / Hyprland kullanıyorsanız `wtype` paketini kurun.
- GNOME veya KDE Wayland kullanıyorsanız `ydotool` + `ydotoold` servisini etkinleştirin, ya da Ayarlar → Yapıştırma Yöntemi seçeneğini test edin.
- Kopyalama (`Panoya kopyalandı ✔`) Wayland üzerinde doğrudan çalışmaya devam eder; `Ctrl+V` ile manuel yapıştırabilirsiniz.

### GNOME Üzerinde Sistem Tepsisi Simgesi Görünmüyor
GNOME 40+ varsayılan olarak tepsi simgelerini gizler. Dağıtımınızdan `gnome-shell-extension-appindicator` paketini kurup etkinleştirin. Tepsi gizli olsa bile `Ctrl+Shift+Space` ile katmanı açabilir ve **Ayarlar** düğmesine erişebilirsiniz.

### `qtp.lock` Kilit Dosyası Takılı Kaldı
Uygulama elektrik kesintisi veya `kill -9` ile zorla sonlandırıldıysa `qtp.lock` dosyası diskte kalabilir. QTP bir sonraki açılışta eski portun yanıt vermediğini otomatik algılar, bayat kilit dosyasını siler ve normal şekilde açılır. Yine de sorun yaşarsanız `qtp.lock` dosyasını elinizle silebilirsiniz.

### `QuickTextPaste.ini` Türkçe Karakterleri Bozuk Görünüyor
Eski `QuickTextPaste.ini` dosyaları bazen `cp1254` (Windows Türkçe) veya BOM'suz `UTF-16` olabilir. QTP her açılışta kodlamayı otomatik algılar ve kayıt sırasında tüm Türkçe karakterler ile emojileri koruyan `UTF-16 LE BOM` biçimine dönüştürür.
