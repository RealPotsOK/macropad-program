from __future__ import annotations

import json
from pathlib import Path

from macropad.core.app_state import AppState, load_app_state, save_app_state


def test_load_app_state_defaults_include_zoom(tmp_path: Path) -> None:
    state = load_app_state(tmp_path / "missing.json")
    assert state.last_zoom == "100%"
    assert state.last_dialog_directory == ""


def test_load_app_state_normalizes_zoom(tmp_path: Path) -> None:
    path = tmp_path / "app_state.json"
    path.write_text(
        json.dumps({"last_port": "COM9", "last_baud": 9600, "last_zoom": "90%"}),
        encoding="utf-8",
    )
    state = load_app_state(path)
    assert state.last_zoom == "90%"


def test_save_and_load_app_state_round_trip_zoom(tmp_path: Path) -> None:
    path = tmp_path / "app_state.json"
    save_app_state(path, AppState(last_port="COM12", last_hint="Microchip", last_baud=9600, last_zoom="80%"))
    state = load_app_state(path)
    assert state.last_port == "COM12"
    assert state.last_hint == "Microchip"
    assert state.last_baud == 9600
    assert state.last_zoom == "80%"


def test_save_and_load_app_state_persists_last_dialog_directory(tmp_path: Path) -> None:
    path = tmp_path / "app_state.json"
    expected_dir = str((tmp_path / "profiles").resolve())
    save_app_state(path, AppState(last_dialog_directory=expected_dir))

    state = load_app_state(path)

    assert state.last_dialog_directory == expected_dir


def test_save_and_load_app_state_persists_setup_profiles_and_encoder_inversion(tmp_path: Path) -> None:
    path = tmp_path / "app_state.json"
    state = AppState(
        key_rows=3,
        key_cols=4,
        encoder_inverted=True,
        active_setup_profile="Desk",
        setup_profiles={
            "Desk": {
                "key_rows": 3,
                "key_cols": 4,
                "has_encoder": True,
                "has_screen": True,
                "encoder_inverted": True,
                "key_mapping": {"0,0": "0,1"},
                "screen_command_prefix": "TXT:",
                "screen_line_separator": "",
                "screen_end_token": "\\n",
            }
        },
    )
    save_app_state(path, state)

    loaded = load_app_state(path)

    assert loaded.encoder_inverted is True
    assert loaded.active_setup_profile == "Desk"
    assert "Desk" in loaded.setup_profiles
    assert loaded.setup_profiles["Desk"]["encoder_inverted"] is True
