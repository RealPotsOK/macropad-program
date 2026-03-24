from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from datetime import datetime
from time import monotonic
from typing import Any, Callable, Iterable

import serial

from ..backoff import ExponentialBackoff
from ..config import Settings
from .errors import SerialControllerError
from .events import (
    BoardEvent,
    EVENT_ENC_DELTA,
    EVENT_ENC_SWITCH,
    EVENT_KEY_STATE,
    EVENT_LED_STATE,
    EVENT_SW_CHANGED,
    parse_event_line,
    timestamp_now,
)
from .ports import resolve_port

LOGGER = logging.getLogger(__name__)

IMG_PREAMBLE_A = 0xAA
IMG_PREAMBLE_B = 0x55
IMG_CMD_SET_FRAME = 0x02
IMG_WIDTH = 128
IMG_HEIGHT = 64
IMG_FORMAT_2BPP_INDEXED = 0x02
DISPLAY_ALLOWED = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 :-'")


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
        self.encoder_delta: int | None = None
        self.encoder_total: int = 0
        self.encoder_switch_state: bool | None = None
        self.key_states: dict[tuple[int, int], bool] = {}

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
        self._write_lock = asyncio.Lock()

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

        async with self._write_lock:
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

    async def clear_oled(self) -> None:
        await self._write_line("CLR")

    async def send_oled_line(self, text: str) -> None:
        normalized = _sanitize_ascii_text(text, allow_pipe=False)
        await self._write_line(f"TXT:{normalized}")

    async def send_oled_lines(self, *lines: str) -> None:
        sanitized = [_sanitize_ascii_text(line, allow_pipe=False) for line in lines]
        await self._write_line(f"TXT:{'|'.join(sanitized)}")

    async def send_oled_text(self, line1: str, line2: str) -> None:
        await self.send_oled_lines(line1, line2)

    async def send_custom_text(self, command: str, *, terminator: str = "\n") -> None:
        payload = str(command or "").encode("ascii", errors="ignore")
        end_bytes = str(terminator or "").encode("ascii", errors="ignore")
        await self._write_bytes(payload + end_bytes)

    async def send_image(self, payload: bytes, *, mode: str = "packet") -> None:
        expected = (IMG_WIDTH * IMG_HEIGHT) // 4
        if len(payload) != expected:
            raise ValueError(f"Image payload must be exactly {expected} bytes, got {len(payload)}.")

        normalized_mode = mode.strip().lower()
        if normalized_mode != "packet":
            raise ValueError("Image mode must be 'packet'.")

        length = len(payload)
        len_lo = length & 0xFF
        len_hi = (length >> 8) & 0xFF
        checksum = (
            IMG_CMD_SET_FRAME
            + IMG_WIDTH
            + IMG_HEIGHT
            + IMG_FORMAT_2BPP_INDEXED
            + len_lo
            + len_hi
            + sum(payload)
        ) & 0xFF
        packet = bytes(
            [
                IMG_PREAMBLE_A,
                IMG_PREAMBLE_B,
                IMG_CMD_SET_FRAME,
                IMG_WIDTH,
                IMG_HEIGHT,
                IMG_FORMAT_2BPP_INDEXED,
                len_lo,
                len_hi,
            ]
        ) + payload + bytes([checksum])
        await self._write_bytes(packet)

    async def _write_line(self, line: str) -> None:
        await self._write_bytes(f"{line}\n".encode("ascii"))

    async def _write_bytes(self, payload: bytes) -> None:
        async with self._write_lock:
            serial_handle = self._serial
            if serial_handle is None or not getattr(serial_handle, "is_open", False):
                raise SerialControllerError("Serial port is not open.")
            if self._raw_logging:
                if len(payload) <= 64 and payload.endswith(b"\n"):
                    LOGGER.debug("TX %s", payload.decode("ascii", errors="ignore").rstrip())
                else:
                    LOGGER.debug("TX %d bytes", len(payload))
            try:
                await asyncio.to_thread(serial_handle.write, payload)
                await asyncio.to_thread(serial_handle.flush)
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

                timestamp = timestamp_now()
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
                elif event.kind == EVENT_ENC_DELTA and event.delta is not None:
                    self.encoder_delta = event.delta
                    self.encoder_total += event.delta
                elif event.kind == EVENT_ENC_SWITCH:
                    self.encoder_switch_state = bool(event.value)
                elif event.kind == EVENT_KEY_STATE and event.row is not None and event.col is not None:
                    self.key_states[(event.row, event.col)] = bool(event.value)

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
    on_connected: Callable[[str], None] | None = None,
    on_disconnected: Callable[[str], None] | None = None,
    on_board: Callable[[BoardSerial | None], None] | None = None,
    on_raw_line: Callable[[datetime, str], None] | None = None,
    serial_factory: Callable[..., Any] | None = None,
    comports_fn: Callable[[], Iterable[Any]] | None = None,
    backoff: ExponentialBackoff | None = None,
) -> None:
    if stop_event is None:
        stop_event = asyncio.Event()
    if backoff is None:
        backoff = ExponentialBackoff(initial=1.0, max_delay=5.0)

    def _safe_callback(callback: Callable[[str], None] | None, value: str) -> None:
        if callback is None:
            return
        try:
            callback(value)
        except Exception as exc:  # pragma: no cover - defensive logging
            LOGGER.warning("Monitor callback failed: %s", exc)

    def _safe_board_callback(callback: Callable[[BoardSerial | None], None] | None, value: BoardSerial | None) -> None:
        if callback is None:
            return
        try:
            callback(value)
        except Exception as exc:  # pragma: no cover - defensive logging
            LOGGER.warning("Monitor callback failed: %s", exc)

    while not stop_event.is_set():
        board: BoardSerial | None = None
        connected_port: str | None = None
        try:
            port = resolve_port(settings, comports_fn=comports_fn)
            board = BoardSerial(
                port=port,
                baud=settings.baud,
                dedupe_ms=settings.dedupe_ms,
                on_event=on_event,
                on_raw_line=on_raw_line,
                raw_logging=LOGGER.isEnabledFor(logging.DEBUG),
                serial_factory=serial_factory,
            )
            await board.open()
            connected_port = port
            _safe_board_callback(on_board, board)
            _safe_callback(on_connected, port)
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
            if connected_port is not None:
                _safe_callback(on_disconnected, str(exc))
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
            _safe_board_callback(on_board, None)
            if connected_port is not None and stop_event.is_set():
                _safe_callback(on_disconnected, "stopped")


def _sanitize_ascii_text(text: str, *, allow_pipe: bool) -> str:
    value = str(text or "").replace("\u2019", "'").replace("\u2018", "'")
    cleaned: list[str] = []
    for char in value:
        code = ord(char)
        if char == "|" and allow_pipe:
            cleaned.append("|")
            continue
        if char == "|" and not allow_pipe:
            cleaned.append(" ")
            continue
        if 0x20 <= code <= 0x7E and char in DISPLAY_ALLOWED:
            cleaned.append(char)
            continue
        cleaned.append(" ")
    return "".join(cleaned).strip()
