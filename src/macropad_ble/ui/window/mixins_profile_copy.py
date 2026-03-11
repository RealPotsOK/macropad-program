from __future__ import annotations

from .shared import *
from .shared import _slot_label


class ProfileCopyMixin:
    def _on_copy_to_slots_clicked(self) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title("Copy To Profile Slots")
        dialog.transient(self.root)
        dialog.configure(bg=BG_PANEL)
        dialog.resizable(False, False)
        dialog.grab_set()

        scope_var = tk.StringVar(value="key")
        all_others_var = tk.BooleanVar(value=True)
        slot_vars: dict[int, tk.BooleanVar] = {}

        for slot in range(1, 11):
            if slot == self.profile_slot:
                continue
            slot_vars[slot] = tk.BooleanVar(value=False)

        tk.Label(
            dialog,
            text="Copy current data to other profile slots",
            bg=BG_PANEL,
            fg=FG_ACCENT,
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor="w", padx=12, pady=(12, 6))

        key_row, key_col = self.selected_key
        tk.Label(
            dialog,
            text=f"Current slot: {self.profile_slot} | Selected key: {key_row},{key_col}",
            bg=BG_PANEL,
            fg=FG_MUTED,
        ).pack(anchor="w", padx=12, pady=(0, 8))

        scope_frame = tk.Frame(dialog, bg=BG_PANEL)
        scope_frame.pack(fill="x", padx=12, pady=(0, 10))
        tk.Radiobutton(
            scope_frame,
            text=f"Current key only ({key_row},{key_col})",
            variable=scope_var,
            value="key",
            bg=BG_PANEL,
            fg=FG_TEXT,
            selectcolor=BG_INPUT,
            activebackground=BG_PANEL,
            activeforeground=FG_TEXT,
        ).pack(anchor="w")
        tk.Radiobutton(
            scope_frame,
            text="Entire profile",
            variable=scope_var,
            value="profile",
            bg=BG_PANEL,
            fg=FG_TEXT,
            selectcolor=BG_INPUT,
            activebackground=BG_PANEL,
            activeforeground=FG_TEXT,
        ).pack(anchor="w", pady=(4, 0))

        tk.Checkbutton(
            dialog,
            text="Copy to all other slots",
            variable=all_others_var,
            bg=BG_PANEL,
            fg=FG_TEXT,
            selectcolor=BG_INPUT,
            activebackground=BG_PANEL,
            activeforeground=FG_TEXT,
        ).pack(anchor="w", padx=12, pady=(0, 8))

        targets_box = tk.Frame(dialog, bg=BG_INPUT, highlightthickness=1, highlightbackground=BORDER_MUTED)
        targets_box.pack(fill="x", padx=12, pady=(0, 10))

        tk.Label(
            targets_box,
            text="Or pick target slots:",
            bg=BG_INPUT,
            fg=FG_MUTED,
            font=("Segoe UI", 9, "bold"),
        ).grid(row=0, column=0, columnspan=3, sticky="w", padx=8, pady=(8, 6))

        slot_checks: list[tk.Checkbutton] = []
        columns = 3
        for index, slot in enumerate(sorted(slot_vars)):
            check = tk.Checkbutton(
                targets_box,
                text=_slot_label(slot, self.profile_names[slot]),
                variable=slot_vars[slot],
                bg=BG_INPUT,
                fg=FG_TEXT,
                selectcolor=BG_PANEL,
                activebackground=BG_INPUT,
                activeforeground=FG_TEXT,
                anchor="w",
                justify="left",
            )
            row = (index // columns) + 1
            col = index % columns
            check.grid(row=row, column=col, sticky="w", padx=8, pady=2)
            slot_checks.append(check)

        for col in range(columns):
            targets_box.grid_columnconfigure(col, weight=1)

        def _refresh_slots_state() -> None:
            state = "disabled" if all_others_var.get() else "normal"
            for check in slot_checks:
                check.configure(state=state)

        all_others_var.trace_add("write", lambda *_args: _refresh_slots_state())
        _refresh_slots_state()

        def _cancel() -> None:
            dialog.destroy()

        def _apply() -> None:
            targets = self._collect_copy_target_slots(all_others=all_others_var.get(), slot_vars=slot_vars)
            if not targets:
                messagebox.showwarning("No Targets", "Select at least one target slot.", parent=dialog)
                return

            scope = scope_var.get().strip().lower()
            if scope == "profile":
                copied, failed = self._copy_entire_profile_to_slots(targets)
                copied_name = "profile"
            else:
                copied, failed = self._copy_selected_key_to_slots(targets)
                copied_name = f"key {key_row},{key_col}"

            if copied:
                self._log(f"Copied {copied_name} to slots: {', '.join(str(slot) for slot in copied)}")
            if failed:
                self._error_count += len(failed)
                self._log(
                    "Copy failed for slots: "
                    + ", ".join(f"{slot} ({reason})" for slot, reason in failed)
                )

            if copied and not failed:
                messagebox.showinfo(
                    "Copy Complete",
                    f"Copied {copied_name} to slots: {', '.join(str(slot) for slot in copied)}",
                    parent=dialog,
                )
                dialog.destroy()
                return

            if copied and failed:
                messagebox.showwarning(
                    "Partial Copy",
                    (
                        f"Copied {copied_name} to slots: {', '.join(str(slot) for slot in copied)}\n"
                        + "Failed: "
                        + ", ".join(f"{slot}" for slot, _reason in failed)
                    ),
                    parent=dialog,
                )
                dialog.destroy()
                return

            messagebox.showerror("Copy Failed", "No slots were updated.", parent=dialog)

        button_row = tk.Frame(dialog, bg=BG_PANEL)
        button_row.pack(fill="x", padx=12, pady=(0, 12))
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
            text="Copy",
            bg="#2563EB",
            fg="#FFFFFF",
            relief="flat",
            padx=10,
            command=_apply,
        ).pack(side="right", padx=(0, 6))

        dialog.bind("<Escape>", lambda _event: _cancel())
        dialog.protocol("WM_DELETE_WINDOW", _cancel)
        self.root.wait_window(dialog)


    def _collect_copy_target_slots(
        self,
        *,
        all_others: bool,
        slot_vars: dict[int, tk.BooleanVar],
    ) -> list[int]:
        if all_others:
            return [slot for slot in range(1, 11) if slot != self.profile_slot]
        targets: list[int] = []
        for slot, flag in sorted(slot_vars.items()):
            if slot == self.profile_slot:
                continue
            if flag.get():
                targets.append(slot)
        return targets


    def _copy_selected_key_to_slots(self, slots: list[int]) -> tuple[list[int], list[tuple[int, str]]]:
        copied: list[int] = []
        failed: list[tuple[int, str]] = []
        source_binding = copy.deepcopy(self._binding_for(self.selected_key))

        for slot in slots:
            try:
                target_name = self.profile_names[slot]
                target_path = self._profile_path(slot)
                target_profile = load_profile(target_path, name=target_name, keys=self.keys)
                target_profile.name = target_name
                target_profile.bindings[self.selected_key] = copy.deepcopy(source_binding)
                save_profile(target_path, target_profile)
                copied.append(slot)
            except Exception as exc:
                failed.append((slot, str(exc)))
        return copied, failed


    def _copy_entire_profile_to_slots(self, slots: list[int]) -> tuple[list[int], list[tuple[int, str]]]:
        copied: list[int] = []
        failed: list[tuple[int, str]] = []
        source_profile = copy.deepcopy(self.profile)

        for slot in slots:
            try:
                target_profile = copy.deepcopy(source_profile)
                target_profile.name = self.profile_names[slot]
                save_profile(self._profile_path(slot), target_profile)
                copied.append(slot)
            except Exception as exc:
                failed.append((slot, str(exc)))
        return copied, failed
