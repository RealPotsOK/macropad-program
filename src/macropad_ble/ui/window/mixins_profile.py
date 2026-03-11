from __future__ import annotations

from .shared import *
from .shared import _slot_label

class ProfileMixin:
    def _normalize_action_for_ui(self, action: KeyAction) -> None:
        kind, value = normalize_profile_action_kind_value(action.kind, action.value)
        action.kind = kind
        action.value = value


    def _refresh_profile_combo_values(self) -> None:
        values = [_slot_label(slot, self.profile_names[slot]) for slot in range(1, 11)]
        if self._profile_combo is not None:
            self._profile_combo.configure(values=values)
        if self._script_profile_combo is not None:
            self._script_profile_combo.configure(values=values)
        current_label = _slot_label(self.profile_slot, self.profile_names[self.profile_slot])
        self.profile_slot_var.set(current_label)
        self.profile_rename_var.set(self.profile_names[self.profile_slot])


    def _profile_path(self, slot: int) -> Path:
        return self.profile_dir / f"profile_{slot:02d}.json"


    def _save_app_state(self) -> None:
        self.app_state.last_port = self._current_port_device
        try:
            self.app_state.last_baud = int(self.baud_var.get().strip())
        except ValueError:
            self.app_state.last_baud = self.settings.baud
        self.app_state.last_zoom = (self.zoom_var.get() or "100%").strip()
        self.app_state.auto_connect = self.auto_connect_var.get()
        self.app_state.selected_profile_slot = self.profile_slot
        self.app_state.profile_names = {str(slot): name for slot, name in self.profile_names.items()}
        save_app_state(self.state_path, self.app_state)


    def _load_profile_slot(self, slot: int) -> None:
        slot = max(1, min(10, slot))
        name = self.profile_names[slot]
        try:
            self.profile = load_profile(self._profile_path(slot), name=name, keys=self.keys)
        except Exception as exc:
            self.profile = create_default_profile(name, keys=self.keys)
            self._error_count += 1
            self._log(f"Profile load error: {exc}")
        self.profile.name = name
        self.profile_slot = slot
        self._refresh_profile_combo_values()
        self._apply_profile_to_tiles()
        self._ensure_workspace_script("python")
        self._ensure_workspace_script("ahk")
        self._rebuild_script_cache()
        self._sync_encoder_controls_from_profile()
        self._sync_oled_controls_from_profile()
        self._save_app_state()
        self._log(f"Profile loaded: slot {slot} ({name})")
        self._spawn(self._push_profile_text_for_slot(slot, reason="profile-change"))


    def _save_profile_slot(self) -> None:
        self._apply_oled_controls_to_profile()
        self.profile.name = self.profile_names[self.profile_slot]
        save_profile(self._profile_path(self.profile_slot), self.profile)
        self._save_app_state()
        self._log(f"Profile saved: slot {self.profile_slot} ({self.profile.name})")


    def _binding_for(self, key: tuple[int, int]) -> KeyBinding:
        binding = self.profile.bindings.get(key)
        if binding is not None:
            self._normalize_action_for_ui(binding.action)
            return binding
        binding = KeyBinding(label=f"Key {key[0]},{key[1]}")
        self._normalize_action_for_ui(binding.action)
        self.profile.bindings[key] = binding
        return binding


    def _apply_profile_to_tiles(self) -> None:
        for key, tile in self.tiles.items():
            binding = self._binding_for(key)
            tile.canvas.itemconfigure(tile.title, text=binding.label)
        self._update_selected_value_label()


    def _display_action_for_binding(self, binding: KeyBinding) -> tuple[str, str]:
        kind = (binding.action.kind or ACTION_NONE).strip().lower() or ACTION_NONE
        value = binding.action.value or ""
        has_inline_python = (
            (binding.script_mode or "").strip().lower() == "python"
            and bool((binding.script_code or "").strip())
        )
        if kind == ACTION_NONE and has_inline_python:
            return ACTION_PYTHON, INLINE_PYTHON_ACTION_VALUE
        return kind, value


    def _update_selected_value_label(self) -> None:
        binding = self._binding_for(self.selected_key)
        action_kind, action_value = self._display_action_for_binding(binding)
        action_text = f"{action_kind or ACTION_NONE}: {action_value or '<empty>'}"
        script_text = f"{binding.script_mode} ({'set' if binding.script_code.strip() else 'empty'})"
        self.selected_value_var.set(f"Action = {action_text} | Script = {script_text}")


    def _sync_encoder_controls_from_profile(self) -> None:
        up = self.profile.enc_up_action
        down = self.profile.enc_down_action
        sw_down = self.profile.enc_sw_down_action
        sw_up = self.profile.enc_sw_up_action
        self._normalize_action_for_ui(up)
        self._normalize_action_for_ui(down)
        self._normalize_action_for_ui(sw_down)
        self._normalize_action_for_ui(sw_up)
        self.enc_up_kind_var.set((up.kind or ACTION_NONE).strip().lower() or ACTION_NONE)
        self.enc_up_value_var.set(up.value or "")
        self.enc_down_kind_var.set((down.kind or ACTION_NONE).strip().lower() or ACTION_NONE)
        self.enc_down_value_var.set(down.value or "")
        self.enc_sw_down_kind_var.set((sw_down.kind or ACTION_NONE).strip().lower() or ACTION_NONE)
        self.enc_sw_down_value_var.set(sw_down.value or "")
        self.enc_sw_up_kind_var.set((sw_up.kind or ACTION_NONE).strip().lower() or ACTION_NONE)
        self.enc_sw_up_value_var.set(sw_up.value or "")


    def _encoder_action_from_controls(self, direction: str) -> KeyAction:
        normalized = direction.strip().lower()
        if normalized == "up":
            kind = self.enc_up_kind_var.get().strip().lower() or ACTION_NONE
            value = self.enc_up_value_var.get().strip()
            return KeyAction(kind=kind, value=value)
        if normalized == "down":
            kind = self.enc_down_kind_var.get().strip().lower() or ACTION_NONE
            value = self.enc_down_value_var.get().strip()
            return KeyAction(kind=kind, value=value)
        if normalized == "sw_down":
            kind = self.enc_sw_down_kind_var.get().strip().lower() or ACTION_NONE
            value = self.enc_sw_down_value_var.get().strip()
            return KeyAction(kind=kind, value=value)
        if normalized == "sw_up":
            kind = self.enc_sw_up_kind_var.get().strip().lower() or ACTION_NONE
            value = self.enc_sw_up_value_var.get().strip()
            return KeyAction(kind=kind, value=value)
        return KeyAction()


    def _select_key(self, key: tuple[int, int]) -> None:
        if key not in self.tiles:
            return
        self.selected_key = key
        row, col = key
        self.selected_key_var.set(f"Selected key: {row},{col}")

        for tile_key, tile in self.tiles.items():
            tile.selected = tile_key == key

        binding = self._binding_for(key)
        self.binding_label_var.set(binding.label)
        action_kind, action_value = self._display_action_for_binding(binding)
        self.action_type_var.set(action_kind or ACTION_NONE)
        self.action_value_var.set(action_value)
        if action_kind == ACTION_PYTHON and action_value and action_value != INLINE_PYTHON_ACTION_VALUE:
            self.script_mode_var.set("python")
        else:
            self.script_mode_var.set(binding.script_mode or "python")
        self._refresh_script_editor_for_selected_key()
        self._sync_script_list_selection(key)
        self._update_selected_value_label()


    def _sync_oled_controls_from_profile(self) -> None:
        self.oled_line1_var.set(self.profile.name or "")
        self.oled_line2_var.set(self.profile.description or "")
        self.description_preset_var.set(infer_description_preset_label(self.profile.description or ""))


    def _apply_oled_controls_to_profile(self) -> None:
        self.profile.description = self.oled_line2_var.get().strip()
        self.description_preset_var.set(infer_description_preset_label(self.profile.description))


