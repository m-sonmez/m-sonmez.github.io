#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QTP Full-Stack Yerel Sunucu & REST API (qtp_server.py)
- Web PWA (index.html / cevaplar.html) için statik sunucu + CORS/PNA destekli REST API
- data.json <-> QuickTextPaste.ini çift yönlü disk senkronizasyonu ve yedekleme
- QuickTextPaste uygulamasını otomatik kontrol etme, indirme, başlatma ve yeniden yükleme
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import mimetypes
import os
import sys
import threading
import urllib.parse
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import qtp_core


SERVER_VERSION = "3.0.0"

ALLOWED_ORIGINS = {
    "https://m-sonmez.github.io",
    "http://127.0.0.1",
    "http://localhost",
}

mimetypes.add_type("application/manifest+json", ".webmanifest")
mimetypes.add_type("image/svg+xml", ".svg")
mimetypes.add_type("application/javascript; charset=utf-8", ".js")


def _configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _cors_origin_for(origin: str | None) -> str | None:
    if not origin:
        return None
    if origin in ALLOWED_ORIGINS:
        return origin
    parsed = urllib.parse.urlparse(origin)
    if parsed.hostname in ("127.0.0.1", "localhost"):
        return origin
    if origin == "null":
        return "*"
    return None


class QTPServerState:
    """Thread-safe çalışma dizini durumu."""

    def __init__(self, work_dir: Path):
        self.work_dir = work_dir.resolve()
        self.lock = threading.RLock()


class QTPRequestHandler(BaseHTTPRequestHandler):
    server_version = f"QTPFullStack/{SERVER_VERSION}"

    @property
    def ctx(self) -> QTPServerState:
        return self.server.ctx  # type: ignore[attr-defined]

    def log_message(self, format: str, *args: Any) -> None:
        # Konsol gürültüsünü azalt; yalnızca API hatalarını veya önemli istekleri kısa yazdır
        if args and isinstance(args[0], str) and args[0].startswith("GET /api/status"):
            return
        sys.stderr.write(f"[QTP-HTTP] {self.address_string()} - {format % args}\n")

    def _send_cors_headers(self) -> None:
        origin = self.headers.get("Origin")
        allowed = _cors_origin_for(origin)
        if allowed:
            self.send_header("Access-Control-Allow-Origin", allowed)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        if self.headers.get("Access-Control-Request-Private-Network"):
            self.send_header("Access-Control-Allow-Private-Network", "true")

    def _send_json(self, payload: Any, status: int = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self._send_cors_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_bytes(
        self,
        data: bytes,
        content_type: str,
        filename: str | None = None,
        status: int = HTTPStatus.OK,
        cache_control: str = "no-store",
    ) -> None:
        self.send_response(status)
        self._send_cors_headers()
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", cache_control)
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        if length > 25 * 1024 * 1024:
            raise ValueError("İstek boyutu çok büyük (25 MB sınırı).")
        raw = self.rfile.read(length)
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("JSON gövdesi nesne olmalıdır.")
        return data

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self._send_cors_headers()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)

        try:
            if path == "/api/health" or path == "/api/status":
                with self.ctx.lock:
                    state = qtp_core.load_state(self.ctx.work_dir)
                    status = qtp_core.get_qtp_status(self.ctx.work_dir)
                    backups = qtp_core.list_backups(self.ctx.work_dir)
                self._send_json({
                    "ok": True,
                    "serverVersion": SERVER_VERSION,
                    "workDir": str(self.ctx.work_dir),
                    "qtp": status,
                    "files": {
                        "count": len(state["items"]),
                        "source": state["source"],
                        "iniMtime": state["iniMtime"],
                        "jsonMtime": state["jsonMtime"],
                        "backupCount": len(backups),
                    },
                })
                return

            if path == "/api/data":
                with self.ctx.lock:
                    state = qtp_core.load_state(self.ctx.work_dir)
                    status = qtp_core.get_qtp_status(self.ctx.work_dir)
                self._send_json({
                    "ok": True,
                    **state,
                    "qtp": status,
                })
                return

            if path == "/api/backups":
                with self.ctx.lock:
                    backups = qtp_core.list_backups(self.ctx.work_dir)
                self._send_json({"ok": True, "backups": backups})
                return

            if path == "/api/export/ini":
                enc = (qs.get("encoding") or ["utf-16-le-bom"])[0]
                with self.ctx.lock:
                    state = qtp_core.load_state(self.ctx.work_dir)
                ini_text = qtp_core.build_qtp_ini(
                    state["items"],
                    program=state.get("program"),
                    extra_sections=state.get("extraSections"),
                )
                raw = qtp_core.encode_qtp_ini(ini_text, encoding=enc)
                self._send_bytes(raw, "text/plain; charset=utf-8", filename="QuickTextPaste.ini")
                return

            if path == "/api/export/json":
                with self.ctx.lock:
                    state = qtp_core.load_state(self.ctx.work_dir)
                clean = qtp_core.strip_for_data_json(state["items"])
                raw = (json.dumps(clean, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
                self._send_bytes(raw, "application/json; charset=utf-8", filename="data.json")
                return

            if path == "/api/export/backup":
                with self.ctx.lock:
                    state = qtp_core.load_state(self.ctx.work_dir)
                payload = {
                    "type": "qtp-pwa-backup",
                    "version": 2,
                    "exportedAt": _dt.datetime.now(_dt.timezone.utc).isoformat(),
                    "settings": {"qtpPrefs": state.get("qtpPrefs") or {}},
                    "program": state.get("program") or {},
                    "extraSections": state.get("extraSections") or [],
                    "items": state["items"],
                }
                raw = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
                stamp = _dt.datetime.now().strftime("%Y-%m-%d")
                self._send_bytes(raw, "application/json; charset=utf-8", filename=f"qtp-tam-yedek-{stamp}.json")
                return

            if path.startswith("/api/"):
                self._send_json({"ok": False, "error": f"Bilinmeyen API yolu: {path}"}, status=HTTPStatus.NOT_FOUND)
                return

            self._serve_static(path)
        except Exception as exc:
            self._send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        try:
            body = self._read_json_body()

            if path == "/api/data":
                items = body.get("items")
                if not isinstance(items, list):
                    self._send_json({"ok": False, "error": "'items' alanı liste olmalıdır."}, status=HTTPStatus.BAD_REQUEST)
                    return

                encoding = str(body.get("encoding") or "utf-16-le-bom")
                reload_qtp = bool(body.get("reloadQtp", False))
                create_backup_flag = bool(body.get("createBackup", False))
                backup_reason = str(body.get("backupReason") or "api_save")

                with self.ctx.lock:
                    # Veri içeriği değişmediyse (örneğin yalnızca kopya sayacı artmışsa) yedek şişirme
                    if create_backup_flag:
                        existing = qtp_core.load_state(self.ctx.work_dir)
                        if qtp_core.strip_for_data_json(existing["items"]) == qtp_core.strip_for_data_json(items):
                            create_backup_flag = False

                    res = qtp_core.save_state(
                        self.ctx.work_dir,
                        items=items,
                        program=body.get("program"),
                        extra_sections=body.get("extraSections"),
                        qtp_prefs=body.get("qtpPrefs"),
                        encoding=encoding,
                        create_backup_flag=create_backup_flag,
                        backup_reason=backup_reason,
                        reload_qtp=reload_qtp,
                    )
                self._send_json(res)
                return

            if path == "/api/import":
                content = body.get("content")
                if not isinstance(content, str):
                    self._send_json({"ok": False, "error": "'content' metni gereklidir."}, status=HTTPStatus.BAD_REQUEST)
                    return
                filename = str(body.get("filename") or "")
                mode = str(body.get("mode") or "merge")
                skip_dups = bool(body.get("skipDups", True))
                reload_qtp = bool(body.get("reloadQtp", True))

                parsed_file = qtp_core.parse_any_content(content, filename=filename)
                with self.ctx.lock:
                    cur = qtp_core.load_state(self.ctx.work_dir)
                    base_items = [] if mode == "replace" else list(cur["items"])
                    existing_texts = {str(x.get("text", "")).strip() for x in base_items}
                    added = 0
                    skipped = 0
                    for raw in parsed_file["items"]:
                        txt = str(raw.get("text", "")).strip()
                        if skip_dups and txt in existing_texts:
                            skipped += 1
                            continue
                        base_items.append(raw)
                        existing_texts.add(txt)
                        added += 1

                    prog = dict(cur.get("program") or {})
                    if parsed_file.get("program"):
                        prog.update(parsed_file["program"])
                    extra_sec = parsed_file.get("extra_sections") or cur.get("extraSections") or []

                    res = qtp_core.save_state(
                        self.ctx.work_dir,
                        items=base_items,
                        program=prog,
                        extra_sections=extra_sec,
                        qtp_prefs=cur.get("qtpPrefs"),
                        create_backup_flag=True,
                        backup_reason="import",
                        reload_qtp=reload_qtp,
                    )
                    fresh = qtp_core.load_state(self.ctx.work_dir)
                self._send_json({**res, "added": added, "skipped": skipped, "state": fresh})
                return

            if path == "/api/sync-from-ini":
                with self.ctx.lock:
                    ini_path = self.ctx.work_dir / "QuickTextPaste.ini"
                    exe = qtp_core.find_quicktextpaste_exe(self.ctx.work_dir)
                    exe_ini = (exe.parent / "QuickTextPaste.ini") if exe else None
                    src_ini = exe_ini if (exe_ini and exe_ini.is_file() and (not ini_path.is_file() or exe_ini.stat().st_mtime > ini_path.stat().st_mtime)) else ini_path
                    if not src_ini.is_file():
                        self._send_json({"ok": False, "error": "QuickTextPaste.ini bulunamadı."}, status=HTTPStatus.NOT_FOUND)
                        return
                    parsed_ini = qtp_core.parse_qtp_ini_full(qtp_core.read_text_auto(src_ini))
                    res = qtp_core.save_state(
                        self.ctx.work_dir,
                        items=parsed_ini["items"],
                        program=parsed_ini["program"],
                        extra_sections=parsed_ini["extra_sections"],
                        create_backup_flag=True,
                        backup_reason="sync_ini",
                        reload_qtp=False,
                    )
                    fresh = qtp_core.load_state(self.ctx.work_dir)
                self._send_json({**res, "state": fresh})
                return

            if path == "/api/backups":
                reason = str(body.get("reason") or "manual")
                with self.ctx.lock:
                    meta = qtp_core.create_backup(self.ctx.work_dir, reason=reason)
                    backups = qtp_core.list_backups(self.ctx.work_dir)
                self._send_json({"ok": True, "created": meta, "backups": backups})
                return

            if path == "/api/backups/restore":
                backup_id = str(body.get("id") or "")
                reload_qtp = bool(body.get("reloadQtp", True))
                if not backup_id:
                    self._send_json({"ok": False, "error": "Yedek kimliği ('id') gerekli."}, status=HTTPStatus.BAD_REQUEST)
                    return
                with self.ctx.lock:
                    res = qtp_core.restore_backup(self.ctx.work_dir, backup_id, reload_qtp=reload_qtp)
                self._send_json(res)
                return

            if path == "/api/qtp/install":
                arch = str(body.get("arch") or "auto")
                with self.ctx.lock:
                    res = qtp_core.install_quicktextpaste(self.ctx.work_dir, arch=arch)
                self._send_json(res)
                return

            if path == "/api/qtp/start":
                bg = bool(body.get("background", True))
                ensure = bool(body.get("ensureInstalled", True))
                with self.ctx.lock:
                    res = qtp_core.start_quicktextpaste(self.ctx.work_dir, background=bg, ensure_installed=ensure)
                self._send_json(res)
                return

            if path == "/api/qtp/stop":
                with self.ctx.lock:
                    res = qtp_core.stop_quicktextpaste()
                    res["status"] = qtp_core.get_qtp_status(self.ctx.work_dir)
                self._send_json(res)
                return

            if path == "/api/qtp/restart":
                with self.ctx.lock:
                    qtp_core.stop_quicktextpaste()
                    res = qtp_core.start_quicktextpaste(self.ctx.work_dir, background=True, ensure_installed=True)
                self._send_json(res)
                return

            self._send_json({"ok": False, "error": f"Bilinmeyen API yolu: {path}"}, status=HTTPStatus.NOT_FOUND)
        except ValueError as exc:
            self._send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
        except FileNotFoundError as exc:
            self._send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.NOT_FOUND)
        except Exception as exc:
            self._send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)

    def _serve_static(self, req_path: str) -> None:
        clean_rel = urllib.parse.unquote(req_path).lstrip("/")
        if not clean_rel:
            clean_rel = "index.html"

        # Gizli sistem/backup/exe dosyalarını statik HTTP üzerinden servis etme
        first_seg = clean_rel.split("/", 1)[0]
        if first_seg.startswith(".") or first_seg in ("backups", "__pycache__", "tests") or clean_rel.lower().endswith(".exe"):
            self.send_error(HTTPStatus.FORBIDDEN, "Erişim reddedildi")
            return

        target = (self.ctx.work_dir / clean_rel).resolve()
        try:
            target.relative_to(self.ctx.work_dir)
        except ValueError:
            self.send_error(HTTPStatus.FORBIDDEN, "Geçersiz dosya yolu")
            return

        if target.is_dir():
            target = target / "index.html"
        if not target.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, "Dosya bulunamadı")
            return

        ctype, _ = mimetypes.guess_type(str(target))
        if not ctype:
            ctype = "application/octet-stream"
        if target.suffix.lower() in (".html", ".json", ".js", ".css", ".webmanifest"):
            if "charset" not in ctype:
                ctype += "; charset=utf-8"

        cache_hdr = "no-cache" if target.suffix.lower() in (".html", ".json", ".js", ".ini") else "public, max-age=3600"
        self._send_bytes(target.read_bytes(), ctype, cache_control=cache_hdr)


def ensure_qtp_ready(work_dir: Path, install_missing: bool = True, start_if_stopped: bool = True) -> dict[str, Any]:
    """QuickTextPaste kurulu ve çalışıyor durumunu doğrular; Windows'ta eksikse kurar ve başlatır."""
    status = qtp_core.get_qtp_status(work_dir)
    if not status["is_windows"]:
        print(f"[QTP] Platform: {status['platform']} (QuickTextPaste Windows uygulamasıdır; Web/API tam işlevle çalışacak).")
        return status

    if not status["installed"] and install_missing:
        print("[QTP] QuickTextPaste bulunamadı; resmi SoftwareOK paketinden indiriliyor...")
        try:
            res = qtp_core.install_quicktextpaste(work_dir, progress_cb=lambda m: print(f"[QTP] {m}"))
            status = res["status"]
            print(f"[QTP] Kurulum tamamlandı: {status['exe_path']}")
        except Exception as exc:
            print(f"[QTP] Uyarı: QuickTextPaste otomatik indirilemedi: {exc}")
            print(f"[QTP] Manuel indirme: {status['download_url']}")
            return status

    if status["installed"] and not status["running"] and start_if_stopped:
        print(f"[QTP] QuickTextPaste başlatılıyor: {status['exe_path']}")
        res = qtp_core.start_quicktextpaste(work_dir, background=True, ensure_installed=False)
        status = res.get("status", status)
        if status.get("running"):
            print(f"[QTP] QuickTextPaste çalışıyor (PID: {', '.join(map(str, status['pids']))}).")
        else:
            print("[QTP] QuickTextPaste başlatma komutu gönderildi.")
    elif status["running"]:
        print(f"[QTP] QuickTextPaste zaten çalışıyor (PID: {', '.join(map(str, status['pids']))}).")

    return status


def create_http_server(work_dir: Path, host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    srv = ThreadingHTTPServer((host, port), QTPRequestHandler)
    srv.ctx = QTPServerState(work_dir)  # type: ignore[attr-defined]
    return srv


def main(argv: list[str] | None = None) -> int:
    _configure_stdio()
    parser = argparse.ArgumentParser(description="QTP Full-Stack Web & REST API Sunucusu")
    parser.add_argument("--host", default="127.0.0.1", help="Dinlenecek adres (varsayılan: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=int(os.environ.get("QTP_PORT", "8765")), help="Port (varsayılan: 8765)")
    parser.add_argument("--work-dir", default=".", help="Çalışma klasörü (data.json ve QuickTextPaste.ini)")
    parser.add_argument("--ensure-qtp", action="store_true", help="QuickTextPaste kurulu ve çalışıyor değilse kur/başlat")
    parser.add_argument("--no-qtp", action="store_true", help="QuickTextPaste otomatik kontrol/başlatmayı atla")
    parser.add_argument("--open-browser", action="store_true", help="Başladıktan sonra tarayıcıyı aç")
    parser.add_argument("--status", action="store_true", help="Yalnızca durum JSON çıktısı ver ve çık")
    parser.add_argument("--install-qtp", action="store_true", help="QuickTextPaste indir/kur ve çık")
    parser.add_argument("--start-qtp", action="store_true", help="QuickTextPaste başlat ve çık")
    parser.add_argument("--sync", action="store_true", help="data.json ve QuickTextPaste.ini dosyalarını senkronize et ve çık")
    args = parser.parse_args(argv)

    work_dir = Path(args.work_dir).resolve()

    if args.status:
        print(json.dumps({
            "qtp": qtp_core.get_qtp_status(work_dir),
            "state": {
                "count": len(qtp_core.load_state(work_dir)["items"]),
                "backups": len(qtp_core.list_backups(work_dir)),
            },
        }, ensure_ascii=False, indent=2))
        return 0

    if args.install_qtp:
        res = qtp_core.install_quicktextpaste(work_dir, progress_cb=lambda m: print(f"[QTP] {m}"))
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0

    if args.start_qtp:
        res = qtp_core.start_quicktextpaste(work_dir, background=True, ensure_installed=True)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0 if res.get("ok") else 1

    if args.sync:
        st = qtp_core.load_state(work_dir)
        res = qtp_core.save_state(
            work_dir,
            items=st["items"],
            program=st["program"],
            extra_sections=st["extraSections"],
            qtp_prefs=st["qtpPrefs"],
            create_backup_flag=False,
            reload_qtp=False,
        )
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0

    # İlk açılışta data.json <-> QuickTextPaste.ini yoksa/eksikse senkronize et
    if not (work_dir / "QuickTextPaste.ini").is_file() and (work_dir / "data.json").is_file():
        st = qtp_core.load_state(work_dir)
        qtp_core.save_state(work_dir, st["items"], create_backup_flag=False)

    if args.ensure_qtp and not args.no_qtp:
        ensure_qtp_ready(work_dir, install_missing=True, start_if_stopped=True)

    srv = create_http_server(work_dir, host=args.host, port=args.port)
    url = f"http://{args.host}:{args.port}/"
    print(f"QTP Full-Stack Sunucusu çalışıyor: {url}")
    print(f"Çalışma klasörü: {work_dir}")
    print("Durdurmak için Ctrl+C tuşlarına basın.")

    if args.open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()

    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nSunucu kapatılıyor...")
    finally:
        srv.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
