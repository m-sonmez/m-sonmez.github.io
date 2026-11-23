"""PyQt6 offscreen duman testi: Overlay (527 öğe), odak, kategori sayacı, Enter/Ctrl+Enter, Ayarlar, Yardım ve Tepsi."""

from __future__ import annotations

import os
from collections import Counter
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest

from qtp_app.core.ini_parser import parse_qtp_ini, read_text_auto
from qtp_app.core.settings import DEFAULT_SETTINGS, load_settings, save_settings
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
        assert f"({expected})" in overlay.category_buttons[code].text()

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
    assert copied[0] == items[0]
    assert overlay.isVisible()
    assert "Panoya kopyalandı" in overlay.toast_label.text()

    QTest.keyClick(overlay.search_input, Qt.Key.Key_Return)
    assert len(pasted) == 1
    assert pasted[0] == items[0]


def test_help_settings_and_tray_smoke(qtbot):
    help_dlg = HelpDialog(DARK_PALETTE)
    qtbot.addWidget(help_dlg)
    assert help_dlg.tabs.count() == 3
    html_text = help_dlg.browsers[0].toPlainText()
    assert "Kullanım Kılavuzu" in html_text or "Kategori" in html_text

    settings_dlg = SettingsWindow(DEFAULT_SETTINGS, DARK_PALETTE)
    qtbot.addWidget(settings_dlg)
    collected = settings_dlg.collect_settings()
    assert collected["theme"] == DEFAULT_SETTINGS["theme"]
    assert collected["hotkeys"] == DEFAULT_SETTINGS["hotkeys"]
    assert collected["backup_count"] == DEFAULT_SETTINGS["backup_count"]

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
        "Aç (Ctrl+Shift+Space)",
        "Ayarlar…",
        "INI Yeniden Yükle",
        "data.json Aç",
        "Yedekler…",
        "Yardım (F1)",
        "Çıkış",
    ]


def test_settings_window_edits_web_port_theme_preserves_nested_and_resets(qtbot, tmp_path: Path):
    import copy

    custom = copy.deepcopy(DEFAULT_SETTINGS)
    custom["web"] = {"port": 8899}
    custom["last_category_by_hotkey"] = {"win_z": "Z"}

    dlg = SettingsWindow(custom, DARK_PALETTE)
    qtbot.addWidget(dlg)

    assert dlg.web_port_spin.value() == 8899
    assert dlg.web_port_spin.toolTip()
    dlg.web_port_spin.setValue(9123)
    dlg.theme_cb.setCurrentText("light")
    dlg._save_and_accept()

    assert dlg.result_settings is not None
    assert dlg.result_settings["web"]["port"] == 9123
    assert dlg.result_settings["theme"] == "light"
    assert dlg.result_settings["last_category_by_hotkey"] == {"win_z": "Z"}

    cfg_path = tmp_path / "qtp_settings.json"
    save_settings(dlg.result_settings, cfg_path)
    reloaded, _, warn = load_settings(tmp_path)
    assert warn is None
    assert reloaded["web"]["port"] == 9123
    assert reloaded["theme"] == "light"
    assert reloaded["last_category_by_hotkey"] == {"win_z": "Z"}

    dlg._reset_defaults()
    assert dlg.web_port_spin.value() == 8765
    assert dlg.theme_cb.currentText() == "dark"
