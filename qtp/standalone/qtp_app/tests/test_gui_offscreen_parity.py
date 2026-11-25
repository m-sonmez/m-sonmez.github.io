"""Offscreen PyQt6 GUI durumu ile CLI JSON çıktısı arasındaki birebir veri eşitliği testi."""

from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from qtp_app import cli
from qtp_app.core.engine import QtpEngine
from qtp_app.ui.overlay import OverlayWindow


def test_gui_offscreen_model_matches_cli_json_output(tmp_path: Path, capsys):
    eng_gui = QtpEngine(work_dir=tmp_path / "gui")
    eng_cli = QtpEngine(work_dir=tmp_path / "cli")

    app = QApplication.instance() or QApplication([])
    overlay = OverlayWindow(eng_gui.items, theme=eng_gui.settings["theme"])
    try:
        overlay.show_overlay(category="ALL", animate=False)
        app.processEvents()

        parser = cli.build_arg_parser()
        cli.execute_cli(eng_cli, parser.parse_args(["--list-categories", "--json"]))
        cli_cats = json.loads(capsys.readouterr().out)["data"]["categories"]
        for cat in cli_cats:
            gui_count = overlay.category_buttons[cat["code"]].property("item_count")
            assert gui_count == cat["count"]

        overlay.search_input.setText("email")
        app.processEvents()
        cli.execute_cli(eng_cli, parser.parse_args(["--search", "email", "--json"]))
        cli_items = json.loads(capsys.readouterr().out)["data"]["items"]

        assert len(cli_items) >= 1
        assert overlay.list_model.rowCount() == len(cli_items)
        gui_texts = [overlay.list_model.item_at(i)["text"] for i in range(overlay.list_model.rowCount())]
        cli_texts = [it["text"] for it in cli_items]
        assert gui_texts == cli_texts

        overlay.set_view_mode("grid", persist=False)
        assert overlay.view_stack.currentWidget() is overlay.list_view
        assert overlay.list_delegate.grid_mode is True
        overlay.set_view_mode("table", persist=False)
        assert overlay.view_stack.currentWidget() is overlay.table_view
        assert overlay.table_model.rowCount() == len(cli_items)
        overlay.set_view_mode("list", persist=False)
        assert overlay.view_stack.currentWidget() is overlay.list_view
        overlay.toggle_check(0)
        assert len(overlay._selected_keys) == 1
        overlay.select_all_visible()
        assert len(overlay._selected_keys) == len(cli_items)
        overlay.clear_selection()
        assert len(overlay._selected_keys) == 0
    finally:
        overlay.close()
        overlay.deleteLater()
        app.processEvents()
