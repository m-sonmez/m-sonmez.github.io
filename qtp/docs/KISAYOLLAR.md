# QTP Klavye Kısayolları Rehberi

QTP, **çapraz platform UI/UX eşitliği** ilkesiyle tasarlanmıştır. Varsayılan global kısayollar Windows 7–11 sistem kısayolları ve Türkçe-Q `AltGr` tuşu ile çakışmayacak şekilde `Win+Alt+*` olarak seçilmiştir ve **15 değiştirici bileşiminin tamamıyla** esnek biçimde özelleştirilebilir. macOS kullanıcıları için katman içinde ek `⌘` (`Cmd`) eş-kısayolları da **ek seçenek** olarak tanımlanmıştır; ancak standart `Ctrl+*` kısayolları hiçbir zaman kaldırılmaz veya değiştirilmez.

---

## 1. Varsayılan Global (Sistem Geneli) Kısayollar

Aşağıdaki kısayollar arka planda sistem genelinde dinlenir (Windows 7–11'de yerel Win32 `RegisterHotKey` ile tuşları aktif uygulamaya sızdırmadan tüketir; Linux/macOS X11 üzerinde `pynput` kullanır) ve `qtp_settings.json` ya da **Ayarlar (`Ctrl+,`)** penceresinden dilediğiniz gibi değiştirilebilir:

| Olay | Kısayol (Windows) | Kısayol (Linux) | Kısayol (macOS) | Açıklama |
| :--- | :--- | :--- | :--- | :--- |
| Tüm Kategorilerle Aç | `Win+Alt+Space` | `Win+Alt+Space` | `Win+Alt+Space` | Katmanı açar ve tüm kategorileri (veya genel son kategoriyi) gösterir. |
| İş Ortağı Kategorisiyle Aç | `Win+Alt+A` | `Win+Alt+A` | `Win+Alt+A` | Katmanı **A · İş Ortağı** (`L-Win+A`) filtresiyle açar. |
| Kurye Kategorisiyle Aç | `Win+Alt+Z` | `Win+Alt+Z` | `Win+Alt+Z` | Katmanı **Z · Kurye** (`L-Win+Z`) filtresiyle açar. |
| Canlı Yardım Kategorisiyle Aç | `Win+Alt+X` | `Win+Alt+X` | `Win+Alt+X` | Katmanı **X · Canlı Yardım** (`L-Win+X`) filtresiyle açar. |
| Turkcell Kategorisiyle Aç | `Win+Alt+Q` | `Win+Alt+Q` | `Win+Alt+Q` | Katmanı **Q · Turkcell** (`L-Win+Q`) filtresiyle açar. |

### Neden `Win+A/Z/X/Q` ve `Ctrl+Alt+Q` Varsayılan Olarak Kullanılmaz?
- **Windows 10/11 Sistem Çakışmaları:** `Win+A` (Hızlı Ayarlar), `Win+Z` (Snap Düzenleri), `Win+X` (Hızlı Bağlantı Menüsü) ve `Win+Q` (Windows Arama) doğrudan işletim sistemi tarafından ayrılmıştır.
- **Türkçe-Q `AltGr` Tuzağı (`Ctrl+Alt+<harf>`):** Windows'ta Türkçe-Q klavyelerde `AltGr` tuşu sistem düzeyinde `Ctrl+Alt` üretir. Bu nedenle `Ctrl+Alt+Q` (`@`), `Ctrl+Alt+A` (`æ`), `Ctrl+Alt+E` (`€`), `Ctrl+Alt+S` (`ß`) ve `Ctrl+Alt+1..9` (`>`, `£`, `#`, `$`, `½`, `{`, `[`, `]`, `}`) atamaları Türkçe karakter ve e-posta adresi yazımını engelleyebilir. QTP ayar penceresinde ve `--check-hotkeys` çıktısında bu bileşimler için canlı uyarı verir.
- **Klavye Dili ve TTY Çakışmaları:** Yalnız `Alt+Shift` / `Ctrl+Shift` dil değiştirme ve Linux/BSD'de `Ctrl+Alt+F1..F12` sanal konsol geçişleriyle çakışılmaz.

---

## 2. Hazır Kısayol Profilleri, Serbest Değiştiriciler ve Özel Yuvalar

**Ayarlar → Global Kısayollar** veya CLI (`--hotkey-preset`, `--hotkey-modifiers`) üzerinden aşağıdaki 6 hazır profil arasında anında geçiş yapabilir veya her kategori için `Ctrl`, `Alt`, `Shift`, `Win` onay kutularından oluşan **15 farklı değiştirici bileşimini** tek tek seçebilirsiniz (`Ctrl`, `Alt`, `Shift`, `Win`, `Ctrl+Alt`, `Ctrl+Shift`, `Alt+Shift`, `Win+Ctrl`, `Win+Alt`, `Win+Shift`, `Ctrl+Alt+Shift`, `Win+Ctrl+Alt`, `Win+Ctrl+Shift`, `Win+Alt+Shift`, `Win+Ctrl+Alt+Shift`):

| Profil Kimliği (`--hotkey-preset`) | Atanan Kısayollar | Kullanım Önerisi |
| :--- | :--- | :--- |
| `recommended` *(Varsayılan)* | `Win+Alt+Space`, `Win+Alt+A/Z/X/Q` | Windows 7–11, Türkçe-Q, tarayıcı ve IDE çakışmasız varsayılan profil. |
| `win_ctrl` | `Win+Ctrl+Space`, `Win+Ctrl+A/Z/X/Q` | Tek elle hızlı `Win+Ctrl` erişimi (`Win+Ctrl+D/Sol/Sağ` masaüstü tuşlarına dokunmaz). |
| `ctrl_alt` | `Ctrl+Alt+Space`, `Ctrl+Alt+A/Z/X/Q` | `Win` tuşsuz; Türkçe-Q'da `@` (`AltGr+Q`) kullananlar için uyarı gösterir. |
| `ctrl_shift_alt` *(takma ad: `triple_mod`)* | `Ctrl+Alt+Shift+Space`, `Ctrl+Alt+Shift+A/Z/X/Q` | RDP/VM ve `Win` tuşsuz ortamlarda A/Z/X/Q harf belleğini korur. |
| `function_keys` | `Ctrl+Shift+F1` (`all`), `F2` (`A`), `F3` (`Z`), `F4` (`X`), `F5` (`Q`) | Windows, Linux, BSD ve **macOS** dahil tüm işletim sistemlerinde **sıfır çakışmalı** Win-tuşsuz profil. |
| `legacy_win` | `Ctrl+Shift+Space`, `Win+A`, `Win+Z`, `Win+X`, `Win+Q` | Eski v2.0/v2.1 klasik eşlemesi (Windows 10/11 çakışma uyarısı verir). |

- **Toplu Değiştirici Değiştirme:** Ayarlar penceresindeki **Tümüne Değiştirici Uygula** veya `qtp --hotkey-modifiers "Win+Ctrl"` ile tüm mevcut yuvaların değiştiricilerini tetik tuşlarını koruyarak tek adımda dönüştürebilirsiniz.
- **Özel Kısayol Yuvaları:** `+ Özel Kısayol Ekle` düğmesiyle veya `qtp --set hotkeys.W "Ctrl+Shift+Alt+W"` komutuyla dilediğiniz ek kategori/önek yuvasını ekleyebilir, boş (`""`) veya `×` ile kaldırabilirsiniz.
- **Desteklenen Tetik Tuşları:** `A–Z`, `0–9`, `F1–F24`, `Space`, `Tab`, `Enter`, `Esc`, `Backspace`, `Insert`, `Delete`, `Home`, `End`, `PageUp`, `PageDown`, `Up/Down/Left/Right`, `Numpad0–9` ve `- = [ ] ; ' , . / \ \``.

---

## 3. Modlar Arası Etkileşim ve Katman Kısayolları (`--gui`, `--tui`, `--web`)

Aşağıdaki tuşların çekirdek gezinme ve işlem mantığı dört modda da aynıdır (`Enter`, `Esc`/`q`, `Ctrl+K`/`/`, `F1`):

| Olay | GUI (`--gui`) | TUI (`--tui`) | Web (`--web`) | Açıklama |
| :--- | :--- | :--- | :--- | :--- |
| Sonraki / Önceki Öğe | `↑` / `↓` | `↑` / `↓` | `↑` / `↓` | Listede satır değiştirir (**tüm modlarda aynı**). |
| Hızlı Kaydır | `PageUp` / `PageDown` | `PageUp` / `PageDown` | Liste kaydırma | 6 satır yukarı/aşağı atlar. |
| Yapıştır | `Enter` (`⏎`) | `Enter` (`⏎`) | `Enter` (`⏎`) | Önceki pencereye yapıştırır (**tüm modlarda aynı**). |
| Yalnızca Kopyala | `Ctrl+Enter` (`⌘+Enter`) | `c` | `Ctrl+Enter` (`⌘+Enter`) | Katmanı kapatmadan panoya kopyalar. |
| Aramaya Odaklan | `Ctrl+K` (`⌘+K`) | `/` | `Ctrl+K` / `/` | Arama kutusuna odaklanır. |
| Kategori Değiştir | Tıkla (`Tümü`/`A`/`Z`/`X`/`Q`) | `Tab` veya `1–5` | Tıkla (`Tümü`/`A`/`Z`/`X`/`Q`) | Kategori sekmesini değiştirir. |
| INI'de Göster | Sağ Tık → INI'de Göster | `e` | `GET /api/show-ini` | Ham `[list_text]`/`[list_label]` satırlarını gösterir. |
| Anlık Yedek / Tam Yedek | Tepsi → Yedekler… | `b` / `B` | Yedekle düğmesi | Dönen yedek veya `qtp-tam-yedek-*.json` oluşturur. |
| INI Yeniden Yükle | Tepsi → INI Yeniden Yükle | `r` | Yenile düğmesi | Diskteki INI/JSON verisini yeniden yükler. |
| Ayarları Aç / Kısayol Kontrol | `Ctrl+,` (`⌘+,`) | `s` / `k` / `P` | `/api/settings`, `Kısayollar` | Ayarları, profilleri ve çakışma durumunu açar. |
| Türkçe Yardım | `F1` | `F1` | `F1` | Dört modda da kanonsal yardımı (`CLI & Parametreler`, `Kullanım`, `Kısayollar`, `SSS`) açar; TUI'de `↑↓`/`PageUp`/`PageDown` ile kaydırılır. |
| Kapat / Çık | `Esc` | `q` / `Esc` | `Esc` | Katmanı veya modal pencereyi kapatır (**tüm modlarda aynı**). |

---

## 4. Fare Etkileşimleri

| Olay | Windows | Linux | macOS | Açıklama |
| :--- | :--- | :--- | :--- | :--- |
| Satıra Sol Tık | Sol Tık | Sol Tık | Sol Tık | Seçili kaydı önceki aktif uygulamaya yapıştırır. |
| Satıra Shift+Tık | `Shift+Sol Tık` | `Shift+Sol Tık` | `Shift+Sol Tık` | Katmanı kapatmadan yalnızca panoya kopyalar. |
| Satır İçi "Kopyala" Düğmesi | Sol Tık | Sol Tık | Sol Tık | Satır üzerine gelince sağda çıkan düğme ile panoya kopyalar. |
| Bağlam Menüsü | Sağ Tık | Sağ Tık | Sağ Tık (`Ctrl+Tık`) | Kaydı panoya alır ve `Yapıştır / Kopyala / INI'de Göster / Yardım` menüsünü açar. |
| Tepsi Simgesi Çift Tık | Çift Tık | Çift Tık | Çift Tık | Katman penceresini açar. |
| Pencere Boyutlandırma | Sağ Alt Köşe Sürükle | Sağ Alt Köşe Sürükle | Sağ Alt Köşe Sürükle | Pencere boyutunu değiştirir ve `qtp_settings.json` içine kaydeder. |
