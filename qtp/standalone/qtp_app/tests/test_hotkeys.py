"""Global kısayol kaydı, 15 değiştirici bileşimi, Win32 RegisterHotKey, çakışma denetimi ve geri dönüş testleri."""

from __future__ import annotations

import itertools
import os
import sys
from pathlib import Path
from unittest import mock

import pytest

from qtp_app.core.hotkeys import (
    CANONICAL_MODIFIERS,
    ERROR_HOTKEY_ALREADY_REGISTERED,
    HOTKEY_PRESETS,
    MOD_ALT,
    MOD_CONTROL,
    MOD_NOREPEAT,
    MOD_SHIFT,
    MOD_WIN,
    WM_HOTKEY,
    HotkeyManager,
    apply_modifier_combo,
    build_preset_hotkeys,
    check_macos_accessibility,
    detect_hotkey_conflicts,
    normalize_hotkey,
    parse_hotkey,
    parse_modifiers,
    read_kde_global_shortcuts,
    resolve_preset_name,
    to_keyboard_lib_combo,
    to_pynput_combo,
    to_win32_hotkey,
)
from qtp_app.core.settings import DEFAULT_HOTKEYS

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent


def _all_15_modifier_combos() -> list[tuple[str, ...]]:
    out: list[tuple[str, ...]] = []
    for r in range(1, len(CANONICAL_MODIFIERS) + 1):
        out.extend(itertools.combinations(CANONICAL_MODIFIERS, r))
    return out


@pytest.mark.parametrize("mods", _all_15_modifier_combos())
def test_all_15_modifier_combinations_parse_win32_and_pynput(mods: tuple[str, ...]):
    scrambled = "+".join(reversed(mods)) + "+A"
    parsed_mods, key = parse_hotkey(scrambled)
    assert parsed_mods == mods
    assert key == "A"

    norm = normalize_hotkey(scrambled)
    assert norm == "+".join([*mods, "A"])

    bitmask, vk = to_win32_hotkey(norm)
    expected_mask = MOD_NOREPEAT
    if "Win" in mods:
        expected_mask |= MOD_WIN
    if "Ctrl" in mods:
        expected_mask |= MOD_CONTROL
    if "Alt" in mods:
        expected_mask |= MOD_ALT
    if "Shift" in mods:
        expected_mask |= MOD_SHIFT
    assert bitmask == expected_mask
    assert vk == ord("A")

    py_combo = to_pynput_combo(norm)
    assert py_combo.endswith("+a")


def test_combo_conversion_helpers_and_special_keys():
    assert to_pynput_combo("Win+A") == "<cmd>+a"
    assert to_pynput_combo("L-Win+Z") == "<cmd>+z"
    assert to_pynput_combo("Ctrl+Shift+Space") == "<ctrl>+<shift>+<space>"
    assert normalize_hotkey("alt+shift+ctrl+z") == "Ctrl+Alt+Shift+Z"
    assert normalize_hotkey("cmd+ctrl+x") == "Win+Ctrl+X"
    assert to_keyboard_lib_combo("Win+Q") == "windows+q"
    assert to_keyboard_lib_combo("Ctrl+Shift+Space") == "ctrl+shift+space"

    for special, expected_norm in (
        ("Win+Ctrl+Tab", "Win+Ctrl+Tab"),
        ("Ctrl+Shift+Numpad0", "Ctrl+Shift+Numpad0"),
        ("Alt+PageUp", "Alt+PageUp"),
        ("Ctrl+-", "Ctrl+-"),
        ("Win+Alt+=", "Win+Alt+="),
        ("Ctrl+F12", "Ctrl+F12"),
    ):
        assert normalize_hotkey(special) == expected_norm
        _mask, vk = to_win32_hotkey(special)
        assert vk > 0


def test_invalid_hotkeys_and_modifiers_raise_turkish_errors_matching_sss():
    sss = (ROOT_DIR / "docs" / "SSS.md").read_text(encoding="utf-8")
    for bad in ("", "Ctrl+Alt", "UnknownKey+A", "A", "Ctrl+A+B", "Ctrl++A"):
        with pytest.raises(ValueError) as exc_info:
            parse_hotkey(bad)
        msg = str(exc_info.value)
        assert (
            "Boş kısayol dizesi kullanılamaz." in msg
            or "değiştirici tuşlar tek başına kullanılamaz" in msg
            or "bilinmeyen tuş" in msg
            or "en az bir değiştirici tuş" in msg
            or "Geçersiz kısayol tanımı" in msg
        )
    assert "Boş kısayol dizesi kullanılamaz." in sss
    assert "değiştirici tuşlar tek başına kullanılamaz" in sss

    with pytest.raises(ValueError):
        parse_modifiers("")
    with pytest.raises(ValueError):
        parse_modifiers("Ctrl++Alt")
    with pytest.raises(ValueError):
        parse_modifiers("Ctrl+F1")
    with pytest.raises(ValueError):
        resolve_preset_name("olmayan_profil")
    assert resolve_preset_name("triple_mod") == "ctrl_shift_alt"


def test_apply_modifier_combo_preserves_trigger_keys_and_custom_slots():
    base = {
        "all": "Win+Alt+Space",
        "A": "Win+Alt+A",
        "Z": "",
        "W": "Ctrl+W",
    }
    for mods in ("Ctrl", "Ctrl+Alt", "Win", "Win+Ctrl", "Win+Alt", "Ctrl+Shift+Alt"):
        rewritten = apply_modifier_combo(base, mods)
        expected_prefix = "+".join(parse_modifiers(mods))
        assert rewritten["all"] == f"{expected_prefix}+Space"
        assert rewritten["A"] == f"{expected_prefix}+A"
        assert rewritten["Z"] == ""
        assert rewritten["W"] == f"{expected_prefix}+W"


def test_detect_hotkey_conflicts_cross_os_and_presets():
    for plat in ("win32", "linux", "freebsd14"):
        assert detect_hotkey_conflicts(HOTKEY_PRESETS["recommended"], platform_name=plat) == {}
    for plat in ("win32", "linux", "freebsd14", "darwin"):
        assert detect_hotkey_conflicts(HOTKEY_PRESETS["function_keys"], platform_name=plat) == {}

    legacy_dynamic = build_preset_hotkeys("legacy_win", ("all", "A", "Z", "X", "Q"))
    win_conflicts = detect_hotkey_conflicts(legacy_dynamic, platform_name="win32")
    for k in ("A", "Z", "X", "Q"):
        assert k in win_conflicts

    wctrl_dynamic = build_preset_hotkeys("win_ctrl", ("all", "A", "Q"))
    wctrl_conflicts = detect_hotkey_conflicts(wctrl_dynamic, platform_name="win32")
    assert "all" in wctrl_conflicts and "Q" in wctrl_conflicts
    assert "A" not in wctrl_conflicts

    trq = detect_hotkey_conflicts(
        {"all": "Ctrl+Alt+Space", "A": "Ctrl+Alt+A", "Q": "Ctrl+Alt+Q", "E": "Ctrl+Alt+E"},
        platform_name="win32",
        language="tr",
    )
    assert "AltGr+A" in trq["A"][0]
    assert "AltGr+Q" in trq["Q"][0]
    assert "AltGr+E" in trq["E"][0]
    assert "all" not in trq

    en_altgr = detect_hotkey_conflicts({"Q": "Ctrl+Alt+Q"}, platform_name="win32", language="en")
    assert "AltGr" in en_altgr["Q"][0] and "Türkçe-Q" not in en_altgr["Q"][0]

    dups = detect_hotkey_conflicts({"all": "Win+Alt+A", "A": "Alt+Win+a"}, platform_name="win32")
    assert "all" in dups and "A" in dups
    assert "Çift atama" in dups["all"][0]

    linux_tty = detect_hotkey_conflicts({"A": "Ctrl+Alt+F1"}, platform_name="linux")
    assert "TTY" in linux_tty["A"][0]

    mac_conf = detect_hotkey_conflicts({"Q": "Win+Q", "S": "Win+Shift+Q", "all": "Win+Space"}, platform_name="darwin")
    assert set(mac_conf.keys()) == {"Q", "S", "all"}

    bad_syntax = detect_hotkey_conflicts({"A": "Ctrl+Alt"}, platform_name="win32")
    assert "A" in bad_syntax


@pytest.mark.skipif(
    sys.platform != "win32" and not os.environ.get("DISPLAY"),
    reason="Başsız POSIX oturumunda X11/pynput sunucusu yok",
)
@pytest.mark.parametrize(
    "preset_name",
    ["recommended", "function_keys", "ctrl_shift_alt"] if sys.platform == "win32" else ["recommended"],
)
def test_register_hotkeys_on_host_os_live_win32(preset_name: str):
    mgr = HotkeyManager()
    triggered: list[str] = []
    try:
        res = mgr.register(HOTKEY_PRESETS[preset_name], triggered.append)
        assert set(res.keys()) == {"all"}
        if sys.platform == "win32" and not all(res.values()) and "1409" in str(mgr.conflicts.get("all", "")):
            mgr.unregister()
            fallback = {"all": "Win+Alt+F12"}
            res = mgr.register(fallback, triggered.append)
        assert all(res.values()), f"{preset_name} kayıt hatası: {mgr.conflicts}"
        assert mgr.conflicts == {}
        assert set(mgr.registered_hotkeys.keys()) == {"all"}
    finally:
        mgr.unregister()
    assert mgr.registered_hotkeys == {}


def test_win32_register_hotkey_error_1409_and_message_loop_mocked(caplog):
    sss = (ROOT_DIR / "docs" / "SSS.md").read_text(encoding="utf-8")
    fake_u32 = mock.Mock()
    fake_k32 = mock.Mock()
    fake_k32.GetCurrentThreadId.return_value = 4242
    fake_u32.RegisterHotKey.side_effect = [0, 1]
    fake_k32.GetLastError.return_value = ERROR_HOTKEY_ALREADY_REGISTERED

    calls = {"n": 0}

    def fake_get_msg(msg_ptr, _hwnd, _min, _max):
        import ctypes

        calls["n"] += 1
        obj = ctypes.cast(msg_ptr, ctypes.POINTER(type(msg_ptr._obj))).contents
        if calls["n"] == 1:
            obj.message = WM_HOTKEY
            obj.wParam = 2
            return 1
        return 0

    fake_u32.GetMessageW.side_effect = fake_get_msg
    triggered: list[str] = []

    mgr = HotkeyManager(
        platform_name="win32",
        win32_user32=fake_u32,
        win32_kernel32=fake_k32,
        use_win32_native=True,
    )
    res = mgr.register({"A": "Win+A", "Z": "Win+Alt+Z"}, triggered.append)
    assert res == {"A": False, "Z": True}
    assert "A" in mgr.conflicts
    assert "ERROR_HOTKEY_ALREADY_REGISTERED / 1409" in mgr.conflicts["A"]
    assert "ERROR_HOTKEY_ALREADY_REGISTERED / 1409" in sss
    assert triggered == ["Z"]

    mgr.unregister()
    fake_u32.PostThreadMessageW.assert_called()
    fake_u32.UnregisterHotKey.assert_called()


def test_reregister_unbinds_old_listener_without_duplicates():
    listeners: list[mock.Mock] = []

    def fake_factory(mapping):
        lst = mock.Mock()
        lst.mapping = mapping
        listeners.append(lst)
        return lst

    mgr = HotkeyManager(pynput_factory=fake_factory, platform_name="win32")
    mgr.register({"A": "Win+Alt+A", "Z": "Win+Alt+Z"}, lambda _c: None)
    assert len(listeners) == 1
    assert "<cmd>+<alt>+a" in listeners[0].mapping

    mgr.register({"A": "Ctrl+Alt+A", "Z": "Win+Alt+Z"}, lambda _c: None)
    listeners[0].stop.assert_called_once()
    assert len(listeners) == 2
    assert "<cmd>+<alt>+a" not in listeners[1].mapping
    assert "<ctrl>+<alt>+a" in listeners[1].mapping

    mgr.unregister()
    listeners[1].stop.assert_called_once()


def test_windows_keyboard_fallback_when_pynput_fails():
    fake_kb = mock.Mock()
    fake_kb.add_hotkey.side_effect = ["h1"]

    def failing_factory(_mapping):
        raise RuntimeError("Windows hook engellendi")

    mgr = HotkeyManager(
        pynput_factory=failing_factory,
        keyboard_module=fake_kb,
        platform_name="win32",
    )
    res = mgr.register(DEFAULT_HOTKEYS, lambda _c: None)
    assert all(res.values())
    assert fake_kb.add_hotkey.call_count == 1

    mgr.unregister()
    assert fake_kb.remove_hotkey.call_count == 1


def test_macos_accessibility_check_non_darwin_returns_true():
    with mock.patch("qtp_app.core.hotkeys.sys.platform", "linux"):
        assert check_macos_accessibility(prompt=False) is True


def test_hotkeys_error_paths_and_macos_accessibility_mocked():
    with pytest.raises(ValueError):
        to_pynput_combo("")
    assert to_pynput_combo("Ctrl+F1") == "<ctrl>+<f1>"

    mgr = HotkeyManager(pynput_factory=lambda _m: mock.Mock(), platform_name="linux")
    res_empty = mgr.register({"A": "", "Z": "   ", "X": "Ctrl+Alt"}, lambda _c: None)
    assert res_empty == {"A": False, "Z": False, "X": False}

    mgr_linux_fail = HotkeyManager(
        pynput_factory=lambda _m: (_ for _ in ()).throw(RuntimeError("X11 error")),
        platform_name="linux",
    )
    res_fail = mgr_linux_fail.register({"A": "Win+Alt+A"}, lambda _c: None)
    assert res_fail == {"A": False}

    mgr_win_no_kb = HotkeyManager(
        pynput_factory=lambda _m: (_ for _ in ()).throw(RuntimeError("Win hook error")),
        keyboard_module=None,
        platform_name="win32",
    )
    with mock.patch.dict("sys.modules", {"keyboard": None}):
        res_win_fail = mgr_win_no_kb.register({"A": "Win+Alt+A"}, lambda _c: None)
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
        assert mgr_wl.register({"all": "Win+Alt+Space"}, lambda _c: None) == {"all": False}

    assert mgr_wl.register({"A": "Win+Alt+A"}, lambda _c: None) == {"A": False}

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
            assert mgr_bsd.register({"all": "Win+Alt+Space"}, lambda _c: None) == {"all": False}

    mgr_err = HotkeyManager(pynput_factory=lambda _m: bad_listener, keyboard_module=bad_kb, platform_name="win32")
    mgr_err.register({"A": "Win+Alt+A"}, lambda _c: None)
    mgr_err._keyboard_handles.append("hk1")
    mgr_err.unregister()
    with mock.patch("qtp_app.core.hotkeys.sys.platform", "darwin"), \
         mock.patch("qtp_app.core.hotkeys.ctypes.CDLL", side_effect=OSError("no framework")):
        assert check_macos_accessibility(prompt=False) is False

    from qtp_app.core.hotkeys import _configure_win32_prototypes

    u32_proto = mock.Mock()
    k32_proto = mock.Mock()
    _configure_win32_prototypes(u32_proto, k32_proto)
    assert u32_proto.RegisterHotKey.restype is not None

    u32_fail = mock.Mock()
    u32_fail.RegisterHotKey.return_value = 0
    k32_fail = mock.Mock()
    k32_fail.GetCurrentThreadId.return_value = 777
    k32_fail.GetLastError.side_effect = [ERROR_HOTKEY_ALREADY_REGISTERED, 5]
    mgr_w32_fail = HotkeyManager(
        platform_name="win32",
        win32_user32=u32_fail,
        win32_kernel32=k32_fail,
        keyboard_module=None,
    )
    res_w32 = mgr_w32_fail.register({"all": "Win+Alt+Space", "A": "Win+Alt+A"}, lambda _c: None)
    assert res_w32 == {"all": False, "A": False}
    assert "1409" in mgr_w32_fail.conflicts["all"]
    assert "hata kodu=5" in mgr_w32_fail.conflicts["A"]
    mgr_w32_fail.unregister()


def test_kde_kglobalshortcutsrc_parsing_and_linux_conflicts(tmp_path: Path):
    kde_rc = tmp_path / "kglobalshortcutsrc"
    kde_rc.write_text(
        "[plasmashell]\n"
        "_k_friendly_name=Plasma\n"
        "manage activities=Meta+Q,Meta+Q,Show Activity Switcher\n"
        "activate task manager entry 1=Meta+1,none,Görev 1\n"
        "[kwin]\n"
        "Overview=Meta+W\\tCtrl+Alt+O,Meta+W,Toggle Overview\n"
        "Window Minimize=Meta+PgDown,Meta+PgDown,Minimize Window\n"
        "Inactive Action=none,Meta+J,Ignored\n"
        "[kwin][$InverseAction]\n"
        "ShouldBeSkipped=Meta+Alt+A,Meta+Alt+A,Skipped\n"
        "[services][dev.warp.Warp.desktop]\n"
        "_launch=Meta+T,none,Warp\n",
        encoding="utf-8",
    )
    parsed = read_kde_global_shortcuts(kde_rc)
    assert "Win+Q" in parsed and any("Show Activity Switcher" in m for m in parsed["Win+Q"])
    assert "Win+W" in parsed and "Ctrl+Alt+O" in parsed
    assert "Win+PageDown" in parsed
    assert "Win+T" in parsed and any("dev.warp.Warp.desktop" in m for m in parsed["Win+T"])
    assert "Win+J" not in parsed
    assert "Win+Alt+A" not in parsed

    sane = {
        "all": "Win+Alt+Space",
        "A": "Win+Alt+A",
        "Z": "Win+Alt+Z",
        "X": "Win+Alt+X",
        "Q": "Win+Alt+Q",
    }
    assert detect_hotkey_conflicts(sane, platform_name="linux", kde_config_path=kde_rc, include_host_config=True) == {}

    bad_kde = dict(sane, Q="Win+Q", X="Win+T", Z="Ctrl+Alt+O")
    c_map = detect_hotkey_conflicts(bad_kde, platform_name="linux", kde_config_path=kde_rc, include_host_config=True)
    assert "Q" in c_map and any("KDE" in msg for msg in c_map["Q"])
    assert "X" in c_map and any("Warp" in msg or "KDE" in msg for msg in c_map["X"])
    assert "Z" in c_map and any("Overview" in msg for msg in c_map["Z"])

    c_static = detect_hotkey_conflicts(
        dict(sane, Q="Win+Q", A="Win+W", Z="Alt+F4"),
        platform_name="linux",
        include_host_config=False,
    )
    assert "Q" in c_static and any("Activities" in msg or "Etkinlikler" in msg for msg in c_static["Q"])
    assert "A" in c_static and any("Overview" in msg for msg in c_static["A"])
    assert "Z" in c_static
