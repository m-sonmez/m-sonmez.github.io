"""Yerel Web sunucusu (--web), çevrimdışı HTML/CSS, kısayol API ve canlı revizyon yenileme testi."""

from __future__ import annotations

import http.client
import json
import shutil
import threading
import time
from pathlib import Path
from unittest import mock

import pytest

from qtp_app.core.engine import QtpEngine
from qtp_app.core.ini_parser import build_qtp_ini, write_qtp_ini
from qtp_app.ui.theme import ACCENT_CYAN, ACCENT_PURPLE, DARK_PALETTE, FOOTER_HINTS_TEXT
from qtp_app.web import create_web_server, run_web_server


def test_web_ui_has_no_external_urls_and_matches_theme(tmp_path: Path):
    eng = QtpEngine(work_dir=tmp_path)
    srv = create_web_server(eng, host="127.0.0.1", port=0)
    port = srv.server_address[1]
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/")
        r_html = conn.getresponse()
        assert r_html.status == 200
        html = r_html.read().decode("utf-8")

        conn.request("GET", "/theme.css")
        r_css = conn.getresponse()
        assert r_css.status == 200
        css = r_css.read().decode("utf-8")

        for blob in (html, css):
            assert "http://" not in blob
            assert "https://" not in blob
            assert "//cdn" not in blob
            assert "fonts.googleapis" not in blob

        assert ACCENT_PURPLE in css
        assert ACCENT_CYAN in css
        assert DARK_PALETTE.surface in css
        assert DARK_PALETTE.window_bg in css
        assert DARK_PALETTE.text_primary in css

        assert FOOTER_HINTS_TEXT in html
        assert "ArrowDown" in html and "ArrowUp" in html and "F1" in html and "Escape" in html

        conn.request("GET", "/api")
        api_idx = json.loads(conn.getresponse().read().decode("utf-8"))
        assert api_idx["ok"] is True
        assert len(api_idx["data"]["routes"]) >= 18

        conn.request("GET", "/api/completion?shell=powershell")
        comp = json.loads(conn.getresponse().read().decode("utf-8"))
        assert comp["ok"] is True and "Register-ArgumentCompleter" in comp["data"]["script"]

        conn.request("GET", "/api/hotkeys/check")
        chk = json.loads(conn.getresponse().read().decode("utf-8"))
        assert chk["ok"] is True and chk["data"]["clean"] is True

        conn.request(
            "POST",
            "/api/hotkeys/preset",
            body=json.dumps({"preset": "function_keys"}),
            headers={"Content-Type": "application/json"},
        )
        pr = json.loads(conn.getresponse().read().decode("utf-8"))
        assert pr["ok"] is True and pr["data"]["hotkeys"]["all"] == "Ctrl+Shift+F1"

        conn.request(
            "POST",
            "/api/hotkeys/modifiers",
            body=json.dumps({"modifiers": "Win+Ctrl"}),
            headers={"Content-Type": "application/json"},
        )
        mr = json.loads(conn.getresponse().read().decode("utf-8"))
        assert mr["ok"] is True and mr["data"]["hotkeys"]["all"] == "Win+Ctrl+F1"

        conn.request("GET", "/api/help?verbose=1")
        h_resp = json.loads(conn.getresponse().read().decode("utf-8"))
        assert h_resp["ok"] is True
        for key in ("usage", "usage_verbose", "kullanim", "kisayollar", "sss"):
            assert h_resp["data"][key], f"/api/help eksik alan: {key}"
        assert "Ayrıntılı Başvuru (--verbose):" in h_resp["message"]
        assert "btnHelp" in html and "showHelpModal" in html and "/api/help?verbose=1" in html
        assert "helpTabs" in html and "CLI &amp; Parametreler" in html

        conn.request("GET", "/api/revision")
        rev = json.loads(conn.getresponse().read().decode("utf-8"))
        assert rev["ok"] is True and rev["data"]["revision"] >= 2
        assert rev["data"]["initial_category"] == "ALL"
        assert rev["data"]["initial_query"] == ""

        conn.request("GET", "/api/olmayan_rota")
        assert conn.getresponse().status == 404
    finally:
        srv.shutdown()
        srv.server_close()


def test_web_live_hot_reload_from_external_file_changes(tmp_path: Path):
    eng = QtpEngine(work_dir=tmp_path)
    eng.settings["auto_reload_interval_ms"] = 100
    srv = create_web_server(eng, host="127.0.0.1", port=0)
    port = srv.server_address[1]
    eng.start_watcher(debounce_ms=80)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/api/items")
        before = json.loads(conn.getresponse().read().decode("utf-8"))["data"]["count"]
        assert before >= 500

        new_items = [
            {"keys": "L-Win+A", "group": "Test", "label": f"L{i}", "text": f"Öğe {i}"}
            for i in range(before + 1)
        ]
        write_qtp_ini(tmp_path / "QuickTextPaste.ini", build_qtp_ini(new_items), create_bak=False)

        deadline = time.monotonic() + 3.0
        after = before
        while time.monotonic() < deadline:
            conn.request("GET", "/api/items")
            after = json.loads(conn.getresponse().read().decode("utf-8"))["data"]["count"]
            if after == before + 1:
                break
            time.sleep(0.05)
        assert after == before + 1
    finally:
        eng.stop_watcher()
        srv.shutdown()
        srv.server_close()


def test_web_server_refuses_non_loopback_host(tmp_path: Path):
    eng = QtpEngine(work_dir=tmp_path)
    with pytest.raises(ValueError) as exc:
        create_web_server(eng, host="0.0.0.0", port=0)
    assert "127.0.0.1" in str(exc.value)


def test_web_server_backups_shutdown_and_error_status(tmp_path: Path):
    eng = QtpEngine(work_dir=tmp_path)
    srv = create_web_server(eng, host="127.0.0.1", port=0)
    port = srv.server_address[1]
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/api/backups")
        r_bak = conn.getresponse()
        assert r_bak.status == 200 and json.loads(r_bak.read())["ok"] is True

        conn.request("POST", "/api/olmayan", body="{bad")
        assert conn.getresponse().status == 404

        conn.request("POST", "/api/import-ini", body=json.dumps({"path": str(tmp_path / "yok.ini")}))
        assert conn.getresponse().status == 400

        conn.request("POST", "/api/shutdown", body="{}")
        assert conn.getresponse().status == 200
        th.join(timeout=3)
    finally:
        srv.server_close()

    assert run_web_server(eng, port=0, open_browser=False, shutdown_after=0.1, quiet=True) == 0
    with mock.patch("qtp_app.web.create_web_server", side_effect=OSError("Address already in use")):
        assert run_web_server(eng, port=8765) == 1

    import sys
    from qtp_app.web import _read_web_asset

    mei = tmp_path / "mei_web"
    (mei / "qtp_app" / "web").mkdir(parents=True)
    (mei / "qtp_app" / "web" / "index.html").write_text("<h1>frozen</h1>", encoding="utf-8")
    (mei / "qtp_app" / "web" / "theme.css").write_text(":root{}", encoding="utf-8")
    with mock.patch.object(sys, "frozen", True, create=True), \
         mock.patch.object(sys, "_MEIPASS", str(mei), create=True), \
         mock.patch("qtp_app.web.importlib.resources.files", side_effect=RuntimeError("frozen")):
        assert _read_web_asset("index.html") == b"<h1>frozen</h1>"
        assert _read_web_asset("theme.css") == b":root{}"
