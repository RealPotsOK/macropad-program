from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtWidgets import QCheckBox, QLabel, QLineEdit, QSpinBox


class MainWindowHelpersMixin:
    def _refresh_status(self) -> None:
        port = str(getattr(self.controller, "selected_port", "") or "auto")
        hint = str(getattr(self.controller, "selected_hint", "") or "none")
        baud = int(getattr(self.controller, "selected_baud", self.settings.baud))
        self._status_message.setText(f"Port {port} | Hint {hint} | Baud {baud}")

    def _update_hidden_label(self) -> None:
        if self._hidden_start:
            self._hidden_label.setText("Hidden startup")
        else:
            self._hidden_label.setText("Visible startup")

    def _current_port_choices(self) -> list[object]:
        get_choices = getattr(self.controller, "port_choices", None)
        if callable(get_choices):
            ports = get_choices()
            if isinstance(ports, Sequence):
                return list(ports)
        return []

    @staticmethod
    def _iter_ports(ports: object) -> list[object]:
        if isinstance(ports, Sequence):
            return list(ports)
        return []

    @staticmethod
    def _set_spin_value(spin: QSpinBox, value: int) -> None:
        spin.blockSignals(True)
        spin.setValue(int(value))
        spin.blockSignals(False)

    @staticmethod
    def _set_checkbox_value(check: QCheckBox, value: bool) -> None:
        check.blockSignals(True)
        check.setChecked(bool(value))
        check.blockSignals(False)

    @staticmethod
    def _set_text(line_edit: QLineEdit, text: str) -> None:
        line_edit.blockSignals(True)
        line_edit.setText(text)
        line_edit.blockSignals(False)

    @staticmethod
    def _pill(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("Pill")
        label.setMargin(6)
        return label
