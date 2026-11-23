"""Sıfır dış bağımlılıklı pano kopyalama, odak geri yükleme ve otomatik yapıştırma motoru."""

from __future__ import annotations

import base64
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

_CF_UNICODETEXT = 13
_GMEM_MOVEABLE = 0x0002


@dataclass
class PasteResult:
    """Yapıştırma işleminin ayrıntılı sonucu."""

    ok: bool
    copied: bool
    pasted: bool
    enter_sent: bool
    method: str
    warning: str | None = None
    exit_code: int = 0


def is_wayland_session() -> bool:
    """Linux üzerinde Wayland oturumu çalışıp çalışmadığını algılar."""
    if sys.platform != "linux":
        return False
    return bool(os.environ.get("WAYLAND_DISPLAY")) or (
        os.environ.get("XDG_SESSION_TYPE", "").strip().lower() == "wayland"
    )


def _emit_osc52(text: str) -> bool:
    """Etkileşimli terminallerde OSC 52 kaçış dizisiyle sistem panosunu günceller."""
    try:
        stream = sys.stdout
        if stream is not None and hasattr(stream, "isatty") and stream.isatty():
            encoded = base64.b64encode(text.encode("utf-8")).decode("ascii")
            stream.write(f"\x1b]52;c;{encoded}\x07")
            stream.flush()
            return True
    except Exception:
        pass
    return False


def _copy_windows_ctypes(text: str) -> bool:
    """Saf ctypes Win32 API (OpenClipboard/SetClipboardData) ile UTF-16 metin kopyalar."""
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalUnlock.restype = ctypes.c_int
    kernel32.GlobalFree.argtypes = [ctypes.c_void_p]
    kernel32.GlobalFree.restype = ctypes.c_void_p
    user32.OpenClipboard.argtypes = [ctypes.c_void_p]
    user32.OpenClipboard.restype = ctypes.c_int
    user32.EmptyClipboard.argtypes = []
    user32.EmptyClipboard.restype = ctypes.c_int
    user32.CloseClipboard.argtypes = []
    user32.CloseClipboard.restype = ctypes.c_int
    user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
    user32.SetClipboardData.restype = ctypes.c_void_p

    payload = text.encode("utf-16-le") + b"\x00\x00"
    hmem = kernel32.GlobalAlloc(_GMEM_MOVEABLE, len(payload))
    if not hmem:
        return False
    ptr = kernel32.GlobalLock(hmem)
    if not ptr:
        kernel32.GlobalFree(hmem)
        return False
    ctypes.memmove(ptr, payload, len(payload))
    kernel32.GlobalUnlock(hmem)

    opened = False
    for _ in range(5):
        if user32.OpenClipboard(None):
            opened = True
            break
        time.sleep(0.01)
    if not opened:
        kernel32.GlobalFree(hmem)
        return False

    try:
        user32.EmptyClipboard()
        res = user32.SetClipboardData(_CF_UNICODETEXT, hmem)
        if not res:
            kernel32.GlobalFree(hmem)
            return False
        return True
    finally:
        user32.CloseClipboard()


def _copy_macos_native(text: str) -> bool:
    """macOS üzerinde önce AppKit NSPasteboard, yoksa yerleşik pbcopy kullanır."""
    try:
        from AppKit import NSPasteboard, NSStringPboardType  # type: ignore

        pb = NSPasteboard.generalPasteboard()
        pb.clearContents()
        pb.declareTypes_owner_([NSStringPboardType], None)
        if pb.setString_forType_(text, NSStringPboardType):
            return True
    except Exception:
        pass

    pbcopy = shutil.which("pbcopy")
    if pbcopy:
        try:
            subprocess.run([pbcopy], input=text.encode("utf-8"), check=True, timeout=2)
            return True
        except Exception:
            pass
    return False


def _copy_linux_x11_ctypes(text: str) -> bool:
    """Harici araç olmadan libX11.so.6 veya Qt panosunu dener."""
    try:
        if os.environ.get("DISPLAY") and not os.environ.get("QT_QPA_PLATFORM") == "offscreen":
            from PyQt6.QtGui import QGuiApplication

            app = QGuiApplication.instance()
            if app is not None and app.clipboard() is not None:
                app.clipboard().setText(text)
                return True
    except Exception:
        pass

    if os.environ.get("DISPLAY"):
        try:
            x11 = ctypes.CDLL("libX11.so.6")
            x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
            x11.XOpenDisplay.restype = ctypes.c_void_p
            dpy = x11.XOpenDisplay(None)
            if dpy:
                try:
                    x11.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
                    x11.XInternAtom.restype = ctypes.c_ulong
                    clip_atom = x11.XInternAtom(dpy, b"CLIPBOARD", 0)
                    utf8_atom = x11.XInternAtom(dpy, b"UTF8_STRING", 0)
                    if clip_atom and utf8_atom:
                        x11.XStoreBytes.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
                        x11.XStoreBytes.restype = ctypes.c_int
                        x11.XFlush.argtypes = [ctypes.c_void_p]
                        x11.XFlush.restype = ctypes.c_int
                        x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
                        x11.XCloseDisplay.restype = ctypes.c_int
                        raw = text.encode("utf-8")
                        x11.XStoreBytes(dpy, raw, len(raw))
                        x11.XFlush(dpy)
                        return True
                finally:
                    x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
                    x11.XCloseDisplay.restype = ctypes.c_int
                    x11.XCloseDisplay(dpy)
        except Exception:
            pass
    return False


def copy_to_clipboard(
    text: str,
    *,
    qt_clipboard: Any = None,
    platform_name: str | None = None,
) -> bool:
    """
    Metni harici araca ihtiyaç duymadan işletim sistemi panosuna kopyalar.
    Sıra: özel Qt panosu -> yerel OS API (Win32 ctypes / macOS AppKit / Linux X11-Qt-OSC52) -> isteğe bağlı pyperclip.
    """
    plat = platform_name or sys.platform

    if qt_clipboard is not None:
        try:
            qt_clipboard.setText(text)
            return True
        except Exception as exc:
            logger.debug("Özel Qt panosu kullanılamadı: %s", exc)

    if plat == "win32":
        try:
            if _copy_windows_ctypes(text):
                return True
        except Exception as exc:
            logger.debug("Win32 ctypes pano hatası: %s", exc)
    elif plat == "darwin":
        if _copy_macos_native(text):
            return True
    elif plat.startswith("linux"):
        if _copy_linux_x11_ctypes(text):
            return True
        if _emit_osc52(text):
            return True

    # Aktif Qt uygulaması varsa son güvenli yerel yol olarak kullan
    try:
        from PyQt6.QtGui import QGuiApplication

        app = QGuiApplication.instance()
        if app is not None and app.clipboard() is not None:
            app.clipboard().setText(text)
            return True
    except Exception:
        pass

    # İsteğe bağlı üçüncü parti yedek (hiçbir zaman zorunlu değil)
    try:
        import pyperclip  # type: ignore

        pyperclip.copy(text)
        return True
    except ImportError:
        pass
    except Exception as exc:
        logger.debug("İsteğe bağlı pyperclip kopyalaması başarısız: %s", exc)

    if _emit_osc52(text):
        return True

    logger.warning("Pano erişimi başarısız: grafik oturumu veya pano desteği bulunamadı.")
    return False


def capture_previous_app(*, platform_name: str | None = None) -> Any:
    """Overlay açılmadan hemen önce odakta bulunan hedef uygulamayı yakalar."""
    plat = platform_name or sys.platform
    try:
        if plat == "win32":
            user32 = ctypes.windll.user32
            user32.GetForegroundWindow.argtypes = []
            user32.GetForegroundWindow.restype = ctypes.c_void_p
            hwnd = int(user32.GetForegroundWindow() or 0)
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
        if plat.startswith("linux") and not is_wayland_session() and os.environ.get("DISPLAY"):
            try:
                from Xlib import X, display as xdisplay  # type: ignore

                dpy = xdisplay.Display()
                try:
                    focus = dpy.get_input_focus()
                    win = getattr(focus, "focus", None)
                    if win and hasattr(win, "id") and win.id not in (0, X.PointerRoot):
                        return int(win.id)
                finally:
                    dpy.close()
            except Exception:
                pass
    except Exception as exc:
        logger.debug("Önceki pencere yakalanamadı: %s", exc)
    return None


def restore_previous_app(handle: Any, *, platform_name: str | None = None) -> bool:
    """Kaydedilen önceki uygulamaya harici ikili gerektirmeden odağı geri verir."""
    if not handle:
        return False
    plat = platform_name or sys.platform
    try:
        if plat == "win32":
            user32 = ctypes.windll.user32
            user32.IsIconic.argtypes = [ctypes.c_void_p]
            user32.IsIconic.restype = ctypes.c_int
            user32.ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
            user32.ShowWindow.restype = ctypes.c_int
            user32.SetForegroundWindow.argtypes = [ctypes.c_void_p]
            user32.SetForegroundWindow.restype = ctypes.c_int
            if isinstance(handle, int) and handle > 0:
                if user32.IsIconic(handle):
                    user32.ShowWindow(handle, 9)  # SW_RESTORE
                return bool(user32.SetForegroundWindow(handle))
            return False
        if plat == "darwin":
            if hasattr(handle, "activateWithOptions_"):
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
        if plat.startswith("linux") and os.environ.get("DISPLAY"):
            try:
                from Xlib import X, display as xdisplay  # type: ignore

                dpy = xdisplay.Display()
                try:
                    win = dpy.create_resource_object("window", int(handle))
                    win.set_input_focus(X.RevertToParent, X.CurrentTime)
                    dpy.flush()
                    return True
                finally:
                    dpy.close()
            except Exception:
                return False
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
            run_fn([ydotool, "key", "29:1", "47:1", "47:0", "29:0"], check=True, timeout=3)
        if send_enter:
            run_fn([ydotool, "key", "28:1", "28:0"], check=True, timeout=3)
        return True, "ydotool", None

    warning = "Wayland oturumunda 'wtype' veya 'ydotool' bulunamadı; yapay yapıştırma gerçekleştirilemedi."
    logger.warning(warning)
    return False, "wayland_unavailable", warning


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
    Metni panoya kopyalar, katmanı gizler, bekler ve aktif uygulamaya yapıştırır.
    Çıkış kodları: 0 başarılı, 3 pano kullanılamıyor, 4 tuş gönderimi gerçekleştirilemedi.
    """
    plat = platform_name or sys.platform
    copied = copy_to_clipboard(text, qt_clipboard=qt_clipboard, platform_name=plat)
    if not copied:
        msg = "Pano erişimi başarısız: grafik oturumu veya pano desteği bulunamadı."
        logger.error(msg)
        return PasteResult(
            ok=False,
            copied=False,
            pasted=False,
            enter_sent=False,
            method="clipboard_error",
            warning=msg,
            exit_code=3,
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
                exit_code=0,
            )
        if not os.environ.get("DISPLAY") and controller is None:
            return PasteResult(
                ok=False,
                copied=True,
                pasted=False,
                enter_sent=False,
                method="wayland_unavailable",
                warning=wl_warn,
                exit_code=4,
            )

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
            exit_code=0,
        )
    except Exception as exc:
        warn = f"Tuş simülasyonu başarısız (yalnızca panoya kopyalandı): {exc}"
        logger.warning(warn)
        return PasteResult(
            ok=False,
            copied=True,
            pasted=False,
            enter_sent=False,
            method="injection_unavailable",
            warning=warn,
            exit_code=4,
        )
