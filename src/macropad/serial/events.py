from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

EVENT_READY = "READY"
EVENT_SW_CHANGED = "SW_CHANGED"
EVENT_LED_STATE = "LED_STATE"
EVENT_KEY_STATE = "KEY_STATE"
EVENT_ENC_DELTA = "ENC_DELTA"
EVENT_ENC_SWITCH = "ENC_SWITCH"

_KEY_PATTERN = re.compile(r"^\s*(\d+)\s*,\s*(\d+)\s*,\s*([01])(?:\b|,|$)")


@dataclass(frozen=True, slots=True)
class BoardEvent:
    kind: str
    timestamp: datetime
    raw_line: str
    value: bool | None = None
    row: int | None = None
    col: int | None = None
    delta: int | None = None


def timestamp_now() -> datetime:
    return datetime.now().astimezone()


def parse_event_line(line: str, *, timestamp: datetime | None = None) -> BoardEvent | None:
    text = line.strip()
    if not text:
        return None

    ts = timestamp or timestamp_now()
    if text == "READY":
        return BoardEvent(kind=EVENT_READY, timestamp=ts, raw_line=text, value=None)

    if text.startswith("SW="):
        bit = text[3:].strip()
        if bit in {"0", "1"}:
            return BoardEvent(kind=EVENT_SW_CHANGED, timestamp=ts, raw_line=text, value=(bit == "1"))
        return None

    if text.startswith("LED="):
        bit = text[4:].strip()
        if bit in {"0", "1"}:
            return BoardEvent(kind=EVENT_LED_STATE, timestamp=ts, raw_line=text, value=(bit == "1"))
        return None

    if text.startswith("KEY="):
        payload = text[4:].strip()
        match = _KEY_PATTERN.match(payload)
        if match is None:
            return None

        row = int(match.group(1), 10)
        col = int(match.group(2), 10)
        pressed_raw = int(match.group(3), 10)

        if row < 0 or col < 0 or pressed_raw not in (0, 1):
            return None

        return BoardEvent(
            kind=EVENT_KEY_STATE,
            timestamp=ts,
            raw_line=text,
            value=(pressed_raw == 1),
            row=row,
            col=col,
        )

    if text.startswith("ENC="):
        raw_delta = text[4:].strip()
        if raw_delta.startswith("+"):
            raw_delta = raw_delta[1:]
        try:
            delta = int(raw_delta, 10)
        except ValueError:
            return None
        if delta == 0:
            return None
        return BoardEvent(
            kind=EVENT_ENC_DELTA,
            timestamp=ts,
            raw_line=text,
            delta=delta,
        )

    if text.startswith("ENC_SW="):
        bit = text[7:].strip()
        if bit in {"0", "1"}:
            return BoardEvent(kind=EVENT_ENC_SWITCH, timestamp=ts, raw_line=text, value=(bit == "1"))
        return None

    return None
