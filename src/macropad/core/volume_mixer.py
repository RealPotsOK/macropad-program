from __future__ import annotations

from dataclasses import dataclass
import re
import sys
from typing import Any, Callable, Iterable


@dataclass(slots=True)
class VolumeMixerSpec:
    target_kind: str = "process"
    target_value: str = ""
    step: float = 0.05


@dataclass(slots=True)
class VolumeMixerTarget:
    target_kind: str
    target_value: str
    label: str


@dataclass(slots=True)
class VolumeMixerResult:
    label: str
    title: str
    matched_sessions: int
    volume_percent: int
    icon_path: str = ""


class VolumeMixerError(RuntimeError):
    pass


def parse_volume_mixer_value(raw_value: str) -> VolumeMixerSpec:
    spec = VolumeMixerSpec()
    value = str(raw_value or "").strip()
    if not value:
        return spec
    if "=" not in value and ":" not in value and ";" not in value and "," not in value:
        spec.target_value = value
        return spec

    tokens = [token.strip() for token in re.split(r"[;,]", value) if token.strip()]
    for token in tokens:
        if "=" in token:
            key, raw = token.split("=", 1)
        elif ":" in token:
            key, raw = token.split(":", 1)
        else:
            continue
        key = key.strip().lower()
        raw = raw.strip()
        if key in {"kind", "match", "target_kind"}:
            if raw.lower() in {"process", "display"}:
                spec.target_kind = raw.lower()
        elif key in {"target", "value", "name"}:
            spec.target_value = raw
        elif key == "step":
            spec.step = _normalize_step(raw, fallback=spec.step)

    return spec


def format_volume_mixer_value(spec: VolumeMixerSpec) -> str:
    kind = spec.target_kind if spec.target_kind in {"process", "display"} else "process"
    target = str(spec.target_value or "").strip()
    step = _normalize_step(spec.step, fallback=0.05)
    return f"kind={kind};target={target};step={step:.3f}"


def list_volume_mixer_targets(
    *,
    session_provider: Callable[[], Iterable[Any]] | None = None,
) -> list[VolumeMixerTarget]:
    targets: list[VolumeMixerTarget] = []
    seen: set[tuple[str, str]] = set()
    for session in _get_sessions(session_provider=session_provider):
        process_name = _session_process_name(session)
        display_name = _session_display_name(session)

        for candidate in _session_target_candidates(process_name, display_name):
            key = (candidate.target_kind, candidate.target_value.lower())
            if key in seen:
                continue
            seen.add(key)
            targets.append(candidate)

    targets.sort(key=lambda item: item.label.lower())
    return targets


def change_volume_mixer_volume(
    raw_value: str,
    *,
    direction: int = 1,
    session_provider: Callable[[], Iterable[Any]] | None = None,
) -> VolumeMixerResult:
    if sys.platform != "win32":
        raise VolumeMixerError("Volume mixer actions are only supported on Windows.")

    spec = parse_volume_mixer_value(raw_value)
    target_value = spec.target_value.strip()
    if not target_value:
        raise VolumeMixerError("Volume mixer action is missing a target app.")

    delta = _normalize_step(spec.step, fallback=0.05)
    delta *= -1 if direction < 0 else 1

    matched = 0
    last_percent = 0
    title = ""
    icon_path = ""
    for session in _get_sessions(session_provider=session_provider):
        if not _session_matches(session, spec):
            continue

        volume = getattr(session, "SimpleAudioVolume", None)
        if volume is None:
            continue
        current = float(volume.GetMasterVolume())
        updated = max(0.0, min(1.0, current + delta))
        volume.SetMasterVolume(updated, None)
        matched += 1
        last_percent = int(round(updated * 100))
        if not title:
            title = _session_title(session)
        if not icon_path:
            icon_path = _session_process_path(session)

    if matched <= 0:
        raise VolumeMixerError(
            f"No active audio sessions matched '{target_value}'. Open the app and make sure it is playing audio."
        )

    return VolumeMixerResult(
        label=_spec_label(spec),
        title=title or _spec_label(spec),
        matched_sessions=matched,
        volume_percent=last_percent,
        icon_path=icon_path,
    )


def _normalize_step(raw_value: str | float, *, fallback: float) -> float:
    try:
        numeric = float(raw_value)
    except (TypeError, ValueError):
        return fallback
    sign = -1.0 if numeric < 0 else 1.0
    magnitude = abs(numeric)
    if magnitude > 1.0:
        magnitude = magnitude / 100.0
    if magnitude <= 0:
        return fallback
    return sign * min(magnitude, 1.0)


def _get_sessions(*, session_provider: Callable[[], Iterable[Any]] | None) -> list[Any]:
    if session_provider is not None:
        return list(session_provider())
    try:
        from pycaw.pycaw import AudioUtilities  # type: ignore
    except Exception as exc:
        raise VolumeMixerError(
            "Volume mixer requires the 'pycaw' package on Windows."
        ) from exc
    return list(AudioUtilities.GetAllSessions())


def _session_process_name(session: Any) -> str:
    process = getattr(session, "Process", None)
    if process is None:
        return ""
    try:
        return str(process.name() or "").strip()
    except Exception:
        return ""


def _session_display_name(session: Any) -> str:
    display_name = getattr(session, "DisplayName", "")
    return str(display_name or "").strip()


def _session_process_path(session: Any) -> str:
    process = getattr(session, "Process", None)
    if process is None:
        return ""
    try:
        return str(process.exe() or "").strip()
    except Exception:
        return ""


def _session_target_candidates(process_name: str, display_name: str) -> list[VolumeMixerTarget]:
    candidates: list[VolumeMixerTarget] = []
    if process_name:
        label = process_name
        if display_name and display_name.lower() != process_name.lower():
            label = f"{process_name} - {display_name}"
        candidates.append(VolumeMixerTarget("process", process_name, label))
    if display_name:
        candidates.append(VolumeMixerTarget("display", display_name, display_name))
    return candidates


def _session_matches(session: Any, spec: VolumeMixerSpec) -> bool:
    target = spec.target_value.strip().lower()
    if not target:
        return False
    if spec.target_kind == "display":
        return _session_display_name(session).strip().lower() == target
    return _session_process_name(session).strip().lower() == target


def _spec_label(spec: VolumeMixerSpec) -> str:
    target = spec.target_value.strip()
    if not target:
        return "volume mixer"
    if spec.target_kind == "display":
        return target
    return target


def _session_title(session: Any) -> str:
    display_name = _session_display_name(session)
    if display_name:
        return display_name
    process_name = _session_process_name(session)
    if process_name.lower().endswith(".exe"):
        return process_name[:-4]
    return process_name or "Volume"
