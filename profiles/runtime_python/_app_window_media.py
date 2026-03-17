from __future__ import annotations

import ctypes
from ctypes import wintypes
from pathlib import Path

WM_APPCOMMAND = 0x0319
APPCOMMAND_MEDIA_PLAY_PAUSE = 14
SMTO_ABORTIFHUNG = 0x0002
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
GA_ROOT = 2
ULONG_PTR = ctypes.c_size_t

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

EnumWindows = user32.EnumWindows
EnumWindows.argtypes = [ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM), wintypes.LPARAM]
EnumWindows.restype = wintypes.BOOL

GetWindowThreadProcessId = user32.GetWindowThreadProcessId
GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
GetWindowThreadProcessId.restype = wintypes.DWORD

IsWindowVisible = user32.IsWindowVisible
IsWindowVisible.argtypes = [wintypes.HWND]
IsWindowVisible.restype = wintypes.BOOL

GetWindowTextLengthW = user32.GetWindowTextLengthW
GetWindowTextLengthW.argtypes = [wintypes.HWND]
GetWindowTextLengthW.restype = ctypes.c_int

GetWindowTextW = user32.GetWindowTextW
GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
GetWindowTextW.restype = ctypes.c_int

GetForegroundWindow = user32.GetForegroundWindow
GetForegroundWindow.argtypes = []
GetForegroundWindow.restype = wintypes.HWND

GetAncestor = user32.GetAncestor
GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
GetAncestor.restype = wintypes.HWND

SendMessageTimeoutW = user32.SendMessageTimeoutW
SendMessageTimeoutW.argtypes = [
    wintypes.HWND,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM,
    wintypes.UINT,
    wintypes.UINT,
    ctypes.POINTER(ULONG_PTR),
]
SendMessageTimeoutW.restype = wintypes.LPARAM

OpenProcess = kernel32.OpenProcess
OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
OpenProcess.restype = wintypes.HANDLE

QueryFullProcessImageNameW = kernel32.QueryFullProcessImageNameW
QueryFullProcessImageNameW.argtypes = [
    wintypes.HANDLE,
    wintypes.DWORD,
    wintypes.LPWSTR,
    ctypes.POINTER(wintypes.DWORD),
]
QueryFullProcessImageNameW.restype = wintypes.BOOL

CloseHandle = kernel32.CloseHandle
CloseHandle.argtypes = [wintypes.HANDLE]
CloseHandle.restype = wintypes.BOOL


def _window_title(hwnd: int) -> str:
    length = GetWindowTextLengthW(hwnd)
    buffer = ctypes.create_unicode_buffer(length + 1)
    GetWindowTextW(hwnd, buffer, len(buffer))
    return buffer.value.strip()


def _process_name(pid: int) -> str:
    handle = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return ""
    try:
        size = wintypes.DWORD(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        if not QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return ""
        return Path(buffer.value).name.lower()
    finally:
        CloseHandle(handle)


def _enumerate_target_windows(process_names: tuple[str, ...]) -> list[tuple[int, int, bool, str]]:
    normalized = {name.strip().lower() for name in process_names if name.strip()}
    if not normalized:
        return []

    targets: list[tuple[int, int, bool, str]] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def callback(hwnd: int, _lparam: int) -> bool:
        root = GetAncestor(hwnd, GA_ROOT)
        if root and int(root) != int(hwnd):
            return True
        pid = wintypes.DWORD()
        GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value:
            return True
        process_name = _process_name(pid.value)
        if process_name not in normalized:
            return True
        title = _window_title(hwnd)
        visible = bool(IsWindowVisible(hwnd))
        if not visible and not title:
            return True
        targets.append((int(hwnd), int(pid.value), visible, title))
        return True

    EnumWindows(callback, 0)
    return targets


def _pick_window(targets: list[tuple[int, int, bool, str]]) -> tuple[int, int, bool, str] | None:
    if not targets:
        return None
    foreground = int(GetForegroundWindow() or 0)
    for target in targets:
        if target[0] == foreground:
            return target
    visible_titled = [target for target in targets if target[2] and target[3]]
    if visible_titled:
        return visible_titled[0]
    titled = [target for target in targets if target[3]]
    if titled:
        return titled[0]
    visible = [target for target in targets if target[2]]
    if visible:
        return visible[0]
    return targets[0]


def send_app_play_pause(process_names: tuple[str, ...], *, label: str) -> bool:
    targets = _enumerate_target_windows(process_names)
    target = _pick_window(targets)
    if target is None:
        print(f"{label} play/pause failed: target window not found.")
        return False

    hwnd, pid, _visible, title = target
    result = ULONG_PTR()
    ok = SendMessageTimeoutW(
        hwnd,
        WM_APPCOMMAND,
        hwnd,
        APPCOMMAND_MEDIA_PLAY_PAUSE << 16,
        SMTO_ABORTIFHUNG,
        1000,
        ctypes.byref(result),
    )
    if not ok:
        print(f"{label} play/pause failed: app command dispatch failed for pid={pid}.")
        return False

    summary = title or "<untitled>"
    print(f"{label} play/pause command sent to pid={pid}, hwnd={hwnd}, title={summary}.")
    return True
