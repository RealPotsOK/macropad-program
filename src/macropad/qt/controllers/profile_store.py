from __future__ import annotations

import ast
import copy
import logging
import os
import re
import subprocess
import sys
import textwrap
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ...config import DEFAULT_SETTINGS, Settings
from ...platform import migrate_legacy_app_data, resolve_app_paths, sync_packaged_runtime_assets
from ...core.actions import (
    ACTION_FILE,
    ACTION_NONE,
    ACTION_PYTHON,
    normalize_profile_action_kind_value,
    resolve_action_path,
)
from ...core.app_state import AppState, load_app_state, save_app_state
from ...core.key_layout import (
    DEFAULT_KEY_COLS,
    DEFAULT_KEY_ROWS,
    build_virtual_keys,
    key_from_text,
    key_to_text,
    normalize_key_dimensions,
)
from ...core.oled_text import (
    DESCRIPTION_PRESET_CUSTOM,
    description_template_for_label,
    infer_description_preset_label,
)
from ...core.profile import KeyAction, KeyBinding, Profile, create_default_profile, load_profile, save_profile
from ..constants import INLINE_PYTHON_ACTION_VALUE

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class ScriptEditorState:
    mode: str
    text: str
    read_only: bool = False
    hint: str = ""
    linked_path: Path | None = None


class ProfileStore:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

        self.app_paths = resolve_app_paths()
        self.legacy_data_migrated = migrate_legacy_app_data(self.app_paths)
        self.runtime_assets_synced = sync_packaged_runtime_assets(self.app_paths)
        self.data_root = self.app_paths.data_root
        self.profile_dir = self.app_paths.profile_dir
        self.state_path = self.app_paths.state_path

        self.app_state = load_app_state(self.state_path)
        self.key_rows, self.key_cols = normalize_key_dimensions(
            int(self.app_state.key_rows or DEFAULT_KEY_ROWS),
            int(self.app_state.key_cols or DEFAULT_KEY_COLS),
        )
        self.keys = build_virtual_keys(self.key_rows, self.key_cols)
        if not self.keys:
            raise RuntimeError("Virtual key layout is empty.")
        self.profile_names = {
            slot: self.app_state.profile_names.get(str(slot), f"Profile {slot}") for slot in range(1, 11)
        }
        self.profile_slot = max(1, min(10, self.app_state.selected_profile_slot))
        self.profile = create_default_profile(self.profile_names[self.profile_slot], keys=self.keys)
        self.selected_key = self.keys[0]
        self._script_cache: dict[tuple[int, int], Any] = {}
        self._script_cache_source: dict[tuple[int, int], str] = {}
        self._workspace_mtime: dict[str, float] = {}

        self.load_profile_slot(self.profile_slot)


    def _normalize_mapping(self, mapping: dict[tuple[int, int], tuple[int, int]]) -> dict[str, str]:
        allowed_targets = set(self.keys)
        normalized: dict[str, str] = {}
        for board_key, virtual_key in mapping.items():
            if virtual_key not in allowed_targets:
                continue
            normalized[key_to_text(board_key)] = key_to_text(virtual_key)
        return normalized

    def key_mapping(self) -> dict[tuple[int, int], tuple[int, int]]:
        mapping: dict[tuple[int, int], tuple[int, int]] = {}
        raw = self.app_state.key_mapping
        if not isinstance(raw, dict):
            return mapping
        for board_text, virtual_text in raw.items():
            board = key_from_text(str(board_text))
            virtual = key_from_text(str(virtual_text))
            if board is None or virtual is None:
                continue
            if virtual not in self.keys:
                continue
            mapping[board] = virtual
        return mapping

    def set_key_mapping(self, mapping: dict[tuple[int, int], tuple[int, int]]) -> None:
        self.app_state.key_mapping = self._normalize_mapping(mapping)

    def set_virtual_layout(self, *, rows: int, cols: int) -> None:
        self.key_rows, self.key_cols = normalize_key_dimensions(rows, cols)
        self.app_state.key_rows = self.key_rows
        self.app_state.key_cols = self.key_cols
        self.keys = build_virtual_keys(self.key_rows, self.key_cols)
        if self.selected_key not in self.keys:
            self.selected_key = self.keys[0]
        self.app_state.key_mapping = self._normalize_mapping(self.key_mapping())
        self.load_profile_slot(self.profile_slot)

    def save_app_state(
        self,
        *,
        last_port: str,
        last_hint: str = "",
        last_baud: int,
        last_zoom: str,
        auto_connect: bool,
        audio_output_device: str = "",
    ) -> None:
        self.app_state.last_port = last_port
        self.app_state.last_hint = str(last_hint or "").strip()
        self.app_state.last_baud = int(last_baud or DEFAULT_SETTINGS.baud)
        self.app_state.last_zoom = (last_zoom or "100%").strip()
        self.app_state.auto_connect = bool(auto_connect)
        self.app_state.audio_output_device = str(audio_output_device or "").strip()
        self.app_state.selected_profile_slot = self.profile_slot
        self.app_state.profile_names = {str(slot): name for slot, name in self.profile_names.items()}
        save_app_state(self.state_path, self.app_state)

    def remember_dialog_path(self, raw_value: str | Path) -> None:
        candidate = Path(raw_value).expanduser()
        directory = candidate if candidate.is_dir() else candidate.parent
        if not directory.exists():
            return
        self.app_state.last_dialog_directory = str(directory.resolve())
        save_app_state(self.state_path, self.app_state)

    def resolve_dialog_directory(self, raw_value: str = "") -> Path:
        candidates: list[Path] = []
        text = str(raw_value or "").strip()
        if text:
            candidate = Path(text).expanduser()
            if candidate.exists():
                candidates.append(candidate if candidate.is_dir() else candidate.parent)
            elif candidate.parent.exists():
                candidates.append(candidate.parent)

        remembered = str(self.app_state.last_dialog_directory or "").strip()
        if remembered:
            remembered_path = Path(remembered).expanduser()
            if remembered_path.exists():
                candidates.append(remembered_path)

        candidates.extend([self.profile_dir, self.data_root, Path.cwd()])
        for candidate in candidates:
            if candidate.exists():
                return candidate.resolve()
        return Path.cwd()

    def profile_path(self, slot: int) -> Path:
        return self.profile_dir / f"profile_{slot:02d}.json"

    def load_profile_slot(self, slot: int) -> Profile:
        bounded = max(1, min(10, slot))
        name = self.profile_names[bounded]
        self.profile = load_profile(self.profile_path(bounded), name=name, keys=self.keys)
        self.profile.name = name
        self.profile_slot = bounded
        migrated = self._migrate_loaded_profile_actions()
        self.ensure_workspace_script("python")
        self.ensure_workspace_script("ahk")
        self.rebuild_python_cache()
        if migrated:
            self.save_profile_slot()
        return self.profile

    def _migrate_loaded_profile_actions(self) -> bool:
        changed = False
        for key in self.keys:
            binding = self.binding_for(key)
            if self.normalize_action_for_ui(binding.action):
                changed = True
            if self._migrate_legacy_inline_script_for_key(key, binding):
                changed = True
        for action in (
            self.profile.enc_up_action,
            self.profile.enc_down_action,
            self.profile.enc_sw_down_action,
            self.profile.enc_sw_up_action,
        ):
            if self.normalize_action_for_ui(action):
                changed = True
        return changed

    def save_profile_slot(self) -> None:
        self.profile.name = self.profile_names[self.profile_slot]
        save_profile(self.profile_path(self.profile_slot), self.profile)

    def rename_current_profile(self, name: str) -> None:
        text = str(name or "").strip()
        if not text:
            return
        self.profile_names[self.profile_slot] = text
        self.profile.name = text

    def set_profile_description(self, description: str) -> None:
        self.profile.description = str(description or "").strip()

    def set_description_preset(self, label: str) -> str:
        current = self.profile.description or ""
        value = description_template_for_label(label, current_value=current)
        self.profile.description = value
        return value

    def description_preset_label(self) -> str:
        return infer_description_preset_label(self.profile.description or "") or DESCRIPTION_PRESET_CUSTOM

    def binding_for(self, key: tuple[int, int]) -> KeyBinding:
        binding = self.profile.bindings.get(key)
        if binding is None:
            binding = KeyBinding(label=f"Key {key[0]},{key[1]}")
            self.profile.bindings[key] = binding
        self.normalize_action_for_ui(binding.action)
        return binding

    def normalize_action_for_ui(self, action: KeyAction) -> bool:
        old_kind = str(action.kind or "")
        old_value = str(action.value or "")
        old_steps = list(action.steps)
        kind, value = normalize_profile_action_kind_value(action.kind, action.value)
        action.kind = kind
        action.value = value
        if kind == ACTION_NONE:
            action.steps = []
        changed = (old_kind != action.kind) or (old_value != action.value) or (old_steps != action.steps)
        if changed and old_kind.strip().lower() != action.kind:
            LOGGER.info("Migrated legacy action kind '%s' -> '%s'.", old_kind, action.kind)
        return changed

    def _migrate_legacy_inline_script_for_key(self, key: tuple[int, int], binding: KeyBinding) -> bool:
        mode = (binding.script_mode or "").strip().lower()
        source = (binding.script_code or "").strip()
        if mode == "step" or not source:
            return False
        if mode not in {"python", "ahk", "file"}:
            return False

        action_kind = (binding.action.kind or "").strip().lower()
        if action_kind in {"", ACTION_NONE}:
            if mode in {"python", "ahk"}:
                runtime_path = self.runtime_script_path(key, mode)
                try:
                    runtime_path.parent.mkdir(parents=True, exist_ok=True)
                    runtime_path.write_text(source.rstrip() + "\n", encoding="utf-8")
                except Exception as exc:
                    LOGGER.warning(
                        "Could not migrate inline %s script for key %s,%s to runtime file: %s",
                        mode,
                        key[0],
                        key[1],
                        exc,
                    )
                    return False
                binding.action = KeyAction(kind=ACTION_FILE, value=str(runtime_path))
            elif mode == "file":
                binding.action = KeyAction(kind=ACTION_FILE, value=source)

        binding.script_mode = "step"
        binding.script_code = ""
        self._script_cache.pop(key, None)
        self._script_cache_source.pop(key, None)
        LOGGER.info("Migrated legacy inline %s script for key %s,%s.", mode, key[0], key[1])
        return True

    def set_selected_key(self, key: tuple[int, int]) -> None:
        if key in self.keys:
            self.selected_key = key

    def selected_binding(self) -> KeyBinding:
        return self.binding_for(self.selected_key)

    def display_action_for_binding(self, binding: KeyBinding) -> tuple[str, str]:
        kind = (binding.action.kind or ACTION_NONE).strip().lower() or ACTION_NONE
        value = binding.action.value or ""
        return kind, value

    def update_binding_action(self, key: tuple[int, int], *, label: str, kind: str, value: str) -> KeyBinding:
        binding = self.binding_for(key)
        requested_kind = kind.strip().lower() or ACTION_NONE
        requested_value = value.strip()
        normalized_kind, normalized_value = normalize_profile_action_kind_value(requested_kind, requested_value)
        binding.label = label.strip() or f"Key {key[0]},{key[1]}"
        binding.action = KeyAction(kind=normalized_kind, value=normalized_value, steps=binding.action.steps)
        return binding

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
        raise ValueError(f"Unsupported workspace mode: {mode}")

    def _comment_prefix(self, mode: str) -> str:
        return "#" if mode.strip().lower() == "python" else ";"

    def _begin_marker(self, key: tuple[int, int], mode: str) -> str:
        return f"{self._comment_prefix(mode)} BEGIN KEY {key[0]},{key[1]}"

    def _end_marker(self, key: tuple[int, int], mode: str) -> str:
        return f"{self._comment_prefix(mode)} END KEY {key[0]},{key[1]}"

    def _default_runtime_script(self, key: tuple[int, int], mode: str) -> str:
        if mode == "python":
            return (
                f"# Macropad runtime script for key {key[0]},{key[1]}\n"
                "# Runs on key-down.\n"
                "# Available variables: key, row, col, pressed, timestamp\n"
                "if pressed:\n"
                "    pass\n"
            )
        return (
            "#Requires AutoHotkey v2.0\n"
            f"; Macropad runtime script for key {key[0]},{key[1]}\n"
            "; Runs on key-down.\n"
            "; Put your AHK commands below.\n"
        )

    def render_workspace_content(self, mode: str) -> str:
        normalized = mode.strip().lower()
        comment = self._comment_prefix(normalized)
        lines = [
            f"{comment} Macropad {normalized.upper()} workspace",
            f"{comment} Edit key code blocks below. Keep BEGIN/END markers intact.",
            f"{comment} Python fallback also supports: def key1_action() .. def key12_action().",
            "",
        ]
        for key in self.keys:
            binding = self.binding_for(key)
            section = binding.script_code if binding.script_mode == normalized else ""
            if not section.strip():
                section = self._default_runtime_script(key, normalized)
            lines.append(self._begin_marker(key, normalized))
            lines.extend(section.rstrip("\n").splitlines())
            lines.append(self._end_marker(key, normalized))
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    def ensure_workspace_script(self, mode: str) -> Path:
        path = self.workspace_script_path(mode)
        if path.exists():
            return path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.render_workspace_content(mode), encoding="utf-8")
        with suppress(OSError):
            self._workspace_mtime[mode] = path.stat().st_mtime
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
                    sections[key] = "\n".join(buffer).rstrip()
                    active_key = None
                    buffer = []
                continue
            if active_key is not None:
                buffer.append(line)

        if active_key is not None:
            sections[active_key] = "\n".join(buffer).rstrip()
        if sections or normalized != "python":
            return sections

        with suppress(SyntaxError, ValueError):
            module = ast.parse(content)
            lines = content.splitlines()
            imports: list[str] = []
            for node in module.body:
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    start = max(0, node.lineno - 1)
                    end = max(start, node.end_lineno or node.lineno)
                    imports.extend(lines[start:end])
            import_block = "\n".join(imports).rstrip()
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
                    body_source = "\n".join(lines[node.body[0].lineno - 1 : (node.end_lineno or node.body[0].lineno)])
                    body = textwrap.dedent(body_source).rstrip()
                else:
                    body = "pass"
                merged = "\n\n".join(part for part in [import_block, body] if part).rstrip()
                sections[key] = merged
        return sections

    def upsert_workspace_section(self, mode: str, key: tuple[int, int], content: str) -> None:
        normalized = mode.strip().lower()
        path = self.ensure_workspace_script(normalized)
        existing = path.read_text(encoding="utf-8") if path.exists() else self.render_workspace_content(normalized)
        lines = existing.splitlines()
        begin_marker = self._begin_marker(key, normalized).strip().lower()
        end_marker = self._end_marker(key, normalized).strip().lower()
        begin_index = -1
        end_index = -1
        for index, line in enumerate(lines):
            lowered = line.strip().lower()
            if lowered == begin_marker:
                begin_index = index
                continue
            if begin_index >= 0 and lowered == end_marker:
                end_index = index
                break
        content_lines = content.rstrip("\n").splitlines()
        if begin_index >= 0 and end_index > begin_index:
            updated = lines[: begin_index + 1] + content_lines + lines[end_index:]
        else:
            updated = list(lines)
            if updated and updated[-1].strip():
                updated.append("")
            updated.extend([self._begin_marker(key, normalized), *content_lines, self._end_marker(key, normalized)])
        path.write_text("\n".join(updated).rstrip() + "\n", encoding="utf-8")
        with suppress(OSError):
            self._workspace_mtime[normalized] = path.stat().st_mtime

    def sync_scripts_from_workspace(self, mode: str, *, force: bool = False, persist: bool = True) -> int:
        normalized = mode.strip().lower()
        if normalized not in {"python", "ahk"}:
            return 0
        path = self.workspace_script_path(normalized)
        if not path.exists():
            return 0
        stat = path.stat()
        if not force and self._workspace_mtime.get(normalized) == stat.st_mtime:
            return 0
        sections = self.parse_workspace_sections(path.read_text(encoding="utf-8"), normalized)
        if not sections:
            self._workspace_mtime[normalized] = stat.st_mtime
            return 0
        changed = 0
        valid_keys = set(self.keys)
        for key, section in sections.items():
            if key not in valid_keys:
                continue
            binding = self.binding_for(key)
            cleaned = section.rstrip()
            if binding.script_code != cleaned:
                binding.script_code = cleaned
                changed += 1
            if cleaned.strip():
                binding.script_mode = normalized
        self._workspace_mtime[normalized] = stat.st_mtime
        if changed and normalized == "python":
            self.rebuild_python_cache()
        if changed and persist:
            self.save_profile_slot()
        return changed

    def linked_python_action_path(self, binding: KeyBinding) -> Path | None:
        kind = (binding.action.kind or "").strip().lower()
        value = (binding.action.value or "").strip()
        if kind != ACTION_PYTHON or not value or value == INLINE_PYTHON_ACTION_VALUE:
            return None
        return resolve_action_path(value)

    def script_editor_state(self, key: tuple[int, int], mode: str) -> ScriptEditorState:
        binding = self.binding_for(key)
        normalized = (mode or binding.script_mode or "python").strip().lower()
        if normalized == "step":
            return ScriptEditorState(mode="step", text=binding.script_code or "", hint="Step mode.")
        if normalized == "python":
            linked_path = self.linked_python_action_path(binding)
            if linked_path is not None:
                if linked_path.exists():
                    text = linked_path.read_text(encoding="utf-8")
                    hint = f"Linked Python file: {linked_path}"
                    header = f"# Linked Python action file (read-only)\n# {linked_path}\n\n"
                    return ScriptEditorState(
                        mode="python",
                        text=header + text,
                        read_only=True,
                        hint=hint,
                        linked_path=linked_path,
                    )
                return ScriptEditorState(
                    mode="python",
                    text=f"# Linked Python action file not found:\n# {linked_path}\n",
                    read_only=True,
                    hint=f"Linked Python file missing: {linked_path}",
                    linked_path=linked_path,
                )
        if normalized in {"python", "ahk"}:
            self.sync_scripts_from_workspace(normalized, persist=False)
        return ScriptEditorState(mode=normalized, text=binding.script_code or "")

    def save_script_for_key(self, key: tuple[int, int], mode: str, content: str) -> None:
        binding = self.binding_for(key)
        binding.script_mode = mode
        binding.script_code = content
        if mode in {"python", "ahk"}:
            self.upsert_workspace_section(mode, key, content)
            self.sync_scripts_from_workspace(mode, force=True, persist=False)
        if mode == "python":
            self.rebuild_python_cache()
        self.save_profile_slot()

    def clear_script_for_key(self, key: tuple[int, int], mode: str) -> None:
        binding = self.binding_for(key)
        binding.script_mode = mode
        binding.script_code = ""
        self._script_cache.pop(key, None)
        self._script_cache_source.pop(key, None)
        if mode in {"python", "ahk"}:
            self.upsert_workspace_section(mode, key, "")
            self.sync_scripts_from_workspace(mode, force=True, persist=False)
        self.save_profile_slot()

    def python_code_for_key(self, key: tuple[int, int]) -> Any | None:
        return self._script_cache.get(key)

    def python_source_for_key(self, key: tuple[int, int]) -> str:
        return self._script_cache_source.get(key, "")

    def rebuild_python_cache(self) -> None:
        self.sync_scripts_from_workspace("python", persist=False)
        self._script_cache.clear()
        self._script_cache_source.clear()
        for key in self.keys:
            binding = self.binding_for(key)
            if binding.script_mode != "python" or not binding.script_code.strip():
                continue
            source = binding.script_code
            with suppress(Exception):
                self._script_cache[key] = compile(source, str(self.runtime_script_path(key, "python")), "exec")
                self._script_cache_source[key] = source

    def open_path_with_default_app(self, path: Path) -> None:
        if os.name == "nt":
            os.startfile(str(path))  # type: ignore[attr-defined]
            return
        if sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
            return
        subprocess.Popen(["xdg-open", str(path)])

    def copy_selected_key_to_slots(self, slots: list[int]) -> tuple[list[int], list[tuple[int, str]]]:
        copied: list[int] = []
        failed: list[tuple[int, str]] = []
        source_binding = copy.deepcopy(self.binding_for(self.selected_key))
        for slot in slots:
            try:
                target_name = self.profile_names[slot]
                target = load_profile(self.profile_path(slot), name=target_name, keys=self.keys)
                target.name = target_name
                target.bindings[self.selected_key] = copy.deepcopy(source_binding)
                save_profile(self.profile_path(slot), target)
                copied.append(slot)
            except Exception as exc:
                failed.append((slot, str(exc)))
        return copied, failed

    def copy_entire_profile_to_slots(self, slots: list[int]) -> tuple[list[int], list[tuple[int, str]]]:
        copied: list[int] = []
        failed: list[tuple[int, str]] = []
        source = copy.deepcopy(self.profile)
        for slot in slots:
            try:
                target = copy.deepcopy(source)
                target.name = self.profile_names[slot]
                save_profile(self.profile_path(slot), target)
                copied.append(slot)
            except Exception as exc:
                failed.append((slot, str(exc)))
        return copied, failed

    def import_profile(self, path: Path) -> None:
        imported = load_profile(path, name=self.profile_names[self.profile_slot], keys=self.keys)
        imported.name = self.profile_names[self.profile_slot]
        self.profile = imported
        self.rebuild_python_cache()
        self.save_profile_slot()

    def export_profile(self, path: Path) -> None:
        save_profile(path, self.profile)

    def normalize_action_choice(self, kind: str, value: str) -> tuple[str, str]:
        normalized_kind = (kind or ACTION_NONE).strip().lower()
        normalized_value = value or ""
        return normalize_profile_action_kind_value(normalized_kind, normalized_value)
