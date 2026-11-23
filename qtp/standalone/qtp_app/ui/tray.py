"""Sistem tepsisi simgesi ve Türkçe sağ tık menüsü."""

from __future__ import annotations

from typing import Callable

from PyQt6.QtGui import QAction, QIcon, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QMenu, QSystemTrayIcon, QWidget

from qtp_app.ui.theme import get_asset_path


def load_tray_icon() -> QIcon:
    """icon.svg dosyasını 22/32 px boyutlarında yüksek netlikle QIcon olarak yükler."""
    svg_path = get_asset_path("icon.svg")
    if svg_path.is_file():
        icon = QIcon()
        renderer = QSvgRenderer(str(svg_path))
        if renderer.isValid():
            for size in (22, 32, 48):
                pixmap = QPixmap(size, size)
                pixmap.fill(0)
                painter = QPainter(pixmap)
                renderer.render(painter)
                painter.end()
                icon.addPixmap(pixmap)
            return icon
    png_path = get_asset_path("icon-192.png")
    if png_path.is_file():
        return QIcon(str(png_path))
    return QIcon()


class QtpTrayIcon(QSystemTrayIcon):
    """Tüm platformlarda aynı Türkçe menü etiketlerini sunan sistem tepsisi yöneticisi."""

    def __init__(
        self,
        *,
        on_open: Callable[[], None],
        on_settings: Callable[[], None],
        on_reload_ini: Callable[[], None],
        on_open_json: Callable[[], None],
        on_backups: Callable[[], None],
        on_help: Callable[[], None],
        on_quit: Callable[[], None],
        open_hotkey: str = "Win+Alt+Space",
        parent: QWidget | None = None,
    ):
        super().__init__(load_tray_icon(), parent)

        self._on_open = on_open
        self.menu = QMenu(parent)

        self.act_open = QAction("", self.menu)
        self.act_settings = QAction("Ayarlar…", self.menu)
        self.act_reload = QAction("INI Yeniden Yükle", self.menu)
        self.act_open_json = QAction("data.json Aç", self.menu)
        self.act_backups = QAction("Yedekler…", self.menu)
        self.act_help = QAction("Yardım (F1)", self.menu)
        self.act_quit = QAction("Çıkış", self.menu)

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

        self.update_hotkeys_label(open_hotkey)
        self.setContextMenu(self.menu)
        self.activated.connect(self._handle_activated)

    def update_hotkeys_label(self, open_hotkey: str) -> None:
        hk = (open_hotkey or "").strip()
        if hk:
            self.act_open.setText(f"Aç ({hk})")
            self.setToolTip(f"QTP — Hazır Cevaplar ({hk})")
        else:
            self.act_open.setText("Aç")
            self.setToolTip("QTP — Hazır Cevaplar")

    def _handle_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._on_open()
