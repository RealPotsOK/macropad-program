from __future__ import annotations

import asyncio
import ctypes
from contextlib import suppress
import logging
import sys
from typing import Sequence

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication
from qasync import QEventLoop

from ..config import Settings
from .app_icon import build_app_icon
from .main_window import MacroPadMainWindow
from .theme import apply_saved_theme

LOGGER = logging.getLogger(__name__)


def _make_application() -> QApplication:
    if sys.platform == "win32":
        with suppress(Exception):
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("MacroPad.Controller")
    app = QApplication.instance()
    if app is None:
        app = QApplication([sys.argv[0]])
    app.setApplicationName("MacroPad Controller")
    app.setOrganizationName("MacroPad")
    app.setQuitOnLastWindowClosed(False)
    app.setFont(QFont("Segoe UI", 10))
    app.setWindowIcon(build_app_icon())
    return app


def _apply_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    apply_saved_theme(app)


def run_qt_app(
    settings: Settings,
    *,
    start_hidden: bool = False,
    launch_command: Sequence[str] | None = None,
    instance_guard: object | None = None,
) -> int:
    app = _make_application()
    _apply_theme(app)

    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    window = MacroPadMainWindow(
        settings,
        launch_command=launch_command,
        instance_guard=instance_guard,
    )

    exit_future = loop.create_future()

    def _finish(code: int) -> None:
        if not exit_future.done():
            exit_future.set_result(int(code))

    window.exitRequested.connect(_finish)
    app.aboutToQuit.connect(lambda: _finish(0))
    window.reconnectRequested.connect(lambda: LOGGER.info("Reconnect requested from Qt shell."))

    if instance_guard is not None and hasattr(instance_guard, "consume_restore_signal"):
        from PySide6.QtCore import QTimer

        window._restore_poller = QTimer(window)  # type: ignore[attr-defined]
        window._restore_poller.setInterval(500)  # type: ignore[attr-defined]
        window._restore_poller.timeout.connect(window.poll_restore_signal)  # type: ignore[attr-defined]
        window._restore_poller.start()  # type: ignore[attr-defined]

    with loop:
        loop.call_soon(lambda: window.startup(hidden=start_hidden))
        return int(loop.run_until_complete(exit_future))
