from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from .cli import _add_common_options, cli_overrides_from_args, configure_logging
from .commands import run_gui
from .config import load_settings
from .desktop import SingleInstanceGuard
from .serial import PortSelectionError, SerialControllerError

APP_ID = "MacroPadController"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="macropad-controller")
    parser.add_argument("--config", type=Path, default=None, help="Path to TOML config file.")
    parser.add_argument(
        "--hidden",
        action="store_true",
        help="Launch hidden to the system tray.",
    )
    _add_common_options(parser)
    return parser


def _launch_command_tokens(*, hidden: bool) -> list[str]:
    if getattr(sys, "frozen", False):
        command = [str(Path(sys.executable).resolve())]
    else:
        argv0 = Path(sys.argv[0]) if sys.argv else Path(sys.executable)
        if argv0.suffix.lower() == ".exe":
            command = [str(argv0.resolve())]
        else:
            command = [str(Path(sys.executable).resolve()), "-m", "macropad_ble.gui_app"]
    if hidden:
        command.append("--hidden")
    return command


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    guard = SingleInstanceGuard(APP_ID)

    try:
        settings = load_settings(
            config_path=args.config,
            cli_overrides=cli_overrides_from_args(args),
        )
        configure_logging(settings.log_level)

        if guard.acquire() is False:
            guard.signal_restore()
            logging.getLogger(__name__).info("Existing MacroPad Controller instance restored.")
            return 0

        return asyncio.run(
            run_gui(
                settings,
                start_hidden=bool(args.hidden),
                launch_command=_launch_command_tokens(hidden=True),
                instance_guard=guard,
            )
        )
    except KeyboardInterrupt:
        return 130
    except (FileNotFoundError, PortSelectionError, SerialControllerError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    finally:
        guard.close()


if __name__ == "__main__":
    raise SystemExit(main())
