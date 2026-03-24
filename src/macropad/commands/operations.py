from __future__ import annotations

import asyncio
import logging
import sys
import threading
from contextlib import suppress
from typing import Any

from ..config import Settings
from ..serial import (
    EVENT_ENC_DELTA,
    EVENT_ENC_SWITCH,
    EVENT_KEY_STATE,
    EVENT_LED_STATE,
    EVENT_READY,
    EVENT_SW_CHANGED,
    BoardEvent,
    BoardSerial,
    SerialControllerError,
    format_port_table,
    list_serial_ports,
    monitor_with_reconnect,
    resolve_port,
)

LOGGER = logging.getLogger(__name__)


def format_event_line(event: BoardEvent) -> str:
    stamp = event.timestamp.isoformat(timespec="seconds")
    if event.kind == EVENT_READY:
        return f"{stamp} READY"
    if event.kind == EVENT_SW_CHANGED:
        return f"{stamp} SW={1 if event.value else 0}"
    if event.kind == EVENT_LED_STATE:
        return f"{stamp} LED={1 if event.value else 0}"
    if event.kind == EVENT_ENC_DELTA and event.delta is not None:
        return f"{stamp} ENC={event.delta:+d}"
    if event.kind == EVENT_ENC_SWITCH:
        return f"{stamp} ENC_SW={1 if event.value else 0}"
    if event.kind == EVENT_KEY_STATE and event.row is not None and event.col is not None:
        state = 1 if event.value else 0
        return f"{stamp} KEY={event.row},{event.col},{state}"
    return f"{stamp} {event.raw_line}"


async def open_board(settings: Settings) -> BoardSerial:
    port = resolve_port(settings)
    board = BoardSerial(
        port=port,
        baud=settings.baud,
        dedupe_ms=settings.dedupe_ms,
        raw_logging=LOGGER.isEnabledFor(logging.DEBUG),
    )
    await board.open()
    return board


async def run_list() -> int:
    ports = list_serial_ports()
    if not ports:
        print("No serial ports found.")
        return 0
    print(format_port_table(ports))
    return 0


async def run_monitor(settings: Settings) -> int:
    print("Monitoring serial events. Press Ctrl+C to stop.")
    stop_event = asyncio.Event()
    await monitor_with_reconnect(
        settings,
        on_event=lambda event: print(format_event_line(event), flush=True),
        stop_event=stop_event,
    )
    return 0


def run_gui(
    settings: Settings,
    *,
    start_hidden: bool = False,
    launch_command: list[str] | None = None,
    instance_guard: object | None = None,
) -> int:
    from ..qt.app import run_qt_app

    return run_qt_app(
        settings,
        start_hidden=start_hidden,
        launch_command=launch_command,
        instance_guard=instance_guard,
    )


def _format_raw_line(timestamp: Any, line: str) -> str:
    return f"{timestamp.isoformat(timespec='seconds')} RX {line}"


async def _listen_stdin_loop(board: BoardSerial, stop_event: asyncio.Event) -> None:
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[str] = asyncio.Queue()

    def _stdin_worker() -> None:
        while not stop_event.is_set():
            line = sys.stdin.readline()
            loop.call_soon_threadsafe(queue.put_nowait, line)
            if line == "":
                return

    worker = threading.Thread(target=_stdin_worker, daemon=True, name="listen-stdin")
    worker.start()

    while not stop_event.is_set():
        try:
            line = await asyncio.wait_for(queue.get(), timeout=0.2)
        except asyncio.TimeoutError:
            continue
        if line == "":
            stop_event.set()
            return

        command = line.strip().lower()
        if not command:
            continue
        if command in {"1", "on", "led=1"}:
            await board.send_led(True)
            print("TX LED=1", flush=True)
            continue
        if command in {"0", "off", "led=0"}:
            await board.send_led(False)
            print("TX LED=0", flush=True)
            continue
        if command in {"q", "quit", "exit"}:
            stop_event.set()
            return

        print("Type 1 or 0 (or q to quit).", flush=True)


async def run_listen(settings: Settings) -> int:
    stop_event = asyncio.Event()
    board = BoardSerial(
        port=resolve_port(settings),
        baud=settings.baud,
        dedupe_ms=settings.dedupe_ms,
        on_raw_line=lambda timestamp, line: print(_format_raw_line(timestamp, line), flush=True),
        raw_logging=LOGGER.isEnabledFor(logging.DEBUG),
    )
    await board.open()
    print(f"Listening on {board.port} @ {settings.baud}. Type 1 or 0, q to quit.", flush=True)

    stdin_task = asyncio.create_task(_listen_stdin_loop(board, stop_event))
    try:
        while not stop_event.is_set():
            await asyncio.sleep(0.2)
            if board.reader_error is not None:
                raise SerialControllerError(f"Serial read failed: {board.reader_error}")
            if not board.is_open:
                raise SerialControllerError("Serial port closed unexpectedly.")
    finally:
        stop_event.set()
        stdin_task.cancel()
        with suppress(asyncio.CancelledError):
            await stdin_task
        await board.close()
    return 0


async def run_led(settings: Settings, led_state: str, *, wait_ack: bool) -> int:
    board = await open_board(settings)
    try:
        if led_state == "on":
            await board.send_led(True)
            print(f"Sent LED=1 to {board.port}")
        elif led_state == "off":
            await board.send_led(False)
            print(f"Sent LED=0 to {board.port}")
        else:
            await board.toggle_led()
            print(f"Sent LED=T to {board.port}")

        if wait_ack:
            event = await board.wait_event(kinds={EVENT_LED_STATE}, timeout=settings.ack_timeout)
            if event is None:
                print(f"No LED ack received within {settings.ack_timeout:.2f}s")
            else:
                print(format_event_line(event))
        return 0
    finally:
        await board.close()


async def run_status(settings: Settings, listen_seconds: float) -> int:
    if listen_seconds <= 0:
        raise SerialControllerError("--listen-seconds must be > 0.")

    board = await open_board(settings)
    try:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + listen_seconds
        while True:
            remaining = deadline - loop.time()
            if remaining <= 0:
                break
            _ = await board.wait_event(timeout=remaining)

        print(f"Port: {board.port}")
        switch_text = "unknown" if board.switch_state is None else str(int(board.switch_state))
        led_text = "unknown" if board.led_state is None else str(int(board.led_state))
        encoder_text = "unknown" if board.encoder_delta is None else str(board.encoder_delta)
        encoder_total = str(board.encoder_total)
        encoder_switch = "unknown" if board.encoder_switch_state is None else str(int(board.encoder_switch_state))
        print(f"Switch: {switch_text}")
        print(f"LED: {led_text}")
        print(f"ENC(last): {encoder_text}")
        print(f"ENC(total): {encoder_total}")
        print(f"ENC_SW: {encoder_switch}")
        return 0
    finally:
        await board.close()
