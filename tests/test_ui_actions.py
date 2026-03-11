from __future__ import annotations

from macropad_ble.ui.actions import (
    ACTION_CHANGE_PROFILE,
    ACTION_PROFILE_NEXT,
    ACTION_PROFILE_PREV,
    ACTION_PROFILE_SET,
    cycle_profile_slot,
    format_change_profile_value,
    normalize_profile_action_kind_value,
    parse_change_profile_value,
)


def test_parse_change_profile_defaults() -> None:
    spec = parse_change_profile_value("")
    assert spec.mode == "next"
    assert spec.step == 1
    assert spec.min_slot == 1
    assert spec.max_slot == 4


def test_parse_change_profile_set_value() -> None:
    spec = parse_change_profile_value("mode=set;slot=8;min=3;max=9")
    assert spec.mode == "set"
    assert spec.target == 8
    assert spec.min_slot == 3
    assert spec.max_slot == 9


def test_parse_change_profile_swaps_invalid_range() -> None:
    spec = parse_change_profile_value("mode=next;step=2;min=10;max=4")
    assert spec.mode == "next"
    assert spec.step == 2
    assert spec.min_slot == 4
    assert spec.max_slot == 10


def test_normalize_legacy_profile_actions() -> None:
    kind_set, value_set = normalize_profile_action_kind_value(ACTION_PROFILE_SET, "3")
    assert kind_set == ACTION_CHANGE_PROFILE
    assert parse_change_profile_value(value_set).mode == "set"

    kind_next, value_next = normalize_profile_action_kind_value(ACTION_PROFILE_NEXT, "2")
    assert kind_next == ACTION_CHANGE_PROFILE
    parsed_next = parse_change_profile_value(value_next)
    assert parsed_next.mode == "next"
    assert parsed_next.step == 2

    kind_prev, value_prev = normalize_profile_action_kind_value(ACTION_PROFILE_PREV, "1")
    assert kind_prev == ACTION_CHANGE_PROFILE
    parsed_prev = parse_change_profile_value(value_prev)
    assert parsed_prev.mode == "prev"
    assert parsed_prev.step == 1


def test_format_change_profile_round_trip() -> None:
    original = parse_change_profile_value("mode=prev;step=3;min=2;max=7")
    text = format_change_profile_value(original)
    parsed = parse_change_profile_value(text)
    assert parsed.mode == "prev"
    assert parsed.step == 3
    assert parsed.min_slot == 2
    assert parsed.max_slot == 7


def test_cycle_profile_slot_wraps_forward_and_backward() -> None:
    assert cycle_profile_slot(4, 1, min_slot=1, max_slot=4) == 1
    assert cycle_profile_slot(1, -1, min_slot=1, max_slot=4) == 4


def test_cycle_profile_slot_wraps_large_delta() -> None:
    assert cycle_profile_slot(4, 5, min_slot=1, max_slot=4) == 1
    assert cycle_profile_slot(2, -5, min_slot=1, max_slot=4) == 1

import asyncio

import macropad_ble.ui.actions as actions
from macropad_ble.ui.key_names import normalize_key_sequence, normalize_single_key_name
from macropad_ble.ui.profile import KeyAction


def test_execute_python_action_uses_pythonw_on_windows(monkeypatch) -> None:
    launched: list[list[str]] = []
    logs: list[str] = []

    monkeypatch.setattr(actions.os, "name", "nt", raising=False)
    monkeypatch.setattr(actions, "_pythonw_executable", lambda: "pythonw.exe")
    monkeypatch.setattr(actions, "_launch_process", lambda cmd: launched.append(cmd))

    asyncio.run(actions.execute_action(KeyAction(kind=actions.ACTION_PYTHON, value="script.py"), log=logs.append))

    assert launched == [["pythonw.exe", "script.py"]]
    assert logs and "Executed Python" in logs[0]


def test_execute_file_action_uses_pythonw_for_py_files_on_windows(monkeypatch, tmp_path) -> None:
    script_path = tmp_path / "macro.py"
    script_path.write_text("print('ok')\n", encoding="utf-8")

    launched: list[list[str]] = []
    logs: list[str] = []

    monkeypatch.setattr(actions.os, "name", "nt", raising=False)
    monkeypatch.setattr(actions, "_pythonw_executable", lambda: "pythonw.exe")
    monkeypatch.setattr(actions, "_launch_process", lambda cmd: launched.append(cmd))

    asyncio.run(
        actions.execute_action(
            KeyAction(kind=actions.ACTION_FILE, value=str(script_path)),
            log=logs.append,
        )
    )

    assert launched == [["pythonw.exe", str(script_path)]]
    assert logs and "Executed file" in logs[0]


def test_normalize_media_key_names() -> None:
    assert normalize_single_key_name("media next track") == "next track"
    assert normalize_single_key_name("media previous track") == "previous track"
    assert normalize_key_sequence("ctrl+media next track") == "ctrl+next track"


def test_execute_send_keys_uses_normalized_sequence(monkeypatch) -> None:
    logs: list[str] = []
    sent: list[str] = []

    class FakeKeyboard:
        @staticmethod
        def send(sequence: str) -> None:
            sent.append(sequence)

    import builtins

    real_import = builtins.__import__

    def fake_import(name: str, globals=None, locals=None, fromlist=(), level: int = 0):
        if name == "keyboard":
            return FakeKeyboard
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    asyncio.run(
        actions.execute_action(
            KeyAction(kind=actions.ACTION_SEND_KEYS, value="media next track"),
            log=logs.append,
        )
    )

    assert sent == ["next track"]
    assert logs and "Sent keys: next track" in logs[0]
