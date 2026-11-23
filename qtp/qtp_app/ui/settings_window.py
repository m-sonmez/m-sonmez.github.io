"""Tema, global kısayollar, yapıştırma ve veri dosyası ayarları penceresi."""

from __future__ import annotations

import copy
from typing import Any

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from qtp_app.core.settings import (
    DEFAULT_SETTINGS,
    SETTING_DESCRIPTIONS,
    VALID_LOG_LEVELS,
    VALID_PASTE_METHODS,
    VALID_THEMES,
)
from qtp_app.ui.help_dialog import HelpDialog
from qtp_app.ui.theme import (
    ThemePalette,
    build_dialog_stylesheet,
    create_app_font,
    load_bundled_fonts,
)


class SettingsWindow(QDialog):
    """qtp_settings.json içindeki tüm alanları Türkçe etiket ve ipuçlarıyla düzenleme penceresi."""

    def __init__(
        self,
        current_settings: dict[str, Any],
        palette: ThemePalette,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("QTP Ayarları")
        self.resize(560, 610)
        self._palette = palette
        self._font_family = load_bundled_fonts()
        self.setFont(create_app_font(self._font_family, 13))
        self.setStyleSheet(build_dialog_stylesheet(palette))
        self.result_settings: dict[str, Any] | None = None

        self._build_ui()
        self._populate(current_settings)

    def _desc(self, key: str) -> tuple[str, str]:
        entry = SETTING_DESCRIPTIONS.get(key, {})
        return entry.get("label", key), entry.get("tooltip", "")

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setSpacing(12)

        # Genel Görünüm ve Davranış
        gen_group = QGroupBox("Görünüm ve Davranış", container)
        gen_form = QFormLayout(gen_group)
        gen_form.setSpacing(8)

        lbl, tip = self._desc("theme")
        self.theme_cb = QComboBox()
        self.theme_cb.addItems(list(VALID_THEMES))
        self.theme_cb.setToolTip(tip)
        gen_form.addRow(lbl + ":", self.theme_cb)

        lbl, tip = self._desc("last_category")
        self.last_cat_cb = QComboBox()
        self.last_cat_cb.addItems(["ALL", "A", "Z", "X", "Q"])
        self.last_cat_cb.setToolTip(tip)
        gen_form.addRow(lbl + ":", self.last_cat_cb)

        lbl, tip = self._desc("window_size")
        size_row = QHBoxLayout()
        self.width_spin = QSpinBox()
        self.width_spin.setRange(560, 2400)
        self.width_spin.setToolTip(tip)
        self.height_spin = QSpinBox()
        self.height_spin.setRange(400, 1600)
        self.height_spin.setToolTip(tip)
        size_row.addWidget(self.width_spin)
        size_row.addWidget(QLabel("×"))
        size_row.addWidget(self.height_spin)
        gen_form.addRow(lbl + ":", size_row)

        lbl, tip = self._desc("language")
        self.lang_cb = QComboBox()
        self.lang_cb.addItems(["tr"])
        self.lang_cb.setToolTip(tip)
        gen_form.addRow(lbl + ":", self.lang_cb)

        lbl, tip = self._desc("start_minimized")
        self.start_min_chk = QCheckBox(lbl)
        self.start_min_chk.setToolTip(tip)
        gen_form.addRow("", self.start_min_chk)

        lbl, tip = self._desc("tray_icon")
        self.tray_chk = QCheckBox(lbl)
        self.tray_chk.setToolTip(tip)
        gen_form.addRow("", self.tray_chk)

        container_layout.addWidget(gen_group)

        # Yapıştırma
        paste_group = QGroupBox("Yapıştırma Ayarları", container)
        paste_form = QFormLayout(paste_group)
        paste_form.setSpacing(8)

        lbl, tip = self._desc("paste_method")
        self.paste_method_cb = QComboBox()
        self.paste_method_cb.addItems(list(VALID_PASTE_METHODS))
        self.paste_method_cb.setToolTip(tip)
        paste_form.addRow(lbl + ":", self.paste_method_cb)

        lbl, tip = self._desc("enter_after_paste")
        self.enter_after_chk = QCheckBox(lbl)
        self.enter_after_chk.setToolTip(tip)
        paste_form.addRow("", self.enter_after_chk)

        container_layout.addWidget(paste_group)

        # Global Kısayollar
        hk_group = QGroupBox("Global Kısayollar", container)
        hk_form = QFormLayout(hk_group)
        hk_form.setSpacing(8)
        _, hk_tip = self._desc("hotkeys")
        hk_group.setToolTip(hk_tip)

        self.hk_edits: dict[str, QLineEdit] = {}
        for key, label_txt in (
            ("all", "Tümü (Genel)"),
            ("A", "Kategori A (İş Ortağı)"),
            ("Z", "Kategori Z (Kurye)"),
            ("X", "Kategori X (Canlı Yardım)"),
            ("Q", "Kategori Q (Turkcell)"),
        ):
            edit = QLineEdit()
            edit.setToolTip(hk_tip)
            hk_form.addRow(label_txt + ":", edit)
            self.hk_edits[key] = edit

        container_layout.addWidget(hk_group)

        # Veri, Yedekleme ve Günlük
        data_group = QGroupBox("Veri, Yedekleme ve Günlük", container)
        data_form = QFormLayout(data_group)
        data_form.setSpacing(8)

        lbl, tip = self._desc("data_path")
        path_row = QHBoxLayout()
        self.data_path_edit = QLineEdit()
        self.data_path_edit.setToolTip(tip)
        browse_btn = QPushButton("Seç…")
        browse_btn.clicked.connect(self._browse_ini)
        path_row.addWidget(self.data_path_edit, 1)
        path_row.addWidget(browse_btn)
        data_form.addRow(lbl + ":", path_row)

        lbl, tip = self._desc("backup_count")
        self.backup_spin = QSpinBox()
        self.backup_spin.setRange(1, 100)
        self.backup_spin.setToolTip(tip)
        data_form.addRow(lbl + ":", self.backup_spin)

        lbl, tip = self._desc("log_level")
        self.log_level_cb = QComboBox()
        self.log_level_cb.addItems(list(VALID_LOG_LEVELS))
        self.log_level_cb.setToolTip(tip)
        data_form.addRow(lbl + ":", self.log_level_cb)

        container_layout.addWidget(data_group)
        container_layout.addStretch()

        scroll.setWidget(container)
        root.addWidget(scroll, 1)

        # Alt Düğmeler: Yardım, Varsayılana Sıfırla, İptal, Kaydet
        btn_row = QHBoxLayout()
        help_btn = QPushButton("Yardım")
        help_btn.clicked.connect(self._open_help)
        reset_btn = QPushButton("Varsayılana Sıfırla")
        reset_btn.clicked.connect(self._reset_defaults)
        cancel_btn = QPushButton("İptal")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("Kaydet")
        save_btn.setObjectName("PrimaryBtn")
        save_btn.clicked.connect(self._save_and_accept)

        btn_row.addWidget(help_btn)
        btn_row.addWidget(reset_btn)
        btn_row.addStretch()
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        root.addLayout(btn_row)

    def _populate(self, data: dict[str, Any]) -> None:
        self.theme_cb.setCurrentText(str(data.get("theme", "dark")))
        self.last_cat_cb.setCurrentText(str(data.get("last_category", "ALL")))
        ws = data.get("window_size") or [720, 520]
        self.width_spin.setValue(int(ws[0]))
        self.height_spin.setValue(int(ws[1]))
        self.lang_cb.setCurrentText(str(data.get("language", "tr")))
        self.start_min_chk.setChecked(bool(data.get("start_minimized", False)))
        self.tray_chk.setChecked(bool(data.get("tray_icon", True)))
        self.paste_method_cb.setCurrentText(str(data.get("paste_method", "auto")))
        self.enter_after_chk.setChecked(bool(data.get("enter_after_paste", True)))

        hotkeys = data.get("hotkeys") or DEFAULT_SETTINGS["hotkeys"]
        for k, edit in self.hk_edits.items():
            edit.setText(str(hotkeys.get(k, DEFAULT_SETTINGS["hotkeys"][k])))

        self.data_path_edit.setText(str(data.get("data_path", "./QuickTextPaste.ini")))
        self.backup_spin.setValue(int(data.get("backup_count", 15)))
        self.log_level_cb.setCurrentText(str(data.get("log_level", "info")))

    def _browse_ini(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "QuickTextPaste.ini Dosyası Seç",
            self.data_path_edit.text(),
            "INI Dosyaları (*.ini);;Tüm Dosyalar (*.*)",
        )
        if path:
            self.data_path_edit.setText(path)

    def _reset_defaults(self) -> None:
        self._populate(copy.deepcopy(DEFAULT_SETTINGS))

    def _open_help(self) -> None:
        dlg = HelpDialog(self._palette, initial_tab=0, parent=self)
        dlg.scroll_to_anchor_text("Ayarlar")
        dlg.exec()

    def collect_settings(self, base: dict[str, Any] | None = None) -> dict[str, Any]:
        """Form değerlerini qtp_settings.json sözlüğü olarak toplar."""
        out = copy.deepcopy(base or DEFAULT_SETTINGS)
        out["theme"] = self.theme_cb.currentText()
        out["last_category"] = self.last_cat_cb.currentText()
        out["window_size"] = [self.width_spin.value(), self.height_spin.value()]
        out["language"] = self.lang_cb.currentText()
        out["start_minimized"] = self.start_min_chk.isChecked()
        out["tray_icon"] = self.tray_chk.isChecked()
        out["paste_method"] = self.paste_method_cb.currentText()
        out["enter_after_paste"] = self.enter_after_chk.isChecked()
        out["hotkeys"] = {
            k: edit.text().strip() or DEFAULT_SETTINGS["hotkeys"][k]
            for k, edit in self.hk_edits.items()
        }
        out["data_path"] = self.data_path_edit.text().strip() or "./QuickTextPaste.ini"
        out["backup_count"] = self.backup_spin.value()
        out["log_level"] = self.log_level_cb.currentText()
        return out

    def _save_and_accept(self) -> None:
        self.result_settings = self.collect_settings()
        self.accept()
