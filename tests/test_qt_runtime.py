from __future__ import annotations

from PySide6.QtWidgets import QApplication

import macropad.qt.controllers.runtime as runtime
from macropad.config import Settings
from macropad.core.app_state import AppState


class _FakeStore:
    def __init__(self, last_baud: int, *, last_port: str = "", last_hint: str = "", auto_connect: bool = True) -> None:
        self.app_state = AppState(last_port=last_port, last_hint=last_hint, last_baud=last_baud, auto_connect=auto_connect)
        self.profile_slot = 1
        self.profile = object()
        self.selected_key = (0, 0)
        self.saved_kwargs: dict[str, object] = {}

    def save_app_state(self, **kwargs) -> None:
        self.saved_kwargs = dict(kwargs)


def _ensure_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_runtime_uses_saved_baud_when_settings_are_default(monkeypatch) -> None:
    _ensure_app()
    fake_store = _FakeStore(last_baud=9600)

    monkeypatch.setattr(runtime, "ProfileStore", lambda _settings: fake_store)
    monkeypatch.setattr(runtime, "list_serial_ports", lambda: [])

    controller = runtime.QtSessionController(Settings())

    assert controller.selected_baud == 9600


def test_runtime_explicit_settings_baud_overrides_saved_baud(monkeypatch) -> None:
    _ensure_app()
    fake_store = _FakeStore(last_baud=9600)

    monkeypatch.setattr(runtime, "ProfileStore", lambda _settings: fake_store)
    monkeypatch.setattr(runtime, "list_serial_ports", lambda: [])

    controller = runtime.QtSessionController(Settings(baud=57600))

    assert controller.selected_baud == 57600


def test_runtime_set_selected_baud_persists_to_app_state(monkeypatch) -> None:
    _ensure_app()
    fake_store = _FakeStore(last_baud=115200)

    monkeypatch.setattr(runtime, "ProfileStore", lambda _settings: fake_store)
    monkeypatch.setattr(runtime, "list_serial_ports", lambda: [])

    controller = runtime.QtSessionController(Settings())
    controller.set_selected_baud(9600)

    assert controller.selected_baud == 9600
    assert fake_store.saved_kwargs["last_baud"] == 9600


def test_runtime_uses_saved_hint_when_settings_hint_is_empty(monkeypatch) -> None:
    _ensure_app()
    fake_store = _FakeStore(last_baud=9600, last_hint="Microchip")

    monkeypatch.setattr(runtime, "ProfileStore", lambda _settings: fake_store)
    monkeypatch.setattr(runtime, "list_serial_ports", lambda: [])

    controller = runtime.QtSessionController(Settings())

    assert controller.selected_hint == "Microchip"


def test_runtime_hidden_start_auto_connects_to_saved_port_even_if_flag_is_false(monkeypatch) -> None:
    _ensure_app()
    fake_store = _FakeStore(last_baud=9600, last_port="COM13", auto_connect=False)

    monkeypatch.setattr(runtime, "ProfileStore", lambda _settings: fake_store)
    monkeypatch.setattr(runtime, "list_serial_ports", lambda: [])

    controller = runtime.QtSessionController(Settings())
    calls: list[str] = []

    async def _fake_connect() -> None:
        calls.append("connect")

    controller.connect = _fake_connect  # type: ignore[method-assign]

    import asyncio

    asyncio.run(controller.auto_connect_if_enabled(hidden_start=True))

    assert calls == ["connect"]


def test_runtime_build_screen_command_uses_single_line_when_separator_is_empty(monkeypatch) -> None:
    _ensure_app()
    fake_store = _FakeStore(last_baud=9600)
    fake_store.app_state.screen_command_prefix = "display:"
    fake_store.app_state.screen_line_separator = ""

    monkeypatch.setattr(runtime, "ProfileStore", lambda _settings: fake_store)
    monkeypatch.setattr(runtime, "list_serial_ports", lambda: [])

    controller = runtime.QtSessionController(Settings())

    assert controller.build_screen_command("Abcde\n123") == "display:Abcde"
