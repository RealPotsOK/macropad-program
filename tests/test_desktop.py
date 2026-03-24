from __future__ import annotations

from pathlib import Path

import macropad.platform.autostart as autostart
import macropad.platform.paths as desktop_paths
import macropad.platform.single_instance as single_instance


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


def test_resolve_app_paths_uses_appdata_on_windows(tmp_path: Path) -> None:
    paths = desktop_paths.resolve_app_paths(
        cwd=tmp_path,
        system="Windows",
        env={"APPDATA": str(tmp_path / "Roaming")},
        home=tmp_path,
    )

    assert paths.data_root == tmp_path / "Roaming" / "macropad"
    assert paths.profile_dir == paths.data_root / "profiles"
    assert paths.state_path == paths.data_root / "app_state.json"
    assert paths.legacy_appdata_root == tmp_path / "Roaming" / "macropad-ble"


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


def test_migrate_legacy_appdata_root_copies_profiles_and_state(tmp_path: Path) -> None:
    legacy_root = tmp_path / "Roaming" / "macropad-ble"
    legacy_profiles = legacy_root / "profiles"
    legacy_profiles.mkdir(parents=True)
    (legacy_profiles / "profile_01.json").write_text("{}", encoding="utf-8")
    (legacy_profiles / "runtime_ahk").mkdir()
    (legacy_profiles / "runtime_ahk" / "all_keys.ahk").write_text("; ok\n", encoding="utf-8")
    (legacy_root / "app_state.json").write_text('{"last_port":"COM14"}', encoding="utf-8")

    paths = desktop_paths.resolve_app_paths(
        cwd=tmp_path,
        system="Windows",
        env={"APPDATA": str(tmp_path / "Roaming")},
        home=tmp_path,
    )

    assert desktop_paths.migrate_legacy_app_data(paths) is True
    assert (paths.profile_dir / "profile_01.json").exists()
    assert (paths.profile_dir / "runtime_ahk" / "all_keys.ahk").exists()
    assert paths.state_path.read_text(encoding="utf-8") == '{"last_port":"COM14"}'


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
