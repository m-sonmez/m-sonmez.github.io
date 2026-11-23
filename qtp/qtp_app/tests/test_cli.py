"""CLI bayrakları (--version, --help, --selftest, --export-ini, --import-ini) testleri."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from qtp_app import __version__
from qtp_app.core.ini_parser import parse_qtp_ini, read_text_auto
from qtp_app.core.json_store import load_data_json, save_data_json
from qtp_app.main import main

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def test_cli_version(capsys, tmp_path: Path, monkeypatch):
    app_dir = tmp_path / "isolated_ver"
    app_dir.mkdir()
    monkeypatch.setattr("qtp_app.core.engine.get_app_dir", lambda: app_dir)
    code = main(["--version"])
    assert code == 0
    out = capsys.readouterr().out
    assert __version__ in out
    assert "Derleme:" in out
    assert list(app_dir.iterdir()) == []


def test_cli_help_turkish(capsys, tmp_path: Path, monkeypatch):
    app_dir = tmp_path / "isolated_help"
    app_dir.mkdir()
    monkeypatch.setattr("qtp_app.core.engine.get_app_dir", lambda: app_dir)
    code = main(["--help"])
    assert code == 0
    out = capsys.readouterr().out
    for flag in ("--help", "--version", "--selftest", "--export-ini", "--import-ini"):
        assert flag in out
    assert "Komut Satırı Kullanımı" in out
    assert list(app_dir.iterdir()) == []


def test_cli_selftest_offscreen(capsys, monkeypatch, tmp_path: Path):
    app_dir = tmp_path / "isolated_selftest"
    app_dir.mkdir()
    monkeypatch.setattr("qtp_app.core.engine.get_app_dir", lambda: app_dir)
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    assert main(["--modes"]) == 0
    capsys.readouterr()
    code = main(["--selftest"])
    assert code == 0
    out = capsys.readouterr().out
    assert "Otomatik test başarılı" in out
    assert list(app_dir.iterdir()) == []


def test_cli_export_and_import_ini(tmp_path: Path, capsys):
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    seed_items = [
        {"keys": "L-Win+A", "group": "Restoran", "label": "İlk", "text": "Mevcut kayıt 1"},
        {"keys": "L-Win+Z", "group": "Kurye", "label": "İki", "text": "Mevcut kayıt 2"},
    ]
    save_data_json(work_dir / "data.json", seed_items)

    exported_ini = tmp_path / "exported.ini"
    code_exp = main(["--work-dir", str(work_dir), "--export-ini", str(exported_ini)])
    assert code_exp == 0
    assert exported_ini.is_file()
    reparsed = parse_qtp_ini(read_text_auto(exported_ini))
    assert len(reparsed.items) == 2

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


def test_cli_full_subcommands_json_and_mode_enforcement(tmp_path: Path, capsys, monkeypatch):
    import json
    from unittest import mock
    from qtp_app import cli

    work_dir = tmp_path / "cli_full"
    work_dir.mkdir()
    save_data_json(
        work_dir / "data.json",
        [{"keys": "L-Win+A", "group": "Restoran", "label": "Selam", "text": "Merhaba Dünya"}],
    )

    monkeypatch.setenv("CI", "true")
    assert cli.run([]) == 2
    assert "--mode" in capsys.readouterr().err
    monkeypatch.delenv("CI", raising=False)

    assert cli.run(["--work-dir", str(work_dir), "--modes", "--json"]) == 0
    assert "web" in capsys.readouterr().out

    assert cli.run(["--work-dir", str(work_dir), "--list-categories"]) == 0
    assert "Tümü" in capsys.readouterr().out

    assert cli.run(["--work-dir", str(work_dir), "--list-items"]) == 0
    assert "Merhaba Dünya" in capsys.readouterr().out

    assert cli.run(["--work-dir", str(work_dir), "--search", "Merhaba"]) == 0
    assert "text_000" in capsys.readouterr().out

    assert cli.run(["--work-dir", str(work_dir), "--show-ini", "text_000"]) == 0
    assert "[list_text]" in capsys.readouterr().out

    assert cli.run(["--work-dir", str(work_dir), "--reload"]) == 0
    assert "INI yeniden yüklendi" in capsys.readouterr().out

    assert cli.run(["--work-dir", str(work_dir), "--backup", "--keep", "5"]) == 0
    assert "Anlık yedek alındı" in capsys.readouterr().out

    bak_out = tmp_path / "tam_yedek.json"
    assert cli.run(["--work-dir", str(work_dir), "--export-backup", str(bak_out)]) == 0
    assert bak_out.is_file()

    assert cli.run(["--work-dir", str(work_dir), "--restore", str(bak_out), "--replace"]) == 0
    assert "geri yüklendi" in capsys.readouterr().out

    assert cli.run(["--work-dir", str(work_dir), "--set", "theme", "light"]) == 0
    assert cli.run(["--work-dir", str(work_dir), "--get", "theme"]) == 0
    assert "theme=light" in capsys.readouterr().out

    assert cli.run(["--work-dir", str(work_dir), "--web", "--port", "0", "--shutdown-after", "0.15"]) == 0
    assert "http://127.0.0.1:" in capsys.readouterr().out

    from qtp_app.core.engine import QtpEngine
    eng = QtpEngine(work_dir=work_dir)
    assert eng.resolve_item("") is None
    assert eng.resolve_item("Merhaba Dünya") is not None
    assert eng.op_show_ini("yok").exit_code == 2
    assert eng.op_paste("yok").exit_code == 2
    assert eng.op_import_ini(FIXTURES_DIR / "minimal.ini", mode="replace").exit_code == 0
    bad_ini = tmp_path / "bad.ini"
    bad_ini.write_text("bozuk ini icerigi", encoding="utf-8")
    assert eng.op_import_ini(bad_ini).exit_code == 2
    assert eng.op_restore("").exit_code == 1
    assert eng.op_restore(tmp_path / "yok.json").exit_code == 1
    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{bozuk", encoding="utf-8")
    assert eng.op_restore(bad_json).exit_code == 2
    assert eng.op_restore("olmayan_yedek_id").exit_code == 1
    assert eng.op_restore(bak_out, mode="merge").exit_code == 0
    assert eng.op_get_setting(None).exit_code == 0

    fake_k32 = mock.Mock()
    fake_k32.AttachConsole.return_value = 0
    fake_k32.AllocConsole.return_value = 1
    with mock.patch("qtp_app.cli.sys.platform", "win32"), \
         mock.patch("qtp_app.cli.sys.stdout", None), \
         mock.patch("qtp_app.cli.sys.stderr", None), \
         mock.patch("qtp_app.cli.sys.stdin", None), \
         mock.patch("qtp_app.cli.ctypes.windll", mock.Mock(kernel32=fake_k32), create=True), \
         mock.patch("builtins.open", return_value=capsys._pytest_outer_stdout if hasattr(capsys, "_pytest_outer_stdout") else mock.MagicMock()):
        cli.attach_windows_console_if_needed("tui")
    fake_k32.AttachConsole.assert_called_once_with(-1)
    fake_k32.AllocConsole.assert_called_once()

    with mock.patch("qtp_app.tui.run_tui", return_value=0) as rt:
        assert cli.run(["--work-dir", str(work_dir), "--tui"]) == 0
        rt.assert_called_once()
    with mock.patch("qtp_app.main.launch_gui", return_value=0) as lg:
        assert cli.run(["--work-dir", str(work_dir), "--gui"]) == 0
        lg.assert_called_once()

    with mock.patch("qtp_app.core.engine.is_dir_writable", return_value=False):
        ro_eng = QtpEngine(work_dir=tmp_path / "ro_work", seed_defaults=False)
        assert len(ro_eng.items) >= 500
    with mock.patch("qtp_app.core.engine.get_bundled_default_path", return_value=tmp_path / "missing.ini"):
        assert eng.op_selftest(run_ui_smoke=False).exit_code == 1
    with mock.patch("qtp_app.core.engine.serialize_qtp_ini", return_value="bozuk"):
        assert eng.op_selftest(run_ui_smoke=False).exit_code == 1
    with mock.patch("qtp_app.core.engine.copy_to_clipboard", return_value=False):
        assert eng.op_copy("text_000").exit_code == 3
    with mock.patch("qtp_app.core.engine.paste_into_active_app", return_value=mock.Mock(ok=False, copied=True, pasted=False, method="err", warning="hata", exit_code=4)):
        assert eng.op_paste("text_000").exit_code == 4
    assert eng.op_export_ini(tmp_path / "x" / "y" / "out.ini").exit_code in (0, 1)
    eng.items = []
    assert eng.op_export_ini(tmp_path / "empty.ini").exit_code == 1

    from qtp_app.core.engine import read_doc_text
    assert "Belge dosyası bulunamadı" in read_doc_text("olmayan_belge.md")
    assert cli.run(["--work-dir", str(work_dir), "--help", "--json"]) == 0
    capsys.readouterr()
    with mock.patch("qtp_app.core.engine.copy_to_clipboard", return_value=False):
        assert cli.run(["--work-dir", str(work_dir), "--copy", "text_000"]) == 3
    with mock.patch("qtp_app.core.engine.paste_into_active_app", return_value=mock.Mock(ok=False, copied=True, pasted=False, method="err", warning="hata", exit_code=4)):
        assert cli.run(["--work-dir", str(work_dir), "--paste", "text_000"]) == 4
    with mock.patch("qtp_app.core.engine.load_state", side_effect=RuntimeError("disk error")):
        assert eng.reload_data().exit_code == 1
    with mock.patch("qtp_app.core.engine.create_backup", return_value=None):
        assert eng.op_backup().exit_code == 1
    with mock.patch("qtp_app.core.engine.create_backup", side_effect=RuntimeError("bak err")):
        assert eng.op_backup().exit_code == 1
    with mock.patch("qtp_app.core.engine.write_full_backup_file", side_effect=RuntimeError("exp err")):
        assert eng.op_export_backup(tmp_path / "x.json").exit_code == 1
    with mock.patch("qtp_app.core.engine.restore_backup", side_effect=RuntimeError("res err")):
        assert eng.op_restore("yedek_id_1").exit_code == 2
    assert eng.op_restore("alt/yedek.json").exit_code == 1

    from qtp_app.core.engine import OperationResult, _get_git_short_sha, get_bundled_default_path, get_bundled_docs_dir
    r_warn = OperationResult(ok=True, exit_code=0, message="ok", warning="uyarı").to_api_dict()
    assert r_warn["warning"] == "uyarı"

    fake_meipass = tmp_path / "mei"
    (fake_meipass / "qtp_app" / "assets" / "defaults").mkdir(parents=True)
    (fake_meipass / "qtp_app" / "assets" / "defaults" / "QuickTextPaste.ini").write_text("ok", encoding="utf-8")
    (fake_meipass / "docs").mkdir(parents=True)
    with mock.patch.object(sys, "frozen", True, create=True), \
         mock.patch.object(sys, "_MEIPASS", str(fake_meipass), create=True), \
         mock.patch("importlib.resources.files", side_effect=RuntimeError("no pkg")):
        assert get_bundled_default_path("QuickTextPaste.ini") == fake_meipass / "qtp_app" / "assets" / "defaults" / "QuickTextPaste.ini"
        assert get_bundled_docs_dir() == fake_meipass / "docs"

    with mock.patch("qtp_app.core.engine.subprocess.run", side_effect=OSError("no git")):
        assert _get_git_short_sha() is None
    with mock.patch("qtp_app.core.engine.decode_bytes_auto", side_effect=RuntimeError("decode crash")):
        assert eng.op_selftest(run_ui_smoke=False).exit_code == 1
    with mock.patch("qtp_app.core.engine.parse_qtp_ini", return_value=mock.Mock(items=[])):
        assert eng.op_selftest(run_ui_smoke=False).exit_code == 1
    with mock.patch("qtp_app.core.engine.shutil.copy2", side_effect=OSError("copy err")):
        eng._seed_defaults_if_empty(True)
    with mock.patch.dict("sys.modules", {"PyQt6": None, "PyQt6.QtWidgets": None}):
        assert eng.op_selftest(run_ui_smoke=True).exit_code == 0
    with mock.patch("qtp_app.core.engine.read_text_auto", side_effect=OSError("io fail")):
        assert eng.op_import_ini(FIXTURES_DIR / "minimal.ini").exit_code == 1
        assert eng.op_restore(FIXTURES_DIR / "data.json").exit_code == 1
    with mock.patch("qtp_app.core.engine.get_bundled_default_path", return_value=tmp_path / "none.ini"):
        eng.items = [{"keys": "L-Win+A", "group": "G", "text": "T"}]
        empty_work = tmp_path / "empty_rel"
        empty_work.mkdir()
        eng.work_dir = empty_work
        eng.ini_path = empty_work / "none2.ini"
        eng.settings["data_path"] = "./none2.ini"
        assert eng.reload_data().data["count"] == 0


