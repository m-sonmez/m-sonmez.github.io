"""Taşınabilir ayar yönetimi (qtp_settings.json)."""

from __future__ import annotations

import copy
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

from qtp_app.core.ini_parser import atomic_write_bytes
from qtp_app.core.logging_setup import get_logger

SETTINGS_FILENAME = "qtp_settings.json"

DEFAULT_HOTKEYS: dict[str, str] = {
    "all": "Ctrl+Shift+Space",
    "A": "Win+A",
    "Z": "Win+Z",
    "X": "Win+X",
    "Q": "Win+Q",
}

DEFAULT_SETTINGS: dict[str, Any] = {
    "theme": "dark",
    "hotkeys": dict(DEFAULT_HOTKEYS),
    "last_category": "ALL",
    "last_category_by_hotkey": {},
    "window_size": [720, 520],
    "paste_method": "auto",
    "enter_after_paste": True,
    "start_minimized": False,
    "tray_icon": True,
    "data_path": "./QuickTextPaste.ini",
    "backup_count": 15,
    "log_level": "info",
    "language": "tr",
}

SETTING_DESCRIPTIONS: dict[str, dict[str, str]] = {
    "theme": {
        "label": "Tema",
        "tooltip": "Arayüz renk temasını belirler: 'auto' işletim sistemini izler, 'dark' koyu, 'light' açık tema kullanır.",
    },
    "hotkeys": {
        "label": "Global Kısayollar",
        "tooltip": "Katmanı (overlay) tüm kategoriler veya belirli kategoriler (A, Z, X, Q) için açan sistem geneli tuş bileşimleri.",
    },
    "last_category": {
        "label": "Son Seçili Kategori",
        "tooltip": "Katman genel kısayolla açıldığında otomatik seçilecek son kategori sekmesini hatırlar.",
    },
    "window_size": {
        "label": "Pencere Boyutu",
        "tooltip": "Katman penceresinin piksel cinsinden [genişlik, yükseklik] boyutu (varsayılan: 720x520).",
    },
    "paste_method": {
        "label": "Yapıştırma Yöntemi",
        "tooltip": "'auto' platforma göre Ctrl+V/Cmd+V veya Wayland'da wtype kullanır; gerekirse 'ctrl_v', 'shift_insert' veya 'type' seçilebilir.",
    },
    "enter_after_paste": {
        "label": "Yapıştırma Sonrası Enter (<E<N<D|)",
        "tooltip": "Kayıt '<E<N<D|' bitiş işaretine sahipse yapıştırma işleminden sonra otomatik Enter tuşu gönderir.",
    },
    "start_minimized": {
        "label": "Küçültülmüş Başlat",
        "tooltip": "Etkinleştirildiğinde uygulama açılışta katmanı göstermeden doğrudan sistem tepsisinde bekler.",
    },
    "tray_icon": {
        "label": "Sistem Tepsisi Simgesi",
        "tooltip": "Sistem tepsisi simgesini ve sağ tık menüsünü gösterir veya gizler.",
    },
    "data_path": {
        "label": "Veri Dosyası Yolu",
        "tooltip": "Okunacak ve kaydedilecek QuickTextPaste.ini dosyasının yolu (varsayılan: ./QuickTextPaste.ini).",
    },
    "backup_count": {
        "label": "Yedek Sayısı",
        "tooltip": "backups/ klasöründe saklanacak maksimum zaman damgalı yedek sayısı (varsayılan: 15).",
    },
    "log_level": {
        "label": "Günlük Düzeyi",
        "tooltip": "qtp.log dosyasına yazılacak ayrıntı düzeyi: debug, info, warn veya error.",
    },
    "language": {
        "label": "Arayüz Dili",
        "tooltip": "Uygulama dili (şu an yalnızca 'tr' desteklenmektedir; gelecek sürümler için ayrılmıştır).",
    },
}

VALID_THEMES = ("auto", "dark", "light")
VALID_PASTE_METHODS = ("auto", "ctrl_v", "shift_insert", "type")
VALID_LOG_LEVELS = ("debug", "info", "warn", "error")


def get_app_dir() -> Path:
    """Çalıştırılabilir dosyanın (veya geliştirme ortamında proje kökünün) dizinini döndürür."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent.parent


def get_os_fallback_dir(platform_name: str | None = None) -> Path:
    """Salt-okunur klasör durumunda işletim sistemine özgü kullanıcı yapılandırma klasörünü döndürür."""
    plat = platform_name or sys.platform
    if plat == "win32":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / "QTP"
    if plat == "darwin":
        return Path.home() / "Library" / "Application Support" / "QTP"
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base_dir = Path(xdg) if xdg else (Path.home() / ".config")
    return base_dir / "qtp"


def is_dir_writable(path: Path) -> bool:
    """Dizine gerçekten yazma izni olup olmadığını geçici dosya denemesiyle kontrol eder."""
    try:
        path.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".qtp_wtest_", dir=str(path))
        os.close(fd)
        Path(tmp).unlink(missing_ok=True)
        return True
    except OSError:
        return False


def resolve_config_dir(preferred_dir: str | Path | None = None, *, platform_name: str | None = None) -> tuple[Path, bool]:
    """
    Ayarlar ve günlük dosyaları için yazılabilir klasörü çözer.
    Dönüş: (klasör_yolu, taşınabilir_mi)
    """
    primary = Path(preferred_dir).resolve() if preferred_dir else get_app_dir()
    if is_dir_writable(primary):
        return primary, True
    fallback = get_os_fallback_dir(platform_name=platform_name)
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback, False


def _sanitize_settings(raw: dict[str, Any] | None) -> dict[str, Any]:
    merged = copy.deepcopy(DEFAULT_SETTINGS)
    if not isinstance(raw, dict):
        return merged

    theme = str(raw.get("theme", merged["theme"])).strip().lower()
    merged["theme"] = theme if theme in VALID_THEMES else DEFAULT_SETTINGS["theme"]

    raw_hotkeys = raw.get("hotkeys")
    if isinstance(raw_hotkeys, dict):
        hk = dict(DEFAULT_HOTKEYS)
        for key in DEFAULT_HOTKEYS:
            if key in raw_hotkeys and str(raw_hotkeys[key]).strip():
                hk[key] = str(raw_hotkeys[key]).strip()
        merged["hotkeys"] = hk

    if "last_category" in raw and isinstance(raw["last_category"], str):
        merged["last_category"] = raw["last_category"].strip() or "ALL"

    if isinstance(raw.get("last_category_by_hotkey"), dict):
        merged["last_category_by_hotkey"] = {
            str(k): str(v) for k, v in raw["last_category_by_hotkey"].items()
        }

    win_size = raw.get("window_size")
    if isinstance(win_size, (list, tuple)) and len(win_size) == 2:
        try:
            w = max(480, min(2400, int(win_size[0])))
            h = max(360, min(1600, int(win_size[1])))
            merged["window_size"] = [w, h]
        except (TypeError, ValueError):
            pass

    pm = str(raw.get("paste_method", merged["paste_method"])).strip().lower()
    merged["paste_method"] = pm if pm in VALID_PASTE_METHODS else DEFAULT_SETTINGS["paste_method"]

    merged["enter_after_paste"] = bool(raw.get("enter_after_paste", DEFAULT_SETTINGS["enter_after_paste"]))
    merged["start_minimized"] = bool(raw.get("start_minimized", DEFAULT_SETTINGS["start_minimized"]))
    merged["tray_icon"] = bool(raw.get("tray_icon", DEFAULT_SETTINGS["tray_icon"]))

    dp = str(raw.get("data_path", DEFAULT_SETTINGS["data_path"])).strip()
    merged["data_path"] = dp or DEFAULT_SETTINGS["data_path"]

    try:
        bc = int(raw.get("backup_count", DEFAULT_SETTINGS["backup_count"]))
        merged["backup_count"] = max(1, min(100, bc))
    except (TypeError, ValueError):
        pass

    ll = str(raw.get("log_level", DEFAULT_SETTINGS["log_level"])).strip().lower()
    merged["log_level"] = ll if ll in VALID_LOG_LEVELS else DEFAULT_SETTINGS["log_level"]

    lang = str(raw.get("language", "tr")).strip().lower()
    merged["language"] = "tr" if lang in ("", "tr") else "tr"

    return merged


def load_settings(
    preferred_dir: str | Path | None = None,
    *,
    platform_name: str | None = None,
) -> tuple[dict[str, Any], Path, str | None]:
    """
    qtp_settings.json dosyasını yükler; yoksa varsayılanlarla oluşturur.
    Bozuk JSON algılanırsa varsayılanları yeniden yazar ve Türkçe uyarı mesajı döndürür.
    Dönüş: (ayarlar_dict, settings_file_path, uyarı_mesajı_veya_None)
    """
    logger = get_logger("settings")
    config_dir, portable = resolve_config_dir(preferred_dir, platform_name=platform_name)
    settings_path = config_dir / SETTINGS_FILENAME
    warning_msg: str | None = None

    if not settings_path.is_file():
        defaults = copy.deepcopy(DEFAULT_SETTINGS)
        save_settings(defaults, settings_path)
        logger.info(
            "Varsayılan ayarlar oluşturuldu: %s (taşınabilir=%s)",
            settings_path,
            portable,
        )
        return defaults, settings_path, None

    try:
        text = settings_path.read_text(encoding="utf-8")
        raw = json.loads(text)
        if not isinstance(raw, dict):
            raise ValueError("Kök JSON nesnesi sözlük değil.")
        clean = _sanitize_settings(raw)
        return clean, settings_path, None
    except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
        warning_msg = (
            f"Bozuk ayar dosyası ({settings_path}) algılandı; varsayılan ayarlarla yeniden oluşturuldu ({exc})."
        )
        logger.warning(warning_msg)
        defaults = copy.deepcopy(DEFAULT_SETTINGS)
        save_settings(defaults, settings_path)
        return defaults, settings_path, warning_msg


def save_settings(settings: dict[str, Any], settings_path: str | Path) -> Path:
    """Ayarları temizleyerek diske atomik yazar."""
    path = Path(settings_path)
    clean = _sanitize_settings(settings)
    payload = json.dumps(clean, ensure_ascii=False, indent=2) + "\n"
    atomic_write_bytes(path, payload.encode("utf-8"))
    get_logger("settings").info("Ayarlar kaydedildi: %s", path)
    return path


def resolve_data_path(settings: dict[str, Any], base_dir: Path) -> Path:
    """data_path ayarını mutlak yola çevirir."""
    raw = str(settings.get("data_path") or "./QuickTextPaste.ini").strip()
    p = Path(raw)
    if p.is_absolute():
        return p
    return (base_dir / p).resolve()
