from __future__ import annotations

import queue
from pathlib import Path
from types import SimpleNamespace

import macropad_ble.desktop.autostart as autostart
import macropad_ble.desktop.paths as desktop_paths
import macropad_ble.desktop.single_instance as single_instance
from macropad_ble.ui.window.mixins_desktop import DesktopMixin


class _FakeKey:
    def __init__(self, values: dict[str, str]) -> None:
        self.values = values

    def __enter__(self) -> "_FakeKey":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class _FakeRegistry:
    HKEY_CURRENT_USER = object()
    REG_SZ = 1

    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    def CreateKey(self, _root: object, _path: str) -> _FakeKey:
        return _FakeKey(self.values)

    def OpenKey(self, _root: object, _path: str) -> _FakeKey:
        return _FakeKey(self.values)

    def QueryValueEx(self, key: _FakeKey, name: str) -> tuple[str, int]:
        if name not in key.values:
            raise FileNotFoundError(name)
        return (key.values[name], self.REG_SZ)

    def SetValueEx(self, key: _FakeKey, name: str, _reserved: int, _kind: int, value: str) -> None:
        key.values[name] = value

    def DeleteValue(self, key: _FakeKey, name: str) -> None:
        if name not in key.values:
            raise FileNotFoundError(name)
        del key.values[name]


class _FakeKernel32:
    def __init__(self) -> None:
        self._next_handle = 1
        self._last_error = 0
        self._mutex_names: set[str] = set()
        self._event_state: dict[str, bool] = {}
        self._event_handles: dict[int, str] = {}

    def CreateMutexW(self, _security: object, _initial_owner: bool, name: str) -> int:
        handle = self._next_handle
        self._next_handle += 1
        self._last_error = 0 if name not in self._mutex_names else single_instance.ERROR_ALREADY_EXISTS
        self._mutex_names.add(name)
        return handle

    def GetLastError(self) -> int:
        return self._last_error

    def CreateEventW(self, _security: object, _manual_reset: bool, initial_state: bool, name: str) -> int:
        handle = self._next_handle
        self._next_handle += 1
        self._event_state.setdefault(name, bool(initial_state))
        self._event_handles[handle] = name
        return handle

    def SetEvent(self, handle: int) -> int:
        self._event_state[self._event_handles[handle]] = True
        return 1

    def WaitForSingleObject(self, handle: int, _timeout: int) -> int:
        return 0 if self._event_state[self._event_handles[handle]] else 258

    def ResetEvent(self, handle: int) -> int:
        self._event_state[self._event_handles[handle]] = False
        return 1

    def CloseHandle(self, _handle: int) -> int:
        return 1


class _FakeRoot:
    def __init__(self) -> None:
        self.withdraw_calls = 0
        self.deiconify_calls = 0
        self.iconify_calls = 0
        self.after_calls: list[int] = []

    def after(self, delay: int, callback) -> str:
        self.after_calls.append(delay)
        if callable(callback):
            callback()
        return "after-id"

    def withdraw(self) -> None:
        self.withdraw_calls += 1

    def deiconify(self) -> None:
        self.deiconify_calls += 1

    def iconify(self) -> None:
        self.iconify_calls += 1

    def state(self, _value: str) -> None:
        return None

    def lift(self) -> None:
        return None

    def focus_force(self) -> None:
        return None

    def attributes(self, _name: str, _value: bool) -> None:
        return None


class _FakeDesktop(DesktopMixin):
    def __init__(self) -> None:
        self.root = _FakeRoot()
        self._closing = False
        self._window_hidden = False
        self._tray_available = True
        self._tray_controller = None
        self._instance_guard = None
        self._tray_dispatch_queue: queue.SimpleQueue[object] = queue.SimpleQueue()
        self._autostart_command = ["MacroPad Controller.exe", "--hidden"]
        self.logs: list[str] = []
        self.exit_prepared = False

    def _log(self, message: str) -> None:
        self.logs.append(message)

    def _prepare_exit(self) -> None:
        self.exit_prepared = True
        self._closing = True

    def _spawn(self, _coro) -> None:
        return None


def test_resolve_app_paths_uses_appdata_on_windows(tmp_path: Path) -> None:
    paths = desktop_paths.resolve_app_paths(
        cwd=tmp_path,
        system="Windows",
        env={"APPDATA": str(tmp_path / "Roaming")},
        home=tmp_path,
    )

    assert paths.data_root == tmp_path / "Roaming" / "macropad-ble"
    assert paths.profile_dir == paths.data_root / "profiles"
    assert paths.state_path == paths.data_root / "app_state.json"


def test_migrate_legacy_app_data_copies_profiles_and_state(tmp_path: Path) -> None:
    legacy_dir = tmp_path / "profiles"
    legacy_dir.mkdir()
    (legacy_dir / "profile_01.json").write_text("{}", encoding="utf-8")
    (legacy_dir / "runtime_python").mkdir()
    (legacy_dir / "runtime_python" / "all_keys.py").write_text("print('ok')\n", encoding="utf-8")
    (legacy_dir / "app_state.json").write_text('{"last_port":"COM13"}', encoding="utf-8")

    paths = desktop_paths.resolve_app_paths(
        cwd=tmp_path,
        system="Windows",
        env={"APPDATA": str(tmp_path / "Roaming")},
        home=tmp_path,
    )

    assert desktop_paths.migrate_legacy_app_data(paths) is True
    assert (paths.profile_dir / "profile_01.json").exists()
    assert (paths.profile_dir / "runtime_python" / "all_keys.py").exists()
    assert paths.state_path.read_text(encoding="utf-8") == '{"last_port":"COM13"}'


def test_autostart_registry_enable_disable_round_trip() -> None:
    registry = _FakeRegistry()
    command = ["C:\\Apps\\MacroPad Controller.exe", "--hidden"]

    assert autostart.is_autostart_enabled(registry_module=registry) is False
    assert autostart.set_autostart_enabled(True, command=command, registry_module=registry) is True
    assert autostart.get_autostart_command(registry_module=registry) == '"C:\\Apps\\MacroPad Controller.exe" --hidden'
    assert autostart.is_autostart_enabled(registry_module=registry) is True
    assert autostart.set_autostart_enabled(False, command=command, registry_module=registry) is False
    assert autostart.is_autostart_enabled(registry_module=registry) is False


def test_single_instance_secondary_launch_signals_restore(monkeypatch) -> None:
    kernel32 = _FakeKernel32()
    monkeypatch.setattr(single_instance.sys, "platform", "win32")

    primary = single_instance.SingleInstanceGuard("MacroPadController", kernel32=kernel32)
    secondary = single_instance.SingleInstanceGuard("MacroPadController", kernel32=kernel32)

    assert primary.acquire() is True
    assert secondary.acquire() is False
    assert secondary.signal_restore() is True
    assert primary.consume_restore_signal() is True
    assert primary.consume_restore_signal() is False


def test_close_hides_window_instead_of_exiting() -> None:
    desktop = _FakeDesktop()
    desktop._on_window_close()

    assert desktop.root.withdraw_calls == 1
    assert desktop.exit_prepared is False
    assert desktop._closing is False


def test_request_exit_prepares_shutdown() -> None:
    desktop = _FakeDesktop()
    desktop._request_exit()

    assert desktop.exit_prepared is True
    assert desktop._closing is True


def test_restore_signal_brings_window_back(monkeypatch) -> None:
    desktop = _FakeDesktop()
    desktop._window_hidden = True
    desktop._instance_guard = SimpleNamespace(consume_restore_signal=lambda: True)

    desktop._poll_desktop_events()

    assert desktop.root.deiconify_calls == 1
    assert desktop._window_hidden is False


def test_tray_dispatch_queue_runs_callbacks_on_poll() -> None:
    desktop = _FakeDesktop()
    called: list[str] = []

    desktop._enqueue_tray_callback(lambda: called.append("done"))
    desktop._poll_desktop_events()

    assert called == ["done"]
