from __future__ import annotations

from contextlib import suppress
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ....core.step_blocks import (
    BLOCK_END,
    BLOCK_FOREVER,
    BLOCK_IF_MOUSE_PRESSED,
    BLOCK_IF_PRESSED,
    BLOCK_CLICK_MOUSE,
    BLOCK_HOLD_KEY,
    BLOCK_MOVE_MOUSE,
    BLOCK_PRESS_KEY,
    BLOCK_REPEAT,
    BLOCK_RESTORE_MOUSE_POS,
    BLOCK_RELEASE_KEY,
    BLOCK_SAVE_MOUSE_POS,
    BLOCK_TYPE_TEXT,
    BLOCK_WAIT,
    BLOCK_WHILE_MOUSE_PRESSED,
    BLOCK_WHILE_PRESSED,
    SCOPED_BLOCKS,
    STEP_BLOCK_PALETTE,
    compute_step_indent_levels,
    default_step_block,
    normalize_step_block,
    parse_step_script,
    serialize_step_script,
    summarize_step_block,
)
from ...smooth_scroll import install_smooth_wheel_scroll
from .constants import (
    BLOCK_COLORS,
    ITEM_BG_ROLE,
    ITEM_BLOCK_ROLE,
    ITEM_SEPARATOR_BEFORE_ROLE,
    ITEM_TEXT_ROLE,
)
from .delegate import BlockItemDelegate
from .details import BlockDetailsWidget


def _palette_group(block_type: str) -> str:
    block = str(block_type or "").strip().lower()
    if block in {BLOCK_FOREVER, BLOCK_REPEAT, BLOCK_WHILE_PRESSED, BLOCK_WHILE_MOUSE_PRESSED, BLOCK_END}:
        return "flow"
    if block in {BLOCK_IF_PRESSED, BLOCK_IF_MOUSE_PRESSED}:
        return "condition"
    if block in {
        BLOCK_TYPE_TEXT,
        BLOCK_PRESS_KEY,
        BLOCK_HOLD_KEY,
        BLOCK_RELEASE_KEY,
        BLOCK_CLICK_MOUSE,
        BLOCK_MOVE_MOUSE,
        BLOCK_SAVE_MOUSE_POS,
        BLOCK_RESTORE_MOUSE_POS,
        BLOCK_WAIT,
    }:
        return "action"
    return "other"


class StepEditorWidget(QWidget):
    changed = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._blocks: list[dict[str, Any]] = []
        self._updating = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        header = QLabel("Step blocks are stored as a scoped chain. Put blocks between Repeat/If/While and End, then drag rows to reorder.")
        header.setWordWrap(True)
        root.addWidget(header)

        body = QSplitter(Qt.Horizontal)
        body.setObjectName("StepEditorBodySplitter")
        body.setHandleWidth(10)
        body.setChildrenCollapsible(False)
        body.setOpaqueResize(False)
        body.setStyleSheet(
            """
            QSplitter#StepEditorBodySplitter::handle {
                background: rgba(120, 138, 165, 0.45);
                border-radius: 4px;
            }
            QSplitter#StepEditorBodySplitter::handle:horizontal {
                margin: 6px 2px;
            }
            QSplitter#StepEditorBodySplitter::handle:hover {
                background: rgba(120, 138, 165, 0.72);
            }
            """
        )
        root.addWidget(body, 1)

        left = QWidget()
        left.setMinimumWidth(190)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(QLabel("Block palette"))
        self.palette = QListWidget()
        self.palette.setItemDelegate(BlockItemDelegate(self.palette))
        self.palette.setSpacing(4)
        self.palette.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.palette.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.palette.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.palette.setWordWrap(True)
        install_smooth_wheel_scroll(self.palette, duration_ms=190, wheel_step=80)
        previous_group: str | None = None
        for block_type, label, color in STEP_BLOCK_PALETTE:
            group = _palette_group(block_type)
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, block_type)
            item.setToolTip(color)
            item.setData(ITEM_BG_ROLE, color)
            item.setData(ITEM_TEXT_ROLE, label)
            item.setData(ITEM_SEPARATOR_BEFORE_ROLE, previous_group is not None and group != previous_group)
            self.palette.addItem(item)
            previous_group = group
        left_layout.addWidget(self.palette, 1)
        left_add = QPushButton("Add Selected Block")
        left_layout.addWidget(left_add)

        middle = QWidget()
        middle.setMinimumWidth(260)
        middle_layout = QVBoxLayout(middle)
        middle_layout.setContentsMargins(0, 0, 0, 0)
        middle_layout.addWidget(QLabel("Current chain"))
        self.block_list = QListWidget()
        self.block_list.setItemDelegate(BlockItemDelegate(self.block_list))
        self.block_list.setSpacing(4)
        self.block_list.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.block_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.block_list.setDragDropMode(QAbstractItemView.InternalMove)
        self.block_list.setDefaultDropAction(Qt.MoveAction)
        install_smooth_wheel_scroll(self.block_list, duration_ms=190, wheel_step=90)
        middle_layout.addWidget(self.block_list, 1)
        button_row = QHBoxLayout()
        self.add_button = QPushButton("Add")
        self.duplicate_button = QPushButton("Duplicate")
        self.remove_button = QPushButton("Remove")
        self.up_button = QPushButton("Up")
        self.down_button = QPushButton("Down")
        for button in (self.add_button, self.duplicate_button, self.remove_button, self.up_button, self.down_button):
            button_row.addWidget(button)
        middle_layout.addLayout(button_row)

        right = QWidget()
        right.setMinimumWidth(240)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(QLabel("Selected block"))
        self.details = BlockDetailsWidget()
        right_layout.addWidget(self.details, 1)
        self.script_preview = QPlainTextEdit()
        self.script_preview.setReadOnly(True)
        self.script_preview.setPlaceholderText("Serialized STEP script preview")
        self.script_preview.setMaximumHeight(120)
        right_layout.addWidget(self.script_preview)

        body.addWidget(left)
        body.addWidget(middle)
        body.addWidget(right)
        body.setCollapsible(0, False)
        body.setCollapsible(1, False)
        body.setCollapsible(2, False)
        body.setStretchFactor(0, 1)
        body.setStretchFactor(1, 2)
        body.setStretchFactor(2, 2)
        body.setSizes([280, 500, 420])

        self.palette.itemDoubleClicked.connect(lambda _item: self._add_from_palette())
        left_add.clicked.connect(self._add_from_palette)
        self.add_button.clicked.connect(self._add_from_palette)
        self.duplicate_button.clicked.connect(self._duplicate_selected)
        self.remove_button.clicked.connect(self._remove_selected)
        self.up_button.clicked.connect(lambda: self._move_selected(-1))
        self.down_button.clicked.connect(lambda: self._move_selected(1))
        self.block_list.currentRowChanged.connect(self._load_current_block)
        self.block_list.model().rowsMoved.connect(lambda *_args: self._sync_from_list())
        self.details.updated.connect(self._details_changed)

    def set_blocks(self, blocks: list[dict[str, Any]]) -> None:
        self._blocks = [normalize_step_block(block) for block in blocks if isinstance(block, dict)]
        self._refresh_list()

    def blocks(self) -> list[dict[str, Any]]:
        return [normalize_step_block(block) for block in self._blocks]

    def set_script_text(self, script_text: str) -> None:
        self.set_blocks(parse_step_script(script_text))

    def script_text(self) -> str:
        return serialize_step_script(self.blocks())

    def _current_index(self) -> int:
        return max(-1, int(self.block_list.currentRow()))

    def _selected_palette_type(self) -> str:
        item = self.palette.currentItem()
        if item is None:
            return BLOCK_REPEAT
        return str(item.data(Qt.UserRole) or BLOCK_REPEAT)

    def _matching_end_index(self, start_index: int, *, blocks: list[dict[str, Any]] | None = None) -> int | None:
        sequence = self._blocks if blocks is None else blocks
        if start_index < 0 or start_index >= len(sequence):
            return None
        start_type = str(normalize_step_block(sequence[start_index]).get("type") or "")
        if start_type not in SCOPED_BLOCKS:
            return None
        depth = 0
        for index in range(start_index + 1, len(sequence)):
            block_type = str(normalize_step_block(sequence[index]).get("type") or "")
            if block_type in SCOPED_BLOCKS:
                depth += 1
            elif block_type == BLOCK_END:
                if depth == 0:
                    return index
                depth -= 1
        return None

    def _scope_start_for_end(self, end_index: int) -> int | None:
        if end_index < 0 or end_index >= len(self._blocks):
            return None
        if str(normalize_step_block(self._blocks[end_index]).get("type") or "") != BLOCK_END:
            return None
        depth = 0
        for index in range(end_index - 1, -1, -1):
            block_type = str(normalize_step_block(self._blocks[index]).get("type") or "")
            if block_type == BLOCK_END:
                depth += 1
            elif block_type in SCOPED_BLOCKS:
                if depth == 0:
                    return index
                depth -= 1
        return None

    def _add_from_palette(self) -> None:
        block_type = self._selected_palette_type()
        insert_at = self._current_index() + 1 if self._current_index() >= 0 else len(self._blocks)
        self._blocks.insert(insert_at, default_step_block(block_type))
        if block_type in SCOPED_BLOCKS:
            self._blocks.insert(insert_at + 1, {"type": BLOCK_END})
        self._refresh_list(select_index=insert_at)
        self._emit_changed()

    def _duplicate_selected(self) -> None:
        index = self._current_index()
        if index < 0 or index >= len(self._blocks):
            return
        block_type = str(normalize_step_block(self._blocks[index]).get("type") or "")
        if block_type in SCOPED_BLOCKS:
            end_index = self._matching_end_index(index)
            if end_index is not None:
                segment = [dict(block) for block in self._blocks[index : end_index + 1]]
                insert_at = end_index + 1
                self._blocks[insert_at:insert_at] = segment
                self._refresh_list(select_index=insert_at)
                self._emit_changed()
                return
        self._blocks.insert(index + 1, dict(self._blocks[index]))
        self._refresh_list(select_index=index + 1)
        self._emit_changed()

    def _remove_selected(self) -> None:
        index = self._current_index()
        if index < 0 or index >= len(self._blocks):
            return
        block_type = str(normalize_step_block(self._blocks[index]).get("type") or "")
        if block_type in SCOPED_BLOCKS:
            end_index = self._matching_end_index(index)
            if end_index is not None:
                del self._blocks[index : end_index + 1]
            else:
                self._blocks.pop(index)
        elif block_type == BLOCK_END:
            self._blocks.pop(index)
        else:
            self._blocks.pop(index)
        self._refresh_list(select_index=min(index, len(self._blocks) - 1))
        self._emit_changed()

    def _move_selected(self, delta: int) -> None:
        index = self._current_index()
        target = index + int(delta)
        if index < 0 or target < 0 or target >= len(self._blocks):
            return
        self._blocks[index], self._blocks[target] = self._blocks[target], self._blocks[index]
        self._refresh_list(select_index=target)
        self._emit_changed()

    def _apply_details_to_selected(self) -> None:
        self._commit_details_to_selected(force_refresh=True)

    def _details_changed(self) -> None:
        self._commit_details_to_selected(force_refresh=False)

    def _commit_details_to_selected(self, *, force_refresh: bool) -> None:
        index = self._current_index()
        if index < 0 or index >= len(self._blocks):
            self._preview_from_details()
            return
        previous_type = str(normalize_step_block(self._blocks[index]).get("type") or "")
        updated = self.details.block()
        updated_type = str(normalize_step_block(updated).get("type") or "")
        self._blocks[index] = updated
        structure_changed = False
        if previous_type in SCOPED_BLOCKS and updated_type not in SCOPED_BLOCKS:
            end_index = self._matching_end_index(index)
            if end_index is not None:
                self._blocks.pop(end_index)
                structure_changed = True
        elif previous_type not in SCOPED_BLOCKS and updated_type in SCOPED_BLOCKS:
            self._blocks.insert(index + 1, {"type": BLOCK_END})
            structure_changed = True

        if force_refresh or structure_changed or self.block_list.count() != len(self._blocks):
            self._refresh_list(select_index=index)
        else:
            self._refresh_items_in_place()
        self._emit_changed()

    def _load_current_block(self, index: int) -> None:
        if self._updating:
            return
        if index < 0 or index >= len(self._blocks):
            self.details.set_block(default_step_block(BLOCK_END))
            return
        self.details.set_block(self._blocks[index])

    def _preview_from_details(self) -> None:
        self.script_preview.setPlainText(serialize_step_script(self._preview_blocks()))

    def _preview_blocks(self) -> list[dict[str, Any]]:
        index = self._current_index()
        if index < 0 or index >= len(self._blocks):
            return self.blocks()
        preview = list(self._blocks)
        preview[index] = self.details.block()
        return preview

    def _refresh_list(self, *, select_index: int | None = None) -> None:
        self._updating = True
        try:
            current = select_index
            self.block_list.clear()
            indent_levels = compute_step_indent_levels(self._blocks)
            for index, block in enumerate(self._blocks):
                item = QListWidgetItem()
                self._apply_item_state(item, block, index=index, indent=indent_levels[index])
                self.block_list.addItem(item)
            if current is not None and 0 <= current < self.block_list.count():
                self.block_list.setCurrentRow(current)
                self.block_list.scrollToItem(self.block_list.item(current))
            elif self.block_list.count() > 0:
                self.block_list.setCurrentRow(min(max(0, self.block_list.currentRow()), self.block_list.count() - 1))
        finally:
            self._updating = False
        self.script_preview.setPlainText(serialize_step_script(self._blocks))
        self._load_current_block(self.block_list.currentRow())

    def _refresh_items_in_place(self) -> None:
        if self.block_list.count() != len(self._blocks):
            self._refresh_list(select_index=self._current_index())
            return
        indent_levels = compute_step_indent_levels(self._blocks)
        self._updating = True
        try:
            for index, block in enumerate(self._blocks):
                item = self.block_list.item(index)
                if item is None:
                    continue
                self._apply_item_state(item, block, index=index, indent=indent_levels[index])
        finally:
            self._updating = False
        self.script_preview.setPlainText(serialize_step_script(self._blocks))

    def _apply_item_state(self, item: QListWidgetItem, block: dict[str, Any], *, index: int, indent: int) -> None:
        normalized = normalize_step_block(block)
        label = summarize_step_block(normalized, index=index, indent=indent)
        item.setText(label)
        item.setData(Qt.UserRole, index)
        item.setData(ITEM_BG_ROLE, BLOCK_COLORS.get(str(normalized.get("type") or ""), "#E5E7EB"))
        item.setData(ITEM_TEXT_ROLE, label)
        item.setData(ITEM_BLOCK_ROLE, dict(normalized))

    def _sync_from_list(self) -> None:
        if self._updating:
            return
        current_row = self.block_list.currentRow()
        reordered: list[dict[str, Any]] = []
        for index in range(self.block_list.count()):
            item = self.block_list.item(index)
            if item is None:
                continue
            payload = item.data(ITEM_BLOCK_ROLE)
            if isinstance(payload, dict):
                reordered.append(normalize_step_block(payload))
        if len(reordered) == len(self._blocks):
            self._blocks = reordered
            self._refresh_list(select_index=current_row if current_row >= 0 else None)
            self._emit_changed()

    def _emit_changed(self) -> None:
        self.script_preview.setPlainText(serialize_step_script(self._blocks))
        self.changed.emit(self.blocks())

    def clear(self) -> None:
        self.set_blocks([])

    def load(self, script_text: str) -> None:
        self.set_script_text(script_text)

    def dump(self) -> str:
        return self.script_text()

    def add_block(self, block_type: str) -> None:
        self.palette.setCurrentRow(self._palette_index(block_type))
        self._add_from_palette()

    def _palette_index(self, block_type: str) -> int:
        for row in range(self.palette.count()):
            item = self.palette.item(row)
            if item is not None and str(item.data(Qt.UserRole) or "") == block_type:
                return row
        return 0

    def select_index(self, index: int) -> None:
        if 0 <= index < self.block_list.count():
            self.block_list.setCurrentRow(index)

    def selected_index(self) -> int:
        return self._current_index()

    def update_selected_block(self, block: dict[str, Any]) -> None:
        index = self._current_index()
        if index < 0 or index >= len(self._blocks):
            return
        self._blocks[index] = normalize_step_block(block)
        self._refresh_list(select_index=index)
        self._emit_changed()

    def selected_block(self) -> dict[str, Any]:
        index = self._current_index()
        if index < 0 or index >= len(self._blocks):
            return default_step_block(BLOCK_END)
        return normalize_step_block(self._blocks[index])

    def remove_selected(self) -> None:
        self._remove_selected()

    def duplicate_selected(self) -> None:
        self._duplicate_selected()

    def move_selected_up(self) -> None:
        self._move_selected(-1)

    def move_selected_down(self) -> None:
        self._move_selected(1)

    def add_selected_palette(self) -> None:
        self._add_from_palette()

    def set_palette_block(self, block_type: str) -> None:
        self.palette.setCurrentRow(self._palette_index(block_type))

    def has_blocks(self) -> bool:
        return bool(self._blocks)

    def block_count(self) -> int:
        return len(self._blocks)

    def __len__(self) -> int:
        return len(self._blocks)

    def __iter__(self):
        return iter(self.blocks())

    def set_read_only(self, read_only: bool) -> None:
        with suppress(Exception):
            self.palette.setEnabled(not read_only)
            self.add_button.setEnabled(not read_only)
            self.duplicate_button.setEnabled(not read_only)
            self.remove_button.setEnabled(not read_only)
            self.up_button.setEnabled(not read_only)
            self.down_button.setEnabled(not read_only)
            self.details.setEnabled(not read_only)
