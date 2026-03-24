from __future__ import annotations

from PySide6.QtCore import Qt

from ....core.step_blocks import (
    BLOCK_IF_ELSE_PRESSED,
    STEP_BLOCK_PALETTE,
)

BLOCK_LABELS = {block_type: label for block_type, label, _color in STEP_BLOCK_PALETTE}
BLOCK_COLORS = {block_type: color for block_type, _label, color in STEP_BLOCK_PALETTE}
BLOCK_LABELS.update(
    {
        BLOCK_IF_ELSE_PRESSED: "If / Else Key (Legacy)",
    }
)
BLOCK_COLORS.update(
    {
        BLOCK_IF_ELSE_PRESSED: "#E9D5FF",
    }
)

ITEM_BG_ROLE = int(Qt.ItemDataRole.UserRole) + 10
ITEM_TEXT_ROLE = int(Qt.ItemDataRole.UserRole) + 11
ITEM_BLOCK_ROLE = int(Qt.ItemDataRole.UserRole) + 12
ITEM_SEPARATOR_BEFORE_ROLE = int(Qt.ItemDataRole.UserRole) + 13
