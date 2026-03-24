from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QSpinBox,
    QVBoxLayout,
)

from ...core.actions import (
    PROFILE_MAX_DEFAULT,
    PROFILE_MIN_DEFAULT,
    ProfileChangeSpec,
    format_change_profile_value,
    parse_change_profile_value,
)


class ChangeProfileDialog(QDialog):
    def __init__(self, *, current_value: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Change Profile Action")
        self.setModal(True)

        spec = parse_change_profile_value(current_value)
        root = QVBoxLayout(self)
        form = QFormLayout()
        root.addLayout(form)

        self.mode = QComboBox()
        self.mode.addItems(["set", "next", "prev"])
        self.mode.setCurrentText(spec.mode)
        form.addRow("Mode", self.mode)

        self.target = QSpinBox()
        self.target.setRange(1, 999)
        self.target.setValue(spec.target or PROFILE_MIN_DEFAULT)
        form.addRow("Target slot", self.target)

        self.step = QSpinBox()
        self.step.setRange(1, 999)
        self.step.setValue(max(1, spec.step))
        form.addRow("Step", self.step)

        self.min_slot = QSpinBox()
        self.min_slot.setRange(1, 999)
        self.min_slot.setValue(max(1, spec.min_slot))
        form.addRow("Min slot", self.min_slot)

        self.max_slot = QSpinBox()
        self.max_slot.setRange(1, 999)
        self.max_slot.setValue(max(self.min_slot.value(), spec.max_slot))
        form.addRow("Max slot", self.max_slot)

        buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Ok)
        root.addWidget(buttons)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        self.mode.currentTextChanged.connect(self._refresh_enabled)
        self._refresh_enabled()

    def _refresh_enabled(self) -> None:
        mode = self.mode.currentText().strip().lower()
        self.target.setEnabled(mode == "set")
        self.step.setEnabled(mode in {"next", "prev"})

    def value(self) -> str:
        mode = self.mode.currentText().strip().lower()
        spec = ProfileChangeSpec(
            mode=mode,
            target=int(self.target.value()) if mode == "set" else None,
            step=int(self.step.value()),
            min_slot=int(self.min_slot.value()),
            max_slot=int(self.max_slot.value()),
        )
        return format_change_profile_value(spec)

