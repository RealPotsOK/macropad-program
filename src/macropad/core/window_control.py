from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass, field
import logging
import sys
from typing import Callable, Iterable

import psutil

LOGGER = logging.getLogger(__name__)

WINDOW_CONTROL_MODE_APPS = "apps"
WINDOW_CONTROL_MODE_MONITOR = "monitor"

SW_MINIMIZE = 6
SW_SHOW = 5
SW_RESTORE = 9
SW_FORCEMINIMIZE = 11


class WindowControlError(RuntimeError):
    pass


@dataclass(slots=True)
class WindowControlSpec:
    mode: str = WINDOW_CONTROL_MODE_APPS
    monitor: int = 1
    targets: tuple[str, ...] = ()


@dataclass(slots=True)
class WindowInfo:
    handle: int
    app: str
    title: str
    monitor: int
    minimized: bool


@dataclass(slots=True)
class WindowControlResult:
    mode: str
    monitor: int
    focused_handle: int | None = None
    focused_app: str = ""
    minimized_count: int = 0
    candidates: int = 0


@dataclass(slots=True)
class WindowControlState:
    cursors: dict[str, int] = field(default_factory=dict)

    def next_index(self, key: str, count: int) -> int:
        if count <= 0:
            return 0
        current = int(self.cursors.get(key, 0)) % count
        self.cursors[key] = (current + 1) % count
        return current


class WindowBackend:
    def list_windows(self) -> list[WindowInfo]:
        raise NotImplementedError

    def minimize(self, handle: int) -> None:
        raise NotImplementedError

    def restore_and_focus(self, handle: int) -> None:
        raise NotImplementedError


def parse_window_control_value(raw_value: str) -> WindowControlSpec:
    mode = WINDOW_CONTROL_MODE_APPS
    monitor = 1
    targets: list[str] = []
    value = str(raw_value or "").strip()
    if not value:
        return WindowControlSpec(mode=mode, monitor=monitor, targets=tuple(targets))

    if "=" not in value and ":" not in value and ";" not in value and "|" not in value:
        token = value.strip().lower()
        if token:
            targets.append(token)
        return WindowControlSpec(mode=mode, monitor=monitor, targets=tuple(targets))

    for token in [part.strip() for part in value.split(";") if part.strip()]:
        key = ""
        raw = ""
        if "=" in token:
            key, raw = token.split("=", 1)
        elif ":" in token:
            key, raw = token.split(":", 1)
        key = key.strip().lower()
        raw = raw.strip()
        if key in {"mode", "action"}:
            normalized = raw.lower()
            if normalized in {WINDOW_CONTROL_MODE_APPS, WINDOW_CONTROL_MODE_MONITOR}:
                mode = normalized
        elif key in {"monitor", "screen", "display"}:
            try:
                monitor = max(1, int(raw))
            except ValueError:
                monitor = 1
        elif key in {"targets", "apps", "target"}:
            candidates = [item.strip().lower() for item in raw.split("|") if item.strip()]
            targets.extend(candidates)

    normalized_targets: list[str] = []
    seen_targets: set[str] = set()
    for target in targets:
        if target in seen_targets:
            continue
        seen_targets.add(target)
        normalized_targets.append(target)
    return WindowControlSpec(
        mode=mode,
        monitor=max(1, int(monitor)),
        targets=tuple(normalized_targets),
    )


def format_window_control_value(spec: WindowControlSpec) -> str:
    mode = spec.mode if spec.mode in {WINDOW_CONTROL_MODE_APPS, WINDOW_CONTROL_MODE_MONITOR} else WINDOW_CONTROL_MODE_APPS
    monitor = max(1, int(spec.monitor))
    if mode == WINDOW_CONTROL_MODE_MONITOR:
        return f"mode=monitor;monitor={monitor}"
    targets: list[str] = []
    seen: set[str] = set()
    for item in spec.targets:
        token = str(item or "").strip().lower()
        if not token or token in seen:
            continue
        seen.add(token)
        targets.append(token)
    return f"mode=apps;monitor={monitor};targets={'|'.join(targets)}"


def list_window_control_windows(
    *,
    backend: WindowBackend | None = None,
) -> list[WindowInfo]:
    active_backend = backend or create_window_backend()
    windows = active_backend.list_windows()
    windows.sort(key=lambda item: (item.monitor, item.app.lower(), item.title.lower(), item.handle))
    return windows


def execute_window_control(
    raw_value: str,
    *,
    log: Callable[[str], None],
    backend: WindowBackend | None = None,
    state: WindowControlState | None = None,
) -> WindowControlResult:
    spec = parse_window_control_value(raw_value)
    active_backend = backend or create_window_backend()
    active_state = state or _WINDOW_CONTROL_STATE
    windows = [item for item in active_backend.list_windows() if item.monitor == spec.monitor]

    if spec.mode == WINDOW_CONTROL_MODE_MONITOR:
        return _execute_monitor_mode(spec, windows, backend=active_backend, state=active_state, log=log)

    return _execute_apps_mode(spec, windows, backend=active_backend, state=active_state, log=log)


def _execute_apps_mode(
    spec: WindowControlSpec,
    windows: list[WindowInfo],
    *,
    backend: WindowBackend,
    state: WindowControlState,
    log: Callable[[str], None],
) -> WindowControlResult:
    if not spec.targets:
        raise WindowControlError("window_control apps mode requires at least one target app.")

    grouped: dict[str, list[WindowInfo]] = {}
    for item in windows:
        key = item.app.strip().lower()
        if not key:
            continue
        grouped.setdefault(key, []).append(item)

    available_targets = [target for target in spec.targets if grouped.get(target)]
    if not available_targets:
        log(f"Window control: no matching app windows on monitor {spec.monitor}.")
        return WindowControlResult(mode=spec.mode, monitor=spec.monitor, candidates=0)

    cursor_key = f"apps:{spec.monitor}:{'|'.join(spec.targets)}"
    start = state.next_index(cursor_key, max(1, len(spec.targets)))
    selected_target: str | None = None
    selected_index = start
    for offset in range(len(spec.targets)):
        idx = (start + offset) % len(spec.targets)
        candidate = spec.targets[idx]
        if candidate in available_targets:
            selected_target = candidate
            selected_index = idx
            break

    if selected_target is None:
        log(f"Window control: no available target app on monitor {spec.monitor}.")
        return WindowControlResult(mode=spec.mode, monitor=spec.monitor, candidates=0)

    state.cursors[cursor_key] = (selected_index + 1) % max(1, len(spec.targets))
    selected_windows = grouped.get(selected_target, [])
    chosen_window = _pick_focus_window(selected_windows)
    chosen_handle = chosen_window.handle if chosen_window is not None else None
    minimized_count = 0
    for item in windows:
        if chosen_handle is not None and item.handle == chosen_handle:
            continue
        _safe_call(lambda handle=item.handle: backend.minimize(handle))
        minimized_count += 1
    _restore_window(chosen_window, backend=backend)
    log(
        f"Window control: monitor {spec.monitor} -> {selected_target} "
        f"(minimized {minimized_count} window{'s' if minimized_count != 1 else ''})."
    )
    return WindowControlResult(
        mode=spec.mode,
        monitor=spec.monitor,
        focused_handle=chosen_window.handle if chosen_window is not None else None,
        focused_app=selected_target,
        minimized_count=minimized_count,
        candidates=len(windows),
    )


def _execute_monitor_mode(
    spec: WindowControlSpec,
    windows: list[WindowInfo],
    *,
    backend: WindowBackend,
    state: WindowControlState,
    log: Callable[[str], None],
) -> WindowControlResult:
    if not windows:
        log(f"Window control: no windows on monitor {spec.monitor}.")
        return WindowControlResult(mode=spec.mode, monitor=spec.monitor, candidates=0)

    ordered = sorted(windows, key=lambda item: (item.app.lower(), item.title.lower(), item.handle))
    cursor_key = f"monitor:{spec.monitor}"
    selected_index = state.next_index(cursor_key, len(ordered))
    chosen = ordered[selected_index]
    minimized_count = 0
    for item in ordered:
        if item.handle == chosen.handle:
            continue
        _safe_call(lambda handle=item.handle: backend.minimize(handle))
        minimized_count += 1
    _restore_window(chosen, backend=backend)
    label = chosen.app or chosen.title or f"0x{chosen.handle:X}"
    log(
        f"Window control: monitor {spec.monitor} -> {label} "
        f"(minimized {minimized_count} window{'s' if minimized_count != 1 else ''})."
    )
    return WindowControlResult(
        mode=spec.mode,
        monitor=spec.monitor,
        focused_handle=chosen.handle,
        focused_app=chosen.app,
        minimized_count=minimized_count,
        candidates=len(ordered),
    )


def _pick_focus_window(windows: list[WindowInfo]) -> WindowInfo | None:
    if not windows:
        return None
    for item in windows:
        if not item.minimized:
            return item
    return windows[0]


def _restore_window(window: WindowInfo | None, *, backend: WindowBackend) -> None:
    if window is None:
        return
    _safe_call(lambda handle=window.handle: backend.restore_and_focus(handle))


def _safe_call(callback: Callable[[], None]) -> None:
    try:
        callback()
    except Exception:
        LOGGER.exception("Window control backend call failed.")


class Win32WindowBackend(WindowBackend):
    def __init__(self) -> None:
        if sys.platform != "win32":
            raise WindowControlError("window_control is only supported on Windows.")

        self._user32 = ctypes.windll.user32
        self._kernel32 = ctypes.windll.kernel32
        self._monitor_index = self._build_monitor_index()

    def list_windows(self) -> list[WindowInfo]:
        handles: list[int] = []

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def _enum_callback(hwnd: int, lparam: int) -> bool:
            if not self._is_candidate_window(hwnd):
                return True
            handles.append(int(hwnd))
            return True

        self._user32.EnumWindows(_enum_callback, 0)
        windows: list[WindowInfo] = []
        for handle in handles:
            title = self._window_title(handle)
            if not title:
                continue
            monitor = self._monitor_for_window(handle)
            app = self._process_name_for_window(handle)
            minimized = bool(self._user32.IsIconic(wintypes.HWND(handle)))
            windows.append(
                WindowInfo(
                    handle=handle,
                    app=app.lower(),
                    title=title,
                    monitor=monitor,
                    minimized=minimized,
                )
            )
        return windows

    def minimize(self, handle: int) -> None:
        hwnd = wintypes.HWND(handle)
        self._show_window(hwnd, SW_MINIMIZE)
        if not bool(self._user32.IsIconic(hwnd)):
            self._show_window(hwnd, SW_FORCEMINIMIZE)

    def restore_and_focus(self, handle: int) -> None:
        hwnd = wintypes.HWND(handle)
        if bool(self._user32.IsIconic(hwnd)):
            self._show_window(hwnd, SW_RESTORE)
        else:
            # Keep maximized/fullscreen windows in their current state.
            self._show_window(hwnd, SW_SHOW)
        self._user32.BringWindowToTop(hwnd)
        self._user32.SetForegroundWindow(hwnd)

    def _is_candidate_window(self, handle: int) -> bool:
        hwnd = wintypes.HWND(handle)
        visible = bool(self._user32.IsWindowVisible(hwnd))
        iconic = bool(self._user32.IsIconic(hwnd))
        if not visible and not iconic:
            return False
        if self._user32.GetWindowTextLengthW(hwnd) <= 0:
            return False
        return True

    def _window_title(self, handle: int) -> str:
        hwnd = wintypes.HWND(handle)
        length = int(self._user32.GetWindowTextLengthW(hwnd))
        if length <= 0:
            return ""
        buffer = ctypes.create_unicode_buffer(length + 1)
        self._user32.GetWindowTextW(hwnd, buffer, length + 1)
        return str(buffer.value or "").strip()

    def _process_name_for_window(self, handle: int) -> str:
        process_id = wintypes.DWORD()
        self._user32.GetWindowThreadProcessId(wintypes.HWND(handle), ctypes.byref(process_id))
        pid = int(process_id.value)
        if pid <= 0:
            return ""
        try:
            return str(psutil.Process(pid).name() or "").strip().lower()
        except Exception:
            return ""

    def _monitor_for_window(self, handle: int) -> int:
        monitor_handle = self._user32.MonitorFromWindow(wintypes.HWND(handle), wintypes.DWORD(2))
        if not monitor_handle:
            return 1
        return int(self._monitor_index.get(int(monitor_handle), 1))

    def _build_monitor_index(self) -> dict[int, int]:
        monitor_handles: list[int] = []

        @ctypes.WINFUNCTYPE(
            wintypes.BOOL,
            wintypes.HMONITOR,
            wintypes.HDC,
            ctypes.POINTER(wintypes.RECT),
            wintypes.LPARAM,
        )
        def _monitor_callback(hmonitor, hdc, lprect, lparam):  # type: ignore[no-untyped-def]
            monitor_handles.append(int(hmonitor))
            return True

        self._user32.EnumDisplayMonitors(0, 0, _monitor_callback, 0)
        if not monitor_handles:
            return {}
        return {handle: index + 1 for index, handle in enumerate(monitor_handles)}

    def _show_window(self, hwnd: wintypes.HWND, command: int) -> None:
        try:
            show_async = getattr(self._user32, "ShowWindowAsync", None)
            if callable(show_async):
                show_async(hwnd, int(command))
                return
        except Exception:
            pass
        self._user32.ShowWindow(hwnd, int(command))


def create_window_backend() -> WindowBackend:
    return Win32WindowBackend()


_WINDOW_CONTROL_STATE = WindowControlState()
