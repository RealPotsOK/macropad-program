from __future__ import annotations

from ..core.profile import ACTION_NONE

APP_TITLE = "MacroPad Controller"

SCRIPT_MODES = ("python", "ahk", "file", "step")
INLINE_PYTHON_ACTION_VALUE = "<inline python script>"
ZOOM_LEVELS = ("100%", "90%", "80%", "70%")

NAV_ITEMS = (
    ("controller", "Controller"),
    ("scripts", "Scripts"),
    ("personalization", "Personalization"),
    ("stats", "Stats"),
)

STATUS_COLORS = {
    "disconnected": "#DC2626",
    "connecting": "#D97706",
    "connected": "#16A34A",
    "reconnecting": "#EA580C",
}

ACTION_LABELS = {
    ACTION_NONE: "None",
    "keyboard": "Keyboard",
    "file": "File",
    "volume_mixer": "Volume Mixer",
    "change_profile": "Change Profile",
    "window_control": "Window Control",
}


def slot_label(slot: int, name: str) -> str:
    return f"{slot}: {name}"


def slot_from_label(label: str) -> int:
    left = str(label or "").split(":", 1)[0].strip()
    try:
        numeric = int(left, 10)
    except ValueError:
        return 1
    return max(1, min(10, numeric))


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
