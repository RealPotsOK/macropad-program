from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from ...core.key_layout import KEY_DISPLAY_MAP, display_grid_size
from ...core.actions import parse_file_action_value
from ...core.profile import KeyBinding
from ...core.step_blocks import parse_step_script
from ..theme import BORDER_MUTED, BORDER_SELECTED


class KeyTile(QFrame):
    clicked = Signal(int, int)

    def __init__(self, row: int, col: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.row = row
        self.col = col
        self._pressed = False
        self._selected = False
        self._compact = False
        self.setObjectName("KeyTile")
        self.setProperty("panel", True)
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(12, 10, 12, 10)
        self._layout.setSpacing(5)
        self.title_label = QLabel(f"Key {row},{col}")
        self.title_label.setWordWrap(True)
        self.title_label.setStyleSheet("font-weight: 700;")
        self.action_label = QLabel("none")
        self.action_label.setWordWrap(True)
        self.action_label.setObjectName("Muted")
        self.state_label = QLabel("UP")
        self.state_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.state_label.setStyleSheet("font-weight: 600;")
        self._layout.addWidget(self.title_label)
        self._layout.addWidget(self.action_label, 1)
        self._layout.addWidget(self.state_label)
        self._refresh_style()

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.row, self.col)
            event.accept()
            return
        super().mousePressEvent(event)

    def set_binding(self, binding: KeyBinding) -> None:
        self.title_label.setText(binding.label or f"Key {self.row},{self.col}")
        self.action_label.setText(_summary_for_binding(binding))

    def set_pressed(self, pressed: bool) -> None:
        self._pressed = bool(pressed)
        self.state_label.setText("DOWN" if self._pressed else "UP")
        self._refresh_style()

    def set_selected(self, selected: bool) -> None:
        self._selected = bool(selected)
        self._refresh_style()

    def set_compact(self, compact: bool) -> None:
        compact_value = bool(compact)
        if compact_value == self._compact:
            return
        self._compact = compact_value
        self.title_label.setVisible(not compact_value)
        self.state_label.setVisible(not compact_value)
        if compact_value:
            self._layout.setContentsMargins(8, 6, 8, 6)
            self._layout.setSpacing(2)
            self.action_label.setAlignment(Qt.AlignCenter)
        else:
            self._layout.setContentsMargins(12, 10, 12, 10)
            self._layout.setSpacing(5)
            self.action_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

    def _refresh_style(self) -> None:
        background = "#2c476b" if self._pressed else "#1d2a44"
        if self._selected and not self._pressed:
            background = "#253858"
        border = BORDER_SELECTED if self._selected else BORDER_MUTED
        self.setStyleSheet(
            f"""
            QFrame#KeyTile {{
                background: {background};
                border: 1px solid {border};
                border-radius: 14px;
            }}
            QLabel {{
                background: transparent;
            }}
            """
        )


class KeyMatrixWidget(QWidget):
    keySelected = Signal(int, int)

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        layout_map: dict[tuple[int, int], tuple[int, int]] | None = None,
    ) -> None:
        super().__init__(parent)
        self._tiles: dict[tuple[int, int], KeyTile] = {}
        self._selected_key: tuple[int, int] | None = None
        self._rows = 0
        self._cols = 0
        self._layout_map: dict[tuple[int, int], tuple[int, int]] = {}
        self._layout = QGridLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(10)
        self.set_layout_map(layout_map or KEY_DISPLAY_MAP)

    def set_binding(self, row: int, col: int, binding: KeyBinding) -> None:
        tile = self._tiles.get((row, col))
        if tile is not None:
            tile.set_binding(binding)

    def set_profile_bindings(self, bindings: dict[tuple[int, int], KeyBinding]) -> None:
        for key, tile in self._tiles.items():
            binding = bindings.get(key)
            if binding is not None:
                tile.set_binding(binding)

    def set_key_state(self, row: int, col: int, pressed: bool) -> None:
        tile = self._tiles.get((row, col))
        if tile is not None:
            tile.set_pressed(pressed)

    def set_selected_key(self, row: int, col: int) -> None:
        self._selected_key = (row, col)
        for key, tile in self._tiles.items():
            tile.set_selected(key == self._selected_key)

    def set_layout_map(self, layout_map: dict[tuple[int, int], tuple[int, int]]) -> None:
        normalized = {
            (int(board_key[0]), int(board_key[1])): (int(display_key[0]), int(display_key[1]))
            for board_key, display_key in dict(layout_map or {}).items()
        }
        if not normalized:
            normalized = dict(KEY_DISPLAY_MAP)
        if normalized == self._layout_map:
            return

        previous_selected = self._selected_key
        self._layout_map = normalized
        self._clear_layout()
        self._tiles = {}
        self._rows, self._cols = display_grid_size(self._layout_map)

        for board_key, display_key in sorted(self._layout_map.items(), key=lambda item: item[1]):
            row, col = board_key
            display_row, display_col = display_key
            tile = KeyTile(row, col)
            tile.clicked.connect(self._handle_tile_click)
            self._tiles[(row, col)] = tile
            self._layout.addWidget(tile, display_row, display_col)

        for row in range(self._rows):
            self._layout.setRowStretch(row, 1)
        for col in range(self._cols):
            self._layout.setColumnStretch(col, 1)

        if previous_selected in self._tiles:
            self.set_selected_key(*previous_selected)
        elif self._tiles:
            first_key = sorted(self._tiles.keys())[0]
            self.set_selected_key(*first_key)

        self._apply_uniform_tile_size()

    def _handle_tile_click(self, row: int, col: int) -> None:
        self.set_selected_key(row, col)
        self.keySelected.emit(row, col)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._apply_uniform_tile_size()

    def _apply_uniform_tile_size(self) -> None:
        if not self._tiles or self._rows <= 0 or self._cols <= 0:
            return
        rect = self.contentsRect()
        spacing = max(0, self._layout.spacing())
        available_width = max(1, rect.width() - (self._cols - 1) * spacing)
        available_height = max(1, rect.height() - (self._rows - 1) * spacing)
        cell_width = max(1, available_width // self._cols)
        cell_height = max(1, available_height // self._rows)
        compact_mode = cell_height < 120 or cell_width < 170
        for tile in self._tiles.values():
            tile.setMaximumSize(cell_width, cell_height)
            tile.set_compact(compact_mode)

    def _clear_layout(self) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()


def _summary_for_binding(binding: KeyBinding) -> str:
    action = binding.action
    kind = str(action.kind or "").strip().lower()
    value = str(action.value or "").strip()
    if kind and kind != "none":
        if kind == "file" and value:
            file_spec = parse_file_action_value(value)
            file_name = Path(file_spec.path or value).name.strip()
            if file_name:
                value = file_name
        if value:
            return f"{kind}: {value}"
        return kind
    mode = str(binding.script_mode or "").strip().lower()
    if mode == "step" and bool((binding.script_code or "").strip()):
        count = len(parse_step_script(binding.script_code))
        return f"step: {count} block(s)" if count else "step"
    return "none"
