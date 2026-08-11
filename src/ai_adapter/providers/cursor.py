"""Cursor provider integration.

Handles format conversion and deployment logic specific to
Cursor (https://cursor.com) — an AI code editor with project-scoped
rules (``.cursor/rules/*.mdc``) and MCP servers (``.cursor/mcp.json``).

Supports:
- MCP server export (standard ``mcpServers`` structure)
- Skill deployment as Cursor rules (*.mdc files)
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import click
import yaml

from ai_adapter.models import MCPServer

# ── Path resolution ─────────────────────────────────────────────────────


def resolve_mcp_output_path(path: str | None) -> Path:
    """Determine the output path for ``.cursor/mcp.json``.

    Priority:
    1. ``--path`` explicitly given → ``{path}/.cursor/mcp.json``
    2. Fallback → ``{cwd}/.cursor/mcp.json``
    """
    base = Path(path).resolve() if path else Path.cwd()
    return base / ".cursor" / "mcp.json"


def resolve_rules_dir(project_dir: str | None = None) -> Path:
    """Return the Cursor rules directory (``.cursor/rules/``) for a project."""
    base = Path(project_dir).resolve() if project_dir else Path.cwd()
    return base / ".cursor" / "rules"


# ── MCP ─────────────────────────────────────────────────────────────────


def export_mcp(servers: list[MCPServer]) -> dict:
    """Export MCP servers in Cursor format (``mcpServers`` dict).

    Cursor is MCP-compatible, so the output mirrors the standard
    ``.mcp.json`` structure: ``{"mcpServers": {name: {command, args, env}}}``.

    Args:
        servers: List of MCP server configurations from ai-adapter.
                 Disabled servers are filtered out automatically.

    Returns:
        Dict suitable for writing to ``.cursor/mcp.json``.
    """
    enabled_servers = [s for s in servers if s.enabled]
    servers_dict: dict[str, dict] = {}

    for s in enabled_servers:
        entry: dict[str, object] = {"command": s.command}
        if s.args:
            entry["args"] = list(s.args)
        if s.env_keys:
            entry["env"] = {k: f"${{{k}}}" for k in s.env_keys}
        servers_dict[s.name] = entry

    return {"mcpServers": servers_dict}


def merge_into_cursor_mcp_json(
    output_path: Path,
    cursor_data: dict,
    force: bool = False,
) -> None:
    """Merge ai-adapter's MCP data into a ``.cursor/mcp.json`` file.

    Reads the existing file at *output_path* (if any) and merges
    ``mcpServers`` server-name-based (new overwrites existing, unknown
    existing preserved). Writes a ``.bak`` backup before modifying.

    Args:
        output_path: Path to ``.cursor/mcp.json``.
        cursor_data: Dict from :func:`export_mcp`.
        force: Skip confirmation prompt if True.
    """
    existing: dict = {}
    if output_path.exists():
        if not force:
            click.confirm(
                f"Overwrite MCP servers in '{output_path}'?",
                abort=True,
            )
        bak_path = output_path.with_suffix(output_path.suffix + ".bak")
        shutil.copy2(output_path, bak_path)
        try:
            with open(output_path) as f:
                existing = json.load(f)
        except (json.JSONDecodeError, OSError):
            existing = {}

    new_servers = dict(cursor_data.get("mcpServers", {}))
    existing_servers = existing.get("mcpServers", {})

    # Preserve servers not exported by ai-adapter (same-name is overwritten)
    managed_names = set(cursor_data.get("mcpServers", {}).keys())
    for name in existing_servers:
        if name not in managed_names:
            new_servers[name] = existing_servers[name]

    existing["mcpServers"] = new_servers

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)

    count = len(new_servers)
    click.echo(
        f"Cursor MCP configuration written: {output_path} ({count} servers)",
    )


# ── Skills ──────────────────────────────────────────────────────────────


def _mdc_content(skill_dir: Path, name: str) -> str:
    """Convert a SKILL.md into Cursor rule (.mdc) content.

    The SKILL.md frontmatter ``description`` becomes the rule description
    (falling back to the skill name); an optional ``globs`` key is passed
    through. Rules are manual (no ``alwaysApply``) so they only fire when
    referenced, matching the on-demand semantics of a skill.

    Args:
        skill_dir: Directory containing SKILL.md.
        name: Skill name used as the description fallback.

    Returns:
        Complete ``.mdc`` file content.

    Raises:
        ValueError: If SKILL.md is missing or has no usable frontmatter.
    """
    skill_file = skill_dir / "SKILL.md"
    if not skill_file.exists():
        raise ValueError("SKILL.md not found")

    content = skill_file.read_text(encoding="utf-8")
    match = re.match(r"^---\s*\n(.*?)\n---(?:\n|$)", content, re.DOTALL)
    if not match:
        raise ValueError("no YAML frontmatter found")

    try:
        metadata = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"invalid frontmatter YAML: {exc}") from exc
    if not isinstance(metadata, dict):
        raise ValueError("frontmatter is not a mapping")

    body = content[match.end() :].strip()

    frontmatter: dict[str, object] = {
        "description": metadata.get("description") or name,
    }
    if metadata.get("globs"):
        frontmatter["globs"] = metadata["globs"]

    head = yaml.safe_dump(frontmatter, allow_unicode=True, sort_keys=False).strip()
    return f"---\n{head}\n---\n{body}\n"


def deploy_skills(
    skills: list,
    skills_store_dir: Path,
    force: bool = False,
    project_dir: str | None = None,
) -> None:
    """Deploy ai-adapter skills to ``.cursor/rules/`` as ``*.mdc`` files.

    Each skill's SKILL.md is converted to a single Cursor rule file.
    Existing rules in the target directory are preserved — only
    ai-adapter managed rules are written, leaving others untouched.
    Skills whose SKILL.md is missing or unparseable are skipped with a
    warning and deployment continues.

    Args:
        skills: List of Skill entries from ai-adapter config.
        skills_store_dir: Path to the ai-adapter skills store.
        force: Overwrite existing same-name rules without prompting.
        project_dir: Target project directory (default: current directory).
    """
    rules_dir = resolve_rules_dir(project_dir)
    rules_dir.mkdir(parents=True, exist_ok=True)

    copied = 0
    for skill_entry in skills:
        src = skills_store_dir / skill_entry.name
        if not src.exists():
            click.echo(f"   Skip: '{skill_entry.name}' directory not found.")
            continue

        try:
            content = _mdc_content(src, skill_entry.name)
        except ValueError as exc:
            click.echo(f"   Skip: '{skill_entry.name}' ({exc}).", err=True)
            continue

        dest = rules_dir / f"{skill_entry.name}.mdc"
        if dest.exists() and not force:
            click.confirm(f"Overwrite '{dest.name}' in Cursor rules?", abort=True)
        dest.write_text(content, encoding="utf-8")
        copied += 1

    click.echo(f"All skills ({copied}) deployed as Cursor rules to {rules_dir}.")
