from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest import mock

from qtp_app.core.engine import QtpEngine
from qtp_app.core.i18n import (
    BUILTIN_LANGUAGES,
    DEFAULT_LANGUAGE,
    LOCALE_FILENAME,
    available_languages,
    detect_system_language,
    get_catalog,
    load_custom_locales,
    resolve_language,
    t,
)
from qtp_app.core.settings import DEFAULT_SETTINGS, set_setting_value


def test_detect_system_language_env_win32_and_fallback(monkeypatch):
    monkeypatch.setenv("LC_ALL", "tr_TR.UTF-8")
    assert detect_system_language(platform_name="linux") == "tr"
    monkeypatch.setenv("LC_ALL", "en_US.UTF-8")
    assert detect_system_language(platform_name="linux") == "en"

    monkeypatch.delenv("LC_ALL", raising=False)
    monkeypatch.delenv("LC_MESSAGES", raising=False)
    monkeypatch.delenv("LANG", raising=False)

    fake_k32 = mock.Mock()
    fake_k32.GetUserDefaultUILanguage.return_value = 0x041F
    with mock.patch("qtp_app.core.i18n.ctypes.windll", mock.Mock(kernel32=fake_k32), create=True):
        assert detect_system_language(platform_name="win32") == "tr"

    fake_k32.GetUserDefaultUILanguage.return_value = 0x0409
    with mock.patch("qtp_app.core.i18n.ctypes.windll", mock.Mock(kernel32=fake_k32), create=True):
        assert detect_system_language(platform_name="win32") == "en"

    with mock.patch("qtp_app.core.i18n.locale.getlocale", return_value=("tr_TR", "UTF-8")):
        assert detect_system_language(platform_name="linux") == "tr"
    with mock.patch("qtp_app.core.i18n.locale.getlocale", return_value=("fr_FR", "UTF-8")):
        assert detect_system_language(platform_name="linux") == "en"
    with mock.patch("qtp_app.core.i18n.locale.getlocale", side_effect=ValueError("bad")):
        assert detect_system_language(platform_name="linux") == "en"


def test_custom_locale_overrides_flat_nested_and_corrupt(tmp_path: Path, monkeypatch):
    assert DEFAULT_LANGUAGE == "auto"
    assert BUILTIN_LANGUAGES == ("en", "tr")
    assert load_custom_locales(None) == {}
    assert load_custom_locales(tmp_path) == {}

    loc_path = tmp_path / LOCALE_FILENAME
    loc_path.write_text("{not valid json", encoding="utf-8")
    assert load_custom_locales(tmp_path) == {}

    loc_path.write_text(json.dumps({"cat.all": "Everything", "overlay.save": "Store"}), encoding="utf-8")
    assert t("cat.all", "en", config_dir=tmp_path) == "Everything"
    assert t("cat.all", "tr", config_dir=tmp_path) == "Everything"

    loc_path.write_text(
        json.dumps(
            {
                "de": {"cat.all": "Alle", "settings.title": "QTP — Einstellungen"},
                "en": {"cat.all": "All Items"},
            }
        ),
        encoding="utf-8",
    )
    langs = available_languages(tmp_path)
    assert "auto" in langs and "en" in langs and "tr" in langs and "de" in langs
    assert resolve_language("de", config_dir=tmp_path) == "de"
    assert t("cat.all", "de", config_dir=tmp_path) == "Alle"
    assert t("cat.all", "en", config_dir=tmp_path) == "All Items"
    assert t("overlay.save", "de", config_dir=tmp_path) == "Save"
    assert t("missing.key.xyz", "en", config_dir=tmp_path) == "missing.key.xyz"
    assert t("overlay.selected_count", "en", count=7) == "7 selected"
    assert t("overlay.selected_count", "tr", count=7) == "7 seçili"
    assert "cat.all" in get_catalog("en", config_dir=tmp_path)

    monkeypatch.setenv("LC_ALL", "en_US.UTF-8")
    assert resolve_language("auto", config_dir=tmp_path) == "en"
    assert resolve_language("unknown_lang", config_dir=tmp_path) == "en"

    cfg = set_setting_value(dict(DEFAULT_SETTINGS), "language", "de", config_dir=tmp_path)
    assert cfg["language"] == "de"

    eng = QtpEngine(work_dir=tmp_path, seed_defaults=False)
    res = eng.op_set_setting("language", "de")
    assert res.ok is True
    assert eng.resolved_language() == "de"
    assert eng.resolve_categories()[0]["label"] == "Alle"
