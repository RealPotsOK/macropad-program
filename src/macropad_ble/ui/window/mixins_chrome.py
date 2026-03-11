from __future__ import annotations

import tkinter.font as tkfont

from .shared import *


class ChromeMixin:
    def _configure_ttk_style(self) -> None:
        style = ttk.Style(self.root)
        with suppress(Exception):
            style.theme_use("clam")

        # Combobox entry and popup-list colors for dark mode.
        self.root.option_add("*TCombobox*Listbox.background", BG_INPUT)
        self.root.option_add("*TCombobox*Listbox.foreground", FG_TEXT)
        self.root.option_add("*TCombobox*Listbox.selectBackground", "#1D4ED8")
        self.root.option_add("*TCombobox*Listbox.selectForeground", "#FFFFFF")
        self.root.option_add("*TCombobox*Listbox*Background", BG_INPUT)
        self.root.option_add("*TCombobox*Listbox*Foreground", FG_TEXT)
        self.root.option_add("*TCombobox*Listbox*selectBackground", "#1D4ED8")
        self.root.option_add("*TCombobox*Listbox*selectForeground", "#FFFFFF")

        style.configure(
            "Dark.TCombobox",
            fieldbackground=BG_INPUT,
            background=BG_INPUT,
            foreground=FG_TEXT,
            bordercolor=BORDER_MUTED,
            arrowcolor=FG_TEXT,
            lightcolor=BG_INPUT,
            darkcolor=BG_INPUT,
        )
        style.map(
            "Dark.TCombobox",
            fieldbackground=[("readonly", BG_INPUT)],
            foreground=[("readonly", FG_TEXT)],
            background=[("readonly", BG_INPUT)],
            selectbackground=[("readonly", "#1D4ED8")],
            selectforeground=[("readonly", "#FFFFFF")],
            arrowcolor=[("readonly", FG_TEXT)],
        )

        style.configure(
            "Dark.TNotebook",
            background=BG_APP,
            borderwidth=0,
            tabmargins=(0, 0, 0, 0),
            bordercolor=BG_APP,
            lightcolor=BG_APP,
            darkcolor=BG_APP,
        )
        style.configure(
            "Dark.TNotebook.Tab",
            background=BG_PANEL,
            foreground=FG_TEXT,
            padding=(14, 7),
            borderwidth=0,
            lightcolor=BG_PANEL,
            darkcolor=BG_PANEL,
        )
        style.map(
            "Dark.TNotebook.Tab",
            background=[("selected", "#162347"), ("!selected", BG_PANEL)],
            foreground=[("selected", "#FFFFFF"), ("!selected", FG_TEXT)],
            padding=[("selected", (14, 7)), ("!selected", (14, 7))],
        )
        self._set_combobox_popup_font(self._zoom_factor())

    def _configure_window_chrome(self) -> None:
        self._set_app_icon()
        self._set_windows_dark_titlebar()

    def _configure_dpi_runtime(self) -> None:
        self._apply_dpi_scaling(force=True)
        if sys.platform != "win32":
            return
        self.root.bind("<Configure>", self._on_window_configure, add="+")
        self._dpi_check_after_id = self.root.after(1000, self._periodic_dpi_check)

    def _on_window_configure(self, _event: tk.Event[tk.Misc]) -> None:
        if sys.platform != "win32" or self._closing:
            return
        if self._dpi_configure_after_id is not None:
            with suppress(Exception):
                self.root.after_cancel(self._dpi_configure_after_id)
        self._dpi_configure_after_id = self.root.after(120, self._apply_dpi_scaling)

    def _periodic_dpi_check(self) -> None:
        self._dpi_check_after_id = None
        if self._closing:
            return
        self._apply_dpi_scaling()
        self._dpi_check_after_id = self.root.after(1000, self._periodic_dpi_check)

    def _scaled_px(self, value: int | float, *, minimum: int = 1, zoom_factor: float | None = None) -> int:
        factor = zoom_factor
        if factor is None:
            factor = self._last_zoom_factor or self._zoom_factor()
        scaled = int(round(float(value) * float(factor)))
        return max(minimum, scaled)

    def _set_combobox_popup_font(self, zoom_factor: float) -> None:
        popup_size = self._scaled_px(10, minimum=7, zoom_factor=zoom_factor)
        self.root.option_add("*TCombobox*Listbox.font", f"{{Segoe UI}} {popup_size}")

    def _apply_theme_metrics(self, zoom_factor: float) -> None:
        style = ttk.Style(self.root)
        tab_pad_x = self._scaled_px(14, minimum=8, zoom_factor=zoom_factor)
        tab_pad_y = self._scaled_px(7, minimum=5, zoom_factor=zoom_factor)
        with suppress(Exception):
            style.configure("Dark.TNotebook.Tab", padding=(tab_pad_x, tab_pad_y))
            style.map(
                "Dark.TNotebook.Tab",
                padding=[("selected", (tab_pad_x, tab_pad_y)), ("!selected", (tab_pad_x, tab_pad_y))],
            )

    def _iter_widgets(self, widget: tk.Misc) -> list[tk.Misc]:
        items: list[tk.Misc] = [widget]
        for child in widget.winfo_children():
            items.extend(self._iter_widgets(child))
        return items

    def _font_baseline_for_widget(self, widget: tk.Misc, zoom_factor: float) -> tuple[str, int, tuple[str, ...]] | None:
        key = str(widget)
        cached = self._font_zoom_baselines.get(key)
        if cached is not None:
            return cached

        try:
            font_value = widget.cget("font")
        except Exception:
            return None
        if not font_value:
            return None

        actual: dict[str, object] | None = None
        with suppress(Exception):
            actual = tkfont.nametofont(str(font_value)).actual()
        if actual is None:
            with suppress(Exception):
                actual = tkfont.Font(root=self.root, font=font_value).actual()
        if actual is None:
            return None

        raw_size = int(actual.get("size", 10) or 10)
        sign = -1 if raw_size < 0 else 1
        current_size = max(1, abs(raw_size))
        base_size = max(1, int(round(current_size / max(0.01, zoom_factor))))
        style_tokens: list[str] = []
        if str(actual.get("weight", "normal")) == "bold":
            style_tokens.append("bold")
        if str(actual.get("slant", "roman")) == "italic":
            style_tokens.append("italic")
        if int(actual.get("underline", 0) or 0):
            style_tokens.append("underline")
        if int(actual.get("overstrike", 0) or 0):
            style_tokens.append("overstrike")

        baseline = (str(actual.get("family", "Segoe UI") or "Segoe UI"), base_size * sign, tuple(style_tokens))
        self._font_zoom_baselines[key] = baseline
        return baseline

    def _apply_widget_font_zoom(self, zoom_factor: float) -> None:
        for widget in self._iter_widgets(self.root):
            baseline = self._font_baseline_for_widget(widget, zoom_factor)
            if baseline is None:
                continue
            family, signed_base_size, tokens = baseline
            sign = -1 if signed_base_size < 0 else 1
            base_size = max(1, abs(signed_base_size))
            target_size = max(1, int(round(base_size * zoom_factor))) * sign
            font_spec: tuple[str, int] | tuple[str, int, str] | tuple[str, int, str, str] | tuple[str, int, str, str, str] | tuple[str, int, str, str, str, str]
            if tokens:
                font_spec = (family, target_size, *tokens)
            else:
                font_spec = (family, target_size)
            with suppress(Exception):
                widget.configure(font=font_spec)

    def _apply_zoom_layout(self, zoom_factor: float) -> None:
        controller_body = getattr(self, "_controller_body", None)
        if controller_body is not None:
            panes = controller_body.panes()
            if len(panes) >= 2:
                left_min = self._scaled_px(560, minimum=420, zoom_factor=zoom_factor)
                right_min = self._scaled_px(340, minimum=260, zoom_factor=zoom_factor)
                with suppress(Exception):
                    controller_body.paneconfigure(panes[0], minsize=left_min)
                    controller_body.paneconfigure(panes[1], minsize=right_min)

        scripts_body = getattr(self, "_scripts_body", None)
        if scripts_body is not None:
            panes = scripts_body.panes()
            if len(panes) >= 2:
                left_min = self._scaled_px(180, minimum=130, zoom_factor=zoom_factor)
                right_min = self._scaled_px(560, minimum=380, zoom_factor=zoom_factor)
                with suppress(Exception):
                    scripts_body.paneconfigure(panes[0], minsize=left_min)
                    scripts_body.paneconfigure(panes[1], minsize=right_min)

        if hasattr(self, "_apply_key_grid_zoom"):
            with suppress(Exception):
                self._apply_key_grid_zoom(zoom_factor)

        step_editor = getattr(self, "_step_editor", None)
        if step_editor is not None and hasattr(step_editor, "apply_zoom"):
            with suppress(Exception):
                step_editor.apply_zoom(zoom_factor)

    def _apply_dpi_scaling(self, force: bool = False) -> None:
        zoom_factor = self._zoom_factor()
        dpi = 96
        previous_zoom_factor = self._last_zoom_factor

        if sys.platform == "win32":
            with suppress(Exception):
                dpi = int(ctypes.windll.user32.GetDpiForWindow(self.root.winfo_id()))
                if dpi <= 0:
                    dpi = 96

        if not force and self._last_dpi == dpi and self._last_zoom_factor == zoom_factor:
            return

        zoom_changed = previous_zoom_factor is None or abs(zoom_factor - previous_zoom_factor) > 0.0001

        with suppress(Exception):
            self.root.tk.call("tk", "scaling", (dpi / 72.0) * zoom_factor)
            if previous_zoom_factor is not None and previous_zoom_factor > 0:
                ratio = zoom_factor / previous_zoom_factor
                if abs(ratio - 1.0) > 0.0001:
                    current_width = max(1, int(self.root.winfo_width()))
                    current_height = max(1, int(self.root.winfo_height()))
                    target_width = max(1, int(round(current_width * ratio)))
                    target_height = max(1, int(round(current_height * ratio)))
                    self.root.geometry(f"{target_width}x{target_height}")

            self._set_combobox_popup_font(zoom_factor)
            self._apply_theme_metrics(zoom_factor)
            self._apply_widget_font_zoom(zoom_factor)
            self._apply_zoom_layout(zoom_factor)

            self._last_dpi = dpi
            self._last_zoom_factor = zoom_factor
            self._ensure_content_fits(allow_shrink=zoom_changed)

    def _zoom_factor(self) -> float:
        raw = (self.zoom_var.get() or "100%").strip()
        if raw.endswith("%"):
            raw = raw[:-1]
        try:
            percent = int(raw, 10)
        except ValueError:
            percent = 100
        percent = max(50, min(200, percent))
        return percent / 100.0

    def _ensure_content_fits(self, allow_shrink: bool = False) -> None:
        with suppress(Exception):
            self.root.update_idletasks()
            required_width = self.root.winfo_reqwidth()
            required_height = self.root.winfo_reqheight()

            zoom_factor = self._last_zoom_factor or self._zoom_factor()
            base_min_width = self._scaled_px(getattr(self, "_base_min_width", 1), minimum=1, zoom_factor=zoom_factor)
            base_min_height = self._scaled_px(getattr(self, "_base_min_height", 1), minimum=1, zoom_factor=zoom_factor)
            target_min_width = max(base_min_width, required_width)
            target_min_height = max(base_min_height, required_height)

            min_width, min_height = self.root.minsize()
            if target_min_width != min_width or target_min_height != min_height:
                self.root.minsize(target_min_width, target_min_height)

            current_width = max(1, int(self.root.winfo_width()))
            current_height = max(1, int(self.root.winfo_height()))

            if allow_shrink:
                target_width = max(target_min_width, required_width)
                target_height = max(target_min_height, required_height)
                if current_width != target_width or current_height != target_height:
                    self.root.geometry(f"{target_width}x{target_height}")
                return

            if current_width >= required_width and current_height >= required_height:
                return
            target_width = max(current_width, required_width, target_min_width)
            target_height = max(current_height, required_height, target_min_height)
            self.root.geometry(f"{target_width}x{target_height}")

    def _set_app_icon(self) -> None:
        icon = tk.PhotoImage(width=32, height=32)
        icon.put(BG_PANEL, to=(0, 0, 32, 32))
        icon.put("#1D4ED8", to=(4, 4, 28, 28))
        icon.put("#334155", to=(8, 8, 24, 24))
        icon.put("#93C5FD", to=(12, 12, 20, 20))
        self._app_icon = icon
        with suppress(Exception):
            self.root.iconphoto(True, icon)

    def _set_windows_dark_titlebar(self) -> None:
        if sys.platform != "win32":
            return
        with suppress(Exception):
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            value = ctypes.c_int(1)
            # Windows 10 1903+ is usually 20, older variants can be 19.
            for attr in (20, 19):
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd,
                    ctypes.c_uint(attr),
                    ctypes.byref(value),
                    ctypes.sizeof(value),
                )

    def _build_ui(self) -> None:
        top = tk.Frame(self.root, bg=BG_PANEL, bd=0, highlightthickness=1, highlightbackground=BORDER_MUTED)
        top.pack(fill="x", padx=10, pady=(10, 8))

        self._status_pill = tk.Label(
            top,
            textvariable=self.connection_var,
            bg=STATUS_COLORS["disconnected"],
            fg="#FFFFFF",
            padx=10,
            pady=5,
            font=("Segoe UI", 10, "bold"),
        )
        self._status_pill.grid(row=0, column=0, padx=(10, 8), pady=8, sticky="w")

        tk.Label(top, text="Port", bg=BG_PANEL, fg=FG_TEXT, font=("Segoe UI", 10, "bold")).grid(
            row=0, column=1, sticky="w"
        )
        self._port_combo = ttk.Combobox(
            top,
            textvariable=self.port_display_var,
            state="readonly",
            width=34,
            style="Dark.TCombobox",
        )
        self._port_combo.grid(row=0, column=2, padx=(6, 8), sticky="w")
        self._port_combo.bind("<<ComboboxSelected>>", self._on_port_selected)

        tk.Button(
            top,
            text="Refresh",
            bg="#172554",
            fg=FG_TEXT,
            activebackground="#1E3A8A",
            activeforeground="#FFFFFF",
            command=self._on_refresh_ports,
            relief="flat",
            padx=10,
            pady=4,
        ).grid(row=0, column=3, padx=(0, 10))

        tk.Label(top, text="Baud", bg=BG_PANEL, fg=FG_TEXT, font=("Segoe UI", 10, "bold")).grid(
            row=0, column=4, sticky="w"
        )
        self._baud_combo = ttk.Combobox(
            top,
            textvariable=self.baud_var,
            values=("9600", "19200", "38400", "57600", "115200", "230400"),
            width=10,
            style="Dark.TCombobox",
        )
        self._baud_combo.grid(row=0, column=5, padx=(6, 10), sticky="w")
        self._baud_combo.bind("<<ComboboxSelected>>", self._on_baud_changed)
        self._baud_combo.bind("<FocusOut>", self._on_baud_changed)
        self._baud_combo.bind("<Return>", self._on_baud_changed)

        tk.Label(top, text="Zoom", bg=BG_PANEL, fg=FG_TEXT, font=("Segoe UI", 10, "bold")).grid(
            row=0, column=6, sticky="w"
        )
        self._zoom_combo = ttk.Combobox(
            top,
            textvariable=self.zoom_var,
            values=("100%", "90%", "80%", "70%"),
            state="readonly",
            width=8,
            style="Dark.TCombobox",
        )
        self._zoom_combo.grid(row=0, column=7, padx=(6, 10), sticky="w")
        self._zoom_combo.bind("<<ComboboxSelected>>", self._on_zoom_selected)

        tk.Checkbutton(
            top,
            text="Auto-connect last",
            variable=self.auto_connect_var,
            command=self._on_auto_connect_toggled,
            bg=BG_PANEL,
            fg=FG_TEXT,
            selectcolor=BG_INPUT,
            activebackground=BG_PANEL,
            activeforeground=FG_TEXT,
            font=("Segoe UI", 9),
        ).grid(row=0, column=8, padx=(0, 10), sticky="w")

        self._connect_button = tk.Button(
            top,
            text="Connect",
            bg="#16A34A",
            fg="#FFFFFF",
            activebackground="#22C55E",
            activeforeground="#FFFFFF",
            relief="flat",
            padx=10,
            pady=5,
            command=self._on_connect_clicked,
            font=("Segoe UI", 10, "bold"),
        )
        self._connect_button.grid(row=0, column=9, padx=(0, 6), sticky="e")

        self._disconnect_button = tk.Button(
            top,
            text="Disconnect",
            bg="#B91C1C",
            fg="#FFFFFF",
            activebackground="#DC2626",
            activeforeground="#FFFFFF",
            relief="flat",
            padx=10,
            pady=5,
            command=self._on_disconnect_clicked,
            font=("Segoe UI", 10, "bold"),
        )
        self._disconnect_button.grid(row=0, column=10, padx=(0, 10), sticky="e")

        tk.Label(top, textvariable=self.port_info_var, bg=BG_PANEL, fg=FG_MUTED, font=("Segoe UI", 9)).grid(
            row=1, column=1, columnspan=10, sticky="w", padx=(0, 10), pady=(0, 8)
        )
        top.grid_columnconfigure(11, weight=1)

        notebook = ttk.Notebook(self.root, style="Dark.TNotebook")
        notebook.pack(fill="both", expand=True, padx=10, pady=(0, 8))

        controller_tab = tk.Frame(notebook, bg=BG_APP)
        scripts_tab = tk.Frame(notebook, bg=BG_APP)
        notebook.add(controller_tab, text="Controller")
        notebook.add(scripts_tab, text="Scripts")

        self._build_controller_tab(controller_tab)
        self._build_scripts_tab(scripts_tab)

        status = tk.Frame(self.root, bg=BG_PANEL, highlightthickness=1, highlightbackground=BORDER_MUTED)
        status.pack(fill="x", side="bottom", padx=10, pady=(0, 10))
        tk.Label(status, textvariable=self.fw_var, bg=BG_PANEL, fg=FG_MUTED, padx=10, pady=7).pack(side="left")
        tk.Label(status, textvariable=self.packet_var, bg=BG_PANEL, fg=FG_MUTED, padx=10, pady=7).pack(side="left")
        tk.Label(status, textvariable=self.enc_var, bg=BG_PANEL, fg=FG_MUTED, padx=10, pady=7).pack(side="left")
        tk.Label(status, textvariable=self.rate_var, bg=BG_PANEL, fg=FG_MUTED, padx=10, pady=7).pack(side="left")
        tk.Label(status, textvariable=self.error_var, bg=BG_PANEL, fg=FG_MUTED, padx=10, pady=7).pack(side="left")
        tk.Label(status, textvariable=self.mouse_var, bg=BG_PANEL, fg=FG_MUTED, padx=10, pady=7).pack(side="right")

    def _build_controller_tab(self, parent: tk.Frame) -> None:
        body = tk.PanedWindow(parent, orient=tk.HORIZONTAL, sashwidth=6, bg=BG_APP, bd=0, relief="flat")
        body.pack(fill="both", expand=True)

        left = tk.Frame(body, bg=BG_APP, padx=6, pady=6)
        right = tk.Frame(body, bg=BG_APP, padx=6, pady=6)
        body.add(left)
        body.add(right)
        self._controller_body = body

        self._build_key_grid(left)
        self._build_encoder_panel(left)
        self._build_profiles_panel(left)
        self._build_side_panel(right)
