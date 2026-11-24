"""Modern, animasyonlu, klavye öncelikli çapraz platform QTP katman (overlay) arayüzü."""

from __future__ import annotations

from collections import OrderedDict
import html
from typing import Any, Callable

from PyQt6.QtCore import (
    QAbstractListModel,
    QAbstractTableModel,
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
    QBrush,
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
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListView,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizeGrip,
    QSizePolicy,
    QStackedWidget,
    QStyledItemDelegate,
    QStyle,
    QTableView,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from qtp_app.core.engine import format_ini_preview, is_note_item, item_matches_category, strip_emojis
from qtp_app.core.logging_setup import get_logger
from qtp_app.core.paster import capture_previous_app, copy_to_clipboard, is_posix_desktop
from qtp_app.ui.flow_layout import FlowLayout
from qtp_app.ui.icons import make_svg_icon
from qtp_app.ui.search import FuzzyMatcher, tr_lower
from qtp_app.ui.theme import (
    ANIMATION_DURATION_MS,
    ANIMATION_SLIDE_OFFSET_PX,
    BADGE_RADIUS,
    CATEGORY_TABS,
    FONT_FAMILY_PRIMARY,
    FONT_SIZE_META,
    FONT_SIZE_TEXT,
    FOOTER_HINTS_TEXT,
    PADDING_HEADER_H,
    PADDING_HEADER_V,
    PADDING_OUTER,
    PADDING_ROW_H,
    PADDING_ROW_V,
    QUICK_EMOJIS,
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
    build_qpalette,
    create_app_font,
    load_bundled_fonts,
    parse_qcolor,
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


class SnippetTableModel(QAbstractTableModel):
    """Tablo görünümü için hazır cevap veri modeli."""

    HEADERS = ("Seç", "Fav", "Kısayol", "Grup", "Etiket", "Hazır Cevap", "Kullanım")

    def __init__(self, checked_keys: set[str], parent: QWidget | None = None):
        super().__init__(parent)
        self._rows: list[tuple[int, dict[str, Any], tuple[int, ...]]] = []
        self._checked_keys = checked_keys

    def set_rows(self, rows: list[tuple[int, dict[str, Any], tuple[int, ...]]]) -> None:
        self.beginResetModel()
        self._rows = list(rows)
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self.HEADERS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            if 0 <= section < len(self.HEADERS):
                return self.HEADERS[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or not (0 <= index.row() < len(self._rows)):
            return None
        item = self._rows[index.row()][1]
        col = index.column()
        if role == Qt.ItemDataRole.TextAlignmentRole and col in (0, 1, 2, 6):
            return int(Qt.AlignmentFlag.AlignCenter)
        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return "☑" if str(item.get("raw_key", "")) in self._checked_keys else "☐"
            if col == 1:
                return "★" if bool(item.get("favorite", False)) else "☆"
            if col == 2:
                return _extract_badge(str(item.get("keys", "")))
            if col == 3:
                return str(item.get("group", "Genel"))
            if col == 4:
                return str(item.get("label", "")) or "-"
            if col == 5:
                return str(item.get("text", "")).replace("\r\n", " ").replace("\n", " ")
            if col == 6:
                return str(int(item.get("copyCount", 0) or 0))
        return None

    def item_at(self, row: int) -> dict[str, Any] | None:
        if 0 <= row < len(self._rows):
            return self._rows[row][1]
        return None


class SnippetItemDelegate(QStyledItemDelegate):
    """2 satırlı metin, seçim kutusu, favori yıldızı, eşleşme vurgulama ve rozet çizer."""

    ROW_HEIGHT = 76
    GRID_WIDTH = 216
    GRID_HEIGHT = 108
    COPY_BTN_WIDTH = 66
    COPY_BTN_HEIGHT = 24
    BADGE_WIDTH = 28
    BADGE_HEIGHT = 24
    _DOC_CACHE_MAX = 256

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
        self.checked_keys: set[str] = set()
        self.grid_mode: bool = False
        self._doc_cache: OrderedDict[tuple[Any, ...], QTextDocument] = OrderedDict()
        self._build_font_cache()

    def _build_font_cache(self) -> None:
        self._text_font = create_app_font(self.font_family, FONT_SIZE_TEXT)
        self._bold_text_font = create_app_font(self.font_family, FONT_SIZE_TEXT, bold=True)
        self._meta_font = create_app_font(self.font_family, FONT_SIZE_META)
        self._badge_font = create_app_font(self.font_family, FONT_SIZE_META, bold=True)
        self._text_fm = QFontMetrics(self._text_font)
        self._meta_fm = QFontMetrics(self._meta_font)

    def set_palette(self, palette: ThemePalette) -> None:
        self.palette = palette
        self._doc_cache.clear()

    def check_box_rect(self, row_rect: QRect) -> QRect:
        card_rect = row_rect.adjusted(2, 3, -2, -3)
        if self.grid_mode:
            return QRect(card_rect.left() + 8, card_rect.top() + 8, 16, 16)
        return QRect(card_rect.left() + 8, card_rect.top() + (card_rect.height() - 16) // 2, 16, 16)

    def star_rect(self, row_rect: QRect) -> QRect:
        chk = self.check_box_rect(row_rect)
        return QRect(chk.right() + 6, chk.top() - 2, 18, 20)

    def copy_button_visible(self, option: Any, index: QModelIndex) -> bool:
        """Liste satırında 'Kopyala' düğmesinin o an görünür olup olmadığını döndürür."""
        if self.grid_mode:
            return False
        return (
            bool(option.state & QStyle.StateFlag.State_Selected)
            or bool(option.state & QStyle.StateFlag.State_MouseOver)
            or (index.row() == self.hovered_row)
        )

    def copy_button_rect(self, row_rect: QRect) -> QRect:
        """Satır içi 'Kopyala' düğmesinin dikdörtgen alanını döndürür (kart görünümünde boş QRect)."""
        if self.grid_mode:
            return QRect()
        badge_x = row_rect.right() - PADDING_ROW_H - self.BADGE_WIDTH
        copy_x = badge_x - 8 - self.COPY_BTN_WIDTH
        copy_y = row_rect.top() + (row_rect.height() - self.COPY_BTN_HEIGHT) // 2
        return QRect(copy_x, copy_y, self.COPY_BTN_WIDTH, self.COPY_BTN_HEIGHT)

    def sizeHint(self, option: Any, index: QModelIndex) -> QSize:
        if self.grid_mode:
            return QSize(self.GRID_WIDTH, self.GRID_HEIGHT)
        return QSize(option.rect.width() or 600, self.ROW_HEIGHT)

    def _get_cached_doc(
        self,
        clipped: str,
        matched_indices: tuple[int, ...],
        text_width: int,
    ) -> QTextDocument:
        key = (
            clipped,
            matched_indices,
            text_width,
            self.palette.name,
            self.palette.text_primary,
            self.palette.highlight_bg,
            self.palette.highlight_text,
        )
        doc = self._doc_cache.get(key)
        if doc is not None:
            self._doc_cache.move_to_end(key)
            return doc
        doc = QTextDocument()
        doc.setDocumentMargin(0)
        doc.setDefaultFont(self._text_font)
        doc.setTextWidth(float(text_width))
        html_body = self._build_highlighted_html(clipped, matched_indices)
        doc.setHtml(
            f'<div style="color:{self.palette.text_primary};line-height:1.3;">{html_body}</div>'
        )
        self._doc_cache[key] = doc
        if len(self._doc_cache) > self._DOC_CACHE_MAX:
            self._doc_cache.popitem(last=False)
        return doc

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
        raw_key = str(item.get("raw_key", ""))
        is_checked = raw_key in self.checked_keys
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
        painter.fillPath(path, parse_qcolor(self.palette.card_bg))
        if is_selected or is_checked:
            if is_selected:
                painter.fillPath(path, parse_qcolor(self.palette.card_selected))
            pen = QPen(parse_qcolor(self.palette.selected_border), 1.5)
            painter.setPen(pen)
            painter.drawPath(path)
        elif is_hovered:
            painter.fillPath(path, parse_qcolor(self.palette.card_hover))
            pen = QPen(parse_qcolor(self.palette.border), 1.0)
            painter.setPen(pen)
            painter.drawPath(path)
        else:
            pen = QPen(parse_qcolor(self.palette.border), 1.0)
            painter.setPen(pen)
            painter.drawPath(path)

        chk_rect = self.check_box_rect(option.rect)
        chk_path = QPainterPath()
        chk_path.addRoundedRect(
            float(chk_rect.x()),
            float(chk_rect.y()),
            float(chk_rect.width()),
            float(chk_rect.height()),
            4.0,
            4.0,
        )
        if is_checked:
            painter.fillPath(chk_path, parse_qcolor(self.palette.selected_border))
            painter.setPen(QPen(parse_qcolor(self.palette.pill_active_text), 1.8))
            painter.drawText(chk_rect, Qt.AlignmentFlag.AlignCenter, "✓")
        else:
            painter.fillPath(chk_path, parse_qcolor(self.palette.input_bg))
            painter.setPen(QPen(parse_qcolor(self.palette.input_border), 1.2))
            painter.drawPath(chk_path)

        st_rect = self.star_rect(option.rect)
        is_fav = bool(item.get("favorite", False))
        painter.setFont(self._bold_text_font)
        painter.setPen(parse_qcolor(self.palette.selected_border if is_fav else self.palette.text_muted))
        painter.drawText(st_rect, Qt.AlignmentFlag.AlignCenter, "★" if is_fav else "☆")

        if self.grid_mode:
            badge_rect = QRect(
                card_rect.right() - PADDING_ROW_H - self.BADGE_WIDTH,
                card_rect.top() + 6,
                self.BADGE_WIDTH,
                self.BADGE_HEIGHT,
            )
        else:
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
        painter.fillPath(badge_path, parse_qcolor(self.palette.badge_bg))
        painter.setFont(self._badge_font)
        painter.setPen(parse_qcolor(self.palette.badge_text))
        painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, _extract_badge(str(item.get("keys", ""))))

        right_reserved = 10 if self.grid_mode else (self.BADGE_WIDTH + PADDING_ROW_H + 14)
        if self.copy_button_visible(option, index):
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
            painter.fillPath(copy_path, parse_qcolor(self.palette.btn_bg))
            painter.setPen(QPen(parse_qcolor(self.palette.btn_border), 1.0))
            painter.drawPath(copy_path)
            painter.setPen(parse_qcolor(self.palette.btn_text))
            painter.setFont(self._badge_font)
            painter.drawText(copy_rect, Qt.AlignmentFlag.AlignCenter, "Kopyala")
            right_reserved += self.COPY_BTN_WIDTH + 8

        if self.grid_mode:
            text_left = card_rect.left() + PADDING_ROW_H
            text_top = card_rect.top() + 34
            text_width = max(100, card_rect.width() - (PADDING_ROW_H * 2))
            text_height = 42
        else:
            text_left = st_rect.right() + 8
            text_top = card_rect.top() + PADDING_ROW_V - 2
            text_width = max(120, card_rect.right() - text_left - right_reserved)
            text_height = 40

        main_rect = QRect(text_left, text_top, text_width, text_height)
        raw_text = str(item.get("text", "")).replace("\r\n", " ").replace("\n", " ")
        max_chars = max(32, int((text_width * 1.95) / max(6, self._text_fm.averageCharWidth())))
        clipped = raw_text[: max_chars - 1] + "…" if len(raw_text) > max_chars else raw_text

        doc = self._get_cached_doc(clipped, matched_indices, text_width)
        painter.save()
        painter.translate(float(main_rect.left()), float(main_rect.top()))
        painter.setClipRect(0, 0, main_rect.width(), main_rect.height())
        doc.drawContents(painter)
        painter.restore()

        meta_rect = QRect(
            text_left,
            card_rect.bottom() - 22,
            max(80, text_width),
            18,
        )
        grp = str(item.get("group", "Genel")).strip()
        lbl = str(item.get("label", "")).strip()
        cc = int(item.get("copyCount", 0) or 0)
        meta_text = f"{grp}  ·  {lbl}" if lbl else grp
        if cc > 0:
            meta_text = f"{meta_text}  ·  {cc} kez"
        painter.setFont(self._meta_font)
        painter.setPen(parse_qcolor(self.palette.text_muted))
        elided_meta = self._meta_fm.elidedText(
            meta_text, Qt.TextElideMode.ElideRight, meta_rect.width()
        )
        painter.drawText(meta_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, elided_meta)

        painter.restore()


class SnippetListView(QListView):
    """Tıklama, seçim kutusu, yıldız, satır içi kopyala ve sağ tık menüsünü destekleyen liste."""

    item_paste_requested = pyqtSignal(int)
    item_copy_requested = pyqtSignal(int)
    item_context_requested = pyqtSignal(int, QPoint)
    item_check_toggled = pyqtSignal(int, bool)
    item_favorite_toggled = pyqtSignal(int)

    def __init__(self, delegate: SnippetItemDelegate, parent: QWidget | None = None):
        super().__init__(parent)
        self._delegate = delegate
        self._press_row: int = -1
        self._press_copy_visible: bool = False
        self.setMouseTracking(True)

    def mousePressEvent(self, event: Any) -> None:
        idx = self.indexAt(event.pos())
        if event.button() == Qt.MouseButton.LeftButton and idx.isValid():
            row = idx.row()
            prev_current = self.currentIndex()
            was_selected = prev_current.isValid() and prev_current.row() == row
            self._press_row = row
            self._press_copy_visible = (not self._delegate.grid_mode) and (
                was_selected or row == self._delegate.hovered_row
            )
        else:
            self._press_row = -1
            self._press_copy_visible = False
        super().mousePressEvent(event)

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
            row = idx.row()
            copy_visible = (
                (not self._delegate.grid_mode)
                and (
                    (row == self._press_row and self._press_copy_visible)
                    or (self._press_row == -1 and row == self._delegate.hovered_row)
                )
            )
            self._press_row = -1
            self._press_copy_visible = False
            self.setCurrentIndex(idx)
            if event.button() == Qt.MouseButton.RightButton:
                self.item_context_requested.emit(row, event.globalPosition().toPoint())
                return
            if event.button() == Qt.MouseButton.LeftButton:
                row_rect = self.visualRect(idx)
                if self._delegate.check_box_rect(row_rect).contains(event.pos()):
                    self.item_check_toggled.emit(row, bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier))
                    return
                if self._delegate.star_rect(row_rect).contains(event.pos()):
                    self.item_favorite_toggled.emit(row)
                    return
                copy_rect = self._delegate.copy_button_rect(row_rect)
                if copy_visible and not copy_rect.isEmpty() and copy_rect.contains(event.pos()):
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
        self.setMinimumSize(440, 280)
        self.resize(560, 320)
        self.setPalette(build_qpalette(palette))
        self.setStyleSheet(build_dialog_stylesheet(palette))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        info = QLabel(f"Kaynak dosya: {ini_path}")
        info.setProperty("class", "MutedHint")
        info.setWordWrap(True)
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


class SnippetEditorDialog(QDialog):
    """Katman üzerinden yeni hazır cevap ekleme veya mevcut kaydı düzenleme iletişim kutusu."""

    def __init__(
        self,
        palette: ThemePalette,
        groups: list[str],
        *,
        item: dict[str, Any] | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        is_edit = item is not None
        self.setWindowTitle("Hazır Cevap Düzenle" if is_edit else "Yeni Hazır Cevap Ekle")
        self.setMinimumSize(480, 380)
        self.resize(580, 480)
        self.setPalette(build_qpalette(palette))
        self.setStyleSheet(build_dialog_stylesheet(palette))
        self.result_payload: dict[str, Any] | None = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)

        top_fields = FlowLayout(margin=0, spacing=8)
        self.keys_cb = QComboBox(self)
        self.keys_cb.setMinimumWidth(140)
        self.keys_cb.setEditable(True)
        self.keys_cb.addItems(["L-Win+A", "L-Win+Z", "L-Win+X", "L-Win+Q", "L-Win+W", "L-Win+1", ""])
        cur_keys = str((item or {}).get("keys", "L-Win+A"))
        self.keys_cb.setCurrentText(cur_keys)

        self.group_cb = QComboBox(self)
        self.group_cb.setMinimumWidth(160)
        self.group_cb.setEditable(True)
        uniq_groups = sorted({g for g in groups if g} | {"Genel"})
        self.group_cb.addItems(uniq_groups)
        self.group_cb.setCurrentText(str((item or {}).get("group", "Genel")) or "Genel")

        top_fields.addWidget(QLabel("Kategori Kısayolu:"))
        top_fields.addWidget(self.keys_cb)
        top_fields.addWidget(QLabel("Grup:"))
        top_fields.addWidget(self.group_cb)
        lay.addLayout(top_fields)

        lbl_row = QHBoxLayout()
        lbl_row.addWidget(QLabel("Etiket / Başlık:"))
        self.label_edit = QLineEdit(self)
        self.label_edit.setText(str((item or {}).get("label", "")))
        self.label_edit.setPlaceholderText("Kısa başlık (isteğe bağlı)")
        lbl_row.addWidget(self.label_edit, 1)
        lay.addLayout(lbl_row)

        txt_head = QHBoxLayout()
        txt_head.addWidget(QLabel("Hazır Cevap Metni:"))
        txt_head.addStretch()
        self.strip_emoji_btn = QPushButton("Emojileri Temizle", self)
        self.strip_emoji_btn.setIcon(make_svg_icon("no_emoji", palette.btn_text, size=14))
        self.strip_emoji_btn.clicked.connect(self._strip_editor_emojis)
        txt_head.addWidget(self.strip_emoji_btn)
        lay.addLayout(txt_head)

        chip_row = FlowLayout(margin=0, spacing=4)
        for emo in QUICK_EMOJIS[:10]:
            eb = QPushButton(emo, self)
            eb.setObjectName("EmojiChipBtn")
            eb.clicked.connect(lambda _c=False, e=emo: self.text_edit.insertPlainText(e))
            chip_row.addWidget(eb)
        lay.addLayout(chip_row)

        self.text_edit = QPlainTextEdit(self)
        self.text_edit.setPlainText(str((item or {}).get("text", "")))
        self.text_edit.textChanged.connect(self._update_char_count)
        lay.addWidget(self.text_edit, 1)

        self.char_count_label = QLabel("0 karakter", self)
        self.char_count_label.setProperty("class", "MutedHint")
        lay.addWidget(self.char_count_label)

        checks_row = FlowLayout(margin=0, spacing=8)
        self.end_marker_chk = QCheckBox("Yapıştırma sonrası Enter gönder (<E<N<D|)", self)
        term_now = (item or {}).get("terminator", "<E<N<D|")
        self.end_marker_chk.setChecked(term_now == "<E<N<D|" or item is None)
        checks_row.addWidget(self.end_marker_chk)
        self.favorite_chk = QCheckBox("Favori olarak işaretle", self)
        self.favorite_chk.setChecked(bool((item or {}).get("favorite", False)))
        checks_row.addWidget(self.favorite_chk)
        lay.addLayout(checks_row)

        self._update_char_count()

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("İptal", self)
        save_btn = QPushButton("Kaydet", self)
        save_btn.setObjectName("PrimaryBtn")
        cancel_btn.clicked.connect(self.reject)
        save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        lay.addLayout(btn_row)

    def _strip_editor_emojis(self) -> None:
        self.text_edit.setPlainText(strip_emojis(self.text_edit.toPlainText()))
        self._update_char_count()

    def _update_char_count(self) -> None:
        self.char_count_label.setText(f"{len(self.text_edit.toPlainText())} karakter")

    def _on_save(self) -> None:
        raw_text = self.text_edit.toPlainText()
        if not raw_text.strip():
            QMessageBox.warning(self, "Eksik Metin", "Metin alanı boş olamaz.")
            return
        self.result_payload = {
            "keys": self.keys_cb.currentText().strip(),
            "group": self.group_cb.currentText().strip() or "Genel",
            "label": self.label_edit.text().strip(),
            "text": raw_text,
            "terminator": "<E<N<D|" if self.end_marker_chk.isChecked() else "",
            "favorite": self.favorite_chk.isChecked(),
        }
        self.accept()


class BulkEditDialog(QDialog):
    """Seçili birden fazla hazır cevabı tek işlemde düzenleme penceresi."""

    def __init__(
        self,
        palette: ThemePalette,
        selected_count: int,
        groups: list[str],
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle(f"Toplu Düzenleme ({selected_count} kayıt)")
        self.setMinimumSize(460, 420)
        self.resize(560, 520)
        self.setPalette(build_qpalette(palette))
        self.setStyleSheet(build_dialog_stylesheet(palette))
        self.result_payload: dict[str, Any] | None = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget(self)
        body.setObjectName("DialogScrollContainer")
        body_lay = QVBoxLayout(body)
        body_lay.setContentsMargins(0, 0, 0, 0)
        body_lay.setSpacing(10)

        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        form.setSpacing(8)

        self.keys_mode_cb = QComboBox(self)
        self.keys_mode_cb.addItem("Mevcut kısayolu koru", "keep")
        self.keys_mode_cb.addItem("Yeni kısayol ata", "set")
        self.keys_mode_cb.addItem("Kısayolsuz yap (Not)", "clear")
        form.addRow("Kısayol İşlemi:", self.keys_mode_cb)

        self.keys_cb = QComboBox(self)
        self.keys_cb.setEditable(True)
        self.keys_cb.addItems(["L-Win+A", "L-Win+Z", "L-Win+X", "L-Win+Q", "L-Win+W", "L-Win+1"])
        form.addRow("Hedef Kısayol:", self.keys_cb)

        self.group_cb = QComboBox(self)
        self.group_cb.setEditable(True)
        self.group_cb.addItem("")
        self.group_cb.addItems(sorted({g for g in groups if g} | {"Genel"}))
        self.group_cb.setCurrentText("")
        form.addRow("Grup (boş = değiştirme):", self.group_cb)

        self.fav_cb = QComboBox(self)
        self.fav_cb.addItem("Değiştirme", "keep")
        self.fav_cb.addItem("Favorilere ekle", "add")
        self.fav_cb.addItem("Favorilerden çıkar", "remove")
        form.addRow("Favori Durumu:", self.fav_cb)

        self.find_edit = QLineEdit(self)
        form.addRow("Metinde Bul:", self.find_edit)

        self.replace_edit = QLineEdit(self)
        form.addRow("Şununla Değiştir:", self.replace_edit)

        self.ignore_case_chk = QCheckBox("Büyük/küçük harf duyarsız", self)
        form.addRow("", self.ignore_case_chk)

        self.prefix_edit = QLineEdit(self)
        form.addRow("Başına Ekle (Önek):", self.prefix_edit)

        self.suffix_edit = QLineEdit(self)
        form.addRow("Sonuna Ekle (Sonek):", self.suffix_edit)

        self.strip_emojis_chk = QCheckBox("Emojileri toplu temizle", self)
        form.addRow("", self.strip_emojis_chk)

        self.add_emoji_edit = QLineEdit(self)
        self.add_emoji_edit.setPlaceholderText("Örn. 😊 veya ✅")
        form.addRow("Sonuna Emoji Ekle:", self.add_emoji_edit)
        body_lay.addLayout(form)

        chip_row = FlowLayout(margin=0, spacing=4)
        for emo in QUICK_EMOJIS[:10]:
            eb = QPushButton(emo, body)
            eb.setObjectName("EmojiChipBtn")
            eb.clicked.connect(
                lambda _c=False, e=emo: self.add_emoji_edit.setText(
                    (self.add_emoji_edit.text().strip() + " " + e).strip()
                )
            )
            chip_row.addWidget(eb)
        body_lay.addLayout(chip_row)
        body_lay.addStretch()
        scroll.setWidget(body)
        lay.addWidget(scroll, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("İptal", self)
        apply_btn = QPushButton("Seçili Kayıtlara Uygula", self)
        apply_btn.setObjectName("PrimaryBtn")
        cancel_btn.clicked.connect(self.reject)
        apply_btn.clicked.connect(self._on_apply)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(apply_btn)
        lay.addLayout(btn_row)

    def _on_apply(self) -> None:
        kmode = self.keys_mode_cb.currentData()
        keys_val = None if kmode == "keep" else ("" if kmode == "clear" else self.keys_cb.currentText().strip())
        self.result_payload = {
            "keys": keys_val,
            "group": self.group_cb.currentText().strip() or None,
            "find": self.find_edit.text() or None,
            "replace": self.replace_edit.text(),
            "ignore_case": self.ignore_case_chk.isChecked(),
            "prefix": self.prefix_edit.text(),
            "suffix": self.suffix_edit.text(),
            "strip_emojis": self.strip_emojis_chk.isChecked(),
            "add_emoji": self.add_emoji_edit.text().strip(),
            "favorite_action": self.fav_cb.currentData(),
        }
        self.accept()


class GroupManagerDialog(QDialog):
    """Grupları yeniden adlandırma/birleştirme, tek grup dışa aktarma ve silme penceresi."""

    def __init__(
        self,
        palette: ThemePalette,
        groups_provider: Callable[[], list[tuple[str, int]]],
        *,
        on_rename: Callable[[str, str], Any],
        on_delete: Callable[[str], Any],
        on_export: Callable[[str], Any] | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Grup Yöneticisi")
        self.setMinimumSize(460, 320)
        self.resize(560, 400)
        self._palette = palette
        self._groups_provider = groups_provider
        self._on_rename = on_rename
        self._on_delete = on_delete
        self._on_export = on_export
        self.setPalette(build_qpalette(palette))
        self.setStyleSheet(build_dialog_stylesheet(palette))

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)

        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.container = QWidget()
        self.container.setObjectName("DialogScrollContainer")
        self.rows_layout = QVBoxLayout(self.container)
        self.rows_layout.setSpacing(6)
        self.scroll.setWidget(self.container)
        lay.addWidget(self.scroll, 1)

        close_row = QHBoxLayout()
        close_row.addStretch()
        close_btn = QPushButton("Kapat", self)
        close_btn.clicked.connect(self.accept)
        close_row.addWidget(close_btn)
        lay.addLayout(close_row)
        self._rebuild_rows()

    def _rebuild_rows(self) -> None:
        while self.rows_layout.count():
            child = self.rows_layout.takeAt(0)
            w = child.widget()
            if w is not None:
                w.deleteLater()
        for grp_name, cnt in self._groups_provider():
            row_w = QWidget(self.container)
            row_lay = QVBoxLayout(row_w)
            row_lay.setContentsMargins(4, 6, 4, 6)
            row_lay.setSpacing(6)

            top_line = QHBoxLayout()
            top_line.setContentsMargins(0, 0, 0, 0)
            top_line.setSpacing(8)
            lbl = QLabel(f"{grp_name} ({cnt})", row_w)
            edit = QLineEdit(grp_name, row_w)
            edit.setMinimumWidth(140)
            top_line.addWidget(lbl)
            top_line.addWidget(edit, 1)
            row_lay.addLayout(top_line)

            act_flow = FlowLayout(margin=0, spacing=6)
            btn_ren = QPushButton("Yeniden Adlandır", row_w)
            btn_exp = QPushButton("INI Dışa Aktar", row_w)
            btn_del = QPushButton("Sil", row_w)
            btn_del.setObjectName("DangerBtn")

            btn_ren.clicked.connect(
                lambda _c=False, old_g=grp_name, ed=edit: self._handle_rename(old_g, ed.text().strip())
            )
            btn_exp.clicked.connect(
                lambda _c=False, g=grp_name: self._on_export(g) if self._on_export is not None else None
            )
            btn_del.clicked.connect(lambda _c=False, g=grp_name: self._handle_delete(g))

            act_flow.addWidget(btn_ren)
            act_flow.addWidget(btn_exp)
            act_flow.addWidget(btn_del)
            row_lay.addLayout(act_flow)
            self.rows_layout.addWidget(row_w)
        self.rows_layout.addStretch()

    def _handle_rename(self, old_g: str, new_g: str) -> None:
        if not new_g or new_g == old_g:
            return
        self._on_rename(old_g, new_g)
        self._rebuild_rows()

    def _handle_delete(self, grp_name: str) -> None:
        ans = QMessageBox.question(
            self,
            "Grubu Sil",
            f"'{grp_name}' grubundaki tüm kayıtlar silinsin mi?",
        )
        if ans == QMessageBox.StandardButton.Yes:
            self._on_delete(grp_name)
            self._rebuild_rows()


class OverlayWindow(QWidget):
    """
    Modern, çerçevesiz, animasyonlu ve klavye öncelikli QTP hızlı yapıştırma katmanı.
    Tüm işletim sistemlerinde birebir aynı görsel ızgara, renk, yazı tipi ve kısayolları sunar.
    """

    paste_triggered = pyqtSignal(dict)
    copy_triggered = pyqtSignal(dict)
    add_item_requested = pyqtSignal()
    edit_item_requested = pyqtSignal(dict)
    delete_item_requested = pyqtSignal(dict)
    settings_requested = pyqtSignal()
    help_requested = pyqtSignal()
    theme_toggle_requested = pyqtSignal(str)
    window_resized = pyqtSignal(int, int)

    def __init__(
        self,
        items: list[dict[str, Any]] | None = None,
        *,
        theme: str = "light",
        view_mode: str = "list",
        strip_emoji: bool = False,
        sort_by: str = "order",
        can_undo: bool = False,
        can_redo: bool = False,
        window_size: tuple[int, int] = (WINDOW_WIDTH, WINDOW_HEIGHT),
        last_category: str = "ALL",
        last_category_by_hotkey: dict[str, str] | None = None,
        initial_query: str = "",
        ini_path: str = "QuickTextPaste.ini",
        on_paste: Callable[[dict[str, Any], Any], None] | None = None,
        on_copy: Callable[[dict[str, Any]], None] | None = None,
        on_add: Callable[[dict[str, Any]], Any] | None = None,
        on_edit: Callable[[dict[str, Any], dict[str, Any]], Any] | None = None,
        on_delete: Callable[[dict[str, Any]], Any] | None = None,
        on_theme_change: Callable[[str], Any] | None = None,
        on_save_all: Callable[[], Any] | None = None,
        on_duplicate: Callable[[dict[str, Any]], Any] | None = None,
        on_move: Callable[[dict[str, Any], str], Any] | None = None,
        on_toggle_favorite: Callable[[dict[str, Any]], Any] | None = None,
        on_bulk_edit: Callable[[list[str], dict[str, Any]], Any] | None = None,
        on_bulk_delete: Callable[[list[str]], Any] | None = None,
        on_rename_group: Callable[[str, str], Any] | None = None,
        on_delete_group: Callable[[str], Any] | None = None,
        on_export_group: Callable[[str], Any] | None = None,
        on_undo: Callable[[], Any] | None = None,
        on_redo: Callable[[], Any] | None = None,
        on_setting_change: Callable[[str, Any], Any] | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._items: list[dict[str, Any]] = list(items or [])
        self._theme_setting = theme
        self._view_mode = view_mode if view_mode in ("list", "grid", "table") else "list"
        self._strip_emoji = bool(strip_emoji)
        self._sort_by = sort_by if sort_by in ("order", "usage", "alpha", "keys", "favorites") else "order"
        self._only_favorites = False
        self._only_notes = False
        self._can_undo = bool(can_undo)
        self._can_redo = bool(can_redo)
        self._selected_keys: set[str] = set()
        self._last_checked_row: int = -1
        self._ini_path = ini_path
        self._on_paste_cb = on_paste
        self._on_copy_cb = on_copy
        self._on_add_cb = on_add
        self._on_edit_cb = on_edit
        self._on_delete_cb = on_delete
        self._on_theme_cb = on_theme_change
        self._on_save_all_cb = on_save_all
        self._on_duplicate_cb = on_duplicate
        self._on_move_cb = on_move
        self._on_toggle_favorite_cb = on_toggle_favorite
        self._on_bulk_edit_cb = on_bulk_edit
        self._on_bulk_delete_cb = on_bulk_delete
        self._on_rename_group_cb = on_rename_group
        self._on_delete_group_cb = on_delete_group
        self._on_export_group_cb = on_export_group
        self._on_undo_cb = on_undo
        self._on_redo_cb = on_redo
        self._on_setting_change_cb = on_setting_change
        self._active_category = (last_category or "ALL").upper()
        self._last_cat_by_hotkey: dict[str, str] = dict(last_category_by_hotkey or {})
        self._active_hotkey_trigger: str = "all"
        self._previous_app: Any = None
        self._matcher = FuzzyMatcher()
        self._font_family = load_bundled_fonts()
        self._palette = resolve_palette(theme, os_is_dark=self._detect_os_dark())

        self._pre_copied_ok: bool = False
        self._resize_edges: Any = Qt.Edge(0)
        self._moving_window: bool = False
        self._drag_origin = QPoint()
        self._drag_start_geom = QRect()
        self._drag_start_pos = QPoint()
        self._shadow_layers: list[tuple[int, int, QBrush]] = []

        base_flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        if is_posix_desktop():
            self.setWindowFlags(base_flags | Qt.WindowType.Window)
        else:
            self.setWindowFlags(base_flags | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setMouseTracking(True)
        self.setAccessibleName("QTP Hızlı Yapıştırma Katmanı")
        self.setAccessibleDescription("Kısayolla tetiklenen hazır cevap arama ve yapıştırma penceresi.")

        w = max(WINDOW_MIN_WIDTH, int(window_size[0] if len(window_size) >= 1 else WINDOW_WIDTH))
        h = max(WINDOW_MIN_HEIGHT, int(window_size[1] if len(window_size) >= 2 else WINDOW_HEIGHT))
        self.setMinimumSize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self.setMaximumSize(16777215, 16777215)
        self.resize(w, h)

        self._anim_group: QParallelAnimationGroup | None = None
        self._toast_timer = QTimer(self)
        self._toast_timer.setSingleShot(True)
        self._toast_timer.timeout.connect(self._fade_out_toast)
        self._toast_anim: QPropertyAnimation | None = None

        self._build_ui()
        self._apply_theme()
        self._bind_shortcuts()
        if initial_query:
            self.search_input.setText(str(initial_query))
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
        outer.setContentsMargins(6, 6, 6, 6)
        self._outer_layout = outer

        self.card = QFrame(self)
        self.card.setObjectName("OverlayCard")
        self.card.setMouseTracking(True)
        outer.addWidget(self.card)

        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(PADDING_OUTER, 8, PADDING_OUTER, 8)
        card_layout.setSpacing(6)
        self._card_layout = card_layout

        self.drag_header = QFrame(self.card)
        self.drag_header.setObjectName("DragHeader")
        self.drag_header.setMouseTracking(True)
        drag_lay = QHBoxLayout(self.drag_header)
        drag_lay.setContentsMargins(2, 0, 2, 0)
        drag_lay.setSpacing(4)
        self.window_title_label = QLabel("QTP — Hazır Cevaplar", self.drag_header)
        self.window_title_label.setObjectName("WindowTitleLabel")
        drag_lay.addWidget(self.window_title_label)
        drag_lay.addStretch()
        self.max_btn = QPushButton("", self.drag_header)
        self.max_btn.setObjectName("WindowChromeBtn")
        self.max_btn.setToolTip("Ekranı kapla / Geri yükle")
        self.max_btn.setAccessibleName("Ekranı kapla veya geri yükle")
        self.max_btn.setIconSize(QSize(13, 13))
        self.max_btn.clicked.connect(self.toggle_maximize)
        self.close_btn = QPushButton("", self.drag_header)
        self.close_btn.setObjectName("WindowChromeBtn")
        self.close_btn.setToolTip("Katmanı gizle (Esc)")
        self.close_btn.setAccessibleName("Katmanı gizle")
        self.close_btn.setIconSize(QSize(13, 13))
        self.close_btn.clicked.connect(self.hide_overlay)
        drag_lay.addWidget(self.max_btn)
        drag_lay.addWidget(self.close_btn)
        self.drag_header.installEventFilter(self)
        self.card.installEventFilter(self)
        card_layout.addWidget(self.drag_header)

        top_row = QHBoxLayout()
        top_row.setSpacing(6)

        search_wrap = QFrame(self.card)
        search_wrap_layout = QHBoxLayout(search_wrap)
        search_wrap_layout.setContentsMargins(0, 0, 0, 0)
        search_wrap_layout.setSpacing(0)

        self.search_input = QLineEdit(search_wrap)
        self.search_input.setObjectName("SearchInput")
        self.search_input.setMinimumWidth(160)
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

        self.add_btn = QPushButton("Yeni Cevap", self.card)
        self.add_btn.setObjectName("HeaderActionBtn")
        self.add_btn.setIconSize(QSize(14, 14))
        self.add_btn.setToolTip("Yeni hazır cevap ekle")
        self.add_btn.clicked.connect(self._open_add_dialog)
        top_row.addWidget(self.add_btn)

        self.theme_btn = QPushButton("", self.card)
        self.theme_btn.setObjectName("HeaderActionBtn")
        self.theme_btn.setFixedSize(34, 34)
        self.theme_btn.setIconSize(QSize(16, 16))
        self.theme_btn.setToolTip("Açık / koyu temayı değiştir")
        self.theme_btn.setAccessibleName("Açık veya koyu temayı değiştir")
        self.theme_btn.clicked.connect(self.toggle_theme)
        top_row.addWidget(self.theme_btn)

        self.help_btn = QPushButton("", self.card)
        self.help_btn.setObjectName("HeaderActionBtn")
        self.help_btn.setFixedSize(34, 34)
        self.help_btn.setIconSize(QSize(16, 16))
        self.help_btn.setToolTip("Türkçe kullanım kılavuzu ve kısayolları aç (F1)")
        self.help_btn.setAccessibleName("Yardım ve kullanım kılavuzu (F1)")
        self.help_btn.clicked.connect(self.help_requested.emit)
        top_row.addWidget(self.help_btn)

        self.settings_btn = QPushButton("", self.card)
        self.settings_btn.setObjectName("HeaderActionBtn")
        self.settings_btn.setFixedSize(34, 34)
        self.settings_btn.setIconSize(QSize(16, 16))
        self.settings_btn.setToolTip("Uygulama ve kısayol ayarlarını aç (Ctrl+,)")
        self.settings_btn.setAccessibleName("Uygulama ve kısayol ayarları")
        self.settings_btn.clicked.connect(self.settings_requested.emit)
        top_row.addWidget(self.settings_btn)

        card_layout.addLayout(top_row)

        pills_row = FlowLayout(margin=0, spacing=5)
        self.category_buttons: dict[str, QPushButton] = {}
        for code, title, _prefix in CATEGORY_TABS:
            btn = QPushButton(title, self.card)
            btn.setProperty("class", "CategoryPill")
            btn.setProperty("category_code", code)
            btn.setProperty("item_count", 0)
            btn.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setAccessibleName(f"Kategori: {title}")
            btn.clicked.connect(lambda _chk=False, c=code: self.set_category(c))
            pills_row.addWidget(btn)
            self.category_buttons[code] = btn
        card_layout.addLayout(pills_row)

        manage_row = FlowLayout(margin=0, spacing=4)

        self.view_list_btn = QPushButton("", self.card)
        self.view_list_btn.setObjectName("HeaderActionBtn")
        self.view_list_btn.setIconSize(QSize(15, 15))
        self.view_list_btn.setToolTip("Liste görünümü")
        self.view_list_btn.setAccessibleName("Liste görünümü")
        self.view_list_btn.clicked.connect(lambda: self.set_view_mode("list"))

        self.view_grid_btn = QPushButton("", self.card)
        self.view_grid_btn.setObjectName("HeaderActionBtn")
        self.view_grid_btn.setIconSize(QSize(15, 15))
        self.view_grid_btn.setToolTip("Kart / Izgara görünümü")
        self.view_grid_btn.setAccessibleName("Kart veya Izgara görünümü")
        self.view_grid_btn.clicked.connect(lambda: self.set_view_mode("grid"))

        self.view_table_btn = QPushButton("", self.card)
        self.view_table_btn.setObjectName("HeaderActionBtn")
        self.view_table_btn.setIconSize(QSize(15, 15))
        self.view_table_btn.setToolTip("Tablo görünümü")
        self.view_table_btn.setAccessibleName("Tablo görünümü")
        self.view_table_btn.clicked.connect(lambda: self.set_view_mode("table"))

        self.scope_fav_btn = QPushButton("", self.card)
        self.scope_fav_btn.setObjectName("HeaderActionBtn")
        self.scope_fav_btn.setIconSize(QSize(15, 15))
        self.scope_fav_btn.setToolTip("Yalnızca favoriler filtresi")
        self.scope_fav_btn.setAccessibleName("Yalnızca favoriler filtresi")
        self.scope_fav_btn.clicked.connect(self._toggle_only_favorites)

        self.scope_notes_btn = QPushButton("", self.card)
        self.scope_notes_btn.setObjectName("HeaderActionBtn")
        self.scope_notes_btn.setIconSize(QSize(15, 15))
        self.scope_notes_btn.setToolTip("Yalnızca kısayolsuz notlar filtresi")
        self.scope_notes_btn.setAccessibleName("Yalnızca kısayolsuz notlar filtresi")
        self.scope_notes_btn.clicked.connect(self._toggle_only_notes)

        self.sort_cb = QComboBox(self.card)
        self.sort_cb.setObjectName("CompactCombo")
        self.sort_cb.addItem("Sıra", "order")
        self.sort_cb.addItem("Kullanım", "usage")
        self.sort_cb.addItem("A–Z", "alpha")
        self.sort_cb.addItem("Kısayol", "keys")
        self.sort_cb.addItem("Favori", "favorites")
        sort_idx = max(0, self.sort_cb.findData(self._sort_by))
        self.sort_cb.setCurrentIndex(sort_idx)
        self.sort_cb.currentIndexChanged.connect(self._on_sort_changed)

        self.emoji_strip_btn = QPushButton("", self.card)
        self.emoji_strip_btn.setObjectName("HeaderActionBtn")
        self.emoji_strip_btn.setIconSize(QSize(15, 15))
        self.emoji_strip_btn.setToolTip("Kopyalama/yapıştırmada emojileri temizle")
        self.emoji_strip_btn.setAccessibleName("Emojileri temizle")
        self.emoji_strip_btn.clicked.connect(self.toggle_strip_emoji)

        self.select_all_btn = QPushButton("", self.card)
        self.select_all_btn.setObjectName("HeaderActionBtn")
        self.select_all_btn.setIconSize(QSize(15, 15))
        self.select_all_btn.setToolTip("Görünen tümünü seç / temizle")
        self.select_all_btn.setAccessibleName("Görünen tümünü seç veya temizle")
        self.select_all_btn.clicked.connect(self.select_all_visible)

        self.bulk_edit_btn = QPushButton("Toplu", self.card)
        self.bulk_edit_btn.setObjectName("HeaderActionBtn")
        self.bulk_edit_btn.setIconSize(QSize(14, 14))
        self.bulk_edit_btn.setToolTip("Seçili kayıtları toplu düzenle")
        self.bulk_edit_btn.clicked.connect(self.open_bulk_edit_dialog)

        self.bulk_del_btn = QPushButton("", self.card)
        self.bulk_del_btn.setObjectName("HeaderActionBtn")
        self.bulk_del_btn.setIconSize(QSize(15, 15))
        self.bulk_del_btn.setToolTip("Seçili kayıtları sil")
        self.bulk_del_btn.setAccessibleName("Seçili kayıtları sil")
        self.bulk_del_btn.clicked.connect(self._confirm_bulk_delete)

        self.groups_btn = QPushButton("", self.card)
        self.groups_btn.setObjectName("HeaderActionBtn")
        self.groups_btn.setIconSize(QSize(15, 15))
        self.groups_btn.setToolTip("Grup Yöneticisi")
        self.groups_btn.setAccessibleName("Grup Yöneticisi")
        self.groups_btn.clicked.connect(self.open_group_manager_dialog)

        self.save_btn = QPushButton("", self.card)
        self.save_btn.setObjectName("HeaderActionBtn")
        self.save_btn.setIconSize(QSize(15, 15))
        self.save_btn.setToolTip("Değişiklikleri kaydet (Ctrl+S)")
        self.save_btn.setAccessibleName("Değişiklikleri kaydet")
        self.save_btn.clicked.connect(self._trigger_save_all)

        self.undo_btn = QPushButton("", self.card)
        self.undo_btn.setObjectName("HeaderActionBtn")
        self.undo_btn.setIconSize(QSize(15, 15))
        self.undo_btn.setToolTip("Geri al (Ctrl+Z)")
        self.undo_btn.setAccessibleName("Geri al")
        self.undo_btn.clicked.connect(self._trigger_undo)

        self.redo_btn = QPushButton("", self.card)
        self.redo_btn.setObjectName("HeaderActionBtn")
        self.redo_btn.setIconSize(QSize(15, 15))
        self.redo_btn.setToolTip("Yinele (Ctrl+Y)")
        self.redo_btn.setAccessibleName("Yinele")
        self.redo_btn.clicked.connect(self._trigger_redo)

        self.more_btn = QToolButton(self.card)
        self.more_btn.setObjectName("HeaderActionBtn")
        self.more_btn.setText("⋯")
        self.more_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.more_btn.setToolTip("Diğer toplu işlemler ve araçlar")
        self.more_btn.setAccessibleName("Diğer toplu işlemler ve araçlar")
        self.more_menu = QMenu(self.more_btn)
        self._more_act_emoji = QAction("Emojileri Temizle", self.more_menu)
        self._more_act_emoji.setCheckable(True)
        self._more_act_emoji.triggered.connect(self.toggle_strip_emoji)
        self._more_act_select_all = QAction("Görünen Tümünü Seç", self.more_menu)
        self._more_act_select_all.triggered.connect(self.select_all_visible)
        self._more_act_bulk_edit = QAction("Toplu Düzenle", self.more_menu)
        self._more_act_bulk_edit.triggered.connect(self.open_bulk_edit_dialog)
        self._more_act_bulk_del = QAction("Seçili Kayıtları Sil", self.more_menu)
        self._more_act_bulk_del.triggered.connect(self._confirm_bulk_delete)
        self._more_act_groups = QAction("Grup Yöneticisi", self.more_menu)
        self._more_act_groups.triggered.connect(self.open_group_manager_dialog)
        for act in (
            self._more_act_emoji,
            self._more_act_select_all,
            self._more_act_bulk_edit,
            self._more_act_bulk_del,
            self._more_act_groups,
        ):
            self.more_menu.addAction(act)
        self.more_btn.setMenu(self.more_menu)

        for b in (
            self.view_list_btn,
            self.view_grid_btn,
            self.view_table_btn,
            self.scope_fav_btn,
            self.scope_notes_btn,
            self.sort_cb,
            self.emoji_strip_btn,
            self.select_all_btn,
            self.bulk_edit_btn,
            self.bulk_del_btn,
            self.groups_btn,
            self.more_btn,
            self.save_btn,
            self.undo_btn,
            self.redo_btn,
        ):
            manage_row.addWidget(b)
        card_layout.addLayout(manage_row)

        self.list_model = SnippetListModel(self)
        self.list_delegate = SnippetItemDelegate(self._palette, self._font_family, self)
        self.list_delegate.checked_keys = self._selected_keys
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
        self.list_view.item_check_toggled.connect(self._on_list_check_toggled)
        self.list_view.item_favorite_toggled.connect(self._on_list_favorite_toggled)

        self.table_model = SnippetTableModel(self._selected_keys, self)
        self.table_view = QTableView(self.card)
        self.table_view.setObjectName("SnippetTable")
        self.table_view.setModel(self.table_model)
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table_view.verticalHeader().setVisible(False)
        self.table_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        hdr = self.table_view.horizontalHeader()
        hdr.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.table_view.clicked.connect(self._on_table_clicked)
        self.table_view.doubleClicked.connect(lambda idx: self.paste_row(idx.row()))
        self.table_view.customContextMenuRequested.connect(self._on_table_context_menu)
        self.table_view.installEventFilter(self)

        self.view_stack = QStackedWidget(self.card)
        self.view_stack.addWidget(self.list_view)
        self.view_stack.addWidget(self.table_view)
        card_layout.addWidget(self.view_stack, 1)

        footer = QFrame(self.card)
        footer.setObjectName("FooterBar")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(2, 2, 2, 0)
        footer_layout.setSpacing(8)

        self.footer_hints = QLabel(FOOTER_HINTS_TEXT, footer)
        self.footer_hints.setObjectName("FooterHints")
        self.footer_hints.setMinimumWidth(0)
        self.footer_hints.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.footer_hints.setToolTip(FOOTER_HINTS_TEXT)
        footer_layout.addWidget(self.footer_hints, 1)

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
        self._update_responsive_chrome()

    def _bind_shortcuts(self) -> None:
        for seq in ("Ctrl+K", "Meta+K"):
            sc = QShortcut(QKeySequence(seq), self)
            sc.activated.connect(self.focus_search)
        for seq in ("Ctrl+,", "Meta+,"):
            sc = QShortcut(QKeySequence(seq), self)
            sc.activated.connect(self.settings_requested.emit)
        for seq in ("Ctrl+Z", "Meta+Z"):
            sc = QShortcut(QKeySequence(seq), self)
            sc.activated.connect(self._trigger_undo)
        for seq in ("Ctrl+Y", "Meta+Y"):
            sc = QShortcut(QKeySequence(seq), self)
            sc.activated.connect(self._trigger_redo)
        for seq in ("Ctrl+S", "Meta+S"):
            sc = QShortcut(QKeySequence(seq), self)
            sc.activated.connect(self._trigger_save_all)
        sc_help = QShortcut(QKeySequence(Qt.Key.Key_F1), self)
        sc_help.activated.connect(self.help_requested.emit)
        sc_esc = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        sc_esc.activated.connect(self.hide_overlay)

    def _sync_toolbar_widgets(self) -> None:
        normal_col = self._palette.btn_text
        active_col = self._palette.pill_active_text
        muted_col = self._palette.text_muted

        toggle_icons = (
            (self.view_list_btn, self._view_mode == "list", "list"),
            (self.view_grid_btn, self._view_mode == "grid", "grid"),
            (self.view_table_btn, self._view_mode == "table", "table"),
            (self.scope_fav_btn, self._only_favorites, "star_filled" if self._only_favorites else "star"),
            (self.scope_notes_btn, self._only_notes, "note"),
            (self.emoji_strip_btn, self._strip_emoji, "no_emoji" if self._strip_emoji else "emoji"),
        )
        for btn, active, icon_name in toggle_icons:
            btn.setProperty("active", "true" if active else "false")
            btn.setIcon(make_svg_icon(icon_name, active_col if active else normal_col, size=15))
            btn.style().unpolish(btn)
            btn.style().polish(btn)

        sel_cnt = len(self._selected_keys)
        bulk_lbl = f"Toplu ({sel_cnt})" if sel_cnt else "Toplu"
        self.bulk_edit_btn.setText(bulk_lbl)
        self.bulk_edit_btn.setIcon(make_svg_icon("edit", normal_col, size=14))
        self.select_all_btn.setIcon(make_svg_icon("check_all", normal_col, size=15))
        self.bulk_del_btn.setIcon(make_svg_icon("trash", normal_col, size=15))
        self.groups_btn.setIcon(make_svg_icon("folder", normal_col, size=15))
        self.more_btn.setIcon(make_svg_icon("grid", normal_col, size=14))
        self.more_btn.setText("⋯")
        self._more_act_emoji.setChecked(self._strip_emoji)
        self._more_act_emoji.setIcon(make_svg_icon("no_emoji" if self._strip_emoji else "emoji", self._palette.menu_text, size=14))
        self._more_act_select_all.setIcon(make_svg_icon("check_all", self._palette.menu_text, size=14))
        self._more_act_bulk_edit.setText(f"Toplu Düzenle ({sel_cnt})" if sel_cnt else "Toplu Düzenle")
        self._more_act_bulk_edit.setIcon(make_svg_icon("edit", self._palette.menu_text, size=14))
        self._more_act_bulk_del.setIcon(make_svg_icon("trash", self._palette.menu_text, size=14))
        self._more_act_groups.setIcon(make_svg_icon("folder", self._palette.menu_text, size=14))
        self.save_btn.setIcon(make_svg_icon("save", normal_col, size=15))
        self.undo_btn.setEnabled(self._can_undo)
        self.redo_btn.setEnabled(self._can_redo)
        self.undo_btn.setIcon(make_svg_icon("undo", normal_col if self._can_undo else muted_col, size=15))
        self.redo_btn.setIcon(make_svg_icon("redo", normal_col if self._can_redo else muted_col, size=15))
        self.max_btn.setIcon(
            make_svg_icon("restore" if self.isMaximized() else "maximize", normal_col, size=13)
        )
        self.close_btn.setIcon(make_svg_icon("close", normal_col, size=13))

        if self._view_mode == "grid":
            self.list_delegate.grid_mode = True
            self.list_view.setViewMode(QListView.ViewMode.IconMode)
            self.list_view.setMovement(QListView.Movement.Static)
            self.list_view.setDragEnabled(False)
            self.list_view.setDragDropMode(QAbstractItemView.DragDropMode.NoDragDrop)
            self.list_view.setSelectionRectVisible(False)
            self.list_view.setWrapping(True)
            self.list_view.setResizeMode(QListView.ResizeMode.Adjust)
            self.list_view.setUniformItemSizes(False)
            self.list_view.setGridSize(QSize(SnippetItemDelegate.GRID_WIDTH + 6, SnippetItemDelegate.GRID_HEIGHT + 6))
            self.list_view.setSpacing(6)
            self.view_stack.setCurrentWidget(self.list_view)
        elif self._view_mode == "table":
            self.list_delegate.grid_mode = False
            self.view_stack.setCurrentWidget(self.table_view)
        else:
            self.list_delegate.grid_mode = False
            self.list_view.setViewMode(QListView.ViewMode.ListMode)
            self.list_view.setMovement(QListView.Movement.Static)
            self.list_view.setDragEnabled(False)
            self.list_view.setWrapping(False)
            self.list_view.setUniformItemSizes(True)
            self.list_view.setGridSize(QSize())
            self.list_view.setSpacing(0)
            self.view_stack.setCurrentWidget(self.list_view)

    def _rebuild_shadow_cache(self) -> None:
        base = parse_qcolor(self._palette.shadow_color)
        base_alpha = max(16, base.alpha())
        layers: list[tuple[int, int, QBrush]] = []
        for step in range(5, 0, -1):
            spread = step
            y_off = 1 if step >= 2 else 0
            layer_col = QColor(base)
            layer_col.setAlpha(max(2, min(255, int(round(base_alpha * (0.28 / (step + 0.5)))))))
            layers.append((spread, y_off, QBrush(layer_col)))
        inner_col = QColor(base)
        inner_col.setAlpha(max(4, min(255, int(round(base_alpha * 0.34)))))
        layers.append((1, 2, QBrush(inner_col)))
        self._shadow_layers = layers

    def paintEvent(self, event: Any) -> None:
        if not self.isMaximized() and hasattr(self, "card") and self._shadow_layers:
            card_rect = self.card.geometry()
            if not card_rect.isEmpty():
                painter = QPainter(self)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                painter.setPen(Qt.PenStyle.NoPen)
                for spread, y_off, brush in self._shadow_layers:
                    r = card_rect.adjusted(-spread, -spread + y_off, spread, spread + y_off)
                    painter.setBrush(brush)
                    painter.drawRoundedRect(
                        r,
                        float(WINDOW_CORNER_RADIUS + spread),
                        float(WINDOW_CORNER_RADIUS + spread),
                    )
                painter.end()
        super().paintEvent(event)

    def _update_responsive_chrome(self) -> None:
        w = self.width()
        h = self.height()
        compact_w = w < 640
        compact_h = h < 440
        for btn in (
            self.emoji_strip_btn,
            self.select_all_btn,
            self.bulk_edit_btn,
            self.bulk_del_btn,
            self.groups_btn,
        ):
            btn.setVisible(not compact_w)
        self.more_btn.setVisible(compact_w)
        if compact_w or compact_h:
            self._card_layout.setContentsMargins(10, 4, 10, 4)
            self._card_layout.setSpacing(2)
        else:
            self._card_layout.setContentsMargins(PADDING_OUTER, 8, PADDING_OUTER, 8)
            self._card_layout.setSpacing(7)

    def _elide_footer_hints(self) -> None:
        card_w = self.card.width() if hasattr(self, "card") and self.card.width() > 0 else self.width() - 12
        avail = max(40, card_w - self.count_label.sizeHint().width() - self.size_grip.width() - 48)
        fm = QFontMetrics(self.footer_hints.font())
        self.footer_hints.setText(fm.elidedText(FOOTER_HINTS_TEXT, Qt.TextElideMode.ElideRight, avail))

    def _apply_theme(self) -> None:
        self._palette = resolve_palette(self._theme_setting, os_is_dark=self._detect_os_dark())
        qpal = build_qpalette(self._palette)
        app = QApplication.instance()
        if app is not None:
            app.setPalette(qpal)
        self.setPalette(qpal)
        self._rebuild_shadow_cache()
        qss = build_overlay_stylesheet(self._palette, translucent=False)
        self.setStyleSheet(qss)
        is_dark = self._palette.name == "dark"
        self.theme_btn.setText("")
        theme_tip = "Açık temaya geç" if is_dark else "Koyu temaya geç"
        self.theme_btn.setToolTip(theme_tip)
        self.theme_btn.setAccessibleName(theme_tip)
        btn_col = self._palette.btn_text
        self.add_btn.setIcon(make_svg_icon("plus", btn_col, size=14))
        self.theme_btn.setIcon(make_svg_icon("sun" if is_dark else "moon", btn_col, size=16))
        self.help_btn.setIcon(make_svg_icon("help", btn_col, size=16))
        self.settings_btn.setIcon(make_svg_icon("settings", btn_col, size=16))
        self.list_delegate.set_palette(self._palette)
        self.more_menu.setPalette(qpal)
        self.more_menu.setStyleSheet(qss)
        for w in (
            self.card,
            self.drag_header,
            self.window_title_label,
            self.max_btn,
            self.close_btn,
            self.search_input,
            self.shortcut_chip,
            self.add_btn,
            self.theme_btn,
            self.help_btn,
            self.settings_btn,
            self.view_list_btn,
            self.view_grid_btn,
            self.view_table_btn,
            self.scope_fav_btn,
            self.scope_notes_btn,
            self.sort_cb,
            self.emoji_strip_btn,
            self.select_all_btn,
            self.bulk_edit_btn,
            self.bulk_del_btn,
            self.groups_btn,
            self.more_btn,
            self.save_btn,
            self.undo_btn,
            self.redo_btn,
            self.toast_label,
            self.list_view,
            self.table_view,
            self.table_view.horizontalHeader(),
        ):
            w.setPalette(qpal)
            w.style().unpolish(w)
            w.style().polish(w)
        self._update_pill_styles()
        self._sync_toolbar_widgets()
        self.list_view.viewport().update()
        self.table_view.viewport().update()
        self.update()

    def toggle_theme(self) -> None:
        """Açık ve koyu tema arasında tek tıkla geçiş yapar."""
        next_theme = "light" if self._palette.name == "dark" else "dark"
        self._theme_setting = next_theme
        self._apply_theme()
        if self._on_theme_cb is not None:
            self._on_theme_cb(next_theme)
        self.theme_toggle_requested.emit(next_theme)
        self.show_toast("Koyu tema etkinleştirildi ✔" if next_theme == "dark" else "Açık tema etkinleştirildi ✔")

    def apply_settings(
        self,
        *,
        theme: str | None = None,
        ini_path: str | None = None,
        view_mode: str | None = None,
        strip_emoji: bool | None = None,
        sort_by: str | None = None,
    ) -> None:
        if theme is not None:
            self._theme_setting = theme
        if ini_path is not None:
            self._ini_path = ini_path
        if view_mode is not None and view_mode in ("list", "grid", "table"):
            self._view_mode = view_mode
        if strip_emoji is not None:
            self._strip_emoji = bool(strip_emoji)
        if sort_by is not None and sort_by in ("order", "usage", "alpha", "keys", "favorites"):
            self._sort_by = sort_by
            sidx = self.sort_cb.findData(sort_by)
            if sidx >= 0:
                self.sort_cb.blockSignals(True)
                self.sort_cb.setCurrentIndex(sidx)
                self.sort_cb.blockSignals(False)
        self._apply_theme()
        self._refresh_list()

    def set_view_mode(self, mode: str, *, persist: bool = True) -> None:
        if mode not in ("list", "grid", "table"):
            return
        self._view_mode = mode
        self._sync_toolbar_widgets()
        if persist and self._on_setting_change_cb is not None:
            self._on_setting_change_cb("view_mode", mode)

    def set_history_state(self, can_undo: bool, can_redo: bool) -> None:
        self._can_undo = bool(can_undo)
        self._can_redo = bool(can_redo)
        self._sync_toolbar_widgets()

    def toggle_strip_emoji(self) -> None:
        self._strip_emoji = not self._strip_emoji
        self._sync_toolbar_widgets()
        if self._on_setting_change_cb is not None:
            self._on_setting_change_cb("strip_emoji", self._strip_emoji)
        self.show_toast("Emojisiz kopyalama etkin ✔" if self._strip_emoji else "Emojili kopyalama etkin ✔")

    def _toggle_only_favorites(self) -> None:
        self._only_favorites = not self._only_favorites
        self._sync_toolbar_widgets()
        self._refresh_list()

    def _toggle_only_notes(self) -> None:
        self._only_notes = not self._only_notes
        self._sync_toolbar_widgets()
        self._refresh_list()

    def _on_sort_changed(self, _index: int) -> None:
        val = str(self.sort_cb.currentData() or "order")
        self._sort_by = val
        if self._on_setting_change_cb is not None:
            self._on_setting_change_cb("sort_by", val)
        self._refresh_list()

    def _on_list_check_toggled(self, row: int, shift: bool) -> None:
        self.toggle_check(row, shift=shift)

    def _on_list_favorite_toggled(self, row: int) -> None:
        item = self.list_model.item_at(row)
        if item and self._on_toggle_favorite_cb is not None:
            res = self._on_toggle_favorite_cb(item)
            if res is not None and hasattr(res, "message"):
                self.show_toast(res.message)

    def _on_table_clicked(self, idx: QModelIndex) -> None:
        if not idx.isValid():
            return
        row = idx.row()
        if idx.column() == 0:
            self.toggle_check(row)
        elif idx.column() == 1:
            self._on_list_favorite_toggled(row)

    def _on_table_context_menu(self, pos: QPoint) -> None:
        idx = self.table_view.indexAt(pos)
        if idx.isValid():
            self._open_context_menu(idx.row(), self.table_view.viewport().mapToGlobal(pos))

    def toggle_check(self, row: int | None = None, *, shift: bool = False) -> None:
        target_row = self.selected_row() if row is None else row
        item = self.list_model.item_at(target_row)
        if not item:
            return
        rk = str(item.get("raw_key", ""))
        if not rk:
            return
        add_mode = rk not in self._selected_keys
        if shift and self._last_checked_row >= 0:
            lo = min(self._last_checked_row, target_row)
            hi = max(self._last_checked_row, target_row)
            for i in range(lo, hi + 1):
                it = self.list_model.item_at(i)
                if it:
                    k = str(it.get("raw_key", ""))
                    if add_mode:
                        self._selected_keys.add(k)
                    else:
                        self._selected_keys.discard(k)
        else:
            if add_mode:
                self._selected_keys.add(rk)
            else:
                self._selected_keys.discard(rk)
        self._last_checked_row = target_row
        self._sync_toolbar_widgets()
        self.list_view.viewport().update()
        self.table_model.layoutChanged.emit()

    def select_all_visible(self) -> None:
        vis_keys = [str(self.list_model.item_at(i).get("raw_key", "")) for i in range(self.list_model.rowCount()) if self.list_model.item_at(i)]
        vis_keys = [k for k in vis_keys if k]
        if vis_keys and all(k in self._selected_keys for k in vis_keys):
            for k in vis_keys:
                self._selected_keys.discard(k)
        else:
            self._selected_keys.update(vis_keys)
        self._sync_toolbar_widgets()
        self.list_view.viewport().update()
        self.table_model.layoutChanged.emit()

    def clear_selection(self) -> None:
        self._selected_keys.clear()
        self._last_checked_row = -1
        self._sync_toolbar_widgets()
        self.list_view.viewport().update()
        self.table_model.layoutChanged.emit()

    def set_items(self, items: list[dict[str, Any]]) -> None:
        self._items = list(items)
        valid_keys = {str(it.get("raw_key", "")) for it in self._items}
        self._selected_keys.intersection_update(valid_keys)
        self._update_pill_counts()
        self._refresh_list()
        self._sync_toolbar_widgets()

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
        cat_items: list[dict[str, Any]] = []
        for it in self._items:
            if not _matches_category(it, self._active_category):
                continue
            if self._only_favorites and not bool(it.get("favorite", False)):
                continue
            if self._only_notes and not is_note_item(it):
                continue
            cat_items.append(it)
        query = self.search_input.text()
        rows = self._matcher.filter_items(query, cat_items)
        if self._sort_by == "usage":
            rows.sort(key=lambda r: (-int(r[1].get("copyCount", 0) or 0), r[0]))
        elif self._sort_by == "alpha":
            rows.sort(key=lambda r: (tr_lower(str(r[1].get("label") or r[1].get("text") or "")), r[0]))
        elif self._sort_by == "keys":
            rows.sort(key=lambda r: (0 if str(r[1].get("keys", "")).strip() else 1, tr_lower(str(r[1].get("keys", ""))), r[0]))
        elif self._sort_by == "favorites":
            rows.sort(key=lambda r: (0 if bool(r[1].get("favorite", False)) else 1, r[0]))
        self.list_model.set_rows(rows)
        self.table_model.set_rows(rows)
        self.count_label.setText(f"{len(rows)} / {len(self._items)} kayıt")
        if rows:
            first = self.list_model.index(0, 0)
            self.list_view.setCurrentIndex(first)
            self.list_view.scrollTo(first)
            first_tbl = self.table_model.index(0, 0)
            self.table_view.setCurrentIndex(first_tbl)

    def focus_search(self) -> None:
        self.search_input.setFocus(Qt.FocusReason.ActiveWindowFocusReason)
        self.search_input.selectAll()

    def selected_row(self) -> int:
        if self._view_mode == "table":
            idx = self.table_view.currentIndex()
            if idx.isValid():
                return idx.row()
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
        tidx = self.table_model.index(nxt, 0)
        self.table_view.setCurrentIndex(tidx)
        self.table_view.scrollTo(tidx)

    def consume_pre_copied(self) -> bool:
        """paste_row() sırasında pencere gizlenmeden önce yapılan kopyalama durumunu döndürür ve sıfırlar."""
        val = bool(self._pre_copied_ok)
        self._pre_copied_ok = False
        return val

    def paste_row(self, row: int | None = None) -> None:
        target_row = self.selected_row() if row is None else row
        item = self.list_model.item_at(target_row)
        if not item:
            return
        prev = self._previous_app
        raw_text = str(item.get("text", ""))
        final_text = strip_emojis(raw_text) if self._strip_emoji else raw_text
        app = QApplication.instance()
        cb = app.clipboard() if app is not None else None
        self._pre_copied_ok = bool(final_text and copy_to_clipboard(final_text, qt_clipboard=cb))
        if app is not None:
            app.processEvents()
        self.hide_overlay(animate=False)
        if app is not None:
            app.processEvents()
        self.paste_triggered.emit(item)
        res = self._on_paste_cb(item, prev) if self._on_paste_cb is not None else None
        self._pre_copied_ok = False
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
        menu.setPalette(build_qpalette(self._palette))
        menu.setStyleSheet(build_overlay_stylesheet(self._palette))
        ic_col = self._palette.menu_text
        act_paste = QAction(make_svg_icon("paste", ic_col), "Yapıştır", menu)
        act_copy = QAction(make_svg_icon("copy", ic_col), "Kopyala", menu)
        is_fav = bool(item.get("favorite", False))
        act_fav = QAction(
            make_svg_icon("star_filled" if is_fav else "star", ic_col),
            "Favoriden Çıkar" if is_fav else "Favoriye Ekle",
            menu,
        )
        act_edit = QAction(make_svg_icon("edit", ic_col), "Düzenle", menu)
        act_dup = QAction(make_svg_icon("duplicate", ic_col), "Çoğalt", menu)
        act_up = QAction(make_svg_icon("arrow_up", ic_col), "Yukarı Taşı", menu)
        act_down = QAction(make_svg_icon("arrow_down", ic_col), "Aşağı Taşı", menu)
        act_delete = QAction(make_svg_icon("trash", ic_col), "Sil", menu)
        act_ini = QAction(make_svg_icon("code", ic_col), "INI'de Göster", menu)
        act_help = QAction(make_svg_icon("help", ic_col), "Yardım", menu)

        act_paste.triggered.connect(lambda: self.paste_row(row))
        act_copy.triggered.connect(lambda: self.copy_row(row))
        act_fav.triggered.connect(lambda: self._on_toggle_favorite_cb(item) if self._on_toggle_favorite_cb else None)
        act_edit.triggered.connect(lambda: self._open_edit_dialog(item))
        act_dup.triggered.connect(lambda: self._on_duplicate_cb(item) if self._on_duplicate_cb else None)
        act_up.triggered.connect(lambda: self._on_move_cb(item, "up") if self._on_move_cb else None)
        act_down.triggered.connect(lambda: self._on_move_cb(item, "down") if self._on_move_cb else None)
        act_delete.triggered.connect(lambda: self._confirm_delete_item(item))
        act_ini.triggered.connect(lambda: self._show_ini_preview(item, row))
        act_help.triggered.connect(self.help_requested.emit)

        menu.addAction(act_paste)
        menu.addAction(act_copy)
        menu.addAction(act_fav)
        menu.addSeparator()
        menu.addAction(act_edit)
        menu.addAction(act_dup)
        menu.addAction(act_up)
        menu.addAction(act_down)
        menu.addAction(act_delete)
        menu.addSeparator()
        menu.addAction(act_ini)
        menu.addAction(act_help)
        menu.exec(global_pos)

    def _open_add_dialog(self) -> None:
        self.add_item_requested.emit()
        groups = [str(it.get("group", "Genel")) for it in self._items]
        dlg = SnippetEditorDialog(self._palette, groups, item=None, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.result_payload is not None:
            if self._on_add_cb is not None:
                res = self._on_add_cb(dlg.result_payload)
                if res is not None and hasattr(res, "message"):
                    self.show_toast(res.message)

    def _open_edit_dialog(self, item: dict[str, Any]) -> None:
        self.edit_item_requested.emit(item)
        groups = [str(it.get("group", "Genel")) for it in self._items]
        dlg = SnippetEditorDialog(self._palette, groups, item=item, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.result_payload is not None:
            if self._on_edit_cb is not None:
                res = self._on_edit_cb(item, dlg.result_payload)
                if res is not None and hasattr(res, "message"):
                    self.show_toast(res.message)

    def _confirm_delete_item(self, item: dict[str, Any]) -> None:
        self.delete_item_requested.emit(item)
        ans = QMessageBox.question(
            self,
            "Kaydı Sil",
            f"'{item.get('label') or str(item.get('text', ''))[:40]}' kaydı silinsin mi?",
        )
        if ans == QMessageBox.StandardButton.Yes and self._on_delete_cb is not None:
            res = self._on_delete_cb(item)
            if res is not None and hasattr(res, "message"):
                self.show_toast(res.message)

    def open_bulk_edit_dialog(self) -> None:
        if not self._selected_keys:
            self.show_toast("Toplu düzenleme için önce kayıt seçin.")
            return
        groups = [str(it.get("group", "Genel")) for it in self._items]
        dlg = BulkEditDialog(self._palette, len(self._selected_keys), groups, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.result_payload is not None:
            if self._on_bulk_edit_cb is not None:
                res = self._on_bulk_edit_cb(sorted(self._selected_keys), dlg.result_payload)
                if res is not None and hasattr(res, "message"):
                    self.show_toast(res.message)

    def _confirm_bulk_delete(self) -> None:
        if not self._selected_keys:
            self.show_toast("Toplu silme için önce kayıt seçin.")
            return
        ans = QMessageBox.question(
            self,
            "Seçili Kayıtları Sil",
            f"Seçili {len(self._selected_keys)} kayıt kalıcı olarak silinsin mi?",
        )
        if ans == QMessageBox.StandardButton.Yes and self._on_bulk_delete_cb is not None:
            res = self._on_bulk_delete_cb(sorted(self._selected_keys))
            if res is not None and hasattr(res, "message"):
                self.show_toast(res.message)

    def open_group_manager_dialog(self) -> None:
        def _groups_provider() -> list[tuple[str, int]]:
            counts: dict[str, int] = {}
            for it in self._items:
                g = str(it.get("group") or "Genel").strip() or "Genel"
                counts[g] = counts.get(g, 0) + 1
            return sorted(counts.items(), key=lambda x: tr_lower(x[0]))

        dlg = GroupManagerDialog(
            self._palette,
            _groups_provider,
            on_rename=lambda o, n: self._on_rename_group_cb(o, n) if self._on_rename_group_cb else None,
            on_delete=lambda g: self._on_delete_group_cb(g) if self._on_delete_group_cb else None,
            on_export=lambda g: self._on_export_group_cb(g) if self._on_export_group_cb else None,
            parent=self,
        )
        dlg.exec()

    def _trigger_save_all(self) -> None:
        if self._on_save_all_cb is not None:
            res = self._on_save_all_cb()
            if res is not None and hasattr(res, "message"):
                self.show_toast(res.message)

    def _trigger_undo(self) -> None:
        if self._on_undo_cb is not None:
            res = self._on_undo_cb()
            if res is not None and hasattr(res, "message"):
                self.show_toast(res.message)

    def _trigger_redo(self) -> None:
        if self._on_redo_cb is not None:
            res = self._on_redo_cb()
            if res is not None and hasattr(res, "message"):
                self.show_toast(res.message)

    def _show_ini_preview(self, item: dict[str, Any], row: int) -> None:
        dlg = IniSnippetViewerDialog(item, row, self._ini_path, self._palette, self)
        dlg.exec()

    def _supports_window_opacity(self) -> bool:
        pname = (QGuiApplication.platformName() or "").strip().lower()
        return not (pname.startswith("wayland") or pname == "offscreen")

    def _supports_raise(self) -> bool:
        pname = (QGuiApplication.platformName() or "").strip().lower()
        return not (pname.startswith("wayland") or pname == "offscreen")

    def _hit_test_edges(self, pos: QPoint) -> Any:
        if self.isMaximized():
            return Qt.Edge(0)
        card_g = self.card.geometry() if hasattr(self, "card") else self.rect()
        if card_g.isEmpty():
            inner = self.rect().adjusted(10, 10, -10, -10)
        else:
            inner = card_g.adjusted(8, 8, -8, -8)
        edges = Qt.Edge(0)
        if pos.x() <= inner.left():
            edges |= Qt.Edge.LeftEdge
        elif pos.x() >= inner.right():
            edges |= Qt.Edge.RightEdge
        if pos.y() <= inner.top():
            edges |= Qt.Edge.TopEdge
        elif pos.y() >= inner.bottom():
            edges |= Qt.Edge.BottomEdge
        return edges

    @staticmethod
    def _cursor_for_edges(edges: Any) -> Qt.CursorShape | None:
        left = bool(edges & Qt.Edge.LeftEdge)
        right = bool(edges & Qt.Edge.RightEdge)
        top = bool(edges & Qt.Edge.TopEdge)
        bottom = bool(edges & Qt.Edge.BottomEdge)
        if (left and top) or (right and bottom):
            return Qt.CursorShape.SizeFDiagCursor
        if (right and top) or (left and bottom):
            return Qt.CursorShape.SizeBDiagCursor
        if left or right:
            return Qt.CursorShape.SizeHorCursor
        if top or bottom:
            return Qt.CursorShape.SizeVerCursor
        return None

    def _update_hover_cursor(self, pos: QPoint) -> None:
        shape = self._cursor_for_edges(self._hit_test_edges(pos))
        if shape is not None:
            self.setCursor(shape)
        else:
            self.unsetCursor()

    def _begin_resize(self, edges: Any, global_pos: QPoint) -> None:
        handle = self.windowHandle()
        if handle is not None and handle.startSystemResize(edges):
            return
        self._resize_edges = edges
        self._drag_origin = global_pos
        self._drag_start_geom = self.geometry()

    def _begin_move(self, global_pos: QPoint) -> None:
        if self.isMaximized():
            return
        handle = self.windowHandle()
        if handle is not None and handle.startSystemMove():
            return
        self._moving_window = True
        self._drag_origin = global_pos
        self._drag_start_pos = self.pos()

    def _handle_drag_move(self, global_pos: QPoint) -> None:
        delta = global_pos - self._drag_origin
        if self._moving_window:
            self.move(self._drag_start_pos + delta)
            return
        if self._resize_edges:
            geom = QRect(self._drag_start_geom)
            min_w = self.minimumWidth()
            min_h = self.minimumHeight()
            if self._resize_edges & Qt.Edge.LeftEdge:
                new_left = min(geom.right() - min_w + 1, geom.left() + delta.x())
                geom.setLeft(new_left)
            elif self._resize_edges & Qt.Edge.RightEdge:
                new_right = max(geom.left() + min_w - 1, geom.right() + delta.x())
                geom.setRight(new_right)
            if self._resize_edges & Qt.Edge.TopEdge:
                new_top = min(geom.bottom() - min_h + 1, geom.top() + delta.y())
                geom.setTop(new_top)
            elif self._resize_edges & Qt.Edge.BottomEdge:
                new_bottom = max(geom.top() + min_h - 1, geom.bottom() + delta.y())
                geom.setBottom(new_bottom)
            self.setGeometry(geom)

    def toggle_maximize(self) -> None:
        """Katman penceresini ekranı kaplama ve normal boyut arasında geçiş yaptırır."""
        if self.isMaximized():
            self.showNormal()
            self._outer_layout.setContentsMargins(6, 6, 6, 6)
        else:
            self._outer_layout.setContentsMargins(0, 0, 0, 0)
            self.showMaximized()
        self._sync_toolbar_widgets()
        self._elide_footer_hints()

    def event(self, ev: Any) -> bool:
        if ev.type() == QEvent.Type.HoverMove and not (self._resize_edges or self._moving_window):
            self._update_hover_cursor(ev.position().toPoint())
        return super().event(ev)

    def mousePressEvent(self, event: Any) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position().toPoint()
            edges = self._hit_test_edges(pos)
            if edges != Qt.Edge(0):
                self._begin_resize(edges, event.globalPosition().toPoint())
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: Any) -> None:
        if self._resize_edges or self._moving_window:
            self._handle_drag_move(event.globalPosition().toPoint())
            event.accept()
            return
        self._update_hover_cursor(event.position().toPoint())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: Any) -> None:
        if self._resize_edges or self._moving_window:
            self._resize_edges = Qt.Edge(0)
            self._moving_window = False
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def eventFilter(self, obj: Any, event: QEvent) -> bool:
        drag_hdr = getattr(self, "drag_header", None)
        card_widget = getattr(self, "card", None)
        if obj in (drag_hdr, card_widget):
            etype = event.type()
            if etype == QEvent.Type.MouseButtonDblClick and obj is drag_hdr and event.button() == Qt.MouseButton.LeftButton:
                self.toggle_maximize()
                return True
            if etype == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                gpos = event.globalPosition().toPoint()
                local_pos = self.mapFromGlobal(gpos)
                edges = self._hit_test_edges(local_pos)
                if edges != Qt.Edge(0):
                    self._begin_resize(edges, gpos)
                    return True
                if obj is drag_hdr:
                    child = drag_hdr.childAt(event.position().toPoint())
                    if not isinstance(child, QPushButton):
                        self._begin_move(gpos)
                        return True
                elif obj is card_widget and card_widget.childAt(event.position().toPoint()) is None:
                    self._begin_move(gpos)
                    return True
            elif etype == QEvent.Type.MouseMove and (self._resize_edges or self._moving_window):
                self._handle_drag_move(event.globalPosition().toPoint())
                return True
            elif etype == QEvent.Type.MouseButtonRelease and (self._resize_edges or self._moving_window):
                self._resize_edges = Qt.Edge(0)
                self._moving_window = False
                return True

        list_widget = getattr(self, "list_view", None)
        table_widget = getattr(self, "table_view", None)
        search_widget = getattr(self, "search_input", None)
        if obj in (search_widget, list_widget, table_widget) and event.type() == QEvent.Type.KeyPress:
            key = event.key()
            mods = event.modifiers()
            if key == Qt.Key.Key_Space and obj in (list_widget, table_widget):
                self.toggle_check()
                return True
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
        query: str | None = None,
        force_category: bool = False,
        animate: bool = True,
        previous_app: Any = None,
    ) -> None:
        """Katmanı aktif ekranda ortalayarak 180 ms animasyonla açar."""
        self._previous_app = previous_app if previous_app is not None else capture_previous_app()

        trig = (hotkey_key or category or "all").strip()
        self._active_hotkey_trigger = trig
        if category is not None:
            chosen = category if force_category else self._last_cat_by_hotkey.get(trig, category)
            self.set_category(chosen, remember=False)
        else:
            self.set_category(self._last_cat_by_hotkey.get(trig, self._active_category), remember=False)

        target_pos = self.pos() if self.isMaximized() else self.center_on_active_screen()
        if query is not None:
            self.search_input.setText(str(query))
        else:
            self.search_input.clear()

        if self._anim_group is not None:
            self._anim_group.stop()

        supports_opacity = self._supports_window_opacity()
        supports_raise = self._supports_raise()
        self._update_responsive_chrome()
        if animate:
            start_pos = QPoint(target_pos.x(), target_pos.y() + ANIMATION_SLIDE_OFFSET_PX)
            if not self.isMaximized():
                self.move(start_pos)
            if supports_opacity:
                self.setWindowOpacity(0.0)
            self.show()
            if supports_raise:
                self.raise_()
            handle = self.windowHandle()
            if handle is not None:
                handle.requestActivate()
            self.activateWindow()
            self.focus_search()

            group = QParallelAnimationGroup(self)
            if supports_opacity:
                fade = QPropertyAnimation(self, b"windowOpacity")
                fade.setDuration(ANIMATION_DURATION_MS)
                fade.setStartValue(0.0)
                fade.setEndValue(1.0)
                fade.setEasingCurve(QEasingCurve.Type.OutCubic)
                group.addAnimation(fade)

            slide = QPropertyAnimation(self, b"pos")
            slide.setDuration(ANIMATION_DURATION_MS)
            slide.setStartValue(start_pos if not self.isMaximized() else target_pos)
            slide.setEndValue(target_pos)
            slide.setEasingCurve(QEasingCurve.Type.OutCubic)
            group.addAnimation(slide)

            self._anim_group = group
            group.start()
        else:
            if supports_opacity:
                self.setWindowOpacity(1.0)
            self.show()
            if supports_raise:
                self.raise_()
            handle = self.windowHandle()
            if handle is not None:
                handle.requestActivate()
            self.activateWindow()
            QApplication.setActiveWindow(self)
            self.focus_search()
        self._elide_footer_hints()

        logger.info("Katman açıldı (kategori=%s, kayıt=%d).", self._active_category, self.list_model.rowCount())

    def hide_overlay(self, *, animate: bool = True) -> None:
        """Katmanı 180 ms animasyonla kapatır."""
        if self._anim_group is not None:
            self._anim_group.stop()
        if not self.isVisible():
            return
        logger.debug("Katman gizlendi.")
        if not animate:
            self.hide()
            return

        cur_pos = self.pos()
        end_pos = QPoint(cur_pos.x(), cur_pos.y() + ANIMATION_SLIDE_OFFSET_PX)

        group = QParallelAnimationGroup(self)
        if self._supports_window_opacity():
            fade = QPropertyAnimation(self, b"windowOpacity")
            fade.setDuration(ANIMATION_DURATION_MS)
            fade.setStartValue(self.windowOpacity())
            fade.setEndValue(0.0)
            fade.setEasingCurve(QEasingCurve.Type.InCubic)
            group.addAnimation(fade)

        slide = QPropertyAnimation(self, b"pos")
        slide.setDuration(ANIMATION_DURATION_MS)
        slide.setStartValue(cur_pos)
        slide.setEndValue(end_pos)
        slide.setEasingCurve(QEasingCurve.Type.InCubic)
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
        self._update_responsive_chrome()
        self._elide_footer_hints()
        if self.toast_label.isVisible():
            self._position_toast()
        self.window_resized.emit(self.width(), self.height())
