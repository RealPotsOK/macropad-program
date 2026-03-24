from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from contextlib import suppress
from typing import Callable

from PySide6.QtCore import QObject, Signal

from ...backoff import ExponentialBackoff
from ...config import DEFAULT_SETTINGS, Settings
from ...serial import (
    BoardEvent,
    BoardSerial,
    EVENT_ENC_DELTA,
    EVENT_ENC_SWITCH,
    EVENT_KEY_STATE,
    EVENT_READY,
    PortInfo,
    SerialControllerError,
    list_serial_ports,
    monitor_with_reconnect,
)
from ...core.actions import (
    ACTION_CHANGE_PROFILE,
    ACTION_NONE,
    ActionExecutionError,
    cycle_profile_slot,
    execute_action,
    parse_change_profile_value,
)
from ...core.oled_text import render_profile_display_lines
from ...core.key_layout import (
    DEFAULT_KEY_COLS,
    DEFAULT_KEY_ROWS,
    build_display_map,
    build_virtual_keys,
    key_from_text,
    key_to_text,
)
from ...core.profile import KeyAction, KeyBinding, Profile, create_default_profile
from ...core.step_blocks import (
    BLOCK_FOREVER,
    BLOCK_REPEAT,
    BLOCK_WHILE_MOUSE_PRESSED,
    BLOCK_WHILE_PRESSED,
    StepExecutionError,
    execute_step_script,
    parse_step_script,
)
from .profile_store import ProfileStore

LOGGER = logging.getLogger(__name__)


class QtSessionController(QObject):
    portsChanged = Signal(object)
    setupChanged = Signal(object)
    connectionStateChanged = Signal(str)
    logMessage = Signal(str)
    profileChanged = Signal(int, object)
    profileSlotChanged = Signal(int)
    profileNameChanged = Signal(str)
    selectedKeyChanged = Signal(int, int)
    selectedBindingChanged = Signal(object)
    rawKeyStateChanged = Signal(int, int, bool)
    keyStateChanged = Signal(int, int, bool)
    boardStateChanged = Signal(object)
    encoderChanged = Signal(str)
    lastPacketChanged = Signal(str)
    autoConnectChanged = Signal(bool)

    def __init__(
        self,
        settings: Settings,
        *,
        on_volume_mixer: Callable[[object], None] | None = None,
        on_audio_file: Callable[[str, int | None], bool] | None = None,
    ) -> None:
        super().__init__()
        self.settings = settings
        self.on_volume_mixer = on_volume_mixer
        self.on_audio_file = on_audio_file
        self.store = ProfileStore(settings)
        self.selected_port = (settings.port or self.store.app_state.last_port or "").strip()
        self.selected_hint = (settings.hint or self.store.app_state.last_hint or "").strip()
        startup_baud = int(self.store.app_state.last_baud or settings.baud or DEFAULT_SETTINGS.baud)
        if settings.baud != DEFAULT_SETTINGS.baud:
            startup_baud = int(settings.baud)
        self.selected_baud = startup_baud
        self.selected_audio_output = str(getattr(self.store.app_state, "audio_output_device", "") or "").strip()
        self.learn_mode = False

        self._ports: list[PortInfo] = []
        self._board: BoardSerial | None = None
        self._monitor_task: asyncio.Task[None] | None = None
        self._monitor_stop: asyncio.Event | None = None
        self._closing = False
        self._display_send_lock = asyncio.Lock()
        self._last_oled_lines: tuple[str, ...] | None = None
        self._backoff = ExponentialBackoff(initial=1.0, max_delay=5.0)
        self._load_active_setup_profile_from_state()
        self._board_to_virtual: dict[tuple[int, int], tuple[int, int]] = self._load_key_mapping()
        self._suspend_actions = False
        self._step_loop_tasks: set[asyncio.Task[None]] = set()
        self._step_forever_tasks: dict[tuple[int, int], asyncio.Task[None]] = {}

        self.refresh_ports()
        self.setupChanged.emit(self.setup_state())

    @property
    def profile_slot(self) -> int:
        return int(self.store.profile_slot)

    @property
    def current_profile(self) -> Profile:
        return self.store.profile

    @property
    def selected_key(self) -> tuple[int, int]:
        return self.store.selected_key

    def refresh_ports(self) -> None:
        self._ports = list_serial_ports()
        self.portsChanged.emit(self._ports)

    def port_choices(self) -> list[PortInfo]:
        return list(self._ports)

    def set_selected_port(self, port: str) -> None:
        self.selected_port = str(port or "").strip()
        self._save_state()

    def set_selected_hint(self, hint: str) -> None:
        self.selected_hint = str(hint or "").strip()
        self._save_state()

    def set_selected_baud(self, baud: int) -> None:
        self.selected_baud = max(1, int(baud))
        self._save_state()

    def set_auto_connect(self, enabled: bool) -> None:
        self.store.app_state.auto_connect = bool(enabled)
        self._save_state()
        self.autoConnectChanged.emit(bool(enabled))

    def set_audio_output_device(self, device_id: str) -> None:
        self.selected_audio_output = str(device_id or "").strip()
        self.store.app_state.audio_output_device = self.selected_audio_output
        self._save_state()

    def set_learn_mode(self, enabled: bool) -> None:
        self.learn_mode = bool(enabled)

    def set_profile_slot(self, slot: int) -> None:
        slot = max(1, min(10, int(slot)))
        if slot == self.profile_slot:
            return
        self.store.load_profile_slot(slot)
        self._emit_profile_state()
        asyncio.create_task(self._push_profile_text(reason="profile-change"))

    def save_current_profile_settings(
        self,
        *,
        name: str,
        description: str,
        oled_line1: str,
        oled_line2: str,
    ) -> None:
        profile = self.current_profile
        clean_name = str(name or "").strip() or f"Profile {self.profile_slot}"
        profile.name = clean_name
        profile.description = str(description or "").strip()
        profile.oled_line1 = str(oled_line1 or "").strip() or "Profile {profile_slot}"
        profile.oled_line2 = str(oled_line2 or "").strip() or "{profile_name}"
        self.store.profile_names[self.profile_slot] = clean_name
        self.store.save_profile_slot()
        self._save_state()
        self._emit_profile_state()
        asyncio.create_task(self._push_profile_text(reason="profile-save"))

    def reset_current_profile(self, *, name: str | None = None) -> None:
        clean_name = str(name or "").strip() or f"Profile {self.profile_slot}"
        fresh = create_default_profile(clean_name, keys=self.store.keys)
        fresh.name = clean_name
        self.store.profile_names[self.profile_slot] = clean_name
        self.store.profile = fresh
        self.store.save_profile_slot()
        self._save_state()
        self._emit_profile_state()
        asyncio.create_task(self._push_profile_text(reason="profile-reset"))

    def push_profile_text_now(self) -> None:
        asyncio.create_task(self._push_profile_text(reason="force"))

    def select_key(self, row: int, col: int) -> None:
        self.store.set_selected_key((int(row), int(col)))
        self.selectedKeyChanged.emit(int(row), int(col))
        self.selectedBindingChanged.emit(self.store.selected_binding())

    def setup_state(self) -> dict[str, object]:
        rows = int(getattr(self.store, "key_rows", DEFAULT_KEY_ROWS))
        cols = int(getattr(self.store, "key_cols", DEFAULT_KEY_COLS))
        app_state = getattr(self.store, "app_state", None)
        has_encoder = bool(getattr(app_state, "has_encoder", True))
        has_screen = bool(getattr(app_state, "has_screen", True))
        screen_prefix = str(getattr(app_state, "screen_command_prefix", "TXT:") or "TXT:")
        screen_separator = str(getattr(app_state, "screen_line_separator", "|") or "|")
        screen_end_token = str(getattr(app_state, "screen_end_token", "\\n") or "\\n")
        return {
            "rows": rows,
            "cols": cols,
            "has_encoder": has_encoder,
            "has_screen": has_screen,
            "encoder_inverted": bool(getattr(app_state, "encoder_inverted", False)),
            "display_map": build_display_map(rows, cols),
            "key_mapping": {
                key_to_text(board): key_to_text(virtual)
                for board, virtual in sorted(self._board_to_virtual.items())
            },
            "screen_command_prefix": screen_prefix,
            "screen_line_separator": screen_separator,
            "screen_end_token": screen_end_token,
            "active_setup_profile": str(getattr(app_state, "active_setup_profile", "Default") or "Default"),
            "setup_profiles": sorted(
                str(name)
                for name in dict(getattr(app_state, "setup_profiles", {}) or {}).keys()
                if str(name).strip()
            ),
        }

    def update_setup(
        self,
        *,
        rows: int,
        cols: int,
        has_encoder: bool,
        has_screen: bool,
        encoder_inverted: bool,
        screen_command_prefix: str,
        screen_line_separator: str,
        screen_end_token: str,
    ) -> None:
        if hasattr(self.store, "set_virtual_layout"):
            self.store.set_virtual_layout(rows=rows, cols=cols)
        app_state = getattr(self.store, "app_state", None)
        if app_state is not None:
            app_state.has_encoder = bool(has_encoder)
            app_state.has_screen = bool(has_screen)
            app_state.encoder_inverted = bool(encoder_inverted)
            app_state.screen_command_prefix = str(screen_command_prefix or "TXT:").strip() or "TXT:"
            app_state.screen_line_separator = str(screen_line_separator or "")
            app_state.screen_end_token = str(screen_end_token or "\\n")
        self._board_to_virtual = self._load_key_mapping()
        self._save_active_setup_profile()
        self._emit_profile_state()
        self.setupChanged.emit(self.setup_state())
        self._save_state()
        self.logMessage.emit(
            f"Setup saved: {self.setup_state()['rows']}x{self.setup_state()['cols']}, "
            f"encoder={'on' if has_encoder else 'off'}, "
            f"screen={'on' if has_screen else 'off'}, "
            f"invert={'on' if encoder_inverted else 'off'}."
        )

    def assign_board_key_mapping(
        self,
        *,
        board_key: tuple[int, int],
        virtual_key: tuple[int, int],
    ) -> None:
        if virtual_key not in self.store.keys:
            return
        self._board_to_virtual[(int(board_key[0]), int(board_key[1]))] = (
            int(virtual_key[0]),
            int(virtual_key[1]),
        )
        self._persist_key_mapping()
        self.setupChanged.emit(self.setup_state())
        self.logMessage.emit(
            f"Mapped board {board_key[0]},{board_key[1]} -> key {virtual_key[0]},{virtual_key[1]}."
        )

    def clear_board_key_mappings(self) -> None:
        self._board_to_virtual.clear()
        self._persist_key_mapping()
        self._save_active_setup_profile()
        self.setupChanged.emit(self.setup_state())
        self.logMessage.emit("Cleared all board-to-key mappings.")

    def begin_setup_capture(self) -> None:
        self._suspend_actions = True

    def end_setup_capture(self) -> None:
        self._suspend_actions = False

    def create_setup_profile(self, name: str) -> str:
        app_state = getattr(self.store, "app_state", None)
        if app_state is None:
            return "Default"
        base = str(name or "").strip() or "Setup"
        candidate = base
        index = 2
        existing = set(dict(getattr(app_state, "setup_profiles", {}) or {}).keys())
        while candidate in existing:
            candidate = f"{base} {index}"
            index += 1
        profiles = dict(getattr(app_state, "setup_profiles", {}) or {})
        profiles[candidate] = self._current_setup_profile_payload()
        app_state.setup_profiles = profiles
        app_state.active_setup_profile = candidate
        self._save_state()
        self.setupChanged.emit(self.setup_state())
        return candidate

    def rename_setup_profile(self, old_name: str, new_name: str) -> str:
        app_state = getattr(self.store, "app_state", None)
        if app_state is None:
            return "Default"
        old = str(old_name or "").strip()
        new = str(new_name or "").strip()
        if not old or not new:
            return old or new or "Default"
        profiles = dict(getattr(app_state, "setup_profiles", {}) or {})
        if old not in profiles:
            return old
        payload = profiles.pop(old)
        candidate = new
        index = 2
        while candidate in profiles:
            candidate = f"{new} {index}"
            index += 1
        profiles[candidate] = payload
        app_state.setup_profiles = profiles
        if str(getattr(app_state, "active_setup_profile", "")) == old:
            app_state.active_setup_profile = candidate
        self._save_state()
        self.setupChanged.emit(self.setup_state())
        return candidate

    def delete_setup_profile(self, name: str) -> bool:
        app_state = getattr(self.store, "app_state", None)
        if app_state is None:
            return False
        target = str(name or "").strip()
        profiles = dict(getattr(app_state, "setup_profiles", {}) or {})
        if target not in profiles:
            return False
        if len(profiles) <= 1:
            return False
        profiles.pop(target, None)
        app_state.setup_profiles = profiles
        if str(getattr(app_state, "active_setup_profile", "")) == target:
            app_state.active_setup_profile = sorted(profiles.keys())[0]
            self.load_setup_profile(app_state.active_setup_profile)
        else:
            self._save_state()
            self.setupChanged.emit(self.setup_state())
        return True

    def save_current_setup_to_profile(self, name: str | None = None) -> str:
        app_state = getattr(self.store, "app_state", None)
        if app_state is None:
            return "Default"
        profile_name = str(name or getattr(app_state, "active_setup_profile", "Default")).strip() or "Default"
        profiles = dict(getattr(app_state, "setup_profiles", {}) or {})
        profiles[profile_name] = self._current_setup_profile_payload()
        app_state.setup_profiles = profiles
        app_state.active_setup_profile = profile_name
        self._save_state()
        self.setupChanged.emit(self.setup_state())
        return profile_name

    def load_setup_profile(self, name: str) -> bool:
        app_state = getattr(self.store, "app_state", None)
        if app_state is None:
            return False
        target = str(name or "").strip()
        profiles = dict(getattr(app_state, "setup_profiles", {}) or {})
        payload = profiles.get(target)
        if not isinstance(payload, dict):
            return False
        self._apply_setup_profile_payload(payload)
        app_state.active_setup_profile = target
        self._save_state()
        self._emit_profile_state()
        self.setupChanged.emit(self.setup_state())
        self.logMessage.emit(f"Loaded setup profile: {target}")
        return True

    def key_for_board_input(self, row: int, col: int) -> tuple[int, int] | None:
        return self._mapped_key_for_board(row, col)

    def build_screen_command(self, text: str) -> str:
        app_state = getattr(self.store, "app_state", None)
        prefix = str(getattr(app_state, "screen_command_prefix", "TXT:") or "TXT:")
        separator = str(getattr(app_state, "screen_line_separator", "|") or "")
        lines = [line.strip() for line in str(text or "").splitlines() if line.strip()]
        if not separator:
            joined = lines[0] if lines else ""
        else:
            joined = separator.join(lines)
        return f"{prefix}{joined}"

    async def send_screen_preview(self, text: str) -> None:
        app_state = getattr(self.store, "app_state", None)
        if not bool(getattr(app_state, "has_screen", True)):
            self.logMessage.emit("Screen is disabled in Setup.")
            return
        board = self._board
        if board is None or not board.is_open:
            self.logMessage.emit("Screen preview failed: board is not connected.")
            return
        command = self.build_screen_command(text)
        end_token = _decode_screen_end_token(str(getattr(app_state, "screen_end_token", "\\n") or "\\n"))
        try:
            await board.send_custom_text(command, terminator=end_token)
        except Exception as exc:
            self.logMessage.emit(f"Screen preview failed: {exc}")
            return
        self.logMessage.emit(f"Screen preview sent: {command!r} + {getattr(app_state, 'screen_end_token', '\\\\n')!r}")

    def current_binding(self) -> KeyBinding:
        return self.store.selected_binding()

    def update_selected_binding(self, *, kind: str, value: str, label: str | None = None) -> None:
        key = self.store.selected_key
        label_text = str(label or "").strip() or f"Key {key[0]},{key[1]}"
        self.store.update_binding_action(key, label=label_text, kind=kind, value=value)
        self.store.save_profile_slot()
        self._emit_profile_state()

    def save_selected_step_script(self, content: str) -> None:
        self._clear_selected_legacy_workspace_script()
        self._clear_selected_direct_action()
        self.store.save_script_for_key(self.selected_key, "step", content)
        self.logMessage.emit(f"Saved STEP script for {self.selected_key[0]},{self.selected_key[1]}.")
        self._emit_profile_state()

    def replace_selected_script_with_step(self) -> None:
        self._clear_selected_legacy_workspace_script()
        self._clear_selected_direct_action()
        self.store.clear_script_for_key(self.selected_key, "step")
        self.logMessage.emit(f"Replaced legacy inline script with STEP for {self.selected_key[0]},{self.selected_key[1]}.")
        self._emit_profile_state()

    def update_encoder_binding(self, direction: str, *, kind: str, value: str) -> None:
        action = self._encoder_action(direction)
        normalized_kind, normalized_value = self.store.normalize_action_choice(kind, value)
        action.kind = normalized_kind
        action.value = normalized_value
        if normalized_kind == ACTION_NONE:
            action.steps = []
        self.store.save_profile_slot()
        self._emit_profile_state()

    async def connect(self) -> None:
        if self._monitor_task is not None and not self._monitor_task.done():
            return
        self._closing = False
        self._monitor_stop = asyncio.Event()
        settings = self._build_monitor_settings()
        self.connectionStateChanged.emit("connecting")
        self.logMessage.emit(f"Connecting to {settings.port or settings.hint or 'auto'} @ {settings.baud}...")
        self._monitor_task = asyncio.create_task(self._monitor_loop(settings))
        self._save_state()

    async def disconnect(self) -> None:
        self._cancel_step_loop_tasks()
        if self._monitor_stop is not None:
            self._monitor_stop.set()
        task = self._monitor_task
        self._monitor_task = None
        if task is not None:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        self._board = None
        self._last_oled_lines = None
        self.connectionStateChanged.emit("disconnected")
        self.logMessage.emit("Disconnected.")

    async def reconnect(self) -> None:
        await self.disconnect()
        await self.connect()

    async def shutdown(self) -> None:
        self._closing = True
        self._cancel_step_loop_tasks()
        await self.disconnect()

    async def auto_connect_if_enabled(self, *, hidden_start: bool = False) -> None:
        has_target = bool(self.selected_port or self.selected_hint)
        if not has_target:
            return
        if self.store.app_state.auto_connect or hidden_start:
            await self.connect()

    def _save_state(self) -> None:
        self.store.save_app_state(
            last_port=self.selected_port,
            last_hint=self.selected_hint,
            last_baud=self.selected_baud,
            last_zoom=self.store.app_state.last_zoom,
            auto_connect=self.store.app_state.auto_connect,
            audio_output_device=self.selected_audio_output,
        )

    def _emit_profile_state(self) -> None:
        self.profileSlotChanged.emit(self.profile_slot)
        self.profileNameChanged.emit(self.current_profile.name)
        self.profileChanged.emit(self.profile_slot, self.current_profile)
        row, col = self.selected_key
        self.selectedKeyChanged.emit(row, col)
        self.selectedBindingChanged.emit(self.store.selected_binding())

    def _load_key_mapping(self) -> dict[tuple[int, int], tuple[int, int]]:
        app_state = getattr(self.store, "app_state", None)
        raw = getattr(app_state, "key_mapping", {})
        if not isinstance(raw, dict):
            return {}
        mapping: dict[tuple[int, int], tuple[int, int]] = {}
        allowed_virtual = set(self._available_keys())
        for board_text, virtual_text in raw.items():
            board_key = key_from_text(str(board_text or ""))
            virtual_key = key_from_text(str(virtual_text or ""))
            if board_key is None or virtual_key is None:
                continue
            if virtual_key not in allowed_virtual:
                continue
            mapping[board_key] = virtual_key
        return mapping

    def _current_setup_profile_payload(self) -> dict[str, object]:
        app_state = getattr(self.store, "app_state", None)
        rows = int(getattr(self.store, "key_rows", DEFAULT_KEY_ROWS))
        cols = int(getattr(self.store, "key_cols", DEFAULT_KEY_COLS))
        return {
            "key_rows": rows,
            "key_cols": cols,
            "has_encoder": bool(getattr(app_state, "has_encoder", True)),
            "has_screen": bool(getattr(app_state, "has_screen", True)),
            "encoder_inverted": bool(getattr(app_state, "encoder_inverted", False)),
            "key_mapping": {
                key_to_text(board): key_to_text(virtual)
                for board, virtual in sorted(self._board_to_virtual.items())
            },
            "screen_command_prefix": str(getattr(app_state, "screen_command_prefix", "TXT:") or "TXT:"),
            "screen_line_separator": str(getattr(app_state, "screen_line_separator", "|") or ""),
            "screen_end_token": str(getattr(app_state, "screen_end_token", "\\n") or "\\n"),
        }

    def _save_active_setup_profile(self) -> None:
        app_state = getattr(self.store, "app_state", None)
        if app_state is None:
            return
        active = str(getattr(app_state, "active_setup_profile", "Default") or "Default")
        profiles = dict(getattr(app_state, "setup_profiles", {}) or {})
        profiles[active] = self._current_setup_profile_payload()
        app_state.setup_profiles = profiles
        app_state.active_setup_profile = active

    def _apply_setup_profile_payload(self, payload: dict[str, object]) -> None:
        rows = int(payload.get("key_rows", DEFAULT_KEY_ROWS) or DEFAULT_KEY_ROWS)
        cols = int(payload.get("key_cols", DEFAULT_KEY_COLS) or DEFAULT_KEY_COLS)
        if hasattr(self.store, "set_virtual_layout"):
            self.store.set_virtual_layout(rows=rows, cols=cols)
        app_state = getattr(self.store, "app_state", None)
        if app_state is None:
            return
        app_state.has_encoder = bool(payload.get("has_encoder", True))
        app_state.has_screen = bool(payload.get("has_screen", True))
        app_state.encoder_inverted = bool(payload.get("encoder_inverted", False))
        app_state.screen_command_prefix = str(payload.get("screen_command_prefix", "TXT:") or "TXT:")
        app_state.screen_line_separator = str(payload.get("screen_line_separator", "|") or "")
        app_state.screen_end_token = str(payload.get("screen_end_token", "\\n") or "\\n")
        raw_mapping = payload.get("key_mapping")
        if isinstance(raw_mapping, dict):
            app_state.key_mapping = {str(k): str(v) for k, v in raw_mapping.items()}
        else:
            app_state.key_mapping = {}
        self._board_to_virtual = self._load_key_mapping()

    def _load_active_setup_profile_from_state(self) -> None:
        app_state = getattr(self.store, "app_state", None)
        if app_state is None:
            return
        active = str(getattr(app_state, "active_setup_profile", "Default") or "Default")
        profiles = dict(getattr(app_state, "setup_profiles", {}) or {})
        payload = profiles.get(active)
        if isinstance(payload, dict):
            self._apply_setup_profile_payload(payload)

    def _persist_key_mapping(self) -> None:
        if hasattr(self.store, "set_key_mapping"):
            self.store.set_key_mapping(self._board_to_virtual)
        else:
            app_state = getattr(self.store, "app_state", None)
            if app_state is not None:
                app_state.key_mapping = {
                    key_to_text(board): key_to_text(virtual)
                    for board, virtual in sorted(self._board_to_virtual.items())
                }
        self._save_state()

    def _mapped_key_for_board(self, row: int, col: int) -> tuple[int, int] | None:
        board_key = (int(row), int(col))
        mapped = self._board_to_virtual.get(board_key)
        if mapped is not None:
            return mapped
        if board_key in set(self._available_keys()):
            return board_key
        return None

    def _available_keys(self) -> list[tuple[int, int]]:
        raw_keys = getattr(self.store, "keys", None)
        if isinstance(raw_keys, list) and raw_keys:
            normalized: list[tuple[int, int]] = []
            for key in raw_keys:
                if isinstance(key, tuple) and len(key) == 2:
                    normalized.append((int(key[0]), int(key[1])))
            if normalized:
                return normalized
        return build_virtual_keys(DEFAULT_KEY_ROWS, DEFAULT_KEY_COLS)

    def _build_monitor_settings(self) -> Settings:
        return Settings(
            port=self.selected_port or None,
            hint=self.selected_hint or None,
            baud=self.selected_baud,
            ack_timeout=self.settings.ack_timeout,
            dedupe_ms=self.settings.dedupe_ms,
            log_level=self.settings.log_level,
        )

    def _encoder_action(self, direction: str) -> KeyAction:
        profile = self.current_profile
        if direction == "up":
            return profile.enc_up_action
        if direction == "down":
            return profile.enc_down_action
        if direction == "sw_down":
            return profile.enc_sw_down_action
        if direction == "sw_up":
            return profile.enc_sw_up_action
        return KeyAction()

    def _clear_selected_legacy_workspace_script(self) -> None:
        binding = self.current_binding()
        legacy_mode = (binding.script_mode or "").strip().lower()
        if legacy_mode not in {"python", "ahk"}:
            return
        if not (binding.script_code or "").strip():
            return
        self.store.clear_script_for_key(self.selected_key, legacy_mode)

    def _clear_selected_direct_action(self) -> None:
        binding = self.current_binding()
        binding.action = KeyAction()

    async def _monitor_loop(self, settings: Settings) -> None:
        def _on_event(event: BoardEvent) -> None:
            self._handle_event(event)

        def _on_raw_line(timestamp: datetime, line: str) -> None:
            self.logMessage.emit(f"{timestamp.isoformat(timespec='seconds')} RX {line}")

        def _on_connected(port: str) -> None:
            self.selected_port = port
            self.connectionStateChanged.emit("connected")
            self.logMessage.emit(f"Connected: {port}")
            self._save_state()

        def _on_disconnected(reason: str) -> None:
            if reason != "stopped":
                self.connectionStateChanged.emit("reconnecting")
                self.logMessage.emit(f"Connection lost: {reason}")

        def _on_board(board: BoardSerial | None) -> None:
            self._board = board
            self.boardStateChanged.emit(board)

        try:
            await monitor_with_reconnect(
                settings,
                on_event=_on_event,
                stop_event=self._monitor_stop,
                on_connected=_on_connected,
                on_disconnected=_on_disconnected,
                on_board=_on_board,
                on_raw_line=_on_raw_line,
                backoff=self._backoff,
            )
        except asyncio.CancelledError:
            raise
        except (SerialControllerError, Exception) as exc:
            self.logMessage.emit(f"Monitor error: {exc}")
            self.connectionStateChanged.emit("disconnected")
        finally:
            self._monitor_task = None
            self._board = None
            self.boardStateChanged.emit(None)
            if self._closing:
                self.connectionStateChanged.emit("disconnected")

    def _handle_event(self, event: BoardEvent) -> None:
        self.lastPacketChanged.emit(event.timestamp.strftime("%H:%M:%S"))

        if event.raw_line == EVENT_READY:
            self.logMessage.emit("Board READY")
            asyncio.create_task(self._push_profile_text(reason="ready"))
            return

        if event.kind == EVENT_ENC_DELTA and event.delta is not None:
            self._cancel_step_loop_tasks()
            adjusted_delta = int(event.delta)
            if bool(getattr(self.store.app_state, "encoder_inverted", False)):
                adjusted_delta = -adjusted_delta
            self.encoderChanged.emit(f"ENC={adjusted_delta:+d}")
            if not self._suspend_actions:
                direction = "up" if adjusted_delta > 0 else "down"
                asyncio.create_task(self._execute_encoder_action(direction, steps=abs(adjusted_delta)))
            return

        if event.kind == EVENT_ENC_SWITCH:
            self._cancel_step_loop_tasks()
            pressed = bool(event.value)
            self.encoderChanged.emit(f"ENC_SW={1 if pressed else 0}")
            if not self._suspend_actions:
                asyncio.create_task(self._execute_encoder_action("sw_down" if pressed else "sw_up"))
            return

        if event.kind == EVENT_KEY_STATE and event.row is not None and event.col is not None:
            pressed = bool(event.value)
            self.rawKeyStateChanged.emit(event.row, event.col, pressed)
            mapped = self._mapped_key_for_board(event.row, event.col)
            was_forever_active_for_key = False
            if mapped is not None and pressed:
                was_forever_active_for_key = self._is_step_forever_running(mapped)
                self._cancel_step_loop_tasks()
            if mapped is None:
                self.logMessage.emit(f"KEY {event.row},{event.col} {'DOWN' if pressed else 'UP'} (unmapped)")
                return
            mapped_row, mapped_col = mapped
            self.keyStateChanged.emit(mapped_row, mapped_col, pressed)
            self.logMessage.emit(
                f"KEY {event.row},{event.col} -> {mapped_row},{mapped_col} {'DOWN' if pressed else 'UP'}"
            )
            if pressed and self.learn_mode:
                self.select_key(mapped_row, mapped_col)
            if pressed and not self._suspend_actions:
                if was_forever_active_for_key:
                    self.logMessage.emit(f"STEP forever stopped for {mapped_row},{mapped_col}.")
                    return
                asyncio.create_task(self._execute_key_action((mapped_row, mapped_col)))

    async def _execute_key_action(self, key: tuple[int, int]) -> None:
        binding = self.store.binding_for(key)
        kind, value = self.store.display_action_for_binding(binding)
        action_kind = (binding.action.kind or "").strip().lower()
        inline_mode = (binding.script_mode or "").strip().lower()
        inline_source = binding.script_code or ""
        has_inline_script = bool(inline_source.strip())
        has_action = bool(action_kind and action_kind != ACTION_NONE)

        if not has_action and not has_inline_script:
            self.logMessage.emit(f"Key {key[0]},{key[1]} has no action.")
            return

        if has_action:
            if kind == ACTION_CHANGE_PROFILE:
                await self._execute_profile_action(binding.action)
            else:
                try:
                    await execute_action(
                        binding.action,
                        log=self.logMessage.emit,
                        on_volume_mixer=self.on_volume_mixer,
                        on_audio_file=self._play_audio_file,
                    )
                except ActionExecutionError as exc:
                    self.logMessage.emit(f"Action failed for {key[0]},{key[1]}: {exc}")
                    return
                self.logMessage.emit(f"Key {key[0]},{key[1]} -> {kind}: {value or '<empty>'}")
            return

        if has_inline_script:
            await self._execute_inline_script(key, mode=inline_mode, source=inline_source)

    async def _execute_encoder_action(self, direction: str, *, steps: int = 1) -> None:
        action = self._encoder_action(direction)
        if action.kind == ACTION_NONE:
            return
        for _ in range(max(1, int(steps))):
            if action.kind == ACTION_CHANGE_PROFILE:
                await self._execute_profile_action(action)
            else:
                try:
                    await execute_action(
                        action,
                        log=self.logMessage.emit,
                        on_volume_mixer=self.on_volume_mixer,
                        on_audio_file=self._play_audio_file,
                    )
                except ActionExecutionError as exc:
                    self.logMessage.emit(f"Encoder action failed: {exc}")
                    return

    async def _execute_profile_action(self, action: KeyAction) -> None:
        kind = str(action.kind or "").strip().lower()
        value = str(action.value or "")
        if kind == ACTION_CHANGE_PROFILE:
            spec = parse_change_profile_value(value)
            if spec.mode == "set":
                self.set_profile_slot(spec.target if spec.target is not None else self.profile_slot)
                return
            delta = spec.step if spec.mode == "next" else -spec.step
            self.set_profile_slot(cycle_profile_slot(self.profile_slot, delta, min_slot=spec.min_slot, max_slot=spec.max_slot))
            return
        await execute_action(
            action,
            log=self.logMessage.emit,
            on_volume_mixer=self.on_volume_mixer,
            on_audio_file=self._play_audio_file,
        )

    async def _execute_inline_script(self, key: tuple[int, int], *, mode: str, source: str) -> None:
        normalized_mode = (mode or "").strip().lower()
        if not source.strip():
            return

        if normalized_mode == "python":
            self.store.sync_scripts_from_workspace("python", persist=False)
            code = self.store.python_code_for_key(key)
            if code is None or self.store.python_source_for_key(key) != source:
                try:
                    self.store.rebuild_python_cache()
                    code = self.store.python_code_for_key(key)
                except Exception as exc:
                    self.logMessage.emit(f"Python script compile error ({key[0]},{key[1]}): {exc}")
                    return
            if code is None:
                self.logMessage.emit(f"Python script missing for {key[0]},{key[1]}.")
                return
            namespace: dict[str, object] = {
                "__builtins__": __builtins__,
                "key": key,
                "row": key[0],
                "col": key[1],
                "pressed": True,
                "timestamp": time.time(),
            }
            try:
                await asyncio.to_thread(exec, code, namespace, namespace)
            except Exception as exc:
                self.logMessage.emit(f"Python script runtime error ({key[0]},{key[1]}): {exc}")
            else:
                self.logMessage.emit(f"Ran Python script for {key[0]},{key[1]}.")
            return

        if normalized_mode == "step":
            parsed_blocks = parse_step_script(source)
            block_types = {str(block.get("type") or "").strip().lower() for block in parsed_blocks}
            has_forever = BLOCK_FOREVER in block_types
            has_loop = bool(block_types.intersection({BLOCK_REPEAT, BLOCK_WHILE_PRESSED, BLOCK_WHILE_MOUSE_PRESSED, BLOCK_FOREVER}))

            if has_forever:
                existing = self._step_forever_tasks.get(key)
                if existing is not None and not existing.done():
                    existing.cancel()
                    return
                task = asyncio.create_task(execute_step_script(source, log=self.logMessage.emit))
                self._register_step_loop_task(task, key=key, forever=True)
                self.logMessage.emit(f"Started STEP forever for {key[0]},{key[1]}.")
                return

            if has_loop:
                task = asyncio.create_task(execute_step_script(source, log=self.logMessage.emit))
                self._register_step_loop_task(task, key=key, forever=False)
                try:
                    await task
                except asyncio.CancelledError:
                    return
                except StepExecutionError as exc:
                    self.logMessage.emit(f"Step script error ({key[0]},{key[1]}): {exc}")
                    return
                except Exception as exc:
                    self.logMessage.emit(f"Step runtime error ({key[0]},{key[1]}): {exc}")
                    return
                self.logMessage.emit(f"Ran STEP script for {key[0]},{key[1]}.")
                return

            try:
                await execute_step_script(source, log=self.logMessage.emit)
            except StepExecutionError as exc:
                self.logMessage.emit(f"Step script error ({key[0]},{key[1]}): {exc}")
            except Exception as exc:
                self.logMessage.emit(f"Step runtime error ({key[0]},{key[1]}): {exc}")
            else:
                self.logMessage.emit(f"Ran STEP script for {key[0]},{key[1]}.")
            return

        if normalized_mode == "ahk":
            self.store.sync_scripts_from_workspace("ahk", persist=False)
            runtime_path = self.store.runtime_script_path(key, "ahk")
            runtime_path.parent.mkdir(parents=True, exist_ok=True)
            runtime_path.write_text(source, encoding="utf-8")
            try:
                await execute_action(
                    KeyAction(kind="file", value=str(runtime_path)),
                    log=self.logMessage.emit,
                    on_volume_mixer=self.on_volume_mixer,
                    on_audio_file=self._play_audio_file,
                )
            except ActionExecutionError as exc:
                self.logMessage.emit(f"AHK script error ({key[0]},{key[1]}): {exc}")
            else:
                self.logMessage.emit(f"Ran AHK script for {key[0]},{key[1]}.")
            return

        if normalized_mode == "file":
            try:
                await execute_action(
                    KeyAction(kind="file", value=source.strip()),
                    log=self.logMessage.emit,
                    on_volume_mixer=self.on_volume_mixer,
                    on_audio_file=self._play_audio_file,
                )
            except ActionExecutionError as exc:
                self.logMessage.emit(f"File script error ({key[0]},{key[1]}): {exc}")
            else:
                self.logMessage.emit(f"Opened file target for {key[0]},{key[1]}.")

    async def _push_profile_text(self, *, reason: str) -> None:
        app_state = getattr(self.store, "app_state", None)
        if not bool(getattr(app_state, "has_screen", True)):
            return
        board = self._board
        if board is None or not board.is_open:
            return
        lines = tuple(
            str(line or "").strip()
            for line in await render_profile_display_lines(
                self.current_profile,
                slot=self.profile_slot,
                port=self.selected_port,
            )
        )
        if not lines:
            lines = ("",)
        if self._last_oled_lines == lines and reason != "force":
            return
        async with self._display_send_lock:
            board = self._board
            if board is None or not board.is_open:
                return
            if any(lines):
                if len(lines) == 1:
                    await board.send_oled_line(lines[0])
                else:
                    await board.send_oled_lines(*lines)
            else:
                await board.clear_oled()
        self._last_oled_lines = lines
        self.logMessage.emit(f"OLED profile text sent ({reason}): {' | '.join(lines)}")

    def _register_step_loop_task(
        self,
        task: asyncio.Task[None],
        *,
        key: tuple[int, int],
        forever: bool,
    ) -> None:
        self._step_loop_tasks.add(task)
        if forever:
            self._step_forever_tasks[key] = task

        def _on_done(done: asyncio.Task[None]) -> None:
            self._step_loop_tasks.discard(done)
            if forever and self._step_forever_tasks.get(key) is done:
                self._step_forever_tasks.pop(key, None)

        task.add_done_callback(_on_done)

    def _cancel_step_loop_tasks(self) -> None:
        tasks = [task for task in self._step_loop_tasks if not task.done()]
        for task in tasks:
            task.cancel()

    def _is_step_forever_running(self, key: tuple[int, int]) -> bool:
        task = self._step_forever_tasks.get((int(key[0]), int(key[1])))
        return bool(task is not None and not task.done())

    def _play_audio_file(self, path: object, volume_percent: int | None = None) -> bool:
        callback = self.on_audio_file
        if callback is None:
            return False
        return bool(callback(str(path), volume_percent))


def _decode_screen_end_token(token: str) -> str:
    text = str(token or "")
    if not text:
        return "\n"
    text = text.replace("\\r", "\r").replace("\\n", "\n").replace("\\t", "\t")
    return text
