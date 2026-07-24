"""Agent file format utilities.

Provides functions to parse, validate, and convert YAML frontmatter in
.agent.md files. The main concern is converting the ``tools`` field from
array format (``tools: [execute, read]``) to object format
(``tools:\n  execute: true\n  read: true``) which is what OpenCode expects.

This module was extracted from ``agent.py`` to avoid circular imports and to
centralise all format-related logic in one place.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml


def parse_frontmatter(path: Path) -> dict:
    """Parse YAML frontmatter from a file.

    Reads the file, extracts the YAML block between the leading ``---``
    delimiters and returns it as a dictionary.  Returns an empty dict when
    no frontmatter is found or the YAML is not a mapping.
    """
    content = path.read_text(encoding="utf-8")
    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if match:
        data = yaml.safe_load(match.group(1))
        return data if isinstance(data, dict) else {}
    return {}


# ---------------------------------------------------------------------------
# tools  field conversion
# ---------------------------------------------------------------------------

def convert_tools_to_object(tools_value: Any) -> tuple[dict[str, bool], bool]:
    """Convert a raw YAML ``tools`` value to object format.

    Returns a ``(converted_dict, was_modified)`` pair so callers can decide
    whether to warn the user or write the file back.

    ================== ====================================================
    Input              Output
    ================== ====================================================
    ``["a", "b"]``     ``({"a": True, "b": True}, True)``
    ``{"a": True}``    ``({"a": True}, False)``
    ``None`` / missing ``({}, False)``
    other types        ``({}, False)``
    ================== ====================================================
    """
    if isinstance(tools_value, list):
        return {item: True for item in tools_value if isinstance(item, str)}, True
    if isinstance(tools_value, dict):
        return tools_value, False
    return {}, False


def _convert_tools_in_frontmatter(frontmatter_text: str) -> tuple[str, bool]:
    """Replace ``tools: [...]`` lines with object-format blocks.

    Operates on the *raw YAML text* (the content between ``---`` markers)
    using a regular expression so that comments and overall layout are
    preserved.  Lines that already use object syntax or that contain ``#``
    (potential inline comments) are left untouched.

    Returns ``(modified_text, was_modified)``.
    """
    # Match lines like:  tools: [execute, read]  or  tools: [execute, read]  # comment
    # Capture group 1 = leading whitespace (indentation)
    # Capture group 2 = content inside the brackets
    pattern = re.compile(
        r'^(\s*)tools:\s*\[(.*?)\]\s*(?:#.*)?$',
        re.MULTILINE,
    )

    def _replace(m: re.Match) -> str:
        indent = m.group(1)
        items_str = m.group(2).strip()
        if not items_str:
            return f"{indent}tools: {{}}"
        # Split by comma, strip quotes and whitespace
        items = []
        for raw in items_str.split(","):
            item = raw.strip().strip("\"'").strip()
            if item:
                items.append(item)
        if not items:
            return f"{indent}tools: {{}}"
        lines = [f"{indent}tools:"]
        for item in items:
            lines.append(f"{indent}  {item}: true")
        return "\n".join(lines)

    new_text, count = pattern.subn(_replace, frontmatter_text)
    return new_text, count > 0


# ---------------------------------------------------------------------------
# File-level operations
# ---------------------------------------------------------------------------

def convert_agent_file(path: Path) -> bool:
    """Read an ``.agent.md`` file, convert its ``tools`` field, and write
    back if the content changed.

    Returns ``True`` if the file was modified, ``False`` otherwise.
    Skips non-``.agent.md`` files silently (returns ``False``).
    """
    if not str(path).endswith(".agent.md"):
        return False

    original = path.read_text(encoding="utf-8")
    match = re.match(r"^(---\s*\n.*?\n---)", original, re.DOTALL)
    if not match:
        return False  # no frontmatter → nothing to convert

    frontmatter_block = match.group(1)
    inner = re.match(r"^---\s*\n(.*?)\n---", frontmatter_block, re.DOTALL)
    if not inner:
        return False

    yaml_text = inner.group(1)
    converted_yaml, was_modified = _convert_tools_in_frontmatter(yaml_text)
    if not was_modified:
        return False

    new_frontmatter = f"---\n{converted_yaml}\n---"
    modified = new_frontmatter + original[match.end():]
    path.write_text(modified, encoding="utf-8")
    return True


def validate_agent_file(path: Path) -> list[str]:
    """Validate the ``tools`` field of an ``.agent.md`` file.

    Returns a list of error messages (empty = valid).
    Skips non-``.agent.md`` files.
    """
    if not str(path).endswith(".agent.md"):
        return []
    if not path.exists():
        return [f"File not found: {path}"]

    try:
        data = parse_frontmatter(path)
        if not data:
            return []  # no frontmatter or empty → nothing to validate
        tools_val = data.get("tools")
        if isinstance(tools_val, list):
            return [
                f"tools field is array format (expected object) in {path}",
            ]
        return []
    except Exception as exc:
        return [f"Error reading {path}: {exc}"]


def batch_validate_and_fix(directory: Path, fix: bool = False) -> list[str]:
    """Validate (and optionally fix) all ``.agent.md`` files in *directory*.

    Returns a list of problem descriptions (empty = all valid).
    When *fix* is ``True``, each problematic file is repaired first and the
    result reflects the state **after** the fix.
    """
    if not directory.exists():
        return [f"Directory not found: {directory}"]

    problems: list[str] = []
    for f in sorted(directory.iterdir()):
        if not f.is_file() or not str(f).endswith(".agent.md"):
            continue
        errs = validate_agent_file(f)
        if errs:
            if fix:
                convert_agent_file(f)  # fix in-place
            else:
                problems.extend(errs)
    # When fixing, re-validate everything and return remaining problems
    if fix:
        problems = []
        for f in sorted(directory.iterdir()):
            if not f.is_file() or not str(f).endswith(".agent.md"):
                continue
            problems.extend(validate_agent_file(f))
    return problems
