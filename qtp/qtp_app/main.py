"""QTP — QuickTextPaste / Hazır Cevaplar tek dosya masaüstü uygulaması giriş noktası ve GUI adaptörü."""

from __future__ import annotations

import atexit
import json
import os
import socket
import sys
import threading
from pathlib import Path
from typing import Any

from qtp_app import __app_name__, __version__
from qtp_app.core.engine import FIRST_RUN_TOAST, QtpEngine
from qtp_app.core.hotkeys import HotkeyManager
from qtp_app.core.logging_setup import get_logger
from qtp_app.core.settings import save_settings

LOCK_FILENAME = "qtp.lock"


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


def launch_gui(engine: QtpEngine) -> int:
    """GUI adaptörü: Overlay + Tray + Global Kısayollar, tüm işlemleri QtpEngine üzerinden yürütür."""
    logger = get_logger("main")
    try:
        from PyQt6.QtCore import QObject, QUrl, pyqtSignal
        from PyQt6.QtGui import QDesktopServices
        from PyQt6.QtWidgets import (
            QApplication,
            QDialog,
            QFileDialog,
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
    except ImportError as exc:
        msg = (
            "HATA: GUI modu PyQt6 gerektirir; bu sistemde PyQt6 yüklenemedi "
            f"({exc}). Başsız veya eski sistemlerde '--tui', '--cli' ya da '--web' modunu kullanın."
        )
        logger.error(msg)
        print(msg, file=sys.stderr)
        return 1

    guard = SingleInstanceGuard(engine.config_dir)
    if guard.try_notify_existing():
        logger.info("QTP zaten çalışıyor; mevcut pencere gösterildi ve ikinci örnek kapatıldı.")
        return 0

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(__app_name__)
    app.setApplicationVersion(__version__)
    app.setQuitOnLastWindowClosed(False)

    logger.info("Uygulama başlatıldı: %d hazır cevap yüklendi (%s).", len(engine.items), engine.ini_path)

    class UiBridge(QObject):
        hotkey_fired = pyqtSignal(str)
        show_ipc = pyqtSignal()

    bridge = UiBridge()

    def handle_paste(item: dict[str, Any], prev_app: Any) -> Any:
        target = str(item.get("raw_key") or item.get("text") or "")
        return engine.op_paste(target, previous_app=prev_app)

    def handle_copy(item: dict[str, Any]) -> Any:
        target = str(item.get("raw_key") or item.get("text") or "")
        return engine.op_copy(target)

    ws = engine.settings.get("window_size") or [720, 520]
    overlay = OverlayWindow(
        engine.items,
        theme=str(engine.settings.get("theme", "dark")),
        window_size=(int(ws[0]), int(ws[1])),
        last_category=str(engine.settings.get("last_category", "ALL")),
        last_category_by_hotkey=engine.settings.get("last_category_by_hotkey") or {},
        ini_path=str(engine.ini_path),
        on_paste=handle_paste,
        on_copy=handle_copy,
    )

    def persist_window_size(w: int, h: int) -> None:
        if engine.settings.get("window_size") != [w, h]:
            engine.settings["window_size"] = [w, h]
            try:
                save_settings(engine.settings, engine.settings_path)
            except Exception:
                pass

    overlay.window_resized.connect(persist_window_size)

    def current_palette() -> Any:
        return resolve_palette(str(engine.settings.get("theme", "dark")), os_is_dark=True)

    def open_help() -> None:
        dlg = HelpDialog(current_palette(), parent=overlay if overlay.isVisible() else None)
        dlg.exec()

    hotkey_mgr = HotkeyManager()

    def register_all_hotkeys() -> None:
        hk_map = engine.settings.get("hotkeys") or {}
        res = hotkey_mgr.register(
            hk_map,
            lambda cat: bridge.hotkey_fired.emit(cat),
            request_macos_permission=False,
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
        dlg = SettingsWindow(engine.settings, current_palette(), parent=overlay if overlay.isVisible() else None)
        if dlg.exec() == dlg.DialogCode.Accepted and dlg.result_settings is not None:
            old_data_path = engine.settings.get("data_path")
            engine.settings.update(dlg.result_settings)
            engine.settings["last_category_by_hotkey"] = overlay.last_category_by_hotkey
            save_settings(engine.settings, engine.settings_path)
            overlay.apply_settings(theme=engine.settings["theme"], ini_path=str(engine.ini_path))
            register_all_hotkeys()
            tray.setVisible(bool(engine.settings.get("tray_icon", True)))
            if engine.settings.get("data_path") != old_data_path:
                engine.reload_data()
                overlay.set_items(engine.items)
            logger.info("Ayarlar kullanıcı tarafından güncellendi.")
            overlay.show_toast("Ayarlar kaydedildi ✔")

    def reload_ini() -> None:
        res = engine.reload_data()
        overlay.set_items(engine.items)
        overlay.show_toast(res.message if not res.ok else f"INI yeniden yüklendi ({len(engine.items)} kayıt) ✔")

    def open_data_json() -> None:
        json_path = engine.work_dir / "data.json"
        if not json_path.is_file():
            from qtp_app.core.json_store import save_data_json

            save_data_json(json_path, engine.items)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(json_path)))
        logger.info("data.json açıldı: %s", json_path)

    def open_backups() -> None:
        pal = current_palette()
        dlg = QDialog(overlay if overlay.isVisible() else None)
        dlg.setWindowTitle("Yedekleme ve Geri Yükleme")
        dlg.resize(520, 400)
        dlg.setStyleSheet(build_dialog_stylesheet(pal))
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel(f"Yedek Klasörü: {engine.work_dir / 'backups'}"))
        lst = QListWidget(dlg)
        lay.addWidget(lst, 1)

        def _refresh() -> None:
            lst.clear()
            for b in engine.op_list_backups().data["backups"]:
                lst.addItem(f"{b.get('id')}  —  {b.get('count', 0)} kayıt ({b.get('reason', '')})")

        _refresh()
        btns = QHBoxLayout()
        btn_now = QPushButton("Anlık Yedek Al")
        btn_full = QPushButton("Tam Yedek Dışa Aktar")
        btn_exp_ini = QPushButton("INI Dışa Aktar…")
        btn_imp_ini = QPushButton("INI İçe Aktar…")
        btn_restore = QPushButton("Seçileni Geri Yükle")
        btn_restore.setObjectName("PrimaryBtn")
        btn_close = QPushButton("Kapat")

        def _do_backup() -> None:
            engine.op_backup()
            _refresh()

        def _do_full() -> None:
            res = engine.op_export_backup(engine.work_dir)
            QMessageBox.information(dlg, "Tam Yedek", res.message)

        def _do_export_ini() -> None:
            path, _ = QFileDialog.getSaveFileName(
                dlg,
                "QuickTextPaste.ini Dışa Aktar",
                str(engine.work_dir / "QuickTextPaste_export.ini"),
                "INI Dosyaları (*.ini);;Tüm Dosyalar (*.*)",
            )
            if path:
                res = engine.op_export_ini(path)
                QMessageBox.information(dlg, "INI Dışa Aktar", res.message)

        def _do_import_ini() -> None:
            path, _ = QFileDialog.getOpenFileName(
                dlg,
                "QuickTextPaste.ini İçe Aktar",
                str(engine.work_dir),
                "INI Dosyaları (*.ini);;Tüm Dosyalar (*.*)",
            )
            if path:
                res = engine.op_import_ini(path, mode="merge")
                overlay.set_items(engine.items)
                _refresh()
                QMessageBox.information(dlg, "INI İçe Aktar", res.message)

        def _do_restore() -> None:
            cur = lst.currentItem()
            if not cur:
                return
            bid = cur.text().split("  —  ", 1)[0].strip()
            res = engine.op_restore(bid)
            overlay.set_items(engine.items)
            overlay.show_toast(res.message)
            dlg.accept()

        btn_now.clicked.connect(_do_backup)
        btn_full.clicked.connect(_do_full)
        btn_exp_ini.clicked.connect(_do_export_ini)
        btn_imp_ini.clicked.connect(_do_import_ini)
        btn_restore.clicked.connect(_do_restore)
        btn_close.clicked.connect(dlg.accept)
        btns.addWidget(btn_now)
        btns.addWidget(btn_full)
        btns.addWidget(btn_exp_ini)
        btns.addWidget(btn_imp_ini)
        btns.addWidget(btn_restore)
        btns.addStretch()
        btns.addWidget(btn_close)
        lay.addLayout(btns)
        dlg.exec()

    def quit_app() -> None:
        engine.settings["last_category"] = overlay.active_category
        engine.settings["last_category_by_hotkey"] = overlay.last_category_by_hotkey
        try:
            save_settings(engine.settings, engine.settings_path)
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
    tray.setVisible(bool(engine.settings.get("tray_icon", True)))

    guard.acquire(lambda: bridge.show_ipc.emit())
    register_all_hotkeys()

    app.aboutToQuit.connect(guard.release)

    if not engine.settings.get("start_minimized", False):
        overlay.show_overlay(category="ALL", hotkey_key="all")
        overlay.show_toast(FIRST_RUN_TOAST, duration_ms=2600)
    elif engine.first_run and tray.isVisible():
        tray.showMessage("QTP", FIRST_RUN_TOAST)

    if engine.settings_warning:
        overlay.show_toast("Bozuk ayar dosyası varsayılanlarla yenilendi", duration_ms=2400)

    return app.exec()


def main(argv: list[str] | None = None) -> int:
    from qtp_app.cli import run

    return run(argv)


if __name__ == "__main__":
    raise SystemExit(main())
