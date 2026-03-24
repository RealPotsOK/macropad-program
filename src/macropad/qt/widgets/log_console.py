from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QPushButton, QPlainTextEdit, QVBoxLayout, QWidget


class LogConsole(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.editor = QPlainTextEdit()
        self.editor.setReadOnly(True)
        self.editor.setMaximumBlockCount(2000)
        self.editor.setPlaceholderText("Diagnostics and raw RX log")
        self.clear_button = QPushButton("Clear")
        self.copy_button = QPushButton("Copy")

        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.setSpacing(8)
        buttons.addWidget(self.copy_button)
        buttons.addWidget(self.clear_button)
        buttons.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addLayout(buttons)
        layout.addWidget(self.editor, 1)

        self.clear_button.clicked.connect(self.editor.clear)
        self.copy_button.clicked.connect(self._copy_all)

    def append_line(self, text: str) -> None:
        line = str(text).rstrip()
        if not line:
            return
        self.editor.appendPlainText(line)
        bar = self.editor.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _copy_all(self) -> None:
        self.editor.selectAll()
        self.editor.copy()
        self.editor.moveCursor(self.editor.textCursor().End)
