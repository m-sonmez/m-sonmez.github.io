"""İçerik genişliğe sığmadığında widget'ları otomatik alt satıra akıtan esnek Qt düzeni."""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import QPoint, QRect, QSize, Qt
from PyQt6.QtWidgets import QLayout, QLayoutItem, QSizePolicy, QStyle, QWidget


class FlowLayout(QLayout):
    """Yatayda sığmayan alt bileşenleri otomatik olarak alt satıra kaydıran QLayout alt sınıfı."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        margin: int = -1,
        h_spacing: int = 6,
        v_spacing: int = 6,
        spacing: int | None = None,
    ):
        super().__init__(parent)
        self._items: list[QLayoutItem] = []
        if spacing is not None:
            h_spacing = spacing
            v_spacing = spacing
        self._h_space = int(h_spacing)
        self._v_space = int(v_spacing)
        if margin >= 0:
            self.setContentsMargins(margin, margin, margin, margin)

    def __del__(self) -> None:
        try:
            while self.count():
                self.takeAt(0)
        except RuntimeError:
            pass

    def addItem(self, item: QLayoutItem | None) -> None:
        if item is not None:
            self._items.append(item)

    def horizontalSpacing(self) -> int:
        if self._h_space >= 0:
            return self._h_space
        return self._smart_spacing(QStyle.PixelMetric.PM_LayoutHorizontalSpacing)

    def verticalSpacing(self) -> int:
        if self._v_space >= 0:
            return self._v_space
        return self._smart_spacing(QStyle.PixelMetric.PM_LayoutVerticalSpacing)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int) -> QLayoutItem | None:
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index: int) -> QLayoutItem | None:
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self) -> Qt.Orientation:
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._do_layout(QRect(0, 0, max(1, width), 0), test_only=True)

    def setGeometry(self, rect: QRect) -> None:
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        size = QSize()
        for item in self._items:
            wid = item.widget()
            if wid is not None and wid.isHidden():
                continue
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def _do_layout(self, rect: QRect, *, test_only: bool) -> int:
        left, top, right, bottom = self.getContentsMargins()
        effective = rect.adjusted(left, top, -right, -bottom)
        x = effective.x()
        y = effective.y()
        line_height = 0
        space_x_default = self.horizontalSpacing()
        space_y_default = self.verticalSpacing()

        for item in self._items:
            wid: Any = item.widget()
            if wid is not None and wid.isHidden():
                continue
            space_x = space_x_default
            space_y = space_y_default
            if wid is not None and (space_x < 0 or space_y < 0):
                style = wid.style()
                if style is not None:
                    if space_x < 0:
                        space_x = style.layoutSpacing(
                            QSizePolicy.ControlType.PushButton,
                            QSizePolicy.ControlType.PushButton,
                            Qt.Orientation.Horizontal,
                        )
                    if space_y < 0:
                        space_y = style.layoutSpacing(
                            QSizePolicy.ControlType.PushButton,
                            QSizePolicy.ControlType.PushButton,
                            Qt.Orientation.Vertical,
                        )
            space_x = max(0, space_x)
            space_y = max(0, space_y)

            hint = item.sizeHint()
            next_x = x + hint.width() + space_x
            if next_x - space_x > effective.right() and line_height > 0:
                x = effective.x()
                y += line_height + space_y
                next_x = x + hint.width() + space_x
                line_height = 0

            if not test_only:
                item_w = min(hint.width(), max(1, effective.width())) if effective.width() > 0 else hint.width()
                item.setGeometry(QRect(QPoint(x, y), QSize(item_w, hint.height())))

            x = next_x
            line_height = max(line_height, hint.height())

        return y + line_height - rect.y() + bottom

    def _smart_spacing(self, pm: QStyle.PixelMetric) -> int:
        parent = self.parent()
        if parent is None:
            return -1
        if isinstance(parent, QWidget):
            style = parent.style()
            return style.pixelMetric(pm, None, parent) if style is not None else -1
        return -1
