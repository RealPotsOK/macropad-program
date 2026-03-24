from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QStyledItemDelegate, QStyle, QStyleOptionViewItem

from .constants import ITEM_BG_ROLE, ITEM_SEPARATOR_BEFORE_ROLE, ITEM_TEXT_ROLE


class BlockItemDelegate(QStyledItemDelegate):
    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:  # type: ignore[override]
        painter.save()
        if bool(index.data(ITEM_SEPARATOR_BEFORE_ROLE)):
            divider_pen = QPen(QColor(209, 213, 219, 120), 1)
            painter.setPen(divider_pen)
            line_y = option.rect.top() + 1
            painter.drawLine(option.rect.left() + 10, line_y, option.rect.right() - 10, line_y)
        rect = option.rect.adjusted(4, 3, -4, -3)
        bg = QColor(str(index.data(ITEM_BG_ROLE) or "#E5E7EB"))
        text = str(index.data(ITEM_TEXT_ROLE) or index.data(Qt.ItemDataRole.DisplayRole) or "")
        selected = bool(option.state & QStyle.StateFlag.State_Selected)

        border = QColor("#60A5FA") if selected else bg.darker(118)
        if selected:
            bg = bg.lighter(97)

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QPen(border, 2 if selected else 1))
        painter.setBrush(bg)
        painter.drawRoundedRect(rect, 10, 10)

        text_rect = rect.adjusted(12, 8, -12, -8)
        painter.setPen(QColor("#0F172A"))
        painter.drawText(text_rect, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextWordWrap), text)
        painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index):  # type: ignore[override]
        size = super().sizeHint(option, index)
        text = str(index.data(ITEM_TEXT_ROLE) or index.data(Qt.ItemDataRole.DisplayRole) or "")
        lines = max(1, text.count("\n") + 1)
        height = max(42, 24 + lines * 18)
        size.setHeight(height)
        return size
