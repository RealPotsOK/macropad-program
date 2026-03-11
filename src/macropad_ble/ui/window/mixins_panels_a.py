from __future__ import annotations

from .shared import *


class PanelsAMixin:
    _tile_base_width = 148
    _tile_base_height = 84
    _tile_base_gap_x = 3
    _tile_base_gap_y = 1

    def _key_grid_metrics(self, zoom_factor: float | None = None) -> tuple[int, int, int, int]:
        factor = zoom_factor
        if factor is None:
            factor = self._last_zoom_factor or self._zoom_factor()
        width = max(94, int(round(self._tile_base_width * factor)))
        height = max(56, int(round(self._tile_base_height * factor)))
        gap_x = max(1, int(round(self._tile_base_gap_x * factor)))
        gap_y = max(0, int(round(self._tile_base_gap_y * factor)))
        return width, height, gap_x, gap_y

    def _tile_font_sizes(self, zoom_factor: float | None = None) -> tuple[int, int, int]:
        factor = zoom_factor
        if factor is None:
            factor = self._last_zoom_factor or self._zoom_factor()
        badge = max(6, int(round(8 * factor)))
        title = max(8, int(round(11 * factor)))
        state = max(8, int(round(10 * factor)))
        return badge, title, state

    def _apply_key_grid_zoom(self, zoom_factor: float | None = None) -> None:
        width, height, gap_x, gap_y = self._key_grid_metrics(zoom_factor)
        badge_size, title_size, state_size = self._tile_font_sizes(zoom_factor)
        title_y = max(24, int(round(height * 0.43)))
        state_y = max(title_y + 16, int(round(height * 0.75)))

        for tile in self.tiles.values():
            tile.canvas.configure(width=width, height=height)
            tile.canvas.grid_configure(padx=gap_x, pady=gap_y)
            tile.canvas.coords(tile.border, 2, 2, width - 2, height - 2)
            for stripe in tile.stripes:
                tile.canvas.coords(stripe, 3, 3, width - 3, height - 3)
            tile.canvas.coords(tile.badge, width - 8, 10)
            tile.canvas.coords(tile.title, width // 2, title_y)
            tile.canvas.coords(tile.state, width // 2, state_y)
            tile.canvas.itemconfigure(tile.badge, font=("Segoe UI", badge_size, "bold"))
            tile.canvas.itemconfigure(tile.title, width=width - 18, font=("Segoe UI Semibold", title_size))
            tile.canvas.itemconfigure(tile.state, font=("Segoe UI", state_size, "bold"))

    def _build_key_grid(self, parent: tk.Frame) -> None:
        tk.Label(
            parent,
            text="Key Matrix",
            bg=BG_APP,
            fg=FG_ACCENT,
            font=("Segoe UI", 13, "bold"),
        ).pack(anchor="w", pady=(0, 6))

        grid = tk.Frame(parent, bg=BG_APP)
        grid.pack(anchor="n")
        self._key_grid_container = grid

        tile_width, tile_height, gap_x, gap_y = self._key_grid_metrics()
        badge_size, title_size, state_size = self._tile_font_sizes()
        title_y = max(24, int(round(tile_height * 0.43)))
        state_y = max(title_y + 16, int(round(tile_height * 0.75)))

        for key in self.keys:
            mapped = map_key_to_display(*key)
            if mapped is None:
                continue
            display_row, display_col = mapped
            row, col = key

            canvas = tk.Canvas(
                grid,
                width=tile_width,
                height=tile_height,
                bg=BG_APP,
                bd=0,
                highlightthickness=0,
                relief="flat",
            )
            canvas.grid(row=display_row, column=display_col, padx=gap_x, pady=gap_y, sticky="nw")

            border = canvas.create_rectangle(2, 2, tile_width - 2, tile_height - 2, outline=BORDER_MUTED, width=2)

            fill_rect = canvas.create_rectangle(3, 3, tile_width - 3, tile_height - 3, outline="", fill=KEY_BG)
            stripes = [fill_rect]

            badge = canvas.create_text(
                tile_width - 8,
                10,
                text=f"R{row} C{col}",
                fill="#F8FAFC",
                font=("Segoe UI", badge_size, "bold"),
                anchor="ne",
            )
            title = canvas.create_text(
                tile_width // 2,
                title_y,
                text=f"Key {row},{col}",
                fill="#FFFFFF",
                width=tile_width - 18,
                font=("Segoe UI Semibold", title_size),
                justify="center",
            )
            state = canvas.create_text(
                tile_width // 2,
                state_y,
                text="UP",
                fill="#E2E8F0",
                font=("Segoe UI", state_size, "bold"),
            )

            for item in [border, *stripes, badge, title, state]:
                canvas.tag_bind(item, "<Button-1>", lambda _evt, key_id=key: self._select_key(key_id))
            canvas.bind("<Button-1>", lambda _evt, key_id=key: self._select_key(key_id))

            self.tiles[key] = TileWidgets(
                canvas=canvas,
                border=border,
                stripes=stripes,
                title=title,
                state=state,
                badge=badge,
                display_row=display_row,
                display_col=display_col,
            )

    def _build_side_panel(self, parent: tk.Frame) -> None:
        self._build_selected_key_panel(parent)
        self._build_log_panel(parent)

    def _build_selected_key_panel(self, parent: tk.Frame) -> None:
        section = tk.Frame(parent, bg=BG_PANEL, highlightthickness=1, highlightbackground=BORDER_MUTED)
        section.pack(fill="x", pady=(0, 10))

        tk.Label(
            section,
            text="Selected Key",
            bg=BG_PANEL,
            fg=FG_ACCENT,
            font=("Segoe UI", 12, "bold"),
        ).pack(anchor="w", padx=10, pady=(10, 6))
        tk.Label(section, textvariable=self.selected_key_var, bg=BG_PANEL, fg=FG_TEXT).pack(anchor="w", padx=10)
        tk.Label(section, textvariable=self.selected_value_var, bg=BG_PANEL, fg=FG_MUTED).pack(
            anchor="w", padx=10, pady=(0, 8)
        )

        form = tk.Frame(section, bg=BG_PANEL)
        form.pack(fill="x", padx=10, pady=(0, 8))
        form.grid_columnconfigure(1, weight=1)

        tk.Label(form, text="Label", bg=BG_PANEL, fg=FG_TEXT).grid(row=0, column=0, sticky="w")
        tk.Entry(
            form,
            textvariable=self.binding_label_var,
            bg=BG_INPUT,
            fg=FG_TEXT,
            insertbackground=FG_TEXT,
            relief="flat",
        ).grid(row=0, column=1, sticky="ew", padx=(8, 0), pady=(0, 8))

        tk.Label(form, text="Action", bg=BG_PANEL, fg=FG_TEXT).grid(row=1, column=0, sticky="w")
        ttk.Combobox(
            form,
            textvariable=self.action_type_var,
            values=ACTION_TYPES,
            state="readonly",
            style="Dark.TCombobox",
        ).grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=(0, 8))

        tk.Label(form, text="Value", bg=BG_PANEL, fg=FG_TEXT).grid(row=2, column=0, sticky="w")
        value_row = tk.Frame(form, bg=BG_PANEL)
        value_row.grid(row=2, column=1, sticky="ew", padx=(8, 0))
        value_row.grid_columnconfigure(0, weight=1)
        tk.Entry(
            value_row,
            textvariable=self.action_value_var,
            bg=BG_INPUT,
            fg=FG_TEXT,
            insertbackground=FG_TEXT,
            relief="flat",
        ).grid(row=0, column=0, sticky="ew")
        tk.Button(
            value_row,
            text="Browse",
            bg="#1E3A8A",
            fg="#FFFFFF",
            activebackground="#1D4ED8",
            activeforeground="#FFFFFF",
            relief="flat",
            padx=8,
            command=self._on_browse_action_clicked,
        ).grid(row=0, column=1, padx=(6, 0), sticky="e")

        tk.Checkbutton(
            form,
            text="Learn / Bind mode",
            variable=self.learn_mode_var,
            bg=BG_PANEL,
            fg=FG_TEXT,
            selectcolor=BG_INPUT,
            activebackground=BG_PANEL,
            activeforeground=FG_TEXT,
        ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(8, 2))

        tk.Label(
            form,
            text="Learn mode: press a pad key to auto-select it for editing.",
            bg=BG_PANEL,
            fg=FG_MUTED,
            font=("Segoe UI", 8),
        ).grid(row=4, column=0, columnspan=2, sticky="w")

        buttons = tk.Frame(section, bg=BG_PANEL)
        buttons.pack(fill="x", padx=10, pady=(8, 10))
        tk.Button(
            buttons,
            text="Save Binding",
            bg="#2563EB",
            fg="#FFFFFF",
            activebackground="#1D4ED8",
            activeforeground="#FFFFFF",
            relief="flat",
            padx=10,
            command=self._on_save_binding_clicked,
        ).pack(side="left")
        tk.Button(
            buttons,
            text="Test Action",
            bg="#334155",
            fg="#FFFFFF",
            activebackground="#475569",
            activeforeground="#FFFFFF",
            relief="flat",
            padx=10,
            command=self._on_test_action_clicked,
        ).pack(side="left", padx=(8, 0))

    def _build_encoder_panel(self, parent: tk.Frame) -> None:
        section = tk.Frame(parent, bg=BG_PANEL, highlightthickness=1, highlightbackground=BORDER_MUTED)
        section.pack(fill="x", pady=(14, 10))

        tk.Label(
            section,
            text="Encoder (ENC)",
            bg=BG_PANEL,
            fg=FG_ACCENT,
            font=("Segoe UI", 12, "bold"),
        ).pack(anchor="w", padx=10, pady=(10, 6))

        form = tk.Frame(section, bg=BG_PANEL)
        form.pack(fill="x", padx=10, pady=(0, 8))
        form.grid_columnconfigure(2, weight=1)

        tk.Label(form, text="Turn Up", bg=BG_PANEL, fg=FG_TEXT).grid(row=0, column=0, sticky="w", pady=(0, 8))
        ttk.Combobox(
            form,
            textvariable=self.enc_up_kind_var,
            values=ACTION_TYPES,
            state="readonly",
            width=12,
            style="Dark.TCombobox",
        ).grid(row=0, column=1, sticky="w", padx=(8, 8), pady=(0, 8))
        up_value_row = tk.Frame(form, bg=BG_PANEL)
        up_value_row.grid(row=0, column=2, sticky="ew", pady=(0, 8))
        up_value_row.grid_columnconfigure(0, weight=1)
        tk.Entry(
            up_value_row,
            textvariable=self.enc_up_value_var,
            bg=BG_INPUT,
            fg=FG_TEXT,
            insertbackground=FG_TEXT,
            relief="flat",
        ).grid(row=0, column=0, sticky="ew")
        tk.Button(
            up_value_row,
            text="Browse",
            bg="#1E3A8A",
            fg="#FFFFFF",
            activebackground="#1D4ED8",
            activeforeground="#FFFFFF",
            relief="flat",
            padx=8,
            command=self._on_browse_encoder_up_clicked,
        ).grid(row=0, column=1, padx=(6, 0))

        tk.Label(form, text="Turn Down", bg=BG_PANEL, fg=FG_TEXT).grid(row=1, column=0, sticky="w")
        ttk.Combobox(
            form,
            textvariable=self.enc_down_kind_var,
            values=ACTION_TYPES,
            state="readonly",
            width=12,
            style="Dark.TCombobox",
        ).grid(row=1, column=1, sticky="w", padx=(8, 8))
        down_value_row = tk.Frame(form, bg=BG_PANEL)
        down_value_row.grid(row=1, column=2, sticky="ew")
        down_value_row.grid_columnconfigure(0, weight=1)
        tk.Entry(
            down_value_row,
            textvariable=self.enc_down_value_var,
            bg=BG_INPUT,
            fg=FG_TEXT,
            insertbackground=FG_TEXT,
            relief="flat",
        ).grid(row=0, column=0, sticky="ew")
        tk.Button(
            down_value_row,
            text="Browse",
            bg="#1E3A8A",
            fg="#FFFFFF",
            activebackground="#1D4ED8",
            activeforeground="#FFFFFF",
            relief="flat",
            padx=8,
            command=self._on_browse_encoder_down_clicked,
        ).grid(row=0, column=1, padx=(6, 0))

        tk.Label(form, text="Switch Down", bg=BG_PANEL, fg=FG_TEXT).grid(row=2, column=0, sticky="w", pady=(8, 8))
        ttk.Combobox(
            form,
            textvariable=self.enc_sw_down_kind_var,
            values=ACTION_TYPES,
            state="readonly",
            width=12,
            style="Dark.TCombobox",
        ).grid(row=2, column=1, sticky="w", padx=(8, 8), pady=(8, 8))
        sw_down_row = tk.Frame(form, bg=BG_PANEL)
        sw_down_row.grid(row=2, column=2, sticky="ew", pady=(8, 8))
        sw_down_row.grid_columnconfigure(0, weight=1)
        tk.Entry(
            sw_down_row,
            textvariable=self.enc_sw_down_value_var,
            bg=BG_INPUT,
            fg=FG_TEXT,
            insertbackground=FG_TEXT,
            relief="flat",
        ).grid(row=0, column=0, sticky="ew")
        tk.Button(
            sw_down_row,
            text="Browse",
            bg="#1E3A8A",
            fg="#FFFFFF",
            activebackground="#1D4ED8",
            activeforeground="#FFFFFF",
            relief="flat",
            padx=8,
            command=self._on_browse_encoder_sw_down_clicked,
        ).grid(row=0, column=1, padx=(6, 0))

        tk.Label(form, text="Switch Up", bg=BG_PANEL, fg=FG_TEXT).grid(row=3, column=0, sticky="w")
        ttk.Combobox(
            form,
            textvariable=self.enc_sw_up_kind_var,
            values=ACTION_TYPES,
            state="readonly",
            width=12,
            style="Dark.TCombobox",
        ).grid(row=3, column=1, sticky="w", padx=(8, 8))
        sw_up_row = tk.Frame(form, bg=BG_PANEL)
        sw_up_row.grid(row=3, column=2, sticky="ew")
        sw_up_row.grid_columnconfigure(0, weight=1)
        tk.Entry(
            sw_up_row,
            textvariable=self.enc_sw_up_value_var,
            bg=BG_INPUT,
            fg=FG_TEXT,
            insertbackground=FG_TEXT,
            relief="flat",
        ).grid(row=0, column=0, sticky="ew")
        tk.Button(
            sw_up_row,
            text="Browse",
            bg="#1E3A8A",
            fg="#FFFFFF",
            activebackground="#1D4ED8",
            activeforeground="#FFFFFF",
            relief="flat",
            padx=8,
            command=self._on_browse_encoder_sw_up_clicked,
        ).grid(row=0, column=1, padx=(6, 0))

        buttons = tk.Frame(section, bg=BG_PANEL)
        buttons.pack(fill="x", padx=10, pady=(8, 10))
        tk.Button(
            buttons,
            text="Save ENC",
            bg="#2563EB",
            fg="#FFFFFF",
            activebackground="#1D4ED8",
            activeforeground="#FFFFFF",
            relief="flat",
            padx=10,
            command=self._on_save_encoder_actions_clicked,
        ).pack(side="left")
        tk.Button(
            buttons,
            text="Test Up",
            bg="#0F766E",
            fg="#FFFFFF",
            relief="flat",
            padx=10,
            command=self._on_test_encoder_up_clicked,
        ).pack(side="left", padx=(8, 0))
        tk.Button(
            buttons,
            text="Test Down",
            bg="#334155",
            fg="#FFFFFF",
            relief="flat",
            padx=10,
            command=self._on_test_encoder_down_clicked,
        ).pack(side="left", padx=(8, 0))
        tk.Button(
            buttons,
            text="Test SW Down",
            bg="#7C3AED",
            fg="#FFFFFF",
            relief="flat",
            padx=10,
            command=self._on_test_encoder_sw_down_clicked,
        ).pack(side="left", padx=(8, 0))
        tk.Button(
            buttons,
            text="Test SW Up",
            bg="#1F2937",
            fg="#FFFFFF",
            relief="flat",
            padx=10,
            command=self._on_test_encoder_sw_up_clicked,
        ).pack(side="left", padx=(8, 0))
