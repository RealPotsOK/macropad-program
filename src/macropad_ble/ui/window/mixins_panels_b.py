from __future__ import annotations

from .shared import *
from .step_editor import StepEditor

class PanelsBMixin:
    def _build_profiles_panel(self, parent: tk.Frame) -> None:
        section = tk.Frame(parent, bg=BG_PANEL, highlightthickness=1, highlightbackground=BORDER_MUTED)
        section.pack(fill="x", pady=(0, 10))

        tk.Label(
            section,
            text="Profiles (up to 10)",
            bg=BG_PANEL,
            fg=FG_ACCENT,
            font=("Segoe UI", 12, "bold"),
        ).pack(anchor="w", padx=10, pady=(10, 8))

        row1 = tk.Frame(section, bg=BG_PANEL)
        row1.pack(fill="x", padx=10, pady=(0, 8))
        tk.Label(row1, text="Slot", bg=BG_PANEL, fg=FG_TEXT).pack(side="left")
        self._profile_combo = ttk.Combobox(
            row1,
            textvariable=self.profile_slot_var,
            state="readonly",
            width=26,
            style="Dark.TCombobox",
        )
        self._profile_combo.pack(side="left", padx=(8, 0), fill="x", expand=True)
        self._profile_combo.bind("<<ComboboxSelected>>", self._on_profile_slot_selected)
        self._refresh_profile_combo_values()

        row2 = tk.Frame(section, bg=BG_PANEL)
        row2.pack(fill="x", padx=10, pady=(0, 8))
        tk.Label(row2, text="Rename", bg=BG_PANEL, fg=FG_TEXT).pack(side="left")
        tk.Entry(
            row2,
            textvariable=self.profile_rename_var,
            bg=BG_INPUT,
            fg=FG_TEXT,
            insertbackground=FG_TEXT,
            relief="flat",
            width=20,
        ).pack(side="left", padx=(8, 0), fill="x", expand=True)
        tk.Button(
            row2,
            text="Apply",
            bg="#1E3A8A",
            fg="#FFFFFF",
            activebackground="#1D4ED8",
            activeforeground="#FFFFFF",
            relief="flat",
            padx=8,
            command=self._on_rename_profile_clicked,
        ).pack(side="left", padx=(6, 0))

        row3 = tk.Frame(section, bg=BG_PANEL)
        row3.pack(fill="x", padx=10, pady=(0, 10))
        tk.Button(
            row3,
            text="Load Slot",
            bg="#334155",
            fg="#FFFFFF",
            relief="flat",
            padx=8,
            command=self._on_load_profile_clicked,
        ).pack(side="left")
        tk.Button(
            row3,
            text="Save Slot",
            bg="#2563EB",
            fg="#FFFFFF",
            relief="flat",
            padx=8,
            command=self._on_save_profile_clicked,
        ).pack(side="left", padx=(6, 0))
        tk.Button(
            row3,
            text="Import",
            bg="#0F766E",
            fg="#FFFFFF",
            relief="flat",
            padx=8,
            command=self._on_import_profile_clicked,
        ).pack(side="left", padx=(6, 0))
        tk.Button(
            row3,
            text="Export",
            bg="#7C3AED",
            fg="#FFFFFF",
            relief="flat",
            padx=8,
            command=self._on_export_profile_clicked,
        ).pack(side="left", padx=(6, 0))

        row5 = tk.Frame(section, bg=BG_PANEL)
        row5.pack(fill="x", padx=10, pady=(0, 6))
        tk.Label(row5, text="Description", bg=BG_PANEL, fg=FG_TEXT).pack(side="left")
        tk.Entry(
            row5,
            textvariable=self.oled_line2_var,
            bg=BG_INPUT,
            fg=FG_TEXT,
            insertbackground=FG_TEXT,
            relief="flat",
            width=28,
        ).pack(side="left", padx=(8, 0), fill="x", expand=True)

        row6 = tk.Frame(section, bg=BG_PANEL)
        row6.pack(fill="x", padx=10, pady=(0, 6))
        tk.Label(row6, text="Preset", bg=BG_PANEL, fg=FG_TEXT).pack(side="left")
        self._description_preset_combo = ttk.Combobox(
            row6,
            textvariable=self.description_preset_var,
            values=DESCRIPTION_PRESET_LABELS,
            state="readonly",
            width=22,
            style="Dark.TCombobox",
        )
        self._description_preset_combo.pack(side="left", padx=(8, 0))
        self._description_preset_combo.bind("<<ComboboxSelected>>", self._on_description_preset_selected)

        row7 = tk.Frame(section, bg=BG_PANEL)
        row7.pack(fill="x", padx=10, pady=(0, 8))
        tk.Label(
            row7,
            text="Use | for extra OLED lines. Line 1 stays the profile name, then the device handles line wrapping and layout.",
            bg=BG_PANEL,
            fg=FG_MUTED,
            font=("Segoe UI", 8),
        ).pack(side="left")

        row8 = tk.Frame(section, bg=BG_PANEL)
        row8.pack(fill="x", padx=10, pady=(0, 8))
        tk.Label(
            row8,
            text="Sent to device as: TXT:<PROFILE NAME>|<DESCRIPTION>",
            bg=BG_PANEL,
            fg=FG_MUTED,
            font=("Segoe UI", 8),
        ).pack(side="left")
        tk.Button(
            row8,
            text="Save Description",
            bg="#0F766E",
            fg="#FFFFFF",
            relief="flat",
            padx=8,
            command=self._on_save_oled_text_clicked,
        ).pack(side="right")
        tk.Button(
            row8,
            text="Preview Text",
            bg="#1E3A8A",
            fg="#FFFFFF",
            relief="flat",
            padx=8,
            command=self._on_preview_oled_text_clicked,
        ).pack(side="right", padx=(0, 6))

        row9 = tk.Frame(section, bg=BG_PANEL)
        row9.pack(fill="x", padx=10, pady=(0, 10))
        tk.Button(
            row9,
            text="Copy To Slots...",
            bg="#0B5ED7",
            fg="#FFFFFF",
            relief="flat",
            padx=10,
            command=self._on_copy_to_slots_clicked,
        ).pack(side="left")


    def _build_log_panel(self, parent: tk.Frame) -> None:
        section = tk.Frame(parent, bg=BG_PANEL, highlightthickness=1, highlightbackground=BORDER_MUTED)
        section.pack(fill="both", expand=True)

        tk.Label(
            section,
            text="Diagnostics",
            bg=BG_PANEL,
            fg=FG_ACCENT,
            font=("Segoe UI", 12, "bold"),
        ).pack(anchor="w", padx=10, pady=(10, 8))

        area = tk.Frame(section, bg=BG_PANEL)
        area.pack(fill="both", expand=True, padx=10)
        self._log_text = tk.Text(
            area,
            height=12,
            wrap="word",
            bg="#020617",
            fg="#DDE7FF",
            insertbackground="#DDE7FF",
            relief="flat",
            font=("Consolas", 10),
        )
        scrollbar = tk.Scrollbar(area, command=self._log_text.yview)
        self._log_text.configure(yscrollcommand=scrollbar.set, state="disabled")
        self._log_text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        buttons = tk.Frame(section, bg=BG_PANEL)
        buttons.pack(fill="x", padx=10, pady=(8, 10))
        tk.Button(
            buttons,
            text="Copy Log",
            bg="#1D4ED8",
            fg="#FFFFFF",
            relief="flat",
            padx=8,
            command=self._copy_log,
        ).pack(side="left")
        tk.Button(
            buttons,
            text="Save Log",
            bg="#0F766E",
            fg="#FFFFFF",
            relief="flat",
            padx=8,
            command=self._save_log,
        ).pack(side="left", padx=(6, 0))
        tk.Button(
            buttons,
            text="Clear Log",
            bg="#334155",
            fg="#FFFFFF",
            relief="flat",
            padx=8,
            command=self._clear_log,
        ).pack(side="left", padx=(6, 0))
        tk.Button(
            buttons,
            text="Open Profiles Folder",
            bg="#4C1D95",
            fg="#FFFFFF",
            relief="flat",
            padx=8,
            command=self._open_profiles_folder,
        ).pack(side="left", padx=(6, 0))


    def _build_scripts_tab(self, parent: tk.Frame) -> None:
        container = tk.Frame(parent, bg=BG_APP, padx=8, pady=8)
        container.pack(fill="both", expand=True)

        tk.Label(
            container,
            text="Scripts Tab (Python / AHK / File / Step Blocks)",
            bg=BG_APP,
            fg=FG_ACCENT,
            font=("Segoe UI", 13, "bold"),
        ).pack(anchor="w", pady=(0, 6))
        tk.Label(
            container,
            text=(
                "Step mode is a visual block chain. Drag rows to reorder, then Save Script.\n"
                "If/While run blocks until End. Repeat still applies to only the next block."
            ),
            bg=BG_APP,
            fg=FG_MUTED,
            justify="left",
        ).pack(anchor="w", pady=(0, 8))

        body = tk.PanedWindow(container, orient=tk.HORIZONTAL, sashwidth=6, bg=BG_APP, bd=0, relief="flat")
        body.pack(fill="both", expand=True)

        left = tk.Frame(body, bg=BG_PANEL, highlightthickness=1, highlightbackground=BORDER_MUTED)
        right = tk.Frame(body, bg=BG_PANEL, highlightthickness=1, highlightbackground=BORDER_MUTED)
        body.add(left)
        body.add(right)
        self._scripts_body = body

        tk.Label(left, text="Keys", bg=BG_PANEL, fg=FG_ACCENT, font=("Segoe UI", 11, "bold")).pack(
            anchor="w", padx=10, pady=(10, 6)
        )
        self._script_key_list = tk.Listbox(
            left,
            bg=BG_INPUT,
            fg=FG_TEXT,
            selectbackground="#1D4ED8",
            selectforeground="#FFFFFF",
            activestyle="none",
            relief="flat",
            font=("Consolas", 11),
        )
        self._script_key_list.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self._script_key_list.bind("<<ListboxSelect>>", self._on_script_key_selected)
        for row, col in self.keys:
            self._script_key_list.insert("end", f"{row},{col}")

        top = tk.Frame(right, bg=BG_PANEL)
        top.pack(fill="x", padx=10, pady=(10, 8))
        tk.Label(top, text="Profile", bg=BG_PANEL, fg=FG_TEXT).pack(side="left")
        self._script_profile_combo = ttk.Combobox(
            top,
            textvariable=self.profile_slot_var,
            state="readonly",
            width=26,
            style="Dark.TCombobox",
        )
        self._script_profile_combo.pack(side="left", padx=(6, 12))
        self._script_profile_combo.bind("<<ComboboxSelected>>", self._on_profile_slot_selected)

        tk.Label(top, text="Mode", bg=BG_PANEL, fg=FG_TEXT).pack(side="left")
        self._script_mode_combo = ttk.Combobox(
            top,
            textvariable=self.script_mode_var,
            values=SCRIPT_MODES,
            state="readonly",
            width=14,
            style="Dark.TCombobox",
        )
        self._script_mode_combo.pack(side="left", padx=(6, 12))
        self._script_mode_combo.bind("<<ComboboxSelected>>", self._on_script_mode_changed)
        self._refresh_profile_combo_values()

        tk.Button(
            top,
            text="Save Script",
            bg="#2563EB",
            fg="#FFFFFF",
            relief="flat",
            padx=10,
            command=self._on_save_script_clicked,
        ).pack(side="left")
        tk.Button(
            top,
            text="Run Now",
            bg="#0F766E",
            fg="#FFFFFF",
            relief="flat",
            padx=10,
            command=self._on_run_script_clicked,
        ).pack(side="left", padx=(6, 0))
        tk.Button(
            top,
            text="Clear Script",
            bg="#475569",
            fg="#FFFFFF",
            relief="flat",
            padx=10,
            command=self._on_clear_script_clicked,
        ).pack(side="left", padx=(6, 0))
        tk.Button(
            top,
            text="Open Python File",
            bg="#1E40AF",
            fg="#FFFFFF",
            relief="flat",
            padx=10,
            command=self._on_open_python_runtime_file_clicked,
        ).pack(side="left", padx=(12, 0))
        tk.Button(
            top,
            text="Open AHK File",
            bg="#7C3AED",
            fg="#FFFFFF",
            relief="flat",
            padx=10,
            command=self._on_open_ahk_runtime_file_clicked,
        ).pack(side="left", padx=(6, 0))

        self._script_text_panel = tk.Frame(right, bg=BG_PANEL)
        self._script_text_panel.pack(fill="both", expand=True, padx=10, pady=(0, 6))

        self._script_editor = tk.Text(
            self._script_text_panel,
            wrap="none",
            bg="#020617",
            fg="#DDE7FF",
            insertbackground="#DDE7FF",
            relief="flat",
            font=("Consolas", 11),
        )
        script_scroll_y = tk.Scrollbar(self._script_text_panel, command=self._script_editor.yview)
        script_scroll_x = tk.Scrollbar(self._script_text_panel, command=self._script_editor.xview, orient="horizontal")
        self._script_editor.configure(yscrollcommand=script_scroll_y.set, xscrollcommand=script_scroll_x.set)
        self._script_editor.pack(side="left", fill="both", expand=True)
        script_scroll_y.pack(side="right", fill="y")
        script_scroll_x.pack(side="bottom", fill="x")

        self._step_panel = tk.Frame(right, bg=BG_PANEL)
        self._step_editor = StepEditor(self._step_panel, on_change=self._on_step_blocks_changed)
        self._step_panel.pack_forget()

        tk.Label(
            right,
            textvariable=self.script_status_var,
            bg=BG_PANEL,
            fg=FG_MUTED,
            justify="left",
        ).pack(anchor="w", padx=10, pady=(0, 10))






