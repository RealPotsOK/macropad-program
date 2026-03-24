from __future__ import annotations

import argparse
import queue
import threading
import time
from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pygame
import serial

from .serial import EVENT_ENC_DELTA, EVENT_KEY_STATE, BoardEvent, parse_event_line


@dataclass(frozen=True, slots=True)
class KeyRect:
    row: int
    col: int
    rect: pygame.Rect


class SerialEventReader(threading.Thread):
    def __init__(self, *, port: str, baud: int, out_queue: queue.Queue[BoardEvent]) -> None:
        super().__init__(daemon=True, name="macropad-serial-reader")
        self.port = port
        self.baud = baud
        self.out_queue = out_queue
        self._stop = threading.Event()

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        while not self._stop.is_set():
            try:
                with serial.Serial(self.port, self.baud, timeout=0.25) as handle:
                    while not self._stop.is_set():
                        raw = handle.readline()
                        if not raw:
                            continue
                        line = raw.decode("ascii", errors="ignore").strip()
                        if not line:
                            continue
                        event = parse_event_line(line)
                        if event is not None:
                            self.out_queue.put(event)
            except Exception:
                if self._stop.is_set():
                    break
                time.sleep(1.0)


def _compute_grid(
    *,
    screen_size: tuple[int, int],
    rows: int,
    cols: int,
    outer_padding: int,
    gap: int,
) -> tuple[pygame.Rect, list[KeyRect]]:
    width, height = screen_size
    available_w = max(10, width - 2 * outer_padding)
    available_h = max(10, height - 2 * outer_padding)

    tile_w = (available_w - gap * (cols - 1)) / max(1, cols)
    tile_h = (available_h - gap * (rows - 1)) / max(1, rows)
    tile_w = int(max(40, tile_w))
    tile_h = int(max(40, tile_h))

    total_w = tile_w * cols + gap * (cols - 1)
    total_h = tile_h * rows + gap * (rows - 1)

    grid_left = (width - total_w) // 2
    grid_top = (height - total_h) // 2
    grid_rect = pygame.Rect(grid_left, grid_top, total_w, total_h)

    rects: list[KeyRect] = []
    for row in range(rows):
        for col in range(cols):
            visual_row = rows - 1 - row
            x = grid_left + col * (tile_w + gap)
            y = grid_top + visual_row * (tile_h + gap)
            rects.append(KeyRect(row=row, col=col, rect=pygame.Rect(x, y, tile_w, tile_h)))
    return grid_rect, rects


def _prepare_coords(size: tuple[int, int]) -> tuple[np.ndarray, np.ndarray]:
    w, h = size
    x = np.linspace(-1.0, 1.0, w, dtype=np.float32)
    y = np.linspace(-1.0, 1.0, h, dtype=np.float32)
    xx, yy = np.meshgrid(x, y, indexing="xy")
    return xx, yy


def _draw_bg(surface: pygame.Surface, *, t: float, xx: np.ndarray, yy: np.ndarray) -> None:
    c1 = np.array([37.0, 99.0, 235.0], dtype=np.float32)
    c2 = np.array([132.0, 204.0, 22.0], dtype=np.float32)
    c3 = np.array([14.0, 165.0, 233.0], dtype=np.float32)

    cx1 = 0.55 * np.sin(t * 0.33)
    cy1 = 0.45 * np.cos(t * 0.29)
    cx2 = 0.52 * np.cos(t * 0.21 + 1.2)
    cy2 = 0.45 * np.sin(t * 0.27 + 2.1)
    cx3 = 0.48 * np.sin(t * 0.19 + 2.8)
    cy3 = 0.42 * np.cos(t * 0.31 + 0.6)

    blob1 = np.exp(-((xx - cx1) ** 2 + (yy - cy1) ** 2) / 0.28)
    blob2 = np.exp(-((xx - cx2) ** 2 + (yy - cy2) ** 2) / 0.22)
    blob3 = np.exp(-((xx - cx3) ** 2 + (yy - cy3) ** 2) / 0.20)

    wave1 = 0.5 + 0.5 * np.sin(2.7 * xx + 1.8 * yy + t * 1.25)
    wave2 = 0.5 + 0.5 * np.sin(-1.7 * xx + 2.4 * yy - t * 0.85)

    m1 = np.clip(0.35 * wave1 + 0.5 * blob1 + 0.35 * blob2, 0.0, 1.0)
    m2 = np.clip(0.40 * wave2 + 0.5 * blob3 + 0.2 * blob1, 0.0, 1.0)

    rgb = c1 * (1.0 - m1[..., None]) + c2 * m1[..., None]
    rgb = rgb * (1.0 - 0.42 * m2[..., None]) + c3 * (0.42 * m2[..., None])
    rgb = np.clip(rgb, 0.0, 255.0).astype(np.uint8)

    pygame.surfarray.blit_array(surface, rgb.swapaxes(0, 1))


def _apply_events(
    *,
    events: Iterable[BoardEvent],
    key_state: dict[tuple[int, int], bool],
    rows: int,
    cols: int,
    enc_state: dict[str, int],
) -> None:
    for event in events:
        if event.kind == EVENT_KEY_STATE and event.row is not None and event.col is not None:
            if 0 <= event.row < rows and 0 <= event.col < cols:
                key_state[(event.row, event.col)] = bool(event.value)
        elif event.kind == EVENT_ENC_DELTA and event.delta is not None:
            enc_state["last"] = int(event.delta)
            enc_state["total"] += int(event.delta)


def run(args: argparse.Namespace) -> int:
    pygame.init()
    pygame.font.init()

    flags = pygame.RESIZABLE
    try:
        screen = pygame.display.set_mode((args.width, args.height), flags, vsync=1)
    except TypeError:
        screen = pygame.display.set_mode((args.width, args.height), flags)
    pygame.display.set_caption("Macropad Continuous Gradient UI")

    clock = pygame.time.Clock()
    fps = max(30, min(240, int(args.fps)))

    title_font = pygame.font.SysFont("Segoe UI", 24, bold=True)
    key_font = pygame.font.SysFont("Segoe UI", 22, bold=True)
    state_font = pygame.font.SysFont("Segoe UI", 19, bold=True)
    badge_font = pygame.font.SysFont("Segoe UI", 14, bold=True)
    info_font = pygame.font.SysFont("Consolas", 18)

    key_state = {(row, col): False for row in range(args.rows) for col in range(args.cols)}
    enc_state = {"last": 0, "total": 0}

    grid_rect, key_rects = _compute_grid(
        screen_size=screen.get_size(),
        rows=args.rows,
        cols=args.cols,
        outer_padding=args.padding,
        gap=args.gap,
    )
    bg_surface = pygame.Surface(grid_rect.size).convert()
    xx, yy = _prepare_coords(grid_rect.size)
    overlay = pygame.Surface((1, 1), pygame.SRCALPHA)
    overlay.fill((6, 10, 18, 86))

    event_queue: queue.Queue[BoardEvent] = queue.Queue()
    reader: SerialEventReader | None = None
    if args.port:
        reader = SerialEventReader(port=args.port, baud=args.baud, out_queue=event_queue)
        reader.start()

    running = True
    while running:
        frame_events = []
        while True:
            try:
                frame_events.append(event_queue.get_nowait())
            except queue.Empty:
                break
        _apply_events(
            events=frame_events,
            key_state=key_state,
            rows=args.rows,
            cols=args.cols,
            enc_state=enc_state,
        )

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.VIDEORESIZE:
                screen = pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE)
                grid_rect, key_rects = _compute_grid(
                    screen_size=screen.get_size(),
                    rows=args.rows,
                    cols=args.cols,
                    outer_padding=args.padding,
                    gap=args.gap,
                )
                bg_surface = pygame.Surface(grid_rect.size).convert()
                xx, yy = _prepare_coords(grid_rect.size)
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False

        t = pygame.time.get_ticks() / 1000.0
        _draw_bg(bg_surface, t=t, xx=xx, yy=yy)

        screen.fill((2, 6, 18))

        title = title_font.render("Macro Pad - Continuous Gradient", True, (220, 232, 255))
        screen.blit(title, (18, 14))

        for key in key_rects:
            local_rect = key.rect.move(-grid_rect.left, -grid_rect.top)
            tile = bg_surface.subsurface(local_rect).copy()
            tile.blit(pygame.transform.scale(overlay, tile.get_size()), (0, 0))
            pygame.draw.rect(tile, (0, 0, 0), tile.get_rect(), width=1)

            pressed = key_state[(key.row, key.col)]
            key_text = key_font.render(f"Key {key.row},{key.col}", True, (237, 245, 255))
            state_text = state_font.render("DOWN" if pressed else "UP", True, (174, 255, 198) if pressed else (219, 228, 245))
            badge_text = badge_font.render(f"R{key.row} C{key.col}", True, (240, 247, 255))

            tile.blit(key_text, key_text.get_rect(center=(tile.get_width() // 2, int(tile.get_height() * 0.46))))
            tile.blit(state_text, state_text.get_rect(center=(tile.get_width() // 2, int(tile.get_height() * 0.74))))
            tile.blit(badge_text, badge_text.get_rect(topright=(tile.get_width() - 8, 8)))

            screen.blit(tile, key.rect.topleft)

        port_text = args.port if args.port else "simulation"
        info = info_font.render(
            f"Port: {port_text}  ENC(last): {enc_state['last']:+d}  ENC(total): {enc_state['total']:+d}  FPS: {clock.get_fps():.1f}",
            True,
            (196, 212, 248),
        )
        screen.blit(info, (18, screen.get_height() - 36))

        pygame.display.flip()
        clock.tick(fps)

    if reader is not None:
        reader.stop()
        reader.join(timeout=1.5)
    pygame.quit()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Pygame continuous-gradient macropad grid demo.")
    parser.add_argument("--port", default="", help="Serial port to read KEY/ENC lines (optional).")
    parser.add_argument("--baud", type=int, default=9600, help="Serial baud.")
    parser.add_argument("--rows", type=int, default=3, help="Grid rows.")
    parser.add_argument("--cols", type=int, default=4, help="Grid columns.")
    parser.add_argument("--fps", type=int, default=60, help="Target FPS (>=30 recommended).")
    parser.add_argument("--width", type=int, default=1280, help="Window width.")
    parser.add_argument("--height", type=int, default=760, help="Window height.")
    parser.add_argument("--padding", type=int, default=48, help="Outer padding around grid.")
    parser.add_argument("--gap", type=int, default=16, help="Gap between key tiles.")
    return parser


def main(argv: list[str] | None = None) -> int:
    return run(build_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
