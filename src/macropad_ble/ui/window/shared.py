from __future__ import annotations

import asyncio
import ast
import copy
import ctypes
import os
import re
import subprocess
import sys
import time
import textwrap
from collections import deque
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Any, Coroutine
import tkinter as tk

from ...config import DEFAULT_SETTINGS, Settings
from ...serial import (
    BoardSerial,
    EVENT_ENC_DELTA,
    EVENT_ENC_SWITCH,
    EVENT_KEY_STATE,
    BoardEvent,
    PortSelectionError,
    SerialControllerError,
    list_serial_ports,
    monitor_with_reconnect,
)
from ..actions import (
    ACTION_AHK,
    ACTION_CHANGE_PROFILE,
    ACTION_FILE,
    ACTION_KEYBOARD,
    ACTION_PROFILE_NEXT,
    ACTION_PROFILE_PREV,
    ACTION_PROFILE_SET,
    ACTION_PYTHON,
    ACTION_SEND_KEYS,
    ACTION_VOLUME_MIXER,
    ACTION_TYPES,
    ActionExecutionError,
    ProfileChangeSpec,
    cycle_profile_slot,
    execute_action,
    format_change_profile_value,
    normalize_profile_action_kind_value,
    parse_change_profile_value,
    PROFILE_CHANGE_MODES,
)
from ..app_state import load_app_state, save_app_state
from ..key_layout import KEY_DISPLAY_MAP, map_key_to_display
from ..oled_text import (
    DESCRIPTION_PRESET_CUSTOM,
    DESCRIPTION_PRESET_LABELS,
    description_refresh_interval,
    description_template_for_label,
    infer_description_preset_label,
    render_profile_display_lines,
)
from ..profile import (
    ACTION_NONE,
    KeyAction,
    KeyBinding,
    create_default_profile,
    load_profile,
    render_profile_oled_lines,
    save_profile,
)

BG_APP = "#050A19"
BG_PANEL = "#0C1327"
BG_INPUT = "#111A33"
FG_TEXT = "#E5ECFF"
FG_MUTED = "#93A7D9"
FG_ACCENT = "#93C5FD"
BORDER_MUTED = "#1F2A44"
BORDER_SELECTED = "#60A5FA"
KEY_BG = "#2F3648"
KEY_BG_SELECTED = "#3A4460"
KEY_BG_PRESSED = "#3F5168"

STATUS_COLORS = {
    "disconnected": "#DC2626",
    "connecting": "#D97706",
    "connected": "#16A34A",
    "reconnecting": "#EA580C",
}

SCRIPT_MODES = ("python", "ahk", "file", "step")
INLINE_PYTHON_ACTION_VALUE = "<inline python script>"
KEY_PICKER_KEYS: list[str] = []
KEY_PICKER_KEYS.extend([chr(code) for code in range(ord("a"), ord("z") + 1)])
KEY_PICKER_KEYS.extend([str(number) for number in range(10)])
KEY_PICKER_KEYS.extend(
    [
        "`",
        "-",
        "=",
        "[",
        "]",
        "\\",
        ";",
        "'",
        ",",
        ".",
        "/",
        "~",
        "!",
        "@",
        "#",
        "$",
        "%",
        "^",
        "&",
        "*",
        "(",
        ")",
        "_",
        "+",
        "{",
        "}",
        "|",
        ":",
        '"',
        "<",
        ">",
        "?",
        "grave",
        "backtick",
        "minus",
        "dash",
        "equals",
        "equal",
        "plus",
        "left bracket",
        "right bracket",
        "open bracket",
        "close bracket",
        "backslash",
        "pipe",
        "semicolon",
        "apostrophe",
        "quote",
        "comma",
        "period",
        "dot",
        "slash",
        "forward slash",
    ]
)
KEY_PICKER_KEYS.extend(
    [
        "space",
        "spacebar",
        "tab",
        "enter",
        "return",
        "backspace",
        "delete",
        "del",
        "insert",
        "ins",
        "home",
        "end",
        "page up",
        "pgup",
        "page down",
        "pgdn",
        "up",
        "down",
        "left",
        "right",
        "esc",
        "escape",
        "caps lock",
        "capslock",
        "num lock",
        "numlock",
        "scroll lock",
        "scrolllock",
        "print screen",
        "prtsc",
        "snapshot",
        "pause",
        "break",
        "menu",
        "apps",
    ]
)
KEY_PICKER_KEYS.extend(
    [
        "shift",
        "left shift",
        "right shift",
        "ctrl",
        "control",
        "left ctrl",
        "right ctrl",
        "alt",
        "left alt",
        "right alt",
        "alt gr",
        "altgr",
        "win",
        "windows",
        "left windows",
        "right windows",
        "command",
        "cmd",
        "option",
    ]
)
KEY_PICKER_KEYS.extend([f"f{index}" for index in range(1, 25)])
KEY_PICKER_KEYS.extend(["fn"])
KEY_PICKER_KEYS.extend(
    [
        "numpad 0",
        "numpad 1",
        "numpad 2",
        "numpad 3",
        "numpad 4",
        "numpad 5",
        "numpad 6",
        "numpad 7",
        "numpad 8",
        "numpad 9",
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
        "numpad +",
        "numpad -",
        "numpad *",
        "numpad /",
        "numpad .",
        "numpad ,",
        "numpad enter",
        "numpad decimal",
        "num +",
        "num -",
        "num *",
        "num /",
        "num .",
        "num enter",
        "decimal",
        "add",
        "subtract",
        "multiply",
        "divide",
    ]
)
KEY_PICKER_KEYS.extend(
    [
        "media play pause",
        "play/pause media",
        "media stop",
        "stop media",
        "media next track",
        "media previous track",
        "volume up",
        "volume down",
        "volume mute",
        "browser back",
        "browser forward",
        "browser refresh",
        "browser stop",
        "browser search",
        "browser favorites",
        "browser home",
        "launch mail",
        "launch media select",
        "launch app1",
        "launch app2",
        "calculator",
        "my computer",
        "sleep",
        "wake",
        "power",
    ]
)


def _enable_windows_dpi_awareness() -> None:
    if sys.platform != "win32":
        return
    with suppress(Exception):
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        return
    with suppress(Exception):
        ctypes.windll.shcore.SetProcessDpiAwareness(2)


def _slot_label(slot: int, name: str) -> str:
    return f"{slot}: {name}"


def _slot_from_label(label: str) -> int:
    left = label.split(":", 1)[0].strip()
    try:
        numeric = int(left, 10)
    except ValueError:
        return 1
    return max(1, min(10, numeric))


@dataclass(slots=True)
class TileWidgets:
    canvas: tk.Canvas
    border: int
    stripes: list[int]
    title: int
    state: int
    badge: int
    display_row: int
    display_col: int
    pressed: bool = False
    selected: bool = False




