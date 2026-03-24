from __future__ import annotations

import asyncio
import ctypes
import json
import sys
from typing import Any, Callable

from .key_names import normalize_single_key_name

STEP_SCRIPT_HEADER = "# STEP_BLOCKS_V1"

BLOCK_PRESS_KEY = "press_key"
BLOCK_MOVE_MOUSE = "move_mouse"
BLOCK_CLICK_MOUSE = "click_mouse"
BLOCK_TYPE_TEXT = "type_text"
BLOCK_HOLD_KEY = "hold_key"
BLOCK_RELEASE_KEY = "release_key"
BLOCK_WAIT = "wait"
BLOCK_REPEAT = "repeat"
BLOCK_FOREVER = "forever"
BLOCK_IF_PRESSED = "if_pressed"
BLOCK_IF_MOUSE_PRESSED = "if_mouse_pressed"
BLOCK_IF_ELSE_PRESSED = "if_else_pressed"
BLOCK_WHILE_PRESSED = "while_pressed"
BLOCK_WHILE_MOUSE_PRESSED = "while_mouse_pressed"
BLOCK_SAVE_MOUSE_POS = "save_mouse_pos"
BLOCK_RESTORE_MOUSE_POS = "restore_mouse_pos"
BLOCK_END = "end"

MOVE_TARGET_COORDS = "coords"
MOVE_TARGET_SAVED = "saved"

STEP_BLOCK_TYPES = (
    BLOCK_FOREVER,
    BLOCK_REPEAT,
    BLOCK_WHILE_PRESSED,
    BLOCK_WHILE_MOUSE_PRESSED,
    BLOCK_END,
    BLOCK_IF_PRESSED,
    BLOCK_IF_MOUSE_PRESSED,
    BLOCK_TYPE_TEXT,
    BLOCK_PRESS_KEY,
    BLOCK_HOLD_KEY,
    BLOCK_RELEASE_KEY,
    BLOCK_CLICK_MOUSE,
    BLOCK_MOVE_MOUSE,
    BLOCK_SAVE_MOUSE_POS,
    BLOCK_RESTORE_MOUSE_POS,
    BLOCK_WAIT,
    BLOCK_IF_ELSE_PRESSED,
)

STEP_BLOCK_PALETTE: list[tuple[str, str, str]] = [
    (BLOCK_FOREVER, "Forever (Toggle)", "#C7D2FE"),
    (BLOCK_REPEAT, "Repeat X Times", "#BFDBFE"),
    (BLOCK_WHILE_PRESSED, "While Key Pressed", "#FEF08A"),
    (BLOCK_WHILE_MOUSE_PRESSED, "While Mouse Pressed", "#FDE68A"),
    (BLOCK_END, "End", "#E5E7EB"),
    (BLOCK_IF_PRESSED, "If Key Pressed", "#DBEAFE"),
    (BLOCK_IF_MOUSE_PRESSED, "If Mouse Pressed", "#DCFCE7"),
    (BLOCK_TYPE_TEXT, "Type Text", "#FBCFE8"),
    (BLOCK_PRESS_KEY, "Press Key", "#FED7AA"),
    (BLOCK_HOLD_KEY, "Hold Key", "#FDE68A"),
    (BLOCK_RELEASE_KEY, "Release Key", "#FECACA"),
    (BLOCK_CLICK_MOUSE, "Click Mouse", "#FEF3C7"),
    (BLOCK_MOVE_MOUSE, "Move Mouse", "#BAE6FD"),
    (BLOCK_SAVE_MOUSE_POS, "Save Mouse Pos", "#BBF7D0"),
    (BLOCK_RESTORE_MOUSE_POS, "Move To Saved Pos", "#A7F3D0"),
    (BLOCK_WAIT, "Wait", "#E5E7EB"),
]

LEGACY_STEP_BLOCK_TYPES = (
    BLOCK_IF_ELSE_PRESSED,
)

SCOPED_BLOCKS = {
    BLOCK_REPEAT,
    BLOCK_FOREVER,
    BLOCK_IF_PRESSED,
    BLOCK_IF_MOUSE_PRESSED,
    BLOCK_WHILE_PRESSED,
    BLOCK_WHILE_MOUSE_PRESSED,
}

DEFAULT_STEP_LOOP_INTERVAL = 0.02


class StepExecutionError(RuntimeError):
    pass


def _clamp_int(raw: Any, default: int, *, minimum: int = 0, maximum: int = 2_000_000) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


def _clamp_float(raw: Any, default: float, *, minimum: float = 0.0, maximum: float = 600.0) -> float:
    try:
        value = float(raw)
    except (TypeError, ValueError):
        value = default
    if value < minimum:
        return minimum
    if value > maximum:
        return maximum
    return value


def _clean_key(value: Any) -> str:
    return normalize_single_key_name(str(value or ""))


def _clean_button(value: Any) -> str:
    button = str(value or "left").strip().lower()
    if button not in {"left", "right", "middle"}:
        return "left"
    return button


def _normalize_move_target(raw: Any) -> str:
    target = str(raw or "").strip().lower()
    if target in {MOVE_TARGET_COORDS, MOVE_TARGET_SAVED}:
        return target
    return MOVE_TARGET_COORDS


def default_step_block(block_type: str) -> dict[str, Any]:
    normalized = str(block_type or "").strip().lower()
    if normalized == BLOCK_PRESS_KEY:
        return {"type": BLOCK_PRESS_KEY, "key": "enter"}
    if normalized == BLOCK_MOVE_MOUSE:
        return {"type": BLOCK_MOVE_MOUSE, "target": MOVE_TARGET_COORDS, "x": 0, "y": 0}
    if normalized == BLOCK_CLICK_MOUSE:
        return {"type": BLOCK_CLICK_MOUSE, "button": "left", "clicks": 1}
    if normalized == BLOCK_SAVE_MOUSE_POS:
        return {"type": BLOCK_SAVE_MOUSE_POS}
    if normalized == BLOCK_RESTORE_MOUSE_POS:
        return {"type": BLOCK_RESTORE_MOUSE_POS}
    if normalized == BLOCK_TYPE_TEXT:
        return {"type": BLOCK_TYPE_TEXT, "text": "Hello"}
    if normalized == BLOCK_HOLD_KEY:
        return {"type": BLOCK_HOLD_KEY, "key": "shift"}
    if normalized == BLOCK_RELEASE_KEY:
        return {"type": BLOCK_RELEASE_KEY, "key": "shift"}
    if normalized == BLOCK_WAIT:
        return {"type": BLOCK_WAIT, "seconds": 0.10}
    if normalized == BLOCK_REPEAT:
        return {"type": BLOCK_REPEAT, "times": 2}
    if normalized == BLOCK_FOREVER:
        return {"type": BLOCK_FOREVER, "interval": DEFAULT_STEP_LOOP_INTERVAL}
    if normalized == BLOCK_IF_PRESSED:
        return {"type": BLOCK_IF_PRESSED, "key": "ctrl"}
    if normalized == BLOCK_IF_MOUSE_PRESSED:
        return {"type": BLOCK_IF_MOUSE_PRESSED, "button": "left"}
    if normalized == BLOCK_IF_ELSE_PRESSED:
        return {"type": BLOCK_IF_ELSE_PRESSED, "key": "ctrl"}
    if normalized == BLOCK_WHILE_PRESSED:
        return {"type": BLOCK_WHILE_PRESSED, "key": "ctrl", "interval": DEFAULT_STEP_LOOP_INTERVAL}
    if normalized == BLOCK_WHILE_MOUSE_PRESSED:
        return {"type": BLOCK_WHILE_MOUSE_PRESSED, "button": "left", "interval": DEFAULT_STEP_LOOP_INTERVAL}
    if normalized == BLOCK_END:
        return {"type": BLOCK_END}
    return {"type": BLOCK_WAIT, "seconds": 0.10}


def normalize_step_block(raw: dict[str, Any] | None) -> dict[str, Any]:
    data = dict(raw or {})
    block_type = str(data.get("type") or "").strip().lower()
    block = default_step_block(block_type)
    block_type = block["type"]

    if block_type == BLOCK_MOVE_MOUSE:
        target_raw = data.get("target")
        if target_raw is None:
            target_raw = data.get("mode")
        block["target"] = _normalize_move_target(target_raw)
        block["x"] = _clamp_int(data.get("x"), 0, minimum=-32_000, maximum=32_000)
        block["y"] = _clamp_int(data.get("y"), 0, minimum=-32_000, maximum=32_000)
        return block
    if block_type == BLOCK_CLICK_MOUSE:
        block["button"] = _clean_button(data.get("button"))
        block["clicks"] = _clamp_int(data.get("clicks"), 1, minimum=1, maximum=50)
        return block
    if block_type == BLOCK_TYPE_TEXT:
        block["text"] = str(data.get("text") or "")
        return block
    if block_type in {BLOCK_PRESS_KEY, BLOCK_HOLD_KEY, BLOCK_RELEASE_KEY, BLOCK_IF_PRESSED, BLOCK_IF_ELSE_PRESSED}:
        block["key"] = _clean_key(data.get("key"))
        return block
    if block_type in {BLOCK_IF_MOUSE_PRESSED, BLOCK_WHILE_MOUSE_PRESSED}:
        block["button"] = _clean_button(data.get("button"))
        block["interval"] = _clamp_float(data.get("interval"), DEFAULT_STEP_LOOP_INTERVAL, minimum=0.0, maximum=10.0)
        block["max_loops"] = _clamp_int(data.get("max_loops"), 0, minimum=0, maximum=100_000)
        return block
    if block_type == BLOCK_WAIT:
        block["seconds"] = _clamp_float(data.get("seconds"), 0.10, minimum=0.0, maximum=600.0)
        return block
    if block_type == BLOCK_REPEAT:
        block["times"] = _clamp_int(data.get("times"), 2, minimum=1, maximum=10_000)
        return block
    if block_type == BLOCK_FOREVER:
        block["interval"] = _clamp_float(data.get("interval"), DEFAULT_STEP_LOOP_INTERVAL, minimum=0.0, maximum=10.0)
        return block
    if block_type == BLOCK_WHILE_PRESSED:
        block["key"] = _clean_key(data.get("key"))
        block["max_loops"] = _clamp_int(data.get("max_loops"), 0, minimum=0, maximum=100_000)
        block["interval"] = _clamp_float(data.get("interval"), DEFAULT_STEP_LOOP_INTERVAL, minimum=0.0, maximum=10.0)
        return block
    return block


def compute_step_indent_levels(blocks: list[dict[str, Any]]) -> list[int]:
    levels: list[int] = []
    depth = 0
    for raw in blocks:
        block = normalize_step_block(raw)
        block_type = block["type"]
        if block_type == BLOCK_END:
            depth = max(0, depth - 1)
            levels.append(depth)
            continue
        levels.append(depth)
        if block_type in SCOPED_BLOCKS:
            depth += 1
    return levels


def summarize_step_block(block: dict[str, Any], *, index: int, indent: int = 0) -> str:
    normalized = normalize_step_block(block)
    block_type = normalized["type"]
    prefix = f"{index + 1:02d}. "
    left_pad = "  " * max(0, int(indent))

    if block_type == BLOCK_MOVE_MOUSE:
        if normalized.get("target") == MOVE_TARGET_SAVED:
            detail = "Move mouse to saved position"
        else:
            detail = f"Move mouse to ({normalized['x']}, {normalized['y']})"
    elif block_type == BLOCK_CLICK_MOUSE:
        detail = f"Click mouse: {normalized['button']} x{normalized['clicks']}"
    elif block_type == BLOCK_SAVE_MOUSE_POS:
        detail = "Save current mouse position"
    elif block_type == BLOCK_RESTORE_MOUSE_POS:
        detail = "Move to saved mouse position"
    elif block_type == BLOCK_TYPE_TEXT:
        text = str(normalized["text"])
        if len(text) > 28:
            text = text[:25] + "..."
        detail = f'Type "{text}"'
    elif block_type == BLOCK_PRESS_KEY:
        detail = f"Press key: {normalized['key'] or '<key>'}"
    elif block_type == BLOCK_HOLD_KEY:
        detail = f"Hold key: {normalized['key'] or '<key>'}"
    elif block_type == BLOCK_RELEASE_KEY:
        detail = f"Release key: {normalized['key'] or '<key>'}"
    elif block_type == BLOCK_WAIT:
        detail = f"Wait {normalized['seconds']:.2f}s"
    elif block_type == BLOCK_REPEAT:
        detail = f"Repeat {normalized['times']}x until End"
    elif block_type == BLOCK_FOREVER:
        detail = "Forever loop until canceled"
    elif block_type == BLOCK_IF_PRESSED:
        detail = f"If [{normalized['key'] or '<key>'}] pressed -> run until End"
    elif block_type == BLOCK_IF_MOUSE_PRESSED:
        detail = f"If mouse [{normalized['button']}] pressed -> run until End"
    elif block_type == BLOCK_IF_ELSE_PRESSED:
        detail = f"If [{normalized['key'] or '<key>'}] pressed -> next block, else block after next"
    elif block_type == BLOCK_WHILE_PRESSED:
        detail = f"While [{normalized['key'] or '<key>'}] pressed -> run until End"
    elif block_type == BLOCK_WHILE_MOUSE_PRESSED:
        detail = f"While mouse [{normalized['button']}] pressed -> run until End"
    elif block_type == BLOCK_END:
        detail = "End"
    else:
        detail = block_type

    return f"{prefix}{left_pad}{detail}"


def parse_step_script(script_code: str) -> list[dict[str, Any]]:
    raw = str(script_code or "").strip()
    if not raw:
        return []

    payload = raw
    if raw.startswith(STEP_SCRIPT_HEADER):
        payload = raw[len(STEP_SCRIPT_HEADER) :].lstrip()
    if not payload:
        return []

    try:
        decoded = json.loads(payload)
    except json.JSONDecodeError:
        return []

    blocks_data: Any = decoded
    if isinstance(decoded, dict):
        blocks_data = decoded.get("blocks", [])
    if not isinstance(blocks_data, list):
        return []
    return [normalize_step_block(item) for item in blocks_data if isinstance(item, dict)]


def serialize_step_script(blocks: list[dict[str, Any]]) -> str:
    normalized = [normalize_step_block(item) for item in blocks if isinstance(item, dict)]
    payload = json.dumps({"version": 1, "blocks": normalized}, indent=2)
    return f"{STEP_SCRIPT_HEADER}\n{payload}\n"


def _keyboard_module():
    try:
        import keyboard  # type: ignore

        return keyboard
    except Exception as exc:  # pragma: no cover - runtime dependency
        raise StepExecutionError(
            "Step blocks that use keys need the 'keyboard' package (pip install keyboard)."
        ) from exc


def _is_key_pressed(key_name: str) -> bool:
    cleaned = _clean_key(key_name)
    if not cleaned:
        return False
    keyboard = _keyboard_module()
    try:
        return bool(keyboard.is_pressed(cleaned))
    except Exception:
        return False


def _is_mouse_button_pressed(button_name: str) -> bool:
    button = _clean_button(button_name)
    if sys.platform == "win32":
        vk = {
            "left": 0x01,
            "right": 0x02,
            "middle": 0x04,
        }[button]
        return bool(ctypes.windll.user32.GetAsyncKeyState(vk) & 0x8000)
    return False


def _move_mouse_now(x: int, y: int) -> None:
    if sys.platform == "win32":
        ctypes.windll.user32.SetCursorPos(int(x), int(y))
        return

    try:
        import pyautogui  # type: ignore

        pyautogui.moveTo(int(x), int(y))
        return
    except Exception as exc:  # pragma: no cover - platform/runtime specific
        raise StepExecutionError(
            "Mouse move requires Windows API support or the 'pyautogui' package."
        ) from exc


def _get_mouse_pos_now() -> tuple[int, int]:
    if sys.platform == "win32":
        point = ctypes.wintypes.POINT()  # type: ignore[attr-defined]
        if ctypes.windll.user32.GetCursorPos(ctypes.byref(point)):
            return int(point.x), int(point.y)
        raise StepExecutionError("Failed to read mouse position from Windows API.")

    try:
        import pyautogui  # type: ignore

        pos = pyautogui.position()
        return int(pos.x), int(pos.y)
    except Exception as exc:  # pragma: no cover - platform/runtime specific
        raise StepExecutionError(
            "Mouse position read requires Windows API support or the 'pyautogui' package."
        ) from exc


def _click_mouse_now(button: str, clicks: int) -> None:
    button_name = _clean_button(button)
    count = _clamp_int(clicks, 1, minimum=1, maximum=50)
    if sys.platform == "win32":
        user32 = ctypes.windll.user32
        flags = {
            "left": (0x0002, 0x0004),
            "right": (0x0008, 0x0010),
            "middle": (0x0020, 0x0040),
        }
        down, up = flags[button_name]
        for _ in range(count):
            user32.mouse_event(down, 0, 0, 0, 0)
            user32.mouse_event(up, 0, 0, 0, 0)
        return

    try:
        import pyautogui  # type: ignore

        pyautogui.click(button=button_name, clicks=count)
        return
    except Exception as exc:  # pragma: no cover - platform/runtime specific
        raise StepExecutionError(
            "Mouse click requires Windows API support or the 'pyautogui' package."
        ) from exc


async def _execute_primitive_block(
    block: dict[str, Any],
    *,
    context: dict[str, Any],
    log: Callable[[str], None] | None,
) -> None:
    block_type = str(block.get("type") or "").strip().lower()
    if block_type == BLOCK_MOVE_MOUSE:
        target = _normalize_move_target(block.get("target"))
        if target == MOVE_TARGET_SAVED:
            saved = context.get("saved_mouse_pos")
            if isinstance(saved, tuple) and len(saved) == 2:
                x, y = int(saved[0]), int(saved[1])
                await asyncio.to_thread(_move_mouse_now, x, y)
                if log:
                    log(f"Step: move mouse to saved position ({x}, {y})")
            else:
                if log:
                    log("Step: move to saved position skipped (nothing saved yet)")
            return

        x = _clamp_int(block.get("x"), 0, minimum=-32_000, maximum=32_000)
        y = _clamp_int(block.get("y"), 0, minimum=-32_000, maximum=32_000)
        await asyncio.to_thread(_move_mouse_now, x, y)
        if log:
            log(f"Step: move mouse to ({x}, {y})")
        return

    if block_type == BLOCK_CLICK_MOUSE:
        button = _clean_button(block.get("button"))
        clicks = _clamp_int(block.get("clicks"), 1, minimum=1, maximum=50)
        await asyncio.to_thread(_click_mouse_now, button, clicks)
        if log:
            log(f"Step: click mouse {button} x{clicks}")
        return

    if block_type == BLOCK_SAVE_MOUSE_POS:
        x, y = await asyncio.to_thread(_get_mouse_pos_now)
        context["saved_mouse_pos"] = (x, y)
        if log:
            log(f"Step: saved mouse position ({x}, {y})")
        return

    if block_type == BLOCK_RESTORE_MOUSE_POS:
        saved = context.get("saved_mouse_pos")
        if isinstance(saved, tuple) and len(saved) == 2:
            x, y = int(saved[0]), int(saved[1])
            await asyncio.to_thread(_move_mouse_now, x, y)
            if log:
                log(f"Step: restored mouse position to ({x}, {y})")
        else:
            if log:
                log("Step: restore mouse position skipped (nothing saved yet)")
        return

    if block_type == BLOCK_TYPE_TEXT:
        text = str(block.get("text") or "")
        keyboard = _keyboard_module()
        await asyncio.to_thread(keyboard.write, text)
        if log:
            log(f'Step: type text "{text}"')
        return

    if block_type == BLOCK_PRESS_KEY:
        key_name = _clean_key(block.get("key"))
        if not key_name:
            return
        keyboard = _keyboard_module()
        await asyncio.to_thread(keyboard.press_and_release, key_name)
        if log:
            log(f"Step: press key {key_name}")
        return

    if block_type == BLOCK_HOLD_KEY:
        key_name = _clean_key(block.get("key"))
        if not key_name:
            return
        keyboard = _keyboard_module()
        await asyncio.to_thread(keyboard.press, key_name)
        if log:
            log(f"Step: hold key {key_name}")
        return

    if block_type == BLOCK_RELEASE_KEY:
        key_name = _clean_key(block.get("key"))
        if not key_name:
            return
        keyboard = _keyboard_module()
        await asyncio.to_thread(keyboard.release, key_name)
        if log:
            log(f"Step: release key {key_name}")
        return

    if block_type == BLOCK_WAIT:
        seconds = _clamp_float(block.get("seconds"), 0.10, minimum=0.0, maximum=600.0)
        if log:
            log(f"Step: wait {seconds:.2f}s")
        await asyncio.sleep(seconds)
        return


async def execute_step_blocks(
    blocks: list[dict[str, Any]],
    *,
    log: Callable[[str], None] | None = None,
) -> None:
    normalized = [normalize_step_block(item) for item in blocks if isinstance(item, dict)]
    total = len(normalized)
    context: dict[str, Any] = {}

    def find_matching_end(start_index: int) -> int:
        depth = 0
        index = start_index
        while index < total:
            block_type = normalized[index]["type"]
            if block_type in SCOPED_BLOCKS:
                depth += 1
            elif block_type == BLOCK_END:
                if depth == 0:
                    return index
                depth -= 1
            index += 1
        return total

    async def run_range(start_index: int, end_index: int) -> None:
        index = start_index
        while index < end_index:
            block = normalized[index]
            block_type = block["type"]

            if block_type == BLOCK_END:
                return

            if block_type == BLOCK_REPEAT:
                body_start = index + 1
                body_end = find_matching_end(body_start)
                times = _clamp_int(block.get("times"), 1, minimum=1, maximum=10_000)
                for _ in range(times):
                    await run_range(body_start, min(body_end, end_index))
                index = body_end + 1 if body_end < total else total
                continue

            if block_type == BLOCK_FOREVER:
                body_start = index + 1
                body_end = find_matching_end(body_start)
                interval = _clamp_float(block.get("interval"), DEFAULT_STEP_LOOP_INTERVAL, minimum=0.0, maximum=10.0)
                while True:
                    await run_range(body_start, min(body_end, end_index))
                    if interval > 0:
                        await asyncio.sleep(interval)
                    else:
                        await asyncio.sleep(0)
                # Unreachable: forever loops are stopped by task cancellation.

            if block_type == BLOCK_IF_PRESSED:
                body_start = index + 1
                body_end = find_matching_end(body_start)
                key_name = _clean_key(block.get("key"))
                if _is_key_pressed(key_name):
                    await run_range(body_start, min(body_end, end_index))
                index = body_end + 1 if body_end < total else total
                continue

            if block_type == BLOCK_IF_MOUSE_PRESSED:
                body_start = index + 1
                body_end = find_matching_end(body_start)
                if _is_mouse_button_pressed(str(block.get("button") or "left")):
                    await run_range(body_start, min(body_end, end_index))
                index = body_end + 1 if body_end < total else total
                continue

            if block_type == BLOCK_IF_ELSE_PRESSED:
                if index + 2 >= end_index:
                    break
                key_name = _clean_key(block.get("key"))
                target = normalized[index + 1] if _is_key_pressed(key_name) else normalized[index + 2]
                await _execute_primitive_block(target, context=context, log=log)
                index += 3
                continue

            if block_type == BLOCK_WHILE_PRESSED:
                body_start = index + 1
                body_end = find_matching_end(body_start)
                key_name = _clean_key(block.get("key"))
                max_loops = _clamp_int(block.get("max_loops"), 0, minimum=0, maximum=100_000)
                interval = _clamp_float(block.get("interval"), DEFAULT_STEP_LOOP_INTERVAL, minimum=0.0, maximum=10.0)
                loops = 0
                while _is_key_pressed(key_name):
                    if max_loops and loops >= max_loops:
                        break
                    await run_range(body_start, min(body_end, end_index))
                    loops += 1
                    if interval > 0:
                        await asyncio.sleep(interval)
                index = body_end + 1 if body_end < total else total
                continue

            if block_type == BLOCK_WHILE_MOUSE_PRESSED:
                body_start = index + 1
                body_end = find_matching_end(body_start)
                button_name = str(block.get("button") or "left")
                max_loops = _clamp_int(block.get("max_loops"), 0, minimum=0, maximum=100_000)
                interval = _clamp_float(block.get("interval"), DEFAULT_STEP_LOOP_INTERVAL, minimum=0.0, maximum=10.0)
                loops = 0
                while _is_mouse_button_pressed(button_name):
                    if max_loops and loops >= max_loops:
                        break
                    await run_range(body_start, min(body_end, end_index))
                    loops += 1
                    if interval > 0:
                        await asyncio.sleep(interval)
                index = body_end + 1 if body_end < total else total
                continue

            await _execute_primitive_block(block, context=context, log=log)
            index += 1

    await run_range(0, total)


async def execute_step_script(
    script_code: str,
    *,
    log: Callable[[str], None] | None = None,
) -> None:
    blocks = parse_step_script(script_code)
    if not blocks:
        return
    await execute_step_blocks(blocks, log=log)
