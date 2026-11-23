"""Sıfır bağımlılıklı pano, pencere odağı, yapıştırma (<E<N<D| -> Enter) ve Wayland testleri."""

from __future__ import annotations

import io
import logging
import os
import sys
from types import SimpleNamespace
from unittest import mock

from qtp_app.core import paster


class _FakeController:
    def __init__(self):
        self.events: list[tuple[str, object]] = []

    def press(self, key):
        self.events.append(("press", key))

    def release(self, key):
        self.events.append(("release", key))

    def type(self, text: str):
        self.events.append(("type", text))


_FAKE_KEYS = SimpleNamespace(
    ctrl="CTRL",
    cmd="CMD",
    shift="SHIFT",
    insert="INSERT",
    enter="ENTER",
)


def test_paste_with_end_marker_sends_ctrl_v_then_enter():
    ctrl = _FakeController()
    hidden = []

    with mock.patch("qtp_app.core.paster.copy_to_clipboard", return_value=True) as copy_mock:
        res = paster.paste_into_active_app(
            "Merhaba dünya",
            has_end_marker=True,
            enter_after_paste=True,
            paste_method="auto",
            hide_overlay_cb=lambda: hidden.append(True),
            delay_ms=0,
            controller=ctrl,
            key_enum=_FAKE_KEYS,
            platform_name="win32",
            wayland=False,
            sleep_fn=lambda _s: None,
        )

    assert res.ok is True
    assert res.exit_code == 0
    assert res.copied is True
    assert res.pasted is True
    assert res.enter_sent is True
    assert hidden == [True]
    copy_mock.assert_called_once_with("Merhaba dünya", qt_clipboard=None, platform_name="win32")
    assert ctrl.events == [
        ("press", "CTRL"),
        ("press", "v"),
        ("release", "v"),
        ("release", "CTRL"),
        ("press", "ENTER"),
        ("release", "ENTER"),
    ]


def test_paste_without_end_marker_skips_enter():
    ctrl = _FakeController()

    with mock.patch("qtp_app.core.paster.copy_to_clipboard", return_value=True):
        res = paster.paste_into_active_app(
            "Sadece yapıştır",
            has_end_marker=False,
            enter_after_paste=True,
            paste_method="auto",
            delay_ms=0,
            controller=ctrl,
            key_enum=_FAKE_KEYS,
            platform_name="darwin",
            wayland=False,
            sleep_fn=lambda _s: None,
        )

    assert res.ok is True
    assert res.enter_sent is False
    assert res.method == "cmd_v"
    assert ctrl.events == [
        ("press", "CMD"),
        ("press", "v"),
        ("release", "v"),
        ("release", "CMD"),
    ]


def test_paste_methods_shift_insert_and_type():
    ctrl_si = _FakeController()
    with mock.patch("qtp_app.core.paster.copy_to_clipboard", return_value=True):
        res_si = paster.paste_into_active_app(
            "Metin",
            has_end_marker=False,
            paste_method="shift_insert",
            delay_ms=0,
            controller=ctrl_si,
            key_enum=_FAKE_KEYS,
            platform_name="linux",
            wayland=False,
            sleep_fn=lambda _s: None,
        )
    assert res_si.method == "shift_insert"
    assert ("press", "INSERT") in ctrl_si.events

    ctrl_tp = _FakeController()
    with mock.patch("qtp_app.core.paster.copy_to_clipboard", return_value=True):
        res_tp = paster.paste_into_active_app(
            "Doğrudan yaz",
            has_end_marker=True,
            paste_method="type",
            delay_ms=0,
            controller=ctrl_tp,
            key_enum=_FAKE_KEYS,
            platform_name="linux",
            wayland=False,
            sleep_fn=lambda _s: None,
        )
    assert res_tp.method == "type"
    assert ctrl_tp.events[0] == ("type", "Doğrudan yaz")
    assert ("press", "ENTER") in ctrl_tp.events


def test_wayland_uses_wtype_when_available_and_warns_otherwise(caplog, monkeypatch):
    with mock.patch("qtp_app.core.paster.copy_to_clipboard", return_value=True), \
         mock.patch("shutil.which", side_effect=lambda name: "/usr/bin/wtype" if name == "wtype" else None), \
         mock.patch("subprocess.run") as run_mock:
        res = paster.paste_into_active_app(
            "Wayland metin",
            has_end_marker=True,
            enter_after_paste=True,
            delay_ms=0,
            platform_name="linux",
            wayland=True,
            sleep_fn=lambda _s: None,
        )
    assert res.ok is True
    assert res.method == "wtype"
    assert res.enter_sent is True
    assert run_mock.call_count == 2
    assert run_mock.call_args_list[0][0][0] == ["/usr/bin/wtype", "-M", "ctrl", "v", "-m", "ctrl"]
    assert run_mock.call_args_list[1][0][0] == ["/usr/bin/wtype", "-k", "Return"]

    monkeypatch.delenv("DISPLAY", raising=False)
    caplog.set_level(logging.WARNING)
    with mock.patch("qtp_app.core.paster.copy_to_clipboard", return_value=True), \
         mock.patch("shutil.which", return_value=None):
        res_fb = paster.paste_into_active_app(
            "Fallback metin",
            has_end_marker=False,
            delay_ms=0,
            platform_name="linux",
            wayland=True,
            sleep_fn=lambda _s: None,
        )
    assert res_fb.ok is False
    assert res_fb.exit_code == 4
    assert res_fb.warning is not None and "wtype" in res_fb.warning


def test_wayland_ydotool_and_clipboard_failure(caplog):
    with mock.patch("qtp_app.core.paster._copy_windows_ctypes", return_value=False), \
         mock.patch("PyQt6.QtGui.QGuiApplication.instance", return_value=None), \
         mock.patch.dict("sys.modules", {"pyperclip": None}):
        res_fail = paster.paste_into_active_app(
            "Metin", delay_ms=0, platform_name="win32", sleep_fn=lambda _s: None
        )
    assert res_fail.ok is False
    assert res_fail.exit_code == 3
    assert res_fail.method == "clipboard_error"

    with mock.patch("qtp_app.core.paster.copy_to_clipboard", return_value=True), \
         mock.patch("shutil.which", side_effect=lambda name: "/usr/bin/ydotool" if name == "ydotool" else None), \
         mock.patch("subprocess.run") as run_mock:
        res_ydo = paster.paste_into_active_app(
            "Ydo",
            has_end_marker=True,
            enter_after_paste=True,
            delay_ms=0,
            platform_name="linux",
            wayland=True,
            sleep_fn=lambda _s: None,
        )
    assert res_ydo.ok is True
    assert res_ydo.method == "ydotool"
    assert run_mock.call_count == 2

    with mock.patch("qtp_app.core.paster.copy_to_clipboard", return_value=True), \
         mock.patch("shutil.which", side_effect=lambda name: "/usr/bin/wtype" if name == "wtype" else None), \
         mock.patch("subprocess.run") as run_mock2:
        paster.paste_into_active_app(
            "A", paste_method="type", delay_ms=0, platform_name="linux", wayland=True, sleep_fn=lambda _s: None
        )
        paster.paste_into_active_app(
            "B", paste_method="shift_insert", delay_ms=0, platform_name="linux", wayland=True, sleep_fn=lambda _s: None
        )
    assert run_mock2.call_args_list[0][0][0] == ["/usr/bin/wtype", "--", "A"]
    assert run_mock2.call_args_list[1][0][0] == ["/usr/bin/wtype", "-M", "shift", "-k", "Insert", "-m", "shift"]

    bad_ctrl = mock.Mock()
    bad_ctrl.press.side_effect = RuntimeError("input denied")
    with mock.patch("qtp_app.core.paster.copy_to_clipboard", return_value=True):
        res_err = paster.paste_into_active_app(
            "Err",
            delay_ms=0,
            controller=bad_ctrl,
            key_enum=_FAKE_KEYS,
            platform_name="win32",
            wayland=False,
            sleep_fn=lambda _s: None,
        )
    assert res_err.ok is False
    assert res_err.exit_code == 4
    assert res_err.copied is True


def test_zero_dep_clipboards_and_window_focus_platforms(monkeypatch):
    orig_display = os.environ.get("DISPLAY")
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    with mock.patch("qtp_app.core.paster.sys.platform", "linux"):
        assert paster.is_wayland_session() is True
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.setenv("XDG_SESSION_TYPE", "x11")
    with mock.patch("qtp_app.core.paster.sys.platform", "linux"):
        assert paster.is_wayland_session() is False

    fake_qt_cb = mock.Mock()
    assert paster.copy_to_clipboard("Qt doğrudan", qt_clipboard=fake_qt_cb) is True
    fake_qt_cb.setText.assert_called_once_with("Qt doğrudan")

    tty_buf = io.StringIO()
    tty_buf.isatty = lambda: True
    monkeypatch.delenv("DISPLAY", raising=False)
    with mock.patch.object(sys, "stdout", tty_buf):
        assert paster.copy_to_clipboard("OSC52 Test", platform_name="linux") is True
    assert "\x1b]52;c;" in tty_buf.getvalue()

    with mock.patch("shutil.which", return_value="/usr/bin/pbcopy"), \
         mock.patch("subprocess.run", return_value=SimpleNamespace(returncode=0)) as pb_run:
        assert paster.copy_to_clipboard("Mac metin", platform_name="darwin") is True
        pb_run.assert_called_once()

    fake_user32 = mock.Mock()
    fake_user32.GetForegroundWindow.return_value = 12345
    fake_user32.IsIconic.return_value = True
    fake_user32.SetForegroundWindow.return_value = 1
    fake_windll = SimpleNamespace(user32=fake_user32)
    with mock.patch.object(paster.ctypes, "windll", fake_windll, create=True):
        hwnd = paster.capture_previous_app(platform_name="win32")
        assert hwnd == 12345
        assert paster.restore_previous_app(hwnd, platform_name="win32") is True
    assert paster.restore_previous_app(None, platform_name="win32") is False

    fake_win = mock.Mock()
    fake_win.id = 9988
    fake_dpy = mock.Mock()
    fake_dpy.get_input_focus.return_value = SimpleNamespace(focus=fake_win)
    fake_dpy.create_resource_object.return_value = fake_win
    fake_xlib = SimpleNamespace(X=SimpleNamespace(PointerRoot=1, RevertToParent=2, CurrentTime=0), display=SimpleNamespace(Display=lambda: fake_dpy))
    monkeypatch.setenv("DISPLAY", ":0")
    with mock.patch.dict("sys.modules", {"Xlib": fake_xlib, "Xlib.X": fake_xlib.X, "Xlib.display": fake_xlib.display}):
        assert paster.capture_previous_app(platform_name="linux") == 9988
        assert paster.restore_previous_app(9988, platform_name="linux") is True

    with mock.patch("subprocess.run", return_value=SimpleNamespace(returncode=0, stdout="4321\n")):
        assert paster.capture_previous_app(platform_name="darwin") == 4321
        assert paster.restore_previous_app(4321, platform_name="darwin") is True
    ns_app = mock.Mock()
    ns_app.activateWithOptions_.return_value = True
    assert paster.restore_previous_app(ns_app, platform_name="darwin") is True

    if orig_display:
        monkeypatch.setenv("DISPLAY", orig_display)
    else:
        monkeypatch.delenv("DISPLAY", raising=False)

    if sys.platform != "win32" and not orig_display:
        fake_kb = SimpleNamespace(Controller=lambda: "FAKE_CTRL", Key=_FAKE_KEYS)
        with mock.patch.dict("sys.modules", {"pynput": SimpleNamespace(keyboard=fake_kb), "pynput.keyboard": fake_kb}):
            ctrl_real, key_real = paster._get_pynput_controller()
        assert ctrl_real == "FAKE_CTRL" and hasattr(key_real, "enter")
    else:
        ctrl_real, key_real = paster._get_pynput_controller()
        assert ctrl_real is not None and hasattr(key_real, "enter")

    fake_k32 = mock.Mock()
    fake_k32.GlobalAlloc.return_value = 100
    fake_k32.GlobalLock.return_value = 200
    fake_u32 = mock.Mock()
    fake_u32.OpenClipboard.return_value = 1
    fake_u32.SetClipboardData.return_value = 1
    with mock.patch.object(paster.ctypes, "windll", SimpleNamespace(user32=fake_u32, kernel32=fake_k32), create=True), \
         mock.patch.object(paster.ctypes, "memmove"):
        assert paster._copy_windows_ctypes("TestWin") is True

    fake_pb = mock.Mock()
    fake_pb.setString_forType_.return_value = True
    fake_appkit = SimpleNamespace(NSPasteboard=SimpleNamespace(generalPasteboard=lambda: fake_pb), NSStringPboardType="str")
    with mock.patch.dict("sys.modules", {"AppKit": fake_appkit}):
        assert paster._copy_macos_native("TestMac") is True

    fake_x11 = mock.Mock()
    fake_x11.XOpenDisplay.return_value = 1
    fake_x11.XInternAtom.return_value = 2
    monkeypatch.setenv("DISPLAY", ":0")
    with mock.patch("qtp_app.core.paster.ctypes.CDLL", return_value=fake_x11):
        assert paster._copy_linux_x11_ctypes("TestX11") is True

    fake_k32_fail = mock.Mock()
    fake_k32_fail.GlobalAlloc.return_value = 0
    with mock.patch.object(paster.ctypes, "windll", SimpleNamespace(user32=fake_u32, kernel32=fake_k32_fail), create=True):
        assert paster._copy_windows_ctypes("Fail") is False

    fake_u32_closed = mock.Mock()
    fake_u32_closed.OpenClipboard.return_value = 0
    with mock.patch.object(paster.ctypes, "windll", SimpleNamespace(user32=fake_u32_closed, kernel32=fake_k32), create=True), \
         mock.patch.object(paster.ctypes, "memmove"), \
         mock.patch("qtp_app.core.paster.time.sleep"):
        assert paster._copy_windows_ctypes("Locked") is False

    fake_u32_setfail = mock.Mock()
    fake_u32_setfail.OpenClipboard.return_value = 1
    fake_u32_setfail.SetClipboardData.return_value = 0
    with mock.patch.object(paster.ctypes, "windll", SimpleNamespace(user32=fake_u32_setfail, kernel32=fake_k32), create=True), \
         mock.patch.object(paster.ctypes, "memmove"):
        assert paster._copy_windows_ctypes("SetFail") is False

    fake_qt_clip = mock.Mock()
    with mock.patch("PyQt6.QtGui.QGuiApplication.instance", return_value=SimpleNamespace(clipboard=lambda: fake_qt_clip)), \
         mock.patch.dict(paster.os.environ, {"DISPLAY": ":0", "QT_QPA_PLATFORM": "xcb"}):
        assert paster._copy_linux_x11_ctypes("QtLinux") is True
        fake_qt_clip.setText.assert_called_once_with("QtLinux")

    with mock.patch("subprocess.run", side_effect=RuntimeError("osascript fail")):
        assert paster.capture_previous_app(platform_name="darwin") is None
        assert paster.restore_previous_app(4321, platform_name="darwin") is False
    with mock.patch("qtp_app.core.paster.sys.platform", "freebsd"):
        assert paster.is_wayland_session() is False

    bad_qt_cb = mock.Mock()
    bad_qt_cb.setText.side_effect = RuntimeError("qt err")
    good_qgui_cb = mock.Mock()
    with mock.patch("qtp_app.core.paster._copy_windows_ctypes", side_effect=RuntimeError("win err")), \
         mock.patch("PyQt6.QtGui.QGuiApplication.instance", return_value=SimpleNamespace(clipboard=lambda: good_qgui_cb)):
        assert paster.copy_to_clipboard("QGuiFallback", qt_clipboard=bad_qt_cb, platform_name="win32") is True
        good_qgui_cb.setText.assert_called_once_with("QGuiFallback")

    fake_pyper = mock.Mock()
    with mock.patch("qtp_app.core.paster._copy_windows_ctypes", return_value=False), \
         mock.patch("PyQt6.QtGui.QGuiApplication.instance", return_value=None), \
         mock.patch.dict("sys.modules", {"pyperclip": fake_pyper}):
        assert paster.copy_to_clipboard("OptFallback", platform_name="win32") is True
        fake_pyper.copy.assert_called_once_with("OptFallback")

    fake_ak = SimpleNamespace(NSWorkspace=SimpleNamespace(sharedWorkspace=lambda: SimpleNamespace(frontmostApplication=lambda: "AK_APP")))
    with mock.patch.dict("sys.modules", {"AppKit": fake_ak}):
        assert paster.capture_previous_app(platform_name="darwin") == "AK_APP"
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.delenv("XDG_SESSION_TYPE", raising=False)
    assert paster.capture_previous_app(platform_name="freebsd") is None
    assert paster.restore_previous_app("123", platform_name="freebsd") is False
    with mock.patch("shutil.which", return_value="/usr/bin/pbcopy"), \
         mock.patch("subprocess.run", side_effect=RuntimeError("pbcopy err")):
        assert paster._copy_macos_native("FailMac") is False


def test_bsd_unix_posix_and_macos_pasteboard_fallback(monkeypatch):
    for bsd_plat in ("freebsd14", "openbsd7", "netbsd10"):
        assert paster.is_posix_desktop(bsd_plat) is True
        monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-1")
        assert paster.is_wayland_session(bsd_plat) is True
        monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)

        monkeypatch.setenv("DISPLAY", ":0")
        monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
        fake_x11 = mock.Mock()
        fake_x11.XOpenDisplay.return_value = 77
        fake_x11.XInternAtom.return_value = 9
        calls = []

        def fake_cdll(name: str):
            calls.append(name)
            if name == "libX11.so.6":
                raise OSError("not found")
            return fake_x11

        with mock.patch("qtp_app.core.paster.ctypes.CDLL", side_effect=fake_cdll):
            assert paster.copy_to_clipboard("BSD Test", platform_name=bsd_plat) is True
        assert calls == ["libX11.so.6", "libX11.so"]

        with mock.patch("shutil.which", side_effect=lambda name: "/usr/local/bin/wtype" if name == "wtype" else None), \
             mock.patch("subprocess.run") as wl_run, \
             mock.patch("qtp_app.core.paster.copy_to_clipboard", return_value=True):
            res = paster.paste_into_active_app(
                "Wayland BSD",
                has_end_marker=True,
                enter_after_paste=True,
                delay_ms=0,
                platform_name=bsd_plat,
                wayland=True,
                sleep_fn=lambda _s: None,
            )
        assert res.ok is True and res.method == "wtype" and wl_run.call_count == 2

    pb_modern = mock.Mock()
    pb_modern.setString_forType_.side_effect = [False, True]
    appkit_both = SimpleNamespace(
        NSPasteboard=SimpleNamespace(generalPasteboard=lambda: pb_modern),
        NSPasteboardTypeString="public.utf8-plain-text",
        NSStringPboardType="NSStringPboardType",
    )
    with mock.patch.dict("sys.modules", {"AppKit": appkit_both}):
        assert paster._copy_macos_native("ModernThenLegacy") is True
    assert [c.args[1] for c in pb_modern.setString_forType_.call_args_list] == [
        "public.utf8-plain-text",
        "NSStringPboardType",
    ]


