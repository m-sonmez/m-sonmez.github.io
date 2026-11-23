"""Tema, esnek global kısayollar, canlı çakışma uyarısı, otomatik yenileme ve veri ayarları penceresi."""

from __future__ import annotations

import copy
from typing import Any, Callable

from PyQt6.QtCore import Qt, pyqtSignal
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
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from qtp_app.core.hotkeys import (
    CANONICAL_MODIFIERS,
    HOTKEY_PRESETS,
    HOTKEY_PRESET_LABELS,
    apply_modifier_combo,
    detect_hotkey_conflicts,
    normalize_hotkey,
    parse_hotkey,
    resolve_preset_name,
)
from qtp_app.core.settings import (
    DEFAULT_HOTKEYS,
    DEFAULT_SETTINGS,
    SETTING_DESCRIPTIONS,
    VALID_LOG_LEVELS,
    VALID_PASTE_METHODS,
    VALID_THEMES,
    _sanitize_settings,
)
from qtp_app.ui.help_dialog import HelpDialog
from qtp_app.ui.theme import (
    ThemePalette,
    build_dialog_stylesheet,
    create_app_font,
    load_bundled_fonts,
)

_BUILTIN_HOTKEY_LABELS: tuple[tuple[str, str], ...] = (
    ("all", "Tümü (Genel)"),
    ("A", "Kategori A (İş Ortağı)"),
    ("Z", "Kategori Z (Kurye)"),
    ("X", "Kategori X (Canlı Yardım)"),
    ("Q", "Kategori Q (Turkcell)"),
)

_BUILTIN_SLOT_SET = {k for k, _ in _BUILTIN_HOTKEY_LABELS}

_MODIFIER_BULK_CHOICES: tuple[str, ...] = (
    "Win+Alt",
    "Win+Ctrl",
    "Ctrl+Alt",
    "Ctrl+Shift",
    "Alt+Shift",
    "Ctrl+Alt+Shift",
    "Win+Shift",
    "Win+Ctrl+Alt",
    "Win+Ctrl+Shift",
    "Win+Alt+Shift",
    "Win+Ctrl+Alt+Shift",
    "Ctrl",
    "Alt",
    "Shift",
    "Win",
)

_QT_KEY_NAMES: dict[int, str] = {
    int(Qt.Key.Key_Space): "Space",
    int(Qt.Key.Key_Tab): "Tab",
    int(Qt.Key.Key_Return): "Enter",
    int(Qt.Key.Key_Enter): "Enter",
    int(Qt.Key.Key_Escape): "Esc",
    int(Qt.Key.Key_Backspace): "Backspace",
    int(Qt.Key.Key_Insert): "Insert",
    int(Qt.Key.Key_Delete): "Delete",
    int(Qt.Key.Key_Home): "Home",
    int(Qt.Key.Key_End): "End",
    int(Qt.Key.Key_PageUp): "PageUp",
    int(Qt.Key.Key_PageDown): "PageDown",
    int(Qt.Key.Key_Up): "Up",
    int(Qt.Key.Key_Down): "Down",
    int(Qt.Key.Key_Left): "Left",
    int(Qt.Key.Key_Right): "Right",
    int(Qt.Key.Key_Minus): "-",
    int(Qt.Key.Key_Equal): "=",
    int(Qt.Key.Key_BracketLeft): "[",
    int(Qt.Key.Key_BracketRight): "]",
    int(Qt.Key.Key_Semicolon): ";",
    int(Qt.Key.Key_Apostrophe): "'",
    int(Qt.Key.Key_Comma): ",",
    int(Qt.Key.Key_Period): ".",
    int(Qt.Key.Key_Slash): "/",
    int(Qt.Key.Key_Backslash): "\\",
    int(Qt.Key.Key_QuoteLeft): "`",
}
for _i in range(24):
    _QT_KEY_NAMES[int(Qt.Key.Key_F1) + _i] = f"F{_i + 1}"
for _i in range(26):
    _QT_KEY_NAMES[int(Qt.Key.Key_A) + _i] = chr(ord("A") + _i)
for _i in range(10):
    _QT_KEY_NAMES[int(Qt.Key.Key_0) + _i] = chr(ord("0") + _i)

_MODIFIER_ONLY_KEYS = {
    int(Qt.Key.Key_Control),
    int(Qt.Key.Key_Shift),
    int(Qt.Key.Key_Alt),
    int(Qt.Key.Key_AltGr),
    int(Qt.Key.Key_Meta),
    int(Qt.Key.Key_Super_L),
    int(Qt.Key.Key_Super_R),
}


class HotkeyEdit(QLineEdit):
    """Hem doğrudan tuş basarak hem de elle düzenleyerek kısayol girişi kabul eden alan."""

    combo_changed = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.capture_mode = False
        self.setPlaceholderText("Tuş bileşimi basın veya yazın (ör. Win+Alt+A)")

    def keyPressEvent(self, event: Any) -> None:
        key_code = int(event.key())
        if key_code in _MODIFIER_ONLY_KEYS:
            event.accept()
            return

        qt_mods = event.modifiers()
        mods: list[str] = []
        if qt_mods & Qt.KeyboardModifier.MetaModifier:
            mods.append("Win")
        if qt_mods & Qt.KeyboardModifier.ControlModifier:
            mods.append("Ctrl")
        if qt_mods & Qt.KeyboardModifier.AltModifier:
            mods.append("Alt")
        if qt_mods & Qt.KeyboardModifier.ShiftModifier:
            mods.append("Shift")

        if self.capture_mode and not mods and key_code == int(Qt.Key.Key_Backspace):
            self.setText("")
            self.combo_changed.emit("")
            event.accept()
            return

        if not mods and key_code == int(Qt.Key.Key_Backspace) and self.text().strip() == "":
            event.accept()
            return

        key_name = _QT_KEY_NAMES.get(key_code)
        is_edit_chord = (mods == ["Ctrl"] and key_name in ("A", "C", "V", "X", "Z")) and not self.capture_mode
        if mods and key_name and not is_edit_chord:
            combo = normalize_hotkey("+".join([*mods, key_name]))
            self.setText(combo)
            self.combo_changed.emit(combo)
            event.accept()
            return

        super().keyPressEvent(event)


class HotkeyRow(QWidget):
    """4 değiştirici onay kutusu (Ctrl/Alt/Shift/Win) ile çift yönlü eşitlenen kısayol satırı."""

    def __init__(
        self,
        slot: str,
        *,
        removable: bool = False,
        on_changed: Callable[[], None] | None = None,
        on_remove: Callable[[str], None] | None = None,
        tooltip: str = "",
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.slot = slot
        self._on_changed = on_changed
        self._syncing = False

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)

        self.chk_ctrl = QCheckBox("Ctrl", self)
        self.chk_alt = QCheckBox("Alt", self)
        self.chk_shift = QCheckBox("Shift", self)
        self.chk_win = QCheckBox("Win", self)
        self._mod_boxes: dict[str, QCheckBox] = {
            "Win": self.chk_win,
            "Ctrl": self.chk_ctrl,
            "Alt": self.chk_alt,
            "Shift": self.chk_shift,
        }
        for chk in (self.chk_ctrl, self.chk_alt, self.chk_shift, self.chk_win):
            chk.setToolTip("Bu değiştiriciyi kısayola ekle veya kaldır")
            chk.toggled.connect(self._on_checkbox_toggled)
            row.addWidget(chk)

        self.edit = HotkeyEdit(self)
        if tooltip:
            self.edit.setToolTip(tooltip)
        self.edit.textChanged.connect(self._on_edit_text_changed)
        row.addWidget(self.edit, 1)

        self.capture_btn = QPushButton("Yakala", self)
        self.capture_btn.setCheckable(True)
        self.capture_btn.setToolTip("Etkinleştirildiğinde klavyeden basılan tuş bileşimini doğrudan yakalar")
        self.capture_btn.toggled.connect(self._on_capture_toggled)
        row.addWidget(self.capture_btn)

        self.remove_btn: QPushButton | None = None
        if removable:
            btn = QPushButton("×", self)
            btn.setFixedWidth(28)
            btn.setToolTip(f"'{slot}' özel kısayol yuvasını kaldır")
            btn.clicked.connect(lambda: on_remove(slot) if on_remove else None)
            row.addWidget(btn)
            self.remove_btn = btn

    def _on_capture_toggled(self, checked: bool) -> None:
        self.edit.capture_mode = checked
        if checked:
            self.edit.setFocus()

    def _current_trigger_fallback(self) -> str:
        raw = self.edit.text().strip()
        if raw:
            try:
                _mods, key = parse_hotkey(raw)
                return key
            except ValueError:
                tail = raw.split("+")[-1].strip()
                if tail:
                    return tail.upper() if len(tail) == 1 else tail
        if self.slot == "all":
            return "Space"
        if len(self.slot) == 1 and self.slot.isalnum():
            return self.slot.upper()
        return "Space"

    def _on_checkbox_toggled(self, _checked: bool) -> None:
        if self._syncing:
            return
        selected = [m for m in CANONICAL_MODIFIERS if self._mod_boxes[m].isChecked()]
        self._syncing = True
        try:
            if not selected:
                self.edit.setText("")
            else:
                key = self._current_trigger_fallback()
                try:
                    self.edit.setText(normalize_hotkey("+".join([*selected, key])))
                except ValueError:
                    self.edit.setText("+".join([*selected, key]))
        finally:
            self._syncing = False
        if self._on_changed:
            self._on_changed()

    def _on_edit_text_changed(self, text: str) -> None:
        if not self._syncing:
            self._sync_boxes_from_text(text)
        if self._on_changed:
            self._on_changed()

    def _sync_boxes_from_text(self, text: str) -> None:
        self._syncing = True
        try:
            clean = (text or "").strip()
            if not clean:
                for chk in self._mod_boxes.values():
                    chk.setChecked(False)
                return
            try:
                mods, _key = parse_hotkey(clean)
            except ValueError:
                mods = tuple(
                    m for m in CANONICAL_MODIFIERS if m.lower() in {t.strip().lower() for t in clean.split("+")}
                )
            for mod_name, chk in self._mod_boxes.items():
                chk.setChecked(mod_name in mods)
        finally:
            self._syncing = False

    def set_combo(self, combo: str) -> None:
        self._syncing = True
        try:
            self.edit.setText(combo)
        finally:
            self._syncing = False
        self._sync_boxes_from_text(combo)


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
        self.resize(680, 700)
        self._palette = palette
        self._base_settings = copy.deepcopy(current_settings)
        self._font_family = load_bundled_fonts()
        self.setFont(create_app_font(self._font_family, 13))
        self.setStyleSheet(build_dialog_stylesheet(palette))
        self.result_settings: dict[str, Any] | None = None
        self.hk_rows: dict[str, HotkeyRow] = {}
        self.hk_edits: dict[str, HotkeyEdit] = {}
        self._hk_form_rows: dict[str, int] = {}

        self._build_ui()
        self._populate(self._base_settings)

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

        hk_group = QGroupBox("Global Kısayollar", container)
        hk_outer = QVBoxLayout(hk_group)
        hk_outer.setSpacing(8)
        _, self._hk_tip = self._desc("hotkeys")
        hk_group.setToolTip(self._hk_tip)

        preset_bar = QHBoxLayout()
        preset_bar.addWidget(QLabel("Kısayol Profili:"))
        self.preset_cb = QComboBox()
        for pid in HOTKEY_PRESETS:
            self.preset_cb.addItem(HOTKEY_PRESET_LABELS.get(pid, pid), pid)
        self.preset_cb.setToolTip("Hazır kısayol şablonunu seçin ve uygulayın")
        self.preset_cb.activated.connect(self._on_preset_activated)
        self.apply_preset_btn = QPushButton("Profili Uygula")
        self.apply_preset_btn.clicked.connect(self._apply_selected_preset)
        preset_bar.addWidget(self.preset_cb, 1)
        preset_bar.addWidget(self.apply_preset_btn)
        hk_outer.addLayout(preset_bar)

        mod_bar = QHBoxLayout()
        mod_bar.addWidget(QLabel("Tümüne Değiştirici Uygula:"))
        self.bulk_mod_cb = QComboBox()
        self.bulk_mod_cb.addItems(list(_MODIFIER_BULK_CHOICES))
        self.bulk_mod_cb.setToolTip("Tüm etkin kısayolların değiştirici ön ekini tek tıkla günceller")
        self.apply_mod_btn = QPushButton("Değiştirici Uygula")
        self.apply_mod_btn.clicked.connect(self._apply_bulk_modifiers)
        mod_bar.addWidget(self.bulk_mod_cb, 1)
        mod_bar.addWidget(self.apply_mod_btn)
        hk_outer.addLayout(mod_bar)

        self.hk_form = QFormLayout()
        self.hk_form.setSpacing(6)
        hk_outer.addLayout(self.hk_form)

        add_slot_bar = QHBoxLayout()
        self.new_slot_edit = QLineEdit()
        self.new_slot_edit.setPlaceholderText("Yeni yuva adı (ör. W, 1, Özel)")
        self.add_slot_btn = QPushButton("+ Özel Kısayol Ekle")
        self.add_slot_btn.clicked.connect(self._on_add_custom_slot)
        add_slot_bar.addWidget(self.new_slot_edit, 1)
        add_slot_bar.addWidget(self.add_slot_btn)
        hk_outer.addLayout(add_slot_bar)

        self.conflict_label = QLabel("")
        self.conflict_label.setWordWrap(True)
        self.conflict_label.setObjectName("HotkeyConflictLabel")
        hk_outer.addWidget(self.conflict_label)

        container_layout.addWidget(hk_group)

        data_group = QGroupBox("Veri, Yedekleme, Otomatik Yenileme ve Günlük", container)
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

        lbl, tip = self._desc("auto_reload")
        self.auto_reload_chk = QCheckBox(f"{lbl} (auto_reload)")
        self.auto_reload_chk.setToolTip(tip)
        data_form.addRow("", self.auto_reload_chk)

        lbl, tip = self._desc("auto_reload_interval_ms")
        self.auto_reload_interval_spin = QSpinBox()
        self.auto_reload_interval_spin.setRange(100, 10000)
        self.auto_reload_interval_spin.setSingleStep(100)
        self.auto_reload_interval_spin.setSuffix(" ms")
        self.auto_reload_interval_spin.setToolTip(tip)
        data_form.addRow(lbl + ":", self.auto_reload_interval_spin)

        lbl, tip = self._desc("log_level")
        self.log_level_cb = QComboBox()
        self.log_level_cb.addItems(list(VALID_LOG_LEVELS))
        self.log_level_cb.setToolTip(tip)
        data_form.addRow(lbl + ":", self.log_level_cb)

        lbl, tip = self._desc("web")
        self.web_port_spin = QSpinBox()
        self.web_port_spin.setRange(0, 65535)
        self.web_port_spin.setToolTip(tip)
        data_form.addRow(f"{lbl} Portu:", self.web_port_spin)

        container_layout.addWidget(data_group)
        container_layout.addStretch()

        scroll.setWidget(container)
        root.addWidget(scroll, 1)

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

    def _clear_hotkey_rows(self) -> None:
        while self.hk_form.rowCount() > 0:
            self.hk_form.removeRow(0)
        self.hk_rows.clear()
        self.hk_edits.clear()
        self._hk_form_rows.clear()

    def add_hotkey_slot(self, slot: str, combo: str = "") -> HotkeyRow:
        clean_slot = slot.strip()
        if clean_slot in self.hk_rows:
            if combo:
                self.hk_rows[clean_slot].set_combo(combo)
            return self.hk_rows[clean_slot]

        label_map = dict(_BUILTIN_HOTKEY_LABELS)
        label_txt = label_map.get(clean_slot, f"Özel ({clean_slot})")
        removable = clean_slot not in _BUILTIN_SLOT_SET
        row_widget = HotkeyRow(
            clean_slot,
            removable=removable,
            on_changed=self._update_conflict_status,
            on_remove=self.remove_custom_slot,
            tooltip=self._hk_tip,
            parent=self,
        )
        row_widget.set_combo(combo)
        self.hk_rows[clean_slot] = row_widget
        self.hk_edits[clean_slot] = row_widget.edit
        self._hk_form_rows[clean_slot] = self.hk_form.rowCount()
        self.hk_form.addRow(label_txt + ":", row_widget)
        self._update_conflict_status()
        return row_widget

    def remove_custom_slot(self, slot: str) -> bool:
        if slot in _BUILTIN_SLOT_SET or slot not in self.hk_rows:
            return False
        widget = self.hk_rows.pop(slot)
        self.hk_edits.pop(slot, None)
        self.hk_form.removeRow(widget)
        self._update_conflict_status()
        return True

    def _on_add_custom_slot(self) -> None:
        raw_slot = self.new_slot_edit.text().strip()
        if not raw_slot or "." in raw_slot:
            QMessageBox.warning(self, "Geçersiz Yuva", "Lütfen geçerli ve noktası bulunmayan bir yuva adı girin (ör. W, 1).")
            return
        if raw_slot in self.hk_rows:
            QMessageBox.information(self, "Mevcut Yuva", f"'{raw_slot}' yuvası zaten tanımlı.")
            return
        key_hint = raw_slot.upper() if len(raw_slot) == 1 and raw_slot.isalnum() else "K"
        self.add_hotkey_slot(raw_slot, f"Win+Alt+{key_hint}")
        self.new_slot_edit.clear()

    def apply_preset(self, preset_id: str) -> None:
        canon = resolve_preset_name(preset_id)
        target_map = HOTKEY_PRESETS[canon]
        for slot, combo in target_map.items():
            if slot in self.hk_rows:
                self.hk_rows[slot].set_combo(combo)
            else:
                self.add_hotkey_slot(slot, combo)
        idx = self.preset_cb.findData(canon)
        if idx >= 0:
            self.preset_cb.setCurrentIndex(idx)
        self._update_conflict_status()

    def _on_preset_activated(self, index: int) -> None:
        pid = self.preset_cb.itemData(index)
        if pid:
            self.apply_preset(str(pid))

    def _apply_selected_preset(self) -> None:
        pid = self.preset_cb.currentData()
        if pid:
            self.apply_preset(str(pid))

    def _apply_bulk_modifiers(self) -> None:
        mods_text = self.bulk_mod_cb.currentText()
        current_map = {k: row.edit.text().strip() for k, row in self.hk_rows.items()}
        rewritten = apply_modifier_combo(current_map, mods_text)
        for slot, combo in rewritten.items():
            if slot in self.hk_rows:
                self.hk_rows[slot].set_combo(combo)
        self._update_conflict_status()

    def _current_hotkeys_map(self) -> dict[str, str]:
        return {k: row.edit.text().strip() for k, row in self.hk_rows.items()}

    def _update_conflict_status(self) -> None:
        hk_map = self._current_hotkeys_map()
        conflicts = detect_hotkey_conflicts(hk_map)
        if not conflicts:
            self.conflict_label.setStyleSheet("color: #10B981; font-weight: 600;")
            self.conflict_label.setText("Çakışma algılanmadı ✔")
            return
        lines = []
        for slot, msgs in conflicts.items():
            combo = hk_map.get(slot, "")
            lines.append(f"[{slot}: {combo}] {'; '.join(msgs)}")
        self.conflict_label.setStyleSheet("color: #F59E0B; font-weight: 600;")
        self.conflict_label.setText("\n".join(lines))

    def _populate(self, data: dict[str, Any]) -> None:
        self.theme_cb.setCurrentText(str(data.get("theme", "light")))
        self.last_cat_cb.setCurrentText(str(data.get("last_category", "ALL")))
        ws = data.get("window_size") or [720, 520]
        self.width_spin.setValue(int(ws[0]))
        self.height_spin.setValue(int(ws[1]))
        self.lang_cb.setCurrentText(str(data.get("language", "tr")))
        self.start_min_chk.setChecked(bool(data.get("start_minimized", False)))
        self.tray_chk.setChecked(bool(data.get("tray_icon", True)))
        self.paste_method_cb.setCurrentText(str(data.get("paste_method", "auto")))
        self.enter_after_chk.setChecked(bool(data.get("enter_after_paste", True)))

        self._clear_hotkey_rows()
        hotkeys = data.get("hotkeys") or DEFAULT_SETTINGS["hotkeys"]
        for k, _lbl in _BUILTIN_HOTKEY_LABELS:
            self.add_hotkey_slot(k, str(hotkeys.get(k, DEFAULT_HOTKEYS[k])))
        for k, v in hotkeys.items():
            if k not in _BUILTIN_SLOT_SET:
                self.add_hotkey_slot(str(k), str(v))

        self.preset_cb.blockSignals(True)
        matched_preset = None
        for pid, pmap in HOTKEY_PRESETS.items():
            if all(hotkeys.get(k) == v for k, v in pmap.items()):
                matched_preset = pid
                break
        if matched_preset:
            idx = self.preset_cb.findData(matched_preset)
            if idx >= 0:
                self.preset_cb.setCurrentIndex(idx)
        self.preset_cb.blockSignals(False)

        self.data_path_edit.setText(str(data.get("data_path", "./QuickTextPaste.ini")))
        self.backup_spin.setValue(int(data.get("backup_count", 15)))
        self.auto_reload_chk.setChecked(bool(data.get("auto_reload", True)))
        self.auto_reload_interval_spin.setValue(int(data.get("auto_reload_interval_ms", 500)))
        self.log_level_cb.setCurrentText(str(data.get("log_level", "info")))
        web_cfg = data.get("web") if isinstance(data.get("web"), dict) else {}
        self.web_port_spin.setValue(int(web_cfg.get("port", DEFAULT_SETTINGS["web"]["port"])))
        self._update_conflict_status()

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
        self._base_settings = copy.deepcopy(DEFAULT_SETTINGS)
        self._populate(self._base_settings)

    def _open_help(self) -> None:
        dlg = HelpDialog(self._palette, initial_tab=0, parent=self)
        dlg.scroll_to_anchor_text("Ayarlar")
        dlg.exec()

    def collect_settings(self, base: dict[str, Any] | None = None) -> dict[str, Any]:
        """Form değerlerini qtp_settings.json sözlüğü olarak toplar."""
        out = copy.deepcopy(base if base is not None else self._base_settings)
        out["theme"] = self.theme_cb.currentText()
        out["last_category"] = self.last_cat_cb.currentText()
        out["window_size"] = [self.width_spin.value(), self.height_spin.value()]
        out["language"] = self.lang_cb.currentText()
        out["start_minimized"] = self.start_min_chk.isChecked()
        out["tray_icon"] = self.tray_chk.isChecked()
        out["paste_method"] = self.paste_method_cb.currentText()
        out["enter_after_paste"] = self.enter_after_chk.isChecked()

        hk_collected: dict[str, str] = {}
        for k, row in self.hk_rows.items():
            raw = row.edit.text().strip()
            if not raw:
                if k in DEFAULT_HOTKEYS:
                    hk_collected[k] = ""
                continue
            try:
                hk_collected[k] = normalize_hotkey(raw)
            except ValueError:
                hk_collected[k] = raw
        out["hotkeys"] = hk_collected

        out["data_path"] = self.data_path_edit.text().strip() or "./QuickTextPaste.ini"
        out["backup_count"] = self.backup_spin.value()
        out["auto_reload"] = self.auto_reload_chk.isChecked()
        out["auto_reload_interval_ms"] = self.auto_reload_interval_spin.value()
        out["log_level"] = self.log_level_cb.currentText()
        out["web"] = {"port": int(self.web_port_spin.value())}
        return _sanitize_settings(out)

    def _save_and_accept(self) -> None:
        hk_map = self._current_hotkeys_map()
        seen_combos: dict[str, str] = {}
        for slot, raw in hk_map.items():
            if not raw:
                continue
            try:
                norm = normalize_hotkey(raw)
            except ValueError as exc:
                QMessageBox.warning(self, "Geçersiz Kısayol", f"[{slot}] {exc}")
                return
            if norm in seen_combos:
                QMessageBox.warning(
                    self,
                    "Çift Kısayol Ataması",
                    f"'{norm}' kısayolu hem '{seen_combos[norm]}' hem de '{slot}' yuvasına atanmış. Kaydetmeden önce benzersiz hale getirin.",
                )
                return
            seen_combos[norm] = slot

        self.result_settings = self.collect_settings()
        self.accept()
