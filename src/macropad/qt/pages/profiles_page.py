from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..controllers.runtime import QtSessionController
from ..utils import slot_label


class ProfilesPage(QWidget):
    def __init__(self, controller: QtSessionController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.controller = controller
        self._loading = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        panel = QFrame(self)
        panel.setProperty("panel", True)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(14, 14, 14, 14)
        panel_layout.setSpacing(10)

        title = QLabel("Profiles")
        title.setObjectName("Section")
        subtitle = QLabel(
            "Manage profile slot, name, description, and OLED display lines."
        )
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)
        panel_layout.addWidget(title)
        panel_layout.addWidget(subtitle)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(8)
        top_row.addWidget(QLabel("Slot"))
        self.slot_combo = QComboBox(panel)
        top_row.addWidget(self.slot_combo, 1)
        self.new_button = QPushButton("New", panel)
        self.save_button = QPushButton("Save", panel)
        self.delete_button = QPushButton("Delete", panel)
        self.push_button = QPushButton("Push Display", panel)
        top_row.addWidget(self.new_button)
        top_row.addWidget(self.save_button)
        top_row.addWidget(self.delete_button)
        top_row.addWidget(self.push_button)
        panel_layout.addLayout(top_row)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(8)
        self.name_edit = QLineEdit(panel)
        self.description_edit = QLineEdit(panel)
        self.oled_line1_edit = QLineEdit(panel)
        self.oled_line2_edit = QLineEdit(panel)
        self.oled_line1_edit.setPlaceholderText("Profile {profile_slot}")
        self.oled_line2_edit.setPlaceholderText("{profile_name}")
        form.addRow("Name", self.name_edit)
        form.addRow("Description", self.description_edit)
        form.addRow("Display Line 1", self.oled_line1_edit)
        form.addRow("Display Line 2", self.oled_line2_edit)
        panel_layout.addLayout(form)

        self.hint = QLabel(
            "Tokens: {profile_slot}, {profile_name}. Description is available to your OLED template logic."
        )
        self.hint.setObjectName("PageSubtitle")
        self.hint.setWordWrap(True)
        panel_layout.addWidget(self.hint)

        self.status = QLabel("")
        self.status.setObjectName("Muted")
        self.status.setWordWrap(True)
        panel_layout.addWidget(self.status)

        root.addWidget(panel, 1)

        self.slot_combo.currentIndexChanged.connect(self._on_slot_changed)
        self.new_button.clicked.connect(self._on_new_clicked)
        self.save_button.clicked.connect(self._on_save_clicked)
        self.delete_button.clicked.connect(self._on_delete_clicked)
        self.push_button.clicked.connect(self._on_push_clicked)

        controller.profileChanged.connect(self._on_controller_profile_changed)
        controller.profileSlotChanged.connect(self._on_controller_profile_slot_changed)

        self._refresh_slot_combo()
        self._load_profile(controller.profile_slot, controller.current_profile)

    def _profile_names(self) -> dict[int, str]:
        return dict(getattr(self.controller.store, "profile_names", {}) or {})

    def _refresh_slot_combo(self) -> None:
        names = self._profile_names()
        self.slot_combo.blockSignals(True)
        self.slot_combo.clear()
        for slot in range(1, 11):
            name = names.get(slot, f"Profile {slot}")
            self.slot_combo.addItem(slot_label(slot, name), userData=slot)
        current_index = self.slot_combo.findData(int(self.controller.profile_slot))
        self.slot_combo.setCurrentIndex(max(0, current_index))
        self.slot_combo.blockSignals(False)

    def _load_profile(self, slot: int, profile: object) -> None:
        self._loading = True
        self.name_edit.setText(str(getattr(profile, "name", "") or f"Profile {slot}"))
        self.description_edit.setText(str(getattr(profile, "description", "") or ""))
        self.oled_line1_edit.setText(str(getattr(profile, "oled_line1", "") or "Profile {profile_slot}"))
        self.oled_line2_edit.setText(str(getattr(profile, "oled_line2", "") or "{profile_name}"))
        index = self.slot_combo.findData(int(slot))
        if index >= 0:
            self.slot_combo.blockSignals(True)
            self.slot_combo.setCurrentIndex(index)
            self.slot_combo.blockSignals(False)
        self._loading = False

    def _on_slot_changed(self, index: int) -> None:
        if self._loading:
            return
        slot = int(self.slot_combo.itemData(index) or self.controller.profile_slot)
        self.controller.set_profile_slot(slot)

    def _on_controller_profile_changed(self, slot: int, profile: object) -> None:
        self._refresh_slot_combo()
        self._load_profile(slot, profile)

    def _on_controller_profile_slot_changed(self, slot: int) -> None:
        index = self.slot_combo.findData(int(slot))
        if index >= 0:
            self.slot_combo.blockSignals(True)
            self.slot_combo.setCurrentIndex(index)
            self.slot_combo.blockSignals(False)

    def _on_save_clicked(self) -> None:
        self.controller.save_current_profile_settings(
            name=self.name_edit.text(),
            description=self.description_edit.text(),
            oled_line1=self.oled_line1_edit.text(),
            oled_line2=self.oled_line2_edit.text(),
        )
        self.status.setText("Profile saved.")

    def _on_new_clicked(self) -> None:
        default_name = f"Profile {self.controller.profile_slot}"
        name, ok = QInputDialog.getText(self, "New Profile", "Profile name:", text=default_name)
        if not ok:
            return
        clean_name = str(name or "").strip() or default_name
        self.controller.reset_current_profile(name=clean_name)
        self.status.setText(f"Created new profile in slot {self.controller.profile_slot}.")

    def _on_delete_clicked(self) -> None:
        slot = int(self.controller.profile_slot)
        answer = QMessageBox.question(
            self,
            "Delete Profile",
            f"Reset profile slot {slot} to defaults?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        self.controller.reset_current_profile(name=f"Profile {slot}")
        self.status.setText(f"Profile slot {slot} reset.")

    def _on_push_clicked(self) -> None:
        self.controller.push_profile_text_now()
        self.status.setText("Pushed profile display text to the board.")
