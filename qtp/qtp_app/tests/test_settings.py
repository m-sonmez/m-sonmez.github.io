"""Taşınabilir ayar yönetimi (qtp_settings.json), salt-okunur geri dönüş ve dönen günlük testleri."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from unittest import mock

from qtp_app.core.logging_setup import LOG_FILENAME, setup_logging
from qtp_app.core.settings import (
    DEFAULT_SETTINGS,
    SETTINGS_FILENAME,
    get_os_fallback_dir,
    load_settings,
    resolve_config_dir,
    resolve_data_path,
    save_settings,
)


def test_first_run_creates_default_settings_in_portable_dir(tmp_path: Path):
    settings, settings_path, warn = load_settings(tmp_path)
    assert warn is None
    assert settings_path == tmp_path / SETTINGS_FILENAME
    assert settings_path.is_file()
    assert settings == DEFAULT_SETTINGS

    loaded_raw = json.loads(settings_path.read_text(encoding="utf-8"))
    assert loaded_raw["theme"] == "dark"
    assert loaded_raw["backup_count"] == 15


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
    assert parsed["language"] == "tr"

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
    custom = dict(DEFAULT_SETTINGS)
    custom["theme"] = "light"
    custom["log_level"] = "debug"
    custom["backup_count"] = 25
    settings_path = tmp_path / SETTINGS_FILENAME
    save_settings(custom, settings_path)

    loaded, _, warn = load_settings(tmp_path)
    assert warn is None
    assert loaded["theme"] == "light"
    assert loaded["log_level"] == "debug"
    assert loaded["backup_count"] == 25
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


def test_get_and_set_setting_value_validation():
    import copy
    import pytest
    from qtp_app.core.settings import SettingValidationError, get_setting_value, set_setting_value

    cfg = copy.deepcopy(DEFAULT_SETTINGS)
    assert get_setting_value(cfg, "theme") == "dark"
    assert get_setting_value(cfg, "web.port") == 8765
    assert get_setting_value(cfg, "hotkeys.A") == "Win+A"

    cfg = set_setting_value(cfg, "theme", "auto")
    cfg = set_setting_value(cfg, "paste_method", "shift_insert")
    cfg = set_setting_value(cfg, "log_level", "debug")
    cfg = set_setting_value(cfg, "last_category", "z")
    cfg = set_setting_value(cfg, "enter_after_paste", "false")
    cfg = set_setting_value(cfg, "start_minimized", "true")
    cfg = set_setting_value(cfg, "backup_count", "20")
    cfg = set_setting_value(cfg, "data_path", "./custom.ini")
    cfg = set_setting_value(cfg, "language", "tr")
    cfg = set_setting_value(cfg, "window_size", "800x600")
    cfg = set_setting_value(cfg, "web.port", "9090")
    cfg = set_setting_value(cfg, "hotkeys.A", "Ctrl+Alt+A")

    assert cfg["theme"] == "auto"
    assert cfg["paste_method"] == "shift_insert"
    assert cfg["log_level"] == "debug"
    assert cfg["last_category"] == "Z"
    assert cfg["enter_after_paste"] is False
    assert cfg["start_minimized"] is True
    assert cfg["backup_count"] == 20
    assert cfg["window_size"] == [800, 600]
    assert cfg["web"]["port"] == 9090
    assert cfg["hotkeys"]["A"] == "Ctrl+Alt+A"

    for bad_key in ("", "olmayan", "web.olmayan", "hotkeys.olmayan"):
        with pytest.raises(SettingValidationError):
            get_setting_value(cfg, bad_key)

    for k, v in (
        ("theme", "neon"),
        ("paste_method", "magic"),
        ("log_level", "verbose"),
        ("last_category", "B"),
        ("enter_after_paste", "belki"),
        ("backup_count", "abc"),
        ("backup_count", "999"),
        ("data_path", "   "),
        ("language", "en"),
        ("window_size", "100"),
        ("window_size", "bad,size"),
        ("window_size", "100,100"),
        ("web.port", "abc"),
        ("web.port", "70000"),
        ("hotkeys.A", ""),
        ("hotkeys.BAD", "Win+B"),
        ("bilinmeyen", "1"),
    ):
        with pytest.raises(SettingValidationError):
            set_setting_value(cfg, k, v)


