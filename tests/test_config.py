from __future__ import annotations

from pathlib import Path

import pytest

from macropad.config import default_user_config_path, load_settings


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_defaults_without_config(tmp_path: Path) -> None:
    settings = load_settings(cwd=tmp_path, system="Linux", env={}, home=tmp_path)
    assert settings.port is None
    assert settings.hint is None
    assert settings.baud == 115200
    assert settings.ack_timeout == 0.75
    assert settings.dedupe_ms == 100
    assert settings.log_level == "INFO"


def test_project_config_preferred_over_user_config(tmp_path: Path) -> None:
    project_config = tmp_path / "macropad.toml"
    user_root = tmp_path / "user-config"
    user_config = user_root / "macropad" / "config.toml"

    _write(project_config, 'hint = "ProjectBoard"\n')
    _write(user_config, 'hint = "UserBoard"\n')

    settings = load_settings(
        cwd=tmp_path,
        system="Linux",
        env={"XDG_CONFIG_HOME": str(user_root)},
        home=tmp_path,
    )
    assert settings.hint == "ProjectBoard"


def test_cli_overrides_take_precedence(tmp_path: Path) -> None:
    config = tmp_path / "macropad.toml"
    _write(
        config,
        "\n".join(
            [
                'hint = "FromFile"',
                "baud = 115200",
                'log_level = "DEBUG"',
            ]
        ),
    )

    settings = load_settings(
        cwd=tmp_path,
        config_path=config,
        cli_overrides={"baud": 9600, "log_level": "INFO", "port": "COM12"},
    )
    assert settings.port == "COM12"
    assert settings.baud == 9600
    assert settings.log_level == "INFO"


def test_explicit_missing_config_raises(tmp_path: Path) -> None:
    missing = tmp_path / "missing.toml"
    with pytest.raises(FileNotFoundError):
        load_settings(config_path=missing, cwd=tmp_path)


def test_windows_user_config_path_uses_appdata() -> None:
    path = default_user_config_path(
        system="Windows",
        env={"APPDATA": r"C:\Users\Test\AppData\Roaming"},
        home=Path(r"C:\Users\Test"),
    )
    expected = Path(r"C:\Users\Test\AppData\Roaming") / "macropad" / "config.toml"
    assert path == expected


def test_legacy_project_config_is_used_when_new_name_is_missing(tmp_path: Path) -> None:
    config = tmp_path / "macropad-ble.toml"
    _write(config, 'hint = "LegacyProject"\n')

    settings = load_settings(cwd=tmp_path, system="Linux", env={}, home=tmp_path)

    assert settings.hint == "LegacyProject"


def test_legacy_user_config_is_used_when_new_name_is_missing(tmp_path: Path) -> None:
    user_root = tmp_path / "user-config"
    legacy_user_config = user_root / "macropad-ble" / "config.toml"
    _write(legacy_user_config, 'hint = "LegacyUser"\n')

    settings = load_settings(
        cwd=tmp_path,
        system="Linux",
        env={"XDG_CONFIG_HOME": str(user_root)},
        home=tmp_path,
    )

    assert settings.hint == "LegacyUser"


def test_invalid_log_level_rejected(tmp_path: Path) -> None:
    config = tmp_path / "macropad.toml"
    _write(config, 'log_level = "LOUD"\n')
    with pytest.raises(ValueError):
        load_settings(config_path=config, cwd=tmp_path)


def test_invalid_dedupe_window_rejected(tmp_path: Path) -> None:
    config = tmp_path / "macropad.toml"
    _write(config, "dedupe_ms = 25\n")
    with pytest.raises(ValueError):
        load_settings(config_path=config, cwd=tmp_path)
