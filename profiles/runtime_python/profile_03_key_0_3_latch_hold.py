"""Profile 3 - R0,C3 key latch toggle (Python version).

Press macro key once:
- Captures currently pressed watch keys.
- Latches them down.

Press macro key again:
- Releases all latched keys in reverse order.

This script persists latch state across invocations using small state files.
"""

from __future__ import annotations

import json
import os
import string
import subprocess
import sys
import time
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
STATE_PATH = SCRIPT_DIR / ".profile_03_r0_c3_latch_state.json"
RELEASE_FLAG_PATH = SCRIPT_DIR / ".profile_03_r0_c3_latch_release.flag"


def _watch_keys() -> list[str]:
    keys = [
        "space",
        "tab",
        "enter",
        "esc",
        "backspace",
        "up",
        "down",
        "left",
        "right",
        "home",
        "end",
        "page up",
        "page down",
        "insert",
        "delete",
        "left shift",
        "right shift",
        "left ctrl",
        "right ctrl",
        "left alt",
        "right alt",
        "left windows",
        "right windows",
        "caps lock",
        "num lock",
        "scroll lock",
        "print screen",
        "pause",
        "num 0",
        "num 1",
        "num 2",
        "num 3",
        "num 4",
        "num 5",
        "num 6",
        "num 7",
        "num 8",
        "num 9",
        "decimal",
        "add",
        "subtract",
        "multiply",
        "divide",
        "num enter",
    ]
    keys.extend(list(string.ascii_lowercase))
    keys.extend([str(index) for index in range(10)])
    keys.extend([f"f{index}" for index in range(1, 25)])
    return keys


def _normalize_key_name(name: str) -> str:
    return " ".join(str(name or "").strip().lower().replace("_", " ").split())


def _capture_pressed_keys() -> list[str]:
    import keyboard  # type: ignore

    pressed: list[str] = []
    for key_name in _watch_keys():
        try:
            if keyboard.is_pressed(key_name):
                pressed.append(key_name)
        except Exception:
            continue
    # Keep order but remove duplicates.
    deduped = list(dict.fromkeys(pressed))
    return deduped


def _write_state(keys: list[str]) -> None:
    payload = {
        "keys": keys,
        "started_at": time.time(),
    }
    STATE_PATH.write_text(json.dumps(payload), encoding="utf-8")


def _read_state_keys() -> list[str]:
    if not STATE_PATH.exists():
        return []
    try:
        raw = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []
    keys = raw.get("keys")
    if not isinstance(keys, list):
        return []
    return [str(value) for value in keys if str(value).strip()]


def _cleanup_state_files() -> None:
    for path in (STATE_PATH, RELEASE_FLAG_PATH):
        try:
            if path.exists():
                path.unlink()
        except Exception:
            pass


def _release_keys_now(keys: list[str]) -> None:
    import keyboard  # type: ignore

    for key_name in reversed(keys):
        with _suppress_exceptions():
            keyboard.release(key_name)


class _suppress_exceptions:
    def __enter__(self) -> None:
        return None

    def __exit__(self, _exc_type, _exc, _tb) -> bool:
        return True


def _spawn_daemon() -> None:
    command = [sys.executable, str(Path(__file__).resolve()), "--daemon"]
    creationflags = 0
    if os.name == "nt":
        creationflags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        creationflags |= getattr(subprocess, "DETACHED_PROCESS", 0)
    subprocess.Popen(command, close_fds=True, creationflags=creationflags)


def _daemon_loop() -> None:
    import keyboard  # type: ignore

    keys = _read_state_keys()
    if not keys:
        _cleanup_state_files()
        return

    held_set = {_normalize_key_name(name) for name in keys}

    for key_name in keys:
        with _suppress_exceptions():
            keyboard.press(key_name)

    def _reassert_on_up(event: object) -> None:
        event_type = getattr(event, "event_type", "")
        name = _normalize_key_name(getattr(event, "name", ""))
        if event_type != "up":
            return
        if name not in held_set:
            return
        with _suppress_exceptions():
            keyboard.press(name)

    hook = keyboard.hook(_reassert_on_up, suppress=False)
    try:
        while not RELEASE_FLAG_PATH.exists():
            time.sleep(0.02)
    finally:
        with _suppress_exceptions():
            keyboard.unhook(hook)
        _release_keys_now(keys)
        _cleanup_state_files()


def _toggle_latch() -> None:
    if STATE_PATH.exists():
        # Toggle off.
        with _suppress_exceptions():
            RELEASE_FLAG_PATH.write_text("release", encoding="utf-8")
        deadline = time.time() + 2.0
        while STATE_PATH.exists() and time.time() < deadline:
            time.sleep(0.02)
        if STATE_PATH.exists():
            # Daemon not running or failed, fallback release now.
            keys = _read_state_keys()
            _release_keys_now(keys)
            _cleanup_state_files()
        return

    keys = _capture_pressed_keys()
    if not keys:
        return
    _cleanup_state_files()
    _write_state(keys)
    _spawn_daemon()


def main() -> None:
    if "--daemon" in sys.argv[1:]:
        _daemon_loop()
        return
    _toggle_latch()


if __name__ == "__main__":
    main()

