from __future__ import annotations

import asyncio

import macropad.core.step_blocks as step_blocks


class _FakeKeyboard:
    def __init__(self, events: list[tuple[str, str]]) -> None:
        self._events = events

    def press_and_release(self, key: str) -> None:
        self._events.append(("press_and_release", key))

    def press(self, key: str) -> None:
        self._events.append(("press", key))

    def release(self, key: str) -> None:
        self._events.append(("release", key))

    def write(self, text: str) -> None:
        self._events.append(("write", text))


def test_step_script_round_trip_supports_new_and_legacy_blocks() -> None:
    blocks = [
        {"type": step_blocks.BLOCK_PRESS_KEY, "key": "a"},
        {"type": step_blocks.BLOCK_IF_MOUSE_PRESSED, "button": "left"},
        {"type": step_blocks.BLOCK_CLICK_MOUSE, "button": "left", "clicks": 2},
        {"type": step_blocks.BLOCK_END},
        {"type": step_blocks.BLOCK_IF_ELSE_PRESSED, "key": "ctrl"},
        {"type": step_blocks.BLOCK_WAIT, "seconds": 0.1},
    ]

    script_text = step_blocks.serialize_step_script(blocks)
    parsed = step_blocks.parse_step_script(script_text)

    assert [block["type"] for block in parsed] == [
        step_blocks.BLOCK_PRESS_KEY,
        step_blocks.BLOCK_IF_MOUSE_PRESSED,
        step_blocks.BLOCK_CLICK_MOUSE,
        step_blocks.BLOCK_END,
        step_blocks.BLOCK_IF_ELSE_PRESSED,
        step_blocks.BLOCK_WAIT,
    ]


def test_execute_step_blocks_repeats_scoped_region(monkeypatch) -> None:
    events: list[tuple[str, str]] = []
    keyboard = _FakeKeyboard(events)

    monkeypatch.setattr(step_blocks, "_keyboard_module", lambda: keyboard)

    blocks = [
        {"type": step_blocks.BLOCK_REPEAT, "times": 2},
        {"type": step_blocks.BLOCK_PRESS_KEY, "key": "a"},
        {"type": step_blocks.BLOCK_HOLD_KEY, "key": "shift"},
        {"type": step_blocks.BLOCK_RELEASE_KEY, "key": "shift"},
        {"type": step_blocks.BLOCK_END},
    ]

    asyncio.run(step_blocks.execute_step_blocks(blocks))

    assert events == [
        ("press_and_release", "a"),
        ("press", "shift"),
        ("release", "shift"),
        ("press_and_release", "a"),
        ("press", "shift"),
        ("release", "shift"),
    ]


def test_execute_step_blocks_mouse_conditions_respect_button_state(monkeypatch) -> None:
    events: list[tuple[str, str]] = []
    keyboard = _FakeKeyboard(events)
    button_states = iter([True, True, True, False])

    monkeypatch.setattr(step_blocks, "_keyboard_module", lambda: keyboard)
    monkeypatch.setattr(step_blocks, "_is_mouse_button_pressed", lambda _button: next(button_states))

    blocks = [
        {"type": step_blocks.BLOCK_IF_MOUSE_PRESSED, "button": "left"},
        {"type": step_blocks.BLOCK_PRESS_KEY, "key": "b"},
        {"type": step_blocks.BLOCK_END},
        {"type": step_blocks.BLOCK_WHILE_MOUSE_PRESSED, "button": "left", "interval": 0.0},
        {"type": step_blocks.BLOCK_PRESS_KEY, "key": "c"},
        {"type": step_blocks.BLOCK_END},
    ]

    asyncio.run(step_blocks.execute_step_blocks(blocks))

    assert events == [
        ("press_and_release", "b"),
        ("press_and_release", "c"),
        ("press_and_release", "c"),
    ]


def test_execute_step_blocks_saves_and_restores_mouse_position(monkeypatch) -> None:
    moves: list[tuple[int, int]] = []

    monkeypatch.setattr(step_blocks, "_get_mouse_pos_now", lambda: (40, 50))
    monkeypatch.setattr(step_blocks, "_move_mouse_now", lambda x, y: moves.append((x, y)))

    blocks = [
        {"type": step_blocks.BLOCK_SAVE_MOUSE_POS},
        {"type": step_blocks.BLOCK_MOVE_MOUSE, "target": step_blocks.MOVE_TARGET_COORDS, "x": 10, "y": 20},
        {"type": step_blocks.BLOCK_RESTORE_MOUSE_POS},
    ]

    asyncio.run(step_blocks.execute_step_blocks(blocks))

    assert moves == [(10, 20), (40, 50)]


def test_execute_step_blocks_forever_runs_until_cancelled(monkeypatch) -> None:
    events: list[tuple[str, str]] = []
    keyboard = _FakeKeyboard(events)

    monkeypatch.setattr(step_blocks, "_keyboard_module", lambda: keyboard)

    blocks = [
        {"type": step_blocks.BLOCK_FOREVER, "interval": 0.0},
        {"type": step_blocks.BLOCK_PRESS_KEY, "key": "a"},
        {"type": step_blocks.BLOCK_END},
    ]

    async def _run() -> None:
        task = asyncio.create_task(step_blocks.execute_step_blocks(blocks))
        await asyncio.sleep(0.03)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    asyncio.run(_run())

    assert events
