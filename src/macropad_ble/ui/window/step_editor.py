from __future__ import annotations

import copy
from contextlib import suppress
from typing import Any, Callable

import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

from ..step_blocks import (
    MOVE_TARGET_COORDS,
    MOVE_TARGET_SAVED,
    STEP_BLOCK_PALETTE,
    compute_step_indent_levels,
    default_step_block,
    parse_step_script,
    serialize_step_script,
    summarize_step_block,
)
from .shared import BG_INPUT, BG_PANEL, BORDER_MUTED, BORDER_SELECTED, FG_ACCENT, FG_MUTED, FG_TEXT


class StepEditor:
    def __init__(
        self,
        parent: tk.Misc,
        *,
        on_change: Callable[[], None] | None = None,
    ) -> None:
        self.on_change = on_change
        self.blocks: list[dict[str, Any]] = []
        self._drag_index: int | None = None
        self._font_zoom_baselines: dict[str, tuple[str, int, tuple[str, ...]]] = {}

        self.frame = tk.Frame(parent, bg=BG_PANEL)
        self.frame.pack(fill="both", expand=True)

        root = tk.PanedWindow(self.frame, orient=tk.HORIZONTAL, sashwidth=6, bg=BG_PANEL, bd=0, relief="flat")
        self._root_pane = root
        root.pack(fill="both", expand=True)

        chain_panel = tk.Frame(root, bg=BG_PANEL, highlightthickness=1, highlightbackground=BORDER_MUTED)
        palette_panel = tk.Frame(root, bg=BG_PANEL, highlightthickness=1, highlightbackground=BORDER_MUTED)
        root.add(chain_panel)
        root.add(palette_panel)

        tk.Label(
            chain_panel,
            text="Step Chain",
            bg=BG_PANEL,
            fg=FG_ACCENT,
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor="w", padx=10, pady=(10, 4))
        tk.Label(
            chain_panel,
            text="Drag rows to reorder. If/While blocks run until an End block.",
            bg=BG_PANEL,
            fg=FG_MUTED,
            justify="left",
        ).pack(anchor="w", padx=10, pady=(0, 8))

        list_frame = tk.Frame(chain_panel, bg=BG_PANEL)
        list_frame.pack(fill="both", expand=True, padx=10)

        self.listbox = tk.Listbox(
            list_frame,
            bg=BG_INPUT,
            fg=FG_TEXT,
            selectbackground="#1D4ED8",
            selectforeground="#FFFFFF",
            activestyle="none",
            relief="flat",
            font=("Consolas", 10),
            highlightthickness=1,
            highlightbackground=BORDER_MUTED,
            highlightcolor=BORDER_SELECTED,
            exportselection=False,
        )
        self.listbox.pack(side="left", fill="both", expand=True)
        scrollbar = tk.Scrollbar(list_frame, command=self.listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.listbox.configure(yscrollcommand=scrollbar.set)

        self.listbox.bind("<<ListboxSelect>>", self._on_list_selection)
        self.listbox.bind("<ButtonPress-1>", self._on_drag_start)
        self.listbox.bind("<B1-Motion>", self._on_drag_motion)
        self.listbox.bind("<ButtonRelease-1>", self._on_drag_end)

        controls = tk.Frame(chain_panel, bg=BG_PANEL)
        controls.pack(fill="x", padx=10, pady=(8, 8))
        tk.Button(
            controls,
            text="Remove",
            bg="#334155",
            fg="#FFFFFF",
            relief="flat",
            padx=8,
            command=self._remove_selected,
        ).pack(side="left")
        tk.Button(
            controls,
            text="Duplicate",
            bg="#0F766E",
            fg="#FFFFFF",
            relief="flat",
            padx=8,
            command=self._duplicate_selected,
        ).pack(side="left", padx=(6, 0))
        tk.Button(
            controls,
            text="Clear All",
            bg="#7F1D1D",
            fg="#FFFFFF",
            relief="flat",
            padx=8,
            command=self.clear,
        ).pack(side="left", padx=(6, 0))

        self.props_frame = tk.Frame(chain_panel, bg=BG_PANEL, highlightthickness=1, highlightbackground=BORDER_MUTED)
        self.props_frame.pack(fill="x", padx=10, pady=(0, 10))

        tk.Label(
            palette_panel,
            text="Blocks",
            bg=BG_PANEL,
            fg=FG_ACCENT,
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor="w", padx=10, pady=(10, 8))
        tk.Label(
            palette_panel,
            text="Click to add block",
            bg=BG_PANEL,
            fg=FG_MUTED,
        ).pack(anchor="w", padx=10, pady=(0, 8))

        palette_scroll_host = tk.Frame(palette_panel, bg=BG_PANEL)
        palette_scroll_host.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        palette_canvas = tk.Canvas(
            palette_scroll_host,
            bg=BG_PANEL,
            highlightthickness=0,
            relief="flat",
            bd=0,
        )
        palette_canvas.pack(side="left", fill="both", expand=True)

        palette_scroll = tk.Scrollbar(palette_scroll_host, orient="vertical", command=palette_canvas.yview)
        palette_scroll.pack(side="right", fill="y")
        palette_canvas.configure(yscrollcommand=palette_scroll.set)

        palette_body = tk.Frame(palette_canvas, bg=BG_PANEL)
        palette_window = palette_canvas.create_window((0, 0), window=palette_body, anchor="nw")

        def _sync_palette_region(_event: object | None = None) -> None:
            palette_canvas.configure(scrollregion=palette_canvas.bbox("all"))

        def _sync_palette_width(event: tk.Event[tk.Misc]) -> None:
            palette_canvas.itemconfigure(palette_window, width=event.width)
        def _mousewheel_units(event: tk.Event[tk.Misc]) -> int:
            delta = int(getattr(event, "delta", 0) or 0)
            if delta != 0:
                # Windows/macOS may send larger deltas; high-res wheels can send small deltas.
                steps = max(1, abs(delta) // 120)
                return -steps if delta > 0 else steps
            num = int(getattr(event, "num", 0) or 0)
            if num == 4:
                return -1
            if num == 5:
                return 1
            return 0

        def _on_palette_mousewheel(event: tk.Event[tk.Misc]) -> None:
            delta_steps = _mousewheel_units(event)
            if delta_steps != 0:
                palette_canvas.yview_scroll(delta_steps, "units")
                return "break"
            return None

        def _bind_palette_wheel(widget: tk.Misc) -> None:
            widget.bind("<MouseWheel>", _on_palette_mousewheel, add="+")
            widget.bind("<Shift-MouseWheel>", _on_palette_mousewheel, add="+")
            widget.bind("<Button-4>", _on_palette_mousewheel, add="+")
            widget.bind("<Button-5>", _on_palette_mousewheel, add="+")

        palette_body.bind("<Configure>", _sync_palette_region)
        palette_canvas.bind("<Configure>", _sync_palette_width)
        _bind_palette_wheel(palette_canvas)
        _bind_palette_wheel(palette_body)
        _bind_palette_wheel(palette_scroll_host)
        _bind_palette_wheel(palette_scroll)

        for block_type, title, color in STEP_BLOCK_PALETTE:
            button = tk.Button(
                palette_body,
                text=title,
                bg=color,
                fg="#FFFFFF",
                activebackground=color,
                activeforeground="#FFFFFF",
                relief="flat",
                padx=10,
                pady=8,
                command=lambda b=block_type: self.add_block(b),
            )
            button.pack(fill="x", pady=(0, 6))
            _bind_palette_wheel(button)

    def _iter_widgets(self, widget: tk.Misc) -> list[tk.Misc]:
        widgets: list[tk.Misc] = [widget]
        for child in widget.winfo_children():
            widgets.extend(self._iter_widgets(child))
        return widgets

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
                actual = tkfont.Font(root=self.frame, font=font_value).actual()
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

    def apply_zoom(self, zoom_factor: float) -> None:
        zoom = max(0.5, min(2.0, float(zoom_factor)))
        panes = self._root_pane.panes()
        if len(panes) >= 2:
            chain_min = max(260, int(round(420 * zoom)))
            palette_min = max(170, int(round(230 * zoom)))
            with suppress(Exception):
                self._root_pane.paneconfigure(panes[0], minsize=chain_min)
                self._root_pane.paneconfigure(panes[1], minsize=palette_min)

        for widget in self._iter_widgets(self.frame):
            baseline = self._font_baseline_for_widget(widget, zoom)
            if baseline is None:
                continue
            family, signed_base_size, tokens = baseline
            sign = -1 if signed_base_size < 0 else 1
            base_size = max(1, abs(signed_base_size))
            target_size = max(1, int(round(base_size * zoom))) * sign
            if tokens:
                font_spec = (family, target_size, *tokens)
            else:
                font_spec = (family, target_size)
            with suppress(Exception):
                widget.configure(font=font_spec)
    def load_script(self, script_code: str) -> None:
        self.blocks = parse_step_script(script_code)
        self._refresh_list(select_index=0 if self.blocks else None)
        self._render_properties()

    def dump_script(self) -> str:
        return serialize_step_script(self.blocks)

    def clear(self) -> None:
        self.blocks = []
        self._refresh_list(select_index=None)
        self._render_properties()
        self._notify_change()

    def add_block(self, block_type: str) -> None:
        self.blocks.append(default_step_block(block_type))
        self._refresh_list(select_index=len(self.blocks) - 1)
        self._render_properties()
        self._notify_change()

    def _selected_index(self) -> int | None:
        selected = self.listbox.curselection()
        if not selected:
            return None
        index = int(selected[0])
        if index < 0 or index >= len(self.blocks):
            return None
        return index

    def _remove_selected(self) -> None:
        index = self._selected_index()
        if index is None:
            return
        self.blocks.pop(index)
        if not self.blocks:
            self._refresh_list(select_index=None)
        else:
            self._refresh_list(select_index=max(0, index - 1))
        self._render_properties()
        self._notify_change()

    def _duplicate_selected(self) -> None:
        index = self._selected_index()
        if index is None:
            return
        self.blocks.insert(index + 1, copy.deepcopy(self.blocks[index]))
        self._refresh_list(select_index=index + 1)
        self._render_properties()
        self._notify_change()

    def _refresh_list(self, *, select_index: int | None) -> None:
        self.listbox.delete(0, "end")
        indent_levels = compute_step_indent_levels(self.blocks)
        for index, block in enumerate(self.blocks):
            indent = indent_levels[index] if index < len(indent_levels) else 0
            self.listbox.insert("end", summarize_step_block(block, index=index, indent=indent))

        if select_index is None:
            return
        if not self.blocks:
            return
        bounded = max(0, min(len(self.blocks) - 1, int(select_index)))
        self.listbox.selection_clear(0, "end")
        self.listbox.selection_set(bounded)
        self.listbox.see(bounded)

    def _on_list_selection(self, _event: object | None = None) -> None:
        self._render_properties()

    def _on_drag_start(self, event: tk.Event[tk.Misc]) -> None:
        if not self.blocks:
            return
        self._drag_index = self.listbox.nearest(event.y)

    def _on_drag_motion(self, event: tk.Event[tk.Misc]) -> None:
        if self._drag_index is None:
            return
        if not self.blocks:
            return
        to_index = self.listbox.nearest(event.y)
        if to_index < 0 or to_index >= len(self.blocks):
            return
        from_index = self._drag_index
        if to_index == from_index:
            return
        moved = self.blocks.pop(from_index)
        self.blocks.insert(to_index, moved)
        self._drag_index = to_index
        self._refresh_list(select_index=to_index)
        self._notify_change()

    def _on_drag_end(self, _event: tk.Event[tk.Misc]) -> None:
        self._drag_index = None

    def _render_properties(self) -> None:
        for child in self.props_frame.winfo_children():
            child.destroy()

        index = self._selected_index()
        if index is None:
            tk.Label(
                self.props_frame,
                text="Select a block to edit its settings.",
                bg=BG_PANEL,
                fg=FG_MUTED,
            ).pack(anchor="w", padx=10, pady=10)
            return

        block = self.blocks[index]
        block_type = str(block.get("type") or "")

        tk.Label(
            self.props_frame,
            text=f"Block {index + 1} Settings",
            bg=BG_PANEL,
            fg=FG_ACCENT,
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w", padx=10, pady=(10, 6))

        if block_type == "move_mouse":
            self._add_choice_field(
                "Target",
                block,
                "target",
                (MOVE_TARGET_COORDS, MOVE_TARGET_SAVED),
                on_after_change=self._render_properties,
            )
            target_mode = str(block.get("target") or MOVE_TARGET_COORDS).strip().lower()
            if target_mode == MOVE_TARGET_SAVED:
                self._add_hint("Uses previously saved mouse position.")
            else:
                self._add_int_field("X", block, "x")
                self._add_int_field("Y", block, "y")
            return

        if block_type == "click_mouse":
            self._add_choice_field("Button", block, "button", ("left", "right", "middle"))
            self._add_int_field("Clicks", block, "clicks", minimum=1)
            return

        if block_type == "type_text":
            self._add_text_field("Text", block, "text")
            return

        if block_type in {"hold_key", "release_key", "if_pressed", "if_else_pressed", "while_pressed"}:
            self._add_text_field("Key", block, "key")
            if block_type == "while_pressed":
                self._add_int_field("Max Loops", block, "max_loops", minimum=1)
                self._add_float_field("Interval", block, "interval", minimum=0.0)
            if block_type == "if_pressed":
                self._add_hint("Runs all following steps until End if key is pressed.")
            if block_type == "while_pressed":
                self._add_hint("Repeats all following steps until End while key is pressed.")
            return

        if block_type == "wait":
            self._add_float_field("Seconds", block, "seconds", minimum=0.0)
            return

        if block_type == "repeat":
            self._add_int_field("Times", block, "times", minimum=1)
            self._add_hint("Repeat still targets the next single block.")
            return

        if block_type in {"save_mouse_pos", "restore_mouse_pos", "end"}:
            if block_type == "save_mouse_pos":
                self._add_hint("No fields. Saves the current mouse position.")
            elif block_type == "restore_mouse_pos":
                self._add_hint("No fields. Moves to the previously saved mouse position.")
            else:
                self._add_hint("No fields. Closes the nearest If/While block above.")
            return

    def _add_row(self, label: str) -> tk.Frame:
        row = tk.Frame(self.props_frame, bg=BG_PANEL)
        row.pack(fill="x", padx=10, pady=(0, 6))
        tk.Label(row, text=label, bg=BG_PANEL, fg=FG_TEXT, width=12, anchor="w").pack(side="left")
        return row

    def _add_hint(self, text: str) -> None:
        tk.Label(
            self.props_frame,
            text=text,
            bg=BG_PANEL,
            fg=FG_MUTED,
            justify="left",
            wraplength=420,
        ).pack(anchor="w", padx=10, pady=(0, 8))

    def _add_text_field(self, label: str, block: dict[str, Any], key: str) -> None:
        row = self._add_row(label)
        var = tk.StringVar(value=str(block.get(key) or ""))
        entry = tk.Entry(
            row,
            textvariable=var,
            bg=BG_INPUT,
            fg=FG_TEXT,
            insertbackground=FG_TEXT,
            relief="flat",
        )
        entry.pack(side="left", fill="x", expand=True)

        def apply(_event: object | None = None) -> None:
            block[key] = var.get().strip()
            self._refresh_list(select_index=self._selected_index())
            self._notify_change()

        entry.bind("<FocusOut>", apply)
        entry.bind("<Return>", apply)

    def _add_int_field(self, label: str, block: dict[str, Any], key: str, *, minimum: int | None = None) -> None:
        row = self._add_row(label)
        var = tk.StringVar(value=str(block.get(key, 0)))
        entry = tk.Entry(
            row,
            textvariable=var,
            bg=BG_INPUT,
            fg=FG_TEXT,
            insertbackground=FG_TEXT,
            relief="flat",
        )
        entry.pack(side="left", fill="x", expand=True)

        def apply(_event: object | None = None) -> None:
            try:
                value = int(var.get().strip())
            except ValueError:
                value = int(block.get(key, 0) or 0)
            if minimum is not None and value < minimum:
                value = minimum
            block[key] = value
            var.set(str(value))
            self._refresh_list(select_index=self._selected_index())
            self._notify_change()

        entry.bind("<FocusOut>", apply)
        entry.bind("<Return>", apply)

    def _add_float_field(self, label: str, block: dict[str, Any], key: str, *, minimum: float | None = None) -> None:
        row = self._add_row(label)
        var = tk.StringVar(value=str(block.get(key, 0.0)))
        entry = tk.Entry(
            row,
            textvariable=var,
            bg=BG_INPUT,
            fg=FG_TEXT,
            insertbackground=FG_TEXT,
            relief="flat",
        )
        entry.pack(side="left", fill="x", expand=True)

        def apply(_event: object | None = None) -> None:
            try:
                value = float(var.get().strip())
            except ValueError:
                value = float(block.get(key, 0.0) or 0.0)
            if minimum is not None and value < minimum:
                value = minimum
            block[key] = value
            var.set(f"{value:.3f}".rstrip("0").rstrip("."))
            self._refresh_list(select_index=self._selected_index())
            self._notify_change()

        entry.bind("<FocusOut>", apply)
        entry.bind("<Return>", apply)

    def _add_choice_field(
        self,
        label: str,
        block: dict[str, Any],
        key: str,
        values: tuple[str, ...],
        *,
        on_after_change: Callable[[], None] | None = None,
    ) -> None:
        row = self._add_row(label)
        selected = str(block.get(key) or values[0]).strip().lower()
        if selected not in values:
            selected = values[0]
        var = tk.StringVar(value=selected)
        combo = ttk.Combobox(row, textvariable=var, values=list(values), state="readonly", width=16)
        combo.pack(side="left", fill="x", expand=True)

        def apply(_event: object | None = None) -> None:
            value = var.get().strip().lower()
            if value not in values:
                value = values[0]
                var.set(value)
            block[key] = value
            self._refresh_list(select_index=self._selected_index())
            self._notify_change()
            if on_after_change is not None:
                on_after_change()

        combo.bind("<<ComboboxSelected>>", apply)

    def _notify_change(self) -> None:
        if self.on_change is None:
            return
        self.on_change()







