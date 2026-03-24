from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace
from typing import Any

import pytest

from macropad.backoff import ExponentialBackoff
from macropad.board_serial import (
    EVENT_ENC_DELTA,
    EVENT_ENC_SWITCH,
    EVENT_KEY_STATE,
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
from macropad.config import Settings


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
    assert parse_event_line("KEY=0,1,1") is not None
    assert parse_event_line("KEY=2,3,0") is not None
    assert parse_event_line("ENC=+1") is not None
    assert parse_event_line("ENC=-1") is not None
    assert parse_event_line("ENC_SW=1") is not None
    assert parse_event_line("ENC_SW=0") is not None

    assert parse_event_line("SW=3") is None
    assert parse_event_line("LED=T") is None
    assert parse_event_line("KEY=1,1,2") is None
    assert parse_event_line("ENC=0") is None
    assert parse_event_line("ENC_SW=2") is None
    assert parse_event_line("random") is None


def test_parse_event_line_types() -> None:
    ready = parse_event_line("READY")
    sw = parse_event_line("SW=1")
    led = parse_event_line("LED=0")
    key = parse_event_line("KEY=1,3,1")
    enc = parse_event_line("ENC=-1")
    enc_sw = parse_event_line("ENC_SW=1")
    assert ready is not None and ready.kind == EVENT_READY
    assert sw is not None and sw.kind == EVENT_SW_CHANGED and sw.value is True
    assert led is not None and led.kind == EVENT_LED_STATE and led.value is False
    assert key is not None and key.kind == EVENT_KEY_STATE and key.row == 1 and key.col == 3 and key.value is True
    assert enc is not None and enc.kind == EVENT_ENC_DELTA and enc.delta == -1
    assert enc_sw is not None and enc_sw.kind == EVENT_ENC_SWITCH and enc_sw.value is True


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


def test_board_serial_oled_text_commands() -> None:
    captured: dict[str, Any] = {}

    def serial_factory(port: str, baud: int, **kwargs: Any) -> FakeSerial:
        captured["instance"] = FakeSerial(port, baud, **kwargs)
        return captured["instance"]

    async def _run() -> None:
        board = BoardSerial(port="COM8", baud=115200, serial_factory=serial_factory)
        await board.open()
        try:
            await board.clear_oled()
            await board.send_oled_line("Volume 42")
            await board.send_oled_text("Now Playing", "Track 01")
            await board.send_oled_lines("Profile 1", "Song Name", "Artist Name")
        finally:
            await board.close()

    asyncio.run(_run())
    instance = captured["instance"]
    assert instance.writes == [
        b"CLR\n",
        b"TXT:Volume 42\n",
        b"TXT:Now Playing|Track 01\n",
        b"TXT:Profile 1|Song Name|Artist Name\n",
    ]


def test_board_serial_oled_text_filters_unsafe_characters() -> None:
    captured: dict[str, Any] = {}

    def serial_factory(port: str, baud: int, **kwargs: Any) -> FakeSerial:
        captured["instance"] = FakeSerial(port, baud, **kwargs)
        return captured["instance"]

    async def _run() -> None:
        board = BoardSerial(port="COM8", baud=115200, serial_factory=serial_factory)
        await board.open()
        try:
            await board.send_oled_line("Profile\t2 @alpha")
            await board.send_oled_text("a|b", "c_d")
            await board.send_oled_lines("one|two", "three_five", "six@seven")
            await board.send_oled_line("it's fine")
            await board.send_oled_line("it’s fine")
        finally:
            await board.close()

    asyncio.run(_run())
    instance = captured["instance"]
    assert instance.writes == [
        b"TXT:Profile 2  alpha\n",
        b"TXT:a b|c d\n",
        b"TXT:one two|three five|six seven\n",
        b"TXT:it's fine\n",
        b"TXT:it's fine\n",
    ]


def test_board_serial_send_image_rejects_text_mode() -> None:
    captured: dict[str, Any] = {}

    def serial_factory(port: str, baud: int, **kwargs: Any) -> FakeSerial:
        captured["instance"] = FakeSerial(port, baud, **kwargs)
        return captured["instance"]

    payload = bytes([0xFF]) * 2048

    async def _run() -> None:
        board = BoardSerial(port="COM8", baud=115200, serial_factory=serial_factory)
        await board.open()
        try:
            with pytest.raises(ValueError):
                await board.send_image(payload, mode="text")
        finally:
            await board.close()

    asyncio.run(_run())


def test_board_serial_send_image_packet_mode() -> None:
    captured: dict[str, Any] = {}

    def serial_factory(port: str, baud: int, **kwargs: Any) -> FakeSerial:
        captured["instance"] = FakeSerial(port, baud, **kwargs)
        return captured["instance"]

    payload = bytes([0x01]) * 2048

    async def _run() -> None:
        board = BoardSerial(port="COM8", baud=115200, serial_factory=serial_factory)
        await board.open()
        try:
            await board.send_image(payload, mode="packet")
        finally:
            await board.close()

    asyncio.run(_run())
    instance = captured["instance"]
    assert len(instance.writes) == 1
    packet = instance.writes[0]
    assert packet[0:2] == bytes([0xAA, 0x55])
    assert packet[2] == 0x02
    assert packet[3] == 128
    assert packet[4] == 64
    assert packet[5] == 0x02
    assert packet[6] == 0x00 and packet[7] == 0x08
    assert packet[8:-1] == payload
    expected_checksum = (0x02 + 128 + 64 + 0x02 + 0x00 + 0x08 + sum(payload)) & 0xFF
    assert packet[-1] == expected_checksum


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


def test_board_serial_tracks_key_state_events() -> None:
    captured: dict[str, Any] = {}

    def serial_factory(port: str, baud: int, **kwargs: Any) -> FakeSerial:
        captured["instance"] = FakeSerial(
            port,
            baud,
            **kwargs,
            lines=[b"KEY=0,1,1\n", b"KEY=0,1,0\n", b"KEY=2,3,1\n"],
        )
        return captured["instance"]

    async def _run() -> dict[tuple[int, int], bool]:
        board = BoardSerial(port="COM7", baud=9600, serial_factory=serial_factory)
        await board.open()
        try:
            _ = await board.wait_event(timeout=0.3)
            _ = await board.wait_event(timeout=0.3)
            _ = await board.wait_event(timeout=0.3)
            return dict(board.key_states)
        finally:
            await board.close()

    key_states = asyncio.run(_run())
    assert key_states[(0, 1)] is False
    assert key_states[(2, 3)] is True


def test_board_serial_tracks_encoder_events() -> None:
    captured: dict[str, Any] = {}

    def serial_factory(port: str, baud: int, **kwargs: Any) -> FakeSerial:
        captured["instance"] = FakeSerial(
            port,
            baud,
            **kwargs,
            lines=[b"ENC=-1\n", b"ENC=+1\n", b"ENC=+1\n"],
        )
        return captured["instance"]

    async def _run() -> tuple[int | None, int]:
        board = BoardSerial(port="COM7", baud=9600, serial_factory=serial_factory)
        await board.open()
        try:
            _ = await board.wait_event(timeout=0.3)
            _ = await board.wait_event(timeout=0.3)
            _ = await board.wait_event(timeout=0.3)
            return (board.encoder_delta, board.encoder_total)
        finally:
            await board.close()

    delta, total = asyncio.run(_run())
    assert delta == 1
    assert total == 1


def test_board_serial_tracks_encoder_switch_events() -> None:
    captured: dict[str, Any] = {}

    def serial_factory(port: str, baud: int, **kwargs: Any) -> FakeSerial:
        captured["instance"] = FakeSerial(
            port,
            baud,
            **kwargs,
            lines=[b"ENC_SW=1\n", b"ENC_SW=0\n"],
        )
        return captured["instance"]

    async def _run() -> bool | None:
        board = BoardSerial(port="COM7", baud=9600, serial_factory=serial_factory)
        await board.open()
        try:
            _ = await board.wait_event(timeout=0.3)
            _ = await board.wait_event(timeout=0.3)
            return board.encoder_switch_state
        finally:
            await board.close()

    switch_state = asyncio.run(_run())
    assert switch_state is False


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


def test_monitor_reconnects_after_many_open_failures_without_overflow() -> None:
    attempts = {"count": 0}
    stop_event = asyncio.Event()
    received: list[bool] = []

    def serial_factory(port: str, baud: int, **kwargs: Any) -> FakeSerial:
        attempts["count"] += 1
        if attempts["count"] <= 1100:
            raise OSError("port missing")
        return FakeSerial(port, baud, **kwargs, lines=[b"SW=1\n"])

    def on_event(event: Any) -> None:
        if event.kind == EVENT_SW_CHANGED:
            received.append(bool(event.value))
            stop_event.set()

    backoff = ExponentialBackoff(
        initial=0.0,
        max_delay=0.0,
        factor=2.0,
        jitter_low=1.0,
        jitter_high=1.0,
        random_fn=lambda _low, _high: 1.0,
    )

    async def _run() -> None:
        await monitor_with_reconnect(
            Settings(port="COM13"),
            on_event=on_event,
            stop_event=stop_event,
            serial_factory=serial_factory,
            backoff=backoff,
        )

    asyncio.run(_run())
    assert attempts["count"] >= 1101
    assert received == [True]
