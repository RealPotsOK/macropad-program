from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, QTimer, Signal
from PySide6.QtWidgets import QMainWindow

from ..config import Settings
from ..platform.single_instance import SingleInstanceGuard
from .app_icon import build_app_icon
from .controllers.runtime import QtSessionController
from .main_window_parts import (
    MainWindowControllerMixin,
    MainWindowHelpersMixin,
    MainWindowLifecycleMixin,
    MainWindowUiMixin,
)
from .pages.controller_page import ControllerPage
from .pages.personalization_page import PersonalizationPage
from .pages.profiles_page import ProfilesPage
from .pages.scripts_page import ScriptsPage
from .pages.setup_page import SetupPage
from .pages.stats_page import StatsPage
from .services.audio_player import AudioPlaybackService
from .services.tray_service import TrayService
from .services.volume_overlay import VolumeOverlayToast


class MacroPadMainWindow(
    MainWindowUiMixin,
    MainWindowControllerMixin,
    MainWindowHelpersMixin,
    MainWindowLifecycleMixin,
    QMainWindow,
):
    exitRequested = Signal(int)
    reconnectRequested = Signal()

    def __init__(
        self,
        settings: Settings,
        *,
        launch_command: list[str] | None = None,
        instance_guard: SingleInstanceGuard | None = None,
    ) -> None:
        super().__init__()
        self.settings = settings
        self._launch_command = [str(part) for part in (launch_command or []) if str(part).strip()]
        self._instance_guard = instance_guard
        self._allow_close = False
        self._tray_available = False
        self._tray = None
        self._restore_timer: QTimer | None = None
        self._hidden_start = False
        self._connection_state = "disconnected"

        self._controller_page_cls = ControllerPage
        self._scripts_page_cls = ScriptsPage
        self._profiles_page_cls = ProfilesPage
        self._setup_page_cls = SetupPage
        self._personalization_page_cls = PersonalizationPage
        self._stats_page_cls = StatsPage
        self._audio_player_cls = AudioPlaybackService
        self._tray_service_cls = TrayService
        self._volume_overlay_cls = VolumeOverlayToast

        self.setWindowTitle("MacroPad Controller")
        self.setWindowIcon(build_app_icon())

        self.audio_player = self._audio_player_cls()
        self.controller = QtSessionController(
            settings,
            on_volume_mixer=self._show_volume_overlay,
            on_audio_file=self._play_audio_file,
        )
        saved_output = str(getattr(self.controller, "selected_audio_output", "") or "").strip()
        if saved_output:
            if not self.audio_player.set_output_device(saved_output):
                self.controller.set_audio_output_device("")
        else:
            self.audio_player.set_output_device("")
        self.overlay = self._volume_overlay_cls()

        self._build_ui()
        compact_min_size = QSize(760, 500)
        self.setMinimumSize(compact_min_size)
        self.resize(compact_min_size)
        self._build_tray()
        self._bind_controller_signals()
        self._sync_header_from_controller()
        self._refresh_status()

    def _play_audio_file(self, path: str, volume_percent: int | None = None) -> bool:
        candidate = Path(path).expanduser()
        return bool(self.audio_player.play_file(candidate, volume_percent=volume_percent))
