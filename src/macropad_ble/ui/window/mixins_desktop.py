from __future__ import annotations

import queue

from ...desktop import (
    TrayController,
    is_autostart_enabled,
    set_autostart_enabled,
)
from .shared import *


class DesktopMixin:
    def _initialize_desktop_mode(self) -> None:
        self._tray_controller = TrayController(
            app_name="MacroPad Controller",
            dispatch=self._enqueue_tray_callback,
            on_open=self._restore_from_tray,
            on_reconnect=lambda: self._spawn(self._reconnect_from_tray()),
            on_toggle_autostart=self._toggle_autostart,
            on_exit=self._request_exit,
            is_autostart_enabled=self._is_autostart_enabled,
        )
        self._tray_available = self._tray_controller.start()

        if self._start_hidden:
            if self._tray_available:
                self._hide_to_tray(log_message=False)
            else:
                self._window_hidden = False
                with suppress(Exception):
                    self.root.deiconify()
                self._log("Tray support unavailable; started with the window visible.")

    def _enqueue_tray_callback(self, callback) -> None:
        self._tray_dispatch_queue.put(callback)

    def _on_window_close(self) -> None:
        self._hide_to_tray()

    def _hide_to_tray(self, *, log_message: bool = True) -> None:
        if self._closing:
            return
        if not self._tray_available:
            self._window_hidden = False
            with suppress(Exception):
                self.root.iconify()
            if log_message:
                self._log("Tray support unavailable; minimized to the taskbar.")
            return

        self._window_hidden = True
        with suppress(Exception):
            self.root.withdraw()
        if log_message:
            self._log("Window hidden to tray.")

    def _restore_from_tray(self) -> None:
        if self._closing:
            return

        self._window_hidden = False
        with suppress(Exception):
            self.root.deiconify()
            self.root.state("normal")
            self.root.lift()
            self.root.focus_force()
            self.root.attributes("-topmost", True)
            self.root.after(150, lambda: self.root.attributes("-topmost", False))

    async def _reconnect_from_tray(self) -> None:
        await self._disconnect()
        await self._connect()

    def _request_exit(self) -> None:
        if self._closing:
            return
        self._prepare_exit()
        self._window_hidden = False

    def _is_autostart_enabled(self) -> bool:
        return is_autostart_enabled()

    def _toggle_autostart(self) -> None:
        if not self._autostart_command:
            self._log("Autostart toggle skipped: launch command is unavailable.")
            return

        enabled = not is_autostart_enabled()
        set_autostart_enabled(enabled, command=self._autostart_command)
        state_text = "enabled" if enabled else "disabled"
        self._log(f"Windows startup {state_text}.")
        if self._tray_controller is not None:
            self._tray_controller.refresh()

    def _poll_desktop_events(self) -> None:
        while True:
            try:
                callback = self._tray_dispatch_queue.get_nowait()
            except queue.Empty:
                break
            with suppress(Exception):
                callback()

        guard = self._instance_guard
        if guard is None:
            return
        if guard.consume_restore_signal():
            self._restore_from_tray()

    def _shutdown_desktop_resources(self) -> None:
        tray = self._tray_controller
        self._tray_controller = None
        if tray is not None:
            tray.stop()
        guard = self._instance_guard
        self._instance_guard = None
        if guard is not None:
            guard.close()
