from __future__ import annotations

import os
import platform
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

APP_DATA_DIRNAME = "macropad-ble"
LEGACY_PROFILE_DIRNAME = "profiles"
APP_STATE_FILENAME = "app_state.json"


@dataclass(frozen=True, slots=True)
class AppPaths:
    data_root: Path
    profile_dir: Path
    state_path: Path
    legacy_profile_dir: Path
    legacy_state_path: Path


def _platform_data_root(
    *,
    system: str | None = None,
    env: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> Path:
    system_name = system or platform.system()
    env_map = dict(env or os.environ)
    home_dir = home or Path.home()

    if system_name == "Windows":
        appdata = env_map.get("APPDATA")
        if appdata:
            return Path(appdata) / APP_DATA_DIRNAME
        return home_dir / "AppData" / "Roaming" / APP_DATA_DIRNAME

    if system_name == "Darwin":
        return home_dir / "Library" / "Application Support" / APP_DATA_DIRNAME

    xdg_config_home = env_map.get("XDG_CONFIG_HOME")
    if xdg_config_home:
        return Path(xdg_config_home) / APP_DATA_DIRNAME
    return home_dir / ".config" / APP_DATA_DIRNAME


def resolve_app_paths(
    *,
    cwd: Path | None = None,
    system: str | None = None,
    env: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> AppPaths:
    current_dir = cwd or Path.cwd()
    data_root = _platform_data_root(system=system, env=env, home=home)
    return AppPaths(
        data_root=data_root,
        profile_dir=data_root / LEGACY_PROFILE_DIRNAME,
        state_path=data_root / APP_STATE_FILENAME,
        legacy_profile_dir=current_dir / LEGACY_PROFILE_DIRNAME,
        legacy_state_path=current_dir / LEGACY_PROFILE_DIRNAME / APP_STATE_FILENAME,
    )


def _has_existing_app_data(paths: AppPaths) -> bool:
    if paths.state_path.exists():
        return True
    if not paths.profile_dir.exists():
        return False
    return any(paths.profile_dir.iterdir())


def _copy_item(source: Path, target: Path) -> None:
    if source.is_dir():
        shutil.copytree(source, target, dirs_exist_ok=True)
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def migrate_legacy_app_data(paths: AppPaths) -> bool:
    if _has_existing_app_data(paths):
        return False
    if not paths.legacy_profile_dir.exists():
        return False

    migrated = False
    paths.profile_dir.mkdir(parents=True, exist_ok=True)
    for source in paths.legacy_profile_dir.iterdir():
        if source.name == APP_STATE_FILENAME:
            continue
        _copy_item(source, paths.profile_dir / source.name)
        migrated = True

    if paths.legacy_state_path.exists() and not paths.state_path.exists():
        paths.state_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(paths.legacy_state_path, paths.state_path)
        migrated = True

    return migrated


def sync_packaged_runtime_assets(paths: AppPaths) -> int:
    source_root = paths.legacy_profile_dir
    target_root = paths.profile_dir
    if not source_root.exists():
        return 0

    updated = 0
    for dirname in ("runtime_python", "runtime_ahk"):
        source_dir = source_root / dirname
        if not source_dir.exists():
            continue

        for source in source_dir.iterdir():
            if source.is_dir():
                continue
            name = source.name.lower()
            if name.startswith("all_keys."):
                continue
            if name.startswith("key_"):
                continue
            if name.startswith("profile_"):
                continue

            target = target_root / dirname / source.name
            if target.exists():
                try:
                    if target.stat().st_mtime >= source.stat().st_mtime:
                        continue
                except OSError:
                    pass
            _copy_item(source, target)
            updated += 1

    return updated
