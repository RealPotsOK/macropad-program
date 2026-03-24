from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QLineEdit,
    QVBoxLayout,
)

from .key_lists import keyboard_key_names


class KeyboardPickerDialog(QDialog):
    def __init__(self, *, current_value: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Pick Keyboard Key")
        self.setModal(True)
        self._selected_key = ""
        self.resize(420, 560)

        root = QVBoxLayout(self)
        root.addWidget(QLabel("Choose a keyboard key or media key."))

        self.search = QLineEdit()
        self.search.setPlaceholderText("Filter keys...")
        root.addWidget(self.search)

        self.list_widget = QListWidget()
        self.list_widget.setUniformItemSizes(True)
        self.list_widget.setSpacing(1)
        self.list_widget.setStyleSheet(
            """
            QListWidget {
                padding: 4px;
            }
            QListWidget::item {
                min-height: 0px;
                padding: 3px 8px;
                margin: 0px;
                border-radius: 6px;
            }
            """
        )
        self.list_widget.addItems(keyboard_key_names())
        root.addWidget(self.list_widget, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Ok)
        root.addWidget(buttons)

        buttons.accepted.connect(self._accept_selection)
        buttons.rejected.connect(self.reject)
        self.search.textChanged.connect(self._apply_filter)
        self.list_widget.itemDoubleClicked.connect(lambda _item: self._accept_selection())
        self.list_widget.currentTextChanged.connect(self._on_selection_changed)

        if current_value:
            self._select_value(current_value)
        self._ensure_current_selection()

    def _select_value(self, value: str) -> None:
        normalized = value.strip().lower()
        for index in range(self.list_widget.count()):
            item = self.list_widget.item(index)
            if item is not None and item.text().strip().lower() == normalized:
                self.list_widget.setCurrentItem(item)
                self.list_widget.scrollToItem(item)
                break

    def _apply_filter(self, text: str) -> None:
        query = text.strip().lower()
        for index in range(self.list_widget.count()):
            item = self.list_widget.item(index)
            if item is None:
                continue
            item.setHidden(bool(query) and query not in item.text().lower())
        self._ensure_current_selection()

    def _on_selection_changed(self, value: str) -> None:
        self._selected_key = value

    def _ensure_current_selection(self) -> None:
        current = self.list_widget.currentItem()
        if current is not None and not current.isHidden():
            self._selected_key = current.text()
            return
        for index in range(self.list_widget.count()):
            item = self.list_widget.item(index)
            if item is not None and not item.isHidden():
                self.list_widget.setCurrentItem(item)
                self.list_widget.scrollToItem(item)
                self._selected_key = item.text()
                return
        self._selected_key = ""

    def _accept_selection(self) -> None:
        self._ensure_current_selection()
        if self._selected_key:
            self.accept()

    def selected_key(self) -> str:
        current = self.list_widget.currentItem()
        if current is not None and not current.isHidden():
            return current.text().strip()
        return self._selected_key.strip()
