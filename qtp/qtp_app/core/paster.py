"""Pano kopyalama, önceki pencere odağını geri yükleme ve otomatik yapıştırma motoru."""

from __future__ import annotations

import ctypes
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Any, Callable

from qtp_app.core.logging_setup import get_logger

logger = get_logger("paster")


@dataclass
class PasteResult:
    """Yapıştırma işleminin ayrıntılı sonucu."""

    ok: bool
    copied: bool
    pasted: bool
    enter_sent: bool
    method: str
    warning: str | None = None


def is_wayland_session() -> bool:
    """Linux üzerinde Wayland oturumu çalışıp çalışmadığını algılar."""
    if sys.platform != "linux":
        return False
    return bool(os.environ.get("WAYLAND_DISPLAY")) or (
        os.environ.get("XDG_SESSION_TYPE", "").strip().lower() == "wayland"
    )


def copy_to_clipboard(text: str, *, qt_clipboard: Any = None) -> bool:
    """Metni panoya kopyalar: önce pyperclip, olmazsa Qt panosunu dener."""
    try:
        import pyperclip

        pyperclip.copy(text)
        return True
    except Exception as exc:
        logger.debug("pyperclip kopyalama başarısız, Qt panosu deneniyor: %s", exc)

    try:
        if qt_clipboard is not None:
            qt_clipboard.setText(text)
            return True
        from PyQt6.QtGui import QGuiApplication

        app = QGuiApplication.instance()
        if app is not None and app.clipboard() is not None:
            app.clipboard().setText(text)
            return True
    except Exception as exc:
        logger.error("Pano kopyalama hatası: %s", exc)
    return False


def capture_previous_app(*, platform_name: str | None = None) -> Any:
    """Overlay açılmadan hemen önce odakta bulunan hedef uygulamayı yakalar."""
    plat = platform_name or sys.platform
    try:
        if plat == "win32":
            user32 = ctypes.windll.user32
            hwnd = int(user32.GetForegroundWindow())
            return hwnd if hwnd else None
        if plat == "darwin":
            try:
                from AppKit import NSWorkspace  # type: ignore

                return NSWorkspace.sharedWorkspace().frontmostApplication()
            except Exception:
                proc = subprocess.run(
                    [
                        "osascript",
                        "-e",
                        'tell application "System Events" to get unix id of first process whose frontmost is true',
                    ],
                    capture_output=True,
                    text=True,
                    timeout=1.5,
                )
                if proc.returncode == 0 and proc.stdout.strip().isdigit():
                    return int(proc.stdout.strip())
                return None
        if plat.startswith("linux") and not is_wayland_session():
            xdotool = shutil.which("xdotool")
            if xdotool:
                proc = subprocess.run([xdotool, "getactivewindow"], capture_output=True, text=True, timeout=1.5)
                if proc.returncode == 0 and proc.stdout.strip():
                    return proc.stdout.strip()
    except Exception as exc:
        logger.debug("Önceki pencere yakalanamadı: %s", exc)
    return None


def restore_previous_app(handle: Any, *, platform_name: str | None = None) -> bool:
    """Kaydedilen önceki uygulamaya odağı geri verir."""
    if not handle:
        return False
    plat = platform_name or sys.platform
    try:
        if plat == "win32":
            user32 = ctypes.windll.user32
            if isinstance(handle, int) and handle > 0:
                if user32.IsIconic(handle):
                    user32.ShowWindow(handle, 9)  # SW_RESTORE
                return bool(user32.SetForegroundWindow(handle))
            return False
        if plat == "darwin":
            if hasattr(handle, "activateWithOptions_"):
                # NSApplicationActivateIgnoringOtherApps = 1 << 1
                return bool(handle.activateWithOptions_(2))
            if isinstance(handle, int):
                proc = subprocess.run(
                    [
                        "osascript",
                        "-e",
                        f'tell application "System Events" to set frontmost of (first process whose unix id is {handle}) to true',
                    ],
                    capture_output=True,
                    text=True,
                    timeout=1.5,
                )
                return proc.returncode == 0
            return False
        if plat.startswith("linux"):
            xdotool = shutil.which("xdotool")
            if xdotool:
                proc = subprocess.run(
                    [xdotool, "windowactivate", "--sync", str(handle)],
                    capture_output=True,
                    text=True,
                    timeout=1.5,
                )
                if proc.returncode == 0:
                    return True
            wmctrl = shutil.which("wmctrl")
            if wmctrl:
                proc = subprocess.run(
                    [wmctrl, "-i", "-a", str(handle)],
                    capture_output=True,
                    text=True,
                    timeout=1.5,
                )
                return proc.returncode == 0
    except Exception as exc:
        logger.debug("Önceki uygulama odağı geri yüklenemedi: %s", exc)
    return False


def _get_pynput_controller() -> tuple[Any, Any]:
    from pynput.keyboard import Controller, Key

    return Controller(), Key


def _send_combo(controller: Any, mod_key: Any, char_or_key: Any) -> None:
    controller.press(mod_key)
    try:
        controller.press(char_or_key)
        controller.release(char_or_key)
    finally:
        controller.release(mod_key)


def _paste_wayland(
    text: str,
    *,
    method: str,
    send_enter: bool,
    runner: Any = None,
) -> tuple[bool, str, str | None]:
    run_fn = runner or subprocess.run
    wtype = shutil.which("wtype")
    if wtype:
        if method == "type":
            run_fn([wtype, "--", text], check=True, timeout=3)
        elif method == "shift_insert":
            run_fn([wtype, "-M", "shift", "-k", "Insert", "-m", "shift"], check=True, timeout=3)
        else:
            run_fn([wtype, "-M", "ctrl", "v", "-m", "ctrl"], check=True, timeout=3)
        if send_enter:
            run_fn([wtype, "-k", "Return"], check=True, timeout=3)
        return True, "wtype", None

    ydotool = shutil.which("ydotool")
    if ydotool:
        if method == "type":
            run_fn([ydotool, "type", "--", text], check=True, timeout=3)
        else:
            # Linux evdev keycodes: 29=LCtrl, 47=V, 28=Enter
            run_fn([ydotool, "key", "29:1", "47:1", "47:0", "29:0"], check=True, timeout=3)
        if send_enter:
            run_fn([ydotool, "key", "28:1", "28:0"], check=True, timeout=3)
        return True, "ydotool", None

    warning = (
        "Wayland oturumunda 'wtype' veya 'ydotool' bulunamadı; pynput (Xlib) ile yapıştırma deneniyor."
    )
    logger.warning(warning)
    return False, "wayland_fallback", warning


def paste_into_active_app(
    text: str,
    *,
    has_end_marker: bool = False,
    enter_after_paste: bool = True,
    paste_method: str = "auto",
    hide_overlay_cb: Callable[[], None] | None = None,
    previous_app: Any = None,
    delay_ms: int = 120,
    controller: Any = None,
    key_enum: Any = None,
    platform_name: str | None = None,
    wayland: bool | None = None,
    qt_clipboard: Any = None,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> PasteResult:
    """
    Metni panoya kopyalar, katmanı gizler, 120 ms bekler ve aktif uygulamaya yapıştırır.
    Öğe '<E<N<D|' bitiş işaretine sahipse ve enter_after_paste açıksa sonda Enter tuşu gönderir.
    """
    plat = platform_name or sys.platform
    copied = copy_to_clipboard(text, qt_clipboard=qt_clipboard)
    if not copied:
        logger.error("Pano erişimi başarısız olduğu için yapıştırma iptal edildi.")
        return PasteResult(
            ok=False,
            copied=False,
            pasted=False,
            enter_sent=False,
            method="clipboard_error",
            warning="Panoya kopyalama başarısız oldu.",
        )

    if hide_overlay_cb is not None:
        try:
            hide_overlay_cb()
        except Exception as exc:
            logger.debug("Katman gizleme geri çağrısı hatası: %s", exc)

    if previous_app is not None:
        restore_previous_app(previous_app, platform_name=plat)

    if delay_ms > 0:
        sleep_fn(delay_ms / 1000.0)

    should_send_enter = bool(has_end_marker and enter_after_paste)
    method_norm = (paste_method or "auto").strip().lower()
    use_wayland = is_wayland_session() if wayland is None else wayland
    warning_msg: str | None = None

    if use_wayland and plat.startswith("linux"):
        ok_wl, used_tool, wl_warn = _paste_wayland(
            text,
            method=method_norm,
            send_enter=should_send_enter,
        )
        if ok_wl:
            logger.info("Wayland üzerinde '%s' ile yapıştırıldı (enter=%s).", used_tool, should_send_enter)
            return PasteResult(
                ok=True,
                copied=True,
                pasted=True,
                enter_sent=should_send_enter,
                method=used_tool,
            )
        warning_msg = wl_warn

    try:
        if controller is None or key_enum is None:
            ctrl, k_enum = _get_pynput_controller()
        else:
            ctrl, k_enum = controller, key_enum

        if method_norm == "type":
            ctrl.type(text)
            used_method = "type"
        elif method_norm == "shift_insert":
            _send_combo(ctrl, k_enum.shift, k_enum.insert)
            used_method = "shift_insert"
        else:
            mod_key = k_enum.cmd if plat == "darwin" else k_enum.ctrl
            _send_combo(ctrl, mod_key, "v")
            used_method = "cmd_v" if plat == "darwin" else "ctrl_v"

        enter_sent = False
        if should_send_enter:
            sleep_fn(0.02)
            ctrl.press(k_enum.enter)
            ctrl.release(k_enum.enter)
            enter_sent = True

        logger.info("Öğe aktif uygulamaya yapıştırıldı (yöntem=%s, enter=%s).", used_method, enter_sent)
        return PasteResult(
            ok=True,
            copied=True,
            pasted=True,
            enter_sent=enter_sent,
            method=used_method,
            warning=warning_msg,
        )
    except Exception as exc:
        logger.error("Tuş simülasyonu başarısız (yalnızca panoya kopyalandı): %s", exc, exc_info=True)
        return PasteResult(
            ok=False,
            copied=True,
            pasted=False,
            enter_sent=False,
            method="error",
            warning=f"Tuş simülasyonu başarısız: {exc}",
        )
