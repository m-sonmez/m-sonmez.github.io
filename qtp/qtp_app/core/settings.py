"""Taşınabilir ayar yönetimi (qtp_settings.json) — tüm modlar tarafından ortak kullanılır."""

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
    "web": {"port": 8765},
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
    "web": {
        "label": "Yerel Web Sunucusu",
        "tooltip": "--web modunun dinleyeceği 127.0.0.1 bağlantı noktası yapılandırması (varsayılan port: 8765).",
    },
}

VALID_THEMES = ("auto", "dark", "light")
VALID_PASTE_METHODS = ("auto", "ctrl_v", "shift_insert", "type")
VALID_LOG_LEVELS = ("debug", "info", "warn", "error")


class SettingValidationError(ValueError):
    """Geçersiz ayar anahtarı veya değeri için Türkçe hata."""


def get_app_dir() -> Path:
    """Çalıştırılabilir dosyanın (veya geliştirme ortamında proje kökünün) dizinini döndürür."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent.parent


def get_os_fallback_dir(platform_name: str | None = None) -> Path:
    """Salt-okunur klasör durumunda işletim sistemine özgü kullanıcı yapılandırma klasörünü döndürür."""
    plat = platform_name or sys.platform
    if plat == "win32":
        base = os.environ.get("APPDATA") or os.environ.get("USERPROFILE") or str(Path.home() / "AppData" / "Roaming")
        if os.environ.get("APPDATA"):
            return Path(base) / "QTP"
        return Path(base) / "AppData" / "Roaming" / "QTP"
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
    """Ayarlar ve günlük dosyaları için yazılabilir klasörü çözer."""
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

    raw_web = raw.get("web")
    if isinstance(raw_web, dict):
        try:
            port = int(raw_web.get("port", 8765))
            if 0 <= port <= 65535:
                merged["web"] = {"port": port}
        except (TypeError, ValueError):
            pass

    return merged


def _parse_bool(raw_val: Any) -> bool:
    if isinstance(raw_val, bool):
        return raw_val
    s = str(raw_val).strip().lower()
    if s in ("true", "1", "evet", "yes", "on"):
        return True
    if s in ("false", "0", "hayir", "hayır", "no", "off"):
        return False
    raise SettingValidationError(f"Geçersiz mantıksal değer: '{raw_val}' (true/false bekleniyor).")


def get_setting_value(settings: dict[str, Any], key: str) -> Any:
    """Noktalı yollar dahil ('web.port', 'hotkeys.A') ayar değerini döndürür."""
    norm = (key or "").strip()
    if not norm:
        raise SettingValidationError("Geçersiz ayar anahtarı: boş anahtar.")
    if "." in norm:
        head, sub = norm.split(".", 1)
        if head in settings and isinstance(settings[head], dict) and sub in settings[head]:
            return settings[head][sub]
        raise SettingValidationError(f"Geçersiz ayar anahtarı: '{norm}'.")
    if norm not in DEFAULT_SETTINGS:
        raise SettingValidationError(f"Geçersiz ayar anahtarı: '{norm}'.")
    return settings.get(norm, DEFAULT_SETTINGS[norm])


def set_setting_value(settings: dict[str, Any], key: str, value: Any) -> dict[str, Any]:
    """Belirtilen ayar anahtarını doğrulayarak günceller ve yeni sözlük döndürür."""
    norm = (key or "").strip()
    updated = copy.deepcopy(settings)

    if norm == "theme":
        val = str(value).strip().lower()
        if val not in VALID_THEMES:
            raise SettingValidationError(f"Geçersiz ayar değeri ('theme'): '{value}' ({', '.join(VALID_THEMES)}).")
        updated["theme"] = val
    elif norm == "paste_method":
        val = str(value).strip().lower()
        if val not in VALID_PASTE_METHODS:
            raise SettingValidationError(
                f"Geçersiz ayar değeri ('paste_method'): '{value}' ({', '.join(VALID_PASTE_METHODS)})."
            )
        updated["paste_method"] = val
    elif norm == "log_level":
        val = str(value).strip().lower()
        if val not in VALID_LOG_LEVELS:
            raise SettingValidationError(
                f"Geçersiz ayar değeri ('log_level'): '{value}' ({', '.join(VALID_LOG_LEVELS)})."
            )
        updated["log_level"] = val
    elif norm == "last_category":
        val = str(value).strip().upper()
        if val not in ("ALL", "A", "Z", "X", "Q"):
            raise SettingValidationError(f"Geçersiz ayar değeri ('last_category'): '{value}' (ALL/A/Z/X/Q).")
        updated["last_category"] = val
    elif norm in ("enter_after_paste", "start_minimized", "tray_icon"):
        updated[norm] = _parse_bool(value)
    elif norm == "backup_count":
        try:
            bc = int(value)
        except (TypeError, ValueError) as exc:
            raise SettingValidationError(f"Geçersiz ayar değeri ('backup_count'): '{value}'.") from exc
        if not (1 <= bc <= 100):
            raise SettingValidationError(f"Geçersiz ayar değeri ('backup_count'): {bc} (1–100 aralığında olmalı).")
        updated["backup_count"] = bc
    elif norm == "data_path":
        dp = str(value).strip()
        if not dp:
            raise SettingValidationError("Geçersiz ayar değeri ('data_path'): boş yol olamaz.")
        updated["data_path"] = dp
    elif norm == "language":
        val = str(value).strip().lower()
        if val != "tr":
            raise SettingValidationError(f"Geçersiz ayar değeri ('language'): '{value}' (yalnızca 'tr').")
        updated["language"] = "tr"
    elif norm == "window_size":
        if isinstance(value, str):
            parts = [p.strip() for p in value.replace("x", ",").replace("×", ",").split(",")]
        elif isinstance(value, (list, tuple)):
            parts = list(value)
        else:
            parts = []
        if len(parts) != 2:
            raise SettingValidationError(f"Geçersiz ayar değeri ('window_size'): '{value}' (örn. 720,520).")
        try:
            w, h = int(parts[0]), int(parts[1])
        except (TypeError, ValueError) as exc:
            raise SettingValidationError(f"Geçersiz ayar değeri ('window_size'): '{value}'.") from exc
        if not (480 <= w <= 2400 and 360 <= h <= 1600):
            raise SettingValidationError("Geçersiz ayar değeri ('window_size'): aralık dışı.")
        updated["window_size"] = [w, h]
    elif norm == "web.port":
        try:
            port = int(value)
        except (TypeError, ValueError) as exc:
            raise SettingValidationError(f"Geçersiz ayar değeri ('web.port'): '{value}'.") from exc
        if not (0 <= port <= 65535):
            raise SettingValidationError(f"Geçersiz ayar değeri ('web.port'): {port} (0–65535).")
        updated.setdefault("web", {})["port"] = port
    elif norm.startswith("hotkeys."):
        sub = norm.split(".", 1)[1]
        if sub not in DEFAULT_HOTKEYS:
            raise SettingValidationError(f"Geçersiz ayar anahtarı: '{norm}'.")
        val = str(value).strip()
        if not val:
            raise SettingValidationError(f"Geçersiz ayar değeri ('{norm}'): boş kısayol.")
        updated.setdefault("hotkeys", dict(DEFAULT_HOTKEYS))[sub] = val
    else:
        raise SettingValidationError(f"Geçersiz ayar anahtarı: '{norm}'.")

    return _sanitize_settings(updated)


def load_settings(
    preferred_dir: str | Path | None = None,
    *,
    platform_name: str | None = None,
) -> tuple[dict[str, Any], Path, str | None]:
    """qtp_settings.json dosyasını yükler; yoksa varsayılanlarla oluşturur."""
    logger = get_logger("settings")
    config_dir, portable = resolve_config_dir(preferred_dir, platform_name=platform_name)
    settings_path = config_dir / SETTINGS_FILENAME

    if not settings_path.is_file():
        defaults = copy.deepcopy(DEFAULT_SETTINGS)
        save_settings(defaults, settings_path)
        logger.info("Varsayılan ayarlar oluşturuldu: %s (taşınabilir=%s)", settings_path, portable)
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
