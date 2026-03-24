from __future__ import annotations

from types import SimpleNamespace

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QMessageBox, QWidget

import macropad.qt.main_window as main_window
from macropad.config import Settings
from macropad.qt.pages.scripts_page import ScriptsPage
from macropad.core.profile import KeyAction, KeyBinding
from macropad.core.step_blocks import BLOCK_PRESS_KEY, serialize_step_script


class _FakeController(QObject):
    portsChanged = Signal(object)
    connectionStateChanged = Signal(str)
    logMessage = Signal(str)
    profileChanged = Signal(int, object)
    profileSlotChanged = Signal(int)
    profileNameChanged = Signal(str)
    selectedKeyChanged = Signal(int, int)
    selectedBindingChanged = Signal(object)
    boardStateChanged = Signal(object)
    encoderChanged = Signal(str)
    lastPacketChanged = Signal(str)
    autoConnectChanged = Signal(bool)

    def __init__(self, _settings: Settings, **_kwargs) -> None:
        super().__init__()
        self.store = SimpleNamespace(
            profile_names={slot: f"Profile {slot}" for slot in range(1, 11)},
            keys=[(0, 0), (0, 1), (0, 2)],
            app_state=SimpleNamespace(auto_connect=False),
        )
        self.profile_slot = 1
        self.current_profile = SimpleNamespace(name="Profile 1")
        self.selected_key = (0, 0)
        self.selected_port = "COM9"
        self.selected_hint = ""
        self.selected_baud = 9600
        self._bindings = {
            (0, 0): KeyBinding(label="Key 0,0", action=KeyAction(), script_mode="step", script_code=""),
            (0, 1): KeyBinding(label="Key 0,1", action=KeyAction(), script_mode="python", script_code="print('legacy')"),
            (0, 2): KeyBinding(label="Key 0,2", action=KeyAction(), script_mode="step", script_code=""),
        }
        self.saved_script: str | None = None
        self.replace_calls = 0

    def refresh_ports(self) -> None:
        self.portsChanged.emit([])

    def current_binding(self) -> KeyBinding:
        return self._bindings[self.selected_key]

    def set_profile_slot(self, slot: int) -> None:
        self.profile_slot = int(slot)
        self.current_profile = SimpleNamespace(name=f"Profile {slot}")
        self.profileSlotChanged.emit(self.profile_slot)
        self.profileChanged.emit(self.profile_slot, self.current_profile)
        self.profileNameChanged.emit(self.current_profile.name)
        self.selectedBindingChanged.emit(self.current_binding())

    def select_key(self, row: int, col: int) -> None:
        self.selected_key = (int(row), int(col))
        self.selectedKeyChanged.emit(*self.selected_key)
        self.selectedBindingChanged.emit(self.current_binding())

    def save_selected_step_script(self, content: str) -> None:
        self.saved_script = content
        binding = self.current_binding()
        binding.script_mode = "step"
        binding.script_code = content
        self.selectedBindingChanged.emit(binding)

    def replace_selected_script_with_step(self) -> None:
        self.replace_calls += 1
        binding = self.current_binding()
        binding.script_mode = "step"
        binding.script_code = ""
        self.selectedBindingChanged.emit(binding)

    async def reconnect(self) -> None:  # pragma: no cover - signal target only
        return None

    async def shutdown(self) -> None:  # pragma: no cover - signal target only
        return None

    async def auto_connect_if_enabled(self) -> None:  # pragma: no cover - startup only
        return None


class _FakeTrayService(QObject):
    openRequested = Signal()
    reconnectRequested = Signal()
    toggleAutostartRequested = Signal()
    exitRequested = Signal()

    def __init__(self) -> None:
        super().__init__()

    def start(self) -> bool:
        return False

    def set_autostart_enabled(self, _enabled: bool) -> None:
        return None

    def stop(self) -> None:
        return None

    def show_message(self, _title: str, _message: str) -> None:
        return None


class _FakeOverlay:
    pass


def test_scripts_page_shows_legacy_banner_and_disables_editor(qtbot) -> None:
    controller = _FakeController(Settings())
    page = ScriptsPage(controller)
    qtbot.addWidget(page)
    page.show()

    controller.select_key(0, 1)

    assert page.compat_frame.isVisible()
    assert page.step_editor.isEnabled()
    assert not page.step_editor.add_button.isEnabled()
    assert not page.save_button.isEnabled()
    assert page.replace_button.isVisible()
    assert "PYTHON" in page.compat_label.text()


def test_scripts_page_saves_step_script(qtbot) -> None:
    controller = _FakeController(Settings())
    page = ScriptsPage(controller)
    qtbot.addWidget(page)
    page.show()

    page.step_editor.set_blocks([{"type": BLOCK_PRESS_KEY, "key": "a"}])
    qtbot.mouseClick(page.save_button, Qt.LeftButton)

    assert controller.saved_script is not None
    assert controller.saved_script == serialize_step_script([{"type": BLOCK_PRESS_KEY, "key": "a"}])


def test_scripts_page_replace_with_step_confirms_and_clears_legacy_mode(monkeypatch, qtbot) -> None:
    controller = _FakeController(Settings())
    page = ScriptsPage(controller)
    qtbot.addWidget(page)
    page.show()
    controller.select_key(0, 1)

    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: QMessageBox.Yes)
    qtbot.mouseClick(page.replace_button, Qt.LeftButton)

    assert controller.replace_calls == 1
    assert not page.compat_frame.isVisible()
    assert page.step_editor.add_button.isEnabled()
    assert page.save_button.isEnabled()


def test_main_window_mounts_real_scripts_page(monkeypatch, qtbot) -> None:
    monkeypatch.setattr(main_window, "QtSessionController", _FakeController)
    monkeypatch.setattr(main_window, "ControllerPage", lambda _controller: QWidget())
    monkeypatch.setattr(main_window, "TrayService", _FakeTrayService)
    monkeypatch.setattr(main_window, "VolumeOverlayToast", _FakeOverlay)
    monkeypatch.setattr(main_window, "build_app_icon", lambda: QIcon())

    window = main_window.MacroPadMainWindow(Settings())
    qtbot.addWidget(window)

    assert isinstance(window.scripts_page, ScriptsPage)
    assert window._stack.widget(1) is window.scripts_page
