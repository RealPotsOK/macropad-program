from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace
from typing import Any

import pytest

from macropad_ble.backoff import ExponentialBackoff
from macropad_ble.board_serial import (
    EVENT_LED_STATE,
    EVENT_READY,
    EVENT_SW_CHANGED,
    BoardSerial,
    PortSelectionError,
    format_port_table,
    monitor_with_reconnect,
    parse_event_line,
    resolve_port,
)
from macropad_ble.config import Settings


class FakeSerial:
    def __init__(
        self,
        _port: str,
        _baud: int,
        *,
        timeout: float = 0.2,
        write_timeout: float = 1.0,
        lines: list[bytes] | None = None,
    ) -> None:
        del timeout, write_timeout
        self.is_open = True
        self._lines = list(lines or [])
        self.writes: list[bytes] = []

    def readline(self) -> bytes:
        if not self.is_open:
            raise OSError("port closed")
        if self._lines:
            return self._lines.pop(0)
        time.sleep(0.01)
        return b""

    def write(self, payload: bytes) -> int:
        if not self.is_open:
            raise OSError("write on closed port")
        self.writes.append(payload)
        return len(payload)

    def flush(self) -> None:
        return None

    def close(self) -> None:
        self.is_open = False


def test_parse_event_line_variants() -> None:
    assert parse_event_line("READY") is not None
    assert parse_event_line("SW=1") is not None
    assert parse_event_line("LED=0") is not None

    assert parse_event_line("SW=3") is None
    assert parse_event_line("LED=T") is None
    assert parse_event_line("random") is None


def test_parse_event_line_types() -> None:
    ready = parse_event_line("READY")
    sw = parse_event_line("SW=1")
    led = parse_event_line("LED=0")
    assert ready is not None and ready.kind == EVENT_READY
    assert sw is not None and sw.kind == EVENT_SW_CHANGED and sw.value is True
    assert led is not None and led.kind == EVENT_LED_STATE and led.value is False


def test_resolve_port_prefers_explicit_port() -> None:
    settings = Settings(port="COM12")
    assert resolve_port(settings, ports=[]) == "COM12"


def test_resolve_port_by_hint() -> None:
    settings = Settings(hint="microchip")
    ports = [
        SimpleNamespace(
            device="COM5",
            description="USB Serial",
            hwid="XYZ",
            manufacturer="Other",
        ),
        SimpleNamespace(
            device="COM12",
            description="Curiosity Nano",
            hwid="nEDBG123",
            manufacturer="Microchip",
        ),
    ]
    selected = resolve_port(settings, ports=[
        SimpleNamespace(device=p.device, description=p.description, hwid=p.hwid, manufacturer=p.manufacturer)
        for p in ports
    ])
    assert selected == "COM12"


def test_resolve_port_fails_without_port_or_hint() -> None:
    settings = Settings()
    with pytest.raises(PortSelectionError) as exc:
        resolve_port(
            settings,
            ports=[
                SimpleNamespace(device="COM11", description="Curiosity", hwid="USB\\VID", manufacturer="Microchip")
            ],
        )
    assert "Provide --port COMx or --hint text" in str(exc.value)


def test_format_port_table_contains_columns() -> None:
    table = format_port_table(
        [SimpleNamespace(device="COM9", description="Board", hwid="USB", manufacturer=None)]
    )
    assert "PORT\tDESCRIPTION\tHWID" in table
    assert "COM9\tBoard\tUSB" in table


def test_board_serial_send_and_toggle() -> None:
    captured: dict[str, Any] = {}

    def serial_factory(port: str, baud: int, **kwargs: Any) -> FakeSerial:
        captured["instance"] = FakeSerial(port, baud, **kwargs)
        return captured["instance"]

    async def _run() -> None:
        board = BoardSerial(port="COM8", baud=9600, serial_factory=serial_factory)
        await board.open()
        try:
            await board.send_led(True)
            await board.toggle_led()
        finally:
            await board.close()

    asyncio.run(_run())
    instance = captured["instance"]
    assert instance.writes == [b"LED=1\n", b"LED=T\n"]


def test_board_serial_dedupes_quick_duplicate_switch_lines() -> None:
    captured: dict[str, Any] = {}

    def serial_factory(port: str, baud: int, **kwargs: Any) -> FakeSerial:
        captured["instance"] = FakeSerial(
            port,
            baud,
            **kwargs,
            lines=[b"SW=1\n", b"SW=1\n"],
        )
        return captured["instance"]

    async def _run() -> list[str]:
        board = BoardSerial(port="COM7", baud=9600, dedupe_ms=100, serial_factory=serial_factory)
        kinds: list[str] = []
        await board.open()
        try:
            event = await board.wait_event(timeout=0.3)
            if event:
                kinds.append(event.kind)
            duplicate = await board.wait_event(timeout=0.2)
            if duplicate:
                kinds.append(duplicate.kind)
            return kinds
        finally:
            await board.close()

    observed = asyncio.run(_run())
    assert observed == [EVENT_SW_CHANGED]


def test_board_serial_raw_callback_receives_all_lines() -> None:
    captured: dict[str, Any] = {}
    raw_lines: list[str] = []

    def serial_factory(port: str, baud: int, **kwargs: Any) -> FakeSerial:
        captured["instance"] = FakeSerial(
            port,
            baud,
            **kwargs,
            lines=[b"READY\n", b"FOO=123\n", b"SW=1\n"],
        )
        return captured["instance"]

    async def _run() -> list[str]:
        board = BoardSerial(
            port="COM7",
            baud=9600,
            serial_factory=serial_factory,
            on_raw_line=lambda _ts, line: raw_lines.append(line),
        )
        await board.open()
        try:
            _ = await board.wait_event(timeout=0.3)
            _ = await board.wait_event(timeout=0.3)
            return list(raw_lines)
        finally:
            await board.close()

    observed = asyncio.run(_run())
    assert observed == ["READY", "FOO=123", "SW=1"]


def test_monitor_reconnects_after_open_failure() -> None:
    attempts = {"count": 0}
    stop_event = asyncio.Event()
    received: list[bool] = []

    def comports_fn() -> list[Any]:
        return [SimpleNamespace(device="COM4", description="Curiosity Nano", hwid="nEDBG", manufacturer="Microchip")]

    def serial_factory(port: str, baud: int, **kwargs: Any) -> FakeSerial:
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise OSError("open failed")
        return FakeSerial(port, baud, **kwargs, lines=[b"SW=1\n"])

    def on_event(event: Any) -> None:
        if event.kind == EVENT_SW_CHANGED:
            received.append(bool(event.value))
            stop_event.set()

    backoff = ExponentialBackoff(
        initial=0.01,
        max_delay=0.05,
        factor=2.0,
        jitter_low=1.0,
        jitter_high=1.0,
        random_fn=lambda _low, _high: 1.0,
    )

    async def _run() -> None:
        await monitor_with_reconnect(
            Settings(hint="Curiosity"),
            on_event=on_event,
            stop_event=stop_event,
            serial_factory=serial_factory,
            comports_fn=comports_fn,
            backoff=backoff,
        )

    asyncio.run(_run())
    assert attempts["count"] >= 2
    assert received == [True]
