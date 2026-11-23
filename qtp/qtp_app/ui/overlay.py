"""Modern, animasyonlu, klavye öncelikli çapraz platform QTP katman (overlay) arayüzü."""

from __future__ import annotations

import html
from typing import Any, Callable

from PyQt6.QtCore import (
    QAbstractListModel,
    QEasingCurve,
    QEvent,
    QModelIndex,
    QParallelAnimationGroup,
    QPoint,
    QPropertyAnimation,
    QRect,
    QSize,
    Qt,
    QTimer,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QAction,
    QColor,
    QCursor,
    QFont,
    QFontMetrics,
    QGuiApplication,
    QKeySequence,
    QPainter,
    QPainterPath,
    QPen,
    QShortcut,
    QTextDocument,
)
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QSizeGrip,
    QStyledItemDelegate,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from qtp_app.core.engine import format_ini_preview, item_matches_category
from qtp_app.core.logging_setup import get_logger
from qtp_app.core.paster import capture_previous_app
from qtp_app.ui.search import FuzzyMatcher
from qtp_app.ui.theme import (
    ACCENT_CYAN,
    ACCENT_PURPLE,
    ANIMATION_DURATION_MS,
    ANIMATION_SLIDE_OFFSET_PX,
    BADGE_RADIUS,
    CATEGORY_TABS,
    DARK_PALETTE,
    FONT_FAMILY_PRIMARY,
    FONT_SIZE_META,
    FONT_SIZE_TEXT,
    FOOTER_HINTS_TEXT,
    PADDING_HEADER_H,
    PADDING_HEADER_V,
    PADDING_OUTER,
    PADDING_ROW_H,
    PADDING_ROW_V,
    ROW_RADIUS,
    SEARCH_CHIP_TEXT,
    SEARCH_PLACEHOLDER,
    TOAST_DURATION_MS,
    ThemePalette,
    WINDOW_CORNER_RADIUS,
    WINDOW_HEIGHT,
    WINDOW_MIN_HEIGHT,
    WINDOW_MIN_WIDTH,
    WINDOW_WIDTH,
    build_dialog_stylesheet,
    build_overlay_stylesheet,
    create_app_font,
    load_bundled_fonts,
    resolve_palette,
)

logger = get_logger("overlay")


def _extract_badge(keys: str) -> str:
    raw = (keys or "").strip()
    if "+" in raw:
        return raw.rsplit("+", 1)[-1].strip().upper()
    return raw.upper() or "•"


def _matches_category(item: dict[str, Any], category_code: str) -> bool:
    return item_matches_category(item, category_code)


class SnippetListModel(QAbstractListModel):
    """527+ öğeyi anında sanallaştırarak listeleyen Qt veri modeli."""

    ROLE_ITEM = Qt.ItemDataRole.UserRole + 1
    ROLE_MATCHES = Qt.ItemDataRole.UserRole + 2
    ROLE_ORIG_INDEX = Qt.ItemDataRole.UserRole + 3

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._rows: list[tuple[int, dict[str, Any], tuple[int, ...]]] = []

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._rows)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or not (0 <= index.row() < len(self._rows)):
            return None
        orig_idx, item, matches = self._rows[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return str(item.get("text", ""))
        if role == Qt.ItemDataRole.AccessibleTextRole:
            lbl = str(item.get("label", "")).strip()
            grp = str(item.get("group", "")).strip()
            txt = str(item.get("text", "")).strip()
            return f"{grp} - {lbl}: {txt}" if lbl else f"{grp}: {txt}"
        if role == self.ROLE_ITEM:
            return item
        if role == self.ROLE_MATCHES:
            return matches
        if role == self.ROLE_ORIG_INDEX:
            return orig_idx
        return None

    def set_rows(self, rows: list[tuple[int, dict[str, Any], tuple[int, ...]]]) -> None:
        self.beginResetModel()
        self._rows = list(rows)
        self.endResetModel()

    def item_at(self, row: int) -> dict[str, Any] | None:
        if 0 <= row < len(self._rows):
            return self._rows[row][1]
        return None


class SnippetItemDelegate(QStyledItemDelegate):
    """2 satırlı metin, eşleşme vurgulama, kısayol rozeti ve satır içi kopyalama düğmesi çizer."""

    ROW_HEIGHT = 76
    COPY_BTN_WIDTH = 66
    COPY_BTN_HEIGHT = 24
    BADGE_WIDTH = 28
    BADGE_HEIGHT = 24

    def __init__(
        self,
        palette: ThemePalette,
        font_family: str = FONT_FAMILY_PRIMARY,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.palette = palette
        self.font_family = font_family
        self.hovered_row: int = -1

    def set_palette(self, palette: ThemePalette) -> None:
        self.palette = palette

    def copy_button_rect(self, row_rect: QRect) -> QRect:
        """Satır içi 'Kopyala' düğmesinin dikdörtgen alanını döndürür."""
        badge_x = row_rect.right() - PADDING_ROW_H - self.BADGE_WIDTH
        copy_x = badge_x - 8 - self.COPY_BTN_WIDTH
        copy_y = row_rect.top() + (row_rect.height() - self.COPY_BTN_HEIGHT) // 2
        return QRect(copy_x, copy_y, self.COPY_BTN_WIDTH, self.COPY_BTN_HEIGHT)

    def sizeHint(self, option: Any, index: QModelIndex) -> QSize:
        return QSize(option.rect.width() or 600, self.ROW_HEIGHT)

    def _build_highlighted_html(self, display_text: str, matched_indices: tuple[int, ...]) -> str:
        if not matched_indices:
            return html.escape(display_text)
        match_set = set(matched_indices)
        parts: list[str] = []
        bg = self.palette.highlight_bg
        fg = self.palette.highlight_text
        for idx, ch in enumerate(display_text):
            esc = html.escape(ch)
            if idx in match_set:
                parts.append(
                    f'<span style="background-color:{bg};color:{fg};font-weight:700;">{esc}</span>'
                )
            else:
                parts.append(esc)
        return "".join(parts)

    def paint(self, painter: QPainter, option: Any, index: QModelIndex) -> None:
        item = index.data(SnippetListModel.ROLE_ITEM)
        if not isinstance(item, dict):
            return
        matched_indices: tuple[int, ...] = index.data(SnippetListModel.ROLE_MATCHES) or ()

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        card_rect = option.rect.adjusted(2, 3, -2, -3)
        is_selected = bool(option.state & QStyle.StateFlag.State_Selected)
        is_hovered = bool(option.state & QStyle.StateFlag.State_MouseOver) or (
            index.row() == self.hovered_row
        )

        path = QPainterPath()
        path.addRoundedRect(
            float(card_rect.x()),
            float(card_rect.y()),
            float(card_rect.width()),
            float(card_rect.height()),
            float(ROW_RADIUS),
            float(ROW_RADIUS),
        )
        if is_selected:
            painter.fillPath(path, QColor(self.palette.selected_bg))
            pen = QPen(QColor(self.palette.selected_border), 1.4)
            painter.setPen(pen)
            painter.drawPath(path)
        elif is_hovered:
            painter.fillPath(path, QColor(self.palette.hover_bg))
        else:
            painter.fillPath(path, QColor(self.palette.surface))

        badge_rect = QRect(
            card_rect.right() - PADDING_ROW_H - self.BADGE_WIDTH,
            card_rect.top() + (card_rect.height() - self.BADGE_HEIGHT) // 2,
            self.BADGE_WIDTH,
            self.BADGE_HEIGHT,
        )
        badge_path = QPainterPath()
        badge_path.addRoundedRect(
            float(badge_rect.x()),
            float(badge_rect.y()),
            float(badge_rect.width()),
            float(badge_rect.height()),
            float(BADGE_RADIUS),
            float(BADGE_RADIUS),
        )
        painter.fillPath(badge_path, QColor(self.palette.badge_bg))
        badge_font = create_app_font(self.font_family, FONT_SIZE_META, bold=True)
        painter.setFont(badge_font)
        painter.setPen(QColor(self.palette.badge_text))
        painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, _extract_badge(str(item.get("keys", ""))))

        right_reserved = self.BADGE_WIDTH + PADDING_ROW_H + 14
        if is_hovered or is_selected:
            copy_rect = self.copy_button_rect(option.rect)
            copy_path = QPainterPath()
            copy_path.addRoundedRect(
                float(copy_rect.x()),
                float(copy_rect.y()),
                float(copy_rect.width()),
                float(copy_rect.height()),
                float(BADGE_RADIUS),
                float(BADGE_RADIUS),
            )
            painter.fillPath(copy_path, QColor(self.palette.pill_bg))
            painter.setPen(QColor(self.palette.text_secondary))
            painter.setFont(create_app_font(self.font_family, FONT_SIZE_META))
            painter.drawText(copy_rect, Qt.AlignmentFlag.AlignCenter, "Kopyala")
            right_reserved += self.COPY_BTN_WIDTH + 8

        text_left = card_rect.left() + PADDING_ROW_H
        text_width = max(120, card_rect.width() - PADDING_ROW_H - right_reserved)
        main_rect = QRect(
            text_left,
            card_rect.top() + PADDING_ROW_V - 2,
            text_width,
            40,
        )

        raw_text = str(item.get("text", "")).replace("\r\n", " ").replace("\n", " ")
        text_font = create_app_font(self.font_family, FONT_SIZE_TEXT)
        fm = QFontMetrics(text_font)
        max_chars = max(40, int((text_width * 1.95) / max(6, fm.averageCharWidth())))
        clipped = raw_text[: max_chars - 1] + "…" if len(raw_text) > max_chars else raw_text

        doc = QTextDocument()
        doc.setDocumentMargin(0)
        doc.setDefaultFont(text_font)
        doc.setTextWidth(float(text_width))
        html_body = self._build_highlighted_html(clipped, matched_indices)
        doc.setHtml(
            f'<div style="color:{self.palette.text_primary};line-height:1.3;">{html_body}</div>'
        )
        painter.save()
        painter.translate(float(main_rect.left()), float(main_rect.top()))
        painter.setClipRect(0, 0, main_rect.width(), main_rect.height())
        doc.drawContents(painter)
        painter.restore()

        meta_rect = QRect(
            text_left,
            card_rect.bottom() - 22,
            text_width,
            18,
        )
        grp = str(item.get("group", "Genel")).strip()
        lbl = str(item.get("label", "")).strip()
        meta_text = f"{grp}  ·  {lbl}" if lbl else grp
        meta_font = create_app_font(self.font_family, FONT_SIZE_META)
        painter.setFont(meta_font)
        painter.setPen(QColor(self.palette.text_muted))
        elided_meta = QFontMetrics(meta_font).elidedText(
            meta_text, Qt.TextElideMode.ElideRight, meta_rect.width()
        )
        painter.drawText(meta_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, elided_meta)

        painter.restore()


class SnippetListView(QListView):
    """Tıklama, Shift+Tıklama, satır içi kopyala düğmesi ve sağ tık menüsünü destekleyen liste."""

    item_paste_requested = pyqtSignal(int)
    item_copy_requested = pyqtSignal(int)
    item_context_requested = pyqtSignal(int, QPoint)

    def __init__(self, delegate: SnippetItemDelegate, parent: QWidget | None = None):
        super().__init__(parent)
        self._delegate = delegate
        self.setMouseTracking(True)

    def mouseMoveEvent(self, event: Any) -> None:
        idx = self.indexAt(event.pos())
        new_row = idx.row() if idx.isValid() else -1
        if new_row != self._delegate.hovered_row:
            self._delegate.hovered_row = new_row
            self.viewport().update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event: Any) -> None:
        if self._delegate.hovered_row != -1:
            self._delegate.hovered_row = -1
            self.viewport().update()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event: Any) -> None:
        idx = self.indexAt(event.pos())
        if idx.isValid():
            self.setCurrentIndex(idx)
            row = idx.row()
            if event.button() == Qt.MouseButton.RightButton:
                self.item_copy_requested.emit(row)
                self.item_context_requested.emit(row, event.globalPosition().toPoint())
                return
            if event.button() == Qt.MouseButton.LeftButton:
                row_rect = self.visualRect(idx)
                if self._delegate.copy_button_rect(row_rect).contains(event.pos()):
                    self.item_copy_requested.emit(row)
                    return
                if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                    self.item_copy_requested.emit(row)
                    return
                self.item_paste_requested.emit(row)
                return
        super().mouseReleaseEvent(event)


class IniSnippetViewerDialog(QDialog):
    """Seçili kaydın QuickTextPaste.ini içindeki ham satırlarını gösterir."""

    def __init__(
        self,
        item: dict[str, Any],
        index: int,
        ini_path: str,
        palette: ThemePalette,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("INI Kaydını Göster")
        self.resize(560, 320)
        self.setStyleSheet(build_dialog_stylesheet(palette))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        info = QLabel(f"Kaynak dosya: {ini_path}")
        info.setProperty("class", "MutedHint")
        layout.addWidget(info)

        preview_lines = format_ini_preview(item, index)
        viewer = QPlainTextEdit()
        viewer.setReadOnly(True)
        viewer.setPlainText(preview_lines)
        layout.addWidget(viewer)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("Kapat")
        close_btn.setObjectName("PrimaryBtn")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)


class OverlayWindow(QWidget):
    """
    Modern, çerçevesiz, animasyonlu ve klavye öncelikli QTP hızlı yapıştırma katmanı.
    Tüm işletim sistemlerinde birebir aynı görsel ızgara, renk, yazı tipi ve kısayolları sunar.
    """

    paste_triggered = pyqtSignal(dict)
    copy_triggered = pyqtSignal(dict)
    settings_requested = pyqtSignal()
    help_requested = pyqtSignal()
    window_resized = pyqtSignal(int, int)

    def __init__(
        self,
        items: list[dict[str, Any]] | None = None,
        *,
        theme: str = "dark",
        window_size: tuple[int, int] = (WINDOW_WIDTH, WINDOW_HEIGHT),
        last_category: str = "ALL",
        last_category_by_hotkey: dict[str, str] | None = None,
        ini_path: str = "QuickTextPaste.ini",
        on_paste: Callable[[dict[str, Any], Any], None] | None = None,
        on_copy: Callable[[dict[str, Any]], None] | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._items: list[dict[str, Any]] = list(items or [])
        self._theme_setting = theme
        self._ini_path = ini_path
        self._on_paste_cb = on_paste
        self._on_copy_cb = on_copy
        self._active_category = (last_category or "ALL").upper()
        self._last_cat_by_hotkey: dict[str, str] = dict(last_category_by_hotkey or {})
        self._active_hotkey_trigger: str = "all"
        self._previous_app: Any = None
        self._matcher = FuzzyMatcher()
        self._font_family = load_bundled_fonts()
        self._palette = resolve_palette(theme, os_is_dark=self._detect_os_dark())

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAccessibleName("QTP Hızlı Yapıştırma Katmanı")
        self.setAccessibleDescription("Kısayolla tetiklenen hazır cevap arama ve yapıştırma penceresi.")

        w = max(WINDOW_MIN_WIDTH, int(window_size[0] if len(window_size) >= 1 else WINDOW_WIDTH))
        h = max(WINDOW_MIN_HEIGHT, int(window_size[1] if len(window_size) >= 2 else WINDOW_HEIGHT))
        self.setMinimumSize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self.resize(w, h)

        self._anim_group: QParallelAnimationGroup | None = None
        self._toast_timer = QTimer(self)
        self._toast_timer.setSingleShot(True)
        self._toast_timer.timeout.connect(self._fade_out_toast)
        self._toast_anim: QPropertyAnimation | None = None

        self._build_ui()
        self._apply_theme()
        self._bind_shortcuts()
        self.set_items(self._items)

    def _detect_os_dark(self) -> bool:
        try:
            hints = QGuiApplication.styleHints()
            color_scheme_enum = getattr(Qt, "ColorScheme", None)
            if hints is not None and hasattr(hints, "colorScheme") and color_scheme_enum is not None:
                return hints.colorScheme() != color_scheme_enum.Light
        except Exception:
            pass
        return True

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)

        self.card = QFrame(self)
        self.card.setObjectName("OverlayCard")
        shadow = QGraphicsDropShadowEffect(self.card)
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 140))
        self.card.setGraphicsEffect(shadow)
        outer.addWidget(self.card)

        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(PADDING_OUTER, PADDING_OUTER, PADDING_OUTER, 10)
        card_layout.setSpacing(10)

        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        search_wrap = QFrame(self.card)
        search_wrap_layout = QHBoxLayout(search_wrap)
        search_wrap_layout.setContentsMargins(0, 0, 0, 0)
        search_wrap_layout.setSpacing(0)

        self.search_input = QLineEdit(search_wrap)
        self.search_input.setObjectName("SearchInput")
        self.search_input.setPlaceholderText(SEARCH_PLACEHOLDER)
        self.search_input.setFont(create_app_font(self._font_family, FONT_SIZE_TEXT))
        self.search_input.setAccessibleName("Hazır Cevap Arama Kutusu")
        self.search_input.setAccessibleDescription("Metin, kategori veya etiket içinde bulanık arama yapar.")
        self.search_input.textChanged.connect(self._refresh_list)

        chip_layout = QHBoxLayout(self.search_input)
        chip_layout.setContentsMargins(0, 0, 10, 0)
        chip_layout.addStretch()
        self.shortcut_chip = QLabel(SEARCH_CHIP_TEXT, self.search_input)
        self.shortcut_chip.setObjectName("ShortcutChip")
        chip_layout.addWidget(self.shortcut_chip)

        search_wrap_layout.addWidget(self.search_input)
        top_row.addWidget(search_wrap, 1)

        self.help_btn = QPushButton("Yardım (F1)", self.card)
        self.help_btn.setObjectName("HeaderActionBtn")
        self.help_btn.setToolTip("Türkçe kullanım kılavuzu ve kısayolları aç (F1)")
        self.help_btn.clicked.connect(self.help_requested.emit)
        top_row.addWidget(self.help_btn)

        self.settings_btn = QPushButton("Ayarlar", self.card)
        self.settings_btn.setObjectName("HeaderActionBtn")
        self.settings_btn.setToolTip("Uygulama ve kısayol ayarlarını aç (Ctrl+,)")
        self.settings_btn.clicked.connect(self.settings_requested.emit)
        top_row.addWidget(self.settings_btn)

        card_layout.addLayout(top_row)

        pills_row = QHBoxLayout()
        pills_row.setSpacing(6)
        self.category_buttons: dict[str, QPushButton] = {}
        for code, title, _prefix in CATEGORY_TABS:
            btn = QPushButton(title, self.card)
            btn.setProperty("class", "CategoryPill")
            btn.setProperty("category_code", code)
            btn.setProperty("item_count", 0)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setAccessibleName(f"Kategori: {title}")
            btn.clicked.connect(lambda _chk=False, c=code: self.set_category(c))
            pills_row.addWidget(btn)
            self.category_buttons[code] = btn
        pills_row.addStretch()
        card_layout.addLayout(pills_row)

        self.list_model = SnippetListModel(self)
        self.list_delegate = SnippetItemDelegate(self._palette, self._font_family, self)
        self.list_view = SnippetListView(self.list_delegate, self.card)
        self.list_view.setObjectName("SnippetList")
        self.list_view.setModel(self.list_model)
        self.list_view.setItemDelegate(self.list_delegate)
        self.list_view.setUniformItemSizes(True)
        self.list_view.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.list_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list_view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.list_view.setAccessibleName("Hazır Cevap Listesi")
        self.search_input.installEventFilter(self)
        self.list_view.installEventFilter(self)
        self.list_view.item_paste_requested.connect(self.paste_row)
        self.list_view.item_copy_requested.connect(self.copy_row)
        self.list_view.item_context_requested.connect(self._open_context_menu)
        card_layout.addWidget(self.list_view, 1)

        footer = QFrame(self.card)
        footer.setObjectName("FooterBar")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(2, 8, 2, 0)
        footer_layout.setSpacing(8)

        self.footer_hints = QLabel(FOOTER_HINTS_TEXT, footer)
        self.footer_hints.setObjectName("FooterHints")
        footer_layout.addWidget(self.footer_hints)
        footer_layout.addStretch()

        self.count_label = QLabel("0 kayıt", footer)
        self.count_label.setObjectName("ItemCountLabel")
        footer_layout.addWidget(self.count_label)

        self.size_grip = QSizeGrip(footer)
        self.size_grip.setFixedSize(14, 14)
        footer_layout.addWidget(self.size_grip)

        card_layout.addWidget(footer)

        self.toast_label = QLabel("", self.card)
        self.toast_label.setObjectName("ToastLabel")
        self.toast_label.hide()
        self._toast_opacity = QGraphicsOpacityEffect(self.toast_label)
        self._toast_opacity.setOpacity(1.0)
        self.toast_label.setGraphicsEffect(self._toast_opacity)

    def _bind_shortcuts(self) -> None:
        for seq in ("Ctrl+K", "Meta+K"):
            sc = QShortcut(QKeySequence(seq), self)
            sc.activated.connect(self.focus_search)
        for seq in ("Ctrl+,", "Meta+,"):
            sc = QShortcut(QKeySequence(seq), self)
            sc.activated.connect(self.settings_requested.emit)
        sc_help = QShortcut(QKeySequence(Qt.Key.Key_F1), self)
        sc_help.activated.connect(self.help_requested.emit)
        sc_esc = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        sc_esc.activated.connect(self.hide_overlay)

    def _apply_theme(self) -> None:
        self._palette = resolve_palette(self._theme_setting, os_is_dark=self._detect_os_dark())
        self.setStyleSheet(build_overlay_stylesheet(self._palette, translucent=False))
        self.list_delegate.set_palette(self._palette)
        self.list_view.viewport().update()
        self._update_pill_styles()

    def apply_settings(
        self,
        *,
        theme: str | None = None,
        ini_path: str | None = None,
    ) -> None:
        if theme is not None:
            self._theme_setting = theme
        if ini_path is not None:
            self._ini_path = ini_path
        self._apply_theme()

    def set_items(self, items: list[dict[str, Any]]) -> None:
        self._items = list(items)
        self._update_pill_counts()
        self._refresh_list()

    def _update_pill_counts(self) -> None:
        for code, title, _prefix in CATEGORY_TABS:
            btn = self.category_buttons[code]
            count = sum(1 for it in self._items if _matches_category(it, code))
            btn.setProperty("item_count", count)
            btn.setText(f"{title} ({count})")
            btn.setToolTip(f"{title} kategorisinde {count} kayıt")

    def _update_pill_styles(self) -> None:
        for code, btn in self.category_buttons.items():
            btn.setProperty("active", "true" if code == self._active_category else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def set_category(self, category_code: str, *, remember: bool = True) -> None:
        norm = (category_code or "ALL").strip().upper()
        if norm not in self.category_buttons:
            norm = "ALL"
        self._active_category = norm
        if remember:
            self._last_cat_by_hotkey[self._active_hotkey_trigger] = norm
        self._update_pill_styles()
        self._refresh_list()

    @property
    def active_category(self) -> str:
        return self._active_category

    @property
    def last_category_by_hotkey(self) -> dict[str, str]:
        return dict(self._last_cat_by_hotkey)

    def _refresh_list(self) -> None:
        cat_items = [it for it in self._items if _matches_category(it, self._active_category)]
        query = self.search_input.text()
        rows = self._matcher.filter_items(query, cat_items)
        self.list_model.set_rows(rows)
        self.count_label.setText(f"{len(rows)} / {len(self._items)} kayıt")
        if rows:
            first = self.list_model.index(0, 0)
            self.list_view.setCurrentIndex(first)
            self.list_view.scrollTo(first)

    def focus_search(self) -> None:
        self.search_input.setFocus(Qt.FocusReason.ActiveWindowFocusReason)
        self.search_input.selectAll()

    def selected_row(self) -> int:
        idx = self.list_view.currentIndex()
        if idx.isValid():
            return idx.row()
        return 0 if self.list_model.rowCount() > 0 else -1

    def move_selection(self, delta: int) -> None:
        total = self.list_model.rowCount()
        if total <= 0:
            return
        cur = self.selected_row()
        nxt = max(0, min(total - 1, cur + delta))
        idx = self.list_model.index(nxt, 0)
        self.list_view.setCurrentIndex(idx)
        self.list_view.scrollTo(idx)

    def paste_row(self, row: int | None = None) -> None:
        target_row = self.selected_row() if row is None else row
        item = self.list_model.item_at(target_row)
        if not item:
            return
        prev = self._previous_app
        self.hide_overlay(animate=False)
        self.paste_triggered.emit(item)
        res = self._on_paste_cb(item, prev) if self._on_paste_cb is not None else None
        msg = res.message if (res is not None and hasattr(res, "message")) else "Yapıştırıldı ✔"
        self.show_toast(msg)

    def copy_row(self, row: int | None = None) -> None:
        target_row = self.selected_row() if row is None else row
        item = self.list_model.item_at(target_row)
        if not item:
            return
        self.copy_triggered.emit(item)
        res = self._on_copy_cb(item) if self._on_copy_cb is not None else None
        msg = res.message if (res is not None and hasattr(res, "message")) else "Panoya kopyalandı ✔"
        self.show_toast(msg)

    def _open_context_menu(self, row: int, global_pos: QPoint) -> None:
        item = self.list_model.item_at(row)
        if not item:
            return
        menu = QMenu(self)
        act_paste = QAction("Yapıştır", menu)
        act_copy = QAction("Kopyala", menu)
        act_ini = QAction("INI'de Göster", menu)
        act_help = QAction("Yardım", menu)

        act_paste.triggered.connect(lambda: self.paste_row(row))
        act_copy.triggered.connect(lambda: self.copy_row(row))
        act_ini.triggered.connect(lambda: self._show_ini_preview(item, row))
        act_help.triggered.connect(self.help_requested.emit)

        menu.addAction(act_paste)
        menu.addAction(act_copy)
        menu.addSeparator()
        menu.addAction(act_ini)
        menu.addAction(act_help)
        menu.exec(global_pos)

    def _show_ini_preview(self, item: dict[str, Any], row: int) -> None:
        dlg = IniSnippetViewerDialog(item, row, self._ini_path, self._palette, self)
        dlg.exec()

    def eventFilter(self, obj: Any, event: QEvent) -> bool:
        list_widget = getattr(self, "list_view", None)
        search_widget = getattr(self, "search_input", None)
        if obj in (search_widget, list_widget) and event.type() == QEvent.Type.KeyPress:
            key = event.key()
            mods = event.modifiers()
            if key == Qt.Key.Key_Down:
                self.move_selection(1)
                return True
            if key == Qt.Key.Key_Up:
                self.move_selection(-1)
                return True
            if key == Qt.Key.Key_PageDown:
                self.move_selection(6)
                return True
            if key == Qt.Key.Key_PageUp:
                self.move_selection(-6)
                return True
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if mods & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier):
                    self.copy_row()
                else:
                    self.paste_row()
                return True
            if key == Qt.Key.Key_Escape:
                self.hide_overlay()
                return True
        return super().eventFilter(obj, event)

    def center_on_active_screen(self) -> QPoint:
        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        if screen is None:
            return self.pos()
        avail = screen.availableGeometry()
        x = avail.x() + (avail.width() - self.width()) // 2
        y = avail.y() + (avail.height() - self.height()) // 2
        self.move(x, y)
        return QPoint(x, y)

    def show_overlay(
        self,
        *,
        category: str | None = None,
        hotkey_key: str | None = None,
        animate: bool = True,
        previous_app: Any = None,
    ) -> None:
        """Katmanı aktif ekranda ortalayarak 180 ms animasyonla açar."""
        self._previous_app = previous_app if previous_app is not None else capture_previous_app()

        trig = (hotkey_key or category or "all").strip()
        self._active_hotkey_trigger = trig
        if category is not None:
            chosen = self._last_cat_by_hotkey.get(trig, category)
            self.set_category(chosen, remember=False)
        else:
            self.set_category(self._last_cat_by_hotkey.get(trig, self._active_category), remember=False)

        target_pos = self.center_on_active_screen()
        self.search_input.clear()

        if self._anim_group is not None:
            self._anim_group.stop()

        if animate:
            start_pos = QPoint(target_pos.x(), target_pos.y() + ANIMATION_SLIDE_OFFSET_PX)
            self.move(start_pos)
            self.setWindowOpacity(0.0)
            self.show()
            self.raise_()
            self.activateWindow()
            self.focus_search()

            fade = QPropertyAnimation(self, b"windowOpacity")
            fade.setDuration(ANIMATION_DURATION_MS)
            fade.setStartValue(0.0)
            fade.setEndValue(1.0)
            fade.setEasingCurve(QEasingCurve.Type.OutCubic)

            slide = QPropertyAnimation(self, b"pos")
            slide.setDuration(ANIMATION_DURATION_MS)
            slide.setStartValue(start_pos)
            slide.setEndValue(target_pos)
            slide.setEasingCurve(QEasingCurve.Type.OutCubic)

            group = QParallelAnimationGroup(self)
            group.addAnimation(fade)
            group.addAnimation(slide)
            self._anim_group = group
            group.start()
        else:
            self.setWindowOpacity(1.0)
            self.show()
            self.raise_()
            self.activateWindow()
            QApplication.setActiveWindow(self)
            self.focus_search()

        logger.info("Katman açıldı (kategori=%s, kayıt=%d).", self._active_category, self.list_model.rowCount())

    def hide_overlay(self, *, animate: bool = True) -> None:
        """Katmanı 180 ms animasyonla kapatır."""
        if self._anim_group is not None:
            self._anim_group.stop()
        if not self.isVisible():
            return
        if not animate:
            self.hide()
            return

        cur_pos = self.pos()
        end_pos = QPoint(cur_pos.x(), cur_pos.y() + ANIMATION_SLIDE_OFFSET_PX)

        fade = QPropertyAnimation(self, b"windowOpacity")
        fade.setDuration(ANIMATION_DURATION_MS)
        fade.setStartValue(self.windowOpacity())
        fade.setEndValue(0.0)
        fade.setEasingCurve(QEasingCurve.Type.InCubic)

        slide = QPropertyAnimation(self, b"pos")
        slide.setDuration(ANIMATION_DURATION_MS)
        slide.setStartValue(cur_pos)
        slide.setEndValue(end_pos)
        slide.setEasingCurve(QEasingCurve.Type.InCubic)

        group = QParallelAnimationGroup(self)
        group.addAnimation(fade)
        group.addAnimation(slide)
        group.finished.connect(self.hide)
        self._anim_group = group
        group.start()

    def show_toast(self, message: str, duration_ms: int = TOAST_DURATION_MS) -> None:
        """Sağ alt köşede kısa süreli bildirim balonu gösterir."""
        self.toast_label.setText(message)
        self.toast_label.adjustSize()
        self._position_toast()
        self._toast_opacity.setOpacity(1.0)
        self.toast_label.show()
        self.toast_label.raise_()
        self._toast_timer.start(duration_ms)

    def _position_toast(self) -> None:
        margin = 18
        tw = self.toast_label.width()
        th = self.toast_label.height()
        x = max(12, self.card.width() - tw - margin)
        y = max(12, self.card.height() - th - 42)
        self.toast_label.move(x, y)

    def _fade_out_toast(self) -> None:
        anim = QPropertyAnimation(self._toast_opacity, b"opacity")
        anim.setDuration(ANIMATION_DURATION_MS)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.finished.connect(self.toast_label.hide)
        self._toast_anim = anim
        anim.start()

    def resizeEvent(self, event: Any) -> None:
        super().resizeEvent(event)
        if self.toast_label.isVisible():
            self._position_toast()
        self.window_resized.emit(self.width(), self.height())
