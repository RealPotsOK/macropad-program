from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime
from time import monotonic
from typing import Any, Callable, Iterable

import serial
from serial.tools import list_ports

from .backoff import ExponentialBackoff
from .config import Settings

LOGGER = logging.getLogger(__name__)

EVENT_READY = "READY"
EVENT_SW_CHANGED = "SW_CHANGED"
EVENT_LED_STATE = "LED_STATE"


class SerialControllerError(RuntimeError):
    """Base runtime error for serial controller operations."""


class PortSelectionError(SerialControllerError):
    """Raised when a unique serial port cannot be selected."""


@dataclass(frozen=True, slots=True)
class PortInfo:
    device: str
    description: str
    hwid: str
    manufacturer: str | None = None


@dataclass(frozen=True, slots=True)
class BoardEvent:
    kind: str
    timestamp: datetime
    raw_line: str
    value: bool | None = None


def _timestamp_now() -> datetime:
    return datetime.now().astimezone()


def parse_event_line(line: str, *, timestamp: datetime | None = None) -> BoardEvent | None:
    text = line.strip()
    if not text:
        return None

    ts = timestamp or _timestamp_now()
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

    return None


def list_serial_ports(
    *, comports_fn: Callable[[], Iterable[Any]] | None = None
) -> list[PortInfo]:
    if comports_fn is None:
        comports_fn = list_ports.comports

    ports: list[PortInfo] = []
    for port in comports_fn():
        ports.append(
            PortInfo(
                device=str(getattr(port, "device", "")),
                description=str(getattr(port, "description", "") or ""),
                hwid=str(getattr(port, "hwid", "") or ""),
                manufacturer=getattr(port, "manufacturer", None),
            )
        )
    return sorted(ports, key=lambda value: value.device.upper())


def format_port_table(ports: list[PortInfo]) -> str:
    if not ports:
        return "No serial ports found."
    lines = ["PORT\tDESCRIPTION\tHWID"]
    for port in ports:
        description = port.description or "<unknown>"
        hwid = port.hwid or "<unknown>"
        lines.append(f"{port.device}\t{description}\t{hwid}")
    return "\n".join(lines)


def resolve_port(
    settings: Settings,
    *,
    ports: list[PortInfo] | None = None,
    comports_fn: Callable[[], Iterable[Any]] | None = None,
) -> str:
    if settings.port:
        return settings.port

    ports = ports if ports is not None else list_serial_ports(comports_fn=comports_fn)
    hint = (settings.hint or "").strip()

    if hint:
        lowered_hint = hint.lower()
        matches: list[PortInfo] = []
        for port in ports:
            searchable = " ".join(
                [
                    port.device,
                    port.description,
                    port.hwid,
                    port.manufacturer or "",
                ]
            ).lower()
            if lowered_hint in searchable:
                matches.append(port)

        if len(matches) == 1:
            return matches[0].device
        if len(matches) > 1:
            details = ", ".join(match.device for match in matches)
            raise PortSelectionError(
                f"Hint '{hint}' matched multiple ports ({details}). Use --port to pick one.\n"
                f"{format_port_table(ports)}"
            )
        raise PortSelectionError(
            f"No serial ports matched hint '{hint}'.\n"
            f"{format_port_table(ports)}\n"
            "Pass --port COMx or adjust --hint."
        )

    raise PortSelectionError(
        "No port selected. Provide --port COMx or --hint text.\n"
        f"{format_port_table(ports)}"
    )


class BoardSerial:
    """Async wrapper around a line-oriented serial protocol."""

    def __init__(
        self,
        *,
        port: str,
        baud: int,
        dedupe_ms: int = 100,
        on_event: Callable[[BoardEvent], None] | None = None,
        on_raw_line: Callable[[datetime, str], None] | None = None,
        raw_logging: bool = False,
        serial_factory: Callable[..., Any] | None = None,
    ) -> None:
        self.port = port
        self.baud = baud
        self.dedupe_ms = dedupe_ms
        self.switch_state: bool | None = None
        self.led_state: bool | None = None

        self._on_event = on_event
        self._on_raw_line = on_raw_line
        self._raw_logging = raw_logging
        self._serial_factory = serial_factory or serial.Serial

        self._serial: Any | None = None
        self._event_queue: asyncio.Queue[BoardEvent] = asyncio.Queue()
        self._reader_task: asyncio.Task[None] | None = None
        self._reader_closed = asyncio.Event()
        self._reader_error: Exception | None = None
        self._last_sw_ts: float = 0.0

    @property
    def is_open(self) -> bool:
        return bool(self._serial is not None and getattr(self._serial, "is_open", False))

    @property
    def reader_error(self) -> Exception | None:
        return self._reader_error

    async def open(self) -> None:
        if self.is_open:
            return
        try:
            self._serial = await asyncio.to_thread(
                self._serial_factory,
                self.port,
                self.baud,
                timeout=0.2,
                write_timeout=1.0,
            )
        except Exception as exc:
            raise SerialControllerError(
                f"Unable to open serial port {self.port} @ {self.baud}: {exc}"
            ) from exc

        self._reader_error = None
        self._reader_closed.clear()
        self._reader_task = asyncio.create_task(self._reader_loop())

    async def close(self) -> None:
        if self._reader_task is not None:
            self._reader_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._reader_task
            self._reader_task = None

        if self._serial is not None:
            with suppress(Exception):
                if getattr(self._serial, "is_open", False):
                    await asyncio.to_thread(self._serial.close)
            self._serial = None
        self._reader_closed.set()

    async def wait_closed(self) -> None:
        await self._reader_closed.wait()

    async def wait_event(
        self,
        *,
        kinds: set[str] | None = None,
        timeout: float | None = None,
    ) -> BoardEvent | None:
        deadline = None if timeout is None else monotonic() + timeout
        while True:
            remaining: float | None = None
            if deadline is not None:
                remaining = deadline - monotonic()
                if remaining <= 0:
                    return None

            try:
                if remaining is None:
                    event = await self._event_queue.get()
                else:
                    event = await asyncio.wait_for(self._event_queue.get(), timeout=remaining)
            except asyncio.TimeoutError:
                return None

            if kinds is None or event.kind in kinds:
                return event

    async def send_led(self, value: bool | int) -> None:
        normalized = int(value)
        if normalized not in (0, 1):
            raise ValueError("LED value must be 0/1 or bool.")
        await self._write_line(f"LED={normalized}")

    async def toggle_led(self) -> None:
        await self._write_line("LED=T")

    async def _write_line(self, line: str) -> None:
        if self._serial is None or not self.is_open:
            raise SerialControllerError("Serial port is not open.")
        if self._raw_logging:
            LOGGER.debug("TX %s", line)

        payload = f"{line}\n".encode("ascii")
        try:
            await asyncio.to_thread(self._serial.write, payload)
            await asyncio.to_thread(self._serial.flush)
        except Exception as exc:
            raise SerialControllerError(f"Failed to write to serial port {self.port}: {exc}") from exc

    async def _reader_loop(self) -> None:
        try:
            while True:
                if self._serial is None:
                    break

                try:
                    raw = await asyncio.to_thread(self._serial.readline)
                except Exception as exc:
                    self._reader_error = exc
                    break

                if not raw:
                    continue

                text = raw.decode("ascii", errors="ignore").strip()
                if not text:
                    continue

                timestamp = _timestamp_now()
                if self._on_raw_line is not None:
                    try:
                        self._on_raw_line(timestamp, text)
                    except Exception as exc:  # pragma: no cover - defensive logging
                        LOGGER.warning("Raw line callback failed: %s", exc)

                if self._raw_logging:
                    LOGGER.debug("RX %s", text)

                event = parse_event_line(text, timestamp=timestamp)
                if event is None:
                    continue

                if event.kind == EVENT_SW_CHANGED:
                    now_ts = monotonic()
                    if (
                        self.dedupe_ms > 0
                        and self.switch_state is not None
                        and event.value == self.switch_state
                        and (now_ts - self._last_sw_ts) * 1000 <= self.dedupe_ms
                    ):
                        continue
                    self.switch_state = bool(event.value)
                    self._last_sw_ts = now_ts
                elif event.kind == EVENT_LED_STATE:
                    self.led_state = bool(event.value)

                self._event_queue.put_nowait(event)
                if self._on_event is not None:
                    try:
                        self._on_event(event)
                    except Exception as exc:  # pragma: no cover - defensive logging
                        LOGGER.warning("Event callback failed: %s", exc)
        except asyncio.CancelledError:
            pass
        finally:
            self._reader_closed.set()


async def monitor_with_reconnect(
    settings: Settings,
    *,
    on_event: Callable[[BoardEvent], None],
    stop_event: asyncio.Event | None = None,
    serial_factory: Callable[..., Any] | None = None,
    comports_fn: Callable[[], Iterable[Any]] | None = None,
    backoff: ExponentialBackoff | None = None,
) -> None:
    if stop_event is None:
        stop_event = asyncio.Event()
    if backoff is None:
        backoff = ExponentialBackoff(initial=1.0, max_delay=5.0)

    while not stop_event.is_set():
        board: BoardSerial | None = None
        try:
            port = resolve_port(settings, comports_fn=comports_fn)
            board = BoardSerial(
                port=port,
                baud=settings.baud,
                dedupe_ms=settings.dedupe_ms,
                on_event=on_event,
                raw_logging=LOGGER.isEnabledFor(logging.DEBUG),
                serial_factory=serial_factory,
            )
            await board.open()
            LOGGER.info("Connected to %s @ %d", port, settings.baud)
            backoff.reset()

            while not stop_event.is_set():
                await asyncio.sleep(0.2)
                if board.reader_error is not None:
                    raise SerialControllerError(f"Serial read failed: {board.reader_error}")
                if not board.is_open:
                    raise SerialControllerError("Serial port closed unexpectedly.")

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if stop_event.is_set():
                break
            delay = backoff.next_delay()
            LOGGER.warning("Monitor error: %s. Reconnecting in %.2fs", exc, delay)
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=delay)
            except asyncio.TimeoutError:
                pass
        finally:
            if board is not None:
                await board.close()
