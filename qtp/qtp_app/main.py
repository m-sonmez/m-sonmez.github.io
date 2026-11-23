"""QTP — QuickTextPaste / Hazır Cevaplar tek dosya masaüstü uygulaması giriş noktası ve CLI."""

from __future__ import annotations

import argparse
import atexit
import datetime as _dt
import importlib.resources
import json
import os
import socket
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

from qtp_app import __app_name__, __build_date__, __display_name__, __version__
from qtp_app.core.hotkeys import HotkeyManager
from qtp_app.core.ini_parser import (
    IniParseError,
    build_qtp_ini,
    decode_bytes_auto,
    parse_qtp_ini,
    read_text_auto,
    serialize_qtp_ini,
    write_qtp_ini,
)
from qtp_app.core.json_store import (
    create_backup,
    list_backups,
    load_data_json,
    load_state,
    restore_backup,
    save_data_json,
    save_state,
    write_full_backup_file,
)
from qtp_app.core.logging_setup import get_logger, setup_logging
from qtp_app.core.paster import copy_to_clipboard, paste_into_active_app
from qtp_app.core.settings import (
    get_app_dir,
    load_settings,
    resolve_config_dir,
    resolve_data_path,
    save_settings,
)

LOCK_FILENAME = "qtp.lock"


def _configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _get_git_short_sha() -> str | None:
    try:
        root = Path(__file__).resolve().parent.parent
        proc = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=2,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout.strip()
    except Exception:
        pass
    return None


def get_bundled_default_path(filename: str) -> Path:
    """Paket içi varsayılan veri dosyasının (QuickTextPaste.ini / data.json) yolunu döndürür."""
    try:
        pkg_root = Path(str(importlib.resources.files("qtp_app")))
        candidate = pkg_root / "assets" / "defaults" / filename
        if candidate.is_file():
            return candidate
    except Exception:
        pass
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        meipass_candidate = Path(getattr(sys, "_MEIPASS")) / "qtp_app" / "assets" / "defaults" / filename
        if meipass_candidate.is_file():
            return meipass_candidate
    local = Path(__file__).resolve().parent / "assets" / "defaults" / filename
    if local.is_file():
        return local
    return Path(__file__).resolve().parent.parent / filename


def load_active_items(work_dir: Path, settings: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, str], list[dict[str, Any]], Path]:
    """
    Ayarlanan veri yolundan veya çalışma dizininden hazır cevapları yükler.
    Yerel dosya yoksa paket içi varsayılan QuickTextPaste.ini / data.json'a düşer.
    """
    ini_path = resolve_data_path(settings, work_dir)
    if ini_path.is_file() or (work_dir / "data.json").is_file():
        state = load_state(work_dir, ini_path=ini_path)
        if state["items"]:
            return state["items"], state.get("program") or {}, state.get("extraSections") or [], ini_path

    bundled_ini = get_bundled_default_path("QuickTextPaste.ini")
    if bundled_ini.is_file():
        doc = parse_qtp_ini(read_text_auto(bundled_ini))
        items = [it.to_dict(include_meta=False) | {"terminator": it.terminator, "raw_key": it.raw_key} for it in doc.items]
        return items, dict(doc.program), list(doc.extra_sections), ini_path

    bundled_json = get_bundled_default_path("data.json")
    if bundled_json.is_file():
        items = load_data_json(bundled_json)
        return items, {}, [], ini_path

    return [], {}, [], ini_path


def format_version_output() -> str:
    sha = _get_git_short_sha()
    sha_part = f" ({sha})" if sha else ""
    return f"{__display_name__} v{__version__} — Derleme: {__build_date__}{sha_part}"


def format_help_text() -> str:
    return (
        f"{__display_name__} v{__version__} — Komut Satırı Kullanımı\n\n"
        "Kullanım:\n"
        "  qtp [SEÇENEK]\n\n"
        "Seçenekler:\n"
        "  -h, --help            Bu Türkçe yardım metnini gösterir ve çıkar.\n"
        "  --version             Sürüm, derleme tarihi ve Git özet bilgisini yazdırır.\n"
        "  --selftest            Başsız arayüz duman testi ile INI gidiş-dönüş testini çalıştırır.\n"
        "  --export-ini YOL      Mevcut kayıtları UTF-16 LE BOM QuickTextPaste.ini olarak dışa aktarır.\n"
        "  --import-ini YOL      Belirtilen INI dosyasını mevcut kayıtlarla birleştirip kaydeder.\n"
        "  --work-dir DIZIN      Veri ve ayarlar için özel çalışma klasörü belirler.\n\n"
        "Kısayollar:\n"
        "  Win+A (İş Ortağı), Win+Z (Kurye), Win+X (Canlı Yardım),\n"
        "  Win+Q (Turkcell), Ctrl+Shift+Space (Tümü)\n"
    )


def run_selftest(work_dir: Path | None = None) -> tuple[bool, str]:
    """
    Faz 6 --selftest: Paketlenmiş QuickTextPaste.ini gidiş-dönüş testi ve
    offscreen PyQt6 overlay duman testi çalıştırır.
    """
    prev_qpa = os.environ.get("QT_QPA_PLATFORM")
    created_qapp = False
    try:
        bundled_ini = get_bundled_default_path("QuickTextPaste.ini")
        if not bundled_ini.is_file():
            return False, f"HATA: Paketlenmiş INI örneği bulunamadı: {bundled_ini}"

        raw_bytes = bundled_ini.read_bytes()
        decoded_text, detected_enc = decode_bytes_auto(raw_bytes)
        doc = parse_qtp_ini(decoded_text)
        reserialized = serialize_qtp_ini(doc, update_test_ini=False)
        if reserialized != decoded_text:
            return False, "HATA: Paketlenmiş QuickTextPaste.ini gidiş-dönüş (round-trip) doğrulaması başarısız."

        reparsed = parse_qtp_ini(reserialized)
        if len(reparsed.items) != len(doc.items) or len(doc.items) == 0:
            return False, f"HATA: Öğe sayısı uyuşmuyor ({len(reparsed.items)} != {len(doc.items)})."

        from PyQt6.QtCore import Qt
        from PyQt6.QtTest import QTest
        from PyQt6.QtWidgets import QApplication
        from qtp_app.ui.overlay import OverlayWindow

        app = QApplication.instance()
        if app is None:
            if not prev_qpa:
                os.environ["QT_QPA_PLATFORM"] = "offscreen"
            app = QApplication([sys.argv[0]])
            created_qapp = True

        items_dicts = [it.to_dict(include_meta=False) | {"terminator": it.terminator} for it in doc.items]
        pasted: list[dict[str, Any]] = []
        overlay = OverlayWindow(
            items_dicts,
            on_paste=lambda item, _prev: pasted.append(item),
        )
        try:
            overlay.show_overlay(category="ALL", animate=False, previous_app=None)
            app.processEvents()

            if overlay.list_model.rowCount() != len(doc.items):
                return (
                    False,
                    f"HATA: Katman beklenen {len(doc.items)} yerine {overlay.list_model.rowCount()} satır listeledi.",
                )

            if not overlay.search_input.hasFocus():
                return False, "HATA: Arama kutusu otomatik odaklanamadı."

            QTest.keyClick(overlay.search_input, Qt.Key.Key_Return)
            app.processEvents()
            if len(pasted) != 1:
                return False, "HATA: Enter tuşu yapıştırma geri çağrısını tetiklemedi."
        finally:
            overlay.close()
            overlay.deleteLater()
            app.processEvents()

        return (
            True,
            f"Otomatik test başarılı: {len(doc.items)} kayıt doğrulandı (kodlama={detected_enc}).",
        )
    except Exception as exc:
        return False, f"HATA: Otomatik test sırasında beklenmeyen hata: {exc}"
    finally:
        if created_qapp:
            pass
        if prev_qpa is None and os.environ.get("QT_QPA_PLATFORM") == "offscreen":
            os.environ.pop("QT_QPA_PLATFORM", None)


def export_ini_cli(target_path: Path, work_dir: Path) -> tuple[bool, str]:
    """Mevcut kayıtları belirtilen yola UTF-16 LE BOM QuickTextPaste.ini olarak yazar."""
    try:
        settings, _sp, _warn = load_settings(work_dir)
        items, program, extra_sections, _ini = load_active_items(work_dir, settings)
        if not items:
            return False, "HATA: Dışa aktarılacak hazır cevap kaydı bulunamadı."
        ini_text = build_qtp_ini(
            items,
            program=program,
            extra_sections=extra_sections,
            preserve_test_ini=True,
        )
        write_qtp_ini(target_path, ini_text, encoding="utf-16-le-bom", create_bak=True)
        return True, f"INI dışa aktarıldı: {target_path} ({len(items)} kayıt)."
    except Exception as exc:
        return False, f"HATA: INI dışa aktarılamadı: {exc}"


def import_ini_cli(source_path: Path, work_dir: Path) -> tuple[bool, str]:
    """Belirtilen INI dosyasını okur, mevcut kayıtları koruyarak birleştirir ve kaydeder."""
    if not source_path.is_file():
        return False, f"HATA: İçe aktarılacak INI dosyası bulunamadı: {source_path}"
    try:
        doc = parse_qtp_ini(read_text_auto(source_path))
        incoming = [
            it.to_dict(include_meta=False) | {"terminator": it.terminator}
            for it in doc.items
        ]
    except IniParseError as exc:
        return False, f"HATA: {exc}"
    except Exception as exc:
        return False, f"HATA: INI okunamadı: {exc}"

    settings, _sp, _warn = load_settings(work_dir)
    ini_target = resolve_data_path(settings, work_dir)
    if (work_dir / "data.json").is_file() or ini_target.is_file():
        state = load_state(work_dir, ini_path=ini_target)
        existing = state["items"]
        program = state.get("program") or {}
        extra_sections = state.get("extraSections") or []
    else:
        existing = []
        program = {}
        extra_sections = []

    merged = list(existing)
    seen = {
        (str(it.get("keys", "")), str(it.get("group", "")), str(it.get("text", "")))
        for it in existing
    }
    added = 0
    for it in incoming:
        sig = (str(it.get("keys", "")), str(it.get("group", "")), str(it.get("text", "")))
        if sig not in seen:
            merged.append(it)
            seen.add(sig)
            added += 1

    if not program and doc.program:
        program = dict(doc.program)
    if not extra_sections and doc.extra_sections:
        extra_sections = list(doc.extra_sections)

    save_state(
        work_dir,
        merged,
        program=program,
        extra_sections=extra_sections,
        backup_reason="cli_import",
        max_backups=int(settings.get("backup_count", 15)),
        ini_path=ini_target,
    )
    return (
        True,
        f"INI içe aktarıldı: {added} yeni kayıt eklendi (toplam {len(merged)} kayıt korundu).",
    )


class SingleInstanceGuard:
    """qtp.lock ve yerel loopback soketiyle tek örnek garantisi."""

    def __init__(self, lock_dir: Path):
        self.lock_path = lock_dir / LOCK_FILENAME
        self._sock: socket.socket | None = None
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._on_show: Any = None

    def try_notify_existing(self) -> bool:
        if not self.lock_path.is_file():
            return False
        try:
            payload = json.loads(self.lock_path.read_text(encoding="utf-8"))
            port = int(payload.get("port", 0))
            if port <= 0:
                return False
            with socket.create_connection(("127.0.0.1", port), timeout=0.35) as conn:
                conn.sendall(b"SHOW\n")
                reply = conn.recv(16)
                return reply.startswith(b"OK")
        except Exception:
            return False

    def acquire(self, on_show_callback: Any) -> None:
        self._on_show = on_show_callback
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.bind(("127.0.0.1", 0))
        srv.listen(4)
        srv.settimeout(0.4)
        self._sock = srv
        port = srv.getsockname()[1]

        lock_data = {"pid": os.getpid(), "port": port}
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        self.lock_path.write_text(json.dumps(lock_data), encoding="utf-8")

        def _serve() -> None:
            while not self._stop_event.is_set():
                try:
                    conn, _addr = srv.accept()
                except socket.timeout:
                    continue
                except OSError:
                    break
                with conn:
                    try:
                        data = conn.recv(64)
                        if data.startswith(b"SHOW") and self._on_show is not None:
                            self._on_show()
                        conn.sendall(b"OK\n")
                    except Exception:
                        pass

        self._thread = threading.Thread(target=_serve, daemon=True, name="qtp-ipc-guard")
        self._thread.start()
        atexit.register(self.release)

    def release(self) -> None:
        self._stop_event.set()
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None
        try:
            if self.lock_path.is_file():
                payload = json.loads(self.lock_path.read_text(encoding="utf-8"))
                if int(payload.get("port", -1)) == -1 or int(payload.get("pid", 0)) == os.getpid():
                    self.lock_path.unlink(missing_ok=True)
        except Exception:
            try:
                self.lock_path.unlink(missing_ok=True)
            except OSError:
                pass


def launch_gui(work_dir: Path) -> int:
    """Masaüstü uygulamasını (Overlay + Tray + Global Kısayollar) başlatır."""
    from PyQt6.QtCore import QObject, QUrl, pyqtSignal
    from PyQt6.QtGui import QDesktopServices
    from PyQt6.QtWidgets import (
        QApplication,
        QDialog,
        QHBoxLayout,
        QLabel,
        QListWidget,
        QMessageBox,
        QPushButton,
        QVBoxLayout,
    )
    from qtp_app.ui.help_dialog import HelpDialog
    from qtp_app.ui.overlay import OverlayWindow
    from qtp_app.ui.settings_window import SettingsWindow
    from qtp_app.ui.theme import build_dialog_stylesheet, resolve_palette
    from qtp_app.ui.tray import QtpTrayIcon

    config_dir, _portable = resolve_config_dir(work_dir)
    settings_path_guess = config_dir / "qtp_settings.json"
    first_run = not settings_path_guess.is_file()

    setup_logging(config_dir, level="info")
    logger = get_logger("main")
    settings, settings_path, corrupt_warn = load_settings(config_dir)
    setup_logging(config_dir, level=settings.get("log_level", "info"))

    guard = SingleInstanceGuard(config_dir)
    if guard.try_notify_existing():
        logger.info("QTP zaten çalışıyor; mevcut pencere gösterildi ve ikinci örnek kapatıldı.")
        return 0

    app = QApplication(sys.argv)
    app.setApplicationName(__app_name__)
    app.setApplicationVersion(__version__)
    app.setQuitOnLastWindowClosed(False)

    items, program_meta, extra_sections, ini_path = load_active_items(work_dir, settings)
    logger.info("Uygulama başlatıldı: %d hazır cevap yüklendi (%s).", len(items), ini_path)

    class UiBridge(QObject):
        hotkey_fired = pyqtSignal(str)
        show_ipc = pyqtSignal()

    bridge = UiBridge()

    def handle_paste(item: dict[str, Any], prev_app: Any) -> None:
        text = str(item.get("text", ""))
        has_end = str(item.get("terminator", "<E<N<D|")) == "<E<N<D|"
        res = paste_into_active_app(
            text,
            has_end_marker=has_end,
            enter_after_paste=bool(settings.get("enter_after_paste", True)),
            paste_method=str(settings.get("paste_method", "auto")),
            hide_overlay_cb=None,
            previous_app=prev_app,
        )
        logger.info(
            "Yapıştırıldı: kategori=%s anahtar=%s yöntem=%s enter=%s ok=%s",
            item.get("keys", ""),
            item.get("raw_key", item.get("id", "")),
            res.method,
            res.enter_sent,
            res.ok,
        )

    def handle_copy(item: dict[str, Any]) -> None:
        text = str(item.get("text", ""))
        ok = copy_to_clipboard(text)
        logger.info(
            "Panoya kopyalandı: kategori=%s anahtar=%s ok=%s",
            item.get("keys", ""),
            item.get("raw_key", item.get("id", "")),
            ok,
        )

    ws = settings.get("window_size") or [720, 520]
    overlay = OverlayWindow(
        items,
        theme=str(settings.get("theme", "dark")),
        window_size=(int(ws[0]), int(ws[1])),
        last_category=str(settings.get("last_category", "ALL")),
        last_category_by_hotkey=settings.get("last_category_by_hotkey") or {},
        ini_path=str(ini_path),
        on_paste=handle_paste,
        on_copy=handle_copy,
    )

    def persist_window_size(w: int, h: int) -> None:
        if settings.get("window_size") != [w, h]:
            settings["window_size"] = [w, h]
            try:
                save_settings(settings, settings_path)
            except Exception:
                pass

    overlay.window_resized.connect(persist_window_size)

    def current_palette() -> Any:
        return resolve_palette(str(settings.get("theme", "dark")), os_is_dark=True)

    def open_help() -> None:
        dlg = HelpDialog(current_palette(), parent=overlay if overlay.isVisible() else None)
        dlg.exec()

    hotkey_mgr = HotkeyManager()

    def register_all_hotkeys(*, prompt_macos: bool = False) -> None:
        hk_map = settings.get("hotkeys") or {}
        res = hotkey_mgr.register(
            hk_map,
            lambda cat: bridge.hotkey_fired.emit(cat),
            request_macos_permission=prompt_macos,
        )
        for cat, ok in res.items():
            if not ok:
                logger.warning("Global kısayol kaydedilemedi: %s -> %s", cat, hk_map.get(cat))

    def on_hotkey_gui(cat: str) -> None:
        if cat == "all":
            overlay.show_overlay(category=None, hotkey_key="all")
        else:
            overlay.show_overlay(category=cat, hotkey_key=cat)

    bridge.hotkey_fired.connect(on_hotkey_gui)
    bridge.show_ipc.connect(lambda: overlay.show_overlay(category="ALL", hotkey_key="all"))

    def open_settings() -> None:
        nonlocal items, program_meta, extra_sections, ini_path
        dlg = SettingsWindow(settings, current_palette(), parent=overlay if overlay.isVisible() else None)
        if dlg.exec() == dlg.DialogCode.Accepted and dlg.result_settings is not None:
            old_data_path = settings.get("data_path")
            settings.update(dlg.result_settings)
            settings["last_category_by_hotkey"] = overlay.last_category_by_hotkey
            save_settings(settings, settings_path)
            setup_logging(config_dir, level=settings.get("log_level", "info"))
            overlay.apply_settings(theme=settings["theme"], ini_path=str(resolve_data_path(settings, work_dir)))
            register_all_hotkeys(prompt_macos=False)
            tray.setVisible(bool(settings.get("tray_icon", True)))
            if settings.get("data_path") != old_data_path:
                items, program_meta, extra_sections, ini_path = load_active_items(work_dir, settings)
                overlay.set_items(items)
            logger.info("Ayarlar kullanıcı tarafından güncellendi.")
            overlay.show_toast("Ayarlar kaydedildi ✔")

    def reload_ini() -> None:
        nonlocal items, program_meta, extra_sections, ini_path
        items, program_meta, extra_sections, ini_path = load_active_items(work_dir, settings)
        overlay.set_items(items)
        logger.info("INI yeniden yüklendi: %d kayıt (%s).", len(items), ini_path)
        overlay.show_toast(f"INI yeniden yüklendi ({len(items)} kayıt) ✔")

    def open_data_json() -> None:
        json_path = work_dir / "data.json"
        if not json_path.is_file():
            save_data_json(json_path, items)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(json_path)))
        logger.info("data.json açıldı: %s", json_path)

    def open_backups() -> None:
        nonlocal items, program_meta, extra_sections
        pal = current_palette()
        dlg = QDialog(overlay if overlay.isVisible() else None)
        dlg.setWindowTitle("Yedekleme ve Geri Yükleme")
        dlg.resize(520, 400)
        dlg.setStyleSheet(build_dialog_stylesheet(pal))
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel(f"Yedek Klasörü: {work_dir / 'backups'}"))
        lst = QListWidget(dlg)
        lay.addWidget(lst, 1)

        def _refresh() -> None:
            lst.clear()
            for b in list_backups(work_dir):
                lst.addItem(f"{b.get('id')}  —  {b.get('count', 0)} kayıt ({b.get('reason', '')})")

        _refresh()
        btns = QHBoxLayout()
        btn_now = QPushButton("Anlık Yedek Al")
        btn_full = QPushButton("Tam Yedek Dışa Aktar")
        btn_restore = QPushButton("Seçileni Geri Yükle")
        btn_restore.setObjectName("PrimaryBtn")
        btn_close = QPushButton("Kapat")

        def _do_backup() -> None:
            if not (work_dir / "data.json").is_file():
                save_data_json(work_dir / "data.json", items)
            meta = create_backup(work_dir, reason="manual_tray", max_keep=int(settings.get("backup_count", 15)))
            _refresh()
            if meta:
                logger.info("Manuel yedek oluşturuldu: %s", meta["id"])

        def _do_full() -> None:
            out_path = write_full_backup_file(work_dir, items, settings=settings, program=program_meta, extra_sections=extra_sections)
            logger.info("Tam yedek dışa aktarıldı: %s", out_path)
            QMessageBox.information(dlg, "Tam Yedek", f"Tam yedek kaydedildi:\n{out_path}")

        def _do_restore() -> None:
            nonlocal items, program_meta, extra_sections
            cur = lst.currentItem()
            if not cur:
                return
            bid = cur.text().split("  —  ", 1)[0].strip()
            res = restore_backup(work_dir, bid)
            st = res["state"]
            items = st["items"]
            program_meta = st.get("program") or {}
            extra_sections = st.get("extraSections") or []
            overlay.set_items(items)
            logger.info("Yedek geri yüklendi: %s (%d kayıt)", bid, len(items))
            overlay.show_toast("Yedek geri yüklendi ✔")
            dlg.accept()

        btn_now.clicked.connect(_do_backup)
        btn_full.clicked.connect(_do_full)
        btn_restore.clicked.connect(_do_restore)
        btn_close.clicked.connect(dlg.accept)
        btns.addWidget(btn_now)
        btns.addWidget(btn_full)
        btns.addWidget(btn_restore)
        btns.addStretch()
        btns.addWidget(btn_close)
        lay.addLayout(btns)
        dlg.exec()

    def quit_app() -> None:
        settings["last_category"] = overlay.active_category
        settings["last_category_by_hotkey"] = overlay.last_category_by_hotkey
        try:
            save_settings(settings, settings_path)
        except Exception:
            pass
        hotkey_mgr.unregister()
        guard.release()
        logger.info("QTP kapatıldı.")
        app.quit()

    overlay.settings_requested.connect(open_settings)
    overlay.help_requested.connect(open_help)

    tray = QtpTrayIcon(
        on_open=lambda: overlay.show_overlay(category="ALL", hotkey_key="all"),
        on_settings=open_settings,
        on_reload_ini=reload_ini,
        on_open_json=open_data_json,
        on_backups=open_backups,
        on_help=open_help,
        on_quit=quit_app,
    )
    tray.setVisible(bool(settings.get("tray_icon", True)))

    guard.acquire(lambda: bridge.show_ipc.emit())
    register_all_hotkeys(prompt_macos=True)

    app.aboutToQuit.connect(guard.release)

    if not settings.get("start_minimized", False):
        overlay.show_overlay(category="ALL", hotkey_key="all")
        overlay.show_toast("QTP hazır. Win+Z / Win+A / Win+X / Win+Q", duration_ms=2600)
    elif first_run and tray.isVisible():
        tray.showMessage("QTP", "QTP hazır. Win+Z / Win+A / Win+X / Win+Q")

    if corrupt_warn:
        overlay.show_toast("Bozuk ayar dosyası varsayılanlarla yenilendi", duration_ms=2400)

    return app.exec()


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False, prog="qtp")
    parser.add_argument("-h", "--help", action="store_true", dest="show_help")
    parser.add_argument("--version", action="store_true")
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--export-ini", metavar="YOL")
    parser.add_argument("--import-ini", metavar="YOL")
    parser.add_argument("--work-dir", metavar="DIZIN")
    return parser


def main(argv: list[str] | None = None) -> int:
    _configure_stdio()
    parser = build_arg_parser()
    args, unknown = parser.parse_known_args(argv)
    if unknown:
        print(f"HATA: Bilinmeyen komut satırı seçeneği: {' '.join(unknown)}", file=sys.stderr)
        print(format_help_text(), file=sys.stderr)
        return 2

    work_dir = Path(args.work_dir).resolve() if args.work_dir else get_app_dir()

    if args.show_help:
        print(format_help_text())
        return 0

    if args.version:
        print(format_version_output())
        return 0

    if args.selftest:
        ok, msg = run_selftest(work_dir)
        print(msg, file=sys.stdout if ok else sys.stderr)
        return 0 if ok else 1

    if args.export_ini:
        ok, msg = export_ini_cli(Path(args.export_ini), work_dir)
        print(msg, file=sys.stdout if ok else sys.stderr)
        return 0 if ok else 1

    if args.import_ini:
        ok, msg = import_ini_cli(Path(args.import_ini), work_dir)
        print(msg, file=sys.stdout if ok else sys.stderr)
        return 0 if ok else 1

    return launch_gui(work_dir)


if __name__ == "__main__":
    raise SystemExit(main())
