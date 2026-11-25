"""Sistem tepsisi simgesi ve Türkçe sağ tık menüsü."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QAction, QIcon, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QMenu, QSystemTrayIcon, QWidget

from qtp_app.core.i18n import t
from qtp_app.ui.icons import make_svg_icon
from qtp_app.ui.theme import DARK_PALETTE, ThemePalette, build_overlay_stylesheet, build_qpalette, get_asset_path

_TRAY_ICON_SIZES = (16, 22, 24, 32, 48, 64)


def load_tray_icon() -> QIcon:
    """icon.svg dosyasını çoklu çözünürlüklerde ve HiDPI DPR oranlarında QIcon olarak yükler."""
    svg_path = get_asset_path("icon.svg")
    if svg_path.is_file():
        icon = QIcon()
        renderer = QSvgRenderer(str(svg_path))
        if renderer.isValid():
            for size in _TRAY_ICON_SIZES:
                for scale in (1.0, 2.0):
                    px_size = max(1, int(round(size * scale)))
                    pixmap = QPixmap(px_size, px_size)
                    pixmap.fill(Qt.GlobalColor.transparent)
                    painter = QPainter(pixmap)
                    renderer.render(painter, QRectF(0.0, 0.0, float(px_size), float(px_size)))
                    painter.end()
                    pixmap.setDevicePixelRatio(scale)
                    icon.addPixmap(pixmap)
            return icon
    png_path = get_asset_path("icon-192.png")
    if png_path.is_file():
        base_pm = QPixmap(str(png_path))
        if not base_pm.isNull():
            icon = QIcon()
            for size in _TRAY_ICON_SIZES:
                icon.addPixmap(
                    base_pm.scaled(
                        size,
                        size,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
            return icon
        return QIcon(str(png_path))
    return QIcon()


class QtpTrayIcon(QSystemTrayIcon):
    """Tüm platformlarda aynı Türkçe menü etiketlerini ve tema uyumlu simgeleri sunan tepsi yöneticisi."""

    def __init__(
        self,
        *,
        on_open: Callable[[], None],
        on_toggle: Callable[[], None] | None = None,
        on_settings: Callable[[], None],
        on_reload_ini: Callable[[], None],
        on_open_json: Callable[[], None],
        on_backups: Callable[[], None],
        on_help: Callable[[], None],
        on_quit: Callable[[], None],
        open_hotkey: str = "Win+Alt+Space",
        palette: ThemePalette | None = None,
        language: str = "en",
        config_dir: Path | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(load_tray_icon(), parent)

        self._on_open = on_open
        self._on_toggle = on_toggle
        self._language = str(language or "en")
        self._config_dir = config_dir
        self._open_hotkey = str(open_hotkey or "").strip()
        self.menu = QMenu(parent)

        self.act_open = QAction("", self.menu)
        self.act_settings = QAction("", self.menu)
        self.act_reload = QAction("", self.menu)
        self.act_open_json = QAction("data.json", self.menu)
        self.act_backups = QAction("", self.menu)
        self.act_help = QAction("", self.menu)
        self.act_quit = QAction("", self.menu)

        self.act_open.triggered.connect(on_open)
        self.act_settings.triggered.connect(on_settings)
        self.act_reload.triggered.connect(on_reload_ini)
        self.act_open_json.triggered.connect(on_open_json)
        self.act_backups.triggered.connect(on_backups)
        self.act_help.triggered.connect(on_help)
        self.act_quit.triggered.connect(on_quit)

        self.menu.addAction(self.act_open)
        self.menu.addSeparator()
        self.menu.addAction(self.act_settings)
        self.menu.addAction(self.act_reload)
        self.menu.addAction(self.act_open_json)
        self.menu.addAction(self.act_backups)
        self.menu.addSeparator()
        self.menu.addAction(self.act_help)
        self.menu.addAction(self.act_quit)

        self.apply_language(self._language, self._config_dir)
        self.apply_palette(palette if palette is not None else DARK_PALETTE)
        self.setContextMenu(self.menu)
        self.activated.connect(self._handle_activated)

    def apply_language(self, language: str, config_dir: Path | None = None) -> None:
        self._language = str(language or "en")
        if config_dir is not None:
            self._config_dir = config_dir
        is_tr = self._language.startswith("tr")
        self.act_settings.setText(t("tray.settings", self._language, self._config_dir))
        self.act_reload.setText(t("tray.reload", self._language, self._config_dir))
        self.act_open_json.setText("data.json Aç" if is_tr else "Open data.json")
        self.act_backups.setText(t("tray.backups", self._language, self._config_dir))
        self.act_help.setText(t("tray.help", self._language, self._config_dir))
        self.act_quit.setText(t("tray.quit", self._language, self._config_dir))
        self.update_hotkeys_label(self._open_hotkey)

    def apply_palette(self, palette: ThemePalette) -> None:
        self.menu.setPalette(build_qpalette(palette))
        self.menu.setStyleSheet(build_overlay_stylesheet(palette))
        icon_color = palette.menu_text
        self.act_open.setIcon(make_svg_icon("paste", icon_color))
        self.act_settings.setIcon(make_svg_icon("settings", icon_color))
        self.act_reload.setIcon(make_svg_icon("reload", icon_color))
        self.act_open_json.setIcon(make_svg_icon("code", icon_color))
        self.act_backups.setIcon(make_svg_icon("backup", icon_color))
        self.act_help.setIcon(make_svg_icon("help", icon_color))
        self.act_quit.setIcon(make_svg_icon("quit", icon_color))

    def update_hotkeys_label(self, open_hotkey: str) -> None:
        hk = (open_hotkey or "").strip()
        self._open_hotkey = hk
        open_lbl = t("tray.open", self._language, self._config_dir)
        app_lbl = t("app.display_name", self._language, self._config_dir)
        if hk:
            self.act_open.setText(f"{open_lbl} ({hk})")
            self.setToolTip(f"{app_lbl} ({hk})")
        else:
            self.act_open.setText(open_lbl)
            self.setToolTip(app_lbl)

    def _handle_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            cb = self._on_toggle or self._on_open
            cb()
        elif reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._on_open()
