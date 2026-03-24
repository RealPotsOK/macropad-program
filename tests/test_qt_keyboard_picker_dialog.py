from __future__ import annotations

from PySide6.QtWidgets import QDialog

from macropad.qt.dialogs.keyboard_picker_dialog import KeyboardPickerDialog


def test_keyboard_picker_selects_current_value_and_accepts(qtbot) -> None:
    dialog = KeyboardPickerDialog(current_value="Page Up")
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitExposed(dialog)

    assert dialog.selected_key() == "Page Up"

    dialog._accept_selection()

    assert dialog.result() == QDialog.DialogCode.Accepted
    assert dialog.selected_key() == "Page Up"


def test_keyboard_picker_filter_keeps_first_visible_selection(qtbot) -> None:
    dialog = KeyboardPickerDialog()
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitExposed(dialog)

    dialog.search.setText("volume")

    assert dialog.selected_key() == "Volume Up"
