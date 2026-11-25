"""Universal internationalization (i18n) catalog for QTP with auto-detection and custom qtp_locale.json overrides."""

from __future__ import annotations

import ctypes
import json
import locale
import os
import sys
from pathlib import Path
from typing import Any

DEFAULT_LANGUAGE = "auto"
BUILTIN_LANGUAGES: tuple[str, ...] = ("en", "tr")
LOCALE_FILENAME = "qtp_locale.json"

CATALOGS: dict[str, dict[str, str]] = {
    "en": {
        "app.display_name": "QTP — QuickTextPaste",
        "cat.all": "All",
        "cat.default_group": "General",
        "overlay.search_placeholder": "Search… (text, category, label)",
        "overlay.search_chip": "Ctrl+K",
        "overlay.footer_hints": "↑↓ Navigate · ⏎ Paste · Ctrl+⏎ Copy · Esc Close",
        "overlay.all_groups": "All Groups",
        "overlay.favorites_only": "Favorites",
        "overlay.notes_only": "Notes",
        "overlay.strip_emoji": "No Emoji",
        "overlay.new_snippet": "+ New",
        "overlay.save": "Save",
        "overlay.undo": "Undo",
        "overlay.redo": "Redo",
        "overlay.groups": "Groups",
        "overlay.settings": "Settings",
        "overlay.help": "Help",
        "overlay.bulk_edit": "Bulk Edit",
        "overlay.bulk_delete": "Delete Selected",
        "overlay.select_all": "Select All",
        "overlay.clear_selection": "Clear Selection",
        "overlay.selected_count": "{count} selected",
        "overlay.sort.order": "Order",
        "overlay.sort.usage": "Most Used",
        "overlay.sort.alpha": "A–Z",
        "overlay.sort.keys": "Shortcut",
        "overlay.sort.favorites": "Favorites First",
        "overlay.view.list": "List",
        "overlay.view.grid": "Grid",
        "overlay.view.table": "Table",
        "overlay.view_tooltip": "Switch View Mode (List / Grid / Table)",
        "overlay.empty": "No matching snippets found.",
        "overlay.copied": "Copied to clipboard ✔",
        "overlay.pasted": "Pasted ✔",
        "overlay.ctx.paste": "Paste (Enter)",
        "overlay.ctx.copy": "Copy (Ctrl+Enter)",
        "overlay.ctx.copy_plain": "Copy without Emoji",
        "overlay.ctx.favorite_add": "Add to Favorites",
        "overlay.ctx.favorite_remove": "Remove from Favorites",
        "overlay.ctx.edit": "Edit…",
        "overlay.ctx.duplicate": "Duplicate",
        "overlay.ctx.move_up": "Move Up",
        "overlay.ctx.move_down": "Move Down",
        "overlay.ctx.show_ini": "Show INI Entry",
        "overlay.ctx.delete": "Delete",
        "overlay.dlg.new_title": "New Snippet",
        "overlay.dlg.edit_title": "Edit Snippet",
        "overlay.dlg.keys": "Hotkey Prefix",
        "overlay.dlg.group": "Group",
        "overlay.dlg.label": "Label",
        "overlay.dlg.text": "Snippet Text",
        "overlay.dlg.end_marker": "Append <E<N<D| (Enter after paste)",
        "overlay.dlg.favorite": "Mark as Favorite",
        "overlay.dlg.save": "Save",
        "overlay.dlg.cancel": "Cancel",
        "overlay.dlg.close": "Close",
        "overlay.dlg.ini_title": "INI Entry",
        "overlay.dlg.delete_confirm_title": "Delete Snippet",
        "overlay.dlg.delete_confirm_body": "Delete this snippet?",
        "overlay.dlg.bulk_title": "Bulk Edit ({count} items)",
        "overlay.dlg.bulk_keys": "New Hotkey Prefix (leave empty to keep)",
        "overlay.dlg.bulk_group": "New Group (leave empty to keep)",
        "overlay.dlg.bulk_find": "Find Text",
        "overlay.dlg.bulk_replace": "Replace With",
        "overlay.dlg.bulk_ignore_case": "Case-insensitive",
        "overlay.dlg.bulk_prefix": "Prefix",
        "overlay.dlg.bulk_suffix": "Suffix",
        "overlay.dlg.bulk_strip_emojis": "Remove Emojis",
        "overlay.dlg.bulk_add_emoji": "Append Emoji",
        "overlay.dlg.bulk_favorite": "Favorites",
        "overlay.dlg.bulk_fav_keep": "Keep",
        "overlay.dlg.bulk_fav_add": "Mark Favorite",
        "overlay.dlg.bulk_fav_remove": "Unmark Favorite",
        "overlay.dlg.bulk_apply": "Apply",
        "overlay.dlg.groups_title": "Manage Groups",
        "overlay.dlg.groups_rename": "Rename / Merge",
        "overlay.dlg.groups_delete": "Delete Group",
        "overlay.dlg.groups_new_name": "New group name:",
        "overlay.dlg.groups_delete_confirm": "Delete group '{name}' and all its snippets?",
        "overlay.dlg.empty_text_error": "Text field cannot be empty.",
        "settings.title": "QTP — Settings",
        "settings.sec.appearance": "Appearance & Language",
        "settings.sec.behavior": "Behavior & Pasting",
        "settings.sec.categories": "Categories (Dynamic & Custom)",
        "settings.sec.hotkeys": "Global Hotkeys",
        "settings.sec.advanced": "Storage & Advanced",
        "settings.theme": "Theme",
        "settings.theme.auto": "Auto (System)",
        "settings.theme.light": "Light",
        "settings.theme.dark": "Dark",
        "settings.language": "Language",
        "settings.language.auto": "Auto (OS Locale)",
        "settings.view_mode": "Default View",
        "settings.sort_by": "Default Sort",
        "settings.last_category": "Startup Category",
        "settings.paste_method": "Paste Method",
        "settings.enter_after_paste": "Send Enter after paste (<E<N<D|)",
        "settings.hide_on_blur": "Hide overlay when focus is lost",
        "settings.strip_emoji": "Strip emojis when copying / pasting",
        "settings.start_minimized": "Start minimized in system tray",
        "settings.tray_icon": "Show system tray icon",
        "settings.auto_reload": "Live auto-reload on file changes",
        "settings.auto_reload_interval": "Auto-reload interval (ms)",
        "settings.data_path": "Data File Path",
        "settings.backup_count": "Max Backups",
        "settings.log_level": "Log Level",
        "settings.web_port": "Web Server Port",
        "settings.window_size": "Window Size (W × H)",
        "settings.cat.code": "Code",
        "settings.cat.label": "Label",
        "settings.cat.prefix": "Hotkey Prefix",
        "settings.cat.add": "+ Add Category",
        "settings.cat.remove": "Remove",
        "settings.cat.hint": "Categories are also auto-discovered from loaded snippets.",
        "settings.hk.preset": "Preset Profile",
        "settings.hk.apply_preset": "Apply Preset",
        "settings.hk.all_slot": "All Snippets (all)",
        "settings.hk.cat_slot": "Category {code}",
        "settings.hk.record": "Record…",
        "settings.hk.press_keys": "Press keys…",
        "settings.hk.clear": "Clear",
        "settings.hk.add_slot": "+ Add Hotkey Slot",
        "settings.hk.apply_mods": "Apply Modifiers to All",
        "settings.hk.conflicts_none": "No hotkey conflicts detected ✔",
        "settings.btn.save": "Save",
        "settings.btn.reset": "Reset Defaults",
        "settings.btn.cancel": "Cancel",
        "preset.recommended": "Recommended — Conflict-Free (Win+Alt)",
        "preset.win_ctrl": "Win+Ctrl Combination (Win+Ctrl)",
        "preset.ctrl_alt": "Ctrl+Alt Combination (Note: AltGr layouts)",
        "preset.ctrl_shift_alt": "Triple Modifier (No Win Key — Ctrl+Alt+Shift)",
        "preset.function_keys": "Function Keys (No Win Key — Ctrl+Shift+F1–Fn)",
        "preset.legacy_win": "Classic QuickTextPaste (Win — Conflict Risk)",
        "conflict.intl_altgr": "On international keyboard layouts using AltGr, '{combo}' may interfere with typing special characters.",
        "conflict.duplicate": "Duplicate binding: '{combo}' is also assigned to another slot ({others}).",
        "tray.open": "Open QTP Overlay",
        "tray.settings": "Settings…",
        "tray.reload": "Reload Data",
        "tray.backups": "Backups…",
        "tray.help": "Help (F1)",
        "tray.quit": "Quit",
        "tray.ready": "QTP ready.",
        "tray.assign_hotkey": "Assign a hotkey in Tray or Settings (Ctrl+,)",
        "help.title": "QTP — Help & Documentation",
        "help.tab.usage": "Usage",
        "help.tab.install": "Installation",
        "help.tab.hotkeys": "Hotkeys",
        "help.tab.faq": "FAQ",
        "help.tab.cli": "CLI Reference",
        "help.search_placeholder": "Search inside documentation…",
        "help.close": "Close",
        "tui.header_brand": "QTP",
        "tui.footer": "↑↓ Move  Enter Paste  c Copy  / Search  Tab/1-9 Cat  F Fav  N Notes  a Add  E Edit  d Del  s Settings  F1 Help  q Quit",
        "tui.filter_fav": "FAV",
        "tui.filter_notes": "NOTES",
        "tui.empty": "(no matching items)",
        "tui.search_label": "Search",
        "tui.status_ready": "Ready",
        "desc.theme.label": "Theme",
        "desc.theme.tooltip": "Controls the interface color theme: 'auto' follows OS, 'dark' uses dark mode, 'light' uses light mode.",
        "desc.view_mode.label": "View Mode",
        "desc.view_mode.tooltip": "Layout mode for the snippet list: 'list', 'grid', or 'table'.",
        "desc.strip_emoji.label": "Copy / Paste without Emoji",
        "desc.strip_emoji.tooltip": "Automatically removes Unicode emojis when copying or pasting while keeping saved text untouched.",
        "desc.sort_by.label": "Sort Order",
        "desc.sort_by.tooltip": "Sorting order: 'order', 'usage' (Most Used), 'alpha' (A–Z), 'keys' (Shortcut), 'favorites' (Favorites First).",
        "desc.categories.label": "Custom Categories",
        "desc.categories.tooltip": "Optional list of custom categories ([{code, label, hotkey_prefix}]). Additional categories are auto-discovered from loaded snippets.",
        "desc.hotkeys.label": "Global Hotkeys",
        "desc.hotkeys.tooltip": "System-wide key combinations opening the overlay for 'all' or any dynamic category/custom slot.",
        "desc.last_category.label": "Last Selected Category",
        "desc.last_category.tooltip": "Remembers the last selected category code ('ALL' or any valid category code).",
        "desc.window_size.label": "Window Size",
        "desc.window_size.tooltip": "Overlay window [width, height] in pixels (default: 720x520).",
        "desc.paste_method.label": "Paste Method",
        "desc.paste_method.tooltip": "'auto' selects the best strategy for the platform; override with 'ctrl_v', 'ctrl_shift_v', 'shift_insert', or 'type'.",
        "desc.enter_after_paste.label": "Enter After Paste (<E<N<D|)",
        "desc.enter_after_paste.tooltip": "Automatically sends Enter after pasting when a snippet has the '<E<N<D|' end marker.",
        "desc.hide_on_blur.label": "Hide on Focus Loss",
        "desc.hide_on_blur.tooltip": "Automatically hides the overlay when clicking outside or switching windows.",
        "desc.start_minimized.label": "Start Minimized",
        "desc.start_minimized.tooltip": "Starts directly in the system tray without showing the overlay on launch.",
        "desc.tray_icon.label": "System Tray Icon",
        "desc.tray_icon.tooltip": "Shows or hides the system tray icon and context menu.",
        "desc.data_path.label": "Data File Path",
        "desc.data_path.tooltip": "Path to QuickTextPaste.ini for reading and saving (default: ./QuickTextPaste.ini).",
        "desc.backup_count.label": "Backup Count",
        "desc.backup_count.tooltip": "Maximum number of timestamped snapshots kept in backups/ (default: 15).",
        "desc.log_level.label": "Log Level",
        "desc.log_level.tooltip": "Verbosity for qtp.log: debug, info, warn, or error.",
        "desc.language.label": "Interface Language",
        "desc.language.tooltip": "UI language: 'auto' (OS locale), 'en', 'tr', or any custom locale defined in qtp_locale.json.",
        "desc.auto_reload.label": "Live Auto-Reload",
        "desc.auto_reload.tooltip": "Automatically reloads external edits to qtp_settings.json, QuickTextPaste.ini, and data.json without restarting.",
        "desc.auto_reload_interval_ms.label": "Auto-Reload Interval (ms)",
        "desc.auto_reload_interval_ms.tooltip": "Polling interval for external file edits (100–10000 ms, default: 500 ms).",
        "desc.web.label": "Local Web Server",
        "desc.web.tooltip": "Loopback 127.0.0.1 port configuration for --web mode (default port: 8765).",
    },
    "tr": {
        "app.display_name": "QTP — QuickTextPaste",
        "cat.all": "Tümü",
        "cat.default_group": "Genel",
        "overlay.search_placeholder": "Ara… (metin, kategori, etiket)",
        "overlay.search_chip": "Ctrl+K",
        "overlay.footer_hints": "↑↓ Gezin · ⏎ Yapıştır · Ctrl+⏎ Kopyala · Esc Kapat",
        "overlay.all_groups": "Tüm Gruplar",
        "overlay.favorites_only": "Favoriler",
        "overlay.notes_only": "Notlar",
        "overlay.strip_emoji": "Emojisiz",
        "overlay.new_snippet": "+ Yeni",
        "overlay.save": "Kaydet",
        "overlay.undo": "Geri Al",
        "overlay.redo": "Yinele",
        "overlay.groups": "Gruplar",
        "overlay.settings": "Ayarlar",
        "overlay.help": "Yardım",
        "overlay.bulk_edit": "Toplu Düzenle",
        "overlay.bulk_delete": "Seçileni Sil",
        "overlay.select_all": "Tümünü Seç",
        "overlay.clear_selection": "Seçimi Temizle",
        "overlay.selected_count": "{count} seçili",
        "overlay.sort.order": "Sıra",
        "overlay.sort.usage": "En Çok Kullanılan",
        "overlay.sort.alpha": "A–Z",
        "overlay.sort.keys": "Kısayol",
        "overlay.sort.favorites": "Favoriler Önce",
        "overlay.view.list": "Liste",
        "overlay.view.grid": "Izgara",
        "overlay.view.table": "Tablo",
        "overlay.view_tooltip": "Görünüm Kipini Değiştir (Liste / Izgara / Tablo)",
        "overlay.empty": "Eşleşen kayıt bulunamadı.",
        "overlay.copied": "Panoya kopyalandı ✔",
        "overlay.pasted": "Yapıştırıldı ✔",
        "overlay.ctx.paste": "Yapıştır (Enter)",
        "overlay.ctx.copy": "Kopyala (Ctrl+Enter)",
        "overlay.ctx.copy_plain": "Emojisiz Kopyala",
        "overlay.ctx.favorite_add": "Favorilere Ekle",
        "overlay.ctx.favorite_remove": "Favorilerden Çıkar",
        "overlay.ctx.edit": "Düzenle…",
        "overlay.ctx.duplicate": "Çoğalt",
        "overlay.ctx.move_up": "Yukarı Taşı",
        "overlay.ctx.move_down": "Aşağı Taşı",
        "overlay.ctx.show_ini": "INI Kaydını Göster",
        "overlay.ctx.delete": "Sil",
        "overlay.dlg.new_title": "Yeni Kayıt",
        "overlay.dlg.edit_title": "Kaydı Düzenle",
        "overlay.dlg.keys": "Kısayol Öneki",
        "overlay.dlg.group": "Grup",
        "overlay.dlg.label": "Etiket",
        "overlay.dlg.text": "Metin",
        "overlay.dlg.end_marker": "<E<N<D| bitiş işaretini ekle (Yapıştırma sonrası Enter)",
        "overlay.dlg.favorite": "Favori olarak işaretle",
        "overlay.dlg.save": "Kaydet",
        "overlay.dlg.cancel": "Vazgeç",
        "overlay.dlg.close": "Kapat",
        "overlay.dlg.ini_title": "INI Kaydı",
        "overlay.dlg.delete_confirm_title": "Kaydı Sil",
        "overlay.dlg.delete_confirm_body": "Bu kayıt silinsin mi?",
        "overlay.dlg.bulk_title": "Toplu Düzenle ({count} kayıt)",
        "overlay.dlg.bulk_keys": "Yeni Kısayol Öneki (korumak için boş bırakın)",
        "overlay.dlg.bulk_group": "Yeni Grup (korumak için boş bırakın)",
        "overlay.dlg.bulk_find": "Bulunacak Metin",
        "overlay.dlg.bulk_replace": "Yeni Metin",
        "overlay.dlg.bulk_ignore_case": "Büyük/küçük harf duyarsız",
        "overlay.dlg.bulk_prefix": "Önek",
        "overlay.dlg.bulk_suffix": "Sonek",
        "overlay.dlg.bulk_strip_emojis": "Emojileri Temizle",
        "overlay.dlg.bulk_add_emoji": "Emoji Ekle",
        "overlay.dlg.bulk_favorite": "Favori",
        "overlay.dlg.bulk_fav_keep": "Değiştirme",
        "overlay.dlg.bulk_fav_add": "Favori Yap",
        "overlay.dlg.bulk_fav_remove": "Favoriden Çıkar",
        "overlay.dlg.bulk_apply": "Uygula",
        "overlay.dlg.groups_title": "Grup Yönetimi",
        "overlay.dlg.groups_rename": "Yeniden Adlandır / Birleştir",
        "overlay.dlg.groups_delete": "Grubu Sil",
        "overlay.dlg.groups_new_name": "Yeni grup adı:",
        "overlay.dlg.groups_delete_confirm": "'{name}' grubu ve içindeki tüm kayıtlar silinsin mi?",
        "overlay.dlg.empty_text_error": "Metin alanı boş olamaz.",
        "settings.title": "QTP — Ayarlar",
        "settings.sec.appearance": "Görünüm ve Dil",
        "settings.sec.behavior": "Davranış ve Yapıştırma",
        "settings.sec.categories": "Kategoriler (Dinamik ve Özel)",
        "settings.sec.hotkeys": "Global Kısayollar",
        "settings.sec.advanced": "Depolama ve Gelişmiş",
        "settings.theme": "Tema",
        "settings.theme.auto": "Otomatik (Sistem)",
        "settings.theme.light": "Açık",
        "settings.theme.dark": "Koyu",
        "settings.language": "Arayüz Dili",
        "settings.language.auto": "Otomatik (Sistem Dili)",
        "settings.view_mode": "Varsayılan Görünüm",
        "settings.sort_by": "Varsayılan Sıralama",
        "settings.last_category": "Açılış Kategorisi",
        "settings.paste_method": "Yapıştırma Yöntemi",
        "settings.enter_after_paste": "Yapıştırma sonrası Enter (<E<N<D|)",
        "settings.hide_on_blur": "Odağı kaybedince katmanı otomatik gizle",
        "settings.strip_emoji": "Kopyalama/yapıştırma sırasında emojileri temizle",
        "settings.start_minimized": "Sistem tepsisinde küçültülmüş başlat",
        "settings.tray_icon": "Sistem tepsisi simgesini göster",
        "settings.auto_reload": "Dosya değişikliklerinde otomatik canlı yenile",
        "settings.auto_reload_interval": "Otomatik yenileme aralığı (ms)",
        "settings.data_path": "Veri Dosyası Yolu",
        "settings.backup_count": "Maksimum Yedek Sayısı",
        "settings.log_level": "Günlük Düzeyi",
        "settings.web_port": "Web Sunucu Portu",
        "settings.window_size": "Pencere Boyutu (G × Y)",
        "settings.cat.code": "Kod",
        "settings.cat.label": "Etiket",
        "settings.cat.prefix": "Kısayol Öneki",
        "settings.cat.add": "+ Kategori Ekle",
        "settings.cat.remove": "Kaldır",
        "settings.cat.hint": "Kategoriler yüklü kayıtlardan da otomatik algılanır.",
        "settings.hk.preset": "Kısayol Profili",
        "settings.hk.apply_preset": "Profili Uygula",
        "settings.hk.all_slot": "Tüm Kayıtlar (all)",
        "settings.hk.cat_slot": "Kategori {code}",
        "settings.hk.record": "Kaydet…",
        "settings.hk.press_keys": "Tuşlara basın…",
        "settings.hk.clear": "Temizle",
        "settings.hk.add_slot": "+ Kısayol Yuvası Ekle",
        "settings.hk.apply_mods": "Tümüne Değiştirici Uygula",
        "settings.hk.conflicts_none": "Kısayol çakışması bulunamadı ✔",
        "settings.btn.save": "Kaydet",
        "settings.btn.reset": "Varsayılanlara Sıfırla",
        "settings.btn.cancel": "Vazgeç",
        "preset.recommended": "Önerilen — Çakışmasız (Win+Alt)",
        "preset.win_ctrl": "Win+Ctrl Bileşimi (Win+Ctrl)",
        "preset.ctrl_alt": "Ctrl+Alt Bileşimi (Dikkat: TR-Q AltGr)",
        "preset.ctrl_shift_alt": "Üçlü Değiştirici (Win Tuşsuz — Ctrl+Alt+Shift)",
        "preset.function_keys": "Fonksiyon Tuşları (Win Tuşsuz — Ctrl+Shift+F1–Fn)",
        "preset.legacy_win": "Klasik QuickTextPaste (Win — Çakışma Riskli)",
        "conflict.intl_altgr": "AltGr kullanan klavye düzenlerinde '{combo}' özel karakter yazımını engelleyebilir.",
        "conflict.duplicate": "Çift atama: '{combo}' başka bir kategoride de kullanılıyor ({others}).",
        "tray.open": "QTP Katmanını Aç",
        "tray.settings": "Ayarlar…",
        "tray.reload": "Verileri Yeniden Yükle",
        "tray.backups": "Yedekler…",
        "tray.help": "Yardım (F1)",
        "tray.quit": "Çıkış",
        "tray.ready": "QTP hazır.",
        "tray.assign_hotkey": "Tepsi veya Ayarlar (Ctrl+,) ile kısayol atayın",
        "help.title": "QTP — Yardım ve Belgeler",
        "help.tab.usage": "Kullanım",
        "help.tab.install": "Kurulum",
        "help.tab.hotkeys": "Kısayollar",
        "help.tab.faq": "SSS",
        "help.tab.cli": "CLI Başvuru",
        "help.search_placeholder": "Belgelerde ara…",
        "help.close": "Kapat",
        "tui.header_brand": "QTP",
        "tui.footer": "↑↓ Gezin  Enter Yapıştır  c Kopyala  / Ara  Tab/1-9 Kat  F Fav  N Not  a Ekle  E Düzenle  d Sil  s Ayar  F1 Yardım  q Çık",
        "tui.filter_fav": "FAV",
        "tui.filter_notes": "NOT",
        "tui.empty": "(eşleşen kayıt yok)",
        "tui.search_label": "Ara",
        "tui.status_ready": "Hazır",
        "desc.theme.label": "Tema",
        "desc.theme.tooltip": "Arayüz renk temasını belirler: 'auto' işletim sistemini izler, 'dark' koyu, 'light' açık tema kullanır.",
        "desc.view_mode.label": "Görünüm Kipi",
        "desc.view_mode.tooltip": "Kayıt listesinin görünüm düzenini belirler: 'list' (Liste), 'grid' (Izgara) veya 'table' (Tablo).",
        "desc.strip_emoji.label": "Emojisiz Kopyala / Yapıştır",
        "desc.strip_emoji.tooltip": "Etkinleştirildiğinde kopyalama ve yapıştırma sırasında Unicode emojiler otomatik temizlenir; kayıtlı özgün metin korunur.",
        "desc.sort_by.label": "Sıralama Ölçütü",
        "desc.sort_by.tooltip": "Kayıtların sıralama düzeni: 'order' (Sıra), 'usage' (En Çok Kullanılan), 'alpha' (A–Z), 'keys' (Kısayol), 'favorites' (Favoriler Önce).",
        "desc.categories.label": "Özel Kategoriler",
        "desc.categories.tooltip": "İsteğe bağlı özel kategori listesi ([{code, label, hotkey_prefix}]). Ek kategoriler yüklü kayıtlardan otomatik algılanır.",
        "desc.hotkeys.label": "Global Kısayollar",
        "desc.hotkeys.tooltip": "Katmanı tüm kayıtlar ('all') veya herhangi bir dinamik kategori/özel yuva için açan sistem geneli tuş bileşimleri.",
        "desc.last_category.label": "Son Seçili Kategori",
        "desc.last_category.tooltip": "Katman genel kısayolla açıldığında otomatik seçilecek son kategori kodunu hatırlar ('ALL' veya geçerli kategori kodu).",
        "desc.window_size.label": "Pencere Boyutu",
        "desc.window_size.tooltip": "Katman penceresinin piksel cinsinden [genişlik, yükseklik] boyutu (varsayılan: 720x520).",
        "desc.paste_method.label": "Yapıştırma Yöntemi",
        "desc.paste_method.tooltip": "'auto' platforma ve hedef pencereye göre seçim yapar; gerekirse 'ctrl_v', 'ctrl_shift_v', 'shift_insert' veya 'type' seçilebilir.",
        "desc.enter_after_paste.label": "Yapıştırma Sonrası Enter (<E<N<D|)",
        "desc.enter_after_paste.tooltip": "Kayıt '<E<N<D|' bitiş işaretine sahipse yapıştırma işleminden sonra otomatik Enter tuşu gönderir.",
        "desc.hide_on_blur.label": "Odağı kaybedince katmanı otomatik gizle",
        "desc.hide_on_blur.tooltip": "Katman penceresi dışına tıklandığında veya başka bir pencereye geçildiğinde katmanı otomatik kapatır.",
        "desc.start_minimized.label": "Küçültülmüş Başlat",
        "desc.start_minimized.tooltip": "Etkinleştirildiğinde uygulama açılışta katmanı göstermeden doğrudan sistem tepsisinde bekler.",
        "desc.tray_icon.label": "Sistem Tepsisi Simgesi",
        "desc.tray_icon.tooltip": "Sistem tepsisi simgesini ve sağ tık menüsünü gösterir veya gizler.",
        "desc.data_path.label": "Veri Dosyası Yolu",
        "desc.data_path.tooltip": "Okunacak ve kaydedilecek QuickTextPaste.ini dosyasının yolu (varsayılan: ./QuickTextPaste.ini).",
        "desc.backup_count.label": "Yedek Sayısı",
        "desc.backup_count.tooltip": "backups/ klasöründe saklanacak maksimum zaman damgalı yedek sayısı (varsayılan: 15).",
        "desc.log_level.label": "Günlük Düzeyi",
        "desc.log_level.tooltip": "qtp.log dosyasına yazılacak ayrıntı düzeyi: debug, info, warn veya error.",
        "desc.language.label": "Arayüz Dili",
        "desc.language.tooltip": "Uygulama dili: 'auto' (sistem dili), 'en', 'tr' veya qtp_locale.json içindeki özel diller.",
        "desc.auto_reload.label": "Otomatik Canlı Yenileme",
        "desc.auto_reload.tooltip": "Etkinleştirildiğinde qtp_settings.json, QuickTextPaste.ini ve data.json dosyasındaki harici değişiklikler yeniden başlatma olmadan canlı yüklenir.",
        "desc.auto_reload_interval_ms.label": "Otomatik Yenileme Aralığı (ms)",
        "desc.auto_reload_interval_ms.tooltip": "Disk değişikliklerinin ne sıklıkla denetleneceğini belirler (100–10000 ms, varsayılan: 500 ms).",
        "desc.web.label": "Yerel Web Sunucusu",
        "desc.web.tooltip": "--web modunun dinleyeceği 127.0.0.1 bağlantı noktası yapılandırması (varsayılan port: 8765).",
    },
}


def detect_system_language(
    *,
    env: dict[str, str] | None = None,
    platform_name: str | None = None,
) -> str:
    """Resolves the OS/environment locale to 'tr' for Turkish systems, otherwise 'en'."""
    environ = env if env is not None else os.environ
    for var in ("LC_ALL", "LC_MESSAGES", "LANG", "LANGUAGE"):
        raw = str(environ.get(var, "")).strip()
        if not raw:
            continue
        first = raw.split(":", 1)[0].strip().lower()
        if not first or first in ("c", "posix", "c.utf-8", "c.utf8"):
            continue
        if first.startswith("tr"):
            return "tr"
        return "en"

    plat = platform_name or sys.platform
    if plat == "win32" and env is None:
        try:
            windll = getattr(ctypes, "windll", None)
            if windll is not None:
                lang_id = int(windll.kernel32.GetUserDefaultUILanguage())
                if (lang_id & 0x3FF) == 0x1F:
                    return "tr"
                return "en"
        except Exception:
            pass

    if env is None:
        try:
            loc = locale.getlocale()[0] or ""
            low = loc.strip().lower()
            if low.startswith("tr") or low.startswith("turkish"):
                return "tr"
        except Exception:
            pass

    return "en"


def load_custom_locales(config_dir: str | Path | None) -> dict[str, dict[str, str]]:
    """Loads optional external string overrides from <config_dir>/qtp_locale.json."""
    if not config_dir:
        return {}
    path = Path(config_dir) / LOCALE_FILENAME
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError):
        return {}
    if not isinstance(raw, dict):
        return {}

    result: dict[str, dict[str, str]] = {}
    global_overrides: dict[str, str] = {}
    for key, val in raw.items():
        k = str(key).strip()
        if not k:
            continue
        if isinstance(val, dict):
            lang_code = k.lower()
            bucket = result.setdefault(lang_code, {})
            for sub_k, sub_v in val.items():
                sk = str(sub_k).strip()
                if sk and isinstance(sub_v, str):
                    bucket[sk] = sub_v
        elif isinstance(val, str):
            global_overrides[k] = val

    if global_overrides:
        result["*"] = global_overrides
    return result


def available_languages(config_dir: str | Path | None = None) -> list[str]:
    """Returns valid language setting values ('auto', 'en', 'tr', plus custom qtp_locale.json locales)."""
    langs: list[str] = [DEFAULT_LANGUAGE, *BUILTIN_LANGUAGES]
    custom = load_custom_locales(config_dir)
    for code in sorted(custom.keys()):
        if code != "*" and code not in langs:
            langs.append(code)
    return langs


def resolve_language(
    lang_setting: str | None = DEFAULT_LANGUAGE,
    config_dir: str | Path | None = None,
    *,
    env: dict[str, str] | None = None,
    platform_name: str | None = None,
) -> str:
    """Resolves a configured language setting into a concrete locale code."""
    norm = str(lang_setting or DEFAULT_LANGUAGE).strip().lower()
    if not norm or norm == DEFAULT_LANGUAGE:
        return detect_system_language(env=env, platform_name=platform_name)
    if norm in BUILTIN_LANGUAGES:
        return norm
    custom = load_custom_locales(config_dir)
    if norm in custom:
        return norm
    return "en"


def get_catalog(lang: str = "en", config_dir: str | Path | None = None) -> dict[str, str]:
    """Returns the merged string catalog for the requested language and optional external overrides."""
    eff = resolve_language(lang, config_dir) if lang == DEFAULT_LANGUAGE else str(lang or "en").strip().lower()
    merged = dict(CATALOGS["en"])
    if eff in CATALOGS and eff != "en":
        merged.update(CATALOGS[eff])
    custom = load_custom_locales(config_dir)
    if "*" in custom:
        merged.update(custom["*"])
    if eff in custom:
        merged.update(custom[eff])
    return merged


def t(
    key: str,
    lang: str = "en",
    config_dir: str | Path | None = None,
    **kwargs: Any,
) -> str:
    """Translates a catalog key with optional str.format placeholders."""
    catalog = get_catalog(lang, config_dir)
    template = catalog.get(key, key)
    if not kwargs:
        return template
    try:
        return template.format(**kwargs)
    except Exception:
        return template
