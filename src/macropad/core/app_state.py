from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .key_layout import DEFAULT_KEY_COLS, DEFAULT_KEY_ROWS, key_from_text, key_to_text, normalize_key_dimensions


@dataclass(slots=True)
class AppState:
    last_port: str = ""
    last_hint: str = ""
    last_baud: int = 115200
    last_zoom: str = "100%"
    auto_connect: bool = True
    selected_profile_slot: int = 1
    profile_names: dict[str, str] = field(default_factory=dict)
    last_dialog_directory: str = ""
    key_rows: int = DEFAULT_KEY_ROWS
    key_cols: int = DEFAULT_KEY_COLS
    has_encoder: bool = True
    has_screen: bool = True
    key_mapping: dict[str, str] = field(default_factory=dict)
    screen_command_prefix: str = "TXT:"
    screen_line_separator: str = "|"
    screen_end_token: str = "\\n"
    encoder_inverted: bool = False
    active_setup_profile: str = "Default"
    setup_profiles: dict[str, dict[str, Any]] = field(default_factory=dict)
    audio_output_device: str = ""


def _normalize_slot(slot: Any) -> int:
    try:
        numeric = int(slot)
    except (TypeError, ValueError):
        return 1
    if numeric < 1:
        return 1
    if numeric > 10:
        return 10
    return numeric


def _normalize_zoom(value: Any) -> str:
    raw = str(value or "").strip()
    if raw.endswith("%"):
        raw = raw[:-1].strip()
    try:
        percent = int(raw)
    except (TypeError, ValueError):
        return "100%"
    if percent in {70, 80, 90, 100}:
        return f"{percent}%"
    return "100%"


def _normalize_screen_token(
    value: Any,
    fallback: str,
    *,
    max_len: int = 32,
    allow_empty: bool = False,
) -> str:
    text = str(value or "").replace("\r", "").replace("\n", "")
    if not text:
        if allow_empty:
            return ""
        return fallback
    if len(text) > max_len:
        return text[:max_len]
    return text


def _normalize_key_mapping(
    mapping: Any,
    *,
    key_rows: int,
    key_cols: int,
) -> dict[str, str]:
    if not isinstance(mapping, dict):
        return {}
    valid_targets = set(key_to_text(key) for key in [(row, col) for row in range(key_rows) for col in range(key_cols)])
    normalized: dict[str, str] = {}
    for raw_board, raw_virtual in mapping.items():
        board = key_from_text(str(raw_board or ""))
        virtual = key_from_text(str(raw_virtual or ""))
        if board is None or virtual is None:
            continue
        board_text = key_to_text(board)
        virtual_text = key_to_text(virtual)
        if virtual_text not in valid_targets:
            continue
        normalized[board_text] = virtual_text
    return normalized


def _normalize_profile_name(value: Any) -> str:
    text = str(value or "").strip()
    return text or "Default"


def _normalize_setup_profiles(raw_profiles: Any, *, fallback: AppState) -> dict[str, dict[str, Any]]:
    profiles: dict[str, dict[str, Any]] = {}
    if isinstance(raw_profiles, dict):
        for raw_name, raw_payload in raw_profiles.items():
            name = _normalize_profile_name(raw_name)
            if not isinstance(raw_payload, dict):
                continue
            rows, cols = normalize_key_dimensions(
                _safe_int(raw_payload.get("key_rows", fallback.key_rows), fallback.key_rows),
                _safe_int(raw_payload.get("key_cols", fallback.key_cols), fallback.key_cols),
            )
            profiles[name] = {
                "key_rows": rows,
                "key_cols": cols,
                "has_encoder": bool(raw_payload.get("has_encoder", fallback.has_encoder)),
                "has_screen": bool(raw_payload.get("has_screen", fallback.has_screen)),
                "key_mapping": _normalize_key_mapping(
                    raw_payload.get("key_mapping"),
                    key_rows=rows,
                    key_cols=cols,
                ),
                "screen_command_prefix": _normalize_screen_token(
                    raw_payload.get("screen_command_prefix", fallback.screen_command_prefix),
                    fallback.screen_command_prefix,
                    max_len=32,
                ),
                "screen_line_separator": _normalize_screen_token(
                    raw_payload.get("screen_line_separator", fallback.screen_line_separator),
                    fallback.screen_line_separator,
                    max_len=8,
                    allow_empty=True,
                ),
                "screen_end_token": _normalize_screen_token(
                    raw_payload.get("screen_end_token", fallback.screen_end_token),
                    fallback.screen_end_token,
                    max_len=16,
                ),
                "encoder_inverted": bool(raw_payload.get("encoder_inverted", fallback.encoder_inverted)),
            }

    if not profiles:
        profiles["Default"] = {
            "key_rows": fallback.key_rows,
            "key_cols": fallback.key_cols,
            "has_encoder": fallback.has_encoder,
            "has_screen": fallback.has_screen,
            "key_mapping": _normalize_key_mapping(
                fallback.key_mapping,
                key_rows=fallback.key_rows,
                key_cols=fallback.key_cols,
            ),
            "screen_command_prefix": fallback.screen_command_prefix,
            "screen_line_separator": fallback.screen_line_separator,
            "screen_end_token": fallback.screen_end_token,
            "encoder_inverted": bool(fallback.encoder_inverted),
        }
    return profiles


def _safe_int(value: Any, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(fallback)


def load_app_state(path: Path) -> AppState:
    if not path.exists():
        return AppState()

    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return AppState()

    state = AppState()
    state.last_port = str(raw.get("last_port") or "")
    state.last_hint = str(raw.get("last_hint") or "").strip()
    try:
        state.last_baud = int(raw.get("last_baud", state.last_baud))
    except (TypeError, ValueError):
        state.last_baud = 115200
    state.last_zoom = _normalize_zoom(raw.get("last_zoom", state.last_zoom))
    state.auto_connect = bool(raw.get("auto_connect", True))
    state.selected_profile_slot = _normalize_slot(raw.get("selected_profile_slot", 1))

    raw_profile_names = raw.get("profile_names")
    if isinstance(raw_profile_names, dict):
        for key, value in raw_profile_names.items():
            key_text = str(key).strip()
            name_text = str(value).strip()
            if key_text and name_text:
                state.profile_names[key_text] = name_text

    state.last_dialog_directory = str(raw.get("last_dialog_directory") or "").strip()
    state.key_rows, state.key_cols = normalize_key_dimensions(
        _safe_int(raw.get("key_rows", state.key_rows), state.key_rows),
        _safe_int(raw.get("key_cols", state.key_cols), state.key_cols),
    )
    state.has_encoder = bool(raw.get("has_encoder", state.has_encoder))
    state.has_screen = bool(raw.get("has_screen", state.has_screen))
    state.screen_command_prefix = _normalize_screen_token(
        raw.get("screen_command_prefix", state.screen_command_prefix),
        state.screen_command_prefix,
        max_len=32,
    )
    state.screen_line_separator = _normalize_screen_token(
        raw.get("screen_line_separator", state.screen_line_separator),
        state.screen_line_separator,
        max_len=8,
        allow_empty=True,
    )
    state.screen_end_token = _normalize_screen_token(
        raw.get("screen_end_token", state.screen_end_token),
        state.screen_end_token,
        max_len=16,
    )
    state.encoder_inverted = bool(raw.get("encoder_inverted", state.encoder_inverted))
    state.key_mapping = _normalize_key_mapping(
        raw.get("key_mapping"),
        key_rows=state.key_rows,
        key_cols=state.key_cols,
    )
    state.setup_profiles = _normalize_setup_profiles(raw.get("setup_profiles"), fallback=state)
    state.active_setup_profile = _normalize_profile_name(raw.get("active_setup_profile", "Default"))
    if state.active_setup_profile not in state.setup_profiles:
        state.active_setup_profile = sorted(state.setup_profiles.keys())[0]
    state.audio_output_device = str(raw.get("audio_output_device") or "").strip()

    return state


def save_app_state(path: Path, state: AppState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "last_port": state.last_port,
        "last_hint": str(state.last_hint or "").strip(),
        "last_baud": int(state.last_baud),
        "last_zoom": _normalize_zoom(state.last_zoom),
        "auto_connect": bool(state.auto_connect),
        "selected_profile_slot": _normalize_slot(state.selected_profile_slot),
        "profile_names": dict(state.profile_names),
        "last_dialog_directory": str(state.last_dialog_directory or "").strip(),
        "key_rows": int(state.key_rows),
        "key_cols": int(state.key_cols),
        "has_encoder": bool(state.has_encoder),
        "has_screen": bool(state.has_screen),
        "key_mapping": _normalize_key_mapping(
            state.key_mapping,
            key_rows=state.key_rows,
            key_cols=state.key_cols,
        ),
        "screen_command_prefix": _normalize_screen_token(
            state.screen_command_prefix,
            "TXT:",
            max_len=32,
        ),
        "screen_line_separator": _normalize_screen_token(
            state.screen_line_separator,
            "|",
            max_len=8,
            allow_empty=True,
        ),
        "screen_end_token": _normalize_screen_token(
            state.screen_end_token,
            "\\n",
            max_len=16,
        ),
        "encoder_inverted": bool(state.encoder_inverted),
        "active_setup_profile": _normalize_profile_name(state.active_setup_profile),
        "setup_profiles": _normalize_setup_profiles(state.setup_profiles, fallback=state),
        "audio_output_device": str(state.audio_output_device or "").strip(),
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
