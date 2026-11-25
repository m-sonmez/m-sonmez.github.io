"""Settings window for theme, language, dynamic categories, global hotkeys, auto-reload, and storage."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Callable

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QGuiApplication
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
    apply_modifier_combo,
    build_preset_hotkeys,
    detect_hotkey_conflicts,
    get_preset_labels,
    normalize_hotkey,
    parse_hotkey,
    resolve_preset_name,
)
from qtp_app.core.i18n import available_languages, resolve_language, t
from qtp_app.core.settings import (
    CATEGORY_CODE_RE,
    DEFAULT_HOTKEYS,
    DEFAULT_SETTINGS,
    VALID_LOG_LEVELS,
    VALID_PASTE_METHODS,
    VALID_SORT_BY,
    VALID_THEMES,
    VALID_VIEW_MODES,
    _sanitize_settings,
    get_setting_descriptions,
    sanitize_categories,
)
from qtp_app.ui.flow_layout import FlowLayout
from qtp_app.ui.help_dialog import HelpDialog
from qtp_app.ui.icons import make_svg_icon
from qtp_app.ui.theme import (
    ThemePalette,
    build_dialog_stylesheet,
    build_qpalette,
    create_app_font,
    load_bundled_fonts,
)

_BUILTIN_SLOT_SET = {"all"}

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
    """Accepts both live keystroke capture and manual editing of hotkey combinations."""

    combo_changed = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None, *, language: str = "en"):
        super().__init__(parent)
        self.capture_mode = False
        self.setPlaceholderText(
            "Tuş bileşimi basın veya yazın (ör. Win+Alt+1)"
            if str(language or "en").startswith("tr")
            else "Press or type a key combo (e.g. Win+Alt+1)"
        )

    def keyPressEvent(self, event: Any) -> None:
        key_code = int(event.key())
        if key_code in _MODIFIER_ONLY_KEYS:
            event.accept()
            return

        qt_mods = event.modifiers()
        is_cocoa = (QGuiApplication.platformName() or "").strip().lower() == "cocoa"
        win_flag = Qt.KeyboardModifier.ControlModifier if is_cocoa else Qt.KeyboardModifier.MetaModifier
        ctrl_flag = Qt.KeyboardModifier.MetaModifier if is_cocoa else Qt.KeyboardModifier.ControlModifier
        mods: list[str] = []
        if qt_mods & win_flag:
            mods.append("Win")
        if qt_mods & ctrl_flag:
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
        edit_mod = "Win" if is_cocoa else "Ctrl"
        is_edit_chord = (mods == [edit_mod] and key_name in ("A", "C", "V", "X", "Z")) and not self.capture_mode
        if mods and key_name and not is_edit_chord:
            combo = normalize_hotkey("+".join([*mods, key_name]))
            self.setText(combo)
            self.combo_changed.emit(combo)
            event.accept()
            return

        super().keyPressEvent(event)


class HotkeyRow(QWidget):
    """Two-way synced hotkey editor row with Ctrl/Alt/Shift/Win checkboxes."""

    def __init__(
        self,
        slot: str,
        *,
        removable: bool = False,
        language: str = "en",
        config_dir: Path | None = None,
        on_changed: Callable[[], None] | None = None,
        on_remove: Callable[[str], None] | None = None,
        tooltip: str = "",
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.slot = slot
        self._on_changed = on_changed
        self._syncing = False
        is_tr = str(language or "en").startswith("tr")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 2, 0, 2)
        outer.setSpacing(4)

        mods_flow = FlowLayout(margin=0, spacing=8)

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
        mod_tip = "Bu değiştiriciyi kısayola ekle veya kaldır" if is_tr else "Toggle this modifier"
        for chk in (self.chk_ctrl, self.chk_alt, self.chk_shift, self.chk_win):
            chk.setToolTip(mod_tip)
            chk.toggled.connect(self._on_checkbox_toggled)
            mods_flow.addWidget(chk)
        outer.addLayout(mods_flow)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)

        self.edit = HotkeyEdit(self, language=language)
        self.edit.setMinimumWidth(140)
        if tooltip:
            self.edit.setToolTip(tooltip)
        self.edit.textChanged.connect(self._on_edit_text_changed)
        row.addWidget(self.edit, 1)

        self.capture_btn = QPushButton(t("settings.hk.record", language, config_dir), self)
        self.capture_btn.setCheckable(True)
        self.capture_btn.setToolTip(
            "Klavyeden basılan tuş bileşimini doğrudan yakala"
            if is_tr
            else "Capture keystrokes directly from keyboard"
        )
        self.capture_btn.toggled.connect(self._on_capture_toggled)
        row.addWidget(self.capture_btn)

        self.remove_btn: QPushButton | None = None
        if removable:
            btn = QPushButton("×", self)
            btn.setFixedWidth(28)
            btn.setToolTip(
                f"'{slot}' kısayol yuvasını kaldır" if is_tr else f"Remove hotkey slot '{slot}'"
            )
            btn.clicked.connect(lambda: on_remove(slot) if on_remove else None)
            row.addWidget(btn)
            self.remove_btn = btn
        outer.addLayout(row)

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
                    m for m in CANONICAL_MODIFIERS if m.lower() in {tok.strip().lower() for tok in clean.split("+")}
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
    """Cross-platform settings dialog covering appearance, language, dynamic categories, hotkeys, and storage."""

    def __init__(
        self,
        current_settings: dict[str, Any],
        palette: ThemePalette,
        parent: QWidget | None = None,
        *,
        language: str | None = None,
        config_dir: Path | None = None,
        discovered_categories: list[dict[str, Any]] | None = None,
    ):
        super().__init__(parent)
        self._palette = palette
        self._config_dir = config_dir
        self._discovered_categories = list(discovered_categories or [])
        self._base_settings = copy.deepcopy(current_settings)
        lang_src = language if language is not None else self._base_settings.get("language", "auto")
        self._lang = resolve_language(lang_src, config_dir)
        self._descriptions = get_setting_descriptions(self._lang, config_dir)
        self._preset_labels = get_preset_labels(self._lang, config_dir)

        self.setWindowTitle(t("settings.title", self._lang, config_dir))
        self.setMinimumSize(520, 420)
        self.resize(680, 720)
        self._font_family = load_bundled_fonts()
        self.setFont(create_app_font(self._font_family, 13))
        self.setPalette(build_qpalette(palette))
        self.setStyleSheet(build_dialog_stylesheet(palette))
        self.result_settings: dict[str, Any] | None = None
        self.hk_rows: dict[str, HotkeyRow] = {}
        self.hk_edits: dict[str, HotkeyEdit] = {}
        self._hk_form_rows: dict[str, int] = {}
        self.cat_rows: list[tuple[QWidget, QLineEdit, QLineEdit, QLineEdit]] = []

        self._build_ui()
        self._populate(self._base_settings)

    def _desc(self, key: str) -> tuple[str, str]:
        entry = self._descriptions.get(key, {})
        return entry.get("label", key), entry.get("tooltip", "")

    def _build_ui(self) -> None:
        is_tr = self._lang.startswith("tr")
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        container = QWidget()
        container.setObjectName("DialogScrollContainer")
        container_layout = QVBoxLayout(container)
        container_layout.setSpacing(12)

        gen_group = QGroupBox(t("settings.sec.appearance", self._lang, self._config_dir), container)
        gen_form = QFormLayout(gen_group)
        gen_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        gen_form.setSpacing(8)

        lbl, tip = self._desc("theme")
        self.theme_cb = QComboBox()
        self.theme_cb.addItems(list(VALID_THEMES))
        self.theme_cb.setToolTip(tip)
        gen_form.addRow(lbl + ":", self.theme_cb)

        lbl, tip = self._desc("language")
        self.lang_cb = QComboBox()
        self.lang_cb.addItems(available_languages(self._config_dir))
        self.lang_cb.setToolTip(tip)
        self.lang_cb.currentTextChanged.connect(lambda _v: self._update_conflict_status())
        gen_form.addRow(lbl + ":", self.lang_cb)

        lbl, tip = self._desc("view_mode")
        self.view_mode_cb = QComboBox()
        self.view_mode_cb.addItems(list(VALID_VIEW_MODES))
        self.view_mode_cb.setToolTip(tip)
        gen_form.addRow(lbl + ":", self.view_mode_cb)

        lbl, tip = self._desc("sort_by")
        self.sort_by_cb = QComboBox()
        self.sort_by_cb.addItems(list(VALID_SORT_BY))
        self.sort_by_cb.setToolTip(tip)
        gen_form.addRow(lbl + ":", self.sort_by_cb)

        lbl, tip = self._desc("strip_emoji")
        self.strip_emoji_chk = QCheckBox(lbl)
        self.strip_emoji_chk.setToolTip(tip)
        gen_form.addRow("", self.strip_emoji_chk)

        lbl, tip = self._desc("last_category")
        self.last_cat_cb = QComboBox()
        self.last_cat_cb.setEditable(True)
        self.last_cat_cb.addItem("ALL")
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

        lbl, tip = self._desc("hide_on_blur")
        self.hide_on_blur_chk = QCheckBox(lbl)
        self.hide_on_blur_chk.setToolTip(tip)
        gen_form.addRow("", self.hide_on_blur_chk)

        lbl, tip = self._desc("start_minimized")
        self.start_min_chk = QCheckBox(lbl)
        self.start_min_chk.setToolTip(tip)
        gen_form.addRow("", self.start_min_chk)

        lbl, tip = self._desc("tray_icon")
        self.tray_chk = QCheckBox(lbl)
        self.tray_chk.setToolTip(tip)
        gen_form.addRow("", self.tray_chk)

        container_layout.addWidget(gen_group)

        paste_group = QGroupBox(t("settings.sec.behavior", self._lang, self._config_dir), container)
        paste_form = QFormLayout(paste_group)
        paste_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
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

        cat_group = QGroupBox(t("settings.sec.categories", self._lang, self._config_dir), container)
        cat_outer = QVBoxLayout(cat_group)
        cat_outer.setSpacing(8)
        cat_hint = QLabel(t("settings.cat.hint", self._lang, self._config_dir), cat_group)
        cat_hint.setProperty("class", "MutedHint")
        cat_hint.setWordWrap(True)
        cat_outer.addWidget(cat_hint)

        self.cat_rows_layout = QVBoxLayout()
        self.cat_rows_layout.setSpacing(6)
        cat_outer.addLayout(self.cat_rows_layout)

        add_cat_row = FlowLayout(margin=0, spacing=6)
        self.new_cat_code = QLineEdit()
        self.new_cat_code.setPlaceholderText(t("settings.cat.code", self._lang, self._config_dir) + " (e.g. 1, WORK)")
        self.new_cat_code.setMinimumWidth(90)
        self.new_cat_label = QLineEdit()
        self.new_cat_label.setPlaceholderText(t("settings.cat.label", self._lang, self._config_dir) + " (e.g. General)")
        self.new_cat_label.setMinimumWidth(110)
        self.new_cat_prefix = QLineEdit()
        self.new_cat_prefix.setPlaceholderText(t("settings.cat.prefix", self._lang, self._config_dir) + " (e.g. L-Win+1)")
        self.new_cat_prefix.setMinimumWidth(110)
        self.add_cat_btn = QPushButton(t("settings.cat.add", self._lang, self._config_dir))
        self.add_cat_btn.clicked.connect(self._on_add_category)
        for w in (self.new_cat_code, self.new_cat_label, self.new_cat_prefix, self.add_cat_btn):
            add_cat_row.addWidget(w)
        cat_outer.addLayout(add_cat_row)
        container_layout.addWidget(cat_group)

        hk_group = QGroupBox(t("settings.sec.hotkeys", self._lang, self._config_dir), container)
        hk_outer = QVBoxLayout(hk_group)
        hk_outer.setSpacing(8)
        _, self._hk_tip = self._desc("hotkeys")
        hk_group.setToolTip(self._hk_tip)

        preset_bar = FlowLayout(margin=0, spacing=6)
        preset_bar.addWidget(QLabel(t("settings.hk.preset", self._lang, self._config_dir) + ":"))
        self.preset_cb = QComboBox()
        self.preset_cb.setMinimumWidth(160)
        for pid in HOTKEY_PRESETS:
            self.preset_cb.addItem(self._preset_labels.get(pid, pid), pid)
        self.preset_cb.activated.connect(self._on_preset_activated)
        self.apply_preset_btn = QPushButton(t("settings.hk.apply_preset", self._lang, self._config_dir))
        self.apply_preset_btn.clicked.connect(self._apply_selected_preset)
        preset_bar.addWidget(self.preset_cb)
        preset_bar.addWidget(self.apply_preset_btn)
        hk_outer.addLayout(preset_bar)

        mod_bar = FlowLayout(margin=0, spacing=6)
        mod_bar.addWidget(QLabel(t("settings.hk.apply_mods", self._lang, self._config_dir) + ":"))
        self.bulk_mod_cb = QComboBox()
        self.bulk_mod_cb.setMinimumWidth(150)
        self.bulk_mod_cb.addItems(list(_MODIFIER_BULK_CHOICES))
        self.apply_mod_btn = QPushButton("Uygula" if is_tr else "Apply")
        self.apply_mod_btn.clicked.connect(self._apply_bulk_modifiers)
        mod_bar.addWidget(self.bulk_mod_cb)
        mod_bar.addWidget(self.apply_mod_btn)
        hk_outer.addLayout(mod_bar)

        self.hk_form = QFormLayout()
        self.hk_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self.hk_form.setSpacing(6)
        hk_outer.addLayout(self.hk_form)

        add_slot_bar = QHBoxLayout()
        self.new_slot_edit = QLineEdit()
        self.new_slot_edit.setPlaceholderText(
            "Yeni yuva adı (ör. 1, WORK, M)" if is_tr else "New slot name (e.g. 1, WORK, M)"
        )
        self.add_slot_btn = QPushButton(t("settings.hk.add_slot", self._lang, self._config_dir))
        self.add_slot_btn.clicked.connect(self._on_add_custom_slot)
        add_slot_bar.addWidget(self.new_slot_edit, 1)
        add_slot_bar.addWidget(self.add_slot_btn)
        hk_outer.addLayout(add_slot_bar)

        self.conflict_label = QLabel("")
        self.conflict_label.setWordWrap(True)
        self.conflict_label.setObjectName("HotkeyConflictLabel")
        hk_outer.addWidget(self.conflict_label)

        container_layout.addWidget(hk_group)

        data_group = QGroupBox(t("settings.sec.advanced", self._lang, self._config_dir), container)
        data_form = QFormLayout(data_group)
        data_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        data_form.setSpacing(8)

        lbl, tip = self._desc("data_path")
        path_row = QHBoxLayout()
        self.data_path_edit = QLineEdit()
        self.data_path_edit.setToolTip(tip)
        browse_btn = QPushButton("Seç…" if is_tr else "Browse…")
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
        data_form.addRow(t("settings.web_port", self._lang, self._config_dir) + ":", self.web_port_spin)

        container_layout.addWidget(data_group)
        container_layout.addStretch()

        scroll.setWidget(container)
        root.addWidget(scroll, 1)

        btn_row = FlowLayout(margin=0, spacing=6)
        help_btn = QPushButton(t("overlay.help", self._lang, self._config_dir))
        help_btn.setIcon(make_svg_icon("help", self._palette.btn_text, size=14))
        help_btn.clicked.connect(self._open_help)
        reset_btn = QPushButton(t("settings.btn.reset", self._lang, self._config_dir))
        reset_btn.setIcon(make_svg_icon("reload", self._palette.btn_text, size=14))
        reset_btn.clicked.connect(self._reset_defaults)
        cancel_btn = QPushButton(t("settings.btn.cancel", self._lang, self._config_dir))
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton(t("settings.btn.save", self._lang, self._config_dir))
        save_btn.setIcon(make_svg_icon("save", self._palette.pill_active_text, size=14))
        save_btn.setObjectName("PrimaryBtn")
        save_btn.clicked.connect(self._save_and_accept)

        btn_row.addWidget(help_btn)
        btn_row.addWidget(reset_btn)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        root.addLayout(btn_row)

    def _clear_category_rows(self) -> None:
        while self.cat_rows_layout.count():
            child = self.cat_rows_layout.takeAt(0)
            w = child.widget() if child is not None else None
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        self.cat_rows.clear()

    def add_category_row(self, code: str, label: str = "", hotkey_prefix: str = "") -> None:
        clean_code = str(code or "").strip().upper()
        if not clean_code or clean_code == "ALL" or not CATEGORY_CODE_RE.fullmatch(clean_code):
            return
        row_w = QWidget(self)
        row_lay = QHBoxLayout(row_w)
        row_lay.setContentsMargins(0, 0, 0, 0)
        row_lay.setSpacing(6)

        ed_code = QLineEdit(clean_code, row_w)
        ed_code.setMinimumWidth(56)
        ed_code.setMaximumWidth(90)
        ed_code.textChanged.connect(lambda _v: self._sync_last_category_choices())

        ed_label = QLineEdit(str(label or clean_code), row_w)
        ed_label.setMinimumWidth(80)

        ed_prefix = QLineEdit(str(hotkey_prefix or ""), row_w)
        ed_prefix.setMinimumWidth(80)

        rm_btn = QPushButton("×", row_w)
        rm_btn.setFixedWidth(28)
        rm_btn.setToolTip(t("settings.cat.remove", self._lang, self._config_dir))

        entry = (row_w, ed_code, ed_label, ed_prefix)
        rm_btn.clicked.connect(lambda _c=False, ent=entry: self._remove_category_row(ent))

        row_lay.addWidget(ed_code)
        row_lay.addWidget(ed_label, 1)
        row_lay.addWidget(ed_prefix, 1)
        row_lay.addWidget(rm_btn)
        self.cat_rows_layout.addWidget(row_w)
        self.cat_rows.append(entry)
        self._sync_last_category_choices()

    def _remove_category_row(self, entry: tuple[QWidget, QLineEdit, QLineEdit, QLineEdit]) -> None:
        if entry in self.cat_rows:
            self.cat_rows.remove(entry)
        row_w = entry[0]
        self.cat_rows_layout.removeWidget(row_w)
        row_w.setParent(None)
        row_w.deleteLater()
        self._sync_last_category_choices()

    def _on_add_category(self) -> None:
        code = self.new_cat_code.text().strip().upper()
        if not code or code == "ALL" or not CATEGORY_CODE_RE.fullmatch(code):
            QMessageBox.warning(
                self,
                "Geçersiz Kategori" if self._lang.startswith("tr") else "Invalid Category",
                "Alfanümerik kategori kodu girin (ör. 1, WORK)."
                if self._lang.startswith("tr")
                else "Enter an alphanumeric category code (e.g. 1, WORK).",
            )
            return
        label = self.new_cat_label.text().strip() or code
        prefix = self.new_cat_prefix.text().strip() or f"L-Win+{code}"
        self.add_category_row(code, label, prefix)
        self.new_cat_code.clear()
        self.new_cat_label.clear()
        self.new_cat_prefix.clear()

    def collect_categories(self) -> list[dict[str, str]]:
        raw: list[dict[str, str]] = []
        for _w, ed_code, ed_label, ed_prefix in self.cat_rows:
            code = ed_code.text().strip().upper()
            if code and code != "ALL" and CATEGORY_CODE_RE.fullmatch(code):
                raw.append(
                    {
                        "code": code,
                        "label": ed_label.text().strip() or code,
                        "hotkey_prefix": ed_prefix.text().strip(),
                    }
                )
        return sanitize_categories(raw)

    def _sync_last_category_choices(self) -> None:
        cur = self.last_cat_cb.currentText().strip().upper() or "ALL"
        choices: list[str] = ["ALL"]
        for cat in self.collect_categories():
            c = cat["code"]
            if c not in choices:
                choices.append(c)
        for cat in self._discovered_categories:
            c = str(cat.get("code", "")).strip().upper()
            if c and c not in choices:
                choices.append(c)
        if cur not in choices:
            choices.append(cur)
        self.last_cat_cb.blockSignals(True)
        self.last_cat_cb.clear()
        self.last_cat_cb.addItems(choices)
        self.last_cat_cb.setCurrentText(cur)
        self.last_cat_cb.blockSignals(False)

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

        if clean_slot == "all":
            label_txt = t("settings.hk.all_slot", self._lang, self._config_dir)
        else:
            label_txt = t("settings.hk.cat_slot", self._lang, self._config_dir, code=clean_slot)
        removable = clean_slot not in _BUILTIN_SLOT_SET
        row_widget = HotkeyRow(
            clean_slot,
            removable=removable,
            language=self._lang,
            config_dir=self._config_dir,
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
        is_tr = self._lang.startswith("tr")
        if not raw_slot or "." in raw_slot:
            QMessageBox.warning(
                self,
                "Geçersiz Yuva" if is_tr else "Invalid Slot",
                "Lütfen geçerli ve noktası bulunmayan bir yuva adı girin (ör. 1, WORK)."
                if is_tr
                else "Enter a valid slot name without dots (e.g. 1, WORK).",
            )
            return
        if raw_slot in self.hk_rows:
            QMessageBox.information(
                self,
                "Mevcut Yuva" if is_tr else "Slot Exists",
                f"'{raw_slot}' yuvası zaten tanımlı." if is_tr else f"Slot '{raw_slot}' already exists.",
            )
            return
        key_hint = raw_slot.upper() if len(raw_slot) == 1 and raw_slot.isalnum() else "K"
        self.add_hotkey_slot(raw_slot, f"Win+Alt+{key_hint}")
        self.new_slot_edit.clear()

    def apply_preset(self, preset_id: str) -> None:
        canon = resolve_preset_name(preset_id)
        active_slots: list[str] = ["all"]
        for s in self.hk_rows:
            if s != "all" and s not in active_slots:
                active_slots.append(s)
        for cat in self.collect_categories():
            if cat["code"] not in active_slots:
                active_slots.append(cat["code"])
        target_map = build_preset_hotkeys(canon, active_slots)
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

    def _effective_language(self) -> str:
        return resolve_language(self.lang_cb.currentText(), self._config_dir)

    def _update_conflict_status(self) -> None:
        hk_map = self._current_hotkeys_map()
        eff_lang = self._effective_language()
        conflicts = detect_hotkey_conflicts(hk_map, language=eff_lang)
        if not conflicts:
            self.conflict_label.setStyleSheet(f"color: {self._palette.success_text}; font-weight: 600;")
            self.conflict_label.setText(t("settings.hk.conflicts_none", self._lang, self._config_dir))
            return
        lines = []
        has_severe = False
        for slot, msgs in conflicts.items():
            combo = hk_map.get(slot, "")
            if any("AltGr" not in m for m in msgs):
                has_severe = True
            lines.append(f"[{slot}: {combo}] {'; '.join(msgs)}")
        color = self._palette.danger_text if has_severe else self._palette.warning_text
        self.conflict_label.setStyleSheet(f"color: {color}; font-weight: 600;")
        self.conflict_label.setText("\n".join(lines))

    def _populate(self, data: dict[str, Any]) -> None:
        self.theme_cb.setCurrentText(str(data.get("theme", "light")))
        self.lang_cb.setCurrentText(str(data.get("language", "auto")))
        self.view_mode_cb.setCurrentText(str(data.get("view_mode", "list")))
        self.sort_by_cb.setCurrentText(str(data.get("sort_by", "order")))
        self.strip_emoji_chk.setChecked(bool(data.get("strip_emoji", False)))
        ws = data.get("window_size") or [720, 520]
        self.width_spin.setValue(int(ws[0]))
        self.height_spin.setValue(int(ws[1]))
        self.hide_on_blur_chk.setChecked(bool(data.get("hide_on_blur", True)))
        self.start_min_chk.setChecked(bool(data.get("start_minimized", False)))
        self.tray_chk.setChecked(bool(data.get("tray_icon", True)))
        self.paste_method_cb.setCurrentText(str(data.get("paste_method", "auto")))
        self.enter_after_chk.setChecked(bool(data.get("enter_after_paste", True)))

        self._clear_category_rows()
        for cat in sanitize_categories(data.get("categories")):
            self.add_category_row(cat["code"], cat["label"], cat["hotkey_prefix"])
        self._sync_last_category_choices()
        self.last_cat_cb.setCurrentText(str(data.get("last_category", "ALL")).strip().upper() or "ALL")

        self._clear_hotkey_rows()
        hotkeys = data.get("hotkeys") or DEFAULT_SETTINGS["hotkeys"]
        self.add_hotkey_slot("all", str(hotkeys.get("all", DEFAULT_HOTKEYS["all"])))
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
        is_tr = self._lang.startswith("tr")
        path, _ = QFileDialog.getOpenFileName(
            self,
            "QuickTextPaste.ini Dosyası Seç" if is_tr else "Select QuickTextPaste.ini File",
            self.data_path_edit.text(),
            "INI Files (*.ini);;All Files (*.*)",
        )
        if path:
            self.data_path_edit.setText(path)

    def _reset_defaults(self) -> None:
        self._base_settings = copy.deepcopy(DEFAULT_SETTINGS)
        self._populate(self._base_settings)

    def _open_help(self) -> None:
        dlg = HelpDialog(
            self._palette,
            initial_tab=0,
            language=self._lang,
            config_dir=self._config_dir,
            parent=self,
        )
        dlg.scroll_to_anchor_text("Ayarlar" if self._lang.startswith("tr") else "Settings")
        dlg.exec()

    def collect_settings(self, base: dict[str, Any] | None = None) -> dict[str, Any]:
        """Collects form values into a sanitized qtp_settings.json dictionary."""
        out = copy.deepcopy(base if base is not None else self._base_settings)
        out["theme"] = self.theme_cb.currentText()
        out["view_mode"] = self.view_mode_cb.currentText()
        out["sort_by"] = self.sort_by_cb.currentText()
        out["strip_emoji"] = self.strip_emoji_chk.isChecked()
        out["categories"] = self.collect_categories()
        out["last_category"] = self.last_cat_cb.currentText().strip().upper() or "ALL"
        out["window_size"] = [self.width_spin.value(), self.height_spin.value()]
        out["language"] = self.lang_cb.currentText()
        out["hide_on_blur"] = self.hide_on_blur_chk.isChecked()
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
        return _sanitize_settings(out, config_dir=self._config_dir)

    def _save_and_accept(self) -> None:
        hk_map = self._current_hotkeys_map()
        is_tr = self._lang.startswith("tr")
        seen_combos: dict[str, str] = {}
        for slot, raw in hk_map.items():
            if not raw:
                continue
            try:
                norm = normalize_hotkey(raw)
            except ValueError as exc:
                QMessageBox.warning(self, "Geçersiz Kısayol" if is_tr else "Invalid Hotkey", f"[{slot}] {exc}")
                return
            if norm in seen_combos:
                QMessageBox.warning(
                    self,
                    "Çift Kısayol Ataması" if is_tr else "Duplicate Hotkey",
                    (
                        f"'{norm}' kısayolu hem '{seen_combos[norm]}' hem de '{slot}' yuvasına atanmış. Kaydetmeden önce benzersiz hale getirin."
                        if is_tr
                        else f"'{norm}' is assigned to both '{seen_combos[norm]}' and '{slot}'. Make them unique before saving."
                    ),
                )
                return
            seen_combos[norm] = slot

        os_conflicts = detect_hotkey_conflicts(hk_map, language=self._effective_language())
        if os_conflicts:
            summary_lines = [
                f"• [{slot}: {hk_map.get(slot, '')}] {'; '.join(msgs)}"
                for slot, msgs in os_conflicts.items()
            ]
            ans = QMessageBox.warning(
                self,
                "Kısayol Çakışması Uyarısı" if is_tr else "Hotkey Conflict Warning",
                (
                    "Uyarı: Seçilen kısayollar işletim sistemi veya masaüstü ortamı ile çakışıyor:\n\n"
                    if is_tr
                    else "Warning: Selected hotkeys conflict with OS or desktop shortcuts:\n\n"
                )
                + "\n".join(summary_lines)
                + ("\n\nYine de kaydetmek istiyor musunuz?" if is_tr else "\n\nSave anyway?"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if ans != QMessageBox.StandardButton.Yes:
                return

        self.result_settings = self.collect_settings()
        self.accept()
