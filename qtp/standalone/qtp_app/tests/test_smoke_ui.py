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
    assert help_dlg.tabs.count() == 4
    tab_titles = [help_dlg.tabs.tabText(i) for i in range(help_dlg.tabs.count())]
    assert tab_titles == ["Kullanım Kılavuzu", "Kısayollar", "Sorun Giderme (SSS)", "CLI & Parametreler"]
    assert "--hotkey-preset" in help_dlg.browsers[3].toPlainText()
    assert build_cli_help_text(verbose=True).splitlines()[0] in help_dlg.browsers[3].toPlainText()

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
    dlg.theme_cb.setCurrentText("light")
    dlg.auto_reload_chk.setChecked(False)
    dlg.auto_reload_interval_spin.setValue(900)
    dlg._save_and_accept()

    assert dlg.result_settings is not None
    assert dlg.result_settings["web"]["port"] == 9123
    assert dlg.result_settings["theme"] == "light"
    assert dlg.result_settings["auto_reload"] is False
    assert dlg.result_settings["auto_reload_interval_ms"] == 900
    assert dlg.result_settings["hotkeys"]["W"] == "Ctrl+Shift+W"

    cfg_path = tmp_path / "qtp_settings.json"
    save_settings(dlg.result_settings, cfg_path)
    reloaded, _, warn = load_settings(tmp_path)
    assert warn is None and reloaded["hotkeys"]["W"] == "Ctrl+Shift+W"

    dlg._reset_defaults()
    assert dlg.web_port_spin.value() == 8765
    assert dlg.theme_cb.currentText() == "dark"
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
