"""Yalnızca Python stdlib kullanan yerel 127.0.0.1 HTTP sunucusu ve JSON API (--web modu)."""

from __future__ import annotations

import importlib.resources
import json
import os
import posixpath
import sys
import threading
import urllib.parse
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from qtp_app.core.engine import OperationResult, QtpEngine, get_bundled_docs_dir
from qtp_app.core.logging_setup import get_logger
from qtp_app.core.operations import OPERATIONS

ALLOWED_LOOPBACK_HOSTS = ("127.0.0.1", "localhost")
web_logger = get_logger("web")

_EXIT_TO_HTTP_STATUS = {
    0: HTTPStatus.OK,
    1: HTTPStatus.BAD_REQUEST,
    2: HTTPStatus.NOT_FOUND,
    3: HTTPStatus.SERVICE_UNAVAILABLE,
    4: HTTPStatus.CONFLICT,
}


def _read_web_asset(filename: str) -> bytes:
    return _read_pkg_asset("web", filename)


def _read_pkg_asset(subdir: str, filename: str) -> bytes:
    try:
        files_fn = getattr(importlib.resources, "files", None)
        if files_fn is not None:
            pkg_root = Path(str(files_fn("qtp_app")))
            candidate = pkg_root / subdir / filename
            if candidate.is_file():
                return candidate.read_bytes()
    except Exception:
        pass
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        meipass_candidate = Path(getattr(sys, "_MEIPASS")) / "qtp_app" / subdir / filename
        if meipass_candidate.is_file():
            return meipass_candidate.read_bytes()
    local = Path(__file__).resolve().parent / subdir / filename
    return local.read_bytes()


def map_exit_to_http_status(exit_code: int) -> int:
    return int(_EXIT_TO_HTTP_STATUS.get(exit_code, HTTPStatus.INTERNAL_SERVER_ERROR))


class QtpWebServer(ThreadingHTTPServer):
    """QtpEngine örneğini taşıyan izole yerel HTTP sunucusu."""

    allow_reuse_address = True

    def __init__(
        self,
        server_address: tuple[str, int],
        engine: QtpEngine,
        *,
        initial_category: str = "ALL",
        initial_query: str = "",
    ):
        self.engine = engine
        self.initial_category = (initial_category or "ALL").strip().upper() or "ALL"
        self.initial_query = str(initial_query or "")
        self.shutdown_event = threading.Event()
        super().__init__(server_address, QtpWebRequestHandler)


class QtpWebRequestHandler(BaseHTTPRequestHandler):
    server_version = "QTPWeb/2.3.0"

    @staticmethod
    def _parse_qs_bool(val: str) -> bool:
        return str(val or "").strip().lower() in ("1", "true", "evet", "yes", "on")

    @staticmethod
    def _parse_opt_bool(body: dict[str, Any], key: str) -> bool | None:
        if key not in body or body[key] is None:
            return None
        val = body[key]
        if isinstance(val, bool):
            return val
        return str(val).strip().lower() in ("1", "true", "evet", "yes", "on")

    @property
    def engine(self) -> QtpEngine:
        return self.server.engine

    def log_request(self, code: int | str = "-", size: int | str = "-") -> None:
        method = getattr(self, "command", "-")
        req_path = getattr(self, "path", "-")
        web_logger.info("%s %s -> %s", method, req_path, code)

    def log_message(self, format: str, *args: Any) -> None:
        web_logger.debug("Web %s - %s", self.address_string(), format % args)

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
        raw_path = parsed.path or "/"
        path = posixpath.normpath(raw_path)
        if not path.startswith("/"):
            path = "/" + path
        if raw_path.endswith("/") and path != "/":
            path += "/"
        qs = urllib.parse.parse_qs(parsed.query)

        if path in ("/", "/qtp.html", "/index.html"):
            self._send_bytes(_read_web_asset("qtp.html"), "text/html; charset=utf-8")
            return
        if path == "/theme.css":
            self._send_bytes(_read_web_asset("theme.css"), "text/css; charset=utf-8")
            return
        if path in ("/icon.svg", "/favicon.ico"):
            try:
                self._send_bytes(_read_pkg_asset("assets", "icon.svg"), "image/svg+xml; charset=utf-8")
                return
            except OSError:
                pass
        if path in ("/docs/KULLANIM.md", "/docs/KURULUM.md", "/docs/KISAYOLLAR.md", "/docs/SSS.md"):
            doc_file = get_bundled_docs_dir() / Path(path).name
            if doc_file.is_file():
                self._send_bytes(doc_file.read_bytes(), "text/markdown; charset=utf-8")
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
            v_param = qs.get("verbose", ["0"])[0].strip().lower()
            self._send_result(self.engine.op_help(verbose=v_param in ("1", "true", "yes", "evet")))
            return
        if path == "/api/selftest":
            self._send_result(self.engine.op_selftest(run_ui_smoke=False))
            return
        if path == "/api/modes":
            self._send_result(self.engine.op_modes())
            return
        if path == "/api/completion":
            shell = qs.get("shell", ["auto"])[0]
            self._send_result(self.engine.op_completion(shell))
            return
        if path == "/api/categories":
            self._send_result(self.engine.op_list_categories())
            return
        if path == "/api/items":
            cat = qs.get("category", ["ALL"])[0]
            q = qs.get("query", [""])[0]
            only_fav = self._parse_qs_bool(qs.get("only_favorites", [""])[0])
            only_notes = self._parse_qs_bool(qs.get("only_notes", [""])[0])
            grp = qs.get("group", [""])[0]
            sort_by = qs.get("sort", qs.get("sort_by", [""]))[0] or None
            self._send_result(
                self.engine.op_list_items(
                    category=cat,
                    query=q,
                    only_favorites=only_fav,
                    only_notes=only_notes,
                    group=grp,
                    sort_by=sort_by,
                )
            )
            return
        if path == "/api/search":
            q = qs.get("q", qs.get("query", [""]))[0]
            cat = qs.get("category", ["ALL"])[0]
            only_fav = self._parse_qs_bool(qs.get("only_favorites", [""])[0])
            only_notes = self._parse_qs_bool(qs.get("only_notes", [""])[0])
            grp = qs.get("group", [""])[0]
            sort_by = qs.get("sort", qs.get("sort_by", [""]))[0] or None
            self._send_result(
                self.engine.op_search(
                    q,
                    category=cat,
                    only_favorites=only_fav,
                    only_notes=only_notes,
                    group=grp,
                    sort_by=sort_by,
                )
            )
            return
        if path == "/api/groups":
            self._send_result(self.engine.op_list_groups())
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
        if path == "/api/hotkeys/check":
            self._send_result(self.engine.op_check_hotkeys())
            return
        if path == "/api/revision":
            fav_count = sum(1 for it in self.engine.items if bool(it.get("favorite", False)))
            res = OperationResult(
                ok=True,
                exit_code=0,
                message="Durum alındı.",
                data={
                    "revision": self.engine.revision,
                    "theme": self.engine.settings.get("theme"),
                    "view_mode": self.engine.settings.get("view_mode", "list"),
                    "strip_emoji": bool(self.engine.settings.get("strip_emoji", False)),
                    "sort_by": self.engine.settings.get("sort_by", "order"),
                    "hotkeys": self.engine.settings.get("hotkeys"),
                    "item_count": len(self.engine.items),
                    "favorite_count": fav_count,
                    "can_undo": bool(self.engine._undo_stack),
                    "can_redo": bool(self.engine._redo_stack),
                    "initial_category": self.server.initial_category,
                    "initial_query": self.server.initial_query,
                },
            )
            self._send_result(res)
            return

        err = f"Bilinmeyen API uç noktası: {path}"
        self._send_result(OperationResult(ok=False, exit_code=2, message=err, error=err))

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        body = self._read_json_body()

        if path == "/api/copy":
            strip_flag = self._parse_opt_bool(body, "strip_emoji")
            self._send_result(self.engine.op_copy(str(body.get("target", "")), strip_emoji=strip_flag))
            return
        if path == "/api/paste":
            strip_flag = self._parse_opt_bool(body, "strip_emoji")
            self._send_result(self.engine.op_paste(str(body.get("target", "")), strip_emoji=strip_flag))
            return
        if path == "/api/reload":
            self._send_result(self.engine.reload_data())
            return
        if path == "/api/save":
            self._send_result(self.engine.op_save_all())
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
        if path == "/api/hotkeys/preset":
            preset = str(body.get("preset", "recommended"))
            self._send_result(self.engine.op_apply_hotkey_preset(preset))
            return
        if path == "/api/hotkeys/modifiers":
            mods = str(body.get("modifiers", "Win+Alt"))
            self._send_result(self.engine.op_apply_hotkey_modifiers(mods))
            return
        if path == "/api/import-ini":
            skip_dup = bool(body.get("skip_duplicates", False))
            self._send_result(
                self.engine.op_import_ini(
                    str(body.get("path", "")),
                    mode=str(body.get("mode", "merge")),
                    skip_duplicates=skip_dup,
                )
            )
            return
        if path == "/api/import-content":
            skip_dup = bool(body.get("skip_duplicates", False))
            self._send_result(
                self.engine.op_import_content(
                    str(body.get("content", "")),
                    filename=str(body.get("filename", "import.ini")),
                    mode=str(body.get("mode", "merge")),
                    skip_duplicates=skip_dup,
                )
            )
            return
        if path == "/api/export-ini":
            raw_keys_val = body.get("raw_keys")
            if isinstance(raw_keys_val, str):
                raw_keys = [k.strip() for k in raw_keys_val.split(",") if k.strip()] or None
            elif isinstance(raw_keys_val, list):
                raw_keys = [str(k).strip() for k in raw_keys_val if str(k).strip()] or None
            else:
                raw_keys = None
            enc = str(body.get("encoding", "utf-16-le-bom") or "utf-16-le-bom")
            self._send_result(
                self.engine.op_export_ini(
                    str(body.get("path", "")),
                    raw_keys=raw_keys,
                    encoding=enc,
                )
            )
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
        if path == "/api/items/add":
            self._send_result(
                self.engine.op_add_item(
                    str(body.get("text", "")),
                    keys=str(body.get("keys", "")),
                    group=str(body.get("group", "Genel")),
                    label=str(body.get("label", "")),
                    terminator=body.get("terminator", "<E<N<D|"),
                    favorite=bool(body.get("favorite", False)),
                )
            )
            return
        if path == "/api/items/update":
            self._send_result(
                self.engine.op_update_item(
                    str(body.get("target", body.get("raw_key", ""))),
                    keys=body.get("keys"),
                    group=body.get("group"),
                    label=body.get("label"),
                    text=body.get("text"),
                    terminator=body.get("terminator"),
                    favorite=self._parse_opt_bool(body, "favorite"),
                )
            )
            return
        if path == "/api/items/delete":
            self._send_result(
                self.engine.op_delete_item(str(body.get("target", body.get("raw_key", ""))))
            )
            return
        if path == "/api/items/duplicate":
            self._send_result(
                self.engine.op_duplicate_item(str(body.get("target", body.get("raw_key", ""))))
            )
            return
        if path == "/api/items/move":
            self._send_result(
                self.engine.op_move_item(
                    str(body.get("target", body.get("raw_key", ""))),
                    direction=str(body.get("direction", "up")),
                )
            )
            return
        if path == "/api/items/favorite":
            self._send_result(
                self.engine.op_toggle_favorite(
                    str(body.get("target", body.get("raw_key", ""))),
                    favorite=self._parse_opt_bool(body, "favorite"),
                )
            )
            return
        if path == "/api/items/bulk-edit":
            targets = body.get("targets", body.get("raw_keys", []))
            self._send_result(
                self.engine.op_bulk_edit(
                    targets,
                    keys=body.get("keys"),
                    group=body.get("group"),
                    find=body.get("find"),
                    replace=str(body.get("replace", "") or ""),
                    ignore_case=bool(body.get("ignore_case", False)),
                    prefix=str(body.get("prefix", "") or ""),
                    suffix=str(body.get("suffix", "") or ""),
                    strip_emojis=bool(body.get("strip_emojis", False)),
                    add_emoji=str(body.get("add_emoji", "") or ""),
                    favorite_action=str(body.get("favorite_action", "keep") or "keep"),
                )
            )
            return
        if path == "/api/items/bulk-delete":
            targets = body.get("targets", body.get("raw_keys", []))
            self._send_result(self.engine.op_bulk_delete(targets))
            return
        if path == "/api/groups/rename":
            self._send_result(
                self.engine.op_rename_group(
                    str(body.get("old_group", body.get("old", ""))),
                    str(body.get("new_group", body.get("new", ""))),
                )
            )
            return
        if path == "/api/groups/delete":
            self._send_result(
                self.engine.op_delete_group(str(body.get("group", body.get("name", ""))))
            )
            return
        if path == "/api/undo":
            self._send_result(self.engine.op_undo())
            return
        if path == "/api/redo":
            self._send_result(self.engine.op_redo())
            return
        if path == "/api/shutdown":
            res = OperationResult(ok=True, exit_code=0, message="Web sunucusu kapatılıyor.")
            self._send_result(res)
            threading.Thread(target=self._trigger_shutdown, daemon=True).start()
            return

        err = f"Bilinmeyen API uç noktası: {path}"
        self._send_result(OperationResult(ok=False, exit_code=2, message=err, error=err))

    def _trigger_shutdown(self) -> None:
        self.server.shutdown_event.set()
        self.server.shutdown()


def create_web_server(
    engine: QtpEngine,
    *,
    host: str = "127.0.0.1",
    port: int | None = None,
    initial_category: str = "ALL",
    initial_query: str = "",
) -> QtpWebServer:
    """Yalnızca 127.0.0.1/localhost üzerine bağlanan yerel web sunucusu oluşturur."""
    if host not in ALLOWED_LOOPBACK_HOSTS:
        raise ValueError(
            f"Güvenlik kuralı: Web sunucusu yalnızca 127.0.0.1 üzerinde çalışabilir ('{host}' reddedildi)."
        )
    chosen_port = int(port if port is not None else engine.settings.get("web", {}).get("port", 8765))
    return QtpWebServer(
        (host, chosen_port),
        engine,
        initial_category=initial_category,
        initial_query=initial_query,
    )


def run_web_server(
    engine: QtpEngine,
    *,
    port: int | None = None,
    open_browser: bool = False,
    shutdown_after: float | None = None,
    quiet: bool = False,
    verbose: int = 0,
    initial_category: str = "ALL",
    initial_query: str = "",
) -> int:
    """Yerel web sunucusunu başlatır; canlı dosya izleyici, ayrıntı günlüğü ve zarif kapanış sağlar."""
    eff_verbose = max(int(verbose or 0), int(getattr(engine, "verbose", 0) or 0))
    eff_quiet = bool(quiet) and eff_verbose <= 0
    if eff_verbose > 0:
        engine.configure_verbosity(eff_verbose, eff_quiet)
        engine.emit_startup_diagnostics("web")

    try:
        srv = create_web_server(
            engine,
            host="127.0.0.1",
            port=port,
            initial_category=initial_category,
            initial_query=initial_query,
        )
    except OSError as exc:
        err = f"HATA: Web sunucusu başlatılamadı (port kullanımda olabilir): {exc}"
        print(err, file=sys.stderr)
        web_logger.error(err)
        return 1

    actual_port = srv.server_address[1]
    url = f"http://127.0.0.1:{actual_port}/"
    if not eff_quiet:
        print(f"QTP Web Modu çalışıyor: {url} (Kapatmak için Ctrl+C veya POST /api/shutdown)")
        sys.stdout.flush()
    web_logger.info(
        "Web sunucusu başlatıldı: %s (kategori=%s, sorgu=%r)",
        url,
        srv.initial_category,
        srv.initial_query,
    )

    engine.start_watcher(on_reload=lambda ev: web_logger.info("Web canlı yenileme: rev=%d kayıt=%d", engine.revision, ev.item_count))

    if open_browser and (
        sys.platform in ("win32", "darwin")
        or os.environ.get("DISPLAY")
        or os.environ.get("WAYLAND_DISPLAY")
    ):
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
        engine.stop_watcher()
        srv.server_close()
        web_logger.info("Web sunucusu kapatıldı.")
    return 0
