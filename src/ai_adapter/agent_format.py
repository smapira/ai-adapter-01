"""Agent file format utilities.

Provides functions to parse, validate, and convert YAML frontmatter in
.agent.md files.  The main concern is keeping the ``tools`` field in the
format the target platform expects: VS Code requires **array** format
(``tools: [execute, read]``) — the canonical format for
``.github/agents/`` — while OpenCode expects **object** format
(``tools:\\n  execute: true``).  Both conversion directions are provided
so each deploy path can normalise as needed.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml


def parse_frontmatter_text(content: str) -> dict:
    """Parse YAML frontmatter from *content*.

    Extracts the YAML block between the leading ``---`` delimiters and
    returns it as a dictionary.  Returns an empty dict when no frontmatter
    is found or the YAML is not a mapping.
    """
    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if match:
        data = yaml.safe_load(match.group(1))
        return data if isinstance(data, dict) else {}
    return {}


def parse_frontmatter(path: Path) -> dict:
    """Parse YAML frontmatter from a file.

    Thin wrapper around :func:`parse_frontmatter_text` so file- and
    string-based callers share one frontmatter grammar.
    """
    return parse_frontmatter_text(path.read_text(encoding="utf-8"))


def strip_frontmatter_text(content: str) -> str:
    """Return *content* without its leading YAML frontmatter block."""
    match = re.match(r"^---\s*\n.*?\n---\s*\n?", content, re.DOTALL)
    return content[match.end() :] if match else content


def slugify_agent_name(name: str) -> str:
    """Return a platform-safe slug for *name*.

    Lowercases and keeps only ``[a-z0-9_-]`` — the shape Gemini CLI
    requires for subagent names, and a safe filename for other
    platforms.  Returns an empty string when nothing survives the
    mapping (e.g. a purely non-ASCII name).
    """
    return re.sub(r"[^a-z0-9_-]+", "-", name.lower()).strip("-")


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


def convert_tools_to_array(tools_value: Any) -> tuple[list[str], bool]:
    """Convert a raw YAML ``tools`` value to array format.

    Returns a ``(converted_list, was_modified)`` pair so callers can decide
    whether to warn the user or write the file back.

    ================== ====================================================
    Input              Output
    ================== ====================================================
    ``{"a": True}``    ``(["a"], True)``
    ``{"a": True,
        "b": False}``  ``(["a"], True)``  — falsy entries dropped
    ``["a", "b"]``     ``(["a", "b"], False)``
    ``None`` / missing ``([], False)``
    other types        ``([], False)``
    ================== ====================================================
    """
    if isinstance(tools_value, dict):
        return [k for k, v in tools_value.items() if isinstance(k, str) and v], True
    if isinstance(tools_value, list):
        return [item for item in tools_value if isinstance(item, str)], False
    return [], False


def convert_tools_to_string(tools_value: Any) -> tuple[str, bool]:
    """Convert a raw YAML ``tools`` value to Claude Code's comma-separated
    string format.

    Returns a ``(converted_string, was_modified)`` pair.  Both array and
    object inputs are real conversions (the canonical store format is
    array); an existing string passes through unmodified.

    ================== ====================================================
    Input              Output
    ================== ====================================================
    ``["a", "b"]``     ``("a, b", True)``
    ``{"a": True}``    ``("a", True)``
    ``{"a": False}``   ``("", True)``       — falsy entries dropped
    ``"a, b"``         ``("a, b", False)``
    ``None`` / missing ``("", False)``
    other types        ``("", False)``
    ================== ====================================================
    """
    if isinstance(tools_value, str):
        return tools_value, False
    if isinstance(tools_value, list):
        names = [item for item in tools_value if isinstance(item, str)]
        return ", ".join(names), True
    if isinstance(tools_value, dict):
        names = [k for k, v in tools_value.items() if isinstance(k, str) and v]
        return ", ".join(names), True
    return "", False


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
        r"^(\s*)tools:\s*\[(.*?)\]\s*(?:#.*)?$",
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


def _convert_tools_in_frontmatter_to_string(frontmatter_text: str) -> tuple[str, bool]:
    """Normalise the ``tools`` field to Claude Code's comma-separated string.

    Handles both array syntax (``tools: [a, b]``) and object blocks
    (``tools:\\n  a: true``) in the *raw YAML text*, preserving comments
    and layout.  Already-string ``tools`` lines are left untouched.

    Returns ``(modified_text, was_modified)``.
    """
    # Array form: tools: [a, b]
    array_pattern = re.compile(r"^(\s*)tools:\s*\[(.*?)\]\s*(?:#.*)?$", re.MULTILINE)
    # Object form: tools:\n  key: value...
    block_pattern = re.compile(r"^(\s*)tools:\s*\n((?:[ \t]+\S[^\n]*\n?)+)", re.MULTILINE)

    def _names_from_items(items_str: str) -> list[str]:
        names: list[str] = []
        for raw in items_str.split(","):
            item = raw.strip().strip("\"'")
            if item:
                names.append(item)
        return names

    def _array_replace(m: re.Match) -> str:
        names = _names_from_items(m.group(2))
        return f"{m.group(1)}tools: {', '.join(names)}"

    def _block_replace(m: re.Match) -> str:
        names: list[str] = []
        for line in m.group(2).strip().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            key, sep, value = line.partition(":")
            if not sep:
                continue
            key = key.strip().strip("\"'")
            value = value.strip().split("#")[0].strip().strip("\"'")
            if value.lower() in ("true", "yes", "on", "1"):
                names.append(key)
        trailing = "\n" if m.group(2).endswith("\n") else ""
        return f"{m.group(1)}tools: {', '.join(names)}{trailing}"

    new_text, count_arr = array_pattern.subn(_array_replace, frontmatter_text)
    new_text, count_blk = block_pattern.subn(_block_replace, new_text)
    return new_text, (count_arr + count_blk) > 0


def _convert_tools_in_frontmatter_to_array(frontmatter_text: str) -> tuple[str, bool]:
    """Replace object-format ``tools`` blocks with array-format lines.

    Operates on the *raw YAML text* (the content between ``---`` markers)
    using a regular expression so that comments and overall layout are
    preserved.  A ``tools:`` key line is matched together with its
    indented ``key: value`` children; entries whose value is truthy are
    collected into ``tools: [a, b]``.  Lines that already use array syntax
    or contain inline comments on the ``tools:`` line are left untouched.

    Returns ``(modified_text, was_modified)``.
    """
    # Match:  tools:\n  key: value\n  key: value ...  (indent = 2+ spaces)
    pattern = re.compile(
        r"^(\s*)tools:\s*\n((?:[ \t]+\S[^\n]*\n?)+)",
        re.MULTILINE,
    )

    def _replace(m: re.Match) -> str:
        indent = m.group(1)
        keys: list[str] = []
        for line in m.group(2).strip().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            key, sep, value = line.partition(":")
            if not sep:
                continue
            key = key.strip().strip("\"'")
            value = value.strip().split("#")[0].strip()
            if value and value[0] in "\"'":
                value = value.strip("\"'")
            if value.lower() in ("true", "yes", "on", "1"):
                keys.append(key)
        if not keys:
            return f"{indent}tools: []\n"
        return f"{indent}tools: [{', '.join(keys)}]\n"

    new_text, count = pattern.subn(_replace, frontmatter_text)
    return new_text, count > 0


# ---------------------------------------------------------------------------
# File-level operations
# ---------------------------------------------------------------------------


def find_agent_file(agents_dir: Path, name: str) -> Path | None:
    """Find an agent file in *agents_dir* by frontmatter name or filename.

    Search order: frontmatter ``name`` first (agents may be stored under
    any filename), then the conventional filename candidates
    (``<name>.agent.md``, ``<name>.md``, ``<name>``).  Returns None when
    no match exists or *agents_dir* does not exist.
    """
    if not agents_dir.is_dir():
        return None
    for f in agents_dir.iterdir():
        if not f.is_file():
            continue
        try:
            fm = parse_frontmatter(f)
            if fm.get("name", "").strip() == name:
                return f
        except Exception:
            continue
    candidates = [
        agents_dir / f"{name}.agent.md",
        agents_dir / f"{name}.md",
        agents_dir / name,
    ]
    for c in candidates:
        if c.exists() and c.is_file():
            return c
    return None


def convert_agent_file(path: Path) -> bool:
    """Read an ``.agent.md`` file, convert its ``tools`` field, and write
    back if the content changed.

    Converts **array → object** format (OpenCode expectation).  For the
    reverse direction see :func:`convert_agent_file_to_array`.

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
    modified = new_frontmatter + original[match.end() :]
    path.write_text(modified, encoding="utf-8")
    return True


def convert_agent_file_to_array(path: Path) -> bool:
    """Read an ``.agent.md`` file, convert its ``tools`` field to array
    format, and write back if the content changed.

    Converts **object → array** format (VS Code expectation — falsy
    entries are dropped).  Returns ``True`` if the file was modified,
    ``False`` otherwise.  Skips non-``.agent.md`` files silently.
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
    converted_yaml, was_modified = _convert_tools_in_frontmatter_to_array(yaml_text)
    if not was_modified:
        return False

    new_frontmatter = f"---\n{converted_yaml}\n---"
    modified = new_frontmatter + original[match.end() :]
    path.write_text(modified, encoding="utf-8")
    return True


def convert_agent_file_to_string(path: Path) -> bool:
    """Read an ``.agent.md`` file, normalise its ``tools`` field to Claude
    Code's comma-separated string, and write back if changed.

    Both array and object inputs are converted (``tools: [a, b]`` and
    ``tools:\\n  a: true`` → ``tools: a, b``).  Returns ``True`` if the
    file was modified, ``False`` otherwise.  Skips non-``.agent.md``
    files silently.
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
    converted_yaml, was_modified = _convert_tools_in_frontmatter_to_string(yaml_text)
    if not was_modified:
        return False

    new_frontmatter = f"---\n{converted_yaml}\n---"
    modified = new_frontmatter + original[match.end() :]
    path.write_text(modified, encoding="utf-8")
    return True


def convert_agent_content_to(content: str, target_shape: str) -> str:
    """Return agent Markdown with the ``tools`` field normalised to *target_shape*.

    Content-level (non-destructive) counterpart of the file-level
    converters — the input text is never written back.

    Args:
        content: Full agent file text (frontmatter + body).
        target_shape: "array" (VS Code / Gemini), "object" (OpenCode), or
            "string" (Claude Code comma-separated).

    Non-tools frontmatter keys, comments, and the body are preserved;
    content without frontmatter is returned unchanged.

    Raises:
        ValueError: Unknown *target_shape*.
    """
    match = re.match(r"^(---\s*\n.*?\n---)", content, re.DOTALL)
    if not match:
        return content
    inner = re.match(r"^---\s*\n(.*?)\n---", match.group(1), re.DOTALL)
    if not inner:
        return content
    converters = {
        "array": _convert_tools_in_frontmatter_to_array,
        "object": _convert_tools_in_frontmatter,
        "string": _convert_tools_in_frontmatter_to_string,
    }
    try:
        converter = converters[target_shape]
    except KeyError:
        raise ValueError(f"Unknown target shape: {target_shape}") from None
    converted_yaml, _ = converter(inner.group(1))
    return f"---\n{converted_yaml}\n---" + content[match.end() :]


def validate_agent_file(path: Path, target_format: str = "object") -> list[str]:
    """Validate the ``tools`` field of an ``.agent.md`` file.

    Args:
        path: File to validate.
        target_format: "object" → array-format tools is an error
            (OpenCode expectation); "array" → object-format tools is an
            error (VS Code expectation); "string" → both array and object
            formats are errors (Claude Code comma-separated expectation).

    Returns:
        A list of error messages (empty = valid).
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
        if target_format == "array" and isinstance(tools_val, dict):
            return [
                f"tools field is object format (expected array) in {path}",
            ]
        if target_format == "string" and isinstance(tools_val, (list, dict)):
            found = "array" if isinstance(tools_val, list) else "object"
            return [
                f"tools field is {found} format (expected comma-separated string) in {path}",
            ]
        if target_format not in ("array", "string") and isinstance(tools_val, list):
            return [
                f"tools field is array format (expected object) in {path}",
            ]
        return []
    except Exception as exc:
        return [f"Error reading {path}: {exc}"]


def batch_validate_and_fix(directory: Path, fix: bool = False, target_format: str = "object") -> list[str]:
    """Validate (and optionally fix) all ``.agent.md`` files in *directory*.

    Args:
        directory: Directory containing ``.agent.md`` files.
        fix: Convert each problematic file in-place before re-validating.
        target_format: "object" (OpenCode, array→object), "array"
            (VS Code, object→array), or "string" (Claude Code, →
            comma-separated).

    Returns:
        A list of problem descriptions (empty = all valid).
        When *fix* is ``True``, each problematic file is repaired first and the
        result reflects the state **after** the fix.
    """
    if not directory.exists():
        return [f"Directory not found: {directory}"]

    converters = {
        "array": convert_agent_file_to_array,
        "string": convert_agent_file_to_string,
    }
    convert = converters.get(target_format, convert_agent_file)

    problems: list[str] = []
    for f in sorted(directory.iterdir()):
        if not f.is_file() or not str(f).endswith(".agent.md"):
            continue
        errs = validate_agent_file(f, target_format=target_format)
        if errs:
            if fix:
                convert(f)  # fix in-place
            else:
                problems.extend(errs)
    # When fixing, re-validate everything and return remaining problems
    if fix:
        problems = []
        for f in sorted(directory.iterdir()):
            if not f.is_file() or not str(f).endswith(".agent.md"):
                continue
            problems.extend(validate_agent_file(f, target_format=target_format))
    return problems
