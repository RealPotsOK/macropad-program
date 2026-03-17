from __future__ import annotations

from .shared import *
from .shared import _slot_from_label

class CallbacksAMixin:
    def _selected_port_device(self) -> str:
        selected = self.port_display_var.get().strip()
        if not selected:
            return ""
        if selected in self._port_display_to_device:
            return self._port_display_to_device[selected]
        if " - " in selected:
            return selected.split(" - ", 1)[0].strip()
        return selected


    def _on_refresh_ports(self) -> None:
        self._refresh_ports(prefer_device=self._selected_port_device())


    def _refresh_ports(self, *, prefer_device: str = "") -> None:
        ports = list_serial_ports()
        self._port_display_to_device.clear()
        self._port_info_map.clear()

        values: list[str] = []
        for port in ports:
            description = port.description or "Unknown device"
            display = f"{port.device} - {description}"
            values.append(display)
            self._port_display_to_device[display] = port.device
            info = f"{description} | HWID: {port.hwid or '<unknown>'}"
            if port.manufacturer:
                info += f" | MFG: {port.manufacturer}"
            self._port_info_map[port.device] = info

        if self._port_combo is not None:
            self._port_combo.configure(values=values)

        target = prefer_device.strip()
        selected_display = ""
        if target:
            for display, device in self._port_display_to_device.items():
                if device == target:
                    selected_display = display
                    break
        if not selected_display and values:
            selected_display = values[0]

        self.port_display_var.set(selected_display)
        self._current_port_device = self._selected_port_device()
        self._update_port_info()


    def _update_port_info(self) -> None:
        device = self._selected_port_device()
        if not device:
            self.port_info_var.set("No serial device selected.")
            return
        self._current_port_device = device
        self.port_info_var.set(self._port_info_map.get(device, "Selected serial device."))


    def _on_port_selected(self, _event: object) -> None:
        self._update_port_info()
        self._save_app_state()


    def _on_baud_changed(self, _event: object) -> None:
        raw_value = self.baud_var.get().strip()
        if not raw_value:
            return
        try:
            numeric = int(raw_value)
        except ValueError:
            self._error_count += 1
            self._log(f"Ignored invalid baud value: {raw_value}")
            return
        if numeric <= 0:
            self._error_count += 1
            self._log(f"Ignored invalid baud value: {raw_value}")
            return
        self.baud_var.set(str(numeric))
        self._save_app_state()


    def _on_zoom_selected(self, _event: object) -> None:
        raw = (self.zoom_var.get() or "").strip()
        if raw not in {"100%", "90%", "80%", "70%"}:
            self.zoom_var.set("100%")
        self._apply_dpi_scaling(force=True)
        self._save_app_state()


    def _on_connect_clicked(self) -> None:
        self._spawn(self._connect())


    def _on_disconnect_clicked(self) -> None:
        self._spawn(self._disconnect())


    def _on_auto_connect_toggled(self) -> None:
        self._save_app_state()


    def _on_profile_slot_selected(self, _event: object) -> None:
        slot = _slot_from_label(self.profile_slot_var.get())
        self._load_profile_slot(slot)
        self._select_key(self.selected_key)


    def _on_rename_profile_clicked(self) -> None:
        new_name = self.profile_rename_var.get().strip()
        if not new_name:
            return
        self.profile_names[self.profile_slot] = new_name
        self.profile.name = new_name
        self._sync_oled_controls_from_profile()
        self._refresh_profile_combo_values()
        self._save_app_state()
        self._log(f"Renamed profile slot {self.profile_slot} to '{new_name}'")
        self._spawn(self._push_profile_text_for_slot(self.profile_slot, reason="profile-rename"))


    def _on_save_binding_clicked(self) -> None:
        binding = self._binding_for(self.selected_key)
        requested_kind = self.action_type_var.get().strip().lower() or ACTION_NONE
        requested_value = self.action_value_var.get().strip()
        if requested_kind == ACTION_PYTHON and requested_value == INLINE_PYTHON_ACTION_VALUE:
            requested_kind = ACTION_NONE
            requested_value = ""
        kind, value = normalize_profile_action_kind_value(
            requested_kind,
            requested_value,
        )
        self.action_type_var.set(kind)
        self.action_value_var.set(value)
        binding.label = self.binding_label_var.get().strip() or f"Key {self.selected_key[0]},{self.selected_key[1]}"
        binding.action = KeyAction(
            kind=kind,
            value=value,
            steps=binding.action.steps,
        )
        self.profile.bindings[self.selected_key] = binding
        self._apply_profile_to_tiles()
        with suppress(Exception):
            self._save_profile_slot()
        self._update_selected_value_label()


    def _on_test_action_clicked(self) -> None:
        kind = self.action_type_var.get().strip().lower() or ACTION_NONE
        value = self.action_value_var.get().strip()
        if kind == ACTION_PYTHON and value == INLINE_PYTHON_ACTION_VALUE:
            self._spawn(self._execute_inline_script(self.selected_key))
            return
        action = KeyAction(kind=kind, value=value)
        self._spawn(self._execute_action_from_editor(action))


    def _on_save_encoder_actions_clicked(self) -> None:
        self.profile.enc_up_action = self._encoder_action_from_controls("up")
        self.profile.enc_down_action = self._encoder_action_from_controls("down")
        self.profile.enc_sw_down_action = self._encoder_action_from_controls("sw_down")
        self.profile.enc_sw_up_action = self._encoder_action_from_controls("sw_up")

        self._normalize_action_for_ui(self.profile.enc_up_action)
        self._normalize_action_for_ui(self.profile.enc_down_action)
        self._normalize_action_for_ui(self.profile.enc_sw_down_action)
        self._normalize_action_for_ui(self.profile.enc_sw_up_action)
        self._sync_encoder_controls_from_profile()
        self._save_profile_slot()
        self._log("Saved encoder actions.")


    def _on_test_encoder_up_clicked(self) -> None:
        self._spawn(self._execute_encoder_action("up"))


    def _on_test_encoder_down_clicked(self) -> None:
        self._spawn(self._execute_encoder_action("down"))


    def _on_test_encoder_sw_down_clicked(self) -> None:
        self._spawn(self._execute_encoder_action("sw_down"))


    def _on_test_encoder_sw_up_clicked(self) -> None:
        self._spawn(self._execute_encoder_action("sw_up"))


    async def _execute_action_from_editor(self, action: KeyAction) -> None:
        try:
            await self._execute_action_with_profile_support(action)
        except ActionExecutionError as exc:
            self._error_count += 1
            self._log(f"Test action failed: {exc}")


    async def _execute_encoder_action(self, direction: str, *, steps: int = 1) -> None:
        normalized = direction.strip().lower()
        if normalized == "up":
            action = self.profile.enc_up_action
            volume_direction = 1
        elif normalized == "down":
            action = self.profile.enc_down_action
            volume_direction = -1
        elif normalized == "sw_down":
            action = self.profile.enc_sw_down_action
            volume_direction = 1
        elif normalized == "sw_up":
            action = self.profile.enc_sw_up_action
            volume_direction = 1
        else:
            return
        if action.kind.strip().lower() in {"", ACTION_NONE}:
            return

        for _ in range(max(1, steps)):
            try:
                await self._execute_action_with_profile_support(action, volume_direction=volume_direction)
            except ActionExecutionError as exc:
                self._error_count += 1
                self._log(f"ENC {normalized} action failed: {exc}")
                return


    def _on_browse_action_clicked(self) -> None:
        self._browse_action_value(self.action_type_var.get(), self.action_value_var)


    def _on_browse_encoder_up_clicked(self) -> None:
        self._browse_action_value(self.enc_up_kind_var.get(), self.enc_up_value_var)


    def _on_browse_encoder_down_clicked(self) -> None:
        self._browse_action_value(self.enc_down_kind_var.get(), self.enc_down_value_var)


    def _on_browse_encoder_sw_down_clicked(self) -> None:
        self._browse_action_value(self.enc_sw_down_kind_var.get(), self.enc_sw_down_value_var)


    def _on_browse_encoder_sw_up_clicked(self) -> None:
        self._browse_action_value(self.enc_sw_up_kind_var.get(), self.enc_sw_up_value_var)


    def _browse_action_value(self, kind_text: str, target_var: tk.StringVar) -> None:
        kind, existing = normalize_profile_action_kind_value(kind_text, target_var.get())
        target_var.set(existing)
        if kind in {ACTION_AHK, ACTION_PYTHON, ACTION_FILE}:
            path = filedialog.askopenfilename(
                title="Select file",
                initialdir=self._resolve_dialog_directory(existing),
            )
            if path:
                target_var.set(path)
                self._remember_dialog_path(path)
            return
        if kind == ACTION_VOLUME_MIXER:
            picked = self._open_volume_mixer_picker(existing)
            if picked:
                target_var.set(picked)
            return
        if kind in {ACTION_KEYBOARD, ACTION_SEND_KEYS}:
            selected = self._open_keyboard_key_picker(target_var.get())
            if selected:
                target_var.set(selected)
            return
        if kind in {ACTION_CHANGE_PROFILE, ACTION_PROFILE_SET, ACTION_PROFILE_NEXT, ACTION_PROFILE_PREV}:
            picked = self._open_change_profile_picker(existing, initial_kind=kind)
            if picked:
                target_var.set(picked)
            return


    def _open_volume_mixer_picker(self, current_value: str) -> str | None:
        from ..volume_mixer import (
            VolumeMixerError,
            VolumeMixerSpec,
            VolumeMixerTarget,
            format_volume_mixer_value,
            list_volume_mixer_targets,
            parse_volume_mixer_value,
        )

        spec = parse_volume_mixer_value(current_value)
        try:
            targets = list_volume_mixer_targets()
        except VolumeMixerError as exc:
            messagebox.showerror("Volume Mixer", str(exc), parent=self.root)
            return None

        if not targets and not spec.target_value.strip():
            messagebox.showinfo(
                "Volume Mixer",
                "No active audio-session apps were found. Open the app and make sure it is producing audio.",
                parent=self.root,
            )
            return None

        current_target = spec.target_value.strip()
        current_kind = spec.target_kind.strip().lower() or "process"
        if current_target and not any(
            item.target_kind == current_kind and item.target_value.lower() == current_target.lower() for item in targets
        ):
            label = f"{current_target} (saved target)"
            targets.insert(0, VolumeMixerTarget(current_kind, current_target, label))

        dialog = tk.Toplevel(self.root)
        dialog.title("Select Volume Mixer App")
        dialog.transient(self.root)
        dialog.configure(bg=BG_PANEL)
        dialog.resizable(False, False)
        dialog.grab_set()

        result: dict[str, str | None] = {"value": None}
        step_percent = int(round((spec.step or 0.05) * 100))
        if step_percent == 0:
            step_percent = 5
        step_var = tk.StringVar(value=str(step_percent))

        tk.Label(
            dialog,
            text="Choose an app with an active Windows audio session",
            bg=BG_PANEL,
            fg=FG_ACCENT,
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w", padx=10, pady=(10, 6))

        list_frame = tk.Frame(dialog, bg=BG_PANEL)
        list_frame.pack(fill="both", expand=True, padx=10, pady=(0, 8))

        target_list = tk.Listbox(
            list_frame,
            width=42,
            height=10,
            bg=BG_INPUT,
            fg=FG_TEXT,
            selectbackground="#1D4ED8",
            selectforeground="#FFFFFF",
            relief="flat",
            activestyle="none",
            highlightthickness=1,
            highlightbackground=BORDER_MUTED,
            highlightcolor=BORDER_SELECTED,
            exportselection=False,
        )
        target_list.pack(side="left", fill="both", expand=True)
        scrollbar = tk.Scrollbar(list_frame, command=target_list.yview)
        scrollbar.pack(side="right", fill="y")
        target_list.configure(yscrollcommand=scrollbar.set)

        labels: list[str] = []
        for item in targets:
            labels.append(item.label)
            target_list.insert("end", item.label)

        default_index = 0
        for index, item in enumerate(targets):
            if item.target_kind == current_kind and item.target_value.lower() == current_target.lower():
                default_index = index
                break
        if labels:
            target_list.selection_set(default_index)
            target_list.see(default_index)

        options = tk.Frame(dialog, bg=BG_PANEL)
        options.pack(fill="x", padx=10, pady=(0, 8))
        tk.Label(options, text="Step %", bg=BG_PANEL, fg=FG_TEXT).pack(side="left")
        tk.Entry(
            options,
            textvariable=step_var,
            width=6,
            bg=BG_INPUT,
            fg=FG_TEXT,
            insertbackground=FG_TEXT,
            relief="flat",
        ).pack(side="left", padx=(8, 0))
        tk.Label(
            options,
            text="Use negative to invert direction. Up/down still apply their own direction on top.",
            bg=BG_PANEL,
            fg=FG_MUTED,
            font=("Segoe UI", 8),
        ).pack(side="left", padx=(10, 0))

        def _refresh_targets() -> None:
            selected_key = ""
            selected = target_list.curselection()
            if selected:
                current_item = targets[selected[0]]
                selected_key = f"{current_item.target_kind}:{current_item.target_value.lower()}"
            elif current_target:
                selected_key = f"{current_kind}:{current_target.lower()}"
            try:
                refreshed = list_volume_mixer_targets()
            except VolumeMixerError as exc:
                messagebox.showerror("Volume Mixer", str(exc), parent=dialog)
                return
            target_list.delete(0, "end")
            targets.clear()
            targets.extend(refreshed)
            if current_target and not any(
                item.target_kind == current_kind and item.target_value.lower() == current_target.lower()
                for item in targets
            ):
                targets.insert(0, VolumeMixerTarget(current_kind, current_target, f"{current_target} (saved target)"))
            for item in targets:
                target_list.insert("end", item.label)
            if targets:
                selected_index = 0
                for index, item in enumerate(targets):
                    target_key = f"{item.target_kind}:{item.target_value.lower()}"
                    if selected_key and target_key == selected_key:
                        selected_index = index
                        break
                target_list.selection_set(selected_index)
                target_list.see(selected_index)

        def _accept(_event: object | None = None) -> None:
            selected = target_list.curselection()
            if not selected:
                messagebox.showerror("Volume Mixer", "Select an app from the list.", parent=dialog)
                return
            raw_percent = step_var.get().strip()
            try:
                percent = int(raw_percent, 10)
            except ValueError:
                messagebox.showerror("Volume Mixer", "Step % must be an integer.", parent=dialog)
                return
            if percent == 0:
                messagebox.showerror("Volume Mixer", "Step % cannot be 0.", parent=dialog)
                return
            if percent > 100:
                percent = 100
            if percent < -100:
                percent = -100
            target = targets[selected[0]]
            result["value"] = format_volume_mixer_value(
                VolumeMixerSpec(
                    target_kind=target.target_kind,
                    target_value=target.target_value,
                    step=percent / 100.0,
                )
            )
            dialog.destroy()

        def _cancel() -> None:
            dialog.destroy()

        buttons = tk.Frame(dialog, bg=BG_PANEL)
        buttons.pack(fill="x", padx=10, pady=(0, 10))
        tk.Button(
            buttons,
            text="Refresh",
            bg="#334155",
            fg="#FFFFFF",
            relief="flat",
            padx=10,
            command=_refresh_targets,
        ).pack(side="left")
        tk.Button(
            buttons,
            text="Cancel",
            bg="#1F2937",
            fg=FG_TEXT,
            relief="flat",
            padx=10,
            command=_cancel,
        ).pack(side="right")
        tk.Button(
            buttons,
            text="Use App",
            bg="#2563EB",
            fg="#FFFFFF",
            relief="flat",
            padx=10,
            command=_accept,
        ).pack(side="right", padx=(0, 6))

        target_list.bind("<Double-Button-1>", _accept)
        target_list.bind("<Return>", _accept)
        dialog.bind("<Escape>", lambda _event: _cancel())
        dialog.protocol("WM_DELETE_WINDOW", _cancel)
        target_list.focus_set()
        self.root.wait_window(dialog)
        return result["value"]


    def _open_change_profile_picker(self, current_value: str, *, initial_kind: str) -> str | None:
        spec = parse_change_profile_value(current_value)
        kind = initial_kind.strip().lower()
        if kind == ACTION_PROFILE_SET:
            spec.mode = "set"
        elif kind == ACTION_PROFILE_PREV:
            spec.mode = "prev"
        elif kind == ACTION_PROFILE_NEXT:
            spec.mode = "next"

        dialog = tk.Toplevel(self.root)
        dialog.title("Change Profile")
        dialog.transient(self.root)
        dialog.configure(bg=BG_PANEL)
        dialog.resizable(False, False)
        dialog.grab_set()

        result: dict[str, str | None] = {"value": None}

        mode_var = tk.StringVar(value=spec.mode)
        target_var = tk.StringVar(value=str(spec.target if spec.target is not None else spec.min_slot))
        step_var = tk.StringVar(value=str(max(1, spec.step)))
        min_var = tk.StringVar(value=str(spec.min_slot))
        max_var = tk.StringVar(value=str(spec.max_slot))

        tk.Label(
            dialog,
            text="Configure profile change action",
            bg=BG_PANEL,
            fg=FG_ACCENT,
            font=("Segoe UI", 10, "bold"),
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(10, 8))

        tk.Label(dialog, text="Mode", bg=BG_PANEL, fg=FG_TEXT).grid(row=1, column=0, sticky="w", padx=10, pady=4)
        mode_combo = ttk.Combobox(
            dialog,
            textvariable=mode_var,
            values=list(PROFILE_CHANGE_MODES),
            state="readonly",
            width=22,
            style="Dark.TCombobox",
        )
        mode_combo.grid(row=1, column=1, sticky="ew", padx=(0, 10), pady=4)

        target_label = tk.Label(dialog, text="Target Slot", bg=BG_PANEL, fg=FG_TEXT)
        target_entry = tk.Entry(
            dialog,
            textvariable=target_var,
            bg=BG_INPUT,
            fg=FG_TEXT,
            insertbackground=FG_TEXT,
            relief="flat",
        )
        step_label = tk.Label(dialog, text="Step", bg=BG_PANEL, fg=FG_TEXT)
        step_entry = tk.Entry(
            dialog,
            textvariable=step_var,
            bg=BG_INPUT,
            fg=FG_TEXT,
            insertbackground=FG_TEXT,
            relief="flat",
        )

        min_label = tk.Label(dialog, text="Range Min", bg=BG_PANEL, fg=FG_TEXT)
        min_entry = tk.Entry(
            dialog,
            textvariable=min_var,
            bg=BG_INPUT,
            fg=FG_TEXT,
            insertbackground=FG_TEXT,
            relief="flat",
        )
        max_label = tk.Label(dialog, text="Range Max", bg=BG_PANEL, fg=FG_TEXT)
        max_entry = tk.Entry(
            dialog,
            textvariable=max_var,
            bg=BG_INPUT,
            fg=FG_TEXT,
            insertbackground=FG_TEXT,
            relief="flat",
        )
        min_label.grid(row=4, column=0, sticky="w", padx=10, pady=4)
        min_entry.grid(row=4, column=1, sticky="ew", padx=(0, 10), pady=4)
        max_label.grid(row=5, column=0, sticky="w", padx=10, pady=4)
        max_entry.grid(row=5, column=1, sticky="ew", padx=(0, 10), pady=4)

        def _refresh_mode_fields() -> None:
            mode = mode_var.get().strip().lower()
            target_label.grid_forget()
            target_entry.grid_forget()
            step_label.grid_forget()
            step_entry.grid_forget()
            if mode == "set":
                target_label.grid(row=2, column=0, sticky="w", padx=10, pady=4)
                target_entry.grid(row=2, column=1, sticky="ew", padx=(0, 10), pady=4)
            else:
                step_label.grid(row=2, column=0, sticky="w", padx=10, pady=4)
                step_entry.grid(row=2, column=1, sticky="ew", padx=(0, 10), pady=4)

        def _cancel() -> None:
            dialog.destroy()

        def _accept() -> None:
            mode = mode_var.get().strip().lower()
            if mode not in PROFILE_CHANGE_MODES:
                messagebox.showerror("Invalid Value", "Mode must be set, next, or prev.", parent=dialog)
                return

            min_slot = self._parse_positive_int(min_var.get(), field_name="Range Min", parent=dialog)
            if min_slot is None:
                return
            max_slot = self._parse_positive_int(max_var.get(), field_name="Range Max", parent=dialog)
            if max_slot is None:
                return
            if min_slot > max_slot:
                min_slot, max_slot = max_slot, min_slot

            if mode == "set":
                target = self._parse_positive_int(target_var.get(), field_name="Target Slot", parent=dialog)
                if target is None:
                    return
                spec_obj = ProfileChangeSpec(mode="set", target=target, min_slot=min_slot, max_slot=max_slot)
            else:
                step = self._parse_positive_int(step_var.get(), field_name="Step", parent=dialog)
                if step is None:
                    return
                spec_obj = ProfileChangeSpec(mode=mode, step=step, min_slot=min_slot, max_slot=max_slot)

            result["value"] = format_change_profile_value(spec_obj)
            dialog.destroy()

        mode_var.trace_add("write", lambda *_args: _refresh_mode_fields())
        _refresh_mode_fields()

        button_row = tk.Frame(dialog, bg=BG_PANEL)
        button_row.grid(row=6, column=0, columnspan=2, sticky="ew", padx=10, pady=(10, 10))
        tk.Button(
            button_row,
            text="Cancel",
            bg="#334155",
            fg="#FFFFFF",
            relief="flat",
            padx=10,
            command=_cancel,
        ).pack(side="right")
        tk.Button(
            button_row,
            text="Use",
            bg="#2563EB",
            fg="#FFFFFF",
            relief="flat",
            padx=10,
            command=_accept,
        ).pack(side="right", padx=(0, 6))

        dialog.grid_columnconfigure(1, weight=1)
        dialog.bind("<Escape>", lambda _event: _cancel())
        dialog.protocol("WM_DELETE_WINDOW", _cancel)
        mode_combo.focus_set()
        self.root.wait_window(dialog)
        return result["value"]


    def _parse_positive_int(self, raw: str, *, field_name: str, parent: tk.Misc) -> int | None:
        text = raw.strip()
        try:
            value = int(text, 10)
        except ValueError:
            messagebox.showerror("Invalid Value", f"{field_name} must be an integer.", parent=parent)
            return None
        if value < 1:
            messagebox.showerror("Invalid Value", f"{field_name} must be at least 1.", parent=parent)
            return None
        return value


    def _open_keyboard_key_picker(self, initial_value: str) -> str | None:
        dialog = tk.Toplevel(self.root)
        dialog.title("Select Keyboard Key")
        dialog.transient(self.root)
        dialog.configure(bg=BG_PANEL)
        dialog.resizable(False, False)
        dialog.grab_set()

        result: dict[str, str | None] = {"value": None}
        key_values = list(dict.fromkeys(item.strip().lower() for item in KEY_PICKER_KEYS if item.strip()))
        initial = initial_value.strip().lower()
        if initial and initial not in key_values:
            key_values.append(initial)

        tk.Label(
            dialog,
            text="Select a keyboard key:",
            bg=BG_PANEL,
            fg=FG_TEXT,
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w", padx=10, pady=(10, 6))

        filter_var = tk.StringVar(value=initial)
        filter_entry = tk.Entry(
            dialog,
            textvariable=filter_var,
            bg=BG_INPUT,
            fg=FG_TEXT,
            insertbackground=FG_TEXT,
            relief="flat",
        )
        filter_entry.pack(fill="x", padx=10)

        list_frame = tk.Frame(dialog, bg=BG_PANEL)
        list_frame.pack(fill="both", expand=True, padx=10, pady=(8, 8))

        key_list = tk.Listbox(
            list_frame,
            width=34,
            height=14,
            bg=BG_INPUT,
            fg=FG_TEXT,
            selectbackground="#1D4ED8",
            selectforeground="#FFFFFF",
            relief="flat",
            activestyle="none",
            highlightthickness=1,
            highlightbackground=BORDER_MUTED,
            highlightcolor=BORDER_SELECTED,
            exportselection=False,
        )
        key_list.pack(side="left", fill="both", expand=True)

        scrollbar = tk.Scrollbar(list_frame, command=key_list.yview)
        scrollbar.pack(side="right", fill="y")
        key_list.configure(yscrollcommand=scrollbar.set)

        filtered: list[str] = []

        def refresh_list() -> None:
            filtered.clear()
            query = filter_var.get().strip().lower()
            if query:
                filtered.extend([item for item in key_values if query in item])
            else:
                filtered.extend(key_values)

            key_list.delete(0, "end")
            for item in filtered:
                key_list.insert("end", item)

            if not filtered:
                return
            default_index = 0
            if initial in filtered:
                default_index = filtered.index(initial)
            key_list.selection_set(default_index)
            key_list.see(default_index)

        def accept(_event: object | None = None) -> None:
            selected = key_list.curselection()
            if not selected:
                return
            result["value"] = key_list.get(selected[0])
            dialog.destroy()

        def cancel() -> None:
            dialog.destroy()

        filter_var.trace_add("write", lambda *_args: refresh_list())
        key_list.bind("<Double-Button-1>", accept)
        key_list.bind("<Return>", accept)
        filter_entry.bind("<Return>", lambda _event: accept())
        dialog.bind("<Escape>", lambda _event: cancel())
        dialog.protocol("WM_DELETE_WINDOW", cancel)

        button_row = tk.Frame(dialog, bg=BG_PANEL)
        button_row.pack(fill="x", padx=10, pady=(0, 10))
        tk.Button(
            button_row,
            text="Cancel",
            bg="#1F2937",
            fg=FG_TEXT,
            activebackground="#374151",
            activeforeground="#FFFFFF",
            relief="flat",
            padx=10,
            command=cancel,
        ).pack(side="right", padx=(6, 0))
        tk.Button(
            button_row,
            text="Use Key",
            bg="#1D4ED8",
            fg="#FFFFFF",
            activebackground="#2563EB",
            activeforeground="#FFFFFF",
            relief="flat",
            padx=10,
            command=accept,
        ).pack(side="right")

        refresh_list()
        filter_entry.focus_set()
        self.root.wait_window(dialog)
        return result["value"]


