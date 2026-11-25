# QTP Klavye Kısayolları Rehberi / Keyboard Shortcuts (`v2.5.0`)

QTP v2.5.0, Windows 10/11 ve Linux (KDE Plasma `~/.config/kglobalshortcutsrc` / GNOME) sistem kısayollarıyla ve uluslararası `AltGr` tuşlarıyla çakışmayan minimal varsayılan kısayol (`Win+Alt+Space`), **6 dinamik hazır profil**, **15 değiştirici bileşimi**, **Win32 `RegisterHotKey` özel kilitleme**, canlı çakışma algılama ve tüm arayüzlerde tam klavye kontrolü sunar.

---

## 1. Varsayılan Global (Sistem Geneli) Kısayollar

| Yuva / Slot | Varsayılan (`recommended`) | Açtığı Ekran |
| :--- | :--- | :--- |
| **`all`** | `Win+Alt+Space` | Tüm kategoriler katmanı (`All` / `Tümü`) |
| **`<özel_kod>`** *(isteğe bağlı)* | `Win+Alt+<kod>` | İlgili kategoriye filtrelenmiş katman (ör. `hotkeys.1`, `hotkeys.WORK`) |

### Neden `Win+<tuş>` ve `Ctrl+Alt` Varsayılan Olarak Kullanılmaz?
- Windows 10/11 sisteminde `Win+A/Z/X/Q/1..9` gibi kısayollar doğrudan sistem tarafından yakalanır; pasif kancalar bu kısayolları bastıramaz.
- Türkçe-Q ve uluslararası `AltGr` klavyelerde `Ctrl+Alt+<tuş>`, `AltGr` karakterleriyle (`@`, `€`, `£`, `{`, `[`) çakışabilir.
- QTP, Windows üzerinde yerel `user32.dll` `RegisterHotKey` API'sini `MOD_NOREPEAT` bayrağıyla kullanarak çalışan kısayolları özel (exclusive) biçimde kaydeder ve çakışma (`ERROR_HOTKEY_ALREADY_REGISTERED / 1409`) oluştuğunda kullanıcıyı uyarır.
- **`QuickTextPaste.ini` Uyumluluğu:** INI dosyasındaki `L-Win+1`, `L-Ctrl+1`, `Alt+M` veya mevcut tüm eski kısayol önekleri kayıpsız korunur ve otomatik kategori keşfinde kullanılır.

---

## 2. Dinamik Hazır Profiller, Serbest Değiştiriciler ve Özel Yuvalar

### 6 Dinamik Hazır Profil (`--hotkey-preset`)

`build_preset_hotkeys(preset, slots)` seçilen profili `all` yuvasına ve tanımlı tüm kategori/özel yuvalarınıza otomatik olarak eşler:

| Profil Adı | `all` | Kategori / Özel Yuva (`<slot>`) | Kullanım Amacı |
| :--- | :--- | :--- | :--- |
| **`recommended`** | `Win+Alt+Space` | `Win+Alt+<tuş>` | Varsayılan — Sistem & AltGr çakışmasız |
| **`win_ctrl`** | `Win+Ctrl+Space` | `Win+Ctrl+<tuş>` | `Win+Ctrl` tercih edenler için |
| **`ctrl_alt`** | `Ctrl+Alt+Space` | `Ctrl+Alt+<tuş>` | `Win` tuşsuz `Ctrl+Alt` (`AltGr` uyarısı gösterir) |
| **`ctrl_shift_alt`** | `Ctrl+Alt+Shift+Space` | `Ctrl+Alt+Shift+<tuş>` | Üçlü değiştirici — tam çakışmasız |
| **`function_keys`** | `Ctrl+Shift+F1` | `Ctrl+Shift+F2..Fn` | `Win` ve harf tuşlarından bağımsız |
| **`legacy_win`** | `Ctrl+Shift+Space` | `Win+<tuş>` | Klasik QuickTextPaste eşlemesi (çakışma riski bildirilir) |

### 15 Geçerli Değiştirici Bileşimi (`--hotkey-modifiers`)
`Ctrl`, `Alt`, `Shift`, `Win` temel değiştiricilerinin boş olmayan her `1–4`'lü bileşimi (`Ctrl`, `Alt`, `Shift`, `Win`, `Ctrl+Alt`, `Ctrl+Shift`, `Ctrl+Win`, `Alt+Shift`, `Alt+Win`, `Shift+Win`, `Ctrl+Alt+Shift`, `Ctrl+Alt+Win`, `Ctrl+Shift+Win`, `Alt+Shift+Win`, `Ctrl+Alt+Shift+Win`) tüm etkin yuvalara toplu uygulanabilir; sıra fark etmez ve otomatik normalleştirilir.

### Dinamik Özel Yuvalar (`hotkeys.<ad>`)
`qtp_settings.json`, GUI **Ayarlar**, Web **Kısayollar** veya `--set hotkeys.work "Win+Alt+W"` komutuyla dilediğiniz kadar ek yuva tanımlayabilirsiniz. Canlı çakışma taraması (`--check-hotkeys`) tüm yuvaları doğrular:
- **GUI:** `Ctrl+,` → Ayarlar → Global Kısayollar bölümünde canlı uyarı rozeti.
- **CLI:** `qtp --cli --check-hotkeys --json`
- **TUI:** `k` (Çakışma Tara), `P` (Profil Uygula), `O` (Toplu Değiştirici)
- **Web:** **Kısayollar** modalındaki *Profil* ve *Toplu Değiştirici* kontrolleri.

---

## 3. Modlar Arası Etkileşim ve Katman Kısayolları (`--gui`, `--tui`, `--web`)

| İşlev | `--gui` (Masaüstü Katmanı) | `--tui` (Terminal) | `--web` / `qtp.html` (Tarayıcı) |
| :--- | :--- | :--- | :--- |
| **Satır Seçimi / Gezinti** | `↑` / `↓` / `PgUp` / `PgDn` | `↑` / `↓` / `PgUp` / `PgDn` | `↑` / `↓` / Tıklama |
| **Kategori Geçişi** | `Tab` / Dinamik Kategori Hapları | `Tab` / `1`–`9` | Dinamik Kategori Hapları (`All` / ...) |
| **Aramaya Odaklanma** | `Ctrl+K` / Doğrudan yazma | `/` | `Ctrl+K` veya `/` |
| **Aktif Uygulamaya Yapıştır** | `Enter` / Sol Tık | `Enter` | Satır `Yapıştır` düğmesi (`--web`, 3 sn gecikmeli) |
| **Yalnızca Panoya Kopyala** | `Ctrl+Enter` / `Shift+Tık` / `Kopyala` | `c` | Satıra Tıklama / `Enter` / `Ctrl+Enter` / `Kopyala` |
| **Yeni Kayıt Ekle (`add_item`)** | Üst çubuk `+` düğmesi | `a` | `+` düğmesi |
| **Seçili Kaydı Düzenle (`update_item`)** | Sağ Tık → `Düzenle` | `E` | Satır içi `Düzenle` düğmesi |
| **Seçili Kaydı Sil (`delete_item`)** | Sağ Tık → `Sil` | `d` | Modal `Sil` düğmesi |
| **Çoklu Seçim / Toplu İşlemler** | `Space` / Kutucuk / `Shift+Tık`, `✏️`, `🗑️` | `Space`, `U`, `X` | Kutucuk / `Shift+Tık` / Üst Toplu Çubuğu |
| **Çoğalt / Sıra Taşı (`duplicate_item`, `move_item`)** | Sağ Tık → `📑` / `⬆️` / `⬇️` | `D`, `K`, `J` | Modal Hızlı İşlemler Çubuğu |
| **Favori / Notlar / Emoji / Görünüm** | `⭐`, `📝`, `😊/🚫`, `☰/▦/▤` | `f`, `F`, `N`, `m` | `⭐`, `Notlar`, `Emoji`, `Liste/Kart/Tablo` |
| **Grup & Kategori Yönetimi** | `📁` / `Ctrl+,` | `g`, `G` | `📁 Gruplar` / `🏷️ Kategoriler` |
| **Dil Geçişi (`EN` / `TR`)** | `Ctrl+,` → Dil | `s` → `language` | Üst çubuk `EN` / `TR` düğmesi |
| **Geri Al / Yinele / Kaydet** | `Ctrl+Z` / `Ctrl+Y` / `Ctrl+S` | `u`, `y`, `w` | `Ctrl+Z` / `Ctrl+Y` / `Ctrl+S` |
| **Ham INI Satırını Göster** | Sağ Tık → `INI'de Göster` | `e` | Modal `Show INI` / Sağ Tık |
| **Açık / Koyu Tema Geçişi** | Üst çubuk Tema düğmesi veya `Ctrl+,` | `s` → `theme` | Üst çubuk Tema düğmesi |
| **Ayarlar / Yedek / Yenile** | `Ctrl+,` / Tepsi Menüsü | `s` / `b` / `B` / `r` / `x` / `i` / `R` | Araçlar Menüsü |
| **Yardım Penceresi** | `F1` (5 sekme) | `F1` (Markdown modal) | `F1` (6 sekme) |
| **Katmanı Gizle / Çık** | `Esc` / `Ctrl+Q` | `Esc` / `q` | `Esc` (Açık modalı kapatır) |

---

## 4. Fare Etkileşimleri

- **Sol Tık (`--gui`):** Öğeyi kopyalar, katmanı gizler ve aktif pencereye `Ctrl+V` (ve istenirse `Enter`) gönderir.
- **Shift + Sol Tık (`--gui`):** Yapıştırma simülasyonu yapmadan yalnızca panoya kopyalar.
- **Sağ Tık (`--gui`):** 10 eylemli bağlam menüsünü açar (`Yapıştır`, `Kopyala`, `Favori`, `Düzenle`, `Çoğalt`, `Yukarı/Aşağı Taşı`, `Sil`, `INI'de Göster`, `Yardım`).
- **Sistem Tepsisi Simgesi:** Sol tek tık katmanı açar/kapatır; sağ tık tepsi menüsünü açar.
