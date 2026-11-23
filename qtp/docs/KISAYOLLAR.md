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

## 2. Katman (Overlay) İçi Klavye Kısayolları

Katman penceresi açıkken aşağıdaki tuşların tamamı üç işletim sisteminde **aynı** şekilde çalışır:

| Olay | Kısayol (Windows) | Kısayol (Linux) | Kısayol (macOS) | Açıklama |
| :--- | :--- | :--- | :--- | :--- |
| Sonraki Öğeye Geç | `↓` (Aşağı Ok) | `↓` (Aşağı Ok) | `↓` (Aşağı Ok) | Listede bir alt satırı seçer (arama kutusu odaktayken de çalışır). |
| Önceki Öğeye Geç | `↑` (Yukarı Ok) | `↑` (Yukarı Ok) | `↑` (Yukarı Ok) | Listede bir üst satırı seçer. |
| Hızlı Aşağı Atla | `PageDown` | `PageDown` | `PageDown` | Listede 6 satır aşağı kaydırır. |
| Hızlı Yukarı Atla | `PageUp` | `PageUp` | `PageUp` | Listede 6 satır yukarı kaydırır. |
| Yapıştır ve Kapat | `Enter` (`⏎`) | `Enter` (`⏎`) | `Enter` (`⏎`) | Katmanı gizler, önceki uygulamaya döner, metni yapıştırır (`<E<N<D|` varsa `Enter` basar). |
| Yalnızca Panoya Kopyala | `Ctrl+Enter` | `Ctrl+Enter` | `Ctrl+Enter` (ek alias: `⌘+Enter`) | Katmanı kapatmadan metni panoya kopyalar ve toast bildirimi gösterir. |
| Aramaya Odaklan | `Ctrl+K` | `Ctrl+K` | `Ctrl+K` (ek alias: `⌘+K`) | İmleci arama kutusuna taşır ve mevcut arama metnini seçer. |
| Ayarları Aç | `Ctrl+,` | `Ctrl+,` | `Ctrl+,` (ek alias: `⌘+,`) | Ayarlar penceresini açar. |
| Türkçe Yardımı Aç | `F1` | `F1` | `F1` | Uygulama içi Türkçe yardım penceresini açar. |
| Katmanı Kapat | `Esc` | `Esc` | `Esc` | Yapıştırma yapmadan katmanı animasyonla gizler. |

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
