from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Iterable


def slot_label(slot: int, name: str) -> str:
    label = str(name or "").strip() or f"Profile {int(slot)}"
    return f"{int(slot)}: {label}"


def open_path_with_default_app(path: Path) -> None:
    if os.name == "nt":
        os.startfile(str(path))  # type: ignore[attr-defined]
        return
    if sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
        return
    subprocess.Popen(["xdg-open", str(path)])


def store_path_text(path: Path, *, roots: Iterable[Path]) -> str:
    resolved = path.expanduser()
    if not resolved.is_absolute():
        resolved = (Path.cwd() / resolved).resolve()
    else:
        resolved = resolved.resolve()

    for root in roots:
        try:
            return str(resolved.relative_to(root.resolve()))
        except Exception:
            continue
    return str(resolved)

