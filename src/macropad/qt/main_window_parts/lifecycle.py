from __future__ import annotations

import asyncio
import logging

from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication

from ...platform.autostart import is_autostart_enabled, set_autostart_enabled
from ..theme import apply_theme

LOGGER = logging.getLogger(__name__)


class MainWindowLifecycleMixin:
    def _build_tray(self) -> None:
        tray = self._tray_service_cls()
        tray.openRequested.connect(self.show_window)
        tray.reconnectRequested.connect(self.request_reconnect)
        tray.toggleAutostartRequested.connect(self.toggle_autostart)
        tray.exitRequested.connect(self.request_exit)
        tray.set_autostart_enabled(is_autostart_enabled())
        self._tray_available = tray.start()
        self._tray = tray if self._tray_available else None

    def startup(self, *, hidden: bool = False) -> None:
        self._hidden_start = bool(hidden)
        refresh_ports = getattr(self.controller, "refresh_ports", None)
        if callable(refresh_ports):
            refresh_ports()
        self._update_hidden_label()
        if hidden:
            self.hide_to_tray(initial=True)
        else:
            self.show_window()

        auto_connect = getattr(self.controller, "auto_connect_if_enabled", None)
        if callable(auto_connect):
            try:
                task = auto_connect(hidden_start=hidden)
            except TypeError:
                task = auto_connect()
            if asyncio.iscoroutine(task):
                asyncio.create_task(task)

    def show_window(self) -> None:
        self._allow_close = False
        self._hidden_start = False
        self._update_hidden_label()
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def hide_to_tray(self, *, initial: bool = False) -> None:
        self._hidden_start = True
        self._update_hidden_label()
        if self._tray_available and self._tray is not None:
            self.hide()
            if not initial:
                self._tray.show_message("MacroPad Controller", "Still running in the tray.")
        else:
            self.showMinimized()

    def request_reconnect(self) -> None:
        self.reconnectRequested.emit()
        reconnect = getattr(self.controller, "reconnect", None)
        if callable(reconnect):
            result = reconnect()
            if asyncio.iscoroutine(result):
                asyncio.create_task(result)

    def request_exit(self) -> None:
        self._allow_close = True
        asyncio.create_task(self.shutdown_async())

    def toggle_autostart(self) -> None:
        if not self._launch_command:
            self._status_message.setText("Autostart command unavailable.")
            return
        enabled = not is_autostart_enabled()
        if set_autostart_enabled(enabled, command=self._launch_command):
            if self._tray is not None:
                self._tray.set_autostart_enabled(enabled)
            self._status_message.setText("Windows startup enabled." if enabled else "Windows startup disabled.")

    def poll_restore_signal(self) -> None:
        guard = self._instance_guard
        if guard is None or not hasattr(guard, "consume_restore_signal"):
            return
        try:
            should_restore = bool(guard.consume_restore_signal())
        except Exception:
            LOGGER.exception("Failed to poll restore signal.")
            return
        if should_restore:
            self.show_window()

    async def shutdown_async(self) -> None:
        self._allow_close = True
        if self._tray is not None:
            self._tray.stop()
        shutdown = getattr(self.controller, "shutdown", None)
        if callable(shutdown):
            result = shutdown()
            if asyncio.iscoroutine(result):
                await result
        if self._instance_guard is not None:
            self._instance_guard.close()
        self.exitRequested.emit(0)
        QApplication.instance().quit()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._allow_close:
            event.accept()
            return
        event.ignore()
        self.hide_to_tray()

    def _show_volume_overlay(self, result) -> None:
        self.overlay.show_result(result)

    def _apply_theme_settings(self, settings) -> None:
        app = QApplication.instance()
        if app is None:
            return
        apply_theme(app, settings)
