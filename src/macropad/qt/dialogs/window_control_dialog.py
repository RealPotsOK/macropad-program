from __future__ import annotations

from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

from ...core.window_control import (
    WINDOW_CONTROL_MODE_APPS,
    WINDOW_CONTROL_MODE_MONITOR,
    WindowInfo,
    WindowControlError,
    WindowControlSpec,
    format_window_control_value,
    list_window_control_windows,
    parse_window_control_value,
)


class WindowControlDialog(QDialog):
    def __init__(self, *, current_value: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Window Control Action")
        self.setModal(True)

        self._spec = parse_window_control_value(current_value)
        self._windows: list[WindowInfo] = []

        root = QVBoxLayout(self)
        form = QFormLayout()
        root.addLayout(form)

        self.mode = QComboBox()
        self.mode.addItem("apps")
        self.mode.addItem("monitor")
        self.mode.setCurrentText(self._spec.mode)
        form.addRow("Mode", self.mode)

        self.monitor = QComboBox()
        form.addRow("Monitor", self.monitor)

        refresh_row = QHBoxLayout()
        self.refresh_button = QPushButton("Refresh windows")
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        refresh_row.addWidget(self.refresh_button)
        refresh_row.addWidget(self.status_label, 1)
        root.addLayout(refresh_row)

        self.active_window = QComboBox()
        self.active_window.setToolTip("Pick a window to auto-set monitor and target app.")
        form.addRow("Active window", self.active_window)

        self.targets = QListWidget()
        self.targets.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self.targets.setMinimumHeight(140)
        root.addWidget(self.targets)

        buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Ok)
        root.addWidget(buttons)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        self.refresh_button.clicked.connect(self._refresh_windows)
        self.mode.currentTextChanged.connect(self._refresh_enabled)
        self.monitor.currentIndexChanged.connect(self._populate_targets)
        self.active_window.currentIndexChanged.connect(self._adopt_active_window)

        self._refresh_windows()
        self._refresh_enabled()

    def _refresh_windows(self) -> None:
        try:
            self._windows = list_window_control_windows()
        except WindowControlError as exc:
            self._windows = []
            self.status_label.setText(str(exc))
            self.active_window.clear()
            self.targets.clear()
            self._refresh_enabled()
            return

        self.active_window.blockSignals(True)
        self.active_window.clear()
        self.active_window.addItem("<none>", ("", 0))
        max_monitor = 1
        for item in self._windows:
            label = f"[M{item.monitor}] {item.app or '<unknown app>'} - {item.title}"
            self.active_window.addItem(label, (item.app, item.monitor))
            max_monitor = max(max_monitor, int(item.monitor))
        self.active_window.blockSignals(False)

        self._refresh_monitor_options(max_monitor=max_monitor)
        self._populate_targets()

        if self._windows:
            self.status_label.setText(f"Found {len(self._windows)} windows.")
        else:
            self.status_label.setText("No eligible windows found.")
        self._refresh_enabled()

    def _populate_targets(self) -> None:
        current_monitor = self._selected_monitor()
        apps: list[str] = []
        seen: set[str] = set()
        for item in self._windows:
            if int(item.monitor) != current_monitor:
                continue
            app = str(item.app or "").strip().lower()
            if not app or app in seen:
                continue
            seen.add(app)
            apps.append(app)
        apps.sort()

        selected = set(self._spec.targets)
        self.targets.blockSignals(True)
        self.targets.clear()
        for app in apps:
            row = QListWidgetItem(app)
            if app in selected:
                row.setSelected(True)
            self.targets.addItem(row)
        self.targets.blockSignals(False)

    def _adopt_active_window(self, index: int) -> None:
        payload = self.active_window.itemData(index)
        if not isinstance(payload, tuple) or len(payload) != 2:
            return
        app, monitor = payload
        try:
            monitor_value = int(monitor)
        except (TypeError, ValueError):
            monitor_value = 0
        if monitor_value > 0:
            self._set_selected_monitor(monitor_value)
        app_text = str(app or "").strip().lower()
        if not app_text:
            return
        for idx in range(self.targets.count()):
            item = self.targets.item(idx)
            if item is None:
                continue
            item.setSelected(item.text().strip().lower() == app_text)

    def _refresh_enabled(self) -> None:
        mode = self.mode.currentText().strip().lower()
        apps_mode = mode == WINDOW_CONTROL_MODE_APPS
        self.targets.setEnabled(apps_mode)

    def value(self) -> str:
        mode = self.mode.currentText().strip().lower()
        monitor = self._selected_monitor()
        targets: list[str] = []
        if mode == WINDOW_CONTROL_MODE_APPS:
            for item in self.targets.selectedItems():
                token = str(item.text() or "").strip().lower()
                if token:
                    targets.append(token)
        spec = WindowControlSpec(
            mode=WINDOW_CONTROL_MODE_MONITOR if mode == WINDOW_CONTROL_MODE_MONITOR else WINDOW_CONTROL_MODE_APPS,
            monitor=max(1, monitor),
            targets=tuple(targets),
        )
        return format_window_control_value(spec)

    def _refresh_monitor_options(self, *, max_monitor: int) -> None:
        monitor_count = max(1, self._system_monitor_count(), int(max_monitor), int(self._spec.monitor))
        current = self._selected_monitor()
        target = max(1, current, int(self._spec.monitor))
        self.monitor.blockSignals(True)
        self.monitor.clear()
        for index in range(1, monitor_count + 1):
            self.monitor.addItem(f"Monitor {index}", index)
        self.monitor.blockSignals(False)
        self._set_selected_monitor(target)

    def _set_selected_monitor(self, monitor: int) -> None:
        target = max(1, int(monitor))
        index = self.monitor.findData(target)
        if index < 0:
            index = 0
        if index >= 0:
            self.monitor.setCurrentIndex(index)

    def _selected_monitor(self) -> int:
        data = self.monitor.currentData()
        try:
            return max(1, int(data))
        except (TypeError, ValueError):
            return 1

    def _system_monitor_count(self) -> int:
        app = QGuiApplication.instance()
        if app is None:
            return 1
        try:
            screens = app.screens()
        except Exception:
            return 1
        return max(1, len(screens))
