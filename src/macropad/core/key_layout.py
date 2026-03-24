from __future__ import annotations

DEFAULT_KEY_ROWS = 3
DEFAULT_KEY_COLS = 4


def normalize_key_dimensions(rows: int, cols: int) -> tuple[int, int]:
    row_count = max(1, min(12, int(rows)))
    col_count = max(1, min(12, int(cols)))
    return row_count, col_count


def build_virtual_keys(rows: int = DEFAULT_KEY_ROWS, cols: int = DEFAULT_KEY_COLS) -> list[tuple[int, int]]:
    row_count, col_count = normalize_key_dimensions(rows, cols)
    return [(row, col) for row in range(row_count) for col in range(col_count)]


def build_display_map(
    rows: int = DEFAULT_KEY_ROWS,
    cols: int = DEFAULT_KEY_COLS,
    *,
    row0_at_bottom: bool = True,
) -> dict[tuple[int, int], tuple[int, int]]:
    row_count, col_count = normalize_key_dimensions(rows, cols)
    mapping: dict[tuple[int, int], tuple[int, int]] = {}
    for row in range(row_count):
        display_row = (row_count - 1 - row) if row0_at_bottom else row
        for col in range(col_count):
            mapping[(row, col)] = (display_row, col)
    return mapping


def key_to_text(key: tuple[int, int]) -> str:
    return f"{int(key[0])},{int(key[1])}"


def key_from_text(value: str) -> tuple[int, int] | None:
    text = str(value or "").strip()
    if not text:
        return None
    parts = [part.strip() for part in text.split(",", 1)]
    if len(parts) != 2:
        return None
    try:
        row = int(parts[0], 10)
        col = int(parts[1], 10)
    except ValueError:
        return None
    if row < 0 or col < 0:
        return None
    return row, col


# Default mapping used by the controller page and tests.
# Key: (virtual_row, virtual_col)
# Value: (display_row, display_col)
KEY_DISPLAY_MAP: dict[tuple[int, int], tuple[int, int]] = build_display_map()


def map_key_to_display(row: int, col: int) -> tuple[int, int] | None:
    return KEY_DISPLAY_MAP.get((row, col))


def display_grid_size(mapping: dict[tuple[int, int], tuple[int, int]] | None = None) -> tuple[int, int]:
    active = mapping or KEY_DISPLAY_MAP
    if not active:
        return (0, 0)

    max_row = max(position[0] for position in active.values())
    max_col = max(position[1] for position in active.values())
    return (max_row + 1, max_col + 1)
