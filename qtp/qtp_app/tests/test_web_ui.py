"""Yerel Web sunucusu (--web), çevrimdışı HTML/CSS denetimi ve tema sabitleri eşitliği testi."""

from __future__ import annotations

import http.client
import json
import re
import threading
from pathlib import Path

import pytest

from qtp_app.core.engine import QtpEngine
from qtp_app.ui.theme import ACCENT_CYAN, ACCENT_PURPLE, DARK_PALETTE, FOOTER_HINTS_TEXT
from qtp_app.web import create_web_server


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

        conn.request("GET", "/api/olmayan_rota")
        r404 = conn.getresponse()
        assert r404.status == 404
    finally:
        srv.shutdown()
        srv.server_close()


def test_web_server_refuses_non_loopback_host(tmp_path: Path):
    eng = QtpEngine(work_dir=tmp_path)
    with pytest.raises(ValueError) as exc:
        create_web_server(eng, host="0.0.0.0", port=0)
    assert "127.0.0.1" in str(exc.value)


def test_web_server_backups_shutdown_and_error_status(tmp_path: Path):
    from unittest import mock
    from qtp_app.web import run_web_server

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
        r_shut = conn.getresponse()
        assert r_shut.status == 200
        th.join(timeout=3)
    finally:
        srv.server_close()

    assert run_web_server(eng, port=0, open_browser=False, shutdown_after=0.1) == 0
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

