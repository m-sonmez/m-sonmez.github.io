"""Sistem geneli global kısayol kaydı, Win32 RegisterHotKey, ön ayar profilleri ve çakışma algılama."""

from __future__ import annotations

import ctypes
from pathlib import Path
import re
import sys
import threading
from typing import Any, Callable, Iterable

from qtp_app.core.i18n import t
from qtp_app.core.logging_setup import get_logger
from qtp_app.core.paster import is_posix_desktop, is_wayland_session

logger = get_logger("hotkeys")

HOTKEY_CATEGORY_ORDER = ("all",)
CANONICAL_MODIFIERS = ("Win", "Ctrl", "Alt", "Shift")
PRESET_ORDER = (
    "recommended",
    "win_ctrl",
    "ctrl_alt",
    "ctrl_shift_alt",
    "function_keys",
    "legacy_win",
)

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000
WM_QUIT = 0x0012
WM_HOTKEY = 0x0312
ERROR_HOTKEY_ALREADY_REGISTERED = 1409

HOTKEY_PRESET_ALIASES: dict[str, str] = {
    "triple_mod": "ctrl_shift_alt",
}

_PRESET_SPECS: dict[str, tuple[str, str]] = {
    "recommended": ("Win+Alt+Space", "Win+Alt"),
    "win_ctrl": ("Win+Ctrl+Space", "Win+Ctrl"),
    "ctrl_alt": ("Ctrl+Alt+Space", "Ctrl+Alt"),
    "ctrl_shift_alt": ("Ctrl+Alt+Shift+Space", "Ctrl+Alt+Shift"),
    "function_keys": ("Ctrl+Shift+F1", "Ctrl+Shift"),
    "legacy_win": ("Ctrl+Shift+Space", "Win"),
}


def build_preset_hotkeys(
    preset_name: str,
    slots: Iterable[str] | None = None,
) -> dict[str, str]:
    """Dynamically builds a preset hotkey mapping for 'all' plus any active category or custom slots."""
    norm = (preset_name or "").strip().lower()
    canon = HOTKEY_PRESET_ALIASES.get(norm, norm)
    if canon not in _PRESET_SPECS:
        raise ValueError(
            f"Geçersiz kısayol profili: '{preset_name}' (geçerli: {', '.join(PRESET_ORDER)})."
        )

    ordered_slots: list[str] = ["all"]
    seen_lower: set[str] = {"all"}
    if slots is not None:
        for raw_slot in slots:
            s = str(raw_slot or "").strip()
            if not s or "." in s:
                continue
            low = s.lower()
            if low in seen_lower:
                continue
            seen_lower.add(low)
            ordered_slots.append(s)

    all_combo, mod_prefix = _PRESET_SPECS[canon]
    result: dict[str, str] = {"all": all_combo}
    if canon == "function_keys":
        fn_idx = 2
        for slot in ordered_slots[1:]:
            if fn_idx <= 24:
                result[slot] = f"{mod_prefix}+F{fn_idx}"
                fn_idx += 1
        return result

    used_triggers: set[str] = {"Space"}
    fallback_pool = list("123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ") + [f"F{n}" for n in range(2, 13)]
    for slot in ordered_slots[1:]:
        up = slot.upper()
        trigger = ""
        if len(up) == 1 and (("A" <= up <= "Z") or ("0" <= up <= "9")) and up not in used_triggers:
            trigger = up
        elif up and (("A" <= up[0] <= "Z") or ("0" <= up[0] <= "9")) and up[0] not in used_triggers:
            trigger = up[0]
        else:
            for cand in fallback_pool:
                if cand not in used_triggers:
                    trigger = cand
                    break
        if trigger:
            used_triggers.add(trigger)
            result[slot] = f"{mod_prefix}+{trigger}"
    return result


HOTKEY_PRESETS: dict[str, dict[str, str]] = {
    pid: build_preset_hotkeys(pid, ("all",)) for pid in PRESET_ORDER
}


def get_preset_labels(
    lang: str = "en",
    config_dir: str | Path | None = None,
) -> dict[str, str]:
    """Returns localized labels for all built-in hotkey presets."""
    return {pid: t(f"preset.{pid}", lang, config_dir) for pid in PRESET_ORDER}


HOTKEY_PRESET_LABELS: dict[str, str] = get_preset_labels("en")

_MOD_ALIASES: dict[str, str] = {
    "win": "Win",
    "l-win": "Win",
    "r-win": "Win",
    "windows": "Win",
    "super": "Win",
    "meta": "Win",
    "cmd": "Win",
    "command": "Win",
    "ctrl": "Ctrl",
    "l-ctrl": "Ctrl",
    "r-ctrl": "Ctrl",
    "control": "Ctrl",
    "ctl": "Ctrl",
    "alt": "Alt",
    "l-alt": "Alt",
    "r-alt": "Alt",
    "opt": "Alt",
    "option": "Alt",
    "shift": "Shift",
    "l-shift": "Shift",
    "r-shift": "Shift",
}

_MOD_BITMASK: dict[str, int] = {
    "Win": MOD_WIN,
    "Ctrl": MOD_CONTROL,
    "Alt": MOD_ALT,
    "Shift": MOD_SHIFT,
}

_MOD_PYNPUT: dict[str, str] = {
    "Win": "<cmd>",
    "Ctrl": "<ctrl>",
    "Alt": "<alt>",
    "Shift": "<shift>",
}

_MOD_KEYBOARD: dict[str, str] = {
    "Win": "windows",
    "Ctrl": "ctrl",
    "Alt": "alt",
    "Shift": "shift",
}

_SPECIAL_KEY_SPECS: dict[str, tuple[str, int, str, str]] = {
    "space": ("Space", 0x20, "<space>", "space"),
    "spc": ("Space", 0x20, "<space>", "space"),
    "boşluk": ("Space", 0x20, "<space>", "space"),
    "tab": ("Tab", 0x09, "<tab>", "tab"),
    "enter": ("Enter", 0x0D, "<enter>", "enter"),
    "return": ("Enter", 0x0D, "<enter>", "enter"),
    "esc": ("Esc", 0x1B, "<esc>", "esc"),
    "escape": ("Esc", 0x1B, "<esc>", "esc"),
    "backspace": ("Backspace", 0x08, "<backspace>", "backspace"),
    "bksp": ("Backspace", 0x08, "<backspace>", "backspace"),
    "insert": ("Insert", 0x2D, "<insert>", "insert"),
    "ins": ("Insert", 0x2D, "<insert>", "insert"),
    "delete": ("Delete", 0x2E, "<delete>", "delete"),
    "del": ("Delete", 0x2E, "<delete>", "delete"),
    "home": ("Home", 0x24, "<home>", "home"),
    "end": ("End", 0x23, "<end>", "end"),
    "pageup": ("PageUp", 0x21, "<page_up>", "page up"),
    "pgup": ("PageUp", 0x21, "<page_up>", "page up"),
    "page_up": ("PageUp", 0x21, "<page_up>", "page up"),
    "pagedown": ("PageDown", 0x22, "<page_down>", "page down"),
    "pgdn": ("PageDown", 0x22, "<page_down>", "page down"),
    "pgdown": ("PageDown", 0x22, "<page_down>", "page down"),
    "page_down": ("PageDown", 0x22, "<page_down>", "page down"),
    "backtab": ("Tab", 0x09, "<tab>", "tab"),
    "up": ("Up", 0x26, "<up>", "up"),
    "down": ("Down", 0x28, "<down>", "down"),
    "left": ("Left", 0x25, "<left>", "left"),
    "right": ("Right", 0x27, "<right>", "right"),
    "-": ("-", 0xBD, "-", "-"),
    "minus": ("-", 0xBD, "-", "-"),
    "=": ("=", 0xBB, "=", "="),
    "equal": ("=", 0xBB, "=", "="),
    "equals": ("=", 0xBB, "=", "="),
    "[": ("[", 0xDB, "[", "["),
    "lbracket": ("[", 0xDB, "[", "["),
    "]": ("]", 0xDD, "]", "]"),
    "rbracket": ("]", 0xDD, "]", "]"),
    ";": (";", 0xBA, ";", ";"),
    "semicolon": (";", 0xBA, ";", ";"),
    "'": ("'", 0xDE, "'", "'"),
    "quote": ("'", 0xDE, "'", "'"),
    "apostrophe": ("'", 0xDE, "'", "'"),
    ",": (",", 0xBC, ",", ","),
    "comma": (",", 0xBC, ",", ","),
    ".": (".", 0xBE, ".", "."),
    "period": (".", 0xBE, ".", "."),
    "dot": (".", 0xBE, ".", "."),
    "/": ("/", 0xBF, "/", "/"),
    "slash": ("/", 0xBF, "/", "/"),
    "\\": ("\\", 0xDC, "\\", "\\"),
    "backslash": ("\\", 0xDC, "\\", "\\"),
    "`": ("`", 0xC0, "`", "`"),
    "grave": ("`", 0xC0, "`", "`"),
    "backtick": ("`", 0xC0, "`", "`"),
}

for _fn in range(1, 25):
    _SPECIAL_KEY_SPECS[f"f{_fn}"] = (f"F{_fn}", 0x70 + (_fn - 1), f"<f{_fn}>", f"f{_fn}")
for _np in range(0, 10):
    _np_vk = 0x60 + _np
    _np_name = f"Numpad{_np}"
    for _np_alias in (f"numpad{_np}", f"np{_np}", f"num{_np}"):
        _SPECIAL_KEY_SPECS[_np_alias] = (_np_name, _np_vk, f"<{_np_vk}>", f"num {_np}")

_CANON_TO_SPEC: dict[str, tuple[str, int, str, str]] = {
    v[0]: v for v in _SPECIAL_KEY_SPECS.values()
}

_WIN_RESERVED_SHORTCUTS: dict[str, str] = {
    "Win+A": "Windows Hızlı Ayarlar (Quick Settings) sistem kısayolu ile çakışır.",
    "Win+Z": "Windows 11 Ekran Düzeni (Snap Layouts) sistem kısayolu ile çakışır.",
    "Win+X": "Windows Hızlı Bağlantı Menüsü (Power User) ile çakışır.",
    "Win+Q": "Windows Arama sistem kısayolu ile çakışır.",
    "Win+S": "Windows Arama sistem kısayolu ile çakışır.",
    "Win+W": "Windows Araçlar (Widgets) sistem kısayolu ile çakışır.",
    "Win+D": "Masaüstünü Göster sistem kısayolu ile çakışır.",
    "Win+E": "Dosya Gezgini sistem kısayolu ile çakışır.",
    "Win+L": "Oturumu Kilitle sistem kısayolu ile çakışır (sistem tarafından ayrılmıştır).",
    "Win+R": "Çalıştır (Run) iletişim kutusu sistem kısayolu ile çakışır.",
    "Win+V": "Windows Pano Geçmişi sistem kısayolu ile çakışır.",
    "Win+C": "Windows Copilot / sohbet sistem kısayolu ile çakışır.",
    "Win+I": "Windows Ayarlar sistem kısayolu ile çakışır.",
    "Win+P": "Proje / Ekran Yansıtma sistem kısayolu ile çakışır.",
    "Win+Tab": "Görev Görünümü (Task View) sistem kısayolu ile çakışır.",
    "Win+Space": "Klavye düzeni değiştirme sistem kısayolu ile çakışır.",
    "Win+Shift+S": "Ekran Alıntısı Aracı sistem kısayolu ile çakışır.",
    "Win+Alt+D": "Görev çubuğu Tarih/Saat sistem kısayolu ile çakışır.",
    "Win+Alt+G": "Xbox Game Bar kayıt sistem kısayolu ile çakışır.",
    "Win+Alt+R": "Xbox Game Bar video kayıt sistem kısayolu ile çakışır.",
    "Win+Alt+B": "Windows HDR geçiş sistem kısayolu ile çakışır.",
    "Win+Alt+K": "Mikrofon sessize alma sistem kısayolu ile çakışır.",
    "Win+Ctrl+Space": "Windows klavye düzeni/giriş dili değiştirme sistem kısayolu ile çakışır.",
    "Win+Ctrl+Q": "Windows Hızlı Yardım (Quick Assist) sistem kısayolu ile çakışır.",
    "Win+Ctrl+D": "Windows yeni sanal masaüstü oluşturma sistem kısayolu ile çakışır.",
    "Win+Ctrl+Left": "Windows önceki sanal masaüstüne geçiş kısayolu ile çakışır.",
    "Win+Ctrl+Right": "Windows sonraki sanal masaüstüne geçiş kısayolu ile çakışır.",
    "Win+Ctrl+F4": "Windows etkin sanal masaüstünü kapatma kısayolu ile çakışır.",
    "Alt+F4": "Aktif pencereyi kapatma sistem kısayolu ile çakışır.",
    "Alt+Tab": "Pencere değiştirme sistem kısayolu ile çakışır.",
    "Alt+Space": "Pencere sistem menüsü kısayolu ile çakışır.",
    "Ctrl+Shift+Esc": "Görev Yöneticisi sistem kısayolu ile çakışır.",
    "Ctrl+Alt+Delete": "Windows güvenlik ekranı sistem kısayolu ile çakışır.",
}
for _digit in range(1, 10):
    _WIN_RESERVED_SHORTCUTS[f"Win+{_digit}"] = (
        f"Görev çubuğu {_digit}. uygulama başlatma sistem kısayolu ile çakışır."
    )

_TRQ_ALTGR_WARNINGS: dict[str, str] = {
    "Ctrl+Alt+Q": "Türkçe-Q klavyede AltGr+Q (@ işareti) yazımını engelleyebilir.",
    "Ctrl+Alt+A": "Türkçe-Q klavyede AltGr+A (æ karakteri) yazımını engelleyebilir.",
    "Ctrl+Alt+E": "Türkçe-Q klavyede AltGr+E (€ işareti) yazımını engelleyebilir.",
    "Ctrl+Alt+S": "Türkçe-Q klavyede AltGr+S (ß karakteri) yazımını engelleyebilir.",
    "Ctrl+Alt+1": "Türkçe-Q klavyede AltGr+1 (>) yazımını engelleyebilir.",
    "Ctrl+Alt+2": "Türkçe-Q klavyede AltGr+2 (£) yazımını engelleyebilir.",
    "Ctrl+Alt+3": "Türkçe-Q klavyede AltGr+3 (#) yazımını engelleyebilir.",
    "Ctrl+Alt+4": "Türkçe-Q klavyede AltGr+4 ($) yazımını engelleyebilir.",
    "Ctrl+Alt+5": "Türkçe-Q klavyede AltGr+5 (½) yazımını engelleyebilir.",
    "Ctrl+Alt+6": "Türkçe-Q klavyede AltGr+6 yazımını engelleyebilir.",
    "Ctrl+Alt+7": "Türkçe-Q klavyede AltGr+7 ({) yazımını engelleyebilir.",
    "Ctrl+Alt+8": "Türkçe-Q klavyede AltGr+8 ([) yazımını engelleyebilir.",
    "Ctrl+Alt+9": "Türkçe-Q klavyede AltGr+9 (]) yazımını engelleyebilir.",
}

_MACOS_RESERVED_SHORTCUTS: dict[str, str] = {
    "Win+Q": "macOS aktif uygulamadan çıkış (Cmd+Q) sistem kısayolu ile çakışır.",
    "Win+Shift+Q": "macOS oturum kapatma (Cmd+Shift+Q) sistem kısayolu ile çakışır.",
    "Win+Space": "macOS Spotlight arama (Cmd+Space) sistem kısayolu ile çakışır.",
}

_LINUX_DESKTOP_RESERVED_SHORTCUTS: dict[str, str] = {
    "Win+Q": "KDE Plasma Etkinlikler (Activities) sistem kısayolu ile çakışır.",
    "Win+W": "KDE Plasma Genel Bakış (Overview) sistem kısayolu ile çakışır.",
    "Win+E": "Masaüstü Dosya Yöneticisi (Dolphin/Files) kısayolu ile çakışır.",
    "Win+D": "Masaüstünü Göster sistem kısayolu ile çakışır.",
    "Win+L": "Ekranı Kilitle sistem kısayolu ile çakışır.",
    "Win+V": "Masaüstü Pano / Bildirimler (Klipper/GNOME) kısayolu ile çakışır.",
    "Win+A": "GNOME Uygulama Izgarası / Masaüstü kısayolu ile çakışır.",
    "Win+S": "GNOME Genel Bakış / Arama kısayolu ile çakışır.",
    "Win+T": "KDE Plasma 6 Döşeme Düzenleyici (Tile Editor) kısayolu ile çakışır.",
    "Win+G": "KDE Plasma Masaüstü Izgarası kısayolu ile çakışır.",
    "Win+Space": "Klavye düzeni / uygulama başlatıcı sistem kısayolu ile çakışır.",
    "Win+Tab": "Pencere / Etkinlik geçiş sistem kısayolu ile çakışır.",
    "Alt+Space": "Pencere sistem menüsü kısayolu ile çakışır.",
    "Alt+F2": "Masaüstü hızlı komut çalıştırıcı sistem kısayolu ile çakışır.",
    "Alt+F4": "Aktif pencereyi kapatma sistem kısayolu ile çakışır.",
    "Alt+Tab": "Pencere değiştirme sistem kısayolu ile çakışır.",
    "Ctrl+Alt+Delete": "Oturum / sistem güvenlik ekranı kısayolu ile çakışır.",
    "Ctrl+Alt+L": "Ekranı Kilitle sistem kısayolu ile çakışır.",
    "Ctrl+Alt+T": "Uçbirim (Terminal) başlatma masaüstü kısayolu ile çakışır.",
    "Ctrl+Esc": "Uygulama menüsü / sistem etkinlikleri kısayolu ile çakışır.",
}
for _linux_digit in range(1, 10):
    _LINUX_DESKTOP_RESERVED_SHORTCUTS[f"Win+{_linux_digit}"] = (
        f"Görev çubuğu / masaüstü {_linux_digit}. uygulama başlatma kısayolu ile çakışır."
    )


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", ctypes.c_void_p),
        ("message", ctypes.c_uint),
        ("wParam", ctypes.c_size_t),
        ("lParam", ctypes.c_ssize_t),
        ("time", ctypes.c_uint32),
        ("pt", POINT),
    ]


def resolve_preset_name(name: str) -> str:
    """Profil adını çözer (takma adları eşler) veya geçersizse ValueError fırlatır."""
    norm = (name or "").strip().lower()
    canonical = HOTKEY_PRESET_ALIASES.get(norm, norm)
    if canonical not in HOTKEY_PRESETS:
        raise ValueError(
            f"Geçersiz kısayol profili: '{name}' (geçerli: {', '.join(HOTKEY_PRESETS)})."
        )
    return canonical


def parse_modifiers(modifiers: str) -> tuple[str, ...]:
    """Değiştirici önekini ('Win+Ctrl', 'Ctrl+Shift+Alt' vb.) doğrulayıp kanonsal sıraya koyar."""
    raw = (modifiers or "").strip()
    if not raw:
        raise ValueError("Geçersiz değiştirici bileşimi: boş değer.")
    parts = [p.strip() for p in raw.split("+")]
    if any(not p for p in parts):
        raise ValueError(f"Geçersiz değiştirici bileşimi ('{modifiers}'): boş '+' segmenti.")
    seen: set[str] = set()
    for part in parts:
        canon = _MOD_ALIASES.get(part.lower())
        if canon is None:
            raise ValueError(
                f"Geçersiz değiştirici bileşimi ('{modifiers}'): Win, Ctrl, Alt veya Shift kullanın."
            )
        seen.add(canon)
    return tuple(m for m in CANONICAL_MODIFIERS if m in seen)


def _resolve_trigger_key(token: str) -> tuple[str, int, str, str] | None:
    low = token.lower()
    if low in _SPECIAL_KEY_SPECS:
        return _SPECIAL_KEY_SPECS[low]
    if len(token) == 1 and "a" <= low <= "z":
        upper = token.upper()
        return (upper, ord(upper), low, low)
    if len(token) == 1 and "0" <= token <= "9":
        return (token, ord(token), token, token)
    return None


def parse_hotkey(combo: str) -> tuple[tuple[str, ...], str]:
    """Kısayol dizesini doğrular ve ((Win?, Ctrl?, Alt?, Shift?), Anahtar) demetine ayrıştırır."""
    raw = (combo or "").strip()
    if not raw:
        raise ValueError("Boş kısayol dizesi kullanılamaz.")

    parts = [p.strip() for p in raw.split("+")]
    if any(not p for p in parts):
        raise ValueError(f"Geçersiz kısayol tanımı ('{combo}'): eksik tuş bileşeni.")

    mod_set: set[str] = set()
    trigger_keys: list[str] = []
    for tok in parts:
        mod = _MOD_ALIASES.get(tok.lower())
        if mod is not None:
            mod_set.add(mod)
            continue
        spec = _resolve_trigger_key(tok)
        if spec is None:
            raise ValueError(f"Geçersiz kısayol bileşeni ('{combo}'): bilinmeyen tuş '{tok}'.")
        trigger_keys.append(spec[0])

    if not trigger_keys:
        raise ValueError(
            f"Geçersiz kısayol tanımı ('{combo}'): değiştirici tuşlar tek başına kullanılamaz; A–Z, F1–F12 veya Space gibi bir tetik tuşu ekleyin."
        )
    if len(trigger_keys) > 1:
        raise ValueError(
            f"Geçersiz kısayol tanımı ('{combo}'): birden fazla tetik tuşu kullanılamaz."
        )
    if not mod_set:
        raise ValueError(
            f"Geçersiz kısayol tanımı ('{combo}'): en az bir değiştirici tuş (Ctrl, Alt, Shift veya Win) gereklidir."
        )

    ordered_mods = tuple(m for m in CANONICAL_MODIFIERS if m in mod_set)
    return ordered_mods, trigger_keys[0]


def normalize_hotkey(combo: str) -> str:
    """Herhangi sıradaki kısayolu kanonsal ('Win+Ctrl+Alt+Shift+Anahtar') biçime çevirir."""
    mods, key = parse_hotkey(combo)
    return "+".join([*mods, key])


def apply_modifier_combo(hotkeys_map: dict[str, str], modifiers: str) -> dict[str, str]:
    """Tüm etkin kısayol yuvalarının değiştiricilerini toplu olarak günceller (tetik tuşlarını korur)."""
    mods = parse_modifiers(modifiers)
    prefix = "+".join(mods)
    updated: dict[str, str] = {}
    for slot, raw_combo in hotkeys_map.items():
        text = str(raw_combo or "").strip()
        if not text:
            updated[slot] = ""
            continue
        try:
            _old_mods, key = parse_hotkey(text)
        except ValueError:
            key = "Space" if slot == "all" else str(slot).upper()[:1] or "Space"
        updated[slot] = f"{prefix}+{key}"
    return updated


def to_win32_hotkey(combo: str) -> tuple[int, int]:
    """Kanonsal kısayol dizesini Win32 RegisterHotKey (MOD_* maskesi | MOD_NOREPEAT, VK_*) çiftine çevirir."""
    mods, key = parse_hotkey(combo)
    mask = MOD_NOREPEAT
    for m in mods:
        mask |= _MOD_BITMASK[m]
    if key in _CANON_TO_SPEC:
        vk = _CANON_TO_SPEC[key][1]
    else:
        vk = ord(key)
    return mask, vk


def to_pynput_combo(combo: str) -> str:
    """Kısayol dizesini pynput GlobalHotKeys biçimine çevirir."""
    mods, key = parse_hotkey(combo)
    tokens = [_MOD_PYNPUT[m] for m in mods]
    if key in _CANON_TO_SPEC:
        tokens.append(_CANON_TO_SPEC[key][2])
    else:
        tokens.append(key.lower())
    return "+".join(tokens)


def to_keyboard_lib_combo(combo: str) -> str:
    """Kısayol dizesini Windows yedek 'keyboard' kütüphanesi biçimine çevirir."""
    mods, key = parse_hotkey(combo)
    tokens = [_MOD_KEYBOARD[m] for m in mods]
    if key in _CANON_TO_SPEC:
        tokens.append(_CANON_TO_SPEC[key][3])
    else:
        tokens.append(key.lower())
    return "+".join(tokens)


def read_kde_global_shortcuts(config_path: Path | None = None) -> dict[str, list[str]]:
    """KDE Plasma ~/.config/kglobalshortcutsrc dosyasından etkin global kısayolları okur."""
    path = Path(config_path) if config_path is not None else (Path.home() / ".config" / "kglobalshortcutsrc")
    try:
        if not path.is_file():
            return {}
        raw_text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}

    bindings: dict[str, list[str]] = {}
    current_section = ""
    skip_section = False

    for raw_line in raw_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            if "[$" in line:
                skip_section = True
                current_section = ""
                continue
            skip_section = False
            if line.startswith("[services][") and line.endswith("]"):
                current_section = line[len("[services][") : -1].strip()
            else:
                current_section = line[1:-1].strip()
            continue
        if skip_section or line.startswith(("#", ";")) or "=" not in line:
            continue

        action_id, rhs = line.split("=", 1)
        action_id = action_id.strip()
        if not action_id or action_id == "_k_friendly_name" or action_id.startswith("$"):
            continue

        parts = rhs.split(",", 2)
        active_field = parts[0].strip()
        if not active_field or active_field.lower() == "none":
            continue
        friendly = parts[2].strip() if len(parts) >= 3 and parts[2].strip() else action_id
        msg = (
            f"KDE Plasma sistem kısayolu ile çakışır: {friendly} ({current_section})."
            if current_section
            else f"KDE Plasma sistem kısayolu ile çakışır: {friendly}."
        )

        for token in re.split(r"\\t|\t", active_field):
            cand = token.strip()
            if not cand or cand.lower() == "none":
                continue
            try:
                norm = normalize_hotkey(cand)
            except ValueError:
                continue
            bucket = bindings.setdefault(norm, [])
            if msg not in bucket:
                bucket.append(msg)

    return bindings


def detect_hotkey_conflicts(
    hotkeys_map: dict[str, str],
    platform_name: str | None = None,
    *,
    kde_config_path: Path | None = None,
    include_host_config: bool | None = None,
    language: str = "en",
) -> dict[str, list[str]]:
    """
    Kısayol haritasındaki çift atamaları, OS sistem kısayollarını, AltGr düzen uyarılarını,
    KDE Plasma global kısayollarını ve Linux/BSD masaüstü geçişlerini denetleyip slot→uyarı döndürür.
    """
    plat = platform_name or sys.platform
    lang_norm = str(language or "en").strip().lower()
    conflicts: dict[str, list[str]] = {}
    normalized_by_slot: dict[str, str] = {}
    slots_by_combo: dict[str, list[str]] = {}

    def _add_conflict(slot_key: str, text_msg: str) -> None:
        bucket = conflicts.setdefault(slot_key, [])
        if text_msg not in bucket:
            bucket.append(text_msg)

    for slot, raw in hotkeys_map.items():
        text = str(raw or "").strip()
        if not text:
            continue
        try:
            norm = normalize_hotkey(text)
        except ValueError as exc:
            _add_conflict(slot, str(exc))
            continue
        normalized_by_slot[slot] = norm
        slots_by_combo.setdefault(norm, []).append(slot)

    for combo_norm, owner_slots in slots_by_combo.items():
        if len(owner_slots) > 1:
            for s in owner_slots:
                others = [o for o in owner_slots if o != s]
                _add_conflict(
                    s,
                    f"Çift atama: '{combo_norm}' başka bir kategoride de kullanılıyor ({', '.join(others)}).",
                )

    kde_bindings: dict[str, list[str]] = {}
    if is_posix_desktop(plat):
        should_read_kde = (kde_config_path is not None) or (
            include_host_config if include_host_config is not None else (platform_name is None)
        )
        if should_read_kde:
            kde_bindings = read_kde_global_shortcuts(kde_config_path)

    for slot, norm in normalized_by_slot.items():
        mods, key = parse_hotkey(norm)
        if plat == "win32":
            if norm in _WIN_RESERVED_SHORTCUTS:
                _add_conflict(slot, _WIN_RESERVED_SHORTCUTS[norm])
            if mods == ("Ctrl", "Alt") and norm in _TRQ_ALTGR_WARNINGS:
                if lang_norm.startswith("tr"):
                    _add_conflict(slot, _TRQ_ALTGR_WARNINGS[norm])
                else:
                    _add_conflict(slot, t("conflict.intl_altgr", "en", combo=norm))
        elif plat == "darwin":
            if norm in _MACOS_RESERVED_SHORTCUTS:
                _add_conflict(slot, _MACOS_RESERVED_SHORTCUTS[norm])
        elif is_posix_desktop(plat):
            if mods == ("Ctrl", "Alt") and re.fullmatch(r"F([1-9]|1[0-2])", key):
                _add_conflict(
                    slot,
                    f"Linux/BSD TTY sanal konsol geçiş kısayolu ({norm}) ile çakışır.",
                )
            if norm in _LINUX_DESKTOP_RESERVED_SHORTCUTS:
                _add_conflict(slot, _LINUX_DESKTOP_RESERVED_SHORTCUTS[norm])
            if norm in kde_bindings:
                for kde_msg in kde_bindings[norm]:
                    _add_conflict(slot, kde_msg)

    return conflicts


def _configure_win32_prototypes(user32: Any, kernel32: Any) -> None:
    user32.RegisterHotKey.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_uint, ctypes.c_uint]
    user32.RegisterHotKey.restype = ctypes.c_int
    user32.UnregisterHotKey.argtypes = [ctypes.c_void_p, ctypes.c_int]
    user32.UnregisterHotKey.restype = ctypes.c_int
    user32.GetMessageW.argtypes = [ctypes.POINTER(MSG), ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint]
    user32.GetMessageW.restype = ctypes.c_int
    user32.PeekMessageW.argtypes = [ctypes.POINTER(MSG), ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint, ctypes.c_uint]
    user32.PeekMessageW.restype = ctypes.c_int
    user32.PostThreadMessageW.argtypes = [ctypes.c_uint32, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t]
    user32.PostThreadMessageW.restype = ctypes.c_int
    kernel32.GetCurrentThreadId.argtypes = []
    kernel32.GetCurrentThreadId.restype = ctypes.c_uint32
    kernel32.GetLastError.argtypes = []
    kernel32.GetLastError.restype = ctypes.c_uint32


def check_macos_accessibility(*, prompt: bool = False) -> bool:
    """
    macOS üzerinde Erişilebilirlik iznini bloklamadan denetler.
    İzin yoksa başlangıcı durdurmaz, SSS.md ile uyumlu uyarı günlüğü yazar.
    """
    if sys.platform != "darwin":
        return True
    try:
        app_services = ctypes.CDLL(
            "/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices"
        )
        if not prompt:
            app_services.AXIsProcessTrusted.argtypes = []
            app_services.AXIsProcessTrusted.restype = ctypes.c_bool
            trusted = bool(app_services.AXIsProcessTrusted())
        else:
            cf = ctypes.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
            cf.CFStringCreateWithCString.restype = ctypes.c_void_p
            cf.CFStringCreateWithCString.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint32]
            cf.CFDictionaryCreate.restype = ctypes.c_void_p
            cf.CFDictionaryCreate.argtypes = [
                ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_void_p),
                ctypes.POINTER(ctypes.c_void_p),
                ctypes.c_long,
                ctypes.c_void_p,
                ctypes.c_void_p,
            ]
            cf.CFRelease.argtypes = [ctypes.c_void_p]
            cf.CFRelease.restype = None
            k_true = ctypes.c_void_p.in_dll(cf, "kCFBooleanTrue")
            k_key = cf.CFStringCreateWithCString(None, b"AXTrustedCheckOptionPrompt", 0x08000100)
            keys = (ctypes.c_void_p * 1)(k_key)
            vals = (ctypes.c_void_p * 1)(k_true)
            opts = cf.CFDictionaryCreate(None, keys, vals, 1, None, None)
            app_services.AXIsProcessTrustedWithOptions.argtypes = [ctypes.c_void_p]
            app_services.AXIsProcessTrustedWithOptions.restype = ctypes.c_bool
            trusted = bool(app_services.AXIsProcessTrustedWithOptions(opts))
            if opts:
                cf.CFRelease(opts)
            if k_key:
                cf.CFRelease(k_key)

        if not trusted:
            logger.warning(
                "macOS Erişilebilirlik izni verilmemiş! Sistem Ayarları -> Gizlilik ve Güvenlik -> Erişilebilirlik altından QTP'ye izin verin."
            )
        return trusted
    except Exception as exc:
        logger.warning("macOS Erişilebilirlik denetimi başarısız: %s", exc)
        return False


class HotkeyManager:
    """
    Global kısayol yaşam döngüsü yöneticisi.
    Windows'ta birincil olarak yerel Win32 RegisterHotKey (tuş tüketimli ve 0 bağımlılık),
    Linux/macOS/BSD üzerinde pynput.GlobalHotKeys kullanır ve çakışmaları güvenle raporlar.
    """

    def __init__(
        self,
        *,
        pynput_factory: Callable[[dict[str, Callable[[], None]]], Any] | None = None,
        keyboard_module: Any = None,
        platform_name: str | None = None,
        win32_user32: Any = None,
        win32_kernel32: Any = None,
        use_win32_native: bool | None = None,
    ):
        self._pynput_factory = pynput_factory
        self._keyboard_module = keyboard_module
        self._platform = platform_name or sys.platform
        self._win32_user32_override = win32_user32
        self._win32_kernel32_override = win32_kernel32
        self._use_win32_native = use_win32_native
        self._pynput_listener: Any = None
        self._keyboard_handles: list[Any] = []
        self._win32_thread: threading.Thread | None = None
        self._win32_thread_id: int | None = None
        self._win32_user32: Any = None
        self._registered: dict[str, str] = {}
        self._status: dict[str, bool] = {}
        self._conflicts: dict[str, str] = {}

    @property
    def registered_hotkeys(self) -> dict[str, str]:
        return dict(self._registered)

    @property
    def status(self) -> dict[str, bool]:
        return dict(self._status)

    @property
    def conflicts(self) -> dict[str, str]:
        return dict(self._conflicts)

    def _should_use_win32_native(self) -> bool:
        if self._use_win32_native is not None:
            return bool(self._use_win32_native)
        if self._win32_user32_override is not None:
            return True
        if self._platform != "win32":
            return False
        if self._pynput_factory is not None or self._keyboard_module is not None:
            return False
        return True

    def _resolve_win32_apis(self) -> tuple[Any, Any]:
        if self._win32_user32_override is not None and self._win32_kernel32_override is not None:
            return self._win32_user32_override, self._win32_kernel32_override
        windll = getattr(ctypes, "windll", None)
        if windll is None:
            return None, None
        u32 = self._win32_user32_override or windll.user32
        k32 = self._win32_kernel32_override or windll.kernel32
        _configure_win32_prototypes(u32, k32)
        return u32, k32

    def unregister(self) -> None:
        """Tüm etkin global kısayolları ve Win32 mesaj döngüsünü serbest bırakır."""
        if self._win32_thread is not None:
            if self._win32_user32 is not None and self._win32_thread_id:
                try:
                    self._win32_user32.PostThreadMessageW(int(self._win32_thread_id), WM_QUIT, 0, 0)
                except Exception as exc:
                    logger.debug("Win32 WM_QUIT gönderilirken uyarı: %s", exc)
            if self._win32_thread is not threading.current_thread():
                self._win32_thread.join(timeout=2.0)
            self._win32_thread = None
            self._win32_thread_id = None
            self._win32_user32 = None

        if self._pynput_listener is not None:
            try:
                self._pynput_listener.stop()
            except Exception as exc:
                logger.debug("pynput dinleyicisi durdurulurken uyarı: %s", exc)
            self._pynput_listener = None

        if self._keyboard_handles:
            kb = self._resolve_keyboard_module()
            for handle in self._keyboard_handles:
                try:
                    if kb is not None:
                        kb.remove_hotkey(handle)
                except Exception as exc:
                    logger.debug("keyboard kısayolu kaldırılırken uyarı: %s", exc)
            self._keyboard_handles.clear()

        self._registered.clear()
        self._status.clear()
        self._conflicts.clear()

    def _resolve_keyboard_module(self) -> Any:
        if self._keyboard_module is not None:
            return self._keyboard_module
        try:
            import keyboard

            return keyboard
        except ImportError:
            return None
        except Exception:
            return None

    def _build_pynput_listener(self, mapping: dict[str, Callable[[], None]]) -> Any:
        if self._pynput_factory is not None:
            return self._pynput_factory(mapping)
        from pynput.keyboard import GlobalHotKeys

        listener = GlobalHotKeys(mapping)
        listener.start()
        return listener

    def _register_win32_native(
        self,
        specs: list[tuple[int, str, str, int, int]],
        on_trigger: Callable[[str], None],
        results: dict[str, bool],
    ) -> bool:
        try:
            u32, k32 = self._resolve_win32_apis()
        except Exception as exc:
            logger.debug("Win32 RegisterHotKey API başlatılamadı: %s", exc)
            return False
        if u32 is None or k32 is None:
            return False

        ready_event = threading.Event()
        id_to_cat: dict[int, tuple[str, str]] = {}

        def _win32_loop() -> None:
            self._win32_thread_id = int(k32.GetCurrentThreadId())
            self._win32_user32 = u32
            init_msg = MSG()
            u32.PeekMessageW(ctypes.byref(init_msg), None, 0, 0, 0)

            for hk_id, cat, norm_combo, mod_mask, vk in specs:
                ok = bool(u32.RegisterHotKey(None, hk_id, mod_mask, vk))
                if ok:
                    id_to_cat[hk_id] = (cat, norm_combo)
                    self._registered[cat] = norm_combo
                    results[cat] = True
                    logger.info(
                        "Global kısayol kaydedildi (Win32 RegisterHotKey): %s -> %s",
                        norm_combo,
                        cat,
                    )
                else:
                    err_code = int(k32.GetLastError())
                    if err_code == ERROR_HOTKEY_ALREADY_REGISTERED:
                        cmsg = (
                            f"Global kısayol kaydedilemedi: {cat} -> '{norm_combo}' başka bir uygulama veya Windows sistem kısayolu tarafından zaten kullanılıyor (ERROR_HOTKEY_ALREADY_REGISTERED / 1409)."
                        )
                    else:
                        cmsg = (
                            f"Global kısayol kaydedilemedi: {cat} -> '{norm_combo}' (Win32 hata kodu={err_code})."
                        )
                    self._conflicts[cat] = cmsg
                    results[cat] = False
                    logger.warning("%s", cmsg)

            ready_event.set()
            if not id_to_cat:
                return

            loop_msg = MSG()
            try:
                while int(u32.GetMessageW(ctypes.byref(loop_msg), None, 0, 0)) > 0:
                    if int(loop_msg.message) == WM_HOTKEY:
                        entry = id_to_cat.get(int(loop_msg.wParam))
                        if entry is not None:
                            try:
                                on_trigger(entry[0])
                            except Exception as cb_exc:
                                logger.debug("Kısayol tetikleme hatası (%s): %s", entry[0], cb_exc)
            finally:
                for hk_id in list(id_to_cat):
                    try:
                        u32.UnregisterHotKey(None, hk_id)
                    except Exception:
                        pass

        self._win32_thread = threading.Thread(
            target=_win32_loop,
            daemon=True,
            name="qtp-win32-hotkeys",
        )
        self._win32_thread.start()
        ready_event.wait(timeout=3.0)
        if not id_to_cat:
            if self._win32_thread.is_alive():
                self._win32_thread.join(timeout=1.0)
            self._win32_thread = None
            self._win32_thread_id = None
            self._win32_user32 = None
        return True

    def register(
        self,
        hotkeys: dict[str, str],
        on_trigger: Callable[[str], None],
        *,
        request_macos_permission: bool = False,
    ) -> dict[str, bool]:
        """Verilen kategori→kısayol haritasını global olarak kaydeder."""
        self.unregister()

        if self._platform == "darwin":
            check_macos_accessibility(prompt=request_macos_permission)

        results: dict[str, bool] = {}
        valid_combos: dict[str, str] = {}
        for category, raw_combo in hotkeys.items():
            combo = str(raw_combo or "").strip()
            if not combo:
                results[category] = False
                continue
            try:
                valid_combos[category] = normalize_hotkey(combo)
            except ValueError as exc:
                msg = f"Geçersiz kısayol tanımı ({category}={combo}): {exc}"
                logger.error("%s", msg)
                self._conflicts[category] = msg
                results[category] = False

        if not valid_combos:
            self._status = results
            return results

        if self._should_use_win32_native():
            win32_specs: list[tuple[int, str, str, int, int]] = []
            for idx, (cat, norm_combo) in enumerate(valid_combos.items(), start=1):
                mod_mask, vk = to_win32_hotkey(norm_combo)
                win32_specs.append((idx, cat, norm_combo, mod_mask, vk))
            if self._register_win32_native(win32_specs, on_trigger, results):
                self._status = results
                logger.debug(
                    "Global kısayol kaydı tamamlandı: %d etkin, %d uyarı.",
                    sum(1 for ok in results.values() if ok),
                    len(self._conflicts),
                )
                return results

        pynput_mapping: dict[str, Callable[[], None]] = {}
        for cat, norm_combo in valid_combos.items():
            py_combo = to_pynput_combo(norm_combo)
            pynput_mapping[py_combo] = (lambda c=cat: on_trigger(c))

        pynput_ok = False
        try:
            self._pynput_listener = self._build_pynput_listener(pynput_mapping)
            pynput_ok = True
            for cat, norm_combo in valid_combos.items():
                self._registered[cat] = norm_combo
                results[cat] = True
                logger.info("Global kısayol kaydedildi (pynput): %s -> %s", norm_combo, cat)
        except Exception as exc:
            if is_posix_desktop(self._platform) and is_wayland_session(self._platform):
                logger.warning(
                    "Wayland oturumunda global kısayollar kısıtlıdır (%s); uygulama tepsi/TUI/CLI/Web ile kullanılabilir.",
                    exc,
                )
            else:
                logger.warning(
                    "pynput global kısayol kaydı başarısız oldu (%s); alternatif yöntem deneniyor.",
                    exc,
                )

        if not pynput_ok and self._platform == "win32":
            kb = self._resolve_keyboard_module()
            if kb is not None:
                for cat, norm_combo in valid_combos.items():
                    kb_combo = to_keyboard_lib_combo(norm_combo)
                    try:
                        handle = kb.add_hotkey(kb_combo, lambda c=cat: on_trigger(c))
                        self._keyboard_handles.append(handle)
                        self._registered[cat] = norm_combo
                        results[cat] = True
                        logger.info("Global kısayol kaydedildi (keyboard fallback): %s -> %s", norm_combo, cat)
                    except Exception as kb_exc:
                        results[cat] = False
                        cmsg = f"Global kısayol kaydedilemedi: {cat} ({kb_exc})"
                        self._conflicts[cat] = cmsg
                        logger.warning("%s", cmsg)
            else:
                for cat in valid_combos:
                    results[cat] = False
                    cmsg = f"Global kısayol kaydedilemedi: {cat} (geri dönüş yok)"
                    self._conflicts[cat] = cmsg
                    logger.warning("%s", cmsg)
        elif not pynput_ok:
            for cat in valid_combos:
                results[cat] = False
                self._conflicts.setdefault(cat, f"Global kısayol kaydedilemedi: {cat}")

        self._status = results
        logger.debug(
            "Global kısayol kaydı tamamlandı: %d etkin, %d uyarı.",
            sum(1 for ok in results.values() if ok),
            len(self._conflicts),
        )
        return results
