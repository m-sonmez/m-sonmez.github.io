# QTP Kullanım Kılavuzu

**QTP (QuickTextPaste / Hazır Cevaplar)**, sık kullandığınız destek yanıtlarını ve metin şablonlarını global kısayollarla anında aramanızı, kategoriye göre filtrelemenizi ve tek tuşla aktif pencereye yapıştırmanızı sağlayan çevrimdışı masaüstü uygulamasıdır.

---

## 1. Katmanı (Overlay) Açma ve İlk Çalıştırma

Uygulama ilk kez çalıştırıldığında:
- Yönetici izni veya kurulum sihirbazı olmadan doğrudan açılır.
- Ekranın ortasında `720×520` piksel boyutunda katman penceresi görünür ve sağ alt köşede *"QTP hazır. Win+Z / Win+A / Win+X / Win+Q"* bildirimi 2,6 saniye süreyle gösterilir.
- Sonraki açılışlarda katman gizliyken şu yollarla açabilirsiniz:
  - **Global kısayollar:** `Win+A`, `Win+Z`, `Win+X`, `Win+Q` veya `Ctrl+Shift+Space`.
  - **Sistem tepsisi:** Tepsi simgesine **çift tıklayın** veya sağ tıklayıp **Aç (Ctrl+Shift+Space)** seçin.
  - **İkinci çalıştırma:** `qtp.exe` / `qtp.bin` tekrar çalıştırıldığında çalışan örnek otomatik olarak öne getirilir.

> `[Ekran Görüntüsü Açıklaması: Aktif ekranın tam ortasında 12 px yuvarlatılmış köşeli, koyu #121216 yarı saydam arka planlı 720×520 px QTP katman penceresi. En üstte otomatik odaklanmış arama kutusu ve sağında "Ctrl+K" çipi; hemen altında mor-camgöbeği geçişli aktif kategori hapları; ortada 2 satırlı metin önizlemeli sanal liste ve her satırın sağında "A/Z/X/Q" rozeti ile "Kopyala" düğmesi; en altta klavye ipuçları ve kayıt sayacı yer alır.]`

---

## 2. Kategori Sekmeleri ve Hafıza

Arama kutusunun hemen altında 5 adet kategori hapı bulunur:

| Sekme Etiketi | İlişkili Global Kısayol | Açıklama |
| :--- | :--- | :--- |
| **Tümü** | `Ctrl+Shift+Space` | Tüm kategorilerdeki hazır cevapları (`W` ve `1` kısayolları dahil) birlikte gösterir. |
| **A · İş Ortağı** | `Win+A` | `L-Win+A` önekli Yemeksepeti İş Ortağı (Restoran) hazır cevaplarını listeler. |
| **Z · Kurye** | `Win+Z` | `L-Win+Z` önekli Yemeksepeti Kurye hazır cevaplarını listeler. |
| **X · Canlı Yardım** | `Win+X` | `L-Win+X` önekli Müşteri Canlı Yardım hazır cevaplarını listeler. |
| **Q · Turkcell** | `Win+Q` | `L-Win+Q` önekli Turkcell destek hazır cevaplarını listeler. |

Her kategori hapı üzerinde güncel kayıt sayısını parantez içinde gösterir (örneğin `A · İş Ortağı (110)`). QTP, hangi global kısayol ile hangi kategoriyi en son kullandığınızı `qtp_settings.json` içinde hatırlar.

---

## 3. Türkçe Uyumlu Bulanık Arama (Fuzzy Search)

Katman açılır açılmaz imleç otomatik olarak üstteki **"Ara… (mesaj, kategori, etiket)"** kutusundadır. Yazmaya başladığınız anda liste canlı olarak filtrelenir:

- **Türkçe yerel harf uyumu:** `İ/i`, `I/ı`, `Ş/ş`, `Ğ/ğ`, `Ç/ç`, `Ö/ö`, `Ü/ü` harfleri Türkçe kurallarına göre eşleştirilir (örneğin `"şifre"` yazımı `"Şifrenizi"` kaydını bulur; `"ı"` ve `"i"` ayrımları korunur).
- **Alt-dizi (Subsequence) arama:** Kelimeleri tam yazmanız gerekmez; harf sırasını koruyan kısaltmalar eşleşir ve eşleşen karakterler metin içinde camgöbeği/mor vurgu ile işaretlenir.
- **Kapsam:** Arama metin içeriği, başlık (`label`), grup adı (`group`) ve kısayol rozeti üzerinde puanlama yapar.
- **Boş arama:** Arama kutusu temizlendiğinde öğeler orijinal `QuickTextPaste.ini` sırasıyla gösterilir.
- İstediğiniz an `Ctrl+K` (macOS'ta `⌘K` de çalışır) ile arama kutusuna odaklanıp metni seçebilirsiniz.

---

## 4. Yapıştırma ve Yalnızca Kopyalama

### 4.1 Doğrudan Aktif Uygulamaya Yapıştırma (`Enter` veya Sol Tık)
1. Listede `↑` / `↓` veya `PageUp` / `PageDown` tuşlarıyla kaydı seçin (veya doğrudan satıra sol tıklayın).
2. `Enter` tuşuna basın.
3. QTP katmanı gizler, odağı katman açılmadan önce önde olan uygulamaya (tarayıcı, sohbet paneli, not defteri vb.) geri verir, `120 ms` bekler ve seçili metni panoya kopyalayıp `Ctrl+V` (macOS'ta `Cmd+V`, Wayland'da `wtype`) gönderir.
4. **`<E<N<D|` Bitiş İşareti:** Kayıt `QuickTextPaste.ini` içinde `<E<N<D|` ile bitiyorsa ve ayarlardan `enter_after_paste` etkinse, yapıştırmadan hemen sonra otomatik olarak bir `Enter` tuşu gönderilir.
5. İşlem sonunda katman kapanmadan önceki pencerede metin yapışmış olur; katman yeniden açıldığında veya bildirim aktifken *"Yapıştırıldı ✔"* bildirimi gösterilir.

### 4.2 Yalnızca Panoya Kopyalama (`Ctrl+Enter`, `Shift+Tık`, Satır İçi Düğme)
Katmanı kapatmadan metni yalnızca panoya almak için:
- `Ctrl+Enter` (macOS'ta `⌘+Enter` da geçerlidir) tuşlayın, **veya**
- Satıra `Shift` tuşunu basılı tutarak sol tıklayın, **veya**
- Fareyi satırın üzerine getirdiğinizde sağda beliren **Kopyala** düğmesine tıklayın.

Katman açık kalır ve sağ alt köşede 1,2 saniyelik *"Panoya kopyalandı ✔"* bildirimi görünür.

---

## 5. Sağ Tık Bağlam Menüsü

Liste satırı üzerinde sağ tıkladığınızda önce kayıt panoya alınır ve dört seçenekli menü açılır:

- **Yapıştır:** Seçili kaydı önceki aktif uygulamaya yapıştırır.
- **Kopyala:** Metni yalnızca panoya kopyalar.
- **INI'de Göster:** Seçili kaydın `QuickTextPaste.ini` içindeki `[list_text]`, `[list_order]` ve `[list_label]` ham satırlarını salt-okunur önizleme penceresinde gösterir.
- **Yardım:** Uygulama içi Türkçe yardım penceresini (`F1`) açar.

---

## 6. Sistem Tepsisi Menüsü

Sistem tepsisindeki mor şimşek simgesine sağ tıkladığınızda tüm platformlarda aynı Türkçe menü açılır:

- **Aç (Ctrl+Shift+Space):** Katmanı ekrana getirir.
- **Ayarlar…:** Ayarlar penceresini açar.
- **INI Yeniden Yükle:** Diskteki `QuickTextPaste.ini` / `data.json` dosyasını yeniden okur ve listeyi günceller.
- **data.json Aç:** Çalışma dizinindeki `data.json` dosyasını varsayılan sistem düzenleyicinizle açar (henüz yoksa oluşturur).
- **Yedekler…:** Yedekleme ve geri yükleme penceresini açar.
- **Yardım (F1):** Bu kullanım kılavuzunu, kısayollar tablosunu ve sorun giderme rehberini açar.
- **Çıkış:** Global kısayolları serbest bırakır, `qtp.lock` kilit dosyasını temizler ve uygulamayı kapatır.

> `[Ekran Görüntüsü Açıklaması: Sistem tepsisinden açılan 7 maddeli Türkçe menü; en üstte "Aç (Ctrl+Shift+Space)", ortada Ayarlar, INI Yeniden Yükle, data.json Aç, Yedekler…, altta Yardım (F1) ve Çıkış öğeleri.]`

---

## 7. Ayarlar Penceresi ve `qtp_settings.json`

Ayarlar penceresine katmandaki **Ayarlar** düğmesinden, `Ctrl+,` kısayolundan veya sistem tepsisi menüsünden ulaşabilirsiniz. Tüm alanlar `qtp_settings.json` dosyasında saklanır ve fareyle üzerine gelindiğinde Türkçe ipucu (tooltip) gösterir:

| Ayar Alanı (`qtp_settings.json`) | Varsayılan | Açıklama |
| :--- | :--- | :--- |
| `theme` | `"dark"` | Arayüz teması: `auto` (işletim sistemi temasını izler), `dark` (koyu tema), `light` (açık tema). |
| `hotkeys` | `all`, `A`, `Z`, `X`, `Q` | Global kısayol haritası (`Ctrl+Shift+Space`, `Win+A`, `Win+Z`, `Win+X`, `Win+Q`). Kaydedildiğinde eski kısayollar temizlenir ve yenileri anında atanır. |
| `last_category` | `"ALL"` | Genel kısayolla açılışta seçilecek son kategori kodu (`ALL`, `A`, `Z`, `X`, `Q`). |
| `last_category_by_hotkey` | `{}` | Her tetiklenen global kısayol için en son seçilen kategori sekmesini saklar. |
| `window_size` | `[720, 520]` | Katman penceresinin piksel cinsinden `[genişlik, yükseklik]` boyutu. Pencere sağ alt köşeden yeniden boyutlandırıldığında otomatik kaydedilir. |
| `paste_method` | `"auto"` | Yapıştırma yöntemi: `auto` (Windows/Linux `Ctrl+V`, macOS `Cmd+V`, Wayland `wtype`), `ctrl_v`, `shift_insert` veya `type` (tuş tuş yazma). |
| `enter_after_paste` | `true` | Kayıt `<E<N<D|` ile bitiyorsa yapıştırmadan hemen sonra otomatik `Enter` gönderir. |
| `start_minimized` | `false` | Etkinleştirilirse uygulama başlangıçta katmanı açmadan doğrudan sistem tepsisinde bekler. |
| `tray_icon` | `true` | Sistem tepsisi simgesini gösterir veya gizler. |
| `data_path` | `"./QuickTextPaste.ini"` | Okunacak ve güncellenecek `QuickTextPaste.ini` dosyasının konumu. |
| `backup_count` | `15` | `backups/` dizininde saklanacak en fazla otomatik/manuel yedek sayısı (`1–100`). |
| `log_level` | `"info"` | `qtp.log` günlük dosyası ayrıntı düzeyi (`debug`, `info`, `warn`, `error`). |
| `language` | `"tr"` | Arayüz dili (yalnızca `"tr"`; gelecek sürümler için ayrılmıştır). |

Pencere altındaki **Kaydet**, **İptal**, **Varsayılana Sıfırla** ve **Yardım** düğmeleri ile ayarları güvenle yönetebilirsiniz.

> `[Ekran Görüntüsü Açıklaması: Görünüm ve Davranış, Yapıştırma Ayarları, Global Kısayollar ve Veri/Yedekleme/Günlük gruplarına bölünmüş 560×610 px QTP Ayarlar penceresi. Alt kısımda Yardım, Varsayılana Sıfırla, İptal ve mor-camgöbeği vurgulu Kaydet düğmeleri bulunur.]`

---

## 8. INI ve JSON Dosyalarıyla Çalışma (Yükleme, İçe/Dışa Aktarma)

- **Çoklu Kodlama Desteği:** QTP; `UTF-16 LE BOM` (QuickTextPaste yerel biçimi), `UTF-16 BE BOM`, BOM'suz `UTF-16`, `UTF-8 BOM`, `UTF-8` ve Türkçe `cp1254` kodlamalı `.ini` dosyalarını otomatik algılar ve bozulmadan okur.
- **Kayıpsız Koruma:** `[Program]` içindeki tüm anahtarlar (`TestIni`, `m_show_tree`, `listcmd_count`, `WinRC`, `lng`, `start_tray`, özel anahtarlar), ek INI bölümleri, `/` alt menüleri ve `<E<N<D|` sonlandırıcıları korunur.
- **Otomatik `.bak` Yedeği:** INI dosyası üzerine her yazma işleminde önceki sürüm `QuickTextPaste.ini.bak` olarak yedeklenir.
- **Komut Satırı Dışa/İçe Aktarma:**
  ```bash
  qtp --export-ini yedek_cikti.ini
  qtp --import-ini yeni_cevaplar.ini
  ```
  `--import-ini`, mevcut `data.json` kayıtlarınızı silmeden yeni kayıtları birleştirir ve otomatik yedek oluşturur.

---

## 9. Yedeklemeler ve Günlük Kayıtları (`qtp.log`)

- **Zaman Damgalı Yedekler (`backups/`):** İçe aktarma veya manuel yedekleme öncesinde `data.json`, `QuickTextPaste.ini` ve `.qtp_state.json` dosyaları `backups/<tarih>_<neden>/` klasörüne kopyalanır. En yeni `backup_count` (varsayılan 15) adet yedek saklanır.
- **Tam Yedek (`qtp-tam-yedek-YYYY-MM-DD.json`):** Web PWA uygulamasıyla (`index.html`) %100 uyumlu `qtp-pwa-backup` v2 biçiminde tek dosya tam yedek üretir ve geri yükler.
- **Dönen Günlükler (`qtp.log`):** İkili dosyanın yanında en fazla 1 MB boyutunda 3 adet dönen günlük dosyası tutulur (`qtp.log`, `qtp.log.1`, `qtp.log.2`, `qtp.log.3`). Katmanın açılması, yapıştırılan öğenin kategorisi ve ham anahtarı, INI yeniden yükleme, ayar değişiklikleri, kısayol kayıtları ve hata izleri kaydedilir.

---

## 10. Komut Satırı (CLI) Seçenekleri

Tüm platformlarda aynı komut satırı bayrakları desteklenir:

| Seçenek | Açıklama |
| :--- | :--- |
| `-h`, `--help` | Türkçe komut satırı yardım özetini yazdırır ve çıkar. |
| `--version` | Uygulama sürümünü, derleme tarihini ve varsa Git kısa özetini yazdırır. |
| `--selftest` | Başsız (offscreen) arayüz duman testi ile gömülü `QuickTextPaste.ini` gidiş-dönüş testini çalıştırır; başarılıysa `0` ile çıkar. |
| `--export-ini YOL` | Mevcut hazır cevapları UTF-16 LE BOM kodlamalı `QuickTextPaste.ini` olarak belirtilen yola yazar. |
| `--import-ini YOL` | Belirtilen INI dosyasını mevcut listeyle birleştirir ve kaydeder. |
| `--work-dir DIZIN` | Veri, ayar ve yedekleme işlemleri için özel bir çalışma dizini belirtir. |
