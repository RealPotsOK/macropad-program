from __future__ import annotations

import asyncio
import re
from contextlib import suppress

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ...core.key_layout import build_display_map, build_virtual_keys
from ...core.profile import KeyBinding
from ..controllers.runtime import QtSessionController
from ..widgets.key_matrix_widget import KeyMatrixWidget


class AutoSetupDialog(QDialog):
    def __init__(
        self,
        controller: QtSessionController,
        *,
        rows: int,
        cols: int,
        has_encoder: bool,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Auto Setup")
        self.setMinimumSize(760, 600)
        self.controller = controller
        self.rows = max(1, int(rows))
        self.cols = max(1, int(cols))
        self.has_encoder = bool(has_encoder)
        self.encoder_inverted: bool | None = None

        self._stage = "keys"
        self._keys = build_virtual_keys(self.rows, self.cols)
        self._index = 0

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        title = QLabel("Auto Setup Wizard")
        title.setObjectName("Section")
        root.addWidget(title)

        self.instruction = QLabel("")
        self.instruction.setWordWrap(True)
        root.addWidget(self.instruction)

        self.matrix = KeyMatrixWidget(layout_map=build_display_map(self.rows, self.cols))
        for row, col in self._keys:
            self.matrix.set_binding(row, col, KeyBinding(label=f"Key {row},{col}"))
        root.addWidget(self.matrix, 1)

        self.status = QLabel("Waiting for input...")
        self.status.setObjectName("Muted")
        root.addWidget(self.status)

        buttons = QDialogButtonBox(QDialogButtonBox.Cancel, Qt.Horizontal, self)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        if hasattr(self.controller, "begin_setup_capture"):
            self.controller.begin_setup_capture()
        if hasattr(self.controller, "rawKeyStateChanged"):
            self.controller.rawKeyStateChanged.connect(self._on_raw_key_state)
        if hasattr(self.controller, "encoderChanged"):
            self.controller.encoderChanged.connect(self._on_encoder_event)

        self._advance_instruction()

    def done(self, result: int) -> None:  # type: ignore[override]
        if hasattr(self.controller, "rawKeyStateChanged"):
            with suppress(TypeError, RuntimeError):
                self.controller.rawKeyStateChanged.disconnect(self._on_raw_key_state)
        if hasattr(self.controller, "encoderChanged"):
            with suppress(TypeError, RuntimeError):
                self.controller.encoderChanged.disconnect(self._on_encoder_event)
        if hasattr(self.controller, "end_setup_capture"):
            self.controller.end_setup_capture()
        super().done(result)

    def _advance_instruction(self) -> None:
        if self._stage == "keys":
            if self._index >= len(self._keys):
                if not self.has_encoder:
                    self.accept()
                    return
                self._stage = "enc_turn"
                self.instruction.setText("Rotate the encoder clockwise once.")
                self.matrix.set_selected_key(-1, -1)
                return
            row, col = self._keys[self._index]
            self.matrix.set_selected_key(row, col)
            self.instruction.setText(
                f"Step {self._index + 1}/{len(self._keys)}: press the physical key for virtual key {row},{col}."
            )
            return

        if self._stage == "enc_turn":
            self.instruction.setText("Rotate the encoder clockwise once.")
            return

        if self._stage == "enc_press":
            self.instruction.setText("Press encoder switch once.")

    def _on_raw_key_state(self, row: int, col: int, pressed: bool) -> None:
        if self._stage != "keys" or not pressed:
            return
        if self._index >= len(self._keys):
            return
        target = self._keys[self._index]
        if hasattr(self.controller, "assign_board_key_mapping"):
            self.controller.assign_board_key_mapping(board_key=(row, col), virtual_key=target)
        self.status.setText(f"Mapped board {row},{col} -> key {target[0]},{target[1]}")
        self._index += 1
        self._advance_instruction()

    def _on_encoder_event(self, text: str) -> None:
        raw = str(text or "").strip()
        if self._stage == "enc_turn" and raw.startswith("ENC="):
            delta_text = raw.split("=", 1)[1].strip()
            if delta_text.startswith("+"):
                delta_text = delta_text[1:]
            with suppress(ValueError):
                delta = int(delta_text, 10)
                if delta != 0:
                    self.encoder_inverted = delta < 0
                    self.status.setText(
                        "Encoder direction captured: "
                        + ("inverted" if self.encoder_inverted else "normal")
                    )
                    self._stage = "enc_press"
                    self._advance_instruction()
            return
        if self._stage == "enc_press" and raw == "ENC_SW=1":
            self.status.setText("Encoder switch captured.")
            self.accept()


class SetupPage(QWidget):
    def __init__(self, controller: QtSessionController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SetupPage")
        self.controller = controller
        self._updating = False
        self._virtual_key_buttons: dict[tuple[int, int], QPushButton] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        top = QFrame(self)
        top.setProperty("panel", True)
        top_layout = QVBoxLayout(top)
        top_layout.setContentsMargins(14, 14, 14, 14)
        top_layout.setSpacing(10)

        top_layout.addWidget(QLabel("Setup"))
        subtitle = QLabel(
            "Configure virtual keys, hardware options, map inputs, and manage setup profiles."
        )
        subtitle.setWordWrap(True)
        subtitle.setObjectName("PageSubtitle")
        top_layout.addWidget(subtitle)

        profile_row = QHBoxLayout()
        profile_row.addWidget(QLabel("Setup Profile"))
        self.profile_combo = QComboBox(top)
        profile_row.addWidget(self.profile_combo, 1)
        self.profile_add_button = QPushButton("Add", top)
        self.profile_rename_button = QPushButton("Rename", top)
        self.profile_delete_button = QPushButton("Delete", top)
        self.profile_save_button = QPushButton("Save", top)
        profile_row.addWidget(self.profile_add_button)
        profile_row.addWidget(self.profile_rename_button)
        profile_row.addWidget(self.profile_delete_button)
        profile_row.addWidget(self.profile_save_button)
        top_layout.addLayout(profile_row)

        form = QFormLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)

        self.rows_spin = QSpinBox(top)
        self.rows_spin.setRange(1, 12)
        self.cols_spin = QSpinBox(top)
        self.cols_spin.setRange(1, 12)
        self.has_encoder = QCheckBox("Encoder enabled", top)
        self.has_screen = QCheckBox("Screen enabled", top)
        self.encoder_inverted = QCheckBox("Invert encoder direction", top)
        self.screen_prefix = _line_edit(top, "TXT:")
        self.screen_separator = _line_edit(top, "|")
        self.screen_end_token = _line_edit(top, "\\n")

        form.addRow("Key rows", self.rows_spin)
        form.addRow("Key cols", self.cols_spin)
        form.addRow("", self.has_encoder)
        form.addRow("", self.has_screen)
        form.addRow("", self.encoder_inverted)
        form.addRow("Screen prefix", self.screen_prefix)
        form.addRow("Line separator", self.screen_separator)
        form.addRow("End token", self.screen_end_token)

        button_row = QHBoxLayout()
        self.save_button = QPushButton("Save Setup", top)
        self.auto_setup_button = QPushButton("Auto Setup", top)
        self.import_format_button = QPushButton("Import from Sample", top)
        self.preview_button = QPushButton("Build Preview", top)
        self.send_button = QPushButton("Send to Screen", top)
        button_row.addWidget(self.save_button)
        button_row.addWidget(self.auto_setup_button)
        button_row.addWidget(self.import_format_button)
        button_row.addWidget(self.preview_button)
        button_row.addWidget(self.send_button)
        button_row.addStretch(1)

        top_layout.addLayout(form)
        top_layout.addLayout(button_row)
        root.addWidget(top, 0)

        body = QSplitter(Qt.Horizontal, self)
        root.addWidget(body, 1)

        left = QFrame(body)
        left.setProperty("panel", True)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(14, 14, 14, 14)
        left_layout.setSpacing(10)
        left_layout.addWidget(QLabel("Virtual Key Mapping"))

        target_row = QHBoxLayout()
        target_row.addWidget(QLabel("Target key"))
        self.target_key_combo = QComboBox(left)
        target_row.addWidget(self.target_key_combo, 1)
        left_layout.addLayout(target_row)

        self.learn_check = QCheckBox("Learn from next key-down", left)
        left_layout.addWidget(self.learn_check)

        self.last_raw = QLabel("Last board key: none")
        self.last_raw.setObjectName("Muted")
        left_layout.addWidget(self.last_raw)

        self.virtual_grid = QWidget(left)
        self.virtual_grid.setObjectName("SetupVirtualGrid")
        self.virtual_grid.setAutoFillBackground(True)
        self.virtual_grid_layout = QGridLayout(self.virtual_grid)
        self.virtual_grid_layout.setContentsMargins(8, 8, 8, 8)
        self.virtual_grid_layout.setSpacing(8)
        left_layout.addWidget(self.virtual_grid, 1)

        clear_row = QHBoxLayout()
        self.clear_mapping_button = QPushButton("Clear Mappings", left)
        clear_row.addWidget(self.clear_mapping_button)
        clear_row.addStretch(1)
        left_layout.addLayout(clear_row)

        right = QFrame(body)
        right.setProperty("panel", True)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(14, 14, 14, 14)
        right_layout.setSpacing(10)

        right_layout.addWidget(QLabel("Learned Board -> Virtual Mapping"))
        self.mapping_list = QListWidget(right)
        right_layout.addWidget(self.mapping_list, 1)

        right_layout.addWidget(QLabel("Screen Text Preview"))
        self.screen_text = QPlainTextEdit(right)
        self.screen_text.setPlaceholderText("PROFILE 1\nVOLUME 75")
        self.screen_text.setFixedHeight(120)
        right_layout.addWidget(self.screen_text)

        self.preview_label = QLabel("")
        self.preview_label.setWordWrap(True)
        self.preview_label.setObjectName("Muted")
        right_layout.addWidget(self.preview_label)

        body.addWidget(left)
        body.addWidget(right)
        body.setStretchFactor(0, 2)
        body.setStretchFactor(1, 3)

        self.save_button.clicked.connect(self._save_setup)
        self.auto_setup_button.clicked.connect(self._run_auto_setup)
        self.import_format_button.clicked.connect(self._import_format_from_sample)
        self.preview_button.clicked.connect(self._build_preview)
        self.send_button.clicked.connect(self._send_preview)
        self.clear_mapping_button.clicked.connect(self._clear_mappings)

        self.profile_combo.currentIndexChanged.connect(self._on_profile_combo_changed)
        self.profile_add_button.clicked.connect(self._add_profile)
        self.profile_rename_button.clicked.connect(self._rename_profile)
        self.profile_delete_button.clicked.connect(self._delete_profile)
        self.profile_save_button.clicked.connect(self._save_profile)

        self.target_key_combo.currentIndexChanged.connect(self._on_target_key_changed)
        self.rows_spin.valueChanged.connect(self._on_dimensions_changed)
        self.cols_spin.valueChanged.connect(self._on_dimensions_changed)

        if hasattr(controller, "setupChanged"):
            controller.setupChanged.connect(self._on_setup_changed)
        if hasattr(controller, "rawKeyStateChanged"):
            controller.rawKeyStateChanged.connect(self._on_raw_key_state)
        if hasattr(controller, "selectedKeyChanged"):
            controller.selectedKeyChanged.connect(self._on_selected_key_changed)

        if hasattr(controller, "setup_state"):
            self._on_setup_changed(controller.setup_state())
        else:
            self._on_setup_changed(
                {
                    "rows": 3,
                    "cols": 4,
                    "has_encoder": True,
                    "has_screen": True,
                    "encoder_inverted": False,
                    "display_map": {},
                    "key_mapping": {},
                    "screen_command_prefix": "TXT:",
                    "screen_line_separator": "|",
                    "screen_end_token": "\\n",
                    "active_setup_profile": "Default",
                    "setup_profiles": ["Default"],
                }
            )
        self._on_selected_key_changed(*controller.selected_key)
        self._build_preview()

    def _on_setup_changed(self, setup: object) -> None:
        if not isinstance(setup, dict):
            return
        self._updating = True
        try:
            rows = int(setup.get("rows", 3))
            cols = int(setup.get("cols", 4))
            self.rows_spin.setValue(rows)
            self.cols_spin.setValue(cols)
            self.has_encoder.setChecked(bool(setup.get("has_encoder", True)))
            self.has_screen.setChecked(bool(setup.get("has_screen", True)))
            self.encoder_inverted.setChecked(bool(setup.get("encoder_inverted", False)))
            self.screen_prefix.setText(str(setup.get("screen_command_prefix", "TXT:")))
            self.screen_separator.setText(str(setup.get("screen_line_separator", "|")))
            self.screen_end_token.setText(str(setup.get("screen_end_token", "\\n")))
            self._rebuild_virtual_key_controls(rows=rows, cols=cols)
            self._refresh_mapping_list(dict(setup.get("key_mapping") or {}))
            self._refresh_setup_profile_combo(
                setup_profiles=list(setup.get("setup_profiles") or []),
                active=str(setup.get("active_setup_profile", "Default")),
            )
        finally:
            self._updating = False
        self._build_preview()

    def _refresh_setup_profile_combo(self, *, setup_profiles: list[object], active: str) -> None:
        names = [str(name).strip() for name in setup_profiles if str(name).strip()]
        if not names:
            names = ["Default"]
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        for name in names:
            self.profile_combo.addItem(name, userData=name)
        index = self.profile_combo.findData(active)
        if index < 0:
            index = 0
        self.profile_combo.setCurrentIndex(index)
        self.profile_combo.blockSignals(False)
        self.profile_delete_button.setEnabled(self.profile_combo.count() > 1)

    def _on_profile_combo_changed(self, index: int) -> None:
        if self._updating:
            return
        name = str(self.profile_combo.itemData(index) or "").strip()
        if not name:
            return
        if hasattr(self.controller, "load_setup_profile"):
            self.controller.load_setup_profile(name)

    def _add_profile(self) -> None:
        text, ok = QInputDialog.getText(self, "Add Setup Profile", "Profile name:")
        if not ok:
            return
        if hasattr(self.controller, "create_setup_profile"):
            created = self.controller.create_setup_profile(text)
            self._select_profile(created)

    def _rename_profile(self) -> None:
        current = self._current_profile_name()
        if not current:
            return
        text, ok = QInputDialog.getText(self, "Rename Setup Profile", "New profile name:", text=current)
        if not ok:
            return
        if hasattr(self.controller, "rename_setup_profile"):
            renamed = self.controller.rename_setup_profile(current, text)
            self._select_profile(renamed)

    def _delete_profile(self) -> None:
        current = self._current_profile_name()
        if not current:
            return
        if QMessageBox.question(
            self,
            "Delete Setup Profile",
            f"Delete setup profile '{current}'?",
            QMessageBox.Yes | QMessageBox.Cancel,
            QMessageBox.Cancel,
        ) != QMessageBox.Yes:
            return
        if hasattr(self.controller, "delete_setup_profile"):
            deleted = self.controller.delete_setup_profile(current)
            if not deleted:
                QMessageBox.information(self, "Setup Profiles", "At least one setup profile must remain.")

    def _save_profile(self) -> None:
        name = self._current_profile_name()
        if not name:
            return
        self._save_setup()
        if hasattr(self.controller, "save_current_setup_to_profile"):
            self.controller.save_current_setup_to_profile(name)

    def _current_profile_name(self) -> str:
        return str(self.profile_combo.currentData() or "").strip()

    def _select_profile(self, name: str) -> None:
        index = self.profile_combo.findData(name)
        if index >= 0:
            self.profile_combo.setCurrentIndex(index)

    def _on_dimensions_changed(self, _value: int) -> None:
        if self._updating:
            return
        self._rebuild_virtual_key_controls(rows=self.rows_spin.value(), cols=self.cols_spin.value())

    def _rebuild_virtual_key_controls(self, *, rows: int, cols: int) -> None:
        while self.virtual_grid_layout.count():
            item = self.virtual_grid_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._virtual_key_buttons.clear()

        keys = build_virtual_keys(rows, cols)

        self.target_key_combo.blockSignals(True)
        self.target_key_combo.clear()
        for row, col in keys:
            text = f"{row},{col}"
            self.target_key_combo.addItem(text, userData=(row, col))
            button = QPushButton(f"R{row} C{col}", self.virtual_grid)
            button.setCheckable(True)
            button.clicked.connect(lambda _checked=False, r=row, c=col: self._set_target_key((r, c)))
            display_row = rows - 1 - row
            self.virtual_grid_layout.addWidget(button, display_row, col)
            self._virtual_key_buttons[(row, col)] = button
        self.target_key_combo.blockSignals(False)

        for row in range(rows):
            self.virtual_grid_layout.setRowStretch(row, 1)
        for col in range(cols):
            self.virtual_grid_layout.setColumnStretch(col, 1)

    def _refresh_mapping_list(self, key_mapping: dict[str, str]) -> None:
        self.mapping_list.clear()
        if not key_mapping:
            self.mapping_list.addItem(QListWidgetItem("No explicit mappings. Identity mapping is used."))
            return
        for board_text, virtual_text in sorted(key_mapping.items()):
            self.mapping_list.addItem(QListWidgetItem(f"Board {board_text} -> Key {virtual_text}"))

    def _on_target_key_changed(self, index: int) -> None:
        if self._updating:
            return
        key = self.target_key_combo.itemData(index)
        if not isinstance(key, tuple) or len(key) != 2:
            return
        self._set_target_key((int(key[0]), int(key[1])))

    def _set_target_key(self, key: tuple[int, int]) -> None:
        index = self.target_key_combo.findData(key)
        if index >= 0 and self.target_key_combo.currentIndex() != index:
            self.target_key_combo.blockSignals(True)
            self.target_key_combo.setCurrentIndex(index)
            self.target_key_combo.blockSignals(False)
        for button_key, button in self._virtual_key_buttons.items():
            button.setChecked(button_key == key)
        current = getattr(self.controller, "selected_key", None)
        if current != key:
            self.controller.select_key(key[0], key[1])

    def _target_key(self) -> tuple[int, int] | None:
        key = self.target_key_combo.currentData()
        if isinstance(key, tuple) and len(key) == 2:
            return int(key[0]), int(key[1])
        return None

    def _on_selected_key_changed(self, row: int, col: int) -> None:
        key = (int(row), int(col))
        if key in self._virtual_key_buttons:
            self._set_target_key(key)

    def _on_raw_key_state(self, row: int, col: int, pressed: bool) -> None:
        self.last_raw.setText(f"Last board key: {row},{col} {'DOWN' if pressed else 'UP'}")
        if not pressed or not self.learn_check.isChecked():
            return
        target = self._target_key()
        if target is None:
            return
        if hasattr(self.controller, "assign_board_key_mapping"):
            self.controller.assign_board_key_mapping(board_key=(row, col), virtual_key=target)

    def _save_setup(self) -> None:
        if not hasattr(self.controller, "update_setup"):
            return
        self.controller.update_setup(
            rows=self.rows_spin.value(),
            cols=self.cols_spin.value(),
            has_encoder=self.has_encoder.isChecked(),
            has_screen=self.has_screen.isChecked(),
            encoder_inverted=self.encoder_inverted.isChecked(),
            screen_command_prefix=self.screen_prefix.text(),
            screen_line_separator=self.screen_separator.text(),
            screen_end_token=self.screen_end_token.text(),
        )

    def _run_auto_setup(self) -> None:
        self._save_setup()
        dialog = AutoSetupDialog(
            self.controller,
            rows=self.rows_spin.value(),
            cols=self.cols_spin.value(),
            has_encoder=self.has_encoder.isChecked(),
            parent=self,
        )
        if dialog.exec() == QDialog.Accepted:
            if dialog.encoder_inverted is not None:
                self.encoder_inverted.setChecked(dialog.encoder_inverted)
            self._save_setup()
            self._save_profile()

    def _build_preview(self) -> None:
        text = self.screen_text.toPlainText()
        prefix = self.screen_prefix.text().strip() or "TXT:"
        separator = self.screen_separator.text()
        end_token = self.screen_end_token.text() or "\\n"
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not separator:
            command = f"{prefix}{(lines[0] if lines else '')}"
            self.preview_label.setText(
                f"Preview: {command}{end_token}  (single-line mode: no separator configured)"
            )
            return
        command = f"{prefix}{separator.join(lines)}"
        self.preview_label.setText(f"Preview: {command}{end_token}")

    def _send_preview(self) -> None:
        self._save_setup()
        if hasattr(self.controller, "send_screen_preview"):
            asyncio.create_task(self.controller.send_screen_preview(self.screen_text.toPlainText()))

    def _clear_mappings(self) -> None:
        if hasattr(self.controller, "clear_board_key_mappings"):
            self.controller.clear_board_key_mappings()

    def _import_format_from_sample(self) -> None:
        sample, ok = QInputDialog.getText(
            self,
            "Import Screen Format",
            "Paste sample command, e.g. display:Abcde|123///",
        )
        if not ok:
            return
        prefix, separator, end_token = parse_screen_format_from_sample(
            sample,
            default_prefix=self.screen_prefix.text().strip() or "TXT:",
            default_separator=self.screen_separator.text(),
            default_end_token=self.screen_end_token.text() or "\\n",
        )
        self.screen_prefix.setText(prefix)
        self.screen_separator.setText(separator)
        self.screen_end_token.setText(end_token)
        self._build_preview()


def _line_edit(parent: QWidget, placeholder: str) -> QLineEdit:
    edit = QLineEdit(parent)
    edit.setPlaceholderText(placeholder)
    return edit


def parse_screen_format_from_sample(
    sample: str,
    *,
    default_prefix: str = "TXT:",
    default_separator: str = "|",
    default_end_token: str = "\\n",
) -> tuple[str, str, str]:
    text = str(sample or "").strip()
    if not text:
        return default_prefix, default_separator, default_end_token

    prefix = default_prefix
    payload = text
    end_token = default_end_token

    delimiter_index = min(
        [
            index
            for index in (
                text.find(":"),
                text.find("="),
            )
            if index >= 0
        ],
        default=-1,
    )
    if delimiter_index >= 0:
        prefix = text[: delimiter_index + 1]
        payload = text[delimiter_index + 1 :]

    if payload.endswith("\\r\\n"):
        payload = payload[: -len("\\r\\n")]
        end_token = "\\r\\n"
    elif payload.endswith("\\n"):
        payload = payload[: -len("\\n")]
        end_token = "\\n"
    elif payload.endswith("\\r"):
        payload = payload[: -len("\\r")]
        end_token = "\\r"
    elif payload.endswith("\r\n"):
        payload = payload[:-2]
        end_token = "\\r\\n"
    elif payload.endswith("\n"):
        payload = payload[:-1]
        end_token = "\\n"
    elif payload.endswith("\r"):
        payload = payload[:-1]
        end_token = "\\r"
    else:
        trailing = re.search(r"([^\w\s])\1{1,}$", payload)
        if trailing is not None:
            end_token = trailing.group(0)
            payload = payload[: -len(end_token)]

    separator = ""
    for candidate in ("|", ";", "~", ",", "/"):
        if candidate not in payload:
            continue
        segments = [segment for segment in payload.split(candidate) if segment]
        if len(segments) >= 2:
            separator = candidate
            break

    return prefix or default_prefix, separator, end_token or default_end_token
