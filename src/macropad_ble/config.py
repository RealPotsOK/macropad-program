from __future__ import annotations

import platform
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

import tomllib

LOG_LEVELS = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"}
CONFIG_FILENAME = "macropad-ble.toml"
APP_CONFIG_FILENAME = "config.toml"
APP_CONFIG_DIRNAME = "macropad-ble"

ALLOWED_KEYS = {
    "port",
    "hint",
    "baud",
    "ack_timeout",
    "dedupe_ms",
    "log_level",
}


@dataclass(frozen=True, slots=True)
class Settings:
    port: str | None = None
    hint: str | None = None
    baud: int = 9600
    ack_timeout: float = 0.75
    dedupe_ms: int = 100
    log_level: str = "INFO"


DEFAULT_SETTINGS = Settings()


def _normalize_optional_string(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    if not normalized:
        return None
    if any(char in normalized for char in ("\n", "\r", "\t")):
        raise ValueError(f"{field_name} must not contain control whitespace.")
    return normalized


def _validate_log_level(value: Any) -> str:
    level = str(value).upper().strip()
    if level not in LOG_LEVELS:
        raise ValueError(f"log_level must be one of {sorted(LOG_LEVELS)}.")
    return level


def _validate_positive_float(value: Any, field_name: str) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a number.") from exc
    if numeric <= 0:
        raise ValueError(f"{field_name} must be > 0.")
    return numeric


def _validate_positive_int(value: Any, field_name: str) -> int:
    try:
        numeric = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be an integer.") from exc
    if numeric <= 0:
        raise ValueError(f"{field_name} must be > 0.")
    return numeric


def _validate_dedupe_ms(value: Any) -> int:
    dedupe_ms = int(value)
    if dedupe_ms == 0:
        return 0
    if dedupe_ms < 50 or dedupe_ms > 150:
        raise ValueError("dedupe_ms must be 0 or between 50 and 150.")
    return dedupe_ms


def default_user_config_path(
    *,
    system: str | None = None,
    env: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> Path:
    env = dict(env or {})
    system = system or platform.system()
    home = home or Path.home()

    if system == "Windows":
        appdata = env.get("APPDATA")
        if appdata:
            return Path(appdata) / APP_CONFIG_DIRNAME / APP_CONFIG_FILENAME
        return home / "AppData" / "Roaming" / APP_CONFIG_DIRNAME / APP_CONFIG_FILENAME

    if system == "Darwin":
        return (
            home
            / "Library"
            / "Application Support"
            / APP_CONFIG_DIRNAME
            / APP_CONFIG_FILENAME
        )

    xdg = env.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / APP_CONFIG_DIRNAME / APP_CONFIG_FILENAME
    return home / ".config" / APP_CONFIG_DIRNAME / APP_CONFIG_FILENAME


def discover_config_path(
    *,
    explicit_path: Path | None,
    cwd: Path | None = None,
    system: str | None = None,
    env: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> Path | None:
    if explicit_path is not None:
        return explicit_path

    cwd = cwd or Path.cwd()
    project_path = cwd / CONFIG_FILENAME
    user_path = default_user_config_path(system=system, env=env, home=home)

    for candidate in (project_path, user_path):
        if candidate.exists():
            return candidate
    return None


def _read_config_file(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        raw = tomllib.load(handle)
    if not isinstance(raw, dict):
        raise ValueError("Config file must contain a TOML table at the root.")
    unknown = sorted(set(raw.keys()) - ALLOWED_KEYS)
    if unknown:
        raise ValueError(f"Unknown config key(s): {', '.join(unknown)}")
    return dict(raw)


def _normalize_settings(raw: Mapping[str, Any]) -> Settings:
    return Settings(
        port=_normalize_optional_string(raw.get("port", DEFAULT_SETTINGS.port), "port"),
        hint=_normalize_optional_string(raw.get("hint", DEFAULT_SETTINGS.hint), "hint"),
        baud=_validate_positive_int(raw.get("baud", DEFAULT_SETTINGS.baud), "baud"),
        ack_timeout=_validate_positive_float(
            raw.get("ack_timeout", DEFAULT_SETTINGS.ack_timeout), "ack_timeout"
        ),
        dedupe_ms=_validate_dedupe_ms(raw.get("dedupe_ms", DEFAULT_SETTINGS.dedupe_ms)),
        log_level=_validate_log_level(raw.get("log_level", DEFAULT_SETTINGS.log_level)),
    )


def load_settings(
    *,
    config_path: Path | None = None,
    cli_overrides: Mapping[str, Any] | None = None,
    cwd: Path | None = None,
    system: str | None = None,
    env: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> Settings:
    selected_path = discover_config_path(
        explicit_path=config_path, cwd=cwd, system=system, env=env, home=home
    )

    if config_path is not None and selected_path is not None and not selected_path.exists():
        raise FileNotFoundError(f"Config file not found: {selected_path}")

    merged = asdict(DEFAULT_SETTINGS)

    if selected_path is not None and selected_path.exists():
        merged.update(_read_config_file(selected_path))

    if cli_overrides:
        filtered = {k: v for k, v in cli_overrides.items() if v is not None}
        unknown = sorted(set(filtered.keys()) - ALLOWED_KEYS)
        if unknown:
            raise ValueError(f"Unknown CLI override key(s): {', '.join(unknown)}")
        merged.update(filtered)

    return _normalize_settings(merged)
