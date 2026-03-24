from __future__ import annotations


def keyboard_key_names() -> list[str]:
    keys: list[str] = [
        "Escape",
        "Tab",
        "Caps Lock",
        "Shift",
        "Ctrl",
        "Alt",
        "Win",
        "Space",
        "Enter",
        "Backspace",
        "Delete",
        "Insert",
        "Home",
        "End",
        "Page Up",
        "Page Down",
        "Up",
        "Down",
        "Left",
        "Right",
        "Print Screen",
        "Scroll Lock",
        "Pause",
        "Menu",
    ]
    keys.extend([chr(code) for code in range(ord("A"), ord("Z") + 1)])
    keys.extend([str(number) for number in range(0, 10)])
    keys.extend([f"F{index}" for index in range(1, 25)])
    keys.extend(
        [
            "Numpad 0",
            "Numpad 1",
            "Numpad 2",
            "Numpad 3",
            "Numpad 4",
            "Numpad 5",
            "Numpad 6",
            "Numpad 7",
            "Numpad 8",
            "Numpad 9",
            "Numpad Add",
            "Numpad Subtract",
            "Numpad Multiply",
            "Numpad Divide",
            "Numpad Decimal",
            "Numpad Enter",
        ]
    )
    keys.extend(
        [
            "Semicolon",
            "Equal",
            "Comma",
            "Minus",
            "Period",
            "Slash",
            "Backquote",
            "Left Bracket",
            "Backslash",
            "Right Bracket",
            "Quote",
        ]
    )
    keys.extend(
        [
            "Media Play/Pause",
            "Media Stop",
            "Media Next Track",
            "Media Previous Track",
            "Volume Up",
            "Volume Down",
            "Volume Mute",
            "Browser Back",
            "Browser Forward",
        ]
    )
    return keys

