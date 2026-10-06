"""Cursor provider integration.

Handles format conversion and deployment logic specific to
Cursor (https://cursor.com) — an AI code editor with project-scoped
rules (``.cursor/rules/*.mdc``), MCP servers (``.cursor/mcp.json``),
and plugin packages (``~/.cursor/plugins/local/``).

Supports:
- MCP server export (standard ``mcpServers`` structure)
- Skill deployment as Cursor rules (*.mdc files)
- Legacy ``.cursorrules`` export (design 07 — migration aid)
- Skill deployment as a Cursor plugin package (design 07)
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import click
import yaml

from ai_adapter.config import is_safe_store_name, resolve_scope_path
from ai_adapter.models import MCPServer

# Legacy project-root rules file (design 07). Cursor still reads it, but
# official docs recommend .cursor/rules/*.mdc — treat this as migration-only.
CURSORRULES_FILENAME = ".cursorrules"

# Shared YAML-frontmatter matcher. Instruction files (AGENTS.md etc.) and
# SKILL.md bodies both use the same ``--- ... ---`` envelope, so one regex
# serves the .mdc converter and the .cursorrules exporter.
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---(?:\n|$)", re.DOTALL)

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
    match = _FRONTMATTER_RE.match(content)
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


# ── Legacy .cursorrules (design 07) ────────────────────────────────────


def _strip_frontmatter(content: str) -> str:
    """Remove a YAML frontmatter block from *content*.

    ``.cursorrules`` is plain text (Cursor ignores any metadata envelope),
    so both ``agent get`` and ``agent get-all`` strip frontmatter before
    writing. Content without frontmatter is returned unchanged.

    Args:
        content: Raw instruction file content.

    Returns:
        Content with any leading ``--- ... ---`` block removed and
        surrounding whitespace stripped.
    """
    match = _FRONTMATTER_RE.match(content)
    if not match:
        return content.strip()
    return content[match.end() :].strip()


def export_cursorrules(named_contents: list[tuple[str, str]]) -> str:
    """Convert instruction content(s) to legacy ``.cursorrules`` text.

    Args:
        named_contents: ``(name, raw content)`` pairs in output order.
            The name is used only as the separator label for multi-instruction
            output (e.g. ``("AGENTS", "---\\n# Root agent\\n---\\n...")``).

    Returns:
        Plain-text body with frontmatter removed. A single instruction is
        emitted as-is; multiple instructions are joined with
        ``# --- <name> ---`` separator comments so the merged file stays
        navigable.
    """
    bodies: list[str] = []
    for name, content in named_contents:
        body = _strip_frontmatter(content)
        if len(named_contents) > 1:
            body = f"# --- {name} ---\n{body}"
        bodies.append(body)
    return "\n\n".join(bodies)


# ── Plugin package (design 07) ──────────────────────────────────────────


def _sanitize_plugin_name(raw: str) -> str:
    """Sanitize a project basename into a Cursor-valid plugin name.

    Cursor's official schema requires: ``^[a-z0-9]([a-z0-9.-]*[a-z0-9])?$``
    — lowercase alphanumerics, hyphens, and periods only; must start and end
    with an alphanumeric (QA NEW-ISSUE-1).  Underscores are NOT allowed.
    """
    name = raw.lower()
    # Replace everything outside the allowed set (note: underscore is NOT
    # allowed by Cursor's schema, so it maps to "-").
    name = re.sub(r"[^a-z0-9.-]+", "-", name)
    name = re.sub(r"-{2,}", "-", name)
    # Strip invalid leading characters only; trailing "-" is handled below
    # so "proj-" becomes "proj-0" rather than silently becoming "proj".
    name = name.lstrip("-.")
    if not name:
        name = "ai-adapter"
    if not name[-1].isalnum():
        name = name + "0"
    if not name[0].isalnum():
        name = "a" + name.lstrip("-.")
    return name


def resolve_plugin_root(project_dir: str | None = None) -> Path:
    """Return the Cursor plugin root for a project.

    Cursor reads plugin packages from ``~/.cursor/plugins/local/<name>/``
    only — a project-local ``skills/`` directory is NOT discovered (design 07
    §2.2). The plugin name is the project directory's basename so each
    project maps to its own local plugin.

    Destination resolution goes through :func:`resolve_scope_path` so Cursor
    shares the single scope matrix with every other tool (design 01).
    """
    base = Path(project_dir).resolve() if project_dir else Path.cwd()
    plugins_dir = resolve_scope_path("cursor", "skills", "user", base).path
    project_name = _sanitize_plugin_name(base.name or "ai-adapter")
    return plugins_dir / project_name


def generate_plugin_manifest(project_name: str) -> dict:
    """Generate the ``.cursor-plugin/plugin.json`` manifest dict.

    The manifest is mandatory — Cursor ignores a plugin directory that has
    no ``.cursor-plugin/plugin.json`` (design 07 §2.2).
    """
    return {
        "name": _sanitize_plugin_name(project_name),
        "version": "1.0.0",
        "description": "Managed by ai-adapter",
    }


def deploy_skills_plugin(
    skills: list,
    skills_store_dir: Path,
    force: bool = False,
    project_dir: str | None = None,
) -> None:
    """Deploy ai-adapter skills as a Cursor plugin package.

    Generates a true plugin package under ``~/.cursor/plugins/local/``:

    - ``.cursor-plugin/plugin.json``  (required manifest — always written)
    - ``skills/<name>/SKILL.md``      (skill body, frontmatter preserved)
    - auxiliary files (scripts/, references/, etc.) copied verbatim

    An existing plugin directory prompts for overwrite unless *force* is
    set; declining leaves the existing package untouched. Only the skills
    being deployed are replaced — sibling skills from earlier deploys are
    preserved. The destination is always user-scope regardless of
    ``--scope`` because Cursor has no project-local plugin discovery.

    Args:
        skills: List of Skill entries from ai-adapter config.
        skills_store_dir: Path to the ai-adapter skills store.
        force: Overwrite an existing plugin package without prompting.
        project_dir: Project directory (default: cwd). Its basename becomes
            the plugin name.
    """
    plugin_root = resolve_plugin_root(project_dir)
    if plugin_root.exists() and not force:
        click.confirm(f"'{plugin_root}' already exists. Overwrite?", abort=True)

    skills_dir = plugin_root / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)

    copied = 0
    for skill_entry in skills:
        src = skills_store_dir / skill_entry.name
        if not src.exists():
            click.echo(f"   Skip: '{skill_entry.name}' directory not found.")
            continue
        # Multi-layer guard against path traversal (review C1): block names
        # that would resolve outside skills_dir even via prefix-siblings.
        # Same guard as zed.py deploy_skills (design 06).
        if not is_safe_store_name(skill_entry.name):
            click.echo(f"   Skip: '{skill_entry.name}' is not a safe store name.", err=True)
            continue
        dest = (skills_dir / skill_entry.name).resolve()
        if not dest.is_relative_to(skills_dir.resolve()):
            click.echo(
                f"   Skip: '{skill_entry.name}' resolves outside the skills directory.",
                err=True,
            )
            continue
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(src, dest)
        copied += 1

    # The manifest is mandatory — write it on every deploy so a package is
    # always valid even when all skills were skipped.
    manifest_path = plugin_root / ".cursor-plugin" / "plugin.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(generate_plugin_manifest(plugin_root.name), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    click.echo(f"Cursor plugin package written: {plugin_root}")
    click.echo(f"  {manifest_path}")
    click.echo(f"  {copied} skill(s) installed under {skills_dir}")
    click.echo("Enable the plugin in Cursor to load these skills.")
