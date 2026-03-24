from __future__ import annotations

from macropad.core.window_control import (
    WINDOW_CONTROL_MODE_APPS,
    WINDOW_CONTROL_MODE_MONITOR,
    WindowBackend,
    WindowControlState,
    WindowInfo,
    execute_window_control,
    format_window_control_value,
    parse_window_control_value,
)


class _FakeBackend(WindowBackend):
    def __init__(self, windows: list[WindowInfo]) -> None:
        self.windows = [_clone_window(window) for window in windows]
        self.minimized: list[int] = []
        self.focused: list[int] = []

    def list_windows(self) -> list[WindowInfo]:
        return [_clone_window(window) for window in self.windows]

    def minimize(self, handle: int) -> None:
        self.minimized.append(int(handle))
        for window in self.windows:
            if window.handle == handle:
                window.minimized = True

    def restore_and_focus(self, handle: int) -> None:
        self.focused.append(int(handle))
        for window in self.windows:
            if window.handle == handle:
                window.minimized = False


def _clone_window(window: WindowInfo) -> WindowInfo:
    return WindowInfo(
        handle=int(window.handle),
        app=str(window.app),
        title=str(window.title),
        monitor=int(window.monitor),
        minimized=bool(window.minimized),
    )


def test_window_control_parse_format_round_trip() -> None:
    spec = parse_window_control_value("mode=apps;monitor=2;targets=spotify.exe|chrome.exe|spotify.exe")
    assert spec.mode == WINDOW_CONTROL_MODE_APPS
    assert spec.monitor == 2
    assert spec.targets == ("spotify.exe", "chrome.exe")
    assert format_window_control_value(spec) == "mode=apps;monitor=2;targets=spotify.exe|chrome.exe"

    monitor_spec = parse_window_control_value("mode=monitor;monitor=3")
    assert monitor_spec.mode == WINDOW_CONTROL_MODE_MONITOR
    assert monitor_spec.monitor == 3
    assert format_window_control_value(monitor_spec) == "mode=monitor;monitor=3"


def test_window_control_apps_mode_round_robins_targets() -> None:
    backend = _FakeBackend(
        [
            WindowInfo(handle=11, app="spotify.exe", title="Spotify", monitor=1, minimized=False),
            WindowInfo(handle=12, app="chrome.exe", title="Chrome", monitor=1, minimized=False),
            WindowInfo(handle=13, app="discord.exe", title="Discord", monitor=1, minimized=False),
        ]
    )
    state = WindowControlState()
    logs: list[str] = []

    first = execute_window_control(
        "mode=apps;monitor=1;targets=spotify.exe|chrome.exe",
        log=logs.append,
        backend=backend,
        state=state,
    )
    assert first.focused_app == "spotify.exe"
    assert backend.focused[-1] == 11
    assert sorted(backend.minimized[-2:]) == [12, 13]

    second = execute_window_control(
        "mode=apps;monitor=1;targets=spotify.exe|chrome.exe",
        log=logs.append,
        backend=backend,
        state=state,
    )
    assert second.focused_app == "chrome.exe"
    assert backend.focused[-1] == 12
    assert sorted(backend.minimized[-2:]) == [11, 13]
    assert any("monitor 1 -> spotify.exe" in line for line in logs)
    assert any("monitor 1 -> chrome.exe" in line for line in logs)


def test_window_control_monitor_mode_cycles_windows() -> None:
    backend = _FakeBackend(
        [
            WindowInfo(handle=21, app="opera.exe", title="Opera", monitor=2, minimized=False),
            WindowInfo(handle=22, app="spotify.exe", title="Spotify", monitor=2, minimized=False),
            WindowInfo(handle=23, app="code.exe", title="VS Code", monitor=2, minimized=False),
        ]
    )
    state = WindowControlState()
    logs: list[str] = []

    first = execute_window_control("mode=monitor;monitor=2", log=logs.append, backend=backend, state=state)
    second = execute_window_control("mode=monitor;monitor=2", log=logs.append, backend=backend, state=state)

    assert first.focused_handle == 23
    assert second.focused_handle == 21
    assert any("Window control: monitor 2" in line for line in logs)
