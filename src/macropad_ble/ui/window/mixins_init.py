from __future__ import annotations

import queue

from ...desktop import migrate_legacy_app_data, resolve_app_paths, sync_packaged_runtime_assets
from .shared import *

class InitMixin:
    def __init__(
        self,
        root: tk.Tk,
        settings: Settings,
        *,
        start_hidden: bool = False,
        launch_command: list[str] | None = None,
        instance_guard: object | None = None,
    ) -> None:
        self.root = root
        self.settings = settings
        self.root.title("MacroPad Controller")
        self._base_window_width = 1240
        self._base_window_height = 780
        self._base_min_width = 920
        self._base_min_height = 560
        self.root.geometry(f"{self._base_window_width}x{self._base_window_height}")
        self.root.minsize(self._base_min_width, self._base_min_height)
        self.root.configure(bg=BG_APP)

        self._closing = False
        self._start_hidden = bool(start_hidden)
        self._window_hidden = bool(start_hidden)
        self._autostart_command = [str(part) for part in (launch_command or []) if str(part).strip()]
        self._instance_guard = instance_guard
        self._tray_controller: Any | None = None
        self._tray_available = False
        self._tray_dispatch_queue: queue.SimpleQueue[Any] = queue.SimpleQueue()
        self._monitor_task: asyncio.Task[None] | None = None
        self._monitor_stop: asyncio.Event | None = None
        self._background_tasks: set[asyncio.Task[None]] = set()
        self._board: BoardSerial | None = None
        self._display_send_lock = asyncio.Lock()
        self._oled_refresh_task: asyncio.Task[None] | None = None
        self._last_oled_lines: tuple[str, ...] | None = None
        self._event_times: deque[float] = deque()
        self._error_count = 0
        self._last_packet_monotonic: float | None = None
        self._last_packet_clock = "--"
        self._enc_total = 0
        self._app_started_monotonic = time.monotonic()

        self.keys = sorted(KEY_DISPLAY_MAP.keys())
        if not self.keys:
            raise SerialControllerError("KEY_DISPLAY_MAP is empty.")
        self.selected_key = self.keys[0]
        self.tiles: dict[tuple[int, int], TileWidgets] = {}
        self._script_cache: dict[tuple[int, int], Any] = {}
        self._script_cache_source: dict[tuple[int, int], str] = {}
        self._workspace_mtime: dict[str, float] = {}

        self.app_paths = resolve_app_paths()
        self._legacy_data_migrated = migrate_legacy_app_data(self.app_paths)
        self._runtime_assets_synced = sync_packaged_runtime_assets(self.app_paths)
        self.data_root = self.app_paths.data_root
        self.profile_dir = self.app_paths.profile_dir
        self.state_path = self.app_paths.state_path
        self.app_state = load_app_state(self.state_path)
        self.profile_names: dict[int, str] = {}
        for slot in range(1, 11):
            self.profile_names[slot] = self.app_state.profile_names.get(str(slot), f"Profile {slot}")
        self.profile_slot = max(1, min(10, self.app_state.selected_profile_slot))
        self.profile = create_default_profile(self.profile_names[self.profile_slot], keys=self.keys)

        self._current_port_device = ""
        self._port_display_to_device: dict[str, str] = {}
        self._port_info_map: dict[str, str] = {}

        startup_baud = self.app_state.last_baud or settings.baud
        if settings.baud != DEFAULT_SETTINGS.baud:
            startup_baud = settings.baud

        self.connection_var = tk.StringVar(value="Disconnected")
        self.port_display_var = tk.StringVar(value="")
        self.port_info_var = tk.StringVar(value="No serial device selected.")
        self.baud_var = tk.StringVar(value=str(startup_baud))
        self.zoom_var = tk.StringVar(value=self.app_state.last_zoom or "100%")
        self.auto_connect_var = tk.BooleanVar(value=self.app_state.auto_connect)

        self.selected_key_var = tk.StringVar(value="")
        self.selected_value_var = tk.StringVar(value="")
        self.binding_label_var = tk.StringVar(value="")
        self.action_type_var = tk.StringVar(value=ACTION_NONE)
        self.action_value_var = tk.StringVar(value="")
        self.learn_mode_var = tk.BooleanVar(value=False)
        self.enc_up_kind_var = tk.StringVar(value=ACTION_NONE)
        self.enc_up_value_var = tk.StringVar(value="")
        self.enc_down_kind_var = tk.StringVar(value=ACTION_NONE)
        self.enc_down_value_var = tk.StringVar(value="")
        self.enc_sw_down_kind_var = tk.StringVar(value=ACTION_NONE)
        self.enc_sw_down_value_var = tk.StringVar(value="")
        self.enc_sw_up_kind_var = tk.StringVar(value=ACTION_NONE)
        self.enc_sw_up_value_var = tk.StringVar(value="")

        self.profile_slot_var = tk.StringVar(value="")
        self.profile_rename_var = tk.StringVar(value="")
        self.oled_line1_var = tk.StringVar(value="")
        self.oled_line2_var = tk.StringVar(value="")
        self.description_preset_var = tk.StringVar(value=DESCRIPTION_PRESET_CUSTOM)
        self.oled_line2_var.trace_add("write", self._on_description_text_changed)

        self.script_mode_var = tk.StringVar(value="python")
        self.script_status_var = tk.StringVar(value="Inline scripts: Python mode is precompiled for low latency.")

        self.fw_var = tk.StringVar(value="FW: unknown")
        self.packet_var = tk.StringVar(value="Last packet: --")
        self.enc_var = tk.StringVar(value="ENC: --")
        self.rate_var = tk.StringVar(value="Rate: 0.0 evt/s")
        self.error_var = tk.StringVar(value="Errors: 0")
        self.mouse_var = tk.StringVar(value="Mouse: --, --")

        self._status_pill: tk.Label | None = None
        self._connect_button: tk.Button | None = None
        self._disconnect_button: tk.Button | None = None
        self._port_combo: ttk.Combobox | None = None
        self._baud_combo: ttk.Combobox | None = None
        self._zoom_combo: ttk.Combobox | None = None
        self._profile_combo: ttk.Combobox | None = None
        self._script_profile_combo: ttk.Combobox | None = None
        self._description_preset_combo: ttk.Combobox | None = None
        self._script_key_list: tk.Listbox | None = None
        self._script_mode_combo: ttk.Combobox | None = None
        self._script_editor: tk.Text | None = None
        self._script_text_panel: tk.Frame | None = None
        self._step_panel: tk.Frame | None = None
        self._step_editor: Any | None = None
        self._script_editor_read_only = False
        self._script_linked_path: Path | None = None
        self._log_text: tk.Text | None = None
        self._stats_text: tk.Text | None = None
        self._stats_process: Any | None = None
        self._stats_last_report = ""
        self._stats_last_updated_at = 0.0
        self._app_icon: tk.PhotoImage | None = None
        self._last_dpi: int | None = None
        self._last_zoom_factor: float | None = None
        self._dpi_check_after_id: str | None = None
        self._dpi_configure_after_id: str | None = None
        self._font_zoom_baselines: dict[str, tuple[str, int, tuple[str, ...]]] = {}
        self._controller_body: tk.PanedWindow | None = None
        self._scripts_body: tk.PanedWindow | None = None
        self._volume_overlay: Any | None = None

        self._configure_ttk_style()
        self._build_ui()
        self._prime_stats_monitoring()
        self._refresh_system_stats(force=True)
        self.root.update_idletasks()
        self._ensure_content_fits()
        self._configure_window_chrome()
        self._initialize_overlay()
        self._configure_dpi_runtime()
        self._refresh_ports(prefer_device=self.app_state.last_port or settings.port or "")
        self._load_profile_slot(self.profile_slot)
        self._select_key(self.selected_key)
        self._set_connection_state("disconnected")
        self.root.protocol("WM_DELETE_WINDOW", self._on_window_close)
        self._initialize_desktop_mode()
        if self._legacy_data_migrated:
            self._log(f"Migrated legacy profiles into {self.data_root}.")
        if self._runtime_assets_synced:
            self._log(f"Updated {self._runtime_assets_synced} runtime helper script(s) from the packaged profiles.")

        if self.auto_connect_var.get() and self._current_port_device:
            self._spawn(self._connect())








