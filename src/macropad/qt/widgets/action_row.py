from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QWidget,
)


class ActionRow(QWidget):
    browseRequested = Signal()
    changed = Signal(str)

    def __init__(self, title: str, kinds: tuple[str, ...], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.title = title
        self.kind_combo = QComboBox()
        self.kind_combo.addItems(list(kinds))
        self.value_edit = QLineEdit()
        self.value_edit.setPlaceholderText("Action value")
        self.browse_button = QPushButton("Browse")
        self.summary_label = QLabel("")
        self.summary_label.setObjectName("Muted")
        self.summary_label.setVisible(False)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        title_label = QLabel(title)
        title_label.setMinimumWidth(72)
        self.kind_combo.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.kind_combo.setMinimumWidth(110)
        self.kind_combo.setMaximumWidth(170)
        self.value_edit.setMinimumWidth(0)
        self.value_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.value_edit.setMaximumWidth(16_777_215)
        self.browse_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.browse_button.setMaximumWidth(88)
        self.summary_label.setMinimumWidth(0)
        self.summary_label.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        self.summary_label.setMaximumWidth(180)
        layout.addWidget(title_label)
        layout.addWidget(self.kind_combo, 1)
        layout.addWidget(self.value_edit, 6)
        layout.addWidget(self.browse_button)
        layout.addWidget(self.summary_label)
        layout.setStretch(1, 1)
        layout.setStretch(2, 6)

        self.kind_combo.currentTextChanged.connect(self.changed.emit)
        self.value_edit.textChanged.connect(self.changed.emit)
        self.browse_button.clicked.connect(self.browseRequested.emit)

    def action(self) -> tuple[str, str]:
        return (self.kind_combo.currentText().strip(), self.value_edit.text())

    def set_action(self, kind: str, value: str) -> None:
        kind_text = str(kind or "").strip()
        value_text = str(value or "")
        if kind_text:
            index = self.kind_combo.findText(kind_text)
            if index >= 0:
                self.kind_combo.setCurrentIndex(index)
            else:
                self.kind_combo.setCurrentText(kind_text)
        else:
            self.kind_combo.setCurrentIndex(0)
        self.value_edit.setText(value_text)

    def set_summary(self, text: str) -> None:
        summary = str(text or "").strip()
        self.summary_label.setText(summary)
        self.summary_label.setToolTip(summary)
        self.summary_label.setVisible(bool(summary))
