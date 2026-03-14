from __future__ import annotations

from .shared import *

class WorkspaceMixin:
    def _runtime_script_path(self, key: tuple[int, int], mode: str) -> Path:
        normalized = mode.strip().lower()
        if normalized == "python":
            return self.profile_dir / "runtime_python" / f"key_{key[0]}_{key[1]}.py"
        if normalized == "ahk":
            return self.profile_dir / "runtime_ahk" / f"key_{key[0]}_{key[1]}.ahk"
        raise ValueError(f"Unsupported runtime script mode: {mode}")


    def _workspace_script_path(self, mode: str) -> Path:
        normalized = mode.strip().lower()
        if normalized == "python":
            return self.profile_dir / "runtime_python" / "all_keys.py"
        if normalized == "ahk":
            return self.profile_dir / "runtime_ahk" / "all_keys.ahk"
        raise ValueError(f"Unsupported workspace mode: {mode}")


    def _workspace_comment_prefix(self, mode: str) -> str:
        normalized = mode.strip().lower()
        if normalized == "python":
            return "#"
        if normalized == "ahk":
            return ";"
        raise ValueError(f"Unsupported workspace mode: {mode}")


    def _workspace_begin_marker(self, key: tuple[int, int], mode: str) -> str:
        return f"{self._workspace_comment_prefix(mode)} BEGIN KEY {key[0]},{key[1]}"


    def _workspace_end_marker(self, key: tuple[int, int], mode: str) -> str:
        return f"{self._workspace_comment_prefix(mode)} END KEY {key[0]},{key[1]}"


    def _default_runtime_script(self, key: tuple[int, int], mode: str) -> str:
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


    def _ensure_ahk_v2_header(self, content: str) -> str:
        stripped = content.lstrip()
        if stripped.lower().startswith("#requires autohotkey v2.0"):
            return content
        payload = content.lstrip("\ufeff")
        if payload.strip():
            return "#Requires AutoHotkey v2.0\n" + payload
        return "#Requires AutoHotkey v2.0\n"


    def _write_runtime_script(self, key: tuple[int, int], mode: str, content: str) -> Path:
        path = self._runtime_script_path(key, mode)
        path.parent.mkdir(parents=True, exist_ok=True)
        normalized = mode.strip().lower()
        if normalized == "ahk":
            content = self._ensure_ahk_v2_header(content)
        path.write_text(content, encoding="utf-8")
        return path


    def _render_workspace_content(self, mode: str) -> str:
        normalized = mode.strip().lower()
        comment = self._workspace_comment_prefix(normalized)
        lines = [
            f"{comment} Macropad {normalized.upper()} workspace",
            f"{comment} Edit key code blocks below. Keep BEGIN/END markers intact.",
            f"{comment} Python fallback also supports: def key1_action() .. def key12_action().",
            "",
        ]
        for key in self.keys:
            binding = self._binding_for(key)
            section = ""
            if binding.script_mode == normalized:
                section = binding.script_code or ""
            if not section.strip():
                section = self._default_runtime_script(key, normalized)
            lines.append(self._workspace_begin_marker(key, normalized))
            lines.extend(section.rstrip("\n").splitlines())
            lines.append(self._workspace_end_marker(key, normalized))
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"


    def _ensure_workspace_script(self, mode: str) -> Path:
        path = self._workspace_script_path(mode)
        if path.exists():
            return path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self._render_workspace_content(mode), encoding="utf-8")
        with suppress(Exception):
            self._workspace_mtime[mode] = path.stat().st_mtime
        return path


    def _parse_workspace_sections(self, content: str, mode: str) -> dict[tuple[int, int], str]:
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
        if sections:
            return sections

        if normalized != "python":
            return sections

        with suppress(SyntaxError, ValueError):
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


    def _upsert_workspace_section(self, mode: str, key: tuple[int, int], content: str) -> None:
        normalized = mode.strip().lower()
        path = self._ensure_workspace_script(normalized)
        existing = ""
        with suppress(Exception):
            existing = path.read_text(encoding="utf-8")
        if not existing:
            existing = self._render_workspace_content(normalized)

        lines = existing.splitlines()
        begin_marker = self._workspace_begin_marker(key, normalized).strip()
        end_marker = self._workspace_end_marker(key, normalized).strip()
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
        with suppress(Exception):
            self._workspace_mtime[normalized] = path.stat().st_mtime


    def _sync_scripts_from_workspace(self, mode: str, *, force: bool = False, persist: bool = True) -> int:
        normalized = mode.strip().lower()
        if normalized not in {"python", "ahk"}:
            return 0
        path = self._workspace_script_path(normalized)
        if not path.exists():
            return 0

        stat = path.stat()
        cached_mtime = self._workspace_mtime.get(normalized)
        if not force and cached_mtime is not None and stat.st_mtime == cached_mtime:
            return 0

        content = path.read_text(encoding="utf-8")
        sections = self._parse_workspace_sections(content, normalized)
        if not sections:
            self._workspace_mtime[normalized] = stat.st_mtime
            return 0

        changed = 0
        valid_keys = set(self.keys)
        for key, section in sections.items():
            if key not in valid_keys:
                continue
            binding = self._binding_for(key)
            cleaned = section.rstrip()
            if binding.script_code != cleaned:
                binding.script_code = cleaned
                changed += 1
            if cleaned.strip():
                binding.script_mode = normalized

        self._workspace_mtime[normalized] = stat.st_mtime
        if changed:
            if normalized == "python":
                self._script_cache.clear()
                self._script_cache_source.clear()
                self._rebuild_script_cache()
            if self.selected_key in valid_keys:
                selected_binding = self._binding_for(self.selected_key)
                if self._script_editor is not None and selected_binding.script_mode == normalized:
                    self._script_editor.delete("1.0", "end")
                    self._script_editor.insert("1.0", selected_binding.script_code or "")
            self._apply_profile_to_tiles()
            if persist:
                self._save_profile_slot()
        return changed
    def _linked_python_action_path(self, binding: KeyBinding) -> Path | None:
        kind = (binding.action.kind or "").strip().lower()
        value = (binding.action.value or "").strip()
        if kind != ACTION_PYTHON:
            return None
        if not value or value == INLINE_PYTHON_ACTION_VALUE:
            return None
        from ..actions import resolve_action_path

        return resolve_action_path(value)


    def _script_text_for_editor(self, key: tuple[int, int], binding: KeyBinding) -> tuple[str, bool, str]:
        mode = (binding.script_mode or "python").strip().lower()

        if mode == "step":
            return binding.script_code or "", False, "Step mode: visual block chain editor."

        if mode == "python":
            linked_path = self._linked_python_action_path(binding)
            if linked_path is not None:
                if linked_path.exists():
                    try:
                        linked_text = linked_path.read_text(encoding="utf-8")
                    except Exception as exc:
                        return (
                            f"# Failed to read linked Python file:\n# {linked_path}\n# {exc}\n",
                            True,
                            f"Linked Python file read failed: {linked_path}",
                        )
                    header = f"# Linked Python action file (read-only)\n# {linked_path}\n\n"
                    return header + linked_text, True, f"Linked Python file: {linked_path}"
                return (
                    f"# Linked Python action file not found:\n# {linked_path}\n",
                    True,
                    f"Linked Python file missing: {linked_path}",
                )

        if mode not in {"python", "ahk"}:
            return binding.script_code or "", False, ""

        self._sync_scripts_from_workspace(mode, persist=False)
        return binding.script_code or "", False, ""


    def _open_path_with_default_app(self, path: Path) -> None:
        if os.name == "nt":
            os.startfile(str(path))  # type: ignore[attr-defined]
            return
        if sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
            return
        subprocess.Popen(["xdg-open", str(path)])


    def _sync_script_list_selection(self, key: tuple[int, int]) -> None:
        if self._script_key_list is None:
            return
        token = f"{key[0]},{key[1]}"
        entries = self._script_key_list.get(0, "end")
        for index, value in enumerate(entries):
            if value == token:
                self._script_key_list.selection_clear(0, "end")
                self._script_key_list.selection_set(index)
                self._script_key_list.see(index)
                break





