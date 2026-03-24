from __future__ import annotations

from macropad.qt.widgets.step_editor import StepEditorWidget
from PySide6.QtCore import Qt

from macropad.core.step_blocks import (
    BLOCK_END,
    BLOCK_FOREVER,
    BLOCK_MOVE_MOUSE,
    BLOCK_REPEAT,
    BLOCK_TYPE_TEXT,
    BLOCK_WAIT,
    BLOCK_WHILE_MOUSE_PRESSED,
    BLOCK_WHILE_PRESSED,
    MOVE_TARGET_COORDS,
)
from macropad.qt.widgets.step_editor.constants import ITEM_SEPARATOR_BEFORE_ROLE


def test_step_editor_hides_irrelevant_rows_for_move_mouse(qtbot) -> None:
    widget = StepEditorWidget()
    qtbot.addWidget(widget)
    widget.show()
    qtbot.waitExposed(widget)
    widget.set_blocks([
        {"type": BLOCK_MOVE_MOUSE, "target": MOVE_TARGET_COORDS, "x": 600, "y": 600},
    ])

    details = widget.details
    details.set_block({"type": BLOCK_MOVE_MOUSE, "target": MOVE_TARGET_COORDS, "x": 600, "y": 600})

    assert details._rows["target"][0].isVisible()
    assert details._rows["x"][0].isVisible()
    assert details._rows["y"][0].isVisible()
    assert not details._rows["button"][0].isVisible()
    assert not details._rows["clicks"][0].isVisible()
    assert not details._rows["key"][0].isVisible()
    assert not details._rows["times"][0].isVisible()
    assert not details._rows["max_loops"][0].isVisible()
    assert not details._rows["interval"][0].isVisible()


def test_step_editor_adds_end_for_scoped_repeat(qtbot) -> None:
    widget = StepEditorWidget()
    qtbot.addWidget(widget)
    widget.show()
    qtbot.waitExposed(widget)

    for index in range(widget.palette.count()):
        item = widget.palette.item(index)
        if item is not None and item.data(Qt.ItemDataRole.UserRole) == BLOCK_REPEAT:
            widget.palette.setCurrentRow(index)
            break

    widget._add_from_palette()

    assert [block["type"] for block in widget.blocks()] == [BLOCK_REPEAT, BLOCK_END]


def test_step_editor_reindents_blocks_when_moved_inside_scope(qtbot) -> None:
    widget = StepEditorWidget()
    qtbot.addWidget(widget)
    widget.show()
    qtbot.waitExposed(widget)
    widget.set_blocks(
        [
            {"type": BLOCK_REPEAT, "times": 2},
            {"type": BLOCK_END},
            {"type": BLOCK_MOVE_MOUSE, "target": MOVE_TARGET_COORDS, "x": 600, "y": 600},
        ]
    )

    widget.block_list.setCurrentRow(2)
    widget._move_selected(-1)

    assert [block["type"] for block in widget.blocks()] == [BLOCK_REPEAT, BLOCK_MOVE_MOUSE, BLOCK_END]
    assert widget.block_list.item(1).text().startswith("02.   ")


def test_step_editor_loads_and_applies_single_block_details(qtbot) -> None:
    widget = StepEditorWidget()
    qtbot.addWidget(widget)
    widget.show()
    qtbot.waitExposed(widget)
    widget.set_blocks(
        [
            {"type": BLOCK_MOVE_MOUSE, "target": MOVE_TARGET_COORDS, "x": 600, "y": 600},
        ]
    )

    assert widget.details.block()["x"] == 600
    assert widget.details.block()["y"] == 600

    widget.details.x_spin.setValue(640)
    widget.details.y_spin.setValue(620)

    assert widget.blocks()[0]["x"] == 640
    assert widget.blocks()[0]["y"] == 620


def test_step_editor_drag_sync_uses_item_payload_not_stale_indices(qtbot) -> None:
    widget = StepEditorWidget()
    qtbot.addWidget(widget)
    widget.show()
    qtbot.waitExposed(widget)
    widget.set_blocks(
        [
            {"type": BLOCK_MOVE_MOUSE, "target": MOVE_TARGET_COORDS, "x": 600, "y": 600},
            {"type": BLOCK_REPEAT, "times": 2},
            {"type": BLOCK_END},
        ]
    )

    moved = widget.block_list.takeItem(0)
    assert moved is not None
    widget.block_list.insertItem(2, moved)
    widget.block_list.setCurrentRow(0)
    widget._sync_from_list()

    assert [block["type"] for block in widget.blocks()] == [BLOCK_REPEAT, BLOCK_END, BLOCK_MOVE_MOUSE]


def test_step_editor_live_updates_selected_block(qtbot) -> None:
    widget = StepEditorWidget()
    qtbot.addWidget(widget)
    widget.show()
    qtbot.waitExposed(widget)
    widget.set_blocks(
        [
            {"type": BLOCK_MOVE_MOUSE, "target": MOVE_TARGET_COORDS, "x": 600, "y": 600},
        ]
    )

    widget.details.x_spin.setValue(700)
    widget.details.y_spin.setValue(710)

    assert widget.blocks()[0]["x"] == 700
    assert widget.blocks()[0]["y"] == 710


def test_step_palette_includes_wait_and_groups_loop_blocks_together(qtbot) -> None:
    widget = StepEditorWidget()
    qtbot.addWidget(widget)
    widget.show()
    qtbot.waitExposed(widget)

    block_types = [
        str(widget.palette.item(i).data(Qt.ItemDataRole.UserRole))
        for i in range(widget.palette.count())
        if widget.palette.item(i) is not None
    ]
    assert BLOCK_WAIT in block_types

    flow_slice = block_types[0:5]
    assert flow_slice == [BLOCK_FOREVER, BLOCK_REPEAT, BLOCK_WHILE_PRESSED, BLOCK_WHILE_MOUSE_PRESSED, BLOCK_END]
    assert block_types.index(BLOCK_TYPE_TEXT) > block_types.index(BLOCK_WHILE_PRESSED)


def test_step_palette_shows_faint_separator_between_block_groups(qtbot) -> None:
    widget = StepEditorWidget()
    qtbot.addWidget(widget)
    widget.show()
    qtbot.waitExposed(widget)

    separators = [
        bool(widget.palette.item(i).data(ITEM_SEPARATOR_BEFORE_ROLE))
        for i in range(widget.palette.count())
        if widget.palette.item(i) is not None
    ]
    assert separators.count(True) >= 2
