"""Taşınabilir ayar yönetimi (qtp_settings.json), göç, özel kısayollar, salt-okunur geri dönüş ve günlük testleri."""

from __future__ import annotations

import copy
import json
import logging
from pathlib import Path
from unittest import mock

import pytest

from qtp_app.core.logging_setup import LOG_FILENAME, setup_logging
from qtp_app.core.settings import (
    DEFAULT_HOTKEYS,
    DEFAULT_SETTINGS,
    LEGACY_DEFAULT_HOTKEYS,
    SETTINGS_FILENAME,
    SettingValidationError,
    get_os_fallback_dir,
    get_setting_value,
    load_settings,
    resolve_config_dir,
    resolve_data_path,
    save_settings,
    set_setting_value,
)


def test_first_run_creates_default_settings_in_portable_dir(tmp_path: Path):
    settings, settings_path, warn = load_settings(tmp_path)
    assert warn is None
    assert settings_path == tmp_path / SETTINGS_FILENAME
    assert settings_path.is_file()
    assert settings == DEFAULT_SETTINGS
    assert settings["hotkeys"] == {"all": "Win+Alt+Space"}
    assert settings["categories"] == []
    assert settings["language"] == "auto"
    assert settings["auto_reload"] is True
    assert settings["auto_reload_interval_ms"] == 500

    loaded_raw = json.loads(settings_path.read_text(encoding="utf-8"))
    assert loaded_raw["theme"] == "light"
    assert loaded_raw["backup_count"] == 15


def test_legacy_default_hotkeys_migrated_safely_without_touching_custom(tmp_path: Path):
    legacy_dir = tmp_path / "legacy"
    legacy_dir.mkdir()
    setup_logging(legacy_dir, level="info")
    cfg_path = legacy_dir / SETTINGS_FILENAME
    legacy_payload = copy.deepcopy(DEFAULT_SETTINGS)
    legacy_payload["hotkeys"] = dict(LEGACY_DEFAULT_HOTKEYS)
    cfg_path.write_text(json.dumps(legacy_payload, ensure_ascii=False), encoding="utf-8")

    migrated, _, warn = load_settings(legacy_dir)
    assert warn is None
    expected_migrated = {
        "all": "Win+Alt+Space",
        "A": "Win+Alt+A",
        "Z": "Win+Alt+Z",
        "X": "Win+Alt+X",
        "Q": "Win+Alt+Q",
    }
    assert migrated["hotkeys"] == expected_migrated
    reloaded_disk = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert reloaded_disk["hotkeys"] == expected_migrated
    assert "Win+Alt+*" in (legacy_dir / LOG_FILENAME).read_text(encoding="utf-8")

    custom_dir = tmp_path / "custom"
    custom_dir.mkdir()
    custom_payload = copy.deepcopy(DEFAULT_SETTINGS)
    custom_payload["hotkeys"] = {
        "all": "Ctrl+Shift+Space",
        "A": "Ctrl+Alt+A",
        "Z": "Win+Z",
        "X": "Win+X",
        "Q": "Win+Q",
        "W": "Ctrl+Shift+W",
    }
    custom_path = custom_dir / SETTINGS_FILENAME
    custom_path.write_text(json.dumps(custom_payload, ensure_ascii=False), encoding="utf-8")

    kept, _, _ = load_settings(custom_dir)
    assert kept["hotkeys"]["A"] == "Ctrl+Alt+A"
    assert kept["hotkeys"]["Z"] == "Win+Z"
    assert kept["hotkeys"]["W"] == "Ctrl+Shift+W"


def test_corrupt_settings_regenerates_defaults_and_logs_turkish_warning(tmp_path: Path):
    setup_logging(tmp_path, level="info")
    bad_file = tmp_path / SETTINGS_FILENAME
    bad_file.write_text("{bozuk ayar json!!!", encoding="utf-8")

    settings, path, warn = load_settings(tmp_path)
    assert warn is not None
    assert "Bozuk ayar dosyası" in warn
    assert path == bad_file
    assert settings == DEFAULT_SETTINGS

    parsed = json.loads(bad_file.read_text(encoding="utf-8"))
    assert parsed["language"] == "auto"

    log_text = (tmp_path / LOG_FILENAME).read_text(encoding="utf-8")
    assert "Bozuk ayar dosyası" in log_text


def test_readonly_folder_selects_os_fallback_dir(tmp_path: Path, monkeypatch):
    win_app = tmp_path / "win_appdata"
    xdg_cfg = tmp_path / "linux_xdg"
    fake_home = tmp_path / "home"
    monkeypatch.setenv("APPDATA", str(win_app))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg_cfg))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))

    assert get_os_fallback_dir("win32") == win_app / "QTP"
    assert get_os_fallback_dir("darwin") == fake_home / "Library" / "Application Support" / "QTP"
    assert get_os_fallback_dir("linux") == xdg_cfg / "qtp"
    assert get_os_fallback_dir("freebsd14") == xdg_cfg / "qtp"
    assert get_os_fallback_dir("openbsd7") == xdg_cfg / "qtp"
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    assert get_os_fallback_dir("netbsd10") == fake_home / ".config" / "qtp"

    readonly_dir = tmp_path / "readonly_bin_dir"
    readonly_dir.mkdir()
    with mock.patch(
        "qtp_app.core.settings.is_dir_writable",
        side_effect=lambda p: Path(p) != readonly_dir,
    ):
        chosen, is_portable = resolve_config_dir(readonly_dir, platform_name="win32")
    assert is_portable is False
    assert chosen == win_app / "QTP"


def test_save_settings_and_logging_levels(tmp_path: Path):
    custom = copy.deepcopy(DEFAULT_SETTINGS)
    custom["theme"] = "dark"
    custom["log_level"] = "debug"
    custom["backup_count"] = 25
    custom["auto_reload"] = False
    custom["auto_reload_interval_ms"] = 1200
    settings_path = tmp_path / SETTINGS_FILENAME
    save_settings(custom, settings_path)

    loaded, _, warn = load_settings(tmp_path)
    assert warn is None
    assert loaded["theme"] == "dark"
    assert loaded["log_level"] == "debug"
    assert loaded["backup_count"] == 25
    assert loaded["auto_reload"] is False
    assert loaded["auto_reload_interval_ms"] == 1200
    assert resolve_data_path(loaded, tmp_path) == (tmp_path / "QuickTextPaste.ini").resolve()

    logger = setup_logging(tmp_path, level="warn")
    assert logger.level == logging.WARNING
    logger.info("Bu bilgi satırı filtrelenmeli")
    logger.warning("Bu uyarı satırı yazılmalı")
    log_content = (tmp_path / LOG_FILENAME).read_text(encoding="utf-8")
    assert "Bu uyarı satırı yazılmalı" in log_content
    assert "Bu bilgi satırı filtrelenmeli" not in log_content

    setup_logging(tmp_path, level="debug", console=True)
    with mock.patch.object(Path, "mkdir", side_effect=OSError("readonly")):
        fallback_logger = setup_logging(tmp_path / "blocked", level="info")
    assert fallback_logger is not None


def test_get_and_set_setting_value_validation_and_custom_slots():
    cfg = copy.deepcopy(DEFAULT_SETTINGS)
    assert get_setting_value(cfg, "theme") == "light"
    assert get_setting_value(cfg, "web.port") == 8765
    assert get_setting_value(cfg, "hotkeys.all") == "Win+Alt+Space"
    assert get_setting_value(cfg, "categories") == []
    assert get_setting_value(cfg, "language") == "auto"
    assert get_setting_value(cfg, "auto_reload") is True

    cfg = set_setting_value(cfg, "theme", "auto")
    cfg = set_setting_value(cfg, "view_mode", "table")
    cfg = set_setting_value(cfg, "strip_emoji", "true")
    cfg = set_setting_value(cfg, "sort_by", "usage")
    cfg = set_setting_value(cfg, "paste_method", "shift_insert")
    cfg = set_setting_value(cfg, "log_level", "debug")
    cfg = set_setting_value(cfg, "last_category", "work_1")
    cfg = set_setting_value(cfg, "categories", '[{"code": "1", "label": "General", "hotkey_prefix": "L-Win+1"}]')
    cfg = set_setting_value(cfg, "enter_after_paste", "false")
    cfg = set_setting_value(cfg, "start_minimized", "true")
    cfg = set_setting_value(cfg, "backup_count", "20")
    cfg = set_setting_value(cfg, "data_path", "./custom.ini")
    cfg = set_setting_value(cfg, "language", "en")
    cfg = set_setting_value(cfg, "language", "tr")
    cfg = set_setting_value(cfg, "window_size", "800x600")
    cfg = set_setting_value(cfg, "web.port", "9090")
    cfg = set_setting_value(cfg, "auto_reload", "false")
    cfg = set_setting_value(cfg, "auto_reload_interval_ms", "750")
    cfg = set_setting_value(cfg, "hotkeys.A", "alt+ctrl+a")
    cfg = set_setting_value(cfg, "hotkeys.W", "shift+ctrl+w")

    assert cfg["theme"] == "auto"
    assert cfg["view_mode"] == "table"
    assert cfg["strip_emoji"] is True
    assert cfg["sort_by"] == "usage"
    assert cfg["paste_method"] == "shift_insert"
    assert cfg["log_level"] == "debug"
    assert cfg["last_category"] == "WORK_1"
    assert cfg["categories"] == [{"code": "1", "label": "General", "hotkey_prefix": "L-Win+1"}]
    assert cfg["enter_after_paste"] is False
    assert cfg["start_minimized"] is True
    assert cfg["backup_count"] == 20
    assert cfg["window_size"] == [800, 600]
    assert cfg["web"]["port"] == 9090
    assert cfg["auto_reload"] is False
    assert cfg["auto_reload_interval_ms"] == 750
    assert cfg["hotkeys"]["A"] == "Ctrl+Alt+A"
    assert cfg["hotkeys"]["W"] == "Ctrl+Shift+W"

    cfg = set_setting_value(cfg, "hotkeys.all", "")
    assert cfg["hotkeys"]["all"] == ""
    cfg = set_setting_value(cfg, "hotkeys.A", "")
    assert "A" not in cfg["hotkeys"]
    cfg = set_setting_value(cfg, "hotkeys.W", "")
    assert "W" not in cfg["hotkeys"]

    for bad_key in ("", "olmayan", "web.olmayan", "hotkeys.olmayan"):
        with pytest.raises(SettingValidationError):
            get_setting_value(cfg, bad_key)

    for k, v in (
        ("theme", "neon"),
        ("view_mode", "kanban"),
        ("strip_emoji", "belki"),
        ("sort_by", "random"),
        ("paste_method", "magic"),
        ("log_level", "verbose"),
        ("last_category", "bad category!"),
        ("categories", "not-json"),
        ("categories", "{}"),
        ("enter_after_paste", "belki"),
        ("auto_reload", "belki"),
        ("auto_reload_interval_ms", "abc"),
        ("auto_reload_interval_ms", "50"),
        ("auto_reload_interval_ms", "20000"),
        ("backup_count", "abc"),
        ("backup_count", "999"),
        ("data_path", "   "),
        ("language", "zz_unsupported"),
        ("window_size", "100"),
        ("window_size", "bad,size"),
        ("window_size", "100,100"),
        ("window_size", "559x400"),
        ("window_size", "560x399"),
        ("web.port", "abc"),
        ("web.port", "70000"),
        ("hotkeys.A", "Ctrl+Alt"),
        ("hotkeys.A", "BilinmeyenTus+A"),
        ("hotkeys.", "Ctrl+A"),
        ("hotkeys.bad.slot", "Ctrl+A"),
        ("bilinmeyen", "1"),
    ):
        with pytest.raises(SettingValidationError):
            set_setting_value(cfg, k, v)


def test_window_size_clamped_to_560x400_and_log_level_noop_skips_setup_logging(tmp_path: Path):
    from qtp_app.core.engine import QtpEngine
    from qtp_app.core.settings import _sanitize_settings

    sanitized = _sanitize_settings({"window_size": [480, 360]})
    assert sanitized["window_size"] == [560, 400]

    cfg = copy.deepcopy(DEFAULT_SETTINGS)
    cfg = set_setting_value(cfg, "window_size", "560x400")
    assert cfg["window_size"] == [560, 400]

    eng = QtpEngine(work_dir=tmp_path, seed_defaults=False)
    with mock.patch("qtp_app.core.engine.setup_logging") as spy_setup:
        unchanged = copy.deepcopy(eng.settings)
        unchanged["theme"] = "dark"
        eng.save_current_settings(unchanged)
        spy_setup.assert_not_called()

        changed = copy.deepcopy(eng.settings)
        changed["log_level"] = "debug"
        eng.save_current_settings(changed)
        spy_setup.assert_called_once()
