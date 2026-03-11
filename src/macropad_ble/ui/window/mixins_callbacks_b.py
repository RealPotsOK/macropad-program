from __future__ import annotations

from .shared import *
from ..step_blocks import parse_step_script

class CallbacksBMixin:
    def _on_description_text_changed(self, *_args: object) -> None:
        self.description_preset_var.set(infer_description_preset_label(self.oled_line2_var.get()))


    def _on_description_preset_selected(self, _event: object | None = None) -> None:
        current_value = self.oled_line2_var.get()
        template = description_template_for_label(
            self.description_preset_var.get(),
            current_value=current_value,
        )
        if template != current_value:
            self.oled_line2_var.set(template)


    def _on_load_profile_clicked(self) -> None:
        self._load_profile_slot(self.profile_slot)
        self._select_key(self.selected_key)


    def _on_save_profile_clicked(self) -> None:
        self.profile.name = self.profile_names[self.profile_slot]
        self._save_profile_slot()
        self._spawn(self._push_profile_text_for_slot(self.profile_slot, reason="profile-save"))


    def _on_import_profile_clicked(self) -> None:
        path = filedialog.askopenfilename(
            title="Import Profile",
            filetypes=(("JSON files", "*.json"), ("All files", "*.*")),
        )
        if not path:
            return
        try:
            imported = load_profile(Path(path), name=self.profile_names[self.profile_slot], keys=self.keys)
        except Exception as exc:
            messagebox.showerror("Import Failed", str(exc))
            return
        self.profile = imported
        self.profile.name = self.profile_names[self.profile_slot]
        self._apply_profile_to_tiles()
        self._sync_oled_controls_from_profile()
        self._rebuild_script_cache()
        self._save_profile_slot()
        self._select_key(self.selected_key)
        self._log(f"Imported profile from {path}")
        self._spawn(self._push_profile_text_for_slot(self.profile_slot, reason="profile-import"))


    def _on_export_profile_clicked(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Export Profile",
            defaultextension=".json",
            filetypes=(("JSON files", "*.json"), ("All files", "*.*")),
        )
        if not path:
            return
        try:
            save_profile(Path(path), self.profile)
        except Exception as exc:
            messagebox.showerror("Export Failed", str(exc))
            return
        self._log(f"Exported profile to {path}")


    def _on_save_oled_text_clicked(self) -> None:
        self._apply_oled_controls_to_profile()
        self._save_profile_slot()
        self._spawn(self._push_profile_text_for_slot(self.profile_slot, reason="oled-save"))


    def _on_preview_oled_text_clicked(self) -> None:
        self._apply_oled_controls_to_profile()
        self._spawn(self._push_profile_text_for_slot(self.profile_slot, reason="oled-preview", force=True))


    def _on_script_key_selected(self, _event: object) -> None:
        if self._script_key_list is None:
            return
        selected = self._script_key_list.curselection()
        if not selected:
            return
        token = self._script_key_list.get(selected[0])
        parts = token.split(",", 1)
        if len(parts) != 2:
            return
        try:
            key = (int(parts[0]), int(parts[1]))
        except ValueError:
            return
        self._select_key(key)
    def _on_script_mode_changed(self, _event: object | None = None) -> None:
        self._refresh_script_editor_for_selected_key()


    def _on_step_blocks_changed(self) -> None:
        mode = (self.script_mode_var.get() or "").strip().lower()
        if mode != "step":
            return
        if self._step_editor is None:
            return
        count = len(self._step_editor.blocks)
        self.script_status_var.set(f"Step mode: {count} block(s). Click Save Script to persist.")


    def _refresh_script_editor_for_selected_key(self) -> None:
        binding = self._binding_for(self.selected_key)
        mode = (self.script_mode_var.get().strip().lower() or binding.script_mode or "python").strip().lower()
        if mode not in SCRIPT_MODES:
            mode = "python"
        self.script_mode_var.set(mode)

        if mode == "step":
            if self._script_text_panel is not None:
                self._script_text_panel.pack_forget()
            if self._step_panel is not None:
                self._step_panel.pack(fill="both", expand=True, padx=10, pady=(0, 6))
            if self._step_editor is not None:
                self._step_editor.load_script(binding.script_code or "")
                count = len(self._step_editor.blocks)
                self.script_status_var.set(
                    f"Step mode: {count} block(s). Drag to reorder. Save Script to apply."
                )
            self._script_editor_read_only = False
            self._script_linked_path = None
            return

        if self._step_panel is not None:
            self._step_panel.pack_forget()
        if self._script_text_panel is not None:
            self._script_text_panel.pack(fill="both", expand=True, padx=10, pady=(0, 6))
        preview_binding = KeyBinding(
            label=binding.label,
            action=binding.action,
            script_mode=mode,
            script_code=binding.script_code,
        )
        text, read_only, hint = self._script_text_for_editor(self.selected_key, preview_binding)
        self._script_editor_read_only = read_only
        self._script_linked_path = self._linked_python_action_path(preview_binding) if read_only else None

        if self._script_editor is not None:
            self._script_editor.configure(state="normal")
            self._script_editor.delete("1.0", "end")
            self._script_editor.insert("1.0", text)
            if read_only:
                self._script_editor.configure(state="disabled")

        if hint:
            self.script_status_var.set(hint)
        elif read_only:
            self.script_status_var.set("Linked action file is read-only in this editor.")


    def _on_save_script_clicked(self) -> None:
        binding = self._binding_for(self.selected_key)
        mode = self.script_mode_var.get().strip().lower() or "python"
        if mode not in SCRIPT_MODES:
            mode = "python"

        if mode == "step":
            if self._step_editor is None:
                return
            binding.script_mode = "step"
            binding.script_code = self._step_editor.dump_script()
            self._script_cache.pop(self.selected_key, None)
            self._script_cache_source.pop(self.selected_key, None)
            count = len(parse_step_script(binding.script_code))
            self.script_status_var.set(f"Saved {count} step block(s) for {self.selected_key[0]},{self.selected_key[1]}")
            self._save_profile_slot()
            self._update_selected_value_label()
            return

        if self._script_editor is None:
            return

        if mode == "python" and self._script_editor_read_only and self._script_linked_path is not None:
            self.script_status_var.set(f"Linked file is read-only here: {self._script_linked_path}")
            return

        binding.script_mode = mode
        binding.script_code = self._script_editor.get("1.0", "end-1c")
        if binding.script_mode in {"python", "ahk"}:
            self._upsert_workspace_section(binding.script_mode, self.selected_key, binding.script_code)
            self._sync_scripts_from_workspace(binding.script_mode, force=True, persist=False)
        if binding.script_mode == "python" and binding.script_code.strip():
            try:
                self._script_cache[self.selected_key] = compile(
                    binding.script_code,
                    str(self._runtime_script_path(self.selected_key, "python")),
                    "exec",
                )
                self._script_cache_source[self.selected_key] = binding.script_code
                self.script_status_var.set(f"Saved script for {self.selected_key[0]},{self.selected_key[1]}")
            except Exception as exc:
                self._error_count += 1
                self.script_status_var.set(f"Compile failed: {exc}")
                return
        else:
            self._script_cache.pop(self.selected_key, None)
            self._script_cache_source.pop(self.selected_key, None)
            self.script_status_var.set(f"Saved script for {self.selected_key[0]},{self.selected_key[1]}")
        self._save_profile_slot()
        self._update_selected_value_label()


    def _on_clear_script_clicked(self) -> None:
        binding = self._binding_for(self.selected_key)
        mode = (self.script_mode_var.get() or binding.script_mode or "python").strip().lower()
        if mode not in SCRIPT_MODES:
            mode = "python"

        if mode == "step":
            if self._step_editor is not None:
                self._step_editor.clear()
            binding.script_mode = "step"
            binding.script_code = ""
            self._script_cache.pop(self.selected_key, None)
            self._script_cache_source.pop(self.selected_key, None)
            self.script_status_var.set("Step blocks cleared.")
            self._save_profile_slot()
            self._update_selected_value_label()
            return

        if self._script_editor is None:
            return

        self._script_editor.configure(state="normal")
        self._script_editor.delete("1.0", "end")
        binding.script_code = ""
        self._script_cache.pop(self.selected_key, None)
        self._script_cache_source.pop(self.selected_key, None)
        if mode in {"python", "ahk"}:
            self._upsert_workspace_section(mode, self.selected_key, "")
            self._sync_scripts_from_workspace(mode, force=True, persist=False)
        self.script_status_var.set("Script cleared.")
        self._save_profile_slot()
        self._update_selected_value_label()


    def _on_run_script_clicked(self) -> None:
        self._spawn(self._execute_inline_script(self.selected_key))


    def _on_open_python_runtime_file_clicked(self) -> None:
        self._open_runtime_script_file("python")


    def _on_open_ahk_runtime_file_clicked(self) -> None:
        self._open_runtime_script_file("ahk")
    def _open_runtime_script_file(self, mode: str) -> None:
        normalized_mode = mode.strip().lower()
        if normalized_mode not in {"python", "ahk"}:
            return

        binding = self._binding_for(self.selected_key)

        if normalized_mode == "python":
            linked_path = self._linked_python_action_path(binding)
            if linked_path is not None:
                path = linked_path
            else:
                path = self._ensure_workspace_script(normalized_mode)
                self._sync_scripts_from_workspace(normalized_mode, force=True, persist=True)
        else:
            path = self._ensure_workspace_script(normalized_mode)
            self._sync_scripts_from_workspace(normalized_mode, force=True, persist=True)

        if binding.script_mode == normalized_mode:
            self.script_mode_var.set(normalized_mode)
            self._refresh_script_editor_for_selected_key()

        try:
            self._open_path_with_default_app(path)
            self.script_status_var.set(f"Opened {normalized_mode} file: {path}")
        except Exception as exc:
            self._error_count += 1
            self.script_status_var.set(f"Open {normalized_mode} file failed: {exc}")
            self._log(f"Open {normalized_mode} file failed: {exc}")


    def _copy_log(self) -> None:
        if self._log_text is None:
            return
        content = self._log_text.get("1.0", "end-1c")
        self.root.clipboard_clear()
        self.root.clipboard_append(content)
        self._log("Log copied to clipboard.")


    def _save_log(self) -> None:
        if self._log_text is None:
            return
        path = filedialog.asksaveasfilename(
            title="Save Diagnostics",
            defaultextension=".log",
            filetypes=(("Log files", "*.log"), ("Text files", "*.txt"), ("All files", "*.*")),
        )
        if not path:
            return
        Path(path).write_text(self._log_text.get("1.0", "end-1c"), encoding="utf-8")
        self._log(f"Saved log to {path}")


    def _clear_log(self) -> None:
        if self._log_text is None:
            return
        self._log_text.configure(state="normal")
        self._log_text.delete("1.0", "end")
        self._log_text.configure(state="disabled")


    def _open_profiles_folder(self) -> None:
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        try:
            import os

            if hasattr(os, "startfile"):
                os.startfile(str(self.profile_dir))  # type: ignore[attr-defined]
                return
        except Exception as exc:
            self._error_count += 1
            self._log(f"Could not open profiles folder: {exc}")
            return
        self._log(f"Profiles folder: {self.profile_dir.resolve()}")


    def _animate_tiles(self) -> None:
        for tile in self.tiles.values():
            fill_color = KEY_BG
            if tile.selected:
                fill_color = KEY_BG_SELECTED
            if tile.pressed:
                fill_color = KEY_BG_PRESSED
            for stripe in tile.stripes:
                tile.canvas.itemconfigure(stripe, fill=fill_color)

            border_color = BORDER_MUTED
            if tile.selected:
                border_color = BORDER_SELECTED
            elif tile.pressed:
                border_color = "#4ADE80"
            tile.canvas.itemconfigure(tile.border, outline=border_color)

            state_color = "#A7F3D0" if tile.pressed else "#E2E8F0"
            tile.canvas.itemconfigure(tile.state, fill=state_color)


    def _update_rate_metrics(self) -> None:
        now = time.monotonic()
        while self._event_times and now - self._event_times[0] > 5.0:
            self._event_times.popleft()
        rate = len(self._event_times) / 5.0
        self.rate_var.set(f"Rate: {rate:.1f} evt/s")
        self.error_var.set(f"Errors: {self._error_count}")
        with suppress(Exception):
            if sys.platform == "win32":
                point = ctypes.wintypes.POINT()  # type: ignore[attr-defined]
                if ctypes.windll.user32.GetCursorPos(ctypes.byref(point)):
                    pointer_x, pointer_y = int(point.x), int(point.y)
                else:
                    pointer_x, pointer_y = self.root.winfo_pointerxy()
            else:
                pointer_x, pointer_y = self.root.winfo_pointerxy()
            self.mouse_var.set(f"Mouse: {pointer_x}, {pointer_y}")

        if self._last_packet_monotonic is None:
            self.packet_var.set("Last packet: --")
            return
        age = now - self._last_packet_monotonic
        self.packet_var.set(f"Last packet: {self._last_packet_clock} ({age:.1f}s ago)")


    async def run(self) -> int:
        try:
            while not self._closing:
                try:
                    self.root.update()
                except tk.TclError:
                    self._request_exit()
                    break
                self._poll_desktop_events()
                self._animate_tiles()
                self._update_rate_metrics()
                await asyncio.sleep(0.03)
        finally:
            await self._disconnect()
            for task in list(self._background_tasks):
                task.cancel()
            for task in list(self._background_tasks):
                with suppress(asyncio.CancelledError):
                    await task
            self._shutdown_desktop_resources()
            with suppress(Exception):
                self.root.destroy()
        return 0











