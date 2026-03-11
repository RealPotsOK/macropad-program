"""Profile 2 (Polus) - R0,C2 action."""

from __future__ import annotations

import ctypes
import time
from ctypes import wintypes

VK_TAB = 0x09
KEYEVENTF_KEYUP = 0x0002
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
TARGET_X = 1380
TARGET_Y = 480


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


def _press_tab(user32: ctypes.WinDLL) -> None:
    user32.keybd_event(VK_TAB, 0, 0, 0)
    user32.keybd_event(VK_TAB, 0, KEYEVENTF_KEYUP, 0)


def _left_click(user32: ctypes.WinDLL) -> None:
    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)


def main() -> None:
    user32 = ctypes.windll.user32
    pos = POINT()
    if not user32.GetCursorPos(ctypes.byref(pos)):
        raise OSError("GetCursorPos failed.")

    original_x, original_y = int(pos.x), int(pos.y)

    _press_tab(user32)
    time.sleep(0.03)

    user32.SetCursorPos(TARGET_X, TARGET_Y)
    time.sleep(0.02)
    _left_click(user32)
    time.sleep(0.02)

    _press_tab(user32)
    time.sleep(0.02)

    user32.SetCursorPos(original_x, original_y)


if __name__ == "__main__":
    main()

