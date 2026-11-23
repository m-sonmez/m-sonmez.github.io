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

    # Her kayıt yalnızca data.json şemasındaki geçerli PWA alanlarını içerir
    for item in reloaded:
        assert set(item.keys()).issubset({"keys", "group", "label", "text"})
        assert "keys" in item and "group" in item and "text" in item


def test_full_backup_roundtrip_qtp_tam_yedek(tmp_path: Path):
    items = [
        {
            "keys": "L-Win+A",
            "group": "Restoran - Ödeme",
            "label": "İade Bilgisi",
            "text": "İadeniz onaylandı.",
            "favorite": True,
            "copyCount": 4,
            "id": "custom_1",
        },
        {
            "keys": "L-Win+Z",
            "group": "Kurye",
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

    # Manuel yedek + rotasyon sınırı
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

    # Boş klasörde load_state empty döner
    empty_st = load_state(tmp_path)
    assert empty_st["source"] == "empty"

    # Yedek klasöründe meta.json eksikse dahi list_backups çalışmalı
    bak_dir = tmp_path / "backups" / "20261123_120000_manual"
    bak_dir.mkdir(parents=True)
    assert list_backups(tmp_path)[0]["reason"] == "unknown"

    # INI dosyası data.json'dan yeniyse INI seçilir
    ini_path = tmp_path / "QuickTextPaste.ini"
    json_path = tmp_path / "data.json"
    save_state(
        tmp_path,
        [{"keys": "L-Win+A", "group": "G", "label": "L", "text": "İlk", "favorite": True, "copyCount": 2}],
        qtp_prefs={"lng": "21", "m_show_tree": "1"},
        create_backup_flag=False,
    )
    ini_path.write_bytes(
        b"\xff\xfe" + "[Program]\r\nlng=21\r\n[list_text]\r\ntext_000=L-Win+Z=Güncel INI<E<N<D|\r\n[list_order]\r\ntext_000=1\r\n[list_label]\r\ntext_000=Kurye/Yeni\r\n".encode("utf-16-le")
    )
    now = 1900000000.0
    os.utime(json_path, (now, now))
    os.utime(ini_path, (now + 20.0, now + 20.0))
    st = load_state(tmp_path)
    assert st["source"] == "QuickTextPaste.ini"
    assert st["items"][0]["text"] == "Güncel INI"

    # parse_any_content INI ve düz JSON listesi yolları
    ini_parsed = parse_any_content("[list_text]\r\ntext_000=L-Win+A=Deneme<E<N<D|\r\n", "test.ini")
    assert ini_parsed["kind"] == "ini" and len(ini_parsed["items"]) == 1
    json_parsed = parse_any_content(json.dumps([{"keys": "L-Win+A", "group": "G", "text": "T", "copyCount": "bad"}]), "data.json")
    assert json_parsed["kind"] == "json" and json_parsed["items"][0]["copyCount"] == 0
    with pytest.raises(JsonStoreError):
        parse_any_content("{bozuk", "data.json")

