from __future__ import annotations

import asyncio
import contextlib
import io
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
from dataclasses import dataclass
import re
from typing import Callable

from ..desktop import resolve_app_paths
from .key_names import normalize_key_sequence
from .profile import ACTION_NONE, KeyAction
from .volume_mixer import VolumeMixerError, VolumeMixerResult, change_volume_mixer_volume

ACTION_AHK = "ahk"
ACTION_PYTHON = "python"
ACTION_FILE = "file"
ACTION_KEYBOARD = "keyboard"
ACTION_SEND_KEYS = "send_keys"
ACTION_MACRO = "macro"
ACTION_VOLUME_MIXER = "volume_mixer"
ACTION_PROFILE_SET = "profile_set"
ACTION_PROFILE_NEXT = "profile_next"
ACTION_PROFILE_PREV = "profile_prev"
ACTION_CHANGE_PROFILE = "change_profile"
AUTOHOTKEY_V2_ENV = "AUTOHOTKEY_V2_EXE"
PYTHON_ACTION_ENV = "MACROPAD_PYTHON_EXE"
PROFILE_MIN_DEFAULT = 1
PROFILE_MAX_DEFAULT = 4
PROFILE_CHANGE_MODES = ("set", "next", "prev")

ACTION_TYPES = (
    ACTION_NONE,
    ACTION_KEYBOARD,
    ACTION_SEND_KEYS,
    ACTION_FILE,
    ACTION_AHK,
    ACTION_PYTHON,
    ACTION_MACRO,
    ACTION_VOLUME_MIXER,
    ACTION_CHANGE_PROFILE,
)


class ActionExecutionError(RuntimeError):
    pass


@dataclass(slots=True)
class PythonScriptResult:
    returncode: int = 0
    stdout: str = ""
    stderr: str = ""


def _windows_popen_kwargs() -> dict[str, object]:
    if os.name != "nt":
        return {}

    # Run child processes without creating a visible console window.
    creationflags = int(getattr(subprocess, "CREATE_NO_WINDOW", 0))
    creationflags |= int(getattr(subprocess, "DETACHED_PROCESS", 0))
    kwargs: dict[str, object] = {"creationflags": creationflags}

    startupinfo_factory = getattr(subprocess, "STARTUPINFO", None)
    use_show_window = getattr(subprocess, "STARTF_USESHOWWINDOW", 0)
    hide_window = getattr(subprocess, "SW_HIDE", 0)
    if startupinfo_factory is not None:
        startupinfo = startupinfo_factory()
        startupinfo.dwFlags |= use_show_window
        startupinfo.wShowWindow = hide_window
        kwargs["startupinfo"] = startupinfo
    return kwargs


def _windows_capture_kwargs() -> dict[str, object]:
    if os.name != "nt":
        return {}

    creationflags = int(getattr(subprocess, "CREATE_NO_WINDOW", 0))
    kwargs: dict[str, object] = {"creationflags": creationflags}
    startupinfo_factory = getattr(subprocess, "STARTUPINFO", None)
    use_show_window = getattr(subprocess, "STARTF_USESHOWWINDOW", 0)
    hide_window = getattr(subprocess, "SW_HIDE", 0)
    if startupinfo_factory is not None:
        startupinfo = startupinfo_factory()
        startupinfo.dwFlags |= use_show_window
        startupinfo.wShowWindow = hide_window
        kwargs["startupinfo"] = startupinfo
    return kwargs


@dataclass(slots=True)
class ProfileChangeSpec:
    mode: str = "next"
    step: int = 1
    target: int | None = None
    min_slot: int = PROFILE_MIN_DEFAULT
    max_slot: int = PROFILE_MAX_DEFAULT


def _to_int(raw: str, fallback: int) -> int:
    value = str(raw or "").strip()
    if not value:
        return fallback
    try:
        return int(value, 10)
    except ValueError:
        return fallback


def _clamp_slot(slot: int, min_slot: int, max_slot: int) -> int:
    if slot < min_slot:
        return min_slot
    if slot > max_slot:
        return max_slot
    return slot


def cycle_profile_slot(current_slot: int, delta: int, *, min_slot: int, max_slot: int) -> int:
    min_value = max(1, int(min_slot))
    max_value = max(min_value, int(max_slot))
    span = (max_value - min_value) + 1
    if span <= 0:
        return min_value
    current = _clamp_slot(int(current_slot), min_value, max_value)
    offset = (current - min_value + int(delta)) % span
    return min_value + offset


def parse_change_profile_value(
    raw_value: str,
    *,
    default_min: int = PROFILE_MIN_DEFAULT,
    default_max: int = PROFILE_MAX_DEFAULT,
) -> ProfileChangeSpec:
    min_slot = max(1, int(default_min))
    max_slot = max(min_slot, int(default_max))
    spec = ProfileChangeSpec(min_slot=min_slot, max_slot=max_slot)
    value = (raw_value or "").strip().lower()
    if not value:
        return spec

    if re.fullmatch(r"[+-]?\d+", value):
        target = _clamp_slot(int(value, 10), spec.min_slot, spec.max_slot)
        return ProfileChangeSpec(mode="set", target=target, min_slot=spec.min_slot, max_slot=spec.max_slot)

    tokens = [token.strip() for token in re.split(r"[;,]", value) if token.strip()]
    if not tokens:
        return spec

    if tokens[0] in PROFILE_CHANGE_MODES:
        spec.mode = tokens[0]
        tokens = tokens[1:]

    has_target = False
    has_step = False

    for token in tokens:
        if "=" in token:
            key, raw = token.split("=", 1)
        elif ":" in token:
            key, raw = token.split(":", 1)
        else:
            continue
        key = key.strip().lower()
        raw = raw.strip()
        if not key:
            continue

        if key in {"mode", "action", "op"}:
            if raw in PROFILE_CHANGE_MODES:
                spec.mode = raw
            continue
        if key in {"slot", "target", "profile", "set"}:
            spec.target = _to_int(raw, spec.min_slot)
            has_target = True
            continue
        if key in {"step", "delta"}:
            spec.step = abs(_to_int(raw, 1))
            has_step = True
            continue
        if key in {"min", "start", "from"}:
            spec.min_slot = max(1, _to_int(raw, spec.min_slot))
            continue
        if key in {"max", "end", "to"}:
            spec.max_slot = max(1, _to_int(raw, spec.max_slot))
            continue

    if spec.min_slot > spec.max_slot:
        spec.min_slot, spec.max_slot = spec.max_slot, spec.min_slot
    spec.step = max(1, abs(int(spec.step or 1)))

    if spec.mode == "set":
        if spec.target is None:
            if has_step and not has_target:
                spec.target = spec.step
            else:
                spec.target = spec.min_slot
        spec.target = _clamp_slot(int(spec.target), spec.min_slot, spec.max_slot)
        return spec

    if spec.target is not None and not has_step:
        spec.step = max(1, abs(int(spec.target)))
    spec.target = None
    return spec


def format_change_profile_value(spec: ProfileChangeSpec) -> str:
    mode = spec.mode.strip().lower()
    if mode not in PROFILE_CHANGE_MODES:
        mode = "next"
    min_slot = max(1, int(spec.min_slot))
    max_slot = max(min_slot, int(spec.max_slot))
    if mode == "set":
        target = spec.target if spec.target is not None else min_slot
        target = _clamp_slot(int(target), min_slot, max_slot)
        return f"mode=set;slot={target};min={min_slot};max={max_slot}"
    step = max(1, abs(int(spec.step or 1)))
    return f"mode={mode};step={step};min={min_slot};max={max_slot}"


def normalize_profile_action_kind_value(
    kind: str,
    value: str,
    *,
    default_min: int = PROFILE_MIN_DEFAULT,
    default_max: int = PROFILE_MAX_DEFAULT,
) -> tuple[str, str]:
    normalized_kind = (kind or ACTION_NONE).strip().lower() or ACTION_NONE
    normalized_value = value or ""

    if normalized_kind == ACTION_PROFILE_SET:
        target = _to_int(normalized_value, default_min)
        spec = ProfileChangeSpec(
            mode="set",
            target=target,
            min_slot=max(1, int(default_min)),
            max_slot=max(max(1, int(default_min)), int(default_max)),
        )
        return ACTION_CHANGE_PROFILE, format_change_profile_value(spec)

    if normalized_kind in {ACTION_PROFILE_NEXT, ACTION_PROFILE_PREV}:
        step = abs(_to_int(normalized_value, 1))
        spec = ProfileChangeSpec(
            mode="next" if normalized_kind == ACTION_PROFILE_NEXT else "prev",
            step=max(1, step),
            min_slot=max(1, int(default_min)),
            max_slot=max(max(1, int(default_min)), int(default_max)),
        )
        return ACTION_CHANGE_PROFILE, format_change_profile_value(spec)

    if normalized_kind == ACTION_CHANGE_PROFILE:
        parsed = parse_change_profile_value(
            normalized_value,
            default_min=default_min,
            default_max=default_max,
        )
        return ACTION_CHANGE_PROFILE, format_change_profile_value(parsed)

    return normalized_kind, normalized_value


def _launch_process(command: list[str]) -> None:
    try:
        subprocess.Popen(command, **_windows_popen_kwargs())
    except Exception as exc:
        joined = " ".join(command)
        raise ActionExecutionError(f"Failed to launch '{joined}': {exc}") from exc

def _resolve_python_executable(*, windowless: bool) -> str:
    if os.name != "nt":
        return sys.executable

    explicit = os.environ.get(PYTHON_ACTION_ENV, "").strip()
    if explicit:
        resolved = shutil.which(explicit)
        if resolved:
            return resolved
        explicit_path = Path(explicit).expanduser()
        if explicit_path.exists():
            return str(explicit_path)
        raise ActionExecutionError(
            f"{PYTHON_ACTION_ENV} is set but not found: {explicit}. "
            "Set it to a valid python.exe/pythonw.exe path."
        )

    candidates: list[Path] = []
    for raw_value in [getattr(sys, "executable", ""), getattr(sys, "_base_executable", "")]:
        if not raw_value:
            continue
        base = Path(raw_value)
        if windowless:
            candidates.append(base.with_name("pythonw.exe"))
            candidates.append(base.with_name("python.exe"))
        else:
            candidates.append(base.with_name("python.exe"))
            candidates.append(base.with_name("pythonw.exe"))
        candidates.append(base)

    for name in (("pythonw.exe", "python.exe") if windowless else ("python.exe", "pythonw.exe")):
        resolved = shutil.which(name)
        if resolved:
            candidates.append(Path(resolved))

    for candidate in candidates:
        name = candidate.name.lower()
        if name not in {"python.exe", "pythonw.exe", "python3.exe", "python3w.exe"}:
            continue
        if candidate.exists():
            return str(candidate)

    raise ActionExecutionError(
        "Python interpreter not found for .py file action. Install Python or set "
        f"{PYTHON_ACTION_ENV} to python.exe/pythonw.exe."
    )


def _pythonw_executable() -> str:
    return _resolve_python_executable(windowless=True)


def _python_console_executable() -> str:
    return _resolve_python_executable(windowless=False)


def _run_python_script_in_process(path: Path) -> PythonScriptResult:
    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()
    absolute_path = path.resolve()
    previous_argv = list(sys.argv)
    previous_cwd = Path.cwd()
    previous_sys_path = list(sys.path)
    returncode = 0
    try:
        sys.argv = [str(absolute_path)]
        sys.path.insert(0, str(absolute_path.parent))
        os.chdir(str(absolute_path.parent))
        with contextlib.redirect_stdout(stdout_buffer), contextlib.redirect_stderr(stderr_buffer):
            runpy.run_path(str(absolute_path), run_name="__main__")
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 0
        returncode = 0 if code in {0, None} else int(code)
    finally:
        sys.argv = previous_argv
        sys.path[:] = previous_sys_path
        os.chdir(str(previous_cwd))

    return PythonScriptResult(
        returncode=returncode,
        stdout=stdout_buffer.getvalue().strip(),
        stderr=stderr_buffer.getvalue().strip(),
    )


def run_python_action_helper(script_path: str) -> int:
    try:
        result = _run_python_script_in_process(Path(script_path))
    except Exception as exc:
        print(f"Python action failed: {exc}", file=sys.stderr)
        return 1

    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    return int(result.returncode)


def _run_python_script_file(path: Path) -> PythonScriptResult:
    absolute_path = path.resolve()
    if getattr(sys, "frozen", False):
        command = [str(Path(sys.executable).resolve()), "--run-python-action", str(absolute_path)]
    else:
        command = [_python_console_executable(), str(absolute_path)]
    completed = subprocess.run(
        command,
        cwd=str(absolute_path.parent),
        capture_output=True,
        text=True,
        **_windows_capture_kwargs(),
    )
    return PythonScriptResult(
        returncode=int(completed.returncode),
        stdout=(completed.stdout or "").strip(),
        stderr=(completed.stderr or "").strip(),
    )


def _dedupe_paths(paths: list[Path]) -> list[Path]:
    unique: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        token = str(path).lower()
        if token in seen:
            continue
        seen.add(token)
        unique.append(path)
    return unique


def _candidate_action_paths(raw_value: str) -> list[Path]:
    raw_text = str(raw_value or "").strip()
    if not raw_text:
        return []

    raw_path = Path(raw_text).expanduser()
    if raw_path.is_absolute():
        return [raw_path]

    app_paths = resolve_app_paths()
    candidates: list[Path] = []
    parts = [part.lower() for part in raw_path.parts]
    targets_profiles_root = bool(parts and parts[0] == "profiles")

    if targets_profiles_root:
        candidates.append((app_paths.data_root / raw_path).resolve())
        candidates.append((Path.cwd() / raw_path).resolve())
    else:
        candidates.append((Path.cwd() / raw_path).resolve())
        candidates.append((app_paths.profile_dir / raw_path).resolve())
        candidates.append((app_paths.data_root / raw_path).resolve())

    return _dedupe_paths(candidates)


def resolve_action_path(raw_value: str) -> Path:
    candidates = _candidate_action_paths(raw_value)
    if not candidates:
        return Path()
    existing = [candidate for candidate in candidates if candidate.exists()]
    if existing:
        raw_path = Path(str(raw_value or "").strip())
        parts = [part.lower() for part in raw_path.parts]
        if len(parts) >= 2 and parts[0] == "profiles" and parts[1] in {"runtime_python", "runtime_ahk"}:
            existing.sort(
                key=lambda path: (path.stat().st_mtime, -candidates.index(path)),
                reverse=True,
            )
            return existing[0]
        return existing[0]
    return candidates[0]


def _launch_windows_file_action(path: Path) -> bool:
    suffix = path.suffix.lower()

    if suffix in {".py", ".pyw"}:
        _launch_process([_pythonw_executable(), str(path)])
        return True
    if suffix == ".ahk":
        _launch_process([_resolve_ahk_v2_executable(), str(path)])
        return True
    if suffix in {".bat", ".cmd"}:
        _launch_process(["cmd.exe", "/c", str(path)])
        return True
    if suffix == ".ps1":
        _launch_process(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(path)])
        return True
    if suffix in {".exe", ".com"}:
        _launch_process([str(path)])
        return True

    try:
        _launch_process([str(path)])
        return True
    except ActionExecutionError:
        return False


def _resolve_ahk_v2_executable() -> str:
    explicit = os.environ.get(AUTOHOTKEY_V2_ENV, "").strip()
    if explicit:
        resolved = shutil.which(explicit)
        if resolved:
            return resolved
        explicit_path = Path(explicit).expanduser()
        if explicit_path.exists():
            return str(explicit_path)
        raise ActionExecutionError(
            f"{AUTOHOTKEY_V2_ENV} is set but not found: {explicit}. "
            "Set it to a valid AutoHotkey v2 executable path."
        )

    candidates: list[str] = []
    if os.name == "nt":
        candidates.extend(
            [
                r"C:\Program Files\AutoHotkey\AutoHotkey64.exe",
                r"C:\Program Files\AutoHotkey\v2\AutoHotkey64.exe",
                "AutoHotkey64.exe",
                "AutoHotkey32.exe",
            ]
        )
    else:
        candidates.extend(["autohotkey", "AutoHotkey64.exe"])

    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
        candidate_path = Path(candidate)
        if candidate_path.is_absolute() and candidate_path.exists():
            return str(candidate_path)

    raise ActionExecutionError(
        "AutoHotkey v2 executable not found. Install AutoHotkey v2 or set "
        f"{AUTOHOTKEY_V2_ENV} to the v2 executable path."
    )


async def execute_action(
    action: KeyAction,
    *,
    log: Callable[[str], None],
    volume_direction: int = 1,
    on_volume_mixer: Callable[[VolumeMixerResult], None] | None = None,
) -> None:
    kind = action.kind.strip().lower()

    if kind in {"", ACTION_NONE}:
        return

    if kind == ACTION_AHK:
        if not action.value.strip():
            raise ActionExecutionError("AHK action is missing script path.")
        path = resolve_action_path(action.value)
        if not path.exists():
            raise ActionExecutionError(f"AHK action path not found: {path}")
        executable = _resolve_ahk_v2_executable()
        _launch_process([executable, str(path)])
        log(f"Executed AHK v2: {path}")
        return

    if kind == ACTION_PYTHON:
        if not action.value.strip():
            raise ActionExecutionError("Python action is missing script path.")
        path = resolve_action_path(action.value)
        if not path.exists():
            raise ActionExecutionError(f"Python action path not found: {path}")
        try:
            result = await asyncio.to_thread(_run_python_script_file, path)
        except Exception as exc:
            raise ActionExecutionError(f"Failed to run Python script '{path}': {exc}") from exc
        for line in result.stdout.splitlines():
            if line.strip():
                log(f"PY STDOUT: {line.strip()}")
        for line in result.stderr.splitlines():
            if line.strip():
                log(f"PY STDERR: {line.strip()}")
        if result.returncode != 0:
            raise ActionExecutionError(f"Python script exited with code {result.returncode}: {path}")
        log(f"Executed Python: {path}")
        return

    if kind == ACTION_FILE:
        if not action.value.strip():
            raise ActionExecutionError("file action is missing file path.")
        path = resolve_action_path(action.value)
        if not path.exists():
            raise ActionExecutionError(f"file action path not found: {path}")

        if os.name == "nt":
            if _launch_windows_file_action(path):
                log(f"Executed file: {path}")
            else:
                os.startfile(str(path))  # type: ignore[attr-defined]
                log(f"Opened file: {path}")
            return
        elif sys.platform == "darwin":
            _launch_process(["open", str(path)])
        else:
            _launch_process(["xdg-open", str(path)])
        log(f"Opened file: {path}")
        return

    if kind == ACTION_VOLUME_MIXER:
        if not action.value.strip():
            raise ActionExecutionError("volume_mixer action is missing a target app.")
        try:
            result = await asyncio.to_thread(
                change_volume_mixer_volume,
                action.value,
                direction=volume_direction,
            )
        except VolumeMixerError as exc:
            raise ActionExecutionError(str(exc)) from exc
        if on_volume_mixer is not None:
            on_volume_mixer(result)
        log(
            f"Volume mixer: {result.label} -> {result.volume_percent}% "
            f"({result.matched_sessions} session{'s' if result.matched_sessions != 1 else ''})"
        )
        return

    if kind in {ACTION_KEYBOARD, ACTION_SEND_KEYS}:
        sequence = normalize_key_sequence(action.value)
        if not sequence:
            raise ActionExecutionError(f"{kind} action is missing key sequence.")

        try:
            import keyboard  # type: ignore
        except Exception as exc:
            raise ActionExecutionError(
                "send_keys requires the 'keyboard' package (pip install keyboard)."
            ) from exc

        try:
            await asyncio.to_thread(keyboard.send, sequence)
        except Exception as exc:
            raise ActionExecutionError(f"Failed to send keys '{sequence}': {exc}") from exc
        log(f"Sent keys: {sequence}")
        return

    if kind == ACTION_MACRO:
        if not action.steps:
            raise ActionExecutionError("macro action has no steps.")

        for step in action.steps:
            step_kind = str(step.get("kind") or ACTION_NONE).strip().lower()
            step_value = str(step.get("value") or "")
            try:
                delay_ms = int(step.get("delay_ms", 0))
            except (TypeError, ValueError):
                delay_ms = 0
            if delay_ms > 0:
                await asyncio.sleep(delay_ms / 1000.0)
            await execute_action(
                KeyAction(kind=step_kind, value=step_value),
                log=log,
                volume_direction=volume_direction,
                on_volume_mixer=on_volume_mixer,
            )
        log("Executed macro.")
        return

    raise ActionExecutionError(f"Unknown action type: {action.kind}")




