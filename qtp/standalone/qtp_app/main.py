"""QTP — QuickTextPaste / Hazır Cevaplar tek dosya masaüstü uygulaması giriş noktası ve GUI adaptörü."""

from __future__ import annotations

import atexit
import json
import os
import signal
import socket
import sys
import threading
from pathlib import Path
from typing import Any, Callable

from qtp_app import __app_name__, __version__
from qtp_app.core.engine import QtpEngine, format_hotkeys_toast
from qtp_app.core.hotkeys import HotkeyManager
from qtp_app.core.logging_setup import get_logger
from qtp_app.core.watcher import ReloadEvent

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
                token = os.environ.get("XDG_ACTIVATION_TOKEN", "").strip()
                msg = json.dumps({"cmd": "SHOW", "activation_token": token}).encode("utf-8") + b"\n"
                conn.sendall(msg)
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
                        data = conn.recv(4096)
                        raw = data.decode("utf-8", errors="ignore").strip()
                        token = ""
                        show_cmd = False
                        if raw.startswith("{"):
                            try:
                                parsed = json.loads(raw)
                                if isinstance(parsed, dict) and str(parsed.get("cmd", "")).upper() == "SHOW":
                                    show_cmd = True
                                    token = str(parsed.get("activation_token") or "").strip()
                            except ValueError:
                                show_cmd = False
                        elif raw.startswith("SHOW"):
                            show_cmd = True
                        if show_cmd and self._on_show is not None:
                            try:
                                self._on_show(token)
                            except TypeError:
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


def apply_reload_event_gui(
    event: ReloadEvent,
    engine: QtpEngine,
    overlay: Any,
    tray: Any,
    register_hotkeys_fn: Callable[[], dict[str, str]],
) -> None:
    """Canlı dosya değişikliği olayını GUI katmanı, tepsi ve global kısayollara uygular."""
    get_logger("main").info(
        "GUI canlı yenileme: öğe_değişti=%s ayar_değişti=%s kısayol_değişti=%s",
        event.items_changed,
        event.settings_changed,
        event.hotkeys_changed,
    )
    if event.warning:
        overlay.show_toast(event.warning, duration_ms=3200)
        return

    if event.items_changed:
        overlay.set_items(engine.items)
        overlay.show_toast(
            f"Hazır cevaplar otomatik yenilendi ({len(engine.items)} kayıt) ✔",
            duration_ms=2200,
        )

    if event.theme_changed or event.data_path_changed or event.settings_changed:
        overlay.apply_settings(
            theme=engine.settings["theme"],
            ini_path=str(engine.ini_path),
            view_mode=engine.settings.get("view_mode", "list"),
            strip_emoji=bool(engine.settings.get("strip_emoji", False)),
            sort_by=engine.settings.get("sort_by", "order"),
            hide_on_blur=bool(engine.settings.get("hide_on_blur", True)),
        )
        if event.theme_changed and hasattr(tray, "apply_palette") and hasattr(overlay, "_palette"):
            tray.apply_palette(overlay._palette)

    if event.window_size_changed:
        ws = engine.settings.get("window_size") or [720, 520]
        overlay.resize(int(ws[0]), int(ws[1]))

    if event.tray_changed:
        tray.setVisible(bool(engine.settings.get("tray_icon", True)))

    if event.hotkeys_changed:
        conflicts = register_hotkeys_fn()
        open_hk = str((engine.settings.get("hotkeys") or {}).get("all", ""))
        tray.update_hotkeys_label(open_hk)
        if conflicts:
            conflict_keys = ", ".join(f"{k} ({engine.settings.get('hotkeys', {}).get(k, '')})" for k in conflicts)
            overlay.show_toast(
                f"Kısayol çakışması: {conflict_keys} — Ayarlar → Global Kısayollar'dan değiştirin",
                duration_ms=3600,
            )
        elif not event.items_changed:
            overlay.show_toast("Ayarlar ve kısayollar otomatik güncellendi ✔", duration_ms=2200)
    elif event.settings_changed and not event.items_changed:
        overlay.show_toast("Ayarlar otomatik yenilendi ✔", duration_ms=2000)


def create_resize_persister(
    engine: QtpEngine,
    overlay: Any,
    *,
    delay_ms: int = 400,
) -> tuple[Callable[[int, int], None], Callable[[], None], Any]:
    """Pencere yeniden boyutlandırma kayıtlarını 400 ms gecikmeyle tek seferde diske yazar."""
    from PyQt6.QtCore import QTimer

    timer = QTimer(overlay)
    timer.setSingleShot(True)
    timer.setInterval(delay_ms)
    pending: list[int] = [0, 0]

    def _flush() -> None:
        w, h = pending[0], pending[1]
        if w <= 0 or h <= 0 or overlay.isMaximized():
            return
        if engine.settings.get("window_size") != [w, h]:
            engine.settings["window_size"] = [w, h]
            try:
                engine.save_current_settings(engine.settings)
            except Exception:
                pass

    def _on_resized(w: int, h: int) -> None:
        if overlay.isMaximized() or not overlay.isVisible():
            return
        pending[0] = int(w)
        pending[1] = int(h)
        timer.start()

    timer.timeout.connect(_flush)
    return _on_resized, _flush, timer


def build_backups_dialog(
    engine: QtpEngine,
    palette: Any,
    *,
    on_restored: Callable[[Any], None] | None = None,
    on_imported: Callable[[Any], None] | None = None,
    parent: Any = None,
) -> Any:
    """Esnek düzenlenmiş yedekleme, INI/Tam Yedek dışa/içe aktarma ve geri yükleme penceresi."""
    from PyQt6.QtWidgets import QDialog, QFileDialog, QLabel, QListWidget, QMessageBox, QPushButton, QVBoxLayout
    from qtp_app.ui.flow_layout import FlowLayout
    from qtp_app.ui.theme import build_dialog_stylesheet, build_qpalette

    dlg = QDialog(parent)
    dlg.setWindowTitle("Yedekleme ve Geri Yükleme")
    dlg.setMinimumSize(480, 360)
    dlg.resize(560, 420)
    dlg.setPalette(build_qpalette(palette))
    dlg.setStyleSheet(build_dialog_stylesheet(palette))

    lay = QVBoxLayout(dlg)
    lay.setContentsMargins(16, 16, 16, 16)
    lay.setSpacing(10)

    dir_label = QLabel(f"Yedek Klasörü: {engine.work_dir / 'backups'}", dlg)
    dir_label.setWordWrap(True)
    lay.addWidget(dir_label)

    lst = QListWidget(dlg)
    lay.addWidget(lst, 1)

    def _refresh() -> None:
        lst.clear()
        for b in engine.op_list_backups().data["backups"]:
            lst.addItem(f"{b.get('id')}  —  {b.get('count', 0)} kayıt ({b.get('reason', '')})")

    _refresh()
    btns = FlowLayout(margin=0, spacing=6)
    btn_now = QPushButton("Anlık Yedek Al", dlg)
    btn_full = QPushButton("Tam Yedek Dışa Aktar", dlg)
    btn_exp_ini = QPushButton("INI Dışa Aktar…", dlg)
    btn_imp_ini = QPushButton("INI İçe Aktar…", dlg)
    btn_restore = QPushButton("Seçileni Geri Yükle", dlg)
    btn_restore.setObjectName("PrimaryBtn")
    btn_close = QPushButton("Kapat", dlg)

    def _do_backup() -> None:
        engine.op_backup()
        _refresh()

    def _do_full() -> None:
        path, _ = QFileDialog.getSaveFileName(
            dlg,
            "Tam Yedek Dışa Aktar",
            str(engine.work_dir / "qtp-tam-yedek.json"),
            "JSON Dosyaları (*.json);;Tüm Dosyalar (*.*)",
        )
        if path:
            res = engine.op_export_backup(path)
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
            if on_imported is not None:
                on_imported(res)
            _refresh()
            QMessageBox.information(dlg, "INI İçe Aktar", res.message)

    def _do_restore() -> None:
        cur = lst.currentItem()
        if not cur:
            return
        bid = cur.text().split("  —  ", 1)[0].strip()
        res = engine.op_restore(bid)
        if on_restored is not None:
            on_restored(res)
        dlg.accept()

    btn_now.clicked.connect(_do_backup)
    btn_full.clicked.connect(_do_full)
    btn_exp_ini.clicked.connect(_do_export_ini)
    btn_imp_ini.clicked.connect(_do_import_ini)
    btn_restore.clicked.connect(_do_restore)
    btn_close.clicked.connect(dlg.accept)
    for btn in (btn_now, btn_full, btn_exp_ini, btn_imp_ini, btn_restore, btn_close):
        btns.addWidget(btn)
    lay.addLayout(btns)
    return dlg


def launch_gui(
    engine: QtpEngine,
    *,
    verbose: int = 0,
    quiet: bool = False,
    initial_category: str | None = None,
    initial_query: str = "",
) -> int:
    """GUI adaptörü: Overlay + Tray + Global Kısayollar, tüm işlemleri QtpEngine üzerinden yürütür."""
    eff_verbose = max(int(verbose or 0), int(getattr(engine, "verbose", 0) or 0))
    eff_quiet = bool(quiet) and eff_verbose <= 0
    if eff_verbose > 0:
        engine.configure_verbosity(eff_verbose, eff_quiet)
        engine.emit_startup_diagnostics("gui")

    logger = get_logger("main")
    try:
        from PyQt6.QtCore import QObject, Qt, QTimer, QUrl, pyqtSignal
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
            QSystemTrayIcon,
            QVBoxLayout,
        )
        from qtp_app.ui.help_dialog import HelpDialog
        from qtp_app.ui.overlay import OverlayWindow
        from qtp_app.ui.settings_window import SettingsWindow
        from qtp_app.ui.theme import build_dialog_stylesheet, build_qpalette, resolve_palette
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
        show_ipc = pyqtSignal(str)
        file_reloaded = pyqtSignal(object)

    bridge = UiBridge()

    tray_ref: list[QtpTrayIcon] = []

    def notify(msg: str, *, duration_ms: int = 3500, warning: bool = False) -> None:
        if overlay.isVisible():
            overlay.show_toast(msg, duration_ms=duration_ms)
            return
        if tray_ref and tray_ref[0].isVisible():
            icon_kind = QSystemTrayIcon.MessageIcon.Warning if warning else QSystemTrayIcon.MessageIcon.Information
            tray_ref[0].showMessage("QTP", msg, icon_kind, duration_ms)
            return
        overlay.show_overlay(category="ALL", hotkey_key="all", force_category=True, animate=False)
        overlay.show_toast(msg, duration_ms=duration_ms)

    def _sync_overlay_after_mutation(res: Any) -> Any:
        if getattr(res, "ok", False):
            overlay.set_items(engine.items)
        overlay.set_history_state(bool(engine._undo_stack), bool(engine._redo_stack))
        return res

    def handle_paste(item: dict[str, Any], prev_app: Any) -> Any:
        target = str(item.get("raw_key") or item.get("text") or "")
        pre_copied = overlay.consume_pre_copied()
        res = engine.op_paste(target, previous_app=prev_app, already_copied=pre_copied)
        paste_data = (res.data or {}).get("paste_result", {}) if hasattr(res, "data") and res.data else {}
        if not res.ok or bool(paste_data.get("warning")):
            notify(res.message, duration_ms=4000, warning=True)
        return res

    def handle_copy(item: dict[str, Any]) -> Any:
        target = str(item.get("raw_key") or item.get("text") or "")
        res = engine.op_copy(target)
        if not res.ok:
            notify(res.message, duration_ms=4000, warning=True)
        return res

    def handle_add(payload: dict[str, Any]) -> Any:
        res = engine.op_add_item(
            str(payload.get("text", "")),
            keys=str(payload.get("keys", "")),
            group=str(payload.get("group", "Genel")),
            label=str(payload.get("label", "")),
            terminator=str(payload.get("terminator", "<E<N<D|")),
            favorite=bool(payload.get("favorite", False)),
        )
        return _sync_overlay_after_mutation(res)

    def handle_edit(item: dict[str, Any], payload: dict[str, Any]) -> Any:
        target = str(item.get("raw_key") or item.get("text") or "")
        res = engine.op_update_item(
            target,
            keys=payload.get("keys"),
            group=payload.get("group"),
            label=payload.get("label"),
            text=payload.get("text"),
            terminator=payload.get("terminator"),
            favorite=payload.get("favorite") if "favorite" in payload else None,
        )
        return _sync_overlay_after_mutation(res)

    def handle_delete(item: dict[str, Any]) -> Any:
        target = str(item.get("raw_key") or item.get("text") or "")
        return _sync_overlay_after_mutation(engine.op_delete_item(target))

    def handle_theme_change(new_theme: str) -> None:
        engine.op_set_setting("theme", new_theme)

    def handle_save_all() -> Any:
        return _sync_overlay_after_mutation(engine.op_save_all())

    def handle_duplicate(item: dict[str, Any]) -> Any:
        target = str(item.get("raw_key") or item.get("text") or "")
        return _sync_overlay_after_mutation(engine.op_duplicate_item(target))

    def handle_move(item: dict[str, Any], direction: str) -> Any:
        target = str(item.get("raw_key") or item.get("text") or "")
        return _sync_overlay_after_mutation(engine.op_move_item(target, direction=direction))

    def handle_toggle_favorite(item: dict[str, Any]) -> Any:
        target = str(item.get("raw_key") or item.get("text") or "")
        return _sync_overlay_after_mutation(engine.op_toggle_favorite(target))

    def handle_bulk_edit(targets: list[str], payload: dict[str, Any]) -> Any:
        res = engine.op_bulk_edit(
            targets,
            keys=payload.get("keys"),
            group=payload.get("group"),
            find=payload.get("find"),
            replace=str(payload.get("replace", "") or ""),
            ignore_case=bool(payload.get("ignore_case", False)),
            prefix=str(payload.get("prefix", "") or ""),
            suffix=str(payload.get("suffix", "") or ""),
            strip_emojis=bool(payload.get("strip_emojis", False)),
            add_emoji=str(payload.get("add_emoji", "") or ""),
            favorite_action=str(payload.get("favorite_action", "keep") or "keep"),
        )
        return _sync_overlay_after_mutation(res)

    def handle_bulk_delete(targets: list[str]) -> Any:
        return _sync_overlay_after_mutation(engine.op_bulk_delete(targets))

    def handle_rename_group(old_g: str, new_g: str) -> Any:
        return _sync_overlay_after_mutation(engine.op_rename_group(old_g, new_g))

    def handle_delete_group(grp_name: str) -> Any:
        return _sync_overlay_after_mutation(engine.op_delete_group(grp_name))

    def handle_export_group(grp_name: str) -> Any:
        keys = [
            str(it.get("raw_key", ""))
            for it in engine.items
            if (str(it.get("group") or "Genel").strip() or "Genel") == grp_name
        ]
        overlay.set_modal_child_open(True)
        try:
            path, _ = QFileDialog.getSaveFileName(
                overlay if overlay.isVisible() else None,
                f"Grubu Dışa Aktar ({grp_name})",
                str(engine.work_dir / f"qtp-grup-{grp_name}.ini"),
                "INI Dosyaları (*.ini);;Tüm Dosyalar (*.*)",
            )
        finally:
            overlay.set_modal_child_open(False)
        if not path:
            return None
        res = engine.op_export_ini(path, raw_keys=keys)
        overlay.show_toast(res.message)
        return res

    def handle_undo() -> Any:
        return _sync_overlay_after_mutation(engine.op_undo())

    def handle_redo() -> Any:
        return _sync_overlay_after_mutation(engine.op_redo())

    def handle_setting_change(key: str, value: Any) -> Any:
        return engine.op_set_setting(key, value)

    effective_cat = (initial_category or "ALL").strip().upper() or "ALL"
    ws = engine.settings.get("window_size") or [720, 520]
    overlay = OverlayWindow(
        engine.items,
        theme=str(engine.settings.get("theme", "light")),
        view_mode=str(engine.settings.get("view_mode", "list")),
        strip_emoji=bool(engine.settings.get("strip_emoji", False)),
        sort_by=str(engine.settings.get("sort_by", "order")),
        hide_on_blur=bool(engine.settings.get("hide_on_blur", True)),
        can_undo=bool(engine._undo_stack),
        can_redo=bool(engine._redo_stack),
        window_size=(int(ws[0]), int(ws[1])),
        last_category=effective_cat,
        last_category_by_hotkey=engine.settings.get("last_category_by_hotkey") or {},
        initial_query=initial_query,
        ini_path=str(engine.ini_path),
        on_paste=handle_paste,
        on_copy=handle_copy,
        on_add=handle_add,
        on_edit=handle_edit,
        on_delete=handle_delete,
        on_theme_change=handle_theme_change,
        on_save_all=handle_save_all,
        on_duplicate=handle_duplicate,
        on_move=handle_move,
        on_toggle_favorite=handle_toggle_favorite,
        on_bulk_edit=handle_bulk_edit,
        on_bulk_delete=handle_bulk_delete,
        on_rename_group=handle_rename_group,
        on_delete_group=handle_delete_group,
        on_export_group=handle_export_group,
        on_undo=handle_undo,
        on_redo=handle_redo,
        on_setting_change=handle_setting_change,
    )
    logger.info(
        "GUI başlatılıyor (platform=%s, tema=%s, yazı_tipi=%s, ilk_kategori=%s, ilk_sorgu=%r).",
        app.platformName(),
        engine.settings.get("theme", "light"),
        overlay._font_family,
        overlay.active_category,
        initial_query,
    )

    on_window_resized, flush_window_size, _resize_timer = create_resize_persister(engine, overlay, delay_ms=400)
    overlay.window_resized.connect(on_window_resized)

    def current_palette() -> Any:
        return resolve_palette(str(engine.settings.get("theme", "light")), os_is_dark=overlay._detect_os_dark())

    app.setPalette(build_qpalette(current_palette()))

    def open_help() -> None:
        overlay.set_modal_child_open(True)
        try:
            dlg = HelpDialog(current_palette(), parent=overlay if overlay.isVisible() else None)
            dlg.exec()
        finally:
            overlay.set_modal_child_open(False)

    hotkey_mgr = HotkeyManager()

    def register_all_hotkeys() -> dict[str, str]:
        hk_map = engine.settings.get("hotkeys") or {}
        res = hotkey_mgr.register(
            hk_map,
            lambda cat: bridge.hotkey_fired.emit(cat),
            request_macos_permission=False,
        )
        for cat, ok in res.items():
            if not ok and cat not in hotkey_mgr.conflicts:
                logger.warning("Global kısayol kaydedilemedi: %s -> %s", cat, hk_map.get(cat))
        return hotkey_mgr.conflicts

    def on_hotkey_gui(cat: str) -> None:
        if cat == "all":
            overlay.show_overlay(category="ALL", hotkey_key="all", force_category=True)
        else:
            overlay.show_overlay(category=cat, hotkey_key=cat, force_category=True)

    def on_show_ipc(token: str = "") -> None:
        clean_tok = str(token or "").strip()
        if clean_tok:
            os.environ["XDG_ACTIVATION_TOKEN"] = clean_tok
        overlay.show_overlay(category="ALL", hotkey_key="all", force_category=True)

    bridge.hotkey_fired.connect(on_hotkey_gui)
    bridge.show_ipc.connect(on_show_ipc)

    def open_settings() -> None:
        overlay.set_modal_child_open(True)
        try:
            dlg = SettingsWindow(engine.settings, current_palette(), parent=overlay if overlay.isVisible() else None)
            accepted = dlg.exec() == dlg.DialogCode.Accepted and dlg.result_settings is not None
        finally:
            overlay.set_modal_child_open(False)
        if accepted and dlg.result_settings is not None:
            old_data_path = engine.settings.get("data_path")
            merged = dict(dlg.result_settings)
            merged["last_category_by_hotkey"] = overlay.last_category_by_hotkey
            engine.save_current_settings(merged)
            overlay.apply_settings(
                theme=engine.settings["theme"],
                ini_path=str(engine.ini_path),
                view_mode=engine.settings.get("view_mode", "list"),
                strip_emoji=bool(engine.settings.get("strip_emoji", False)),
                sort_by=engine.settings.get("sort_by", "order"),
                hide_on_blur=bool(engine.settings.get("hide_on_blur", True)),
            )
            tray.apply_palette(current_palette())
            ws_new = engine.settings.get("window_size") or [720, 520]
            overlay.resize(int(ws_new[0]), int(ws_new[1]))
            conflicts = register_all_hotkeys()
            open_hk = str((engine.settings.get("hotkeys") or {}).get("all", ""))
            tray.update_hotkeys_label(open_hk)
            tray.setVisible(bool(engine.settings.get("tray_icon", True)))
            if engine.settings.get("data_path") != old_data_path:
                engine.reload_data()
                overlay.set_items(engine.items)
            logger.info("Ayarlar kullanıcı tarafından güncellendi.")
            if conflicts:
                ckeys = ", ".join(f"{k} ({engine.settings.get('hotkeys', {}).get(k, '')})" for k in conflicts)
                overlay.show_toast(
                    f"Kısayol çakışması: {ckeys} — Ayarlar → Global Kısayollar",
                    duration_ms=3200,
                )
            else:
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
        overlay.set_modal_child_open(True)
        try:
            dlg = build_backups_dialog(
                engine,
                pal,
                on_restored=lambda res: (overlay.set_items(engine.items), overlay.show_toast(res.message)),
                on_imported=lambda _res: overlay.set_items(engine.items),
                parent=overlay if overlay.isVisible() else None,
            )
            dlg.exec()
        finally:
            overlay.set_modal_child_open(False)

    lifecycle_state = {"quitting": False, "cleaned": False}

    def _cleanup() -> None:
        if lifecycle_state["cleaned"]:
            return
        lifecycle_state["cleaned"] = True
        engine.stop_watcher()
        hotkey_mgr.unregister()
        guard.release()

    def quit_app() -> None:
        if lifecycle_state["quitting"]:
            return
        lifecycle_state["quitting"] = True
        flush_window_size()
        engine.settings["last_category"] = overlay.active_category
        engine.settings["last_category_by_hotkey"] = overlay.last_category_by_hotkey
        try:
            engine.save_current_settings(engine.settings)
        except Exception:
            pass
        _cleanup()
        logger.info("QTP kapatıldı.")
        app.quit()

    overlay.settings_requested.connect(open_settings)
    overlay.help_requested.connect(open_help)

    def toggle_overlay_visibility() -> None:
        if overlay.isVisible():
            overlay.hide_overlay()
        else:
            overlay.show_overlay(category="ALL", hotkey_key="all", force_category=True)

    open_hk = str((engine.settings.get("hotkeys") or {}).get("all", ""))
    tray = QtpTrayIcon(
        on_open=lambda: overlay.show_overlay(category="ALL", hotkey_key="all", force_category=True),
        on_toggle=toggle_overlay_visibility,
        on_settings=open_settings,
        on_reload_ini=reload_ini,
        on_open_json=open_data_json,
        on_backups=open_backups,
        on_help=open_help,
        on_quit=quit_app,
        open_hotkey=open_hk,
        palette=current_palette(),
    )
    tray_ref.append(tray)
    overlay.theme_toggle_requested.connect(lambda _t: tray.apply_palette(current_palette()))
    tray.setVisible(bool(engine.settings.get("tray_icon", True)))

    bridge.file_reloaded.connect(
        lambda ev: apply_reload_event_gui(ev, engine, overlay, tray, register_all_hotkeys),
        Qt.ConnectionType.QueuedConnection,
    )
    engine.start_watcher(on_reload=lambda ev: bridge.file_reloaded.emit(ev))

    guard.acquire(lambda tok="": bridge.show_ipc.emit(tok))
    conflicts = register_all_hotkeys()

    app.aboutToQuit.connect(_cleanup)

    toast_msg = format_hotkeys_toast(engine.settings.get("hotkeys"))
    if not engine.settings.get("start_minimized", False):
        overlay.show_overlay(
            category=initial_category or "ALL",
            hotkey_key="all",
            query=initial_query if initial_query else "",
            force_category=True,
        )
        if not eff_quiet:
            overlay.show_toast(toast_msg, duration_ms=2600)
    elif engine.first_run and tray.isVisible() and not eff_quiet:
        tray.showMessage("QTP", toast_msg)

    if getattr(engine, "startup_warning", None):
        notify(str(engine.startup_warning), duration_ms=4000, warning=True)
    elif engine.settings_warning:
        notify("Bozuk ayar dosyası varsayılanlarla yenilendi", duration_ms=2400, warning=True)
    elif conflicts:
        ckeys = ", ".join(f"{k} ({engine.settings.get('hotkeys', {}).get(k, '')})" for k in conflicts)
        notify(
            f"Kısayol çakışması: {ckeys} — Ayarlar → Global Kısayollar'dan değiştirin",
            duration_ms=3400,
            warning=True,
        )

    wakeup_timer = QTimer()
    wakeup_timer.setInterval(250)
    wakeup_timer.timeout.connect(lambda: None)
    prev_sigint = None
    prev_sigterm = None
    on_main_thread = threading.current_thread() is threading.main_thread()
    if on_main_thread:
        def _on_os_signal(_signum: int, _frame: Any) -> None:
            QTimer.singleShot(0, quit_app)

        prev_sigint = signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGINT, _on_os_signal)
        if hasattr(signal, "SIGTERM"):
            prev_sigterm = signal.getsignal(signal.SIGTERM)
            signal.signal(signal.SIGTERM, _on_os_signal)
        wakeup_timer.start()

    try:
        return app.exec()
    except KeyboardInterrupt:
        quit_app()
        return 0
    finally:
        wakeup_timer.stop()
        if on_main_thread:
            if prev_sigint is not None:
                signal.signal(signal.SIGINT, prev_sigint)
            if hasattr(signal, "SIGTERM") and prev_sigterm is not None:
                signal.signal(signal.SIGTERM, prev_sigterm)
        _cleanup()


def main(argv: list[str] | None = None) -> int:
    from qtp_app.cli import run

    return run(argv)


if __name__ == "__main__":
    raise SystemExit(main())
