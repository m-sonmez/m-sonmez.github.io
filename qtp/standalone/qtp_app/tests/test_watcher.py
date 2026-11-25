"""Dinamik canlı dosya izleyici (ConfigFileWatcher) ve çalışma zamanı sıcak yenileme testleri."""

from __future__ import annotations

import copy
import json
import os
import shutil
import threading
import time
from pathlib import Path

from qtp_app.core.engine import QtpEngine
from qtp_app.core.ini_parser import build_qtp_ini, write_qtp_ini
from qtp_app.core.logging_setup import LOG_FILENAME
from qtp_app.core.settings import DEFAULT_SETTINGS
from qtp_app.core.watcher import ConfigFileWatcher, ReloadEvent

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def _wait_until(predicate, timeout: float = 3.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.04)
    assert predicate()


def test_watcher_reloads_ini_in_place_and_atomic_replace(tmp_path: Path):
    work = tmp_path / "watch_ini"
    work.mkdir()
    shutil.copy2(FIXTURES_DIR / "minimal.ini", work / "QuickTextPaste.ini")
    shutil.copy2(FIXTURES_DIR / "data.json", work / "data.json")
    cfg = copy.deepcopy(DEFAULT_SETTINGS)
    cfg["auto_reload_interval_ms"] = 100
    (work / "qtp_settings.json").write_text(json.dumps(cfg), encoding="utf-8")

    eng = QtpEngine(work_dir=work, seed_defaults=False)
    events: list[ReloadEvent] = []
    eng.start_watcher(on_reload=events.append, debounce_ms=80)
    try:
        items_ext = [
            {"keys": "L-Win+A", "group": "Partner", "label": "Bir", "text": "Birinci metin"},
            {"keys": "L-Win+Z", "group": "Field", "label": "İki", "text": "İkinci metin"},
            {"keys": "L-Win+X", "group": "Live", "label": "Üç", "text": "Üçüncü metin eklendi"},
        ]
        write_qtp_ini(work / "QuickTextPaste.ini", build_qtp_ini(items_ext), create_bak=False)

        _wait_until(lambda: any(e.items_changed and e.item_count == 3 for e in events))
        assert len(eng.items) == 3
        assert eng.items[2]["text"] == "Üçüncü metin eklendi"

        items_rep = items_ext + [{"keys": "L-Win+Q", "group": "Telecom", "label": "Dört", "text": "Atomik değişim"}]
        tmp_atomic = work / "QuickTextPaste.ini.tmp"
        write_qtp_ini(tmp_atomic, build_qtp_ini(items_rep), create_bak=False)
        os.replace(tmp_atomic, work / "QuickTextPaste.ini")

        _wait_until(lambda: len(eng.items) == 4)
        assert eng.items[3]["text"] == "Atomik değişim"
    finally:
        eng.stop_watcher()

    assert not any(t.name == "qtp-config-watcher" for t in threading.enumerate())


def test_watcher_reloads_data_json_and_suppresses_internal_writes(tmp_path: Path):
    work = tmp_path / "watch_json"
    work.mkdir()
    shutil.copy2(FIXTURES_DIR / "minimal.ini", work / "QuickTextPaste.ini")
    cfg = copy.deepcopy(DEFAULT_SETTINGS)
    cfg["auto_reload_interval_ms"] = 100
    (work / "qtp_settings.json").write_text(json.dumps(cfg), encoding="utf-8")

    eng = QtpEngine(work_dir=work, seed_defaults=False)
    events: list[ReloadEvent] = []
    eng.start_watcher(on_reload=events.append, debounce_ms=80)
    try:
        assert eng.op_set_setting("theme", "dark").exit_code == 0
        time.sleep(0.35)
        assert not any(e.settings_changed for e in events)

        ext_json = [{"keys": "L-Win+A", "group": "JSON", "label": "Yeni", "text": "data.json harici güncelleme"}]
        (work / "data.json").write_text(json.dumps(ext_json, ensure_ascii=False), encoding="utf-8")
        _wait_until(lambda: any(e.items_changed and e.item_count == 1 for e in events))
        assert eng.items[0]["text"] == "data.json harici güncelleme"
    finally:
        eng.stop_watcher()


def test_watcher_settings_hotkeys_theme_datapath_and_corrupt_resilience(tmp_path: Path):
    work = tmp_path / "watch_settings"
    work.mkdir()
    shutil.copy2(FIXTURES_DIR / "minimal.ini", work / "QuickTextPaste.ini")
    alt_ini = work / "alternatif.ini"
    write_qtp_ini(
        alt_ini,
        build_qtp_ini([{"keys": "L-Win+Q", "group": "Özel", "label": "Alt", "text": "Alternatif INI kaydı"}]),
        create_bak=False,
    )
    cfg = copy.deepcopy(DEFAULT_SETTINGS)
    cfg["auto_reload_interval_ms"] = 100
    cfg_path = work / "qtp_settings.json"
    cfg_path.write_text(json.dumps(cfg), encoding="utf-8")

    eng = QtpEngine(work_dir=work, seed_defaults=False)
    events: list[ReloadEvent] = []
    eng.start_watcher(on_reload=events.append, debounce_ms=80)
    try:
        new_cfg = copy.deepcopy(eng.settings)
        new_cfg["hotkeys"]["A"] = "Ctrl+Shift+Alt+A"
        new_cfg["theme"] = "dark"
        new_cfg["log_level"] = "debug"
        new_cfg["window_size"] = [820, 600]
        new_cfg["data_path"] = "./alternatif.ini"
        cfg_path.write_text(json.dumps(new_cfg, ensure_ascii=False), encoding="utf-8")

        _wait_until(
            lambda: any(
                e.hotkeys_changed and e.theme_changed and e.data_path_changed and e.items_changed
                for e in events
            )
        )
        assert eng.settings["hotkeys"]["A"] == "Ctrl+Alt+Shift+A"
        assert eng.settings["theme"] == "dark"
        assert eng.settings["window_size"] == [820, 600]
        assert eng.items[0]["text"] == "Alternatif INI kaydı"

        cfg_path.write_text("{bozuk ayar!!!", encoding="utf-8")
        _wait_until(lambda: any(e.warning and "Otomatik ayar yenileme başarısız" in e.warning for e in events))
        assert eng.settings["theme"] == "dark"

        alt_ini.write_text("[bozuk_ini\r\n", encoding="utf-16-le")
        _wait_until(lambda: any(e.warning and "Otomatik veri yenileme başarısız" in e.warning for e in events))
        assert eng.items[0]["text"] == "Alternatif INI kaydı"

        log_text = (work / LOG_FILENAME).read_text(encoding="utf-8")
        sss = (Path(__file__).resolve().parent.parent.parent.parent / "docs" / "SSS.md").read_text(encoding="utf-8")
        assert "Otomatik ayar yenileme başarısız (mevcut ayarlar korundu):" in log_text
        assert "Otomatik ayar yenileme başarısız (mevcut ayarlar korundu):" in sss
        assert "Otomatik veri yenileme başarısız (önceki geçerli kayıtlar korundu):" in log_text
        assert "Otomatik veri yenileme başarısız (önceki geçerli kayıtlar korundu):" in sss
    finally:
        eng.stop_watcher()


def test_ephemeral_engine_never_starts_watcher_and_unit_watcher_branches(tmp_path: Path):
    eph = QtpEngine(work_dir=tmp_path, seed_defaults=False, ephemeral=True)
    assert eph.start_watcher() is None
    assert eph._watcher is None

    target = tmp_path / "unit.txt"
    seen: list[list] = []
    w = ConfigFileWatcher({"u": target}, seen.append, interval_ms=100, debounce_ms=50)
    with w.suppress_write(target):
        target.write_text("dahili", encoding="utf-8")
    assert w.poll_once() == []

    target.write_text("harici_v1", encoding="utf-8")
    w.poll_once()
    time.sleep(0.08)
    changes = w.poll_once()
    assert len(changes) == 1 and changes[0].kind == "u"
    w.set_interval(250)
    assert "u" in w.targets


def test_watcher_stat_first_short_circuits_sha256(tmp_path: Path):
    import hashlib
    from unittest import mock
    from qtp_app.core.watcher import compute_file_fingerprint

    missing = compute_file_fingerprint(tmp_path / "yok.txt")
    assert missing == (False, 0, 0, "")

    target = tmp_path / "big.json"
    target.write_text('[{"text": "alfa"}]', encoding="utf-8")
    watcher = ConfigFileWatcher({"u": target}, lambda _c: None, interval_ms=100, debounce_ms=50)

    with mock.patch.object(hashlib, "sha256", wraps=hashlib.sha256) as sha_spy:
        for _ in range(5):
            assert watcher.poll_once() == []
        assert sha_spy.call_count == 0

        target.write_text('[{"text": "beta daha uzun metin"}]', encoding="utf-8")
        watcher.poll_once()
        assert sha_spy.call_count >= 1
