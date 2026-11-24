"""PyQt6 arayüz düzeni, düğme alanları, HiDPI simge, gecikmeli kayıt ve pencere geometrisi testleri."""

from __future__ import annotations

import os
from pathlib import Path
from unittest import mock

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QPoint, QRect, QSize, Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QComboBox,
    QLineEdit,
    QListView,
    QScrollArea,
    QSystemTrayIcon,
    QWidget,
)

from qtp_app.core.engine import QtpEngine
from qtp_app.core.ini_parser import parse_qtp_ini, read_text_auto
from qtp_app.core.settings import DEFAULT_SETTINGS
from qtp_app.main import build_backups_dialog, create_resize_persister
from qtp_app.ui.help_dialog import HelpDialog, markdown_to_html
from qtp_app.ui.icons import make_svg_icon, render_svg_pixmap
from qtp_app.ui.overlay import (
    BulkEditDialog,
    GroupManagerDialog,
    IniSnippetViewerDialog,
    OverlayWindow,
    SnippetEditorDialog,
)
from qtp_app.ui.settings_window import HotkeyEdit, SettingsWindow
from qtp_app.ui.theme import DARK_PALETTE, FOOTER_HINTS_TEXT, LIGHT_PALETTE
from qtp_app.ui.tray import QtpTrayIcon, load_tray_icon

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def _load_fixture_items() -> list[dict]:
    doc = parse_qtp_ini(read_text_auto(FIXTURES_DIR / "QuickTextPaste.ini"))
    return [{**it.to_dict(include_meta=False), "terminator": it.terminator} for it in doc.items]


def _mapped_rect(widget: QWidget, ancestor: QWidget) -> QRect:
    tl = widget.mapTo(ancestor, QPoint(0, 0))
    return QRect(tl, widget.size())


def _assert_inside_parent(widget: QWidget, container: QWidget, *, check_vertical: bool = True) -> None:
    if not widget.isVisible() or widget.width() <= 0 or widget.height() <= 0:
        return
    r = _mapped_rect(widget, container)
    crect = container.rect()
    assert r.left() >= -1, f"{widget.objectName() or type(widget).__name__} sol kenardan taştı: {r} vs {crect}"
    assert r.right() <= crect.right() + 1, (
        f"{widget.objectName() or type(widget).__name__} sağ kenardan taştı: {r} vs {crect}"
    )
    if check_vertical:
        assert r.top() >= -1, f"{widget.objectName() or type(widget).__name__} üstten taştı: {r} vs {crect}"
        assert r.bottom() <= crect.bottom() + 1, (
            f"{widget.objectName() or type(widget).__name__} alttan taştı: {r} vs {crect}"
        )


def _assert_no_overlap(widgets: list[QWidget], ancestor: QWidget) -> None:
    rects: list[tuple[QWidget, QRect]] = [
        (w, _mapped_rect(w, ancestor)) for w in widgets if w.isVisible() and w.width() > 0 and w.height() > 0
    ]
    for i, (wi, ri) in enumerate(rects):
        for wj, rj in rects[i + 1 :]:
            inter = ri.intersected(rj)
            assert inter.isEmpty() or inter.width() <= 1 or inter.height() <= 1, (
                f"Çakışan widget'lar: {type(wi).__name__} {ri} vs {type(wj).__name__} {rj}"
            )


@pytest.mark.parametrize("size_wh", [(560, 400), (720, 520), (1024, 700), (1920, 1080)])
@pytest.mark.parametrize("view_mode", ["list", "grid", "table"])
@pytest.mark.parametrize("theme", ["light", "dark"])
def test_overlay_geometry_no_clipping_across_sizes_views_themes(qtbot, size_wh, view_mode, theme):
    items = _load_fixture_items()
    app = QApplication.instance()
    w, h = size_wh
    overlay = OverlayWindow(
        items,
        theme=theme,
        view_mode=view_mode,
        window_size=(w, h),
    )
    qtbot.addWidget(overlay)
    overlay.show_overlay(category="ALL", animate=False)
    overlay.resize(w, h)
    app.processEvents()

    assert overlay.width() == w
    assert overlay.height() == h
    assert overlay.theme_btn.text() == ""
    assert overlay.help_btn.text() == ""
    assert overlay.settings_btn.text() == ""
    assert len(overlay._shadow_layers) == 6

    compact = w < 640
    assert overlay.more_btn.isVisible() is compact
    assert overlay.bulk_edit_btn.isVisible() is (not compact)

    active_view = overlay.table_view if view_mode == "table" else overlay.list_view
    assert active_view.height() >= 180, f"{w}x{h} {view_mode}: liste alanı çok kısa ({active_view.height()}px)"
    _assert_inside_parent(active_view, overlay.card)

    header_controls = [
        overlay.window_title_label,
        overlay.max_btn,
        overlay.close_btn,
        overlay.search_input,
        overlay.add_btn,
        overlay.theme_btn,
        overlay.help_btn,
        overlay.settings_btn,
        overlay.footer_hints,
        overlay.count_label,
        overlay.size_grip,
        *overlay.category_buttons.values(),
        overlay.view_list_btn,
        overlay.view_grid_btn,
        overlay.view_table_btn,
        overlay.scope_fav_btn,
        overlay.scope_notes_btn,
        overlay.sort_cb,
        overlay.emoji_strip_btn,
        overlay.select_all_btn,
        overlay.bulk_edit_btn,
        overlay.bulk_del_btn,
        overlay.groups_btn,
        overlay.more_btn,
        overlay.save_btn,
        overlay.undo_btn,
        overlay.redo_btn,
    ]
    for ctrl in header_controls:
        _assert_inside_parent(ctrl, overlay.card)

    _assert_no_overlap([overlay.search_input, overlay.add_btn, overlay.theme_btn, overlay.help_btn, overlay.settings_btn], overlay.card)
    _assert_no_overlap(list(overlay.category_buttons.values()), overlay.card)
    _assert_no_overlap([overlay.footer_hints, overlay.count_label, overlay.size_grip], overlay.card)

    hint_rect = _mapped_rect(overlay.footer_hints, overlay.card)
    count_rect = _mapped_rect(overlay.count_label, overlay.card)
    assert hint_rect.right() <= count_rect.left()


def test_list_and_grid_copy_hitbox_and_static_movement(qtbot):
    items = _load_fixture_items()[:10]
    pasted: list[dict] = []
    copied: list[dict] = []
    overlay = OverlayWindow(
        items,
        theme="light",
        window_size=(720, 520),
        on_paste=lambda it, _prev: pasted.append(it),
        on_copy=lambda it: copied.append(it),
    )
    qtbot.addWidget(overlay)
    overlay.show_overlay(category="ALL", animate=False)
    QApplication.instance().processEvents()

    idx_row0 = overlay.list_model.index(0, 0)
    idx_row1 = overlay.list_model.index(1, 0)
    overlay.list_view.setCurrentIndex(idx_row0)
    overlay.list_delegate.hovered_row = -1
    row1_rect = overlay.list_view.visualRect(idx_row1)
    copy_pos_row1 = overlay.list_delegate.copy_button_rect(row1_rect).center()
    assert not copy_pos_row1.isNull()

    QTest.mouseClick(overlay.list_view.viewport(), Qt.MouseButton.LeftButton, pos=copy_pos_row1)
    assert len(pasted) == 1 and pasted[0]["text"] == items[1]["text"]
    assert len(copied) == 0

    overlay.show_overlay(category="ALL", animate=False)
    QApplication.instance().processEvents()
    overlay.list_view.setCurrentIndex(idx_row1)
    overlay.list_delegate.hovered_row = 1
    copy_pos_row1_visible = overlay.list_delegate.copy_button_rect(overlay.list_view.visualRect(idx_row1)).center()
    QTest.mouseClick(overlay.list_view.viewport(), Qt.MouseButton.LeftButton, pos=copy_pos_row1_visible)
    assert len(copied) == 1 and copied[0]["text"] == items[1]["text"]

    overlay.set_view_mode("grid", persist=False)
    QApplication.instance().processEvents()
    assert overlay.list_view.movement() == QListView.Movement.Static
    assert overlay.list_view.dragEnabled() is False
    assert overlay.list_delegate.copy_button_rect(overlay.list_view.visualRect(idx_row1)).isEmpty()

    grid_rect_0 = overlay.list_view.visualRect(idx_row0)
    bottom_right_inside = QPoint(grid_rect_0.right() - 18, grid_rect_0.bottom() - 14)
    QTest.mouseClick(overlay.list_view.viewport(), Qt.MouseButton.LeftButton, pos=bottom_right_inside)
    assert len(pasted) == 2
    assert len(copied) == 1


def test_wayland_and_offscreen_suppress_raise_call(qtbot):
    overlay = OverlayWindow(_load_fixture_items()[:5], theme="light")
    qtbot.addWidget(overlay)

    with mock.patch("qtp_app.ui.overlay.QGuiApplication.platformName", return_value="offscreen"):
        assert overlay._supports_raise() is False
        with mock.patch.object(overlay, "raise_") as mock_raise:
            overlay.show_overlay(animate=False)
            assert mock_raise.call_count == 0

    with mock.patch("qtp_app.ui.overlay.QGuiApplication.platformName", return_value="wayland"):
        assert overlay._supports_raise() is False
        with mock.patch.object(overlay, "raise_") as mock_raise:
            overlay.show_overlay(animate=False)
            assert mock_raise.call_count == 0

    with mock.patch("qtp_app.ui.overlay.QGuiApplication.platformName", return_value="xcb"):
        assert overlay._supports_raise() is True
        with mock.patch.object(overlay, "raise_") as mock_raise:
            overlay.show_overlay(animate=False)
            assert mock_raise.call_count == 1


def test_resize_persistence_is_debounced(qtbot, tmp_path: Path):
    eng = QtpEngine(work_dir=tmp_path)
    overlay = OverlayWindow(eng.items, theme="light", window_size=(720, 520))
    qtbot.addWidget(overlay)
    on_resized, flush_resize, _timer = create_resize_persister(eng, overlay, delay_ms=400)
    overlay.window_resized.connect(on_resized)
    overlay.show_overlay(animate=False)
    QApplication.instance().processEvents()

    with mock.patch.object(eng, "save_current_settings", wraps=eng.save_current_settings) as spy_save:
        for step in range(50):
            overlay.window_resized.emit(600 + step, 440)
        assert spy_save.call_count == 0
        qtbot.wait(650)
        assert spy_save.call_count == 1
        assert eng.settings["window_size"] == [649, 440]

        overlay.showMaximized()
        QApplication.instance().processEvents()
        overlay.window_resized.emit(1200, 900)
        qtbot.wait(500)
        assert spy_save.call_count == 1
        flush_resize()
        assert spy_save.call_count == 1


def test_tray_trigger_and_doubleclick_and_hidpi_icons(qtbot):
    opened: list[int] = []
    toggled: list[int] = []
    tray = QtpTrayIcon(
        on_open=lambda: opened.append(1),
        on_toggle=lambda: toggled.append(1),
        on_settings=lambda: None,
        on_reload_ini=lambda: None,
        on_open_json=lambda: None,
        on_backups=lambda: None,
        on_help=lambda: None,
        on_quit=lambda: None,
    )
    tray._handle_activated(QSystemTrayIcon.ActivationReason.Trigger)
    assert len(toggled) == 1 and len(opened) == 0
    tray._handle_activated(QSystemTrayIcon.ActivationReason.DoubleClick)
    assert len(opened) == 1
    tray._handle_activated(QSystemTrayIcon.ActivationReason.Context)
    assert len(toggled) == 1 and len(opened) == 1

    tray_fallback = QtpTrayIcon(
        on_open=lambda: opened.append(2),
        on_settings=lambda: None,
        on_reload_ini=lambda: None,
        on_open_json=lambda: None,
        on_backups=lambda: None,
        on_help=lambda: None,
        on_quit=lambda: None,
    )
    tray_fallback._handle_activated(QSystemTrayIcon.ActivationReason.Trigger)
    assert opened[-1] == 2

    px2 = render_svg_pixmap("settings", DARK_PALETTE.btn_text, size=16, dpr=2.0)
    assert px2.width() == 32 and px2.height() == 32
    assert px2.devicePixelRatio() == pytest.approx(2.0)

    ico = make_svg_icon("sun", DARK_PALETTE.btn_text, size=16)
    avail_sizes = ico.availableSizes()
    assert QSize(16, 16) in avail_sizes
    hi_pm = ico.pixmap(QSize(16, 16), 2.0)
    assert not hi_pm.isNull()
    assert hi_pm.width() >= 32 or hi_pm.devicePixelRatio() >= 2.0

    tray_ico = load_tray_icon()
    assert isinstance(tray_ico, QIcon) and not tray_ico.isNull()


def test_hotkey_edit_macos_ctrl_meta_swap(qtbot):
    edit = HotkeyEdit()
    qtbot.addWidget(edit)

    with mock.patch("qtp_app.ui.settings_window.QGuiApplication.platformName", return_value="cocoa"):
        QTest.keyClick(edit, Qt.Key.Key_K, Qt.KeyboardModifier.ControlModifier)
        assert edit.text() == "Win+K"
        QTest.keyClick(edit, Qt.Key.Key_K, Qt.KeyboardModifier.MetaModifier)
        assert edit.text() == "Ctrl+K"

    with mock.patch("qtp_app.ui.settings_window.QGuiApplication.platformName", return_value="xcb"):
        QTest.keyClick(edit, Qt.Key.Key_J, Qt.KeyboardModifier.ControlModifier)
        assert edit.text() == "Ctrl+J"
        QTest.keyClick(edit, Qt.Key.Key_J, Qt.KeyboardModifier.MetaModifier)
        assert edit.text() == "Win+J"


def test_help_markdown_links_and_all_dialogs_at_minimum_size(qtbot, tmp_path: Path):
    rendered = markdown_to_html(
        "Bakınız [QTP Rehberi](https://example.com/docs) ve [Kurulum](KURULUM.md) ve `kodu [x](y)` ve [Bad](javascript:alert(1)).",
        LIGHT_PALETTE,
    )
    assert '<a href="https://example.com/docs">QTP Rehberi</a>' in rendered
    assert '<a href="KURULUM.md">Kurulum</a>' in rendered
    assert "<code>kodu [x](y)</code>" in rendered
    assert "javascript:" not in rendered or '<a href="javascript:' not in rendered

    app = QApplication.instance()
    items = _load_fixture_items()[:6]
    eng = QtpEngine(work_dir=tmp_path)

    help_dlg = HelpDialog(LIGHT_PALETTE)
    settings_dlg = SettingsWindow(DEFAULT_SETTINGS, DARK_PALETTE)
    group_dlg = GroupManagerDialog(
        LIGHT_PALETTE,
        lambda: [("Müşteri Destek / Kurye Operasyon", 14), ("Genel", 3)],
        on_rename=lambda _o, _n: None,
        on_delete=lambda _g: None,
        on_export=lambda _g: None,
    )
    editor_dlg = SnippetEditorDialog(LIGHT_PALETTE, ["Genel", "Kurye"], item=items[0])
    bulk_dlg = BulkEditDialog(DARK_PALETTE, 5, ["Genel", "Kurye"])
    ini_dlg = IniSnippetViewerDialog(items[0], 0, str(tmp_path / "QuickTextPaste.ini"), LIGHT_PALETTE)
    backups_dlg = build_backups_dialog(eng, DARK_PALETTE)

    for dlg in (help_dlg, settings_dlg, group_dlg, editor_dlg, bulk_dlg, ini_dlg, backups_dlg):
        qtbot.addWidget(dlg)
        min_sz = dlg.minimumSize()
        assert min_sz.width() > 0 and min_sz.height() > 0
        dlg.resize(min_sz)
        dlg.show()
        app.processEvents()

        assert dlg.width() <= min_sz.width() + 2
        scroll_areas = dlg.findChildren(QScrollArea)
        scroll_viewports = [sa.viewport() for sa in scroll_areas]
        for sa in scroll_areas:
            assert sa.horizontalScrollBar().maximum() == 0, f"{type(dlg).__name__} yatay taşma!"
        for child in dlg.findChildren(QWidget):
            if not isinstance(child, (QAbstractButton, QComboBox, QLineEdit)):
                continue
            if not child.isVisible():
                continue
            target_container = dlg
            in_scroll = False
            for sa, vp in zip(scroll_areas, scroll_viewports):
                if sa.isAncestorOf(child):
                    target_container = vp
                    in_scroll = True
                    break
            _assert_inside_parent(child, target_container, check_vertical=not in_scroll)
