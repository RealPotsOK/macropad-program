from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class AppState:
    last_port: str = ""
    last_baud: int = 115200
    last_zoom: str = "100%"
    auto_connect: bool = True
    selected_profile_slot: int = 1
    profile_names: dict[str, str] = field(default_factory=dict)
    last_dialog_directory: str = ""


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


def load_app_state(path: Path) -> AppState:
    if not path.exists():
        return AppState()

    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return AppState()

    state = AppState()
    state.last_port = str(raw.get("last_port") or "")
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

    return state


def save_app_state(path: Path, state: AppState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "last_port": state.last_port,
        "last_baud": int(state.last_baud),
        "last_zoom": _normalize_zoom(state.last_zoom),
        "auto_connect": bool(state.auto_connect),
        "selected_profile_slot": _normalize_slot(state.selected_profile_slot),
        "profile_names": dict(state.profile_names),
        "last_dialog_directory": str(state.last_dialog_directory or "").strip(),
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
