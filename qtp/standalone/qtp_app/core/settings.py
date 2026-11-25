"""Portable settings management (qtp_settings.json) shared across all QTP modes."""

from __future__ import annotations

import copy
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

from qtp_app.core.hotkeys import HOTKEY_PRESETS, build_preset_hotkeys, normalize_hotkey
from qtp_app.core.i18n import DEFAULT_LANGUAGE, available_languages, t
from qtp_app.core.ini_parser import atomic_write_bytes
from qtp_app.core.logging_setup import get_logger

SETTINGS_FILENAME = "qtp_settings.json"

CATEGORY_CODE_RE = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
_LOCALE_CODE_RE = re.compile(r"^[a-z]{2,3}(?:[-_][a-z0-9]{2,8})?$")

DEFAULT_HOTKEYS: dict[str, str] = dict(HOTKEY_PRESETS["recommended"])

LEGACY_DEFAULT_HOTKEYS: dict[str, str] = {
    "all": "Ctrl+Shift+Space",
    "A": "Win+A",
    "Z": "Win+Z",
    "X": "Win+X",
    "Q": "Win+Q",
}

DEFAULT_SETTINGS: dict[str, Any] = {
    "theme": "light",
    "view_mode": "list",
    "strip_emoji": False,
    "sort_by": "order",
    "categories": [],
    "hotkeys": dict(DEFAULT_HOTKEYS),
    "last_category": "ALL",
    "last_category_by_hotkey": {},
    "window_size": [720, 520],
    "paste_method": "auto",
    "enter_after_paste": True,
    "hide_on_blur": True,
    "start_minimized": False,
    "tray_icon": True,
    "data_path": "./QuickTextPaste.ini",
    "backup_count": 15,
    "log_level": "info",
    "language": DEFAULT_LANGUAGE,
    "auto_reload": True,
    "auto_reload_interval_ms": 500,
    "web": {"port": 8765},
}

_SETTING_DESC_KEYS: tuple[str, ...] = (
    "theme",
    "view_mode",
    "strip_emoji",
    "sort_by",
    "categories",
    "hotkeys",
    "last_category",
    "window_size",
    "paste_method",
    "enter_after_paste",
    "hide_on_blur",
    "start_minimized",
    "tray_icon",
    "data_path",
    "backup_count",
    "log_level",
    "language",
    "auto_reload",
    "auto_reload_interval_ms",
    "web",
)


def get_setting_descriptions(
    lang: str = "en",
    config_dir: str | Path | None = None,
) -> dict[str, dict[str, str]]:
    """Returns localized label and tooltip descriptions for all setting keys."""
    return {
        key: {
            "label": t(f"desc.{key}.label", lang, config_dir),
            "tooltip": t(f"desc.{key}.tooltip", lang, config_dir),
        }
        for key in _SETTING_DESC_KEYS
    }


SETTING_DESCRIPTIONS: dict[str, dict[str, str]] = get_setting_descriptions("en")

VALID_THEMES = ("auto", "dark", "light")
VALID_VIEW_MODES = ("list", "grid", "table")
VALID_SORT_BY = ("order", "usage", "alpha", "keys", "favorites")
VALID_PASTE_METHODS = ("auto", "ctrl_v", "ctrl_shift_v", "shift_insert", "type")
VALID_LOG_LEVELS = ("debug", "info", "warn", "error")


class SettingValidationError(ValueError):
    """Validation error raised for invalid setting keys or values."""


def sanitize_categories(raw: Any) -> list[dict[str, str]]:
    """Sanitizes user-configured category entries into canonical {code, label, hotkey_prefix} dicts."""
    if not isinstance(raw, list):
        return []
    cleaned: list[dict[str, str]] = []
    seen_codes: set[str] = set()
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        code = str(entry.get("code", "")).strip().upper()
        if not code or code == "ALL" or not CATEGORY_CODE_RE.fullmatch(code):
            continue
        if code in seen_codes:
            continue
        seen_codes.add(code)
        label = str(entry.get("label", "")).strip() or code
        prefix = str(entry.get("hotkey_prefix", "")).strip()
        cleaned.append({"code": code, "label": label, "hotkey_prefix": prefix})
    return cleaned


def get_app_dir() -> Path:
    """Returns the executable directory (or repository standalone root during development)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent.parent


def get_os_fallback_dir(platform_name: str | None = None) -> Path:
    """Returns the OS user configuration directory when the app directory is read-only."""
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
    """Checks whether the directory is truly writable using a temporary file probe."""
    try:
        path.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".qtp_wtest_", dir=str(path))
        os.close(fd)
        Path(tmp).unlink(missing_ok=True)
        return True
    except OSError:
        return False


def resolve_config_dir(
    preferred_dir: str | Path | None = None,
    *,
    platform_name: str | None = None,
) -> tuple[Path, bool]:
    """Resolves a writable directory for settings and log files."""
    primary = Path(preferred_dir).resolve() if preferred_dir else get_app_dir()
    if is_dir_writable(primary):
        return primary, True
    fallback = get_os_fallback_dir(platform_name=platform_name)
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback, False


def _sanitize_settings(
    raw: dict[str, Any] | None,
    *,
    config_dir: str | Path | None = None,
) -> dict[str, Any]:
    merged = copy.deepcopy(DEFAULT_SETTINGS)
    if not isinstance(raw, dict):
        return merged

    theme = str(raw.get("theme", merged["theme"])).strip().lower()
    merged["theme"] = theme if theme in VALID_THEMES else DEFAULT_SETTINGS["theme"]

    vm = str(raw.get("view_mode", merged["view_mode"])).strip().lower()
    merged["view_mode"] = vm if vm in VALID_VIEW_MODES else DEFAULT_SETTINGS["view_mode"]

    merged["strip_emoji"] = bool(raw.get("strip_emoji", DEFAULT_SETTINGS["strip_emoji"]))

    sb = str(raw.get("sort_by", merged["sort_by"])).strip().lower()
    merged["sort_by"] = sb if sb in VALID_SORT_BY else DEFAULT_SETTINGS["sort_by"]

    merged["categories"] = sanitize_categories(raw.get("categories"))

    raw_hotkeys = raw.get("hotkeys")
    if isinstance(raw_hotkeys, dict):
        hk = dict(DEFAULT_HOTKEYS)
        for key, raw_val in raw_hotkeys.items():
            slot = str(key).strip()
            if not slot or "." in slot:
                continue
            val_text = str(raw_val or "").strip()
            if not val_text:
                if slot in DEFAULT_HOTKEYS:
                    hk[slot] = ""
                continue
            try:
                hk[slot] = normalize_hotkey(val_text)
            except ValueError:
                if slot in DEFAULT_HOTKEYS:
                    hk[slot] = DEFAULT_HOTKEYS[slot]
        merged["hotkeys"] = hk

    if "last_category" in raw and isinstance(raw["last_category"], str):
        lc = raw["last_category"].strip().upper()
        if lc == "ALL" or CATEGORY_CODE_RE.fullmatch(lc):
            merged["last_category"] = lc
        else:
            merged["last_category"] = "ALL"

    if isinstance(raw.get("last_category_by_hotkey"), dict):
        merged["last_category_by_hotkey"] = {
            str(k): str(v) for k, v in raw["last_category_by_hotkey"].items()
        }

    win_size = raw.get("window_size")
    if isinstance(win_size, (list, tuple)) and len(win_size) == 2:
        try:
            w = max(560, min(2400, int(win_size[0])))
            h = max(400, min(1600, int(win_size[1])))
            merged["window_size"] = [w, h]
        except (TypeError, ValueError):
            pass

    pm = str(raw.get("paste_method", merged["paste_method"])).strip().lower()
    merged["paste_method"] = pm if pm in VALID_PASTE_METHODS else DEFAULT_SETTINGS["paste_method"]

    merged["enter_after_paste"] = bool(raw.get("enter_after_paste", DEFAULT_SETTINGS["enter_after_paste"]))
    merged["hide_on_blur"] = bool(raw.get("hide_on_blur", DEFAULT_SETTINGS["hide_on_blur"]))
    merged["start_minimized"] = bool(raw.get("start_minimized", DEFAULT_SETTINGS["start_minimized"]))
    merged["tray_icon"] = bool(raw.get("tray_icon", DEFAULT_SETTINGS["tray_icon"]))
    merged["auto_reload"] = bool(raw.get("auto_reload", DEFAULT_SETTINGS["auto_reload"]))

    try:
        interval = int(raw.get("auto_reload_interval_ms", DEFAULT_SETTINGS["auto_reload_interval_ms"]))
        merged["auto_reload_interval_ms"] = max(100, min(10000, interval))
    except (TypeError, ValueError):
        pass

    dp = str(raw.get("data_path", DEFAULT_SETTINGS["data_path"])).strip()
    merged["data_path"] = dp or DEFAULT_SETTINGS["data_path"]

    try:
        bc = int(raw.get("backup_count", DEFAULT_SETTINGS["backup_count"]))
        merged["backup_count"] = max(1, min(100, bc))
    except (TypeError, ValueError):
        pass

    ll = str(raw.get("log_level", DEFAULT_SETTINGS["log_level"])).strip().lower()
    merged["log_level"] = ll if ll in VALID_LOG_LEVELS else DEFAULT_SETTINGS["log_level"]

    lang = str(raw.get("language", DEFAULT_LANGUAGE)).strip().lower()
    valid_langs = available_languages(config_dir)
    if lang in valid_langs:
        merged["language"] = lang
    elif config_dir is None and _LOCALE_CODE_RE.fullmatch(lang):
        merged["language"] = lang
    else:
        merged["language"] = DEFAULT_LANGUAGE

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
    """Returns the value of a setting key including dotted paths ('web.port', 'hotkeys.all')."""
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


def set_setting_value(
    settings: dict[str, Any],
    key: str,
    value: Any,
    *,
    config_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Validates and updates the requested setting key, returning a new sanitized settings dict."""
    norm = (key or "").strip()
    updated = copy.deepcopy(settings)

    if norm == "theme":
        val = str(value).strip().lower()
        if val not in VALID_THEMES:
            raise SettingValidationError(f"Geçersiz ayar değeri ('theme'): '{value}' ({', '.join(VALID_THEMES)}).")
        updated["theme"] = val
    elif norm == "view_mode":
        val = str(value).strip().lower()
        if val not in VALID_VIEW_MODES:
            raise SettingValidationError(
                f"Geçersiz ayar değeri ('view_mode'): '{value}' ({', '.join(VALID_VIEW_MODES)})."
            )
        updated["view_mode"] = val
    elif norm == "sort_by":
        val = str(value).strip().lower()
        if val not in VALID_SORT_BY:
            raise SettingValidationError(
                f"Geçersiz ayar değeri ('sort_by'): '{value}' ({', '.join(VALID_SORT_BY)})."
            )
        updated["sort_by"] = val
    elif norm == "categories":
        parsed_cats = value
        if isinstance(value, str):
            try:
                parsed_cats = json.loads(value)
            except json.JSONDecodeError as exc:
                raise SettingValidationError(
                    f"Geçersiz ayar değeri ('categories'): geçerli JSON listesi bekleniyor ({exc})."
                ) from exc
        if not isinstance(parsed_cats, list):
            raise SettingValidationError(
                "Geçersiz ayar değeri ('categories'): kategori nesneleri listesi bekleniyor."
            )
        for entry in parsed_cats:
            if not isinstance(entry, dict):
                raise SettingValidationError(
                    "Geçersiz ayar değeri ('categories'): her öğe {code, label, hotkey_prefix} nesnesi olmalı."
                )
            code = str(entry.get("code", "")).strip().upper()
            if not code or code == "ALL" or not CATEGORY_CODE_RE.fullmatch(code):
                raise SettingValidationError(
                    f"Geçersiz ayar değeri ('categories'): geçersiz kategori kodu '{entry.get('code', '')}'."
                )
        updated["categories"] = sanitize_categories(parsed_cats)
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
        val = str(value or "").strip().upper()
        if val != "ALL" and not CATEGORY_CODE_RE.fullmatch(val):
            raise SettingValidationError(
                f"Geçersiz ayar değeri ('last_category'): '{value}' (ALL veya alfanümerik kod bekleniyor)."
            )
        updated["last_category"] = val
    elif norm in ("enter_after_paste", "hide_on_blur", "start_minimized", "tray_icon", "auto_reload", "strip_emoji"):
        updated[norm] = _parse_bool(value)
    elif norm == "auto_reload_interval_ms":
        try:
            iv = int(value)
        except (TypeError, ValueError) as exc:
            raise SettingValidationError(f"Geçersiz ayar değeri ('auto_reload_interval_ms'): '{value}'.") from exc
        if not (100 <= iv <= 10000):
            raise SettingValidationError(
                f"Geçersiz ayar değeri ('auto_reload_interval_ms'): {iv} (100–10000 ms aralığında olmalı)."
            )
        updated["auto_reload_interval_ms"] = iv
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
        val = str(value or "").strip().lower()
        valid_langs = available_languages(config_dir)
        if val not in valid_langs:
            raise SettingValidationError(
                f"Geçersiz ayar değeri ('language'): '{value}' ({', '.join(valid_langs)})."
            )
        updated["language"] = val
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
        if not (560 <= w <= 2400 and 400 <= h <= 1600):
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
        sub = norm.split(".", 1)[1].strip()
        if not sub or "." in sub:
            raise SettingValidationError(f"Geçersiz ayar anahtarı: '{norm}'.")
        val = str(value or "").strip()
        hk = dict(updated.get("hotkeys") or DEFAULT_HOTKEYS)
        if not val:
            if sub in DEFAULT_HOTKEYS:
                hk[sub] = ""
            else:
                hk.pop(sub, None)
        else:
            try:
                hk[sub] = normalize_hotkey(val)
            except ValueError as exc:
                raise SettingValidationError(f"Geçersiz ayar değeri ('{norm}'): {exc}") from exc
        updated["hotkeys"] = hk
    else:
        raise SettingValidationError(f"Geçersiz ayar anahtarı: '{norm}'.")

    return _sanitize_settings(updated, config_dir=config_dir)


def load_settings(
    preferred_dir: str | Path | None = None,
    *,
    platform_name: str | None = None,
) -> tuple[dict[str, Any], Path, str | None]:
    """Loads qtp_settings.json, creating defaults if missing and safely migrating legacy v2.0 defaults."""
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
        migrated = False
        if isinstance(raw.get("hotkeys"), dict) and raw["hotkeys"] == LEGACY_DEFAULT_HOTKEYS:
            raw = copy.deepcopy(raw)
            raw["hotkeys"] = build_preset_hotkeys("recommended", tuple(LEGACY_DEFAULT_HOTKEYS.keys()))
            migrated = True
        clean = _sanitize_settings(raw, config_dir=config_dir)
        if migrated:
            save_settings(clean, settings_path)
            logger.info(
                "Eski çakışmalı varsayılan kısayollar (Win+A/Z/X/Q) yeni çakışmasız önerilen profile (Win+Alt+*) otomatik geçirildi."
            )
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
    """Sanitizes and atomically writes settings to disk."""
    path = Path(settings_path)
    clean = _sanitize_settings(settings, config_dir=path.parent)
    payload = json.dumps(clean, ensure_ascii=False, indent=2) + "\n"
    atomic_write_bytes(path, payload.encode("utf-8"))
    get_logger("settings").info("Ayarlar kaydedildi: %s", path)
    return path


def resolve_data_path(settings: dict[str, Any], base_dir: Path) -> Path:
    """Resolves data_path relative to base_dir."""
    raw = str(settings.get("data_path") or "./QuickTextPaste.ini").strip()
    p = Path(raw)
    if p.is_absolute():
        return p
    return (base_dir / p).resolve()
