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

    # Yeniden yazılan dosya geçerli JSON olmalı
    parsed = json.loads(bad_file.read_text(encoding="utf-8"))
    assert parsed["language"] == "tr"

    # qtp.log içine uyarı yazılmış olmalı
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

    # console=True ve OSError (salt-okunur günlük dizini) güvenli geri dönüşü
    setup_logging(tmp_path, level="debug", console=True)
    with mock.patch.object(Path, "mkdir", side_effect=OSError("readonly")):
        fallback_logger = setup_logging(tmp_path / "blocked", level="info")
    assert fallback_logger is not None

