from __future__ import annotations

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from ..app_icon import build_app_icon


class TrayService(QObject):
    openRequested = Signal()
    reconnectRequested = Signal()
    toggleAutostartRequested = Signal()
    exitRequested = Signal()

    def __init__(self, *, app_name: str = "MacroPad Controller", parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.app_name = app_name
        self.tray = QSystemTrayIcon(self._build_icon(), self)
        self.menu = QMenu()
        self.open_action = QAction("Open", self.menu)
        self.reconnect_action = QAction("Reconnect", self.menu)
        self.autostart_action = QAction("Launch on Windows startup", self.menu)
        self.exit_action = QAction("Exit", self.menu)
        self.autostart_action.setCheckable(True)

        self.menu.addAction(self.open_action)
        self.menu.addAction(self.reconnect_action)
        self.menu.addSeparator()
        self.menu.addAction(self.autostart_action)
        self.menu.addSeparator()
        self.menu.addAction(self.exit_action)
        self.tray.setContextMenu(self.menu)
        self.tray.setToolTip(self.app_name)

        self.open_action.triggered.connect(self.openRequested.emit)
        self.reconnect_action.triggered.connect(self.reconnectRequested.emit)
        self.autostart_action.triggered.connect(self.toggleAutostartRequested.emit)
        self.exit_action.triggered.connect(self.exitRequested.emit)
        self.tray.activated.connect(self._on_activated)

    def start(self) -> bool:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return False
        self.tray.show()
        return True

    def stop(self) -> None:
        self.tray.hide()

    def set_autostart_enabled(self, enabled: bool) -> None:
        self.autostart_action.setChecked(bool(enabled))

    def show_message(self, title: str, message: str) -> None:
        self.tray.showMessage(title, message, QSystemTrayIcon.Information, 2000)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in {QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick}:
            self.openRequested.emit()

    def _build_icon(self) -> QIcon:
        return build_app_icon(size=64)
