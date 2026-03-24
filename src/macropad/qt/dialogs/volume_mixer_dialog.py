from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QFormLayout,
    QDoubleSpinBox,
    QVBoxLayout,
)

from ...core.volume_mixer import (
    VolumeMixerError,
    VolumeMixerSpec,
    VolumeMixerTarget,
    format_volume_mixer_value,
    list_volume_mixer_targets,
    parse_volume_mixer_value,
)


class VolumeMixerDialog(QDialog):
    def __init__(self, *, current_value: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Volume Mixer Action")
        self.setModal(True)

        spec = parse_volume_mixer_value(current_value)
        root = QVBoxLayout(self)
        form = QFormLayout()
        root.addLayout(form)
        self._targets: list[VolumeMixerTarget] = []

        self.target = QComboBox()
        self.target.setEditable(True)
        form.addRow("App", self.target)

        self.step = QDoubleSpinBox()
        self.step.setDecimals(3)
        self.step.setRange(-1.0, 1.0)
        self.step.setSingleStep(0.05)
        self.step.setValue(float(spec.step))
        form.addRow("Step", self.step)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

        buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Ok)
        root.addWidget(buttons)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        self._populate_targets(spec)

    def _populate_targets(self, spec: VolumeMixerSpec) -> None:
        self.target.clear()
        self._targets.clear()
        self.target.addItem(spec.target_value or "")

        try:
            targets = list_volume_mixer_targets()
        except VolumeMixerError as exc:
            self.status_label.setText(str(exc))
            return

        self._targets.extend(targets)
        current_index = 0
        for index, item in enumerate(targets, start=1):
            self.target.addItem(item.label, userData=(item.target_kind, item.target_value))
            if (
                item.target_kind == spec.target_kind
                and item.target_value.strip().lower() == spec.target_value.strip().lower()
            ):
                current_index = index

        if targets:
            self.status_label.setText("Pick an active mixer app or type one manually.")
        else:
            self.status_label.setText("No active mixer apps found. Start audio playback first, or type a process name.")

        if current_index > 0:
            self.target.setCurrentIndex(current_index)
        else:
            self.target.setCurrentText(spec.target_value or "")

    def value(self) -> str:
        current_index = self.target.currentIndex()
        current_data = self.target.itemData(current_index)
        current_text = self.target.currentText().strip()
        target_kind = "process"
        target_value = current_text
        if isinstance(current_data, tuple) and len(current_data) == 2:
            selected_label = self.target.itemText(current_index).strip()
            if current_text == selected_label:
                target_kind = str(current_data[0] or "process").strip().lower() or "process"
                target_value = str(current_data[1] or current_text).strip()
        spec = VolumeMixerSpec(
            target_kind=target_kind,
            target_value=target_value,
            step=float(self.step.value()),
        )
        return format_volume_mixer_value(spec)
