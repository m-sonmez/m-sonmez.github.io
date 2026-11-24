"""Sıfır dış bağımlılıklı pano kopyalama, odak geri yükleme ve otomatik yapıştırma motoru."""

from __future__ import annotations

import base64
import ctypes
import os
import re
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

TERMINAL_APP_TOKENS: tuple[str, ...] = (
    "konsole",
    "alacritty",
    "kitty",
    "ghostty",
    "wezterm",
    "foot",
    "gnome-terminal",
    "kgx",
    "tilix",
    "terminator",
    "xterm",
    "urxvt",
    "st",
    "rio",
    "warp",
    "tabby",
    "hyper",
    "xfce4-terminal",
    "mate-terminal",
    "lxterminal",
)

_TERMINAL_MULTI_TOKENS: tuple[str, ...] = tuple(t for t in TERMINAL_APP_TOKENS if t != "st")
_ST_TERM_RE = re.compile(r"(?:^|[^a-z0-9])st(?:-\d+color)?(?:[^a-z0-9]|$)")

WAYLAND_COPY_ONLY_MSG = (
    "Panoya kopyalandı ✔ (Wayland oturumunda yapıştırmak için Ctrl+V / Ctrl+Shift+V kullanın)"
)
WAYLAND_UNAVAILABLE_LOG = (
    "Wayland oturumunda 'wtype' veya 'ydotool' bulunamadı; yapay yapıştırma gerçekleştirilemedi."
)


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


def is_posix_desktop(platform_name: str | None = None) -> bool:
    """Linux, FreeBSD, OpenBSD, NetBSD ve benzeri Unix/POSIX masaüstlerini tanır."""
    plat = (platform_name or sys.platform).strip().lower()
    if not plat or plat in ("win32", "darwin", "cygwin", "msys") or plat.startswith("win"):
        return False
    return True


def is_wayland_session(platform_name: str | None = None) -> bool:
    """Linux / BSD Unix-benzeri üzerinde Wayland oturumu çalışıp çalışmadığını algılar."""
    if not is_posix_desktop(platform_name):
        return False
    return bool(os.environ.get("WAYLAND_DISPLAY")) or (
        os.environ.get("XDG_SESSION_TYPE", "").strip().lower() == "wayland"
    )


def _is_terminal_identifier(raw_name: str | None) -> bool:
    low = str(raw_name or "").strip().lower()
    if not low:
        return False
    if any(tok in low for tok in _TERMINAL_MULTI_TOKENS):
        return True
    return bool(_ST_TERM_RE.search(low))


def _query_x11_window_hint(win_id: int) -> str:
    if not os.environ.get("DISPLAY") or win_id <= 0:
        return ""
    try:
        from Xlib import display as xdisplay

        dpy = xdisplay.Display()
        try:
            cur = dpy.create_resource_object("window", int(win_id))
            parts: list[str] = []
            for _ in range(8):
                if cur is None:
                    break
                try:
                    wm_cls = cur.get_wm_class()
                    if wm_cls:
                        parts.extend(str(x) for x in wm_cls if x)
                except Exception:
                    pass
                try:
                    wm_name = cur.get_wm_name()
                    if wm_name:
                        parts.append(str(wm_name))
                except Exception:
                    pass
                if parts:
                    break
                try:
                    tree = cur.query_tree()
                    parent = getattr(tree, "parent", None)
                    root = getattr(tree, "root", None)
                    if parent is None or (root is not None and getattr(parent, "id", 0) == getattr(root, "id", -1)):
                        break
                    cur = parent
                except Exception:
                    break
            return " ".join(parts)
        finally:
            dpy.close()
    except Exception:
        return ""


def is_terminal_window(previous_app: Any = None, *, platform_name: str | None = None) -> bool:
    """Hedef uygulamanın Linux/POSIX uçbirim (terminal) penceresi olup olmadığını belirler."""
    plat = platform_name or sys.platform
    if not is_posix_desktop(plat) or previous_app is None:
        return False
    if isinstance(previous_app, str):
        return _is_terminal_identifier(previous_app)
    if isinstance(previous_app, dict):
        for key in ("wm_class", "app_id", "title", "name", "class"):
            if _is_terminal_identifier(previous_app.get(key)):
                return True
        return False
    if isinstance(previous_app, int):
        hint = _query_x11_window_hint(previous_app)
        return _is_terminal_identifier(hint)
    for attr in ("wm_class", "app_id", "title", "name"):
        val = getattr(previous_app, attr, None)
        if val and _is_terminal_identifier(str(val)):
            return True
    return False


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
    """macOS üzerinde önce AppKit NSPasteboard (NSPasteboardTypeString -> NSStringPboardType), yoksa yerleşik pbcopy kullanır."""
    try:
        import AppKit

        pb = AppKit.NSPasteboard.generalPasteboard()
        for type_attr in ("NSPasteboardTypeString", "NSStringPboardType"):
            pb_type = getattr(AppKit, type_attr, None)
            if pb_type is None:
                continue
            pb.clearContents()
            pb.declareTypes_owner_([pb_type], None)
            if pb.setString_forType_(text, pb_type):
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


def _write_qt_clipboard(cb: Any, text: str, app: Any = None) -> None:
    cb.setText(text)
    try:
        supports_sel = getattr(cb, "supportsSelection", None)
        if callable(supports_sel) and supports_sel() is True:
            from PyQt6.QtGui import QClipboard

            cb.setText(text, QClipboard.Mode.Selection)
    except Exception:
        pass
    if app is not None and hasattr(app, "processEvents"):
        try:
            app.processEvents()
        except Exception:
            pass


def _run_clipboard_daemon_cmd(cmd: list[str], text: str) -> bool:
    try:
        proc = subprocess.run(
            cmd,
            input=text.encode("utf-8"),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            timeout=2,
            check=False,
        )
        return getattr(proc, "returncode", 1) == 0
    except Exception:
        return False


def _copy_posix_clipboard(text: str, *, platform_name: str | None = None) -> bool:
    """Linux/BSD pano sırası: canlı Qt QGuiApplication panosu -> wl-copy -> xclip/xsel."""
    try:
        from PyQt6.QtGui import QGuiApplication

        app = QGuiApplication.instance()
        pname = (app.platformName() or "").strip().lower() if app is not None and hasattr(app, "platformName") else ""
        if app is not None and pname != "offscreen" and app.clipboard() is not None:
            _write_qt_clipboard(app.clipboard(), text, app=app)
            return True
    except Exception:
        pass

    if is_wayland_session(platform_name):
        wl_copy = shutil.which("wl-copy")
        if wl_copy and _run_clipboard_daemon_cmd([wl_copy], text):
            return True

    if os.environ.get("DISPLAY"):
        xclip_bin = shutil.which("xclip")
        if xclip_bin and _run_clipboard_daemon_cmd([xclip_bin, "-selection", "clipboard"], text):
            return True
        xsel_bin = shutil.which("xsel")
        if xsel_bin and _run_clipboard_daemon_cmd([xsel_bin, "--clipboard", "--input"], text):
            return True

    return False


_copy_unix_x11_ctypes = _copy_posix_clipboard
_copy_linux_x11_ctypes = _copy_posix_clipboard


def copy_to_clipboard(
    text: str,
    *,
    qt_clipboard: Any = None,
    platform_name: str | None = None,
) -> bool:
    """
    Metni işletim sistemi panosuna kopyalar.
    Sıra: özel Qt panosu -> yerel OS API / Wayland wl-copy / X11 xclip-xsel -> OSC 52 -> Qt fallback -> pyperclip.
    """
    plat = platform_name or sys.platform

    if qt_clipboard is not None:
        try:
            _write_qt_clipboard(qt_clipboard, text)
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
    elif is_posix_desktop(plat):
        if _copy_posix_clipboard(text, platform_name=plat):
            return True
        if _emit_osc52(text):
            return True

    try:
        from PyQt6.QtGui import QGuiApplication

        app = QGuiApplication.instance()
        if app is not None and app.clipboard() is not None:
            _write_qt_clipboard(app.clipboard(), text, app=app)
            return True
    except Exception:
        pass

    try:
        import pyperclip

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
                from AppKit import NSWorkspace

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
        if is_posix_desktop(plat) and not is_wayland_session(plat) and os.environ.get("DISPLAY"):
            try:
                from Xlib import X, display as xdisplay

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
                    user32.ShowWindow(handle, 9)
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
        if is_posix_desktop(plat) and os.environ.get("DISPLAY") and isinstance(handle, int):
            try:
                from Xlib import X, display as xdisplay

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


def bring_window_to_top(win_id: int, *, platform_name: str | None = None) -> bool:
    """Pencereyi işletim sistemi düzeyinde en üst katmana (topmost) ve öne getirir."""
    plat = platform_name or sys.platform
    if plat != "win32" or not win_id:
        return False
    try:
        windll = getattr(ctypes, "windll", None)
        if windll is None:
            return False
        u32 = windll.user32
        u32.SetWindowPos.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_uint,
        ]
        u32.SetWindowPos.restype = ctypes.c_int
        u32.SetForegroundWindow.argtypes = [ctypes.c_void_p]
        u32.SetForegroundWindow.restype = ctypes.c_int
        hwnd = ctypes.c_void_p(int(win_id))
        hwnd_topmost = ctypes.c_void_p(-1)
        swp_flags = 0x0001 | 0x0002 | 0x0040
        ok_pos = bool(u32.SetWindowPos(hwnd, hwnd_topmost, 0, 0, 0, 0, swp_flags))
        u32.SetForegroundWindow(hwnd)
        return ok_pos
    except Exception as exc:
        logger.debug("Pencere en üste getirilemedi: %s", exc)
        return False


def _get_pynput_controller() -> tuple[Any, Any]:
    from pynput.keyboard import Controller, Key

    return Controller(), Key


def _send_combo(
    controller: Any,
    mod_keys: Any,
    char_or_key: Any,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> None:
    mods = list(mod_keys) if isinstance(mod_keys, (list, tuple)) else [mod_keys]
    for mod_key in mods:
        controller.press(mod_key)
    sleep_fn(0.02)
    try:
        controller.press(char_or_key)
        sleep_fn(0.01)
        controller.release(char_or_key)
    finally:
        sleep_fn(0.01)
        for mod_key in reversed(mods):
            controller.release(mod_key)


def _check_proc_rc(res: Any, tool_name: str) -> None:
    rc = getattr(res, "returncode", 0)
    if isinstance(rc, int) and rc != 0:
        raise RuntimeError(f"{tool_name} çıkış kodu={rc}")


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
        try:
            if method == "type":
                res = run_fn([wtype, "--", text], check=True, timeout=3)
            elif method == "ctrl_shift_v":
                res = run_fn([wtype, "-M", "ctrl", "-M", "shift", "-k", "v", "-m", "shift", "-m", "ctrl"], check=True, timeout=3)
            elif method == "shift_insert":
                res = run_fn([wtype, "-M", "shift", "-k", "Insert", "-m", "shift"], check=True, timeout=3)
            else:
                res = run_fn([wtype, "-M", "ctrl", "-k", "v", "-m", "ctrl"], check=True, timeout=3)
            _check_proc_rc(res, "wtype")
            if send_enter:
                res_ret = run_fn([wtype, "-k", "Return"], check=True, timeout=3)
                _check_proc_rc(res_ret, "wtype Return")
            return True, "wtype", None
        except Exception as exc:
            logger.debug("Wayland 'wtype' çalıştırılamadı veya compositor tarafından reddedildi: %s", exc)

    ydotool = shutil.which("ydotool")
    if ydotool:
        try:
            if method == "type":
                res = run_fn([ydotool, "type", "--", text], check=True, timeout=3)
            elif method == "ctrl_shift_v":
                res = run_fn([ydotool, "key", "29:1", "42:1", "47:1", "47:0", "42:0", "29:0"], check=True, timeout=3)
            elif method == "shift_insert":
                res = run_fn([ydotool, "key", "42:1", "110:1", "110:0", "42:0"], check=True, timeout=3)
            else:
                res = run_fn([ydotool, "key", "29:1", "47:1", "47:0", "29:0"], check=True, timeout=3)
            _check_proc_rc(res, "ydotool")
            if send_enter:
                res_ret = run_fn([ydotool, "key", "28:1", "28:0"], check=True, timeout=3)
                _check_proc_rc(res_ret, "ydotool Return")
            return True, "ydotool", None
        except Exception as exc:
            logger.debug("Wayland 'ydotool' çalıştırılamadı: %s", exc)

    logger.warning(WAYLAND_UNAVAILABLE_LOG)
    return False, "wayland_unavailable", WAYLAND_COPY_ONLY_MSG


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
    already_copied: bool = False,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> PasteResult:
    """
    Metni panoya kopyalar (veya already_copied=True ise korur), katmanı gizler, bekler ve aktif uygulamaya yapıştırır.
    Çıkış kodları: 0 başarılı, 3 pano kullanılamıyor, 4 tuş gönderimi gerçekleştirilemedi.
    """
    plat = platform_name or sys.platform
    if already_copied:
        copied = True
    else:
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
    if method_norm == "auto":
        if is_posix_desktop(plat) and is_terminal_window(previous_app, platform_name=plat):
            effective_method = "ctrl_shift_v"
        else:
            effective_method = "ctrl_v"
    else:
        effective_method = method_norm

    use_wayland = is_wayland_session(plat) if wayland is None else wayland

    if use_wayland and is_posix_desktop(plat):
        ok_wl, used_tool, wl_warn = _paste_wayland(
            text,
            method=effective_method,
            send_enter=should_send_enter,
        )
        if ok_wl:
            logger.info(
                "Wayland üzerinde '%s' (%s) ile yapıştırıldı (enter=%s).",
                used_tool,
                effective_method,
                should_send_enter,
            )
            return PasteResult(
                ok=True,
                copied=True,
                pasted=True,
                enter_sent=should_send_enter,
                method=used_tool,
                exit_code=0,
            )
        if controller is None:
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

        if effective_method == "type":
            ctrl.type(text)
            used_method = "type"
        elif effective_method == "ctrl_shift_v":
            _send_combo(ctrl, [k_enum.ctrl, k_enum.shift], "v", sleep_fn=sleep_fn)
            used_method = "ctrl_shift_v"
        elif effective_method == "shift_insert":
            _send_combo(ctrl, k_enum.shift, k_enum.insert, sleep_fn=sleep_fn)
            used_method = "shift_insert"
        else:
            mod_key = k_enum.cmd if plat == "darwin" else k_enum.ctrl
            _send_combo(ctrl, mod_key, "v", sleep_fn=sleep_fn)
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
