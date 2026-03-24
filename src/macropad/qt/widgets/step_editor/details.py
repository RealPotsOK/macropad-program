from __future__ import annotations

from typing import Any

from PySide6.QtCore import QSignalBlocker, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ...dialogs.keyboard_picker_dialog import KeyboardPickerDialog
from ....core.step_blocks import (
    BLOCK_CLICK_MOUSE,
    BLOCK_END,
    BLOCK_FOREVER,
    BLOCK_HOLD_KEY,
    BLOCK_IF_ELSE_PRESSED,
    BLOCK_IF_MOUSE_PRESSED,
    BLOCK_IF_PRESSED,
    BLOCK_MOVE_MOUSE,
    BLOCK_PRESS_KEY,
    BLOCK_RELEASE_KEY,
    BLOCK_REPEAT,
    BLOCK_RESTORE_MOUSE_POS,
    BLOCK_SAVE_MOUSE_POS,
    BLOCK_TYPE_TEXT,
    BLOCK_WAIT,
    BLOCK_WHILE_MOUSE_PRESSED,
    BLOCK_WHILE_PRESSED,
    MOVE_TARGET_COORDS,
    MOVE_TARGET_SAVED,
    STEP_BLOCK_TYPES,
    default_step_block,
    normalize_step_block,
)
from .constants import BLOCK_LABELS


class BlockDetailsWidget(QWidget):
    updated = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._block: dict[str, Any] = default_step_block(BLOCK_END)
        self._loading = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(QLabel("Edit the selected step block. Only the fields used by the selected block type are saved."))

        form = QFormLayout()
        root.addLayout(form)
        self._rows: dict[str, tuple[QWidget, QWidget]] = {}

        self.type_combo = QComboBox()
        for block_type in STEP_BLOCK_TYPES:
            label = BLOCK_LABELS.get(block_type, block_type)
            self.type_combo.addItem(label, userData=block_type)
        self._add_row(form, "type", "Type", self.type_combo)

        self.target_combo = QComboBox()
        self.target_combo.addItem("Mouse coordinates", userData=MOVE_TARGET_COORDS)
        self.target_combo.addItem("Saved position", userData=MOVE_TARGET_SAVED)
        self._add_row(form, "target", "Move target", self.target_combo)

        self.x_spin = QSpinBox()
        self.x_spin.setRange(-32000, 32000)
        self._add_row(form, "x", "Mouse X", self.x_spin)

        self.y_spin = QSpinBox()
        self.y_spin.setRange(-32000, 32000)
        self._add_row(form, "y", "Mouse Y", self.y_spin)

        self.button_combo = QComboBox()
        self.button_combo.addItems(["left", "right", "middle"])
        self._add_row(form, "button", "Button", self.button_combo)

        self.clicks_spin = QSpinBox()
        self.clicks_spin.setRange(1, 50)
        self._add_row(form, "clicks", "Clicks", self.clicks_spin)

        self.text_edit = QPlainTextEdit()
        self.text_edit.setPlaceholderText("Text to type")
        self.text_edit.setMaximumHeight(100)
        self._add_row(form, "text", "Text", self.text_edit)

        self.key_edit = QLineEdit()
        self.key_browse = QPushButton("Browse")
        key_row = QWidget()
        key_layout = QHBoxLayout(key_row)
        key_layout.setContentsMargins(0, 0, 0, 0)
        key_layout.addWidget(self.key_edit, 1)
        key_layout.addWidget(self.key_browse)
        self._add_row(form, "key", "Key", key_row)

        self.seconds_spin = QDoubleSpinBox()
        self.seconds_spin.setDecimals(3)
        self.seconds_spin.setRange(0.0, 600.0)
        self.seconds_spin.setSingleStep(0.05)
        self._add_row(form, "seconds", "Seconds", self.seconds_spin)

        self.times_spin = QSpinBox()
        self.times_spin.setRange(1, 10000)
        self._add_row(form, "times", "Repeat count", self.times_spin)

        self.max_loops_spin = QSpinBox()
        self.max_loops_spin.setRange(1, 100000)
        self._add_row(form, "max_loops", "Max loops", self.max_loops_spin)

        self.interval_spin = QDoubleSpinBox()
        self.interval_spin.setDecimals(3)
        self.interval_spin.setRange(0.0, 10.0)
        self.interval_spin.setSingleStep(0.05)
        self._add_row(form, "interval", "Loop interval", self.interval_spin)

        self.summary = QLabel("")
        self.summary.setWordWrap(True)
        root.addWidget(self.summary)

        self.type_combo.currentIndexChanged.connect(self._emit_updated)
        self.target_combo.currentIndexChanged.connect(self._emit_updated)
        self.x_spin.valueChanged.connect(self._emit_updated)
        self.y_spin.valueChanged.connect(self._emit_updated)
        self.button_combo.currentIndexChanged.connect(self._emit_updated)
        self.clicks_spin.valueChanged.connect(self._emit_updated)
        self.text_edit.textChanged.connect(self._emit_updated)
        self.key_edit.textChanged.connect(self._emit_updated)
        self.seconds_spin.valueChanged.connect(self._emit_updated)
        self.times_spin.valueChanged.connect(self._emit_updated)
        self.max_loops_spin.valueChanged.connect(self._emit_updated)
        self.interval_spin.valueChanged.connect(self._emit_updated)
        self.key_browse.clicked.connect(self._browse_key)
        self._refresh_row_visibility()

    def _add_row(self, form: QFormLayout, key: str, label_text: str, field: QWidget) -> None:
        label = QLabel(label_text, self)
        self._rows[key] = (label, field)
        form.addRow(label, field)

    def _set_row_visible(self, key: str, visible: bool) -> None:
        label, field = self._rows[key]
        label.setVisible(visible)
        field.setVisible(visible)

    def _refresh_row_visibility(self) -> None:
        block_type = str(self.type_combo.currentData() or BLOCK_END)
        move_target = str(self.target_combo.currentData() or MOVE_TARGET_COORDS)
        visible_rows = {"type"}

        if block_type == BLOCK_MOVE_MOUSE:
            visible_rows.update({"target"})
            if move_target == MOVE_TARGET_COORDS:
                visible_rows.update({"x", "y"})
        elif block_type == BLOCK_CLICK_MOUSE:
            visible_rows.update({"button", "clicks"})
        elif block_type == BLOCK_TYPE_TEXT:
            visible_rows.update({"text"})
        elif block_type in {BLOCK_PRESS_KEY, BLOCK_HOLD_KEY, BLOCK_RELEASE_KEY, BLOCK_IF_PRESSED, BLOCK_IF_ELSE_PRESSED, BLOCK_WHILE_PRESSED}:
            visible_rows.update({"key"})
        elif block_type in {BLOCK_IF_MOUSE_PRESSED, BLOCK_WHILE_MOUSE_PRESSED}:
            visible_rows.update({"button"})
        elif block_type == BLOCK_REPEAT:
            visible_rows.update({"times"})
        elif block_type == BLOCK_FOREVER:
            visible_rows.update({"interval"})
        elif block_type == BLOCK_WAIT:
            visible_rows.update({"seconds"})

        for row_key in self._rows:
            self._set_row_visible(row_key, row_key in visible_rows)

    def _emit_updated(self, *_args: Any) -> None:
        self._refresh_row_visibility()
        self.summary.setText(self._summary_text(self.block()))
        if not self._loading:
            self.updated.emit()

    def _browse_key(self, *_args: Any) -> None:
        dialog = KeyboardPickerDialog(current_value=self.key_edit.text(), parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            chosen = dialog.selected_key()
            if chosen:
                self.key_edit.setText(chosen)

    def _summary_text(self, block: dict[str, Any]) -> str:
        block = normalize_step_block(block)
        block_type = block["type"]
        if block_type == BLOCK_MOVE_MOUSE:
            if block["target"] == MOVE_TARGET_SAVED:
                return "Move mouse to the saved position."
            return f"Move mouse to ({block['x']}, {block['y']})."
        if block_type == BLOCK_CLICK_MOUSE:
            return f"Click mouse button {block['button']} x{block['clicks']}."
        if block_type == BLOCK_SAVE_MOUSE_POS:
            return "Save the current mouse position."
        if block_type == BLOCK_RESTORE_MOUSE_POS:
            return "Move mouse back to the saved position."
        if block_type == BLOCK_TYPE_TEXT:
            return f"Type text: {block['text']!r}"
        if block_type == BLOCK_PRESS_KEY:
            return f"Press key once: {block['key'] or '<key>'}"
        if block_type == BLOCK_HOLD_KEY:
            return f"Hold key: {block['key'] or '<key>'}"
        if block_type == BLOCK_RELEASE_KEY:
            return f"Release key: {block['key'] or '<key>'}"
        if block_type == BLOCK_REPEAT:
            return f"Repeat the nested block region {block['times']} times until End."
        if block_type == BLOCK_FOREVER:
            return "Repeat the nested block region forever until the key is pressed again."
        if block_type == BLOCK_IF_PRESSED:
            return f"If {block['key'] or '<key>'} is pressed, run until End."
        if block_type == BLOCK_IF_MOUSE_PRESSED:
            return f"If mouse button {block['button']} is pressed, run until End."
        if block_type == BLOCK_IF_ELSE_PRESSED:
            return f"If {block['key'] or '<key>'} is pressed, run the next block, otherwise the block after it."
        if block_type == BLOCK_WHILE_PRESSED:
            return f"While {block['key'] or '<key>'} is pressed, run until End."
        if block_type == BLOCK_WHILE_MOUSE_PRESSED:
            return f"While mouse button {block['button']} is pressed, run until End."
        if block_type == BLOCK_WAIT:
            return f"Legacy wait block: {block['seconds']:.2f}s."
        if block_type == BLOCK_END:
            return "End of scoped block."
        return block_type

    def set_block(self, block: dict[str, Any]) -> None:
        normalized = normalize_step_block(block)
        self._block = normalized
        self._loading = True
        blockers = [
            QSignalBlocker(self.type_combo),
            QSignalBlocker(self.target_combo),
            QSignalBlocker(self.x_spin),
            QSignalBlocker(self.y_spin),
            QSignalBlocker(self.button_combo),
            QSignalBlocker(self.clicks_spin),
            QSignalBlocker(self.text_edit),
            QSignalBlocker(self.key_edit),
            QSignalBlocker(self.seconds_spin),
            QSignalBlocker(self.times_spin),
            QSignalBlocker(self.max_loops_spin),
            QSignalBlocker(self.interval_spin),
        ]
        self._set_combo_by_type(normalized["type"])
        self.target_combo.setCurrentIndex(self.target_combo.findData(normalized.get("target", MOVE_TARGET_COORDS)))
        self.x_spin.setValue(int(normalized.get("x", 0)))
        self.y_spin.setValue(int(normalized.get("y", 0)))
        self.button_combo.setCurrentText(str(normalized.get("button") or "left"))
        self.clicks_spin.setValue(int(normalized.get("clicks", 1)))
        self.text_edit.setPlainText(str(normalized.get("text") or ""))
        self.key_edit.setText(str(normalized.get("key") or ""))
        self.seconds_spin.setValue(float(normalized.get("seconds", 0.1)))
        self.times_spin.setValue(int(normalized.get("times", 2)))
        self.max_loops_spin.setValue(int(normalized.get("max_loops", 50)))
        self.interval_spin.setValue(float(normalized.get("interval", 0.05)))
        del blockers
        self._loading = False
        self._refresh_row_visibility()
        self.summary.setText(self._summary_text(normalized))

    def _set_combo_by_type(self, block_type: str) -> None:
        for index in range(self.type_combo.count()):
            if self.type_combo.itemData(index) == block_type:
                self.type_combo.setCurrentIndex(index)
                return
        self.type_combo.setCurrentIndex(0)

    def block(self) -> dict[str, Any]:
        block_type = str(self.type_combo.currentData() or BLOCK_END)
        block = default_step_block(block_type)
        block["type"] = block_type
        if block_type == BLOCK_MOVE_MOUSE:
            block["target"] = str(self.target_combo.currentData() or MOVE_TARGET_COORDS)
            block["x"] = int(self.x_spin.value())
            block["y"] = int(self.y_spin.value())
        elif block_type == BLOCK_CLICK_MOUSE:
            block["button"] = str(self.button_combo.currentText() or "left")
            block["clicks"] = int(self.clicks_spin.value())
        elif block_type == BLOCK_TYPE_TEXT:
            block["text"] = self.text_edit.toPlainText()
        elif block_type in {BLOCK_PRESS_KEY, BLOCK_HOLD_KEY, BLOCK_RELEASE_KEY, BLOCK_IF_PRESSED, BLOCK_IF_ELSE_PRESSED, BLOCK_WHILE_PRESSED}:
            block["key"] = self.key_edit.text().strip()
            if block_type == BLOCK_WHILE_PRESSED:
                block["interval"] = float(self.interval_spin.value())
                block["max_loops"] = int(self.max_loops_spin.value())
        elif block_type in {BLOCK_IF_MOUSE_PRESSED, BLOCK_WHILE_MOUSE_PRESSED}:
            block["button"] = str(self.button_combo.currentText() or "left")
            if block_type == BLOCK_WHILE_MOUSE_PRESSED:
                block["interval"] = float(self.interval_spin.value())
                block["max_loops"] = int(self.max_loops_spin.value())
        elif block_type == BLOCK_REPEAT:
            block["times"] = int(self.times_spin.value())
        elif block_type == BLOCK_FOREVER:
            block["interval"] = float(self.interval_spin.value())
        elif block_type == BLOCK_WAIT:
            block["seconds"] = float(self.seconds_spin.value())
        elif block_type == BLOCK_END:
            block = {"type": BLOCK_END}
        return normalize_step_block(block)
