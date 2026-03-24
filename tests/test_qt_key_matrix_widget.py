from __future__ import annotations

from macropad.qt.widgets.key_matrix_widget import KeyMatrixWidget
from macropad.core.profile import KeyAction, KeyBinding
from macropad.core.step_blocks import BLOCK_PRESS_KEY, serialize_step_script


def test_key_matrix_tiles_resize_to_uniform_cell_sizes(qtbot) -> None:
    widget = KeyMatrixWidget()
    qtbot.addWidget(widget)
    widget.resize(800, 600)
    widget.show()
    qtbot.waitExposed(widget)
    qtbot.wait(50)

    widths = {tile.width() for tile in widget._tiles.values()}
    heights = {tile.height() for tile in widget._tiles.values()}

    assert len(widths) == 1
    assert len(heights) == 1


def test_key_matrix_summary_prefers_direct_action_over_step_script(qtbot) -> None:
    widget = KeyMatrixWidget()
    qtbot.addWidget(widget)

    binding = KeyBinding(
        label="Key 0,0",
        action=KeyAction(kind="file", value=""),
        script_mode="step",
        script_code=serialize_step_script([{"type": BLOCK_PRESS_KEY, "key": "a"}]),
    )

    widget.set_binding(0, 0, binding)

    assert widget._tiles[(0, 0)].action_label.text() == "file"


def test_key_matrix_summary_shows_file_name_only_for_file_action(qtbot) -> None:
    widget = KeyMatrixWidget()
    qtbot.addWidget(widget)

    binding = KeyBinding(
        label="Key 0,0",
        action=KeyAction(kind="file", value=r"C:\tmp\scripts\toggle_opera_gx_session.py"),
    )

    widget.set_binding(0, 0, binding)

    assert widget._tiles[(0, 0)].action_label.text() == "file: toggle_opera_gx_session.py"


def test_key_matrix_compact_mode_hides_index_and_state_when_too_small(qtbot) -> None:
    widget = KeyMatrixWidget()
    qtbot.addWidget(widget)
    widget.resize(280, 180)
    widget.show()
    qtbot.waitExposed(widget)
    qtbot.wait(50)

    tile = widget._tiles[(0, 0)]
    assert tile.action_label.isVisible()
    assert not tile.title_label.isVisible()
    assert not tile.state_label.isVisible()
