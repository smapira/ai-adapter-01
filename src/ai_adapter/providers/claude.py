"""Claude Code provider integration.

Handles deployment to Claude Code native paths (``.claude/``) and the
user-scope MCP file (``~/.claude.json``).

Claude Code reads project agents/skills from ``.claude/`` and user-scope
MCP servers from ``~/.claude.json``'s ``mcpServers`` key. Project-scope
MCP stays in ``.mcp.json`` (existing ``mcp get --format standard``).

Scope resolution is delegated to :func:`ai_adapter.config.resolve_scope_path`
(design 01) — this module never re-implements path mapping.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import click

from ai_adapter.agent_format import convert_agent_file, find_agent_file
from ai_adapter.config import add_to_gitignore, resolve_scope_path
from ai_adapter.models import Agent, MCPServer, Skill

# ── Shared CLI validation ───────────────────────────────────────────────


def validate_claude_scope(format_name: str, scope: str, ignored_option: str | None = None) -> None:
    """Validate a ``--format``/``--scope`` pair for native-path deploys.

    Only Claude Code, Codex, OpenCode, Gemini CLI, and Zed have user-scope
    deploy targets among the formats that accept ``--scope`` (designs
    02/03/04/05/06).  Other formats keep their fixed project-scope
    destinations, so pairing them with ``--scope user`` is always a user
    error.  When *ignored_option* is given and scope is "user", a warning
    notes that the option no longer applies.
    """
    if scope != "user":
        return
    if format_name not in ("claude", "codex", "opencode", "gemini", "zed"):
        raise click.ClickException(
            f"--scope user is only supported with --format claude, codex, opencode, gemini, or zed "
            f"(got --format {format_name})",
        )
    if ignored_option:
        click.echo(f"Warning: {ignored_option} is ignored with --scope user.", err=True)


# ── Path resolution ─────────────────────────────────────────────────────


def resolve_agents_path(scope: str, project_dir: Path | None = None) -> Path:
    """Return the Claude Code agents directory for *scope*.

    Args:
        scope: "project" → ``.claude/agents/``, "user" → ``~/.claude/agents/``.
        project_dir: Project directory for project scope (defaults to cwd).
    """
    return resolve_scope_path("claude", "agents", scope, project_dir).path


def resolve_skills_path(scope: str, project_dir: Path | None = None) -> Path:
    """Return the Claude Code skills directory for *scope*.

    Args:
        scope: "project" → ``.claude/skills/``, "user" → ``~/.claude/skills/``.
        project_dir: Project directory for project scope (defaults to cwd).
    """
    return resolve_scope_path("claude", "skills", scope, project_dir).path


def resolve_user_json_path() -> Path:
    """Return ``~/.claude.json`` — Claude Code's user-scope MCP file."""
    return Path.home() / ".claude.json"


# ── Agents ──────────────────────────────────────────────────────────────


def claude_agent_filename(src_name: str) -> str:
    """Return the destination filename Claude Code reads for *src_name*.

    Claude Code only reads plain ``.md`` agent files, so ``.agent.md``
    store files are normalised to ``.md``; other names pass through.
    """
    if src_name.endswith(".agent.md"):
        return src_name[: -len(".agent.md")] + ".md"
    return src_name


def deploy_agent_file(src: Path, dest_dir: Path, force: bool = False, fix: bool = False) -> Path:
    """Copy one agent file into *dest_dir* with Claude Code conventions.

    ``.agent.md`` sources are renamed to ``.md`` and their frontmatter
    ``tools`` field is normalised to object format via
    :func:`ai_adapter.agent_format.convert_agent_file` (Claude Code reads
    ``.md`` files; the conversion is applied to a temp copy, never to the
    store, and never clobbers an unrelated file in *dest_dir*).

    When *fix* is True, plain ``.md`` sources also get their array-format
    ``tools`` field converted (staged under a temp ``.agent.md`` name so
    ``convert_agent_file`` can process them, then renamed).

    Args:
        src: Source agent file (usually in ``~/.ai-adapter/agents/``).
        dest_dir: Destination directory (``.claude/agents/``).
        force: Overwrite an existing destination without prompting.
        fix: Also convert array-format tools in plain ``.md`` sources.

    Returns:
        The destination path.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / claude_agent_filename(src.name)
    if dest.exists() and not force:
        click.confirm(f"'{dest.name}' already exists. Overwrite?", abort=True)

    needs_conversion = src.name.endswith(".agent.md") or (fix and src.name.endswith(".md"))
    if not needs_conversion:
        shutil.copy2(src, dest)
        return dest

    # convert_agent_file only touches files ending in ".agent.md", so stage
    # the copy under a unique ".agent.md" temp name (same directory → atomic
    # rename), convert in place, then move to the ".md" name Claude reads.
    staging = dest_dir / f"{src.stem}.aiadapter-staging.agent.md"
    try:
        shutil.copy2(src, staging)
        if convert_agent_file(staging):
            click.echo(f"  Warning: converted tools format in {dest.name}", err=True)
        staging.replace(dest)
    finally:
        staging.unlink(missing_ok=True)
    return dest


def deploy_agents(
    agents: list[Agent],
    src_dir: Path,
    scope: str,
    project_dir: Path | None = None,
    force: bool = False,
    fix: bool = False,
) -> None:
    """Copy agent files to ``.claude/agents/`` for the given scope.

    Registered agents are located in *src_dir* by frontmatter name or
    filename; missing files are skipped with a notice.  Project-scope
    destinations are added to ``.gitignore`` (user scope never is —
    walking up from ``$HOME`` could touch a dotfiles repo).

    Args:
        agents: Registered agent entries from the config.
        src_dir: The ai-adapter agents store (``~/.ai-adapter/agents/``).
        scope: "project" or "user".
        project_dir: Project directory for project scope.
        force: Overwrite existing files without prompting.
        fix: Also convert array-format tools in plain ``.md`` sources.
    """
    target = resolve_scope_path("claude", "agents", scope, project_dir)
    dest_dir = target.path
    dest_dir.mkdir(parents=True, exist_ok=True)

    copied = 0
    for agent_entry in agents:
        src = find_agent_file(src_dir, agent_entry.name)
        if src is None:
            click.echo(f"   Skip: '{agent_entry.name}' file not found.")
            continue
        dest = deploy_agent_file(src, dest_dir, force, fix=fix)
        if target.use_gitignore:
            add_to_gitignore(dest)
        copied += 1

    click.echo(f"All agents ({copied}) copied to {dest_dir}.")


# ── Skills ──────────────────────────────────────────────────────────────


def deploy_skills(
    skills: list[Skill],
    src_dir: Path,
    scope: str,
    project_dir: Path | None = None,
    force: bool = False,
) -> None:
    """Copy skill directories to ``.claude/skills/`` for the given scope.

    Skills are directories containing ``SKILL.md``; the whole tree is
    copied so frontmatter and helper files are preserved.  Existing
    non-managed skill directories are confirmed (or overwritten with
    *force*); project-scope destinations are added to ``.gitignore``.

    Args:
        skills: Registered skill entries from the config.
        src_dir: The ai-adapter skills store (``~/.ai-adapter/skills/``).
        scope: "project" or "user".
        project_dir: Project directory for project scope.
        force: Overwrite existing skill directories without prompting.
    """
    target = resolve_scope_path("claude", "skills", scope, project_dir)
    dest_dir = target.path
    dest_dir.mkdir(parents=True, exist_ok=True)

    copied = 0
    for skill_entry in skills:
        src = src_dir / skill_entry.name
        if not src.exists():
            click.echo(f"   Skip: '{skill_entry.name}' directory not found.")
            continue
        dest = dest_dir / skill_entry.name
        if dest.exists():
            if force:
                shutil.rmtree(dest)
            else:
                click.confirm(f"'{dest}' already exists. Overwrite?", abort=True)
                shutil.rmtree(dest)
        shutil.copytree(src, dest)
        if target.use_gitignore:
            add_to_gitignore(dest)
        copied += 1

    click.echo(f"All skills ({copied}) copied to {dest_dir}.")


# ── MCP (user scope: ~/.claude.json) ────────────────────────────────────


def export_mcp_user(servers: list[MCPServer]) -> dict:
    """Export MCP servers for ``~/.claude.json`` (user scope).

    Claude Code defines user-scope MCP servers in ``~/.claude.json``'s
    ``mcpServers`` key; project scope uses ``.mcp.json`` (existing
    ``mcp get --format standard``).  Disabled servers are filtered out.

    Args:
        servers: MCP server configurations from ai-adapter.

    Returns:
        ``{"mcpServers": {name: {command, args, env}}}`` — the payload
        merged by :func:`merge_into_claude_json`.
    """
    servers_dict: dict[str, dict] = {}
    for s in servers:
        if not s.enabled:
            continue
        entry: dict[str, object] = {"command": s.command}
        if s.args:
            entry["args"] = list(s.args)
        if s.env_keys:
            entry["env"] = {k: f"${{{k}}}" for k in s.env_keys}
        servers_dict[s.name] = entry
    return {"mcpServers": servers_dict}


def merge_into_claude_json(path: Path, data: dict, force: bool = False) -> None:
    """Merge MCP servers into ``~/.claude.json`` preserving other keys.

    ``~/.claude.json`` is Claude Code's own user data (project history,
    permissions, …), so only the ``mcpServers`` key is touched — every
    other key is preserved verbatim.  Managed server names are
    overwritten; unmanaged existing servers are kept.  A ``.bak`` backup
    is taken before modifying an existing file; a missing file starts
    from ``{"mcpServers": {}}``.

    If the existing file cannot be parsed as a JSON object, this
    function **aborts** instead of overwriting — corrupting Claude Code's
    user data would violate the design's AC2 (never touch unmanaged keys).

    Args:
        path: Path to ``~/.claude.json``.
        data: Dict from :func:`export_mcp_user`.
        force: Skip the confirmation prompt if True.

    Raises:
        click.ClickException: When the existing file is unreadable or is
            not a JSON object (merge is aborted to protect user data).
    """
    existing: dict = {}
    if path.exists():
        if not force:
            click.confirm(f"Overwrite MCP servers in '{path}'?", abort=True)
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise click.ClickException(
                f"Cannot merge into '{path}': file is not valid JSON ({exc}). "
                "Fix or remove the file first — refusing to overwrite Claude Code user data."
            ) from exc
        if not isinstance(existing, dict):
            raise click.ClickException(
                f"Cannot merge into '{path}': top-level JSON value is not an object. "
                "Fix or remove the file first — refusing to overwrite Claude Code user data."
            )
        bak_path = path.parent / (path.name + ".bak")
        shutil.copy2(path, bak_path)

    new_servers = dict(data.get("mcpServers", {}))
    existing_servers = existing.get("mcpServers", {})
    if not isinstance(existing_servers, dict):
        existing_servers = {}

    # Preserve servers not managed by ai-adapter (same-name is overwritten)
    for name, server in existing_servers.items():
        if name not in new_servers:
            new_servers[name] = server

    existing["mcpServers"] = new_servers
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")
    except OSError as exc:
        raise click.ClickException(f"Failed to write '{path}': {exc}") from exc

    count = len(new_servers)
    click.echo(f"Claude MCP configuration written: {path} ({count} servers)")
