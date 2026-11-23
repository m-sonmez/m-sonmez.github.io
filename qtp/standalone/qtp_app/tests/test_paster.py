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


def test_wayland_uses_wtype_when_available_and_warns_otherwise(capsys, monkeypatch):
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
    assert run_mock.call_args_list[0][0][0] == ["/usr/bin/wtype", "-M", "ctrl", "-k", "v", "-m", "ctrl"]
    assert run_mock.call_args_list[1][0][0] == ["/usr/bin/wtype", "-k", "Return"]

    monkeypatch.setenv("DISPLAY", ":0")
    capsys.readouterr()
    with mock.patch("qtp_app.core.paster.copy_to_clipboard", return_value=True), \
         mock.patch("shutil.which", return_value=None), \
         mock.patch("qtp_app.core.paster._get_pynput_controller") as pynput_mock:
        res_fb = paster.paste_into_active_app(
            "Fallback metin",
            has_end_marker=False,
            delay_ms=0,
            platform_name="linux",
            wayland=True,
            sleep_fn=lambda _s: None,
        )
    err_out = capsys.readouterr().err
    assert res_fb.ok is False
    assert res_fb.exit_code == 4
    assert res_fb.method == "wayland_unavailable"
    assert res_fb.warning == paster.WAYLAND_COPY_ONLY_MSG
    assert paster.WAYLAND_UNAVAILABLE_LOG in err_out
    pynput_mock.assert_not_called()


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
        paster.paste_into_active_app(
            "C", paste_method="ctrl_shift_v", delay_ms=0, platform_name="linux", wayland=True, sleep_fn=lambda _s: None
        )
        paster.paste_into_active_app(
            "D", paste_method="auto", previous_app="org.kde.konsole", delay_ms=0, platform_name="linux", wayland=True, sleep_fn=lambda _s: None
        )
    assert run_mock2.call_args_list[0][0][0] == ["/usr/bin/wtype", "--", "A"]
    assert run_mock2.call_args_list[1][0][0] == ["/usr/bin/wtype", "-M", "shift", "-k", "Insert", "-m", "shift"]
    assert run_mock2.call_args_list[2][0][0] == ["/usr/bin/wtype", "-M", "ctrl", "-M", "shift", "-k", "v", "-m", "shift", "-m", "ctrl"]
    assert run_mock2.call_args_list[3][0][0] == ["/usr/bin/wtype", "-M", "ctrl", "-M", "shift", "-k", "v", "-m", "shift", "-m", "ctrl"]

    ctrl_term = _FakeController()
    with mock.patch("qtp_app.core.paster.copy_to_clipboard", return_value=True) as pre_copy_mock:
        res_term = paster.paste_into_active_app(
            "Uçbirim",
            previous_app={"app_id": "com.mitchellh.ghostty"},
            paste_method="auto",
            already_copied=True,
            delay_ms=0,
            controller=ctrl_term,
            key_enum=_FAKE_KEYS,
            platform_name="linux",
            wayland=False,
            sleep_fn=lambda _s: None,
        )
    pre_copy_mock.assert_not_called()
    assert res_term.ok is True and res_term.method == "ctrl_shift_v"
    assert ctrl_term.events[:4] == [("press", "CTRL"), ("press", "SHIFT"), ("press", "v"), ("release", "v")]

    with mock.patch("qtp_app.core.paster.copy_to_clipboard", return_value=True), \
         mock.patch("shutil.which", side_effect=lambda name: f"/usr/bin/{name}" if name in ("wtype", "ydotool") else None), \
         mock.patch("subprocess.run", side_effect=[SimpleNamespace(returncode=1), SimpleNamespace(returncode=0)]) as fb_run:
        res_wfail = paster.paste_into_active_app(
            "FallbackYdo",
            paste_method="auto",
            delay_ms=0,
            platform_name="linux",
            wayland=True,
            sleep_fn=lambda _s: None,
        )
    assert res_wfail.ok is True and res_wfail.method == "ydotool"
    assert fb_run.call_count == 2

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

    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    with mock.patch("shutil.which", side_effect=lambda name: "/usr/bin/wl-copy" if name == "wl-copy" else None), \
         mock.patch("subprocess.run", return_value=SimpleNamespace(returncode=0)) as wl_copy_run:
        assert paster._copy_linux_x11_ctypes("TestWaylandCopy", platform_name="linux") is True
    assert wl_copy_run.call_args[0][0] == ["/usr/bin/wl-copy"]
    assert wl_copy_run.call_args.kwargs.get("start_new_session") is True

    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.setenv("XDG_SESSION_TYPE", "x11")
    monkeypatch.setenv("DISPLAY", ":0")
    with mock.patch("shutil.which", side_effect=lambda name: "/usr/bin/xclip" if name == "xclip" else None), \
         mock.patch("subprocess.run", return_value=SimpleNamespace(returncode=0)) as xclip_run:
        assert paster._copy_linux_x11_ctypes("TestX11Clip", platform_name="linux") is True
    assert xclip_run.call_args[0][0] == ["/usr/bin/xclip", "-selection", "clipboard"]

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
        with mock.patch("shutil.which", side_effect=lambda name: "/usr/local/bin/xsel" if name == "xsel" else None), \
             mock.patch("subprocess.run", return_value=SimpleNamespace(returncode=0)) as bsd_clip_run:
            assert paster.copy_to_clipboard("BSD Test", platform_name=bsd_plat) is True
        assert bsd_clip_run.call_args[0][0] == ["/usr/local/bin/xsel", "--clipboard", "--input"]
        assert paster.is_terminal_window("konsole", platform_name=bsd_plat) is True
        assert paster.is_terminal_window("firefox", platform_name=bsd_plat) is False

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


def test_paster_terminal_detection_ydotool_and_qt_selection_coverage(monkeypatch):
    assert paster.is_wayland_session("win32") is False
    assert paster.is_terminal_window(None, platform_name="linux") is False
    assert paster.is_terminal_window("konsole", platform_name="win32") is False
    assert paster.is_terminal_window("st", platform_name="linux") is True
    assert paster.is_terminal_window("firefox", platform_name="linux") is False
    assert paster.is_terminal_window({"app_id": "org.wezfurlong.wezterm"}, platform_name="linux") is True
    assert paster.is_terminal_window({"wm_class": "chromium"}, platform_name="linux") is False
    assert paster.is_terminal_window(SimpleNamespace(wm_class="kitty"), platform_name="linux") is True
    assert paster.is_terminal_window(SimpleNamespace(wm_class="gedit"), platform_name="linux") is False

    root_win = mock.Mock()
    root_win.id = 1
    parent_win = mock.Mock()
    parent_win.get_wm_class.return_value = ("Alacritty", "Alacritty")
    parent_win.get_wm_name.return_value = "Alacritty"
    child_win = mock.Mock()
    child_win.get_wm_class.return_value = None
    child_win.get_wm_name.return_value = None
    child_win.query_tree.return_value = SimpleNamespace(parent=parent_win, root=root_win)
    fake_dpy = mock.Mock()
    fake_dpy.create_resource_object.return_value = child_win
    fake_xlib = SimpleNamespace(display=SimpleNamespace(Display=lambda: fake_dpy))
    monkeypatch.setenv("DISPLAY", ":0")
    with mock.patch.dict("sys.modules", {"Xlib": fake_xlib, "Xlib.display": fake_xlib.display}):
        assert paster.is_terminal_window(555, platform_name="linux") is True
    fake_dpy.close.assert_called_once()

    sel_cb = mock.Mock()
    sel_cb.supportsSelection.return_value = True
    fake_app = mock.Mock()
    fake_app.platformName.return_value = "wayland"
    fake_app.clipboard.return_value = sel_cb
    with mock.patch("PyQt6.QtGui.QGuiApplication.instance", return_value=fake_app):
        assert paster._copy_posix_clipboard("LiveQt", platform_name="linux") is True
    assert sel_cb.setText.call_count == 2
    fake_app.processEvents.assert_called_once()

    with mock.patch("subprocess.run", return_value=SimpleNamespace(returncode=1)):
        assert paster._run_clipboard_daemon_cmd(["wl-copy"], "x") is False
    with mock.patch("subprocess.run", side_effect=OSError("boom")):
        assert paster._run_clipboard_daemon_cmd(["wl-copy"], "x") is False

    bad_stream = SimpleNamespace(isatty=lambda: (_ for _ in ()).throw(RuntimeError("tty err")))
    with mock.patch.object(sys, "stdout", bad_stream):
        assert paster._emit_osc52("fail") is False

    with mock.patch("shutil.which", side_effect=lambda name: "/usr/bin/ydotool" if name == "ydotool" else None), \
         mock.patch("subprocess.run", return_value=SimpleNamespace(returncode=0)) as ydo_run:
        assert paster._paste_wayland("T", method="type", send_enter=False)[0] is True
        assert paster._paste_wayland("T", method="ctrl_shift_v", send_enter=False)[0] is True
        assert paster._paste_wayland("T", method="shift_insert", send_enter=False)[0] is True
    assert ydo_run.call_args_list[0][0][0] == ["/usr/bin/ydotool", "type", "--", "T"]
    assert ydo_run.call_args_list[1][0][0][1] == "key"
    assert ydo_run.call_args_list[2][0][0][1] == "key"

    with mock.patch("shutil.which", side_effect=lambda name: "/usr/bin/ydotool" if name == "ydotool" else None), \
         mock.patch("subprocess.run", return_value=SimpleNamespace(returncode=2)):
        ok_fail, meth_fail, _ = paster._paste_wayland("T", method="ctrl_v", send_enter=False)
    assert ok_fail is False and meth_fail == "wayland_unavailable"

    with mock.patch("qtp_app.core.paster._copy_posix_clipboard", return_value=True), \
         mock.patch("qtp_app.core.paster.restore_previous_app", return_value=True) as rest_mock, \
         mock.patch("qtp_app.core.paster.shutil.which", side_effect=lambda name: "/usr/bin/ydotool" if name == "ydotool" else None), \
         mock.patch("qtp_app.core.paster.subprocess.run", return_value=SimpleNamespace(returncode=0)):
        slept: list[float] = []
        res_ok = paster.paste_into_active_app(
            "OK",
            has_end_marker=True,
            enter_after_paste=True,
            hide_overlay_cb=lambda: (_ for _ in ()).throw(RuntimeError("hide err")),
            previous_app="konsole",
            delay_ms=10,
            platform_name="linux",
            wayland=True,
            sleep_fn=slept.append,
        )
    assert res_ok.ok is True and res_ok.method == "ydotool"
    rest_mock.assert_called_once()
    assert 0.01 in slept

    ctrl_auto = _FakeController()
    with mock.patch("qtp_app.core.paster._get_pynput_controller", return_value=(ctrl_auto, _FAKE_KEYS)):
        res_auto = paster.paste_into_active_app(
            "Pre",
            already_copied=True,
            delay_ms=0,
            platform_name="linux",
            wayland=False,
            sleep_fn=lambda _s: None,
        )
    assert res_auto.ok is True and res_auto.copied is True and res_auto.method == "ctrl_v"
