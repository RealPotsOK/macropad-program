from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ...core.actions import (
    ACTION_CHANGE_PROFILE,
    ACTION_FILE,
    ACTION_KEYBOARD,
    ACTION_NONE,
    ACTION_VOLUME_MIXER,
    ACTION_WINDOW_CONTROL,
    format_audio_file_action_value,
    format_change_profile_value,
    is_audio_file_path,
    parse_file_action_value,
    parse_change_profile_value,
)
from ...core.profile import KeyAction, KeyBinding
from ...core.step_blocks import parse_step_script
from ...core.volume_mixer import format_volume_mixer_value, parse_volume_mixer_value
from ...core.window_control import format_window_control_value, parse_window_control_value
from ..controllers.runtime import QtSessionController
from ..dialogs.change_profile_dialog import ChangeProfileDialog
from ..dialogs.keyboard_picker_dialog import KeyboardPickerDialog
from ..dialogs.volume_mixer_dialog import VolumeMixerDialog
from ..dialogs.window_control_dialog import WindowControlDialog
from ..widgets.action_row import ActionRow
from ..widgets.encoder_panel import EncoderPanel
from ..widgets.key_matrix_widget import KeyMatrixWidget
from ..widgets.log_console import LogConsole


class ControllerPage(QWidget):
    learnModeChanged = Signal(bool)

    def __init__(self, controller: QtSessionController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.controller = controller

        self.matrix = KeyMatrixWidget()
        self.matrix.keySelected.connect(self._on_key_selected)
        self.encoder_panel = EncoderPanel()
        self.log_console = LogConsole()
        self.selected_panel = _SelectedKeyPanel()

        left = QFrame()
        left.setProperty("panel", True)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(14, 14, 14, 14)
        left_layout.setSpacing(12)
        left_layout.addWidget(QLabel("Key Matrix"))
        left_layout.addWidget(self.matrix, 1)
        left_layout.addWidget(self.encoder_panel, 0)

        right = QFrame()
        right.setProperty("panel", True)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(14, 14, 14, 14)
        right_layout.setSpacing(12)
        right_layout.addWidget(self.selected_panel, 0)
        right_layout.addWidget(self.log_console, 1)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([1, 1])

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(splitter, 1)

        self.selected_panel.applyRequested.connect(self._apply_selected_binding)
        self.selected_panel.browseRequested.connect(self._browse_selected_binding)
        self.encoder_panel.saveRequested.connect(self._save_encoder_bindings)
        self.encoder_panel.browseRequested.connect(self._browse_encoder_action)
        self.encoder_panel.learn_check.toggled.connect(self.learnModeChanged.emit)

        controller.logMessage.connect(self.log_console.append_line)
        controller.profileChanged.connect(self._on_profile_changed)
        controller.selectedKeyChanged.connect(self._on_selected_key_changed)
        controller.selectedBindingChanged.connect(self._on_selected_binding)
        controller.keyStateChanged.connect(self.matrix.set_key_state)
        controller.encoderChanged.connect(self.log_console.append_line)
        controller.lastPacketChanged.connect(self._on_last_packet)
        if hasattr(controller, "setupChanged"):
            controller.setupChanged.connect(self._on_setup_changed)

        if hasattr(controller, "setup_state"):
            self._on_setup_changed(controller.setup_state())
        self._sync_profile_state()
        self._on_selected_key_changed(*controller.selected_key)
        self.set_learn_mode_checked(getattr(controller, "learn_mode", False))

    def _on_profile_changed(self, _slot: int, profile) -> None:
        self.matrix.set_profile_bindings(profile.bindings)
        self.encoder_panel.set_actions(
            up=profile.enc_up_action,
            down=profile.enc_down_action,
            sw_down=profile.enc_sw_down_action,
            sw_up=profile.enc_sw_up_action,
        )

    def _on_selected_key_changed(self, row: int, col: int) -> None:
        self.matrix.set_selected_key(row, col)
        binding = self.controller.current_binding()
        self.selected_panel.set_key(row, col)
        self.selected_panel.set_binding(binding)

    def _on_key_selected(self, row: int, col: int) -> None:
        self.controller.select_key(row, col)

    def _on_selected_binding(self, binding: KeyBinding) -> None:
        self.selected_panel.set_binding(binding)
        row, col = self.controller.selected_key
        self.matrix.set_binding(row, col, binding)

    def _on_last_packet(self, text: str) -> None:
        self.log_console.append_line(f"Last packet: {text}")

    def _on_setup_changed(self, setup: object) -> None:
        if not isinstance(setup, dict):
            return
        display_map = setup.get("display_map")
        if isinstance(display_map, dict):
            self.matrix.set_layout_map(display_map)
        has_encoder = bool(setup.get("has_encoder", True))
        self.encoder_panel.setVisible(has_encoder)

    def _sync_profile_state(self) -> None:
        profile = self.controller.current_profile
        self.matrix.set_profile_bindings(profile.bindings)
        self.encoder_panel.set_actions(
            up=profile.enc_up_action,
            down=profile.enc_down_action,
            sw_down=profile.enc_sw_down_action,
            sw_up=profile.enc_sw_up_action,
        )

    def set_learn_mode_checked(self, enabled: bool) -> None:
        self.encoder_panel.learn_check.blockSignals(True)
        self.encoder_panel.learn_check.setChecked(bool(enabled))
        self.encoder_panel.learn_check.blockSignals(False)

    def _apply_selected_binding(self) -> None:
        kind, value = self.selected_panel.action()
        label = self.selected_panel.label_edit.text()
        self.controller.update_selected_binding(kind=kind, value=value, label=label)

    def _browse_selected_binding(self) -> None:
        kind, value = self.selected_panel.action()
        selected = self._browse_action_value(kind, value)
        if selected is not None:
            self.selected_panel.value_edit.setText(selected)

    def _browse_encoder_action(self, direction: str) -> None:
        kind, value = self.encoder_panel.action(direction)
        selected = self._browse_action_value(kind, value)
        if selected is not None:
            self.encoder_panel.set_action_value(direction, selected)

    def _browse_action_value(self, kind: str, value: str) -> str | None:
        normalized = kind.strip().lower()
        if normalized == ACTION_KEYBOARD:
            dialog = KeyboardPickerDialog(current_value=value, parent=self)
            if dialog.exec() == QDialog.DialogCode.Accepted and dialog.selected_key():
                return dialog.selected_key()
            return None
        if normalized == ACTION_FILE:
            path_text, _filter = QFileDialog.getOpenFileName(self, "Choose File", "", "All Files (*)")
            return path_text or None
        if normalized == ACTION_VOLUME_MIXER:
            dialog = VolumeMixerDialog(current_value=value, parent=self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                return dialog.value()
            return None
        if normalized == ACTION_CHANGE_PROFILE:
            dialog = ChangeProfileDialog(current_value=value, parent=self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                return dialog.value()
            return None
        if normalized == ACTION_WINDOW_CONTROL:
            dialog = WindowControlDialog(current_value=value, parent=self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                return dialog.value()
            return None
        QMessageBox.information(self, "Browse", "This action type does not use Browse.")
        return None

    def _save_encoder_bindings(self) -> None:
        actions = self.encoder_panel.actions()
        for direction, (kind, value) in actions.items():
            self.controller.update_encoder_binding(direction, kind=kind, value=value)
        self.log_console.append_line("Encoder bindings saved.")


class _SelectedKeyPanel(QFrame):
    applyRequested = Signal()
    browseRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("panel", True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        title = QLabel("Selected Key")
        title.setObjectName("Section")
        self.key_label = QLabel("Key 0,0")
        self.key_label.setObjectName("Muted")
        self.label_edit = QLineEdit()
        self.label_edit.setPlaceholderText("Key label")
        self._audio_volume = 100
        self.action_row = ActionRow(
            "Action",
            (
                ACTION_NONE,
                ACTION_KEYBOARD,
                ACTION_FILE,
                ACTION_VOLUME_MIXER,
                ACTION_CHANGE_PROFILE,
                ACTION_WINDOW_CONTROL,
            ),
        )
        self.value_edit = self.action_row.value_edit
        self.audio_volume_row = QFrame(self)
        self.audio_volume_row.setObjectName("AudioVolumeRow")
        audio_layout = QHBoxLayout(self.audio_volume_row)
        audio_layout.setContentsMargins(0, 0, 0, 0)
        audio_layout.setSpacing(8)
        self.audio_volume_label = QLabel("Audio volume")
        self.audio_volume_label.setObjectName("AudioVolumeLabel")
        self.audio_volume_slider = QSlider(Qt.Horizontal, self.audio_volume_row)
        self.audio_volume_slider.setObjectName("AudioVolumeSlider")
        self.audio_volume_slider.setRange(0, 100)
        self.audio_volume_slider.setValue(self._audio_volume)
        self.audio_volume_slider.setSingleStep(1)
        self.audio_volume_slider.setPageStep(5)
        self.audio_volume_spin = QSpinBox(self.audio_volume_row)
        self.audio_volume_spin.setObjectName("AudioVolumeSpin")
        self.audio_volume_spin.setRange(0, 100)
        self.audio_volume_spin.setValue(self._audio_volume)
        self.audio_volume_spin.setSuffix("%")
        self.audio_volume_spin.setFixedWidth(84)
        audio_layout.addWidget(self.audio_volume_label)
        audio_layout.addWidget(self.audio_volume_slider, 1)
        audio_layout.addWidget(self.audio_volume_spin)
        self.audio_volume_row.setVisible(False)
        self.action_row.browseRequested.connect(self.browseRequested.emit)
        self.action_row.changed.connect(self._on_action_row_changed)
        self.audio_volume_slider.valueChanged.connect(self._on_audio_slider_changed)
        self.audio_volume_spin.valueChanged.connect(self._on_audio_spin_changed)
        self.apply_button = QPushButton("Apply to key")
        self.apply_button.clicked.connect(self.applyRequested.emit)

        layout.addWidget(title)
        layout.addWidget(self.key_label)
        layout.addWidget(self.label_edit)
        layout.addWidget(self.action_row)
        layout.addWidget(self.audio_volume_row)
        layout.addWidget(self.apply_button)

    def set_key(self, row: int, col: int) -> None:
        self.key_label.setText(f"Key {row},{col}")

    def set_binding(self, binding: KeyBinding) -> None:
        self.label_edit.setText(binding.label)
        kind = str(binding.action.kind or "").strip().lower()
        value = str(binding.action.value or "")
        display_value = value
        if kind == ACTION_FILE:
            spec = parse_file_action_value(value)
            display_value = spec.path or value
            if is_audio_file_path(spec.path):
                self._set_audio_controls_visible(True)
                self._set_audio_volume(spec.audio_volume if spec.audio_volume is not None else 100)
            else:
                self._set_audio_controls_visible(False)
        else:
            self._set_audio_controls_visible(False)
        self.action_row.set_action(kind, display_value)
        self.action_row.set_summary(_summary_for_binding(binding))
        self._on_action_row_changed()

    def action(self) -> tuple[str, str]:
        kind, value = self.action_row.action()
        normalized_kind = str(kind or "").strip().lower()
        text_value = str(value or "").strip()
        if normalized_kind == ACTION_FILE:
            spec = parse_file_action_value(text_value)
            path_value = str(spec.path or "").strip()
            if not path_value:
                return normalized_kind, ""
            if is_audio_file_path(path_value):
                return normalized_kind, format_audio_file_action_value(path_value, self.audio_volume_spin.value())
            return normalized_kind, path_value
        return normalized_kind, text_value

    def _set_audio_controls_visible(self, visible: bool) -> None:
        self.audio_volume_row.setVisible(bool(visible))

    def _set_audio_volume(self, value: int) -> None:
        clamped = max(0, min(100, int(value)))
        self._audio_volume = clamped
        self.audio_volume_slider.blockSignals(True)
        self.audio_volume_spin.blockSignals(True)
        self.audio_volume_slider.setValue(clamped)
        self.audio_volume_spin.setValue(clamped)
        self.audio_volume_slider.blockSignals(False)
        self.audio_volume_spin.blockSignals(False)

    def _on_audio_slider_changed(self, value: int) -> None:
        self._audio_volume = max(0, min(100, int(value)))
        if self.audio_volume_spin.value() != self._audio_volume:
            self.audio_volume_spin.blockSignals(True)
            self.audio_volume_spin.setValue(self._audio_volume)
            self.audio_volume_spin.blockSignals(False)

    def _on_audio_spin_changed(self, value: int) -> None:
        self._audio_volume = max(0, min(100, int(value)))
        if self.audio_volume_slider.value() != self._audio_volume:
            self.audio_volume_slider.blockSignals(True)
            self.audio_volume_slider.setValue(self._audio_volume)
            self.audio_volume_slider.blockSignals(False)

    def _on_action_row_changed(self, *_args: object) -> None:
        kind, value = self.action_row.action()
        if str(kind or "").strip().lower() != ACTION_FILE:
            self._set_audio_controls_visible(False)
            return
        spec = parse_file_action_value(value)
        path_value = str(spec.path or "").strip()
        if not is_audio_file_path(path_value):
            self._set_audio_controls_visible(False)
            return
        self._set_audio_controls_visible(True)
        if spec.audio_volume is not None:
            self._set_audio_volume(spec.audio_volume)


def _summary_for_action(action: KeyAction) -> str:
    kind = str(action.kind or "").strip().lower()
    value = str(action.value or "").strip()
    if not kind or kind == ACTION_NONE:
        return "none"
    if kind == ACTION_VOLUME_MIXER:
        try:
            value = format_volume_mixer_value(parse_volume_mixer_value(value))
        except Exception:
            pass
    elif kind == ACTION_CHANGE_PROFILE:
        try:
            value = format_change_profile_value(parse_change_profile_value(value))
        except Exception:
            pass
    elif kind == ACTION_WINDOW_CONTROL:
        try:
            value = format_window_control_value(parse_window_control_value(value))
        except Exception:
            pass
    elif kind == ACTION_FILE and value:
        file_spec = parse_file_action_value(value)
        file_name = Path(file_spec.path or value).name.strip()
        if file_name:
            value = file_name
    if value:
        return f"{kind}: {value}"
    return kind


def _summary_for_binding(binding: KeyBinding) -> str:
    action_summary = _summary_for_action(binding.action)
    if action_summary != "none":
        return action_summary
    mode = str(binding.script_mode or "").strip().lower()
    if mode == "step" and bool((binding.script_code or "").strip()):
        count = len(parse_step_script(binding.script_code))
        return f"step: {count} block(s)" if count else "step"
    return "none"
