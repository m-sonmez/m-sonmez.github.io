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
    work = tmp_path / "work"
    work.mkdir(parents=True, exist_ok=True)
    shutil.copy2(FIXTURES_DIR / "minimal.ini", work / "QuickTextPaste.ini")
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
    eng._test_copied = copied_texts  # type: ignore[attr-defined]
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

    if mode == "cli":
        argv_map: dict[str, list[str]] = {
            "version": ["--version", "--json"],
            "help": ["--help", "--json"],
            "selftest": ["--selftest", "--json"],
            "modes": ["--modes", "--json"],
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
            "get_setting": ["--get", "theme", "--json"],
            "set_setting": ["--set", "theme", "light", "--json"],
        }
        parser = cli.build_arg_parser()
        args = parser.parse_args(argv_map[op_id])
        code = cli.execute_cli(engine, args)
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
            "get_setting": ("theme", ""),
            "set_setting": ("theme", "light"),
        }
        a1, a2 = arg_map[op_id]
        res = tui.execute_operation(op_id, a1, a2)
        screen = "\n".join(tui.render_plain_lines())
        # Dinamik geçici yol/zaman içermeyen kararlı görüntü kontrolü
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
                "help": ("GET", "/api/help", None),
                "selftest": ("GET", "/api/selftest", None),
                "modes": ("GET", "/api/modes", None),
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
                "get_setting": ("GET", "/api/settings?key=theme", None),
                "set_setting": ("POST", "/api/settings", {"key": "theme", "value": "light"}),
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

    # mode == "gui" (QtpEngine + OverlayWindow adaptör katmanı)
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
            res = engine.op_help(cli.format_help_text())
        elif op_id == "selftest":
            res = engine.op_selftest(run_ui_smoke=False)
        elif op_id == "modes":
            res = engine.op_modes()
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
        assert spec.success_msg_tr.split()[0] in msg, f"{mode}/{op_id} mesaj uyumsuz: {msg}"

    # Salt-okunur işlemlerde tüm 4 modun JSON veri özeti (hash) birebir aynı olmalı
    if spec.read_only and op_id not in ("help", "selftest"):
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
    elif mode == "tui":
        tui = QtpTui(eng)
        r1 = tui.execute_operation("copy", "olmayan_anahtar_999")
        assert r1.exit_code == 2 and "Öğe bulunamadı:" in r1.message
        r2 = tui.execute_operation("set_setting", "bilinmeyen_ayar", "x")
        assert r2.exit_code == 2 and "Geçersiz ayar anahtarı:" in r2.message
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
        finally:
            srv.shutdown()
            srv.server_close()
    else:
        r1 = eng.op_copy("olmayan_anahtar_999")
        assert r1.exit_code == 2 and "Öğe bulunamadı:" in (r1.error or "")
        r2 = eng.op_set_setting("bilinmeyen_ayar", "x")
        assert r2.exit_code == 2 and "Geçersiz ayar anahtarı:" in (r2.error or "")


def test_tui_interactive_keys_ansi_and_win_console_shim(tmp_path: Path):
    import io
    import sys
    from types import SimpleNamespace
    from unittest import mock
    from qtp_app.tui.app import _parse_stream_keys, run_tui
    from qtp_app.tui._win_console import WinConsoleBackend

    eng = _make_isolated_engine(tmp_path)
    tui = QtpTui(eng, term_size=(90, 20), use_color=True)
    # Tuş gezinme, arama modu, kategori geçişi, modal açıp kapama ve çıkış
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

    # Arama modunda ENTER doğrudan yapıştırmayı tetikler
    tui2 = QtpTui(eng)
    tui2.run_scripted(["/", "M", "ENTER", "q"])
    assert len(eng._test_copied) >= 1  # type: ignore[attr-defined]

    # _parse_stream_keys tüm kaçış dizilerini tanımalı
    parsed = _parse_stream_keys("\x1b[A\x1b[B\x1b[5~\x1b[6~\x1bOP\t\x08\r\x1bq")
    assert parsed == ["UP", "DOWN", "PGUP", "PGDN", "F1", "TAB", "BACKSPACE", "ENTER", "ESC", "q"]

    # run_tui scripted & non-tty stdin
    out_buf = io.StringIO()
    rc = run_tui(eng, scripted_keys=["DOWN", "c", "q"], out_stream=out_buf)
    assert rc == 0 and "Panoya kopyalandı" in out_buf.getvalue()

    fake_in = io.StringIO("c\nq")
    fake_in.isatty = lambda: False  # type: ignore[method-assign]
    out_buf2 = io.StringIO()
    with mock.patch.object(sys, "stdin", fake_in):
        assert run_tui(eng, out_stream=out_buf2) == 0

    # WinConsoleBackend ANSI / msvcrt shim kapsamı
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

    # TUI ek işlemler ve boş arama + curses mock kapsamı
    assert tui.execute_operation("export_ini", str(tmp_path / "tui_exp.ini")).exit_code == 0
    assert tui.execute_operation("import_ini", str(FIXTURES_DIR / "minimal.ini"), "merge").exit_code == 0
    assert tui.execute_operation("restore", str(FIXTURES_DIR / "data.json"), "replace").exit_code == 0
    assert tui.execute_operation("set_setting", "theme", "dark").exit_code == 0
    assert tui.execute_operation("nonexistent_op").exit_code == 2
    tui.run_scripted(["/", "z", "z", "z", "q", "q", "q", "UP", "DOWN", "ESC", "q"])

    # Linux/macOS curses döngüsü mock ile çalıştırılır
    fake_stdscr = mock.Mock()
    fake_stdscr.getmaxyx.return_value = (24, 90)
    fake_stdscr.get_wch.side_effect = ["\n", "\x1b"]
    fake_curses = SimpleNamespace(
        KEY_ENTER=10, KEY_UP=259, KEY_DOWN=258, KEY_PPAGE=339, KEY_NPAGE=338, KEY_F1=265, KEY_BACKSPACE=263,
        curs_set=mock.Mock(),
        wrapper=lambda fn: fn(fake_stdscr),
    )
    fake_tty_in = io.StringIO("")
    fake_tty_in.isatty = lambda: True  # type: ignore[method-assign]
    with mock.patch("qtp_app.tui.app.sys.platform", "linux"), \
         mock.patch.object(sys, "stdin", fake_tty_in), \
         mock.patch.dict("sys.modules", {"curses": fake_curses}):
        assert run_tui(eng, out_stream=io.StringIO()) == 0


