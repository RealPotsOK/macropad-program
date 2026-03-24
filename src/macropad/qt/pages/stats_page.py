from __future__ import annotations

import time
from contextlib import suppress
from datetime import datetime

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QVBoxLayout,
    QWidget,
)

from ...platform import resolve_app_paths
from ...core.system_stats import StatsContext, build_system_stats_report


class StatsPage(QWidget):
    def __init__(self, controller: object | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.controller = controller
        self.started_monotonic = time.monotonic()
        self.refresh_count = 0
        self.last_refresh = ""
        self.last_packet = ""

        self.key_press_counts: dict[tuple[int, int], int] = {}
        self.known_keys: list[tuple[int, int]] = []
        self.total_key_presses = 0

        self.encoder_up_steps = 0
        self.encoder_down_steps = 0
        self.encoder_up_events = 0
        self.encoder_down_events = 0
        self.encoder_switch_presses = 0

        self._build_ui()
        self._bind_controller()
        self._update_known_keys_from_controller()

        self.timer = QTimer(self)
        self.timer.setInterval(1500)
        self.timer.timeout.connect(self.refresh)
        self.timer.start()
        self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        summary = QFrame(self)
        summary.setProperty("panel", True)
        summary_layout = QGridLayout(summary)
        summary_layout.setContentsMargins(14, 14, 14, 14)
        summary_layout.setHorizontalSpacing(12)
        summary_layout.setVerticalSpacing(8)

        self.total_keys_label = QLabel("Total key presses: 0")
        self.most_key_label = QLabel("Most pressed: n/a")
        self.least_key_label = QLabel("Least pressed: n/a")
        self.encoder_summary_label = QLabel("Encoder: up 0 | down 0 | switch 0")
        self.refresh_count_label = QLabel("Graph refreshes: 0")
        self.last_packet_label = QLabel("Last packet: n/a")
        self.last_refresh_label = QLabel("Last refresh: n/a")

        summary_layout.addWidget(self.total_keys_label, 0, 0)
        summary_layout.addWidget(self.most_key_label, 0, 1)
        summary_layout.addWidget(self.least_key_label, 0, 2)
        summary_layout.addWidget(self.encoder_summary_label, 1, 0)
        summary_layout.addWidget(self.refresh_count_label, 1, 1)
        summary_layout.addWidget(self.last_packet_label, 1, 2)
        summary_layout.addWidget(self.last_refresh_label, 2, 0, 1, 3)

        root.addWidget(summary, 0)

        body = QSplitter(self)
        root.addWidget(body, 1)

        keys_panel = QFrame(body)
        keys_panel.setProperty("panel", True)
        keys_layout = QVBoxLayout(keys_panel)
        keys_layout.setContentsMargins(14, 14, 14, 14)
        keys_layout.setSpacing(10)
        keys_layout.addWidget(QLabel("Key Press Bar Graph"))

        self.key_table = QTableWidget(keys_panel)
        self.key_table.setColumnCount(3)
        self.key_table.setHorizontalHeaderLabels(["Key", "Presses", "Usage"])
        self.key_table.verticalHeader().setVisible(False)
        self.key_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.key_table.setSelectionMode(QTableWidget.NoSelection)
        self.key_table.horizontalHeader().setStretchLastSection(True)
        self.key_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.key_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        keys_layout.addWidget(self.key_table, 1)

        encoder_panel = QFrame(body)
        encoder_panel.setProperty("panel", True)
        encoder_layout = QVBoxLayout(encoder_panel)
        encoder_layout.setContentsMargins(14, 14, 14, 14)
        encoder_layout.setSpacing(10)
        encoder_layout.addWidget(QLabel("Encoder Bar Graph"))

        self.enc_up_value = QLabel("Up steps: 0 (events: 0)")
        self.enc_down_value = QLabel("Down steps: 0 (events: 0)")
        self.enc_sw_value = QLabel("Switch presses: 0")
        encoder_layout.addWidget(self.enc_up_value)
        self.enc_up_bar = QProgressBar(encoder_panel)
        self.enc_up_bar.setRange(0, 1)
        self.enc_up_bar.setValue(0)
        encoder_layout.addWidget(self.enc_up_bar)
        encoder_layout.addWidget(self.enc_down_value)
        self.enc_down_bar = QProgressBar(encoder_panel)
        self.enc_down_bar.setRange(0, 1)
        self.enc_down_bar.setValue(0)
        encoder_layout.addWidget(self.enc_down_bar)
        encoder_layout.addWidget(self.enc_sw_value)
        encoder_layout.addStretch(1)

        body.addWidget(keys_panel)
        body.addWidget(encoder_panel)
        body.setStretchFactor(0, 3)
        body.setStretchFactor(1, 2)

        system_panel = QFrame(self)
        system_panel.setProperty("panel", True)
        system_layout = QVBoxLayout(system_panel)
        system_layout.setContentsMargins(14, 14, 14, 14)
        system_layout.setSpacing(10)
        system_layout.addWidget(QLabel("System Stats"))
        self.system_text = QPlainTextEdit(system_panel)
        self.system_text.setReadOnly(True)
        system_layout.addWidget(self.system_text, 1)

        controls = QHBoxLayout()
        self.refresh_button = QPushButton("Refresh", system_panel)
        self.reset_button = QPushButton("Reset Counters", system_panel)
        controls.addWidget(self.refresh_button)
        controls.addWidget(self.reset_button)
        controls.addStretch(1)
        system_layout.addLayout(controls)
        root.addWidget(system_panel, 1)

        self.refresh_button.clicked.connect(self.refresh)
        self.reset_button.clicked.connect(self.reset_counters)

    def _bind_controller(self) -> None:
        controller = self.controller
        if controller is None:
            return
        if hasattr(controller, "keyStateChanged"):
            controller.keyStateChanged.connect(self._on_key_state)
        if hasattr(controller, "encoderChanged"):
            controller.encoderChanged.connect(self._on_encoder_status)
        if hasattr(controller, "lastPacketChanged"):
            controller.lastPacketChanged.connect(self._on_last_packet)
        if hasattr(controller, "setupChanged"):
            controller.setupChanged.connect(self._on_setup_changed)

    def _update_known_keys_from_controller(self) -> None:
        controller = self.controller
        if controller is None:
            return
        raw_keys = getattr(getattr(controller, "store", None), "keys", [])
        keys: list[tuple[int, int]] = []
        for raw in list(raw_keys or []):
            if isinstance(raw, tuple) and len(raw) == 2:
                keys.append((int(raw[0]), int(raw[1])))
        if not keys:
            return
        self._set_known_keys(keys)

    def _set_known_keys(self, keys: list[tuple[int, int]]) -> None:
        normalized = sorted(set((int(row), int(col)) for row, col in keys))
        self.known_keys = normalized
        for key in normalized:
            self.key_press_counts.setdefault(key, 0)
        self._update_key_table()
        self._update_summary()

    def _on_setup_changed(self, _setup: object) -> None:
        self._update_known_keys_from_controller()

    def _on_last_packet(self, text: str) -> None:
        self.last_packet = str(text or "").strip()
        self.last_packet_label.setText(f"Last packet: {self.last_packet or 'n/a'}")

    def _on_key_state(self, row: int, col: int, pressed: bool) -> None:
        if not pressed:
            return
        key = (int(row), int(col))
        if key not in self.key_press_counts:
            self.key_press_counts[key] = 0
            self.known_keys = sorted(set(self.known_keys + [key]))
        self.key_press_counts[key] += 1
        self.total_key_presses += 1
        self._update_key_table()
        self._update_summary()

    def _on_encoder_status(self, text: str) -> None:
        raw = str(text or "").strip().upper()
        if raw.startswith("ENC="):
            value = raw.split("=", 1)[1].strip()
            if value.startswith("+"):
                value = value[1:]
            with suppress(ValueError):
                delta = int(value, 10)
                if delta > 0:
                    self.encoder_up_steps += delta
                    self.encoder_up_events += 1
                elif delta < 0:
                    self.encoder_down_steps += abs(delta)
                    self.encoder_down_events += 1
        elif raw == "ENC_SW=1":
            self.encoder_switch_presses += 1
        self._update_encoder_graph()
        self._update_summary()

    def _update_key_table(self) -> None:
        keys = self.known_keys or sorted(self.key_press_counts.keys())
        self.key_table.setRowCount(len(keys))
        max_count = 0
        for key in keys:
            max_count = max(max_count, int(self.key_press_counts.get(key, 0)))
        bar_max = max(1, max_count)
        for row_index, key in enumerate(keys):
            count = int(self.key_press_counts.get(key, 0))
            self.key_table.setItem(row_index, 0, QTableWidgetItem(f"{key[0]},{key[1]}"))
            self.key_table.setItem(row_index, 1, QTableWidgetItem(str(count)))
            bar = QProgressBar(self.key_table)
            bar.setRange(0, bar_max)
            bar.setValue(count)
            bar.setTextVisible(True)
            if max_count > 0:
                pct = int(round((count / max_count) * 100))
                bar.setFormat(f"{pct}%")
            else:
                bar.setFormat("0%")
            self.key_table.setCellWidget(row_index, 2, bar)

    def _update_encoder_graph(self) -> None:
        max_steps = max(1, self.encoder_up_steps, self.encoder_down_steps)
        self.enc_up_bar.setRange(0, max_steps)
        self.enc_up_bar.setValue(self.encoder_up_steps)
        self.enc_down_bar.setRange(0, max_steps)
        self.enc_down_bar.setValue(self.encoder_down_steps)
        self.enc_up_value.setText(f"Up steps: {self.encoder_up_steps} (events: {self.encoder_up_events})")
        self.enc_down_value.setText(f"Down steps: {self.encoder_down_steps} (events: {self.encoder_down_events})")
        self.enc_sw_value.setText(f"Switch presses: {self.encoder_switch_presses}")

    def _update_summary(self) -> None:
        keys = self.known_keys or sorted(self.key_press_counts.keys())
        self.total_keys_label.setText(f"Total key presses: {self.total_key_presses}")
        if not keys:
            self.most_key_label.setText("Most pressed: n/a")
            self.least_key_label.setText("Least pressed: n/a")
        else:
            most_key = max(keys, key=lambda key: int(self.key_press_counts.get(key, 0)))
            least_key = min(keys, key=lambda key: int(self.key_press_counts.get(key, 0)))
            most_count = int(self.key_press_counts.get(most_key, 0))
            least_count = int(self.key_press_counts.get(least_key, 0))
            self.most_key_label.setText(f"Most pressed: {most_key[0]},{most_key[1]} ({most_count})")
            self.least_key_label.setText(f"Least pressed: {least_key[0]},{least_key[1]} ({least_count})")
        self.encoder_summary_label.setText(
            "Encoder: "
            f"up {self.encoder_up_steps} ({self.encoder_up_events} events) | "
            f"down {self.encoder_down_steps} ({self.encoder_down_events} events) | "
            f"switch {self.encoder_switch_presses}"
        )
        self.refresh_count_label.setText(f"Graph refreshes: {self.refresh_count}")
        self.last_packet_label.setText(f"Last packet: {self.last_packet or 'n/a'}")
        self.last_refresh_label.setText(f"Last refresh: {self.last_refresh or 'n/a'}")

    def _update_system_report(self) -> None:
        paths = resolve_app_paths()
        report = build_system_stats_report(
            StatsContext(data_root=paths.data_root, app_started_monotonic=self.started_monotonic)
        )
        self.system_text.setPlainText(report)

    def refresh(self) -> None:
        self.refresh_count += 1
        self.last_refresh = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._update_key_table()
        self._update_encoder_graph()
        self._update_summary()
        self._update_system_report()

    def reset_counters(self) -> None:
        self.total_key_presses = 0
        for key in list(self.key_press_counts.keys()):
            self.key_press_counts[key] = 0
        self.encoder_up_steps = 0
        self.encoder_down_steps = 0
        self.encoder_up_events = 0
        self.encoder_down_events = 0
        self.encoder_switch_presses = 0
        self.refresh()
