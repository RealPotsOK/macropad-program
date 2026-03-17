from __future__ import annotations

from .shared import *
from .system_stats import StatsContext, build_system_stats_report


class StatsMixin:
    def _prime_stats_monitoring(self) -> None:
        self._stats_last_updated_at = 0.0
        self._stats_last_report = ""
        try:
            import psutil
        except ImportError:
            self._stats_process = None
            return

        with suppress(Exception):
            self._stats_process = psutil.Process(os.getpid())
            psutil.cpu_percent(interval=None)
            psutil.cpu_percent(interval=None, percpu=True)
            self._stats_process.cpu_percent(interval=None)

    def _build_stats_tab(self, parent: tk.Frame) -> None:
        container = tk.Frame(parent, bg=BG_APP, padx=8, pady=8)
        container.pack(fill="both", expand=True)

        tk.Label(
            container,
            text="System Stats",
            bg=BG_APP,
            fg=FG_ACCENT,
            font=("Segoe UI", 13, "bold"),
        ).pack(anchor="w", pady=(0, 6))
        tk.Label(
            container,
            text="Live CPU, core, memory, disk, process, and network metrics. Refreshes about once per second.",
            bg=BG_APP,
            fg=FG_MUTED,
            justify="left",
        ).pack(anchor="w", pady=(0, 8))

        controls = tk.Frame(container, bg=BG_APP)
        controls.pack(fill="x", pady=(0, 8))
        tk.Button(
            controls,
            text="Refresh Now",
            bg="#1D4ED8",
            fg="#FFFFFF",
            relief="flat",
            padx=10,
            command=lambda: self._refresh_system_stats(force=True),
        ).pack(side="left")

        stats_panel = tk.Frame(container, bg=BG_PANEL, highlightthickness=1, highlightbackground=BORDER_MUTED)
        stats_panel.pack(fill="both", expand=True)

        self._stats_text = tk.Text(
            stats_panel,
            wrap="none",
            bg="#020617",
            fg="#DDE7FF",
            insertbackground="#DDE7FF",
            relief="flat",
            font=("Consolas", 10),
            state="disabled",
        )
        stats_scroll_y = tk.Scrollbar(stats_panel, command=self._stats_text.yview)
        stats_scroll_x = tk.Scrollbar(stats_panel, command=self._stats_text.xview, orient="horizontal")
        self._stats_text.configure(yscrollcommand=stats_scroll_y.set, xscrollcommand=stats_scroll_x.set)
        self._stats_text.pack(side="left", fill="both", expand=True)
        stats_scroll_y.pack(side="right", fill="y")
        stats_scroll_x.pack(side="bottom", fill="x")

        self._refresh_system_stats(force=True)

    def _refresh_system_stats_if_due(self) -> None:
        self._refresh_system_stats(force=False)

    def _refresh_system_stats(self, *, force: bool = False) -> None:
        if self._stats_text is None:
            return

        now = time.monotonic()
        if not force and now - self._stats_last_updated_at < 1.0:
            return

        try:
            report = build_system_stats_report(
                StatsContext(
                    data_root=self.data_root,
                    app_started_monotonic=self._app_started_monotonic,
                    process=self._stats_process,
                )
            )
        except Exception as exc:
            report = f"Stats refresh failed:\n{exc}"

        if force or report != self._stats_last_report:
            self._stats_text.configure(state="normal")
            self._stats_text.delete("1.0", "end")
            self._stats_text.insert("1.0", report)
            self._stats_text.configure(state="disabled")
            self._stats_last_report = report

        self._stats_last_updated_at = now
