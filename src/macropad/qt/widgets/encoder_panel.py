from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox, QFrame, QGridLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from .action_row import ActionRow


class EncoderPanel(QFrame):
    saveRequested = Signal()
    actionChanged = Signal(str)
    browseRequested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("panel", True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        title = QLabel("Encoder")
        title.setObjectName("Section")
        layout.addWidget(title)

        kinds = (
            "none",
            "keyboard",
            "file",
            "volume_mixer",
            "change_profile",
            "window_control",
        )
        self.up_row = ActionRow("Turn up", kinds)
        self.down_row = ActionRow("Turn down", kinds)
        self.sw_down_row = ActionRow("Press down", kinds)
        self.sw_up_row = ActionRow("Press up", kinds)
        for row in (self.up_row, self.down_row, self.sw_down_row, self.sw_up_row):
            layout.addWidget(row)
            row.changed.connect(lambda *_args, row=row: self.actionChanged.emit(row.title))
        self.up_row.browseRequested.connect(lambda: self.browseRequested.emit("up"))
        self.down_row.browseRequested.connect(lambda: self.browseRequested.emit("down"))
        self.sw_down_row.browseRequested.connect(lambda: self.browseRequested.emit("sw_down"))
        self.sw_up_row.browseRequested.connect(lambda: self.browseRequested.emit("sw_up"))

        footer = QGridLayout()
        self.learn_check = QCheckBox("Learn mode")
        self.save_button = QPushButton("Save encoder")
        footer.addWidget(self.learn_check, 0, 0)
        footer.addWidget(self.save_button, 0, 1)
        footer.setColumnStretch(1, 1)
        layout.addLayout(footer)

        self.save_button.clicked.connect(self.saveRequested.emit)

    def set_actions(self, *, up, down, sw_down, sw_up) -> None:
        self.up_row.set_action(up.kind, up.value)
        self.down_row.set_action(down.kind, down.value)
        self.sw_down_row.set_action(sw_down.kind, sw_down.value)
        self.sw_up_row.set_action(sw_up.kind, sw_up.value)

    def actions(self) -> dict[str, tuple[str, str]]:
        return {
            "up": self.up_row.action(),
            "down": self.down_row.action(),
            "sw_down": self.sw_down_row.action(),
            "sw_up": self.sw_up_row.action(),
        }

    def action(self, direction: str) -> tuple[str, str]:
        return self._row_for_direction(direction).action()

    def set_action_value(self, direction: str, value: str) -> None:
        row = self._row_for_direction(direction)
        kind, _current_value = row.action()
        row.set_action(kind, value)

    def _row_for_direction(self, direction: str) -> ActionRow:
        normalized = direction.strip().lower()
        if normalized == "up":
            return self.up_row
        if normalized == "down":
            return self.down_row
        if normalized == "sw_down":
            return self.sw_down_row
        if normalized == "sw_up":
            return self.sw_up_row
        raise ValueError(f"Unknown encoder direction: {direction}")
