# QTP Klavye Kısayolları Rehberi

QTP v2.2.0, Windows 10/11 sistem kısayollarıyla ve Türkçe-Q `AltGr` karakterleriyle çakışmayan akıllı varsayılan kısayollar, **6 hazır profil**, **15 değiştirici bileşimi**, **Win32 `RegisterHotKey` özel kilitleme**, canlı çakışma algılama ve tüm arayüzlerde tam klavye/CRUD kontrolü sunar.

---

## 1. Varsayılan Global (Sistem Geneli) Kısayollar

| Yuva / Kategori | Varsayılan (`recommended`) | Açtığı Ekran |
| :--- | :--- | :--- |
| **`all`** | `Win+Alt+Space` | Tüm kategoriler katmanı |
| **`A`** | `Win+Alt+A` | `L-Win+A` önekli hazır cevaplar |
| **`Z`** | `Win+Alt+Z` | `L-Win+Z` önekli hazır cevaplar |
| **`X`** | `Win+Alt+X` | `L-Win+X` önekli hazır cevaplar |
| **`Q`** | `Win+Alt+Q` | `L-Win+Q` önekli hazır cevaplar |

### Neden `Win+A/Z/X/Q` ve `Ctrl+Alt` Varsayılan Olarak Kullanılmaz?
- Windows 10/11 sisteminde `Win+A` (*Hızlı Ayarlar*), `Win+Z` (*Pencere Düzenleri*), `Win+X` (*Hızlı Bağlantı Menüsü*) ve `Win+Q` (*Windows Arama*) doğrudan Explorer tarafından yakalanır; arka plan uygulamalarının pasif kancaları bu kısayolları bastıramaz ve çift tetiklemeye yol açar.
- Türkçe-Q klavyede `Ctrl+Alt+<tuş>`, `AltGr` ile aynı tarama kodunu ürettiğinden `Ctrl+Alt+Q` yazarken `@` işaretini engelleyebilir.
- QTP, Windows üzerinde yerel `user32.dll` `RegisterHotKey` API'sini `MOD_NOREPEAT` bayrağıyla kullanarak çalışan kısa yolları özel (exclusive) biçimde kaydeder ve çakışma (`ERROR_HOTKEY_ALREADY_REGISTERED / 1409`) oluştuğunda GUI/CLI/TUI/Web üzerinden kullanıcıyı uyarır.
- **`QuickTextPaste.ini` Uyumluluğu:** INI dosyasındaki `L-Win+A`, `L-Win+Z`, `L-Win+X`, `L-Win+Q`, `L-Win+W`, `L-Win+1` alanları yalnızca kategori sınıflandırma etiketidir; QTP bu satırları asla bozmaz ve bayt-birebir korur.

---

## 2. Hazır Kısayol Profilleri, Serbest Değiştiriciler ve Özel Yuvalar

### 6 Hazır Kısayol Profili (`--hotkey-preset`)

| Profil Adı | `all` | `A` | `Z` | `X` | `Q` | Kullanım Amacı |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`recommended`** | `Win+Alt+Space` | `Win+Alt+A` | `Win+Alt+Z` | `Win+Alt+X` | `Win+Alt+Q` | Varsayılan — Sistem & AltGr çakışmasız |
| **`win_ctrl`** | `Win+Ctrl+Space` | `Win+Ctrl+A` | `Win+Ctrl+Z` | `Win+Ctrl+X` | `Win+Ctrl+Q` | `Win+Ctrl` tercih edenler için |
| **`ctrl_alt`** | `Ctrl+Alt+Space` | `Ctrl+Alt+A` | `Ctrl+Alt+Z` | `Ctrl+Alt+X` | `Ctrl+Alt+Q` | `Win` tuşsuz `Ctrl+Alt` (TR-Q `AltGr` uyarısı gösterir) |
| **`ctrl_shift_alt`** | `Ctrl+Alt+Shift+Space` | `Ctrl+Alt+Shift+A` | `Ctrl+Alt+Shift+Z` | `Ctrl+Alt+Shift+X` | `Ctrl+Alt+Shift+Q` | Üçlü değiştirici — tam çakışmasız |
| **`function_keys`** | `Ctrl+Shift+F1` | `Ctrl+Shift+F2` | `Ctrl+Shift+F3` | `Ctrl+Shift+F4` | `Ctrl+Shift+F5` | `Win` ve harf tuşlarından tamamen bağımsız |
| **`legacy_win`** | `Ctrl+Shift+Space` | `Win+A` | `Win+Z` | `Win+X` | `Win+Q` | Klasik QuickTextPaste eşlemesi (çakışma riski bildirilir) |

### 15 Geçerli Değiştirici Bileşimi (`--hotkey-modifiers`)
`Ctrl`, `Alt`, `Shift`, `Win` temel değiştiricilerinin boş olmayan her `1–4`'lü bileşimi (`Ctrl`, `Alt`, `Shift`, `Win`, `Ctrl+Alt`, `Ctrl+Shift`, `Ctrl+Win`, `Alt+Shift`, `Alt+Win`, `Shift+Win`, `Ctrl+Alt+Shift`, `Ctrl+Alt+Win`, `Ctrl+Shift+Win`, `Alt+Shift+Win`, `Ctrl+Alt+Shift+Win`) tüm yuvalara toplu uygulanabilir; sıra fark etmez ve otomatik standart sıraya normalleştirilir. Türkçe-Q `AltGr` (`RightAlt`) kullanan sistemlerde `Win+Alt` veya `Ctrl+Alt+Shift` önerilir.

### Dinamik Özel Yuvalar (`hotkeys.<ad>`)
Varsayılan `all`, `A`, `Z`, `X`, `Q` yuvalarına ek olarak `qtp_settings.json` veya `--set hotkeys.destek "Win+Alt+D"` komutuyla dilediğiniz kadar ek yuva tanımlayabilirsiniz. Canlı çakışma taraması (`--check-hotkeys`) bu yuvaları da doğrular:
- **GUI:** `Ctrl+,` → Ayarlar → Global Kısayollar bölümünde canlı uyarı rozeti (kırmızı: sistem/OS çakışması, kehribar: TR-Q `AltGr` uyarısı, yeşil: çakışma yok).
- **CLI:** `qtp --cli --check-hotkeys --json`
- **TUI:** `k` (Çakışma Tara), `P` (Profil Uygula), `O` (Toplu Değiştirici)
- **Web:** **Kısayollar** modalındaki *Çakışma Tara*, *Profil* ve *Toplu Değiştirici* düğmeleri.

---

## 3. Modlar Arası Etkileşim ve Katman Kısayolları (`--gui`, `--tui`, `--web`)

| İşlev | `--gui` (Masaüstü Katmanı) | `--tui` (Terminal) | `--web` / `qtp.html` (Tarayıcı) |
| :--- | :--- | :--- | :--- |
| **Satır Seçimi / Gezinti** | `↑` / `↓` / `PgUp` / `PgDn` | `↑` / `↓` / `PgUp` / `PgDn` | `↑` / `↓` / Tıklama |
| **Kategori Geçişi** | `Tab` / Kategori Hapları | `Tab` / `1`–`5` | Kategori Hapları (`Tümü` / `A` / `Z` / `X` / `Q`) |
| **Aramaya Odaklanma** | `Ctrl+K` / Doğrudan yazma | `/` | `Ctrl+K` veya `/` |
| **Aktif Uygulamaya Yapıştır** | `Enter` / Çift veya Sol Tık | `Enter` | Satır `Yapıştır` düğmesi (`--web`) |
| **Yalnızca Panoya Kopyala** | `Ctrl+Enter` / `Shift+Tık` / `Kopyala` | `c` | `Ctrl+Enter` / Satır `Kopyala` düğmesi |
| **Yeni Cevap Ekle (`add_item`)** | Üst çubuk `+ Yeni Cevap` düğmesi | `a` | `+ Yeni Cevap` düğmesi |
| **Seçili Cevabı Düzenle (`update_item`)** | Sağ Tık → `Düzenle` | `E` | Satır içi `Düzenle` düğmesi |
| **Seçili Cevabı Sil (`delete_item`)** | Sağ Tık → `Sil` | `d` | Satır içi `Sil` düğmesi |
| **Ham INI Satırını Göster** | Sağ Tık → `INI'de Göster` | `e` | Satır içi `INI` düğmesi |
| **Açık / Koyu Tema Geçişi** | `Ctrl+,` / `Ayarlar → Tema` | `s` → `theme` | Üst sağ `🌙 Koyu` / `☀️ Açık` düğmesi |
| **Ayarlar / Yedek / Yenile** | `Ctrl+,` / Tepsi Menüsü | `s` / `b` / `B` / `r` / `x` / `i` / `R` | `Ayarlar`, `Yedek Al`, `Yeniden Yükle`, `İçe/Dışa Aktar` |
| **Yardım Penceresi** | `F1` (5 sekme) | `F1` (Markdown modal) | `F1` / `Yardım (F1)` (6 sekme) |
| **Katmanı Gizle / Çık** | `Esc` / `Ctrl+Q` | `Esc` / `q` | `Esc` (Açık modalı kapatır) |

---

## 4. Fare Etkileşimleri

- **Sol Tık (`--gui`):** Öğeyi kopyalar, katmanı gizler ve aktif pencereye `Ctrl+V` (ve istenirse `Enter`) gönderir.
- **Shift + Sol Tık (`--gui`):** Yapıştırma simülasyonu yapmadan yalnızca panoya kopyalar.
- **Sağ Tık (`--gui`):** Bağlam menüsünü açar (`Yapıştır`, `Yalnızca Panoya Kopyala`, `Düzenle`, `Sil`, `INI'de Göster`).
- **Sistem Tepsisi Simgesi:** Sol tık ile katmanı açar/kapatır; sağ tık ile tüm hızlı işlemleri (`Katmanı Aç`, `Ayarlar`, `Yedekler…`, `INI İçe/Dışa Aktar`, `INI Yeniden Yükle`, `Yardım (F1)`, `Çıkış`) açar.
