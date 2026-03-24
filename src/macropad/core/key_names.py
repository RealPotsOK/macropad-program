from __future__ import annotations

import re

_ALIASES = {
    "prtsc": "print screen",
    "snapshot": "print screen",
    "del": "delete",
    "ins": "insert",
    "pgup": "page up",
    "pgdn": "page down",
    "capslock": "caps lock",
    "numlock": "num lock",
    "scrolllock": "scroll lock",
    "escape": "esc",
    "return": "enter",
    "control": "ctrl",
    "left control": "left ctrl",
    "right control": "right ctrl",
    "windows": "win",
    "left windows": "left windows",
    "right windows": "right windows",
    "command": "win",
    "cmd": "win",
    "option": "alt",
    "spacebar": "space",
    "play/pause media": "play/pause media",
    "media play pause": "play/pause media",
    "media stop": "stop media",
    "media next track": "next track",
    "media previous track": "previous track",
}


def normalize_single_key_name(value: str) -> str:
    normalized = re.sub(r"\s+", " ", str(value or "").strip().lower())
    if not normalized:
        return ""
    return _ALIASES.get(normalized, normalized)


def normalize_key_sequence(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""

    parts = re.split(r"(\+|,)", raw)
    normalized: list[str] = []
    for part in parts:
        token = part.strip()
        if not token:
            continue
        if token in {"+", ","}:
            normalized.append(token)
            continue
        normalized.append(normalize_single_key_name(token))
    return "".join(normalized)
