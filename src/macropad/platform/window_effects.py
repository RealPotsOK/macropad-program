from __future__ import annotations

import ctypes
from ctypes import wintypes
import sys


DWMWA_SYSTEMBACKDROP_TYPE = 38

SYSTEM_BACKDROP_AUTO = 0
SYSTEM_BACKDROP_NONE = 1
SYSTEM_BACKDROP_MAINWINDOW = 2  # Mica
SYSTEM_BACKDROP_TRANSIENTWINDOW = 3  # Acrylic-like
SYSTEM_BACKDROP_TABBEDWINDOW = 4

ACCENT_DISABLED = 0
ACCENT_ENABLE_BLURBEHIND = 3
ACCENT_ENABLE_ACRYLICBLURBEHIND = 4

WCA_ACCENT_POLICY = 19


class DWM_BLURBEHIND(ctypes.Structure):
    _fields_ = [
        ("dwFlags", wintypes.DWORD),
        ("fEnable", wintypes.BOOL),
        ("hRgnBlur", wintypes.HRGN),
        ("fTransitionOnMaximized", wintypes.BOOL),
    ]


class ACCENT_POLICY(ctypes.Structure):
    _fields_ = [
        ("AccentState", ctypes.c_int),
        ("AccentFlags", ctypes.c_int),
        ("GradientColor", ctypes.c_uint32),
        ("AnimationId", ctypes.c_int),
    ]


class WINDOWCOMPOSITIONATTRIBDATA(ctypes.Structure):
    _fields_ = [
        ("Attribute", ctypes.c_int),
        ("Data", ctypes.c_void_p),
        ("SizeOfData", ctypes.c_size_t),
    ]


def apply_backdrop(hwnd: int, *, mode: str, color: str, opacity: int = 180) -> bool:
    """Try modern DWM backdrop first, then AccentPolicy, then legacy blur-behind."""
    if sys.platform != "win32" or not hwnd:
        return False

    requested = str(mode or "none").strip().lower()
    if requested in {"none", "off", "disabled"}:
        _disable_accent(hwnd)
        _set_system_backdrop(hwnd, SYSTEM_BACKDROP_NONE)
        return True

    # 1) Win11+ backdrop attribute.
    backdrop = _system_backdrop_for_mode(requested)
    if backdrop is not None and _set_system_backdrop(hwnd, backdrop):
        return True

    # 2) Accent policy (works on Win10/Win11).
    accent_state = _accent_state_for_mode(requested)
    if accent_state is not None and _set_accent(hwnd, accent_state, color=color, opacity=opacity):
        return True

    # 3) Legacy blur-behind fallback.
    return _enable_legacy_blur_behind(hwnd)


def _set_system_backdrop(hwnd: int, backdrop: int) -> bool:
    try:
        dwmapi = ctypes.windll.dwmapi
        value = ctypes.c_int(int(backdrop))
        func = dwmapi.DwmSetWindowAttribute
        func.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
        func.restype = ctypes.c_long
        result = func(
            wintypes.HWND(hwnd),
            wintypes.DWORD(DWMWA_SYSTEMBACKDROP_TYPE),
            ctypes.byref(value),
            wintypes.DWORD(ctypes.sizeof(value)),
        )
        return int(result) == 0
    except Exception:
        return False


def _set_accent(hwnd: int, accent_state: int, *, color: str, opacity: int) -> bool:
    try:
        user32 = ctypes.windll.user32
        set_window_composition_attribute = user32.SetWindowCompositionAttribute
    except Exception:
        return False

    accent = ACCENT_POLICY()
    accent.AccentState = int(accent_state)
    accent.AccentFlags = 0
    accent.GradientColor = _gradient_color(color, opacity) if accent_state != ACCENT_DISABLED else 0
    accent.AnimationId = 0

    data = WINDOWCOMPOSITIONATTRIBDATA()
    data.Attribute = WCA_ACCENT_POLICY
    data.Data = ctypes.addressof(accent)
    data.SizeOfData = ctypes.sizeof(accent)

    try:
        set_window_composition_attribute.argtypes = [
            wintypes.HWND,
            ctypes.POINTER(WINDOWCOMPOSITIONATTRIBDATA),
        ]
        set_window_composition_attribute.restype = wintypes.BOOL
        return bool(set_window_composition_attribute(wintypes.HWND(hwnd), ctypes.byref(data)))
    except Exception:
        return False


def _enable_legacy_blur_behind(hwnd: int) -> bool:
    DWM_BB_ENABLE = 0x00000001
    blur = DWM_BLURBEHIND()
    blur.dwFlags = DWM_BB_ENABLE
    blur.fEnable = True
    blur.hRgnBlur = 0
    blur.fTransitionOnMaximized = False
    try:
        dwmapi = ctypes.windll.dwmapi
        func = dwmapi.DwmEnableBlurBehindWindow
        func.argtypes = [wintypes.HWND, ctypes.POINTER(DWM_BLURBEHIND)]
        func.restype = ctypes.c_long
        result = func(wintypes.HWND(hwnd), ctypes.byref(blur))
        return int(result) == 0
    except Exception:
        return False


def _disable_accent(hwnd: int) -> bool:
    return _set_accent(hwnd, ACCENT_DISABLED, color="#000000", opacity=0)


def _system_backdrop_for_mode(mode: str) -> int | None:
    if mode in {"mica"}:
        return SYSTEM_BACKDROP_MAINWINDOW
    if mode in {"acrylic"}:
        return SYSTEM_BACKDROP_TRANSIENTWINDOW
    if mode in {"tabbed"}:
        return SYSTEM_BACKDROP_TABBEDWINDOW
    if mode in {"blur"}:
        # No direct "blur" system backdrop type; handled by Accent/legacy.
        return None
    return None


def _accent_state_for_mode(mode: str) -> int | None:
    if mode in {"blur"}:
        return ACCENT_ENABLE_BLURBEHIND
    if mode in {"acrylic", "mica"}:
        return ACCENT_ENABLE_ACRYLICBLURBEHIND
    if mode in {"none", "off", "disabled"}:
        return ACCENT_DISABLED
    return None


def _gradient_color(color: str, opacity: int) -> int:
    text = str(color or "").strip().lstrip("#")
    if len(text) == 3:
        text = "".join(ch * 2 for ch in text)
    if len(text) >= 8:
        text = text[-6:]
    if len(text) != 6:
        text = "000000"
    try:
        red = int(text[0:2], 16)
        green = int(text[2:4], 16)
        blue = int(text[4:6], 16)
    except ValueError:
        red = green = blue = 0
    alpha = max(0, min(255, int(opacity)))
    return (alpha << 24) | (blue << 16) | (green << 8) | red
