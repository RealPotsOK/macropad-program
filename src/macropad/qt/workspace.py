from __future__ import annotations

import ast
import contextlib
import copy
import re
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..platform import AppPaths
from ..core.profile import KeyBinding, Profile, create_default_profile, load_profile, save_profile


PROFILE_SLOT_MIN = 1
PROFILE_SLOT_MAX = 10


@dataclass(slots=True)
class QtWorkspaceStore:
    app_paths: AppPaths
    keys: list[tuple[int, int]]
    profile_slot_min: int = PROFILE_SLOT_MIN
    profile_slot_max: int = PROFILE_SLOT_MAX

    @property
    def profile_dir(self) -> Path:
        return self.app_paths.profile_dir

    def profile_path(self, slot: int) -> Path:
        return self.profile_dir / f"profile_{int(slot):02d}.json"

    def runtime_script_path(self, key: tuple[int, int], mode: str) -> Path:
        normalized = mode.strip().lower()
        if normalized == "python":
            return self.profile_dir / "runtime_python" / f"key_{key[0]}_{key[1]}.py"
        if normalized == "ahk":
            return self.profile_dir / "runtime_ahk" / f"key_{key[0]}_{key[1]}.ahk"
        raise ValueError(f"Unsupported runtime script mode: {mode}")

    def workspace_script_path(self, mode: str) -> Path:
        normalized = mode.strip().lower()
        if normalized == "python":
            return self.profile_dir / "runtime_python" / "all_keys.py"
        if normalized == "ahk":
            return self.profile_dir / "runtime_ahk" / "all_keys.ahk"
        raise ValueError(f"Unsupported workspace script mode: {mode}")

    def workspace_comment_prefix(self, mode: str) -> str:
        normalized = mode.strip().lower()
        if normalized == "python":
            return "#"
        if normalized == "ahk":
            return ";"
        raise ValueError(f"Unsupported workspace script mode: {mode}")

    def workspace_begin_marker(self, key: tuple[int, int], mode: str) -> str:
        return f"{self.workspace_comment_prefix(mode)} BEGIN KEY {key[0]},{key[1]}"

    def workspace_end_marker(self, key: tuple[int, int], mode: str) -> str:
        return f"{self.workspace_comment_prefix(mode)} END KEY {key[0]},{key[1]}"

    def default_runtime_script(self, key: tuple[int, int], mode: str) -> str:
        normalized = mode.strip().lower()
        if normalized == "python":
            return (
                f"# Macropad runtime script for key {key[0]},{key[1]}\n"
                "# Runs on key-down.\n"
                "# Available variables: key, row, col, pressed, timestamp\n"
                "if pressed:\n"
                "    pass\n"
            )
        if normalized == "ahk":
            return (
                "#Requires AutoHotkey v2.0\n"
                f"; Macropad runtime script for key {key[0]},{key[1]}\n"
                "; Runs on key-down.\n"
                "; Put your AHK commands below.\n"
            )
        return ""

    def ensure_runtime_script(self, key: tuple[int, int], mode: str) -> Path:
        path = self.runtime_script_path(key, mode)
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(self.default_runtime_script(key, mode), encoding="utf-8")
        return path

    def _ensure_ahk_v2_header(self, content: str) -> str:
        stripped = content.lstrip()
        if stripped.lower().startswith("#requires autohotkey v2.0"):
            return content
        payload = content.lstrip("\ufeff")
        if payload.strip():
            return "#Requires AutoHotkey v2.0\n" + payload
        return "#Requires AutoHotkey v2.0\n"

    def write_runtime_script(self, key: tuple[int, int], mode: str, content: str) -> Path:
        path = self.runtime_script_path(key, mode)
        path.parent.mkdir(parents=True, exist_ok=True)
        normalized = mode.strip().lower()
        if normalized == "ahk":
            content = self._ensure_ahk_v2_header(content)
        path.write_text(content, encoding="utf-8")
        return path

    def _render_workspace_content(self, profile: Profile, mode: str) -> str:
        normalized = mode.strip().lower()
        comment = self.workspace_comment_prefix(normalized)
        lines = [
            f"{comment} Macropad {normalized.upper()} workspace",
            f"{comment} Edit key code blocks below. Keep BEGIN/END markers intact.",
            f"{comment} Python fallback also supports: def key1_action() .. def key12_action().",
            "",
        ]
        for key in self.keys:
            binding = profile.bindings.get(key) or KeyBinding(label=f"Key {key[0]},{key[1]}")
            section = ""
            if binding.script_mode == normalized:
                section = binding.script_code or ""
            if not section.strip():
                section = self.default_runtime_script(key, normalized)
            lines.append(self.workspace_begin_marker(key, normalized))
            lines.extend(section.rstrip("\n").splitlines())
            lines.append(self.workspace_end_marker(key, normalized))
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    def ensure_workspace_script(self, mode: str, profile: Profile) -> Path:
        path = self.workspace_script_path(mode)
        if path.exists():
            return path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self._render_workspace_content(profile, mode), encoding="utf-8")
        return path

    def parse_workspace_sections(self, content: str, mode: str) -> dict[tuple[int, int], str]:
        normalized = mode.strip().lower()
        begin_re = re.compile(r"^\s*[#;]\s*BEGIN KEY\s+(\d+)\s*,\s*(\d+)\s*$", flags=re.IGNORECASE)
        end_re = re.compile(r"^\s*[#;]\s*END KEY\s+(\d+)\s*,\s*(\d+)\s*$", flags=re.IGNORECASE)

        sections: dict[tuple[int, int], str] = {}
        active_key: tuple[int, int] | None = None
        buffer: list[str] = []
        for line in content.splitlines():
            begin_match = begin_re.match(line)
            if begin_match:
                if active_key is not None:
                    sections[active_key] = "\n".join(buffer).rstrip()
                active_key = (int(begin_match.group(1)), int(begin_match.group(2)))
                buffer = []
                continue

            end_match = end_re.match(line)
            if end_match:
                key = (int(end_match.group(1)), int(end_match.group(2)))
                if active_key == key:
                    sections[active_key] = "\n".join(buffer).rstrip()
                    active_key = None
                    buffer = []
                continue

            if active_key is not None:
                buffer.append(line)

        if active_key is not None:
            sections[active_key] = "\n".join(buffer).rstrip()
        if sections or normalized != "python":
            return sections

        with contextlib.suppress(SyntaxError, ValueError):
            module = ast.parse(content)
            lines = content.splitlines()
            import_lines: list[str] = []
            for node in module.body:
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    start = max(0, node.lineno - 1)
                    end = max(start, (node.end_lineno or node.lineno))
                    import_lines.extend(lines[start:end])
            import_block = "\n".join(import_lines).rstrip()

            key_func_re = re.compile(r"^key(\d+)_action$", flags=re.IGNORECASE)
            for node in module.body:
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                match = key_func_re.match(node.name)
                if not match:
                    continue
                index = int(match.group(1))
                if index < 1 or index > len(self.keys):
                    continue
                key = self.keys[index - 1]
                if node.body:
                    body_start = node.body[0].lineno
                    body_end = node.end_lineno or body_start
                    body_source = "\n".join(lines[body_start - 1 : body_end])
                    body = textwrap.dedent(body_source).rstrip()
                else:
                    body = "pass"

                merged_parts: list[str] = []
                if import_block:
                    merged_parts.append(import_block)
                if body:
                    merged_parts.append(body)
                sections[key] = "\n\n".join(merged_parts).rstrip()
        return sections

    def upsert_workspace_section(self, mode: str, key: tuple[int, int], content: str, *, profile: Profile) -> Path:
        path = self.ensure_workspace_script(mode, profile)
        existing = ""
        with contextlib.suppress(Exception):
            existing = path.read_text(encoding="utf-8")
        if not existing:
            existing = self._render_workspace_content(profile, mode)

        lines = existing.splitlines()
        begin_marker = self.workspace_begin_marker(key, mode).strip()
        end_marker = self.workspace_end_marker(key, mode).strip()
        begin_index = -1
        end_index = -1
        for index, line in enumerate(lines):
            if line.strip().lower() == begin_marker.lower():
                begin_index = index
                continue
            if begin_index >= 0 and line.strip().lower() == end_marker.lower():
                end_index = index
                break

        content_lines = content.rstrip("\n").splitlines()
        if begin_index >= 0 and end_index > begin_index:
            updated = lines[: begin_index + 1] + content_lines + lines[end_index:]
        else:
            updated = list(lines)
            if updated and updated[-1].strip():
                updated.append("")
            updated.append(begin_marker)
            updated.extend(content_lines)
            updated.append(end_marker)
        path.write_text("\n".join(updated).rstrip() + "\n", encoding="utf-8")
        return path

    def sync_profile_from_workspace(self, profile: Profile, mode: str, *, force: bool = False) -> int:
        path = self.workspace_script_path(mode)
        if not path.exists():
            return 0
        content = path.read_text(encoding="utf-8")
        sections = self.parse_workspace_sections(content, mode)
        if not sections:
            return 0

        changed = 0
        valid_keys = set(self.keys)
        for key, section in sections.items():
            if key not in valid_keys:
                continue
            binding = profile.bindings.setdefault(key, KeyBinding(label=f"Key {key[0]},{key[1]}"))
            cleaned = section.rstrip()
            if binding.script_code != cleaned:
                binding.script_code = cleaned
                changed += 1
            if cleaned.strip():
                binding.script_mode = mode.strip().lower()
        return changed

    def load_profile(self, slot: int, *, name: str | None = None) -> Profile:
        slot = max(self.profile_slot_min, min(self.profile_slot_max, int(slot)))
        fallback = name or f"Profile {slot}"
        path = self.profile_path(slot)
        if not path.exists():
            return create_default_profile(fallback, keys=self.keys)
        return load_profile(path, name=fallback, keys=self.keys)

    def save_profile(self, slot: int, profile: Profile) -> None:
        save_profile(self.profile_path(slot), profile)

    def profile_slots(self) -> list[int]:
        return list(range(self.profile_slot_min, self.profile_slot_max + 1))

    def profile_names_from_state(self, profile_names: dict[str, str]) -> dict[int, str]:
        names: dict[int, str] = {}
        for slot in self.profile_slots():
            names[slot] = str(profile_names.get(str(slot)) or f"Profile {slot}")
        return names
