from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import threading
from contextlib import suppress
from pathlib import Path
from typing import Any

from .board_serial import (
    EVENT_LED_STATE,
    EVENT_READY,
    EVENT_SW_CHANGED,
    BoardEvent,
    BoardSerial,
    PortSelectionError,
    SerialControllerError,
    format_port_table,
    list_serial_ports,
    monitor_with_reconnect,
    resolve_port,
)
from .config import Settings, load_settings

LOGGER = logging.getLogger(__name__)


def _add_common_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--config", type=Path, default=argparse.SUPPRESS, help="Path to TOML config file."
    )
    parser.add_argument(
        "--port",
        default=argparse.SUPPRESS,
        help="Explicit serial port (example: COM12).",
    )
    parser.add_argument(
        "--hint",
        default=argparse.SUPPRESS,
        help="Case-insensitive substring matched against serial port description/HWID/manufacturer.",
    )
    parser.add_argument("--baud", type=int, default=argparse.SUPPRESS, help="Serial baud rate.")
    parser.add_argument(
        "--ack-timeout",
        type=float,
        default=argparse.SUPPRESS,
        help="Seconds to wait for LED state ack.",
    )
    parser.add_argument(
        "--dedupe-ms",
        type=int,
        default=argparse.SUPPRESS,
        help="Ignore duplicate SW events within this window (0 to disable, otherwise 50-150).",
    )
    parser.add_argument(
        "--log-level",
        "--log",
        dest="log_level",
        default=argparse.SUPPRESS,
        help="Logging level.",
    )


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    _add_common_options(common)

    parser = argparse.ArgumentParser(
        prog="macropad-ble",
        description="Serial controller for ATmega macropad boards.",
        parents=[common],
    )

    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list", help="List available serial ports.", parents=[common])
    subparsers.add_parser("monitor", help="Monitor serial events with auto-reconnect.", parents=[common])
    subparsers.add_parser(
        "listen",
        help="Listen to raw serial lines and allow interactive LED 1/0 input.",
        parents=[common],
    )

    led_parser = subparsers.add_parser("led", help="Send LED commands.", parents=[common])
    led_parser.add_argument("led_state", choices=("on", "off", "toggle"))
    led_parser.add_argument(
        "--no-wait-ack",
        action="store_true",
        help="Do not wait for LED=<0|1> acknowledgement before exiting.",
    )

    status_parser = subparsers.add_parser(
        "status", help="Print last known switch/LED state.", parents=[common]
    )
    status_parser.add_argument(
        "--listen-seconds",
        type=float,
        default=1.0,
        help="How long to listen for incoming state lines before printing status.",
    )

    return parser


def cli_overrides_from_args(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "port": getattr(args, "port", None),
        "hint": getattr(args, "hint", None),
        "baud": getattr(args, "baud", None),
        "ack_timeout": getattr(args, "ack_timeout", None),
        "dedupe_ms": getattr(args, "dedupe_ms", None),
        "log_level": getattr(args, "log_level", None),
    }


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def _event_line(event: BoardEvent) -> str:
    stamp = event.timestamp.isoformat(timespec="seconds")
    if event.kind == EVENT_READY:
        return f"{stamp} READY"
    if event.kind == EVENT_SW_CHANGED:
        return f"{stamp} SW={1 if event.value else 0}"
    if event.kind == EVENT_LED_STATE:
        return f"{stamp} LED={1 if event.value else 0}"
    return f"{stamp} {event.raw_line}"


async def _open_board(settings: Settings) -> BoardSerial:
    port = resolve_port(settings)
    board = BoardSerial(
        port=port,
        baud=settings.baud,
        dedupe_ms=settings.dedupe_ms,
        raw_logging=LOGGER.isEnabledFor(logging.DEBUG),
    )
    await board.open()
    return board


async def _run_list() -> int:
    ports = list_serial_ports()
    if not ports:
        print("No serial ports found.")
        return 0
    print(format_port_table(ports))
    return 0


async def _run_monitor(settings: Settings) -> int:
    print("Monitoring serial events. Press Ctrl+C to stop.")
    stop_event = asyncio.Event()
    await monitor_with_reconnect(
        settings,
        on_event=lambda event: print(_event_line(event), flush=True),
        stop_event=stop_event,
    )
    return 0


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


async def _run_listen(settings: Settings) -> int:
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


async def _run_led(settings: Settings, led_state: str, *, wait_ack: bool) -> int:
    board = await _open_board(settings)
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
                print(_event_line(event))
        return 0
    finally:
        await board.close()


async def _run_status(settings: Settings, listen_seconds: float) -> int:
    if listen_seconds <= 0:
        raise SerialControllerError("--listen-seconds must be > 0.")

    board = await _open_board(settings)
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
        print(f"Switch: {switch_text}")
        print(f"LED: {led_text}")
        return 0
    finally:
        await board.close()


async def _dispatch(args: argparse.Namespace, settings: Settings) -> int:
    if args.command == "list":
        return await _run_list()
    if args.command == "monitor":
        return await _run_monitor(settings)
    if args.command == "listen":
        return await _run_listen(settings)
    if args.command == "led":
        return await _run_led(settings, args.led_state, wait_ack=not args.no_wait_ack)
    if args.command == "status":
        return await _run_status(settings, args.listen_seconds)
    raise SerialControllerError(f"Unknown command: {args.command}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        settings = load_settings(
            config_path=getattr(args, "config", None),
            cli_overrides=cli_overrides_from_args(args),
        )
    except Exception as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    configure_logging(settings.log_level)

    try:
        return asyncio.run(_dispatch(args, settings))
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return 130
    except (PortSelectionError, SerialControllerError) as exc:
        LOGGER.error("%s", exc)
        return 1
    except Exception as exc:  # pragma: no cover - defensive safety net
        LOGGER.exception("Unhandled error: %s", exc)
        return 1
