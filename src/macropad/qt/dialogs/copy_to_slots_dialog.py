from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QLabel,
    QRadioButton,
    QVBoxLayout,
)

from ..utils import slot_label


class CopyToSlotsDialog(QDialog):
    def __init__(
        self,
        *,
        current_slot: int,
        current_key: tuple[int, int],
        slot_names: dict[int, str],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Copy To Slots")
        self.setModal(True)
        self._current_slot = int(current_slot)
        self._current_key = current_key
        self._slot_checks: dict[int, QCheckBox] = {}

        root = QVBoxLayout(self)
        root.addWidget(QLabel(f"Current slot: {current_slot} | Selected key: {current_key[0]},{current_key[1]}"))

        self.key_only = QRadioButton("Copy selected key only")
        self.profile_all = QRadioButton("Copy entire profile")
        self.key_only.setChecked(True)
        root.addWidget(self.key_only)
        root.addWidget(self.profile_all)

        self.all_others = QCheckBox("Copy to all other slots")
        self.all_others.setChecked(True)
        root.addWidget(self.all_others)

        grid = QGridLayout()
        root.addLayout(grid)
        grid.addWidget(QLabel("Or pick target slots:"), 0, 0, 1, 3)

        slots = [slot for slot in range(1, 11) if slot != self._current_slot]
        for index, slot in enumerate(slots):
            check = QCheckBox(slot_label(slot, slot_names.get(slot, f"Profile {slot}")))
            self._slot_checks[slot] = check
            row = (index // 3) + 1
            col = index % 3
            grid.addWidget(check, row, col)

        buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Ok)
        root.addWidget(buttons)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        self.all_others.toggled.connect(self._refresh_target_state)
        self._refresh_target_state()

    def _refresh_target_state(self) -> None:
        enabled = not self.all_others.isChecked()
        for check in self._slot_checks.values():
            check.setEnabled(enabled)

    def copy_scope(self) -> str:
        return "profile" if self.profile_all.isChecked() else "key"

    def target_slots(self) -> list[int]:
        if self.all_others.isChecked():
            return [slot for slot in range(1, 11) if slot != self._current_slot]
        return [slot for slot, check in sorted(self._slot_checks.items()) if check.isChecked()]

