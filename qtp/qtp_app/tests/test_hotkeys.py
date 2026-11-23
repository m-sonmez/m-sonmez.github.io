"""Global kısayol kaydı, yeniden kayıt ve platform geri dönüş testleri."""

from __future__ import annotations

from unittest import mock

from qtp_app.core.hotkeys import (
    HotkeyManager,
    check_macos_accessibility,
    to_keyboard_lib_combo,
    to_pynput_combo,
)
from qtp_app.core.settings import DEFAULT_HOTKEYS


def test_combo_conversion_helpers():
    assert to_pynput_combo("Win+A") == "<cmd>+a"
    assert to_pynput_combo("L-Win+Z") == "<cmd>+z"
    assert to_pynput_combo("Ctrl+Shift+Space") == "<ctrl>+<shift>+<space>"
    assert to_keyboard_lib_combo("Win+Q") == "windows+q"
    assert to_keyboard_lib_combo("Ctrl+Shift+Space") == "ctrl+shift+space"


def test_register_all_five_hotkeys_on_host_os():
    mgr = HotkeyManager()
    triggered: list[str] = []
    try:
        res = mgr.register(DEFAULT_HOTKEYS, triggered.append)
        assert set(res.keys()) == {"all", "A", "Z", "X", "Q"}
        assert all(res.values())
        assert set(mgr.registered_hotkeys.keys()) == {"all", "A", "Z", "X", "Q"}
    finally:
        mgr.unregister()
    assert mgr.registered_hotkeys == {}


def test_reregister_unbinds_old_listener_without_duplicates():
    listeners: list[mock.Mock] = []

    def fake_factory(mapping):
        lst = mock.Mock()
        lst.mapping = mapping
        listeners.append(lst)
        return lst

    mgr = HotkeyManager(pynput_factory=fake_factory, platform_name="win32")
    mgr.register({"A": "Win+A", "Z": "Win+Z"}, lambda _c: None)
    assert len(listeners) == 1
    assert "<cmd>+a" in listeners[0].mapping

    mgr.register({"A": "Ctrl+Alt+A", "Z": "Win+Z"}, lambda _c: None)
    listeners[0].stop.assert_called_once()
    assert len(listeners) == 2
    assert "<cmd>+a" not in listeners[1].mapping
    assert "<ctrl>+<alt>+a" in listeners[1].mapping

    mgr.unregister()
    listeners[1].stop.assert_called_once()


def test_windows_keyboard_fallback_when_pynput_fails():
    fake_kb = mock.Mock()
    fake_kb.add_hotkey.side_effect = ["h1", "h2", "h3", "h4", "h5"]

    def failing_factory(_mapping):
        raise RuntimeError("Windows hook engellendi")

    mgr = HotkeyManager(
        pynput_factory=failing_factory,
        keyboard_module=fake_kb,
        platform_name="win32",
    )
    res = mgr.register(DEFAULT_HOTKEYS, lambda _c: None)
    assert all(res.values())
    assert fake_kb.add_hotkey.call_count == 5

    mgr.unregister()
    assert fake_kb.remove_hotkey.call_count == 5


def test_macos_accessibility_check_non_darwin_returns_true():
    with mock.patch("qtp_app.core.hotkeys.sys.platform", "linux"):
        assert check_macos_accessibility(prompt=False) is True


def test_hotkeys_error_paths_and_macos_accessibility_mocked():
    import pytest

    with pytest.raises(ValueError):
        to_pynput_combo("")
    assert to_pynput_combo("Ctrl+F1") == "<ctrl>+<f1>"

    mgr = HotkeyManager(pynput_factory=lambda _m: mock.Mock(), platform_name="linux")
    res_empty = mgr.register({"A": "", "Z": "   "}, lambda _c: None)
    assert res_empty == {"A": False, "Z": False}

    mgr_linux_fail = HotkeyManager(
        pynput_factory=lambda _m: (_ for _ in ()).throw(RuntimeError("X11 error")),
        platform_name="linux",
    )
    res_fail = mgr_linux_fail.register({"A": "Win+A"}, lambda _c: None)
    assert res_fail == {"A": False}

    mgr_win_no_kb = HotkeyManager(
        pynput_factory=lambda _m: (_ for _ in ()).throw(RuntimeError("Win hook error")),
        keyboard_module=None,
        platform_name="win32",
    )
    with mock.patch.dict("sys.modules", {"keyboard": None}):
        res_win_fail = mgr_win_no_kb.register({"A": "Win+A"}, lambda _c: None)
    assert res_win_fail == {"A": False}

    fake_app_svc = mock.Mock()
    fake_app_svc.AXIsProcessTrusted.return_value = False
    fake_app_svc.AXIsProcessTrustedWithOptions.return_value = True
    fake_cf = mock.Mock()
    fake_cf.CFStringCreateWithCString.return_value = 111
    fake_cf.CFDictionaryCreate.return_value = 222

    def fake_cdll(path: str):
        if "ApplicationServices" in path:
            return fake_app_svc
        return fake_cf

    with mock.patch("qtp_app.core.hotkeys.sys.platform", "darwin"), \
         mock.patch("qtp_app.core.hotkeys.ctypes.CDLL", side_effect=fake_cdll), \
         mock.patch("qtp_app.core.hotkeys.ctypes.c_void_p.in_dll", return_value=333):
        assert check_macos_accessibility(prompt=False) is False
        assert check_macos_accessibility(prompt=True) is True

    mgr_wl = HotkeyManager(
        pynput_factory=lambda _m: (_ for _ in ()).throw(RuntimeError("Wayland no X11")),
        platform_name="linux",
    )
    with mock.patch("qtp_app.core.hotkeys.is_wayland_session", return_value=True):
        assert mgr_wl.register({"all": "Ctrl+Shift+Space"}, lambda _c: None) == {"all": False}

    assert mgr_wl.register({"A": "Win+A"}, lambda _c: None) == {"A": False}

    bad_listener = mock.Mock()
    bad_listener.stop.side_effect = RuntimeError("stop err")
    bad_kb = mock.Mock()
    bad_kb.remove_hotkey.side_effect = RuntimeError("remove err")
    for bsd_plat in ("freebsd14", "openbsd7"):
        mgr_bsd = HotkeyManager(
            pynput_factory=lambda _m: (_ for _ in ()).throw(RuntimeError("Wayland no X11")),
            platform_name=bsd_plat,
        )
        with mock.patch("qtp_app.core.hotkeys.is_wayland_session", return_value=True):
            assert mgr_bsd.register({"all": "Ctrl+Shift+Space"}, lambda _c: None) == {"all": False}

    mgr_err = HotkeyManager(pynput_factory=lambda _m: bad_listener, keyboard_module=bad_kb, platform_name="win32")
    mgr_err.register({"A": "Win+A"}, lambda _c: None)
    mgr_err._keyboard_handles.append("hk1")
    mgr_err.unregister()
    with mock.patch("qtp_app.core.hotkeys.sys.platform", "darwin"), \
         mock.patch("qtp_app.core.hotkeys.ctypes.CDLL", side_effect=OSError("no framework")):
        assert check_macos_accessibility(prompt=False) is False


