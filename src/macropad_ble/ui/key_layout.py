from __future__ import annotations

# Edit this mapping to change where board keys appear in the GUI.
# Key: (board_row, board_col)
# Value: (display_row, display_col)
KEY_DISPLAY_MAP: dict[tuple[int, int], tuple[int, int]] = {
    (0, 0): (2, 0),
    (0, 1): (2, 1),
    (0, 2): (2, 2),
    (0, 3): (2, 3),
    (1, 0): (1, 0),
    (1, 1): (1, 1),
    (1, 2): (1, 2),
    (1, 3): (1, 3),
    (2, 0): (0, 0),
    (2, 1): (0, 1),
    (2, 2): (0, 2),
    (2, 3): (0, 3),
}


def map_key_to_display(row: int, col: int) -> tuple[int, int] | None:
    return KEY_DISPLAY_MAP.get((row, col))


def display_grid_size() -> tuple[int, int]:
    if not KEY_DISPLAY_MAP:
        return (0, 0)

    max_row = max(position[0] for position in KEY_DISPLAY_MAP.values())
    max_col = max(position[1] for position in KEY_DISPLAY_MAP.values())
    return (max_row + 1, max_col + 1)
