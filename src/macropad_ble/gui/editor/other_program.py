from __future__ import annotations

import argparse
import asyncio

from ...config import Settings
from ...serial import PortSelectionError, SerialControllerError, resolve_port
from ...ui.key_layout import KEY_DISPLAY_MAP


def _grid_size_from_layout() -> tuple[int, int]:
    if not KEY_DISPLAY_MAP:
        return (3, 4)
    max_row = max(key[0] for key in KEY_DISPLAY_MAP.keys())
    max_col = max(key[1] for key in KEY_DISPLAY_MAP.keys())
    return (max_row + 1, max_col + 1)


def _build_args(settings: Settings) -> argparse.Namespace:
    port = ""
    if settings.port or settings.hint:
        try:
            port = resolve_port(settings)
        except PortSelectionError as exc:
            raise SerialControllerError(str(exc)) from exc

    rows, cols = _grid_size_from_layout()
    return argparse.Namespace(
        port=port,
        baud=settings.baud,
        rows=rows,
        cols=cols,
        fps=60,
        width=1280,
        height=760,
        padding=48,
        gap=16,
    )


async def run_key_window(settings: Settings) -> int:
    try:
        from ...pygame_continuous_ui import run as run_pygame_ui
    except ModuleNotFoundError as exc:
        raise SerialControllerError(
            "GUI requires pygame-ce + numpy. Install with: pip install -e .[ui]"
        ) from exc

    args = _build_args(settings)
    return await asyncio.to_thread(run_pygame_ui, args)

