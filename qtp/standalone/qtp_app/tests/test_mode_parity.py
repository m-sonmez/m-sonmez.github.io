"""Tüm çalışma modları (--gui, --tui, --cli, --web) için parametreli eşitlik testleri ve altın anlık görüntüler."""

from __future__ import annotations

import http.client
import json
import os
import shutil
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from qtp_app import cli
from qtp_app.core.engine import QtpEngine
from qtp_app.core.operations import OPERATIONS, OPERATIONS_BY_ID
from qtp_app.tui.app import QtpTui
from qtp_app.web import create_web_server

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
GOLDEN_DIR = Path(__file__).resolve().parent / "golden"


def _make_isolated_engine(tmp_path: Path) -> QtpEngine:
    from qtp_app.core.ini_parser import build_qtp_ini, write_qtp_ini
    from qtp_app.core.settings import DEFAULT_SETTINGS, save_settings

    work = tmp_path / "work"
    work.mkdir(parents=True, exist_ok=True)
    seed_items = [
        {"keys": "L-Win+1", "group": "General", "label": "Greeting", "text": "Merhaba Dünya!"},
        {"keys": "L-Win+2", "group": "Work", "label": "Update", "text": "Status update ready"},
    ]
    write_qtp_ini(work / "QuickTextPaste.ini", build_qtp_ini(seed_items), create_bak=False)
    cfg = dict(DEFAULT_SETTINGS)
    cfg["language"] = "en"
    save_settings(cfg, work / "qtp_settings.json")
    copied_texts: list[str] = []

    def fake_copy(txt: str) -> bool:
        copied_texts.append(txt)
        return True

    def fake_paste(txt: str, **kwargs) -> SimpleNamespace:
        copied_texts.append(txt)
        return SimpleNamespace(
            ok=True,
            copied=True,
            pasted=True,
            enter_sent=bool(kwargs.get("has_end_marker") and kwargs.get("enter_after_paste")),
            method="ctrl_v",
            warning=None,
            exit_code=0,
        )

    eng = QtpEngine(work_dir=work, seed_defaults=False, clipboard_fn=fake_copy, paste_fn=fake_paste)
    eng._test_copied = copied_texts
    return eng


def _assert_or_update_golden(subdir: str, op_id: str, rendered_text: str) -> None:
    path = GOLDEN_DIR / subdir / f"{op_id}.txt"
    if os.environ.get("UPDATE_GOLDEN") == "1":
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered_text, encoding="utf-8")
        return
    if not path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered_text, encoding="utf-8")
    expected = path.read_text(encoding="utf-8")
    assert rendered_text == expected, f"Altın anlık görüntü sapması ({subdir}/{op_id}.txt)"


def _invoke_mode_op(mode: str, engine: QtpEngine, op_id: str, tmp_path: Path, capsys) -> tuple[int, str, dict]:
    """Belirtilen mod adaptörü üzerinden işlemi çalıştırır -> (exit_code, msg, payload)."""
    import_ini_file = FIXTURES_DIR / "encoding_utf8bom.ini"
    export_ini_target = tmp_path / f"out_{mode}.ini"
    export_bak_target = tmp_path / f"bak_{mode}.json"
    bulk_targets = ",".join(it["raw_key"] for it in engine.items[:2]) or "text_000"
    group0 = str(engine.items[0].get("group") or "Genel") if engine.items else "Genel"

    if op_id == "undo":
        engine.op_toggle_favorite("text_000")
    elif op_id == "redo":
        engine.op_toggle_favorite("text_000")
        engine.op_undo()

    if mode == "cli":
        argv_map: dict[str, list[str]] = {
            "version": ["--version", "--json"],
            "help": ["--help", "--verbose", "--json"],
            "selftest": ["--selftest", "--json"],
            "modes": ["--modes", "--json"],
            "completion": ["--completion", "bash", "--json"],
            "list_categories": ["--list-categories", "--json"],
            "list_items": ["--list-items", "--json"],
            "search": ["--search", "Merhaba", "--json"],
            "show_ini": ["--show-ini", "text_000", "--json"],
            "copy": ["--copy", "text_000", "--json"],
            "paste": ["--paste", "text_000", "--json"],
            "export_ini": ["--export-ini", str(export_ini_target), "--json"],
            "import_ini": ["--import-ini", str(import_ini_file), "--merge", "--json"],
            "export_backup": ["--export-backup", str(export_bak_target), "--json"],
            "backup": ["--backup", "--json"],
            "restore": ["--restore", str(FIXTURES_DIR / "data.json"), "--replace", "--json"],
            "reload": ["--reload", "--json"],
            "save_all": ["--save", "--json"],
            "get_setting": ["--get", "theme", "--json"],
            "set_setting": ["--set", "theme", "light", "--json"],
            "check_hotkeys": ["--check-hotkeys", "--json"],
            "hotkey_preset": ["--hotkey-preset", "recommended", "--json"],
            "hotkey_modifiers": ["--hotkey-modifiers", "Win+Alt", "--json"],
            "add_item": ["--add-item", "Parite yeni cevap", "--item-keys", "A", "--item-group", "Parite", "--item-label", "Etiket", "--json"],
            "update_item": ["--update-item", "text_000", "--item-text", "Parite güncel cevap", "--json"],
            "delete_item": ["--delete-item", "text_000", "--json"],
            "duplicate_item": ["--duplicate-item", "text_000", "--json"],
            "move_item": ["--move-item", "text_001", "--direction", "up", "--json"],
            "toggle_favorite": ["--toggle-favorite", "text_000", "--json"],
            "bulk_edit": ["--bulk-edit", bulk_targets, "--prefix", "Önek ", "--json"],
            "bulk_delete": ["--bulk-delete", bulk_targets, "--json"],
            "rename_group": ["--rename-group", group0, "--new-group", "PariteGrup", "--json"],
            "delete_group": ["--delete-group", group0, "--json"],
            "undo": ["--undo", "--json"],
            "redo": ["--redo", "--json"],
        }
        parser = cli.build_arg_parser()
        args = parser.parse_args(argv_map[op_id])
        code = cli.execute_cli(engine, args, option_strings=cli.collect_option_strings(parser))
        out = capsys.readouterr().out
        parsed = json.loads(out)
        return code, parsed["message"], parsed

    if mode == "tui":
        tui = QtpTui(engine, term_size=(100, 22), use_color=False)
        arg_map: dict[str, tuple[str, str]] = {
            "version": ("", ""),
            "help": ("", ""),
            "selftest": ("", ""),
            "modes": ("", ""),
            "completion": ("bash", ""),
            "list_categories": ("", ""),
            "list_items": ("", ""),
            "search": ("Merhaba", ""),
            "show_ini": ("text_000", ""),
            "copy": ("text_000", ""),
            "paste": ("text_000", ""),
            "export_ini": (str(export_ini_target), ""),
            "import_ini": (str(import_ini_file), "merge"),
            "export_backup": (str(export_bak_target), ""),
            "backup": ("", ""),
            "restore": (str(FIXTURES_DIR / "data.json"), "replace"),
            "reload": ("", ""),
            "save_all": ("", ""),
            "get_setting": ("theme", ""),
            "set_setting": ("theme", "light"),
            "check_hotkeys": ("", ""),
            "hotkey_preset": ("recommended", ""),
            "hotkey_modifiers": ("Win+Alt", ""),
            "add_item": ("Parite yeni cevap", json.dumps({"keys": "A", "group": "Parite", "label": "Etiket"})),
            "update_item": ("text_000", json.dumps({"text": "Parite güncel cevap"})),
            "delete_item": ("text_000", ""),
            "duplicate_item": ("text_000", ""),
            "move_item": ("text_001", "up"),
            "toggle_favorite": ("text_000", ""),
            "bulk_edit": (bulk_targets, json.dumps({"prefix": "Önek "})),
            "bulk_delete": (bulk_targets, ""),
            "rename_group": (group0, "PariteGrup"),
            "delete_group": (group0, ""),
            "undo": ("", ""),
            "redo": ("", ""),
        }
        a1, a2 = arg_map[op_id]
        res = tui.execute_operation(op_id, a1, a2)
        screen = "\n".join(tui.render_plain_lines())
        if op_id in ("list_categories", "list_items", "search", "show_ini", "copy", "paste", "modes", "get_setting", "set_setting"):
            _assert_or_update_golden("tui", op_id, screen)
        return res.exit_code, res.message, res.to_api_dict()

    if mode == "web":
        srv = create_web_server(engine, host="127.0.0.1", port=0)
        port = srv.server_address[1]
        th = threading.Thread(target=srv.serve_forever, daemon=True)
        th.start()
        try:
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            route_map: dict[str, tuple[str, str, dict | None]] = {
                "version": ("GET", "/api/version", None),
                "help": ("GET", "/api/help?verbose=1", None),
                "selftest": ("GET", "/api/selftest", None),
                "modes": ("GET", "/api/modes", None),
                "completion": ("GET", "/api/completion?shell=bash", None),
                "list_categories": ("GET", "/api/categories", None),
                "list_items": ("GET", "/api/items", None),
                "search": ("GET", "/api/search?q=Merhaba", None),
                "show_ini": ("GET", "/api/show-ini?target=text_000", None),
                "copy": ("POST", "/api/copy", {"target": "text_000"}),
                "paste": ("POST", "/api/paste", {"target": "text_000"}),
                "export_ini": ("POST", "/api/export-ini", {"path": str(export_ini_target)}),
                "import_ini": ("POST", "/api/import-ini", {"path": str(import_ini_file), "mode": "merge"}),
                "export_backup": ("POST", "/api/export-backup", {"path": str(export_bak_target)}),
                "backup": ("POST", "/api/backup", {}),
                "restore": ("POST", "/api/restore", {"target": str(FIXTURES_DIR / "data.json"), "mode": "replace"}),
                "reload": ("POST", "/api/reload", {}),
                "save_all": ("POST", "/api/save", {}),
                "get_setting": ("GET", "/api/settings?key=theme", None),
                "set_setting": ("POST", "/api/settings", {"key": "theme", "value": "light"}),
                "check_hotkeys": ("GET", "/api/hotkeys/check", None),
                "hotkey_preset": ("POST", "/api/hotkeys/preset", {"preset": "recommended"}),
                "hotkey_modifiers": ("POST", "/api/hotkeys/modifiers", {"modifiers": "Win+Alt"}),
                "add_item": ("POST", "/api/items/add", {"text": "Parite yeni cevap", "keys": "A", "group": "Parite", "label": "Etiket"}),
                "update_item": ("POST", "/api/items/update", {"target": "text_000", "text": "Parite güncel cevap"}),
                "delete_item": ("POST", "/api/items/delete", {"target": "text_000"}),
                "duplicate_item": ("POST", "/api/items/duplicate", {"target": "text_000"}),
                "move_item": ("POST", "/api/items/move", {"target": "text_001", "direction": "up"}),
                "toggle_favorite": ("POST", "/api/items/favorite", {"target": "text_000"}),
                "bulk_edit": ("POST", "/api/items/bulk-edit", {"targets": bulk_targets.split(","), "prefix": "Önek "}),
                "bulk_delete": ("POST", "/api/items/bulk-delete", {"targets": bulk_targets.split(",")}),
                "rename_group": ("POST", "/api/groups/rename", {"old_group": group0, "new_group": "PariteGrup"}),
                "delete_group": ("POST", "/api/groups/delete", {"group": group0}),
                "undo": ("POST", "/api/undo", {}),
                "redo": ("POST", "/api/redo", {}),
            }
            method, url, body = route_map[op_id]
            headers = {"Content-Type": "application/json"} if body is not None else {}
            conn.request(method, url, body=json.dumps(body) if body is not None else None, headers=headers)
            resp = conn.getresponse()
            raw = resp.read().decode("utf-8")
            parsed = json.loads(raw)
            if op_id in ("list_categories", "list_items", "search", "show_ini", "modes", "get_setting"):
                snap_obj = json.loads(json.dumps(parsed, ensure_ascii=False))
                if isinstance(snap_obj.get("data"), dict) and "ini_path" in snap_obj["data"]:
                    snap_obj["data"]["ini_path"] = Path(str(snap_obj["data"]["ini_path"])).name
                _assert_or_update_golden("web", op_id, json.dumps(snap_obj, ensure_ascii=False, indent=2, sort_keys=True))
            return int(parsed["exit_code"]), parsed["message"], parsed
        finally:
            srv.shutdown()
            srv.server_close()

    from PyQt6.QtWidgets import QApplication
    from qtp_app.ui.overlay import OverlayWindow

    app = QApplication.instance() or QApplication([])
    overlay = OverlayWindow(
        engine.items,
        theme=engine.settings["theme"],
        on_paste=lambda it, prev: engine.op_paste(str(it.get("raw_key") or it.get("text")), previous_app=prev),
        on_copy=lambda it: engine.op_copy(str(it.get("raw_key") or it.get("text"))),
    )
    try:
        if op_id == "version":
            res = engine.op_version()
        elif op_id == "help":
            res = engine.op_help(verbose=True)
        elif op_id == "selftest":
            res = engine.op_selftest(run_ui_smoke=False)
        elif op_id == "modes":
            res = engine.op_modes()
        elif op_id == "completion":
            res = engine.op_completion("bash")
        elif op_id == "list_categories":
            res = engine.op_list_categories()
        elif op_id == "list_items":
            res = engine.op_list_items()
        elif op_id == "search":
            overlay.search_input.setText("Merhaba")
            app.processEvents()
            res = engine.op_search("Merhaba")
            assert overlay.list_model.rowCount() == res.data["count"]
        elif op_id == "show_ini":
            res = engine.op_show_ini("text_000")
        elif op_id == "copy":
            res = engine.op_copy("text_000")
        elif op_id == "paste":
            res = engine.op_paste("text_000")
        elif op_id == "export_ini":
            res = engine.op_export_ini(export_ini_target)
        elif op_id == "import_ini":
            res = engine.op_import_ini(import_ini_file, mode="merge")
        elif op_id == "export_backup":
            res = engine.op_export_backup(export_bak_target)
        elif op_id == "backup":
            res = engine.op_backup()
        elif op_id == "restore":
            res = engine.op_restore(FIXTURES_DIR / "data.json", mode="replace")
        elif op_id == "reload":
            res = engine.reload_data()
        elif op_id == "get_setting":
            res = engine.op_get_setting("theme")
        elif op_id == "set_setting":
            res = engine.op_set_setting("theme", "light")
        elif op_id == "check_hotkeys":
            res = engine.op_check_hotkeys()
        elif op_id == "hotkey_preset":
            res = engine.op_apply_hotkey_preset("recommended")
        elif op_id == "hotkey_modifiers":
            res = engine.op_apply_hotkey_modifiers("Win+Alt")
        elif op_id == "add_item":
            res = engine.op_add_item("Parite yeni cevap", keys="A", group="Parite", label="Etiket")
        elif op_id == "update_item":
            res = engine.op_update_item("text_000", text="Parite güncel cevap")
        elif op_id == "delete_item":
            res = engine.op_delete_item("text_000")
        elif op_id == "save_all":
            res = engine.op_save_all()
        elif op_id == "duplicate_item":
            res = engine.op_duplicate_item("text_000")
        elif op_id == "move_item":
            res = engine.op_move_item("text_001", direction="up")
        elif op_id == "toggle_favorite":
            res = engine.op_toggle_favorite("text_000")
        elif op_id == "bulk_edit":
            res = engine.op_bulk_edit(bulk_targets, prefix="Önek ")
        elif op_id == "bulk_delete":
            res = engine.op_bulk_delete(bulk_targets)
        elif op_id == "rename_group":
            res = engine.op_rename_group(group0, "PariteGrup")
        elif op_id == "delete_group":
            res = engine.op_delete_group(group0)
        elif op_id == "undo":
            res = engine.op_undo()
        elif op_id == "redo":
            res = engine.op_redo()
        else:
            raise AssertionError(f"Bilinmeyen GUI işlemi: {op_id}")
        return res.exit_code, res.message, res.to_api_dict()
    finally:
        overlay.close()
        overlay.deleteLater()
        app.processEvents()


def test_every_operation_reachable_in_all_four_modes():
    from qtp_app import main as main_mod, tui as tui_mod, web as web_mod

    cli_src = Path(cli.__file__).read_text(encoding="utf-8")
    tui_src = Path(tui_mod.app.__file__).read_text(encoding="utf-8")
    web_src = Path(web_mod.__file__).read_text(encoding="utf-8")
    main_src = Path(main_mod.__file__).read_text(encoding="utf-8")

    for op in OPERATIONS:
        assert op.cli_flag in cli_src, f"CLI içinde eksik: {op.cli_flag}"
        assert f'"{op.op_id}"' in tui_src, f"TUI içinde eksik: {op.op_id}"
        route_path = op.web_route.split(" ", 1)[1]
        assert route_path in web_src, f"Web API içinde eksik: {route_path}"
        assert op.gui_binding, f"GUI bağlaması boş: {op.op_id}"
    assert "QtpEngine" in main_src


@pytest.mark.parametrize("op_id", [op.op_id for op in OPERATIONS])
def test_cross_mode_parity_for_operation(op_id: str, tmp_path: Path, capsys):
    results: dict[str, tuple[int, str, dict]] = {}
    for mode in ("gui", "tui", "cli", "web"):
        eng = _make_isolated_engine(tmp_path / mode)
        results[mode] = _invoke_mode_op(mode, eng, op_id, tmp_path / mode, capsys)

    exit_codes = {m: r[0] for m, r in results.items()}
    assert len(set(exit_codes.values())) == 1, f"{op_id} çıkış kodları uyumsuz: {exit_codes}"
    assert exit_codes["cli"] == 0

    spec = OPERATIONS_BY_ID[op_id]
    for mode, (_code, msg, _payload) in results.items():
        if op_id == "help":
            assert "Usage:" in msg or "Kullanım" in msg, f"{mode}/{op_id} mesaj uyumsuz: {msg}"
        else:
            assert spec.success_msg_tr.split()[0] in msg, f"{mode}/{op_id} mesaj uyumsuz: {msg}"

    if spec.read_only and op_id != "selftest":
        hashes = {}
        for mode, (_code, _msg, payload) in results.items():
            data_copy = json.loads(json.dumps(payload["data"], ensure_ascii=False))
            if isinstance(data_copy, dict) and "ini_path" in data_copy:
                data_copy["ini_path"] = Path(str(data_copy["ini_path"])).name
            canonical = json.dumps(data_copy, ensure_ascii=False, sort_keys=True)
            hashes[mode] = canonical
        assert len(set(hashes.values())) == 1, f"{op_id} veri yükü modlar arası farklı: {hashes}"


@pytest.mark.parametrize("mode", ["gui", "tui", "cli", "web"])
def test_error_parity_across_modes(mode: str, tmp_path: Path, capsys):
    eng = _make_isolated_engine(tmp_path / f"err_{mode}")
    if mode == "cli":
        parser = cli.build_arg_parser()
        code_nf = cli.execute_cli(eng, parser.parse_args(["--copy", "olmayan_anahtar_999", "--json"]))
        out_nf = json.loads(capsys.readouterr().out)
        assert code_nf == 2 and "Öğe bulunamadı:" in out_nf["error"]

        code_badset = cli.execute_cli(eng, parser.parse_args(["--set", "bilinmeyen_ayar", "x", "--json"]))
        out_bs = json.loads(capsys.readouterr().out)
        assert code_badset == 2 and "Geçersiz ayar anahtarı:" in out_bs["error"]
        code_undo = cli.execute_cli(eng, parser.parse_args(["--undo", "--json"]))
        out_un = json.loads(capsys.readouterr().out)
        assert code_undo == 2 and "Geri alınacak işlem yok." in out_un["error"]
    elif mode == "tui":
        tui = QtpTui(eng)
        r1 = tui.execute_operation("copy", "olmayan_anahtar_999")
        assert r1.exit_code == 2 and "Öğe bulunamadı:" in r1.message
        r2 = tui.execute_operation("set_setting", "bilinmeyen_ayar", "x")
        assert r2.exit_code == 2 and "Geçersiz ayar anahtarı:" in r2.message
        r3 = tui.execute_operation("undo")
        assert r3.exit_code == 2 and "Geri alınacak işlem yok." in r3.message
    elif mode == "web":
        srv = create_web_server(eng, port=0)
        port = srv.server_address[1]
        th = threading.Thread(target=srv.serve_forever, daemon=True)
        th.start()
        try:
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            conn.request("POST", "/api/copy", body=json.dumps({"target": "olmayan_anahtar_999"}))
            r1 = json.loads(conn.getresponse().read().decode("utf-8"))
            assert r1["exit_code"] == 2 and "Öğe bulunamadı:" in r1["error"]
            conn.request("POST", "/api/settings", body=json.dumps({"key": "bilinmeyen_ayar", "value": "x"}))
            r2 = json.loads(conn.getresponse().read().decode("utf-8"))
            assert r2["exit_code"] == 2 and "Geçersiz ayar anahtarı:" in r2["error"]
            conn.request("POST", "/api/undo", body="{}")
            r3 = json.loads(conn.getresponse().read().decode("utf-8"))
            assert r3["exit_code"] == 2 and "Geri alınacak işlem yok." in r3["error"]
        finally:
            srv.shutdown()
            srv.server_close()
    else:
        r1 = eng.op_copy("olmayan_anahtar_999")
        assert r1.exit_code == 2 and "Öğe bulunamadı:" in (r1.error or "")
        r2 = eng.op_set_setting("bilinmeyen_ayar", "x")
        assert r2.exit_code == 2 and "Geçersiz ayar anahtarı:" in (r2.error or "")
        r3 = eng.op_undo()
        assert r3.exit_code == 2 and "Geri alınacak işlem yok." in (r3.error or "")


def test_tui_interactive_keys_ansi_and_win_console_shim(tmp_path: Path):
    import io
    import sys
    from types import SimpleNamespace
    from unittest import mock
    from qtp_app.tui.app import _parse_stream_keys, run_tui
    from qtp_app.tui._win_console import WinConsoleBackend

    eng = _make_isolated_engine(tmp_path)
    tui = QtpTui(eng, term_size=(90, 20), use_color=True)
    screen = tui.run_scripted([
        "DOWN", "UP", "PGDN", "PGUP", "TAB", "1", "2", "1",
        "/", "M", "e", "r", "BACKSPACE", "r", "ESC",
        "c", "e", "ESC",
        "F1", "q",
        "V", "ENTER",
        "s", "ESC",
        "b", "B", "r", "T", "M", "ESC",
        "q",
    ])
    assert any("QTP" in l for l in screen)
    assert tui.running is False
    ansi = tui.render_ansi_lines()
    assert any("\x1b[" in l for l in ansi)

    tui2 = QtpTui(eng)
    tui2.run_scripted(["/", "M", "ENTER", "q"])
    assert len(eng._test_copied) >= 1

    tui3 = QtpTui(eng, use_color=False)
    tui3.run_scripted([
        " ", "w", "f", "F", "F", "m", "m",
        "D", "J", "K",
        "a", "N", "o", "t", "ENTER",
        "E", "!", "ENTER",
        "U", "A", "ENTER",
        "g", "Z", "ENTER",
        "u", "y",
        "X", "ENTER",
        "G", "ESC",
        "d", "ESC",
        "q",
    ])
    from qtp_app.core.watcher import ReloadEvent
    tui3.apply_reload_event(ReloadEvent(items_changed=False, settings_changed=False, warning="Uyarı testi"))
    assert tui3.status_message == "Uyarı testi"
    tui3.apply_reload_event(ReloadEvent(items_changed=True, settings_changed=False))
    tui3.apply_reload_event(ReloadEvent(items_changed=False, settings_changed=True))
    assert "güncellendi" in tui3.status_message

    parsed = _parse_stream_keys("\x1b[A\x1b[B\x1b[5~\x1b[6~\x1bOP\x1b[11~\t\x08\r\n\x1bq")
    assert parsed == ["UP", "DOWN", "PGUP", "PGDN", "F1", "F1", "TAB", "BACKSPACE", "ENTER", "ESC", "q"]

    out_buf = io.StringIO()
    rc = run_tui(eng, scripted_keys=["DOWN", "c", "q"], out_stream=out_buf)
    assert rc == 0 and "Panoya kopyalandı" in out_buf.getvalue()

    fake_in = io.StringIO("c\nq")
    fake_in.isatty = lambda: False
    out_buf2 = io.StringIO()
    with mock.patch.object(sys, "stdin", fake_in):
        assert run_tui(eng, out_stream=out_buf2) == 0

    con_buf = io.StringIO()
    backend = WinConsoleBackend(out_stream=con_buf)
    fake_k32 = mock.Mock()
    fake_k32.GetConsoleMode.return_value = 1
    fake_msvcrt = SimpleNamespace(getwch=mock.Mock(side_effect=["\r", "\x1b", "\x08", "\t", "\x03", "\xe0", "H", "\xe0", "P", "\xe0", ";", "a"]))
    with mock.patch("qtp_app.tui._win_console.ctypes.windll", SimpleNamespace(kernel32=fake_k32), create=True), \
         mock.patch.dict("sys.modules", {"msvcrt": fake_msvcrt}):
        backend.enter()
        assert backend.size()[0] >= 40
        backend.render(["satır 1", "satır 2"])
        keys_read = [backend.read_key() for _ in range(9)]
        backend.leave()
    assert keys_read == ["ENTER", "ESC", "BACKSPACE", "TAB", "ESC", "UP", "DOWN", "F1", "a"]
    assert "\x1b[?1049h" in con_buf.getvalue()
    assert "\x1b[?1049l" in con_buf.getvalue()

    assert tui.execute_operation("export_ini", str(tmp_path / "tui_exp.ini")).exit_code == 0
    assert tui.execute_operation("import_ini", str(FIXTURES_DIR / "minimal.ini"), "merge").exit_code == 0
    assert tui.execute_operation("restore", str(FIXTURES_DIR / "data.json"), "replace").exit_code == 0
    assert tui.execute_operation("set_setting", "theme", "dark").exit_code == 0
    assert tui.execute_operation("nonexistent_op").exit_code == 2
    tui.run_scripted(["/", "z", "z", "z", "q", "q", "q", "UP", "DOWN", "ESC", "x", "q"])
    tui_crud = QtpTui(eng, term_size=(100, 22), use_color=False)
    before_crud = len(eng.items)
    tui_crud.run_scripted([
        "a", "I", "p", "t", "ESC",
        "a", "T", "U", "I", "X", "BACKSPACE", "1", "ENTER",
        "E", "2", "ENTER",
        "d", "n", "ESC",
        "d", "y",
        "k", "P", "C", "s",
        "q",
    ])
    assert len(eng.items) == before_crud
    assert tui_crud.execute_operation("add_item", "Kısa", "{bozuk json").exit_code == 0
    assert tui_crud.execute_operation("update_item", eng.items[-1]["raw_key"], "{bozuk").exit_code == 0
    assert tui_crud.execute_operation("delete_item", eng.items[-1]["raw_key"]).exit_code == 0

    fake_stdscr = mock.Mock()
    fake_stdscr.getmaxyx.return_value = (24, 90)
    fake_stdscr.get_wch.side_effect = ["\n", "\x1b"]
    fake_curses = SimpleNamespace(
        KEY_ENTER=10, KEY_UP=259, KEY_DOWN=258, KEY_PPAGE=339, KEY_NPAGE=338, KEY_F1=265, KEY_BACKSPACE=263,
        curs_set=mock.Mock(),
        wrapper=lambda fn: fn(fake_stdscr),
    )
    fake_tty_in = io.StringIO("")
    fake_tty_in.isatty = lambda: True
    with mock.patch("qtp_app.tui.app.sys.platform", "linux"), \
         mock.patch.object(sys, "stdin", fake_tty_in), \
         mock.patch.dict("sys.modules", {"curses": fake_curses}):
        assert run_tui(eng, out_stream=io.StringIO()) == 0


def test_win7_legacy_console_no_vt_and_posix_curses_fallback(tmp_path: Path, monkeypatch):
    import io
    import sys
    from types import SimpleNamespace
    from unittest import mock
    from qtp_app.tui.app import _decode_posix_key, run_tui
    from qtp_app.tui._win_console import WinConsoleBackend

    eng = _make_isolated_engine(tmp_path)

    win7_buf = io.StringIO()
    fake_k32 = mock.Mock()
    fake_k32.GetStdHandle.return_value = 99
    fake_k32.GetConsoleMode.return_value = 1
    fake_k32.SetConsoleMode.return_value = 0
    fake_k32.GetConsoleScreenBufferInfo.return_value = 1
    fake_msvcrt = SimpleNamespace(getwch=mock.Mock(side_effect=["c", "q"]))
    with mock.patch("qtp_app.tui._win_console.ctypes.windll", SimpleNamespace(kernel32=fake_k32), create=True), \
         mock.patch.dict("sys.modules", {"msvcrt": fake_msvcrt}), \
         mock.patch("qtp_app.tui.app.sys.platform", "win32"):
        fake_tty_win = io.StringIO("")
        fake_tty_win.isatty = lambda: True
        with mock.patch.object(sys, "stdin", fake_tty_win):
            assert run_tui(eng, out_stream=win7_buf) == 0

    rendered = win7_buf.getvalue()
    assert "\x1b[" not in rendered
    assert "QTP" in rendered
    assert fake_k32.FillConsoleOutputCharacterW.called
    assert fake_k32.FillConsoleOutputAttribute.called
    assert fake_k32.SetConsoleCursorPosition.called
    assert fake_k32.SetConsoleTextAttribute.called

    win7_direct = WinConsoleBackend(out_stream=io.StringIO())
    with mock.patch("qtp_app.tui._win_console.ctypes.windll", SimpleNamespace(kernel32=fake_k32), create=True):
        win7_direct.enter()
        assert win7_direct.supports_ansi is False
        win7_direct.render(["\x1b[36mBaşlık\x1b[0m", ">   1. [A] Seçili satır"])
        win7_direct.leave()
    assert "\x1b[" not in win7_direct.out.getvalue()

    seq = iter(["\x1b", "[", "A", "\x1b", "[", "B", "\x1b", "O", "P", "\x1b", "[", "5", "~", "\x1b", "[", "1", "1", "~", "\x1b", "\x1b", "Z", "\x03", "", "\r", "\t", "\x7f", "q"])
    assert _decode_posix_key(lambda n: "".join(next(seq) for _ in range(n)), lambda: True) == "UP"
    assert _decode_posix_key(lambda n: "".join(next(seq) for _ in range(n)), lambda: True) == "DOWN"
    assert _decode_posix_key(lambda n: "".join(next(seq) for _ in range(n)), lambda: True) == "F1"
    assert _decode_posix_key(lambda n: "".join(next(seq) for _ in range(n)), lambda: True) == "PGUP"
    assert _decode_posix_key(lambda n: "".join(next(seq) for _ in range(n)), lambda: True) == "F1"
    assert _decode_posix_key(lambda n: "".join(next(seq) for _ in range(n)), lambda: False) == "ESC"
    assert _decode_posix_key(lambda n: "".join(next(seq) for _ in range(n)), lambda: True) == "ESC"
    assert _decode_posix_key(lambda n: "".join(next(seq) for _ in range(n)), lambda: True) == "q"
    assert _decode_posix_key(lambda n: "".join(next(seq) for _ in range(n)), lambda: True) == "q"
    assert _decode_posix_key(lambda n: "".join(next(seq) for _ in range(n)), lambda: True) == "ENTER"
    assert _decode_posix_key(lambda n: "".join(next(seq) for _ in range(n)), lambda: True) == "TAB"
    assert _decode_posix_key(lambda n: "".join(next(seq) for _ in range(n)), lambda: True) == "BACKSPACE"
    assert _decode_posix_key(lambda n: "".join(next(seq) for _ in range(n)), lambda: True) == "q"

    no_windll_backend = WinConsoleBackend(out_stream=io.StringIO())
    with mock.patch("qtp_app.tui._win_console.ctypes.windll", None, create=True):
        no_windll_backend.enter()
        assert no_windll_backend.supports_ansi is False
        no_windll_backend.render(["Satır"])
        no_windll_backend.leave()

    err_k32 = mock.Mock()
    err_k32.GetStdHandle.return_value = 55
    err_k32.GetConsoleMode.return_value = 1
    err_k32.SetConsoleMode.return_value = 0
    err_k32.GetConsoleScreenBufferInfo.return_value = 0
    err_k32.SetConsoleCursorPosition.side_effect = RuntimeError("cursor fail")
    err_k32.SetConsoleTextAttribute.side_effect = RuntimeError("attr fail")
    err_backend = WinConsoleBackend(out_stream=io.StringIO())
    with mock.patch("qtp_app.tui._win_console.ctypes.windll", SimpleNamespace(kernel32=err_k32), create=True):
        err_backend.enter()
        err_backend.render([">   1. [A] Hata dalı"])
        err_backend.leave()

    monkeypatch.setenv("TERM", "xterm-256color")
    termios_in = io.StringIO("cq")
    termios_in.isatty = lambda: True
    termios_in.fileno = lambda: 7
    fake_termios = SimpleNamespace(TCSADRAIN=1, tcgetattr=mock.Mock(return_value=[1]), tcsetattr=mock.Mock())
    fake_tty = SimpleNamespace(setcbreak=mock.Mock())
    fake_select = SimpleNamespace(select=mock.Mock(return_value=([], [], [])))
    termios_out = io.StringIO()
    with mock.patch("qtp_app.tui.app.sys.platform", "linux"), \
         mock.patch.object(sys, "stdin", termios_in), \
         mock.patch.dict("sys.modules", {"curses": None, "termios": fake_termios, "tty": fake_tty, "select": fake_select}):
        assert run_tui(eng, out_stream=termios_out) == 0
    assert "\x1b[" in termios_out.getvalue()
    assert fake_tty.setcbreak.called
    assert fake_termios.tcsetattr.called

    monkeypatch.setenv("TERM", "dumb")
    plain_in = io.StringIO("c\nq\n")
    plain_in.isatty = lambda: True
    plain_out = io.StringIO()
    with mock.patch("qtp_app.tui.app.sys.platform", "freebsd14"), \
         mock.patch.object(sys, "stdin", plain_in), \
         mock.patch.dict("sys.modules", {"curses": None}):
        assert run_tui(eng, out_stream=plain_out) == 0
    assert "Panoya kopyalandı" in plain_out.getvalue()

    class _FakeCursesError(Exception):
        pass

    err_curses = SimpleNamespace(
        error=_FakeCursesError,
        KEY_ENTER=10,
        KEY_UP=259,
        KEY_DOWN=258,
        KEY_PPAGE=339,
        KEY_NPAGE=338,
        KEY_F1=265,
        KEY_BACKSPACE=263,
        wrapper=mock.Mock(side_effect=_FakeCursesError("no terminfo")),
    )
    plain_in2 = io.StringIO("q\n")
    plain_in2.isatty = lambda: True
    with mock.patch("qtp_app.tui.app.sys.platform", "openbsd7"), \
         mock.patch.object(sys, "stdin", plain_in2), \
         mock.patch.dict("sys.modules", {"curses": err_curses}):
        assert run_tui(eng, out_stream=io.StringIO()) == 0


@pytest.mark.parametrize("mode", ["cli", "web", "tui", "gui"])
def test_cross_mode_help_flag_and_order_parity(mode: str, tmp_path: Path, capsys, monkeypatch):
    work_dir = tmp_path / f"help_{mode}"
    work_dir.mkdir()
    monkeypatch.setattr("qtp_app.core.engine.get_app_dir", lambda: work_dir)
    mode_flag = f"--{mode}"

    assert cli.run([mode_flag, "--help"]) == 0
    std_out = capsys.readouterr().out
    assert std_out == cli.format_help_text(verbose=False) + "\n"
    assert list(work_dir.iterdir()) == []

    for argv in (
        [mode_flag, "--verbose", "--help"],
        ["--verbose", mode_flag, "--help"],
        [mode_flag, "-v", "-h"],
    ):
        assert cli.run(argv) == 0
        v_out = capsys.readouterr().out
        assert v_out == cli.format_help_text(verbose=True) + "\n"
        assert "Detailed Reference (--verbose):" in v_out or "Ayrıntılı Başvuru (--verbose):" in v_out
        assert list(work_dir.iterdir()) == []


def test_only_notes_filter_parity_across_engine_gui_and_static_js(tmp_path: Path):
    import re
    import subprocess
    from PyQt6.QtWidgets import QApplication
    from qtp_app.core.json_store import save_state
    from qtp_app.ui.overlay import OverlayWindow

    work = tmp_path / "notes_parity"
    work.mkdir()
    sample_items = [
        {"keys": "L-Win+2", "group": "Work", "label": "NoteEn", "text": "[NOTE] Universal internal rule"},
        {"keys": "L-Win+2", "group": "Work", "label": "NoteTr", "text": "[DAHİLİ NOT] Legacy internal rule"},
        {"keys": "", "group": "General", "label": "Plain", "text": "Keyless plain note"},
        {"keys": "L-Win+1", "group": "General", "label": "Normal", "text": "Normal snippet"},
    ]
    save_state(work, sample_items, create_backup_flag=False)
    eng = QtpEngine(work_dir=work, seed_defaults=False)

    eng_texts = [it["text"] for it in eng.op_list_items(only_notes=True).data["items"]]
    assert eng_texts == [
        "[NOTE] Universal internal rule",
        "[DAHİLİ NOT] Legacy internal rule",
        "Keyless plain note",
    ]

    app = QApplication.instance() or QApplication([])
    overlay = OverlayWindow(eng.items, theme="light")
    try:
        overlay.scope_notes_btn.click()
        app.processEvents()
        gui_texts = [overlay.list_model.item_at(i)["text"] for i in range(overlay.list_model.rowCount())]
        assert gui_texts == eng_texts
    finally:
        overlay.close()
        overlay.deleteLater()

    node = shutil.which("node")
    if node:
        html_path = Path(__file__).resolve().parent.parent / "web" / "qtp.html"
        html = html_path.read_text(encoding="utf-8")
        scripts = re.findall(r"<script>([\s\S]*?)</script>", html)
        start_pure = scripts[0].index("function trLower(text) {")
        end_pure = scripts[0].index("function downloadBytes(")
        pure_js = scripts[0].split("const state = {", 1)[0] + "\n" + scripts[0][start_pure:end_pure]
        vm_code = (
            "const assert = require('assert');\n"
            + pure_js
            + f"\nconst sample = {json.dumps(sample_items, ensure_ascii=False)};\n"
            + "const res = filterAndSortItemsStatic(sample, { onlyNotes: true });\n"
            + f"assert.deepStrictEqual(res.map(it => it.text), {json.dumps(eng_texts, ensure_ascii=False)});\n"
            + "console.log('NOTE_PARITY_OK');\n"
        )
        vm_file = work / "note_parity_check.js"
        vm_file.write_text(vm_code, encoding="utf-8")
        proc = subprocess.run([node, str(vm_file)], capture_output=True, text=True, check=False)
        assert proc.returncode == 0, f"JS note parity hatası: {proc.stderr}"
        assert "NOTE_PARITY_OK" in proc.stdout


def test_sort_keys_and_alpha_parity_across_engine_gui_and_static_js(tmp_path: Path):
    import re
    import subprocess
    from PyQt6.QtWidgets import QApplication
    from qtp_app.core.json_store import save_state
    from qtp_app.ui.overlay import OverlayWindow

    work = tmp_path / "sort_parity"
    work.mkdir()
    sample_items = [
        {"keys": "", "group": "General", "label": "Not Kayıt", "text": "Kısayolsuz not"},
        {"keys": "L-Win+2", "group": "Work", "label": "Şifre", "text": "Şifre metni"},
        {"keys": "L-Win+1", "group": "General", "label": "Cem", "text": "Cem metni"},
        {"keys": "L-Win+1", "group": "General", "label": "Çözüm", "text": "Çözüm metni"},
        {"keys": "L-Win+3", "group": "Dev", "label": "18 Yaş", "text": "18 Yaş metni"},
        {"keys": "L-Win+2", "group": "Work", "label": "[NOTE] Kural", "text": "Dahili"},
    ]
    save_state(work, sample_items, create_backup_flag=False)
    eng = QtpEngine(work_dir=work, seed_defaults=False)

    app = QApplication.instance() or QApplication([])
    overlay = OverlayWindow(eng.items, theme="light")
    try:
        for sort_mode in ("keys", "alpha"):
            eng_texts = [it["text"] for it in eng.op_list_items(sort_by=sort_mode).data["items"]]
            overlay.apply_settings(sort_by=sort_mode)
            gui_texts = [overlay.list_model.item_at(i)["text"] for i in range(overlay.list_model.rowCount())]
            assert gui_texts == eng_texts, f"sort_by={sort_mode} GUI != Engine"
            if sort_mode == "keys":
                assert eng_texts[-1] == "Kısayolsuz not"
            if sort_mode == "alpha":
                assert eng_texts.index("Cem metni") < eng_texts.index("Çözüm metni")
                assert eng_texts.index("Dahili") < eng_texts.index("18 Yaş metni")

            node = shutil.which("node")
            if node:
                html_path = Path(__file__).resolve().parent.parent / "web" / "qtp.html"
                html = html_path.read_text(encoding="utf-8")
                scripts = re.findall(r"<script>([\s\S]*?)</script>", html)
                start_pure = scripts[0].index("function trLower(text) {")
                end_pure = scripts[0].index("function downloadBytes(")
                pure_js = scripts[0].split("const state = {", 1)[0] + "\n" + scripts[0][start_pure:end_pure]
                vm_code = (
                    "const assert = require('assert');\n"
                    + pure_js
                    + f"\nconst sample = {json.dumps(sample_items, ensure_ascii=False)};\n"
                    + f"const res = filterAndSortItemsStatic(sample, {{ sortBy: {json.dumps(sort_mode)} }});\n"
                    + f"assert.deepStrictEqual(res.map(it => it.text), {json.dumps(eng_texts, ensure_ascii=False)});\n"
                    + "console.log('SORT_PARITY_OK');\n"
                )
                vm_file = work / f"sort_{sort_mode}_parity.js"
                vm_file.write_text(vm_code, encoding="utf-8")
                proc = subprocess.run([node, str(vm_file)], capture_output=True, text=True, check=False)
                assert proc.returncode == 0, f"JS sort={sort_mode} parity hatası: {proc.stderr}"
                assert "SORT_PARITY_OK" in proc.stdout
    finally:
        overlay.close()
        overlay.deleteLater()


@pytest.mark.parametrize("mode", ["cli", "web", "tui", "gui"])
def test_cross_mode_verbose_quiet_and_initial_filters_parity(mode: str, tmp_path: Path, capsys, monkeypatch):
    import io
    import sys
    from unittest import mock
    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QApplication
    from qtp_app import main as main_mod
    from qtp_app.core.ini_parser import parse_qtp_ini, read_text_auto
    from qtp_app.ui.help_dialog import HelpDialog
    from qtp_app.ui.theme import DARK_PALETTE

    work = tmp_path / f"parity_{mode}"
    work.mkdir()
    shutil.copy2(FIXTURES_DIR / "QuickTextPaste.ini", work / "QuickTextPaste.ini")
    eng_ref = QtpEngine(work_dir=work)
    expected_items = eng_ref.op_list_items(category="A", query="sipariş").data["items"]
    expected_keys = [it["raw_key"] for it in expected_items]
    assert len(expected_keys) > 0

    if mode == "cli":
        assert cli.run(["--work-dir", str(work), "--cli", "-vv", "--category", "A", "--query", "sipariş", "--json"]) == 0
        cap = capsys.readouterr()
        assert "[INFO]" in cap.err and "[DEBUG]" in cap.err
        parsed = json.loads(cap.out)
        assert [it["raw_key"] for it in parsed["data"]["items"]] == expected_keys

        assert cli.run(["--work-dir", str(work), "--cli", "-q", "--selftest"]) == 0
        q_cap = capsys.readouterr()
        assert q_cap.out == "" and q_cap.err == ""

        assert cli.run(["--work-dir", str(work), "--cli", "-q", "-vv", "--selftest"]) == 0
        vq_cap = capsys.readouterr()
        assert "[INFO]" in vq_cap.err and "[DEBUG]" in vq_cap.err and "Otomatik test başarılı" in vq_cap.out
        return

    if mode == "web":
        assert cli.run(["--work-dir", str(work), "--web", "-vv", "--port", "0", "--shutdown-after", "0.25", "--category", "A", "--query", "sipariş"]) == 0
        cap = capsys.readouterr()
        assert "QTP Web Modu çalışıyor:" in cap.out
        assert "[INFO]" in cap.err and "[DEBUG]" in cap.err
        assert "Web sunucusu başlatıldı:" in cap.err and "Web sunucusu kapatıldı." in cap.err

        assert cli.run(["--work-dir", str(work), "--web", "-q", "--port", "0", "--shutdown-after", "0.1"]) == 0
        q_cap = capsys.readouterr()
        assert q_cap.out == "" and "[INFO]" not in q_cap.err

        eng_web = QtpEngine(work_dir=work, verbose=2)
        srv = create_web_server(eng_web, port=0, initial_category="A", initial_query="sipariş")
        port = srv.server_address[1]
        th = threading.Thread(target=srv.serve_forever, daemon=True)
        th.start()
        try:
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            conn.request("GET", "/api/revision")
            rev = json.loads(conn.getresponse().read().decode("utf-8"))
            assert rev["data"]["initial_category"] == "A"
            assert rev["data"]["initial_query"] == "sipariş"
            conn.request("GET", "/api/items?category=A&query=sipari%C5%9F")
            web_items = json.loads(conn.getresponse().read().decode("utf-8"))["data"]["items"]
            assert [it["raw_key"] for it in web_items] == expected_keys
            conn.request("GET", "/api/help?verbose=1")
            h_data = json.loads(conn.getresponse().read().decode("utf-8"))["data"]
            assert h_data["usage_verbose"] == cli.format_help_text(verbose=True)
        finally:
            srv.shutdown()
            srv.server_close()
        http_err = capsys.readouterr().err
        assert "GET /api/revision -> 200" in http_err
        return

    if mode == "tui":
        fake_in = io.StringIO("q")
        fake_in.isatty = lambda: False
        with mock.patch.object(sys, "stdin", fake_in):
            assert cli.run(["--work-dir", str(work), "--tui", "-vv", "--category", "A", "--query", "sipariş"]) == 0
        cap = capsys.readouterr()
        assert "[INFO]" in cap.err and "[DEBUG]" in cap.err
        assert "[INFO]" not in cap.out and "[DEBUG]" not in cap.out

        tui = QtpTui(eng_ref, term_size=(100, 20), initial_category="A", initial_query="sipariş", quiet=True)
        assert [it.get("raw_key") for it in tui._visible_items] == expected_keys
        assert "QTP hazır" not in tui.status_message
        tui.execute_operation("help")
        assert len(tui.modal_lines) > 200
        joined = "\n".join(tui.modal_lines)
        for part in ("QTP Kullanım Kılavuzu", "QTP Klavye Kısayolları Rehberi", "SSS"):
            assert part in joined
        assert "Detailed Reference (--verbose):" in joined or "Ayrıntılı Başvuru (--verbose):" in joined
        before_scroll = tui.modal_scroll
        tui.handle_key("PGDN")
        assert tui.modal_scroll > before_scroll
        tui.handle_key("DOWN")
        assert tui.modal_scroll > before_scroll + 1
        tui.handle_key("UP")
        tui.handle_key("PGUP")
        tui.handle_key("ESC")
        assert tui.modal_lines == []

        tui_frames = QtpTui(eng_ref, term_size=(100, 28), initial_category="A", initial_query="sipariş")
        tui_frames.run_scripted(["F1", "PGDN", "PGDN", "PGDN", "PGDN", "PGDN", "PGDN", "ESC", "q"])
        all_frames = "\n".join(tui_frames.recorded_frames)
        assert "Detailed Reference (--verbose):" in all_frames or "Ayrıntılı Başvuru (--verbose):" in all_frames
        assert "Katmanı (Overlay) Açma" in all_frames
        return

    app = QApplication.instance() or QApplication([])
    captured_overlays = []
    orig_exec = app.exec
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    def fake_exec():
        QTimer.singleShot(80, app.quit)
        return orig_exec()

    with mock.patch.object(main_mod, "SingleInstanceGuard") as guard_cls, \
         mock.patch("qtp_app.main.HotkeyManager.register", return_value={"all": True}), \
         mock.patch("qtp_app.ui.overlay.OverlayWindow.show_overlay", autospec=True) as mock_show, \
         mock.patch.object(app, "exec", side_effect=fake_exec):
        guard_inst = guard_cls.return_value
        guard_inst.try_notify_existing.return_value = False

        def record_show(self_ov, *a, **kw):
            captured_overlays.append((self_ov.active_category, self_ov.search_input.text(), self_ov.list_model.rowCount(), [self_ov.list_model.item_at(i)["raw_key"] for i in range(self_ov.list_model.rowCount())]))

        mock_show.side_effect = record_show
        assert cli.run(["--work-dir", str(work), "--gui", "-vv", "--category", "A", "--query", "sipariş"]) == 0
    g_cap = capsys.readouterr()
    assert "[INFO]" in g_cap.err and "[DEBUG]" in g_cap.err
    assert captured_overlays[-1][0] == "A"
    assert captured_overlays[-1][1] == "sipariş"
    assert captured_overlays[-1][3] == expected_keys

    help_dlg = HelpDialog(DARK_PALETTE)
    assert help_dlg.tabs.count() == 5
    assert cli.format_help_text(verbose=True).splitlines()[0] in help_dlg.browsers[4].toPlainText()
    help_dlg.close()
    help_dlg.deleteLater()


def test_dynamic_category_auto_discovery_and_backward_compat(tmp_path: Path):
    from qtp_app.core.json_store import save_data_json, save_state

    empty_dir = tmp_path / "empty_cats"
    empty_dir.mkdir()
    save_data_json(empty_dir / "data.json", [])
    eng_empty = QtpEngine(work_dir=empty_dir, seed_defaults=False)
    assert [c["code"] for c in eng_empty.resolve_categories()] == ["ALL"]

    legacy_dir = tmp_path / "legacy_527"
    legacy_dir.mkdir()
    shutil.copy2(FIXTURES_DIR / "QuickTextPaste.ini", legacy_dir / "QuickTextPaste.ini")
    eng_legacy = QtpEngine(work_dir=legacy_dir, seed_defaults=False)
    cats = eng_legacy.resolve_categories()
    codes = [c["code"] for c in cats]
    assert codes[0] == "ALL"
    for expected_code in ("A", "Z", "X", "Q", "W", "1"):
        assert expected_code in codes
    assert cats[0]["count"] == len(eng_legacy.items) and cats[0]["count"] >= 500

    custom_dir = tmp_path / "custom_ini"
    custom_dir.mkdir()
    save_state(
        custom_dir,
        [
            {"keys": "L-Ctrl+1", "group": "Mail", "label": "M1", "text": "Mail reply"},
            {"keys": "Alt+M", "group": "Dev", "label": "D1", "text": "Dev macro"},
            {"keys": "", "group": "Notes", "label": "N1", "text": "[NOTE] Keyless note"},
        ],
        create_backup_flag=False,
    )
    eng_custom = QtpEngine(work_dir=custom_dir, seed_defaults=False)
    assert [c["code"] for c in eng_custom.resolve_categories()] == ["ALL", "1", "M"]
    eng_custom.op_set_setting("categories", json.dumps([{"code": "TEAM", "label": "Team", "hotkey_prefix": "L-Win+T"}]))
    assert [c["code"] for c in eng_custom.resolve_categories()] == ["ALL", "TEAM", "1", "M"]



