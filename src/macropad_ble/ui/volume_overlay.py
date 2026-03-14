from __future__ import annotations

from pathlib import Path
import tkinter as tk
from typing import Any

from PIL import Image, ImageDraw, ImageTk

from .volume_mixer import VolumeMixerResult
from .windows_icons import extract_file_icon

OVERLAY_BG = "#0B1020"
OVERLAY_BORDER = "#1E293B"
OVERLAY_BAR_BG = "#1F2937"
OVERLAY_BAR_FILL = "#22C55E"
OVERLAY_TEXT = "#F8FAFC"
OVERLAY_MUTED = "#CBD5E1"


class VolumeOverlayToast:
    def __init__(self, root: tk.Misc) -> None:
        self.root = root
        self._window: tk.Toplevel | None = None
        self._hide_after_id: str | None = None
        self._icon_label: tk.Label | None = None
        self._title_label: tk.Label | None = None
        self._bar_canvas: tk.Canvas | None = None
        self._bar_fill: int | None = None
        self._percent_label: tk.Label | None = None
        self._icon_photo: ImageTk.PhotoImage | None = None
        self._icon_cache: dict[tuple[str, int], ImageTk.PhotoImage] = {}

    def show(self, result: VolumeMixerResult) -> None:
        self._ensure_window()
        if self._window is None:
            return

        title = str(result.title or result.label or "Volume").strip()
        percent = max(0, min(100, int(result.volume_percent)))

        if self._title_label is not None:
            self._title_label.configure(text=title)
        if self._percent_label is not None:
            self._percent_label.configure(text=f"{percent}%")

        self._set_icon(title=title, icon_path=result.icon_path)
        self._set_progress(percent)
        self._position_window()

        self._window.deiconify()
        self._window.lift()
        with _suppress_tk():
            self._window.attributes("-topmost", True)

        if self._hide_after_id is not None:
            with _suppress_tk():
                self._window.after_cancel(self._hide_after_id)
        self._hide_after_id = self._window.after(1400, self.hide)

    def hide(self) -> None:
        if self._window is None:
            return
        if self._hide_after_id is not None:
            with _suppress_tk():
                self._window.after_cancel(self._hide_after_id)
        self._hide_after_id = None
        with _suppress_tk():
            self._window.withdraw()

    def destroy(self) -> None:
        self.hide()
        if self._window is not None:
            with _suppress_tk():
                self._window.destroy()
        self._window = None
        self._icon_photo = None
        self._icon_cache.clear()

    def _ensure_window(self) -> None:
        if self._window is not None:
            return

        window = tk.Toplevel(self.root)
        window.withdraw()
        window.overrideredirect(True)
        window.configure(bg=OVERLAY_BG)
        with _suppress_tk():
            window.attributes("-topmost", True)
            window.attributes("-alpha", 0.97)

        frame = tk.Frame(
            window,
            bg=OVERLAY_BG,
            highlightthickness=1,
            highlightbackground=OVERLAY_BORDER,
            padx=14,
            pady=12,
        )
        frame.pack(fill="both", expand=True)

        self._icon_label = tk.Label(
            frame,
            text="S",
            width=2,
            bg="#1DB954",
            fg="#FFFFFF",
            font=("Segoe UI Semibold", 12),
            relief="flat",
        )
        self._icon_label.grid(row=0, column=0, rowspan=2, sticky="nsw", padx=(0, 12))

        self._title_label = tk.Label(
            frame,
            text="Spotify",
            bg=OVERLAY_BG,
            fg=OVERLAY_TEXT,
            font=("Segoe UI Semibold", 10),
            anchor="w",
        )
        self._title_label.grid(row=0, column=1, sticky="sw")

        self._bar_canvas = tk.Canvas(
            frame,
            width=240,
            height=12,
            bg=OVERLAY_BG,
            bd=0,
            highlightthickness=0,
            relief="flat",
        )
        self._bar_canvas.grid(row=1, column=1, sticky="ew", pady=(4, 0))
        self._bar_canvas.create_rectangle(0, 0, 240, 12, fill=OVERLAY_BAR_BG, outline="")
        self._bar_fill = self._bar_canvas.create_rectangle(0, 0, 0, 12, fill=OVERLAY_BAR_FILL, outline="")

        self._percent_label = tk.Label(
            frame,
            text="0%",
            bg=OVERLAY_BG,
            fg=OVERLAY_MUTED,
            font=("Segoe UI Semibold", 11),
            anchor="e",
            width=4,
        )
        self._percent_label.grid(row=0, column=2, rowspan=2, sticky="nse", padx=(12, 0))

        frame.grid_columnconfigure(1, weight=1)
        self._window = window

    def _set_progress(self, percent: int) -> None:
        if self._bar_canvas is None or self._bar_fill is None:
            return
        width = int(self._bar_canvas.cget("width"))
        fill_width = int(round(width * (percent / 100.0)))
        self._bar_canvas.coords(self._bar_fill, 0, 0, fill_width, 12)

    def _set_icon(self, *, title: str, icon_path: str) -> None:
        if self._icon_label is None:
            return

        photo = None
        key = (str(Path(icon_path).expanduser()), 28)
        if icon_path:
            photo = self._icon_cache.get(key)
            if photo is None:
                image = extract_file_icon(icon_path, size=28)
                if image is not None:
                    photo = ImageTk.PhotoImage(image)
                    self._icon_cache[key] = photo
        if photo is not None:
            self._icon_photo = photo
            self._icon_label.configure(image=photo, text="", bg=OVERLAY_BG, width=28, height=28)
            return

        fallback = _fallback_icon_image(title, size=28)
        self._icon_photo = ImageTk.PhotoImage(fallback)
        self._icon_label.configure(image=self._icon_photo, text="", bg=OVERLAY_BG, width=28, height=28)

    def _position_window(self) -> None:
        if self._window is None:
            return
        self._window.update_idletasks()
        width = self._window.winfo_width()
        height = self._window.winfo_height()
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = max(0, (screen_width - width) // 2)
        y = max(0, screen_height - height - 88)
        self._window.geometry(f"+{x}+{y}")


def _fallback_icon_image(title: str, *, size: int) -> Image.Image:
    base = Image.new("RGBA", (size, size), "#2563EB")
    draw = ImageDraw.Draw(base)
    draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=8, fill="#2563EB")
    letter = (title.strip()[:1] or "?").upper()
    draw.text((size // 2, size // 2), letter, fill="#FFFFFF", anchor="mm")
    return base


class _suppress_tk:
    def __enter__(self) -> None:
        return None

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        return exc_type is tk.TclError
