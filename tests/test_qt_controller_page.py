from __future__ import annotations

from types import SimpleNamespace

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QDialog

from macropad.config import Settings
from macropad.qt.pages import controller_page
from macropad.qt.pages.controller_page import ControllerPage
from macropad.core.actions import ACTION_KEYBOARD, ACTION_WINDOW_CONTROL
from macropad.core.profile import KeyAction, KeyBinding


class _FakeController(QObject):
    portsChanged = Signal(object)
    connectionStateChanged = Signal(str)
    logMessage = Signal(str)
    profileChanged = Signal(int, object)
    profileSlotChanged = Signal(int)
    profileNameChanged = Signal(str)
    selectedKeyChanged = Signal(int, int)
    selectedBindingChanged = Signal(object)
    keyStateChanged = Signal(int, int, bool)
    encoderChanged = Signal(str)
    lastPacketChanged = Signal(str)
    autoConnectChanged = Signal(bool)

    def __init__(self) -> None:
        super().__init__()
        self.store = SimpleNamespace(app_state=SimpleNamespace(auto_connect=False))
        self.selected_baud = 9600
        self.profile_slot = 1
        self.selected_port = ""
        self.selected_hint = ""
        self.selected_key = (0, 0)
        self.current_profile = SimpleNamespace(
            name="Profile 1",
            bindings={(0, 0): KeyBinding(label="Key 0,0", action=KeyAction())},
            enc_up_action=KeyAction(),
            enc_down_action=KeyAction(),
            enc_sw_down_action=KeyAction(),
            enc_sw_up_action=KeyAction(),
        )
        self._binding = self.current_profile.bindings[(0, 0)]

    def port_choices(self) -> list[object]:
        return []

    def current_binding(self) -> KeyBinding:
        return self._binding

    def refresh_ports(self) -> None:
        return None

    async def connect(self) -> None:
        return None

    async def disconnect(self) -> None:
        return None

    async def reconnect(self) -> None:
        return None

    def set_auto_connect(self, _enabled: bool) -> None:
        return None

    def set_learn_mode(self, _enabled: bool) -> None:
        return None

    def set_selected_hint(self, value: str) -> None:
        self.selected_hint = value

    def set_selected_baud(self, value: int) -> None:
        self.selected_baud = int(value)

    def set_profile_slot(self, value: int) -> None:
        self.profile_slot = int(value)

    def select_key(self, row: int, col: int) -> None:
        self.selected_key = (int(row), int(col))

    def update_selected_binding(self, *, kind: str, value: str, label: str | None = None) -> None:
        self._binding.label = str(label or self._binding.label)
        self._binding.action.kind = kind
        self._binding.action.value = value


def test_controller_page_keyboard_browse_sets_selected_value(monkeypatch, qtbot) -> None:
    class _FakeKeyboardPickerDialog:
        def __init__(self, *, current_value: str = "", parent=None) -> None:
            self._value = current_value

        def exec(self) -> QDialog.DialogCode:
            return QDialog.DialogCode.Accepted

        def selected_key(self) -> str:
            return "Caps Lock"

    monkeypatch.setattr(controller_page, "KeyboardPickerDialog", _FakeKeyboardPickerDialog)

    page = ControllerPage(_FakeController())
    qtbot.addWidget(page)
    page.show()

    page.selected_panel.action_row.set_action(ACTION_KEYBOARD, "")
    page._browse_selected_binding()

    assert page.selected_panel.action()[1] == "Caps Lock"


def test_controller_page_window_control_browse_sets_selected_value(monkeypatch, qtbot) -> None:
    class _FakeWindowControlDialog:
        def __init__(self, *, current_value: str = "", parent=None) -> None:
            self._value = current_value

        def exec(self) -> QDialog.DialogCode:
            return QDialog.DialogCode.Accepted

        def value(self) -> str:
            return "mode=monitor;monitor=2"

    monkeypatch.setattr(controller_page, "WindowControlDialog", _FakeWindowControlDialog)

    page = ControllerPage(_FakeController())
    qtbot.addWidget(page)
    page.show()

    page.selected_panel.action_row.set_action(ACTION_WINDOW_CONTROL, "")
    page._browse_selected_binding()

    assert page.selected_panel.action()[1] == "mode=monitor;monitor=2"


def test_controller_page_action_catalog_is_cleaned_up(qtbot) -> None:
    page = ControllerPage(_FakeController())
    qtbot.addWidget(page)
    page.show()

    expected = [
        "none",
        "keyboard",
        "file",
        "volume_mixer",
        "change_profile",
        "window_control",
    ]
    selected_items = [
        page.selected_panel.action_row.kind_combo.itemText(index)
        for index in range(page.selected_panel.action_row.kind_combo.count())
    ]
    assert selected_items == expected

    for row in (
        page.encoder_panel.up_row,
        page.encoder_panel.down_row,
        page.encoder_panel.sw_down_row,
        page.encoder_panel.sw_up_row,
    ):
        items = [row.kind_combo.itemText(index) for index in range(row.kind_combo.count())]
        assert items == expected
