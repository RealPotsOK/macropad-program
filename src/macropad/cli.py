from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import Any

from .commands import run_gui, run_led, run_list, run_listen, run_monitor, run_status
from .config import Settings, load_settings
from .serial import PortSelectionError, SerialControllerError


def _add_common_options(
    parser: argparse.ArgumentParser,
    *,
    default: Any = argparse.SUPPRESS,
) -> None:
    parser.add_argument("--port", default=default, help="Serial port (example: COM13, /dev/ttyACM0).")
    parser.add_argument(
        "--hint",
        default=default,
        help="Substring to match in port description/HWID/manufacturer.",
    )
    parser.add_argument("--baud", type=int, default=default, help="Serial baud rate.")
    parser.add_argument(
        "--ack-timeout",
        dest="ack_timeout",
        type=float,
        default=default,
        help="Seconds to wait for LED ack events.",
    )
    parser.add_argument(
        "--dedupe-ms",
        dest="dedupe_ms",
        type=int,
        default=default,
        help="Ignore duplicate SW events within this window (0 to disable).",
    )
    parser.add_argument(
        "--log",
        "--log-level",
        dest="log_level",
        default=default,
        metavar="LEVEL",
        help="Logging level: CRITICAL, ERROR, WARNING, INFO, DEBUG.",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="macropad")
    parser.add_argument("--config", type=Path, default=None, help="Path to TOML config file.")
    _add_common_options(parser)

    # Re-add the same flags on each subcommand so users can place options
    # either before or after command names.
    command_common = argparse.ArgumentParser(add_help=False)
    _add_common_options(command_common)

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", parents=[command_common], help="List serial ports.")
    subparsers.add_parser(
        "monitor",
        parents=[command_common],
        help="Monitor board events with auto-reconnect.",
    )
    subparsers.add_parser(
        "gui",
        parents=[command_common],
        help="Open a 12-key live view window.",
    )
    subparsers.add_parser(
        "listen",
        parents=[command_common],
        help="Print all RX lines; type 1/0 to send LED commands.",
    )

    led_parser = subparsers.add_parser("led", parents=[command_common], help="Send LED command.")
    led_parser.add_argument("led_state", choices=("on", "off", "toggle"))
    led_parser.add_argument(
        "--wait-ack",
        action="store_true",
        help="Wait for LED=0/1 response before exiting.",
    )

    status_parser = subparsers.add_parser(
        "status",
        parents=[command_common],
        help="Show last known SW/LED state from short listen window.",
    )
    status_parser.add_argument(
        "--listen-seconds",
        type=float,
        default=0.35,
        help="How long to listen before printing state.",
    )

    return parser


def cli_overrides_from_args(args: argparse.Namespace) -> dict[str, Any]:
    keys = ("port", "hint", "baud", "ack_timeout", "dedupe_ms", "log_level")
    overrides: dict[str, Any] = {}
    for key in keys:
        if hasattr(args, key):
            value = getattr(args, key)
            if value is not None:
                overrides[key] = value
    return overrides


def configure_logging(log_level: str) -> None:
    level_name = str(log_level).upper().strip()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


async def _run_command(args: argparse.Namespace, settings: Settings) -> int:
    command = args.command

    if command == "list":
        return await run_list()
    if command == "monitor":
        return await run_monitor(settings)
    if command == "gui":
        return run_gui(settings)
    if command == "listen":
        return await run_listen(settings)
    if command == "led":
        return await run_led(settings, args.led_state, wait_ack=bool(args.wait_ack))
    if command == "status":
        return await run_status(settings, listen_seconds=float(args.listen_seconds))

    raise SerialControllerError(f"Unknown command: {command}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        settings = load_settings(
            config_path=args.config,
            cli_overrides=cli_overrides_from_args(args),
        )
        configure_logging(settings.log_level)
        return asyncio.run(_run_command(args, settings))
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130
    except (FileNotFoundError, PortSelectionError, SerialControllerError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
