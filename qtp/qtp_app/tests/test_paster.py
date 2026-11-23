"""Pano kopyalama, yapıştırma tuş sırası (<E<N<D| -> Enter) ve Wayland testleri."""

from __future__ import annotations

import logging
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
    assert res.copied is True
    assert res.pasted is True
    assert res.enter_sent is True
    assert hidden == [True]
    copy_mock.assert_called_once_with("Merhaba dünya", qt_clipboard=None)
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


def test_wayland_uses_wtype_when_available_and_warns_otherwise(caplog):
    # 1. wtype mevcutsa doğrudan wtype çağrılmalı
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

    # 2. wtype ve ydotool yoksa uyarı günlüğü basıp pynput geri dönüşüne geçmeli
    ctrl = _FakeController()
    caplog.set_level(logging.WARNING)
    with mock.patch("qtp_app.core.paster.copy_to_clipboard", return_value=True), \
         mock.patch("shutil.which", return_value=None):
        res_fb = paster.paste_into_active_app(
            "Fallback metin",
            has_end_marker=False,
            delay_ms=0,
            controller=ctrl,
            key_enum=_FAKE_KEYS,
            platform_name="linux",
            wayland=True,
            sleep_fn=lambda _s: None,
        )
    assert res_fb.ok is True
    assert res_fb.warning is not None and "wtype" in res_fb.warning
    assert ("press", "CTRL") in ctrl.events


def test_copy_to_clipboard_falls_back_to_qt():
    fake_qt_cb = mock.Mock()
    with mock.patch("pyperclip.copy", side_effect=RuntimeError("no xclip")):
        ok = paster.copy_to_clipboard("Qt pano testi", qt_clipboard=fake_qt_cb)
    assert ok is True
    fake_qt_cb.setText.assert_called_once_with("Qt pano testi")


def test_wayland_ydotool_and_clipboard_failure(caplog):
    with mock.patch("qtp_app.core.paster.copy_to_clipboard", return_value=False):
        res_fail = paster.paste_into_active_app("Metin", delay_ms=0, sleep_fn=lambda _s: None)
    assert res_fail.ok is False
    assert res_fail.method == "clipboard_error"

    # ydotool fallback on Wayland
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

    # wtype type & shift_insert branches
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

    # Controller raising exception returns ok=False, copied=True
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
    assert res_err.copied is True
    assert res_err.method == "error"


def test_capture_and_restore_previous_app_platforms(monkeypatch):
    # Wayland detection
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    with mock.patch("qtp_app.core.paster.sys.platform", "linux"):
        assert paster.is_wayland_session() is True
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.setenv("XDG_SESSION_TYPE", "x11")
    with mock.patch("qtp_app.core.paster.sys.platform", "linux"):
        assert paster.is_wayland_session() is False

    # Windows win32 mocked user32
    fake_user32 = mock.Mock()
    fake_user32.GetForegroundWindow.return_value = 12345
    fake_user32.IsIconic.return_value = True
    fake_user32.SetForegroundWindow.return_value = 1
    fake_windll = SimpleNamespace(user32=fake_user32)
    with mock.patch.object(paster.ctypes, "windll", fake_windll, create=True):
        hwnd = paster.capture_previous_app(platform_name="win32")
        assert hwnd == 12345
        assert paster.restore_previous_app(hwnd, platform_name="win32") is True
        fake_user32.ShowWindow.assert_called_once_with(12345, 9)
        fake_user32.SetForegroundWindow.assert_called_once_with(12345)

    assert paster.restore_previous_app(None, platform_name="win32") is False

    # Linux xdotool & wmctrl
    with mock.patch("shutil.which", side_effect=lambda n: "/usr/bin/xdotool" if n == "xdotool" else None), \
         mock.patch("subprocess.run", return_value=SimpleNamespace(returncode=0, stdout="98765\n")):
        wid = paster.capture_previous_app(platform_name="linux")
        assert wid == "98765"
        assert paster.restore_previous_app("98765", platform_name="linux") is True

    with mock.patch("shutil.which", side_effect=lambda n: "/usr/bin/wmctrl" if n == "wmctrl" else None), \
         mock.patch("subprocess.run", return_value=SimpleNamespace(returncode=0, stdout="")):
        assert paster.restore_previous_app("98765", platform_name="linux") is True

    # macOS osascript fallback + NSRunningApplication handle
    with mock.patch("subprocess.run", return_value=SimpleNamespace(returncode=0, stdout="4321\n")):
        pid = paster.capture_previous_app(platform_name="darwin")
        assert pid == 4321
        assert paster.restore_previous_app(4321, platform_name="darwin") is True

    ns_app = mock.Mock()
    ns_app.activateWithOptions_.return_value = True
    assert paster.restore_previous_app(ns_app, platform_name="darwin") is True

    # AppKit macOS capture path & previous_app restore inside paste_into_active_app
    fake_appkit = SimpleNamespace(
        NSWorkspace=SimpleNamespace(sharedWorkspace=lambda: SimpleNamespace(frontmostApplication=lambda: "NS_APP"))
    )
    with mock.patch.dict("sys.modules", {"AppKit": fake_appkit}):
        assert paster.capture_previous_app(platform_name="darwin") == "NS_APP"

    ctrl2 = _FakeController()
    with mock.patch("qtp_app.core.paster.copy_to_clipboard", return_value=True), \
         mock.patch("qtp_app.core.paster.restore_previous_app") as rest_mock:
        paster.paste_into_active_app(
            "X",
            previous_app=555,
            delay_ms=10,
            controller=ctrl2,
            key_enum=_FAKE_KEYS,
            platform_name="win32",
            wayland=False,
            sleep_fn=lambda _s: None,
        )
    rest_mock.assert_called_once_with(555, platform_name="win32")

    # copy_to_clipboard QGuiApplication.instance() fallback when qt_clipboard=None
    fake_cb = mock.Mock()
    fake_qapp = SimpleNamespace(clipboard=lambda: fake_cb)
    with mock.patch("pyperclip.copy", side_effect=RuntimeError("no pyperclip")), \
         mock.patch("PyQt6.QtGui.QGuiApplication.instance", return_value=fake_qapp):
        assert paster.copy_to_clipboard("FallbackQt") is True
        fake_cb.setText.assert_called_once_with("FallbackQt")

    # _get_pynput_controller gerçek pynput yüklemesi ve hata yakalama
    ctrl_real, key_real = paster._get_pynput_controller()
    assert ctrl_real is not None and hasattr(key_real, "enter")
    assert paster.capture_previous_app(platform_name="freebsd") is None
    with mock.patch("subprocess.run", side_effect=RuntimeError("fail")):
        assert paster.capture_previous_app(platform_name="darwin") is None
        assert paster.restore_previous_app("123", platform_name="linux") is False



