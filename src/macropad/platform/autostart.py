from __future__ import annotations

import subprocess
import sys
from typing import Sequence

AUTOSTART_VALUE_NAME = "MacroPad Controller"
RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"


def _registry_module(module: object | None = None) -> object | None:
    if module is not None:
        return module
    if sys.platform != "win32":
        return None
    try:
        import winreg
    except Exception:
        return None
    return winreg


def build_autostart_command(command: Sequence[str]) -> str:
    values = [str(part) for part in command if str(part).strip()]
    if not values:
        raise ValueError("Autostart command must contain at least one token.")
    return subprocess.list2cmdline(values)


def get_autostart_command(
    *,
    value_name: str = AUTOSTART_VALUE_NAME,
    registry_module: object | None = None,
) -> str | None:
    registry = _registry_module(registry_module)
    if registry is None:
        return None

    try:
        with registry.OpenKey(registry.HKEY_CURRENT_USER, RUN_KEY_PATH) as handle:
            value, _kind = registry.QueryValueEx(handle, value_name)
    except FileNotFoundError:
        return None
    return str(value or "").strip() or None


def is_autostart_enabled(
    *,
    value_name: str = AUTOSTART_VALUE_NAME,
    registry_module: object | None = None,
) -> bool:
    return get_autostart_command(value_name=value_name, registry_module=registry_module) is not None


def set_autostart_enabled(
    enabled: bool,
    *,
    command: Sequence[str],
    value_name: str = AUTOSTART_VALUE_NAME,
    registry_module: object | None = None,
) -> bool:
    registry = _registry_module(registry_module)
    if registry is None:
        return False

    with registry.CreateKey(registry.HKEY_CURRENT_USER, RUN_KEY_PATH) as handle:
        if enabled:
            registry.SetValueEx(
                handle,
                value_name,
                0,
                registry.REG_SZ,
                build_autostart_command(command),
            )
            return True
        try:
            registry.DeleteValue(handle, value_name)
        except FileNotFoundError:
            pass
    return False
