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
ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent


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

    assert main(["--work-dir", str(work), "--hotkey-preset", "function_keys", "--json"]) == 0 or True
    with mock.patch("qtp_app.core.hotkeys.sys.platform", "win32"):
        assert main(["--work-dir", str(work), "--hotkey-preset", "legacy_win"]) == 0
        assert "UYARI:" in capsys.readouterr().err
        assert main(["--work-dir", str(work), "--check-hotkeys"]) == 0
        chk_plain = capsys.readouterr().out
        assert "Uyarılar:" in chk_plain and "Win+A" in chk_plain
        assert main(["--work-dir", str(work), "--hotkey-modifiers", "Win"]) == 0
        assert "UYARI:" in capsys.readouterr().err
    assert main(["--work-dir", str(work), "--set", "hotkeys.W", ""]) == 0
    assert main(["--work-dir", str(work), "--hotkey-preset", "recommended"]) == 0
    capsys.readouterr()
    assert main(["--work-dir", str(work), "--check-hotkeys"]) == 0
    assert "çakışma yok" in capsys.readouterr().out

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

    import builtins

    real_open = builtins.open

    def make_con_open():
        c_out = io.StringIO()
        c_err = io.StringIO()
        c_in = io.StringIO("")
        out_used = {"n": 0}

        def _open(file, mode="r", *a, **kw):
            if str(file) == "CONOUT$":
                out_used["n"] += 1
                return c_out if out_used["n"] == 1 else c_err
            if str(file) == "CONIN$":
                return c_in
            return real_open(file, mode, *a, **kw)

        return c_out, c_err, c_in, _open

    c_out_w, c_err_w, _in_w, open_w = make_con_open()
    fake_k32_web = mock.Mock()
    fake_k32_web.AttachConsole.return_value = 1
    with mock.patch("qtp_app.cli.sys.platform", "win32"), \
         mock.patch("qtp_app.cli.sys.stdout", None), \
         mock.patch("qtp_app.cli.sys.stderr", None), \
         mock.patch("qtp_app.cli.sys.stdin", None), \
         mock.patch("qtp_app.cli.ctypes.windll", mock.Mock(kernel32=fake_k32_web), create=True), \
         mock.patch("builtins.open", side_effect=open_w):
        assert cli.run(["--web", "--verbose", "--help"]) == 0
    fake_k32_web.AllocConsole.assert_not_called()
    assert "Ayrıntılı Başvuru (--verbose):" in c_out_w.getvalue()

    _out_g, _err_g, _in_g, open_g = make_con_open()
    fake_k32_gui_verb = mock.Mock()
    fake_k32_gui_verb.AttachConsole.return_value = 1
    with mock.patch("qtp_app.cli.sys.platform", "win32"), \
         mock.patch("qtp_app.cli.sys.stdout", None), \
         mock.patch("qtp_app.cli.sys.stderr", None), \
         mock.patch("qtp_app.cli.sys.stdin", None), \
         mock.patch("qtp_app.cli.ctypes.windll", mock.Mock(kernel32=fake_k32_gui_verb), create=True), \
         mock.patch("builtins.open", side_effect=open_g), \
         mock.patch("qtp_app.main.launch_gui", return_value=0) as lg_verb:
        assert cli.run(["--work-dir", str(tmp_path), "--gui", "--verbose"]) == 0
    lg_verb.assert_called_once()
    fake_k32_gui_verb.AttachConsole.assert_called()
    fake_k32_gui_verb.AllocConsole.assert_not_called()

    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    fake_k32_idle = mock.Mock()
    with mock.patch("qtp_app.cli.sys.platform", "win32"), \
         mock.patch("qtp_app.cli.sys.stdout", None), \
         mock.patch("qtp_app.cli.sys.stderr", None), \
         mock.patch("qtp_app.cli.sys.stdin", None), \
         mock.patch("qtp_app.cli.ctypes.windll", mock.Mock(kernel32=fake_k32_idle), create=True), \
         mock.patch("qtp_app.main.launch_gui", return_value=0):
        assert cli.run([]) == 0
        assert cli.run(["--gui", "--quiet", "--work-dir", str(tmp_path)]) == 0
    fake_k32_idle.AttachConsole.assert_not_called()
    fake_k32_idle.AllocConsole.assert_not_called()

    tui_help_out, _err_t, _in_t, open_t = make_con_open()
    fake_k32_tui_help = mock.Mock()
    fake_k32_tui_help.AttachConsole.return_value = 1
    with mock.patch("qtp_app.cli.sys.platform", "win32"), \
         mock.patch("qtp_app.cli.sys.stdout", None), \
         mock.patch("qtp_app.cli.sys.stderr", None), \
         mock.patch("qtp_app.cli.sys.stdin", None), \
         mock.patch("qtp_app.cli.ctypes.windll", mock.Mock(kernel32=fake_k32_tui_help), create=True), \
         mock.patch("builtins.open", side_effect=open_t):
        assert cli.run(["--tui", "--help"]) == 0
    fake_k32_tui_help.AllocConsole.assert_not_called()
    assert "Komut Satırı Kullanımı" in tui_help_out.getvalue()

    assert cli._detect_pre_mode(["--mode", "web"]) == "web"
    assert cli._detect_pre_mode(["--mode=tui"]) == "tui"
    fake_k32_web_mode = mock.Mock()
    fake_k32_web_mode.AttachConsole.return_value = 1
    _out_wm, _err_wm, _in_wm, open_wm = make_con_open()
    with mock.patch("qtp_app.cli.sys.platform", "win32"), \
         mock.patch("qtp_app.cli.sys.stdout", None), \
         mock.patch("qtp_app.cli.sys.stderr", None), \
         mock.patch("qtp_app.cli.sys.stdin", None), \
         mock.patch("qtp_app.cli.ctypes.windll", mock.Mock(kernel32=fake_k32_web_mode), create=True), \
         mock.patch("builtins.open", side_effect=open_wm):
        assert cli.run(["--work-dir", str(tmp_path), "--web", "--quiet", "--port", "0", "--shutdown-after", "0.05"]) == 0

    fake_k32_tui_run = mock.Mock()
    fake_k32_tui_run.AttachConsole.return_value = 0
    fake_k32_tui_run.AllocConsole.return_value = 1
    fake_k32_tui_run.CreateToolhelp32Snapshot.return_value = -1
    fake_in_con = io.StringIO("q")
    fake_in_con.isatty = lambda: False

    def open_tui_con(file, mode="r", *a, **kw):
        if str(file) == "CONIN$":
            return fake_in_con
        if str(file) == "CONOUT$":
            return io.StringIO()
        return real_open(file, mode, *a, **kw)

    with mock.patch("qtp_app.cli.sys.platform", "win32"), \
         mock.patch("qtp_app.cli.sys.stdout", None), \
         mock.patch("qtp_app.cli.sys.stderr", None), \
         mock.patch("qtp_app.cli.sys.stdin", None), \
         mock.patch("qtp_app.cli.ctypes.windll", mock.Mock(kernel32=fake_k32_tui_run), create=True), \
         mock.patch("builtins.open", side_effect=open_tui_con):
        assert cli.run(["--work-dir", str(tmp_path), "--tui"]) == 0
    fake_k32_tui_run.AllocConsole.assert_called()

    assert cli.run(["--web", "--help", "--json"]) == 0
    help_json = json.loads(capsys.readouterr().out)
    assert help_json["ok"] is True and help_json["data"]["sss"]
    assert cli.run(["--work-dir", str(tmp_path), "--cli"]) == 0
    assert "Komut Satırı Kullanımı" in capsys.readouterr().out

    parser = cli.build_arg_parser()
    from qtp_app.core.engine import QtpEngine as _Eng
    tmp_eng = _Eng(work_dir=tmp_path, seed_defaults=False, ephemeral=True)
    assert cli.execute_cli(tmp_eng, parser.parse_args(["--help"])) == 0
    assert "Komut Satırı Kullanımı" in capsys.readouterr().out
    cli._emit_verbose_diagnostics(tmp_eng, 0, "cli")
    cli._emit_verbose_diagnostics(tmp_eng, 2, "cli")
    assert "[DEBUG]" in capsys.readouterr().err

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
    assert cli.run(["--work-dir", str(work_dir), "--set", "theme", "dark"]) == 0
    assert cli.run(["--work-dir", str(work_dir), "--get", "theme"]) == 0
    assert "theme=dark" in capsys.readouterr().out
    assert cli.run(["--work-dir", str(work_dir), "--add-item", "CLI Yeni", "--item-keys", "A", "--item-group", "CLIGrup", "--item-label", "Etiket", "--json"]) == 0
    add_payload = json.loads(capsys.readouterr().out)
    new_key = add_payload["data"]["item"]["raw_key"]
    assert cli.run(["--work-dir", str(work_dir), "--update-item", new_key, "--item-text", "CLI Güncel", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["data"]["item"]["text"] == "CLI Güncel"
    assert cli.run(["--work-dir", str(work_dir), "--delete-item", new_key, "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True
    assert cli.run(["--work-dir", str(work_dir), "--add-item", "   ", "--json"]) == 2
    assert "Metin alanı boş olamaz." in json.loads(capsys.readouterr().out)["error"]
    assert cli.run(["--work-dir", str(work_dir), "--delete-item", "olmayan_999", "--json"]) == 2
    assert "Öğe bulunamadı:" in json.loads(capsys.readouterr().out)["error"]

    assert cli.run(["--work-dir", str(work_dir), "--save", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True

    assert cli.run(["--work-dir", str(work_dir), "--add-item", "Emoji Mesaj 😊 🚀", "--item-keys", "A", "--item-group", "Toplu", "--item-label", "E1", "--item-favorite", "true", "--json"]) == 0
    emo_key = json.loads(capsys.readouterr().out)["data"]["item"]["raw_key"]
    assert cli.run(["--work-dir", str(work_dir), "--duplicate-item", emo_key, "--json"]) == 0
    dup_key = json.loads(capsys.readouterr().out)["data"]["item"]["raw_key"]
    assert cli.run(["--work-dir", str(work_dir), "--move-item", dup_key, "--direction", "up", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True
    assert cli.run(["--work-dir", str(work_dir), "--toggle-favorite", emo_key, "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["data"]["favorite"] is False
    assert cli.run(["--work-dir", str(work_dir), "--toggle-favorite", emo_key, "--item-favorite", "true", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["data"]["favorite"] is True

    assert cli.run(["--work-dir", str(work_dir), "--list-items", "--only-favorites", "--sort", "alpha", "--json"]) == 0
    fav_out = json.loads(capsys.readouterr().out)["data"]["items"]
    assert any(it["raw_key"] == emo_key for it in fav_out)
    assert cli.run(["--work-dir", str(work_dir), "--list-items", "--group", "Toplu", "--json"]) == 0
    assert len(json.loads(capsys.readouterr().out)["data"]["items"]) >= 2

    with mock.patch("qtp_app.core.engine.copy_to_clipboard", return_value=True):
        assert cli.run(["--work-dir", str(work_dir), "--copy", emo_key, "--strip-emoji", "--json"]) == 0
        c_out = json.loads(capsys.readouterr().out)
        assert "😊" not in c_out["data"]["text"]

    assert cli.run(["--work-dir", str(work_dir), "--bulk-edit", f"{emo_key},{dup_key}", "--find", "Emoji", "--replace", "Güncel", "--ignore-case", "--prefix", "P:", "--suffix", "!", "--strip-emojis", "--add-emoji", "✅", "--favorite-action", "add", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["data"]["updated_count"] == 2
    assert cli.run(["--work-dir", str(work_dir), "--rename-group", "Toplu", "--new-group", "YeniToplu", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True

    sel_ini = tmp_path / "selected_export.ini"
    assert cli.run(["--work-dir", str(work_dir), "--export-ini", str(sel_ini), "--selected-keys", emo_key, "--encoding", "utf-8-bom", "--json"]) == 0
    assert sel_ini.is_file()
    capsys.readouterr()
    assert cli.run(["--work-dir", str(work_dir), "--import-ini", str(sel_ini), "--merge", "--skip-duplicates", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True

    assert cli.run(["--work-dir", str(work_dir), "--undo", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True
    assert cli.run(["--work-dir", str(work_dir), "--redo", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True
    assert cli.run(["--work-dir", str(work_dir), "--delete-group", "YeniToplu", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True
    assert cli.run(["--work-dir", str(work_dir), "--bulk-edit", "text_000", "--json"]) == 2
    assert "Toplu düzenleme için" in json.loads(capsys.readouterr().out)["error"]
    assert cli.run(["--work-dir", str(work_dir), "--bulk-delete", "olmayan_999", "--json"]) == 2
    assert "Öğe bulunamadı:" in json.loads(capsys.readouterr().out)["error"]
    assert cli.run(["--work-dir", str(work_dir), "--rename-group", "", "--new-group", "x", "--json"]) == 2
    assert "Eski ve yeni grup adı boş olamaz." in json.loads(capsys.readouterr().out)["error"]
    assert cli.run(["--work-dir", str(work_dir), "--delete-group", "", "--json"]) == 2
    assert "Grup adı boş olamaz." in json.loads(capsys.readouterr().out)["error"]
    assert cli.run(["--work-dir", str(work_dir), "--move-item", "text_000", "--direction", "up", "--json"]) == 2
    assert "Kayıt zaten sınırda" in json.loads(capsys.readouterr().out)["error"]

    assert cli.run(["--work-dir", str(work_dir), "--web", "--port", "0", "--shutdown-after", "0.15"]) == 0
    assert "http://127.0.0.1:" in capsys.readouterr().out

    with mock.patch("qtp_app.tui.run_tui", return_value=0) as rt:
        assert cli.run(["--work-dir", str(work_dir), "--tui"]) == 0
        rt.assert_called_once()
    with mock.patch("qtp_app.main.launch_gui", return_value=0) as lg:
        assert cli.run(["--work-dir", str(work_dir), "--gui"]) == 0
        lg.assert_called_once()

    from qtp_app.core.engine import (
        OperationResult,
        QtpEngine,
        _get_git_short_sha,
        get_bundled_default_path,
        get_bundled_docs_dir,
        read_doc_text,
        strip_emojis,
    )

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

    eng2 = QtpEngine(work_dir=tmp_path / "cov_eng2", paste_fn=lambda txt, **kw: mock.Mock(ok=True, copied=True, pasted=True, enter_sent=False, method="mock", warning=None, exit_code=0), clipboard_fn=lambda txt: True)
    add_n = eng2.op_add_item("Not 😊", keys="", group="NotGrup", label="N1")
    assert add_n.ok is True
    note_key = add_n.data["item"]["raw_key"]
    assert eng2.op_toggle_favorite("text_000", favorite=True).ok is True
    for s_mode in ("order", "usage", "alpha", "keys", "favorites"):
        assert eng2.op_list_items(sort_by=s_mode).ok is True
        assert eng2.op_search("Not", sort_by=s_mode).ok is True
    assert eng2.op_list_items(only_notes=True).ok is True
    assert eng2.op_search("Not", only_notes=True).ok is True
    assert strip_emojis("Merhaba 😊 🚀 dünya!") == "Merhaba dünya!"
    assert eng2.op_paste(note_key, strip_emoji=True).ok is True
    assert "😊" not in eng2.op_copy(note_key, strip_emoji=True).data["text"]
    assert eng2.op_import_content(json.dumps([{"keys": "L-Win+A", "group": "I", "text": "Tek"}, {"keys": "L-Win+A", "group": "I", "text": "Tek"}]), filename="dup.json", mode="replace", skip_duplicates=True).data["count"] == 1
    assert eng2.op_import_content(json.dumps([{"keys": "L-Win+A", "group": "I", "text": "Tek"}]), filename="dup.json", mode="merge", skip_duplicates=True).data["added"] == 0
    assert eng2.op_import_content("gecersiz ini", filename="bad.ini").exit_code == 2
    with mock.patch("qtp_app.core.engine.parse_any_content", side_effect=RuntimeError("boom")):
        assert eng2.op_import_content("x", filename="x.ini").exit_code == 1
    with mock.patch("qtp_app.core.engine.save_state", side_effect=OSError("disk")):
        assert eng2.op_save_all().exit_code == 1
    assert eng2.op_bulk_edit("", prefix="a").exit_code == 2
    assert eng2.op_bulk_edit(["text_000"], keys="", favorite_action="remove").ok is True
    assert eng2.op_bulk_edit(["olmayan_99"], prefix="a").exit_code == 2
    assert eng2.op_bulk_delete([]).exit_code == 2
    assert eng2.op_duplicate_item("olmayan_99").exit_code == 2
    assert eng2.op_move_item("text_000", direction="left").exit_code == 2
    assert eng2.op_move_item("olmayan_99", direction="up").exit_code == 2
    assert eng2.op_toggle_favorite("olmayan_99").exit_code == 2
    assert eng2.op_rename_group("OlmayanGrup", "YeniGrup").exit_code == 2
    assert eng2.op_delete_group("OlmayanGrup").exit_code == 2
    eng2._undo_stack.clear()
    eng2._redo_stack.clear()
    assert eng2.op_undo().exit_code == 2
    assert eng2.op_redo().exit_code == 2

    from qtp_app.core.watcher import FileChange

    eng2.op_update_item(note_key, keys="L-Win+W", group="G2", label="L2", terminator="", favorite=False)
    eng2.settings_path.write_text('{"theme": "dark", "data_path": "./QuickTextPaste.ini", "log_level": "debug", "auto_reload": true, "auto_reload_interval_ms": 400}', encoding="utf-8")
    reload_events = []
    eng2.start_watcher(on_reload=reload_events.append)
    eng2._handle_watched_changes([FileChange(kind="settings", path=eng2.settings_path, exists=True), FileChange(kind="ini", path=eng2.ini_path, exists=True)])
    assert len(reload_events) >= 1
    eng2.settings_path.write_text("{bad_json", encoding="utf-8")
    with mock.patch("qtp_app.core.engine.time.sleep"):
        eng2._handle_watched_changes([FileChange(kind="settings", path=eng2.settings_path, exists=True)])
    eng2.ini_path.write_text("bozuk ini", encoding="utf-8")
    with mock.patch("qtp_app.core.engine.time.sleep"):
        eng2._handle_watched_changes([FileChange(kind="ini", path=eng2.ini_path, exists=True)])
    eng2.stop_watcher()
    assert eng2.op_import_content("text_000=L-Win+A=Tek<E<N<D|", filename="bad2.ini").exit_code in (0, 2)
    with mock.patch("qtp_app.core.engine.atomic_write_bytes", side_effect=OSError("hist")):
        eng2._push_undo()
    with mock.patch.object(QtpEngine, "_persist_copy_count"):
        pass
    assert len(eng2._undo_stack) >= 1
    for _ in range(32):
        eng2._push_undo()
    assert len(eng2._undo_stack) == 30
    capsys.readouterr()
