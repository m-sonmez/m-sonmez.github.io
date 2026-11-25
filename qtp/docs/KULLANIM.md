# QTP Kullanım Kılavuzu / Usage Guide (`v2.5.0`)

**QTP (QuickTextPaste & Snippet Manager)**, sık kullandığınız metin şablonlarını ve hazır kayıtları tamamen yapılandırma odaklı kategoriler ve çakışmasız global kısayollarla (`Win+Alt+Space` ve dilediğiniz dinamik yuvalar) anında aramanızı, filtrelemenizi, dosya değişikliklerini yeniden başlatmadan canlı yenilemenizi ve tek tuşla aktif pencereye yapıştırmanızı sağlayan evrensel çevrimdışı uygulamadır.

> **English Quick Start:** Run `qtp` (GUI), `qtp --tui`, `qtp --web --open-browser`, or `qtp --cli --help`. Only virtual `All` is built in — define custom categories in `qtp_settings.json`, GUI **Settings**, or Web **Categories**, or drop any existing `QuickTextPaste.ini` / `data.json` into the folder to auto-discover categories. Switch UI language via `language` (`"auto"`, `"en"`, `"tr"`) or provide a custom `<config_dir>/qtp_locale.json`.

---

## 1. Katmanı (Overlay) Açma ve İlk Çalıştırma

Uygulama ilk kez çalıştırıldığında:
- Yönetici izni veya kurulum sihirbazı olmadan doğrudan açılır.
- Ekranın ortasında `720×520` piksel boyutunda katman penceresi görünür ve etkin global kısayolları gösteren başlangıç bildirimi 2,6 saniye süreyle gösterilir.
- Eski v2.0 `qtp_settings.json` dosyanızda el değmemiş eski çakışmalı varsayılanlar (`Ctrl+Shift+Space` + `Win+*`) varsa QTP bunu algılayıp bir kez otomatik olarak `recommended` (`Win+Alt+*`) profiline yükseltir; **özelleştirilmiş kısayollarınız hiçbir zaman üzerine yazılmaz**.
- Sonraki açılışlarda katman gizliyken şu yollarla açabilirsiniz:
  - **Global kısayollar:** Varsayılan `Win+Alt+Space` (`all`) veya özelleştirdiğiniz tüm 15 değiştirici bileşimi / dinamik kategori yuvaları (`hotkeys.<kod>`).
  - **Sistem tepsisi:** Tepsi simgesine **sol tek tıklayarak** katmanı açıp kapatabilir, **çift tıklayarak** öne getirebilir veya sağ tıklayıp **Aç (`Win+Alt+Space`)** *(etkin `all` kısayoluyla dinamik güncellenir)* seçebilirsiniz.
  - **İkinci çalıştırma:** `qtp.exe` / `qtp.bin` tekrar çalıştırıldığında çalışan örnek IPC üzerinden otomatik olarak öne getirilir.

---

## 2. Dinamik Kategoriler (`categories`) ve Geriye Dönük Uyumluluk

QTP'de sabit kodlu hiçbir alan veya kategori yoktur; yalnızca sanal **`All` / `Tümü`** sekmesi yerleşiktir:
1. **`qtp_settings.json` → `categories`:** Kendi kategorilerinizi `[{"code": "1", "label": "General", "hotkey_prefix": "L-Win+1"}, ...]` biçiminde GUI **Ayarlar**, Web **Kategoriler** modalı (`POST /api/categories`) veya `qtp_settings.json` üzerinden tanımlayabilirsiniz.
2. **Otomatik Keşif (`resolve_categories`):** Yüklü `QuickTextPaste.ini` veya `data.json` dosyanızdaki tüm farklı `keys` önekleri (örneğin `L-Win+1`, `L-Win+2`, `L-Win+3`, `L-Ctrl+1`, `Alt+M` ya da mevcut eski INI dosyalarınızdaki tüm harf/rakam kodları) son `+` sonrası kod alınarak ilk görünüm sırasıyla otomatik kategori haplarına dönüştürülür.
3. **Kısayolsuz Notlar (`[NOTE]` / `[DAHİLİ NOT]`):** `keys` alanı boş bırakılan ya da `[NOTE]` / `[DAHİLİ NOT]` ile başlayan kayıtlar tüm modlarda **Notlar** (`--only-notes` / TUI `N`) filtresiyle yakalanır ve `sort_by="keys"` kipinde deterministik olarak listenin sonunda yer alır.

---

## 3. Bulanık Arama (Fuzzy Search) ve Deterministik Sıralama

Katman açılır açılmaz imleç otomatik olarak üstteki arama kutusundadır. Yazmaya başladığınız anda liste canlı olarak filtrelenir:

- **Yerel harf uyumu:** Türkçe ve Latin harfleri (`İ/i`, `I/ı`, `Ş/ş`, `Ğ/ğ`, `Ç/ç`, `Ö/ö`, `Ü/ü`) doğru eşleştirilir.
- **Alt-dizi (Subsequence) arama:** Kelimeleri tam yazmanız gerekmez; harf sırasını koruyan kısaltmalar eşleşir ve eşleşen karakterler vurgulanır.
- **Kapsam:** Arama metin içeriği, başlık (`label`), grup adı (`group`) ve kısayol rozeti üzerinde puanlama yapar.
- **Çapraz mod sıralama eşitliği (`order`, `usage`, `alpha`, `keys`, `favorites`):** `locale_sort_key` sıralama anahtarı CLI, TUI, GUI ve Web (`qtp.html`) arasında birebir özdeş sıralama üretir.
- İstediğiniz an `Ctrl+K` (macOS'ta `⌘K`) ile arama kutusuna odaklanıp metni seçebilirsiniz.

---

## 4. Yapıştırma ve Yalnızca Kopyalama

### 4.1 Doğrudan Aktif Uygulamaya Yapıştırma (`Enter` veya Sol Tık)
1. Listede `↑` / `↓` veya `PageUp` / `PageDown` tuşlarıyla kaydı seçin (veya doğrudan satıra sol tıklayın).
2. `Enter` tuşuna basın.
3. QTP önce seçili metni güvenli biçimde panoya kopyalar (Wayland dahil), ardından katmanı gizler, odağı önceki uygulamaya geri verir, `120 ms` bekler ve hedefe uygun yapıştırma kısayolunu (`Ctrl+V`, Linux uçbirimlerinde otomatik `Ctrl+Shift+V`, macOS'ta `Cmd+V`, Wayland'da `wtype` / `ydotool`) gönderir.
4. **`<E<N<D|` Bitiş İşareti:** Kayıt `<E<N<D|` ile bitiyorsa ve `enter_after_paste` etkinse yapıştırmadan hemen sonra otomatik olarak `Enter` gönderilir.

### 4.2 Yalnızca Panoya Kopyalama (`Ctrl+Enter`, `Shift+Tık`, Satır İçi Düğme)
- `Ctrl+Enter` (macOS'ta `⌘+Enter`), satıra `Shift+Sol Tık` veya satır üzerindeki **Kopyala** düğmesi katmanı kapatmadan metni panoya alır.

---

## 5. Sağ Tık Bağlam Menüsü

Liste satırı üzerinde sağ tıkladığınızda **10 seçenekli** bağlam menüsü açılır:
- **Yapıştır**, **Kopyala**, **Favoriye Ekle / Favoriden Çıkar**, **Düzenle**, **Çoğalt**, **Yukarı Taşı**, **Aşağı Taşı**, **Sil**, **INI'de Göster** (`[list_text]`, `[list_order]`, `[list_label]` ham görünümü) ve **Yardım** (`F1`).

---

## 6. Sistem Tepsisi Menüsü

Sistem tepsisindeki simgeye sağ tıkladığınızda etkin dilde (`EN`/`TR`/`qtp_locale.json`) menü açılır:
- **Aç (`Win+Alt+Space`):** Katmanı ekrana getirir (etkin `all` kısayoluna göre dinamik güncellenir).
- **Ayarlar…**, **INI Yeniden Yükle**, **data.json Aç**, **Yedekler…**, **Yardım (F1)** ve **Çıkış**.

---

## 7. Ayarlar Penceresi, Esnek Kısayollar, Çoklu Dil (`qtp_locale.json`) ve `qtp_settings.json`

Ayarlar penceresine **Ayarlar** düğmesi, `Ctrl+,` veya sistem tepsisi üzerinden ulaşabilirsiniz:

- **Kategoriler Bölümü:** Yeni kategori kodu (`1`, `WORK` vb.), görünen etiket ve `hotkey_prefix` ekleyebilir, düzenleyebilir veya silebilirsiniz.
- **Hazır Profil ve Toplu Değiştirici:** Tek tıkla `recommended` (`Win+Alt`), `win_ctrl`, `ctrl_alt`, `ctrl_shift_alt`, `function_keys` (`Ctrl+Shift+F1–Fn`) veya `legacy_win` profilini etkin tüm yuvalara dinamik uygulayabilirsiniz.
- **Esnek Kısayol Satırı (`HotkeyRow`):** Her kısayol için 4 değiştirici onay kutusu (`Ctrl`, `Alt`, `Shift`, `Win`), klavyeden doğrudan kayıt yapabilen **Yakala / `HotkeyEdit`** kutusu ve **+ Özel Kısayol Ekle** / `×` düğmeleri sunulur.
- **Çoklu Dil ve `qtp_locale.json`:** `language` varsayılan olarak `"auto"` değerindedir (Türkçe sistemlerde `tr`, diğer tüm sistemlerde `en`). Çalışma veya ayar dizinine `qtp_locale.json` koyarak (`{"key": "Özel metin"}` veya `{"de": {"ui.all": "Alle"}}`) herhangi bir dilde özelleştirme yapabilirsiniz.

| Ayar Alanı (`qtp_settings.json`) | Varsayılan | Açıklama |
| :--- | :--- | :--- |
| `language` | `"auto"` | Arayüz dili: `auto`, `en`, `tr` veya `qtp_locale.json` içindeki özel dil kodu. |
| `categories` | `[]` | Özel kategori tanımları (`[{"code", "label", "hotkey_prefix"}]`); veri kategorileriyle otomatik birleşir. |
| `theme` | `"light"` | Arayüz teması: `auto`, `dark` veya `light`. |
| `view_mode` | `"list"` | Liste görünüm düzeni: `list`, `grid` veya `table`. |
| `strip_emoji` | `false` | Kopyalama/yapıştırma sırasında Unicode emojileri temizler (özgün kayıt korunur). |
| `sort_by` | `"order"` | Sıralama ölçütü: `order`, `usage`, `alpha`, `keys` veya `favorites`. |
| `hotkeys` | `{"all": "Win+Alt+Space"}` | Global kısayol haritası (`all` ve isteğe bağlı kategori/özel yuvalar). |
| `last_category` | `"ALL"` | Genel açılışta son seçili kategori (`ALL` veya herhangi bir alfasayısal kategori kodu). |
| `last_category_by_hotkey` | `{}` | Her kısayol için en son seçilen sekme hafızası. |
| `window_size` | `[720, 520]` | Katman penceresi piksel `[genişlik, yükseklik]` boyutu. |
| `paste_method` | `"auto"` | `auto`, `ctrl_v`, `ctrl_shift_v`, `shift_insert` veya `type`. |
| `enter_after_paste` | `true` | `<E<N<D|` sonrası otomatik `Enter`. |
| `hide_on_blur` | `true` | Odak başka pencereye geçtiğinde katmanı otomatik gizler. |
| `start_minimized` | `false` | Sistem tepsisinde küçültülmüş başlatma. |
| `tray_icon` | `true` | Sistem tepsisi simgesi görünürlüğü. |
| `data_path` | `"./QuickTextPaste.ini"` | İzlenen ve yüklenen `QuickTextPaste.ini` dosya yolu. |
| `backup_count` | `15` | `backups/` dizinindeki en yeni yedek sayısı (`1–100`). |
| `auto_reload` | `true` | `qtp_settings.json`, `QuickTextPaste.ini` ve `data.json` değişikliklerini canlı yeniler. |
| `auto_reload_interval_ms` | `500` | Disk izleme denetim aralığı (`100–10000 ms`, `250 ms` debounce). |
| `log_level` | `"info"` | `qtp.log` ayrıntı düzeyi (`debug`, `info`, `warn`, `error`). |
| `web.port` | `{"port": 8765}` | `--web` sunucusu yerel `127.0.0.1` bağlantı noktası (`0–65535`). |

---

## 8. Dinamik Canlı Otomatik Yenileme (`auto_reload`)

`--gui`, `--web` ve etkileşimli `--tui` modları çalışırken sıfır bağımlılıklı `ConfigFileWatcher` bileşeni diskteki `qtp_settings.json`, etkin `QuickTextPaste.ini` (`data_path`) ve `data.json` dosyalarını arka planda izler (`--selftest` / `--version` / `--completion` gibi tek seferlik CLI komutları arka plan iş parçacığı açmaz ve dosya oluşturmaz):
- **Ayar Değişiklikleri:** Harici düzenleyiciyle `qtp_settings.json` değiştirildiğinde dil, kategoriler, tema, pencere boyutu, `data_path`, `log_level` ve global kısayollar yeniden başlatma olmadan güncellenir.
- **Veri Değişiklikleri:** `QuickTextPaste.ini` veya `data.json` değiştiğinde liste ve otomatik keşfedilen kategoriler canlı yenilenir.
- **Bozuk Dosya Koruması:** Harici yazım bozuk/eksikse son geçerli ayar ve kayıt listesi korunur; bozuk açılışta bir kez `corrupt_load` yedeği alınıp uyarı bildirilir.

---

## 9. INI ve JSON Dosyalarıyla Çalışma, Yedeklemeler ve Günlükler (`qtp.log`)

- **Çoklu Kodlama Desteği:** `UTF-16 LE BOM`, `UTF-16 BE BOM`, BOM'suz `UTF-16`, `UTF-8 BOM`, `UTF-8` ve `cp1254` kodlamaları otomatik algılanır; `[Program]`, ek bölümler ve `<E<N<D|` işaretleri kayıpsız korunur.
- **Zaman Damgalı Yedekler (`backups/`) ve Tam Yedek (`qtp-tam-yedek-*.json`):** Her kaydetme öncesinde otomatik yedek alınır; `.bak` yedeği ve 1 MB × 3 dönen `qtp.log` günlükleri tutulur.

---

## 10. Komut Satırı (CLI) Seçenekleri, Ayrıntı Düzeyi ve Otomatik Tamamlama

- **Etkileşimli Windows Konsolu:** Windows tek-dosya (`console=False`) ikilisinde `--help`, `--verbose`, `--completion`, `--cli`, `--web` veya `--tui` çalıştırıldığında üst süreç zincirine UTF-8 (`65001`) ile bağlanır; çift tık ve sessiz `--gui` penceresiz kalır.
- **Modlar Arası Eşit `--help`, `-v`/`--verbose`/`-vv` ve `-q`/`--quiet`:**
  - `qtp --cli --help`, `qtp --web --help`, `qtp --tui --help`, `qtp --gui --help` yan etkisiz çalışır ve `0` ile çıkar.
  - `-v` / `-vv`: Dört modun tamamında `stderr` akışına tanılama kayıtları akıtır (`stdout` JSON kirletilmez).
  - `-q` / `--quiet`: Başlangıç afişlerini gizler, hataları `stderr` üzerinde korur.
  - `--category` ve `--query`: Dört modun tamamında açılışta aynı başlangıç kategori ve arama filtresini uygular.
- **Kabuk Otomatik Tamamlama (`--completion [powershell|bash|zsh|fish]`):**
  - PowerShell: `.\qtp.exe --completion powershell | Out-String | Invoke-Expression`
  - Bash: `eval "$(./qtp.bin --completion bash)"`
  - Zsh: `eval "$(./qtp.bin --completion zsh)"`
  - Fish: `./qtp.bin --completion fish | source`

---

## 11. TUI Modu (`--tui`) ve Web Modu (`--web`)

- **`--gui` Ana Katmanı (v2.5.0):** Varsayılan **Açık (Light)** tema, dinamik kategori hapları, 1-tık tema/dil geçişi, **Liste / Kart / Tablo** görünümleri, çoklu seçim & **Toplu Düzenle**, **Grup Yöneticisi**, **Emoji Temizle**, `Ctrl+Z`/`Ctrl+Y`/`Ctrl+S`, 8 kenar yeniden boyutlandırma ve Wayland `XDG_ACTIVATION_TOKEN` + IPC desteği sunar.
- **`--tui` Etkileşimli Uçbirim:** `Tab` / `1–9` (dinamik kategori geçişi), `a` (Yeni Ekle), `E` (Düzenle), `d` (Sil), `Space` (çoklu seçim), `U`/`X` (toplu düzenle/sil), `D` (çoğalt), `K`/`J` (yukarı/aşağı taşı), `f`/`F` (favori değiştir/filtrele), `N` (yalnızca notları filtrele), `m` (emoji temizle), `g`/`G` (grup yöneticisi), `u`/`y` (geri al/yinele), `w` (kaydet), `P`/`O` (kısayol profili), `k` (çakışma tarama) ve `F1` destekler.
- **`--web` ve Çevrimdışı PWA (`qtp.html`):** Yerelde `127.0.0.1` loopback üzerinde veya sıfır arka uçlu GitHub Pages üzerinde (`sw.js` `qtp-pwa-cache-v4.0.0` çevrimdışı yönlendirme ile) çalışır; **EN / TR dil düğmesi**, **Kategoriler yöneticisi (`POST /api/categories`)**, **Açık / Koyu tema**, **Yoğunluk Kipleri (`compact` / `default` / `metro`)**, **Liste / Kart / Tablo**, **Toplu Düzenle / Sil**, **Grup Yöneticisi**, **Sürükle-Bırak İçe Aktarım**, **UTF-16 LE / UTF-8 / ANSI / JSON / Word `.doc` / Yazdır Dışa Aktarım**, **30 Adımlı Geri Al/Yinele**, **Anlık Kayıt Geçmişi** ve **6 sekmeli `F1` Yardım** sunar.

### CLI CRUD Komutları ve HTTP API JSON Örnekleri
- **CLI ile Ekleme / Güncelleme / Silme:**
  ```bash
  qtp --cli --add-item "Best regards," --item-keys L-Win+1 --item-group "Email" --item-label "Sign-off"
  qtp --cli --update-item text_000 --item-text "Updated text" --item-group "General"
  qtp --cli --delete-item text_000
  ```
- **Web API (`POST /api/items/add`, `/api/items/update`, `/api/items/delete`, `POST /api/categories`):**
  ```json
  {
    "text": "Hello, thank you for reaching out.",
    "keys": "L-Win+1",
    "group": "General / Email",
    "label": "Greeting",
    "terminator": "<E<N<D|"
  }
  ```

---

## 12. Modlar Arası Eşitlik Matrisi

Tüm işlemler ortak [operations.py](../standalone/qtp_app/core/operations.py) kayıt defteri ve [engine.py](../standalone/qtp_app/core/engine.py) üzerinden çalıştırılır:

| İşlem (`op_id`) | `--gui` | `--tui` | `--cli` | `--web` |
| :--- | :--- | :--- | :--- | :--- |
| `version` | Tepsi / Yardım (F1) | `V` | `--version` | `GET /api/version` |
| `help` | `F1` / Tepsi → Yardım (F1) | `F1` | `--help` | `GET /api/help` |
| `selftest` | Başlangıç Doğrulama | `T` | `--selftest` | `GET /api/selftest` |
| `modes` | Yardım (F1) → Modlar | `M` | `--modes` | `GET /api/modes` |
| `completion` | Yardım (F1) → Otomatik Tamamlama | `C` | `--completion` | `GET /api/completion` |
| `list_categories` | Dinamik Kategori Hapları (`All` / `Tümü` / ...) | `Tab` / `1–9` | `--list-categories` | `GET /api/categories` |
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
| `add_item` | `+ Yeni` | `a` | `--add-item <metin>` | `POST /api/items/add` |
| `update_item` | Sağ Tık → Düzenle | `E` | `--update-item <hedef>` | `POST /api/items/update` |
| `delete_item` | Sağ Tık → Sil | `d` | `--delete-item <hedef>` | `POST /api/items/delete` |
| `save_all` | 💾 Kaydet (`Ctrl+S`) | `w` | `--save` | `POST /api/save` |
| `duplicate_item` | Sağ Tık → Çoğalt | `D` | `--duplicate-item <hedef>` | `POST /api/items/duplicate` |
| `move_item` | Sağ Tık → Yukarı / Aşağı Taşı | `K / J` | `--move-item <hedef> --direction up\|down` | `POST /api/items/move` |
| `toggle_favorite` | Sağ Tık → ⭐ Favori | `f` | `--toggle-favorite <hedef>` | `POST /api/items/favorite` |
| `bulk_edit` | ✏️ Toplu Düzenle | `U` | `--bulk-edit <anahtarlar_csv>` | `POST /api/items/bulk-edit` |
| `bulk_delete` | 🗑️ Seçileni Sil | `X` | `--bulk-delete <anahtarlar_csv>` | `POST /api/items/bulk-delete` |
| `rename_group` | 📁 Gruplar → Yeniden Adlandır | `g` | `--rename-group <eski> --new-group <yeni>` | `POST /api/groups/rename` |
| `delete_group` | 📁 Gruplar → Grubu Sil | `G` | `--delete-group <grup>` | `POST /api/groups/delete` |
| `undo` | Ctrl+Z / ↩️ Geri Al | `u` | `--undo` | `POST /api/undo` |
| `redo` | Ctrl+Y / ↪️ Yinele | `y` | `--redo` | `POST /api/redo` |
