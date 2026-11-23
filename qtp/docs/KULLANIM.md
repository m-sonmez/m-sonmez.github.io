# QTP Kullanım Kılavuzu

**QTP (QuickTextPaste / Hazır Cevaplar)**, sık kullandığınız destek yanıtlarını ve metin şablonlarını çakışmasız global kısayollarla (`Win+Alt+Space / A / Z / X / Q`) anında aramanızı, kategoriye göre filtrelemenizi, dosya değişikliklerini yeniden başlatmadan canlı yenilemenizi ve tek tuşla aktif pencereye yapıştırmanızı sağlayan çevrimdışı masaüstü uygulamasıdır.

---

## 1. Katmanı (Overlay) Açma ve İlk Çalıştırma

Uygulama ilk kez çalıştırıldığında:
- Yönetici izni veya kurulum sihirbazı olmadan doğrudan açılır.
- Ekranın ortasında `720×520` piksel boyutunda katman penceresi görünür ve sağ alt köşede etkin kısayolları gösteren *"QTP hazır. Win+Alt+Space / Win+Alt+A / Win+Alt+Z / Win+Alt+X / Win+Alt+Q"* bildirimi 2,6 saniye süreyle gösterilir.
- Eski v2.0/v2.1 `qtp_settings.json` dosyanızda el değmemiş eski çakışmalı varsayılanlar (`Ctrl+Shift+Space`, `Win+A/Z/X/Q`) varsa QTP bunu algılayıp bir kez otomatik olarak yeni `recommended` (`Win+Alt+*`) profiline yükseltir; **özelleştirilmiş kısayollarınız hiçbir zaman üzerine yazılmaz**.
- Sonraki açılışlarda katman gizliyken şu yollarla açabilirsiniz:
  - **Global kısayollar:** `Win+Alt+Space`, `Win+Alt+A`, `Win+Alt+Z`, `Win+Alt+X`, `Win+Alt+Q` (veya özelleştirdiğiniz tüm 15 değiştirici bileşimi / özel yuvalar).
  - **Sistem tepsisi:** Tepsi simgesine **çift tıklayın** veya sağ tıklayıp **Aç (Win+Alt+Space)** *(etkin `all` kısayoluyla dinamik güncellenir)* seçin.
  - **İkinci çalıştırma:** `qtp.exe` / `qtp.bin` tekrar çalıştırıldığında çalışan örnek otomatik olarak öne getirilir.

---

## 2. Kategori Sekmeleri ve Hafıza

Arama kutusunun hemen altında 5 adet kategori hapı bulunur (`QuickTextPaste.ini` içindeki `L-Win+A/Z/X/Q/W/1` önekleri kayıpsız korunur):

| Sekme Etiketi | Varsayılan Global Kısayol | Açıklama |
| :--- | :--- | :--- |
| **Tümü** | `Win+Alt+Space` | Tüm kategorilerdeki hazır cevapları (`W` ve `1` kısayolları dahil) birlikte gösterir. |
| **A · İş Ortağı** | `Win+Alt+A` | `L-Win+A` önekli Yemeksepeti İş Ortağı (Restoran) hazır cevaplarını listeler. |
| **Z · Kurye** | `Win+Alt+Z` | `L-Win+Z` önekli Yemeksepeti Kurye hazır cevaplarını listeler. |
| **X · Canlı Yardım** | `Win+Alt+X` | `L-Win+X` önekli Müşteri Canlı Yardım hazır cevaplarını listeler. |
| **Q · Turkcell** | `Win+Alt+Q` | `L-Win+Q` önekli Turkcell destek hazır cevaplarını listeler. |

Her kategori hapı üzerinde güncel kayıt sayısını parantez içinde gösterir (örneğin `A · İş Ortağı (110)`). QTP, hangi global kısayol ile hangi kategoriyi en son kullandığınızı `qtp_settings.json` içinde hatırlar.

---

## 3. Türkçe Uyumlu Bulanık Arama (Fuzzy Search)

Katman açılır açılmaz imleç otomatik olarak üstteki **"Ara… (mesaj, kategori, etiket)"** kutusundadır. Yazmaya başladığınız anda liste canlı olarak filtrelenir:

- **Türkçe yerel harf uyumu:** `İ/i`, `I/ı`, `Ş/ş`, `Ğ/ğ`, `Ç/ç`, `Ö/ö`, `Ü/ü` harfleri Türkçe kurallarına göre eşleştirilir.
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

### 4.2 Yalnızca Panoya Kopyalama (`Ctrl+Enter`, `Shift+Tık`, Satır İçi Düğme)
- `Ctrl+Enter` (macOS'ta `⌘+Enter`), satıra `Shift+Sol Tık` veya satır üzerindeki **Kopyala** düğmesi katmanı kapatmadan metni panoya alır ve *"Panoya kopyalandı ✔"* bildirimini gösterir.

---

## 5. Sağ Tık Bağlam Menüsü

Liste satırı üzerinde sağ tıkladığınızda önce kayıt panoya alınır ve dört seçenekli menü açılır:
- **Yapıştır**, **Kopyala**, **INI'de Göster** (`[list_text]`, `[list_order]`, `[list_label]` ham görünümü) ve **Yardım** (`F1`).

---

## 6. Sistem Tepsisi Menüsü

Sistem tepsisindeki mor şimşek simgesine sağ tıkladığınızda tüm platformlarda aynı Türkçe menü açılır:
- **Aç (`Win+Alt+Space`):** Katmanı ekrana getirir (etkin `all` kısayoluna göre dinamik güncellenir).
- **Ayarlar…**, **INI Yeniden Yükle**, **data.json Aç**, **Yedekler…**, **Yardım (F1)** ve **Çıkış**.

---

## 7. Ayarlar Penceresi, Esnek Kısayollar ve Canlı Yenileme (`qtp_settings.json`)

Ayarlar penceresine **Ayarlar** düğmesi, `Ctrl+,` veya sistem tepsisi üzerinden ulaşabilirsiniz:

- **Hazır Profil ve Toplu Değiştirici:** Tek tıkla `Önerilen (Win+Alt)`, `Win+Ctrl`, `Ctrl+Alt`, `Üçlü Değiştirici (Ctrl+Alt+Shift)`, `Fonksiyon Tuşları (Ctrl+Shift+F1–F5)` veya `Klasik QuickTextPaste (Win)` profilini seçebilir ya da **Tümüne Değiştirici Uygula** ile mevcut yuvaların ön ekini topluca değiştirebilirsiniz.
- **Esnek Kısayol Satırı (`HotkeyRow`):** Her kısayol için **4 değiştirici onay kutusu** (`Ctrl`, `Alt`, `Shift`, `Win`), klavyeden doğrudan kayıt yapabilen **Yakala / `HotkeyEdit`** kutusu (çift yönlü senkronize) ve **+ Özel Kısayol Ekle** / `×` düğmeleri sunulur.
- **Canlı Çakışma Uyarıcısı:** Değişiklik yaptığınız anda Windows sistem kısayolları, Türkçe-Q `AltGr` tuşları (`Ctrl+Alt+Q/A/E/S/1..9`), Linux TTY geçişleri ve çift atamalar anında Türkçe olarak raporlanır. Çift QTP atamaları kaydetmede engellenir.

| Ayar Alanı (`qtp_settings.json`) | Varsayılan | Açıklama |
| :--- | :--- | :--- |
| `theme` | `"dark"` | Arayüz teması: `auto`, `dark` veya `light`. |
| `hotkeys` | `Win+Alt+Space/A/Z/X/Q` | Global kısayol haritası (`all`, `A`, `Z`, `X`, `Q` ve isteğe bağlı özel yuvalar). |
| `last_category` | `"ALL"` | Genel açılışta son seçili kategori (`ALL`, `A`, `Z`, `X`, `Q`). |
| `last_category_by_hotkey` | `{}` | Her kısayol için en son seçilen sekme hafızası. |
| `window_size` | `[720, 520]` | Katman penceresi piksel `[genişlik, yükseklik]` boyutu. |
| `paste_method` | `"auto"` | `auto`, `ctrl_v`, `shift_insert` veya `type`. |
| `enter_after_paste` | `true` | `<E<N<D|` sonrası otomatik `Enter`. |
| `start_minimized` | `false` | Sistem tepsisinde küçültülmüş başlatma. |
| `tray_icon` | `true` | Sistem tepsisi simgesi görünürlüğü. |
| `data_path` | `"./QuickTextPaste.ini"` | İzlenen ve yüklenen `QuickTextPaste.ini` dosya yolu. |
| `backup_count` | `15` | `backups/` dizinindeki en yeni yedek sayısı (`1–100`). |
| `auto_reload` | `true` | `qtp_settings.json`, `QuickTextPaste.ini` ve `data.json` değişikliklerini yeniden başlatmadan canlı yeniler. |
| `auto_reload_interval_ms` | `500` | Disk izleme denetim aralığı (`100–10000 ms`, `250 ms` debounce). |
| `log_level` | `"info"` | `qtp.log` ayrıntı düzeyi (`debug`, `info`, `warn`, `error`). |
| `language` | `"tr"` | Arayüz dili (`tr`). |
| `web.port` | `{"port": 8765}` | `--web` sunucusu yerel `127.0.0.1` bağlantı noktası (`0–65535`). |

---

## 8. Dinamik Canlı Otomatik Yenileme (`auto_reload`)

`--gui`, `--web` ve etkileşimli `--tui` modları çalışırken sıfır bağımlılıklı `ConfigFileWatcher` bileşeni diskteki `qtp_settings.json`, etkin `QuickTextPaste.ini` (`data_path`) ve `data.json` dosyalarını arka planda izler (`--selftest` / `--version` / `--completion` gibi tek seferlik CLI komutları arka plan iş parçacığı açmaz ve dosya oluşturmaz):
- **Ayar Değişiklikleri:** Harici bir düzenleyiciyle `qtp_settings.json` değiştirildiğinde tema, pencere boyutu, `data_path`, günlük düzeyi (`log_level`) ve **işletim sistemine kayıtlı global kısayollar** yeniden başlatma olmadan anında güncellenir (eski kısayollar çözülür, yenileri `RegisterHotKey` / `pynput` ile bağlanır).
- **Veri Değişiklikleri:** `QuickTextPaste.ini` veya `data.json` harici bir düzenleyici tarafından değiştirildiğinde (atomik `os.replace` dahil) liste canlı yenilenir.
- **Kendi Yazımını Bastırma ve Bozuk Dosya Koruması:** QTP'nin kendi kaydettiği dosyalar yankı yenilemeye neden olmaz; harici yazım sırasında dosya bozuk/eksikse son geçerli ayar ve kayıt listesi korunur ve `qtp.log` / uyarı bildirimi yazılır.

---

## 9. INI ve JSON Dosyalarıyla Çalışma, Yedeklemeler ve Günlükler (`qtp.log`)

- **Çoklu Kodlama Desteği:** `UTF-16 LE BOM`, `UTF-16 BE BOM`, BOM'suz `UTF-16`, `UTF-8 BOM`, `UTF-8` ve Türkçe `cp1254` kodlamaları otomatik algılanır; `[Program]`, ek bölümler ve `<E<N<D|` işaretleri kayıpsız korunur.
- **Zaman Damgalı Yedekler (`backups/`) ve Tam Yedek (`qtp-tam-yedek-*.json`):** Her kaydetme öncesinde otomatik yedek alınır; `.bak` yedeği ve 1 MB × 3 dönen `qtp.log` günlükleri tutulur.

---

## 10. Komut Satırı (CLI) Seçenekleri, Ayrıntı Düzeyi ve Otomatik Tamamlama

- **Etkileşimli Windows Konsolu:** Windows tek-dosya (`console=False`) ikilisinde `--help`, `--verbose`, `--completion`, `--cli`, `--web` veya `--tui` çalıştırıldığında QTP üst süreç zincirini (`PowerShell`/`pwsh`/`cmd`/Terminal) yürüyerek UTF-8 konsol akışlarını `argparse`'dan hemen önce otomatik bağlar; çift tık ve sessiz `--gui` açılışlarında ise siyah konsol penceresi açmaz.
- **Modlar Arası Eşit `--help`, `-v`/`--verbose`/`-vv` ve `-q`/`--quiet`:**
  - `qtp --cli --help`, `qtp --web --help`, `qtp --tui --help`, `qtp --gui --help` (ve tüm `--verbose --help` bileşimleri, bayrak sırasından bağımsız olarak) yan etkisiz çalışır (diskte hiç dosya oluşturmaz), aynı kanonsal Türkçe yardımı yazar ve `0` ile çıkar.
  - `-v` / `-vv`: Dört modun tamamında (`--cli`, `--web`, `--tui`, `--gui`) `stderr` akışına tek tip `[INFO]` / `[DEBUG]` tanılama kayıtları akıtır (`--web` HTTP istekleri, `--gui` kısayol/Qt yüklemesi, `--tui` arka ucu dahil); `stdout` JSON ve TUI ekranı kirletilmez.
  - `-q` / `--quiet`: Tüm modlarda başlangıç ve bilgi afişlerini (`QTP Web Modu çalışıyor: ...`, TUI/GUI başlangıç balonu, CLI durum satırları) gizler (`-v` açıkça verilmediyse); hataları `stderr` üzerinde daima korur.
  - `--category` ve `--query`: Dört modun tamamında (`--cli`, `--tui`, `--gui`, `--web`) açılışta aynı başlangıç kategori ve arama filtresini uygular.
- **Kabuk Otomatik Tamamlama (`--completion [powershell|bash|zsh|fish]`):** Geçerli bayraklar ve ayar anahtarlarından dinamik tamamlama betiği üretir ve hiçbir yan etki dosyası oluşturmaz:
  - PowerShell: `.\qtp.exe --completion powershell | Out-String | Invoke-Expression`
  - Bash: `eval "$(./qtp.bin --completion bash)"`
  - Zsh: `eval "$(./qtp.bin --completion zsh)"`
  - Fish: `./qtp.bin --completion fish | source`

---

## 11. TUI Modu (`--tui`) ve Web Modu (`--web`)

- **`--tui`:** Python standart kütüphanesi dışında bağımlılık gerektirmez; Linux/macOS'ta `curses` (veya `termios`/düz metin), Windows'ta VT100 veya Win32 Console API kullanır. Canlı oturumda dosya değişikliklerini otomatik yansıtır; `F1` yardım modalında eksiksiz dört bölümlü içeriği (`CLI & Parametreler`, `Kullanım`, `Kısayollar`, `SSS`) `↑`/`↓` ve `PageUp`/`PageDown` kaydırmasıyla sunar ve `k` (çakışma denetimi), `P` (önerilen profil), `C` (tamamlama) tuşlarını destekler.
- **`--web`:** Yalnızca `127.0.0.1` loopback üzerinde çalışan çevrimdışı HTTP/JSON arayüzüdür; **Yardım (F1)** düğmesi / `F1` tuşu (`/api/help?verbose=1`), **Kısayollar** modalı, canlı `/api/revision` yenilemesi (başlangıç `--category`/`--query` dahil) ve `/api/hotkeys/*`, `/api/completion` uç noktalarını sunar (`POST /api/shutdown` ile zarifçe kapanır).
- **`--gui` `F1` Yardım Penceresi:** `Kullanım Kılavuzu`, `Kısayollar`, `Sorun Giderme (SSS)` sekmelerine ek olarak **CLI & Parametreler** sekmesinde birebir `--verbose --help` başvurusunu içerir.

---

## 12. Modlar Arası Eşitlik Matrisi

Tüm işlemler ortak [operations.py](../qtp_app/core/operations.py) kayıt defteri ve [engine.py](../qtp_app/core/engine.py) üzerinden çalıştırılır:

| İşlem (`op_id`) | `--gui` | `--tui` | `--cli` | `--web` |
| :--- | :--- | :--- | :--- | :--- |
| `version` | Tepsi / Yardım (F1) | `V` | `--version` | `GET /api/version` |
| `help` | `F1` / Tepsi → Yardım (F1) | `F1` | `--help` | `GET /api/help` |
| `selftest` | Başlangıç Doğrulama | `T` | `--selftest` | `GET /api/selftest` |
| `modes` | Yardım (F1) → Modlar | `M` | `--modes` | `GET /api/modes` |
| `completion` | Yardım (F1) → Otomatik Tamamlama | `C` | `--completion` | `GET /api/completion` |
| `list_categories` | Kategori Hapları (`Tümü` / `A` / `Z` / `X` / `Q`) | `Tab` / `1–5` | `--list-categories` | `GET /api/categories` |
| `list_items` | Sanal Liste (`QListView`) | `↑` / `↓` | `--list-items` | `GET /api/items` |
| `search` | `Ctrl+K` / Arama Kutusu | `/` | `--search <q>` | `GET /api/search?q=` |
| `show_ini` | Sağ Tık → INI'de Göster | `e` | `--show-ini <hedef>` | `GET /api/show-ini` |
| `copy` | `Ctrl+Enter` / `Shift+Tık` / Kopyala | `c` | `--copy <hedef>` | `POST /api/copy` |
| `paste` | `Enter` / Sol Tık | `Enter` | `--paste <hedef>` | `POST /api/paste` |
| `export_ini` | Tepsi / Yedekler → INI Dışa Aktar | `x` | `--export-ini <yol>` | `POST /api/export-ini` |
| `import_ini` | Tepsi / INI İçe Aktar | `i` | `--import-ini <yol>` | `POST /api/import-ini` |
| `export_backup` | Tepsi → Yedekler… → Tam Yedek Dışa Aktar | `B` | `--export-backup <yol>` | `POST /api/export-backup` |
| `restore` | Tepsi → Yedekler… → Seçileni Geri Yükle | `R` | `--restore <hedef>` | `POST /api/restore` |
| `backup` | Tepsi → Yedekler… → Anlık Yedek Al | `b` | `--backup` | `POST /api/backup` |
| `reload` | Tepsi → INI Yeniden Yükle | `r` | `--reload` | `POST /api/reload` |
| `get_setting` | `Ctrl+,` / Ayarlar Penceresi | `s` | `--get <anahtar>` | `GET /api/settings` |
| `set_setting` | `Ctrl+,` / Ayarlar → Kaydet | `s` | `--set <anahtar> <değer>` | `POST /api/settings` |
| `check_hotkeys` | `Ctrl+,` / Ayarlar → Global Kısayollar | `k` | `--check-hotkeys` | `GET /api/hotkeys/check` |
| `hotkey_preset` | `Ctrl+,` / Ayarlar → Kısayol Profili | `P` | `--hotkey-preset <profil>` | `POST /api/hotkeys/preset` |
| `hotkey_modifiers` | `Ctrl+,` / Ayarlar → Tümüne Değiştirici Uygula | `O` | `--hotkey-modifiers <değ.>` | `POST /api/hotkeys/modifiers` |
