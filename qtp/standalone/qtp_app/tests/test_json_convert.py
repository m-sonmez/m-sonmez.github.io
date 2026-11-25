"""INI <-> JSON dönüşümü, data.json şeması ve tam yedek (qtp-tam-yedek-*.json) testleri."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from qtp_app.core.ini_parser import decode_bytes_auto, parse_qtp_ini, read_text_auto
from qtp_app.core.json_store import (
    JsonStoreError,
    create_backup,
    export_full_backup,
    ini_to_json,
    json_to_ini,
    list_backups,
    load_data_json,
    load_state,
    parse_any_content,
    restore_backup,
    save_data_json,
    save_state,
    write_full_backup_file,
)

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def test_ini_to_json_to_ini_preserves_order_and_text():
    ini_text = read_text_auto(FIXTURES_DIR / "QuickTextPaste.ini")
    json_items = ini_to_json(ini_text)
    expected_json = load_data_json(FIXTURES_DIR / "data.json")
    assert len(json_items) == len(expected_json)
    assert json_items == expected_json

    ini_bytes = json_to_ini(json_items, encoding="utf-16-le-bom")
    assert ini_bytes.startswith(b"\xff\xfe")
    decoded, _ = decode_bytes_auto(ini_bytes)
    reparsed_items = ini_to_json(decoded)
    assert reparsed_items == json_items


def test_data_json_preserves_all_pwa_fields(tmp_path: Path):
    src_items = load_data_json(FIXTURES_DIR / "data.json")
    out_json = tmp_path / "data.json"
    save_data_json(out_json, src_items)
    reloaded = load_data_json(out_json)
    assert reloaded == src_items

    for item in reloaded:
        assert set(item.keys()).issubset({"keys", "group", "label", "text"})
        assert "keys" in item and "group" in item and "text" in item


def test_full_backup_roundtrip_qtp_tam_yedek(tmp_path: Path):
    items = [
        {
            "keys": "L-Win+A",
            "group": "Partner - Ödeme",
            "label": "İade Bilgisi",
            "text": "İadeniz onaylandı.",
            "favorite": True,
            "copyCount": 4,
            "id": "custom_1",
        },
        {
            "keys": "L-Win+Z",
            "group": "Field",
            "label": "Konum",
            "text": "Konum paylaşabilir misiniz?",
        },
    ]
    backup_file = write_full_backup_file(
        tmp_path,
        items,
        settings={"theme": "dark", "qtpPrefs": {"lng": 21}},
        program={"WinRC": "1;2;3;4;1;x,y,w,h,SW", "lng": "21"},
        extra_sections=[{"name": "EkBolum", "lines": ["anahtar=deger"]}],
    )
    assert backup_file.name.startswith("qtp-tam-yedek-")
    assert backup_file.name.endswith(".json")

    parsed = parse_any_content(backup_file.read_text(encoding="utf-8"), backup_file.name)
    assert parsed["kind"] == "backup"
    assert len(parsed["items"]) == 2
    assert parsed["items"][0]["favorite"] is True
    assert parsed["items"][0]["copyCount"] == 4
    assert parsed["program"]["WinRC"] == "1;2;3;4;1;x,y,w,h,SW"
    assert parsed["extra_sections"] == [{"name": "EkBolum", "lines": ["anahtar=deger"]}]

    payload = export_full_backup(items)
    assert payload["type"] == "qtp-pwa-backup"
    assert payload["version"] == 2


def test_save_load_state_and_backups_lifecycle(tmp_path: Path):
    items_v1 = [{"keys": "L-Win+A", "group": "Test", "label": "S1", "text": "Birinci sürüm"}]
    items_v2 = items_v1 + [{"keys": "L-Win+Z", "group": "Test", "label": "S2", "text": "İkinci sürüm"}]

    save_state(tmp_path, items_v1, create_backup_flag=False)
    st1 = load_state(tmp_path)
    assert len(st1["items"]) == 1

    save_state(tmp_path, items_v2, create_backup_flag=True, backup_reason="update")
    backups = list_backups(tmp_path)
    assert len(backups) == 1
    assert backups[0]["count"] == 1

    restored = restore_backup(tmp_path, backups[0]["id"])
    assert len(restored["state"]["items"]) == 1
    assert restored["state"]["items"][0]["text"] == "Birinci sürüm"

    for i in range(4):
        create_backup(tmp_path, reason=f"rot_{i}", max_keep=2)
    assert len(list_backups(tmp_path)) == 2


def test_json_store_error_paths(tmp_path: Path):
    bad_json = tmp_path / "data.json"
    bad_json.write_text("{bozuk json", encoding="utf-8")
    with pytest.raises(JsonStoreError) as e1:
        load_data_json(bad_json)
    assert "geçersiz JSON biçimi" in str(e1.value)

    obj_json = tmp_path / "obj.json"
    obj_json.write_text(json.dumps({"not": "a list"}), encoding="utf-8")
    with pytest.raises(JsonStoreError) as e2:
        load_data_json(obj_json)
    assert "JSON dizisi" in str(e2.value)

    with pytest.raises(JsonStoreError) as e3:
        parse_any_content('{"unknown": 1}', "x.json")
    assert "Desteklenmeyen dosya biçimi" in str(e3.value)

    with pytest.raises(FileNotFoundError):
        restore_backup(tmp_path, "olmayan_yedek")
    with pytest.raises(FileNotFoundError):
        load_data_json(tmp_path / "olmayan.json")


def test_load_state_ini_newer_and_parse_any_content_branches(tmp_path: Path):
    import os

    empty_st = load_state(tmp_path)
    assert empty_st["source"] == "empty"

    bak_dir = tmp_path / "backups" / "20261123_120000_manual"
    bak_dir.mkdir(parents=True)
    assert list_backups(tmp_path)[0]["reason"] == "unknown"

    ini_path = tmp_path / "QuickTextPaste.ini"
    json_path = tmp_path / "data.json"
    save_state(
        tmp_path,
        [{"keys": "L-Win+A", "group": "G", "label": "L", "text": "İlk", "favorite": True, "copyCount": 2}],
        qtp_prefs={"lng": "21", "m_show_tree": "1"},
        create_backup_flag=False,
    )
    ini_path.write_bytes(
        b"\xff\xfe" + "[Program]\r\nlng=21\r\n[list_text]\r\ntext_000=L-Win+Z=Güncel INI<E<N<D|\r\n[list_order]\r\ntext_000=1\r\n[list_label]\r\ntext_000=Field/Yeni\r\n".encode("utf-16-le")
    )
    now = 1900000000.0
    os.utime(json_path, (now, now))
    os.utime(ini_path, (now + 20.0, now + 20.0))
    st = load_state(tmp_path)
    assert st["source"] == "QuickTextPaste.ini"
    assert st["items"][0]["text"] == "Güncel INI"

    ini_parsed = parse_any_content("[list_text]\r\ntext_000=L-Win+A=Deneme<E<N<D|\r\n", "test.ini")
    assert ini_parsed["kind"] == "ini" and len(ini_parsed["items"]) == 1
    json_parsed = parse_any_content(json.dumps([{"keys": "L-Win+A", "group": "G", "text": "T", "copyCount": "bad"}]), "data.json")
    assert json_parsed["kind"] == "json" and json_parsed["items"][0]["copyCount"] == 0
    with pytest.raises(JsonStoreError):
        parse_any_content("{bozuk", "data.json")


def test_corrupt_data_never_resurrects_bundled_defaults_and_empty_stays_empty(tmp_path: Path):
    import http.client
    import threading
    from qtp_app.core.engine import QtpEngine
    from qtp_app.tui.app import QtpTui
    from qtp_app.web import create_web_server

    empty_dir = tmp_path / "empty_saved"
    empty_dir.mkdir()
    save_state(empty_dir, [{"keys": "L-Win+A", "group": "G", "label": "L", "text": "Tek kayıt"}], create_backup_flag=False)
    eng_emp = QtpEngine(work_dir=empty_dir, seed_defaults=False)
    assert len(eng_emp.items) == 1
    assert eng_emp.op_delete_item("text_000").ok is True
    assert eng_emp.op_save_all().ok is True
    eng_emp_reloaded = QtpEngine(work_dir=empty_dir, seed_defaults=False)
    assert len(eng_emp_reloaded.items) == 0
    assert eng_emp_reloaded.startup_warning is None
    rel_empty = eng_emp_reloaded.reload_data()
    assert rel_empty.ok is True and rel_empty.data["count"] == 0

    bad_dir = tmp_path / "corrupt_ini"
    bad_dir.mkdir()
    (bad_dir / "QuickTextPaste.ini").write_text("[bozuk_ini\r\n", encoding="utf-8")
    eng_bad = QtpEngine(work_dir=bad_dir, seed_defaults=False)
    assert eng_bad.items == []
    assert eng_bad.startup_warning is not None
    assert "HATA: Kayıtlar yeniden yüklenemedi:" in eng_bad.startup_warning
    assert len(list_backups(bad_dir)) == 1
    assert list_backups(bad_dir)[0]["reason"] == "corrupt_load"

    res_rel = eng_bad.reload_data()
    assert res_rel.ok is False and res_rel.exit_code == 1
    assert "HATA: Kayıtlar yeniden yüklenemedi:" in res_rel.message
    assert len(list_backups(bad_dir)) == 1

    tui_bad = QtpTui(eng_bad, term_size=(100, 20))
    assert tui_bad.status_message == eng_bad.startup_warning

    srv = create_web_server(eng_bad, host="127.0.0.1", port=0)
    port = srv.server_address[1]
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/api/revision")
        rev = json.loads(conn.getresponse().read().decode("utf-8"))
        assert rev["data"]["warning"] == eng_bad.startup_warning
    finally:
        srv.shutdown()
        srv.server_close()


def test_persist_copy_count_and_update_ini_false_skip_identical_data_json_write(tmp_path: Path):
    import os
    import time
    from qtp_app.core.engine import QtpEngine

    work = tmp_path / "copy_noop"
    work.mkdir()
    save_state(work, [{"keys": "L-Win+A", "group": "G", "label": "L", "text": "Merhaba"}], create_backup_flag=False)
    eng = QtpEngine(work_dir=work, seed_defaults=False, clipboard_fn=lambda _t: True)
    assert eng.op_save_all().ok is True

    json_path = work / "data.json"
    mtime_before = json_path.stat().st_mtime_ns
    time.sleep(0.02)

    assert eng.op_copy("text_000").ok is True
    assert json_path.stat().st_mtime_ns == mtime_before

    save_state(work, eng.items, update_ini=False, create_backup_flag=False)
    assert json_path.stat().st_mtime_ns == mtime_before
    os.utime(json_path, None)

