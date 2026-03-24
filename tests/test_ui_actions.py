from __future__ import annotations

from macropad.core.actions import (
    ACTION_AHK,
    ACTION_CHANGE_PROFILE,
    ACTION_FILE,
    ACTION_KEYBOARD,
    ACTION_MACRO,
    ACTION_PROFILE_NEXT,
    ACTION_PROFILE_PREV,
    ACTION_PROFILE_SET,
    ACTION_PYTHON,
    ACTION_SEND_KEYS,
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


def test_normalize_legacy_non_profile_actions() -> None:
    kind_send_keys, _value_send_keys = normalize_profile_action_kind_value(ACTION_SEND_KEYS, "ctrl+a")
    assert kind_send_keys == ACTION_KEYBOARD

    kind_python, value_python = normalize_profile_action_kind_value(ACTION_PYTHON, "profiles/runtime_python/key.py")
    assert kind_python == ACTION_FILE
    assert value_python == "profiles/runtime_python/key.py"

    kind_ahk, value_ahk = normalize_profile_action_kind_value(ACTION_AHK, "profiles/runtime_ahk/key.ahk")
    assert kind_ahk == ACTION_FILE
    assert value_ahk == "profiles/runtime_ahk/key.ahk"

    kind_macro, value_macro = normalize_profile_action_kind_value(ACTION_MACRO, "legacy payload")
    assert kind_macro == "none"
    assert value_macro == ""


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
from pathlib import Path

import macropad.core.actions as actions
from macropad.platform.paths import AppPaths
from macropad.core.key_names import normalize_key_sequence, normalize_single_key_name
from macropad.core.profile import KeyAction


def test_resolve_action_path_prefers_appdata_profiles_directory(monkeypatch, tmp_path) -> None:
    app_root = tmp_path / "AppData" / "Roaming" / "macropad"
    script_path = app_root / "profiles" / "runtime_python" / "script.py"
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text("print('ok')\n", encoding="utf-8")

    monkeypatch.setattr(
        actions,
        "resolve_app_paths",
        lambda: AppPaths(
            data_root=app_root,
            profile_dir=app_root / "profiles",
            state_path=app_root / "app_state.json",
            legacy_appdata_root=tmp_path / "AppData" / "Roaming" / "macropad-ble",
            legacy_appdata_profile_dir=tmp_path / "AppData" / "Roaming" / "macropad-ble" / "profiles",
            legacy_appdata_state_path=tmp_path / "AppData" / "Roaming" / "macropad-ble" / "app_state.json",
            legacy_profile_dir=tmp_path / "profiles",
            legacy_state_path=tmp_path / "profiles" / "app_state.json",
        ),
    )

    resolved = actions.resolve_action_path("profiles/runtime_python/script.py")

    assert resolved == script_path.resolve()


def test_resolve_action_path_prefers_local_profiles_in_dev_mode(monkeypatch, tmp_path) -> None:
    app_root = tmp_path / "AppData" / "Roaming" / "macropad"
    appdata_script = app_root / "profiles" / "runtime_python" / "script.py"
    local_script = tmp_path / "project" / "profiles" / "runtime_python" / "script.py"
    appdata_script.parent.mkdir(parents=True, exist_ok=True)
    local_script.parent.mkdir(parents=True, exist_ok=True)
    appdata_script.write_text("print('appdata')\n", encoding="utf-8")
    local_script.write_text("print('local')\n", encoding="utf-8")

    monkeypatch.setattr(actions.sys, "frozen", False, raising=False)
    monkeypatch.setattr(
        actions,
        "resolve_app_paths",
        lambda: AppPaths(
            data_root=app_root,
            profile_dir=app_root / "profiles",
            state_path=app_root / "app_state.json",
            legacy_appdata_root=tmp_path / "AppData" / "Roaming" / "macropad-ble",
            legacy_appdata_profile_dir=tmp_path / "AppData" / "Roaming" / "macropad-ble" / "profiles",
            legacy_appdata_state_path=tmp_path / "AppData" / "Roaming" / "macropad-ble" / "app_state.json",
            legacy_profile_dir=tmp_path / "profiles",
            legacy_state_path=tmp_path / "profiles" / "app_state.json",
        ),
    )
    monkeypatch.chdir(local_script.parents[2])

    resolved = actions.resolve_action_path("profiles/runtime_python/script.py")

    assert resolved == local_script.resolve()


def test_execute_legacy_python_action_migrates_to_file_action(monkeypatch, tmp_path) -> None:
    script_path = tmp_path / "macro.py"
    script_path.write_text("print('ok')\n", encoding="utf-8")

    launched: list[list[str]] = []
    logs: list[str] = []

    monkeypatch.setattr(actions.os, "name", "nt", raising=False)
    monkeypatch.setattr(actions, "_pythonw_executable", lambda: "pythonw.exe")
    monkeypatch.setattr(actions, "_launch_process", lambda cmd, **kwargs: launched.append(cmd))

    asyncio.run(
        actions.execute_action(
            KeyAction(kind=actions.ACTION_PYTHON, value=str(script_path)),
            log=logs.append,
        )
    )

    assert launched == [["pythonw.exe", str(script_path)]]
    assert logs and "Executed file:" in logs[0]


def test_execute_file_action_uses_pythonw_for_py_files_on_windows(monkeypatch, tmp_path) -> None:
    script_path = tmp_path / "macro.py"
    script_path.write_text("print('ok')\n", encoding="utf-8")

    launched: list[list[str]] = []
    logs: list[str] = []

    monkeypatch.setattr(actions.os, "name", "nt", raising=False)
    monkeypatch.setattr(actions, "_pythonw_executable", lambda: "pythonw.exe")
    monkeypatch.setattr(actions, "_launch_process", lambda cmd, **kwargs: launched.append(cmd))

    asyncio.run(
        actions.execute_action(
            KeyAction(kind=actions.ACTION_FILE, value=str(script_path)),
            log=logs.append,
        )
    )

    assert launched == [["pythonw.exe", str(script_path)]]
    assert logs and "Executed file" in logs[0]


def test_execute_file_action_plays_audio_in_background_when_callback_provided(monkeypatch, tmp_path) -> None:
    audio_path = tmp_path / "beep.mp3"
    audio_path.write_bytes(b"ID3")

    launched: list[list[str]] = []
    handled: list[str] = []
    logs: list[str] = []

    monkeypatch.setattr(actions.os, "name", "nt", raising=False)
    monkeypatch.setattr(actions, "_launch_windows_file_action", lambda _path: launched.append(["launch"]) or True)

    asyncio.run(
        actions.execute_action(
            KeyAction(kind=actions.ACTION_FILE, value=str(audio_path)),
            log=logs.append,
            on_audio_file=lambda path, _volume=None: handled.append(str(path)) or True,
        )
    )

    assert launched == []
    assert handled and Path(handled[0]).name == "beep.mp3"
    assert logs and logs[0].startswith("Playing audio:")


def test_execute_volume_mixer_action(monkeypatch) -> None:
    logs: list[str] = []
    overlays: list[object] = []

    monkeypatch.setattr(
        actions,
        "change_volume_mixer_volume",
        lambda raw_value, direction=1: type(
            "Result",
            (),
            {
                "label": "spotify.exe",
                "title": "Spotify",
                "matched_sessions": 1,
                "volume_percent": 55,
                "icon_path": "",
            },
        )(),
    )

    asyncio.run(
        actions.execute_action(
            KeyAction(kind=actions.ACTION_VOLUME_MIXER, value="kind=process;target=spotify.exe;step=0.05"),
            log=logs.append,
            volume_direction=-1,
            on_volume_mixer=overlays.append,
        )
    )

    assert logs == ["Volume mixer: spotify.exe -> 55% (1 session)"]
    assert len(overlays) == 1


def test_execute_change_profile_action_calls_handler() -> None:
    logs: list[str] = []
    received: list[object] = []

    asyncio.run(
        actions.execute_action(
            KeyAction(kind=ACTION_CHANGE_PROFILE, value="mode=prev;step=2;min=1;max=4"),
            log=logs.append,
            on_change_profile=received.append,
        )
    )

    assert len(received) == 1
    spec = received[0]
    assert getattr(spec, "mode", None) == "prev"
    assert getattr(spec, "step", None) == 2
    assert logs and logs[0].startswith("Change profile: mode=prev;step=2")


def test_run_python_script_file_executes_main_and_captures_output(tmp_path) -> None:
    script_path = tmp_path / "run_me.py"
    marker_path = tmp_path / "marker.txt"
    script_path.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "print('hello')",
                f"Path({str(marker_path)!r}).write_text('done', encoding='utf-8')",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = actions._run_python_script_file(script_path)

    assert result.stdout == "hello"
    assert result.stderr == ""
    assert marker_path.read_text(encoding="utf-8") == "done"


def test_pythonw_executable_ignores_packaged_app_exe(monkeypatch, tmp_path) -> None:
    app_exe = tmp_path / "MacroPad Controller.exe"
    python_exe = tmp_path / "python.exe"
    app_exe.write_text("", encoding="utf-8")
    python_exe.write_text("", encoding="utf-8")

    monkeypatch.setattr(actions.os, "name", "nt", raising=False)
    monkeypatch.setattr(actions.sys, "executable", str(app_exe))
    monkeypatch.setattr(actions.sys, "_base_executable", str(app_exe), raising=False)
    monkeypatch.setattr(
        actions.shutil,
        "which",
        lambda name: str(python_exe) if name.lower() == "python.exe" else None,
    )

    assert actions._pythonw_executable() == str(python_exe)


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
