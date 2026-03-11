from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ACTION_NONE = "none"


@dataclass(slots=True)
class KeyAction:
    kind: str = ACTION_NONE
    value: str = ""
    steps: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class KeyBinding:
    label: str
    action: KeyAction = field(default_factory=KeyAction)
    script_mode: str = "python"
    script_code: str = ""


@dataclass(slots=True)
class Profile:
    name: str
    description: str = ""
    bindings: dict[tuple[int, int], KeyBinding] = field(default_factory=dict)
    enc_up_action: KeyAction = field(default_factory=KeyAction)
    enc_down_action: KeyAction = field(default_factory=KeyAction)
    enc_sw_down_action: KeyAction = field(default_factory=KeyAction)
    enc_sw_up_action: KeyAction = field(default_factory=KeyAction)
    oled_line1: str = "Profile {profile_slot}"
    oled_line2: str = "{profile_name}"


def _key_to_text(key: tuple[int, int]) -> str:
    return f"{key[0]},{key[1]}"


def _key_from_text(text: str) -> tuple[int, int] | None:
    parts = [part.strip() for part in text.split(",")]
    if len(parts) != 2:
        return None
    try:
        row = int(parts[0], 10)
        col = int(parts[1], 10)
    except ValueError:
        return None
    if row < 0 or col < 0:
        return None
    return (row, col)


def create_default_profile(
    name: str,
    *,
    keys: list[tuple[int, int]],
) -> Profile:
    bindings: dict[tuple[int, int], KeyBinding] = {}
    for row, col in sorted(keys):
        bindings[(row, col)] = KeyBinding(label=f"Key {row},{col}")
    return Profile(name=name, bindings=bindings)


def profile_to_dict(profile: Profile) -> dict[str, Any]:
    bindings: dict[str, Any] = {}
    for key, binding in sorted(profile.bindings.items()):
        bindings[_key_to_text(key)] = {
            "label": binding.label,
            "action": {
                "kind": binding.action.kind,
                "value": binding.action.value,
                "steps": list(binding.action.steps),
            },
            "script_mode": binding.script_mode,
            "script_code": binding.script_code,
        }
    encoder_actions = {
        "up": {
            "kind": profile.enc_up_action.kind,
            "value": profile.enc_up_action.value,
            "steps": list(profile.enc_up_action.steps),
        },
        "down": {
            "kind": profile.enc_down_action.kind,
            "value": profile.enc_down_action.value,
            "steps": list(profile.enc_down_action.steps),
        },
        "sw_down": {
            "kind": profile.enc_sw_down_action.kind,
            "value": profile.enc_sw_down_action.value,
            "steps": list(profile.enc_sw_down_action.steps),
        },
        "sw_up": {
            "kind": profile.enc_sw_up_action.kind,
            "value": profile.enc_sw_up_action.value,
            "steps": list(profile.enc_sw_up_action.steps),
        },
    }
    oled = {
        "line1": profile.oled_line1,
        "line2": profile.oled_line2,
    }
    return {
        "name": profile.name,
        "description": profile.description,
        "bindings": bindings,
        "encoder_actions": encoder_actions,
        "oled": oled,
    }


def profile_from_dict(
    data: dict[str, Any],
    *,
    fallback_name: str,
    keys: list[tuple[int, int]],
) -> Profile:
    profile = create_default_profile(fallback_name, keys=keys)
    profile.name = str(data.get("name") or fallback_name)
    profile.description = str(data.get("description") or "")

    raw_bindings = data.get("bindings")
    if not isinstance(raw_bindings, dict):
        raw_bindings = {}

    key_set = set(keys)
    for key_text, value in raw_bindings.items():
        if not isinstance(key_text, str) or not isinstance(value, dict):
            continue
        key = _key_from_text(key_text)
        if key is None or key not in key_set:
            continue

        label = str(value.get("label") or f"Key {key[0]},{key[1]}")
        action_data = value.get("action")
        action = KeyAction()
        if isinstance(action_data, dict):
            action.kind = str(action_data.get("kind") or ACTION_NONE).strip().lower()
            action.value = str(action_data.get("value") or "")
            raw_steps = action_data.get("steps")
            if isinstance(raw_steps, list):
                action.steps = [step for step in raw_steps if isinstance(step, dict)]

        profile.bindings[key] = KeyBinding(label=label, action=action)
        binding = profile.bindings[key]
        binding.script_mode = str(value.get("script_mode") or "python").strip().lower()
        binding.script_code = str(value.get("script_code") or "")

    encoder_data = data.get("encoder_actions")
    if isinstance(encoder_data, dict):
        for direction, attr_name in (
            ("up", "enc_up_action"),
            ("down", "enc_down_action"),
            ("sw_down", "enc_sw_down_action"),
            ("sw_up", "enc_sw_up_action"),
        ):
            raw_action = encoder_data.get(direction)
            if not isinstance(raw_action, dict):
                continue
            action = KeyAction()
            action.kind = str(raw_action.get("kind") or ACTION_NONE).strip().lower()
            action.value = str(raw_action.get("value") or "")
            raw_steps = raw_action.get("steps")
            if isinstance(raw_steps, list):
                action.steps = [step for step in raw_steps if isinstance(step, dict)]
            setattr(profile, attr_name, action)

    oled_data = data.get("oled")
    if isinstance(oled_data, dict):
        profile.oled_line1 = str(oled_data.get("line1") or profile.oled_line1)
        profile.oled_line2 = str(oled_data.get("line2") or profile.oled_line2)
    else:
        profile.oled_line1 = str(data.get("oled_line1") or profile.oled_line1)
        profile.oled_line2 = str(data.get("oled_line2") or profile.oled_line2)

    return profile


def render_profile_oled_lines(profile: Profile, *, slot: int) -> tuple[str, str]:
    context = {
        "profile_slot": int(slot),
        "profile_name": profile.name,
    }
    line1 = _render_oled_line(profile.oled_line1, context)
    line2 = _render_oled_line(profile.oled_line2, context)
    return line1, line2


def _render_oled_line(template: str, context: dict[str, Any]) -> str:
    raw = str(template or "")
    try:
        rendered = raw.format(**context)
    except Exception:
        rendered = raw
    rendered = rendered.replace("\r", " ").replace("\n", " ").strip()
    return rendered


def load_profile(
    path: Path,
    *,
    name: str,
    keys: list[tuple[int, int]],
) -> Profile:
    if not path.exists():
        return create_default_profile(name, keys=keys)

    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Profile JSON root must be an object.")
    return profile_from_dict(raw, fallback_name=name, keys=keys)


def save_profile(path: Path, profile: Profile) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(profile_to_dict(profile), indent=2, sort_keys=True),
        encoding="utf-8",
    )
