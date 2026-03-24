from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ...core.profile import KeyBinding
from ..controllers.runtime import QtSessionController
from ..smooth_scroll import install_smooth_wheel_scroll
from ..utils import slot_label
from ..widgets.step_editor import StepEditorWidget

LEGACY_SCRIPT_MODES = {"python", "ahk", "file"}


class ScriptsPage(QWidget):
    def __init__(self, controller: QtSessionController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.controller = controller
        self._binding: KeyBinding | None = None
        self._updating = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        top = QFrame(self)
        top.setProperty("panel", True)
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(14, 14, 14, 14)
        top_layout.setSpacing(10)

        top_layout.addWidget(QLabel("Profile"))
        self.profile_combo = QComboBox(top)
        top_layout.addWidget(self.profile_combo, 1)
        top_layout.addWidget(QLabel("Key"))
        self.key_combo = QComboBox(top)
        top_layout.addWidget(self.key_combo, 1)
        self.save_button = QPushButton("Save STEP", top)
        self.reload_button = QPushButton("Reload", top)
        self.replace_button = QPushButton("Replace with STEP", top)
        top_layout.addWidget(self.save_button)
        top_layout.addWidget(self.reload_button)
        top_layout.addWidget(self.replace_button)

        root.addWidget(top, 0)

        body = QSplitter(Qt.Horizontal, self)
        body.setObjectName("ScriptsBodySplitter")
        body.setHandleWidth(10)
        body.setChildrenCollapsible(False)
        body.setOpaqueResize(False)
        root.addWidget(body, 1)

        left = QFrame(body)
        left.setProperty("panel", True)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(14, 14, 14, 14)
        left_layout.setSpacing(10)
        left_layout.addWidget(QLabel("Keys"))
        self.key_list = QListWidget(left)
        self.key_list.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        install_smooth_wheel_scroll(self.key_list, duration_ms=180, wheel_step=84)
        left_layout.addWidget(self.key_list, 1)

        right = QFrame(body)
        right.setProperty("panel", True)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(14, 14, 14, 14)
        right_layout.setSpacing(10)

        self.title_label = QLabel("STEP Script")
        self.title_label.setObjectName("Section")
        right_layout.addWidget(self.title_label)

        self.status_label = QLabel("Build key behavior with visual STEP blocks.")
        self.status_label.setWordWrap(True)
        right_layout.addWidget(self.status_label)

        self.compat_frame = QFrame(right)
        self.compat_frame.setProperty("panel", True)
        compat_layout = QVBoxLayout(self.compat_frame)
        compat_layout.setContentsMargins(12, 12, 12, 12)
        compat_layout.setSpacing(6)
        compat_title = QLabel("Legacy inline script detected")
        compat_title.setObjectName("Section")
        self.compat_label = QLabel("")
        self.compat_label.setWordWrap(True)
        compat_layout.addWidget(compat_title)
        compat_layout.addWidget(self.compat_label)
        right_layout.addWidget(self.compat_frame, 0)

        self.step_editor = StepEditorWidget(right)
        right_layout.addWidget(self.step_editor, 1)

        body.addWidget(left)
        body.addWidget(right)
        body.setCollapsible(0, False)
        body.setCollapsible(1, False)
        body.setStretchFactor(0, 1)
        body.setStretchFactor(1, 3)
        body.setSizes([250, 950])

        self.profile_combo.currentIndexChanged.connect(self._on_profile_changed)
        self.key_combo.currentIndexChanged.connect(self._on_key_combo_changed)
        self.key_list.currentRowChanged.connect(self._on_key_list_changed)
        self.save_button.clicked.connect(self._save_step_script)
        self.reload_button.clicked.connect(self._reload_current_binding)
        self.replace_button.clicked.connect(self._replace_with_step)
        self.step_editor.changed.connect(self._on_step_editor_changed)

        controller.profileChanged.connect(self._on_controller_profile_changed)
        controller.profileSlotChanged.connect(self._on_controller_profile_slot_changed)
        controller.selectedKeyChanged.connect(self._on_controller_selected_key_changed)
        controller.selectedBindingChanged.connect(self._on_controller_selected_binding_changed)

        self._refresh_profile_combo()
        self._refresh_key_controls()
        self._on_controller_profile_changed(controller.profile_slot, controller.current_profile)
        row, col = controller.selected_key
        self._on_controller_selected_key_changed(row, col)
        self._on_controller_selected_binding_changed(controller.current_binding())

    def _refresh_profile_combo(self) -> None:
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        for slot in range(1, 11):
            name = self.controller.store.profile_names.get(slot, f"Profile {slot}")
            self.profile_combo.addItem(slot_label(slot, name), userData=slot)
        index = max(0, self.profile_combo.findData(self.controller.profile_slot))
        self.profile_combo.setCurrentIndex(index)
        self.profile_combo.blockSignals(False)

    def _refresh_key_controls(self) -> None:
        self._updating = True
        try:
            selected_key = self.controller.selected_key
            self.key_combo.blockSignals(True)
            self.key_combo.clear()
            self.key_list.blockSignals(True)
            self.key_list.clear()
            for key in self.controller.store.keys:
                text = f"{key[0]},{key[1]}"
                self.key_combo.addItem(text, userData=key)
                item = QListWidgetItem(text)
                self.key_list.addItem(item)
            index = max(0, self.key_combo.findData(selected_key))
            self.key_combo.setCurrentIndex(index)
            row = self._key_row(selected_key)
            if row >= 0:
                self.key_list.setCurrentRow(row)
        finally:
            self.key_combo.blockSignals(False)
            self.key_list.blockSignals(False)
            self._updating = False

    def _key_row(self, key: tuple[int, int]) -> int:
        text = f"{key[0]},{key[1]}"
        for row in range(self.key_list.count()):
            item = self.key_list.item(row)
            if item is not None and item.text() == text:
                return row
        return -1

    def _on_profile_changed(self, index: int) -> None:
        if self._updating:
            return
        slot = int(self.profile_combo.itemData(index) or self.controller.profile_slot)
        self.controller.set_profile_slot(slot)

    def _on_key_combo_changed(self, index: int) -> None:
        if self._updating:
            return
        key = self.key_combo.itemData(index)
        if isinstance(key, tuple) and len(key) == 2:
            self.controller.select_key(int(key[0]), int(key[1]))

    def _on_key_list_changed(self, row: int) -> None:
        if self._updating or row < 0:
            return
        item = self.key_list.item(row)
        if item is None:
            return
        row_text, col_text = item.text().split(",", 1)
        self.controller.select_key(int(row_text), int(col_text))

    def _save_step_script(self) -> None:
        if self._legacy_mode(self._binding):
            return
        self.controller.save_selected_step_script(self.step_editor.script_text())

    def _reload_current_binding(self) -> None:
        self._on_controller_selected_binding_changed(self.controller.current_binding())

    def _replace_with_step(self) -> None:
        binding = self._binding
        legacy_mode = self._legacy_mode(binding)
        if not legacy_mode:
            return
        result = QMessageBox.warning(
            self,
            "Replace Legacy Script",
            (
                f"This key currently uses an inline {legacy_mode.upper()} script.\n\n"
                "Replacing it with STEP will clear that inline script for this key."
            ),
            QMessageBox.Yes | QMessageBox.Cancel,
            QMessageBox.Cancel,
        )
        if result != QMessageBox.Yes:
            return
        self.controller.replace_selected_script_with_step()

    def _on_step_editor_changed(self, _blocks: object) -> None:
        if self._legacy_mode(self._binding):
            self.status_label.setText("Legacy inline script is read-only here. Replace it with STEP to edit blocks.")
            return
        count = len(self.step_editor.blocks())
        self.status_label.setText(f"STEP editor ready. {count} block(s) in the current chain.")

    def _on_controller_profile_changed(self, slot: int, profile: object) -> None:
        self._refresh_profile_combo()
        self._refresh_key_controls()
        profile_name = getattr(profile, "name", f"Profile {slot}")
        self.title_label.setText(f"STEP Script - Profile {slot}: {profile_name}")

    def _on_controller_profile_slot_changed(self, slot: int) -> None:
        index = self.profile_combo.findData(slot)
        if index >= 0:
            self.profile_combo.blockSignals(True)
            self.profile_combo.setCurrentIndex(index)
            self.profile_combo.blockSignals(False)

    def _on_controller_selected_key_changed(self, row: int, col: int) -> None:
        key = (int(row), int(col))
        self._updating = True
        try:
            index = self.key_combo.findData(key)
            if index >= 0:
                self.key_combo.setCurrentIndex(index)
            list_row = self._key_row(key)
            if list_row >= 0:
                self.key_list.setCurrentRow(list_row)
        finally:
            self._updating = False

    def _on_controller_selected_binding_changed(self, binding: object) -> None:
        if not isinstance(binding, KeyBinding):
            return
        self._binding = binding
        current_key = self.controller.selected_key
        current_mode = (binding.script_mode or "").strip().lower()
        current_text = binding.script_code or ""
        legacy_mode = self._legacy_mode(binding)

        self.compat_frame.setVisible(bool(legacy_mode))
        self.replace_button.setVisible(bool(legacy_mode))
        self.replace_button.setEnabled(bool(legacy_mode))
        self.step_editor.set_read_only(bool(legacy_mode))
        self.save_button.setEnabled(not legacy_mode)

        if legacy_mode:
            self.compat_label.setText(
                f"Key {current_key[0]},{current_key[1]} uses an inline {legacy_mode.upper()} script. "
                "That script still runs at runtime, but it cannot be edited on this page."
            )
            self.step_editor.set_blocks([])
            self.status_label.setText("Legacy inline script is read-only here. Replace it with STEP to edit blocks.")
            return

        if current_mode == "step":
            self.step_editor.set_script_text(current_text)
        else:
            self.step_editor.set_blocks([])
        count = len(self.step_editor.blocks())
        self.status_label.setText(
            f"Editing STEP blocks for key {current_key[0]},{current_key[1]}. {count} block(s) in the chain."
        )

    def _legacy_mode(self, binding: KeyBinding | None) -> str:
        if binding is None:
            return ""
        mode = (binding.script_mode or "").strip().lower()
        if mode in LEGACY_SCRIPT_MODES and bool((binding.script_code or "").strip()):
            return mode
        return ""
