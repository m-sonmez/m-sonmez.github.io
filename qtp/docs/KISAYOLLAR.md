# QTP Klavye Kısayolları Rehberi

QTP, **çapraz platform UI/UX eşitliği** ilkesiyle tasarlanmıştır. Varsayılan tüm global kısayollar ve katman içi klavye kısayolları Windows, Linux ve macOS üzerinde **birebir aynı** çalışır. macOS kullanıcıları için sistem alışkanlığı gereği ek `⌘` (`Cmd`) eş-kısayolları da **ek seçenek** olarak tanımlanmıştır; ancak standart `Ctrl+*` kısayolları hiçbir zaman kaldırılmaz veya değiştirilmez.

---

## 1. Global (Sistem Geneli) Kısayollar

Aşağıdaki kısayollar arka planda sistem genelinde dinlenir ve hangi uygulamada olursanız olun katmanı açar (`qtp_settings.json` içinden yeniden yapılandırılabilir):

| Olay | Kısayol (Windows) | Kısayol (Linux) | Kısayol (macOS) | Açıklama |
| :--- | :--- | :--- | :--- | :--- |
| Tüm Kategorilerle Aç | `Ctrl+Shift+Space` | `Ctrl+Shift+Space` | `Ctrl+Shift+Space` | Katmanı açar ve tüm kategorileri (veya genel son kategoriyi) gösterir. |
| İş Ortağı Kategorisiyle Aç | `Win+A` | `Win+A` (`Super+A`) | `Win+A` (`Cmd+A` değil, `Command/Meta` harita ayarı) | Katmanı **A · İş Ortağı** (`L-Win+A`) filtresiyle açar. |
| Kurye Kategorisiyle Aç | `Win+Z` | `Win+Z` (`Super+Z`) | `Win+Z` | Katmanı **Z · Kurye** (`L-Win+Z`) filtresiyle açar. |
| Canlı Yardım Kategorisiyle Aç | `Win+X` | `Win+X` (`Super+X`) | `Win+X` | Katmanı **X · Canlı Yardım** (`L-Win+X`) filtresiyle açar. |
| Turkcell Kategorisiyle Aç | `Win+Q` | `Win+Q` (`Super+Q`) | `Win+Q` | Katmanı **Q · Turkcell** (`L-Win+Q`) filtresiyle açar. |

> **Not (macOS):** `pynput` üzerinde `Win` tuşu Apple `Command (⌘)` tuşuna (`<cmd>`) karşılık gelir. macOS'ta `Cmd+A` (Tümünü Seç) veya `Cmd+Q` (Çıkış) ile çakışma yaşanmasını önlemek isterseniz **Ayarlar → Global Kısayollar** üzerinden bu tuşları `Ctrl+Alt+A` / `Ctrl+Shift+Q` gibi dilediğiniz bileşime değiştirebilirsiniz.

> **Not (Windows):** Windows 11'de `Win+A` (Hızlı Ayarlar), `Win+X` (Hızlı Bağlantı) veya `Win+Q` (Arama) sistem kısayolları işletim sistemi tarafından tutuluyorsa, QTP otomatik olarak alternatif kanca (`keyboard`) geri dönüşünü dener; gerekirse ayarlardan `Ctrl+Alt+*` gibi çakışmasız bir kısayol atayabilirsiniz.

---

## 2. Modlar Arası Etkileşim ve Katman Kısayolları (`--gui`, `--tui`, `--web`)

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
| Ayarları Aç | `Ctrl+,` (`⌘+,`) | `s` | `/api/settings` | Ayarları görüntüler veya düzenler. |
| Türkçe Yardım | `F1` | `F1` | `F1` | Uygulama içi Türkçe yardımı açar (**tüm modlarda aynı**). |
| Kapat / Çık | `Esc` | `q` / `Esc` | `Esc` | Katmanı veya modal pencereyi kapatır (**tüm modlarda aynı**). |

> Not: `Ctrl+K` / `Ctrl+Enter` / `Ctrl+,` tüm masaüstü işletim sistemlerinde (Windows, Linux, macOS) birincil standart olarak korunur; macOS'ta `⌘` eşdeğerleri yalnızca ek sunum kısayolu olarak eklenir. TUI modunda terminal sınırlamaları nedeniyle `c`, `/`, `e`, `b`, `r`, `s`, `q` tek tuş eşdeğerleri sağlanır.

---

## 3. Fare Etkileşimleri

| Olay | Windows | Linux | macOS | Açıklama |
| :--- | :--- | :--- | :--- | :--- |
| Satıra Sol Tık | Sol Tık | Sol Tık | Sol Tık | Seçili kaydı önceki aktif uygulamaya yapıştırır. |
| Satıra Shift+Tık | `Shift+Sol Tık` | `Shift+Sol Tık` | `Shift+Sol Tık` | Katmanı kapatmadan yalnızca panoya kopyalar. |
| Satır İçi "Kopyala" Düğmesi | Sol Tık | Sol Tık | Sol Tık | Satır üzerine gelince sağda çıkan düğme ile panoya kopyalar. |
| Bağlam Menüsü | Sağ Tık | Sağ Tık | Sağ Tık (`Ctrl+Tık`) | Kaydı panoya alır ve `Yapıştır / Kopyala / INI'de Göster / Yardım` menüsünü açar. |
| Tepsi Simgesi Çift Tık | Çift Tık | Çift Tık | Çift Tık | Katman penceresini açar. |
| Pencere Boyutlandırma | Sağ Alt Köşe Sürükle | Sağ Alt Köşe Sürükle | Sağ Alt Köşe Sürükle | Pencere boyutunu değiştirir ve `qtp_settings.json` içine kaydeder. |
