from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from PySide6.QtWidgets import QApplication

import macropad.qt.controllers.runtime as runtime
from macropad.config import Settings
from macropad.core.app_state import AppState
from macropad.core.profile import KeyAction, KeyBinding


class _FakeStore:
    def __init__(self, binding: KeyBinding) -> None:
        self.app_state = AppState(last_baud=9600, auto_connect=False)
        self.profile_slot = 1
        self.profile = SimpleNamespace(name="Profile 1")
        self.profile_names = {slot: f"Profile {slot}" for slot in range(1, 11)}
        self.selected_key = (0, 0)
        self.keys = [(0, 0)]
        self.binding = binding
        self.saved_kwargs: dict[str, object] = {}
        self.calls: list[tuple[str, object]] = []

    def save_app_state(self, **kwargs) -> None:
        self.saved_kwargs = dict(kwargs)

    def load_profile_slot(self, slot: int) -> None:
        self.profile_slot = slot

    def set_selected_key(self, key: tuple[int, int]) -> None:
        self.selected_key = key

    def selected_binding(self) -> KeyBinding:
        return self.binding

    def binding_for(self, _key: tuple[int, int]) -> KeyBinding:
        return self.binding

    def display_action_for_binding(self, binding: KeyBinding) -> tuple[str, str]:
        return binding.action.kind, binding.action.value

    def save_script_for_key(self, key: tuple[int, int], mode: str, content: str) -> None:
        self.calls.append(("save", (key, mode, content)))
        self.binding.script_mode = mode
        self.binding.script_code = content

    def clear_script_for_key(self, key: tuple[int, int], mode: str) -> None:
        self.calls.append(("clear", (key, mode)))
        self.binding.script_mode = mode
        self.binding.script_code = ""

    def sync_scripts_from_workspace(self, mode: str, *, persist: bool = False) -> int:
        self.calls.append(("sync", (mode, persist)))
        return 0

    def python_code_for_key(self, _key: tuple[int, int]):
        return compile(self.binding.script_code, "<test>", "exec") if self.binding.script_code.strip() else None

    def python_source_for_key(self, _key: tuple[int, int]) -> str:
        return self.binding.script_code

    def rebuild_python_cache(self) -> None:
        self.calls.append(("rebuild", None))

    def runtime_script_path(self, key: tuple[int, int], mode: str) -> Path:
        return Path(f"{mode}_{key[0]}_{key[1]}.txt")



def _ensure_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_runtime_executes_step_inline_script(monkeypatch) -> None:
    _ensure_app()
    binding = KeyBinding(label="Key 0,0", action=KeyAction(kind="none", value=""), script_mode="step", script_code="STEP")
    fake_store = _FakeStore(binding)
    calls: list[str] = []

    async def fake_execute_step_script(source: str, *, log=None) -> None:
        calls.append(source)

    monkeypatch.setattr(runtime, "ProfileStore", lambda _settings: fake_store)
    monkeypatch.setattr(runtime, "list_serial_ports", lambda: [])
    monkeypatch.setattr(runtime, "execute_step_script", fake_execute_step_script)

    controller = runtime.QtSessionController(Settings())
    asyncio.run(controller._execute_key_action((0, 0)))

    assert calls == ["STEP"]


def test_runtime_executes_legacy_file_inline_script(monkeypatch) -> None:
    _ensure_app()
    binding = KeyBinding(
        label="Key 0,0",
        action=KeyAction(kind="none", value=""),
        script_mode="file",
        script_code="C:/temp/example.txt",
    )
    fake_store = _FakeStore(binding)
    executed: list[KeyAction] = []

    async def fake_execute_action(action: KeyAction, **_kwargs) -> None:
        executed.append(action)

    monkeypatch.setattr(runtime, "ProfileStore", lambda _settings: fake_store)
    monkeypatch.setattr(runtime, "list_serial_ports", lambda: [])
    monkeypatch.setattr(runtime, "execute_action", fake_execute_action)

    controller = runtime.QtSessionController(Settings())
    asyncio.run(controller._execute_key_action((0, 0)))

    assert [(action.kind, action.value) for action in executed] == [("file", "C:/temp/example.txt")]


def test_runtime_prefers_direct_action_over_step_script_when_present(monkeypatch) -> None:
    _ensure_app()
    binding = KeyBinding(
        label="Key 0,0",
        action=KeyAction(kind="file", value=""),
        script_mode="step",
        script_code="STEP",
    )
    fake_store = _FakeStore(binding)
    step_calls: list[str] = []
    action_calls: list[KeyAction] = []

    async def fake_execute_step_script(source: str, *, log=None) -> None:
        step_calls.append(source)

    async def fake_execute_action(action: KeyAction, **_kwargs) -> None:
        action_calls.append(action)

    monkeypatch.setattr(runtime, "ProfileStore", lambda _settings: fake_store)
    monkeypatch.setattr(runtime, "list_serial_ports", lambda: [])
    monkeypatch.setattr(runtime, "execute_step_script", fake_execute_step_script)
    monkeypatch.setattr(runtime, "execute_action", fake_execute_action)

    controller = runtime.QtSessionController(Settings())
    asyncio.run(controller._execute_key_action((0, 0)))

    assert step_calls == []
    assert [(action.kind, action.value) for action in action_calls] == [("file", "")]


def test_runtime_save_selected_step_script_clears_legacy_python_workspace_first(monkeypatch) -> None:
    _ensure_app()
    binding = KeyBinding(
        label="Key 0,0",
        action=KeyAction(kind="none", value=""),
        script_mode="python",
        script_code="print('legacy')",
    )
    fake_store = _FakeStore(binding)

    monkeypatch.setattr(runtime, "ProfileStore", lambda _settings: fake_store)
    monkeypatch.setattr(runtime, "list_serial_ports", lambda: [])

    controller = runtime.QtSessionController(Settings())
    controller.save_selected_step_script("# STEP_BLOCKS_V1\n{}\n")

    assert fake_store.calls[0] == ("clear", ((0, 0), "python"))
    assert fake_store.calls[1] == ("save", ((0, 0), "step", "# STEP_BLOCKS_V1\n{}\n"))


def test_runtime_step_forever_toggles_on_second_key_press(monkeypatch) -> None:
    _ensure_app()
    binding = KeyBinding(label="Key 0,0", action=KeyAction(kind="none", value=""), script_mode="step", script_code="STEP")
    fake_store = _FakeStore(binding)
    started: list[str] = []
    cancelled: list[str] = []

    async def fake_execute_step_script(source: str, *, log=None) -> None:
        started.append(source)
        try:
            while True:
                await asyncio.sleep(0.01)
        except asyncio.CancelledError:
            cancelled.append(source)
            raise

    monkeypatch.setattr(runtime, "ProfileStore", lambda _settings: fake_store)
    monkeypatch.setattr(runtime, "list_serial_ports", lambda: [])
    monkeypatch.setattr(runtime, "parse_step_script", lambda _source: [{"type": runtime.BLOCK_FOREVER}, {"type": "end"}])
    monkeypatch.setattr(runtime, "execute_step_script", fake_execute_step_script)

    controller = runtime.QtSessionController(Settings())
    press_event = runtime.BoardEvent(
        kind=runtime.EVENT_KEY_STATE,
        timestamp=datetime.now().astimezone(),
        raw_line="KEY=0,0,1",
        value=True,
        row=0,
        col=0,
    )

    async def _run() -> None:
        controller._handle_event(press_event)
        await asyncio.sleep(0.04)
        assert controller._is_step_forever_running((0, 0))
        controller._handle_event(press_event)
        await asyncio.sleep(0.04)
        assert not controller._is_step_forever_running((0, 0))
        controller._cancel_step_loop_tasks()
        await asyncio.sleep(0.01)

    asyncio.run(_run())

    assert len(started) == 1
    assert cancelled


def test_runtime_step_loops_cancel_immediately_on_encoder_event(monkeypatch) -> None:
    _ensure_app()
    binding = KeyBinding(label="Key 0,0", action=KeyAction(kind="none", value=""), script_mode="step", script_code="STEP")
    fake_store = _FakeStore(binding)
    cancelled: list[str] = []

    async def fake_execute_step_script(_source: str, *, log=None) -> None:
        try:
            while True:
                await asyncio.sleep(0.01)
        except asyncio.CancelledError:
            cancelled.append("cancelled")
            raise

    monkeypatch.setattr(runtime, "ProfileStore", lambda _settings: fake_store)
    monkeypatch.setattr(runtime, "list_serial_ports", lambda: [])
    monkeypatch.setattr(runtime, "parse_step_script", lambda _source: [{"type": runtime.BLOCK_FOREVER}, {"type": "end"}])
    monkeypatch.setattr(runtime, "execute_step_script", fake_execute_step_script)

    controller = runtime.QtSessionController(Settings())
    controller._suspend_actions = True
    key_press = runtime.BoardEvent(
        kind=runtime.EVENT_KEY_STATE,
        timestamp=datetime.now().astimezone(),
        raw_line="KEY=0,0,1",
        value=True,
        row=0,
        col=0,
    )
    enc_event = runtime.BoardEvent(
        kind=runtime.EVENT_ENC_DELTA,
        timestamp=datetime.now().astimezone(),
        raw_line="ENC=+1",
        delta=1,
    )

    async def _run() -> None:
        controller._suspend_actions = False
        controller._handle_event(key_press)
        await asyncio.sleep(0.04)
        assert controller._is_step_forever_running((0, 0))
        controller._suspend_actions = True
        controller._handle_event(enc_event)
        await asyncio.sleep(0.04)
        assert not controller._is_step_forever_running((0, 0))

    asyncio.run(_run())

    assert cancelled
