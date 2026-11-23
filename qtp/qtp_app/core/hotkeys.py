"""Sistem geneli global kısayol kaydı ve zarif platform geri dönüşü (Windows / Linux / macOS)."""

from __future__ import annotations

import ctypes
import re
import sys
from typing import Any, Callable

from qtp_app.core.logging_setup import get_logger
from qtp_app.core.paster import is_posix_desktop, is_wayland_session

logger = get_logger("hotkeys")

HOTKEY_CATEGORY_ORDER = ("all", "A", "Z", "X", "Q")

_MOD_MAP_PYNPUT = {
    "ctrl": "<ctrl>",
    "l-ctrl": "<ctrl>",
    "control": "<ctrl>",
    "shift": "<shift>",
    "l-shift": "<shift>",
    "alt": "<alt>",
    "l-alt": "<alt>",
    "win": "<cmd>",
    "l-win": "<cmd>",
    "super": "<cmd>",
    "cmd": "<cmd>",
    "meta": "<cmd>",
}

_SPECIAL_KEY_PYNPUT = {
    "space": "<space>",
    "enter": "<enter>",
    "return": "<enter>",
    "tab": "<tab>",
    "esc": "<esc>",
    "escape": "<esc>",
}

_MOD_MAP_KEYBOARD = {
    "ctrl": "ctrl",
    "l-ctrl": "ctrl",
    "control": "ctrl",
    "shift": "shift",
    "l-shift": "shift",
    "alt": "alt",
    "l-alt": "alt",
    "win": "windows",
    "l-win": "windows",
    "super": "windows",
    "cmd": "windows",
    "meta": "windows",
}


def to_pynput_combo(combo: str) -> str:
    """'Win+A', 'Ctrl+Shift+Space' gibi kısayol dizelerini pynput biçimine çevirir."""
    tokens = [t.strip() for t in re.split(r"\+", combo or "") if t.strip()]
    if not tokens:
        raise ValueError("Boş kısayol dizesi.")
    mapped: list[str] = []
    for tok in tokens:
        low = tok.lower()
        if low in _MOD_MAP_PYNPUT:
            mapped.append(_MOD_MAP_PYNPUT[low])
        elif low in _SPECIAL_KEY_PYNPUT:
            mapped.append(_SPECIAL_KEY_PYNPUT[low])
        elif len(low) == 1:
            mapped.append(low)
        else:
            mapped.append(f"<{low}>")
    return "+".join(mapped)


def to_keyboard_lib_combo(combo: str) -> str:
    """'Win+A' gibi dizeleri Windows yedek 'keyboard' kütüphanesi biçimine çevirir."""
    tokens = [t.strip() for t in re.split(r"\+", combo or "") if t.strip()]
    mapped = [_MOD_MAP_KEYBOARD.get(t.lower(), t.lower()) for t in tokens]
    return "+".join(mapped)


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
    Wayland veya macOS izni yokluğunda başlangıcı asla bloklamaz; uyarı günlüğü basar.
    """

    def __init__(
        self,
        *,
        pynput_factory: Callable[[dict[str, Callable[[], None]]], Any] | None = None,
        keyboard_module: Any = None,
        platform_name: str | None = None,
    ):
        self._pynput_factory = pynput_factory
        self._keyboard_module = keyboard_module
        self._platform = platform_name or sys.platform
        self._pynput_listener: Any = None
        self._keyboard_handles: list[Any] = []
        self._registered: dict[str, str] = {}
        self._status: dict[str, bool] = {}

    @property
    def registered_hotkeys(self) -> dict[str, str]:
        return dict(self._registered)

    @property
    def status(self) -> dict[str, bool]:
        return dict(self._status)

    def unregister(self) -> None:
        """Tüm etkin global kısayolları serbest bırakır."""
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

        pynput_mapping: dict[str, Callable[[], None]] = {}
        combo_by_category: dict[str, str] = {}
        results: dict[str, bool] = {}

        for category, raw_combo in hotkeys.items():
            combo = str(raw_combo or "").strip()
            if not combo:
                results[category] = False
                continue
            try:
                py_combo = to_pynput_combo(combo)
            except ValueError as exc:
                logger.error("Geçersiz kısayol tanımı (%s=%s): %s", category, combo, exc)
                results[category] = False
                continue

            combo_by_category[category] = combo
            pynput_mapping[py_combo] = (lambda cat=category: on_trigger(cat))

        if not pynput_mapping:
            self._status = results
            return results

        pynput_ok = False
        try:
            self._pynput_listener = self._build_pynput_listener(pynput_mapping)
            pynput_ok = True
            for cat, combo in combo_by_category.items():
                self._registered[cat] = combo
                results[cat] = True
                logger.info("Global kısayol kaydedildi (pynput): %s -> %s", combo, cat)
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
                for cat, combo in combo_by_category.items():
                    kb_combo = to_keyboard_lib_combo(combo)
                    try:
                        handle = kb.add_hotkey(kb_combo, lambda c=cat: on_trigger(c))
                        self._keyboard_handles.append(handle)
                        self._registered[cat] = combo
                        results[cat] = True
                        logger.info("Global kısayol kaydedildi (keyboard fallback): %s -> %s", combo, cat)
                    except Exception as kb_exc:
                        results[cat] = False
                        logger.warning("Global kısayol kaydedilemedi: %s (%s)", cat, kb_exc)
            else:
                for cat in combo_by_category:
                    results[cat] = False
                    logger.warning("Global kısayol kaydedilemedi: %s (geri dönüş yok)", cat)
        elif not pynput_ok:
            for cat in combo_by_category:
                results[cat] = False

        self._status = results
        return results
