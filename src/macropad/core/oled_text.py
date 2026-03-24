from __future__ import annotations

import asyncio
from datetime import datetime
import sys
import time
from typing import Any

from .profile import Profile

DESCRIPTION_PRESET_CUSTOM = "Custom text"
DESCRIPTION_PRESET_ITEMS: tuple[tuple[str, str], ...] = (
    (DESCRIPTION_PRESET_CUSTOM, ""),
    ("Time", "{time}"),
    ("Date", "{date}"),
    ("Date + time", "{datetime}"),
    ("Profile slot", "PROFILE {profile_slot}"),
    ("Profile name", "{profile_name}"),
    ("COM port", "{port}"),
    ("Spotify track", "{spotify_track}"),
    ("Spotify artist", "{spotify_artist}"),
    ("Spotify now playing", "{spotify_track}|{spotify_artist}"),
    ("Any media track", "{media_track}"),
    ("Any media artist", "{media_artist}"),
    ("Any media now playing", "{media_track}|{media_artist}"),
)
DESCRIPTION_PRESET_LABELS: tuple[str, ...] = tuple(label for label, _template in DESCRIPTION_PRESET_ITEMS)
DESCRIPTION_PRESET_TEMPLATES = {label: template for label, template in DESCRIPTION_PRESET_ITEMS}

_REFRESH_INTERVALS = {
    "{time}": 15.0,
    "{date}": 60.0,
    "{datetime}": 15.0,
    "{spotify_track}": 2.0,
    "{spotify_artist}": 2.0,
    "{spotify_track_artist}": 2.0,
    "{media_track}": 2.0,
    "{media_artist}": 2.0,
    "{media_track_artist}": 2.0,
}

_MEDIA_CONTEXT_CACHE: dict[str, str] = {
    "spotify_track": "",
    "spotify_artist": "",
    "spotify_track_artist": "",
    "media_track": "",
    "media_artist": "",
    "media_track_artist": "",
}
_MEDIA_CONTEXT_DISABLED_UNTIL = 0.0
_MEDIA_CONTEXT_BACKOFF_SECONDS = 30.0
_MEDIA_MANAGER_TIMEOUT_SECONDS = 0.35
_MEDIA_PROPERTIES_TIMEOUT_SECONDS = 0.2


class _SafeTemplateContext(dict[str, Any]):
    def __missing__(self, key: str) -> str:
        return ""


def description_template_for_label(label: str, *, current_value: str = "") -> str:
    normalized = str(label or "").strip()
    if normalized == DESCRIPTION_PRESET_CUSTOM:
        return current_value
    return DESCRIPTION_PRESET_TEMPLATES.get(normalized, current_value)


def infer_description_preset_label(template: str) -> str:
    normalized = str(template or "").strip()
    for label, preset_template in DESCRIPTION_PRESET_ITEMS:
        if label == DESCRIPTION_PRESET_CUSTOM:
            continue
        if normalized == preset_template:
            return label
    return DESCRIPTION_PRESET_CUSTOM


def description_refresh_interval(template: str) -> float | None:
    normalized = str(template or "")
    interval: float | None = None
    for token, seconds in _REFRESH_INTERVALS.items():
        if token in normalized:
            interval = seconds if interval is None else min(interval, seconds)
    return interval


def render_template_text(template: str, context: dict[str, Any]) -> str:
    raw = str(template or "")
    try:
        rendered = raw.format_map(_SafeTemplateContext(context))
    except Exception:
        rendered = raw
    return rendered.replace("\r", " ").replace("\n", " ").strip()


async def render_profile_display_lines(
    profile: Profile,
    *,
    slot: int,
    port: str = "",
) -> tuple[str, ...]:
    context = await build_description_context(profile=profile, slot=slot, port=port)
    rendered_name = render_template_text(profile.name, context)
    rendered_description = render_template_text(profile.description, context)

    base_lines: list[str] = [rendered_name]
    if "|" in rendered_description:
        base_lines.extend(part.strip() for part in rendered_description.split("|"))
    else:
        base_lines.append(rendered_description)
    return tuple(base_lines)


async def build_description_context(
    *,
    profile: Profile,
    slot: int,
    port: str = "",
) -> dict[str, Any]:
    now = datetime.now()
    context: dict[str, Any] = {
        "profile_slot": int(slot),
        "profile_name": str(profile.name or ""),
        "port": str(port or ""),
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M"),
        "datetime": now.strftime("%Y-%m-%d %H:%M"),
        "spotify_track": "",
        "spotify_artist": "",
        "spotify_track_artist": "",
        "media_track": "",
        "media_artist": "",
        "media_track_artist": "",
    }
    context.update(await _read_media_context())
    return context


async def _read_media_context() -> dict[str, str]:
    global _MEDIA_CONTEXT_DISABLED_UNTIL
    context = dict(_MEDIA_CONTEXT_CACHE)
    if sys.platform != "win32":
        return context

    if time.monotonic() < _MEDIA_CONTEXT_DISABLED_UNTIL:
        return context

    try:
        from winsdk.windows.media.control import (  # type: ignore
            GlobalSystemMediaTransportControlsSessionManager as GSMTCManager,
        )
    except Exception:
        return context

    try:
        manager = await asyncio.wait_for(
            GSMTCManager.request_async(),
            timeout=_MEDIA_MANAGER_TIMEOUT_SECONDS,
        )
        sessions = list(manager.get_sessions())
    except Exception:
        _MEDIA_CONTEXT_DISABLED_UNTIL = time.monotonic() + _MEDIA_CONTEXT_BACKOFF_SECONDS
        return context

    spotify_track = ""
    spotify_artist = ""
    media_track = ""
    media_artist = ""

    for session in sessions:
        source = str(getattr(session, "source_app_user_model_id", "") or "").lower()
        try:
            props = await asyncio.wait_for(
                session.try_get_media_properties_async(),
                timeout=_MEDIA_PROPERTIES_TIMEOUT_SECONDS,
            )
        except Exception:
            continue
        track = str(getattr(props, "title", "") or "").strip()
        artist = str(getattr(props, "artist", "") or "").strip()
        if (track or artist) and not media_track and not media_artist:
            media_track = track
            media_artist = artist
        if (track or artist) and "spotify" in source and not spotify_track and not spotify_artist:
            spotify_track = track
            spotify_artist = artist
        if media_track and spotify_track:
            break

    context = {
        "spotify_track": spotify_track,
        "spotify_artist": spotify_artist,
        "spotify_track_artist": _join_track_artist(spotify_track, spotify_artist),
        "media_track": media_track,
        "media_artist": media_artist,
        "media_track_artist": _join_track_artist(media_track, media_artist),
    }
    _MEDIA_CONTEXT_CACHE.update(context)
    return context


def _join_track_artist(track: str, artist: str) -> str:
    left = str(track or "").strip()
    right = str(artist or "").strip()
    if left and right:
        return f"{left} - {right}"
    return left or right
