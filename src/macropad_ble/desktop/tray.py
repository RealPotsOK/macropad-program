from __future__ import annotations

import sys
import threading
from typing import Callable

DispatchFn = Callable[[Callable[[], None]], None]


class TrayController:
    def __init__(
        self,
        *,
        app_name: str,
        dispatch: DispatchFn,
        on_open: Callable[[], None],
        on_reconnect: Callable[[], None],
        on_toggle_autostart: Callable[[], None],
        on_exit: Callable[[], None],
        is_autostart_enabled: Callable[[], bool],
    ) -> None:
        self.app_name = app_name
        self._dispatch = dispatch
        self._on_open = on_open
        self._on_reconnect = on_reconnect
        self._on_toggle_autostart = on_toggle_autostart
        self._on_exit = on_exit
        self._is_autostart_enabled = is_autostart_enabled
        self._icon = None
        self._thread: threading.Thread | None = None

    @property
    def supported(self) -> bool:
        return sys.platform == "win32"

    def start(self) -> bool:
        if not self.supported or self._icon is not None:
            return False
        pystray, image = self._load_dependencies()
        if pystray is None or image is None:
            return False

        self._icon = pystray.Icon(
            self.app_name,
            image,
            self.app_name,
            self._build_menu(pystray),
        )
        self._thread = threading.Thread(
            target=self._icon.run,
            daemon=True,
            name="macropad-tray",
        )
        self._thread.start()
        return True

    def refresh(self) -> None:
        icon = self._icon
        if icon is None:
            return
        try:
            icon.update_menu()
        except Exception:
            return

    def stop(self) -> None:
        icon = self._icon
        thread = self._thread
        self._icon = None
        self._thread = None
        if icon is not None:
            try:
                icon.stop()
            except Exception:
                pass
        if thread is not None and thread.is_alive():
            thread.join(timeout=1.0)

    def _build_menu(self, pystray: object) -> object:
        menu = pystray.Menu  # type: ignore[attr-defined]
        item = pystray.MenuItem  # type: ignore[attr-defined]
        return menu(
            item("Open", self._wrap(self._on_open), default=True),
            item("Reconnect", self._wrap(self._on_reconnect)),
            item(
                "Launch on Windows startup",
                self._wrap(self._on_toggle_autostart),
                checked=lambda _menu_item: bool(self._is_autostart_enabled()),
            ),
            item("Exit", self._wrap(self._on_exit)),
        )

    def _wrap(self, callback: Callable[[], None]) -> Callable[[object, object], None]:
        def _inner(_icon: object, _item: object) -> None:
            self._dispatch(callback)

        return _inner

    def _load_dependencies(self) -> tuple[object | None, object | None]:
        try:
            import pystray  # type: ignore
            from PIL import Image, ImageDraw  # type: ignore
        except Exception:
            return (None, None)

        image = Image.new("RGBA", (64, 64), (5, 10, 25, 255))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((6, 6, 58, 58), radius=12, fill=(14, 28, 56, 255), outline=(147, 197, 253, 255), width=3)
        draw.rectangle((20, 16, 28, 48), fill=(96, 165, 250, 255))
        draw.rectangle((36, 16, 44, 48), fill=(74, 222, 128, 255))
        return (pystray, image)
