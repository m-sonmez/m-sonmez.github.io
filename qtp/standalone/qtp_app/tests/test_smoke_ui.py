"""PyQt6 offscreen duman testi: Overlay (527 öğe), HotkeyRow/HotkeyEdit/Profil, Canlı Yenileme ve Tepsi."""

from __future__ import annotations

import copy
import os
from collections import Counter
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QMessageBox

from qtp_app.core.engine import QtpEngine
from qtp_app.core.ini_parser import parse_qtp_ini, read_text_auto
from qtp_app.core.settings import DEFAULT_SETTINGS, load_settings, save_settings
from qtp_app.core.watcher import ReloadEvent
from qtp_app.main import apply_reload_event_gui
from qtp_app.ui.help_dialog import HelpDialog
from qtp_app.ui.overlay import OverlayWindow
from qtp_app.ui.settings_window import SettingsWindow
from qtp_app.ui.theme import DARK_PALETTE, FOOTER_HINTS_TEXT
from qtp_app.ui.tray import QtpTrayIcon

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def test_overlay_renders_all_items_focus_pills_and_enter_paste(qtbot):
    doc = parse_qtp_ini(read_text_auto(FIXTURES_DIR / "QuickTextPaste.ini"))
    items = [{**it.to_dict(include_meta=False), "terminator": it.terminator} for it in doc.items]
    total = len(items)
    counts_by_key = Counter(it["keys"] for it in items)

    pasted: list[dict] = []
    copied: list[dict] = []
    overlay = OverlayWindow(
        items,
        theme="dark",
        on_paste=lambda item, _prev: pasted.append(item),
        on_copy=lambda item: copied.append(item),
    )
    qtbot.addWidget(overlay)

    overlay.show_overlay(category="ALL", animate=False, previous_app=None)
    qtbot.waitUntil(lambda: overlay.isVisible() and overlay.search_input.hasFocus(), timeout=1500)

    assert overlay.list_model.rowCount() == total
    assert overlay.search_input.hasFocus()
    assert overlay.category_buttons["ALL"].property("item_count") == total
    assert f"({total})" in overlay.category_buttons["ALL"].text()
    for code in ("A", "Z", "X", "Q"):
        expected = counts_by_key[f"L-Win+{code}"]
        assert overlay.category_buttons[code].property("item_count") == expected

    assert overlay.footer_hints.text() == FOOTER_HINTS_TEXT

    overlay.set_category("Z")
    assert overlay.list_model.rowCount() == counts_by_key["L-Win+Z"]
    overlay.set_category("ALL")
    overlay.search_input.setText("şifre")
    assert 0 < overlay.list_model.rowCount() < total
    overlay.search_input.clear()
    assert overlay.list_model.rowCount() == total

    QTest.keyClick(overlay.search_input, Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier)
    assert len(copied) == 1
    assert "Panoya kopyalandı" in overlay.toast_label.text()

    QTest.keyClick(overlay.search_input, Qt.Key.Key_Return)
    assert len(pasted) == 1


def test_help_settings_and_tray_smoke(qtbot):
    from qtp_app.core.engine import build_cli_help_text

    help_dlg = HelpDialog(DARK_PALETTE)
    qtbot.addWidget(help_dlg)
    assert help_dlg.tabs.count() == 5
    tab_titles = [help_dlg.tabs.tabText(i) for i in range(help_dlg.tabs.count())]
    assert tab_titles == [
        "Kullanım (Web/GUI/TUI/CLI)",
        "Kurulum & İndirme",
        "Kısayollar & Profiller",
        "Sorun Giderme (SSS)",
        "CLI & Parametreler",
    ]
    assert "--hotkey-preset" in help_dlg.browsers[4].toPlainText()
    assert build_cli_help_text(verbose=True).splitlines()[0] in help_dlg.browsers[4].toPlainText()
    assert "Windows" in help_dlg.browsers[1].toPlainText()

    settings_dlg = SettingsWindow(DEFAULT_SETTINGS, DARK_PALETTE)
    qtbot.addWidget(settings_dlg)
    collected = settings_dlg.collect_settings()
    assert collected["theme"] == DEFAULT_SETTINGS["theme"]
    assert collected["hotkeys"] == DEFAULT_SETTINGS["hotkeys"]
    assert collected["auto_reload"] is True
    assert collected["auto_reload_interval_ms"] == 500
    assert "Çakışma algılanmadı" in settings_dlg.conflict_label.text()

    tray = QtpTrayIcon(
        on_open=lambda: None,
        on_settings=lambda: None,
        on_reload_ini=lambda: None,
        on_open_json=lambda: None,
        on_backups=lambda: None,
        on_help=lambda: None,
        on_quit=lambda: None,
    )
    labels = [act.text() for act in tray.menu.actions() if not act.isSeparator()]
    assert labels == [
        "Aç (Win+Alt+Space)",
        "Ayarlar…",
        "INI Yeniden Yükle",
        "data.json Aç",
        "Yedekler…",
        "Yardım (F1)",
        "Çıkış",
    ]
    tray.update_hotkeys_label("Win+Ctrl+Space")
    assert tray.act_open.text() == "Aç (Win+Ctrl+Space)"


def test_settings_window_hotkeys_presets_checkboxes_custom_slots_and_conflicts(qtbot, tmp_path: Path):
    custom = copy.deepcopy(DEFAULT_SETTINGS)
    custom["web"] = {"port": 8899}
    custom["last_category_by_hotkey"] = {"win_z": "Z"}

    dlg = SettingsWindow(custom, DARK_PALETTE)
    qtbot.addWidget(dlg)

    dlg.apply_preset("function_keys")
    assert dlg.hk_edits["all"].text() == "Ctrl+Shift+F1"
    assert dlg.hk_edits["A"].text() == "Ctrl+Shift+F2"
    assert "Çakışma algılanmadı" in dlg.conflict_label.text()

    with mock.patch("qtp_app.core.hotkeys.sys.platform", "win32"):
        dlg.apply_preset("legacy_win")
        assert dlg.hk_edits["A"].text() == "Win+A"
        assert "Hızlı Ayarlar" in dlg.conflict_label.text()

        dlg.hk_edits["Q"].setText("Ctrl+Alt+Q")
        assert "AltGr+Q" in dlg.conflict_label.text()

    dlg.apply_preset("recommended")
    assert "Çakışma algılanmadı" in dlg.conflict_label.text()

    row_a = dlg.hk_rows["A"]
    row_a.chk_ctrl.setChecked(True)
    row_a.chk_win.setChecked(False)
    assert dlg.hk_edits["A"].text() == "Ctrl+Alt+A"
    QTest.keyClick(row_a.edit, Qt.Key.Key_B, Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier)
    assert row_a.edit.text() == "Ctrl+Alt+B"
    assert row_a.chk_ctrl.isChecked() and row_a.chk_alt.isChecked()

    dlg.bulk_mod_cb.setCurrentText("Win+Ctrl")
    dlg._apply_bulk_modifiers()
    assert dlg.hk_edits["all"].text() == "Win+Ctrl+Space"
    assert dlg.hk_edits["A"].text() == "Win+Ctrl+B"

    dlg.new_slot_edit.setText("W")
    dlg._on_add_custom_slot()
    assert "W" in dlg.hk_edits
    dlg.remove_custom_slot("W")
    assert "W" not in dlg.hk_edits
    dlg.add_hotkey_slot("W", "Ctrl+Shift+W")

    dlg.web_port_spin.setValue(9123)
    dlg.theme_cb.setCurrentText("dark")
    dlg.auto_reload_chk.setChecked(False)
    dlg.auto_reload_interval_spin.setValue(900)
    with mock.patch.object(QMessageBox, "warning", return_value=QMessageBox.StandardButton.Yes):
        dlg._save_and_accept()

    assert dlg.result_settings is not None
    assert dlg.result_settings["web"]["port"] == 9123
    assert dlg.result_settings["theme"] == "dark"
    assert dlg.result_settings["auto_reload"] is False
    assert dlg.result_settings["auto_reload_interval_ms"] == 900
    assert dlg.result_settings["hotkeys"]["W"] == "Ctrl+Shift+W"

    cfg_path = tmp_path / "qtp_settings.json"
    save_settings(dlg.result_settings, cfg_path)
    reloaded, _, warn = load_settings(tmp_path)
    assert warn is None and reloaded["hotkeys"]["W"] == "Ctrl+Shift+W"

    dlg._reset_defaults()
    assert dlg.web_port_spin.value() == 8765
    assert dlg.theme_cb.currentText() == "light"
    assert "W" not in dlg.hk_edits


def test_gui_live_reload_event_handler_updates_overlay_tray_and_hotkeys(qtbot, tmp_path: Path):
    work = tmp_path / "gui_reload"
    work.mkdir()
    eng = QtpEngine(work_dir=work)
    eng.settings["theme"] = "light"
    eng.settings["window_size"] = [800, 560]
    eng.settings["hotkeys"]["all"] = "Win+Ctrl+Space"

    overlay = OverlayWindow(eng.items, theme="dark")
    qtbot.addWidget(overlay)
    tray = QtpTrayIcon(
        on_open=lambda: None,
        on_settings=lambda: None,
        on_reload_ini=lambda: None,
        on_open_json=lambda: None,
        on_backups=lambda: None,
        on_help=lambda: None,
        on_quit=lambda: None,
    )
    reg_calls = {"n": 0}

    def fake_register():
        reg_calls["n"] += 1
        return {}

    apply_reload_event_gui(
        ReloadEvent(
            settings_changed=True,
            hotkeys_changed=True,
            theme_changed=True,
            window_size_changed=True,
            items_changed=True,
            item_count=len(eng.items),
        ),
        eng,
        overlay,
        tray,
        fake_register,
    )
    assert reg_calls["n"] == 1
    assert tray.act_open.text() == "Aç (Win+Ctrl+Space)"
    assert overlay.size().width() == 800
    assert "otomatik yenilendi" in overlay.toast_label.text()

    from PyQt6.QtWidgets import QMessageBox
    from qtp_app.ui.overlay import SnippetEditorDialog
    from qtp_app.ui.theme import LIGHT_PALETTE

    crud_events: list[tuple[str, str]] = []
    ov_crud = OverlayWindow(
        eng.items,
        theme="light",
        on_add=lambda payload: (crud_events.append(("add", payload["text"])), eng.op_add_item(**payload))[1],
        on_edit=lambda it, payload: (crud_events.append(("edit", payload["text"])), eng.op_update_item(it["raw_key"], **payload))[1],
        on_delete=lambda it: (crud_events.append(("del", it["raw_key"])), eng.op_delete_item(it["raw_key"]))[1],
    )
    qtbot.addWidget(ov_crud)

    ed_empty = SnippetEditorDialog(LIGHT_PALETTE, ["Genel"], parent=ov_crud)
    qtbot.addWidget(ed_empty)
    with mock.patch.object(QMessageBox, "warning") as warn_box:
        ed_empty._on_save()
        assert warn_box.called
    ed_empty.text_edit.setPlainText("GUI Yeni Snippet")
    ed_empty.keys_cb.setCurrentText("L-Win+A")
    ed_empty._on_save()
    assert ed_empty.result_payload is not None and ed_empty.result_payload["text"] == "GUI Yeni Snippet"

    with mock.patch("qtp_app.ui.overlay.SnippetEditorDialog.exec", return_value=int(SnippetEditorDialog.DialogCode.Accepted)), \
         mock.patch.object(SnippetEditorDialog, "result_payload", new_callable=mock.PropertyMock, return_value={"text": "GUI Dialog Cevap", "keys": "L-Win+A", "group": "Genel", "label": "G1", "terminator": "<E<N<D|"}, create=True):
        ov_crud._open_add_dialog()
    assert any(ev[0] == "add" and ev[1] == "GUI Dialog Cevap" for ev in crud_events)

    first_item = dict(eng.items[0])
    with mock.patch("qtp_app.ui.overlay.SnippetEditorDialog.exec", return_value=int(SnippetEditorDialog.DialogCode.Accepted)), \
         mock.patch.object(SnippetEditorDialog, "result_payload", new_callable=mock.PropertyMock, return_value={"text": "GUI Güncel", "keys": "L-Win+A", "group": "Genel", "label": "G1", "terminator": "<E<N<D|"}, create=True):
        ov_crud._open_edit_dialog(first_item)
    assert any(ev[0] == "edit" and ev[1] == "GUI Güncel" for ev in crud_events)

    with mock.patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
        ov_crud._confirm_delete_item(first_item)
    assert any(ev[0] == "del" for ev in crud_events)


def _sample_image_mean_luminance(image) -> tuple[float, bool]:
    w = image.width()
    h = image.height()
    total_lum = 0.0
    samples = 0
    rows: list[list[float]] = []
    for y in range(2, max(3, h - 2)):
        row_lums: list[float] = []
        for x in range(2, max(3, w - 2)):
            c = image.pixelColor(x, y)
            if c.alpha() == 0:
                row_lums.append(1.0)
                continue
            lum = (0.2126 * c.red() + 0.7152 * c.green() + 0.0722 * c.blue()) / 255.0
            row_lums.append(lum)
            total_lum += lum
            samples += 1
        rows.append(row_lums)
    has_dark_block = False
    gh = len(rows)
    gw = len(rows[0]) if rows else 0
    for y in range(0, max(0, gh - 6), 2):
        for x in range(0, max(0, gw - 6), 2):
            if all(rows[y + dy][x + dx] < 0.22 for dy in range(6) for dx in range(6)):
                has_dark_block = True
                break
        if has_dark_block:
            break
    return (total_lum / max(1, samples)), has_dark_block


def test_offscreen_rendered_pixel_luminance_light_vs_dark_and_live_switch(qtbot):
    from PyQt6.QtCore import QRect
    from PyQt6.QtGui import QImage, QPainter
    from PyQt6.QtWidgets import QApplication, QStyle, QStyleOptionViewItem
    from qtp_app.ui.overlay import (
        BulkEditDialog,
        GroupManagerDialog,
        IniSnippetViewerDialog,
        SnippetEditorDialog,
        SnippetItemDelegate,
    )
    from qtp_app.ui.theme import DARK_PALETTE, LIGHT_PALETTE

    sample_items = [
        {"raw_key": "text_000", "keys": "L-Win+A", "group": "Restoran", "label": "Selam", "text": "Merhaba destek talebiniz alındı", "terminator": "<E<N<D|"},
        {"raw_key": "text_001", "keys": "L-Win+Z", "group": "Kurye", "label": "Teslim", "text": "Sipariş yola çıktı", "terminator": "<E<N<D|"},
    ]
    theme_events: list[str] = []
    ov = OverlayWindow(sample_items, theme="light", on_theme_change=theme_events.append)
    qtbot.addWidget(ov)
    ov.show_overlay(category="ALL", animate=False)
    QApplication.processEvents()

    light_card_lum, has_dark_card = _sample_image_mean_luminance(ov.card.grab().toImage())
    light_list_lum, has_dark_list = _sample_image_mean_luminance(ov.list_view.viewport().grab().toImage())
    assert light_card_lum > 0.78, f"Açık tema kart parlaklığı düşük: {light_card_lum:.3f}"
    assert light_list_lum > 0.78, f"Açık tema liste parlaklığı düşük: {light_list_lum:.3f}"
    assert not has_dark_card and not has_dark_list, "Açık tema içinde koyu blok sızıntısı bulundu"

    ov.toggle_theme()
    QApplication.processEvents()
    assert theme_events == ["dark"]
    dark_card_lum, _ = _sample_image_mean_luminance(ov.card.grab().toImage())
    dark_list_lum, _ = _sample_image_mean_luminance(ov.list_view.viewport().grab().toImage())
    assert dark_card_lum < 0.25, f"Koyu tema kart parlaklığı yüksek: {dark_card_lum:.3f}"
    assert dark_list_lum < 0.25, f"Koyu tema liste parlaklığı yüksek: {dark_list_lum:.3f}"

    ov.toggle_theme()
    QApplication.processEvents()
    assert theme_events == ["dark", "light"]
    relight_card_lum, _ = _sample_image_mean_luminance(ov.card.grab().toImage())
    relight_list_lum, _ = _sample_image_mean_luminance(ov.list_view.viewport().grab().toImage())
    assert relight_card_lum > 0.78
    assert relight_list_lum > 0.78

    for pal, expect_light in ((LIGHT_PALETTE, True), (DARK_PALETTE, False)):
        delegate = SnippetItemDelegate(pal)
        for state_flag in (QStyle.StateFlag.State_None, QStyle.StateFlag.State_MouseOver, QStyle.StateFlag.State_Selected):
            img = QImage(640, delegate.ROW_HEIGHT, QImage.Format.Format_ARGB32)
            img.fill(0)
            painter = QPainter(img)
            opt = QStyleOptionViewItem()
            opt.rect = QRect(0, 0, 640, delegate.ROW_HEIGHT)
            opt.state = state_flag
            delegate.paint(painter, opt, ov.list_model.index(0, 0))
            painter.end()
            lum, has_dark_blk = _sample_image_mean_luminance(img)
            if expect_light:
                assert lum > 0.70, f"Açık delegate ({state_flag}) çok koyu: {lum:.3f}"
                assert not has_dark_blk
            else:
                assert lum < 0.30, f"Koyu delegate ({state_flag}) çok açık: {lum:.3f}"

        for dlg in (
            SettingsWindow(DEFAULT_SETTINGS, pal),
            HelpDialog(pal),
            SnippetEditorDialog(pal, ["Genel"], item=sample_items[0]),
            IniSnippetViewerDialog(sample_items[0], 0, "QuickTextPaste.ini", pal),
            BulkEditDialog(pal, 2, ["Genel", "Kurye"]),
            GroupManagerDialog(
                pal,
                lambda: [("Genel", 2), ("Kurye", 1)],
                on_rename=lambda _o, _n: None,
                on_delete=lambda _g: None,
            ),
        ):
            qtbot.addWidget(dlg)
            dlg.show()
            QApplication.processEvents()
            dlg_lum, dlg_dark_blk = _sample_image_mean_luminance(dlg.grab().toImage())
            if expect_light:
                assert dlg_lum > 0.78, f"Açık {type(dlg).__name__} parlaklığı düşük: {dlg_lum:.3f}"
                assert not dlg_dark_blk, f"Açık {type(dlg).__name__} içinde koyu blok sızıntısı bulundu"
            else:
                assert dlg_lum < 0.25, f"Koyu {type(dlg).__name__} parlaklığı yüksek: {dlg_lum:.3f}"
            dlg.close()

    ed = SnippetEditorDialog(LIGHT_PALETTE, ["Genel"], item={"keys": "L-Win+A", "group": "Genel", "text": "Merhaba 😊 🚀", "favorite": True})
    qtbot.addWidget(ed)
    ed._strip_editor_emojis()
    assert ed.text_edit.toPlainText() == "Merhaba"
    ed.close()

    ov.set_view_mode("grid", persist=False)
    QApplication.processEvents()
    ov.set_view_mode("table", persist=False)
    QApplication.processEvents()
    assert ov.table_model.rowCount() == 2
    ov.toggle_strip_emoji()
    assert ov._strip_emoji is True


def test_overlay_copy_before_hide_wayland_opacity_svg_icons_and_8edge_resize(qtbot):
    from PyQt6.QtCore import QPoint
    from PyQt6.QtWidgets import QApplication
    from qtp_app.ui.icons import make_svg_icon, render_svg_pixmap
    from qtp_app.ui.theme import LIGHT_PALETTE
    from qtp_app.ui.tray import load_tray_icon

    tray_ic = load_tray_icon()
    assert not tray_ic.isNull()
    assert len(tray_ic.availableSizes()) >= 4

    for pal in (LIGHT_PALETTE, DARK_PALETTE):
        for icon_name in ("plus", "sun", "moon", "help", "settings", "copy", "edit", "trash", "save", "close", "maximize", "restore"):
            px = render_svg_pixmap(icon_name, pal.text_primary, size=18)
            assert not px.isNull() and px.width() == 18 and px.height() == 18
            ic = make_svg_icon(icon_name, pal.text_primary)
            assert not ic.isNull()

    items = [
        {"raw_key": "text_000", "keys": "L-Win+A", "group": "Restoran", "label": "Selam", "text": "Kopya önce gelmeli", "terminator": "<E<N<D|"},
    ]
    events: list[str] = []
    ov = OverlayWindow(
        items,
        theme="light",
        on_paste=lambda _it, _prev: events.append(f"paste:{int(ov.consume_pre_copied())}"),
    )
    qtbot.addWidget(ov)
    ov.show_overlay(category="ALL", animate=False)
    QApplication.processEvents()

    orig_hide = ov.hide_overlay

    def _spy_hide(*, animate: bool = True):
        events.append("hide")
        return orig_hide(animate=animate)

    def _spy_copy(txt: str, **_kw):
        events.append(f"copy:{txt}")
        return True

    with mock.patch("qtp_app.ui.overlay.copy_to_clipboard", side_effect=_spy_copy), \
         mock.patch.object(ov, "hide_overlay", side_effect=_spy_hide):
        ov.paste_row(0)

    assert events == ["copy:Kopya önce gelmeli", "hide", "paste:1"]

    with mock.patch("qtp_app.ui.overlay.QGuiApplication.platformName", return_value="wayland"):
        assert ov._supports_window_opacity() is False
        with mock.patch.object(ov, "setWindowOpacity") as op_mock:
            ov.show_overlay(category="ALL", animate=True)
            QApplication.processEvents()
            ov.hide_overlay(animate=True)
            QApplication.processEvents()
        op_mock.assert_not_called()

    ov.show_overlay(category="ALL", animate=False)
    ov.resize(740, 540)
    QApplication.processEvents()
    w, h = ov.width(), ov.height()
    assert ov._hit_test_edges(QPoint(2, h // 2)) == Qt.Edge.LeftEdge
    assert ov._hit_test_edges(QPoint(w - 2, h // 2)) == Qt.Edge.RightEdge
    assert ov._hit_test_edges(QPoint(w // 2, 2)) == Qt.Edge.TopEdge
    assert ov._hit_test_edges(QPoint(w // 2, h - 2)) == Qt.Edge.BottomEdge
    assert ov._cursor_for_edges(Qt.Edge.LeftEdge | Qt.Edge.TopEdge) == Qt.CursorShape.SizeFDiagCursor
    assert ov._cursor_for_edges(Qt.Edge.RightEdge | Qt.Edge.TopEdge) == Qt.CursorShape.SizeBDiagCursor
    assert ov._cursor_for_edges(Qt.Edge.LeftEdge) == Qt.CursorShape.SizeHorCursor
    assert ov._cursor_for_edges(Qt.Edge.BottomEdge) == Qt.CursorShape.SizeVerCursor

    resized_signals: list[tuple[int, int]] = []
    ov.window_resized.connect(lambda rw, rh: resized_signals.append((rw, rh)))
    with mock.patch.object(ov, "windowHandle", return_value=None):
        ov._begin_resize(Qt.Edge.RightEdge | Qt.Edge.BottomEdge, QPoint(100, 100))
        ov._handle_drag_move(QPoint(160, 150))
    QApplication.processEvents()
    assert ov.width() >= w + 50 and ov.height() >= h + 40
    assert resized_signals

    ov.toggle_maximize()
    assert ov.isMaximized() is True
    ov.toggle_maximize()
    assert ov.isMaximized() is False


def test_overlay_focus_loss_initial_category_ipc_and_conflict_confirm(qtbot, tmp_path: Path):
    import json
    import shutil
    import socket
    from PyQt6.QtCore import QEvent, QTimer
    from PyQt6.QtWidgets import QApplication, QMessageBox
    from qtp_app.core.settings import set_setting_value
    from qtp_app.main import SingleInstanceGuard, launch_gui

    app = QApplication.instance()
    cfg = copy.deepcopy(DEFAULT_SETTINGS)
    assert cfg["hide_on_blur"] is True
    assert set_setting_value(cfg, "hide_on_blur", "false")["hide_on_blur"] is False

    doc = parse_qtp_ini(read_text_auto(FIXTURES_DIR / "QuickTextPaste.ini"))
    items = [{**it.to_dict(include_meta=False), "terminator": it.terminator} for it in doc.items[:30]]
    ov = OverlayWindow(items, theme="light", hide_on_blur=True)
    qtbot.addWidget(ov)
    ov.show_overlay(category="ALL", animate=False)
    QApplication.processEvents()
    assert ov.isVisible() is True

    with mock.patch.object(ov, "isActiveWindow", return_value=False):
        ov.handle_focus_lost(delay_ms=0)
    assert ov.isVisible() is True

    ov._opened_monotonic -= 1.0
    ov.set_modal_child_open(True)
    with mock.patch.object(ov, "isActiveWindow", return_value=False):
        ov.handle_focus_lost(delay_ms=0)
    assert ov.isVisible() is True
    ov.set_modal_child_open(False)

    ov.apply_settings(hide_on_blur=False)
    with mock.patch.object(ov, "isActiveWindow", return_value=False):
        ov.handle_focus_lost(delay_ms=0)
    assert ov.isVisible() is True

    ov.apply_settings(hide_on_blur=True)
    with mock.patch.object(ov, "isActiveWindow", return_value=False), \
         mock.patch("qtp_app.ui.overlay.QApplication.activeWindow", return_value=None):
        ov.handle_focus_lost(delay_ms=0)
    QApplication.processEvents()
    assert ov.isVisible() is False

    ov.show_overlay(category="ALL", animate=False)
    ov._opened_monotonic -= 1.0
    with mock.patch.object(ov, "isActiveWindow", return_value=False), \
         mock.patch("qtp_app.ui.overlay.QApplication.activeWindow", return_value=None):
        ov.event(QEvent(QEvent.Type.WindowDeactivate))
    assert ov._blur_timer.isActive() is True
    ov._blur_timer.stop()

    with mock.patch.object(ov, "isActiveWindow", return_value=False), \
         mock.patch.object(ov, "hide") as hide_mock, \
         mock.patch.object(ov, "activateWindow") as act_mock, \
         mock.patch("qtp_app.ui.overlay.bring_window_to_top", return_value=True) as top_mock:
        ov.show_overlay(category="ALL", hotkey_key="all", force_category=True, animate=False)
    assert hide_mock.called
    assert act_mock.called
    assert top_mock.called
    assert bool(ov.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)

    ipc_dir = tmp_path / "ipc"
    received_tokens: list[str] = []
    g_srv = SingleInstanceGuard(ipc_dir)
    g_srv.acquire(lambda tok="": received_tokens.append(tok))
    g_cli = SingleInstanceGuard(ipc_dir)
    with mock.patch.dict(os.environ, {"XDG_ACTIVATION_TOKEN": "wl-token-241"}):
        assert g_cli.try_notify_existing() is True
    lock_info = json.loads(g_srv.lock_path.read_text(encoding="utf-8"))
    with socket.create_connection(("127.0.0.1", int(lock_info["port"])), timeout=1.0) as s:
        s.sendall(b"SHOW\n")
        assert s.recv(16).startswith(b"OK")
    qtbot.waitUntil(lambda: len(received_tokens) >= 2, timeout=2000)
    assert received_tokens[0] == "wl-token-241"
    assert received_tokens[1] == ""
    g_srv.release()

    sw = SettingsWindow(DEFAULT_SETTINGS, DARK_PALETTE)
    qtbot.addWidget(sw)
    assert sw.hide_on_blur_chk.isChecked() is True
    sw.hide_on_blur_chk.setChecked(False)
    sw.hk_rows["Q"].edit.setText("Win+Q")
    with mock.patch(
             "qtp_app.ui.settings_window.detect_hotkey_conflicts",
             return_value={"Q": ["KDE Plasma Etkinlikler (Activities) sistem kısayolu ile çakışır."]},
         ):
        sw._update_conflict_status()
        assert "KDE" in sw.conflict_label.text() or "Win+Q" in sw.conflict_label.text()
        with mock.patch.object(QMessageBox, "warning", return_value=QMessageBox.StandardButton.No) as warn_no:
            sw._save_and_accept()
        assert warn_no.called and sw.result_settings is None
        with mock.patch.object(QMessageBox, "warning", return_value=QMessageBox.StandardButton.Yes) as warn_yes:
            sw._save_and_accept()
        assert warn_yes.called and sw.result_settings is not None
        assert sw.result_settings["hide_on_blur"] is False

    stale_wd = tmp_path / "stale_wd"
    stale_wd.mkdir(parents=True, exist_ok=True)
    shutil.copy2(FIXTURES_DIR / "QuickTextPaste.ini", stale_wd / "QuickTextPaste.ini")
    stale_cfg = copy.deepcopy(DEFAULT_SETTINGS)
    stale_cfg["last_category"] = "Z"
    stale_cfg["last_category_by_hotkey"] = {"all": "Z", "A": "A", "Z": "Z", "X": "X", "Q": "Q"}
    stale_cfg["start_minimized"] = False
    save_settings(stale_cfg, stale_wd / "qtp_settings.json")

    eng_stale = QtpEngine(work_dir=stale_wd)
    orig_show = OverlayWindow.show_overlay
    shown_cats: list[str] = []

    def _spy_show(self_ov, *, category=None, hotkey_key=None, query=None, force_category=False, animate=True):
        orig_show(
            self_ov,
            category=category,
            hotkey_key=hotkey_key,
            query=query,
            force_category=force_category,
            animate=animate,
        )
        shown_cats.append(self_ov.active_category)

    fake_hk = mock.Mock()
    fake_hk.register.return_value = {}
    fake_hk.conflicts = {}
    orig_exec = app.exec

    def _fake_exec():
        QTimer.singleShot(50, app.quit)
        return orig_exec()

    with mock.patch.object(OverlayWindow, "show_overlay", _spy_show), \
         mock.patch("qtp_app.main.HotkeyManager", return_value=fake_hk), \
         mock.patch.object(app, "exec", side_effect=_fake_exec):
        rc = launch_gui(eng_stale, quiet=True)
    assert rc == 0
    assert shown_cats and shown_cats[0] == "ALL"
