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

