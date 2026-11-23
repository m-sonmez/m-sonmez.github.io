"""Yalnızca Python stdlib kullanan yerel 127.0.0.1 HTTP sunucusu ve JSON API (--web modu)."""

from __future__ import annotations

import importlib.resources
import json
import os
import signal
import sys
import threading
import urllib.parse
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from qtp_app.core.engine import OperationResult, QtpEngine
from qtp_app.core.operations import OPERATIONS

ALLOWED_LOOPBACK_HOSTS = ("127.0.0.1", "localhost")

_EXIT_TO_HTTP_STATUS = {
    0: HTTPStatus.OK,
    1: HTTPStatus.BAD_REQUEST,
    2: HTTPStatus.NOT_FOUND,
    3: HTTPStatus.SERVICE_UNAVAILABLE,
    4: HTTPStatus.CONFLICT,
}


def _read_web_asset(filename: str) -> bytes:
    try:
        pkg_root = Path(str(importlib.resources.files("qtp_app")))
        candidate = pkg_root / "web" / filename
        if candidate.is_file():
            return candidate.read_bytes()
    except Exception:
        pass
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        meipass_candidate = Path(getattr(sys, "_MEIPASS")) / "qtp_app" / "web" / filename
        if meipass_candidate.is_file():
            return meipass_candidate.read_bytes()
    local = Path(__file__).resolve().parent / "web" / filename
    return local.read_bytes()


def map_exit_to_http_status(exit_code: int) -> int:
    return int(_EXIT_TO_HTTP_STATUS.get(exit_code, HTTPStatus.INTERNAL_SERVER_ERROR))


class QtpWebServer(ThreadingHTTPServer):
    """QtpEngine örneğini taşıyan izole yerel HTTP sunucusu."""

    allow_reuse_address = True

    def __init__(self, server_address: tuple[str, int], engine: QtpEngine):
        self.engine = engine
        self.shutdown_event = threading.Event()
        super().__init__(server_address, QtpWebRequestHandler)


class QtpWebRequestHandler(BaseHTTPRequestHandler):
    server_version = "QTPWeb/2.1.0"

    @property
    def engine(self) -> QtpEngine:
        return self.server.engine  # type: ignore[attr-defined]

    def log_message(self, format: str, *args: Any) -> None:
        self.engine.logger.debug("Web %s - %s", self.address_string(), format % args)

    def _send_bytes(self, content: bytes, content_type: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _send_result(self, result: OperationResult) -> None:
        status = map_exit_to_http_status(result.exit_code)
        body = json.dumps(result.to_api_dict(), ensure_ascii=False).encode("utf-8")
        self._send_bytes(body, "application/json; charset=utf-8", status=status)

    def _read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            parsed = json.loads(raw.decode("utf-8"))
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)

        if path in ("/", "/index.html"):
            self._send_bytes(_read_web_asset("index.html"), "text/html; charset=utf-8")
            return
        if path == "/theme.css":
            self._send_bytes(_read_web_asset("theme.css"), "text/css; charset=utf-8")
            return
        if path == "/api":
            routes = [
                {"op_id": op.op_id, "label": op.label_tr, "route": op.web_route}
                for op in OPERATIONS
            ]
            res = OperationResult(ok=True, exit_code=0, message="API uç noktaları listelendi.", data={"routes": routes})
            self._send_result(res)
            return
        if path == "/api/version":
            self._send_result(self.engine.op_version())
            return
        if path == "/api/help":
            self._send_result(self.engine.op_help())
            return
        if path == "/api/selftest":
            self._send_result(self.engine.op_selftest(run_ui_smoke=False))
            return
        if path == "/api/modes":
            self._send_result(self.engine.op_modes())
            return
        if path == "/api/categories":
            self._send_result(self.engine.op_list_categories())
            return
        if path == "/api/items":
            cat = qs.get("category", ["ALL"])[0]
            q = qs.get("query", [""])[0]
            self._send_result(self.engine.op_list_items(category=cat, query=q))
            return
        if path == "/api/search":
            q = qs.get("q", qs.get("query", [""]))[0]
            cat = qs.get("category", ["ALL"])[0]
            self._send_result(self.engine.op_search(q, category=cat))
            return
        if path == "/api/show-ini":
            target = qs.get("target", [""])[0]
            self._send_result(self.engine.op_show_ini(target))
            return
        if path == "/api/settings":
            key = qs.get("key", [""])[0] or None
            self._send_result(self.engine.op_get_setting(key))
            return
        if path == "/api/backups":
            self._send_result(self.engine.op_list_backups())
            return

        err = f"Bilinmeyen API uç noktası: {path}"
        self._send_result(OperationResult(ok=False, exit_code=2, message=err, error=err))

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        body = self._read_json_body()

        if path == "/api/copy":
            self._send_result(self.engine.op_copy(str(body.get("target", ""))))
            return
        if path == "/api/paste":
            self._send_result(self.engine.op_paste(str(body.get("target", ""))))
            return
        if path == "/api/reload":
            self._send_result(self.engine.reload_data())
            return
        if path == "/api/backup":
            keep = body.get("keep")
            self._send_result(self.engine.op_backup(keep=int(keep) if keep is not None else None))
            return
        if path == "/api/settings":
            key = str(body.get("key", ""))
            value = body.get("value")
            self._send_result(self.engine.op_set_setting(key, value))
            return
        if path == "/api/import-ini":
            self._send_result(
                self.engine.op_import_ini(
                    str(body.get("path", "")),
                    mode=str(body.get("mode", "merge")),
                )
            )
            return
        if path == "/api/export-ini":
            self._send_result(self.engine.op_export_ini(str(body.get("path", ""))))
            return
        if path == "/api/export-backup":
            self._send_result(self.engine.op_export_backup(str(body.get("path", ""))))
            return
        if path == "/api/restore":
            self._send_result(
                self.engine.op_restore(
                    str(body.get("target", body.get("path", ""))),
                    mode=str(body.get("mode", "replace")),
                )
            )
            return
        if path == "/api/shutdown":
            res = OperationResult(ok=True, exit_code=0, message="Web sunucusu kapatılıyor.")
            self._send_result(res)
            threading.Thread(target=self._trigger_shutdown, daemon=True).start()
            return

        err = f"Bilinmeyen API uç noktası: {path}"
        self._send_result(OperationResult(ok=False, exit_code=2, message=err, error=err))

    def _trigger_shutdown(self) -> None:
        self.server.shutdown_event.set()  # type: ignore[attr-defined]
        self.server.shutdown()


def create_web_server(engine: QtpEngine, *, host: str = "127.0.0.1", port: int | None = None) -> QtpWebServer:
    """Yalnızca 127.0.0.1/localhost üzerine bağlanan yerel web sunucusu oluşturur."""
    if host not in ALLOWED_LOOPBACK_HOSTS:
        raise ValueError(
            f"Güvenlik kuralı: Web sunucusu yalnızca 127.0.0.1 üzerinde çalışabilir ('{host}' reddedildi)."
        )
    chosen_port = int(port if port is not None else engine.settings.get("web", {}).get("port", 8765))
    return QtpWebServer((host, chosen_port), engine)


def run_web_server(
    engine: QtpEngine,
    *,
    port: int | None = None,
    open_browser: bool = False,
    shutdown_after: float | None = None,
) -> int:
    """Yerel web sunucusunu başlatır; SIGINT/SIGTERM veya --shutdown-after ile zarifçe kapatır."""
    try:
        srv = create_web_server(engine, host="127.0.0.1", port=port)
    except OSError as exc:
        err = f"HATA: Web sunucusu başlatılamadı (port kullanımda olabilir): {exc}"
        print(err, file=sys.stderr)
        engine.logger.error(err)
        return 1

    actual_port = srv.server_address[1]
    url = f"http://127.0.0.1:{actual_port}/"
    print(f"QTP Web Modu çalışıyor: {url} (Kapatmak için Ctrl+C veya POST /api/shutdown)")
    sys.stdout.flush()
    engine.logger.info("Web sunucusu başlatıldı: %s", url)

    if open_browser and (sys.platform == "win32" or os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        try:
            webbrowser.open(url)
        except Exception:
            pass

    if shutdown_after is not None and shutdown_after > 0:
        timer = threading.Timer(float(shutdown_after), lambda: (srv.shutdown_event.set(), srv.shutdown()))
        timer.daemon = True
        timer.start()

    try:
        srv.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
        engine.logger.info("Web sunucusu kapatıldı.")
    return 0
