"""CLI bayrakları, Windows ata-PID AttachConsole, -v/-q, --completion ve kısayol komutları testleri."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest import mock

from qtp_app import __version__, cli
from qtp_app.core.ini_parser import parse_qtp_ini, read_text_auto
from qtp_app.core.json_store import load_data_json, save_data_json
from qtp_app.main import main

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
ROOT_DIR = Path(__file__).resolve().parent.parent.parent


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


def test_cli_help_and_verbose_help_turkish(capsys, tmp_path: Path, monkeypatch):
    app_dir = tmp_path / "isolated_help"
    app_dir.mkdir()
    monkeypatch.setattr("qtp_app.core.engine.get_app_dir", lambda: app_dir)

    code = main(["--help"])
    assert code == 0
    out = capsys.readouterr().out
    for flag in ("--help", "--version", "--selftest", "--export-ini", "--import-ini", "--completion", "--verbose"):
        assert flag in out
    assert "Komut Satırı Kullanımı" in out
    assert list(app_dir.iterdir()) == []

    for argv in (["--verbose", "--help"], ["--cli", "--verbose", "--help"], ["-v", "-h"]):
        assert main(argv) == 0
        vout = capsys.readouterr().out
        assert "Ayrıntılı Başvuru (--verbose):" in vout
        assert "function_keys" in vout
        assert "Register-ArgumentCompleter" in vout or "completion powershell" in vout
        assert list(app_dir.iterdir()) == []


def test_cli_verbose_diagnostics_and_quiet(capsys, tmp_path: Path, monkeypatch):
    app_dir = tmp_path / "isolated_v"
    app_dir.mkdir()
    monkeypatch.setattr("qtp_app.core.engine.get_app_dir", lambda: app_dir)
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    assert main(["-vv", "--selftest"]) == 0
    captured = capsys.readouterr()
    assert "Otomatik test başarılı" in captured.out
    assert "[INFO]" in captured.err and "[DEBUG]" in captured.err

    work = tmp_path / "quiet_work"
    work.mkdir()
    save_data_json(work / "data.json", [{"keys": "L-Win+A", "group": "G", "text": "Merhaba"}])
    assert main(["--work-dir", str(work), "-q", "--backup"]) == 0
    q_cap = capsys.readouterr()
    assert q_cap.out == ""


def test_cli_completion_all_shells_ephemeral_and_errors(capsys, tmp_path: Path, monkeypatch):
    app_dir = tmp_path / "isolated_comp"
    app_dir.mkdir()
    monkeypatch.setattr("qtp_app.core.engine.get_app_dir", lambda: app_dir)
    sss = (ROOT_DIR / "docs" / "SSS.md").read_text(encoding="utf-8")

    for sh, expected_tok in (
        ("powershell", "Register-ArgumentCompleter"),
        ("bash", "_qtp_completions"),
        ("zsh", "#compdef qtp qtp.bin"),
        ("fish", "complete -c qtp"),
    ):
        assert main(["--completion", sh]) == 0
        out = capsys.readouterr().out
        assert expected_tok in out
        assert "hotkey-preset" in out
        assert "web.port" in out
        assert list(app_dir.iterdir()) == []

    monkeypatch.setenv("SHELL", "/usr/bin/zsh")
    with mock.patch("qtp_app.core.engine.sys.platform", "linux"):
        assert main(["--completion", "--json"]) == 0
        parsed = json.loads(capsys.readouterr().out)
        assert parsed["data"]["shell"] == "zsh"

    from qtp_app.core.engine import detect_target_shell, format_hotkeys_toast

    assert detect_target_shell("auto", platform_name="linux", env={"SHELL": "/usr/bin/fish"}) == "fish"
    assert detect_target_shell("auto", platform_name="linux", env={"SHELL": "/bin/bash"}) == "bash"
    assert detect_target_shell("auto", platform_name="win32", env={}) == "powershell"
    assert detect_target_shell("auto", platform_name="linux", env={"PSModulePath": "/ps", "SHELL": "pwsh"}) == "powershell"
    assert "Win+Ctrl+W" in format_hotkeys_toast({"all": "", "W": "Win+Ctrl+W"})
    assert "Ctrl+," in format_hotkeys_toast({"all": ""})

    with mock.patch("qtp_app.core.engine.sys.platform", "win32"):
        monkeypatch.delenv("SHELL", raising=False)
        assert main(["--completion"]) == 0
        assert "Register-ArgumentCompleter" in capsys.readouterr().out

    assert main(["--completion", "invalid_shell"]) == 2
    err = capsys.readouterr().err
    assert "Desteklenmeyen kabuk türü:" in err
    assert "Desteklenmeyen kabuk türü:" in sss
    assert list(app_dir.iterdir()) == []


def test_cli_hotkey_check_preset_and_modifiers(capsys, tmp_path: Path):
    work = tmp_path / "hk_cli"
    work.mkdir()
    assert main(["--work-dir", str(work), "--check-hotkeys", "--json"]) == 0
    chk = json.loads(capsys.readouterr().out)
    assert chk["ok"] is True and chk["data"]["clean"] is True
    assert chk["data"]["hotkeys"]["all"] == "Win+Alt+Space"

    assert main(["--work-dir", str(work), "--hotkey-preset", "function_keys", "--json"]) == 0
    pr = json.loads(capsys.readouterr().out)
    assert pr["data"]["hotkeys"]["all"] == "Ctrl+Shift+F1"

    assert main(["--work-dir", str(work), "--hotkey-modifiers", "Win+Ctrl", "--json"]) == 0
    mr = json.loads(capsys.readouterr().out)
    assert mr["data"]["hotkeys"]["all"] == "Win+Ctrl+F1"

    assert main(["--work-dir", str(work), "--set", "hotkeys.W", "Ctrl+Shift+Alt+W"]) == 0
    capsys.readouterr()
    assert main(["--work-dir", str(work), "--get", "hotkeys.W", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["data"]["value"] == "Ctrl+Alt+Shift+W"

    assert main(["--work-dir", str(work), "--hotkey-preset", "bad_preset"]) == 2
    assert main(["--work-dir", str(work), "--hotkey-modifiers", "InvalidMod"]) == 2
    capsys.readouterr()


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


def test_windows_ancestor_pid_console_attach_before_argparse(capsys, tmp_path: Path, monkeypatch):
    import io

    my_pid = os.getpid()
    fake_k32 = mock.Mock()
    fake_k32.AttachConsole.side_effect = [0, 0, 1]
    fake_k32.AllocConsole.return_value = 1

    rows = [(my_pid, 9001), (9001, 4444), (4444, 1)]
    idx = {"i": 0}
    fake_k32.CreateToolhelp32Snapshot.return_value = 777

    def fill_entry(entry_ptr, _i):
        import ctypes

        entry = ctypes.cast(entry_ptr, ctypes.POINTER(cli.PROCESSENTRY32W)).contents
        pid, ppid = rows[idx["i"]]
        entry.th32ProcessID = pid
        entry.th32ParentProcessID = ppid
        idx["i"] += 1

    def first_w(_snap, entry_ptr):
        fill_entry(entry_ptr, 0)
        return 1

    def next_w(_snap, entry_ptr):
        if idx["i"] >= len(rows):
            return 0
        fill_entry(entry_ptr, idx["i"])
        return 1

    fake_k32.Process32FirstW.side_effect = first_w
    fake_k32.Process32NextW.side_effect = next_w

    out_con = io.StringIO()
    err_con = io.StringIO()
    in_con = io.StringIO("")

    def fake_open(name, mode="r", **_kwargs):
        if name == "CONOUT$":
            return out_con if not out_con.closed else err_con
        return in_con

    app_dir = tmp_path / "con_isolated"
    app_dir.mkdir()
    monkeypatch.setattr("qtp_app.core.engine.get_app_dir", lambda: app_dir)

    with mock.patch("qtp_app.cli.sys.platform", "win32"), \
         mock.patch("qtp_app.cli.sys.stdout", None), \
         mock.patch("qtp_app.cli.sys.stderr", None), \
         mock.patch("qtp_app.cli.sys.stdin", None), \
         mock.patch("qtp_app.cli.ctypes.windll", mock.Mock(kernel32=fake_k32), create=True), \
         mock.patch("builtins.open", side_effect=[out_con, err_con, in_con]):
        code = cli.run(["--help"])

    assert code == 0
    assert fake_k32.AttachConsole.call_args_list == [mock.call(-1), mock.call(9001), mock.call(4444)]
    fake_k32.SetConsoleOutputCP.assert_called_with(65001)
    fake_k32.SetConsoleCP.assert_called_with(65001)
    assert "Komut Satırı Kullanımı" in out_con.getvalue()

    fake_k32_tui = mock.Mock()
    fake_k32_tui.AttachConsole.return_value = 0
    fake_k32_tui.AllocConsole.return_value = 1
    fake_k32_tui.CreateToolhelp32Snapshot.return_value = -1
    with mock.patch("qtp_app.cli.sys.platform", "win32"), \
         mock.patch("qtp_app.cli.sys.stdout", None), \
         mock.patch("qtp_app.cli.sys.stderr", None), \
         mock.patch("qtp_app.cli.sys.stdin", None), \
         mock.patch("qtp_app.cli.ctypes.windll", mock.Mock(kernel32=fake_k32_tui), create=True), \
         mock.patch("builtins.open", return_value=io.StringIO()):
        assert cli.attach_windows_console_if_needed("tui") is True
    fake_k32_tui.AttachConsole.assert_called_once_with(-1)
    fake_k32_tui.AllocConsole.assert_called_once()


def test_cli_unknown_flag_and_full_subcommands(tmp_path: Path, capsys, monkeypatch):
    code_bad = main(["--bilinmeyen-bayrak"])
    assert code_bad == 2
    assert "Bilinmeyen komut satırı seçeneği" in capsys.readouterr().err

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
    assert cli.run(["--work-dir", str(work_dir), "--restore", str(bak_out), "--replace"]) == 0
    assert cli.run(["--work-dir", str(work_dir), "--set", "theme", "light"]) == 0
    assert cli.run(["--work-dir", str(work_dir), "--get", "theme"]) == 0
    assert "theme=light" in capsys.readouterr().out
    assert cli.run(["--work-dir", str(work_dir), "--web", "--port", "0", "--shutdown-after", "0.15"]) == 0
    assert "http://127.0.0.1:" in capsys.readouterr().out

    with mock.patch("qtp_app.tui.run_tui", return_value=0) as rt:
        assert cli.run(["--work-dir", str(work_dir), "--tui"]) == 0
        rt.assert_called_once()
    with mock.patch("qtp_app.main.launch_gui", return_value=0) as lg:
        assert cli.run(["--work-dir", str(work_dir), "--gui"]) == 0
        lg.assert_called_once()

    from qtp_app.core.engine import QtpEngine, OperationResult, _get_git_short_sha, get_bundled_default_path, get_bundled_docs_dir, read_doc_text

    eng = QtpEngine(work_dir=work_dir)
    assert eng.resolve_item("") is None
    assert eng.op_show_ini("yok").exit_code == 2
    assert eng.op_paste("yok").exit_code == 2
    assert eng.op_import_ini(tmp_path / "yok.ini").exit_code == 1
    assert eng.op_import_ini(FIXTURES_DIR / "minimal.ini", mode="replace").exit_code == 0
    assert eng.op_restore("").exit_code == 1
    assert eng.op_restore(tmp_path / "yok.json").exit_code == 1
    assert eng.op_restore("olmayan_yedek_id").exit_code == 1
    assert eng.op_get_setting(None).exit_code == 0
    assert "Belge dosyası bulunamadı" in read_doc_text("olmayan_belge.md")
    assert OperationResult(ok=True, exit_code=0, message="ok", warning="uyarı").to_api_dict()["warning"] == "uyarı"

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

    with mock.patch("qtp_app.core.engine.is_dir_writable", return_value=False):
        ro_eng = QtpEngine(work_dir=tmp_path / "ro_work", seed_defaults=False)
        assert len(ro_eng.items) >= 500
    with mock.patch("qtp_app.core.engine.get_bundled_default_path", return_value=tmp_path / "missing.ini"):
        assert eng.op_selftest(run_ui_smoke=False).exit_code == 1
    with mock.patch("qtp_app.core.engine.serialize_qtp_ini", return_value="bozuk"):
        assert eng.op_selftest(run_ui_smoke=False).exit_code == 1
    with mock.patch("qtp_app.core.engine.decode_bytes_auto", side_effect=RuntimeError("decode crash")):
        assert eng.op_selftest(run_ui_smoke=False).exit_code == 1
    with mock.patch("qtp_app.core.engine.parse_qtp_ini", return_value=mock.Mock(items=[])):
        assert eng.op_selftest(run_ui_smoke=False).exit_code == 1
    with mock.patch.dict("sys.modules", {"PyQt6": None, "PyQt6.QtWidgets": None}):
        assert eng.op_selftest(run_ui_smoke=True).exit_code == 0
    with mock.patch("qtp_app.core.engine.copy_to_clipboard", return_value=False):
        assert eng.op_copy("text_000").exit_code == 3
        assert cli.run(["--work-dir", str(work_dir), "--copy", "text_000"]) == 3
    with mock.patch("qtp_app.core.engine.paste_into_active_app", return_value=mock.Mock(ok=False, copied=True, pasted=False, method="err", warning="hata", exit_code=4)):
        assert eng.op_paste("text_000").exit_code == 4
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
    bad_ini = tmp_path / "bad_cli.ini"
    bad_ini.write_text("bozuk ini icerigi", encoding="utf-8")
    assert eng.op_import_ini(bad_ini).exit_code == 2
    bad_json = tmp_path / "bad_cli.json"
    bad_json.write_text("{bozuk", encoding="utf-8")
    assert eng.op_restore(bad_json).exit_code == 2
    with mock.patch("qtp_app.core.engine.read_text_auto", side_effect=OSError("io fail")):
        assert eng.op_import_ini(FIXTURES_DIR / "minimal.ini").exit_code == 1
        assert eng.op_restore(FIXTURES_DIR / "data.json").exit_code == 1
    with mock.patch("qtp_app.core.engine.shutil.copy2", side_effect=OSError("copy err")):
        eng._seed_defaults_if_empty(True)
    with mock.patch("qtp_app.core.engine.write_qtp_ini", side_effect=OSError("write err")):
        assert eng.op_export_ini(tmp_path / "fail_out.ini").exit_code == 1
    eng.items = []
    assert eng.op_export_ini(tmp_path / "empty.ini").exit_code == 1
    with mock.patch("qtp_app.core.engine.get_bundled_default_path", return_value=tmp_path / "none.ini"):
        eng.items = [{"keys": "L-Win+A", "group": "G", "text": "T"}]
        empty_work = tmp_path / "empty_rel"
        empty_work.mkdir()
        eng.work_dir = empty_work
        eng.ini_path = empty_work / "none2.ini"
        eng.settings["data_path"] = "./none2.ini"
        assert eng.reload_data().data["count"] == 0
    capsys.readouterr()
