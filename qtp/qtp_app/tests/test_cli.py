"""CLI bayrakları (--version, --help, --selftest, --export-ini, --import-ini) testleri."""

from __future__ import annotations

import os
from pathlib import Path

from qtp_app import __version__
from qtp_app.core.ini_parser import parse_qtp_ini, read_text_auto
from qtp_app.core.json_store import load_data_json, save_data_json
from qtp_app.main import main

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def test_cli_version(capsys):
    code = main(["--version"])
    assert code == 0
    out = capsys.readouterr().out
    assert __version__ in out
    assert "Derleme:" in out


def test_cli_help_turkish(capsys):
    code = main(["--help"])
    assert code == 0
    out = capsys.readouterr().out
    for flag in ("--help", "--version", "--selftest", "--export-ini", "--import-ini"):
        assert flag in out
    assert "Komut Satırı Kullanımı" in out


def test_cli_selftest_offscreen(capsys, monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    code = main(["--selftest"])
    assert code == 0
    out = capsys.readouterr().out
    assert "Otomatik test başarılı" in out


def test_cli_export_and_import_ini(tmp_path: Path, capsys):
    # Başlangıçta 2 kayıtlı bir çalışma dizini hazırla
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    seed_items = [
        {"keys": "L-Win+A", "group": "Restoran", "label": "İlk", "text": "Mevcut kayıt 1"},
        {"keys": "L-Win+Z", "group": "Kurye", "label": "İki", "text": "Mevcut kayıt 2"},
    ]
    save_data_json(work_dir / "data.json", seed_items)

    # --export-ini çıktısı aynı sayıda kaydı geri okunabilir biçimde yazmalı
    exported_ini = tmp_path / "exported.ini"
    code_exp = main(["--work-dir", str(work_dir), "--export-ini", str(exported_ini)])
    assert code_exp == 0
    assert exported_ini.is_file()
    reparsed = parse_qtp_ini(read_text_auto(exported_ini))
    assert len(reparsed.items) == 2

    # --import-ini yeni kayıtları mevcut kayıtları koruyarak birleştirmeli
    incoming_ini = FIXTURES_DIR / "minimal.ini"
    code_imp = main(["--work-dir", str(work_dir), "--import-ini", str(incoming_ini)])
    assert code_imp == 0
    out_imp = capsys.readouterr().out
    assert "yeni kayıt eklendi" in out_imp

    merged_items = load_data_json(work_dir / "data.json")
    assert len(merged_items) == 4
    texts = {it["text"] for it in merged_items}
    assert "Mevcut kayıt 1" in texts
    assert "Mevcut kayıt 2" in texts


def test_cli_unknown_flag_and_missing_import_fail(tmp_path: Path, capsys):
    code_bad = main(["--bilinmeyen-bayrak"])
    assert code_bad == 2
    err = capsys.readouterr().err
    assert "Bilinmeyen komut satırı seçeneği" in err

    code_missing = main(["--work-dir", str(tmp_path), "--import-ini", str(tmp_path / "yok.ini")])
    assert code_missing == 1
    err2 = capsys.readouterr().err
    assert "İçe aktarılacak INI dosyası bulunamadı" in err2
