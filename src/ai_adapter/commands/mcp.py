"""mcp subcommand implementation.

Manages MCP server configurations under ~/.ai-adapter/mcp/.
Exports settings in formats compatible with various tools (VS Code / Claude / Cursor / OpenClaw).
"""

from __future__ import annotations

import json
from pathlib import Path

import click

from ai_adapter import config as _config
from ai_adapter.models import MCPServer
from ai_adapter.providers.claude import export_mcp_user as _export_claude_mcp_user
from ai_adapter.providers.claude import merge_into_claude_json as _merge_claude_json
from ai_adapter.providers.claude import resolve_user_json_path as _claude_user_json_path
from ai_adapter.providers.claude import validate_claude_scope
from ai_adapter.providers.codex import export_mcp_toml as _export_codex_mcp
from ai_adapter.providers.codex import merge_into_config_toml as _merge_codex_config
from ai_adapter.providers.codex import resolve_config_toml_path as _codex_config_path
from ai_adapter.providers.cursor import export_mcp as _export_cursor_mcp
from ai_adapter.providers.cursor import merge_into_cursor_mcp_json as _merge_cursor_mcp
from ai_adapter.providers.cursor import resolve_mcp_output_path as _cursor_output_path
from ai_adapter.providers.gemini import export_mcp as _export_gemini_mcp
from ai_adapter.providers.gemini import merge_into_settings as _merge_gemini_settings
from ai_adapter.providers.gemini import resolve_settings_path as _gemini_settings_path
from ai_adapter.providers.openclaw import export_mcp as _export_openclaw_mcp
from ai_adapter.providers.openclaw import merge_into_openclaw_json as _merge_openclaw
from ai_adapter.providers.openclaw import resolve_mcp_output_path as _openclaw_output_path
from ai_adapter.providers.vscode import export_mcp as _export_vscode_mcp
from ai_adapter.providers.vscode import merge_into_vscode_mcp_json as _merge_vscode_mcp
from ai_adapter.providers.vscode import resolve_mcp_output_path as _vscode_output_path


@click.group(name="mcp")
def mcp_group() -> None:
    """Manage MCP server configurations."""


@mcp_group.command(name="list")
@click.option("--tool", help="Filter by tool name (vscode/claude/cursor)")
@click.option("--env", help="Filter by environment name")
def mcp_list(tool: str | None, env: str | None) -> None:
    """List MCP servers."""
    config = _config.load_config()
    if config is None:
        click.echo("Configuration file not found. Run ai-adapter init first.")
        return

    servers = config.mcp_servers
    if tool:
        servers = [s for s in servers if tool in s.tools]
    if env:
        servers = [s for s in servers if s.env is None or s.env == env]

    if not servers:
        click.echo("No MCP servers registered.")
        return

    click.echo("MCP Servers:")
    click.echo("-" * 70)
    for s in servers:
        enabled_mark = "✓" if s.enabled else "✗"
        tools_str = f" [{', '.join(s.tools)}]" if s.tools else ""
        env_str = f" (env: {s.env})" if s.env else ""
        click.echo(f"  {enabled_mark} {s.name}{tools_str}{env_str}")
        click.echo(f"     command: {s.command} {' '.join(s.args)}")


@mcp_group.command(name="add")
@click.argument("name", required=False)
@click.option("--command", "-c", help="Command to execute")
@click.option("--args", "-a", multiple=True, help="Command arguments (can be specified multiple times)")
@click.option("--env-key", "-e", multiple=True, help="Required env var keys (can be specified multiple times)")
@click.option(
    "--tool", "-t", multiple=True, help="Compatible tools: vscode/claude/cursor (can be specified multiple times)"
)
@click.option("--env", help="Target environment")
@click.option(
    "--file",
    "-f",
    "json_path",
    type=click.Path(exists=True, readable=True),
    help="Path to .mcp.json file for bulk import",
)
@click.option("--force", is_flag=True, help="Overwrite existing server without prompting")
def mcp_add(
    name: str | None,
    command: str | None,
    args: tuple[str, ...],
    env_key: tuple[str, ...],
    tool: tuple[str, ...],
    env: str | None,
    json_path: str | None,
    force: bool,
) -> None:
    """Add an MCP server configuration.

    NAME: MCP server name (omit when using --file).
    """
    config = _config.load_config()
    if config is None:
        click.echo("Configuration file not found. Run ai-adapter init first.")
        return

    # --file mode: bulk import from .mcp.json
    if json_path:
        _import_mcp_from_file(config, json_path, force=force)
        return

    # Interactive single-server mode
    if not name:
        click.echo("NAME is required when --file is not used.", err=True)
        raise click.ClickException("Provide NAME or use --file.")

    if not command:
        click.echo("--command is required.", err=True)
        raise click.ClickException("--command option is required.")

    # Duplicate check — overwrite if --force, else error
    existing = next((s for s in config.mcp_servers if s.name == name), None)
    if existing is not None:
        if not force:
            click.echo(f"MCP server '{name}' already exists. Use --force to overwrite.", err=True)
            raise click.ClickException(f"MCP server '{name}' is already registered.")
        existing.command = command
        existing.args = list(args)
        existing.env_keys = list(env_key)
        existing.tools = list(tool) if tool else ["vscode", "claude", "cursor"]
        existing.env = env
        existing.enabled = True
        _config.save_config(config)
        click.echo(f"MCP server '{name}' updated.")
        return

    server = MCPServer(
        name=name,
        command=command,
        args=list(args),
        env_keys=list(env_key),
        enabled=True,
        tools=list(tool) if tool else ["vscode", "claude", "cursor"],
        env=env,
    )

    config.mcp_servers.append(server)
    _config.save_config(config)
    click.echo(f"MCP server '{name}' added.")


@mcp_group.command(name="remove")
@click.argument("name")
def mcp_remove(name: str) -> None:
    """Remove an MCP server configuration.

    NAME: MCP server name to remove.
    """
    config = _config.load_config()
    if config is None:
        click.echo("Configuration file not found. Run ai-adapter init first.")
        return

    found = None
    for s in config.mcp_servers:
        if s.name == name:
            found = s
            break

    if found is None:
        click.echo(f"MCP server '{name}' is not registered.", err=True)
        raise click.ClickException(f"MCP server '{name}' not found.")

    config.mcp_servers.remove(found)
    _config.save_config(config)
    click.echo(f"MCP server '{name}' removed.")


def _mcp_get_standard(servers: list[MCPServer], path: str | None, force: bool = False) -> None:
    """Export MCP servers in standard .mcp.json format."""
    mcp_config: dict = {"mcpServers": {}}
    for server in servers:
        env_dict = {}
        for key in server.env_keys:
            env_dict[key] = f"${{{key}}}"

        entry: dict = {
            "command": server.command,
            "args": server.args,
        }
        if env_dict:
            entry["env"] = env_dict

        mcp_config["mcpServers"][server.name] = entry

    output_dir = Path(path).resolve() if path else Path.cwd()
    output_path = output_dir / ".mcp.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(mcp_config, f, indent=2, ensure_ascii=False)

    _config.add_to_gitignore(output_path)
    click.echo(f"MCP configuration exported: {output_path}")


def _mcp_get_openclaw(servers: list[MCPServer], path: str | None, force: bool = False) -> None:
    """Export MCP servers in OpenClaw openclaw.json format.

    Determines output path via ``resolve_mcp_output_path()``, then merges
    ai-adapter's MCP servers into the target openclaw.json.
    """
    openclaw_path = _openclaw_output_path(path)
    data = _export_openclaw_mcp(servers)
    _merge_openclaw(openclaw_path, data, force=force)


def _mcp_get_cursor(servers: list[MCPServer], path: str | None, force: bool = False) -> None:
    """Export MCP servers in Cursor format (.cursor/mcp.json).

    Cursor is MCP-compatible, so the standard mcpServers structure is
    merged into the project's .cursor/mcp.json (preserving unmanaged servers).
    """
    cursor_path = _cursor_output_path(path)
    data = _export_cursor_mcp(servers)
    _merge_cursor_mcp(cursor_path, data, force=force)


def _mcp_get_claude_user(servers: list[MCPServer], force: bool = False) -> None:
    """Merge MCP servers into ~/.claude.json (Claude Code user scope).

    Claude Code reads user-scope MCP servers from ``~/.claude.json``'s
    ``mcpServers`` key; project scope stays in ``.mcp.json`` (standard).
    The merge preserves every non-``mcpServers`` key (project history etc.)
    and takes a ``.bak`` backup.
    """
    claude_json = _claude_user_json_path()
    data = _export_claude_mcp_user(servers)
    _merge_claude_json(claude_json, data, force=force)


def _mcp_get_codex(servers: list[MCPServer], path: str | None, force: bool = False, scope: str = "project") -> None:
    """Merge MCP servers into Codex config.toml for the given scope.

    ``--scope project`` (default) targets ``<cwd>/.codex/config.toml``,
    ``--scope user`` targets ``~/.codex/config.toml``; *path* overrides
    the project directory for project scope.  Comments and non-MCP
    sections are preserved (text-splice merge) and a ``.bak`` backup is
    taken before modifying an existing file.
    """
    project_path = Path(path).resolve() if path else None
    config_toml = _codex_config_path(scope, project_path)
    data = _export_codex_mcp(servers)
    _merge_codex_config(config_toml, data, force=force)
    if scope == "project":
        _config.add_to_gitignore(config_toml)


def _mcp_get_vscode(servers: list[MCPServer], path: str | None, force: bool = False) -> None:
    """Export MCP servers in VS Code format (.vscode/mcp.json).

    Uses the ``servers`` key with ``type: "stdio"`` entries and
    ``${env:KEY}`` env values (VS Code setting-variable syntax).
    Merge preserves unmanaged servers and takes a ``.bak`` backup.
    """
    vscode_path = _vscode_output_path(path)
    data = _export_vscode_mcp(servers)
    _merge_vscode_mcp(vscode_path, data, force=force)
    # Not gitignored — consistent with `vscode install` (QA M2b): VS Code
    # docs recommend committing .vscode/mcp.json to share servers with the
    # team.  env values use ${env:KEY} references, no secrets in file.


def _mcp_get_gemini(servers: list[MCPServer], path: str | None, force: bool = False, scope: str = "project") -> None:
    """Merge MCP servers into Gemini settings.json for the given scope.

    ``--scope project`` (default) targets ``<cwd>/.gemini/settings.json``,
    ``--scope user`` targets ``~/.gemini/settings.json``; *path* overrides
    the project directory for project scope.  Merge preserves unmanaged
    servers and non-MCP settings keys (model, theme, …) and takes a
    ``.bak`` backup (design 05 task 05-5).
    """
    project_path = Path(path).resolve() if path else None
    settings_path = _gemini_settings_path(scope, project_path)
    data = _export_gemini_mcp(servers)
    _merge_gemini_settings(settings_path, data, force=force)
    if scope == "project":
        _config.add_to_gitignore(settings_path)
    click.echo(f"MCP configuration merged into: {settings_path}")


@mcp_group.command(name="get")
@click.option(
    "--path",
    default=None,
    help="Output directory (default: current directory). "
    "With --format standard/claude: writes .mcp.json. "
    "With --format openclaw: writes openclaw.json. "
    "With --format cursor: writes .cursor/mcp.json. "
    "With --format codex: writes .codex/config.toml. "
    "With --format vscode: writes .vscode/mcp.json. "
    "With --format gemini: writes .gemini/settings.json.",
)
@click.option(
    "--format",
    "-f",
    type=click.Choice(["standard", "openclaw", "cursor", "claude", "codex", "vscode", "gemini"]),
    default="standard",
    help=(
        "Output format (standard=.mcp.json, openclaw=openclaw.json, "
        "cursor=.cursor/mcp.json, claude=.mcp.json or ~/.claude.json with --scope user, "
        "codex=.codex/config.toml or ~/.codex/config.toml with --scope user, "
        "vscode=.vscode/mcp.json, gemini=.gemini/settings.json or ~/.gemini/settings.json with --scope user)"
    ),
)
@click.option("--env", help="Filter by environment name (only export servers for this env)")
@click.option(
    "--force",
    is_flag=True,
    help="Overwrite output file without confirmation",
)
@click.option(
    "--scope",
    type=click.Choice(["project", "user"]),
    default="project",
    help=(
        "Deploy scope: project=.mcp.json (claude/standard), .codex/config.toml (codex), "
        "or .gemini/settings.json (gemini); "
        "user=~/.claude.json (claude), ~/.codex/config.toml (codex), or ~/.gemini/settings.json (gemini)"
    ),
)
def mcp_get(path: str | None, format: str, env: str | None, force: bool, scope: str) -> None:
    """Export MCP configuration to a tool-native file.

    Targets: .mcp.json, openclaw.json, .cursor/mcp.json, ~/.claude.json,
    Codex config.toml, or Gemini settings.json.
    """
    validate_claude_scope(format, scope, ignored_option="--path" if path else None)
    config = _config.load_config()
    if config is None:
        click.echo("Configuration file not found. Run ai-adapter init first.")
        return

    enabled_servers = [s for s in config.mcp_servers if s.enabled]
    if env:
        enabled_servers = [s for s in enabled_servers if s.env is None or s.env == env]
    if not enabled_servers:
        click.echo("No enabled MCP servers registered.")
        return

    if format == "claude":
        if scope == "user":
            _mcp_get_claude_user(enabled_servers, force)
        else:
            # Claude Code reads project MCP from .mcp.json — same as standard.
            _mcp_get_standard(enabled_servers, path, force)
    elif format == "codex":
        _mcp_get_codex(enabled_servers, path, force, scope)
    elif format == "openclaw":
        _mcp_get_openclaw(enabled_servers, path, force)
    elif format == "cursor":
        _mcp_get_cursor(enabled_servers, path, force)
    elif format == "vscode":
        _mcp_get_vscode(enabled_servers, path, force)
    elif format == "gemini":
        _mcp_get_gemini(enabled_servers, path, force, scope)
    else:
        _mcp_get_standard(enabled_servers, path, force)


def _import_mcp_from_file(config, json_path: str, *, force: bool = False) -> None:
    """Import MCP server configurations from a .mcp.json file."""
    with open(json_path) as f:
        data = json.load(f)

    servers_data = data.get("mcpServers", {})
    if not servers_data:
        click.echo(f"'{json_path}' has no mcpServers.", err=True)
        raise click.ClickException("Not a valid .mcp.json file.")

    loaded = 0
    updated = 0
    skipped = 0
    for name, server_data in servers_data.items():
        existing = next((s for s in config.mcp_servers if s.name == name), None)
        if existing is not None:
            if force:
                existing.command = server_data.get("command", "")
                existing.args = server_data.get("args", [])
                existing.env_keys = list(server_data.get("env", {}).keys())
                existing.enabled = server_data.get("enabled", True)
                existing.tools = []
                existing.env = None
                updated += 1
            else:
                skipped += 1
            continue

        server = MCPServer(
            name=name,
            command=server_data.get("command", ""),
            args=server_data.get("args", []),
            env_keys=list(server_data.get("env", {}).keys()),
            enabled=server_data.get("enabled", True),
            tools=[],
            env=None,
        )
        config.mcp_servers.append(server)
        loaded += 1

    _config.save_config(config)
    click.echo(f"MCP configurations imported: {loaded} added, {updated} updated, {skipped} skipped (duplicate)")


@mcp_group.command(name="remove-all")
@click.option("--force", is_flag=True, help="Delete without confirmation")
def mcp_remove_all(force: bool) -> None:
    """Remove all MCP server configurations and delete .mcp.json."""
    config = _config.load_config()
    if config is None or not config.mcp_servers:
        click.echo("No MCP servers registered.")
        return

    count = len(config.mcp_servers)
    if not force:
        click.confirm(f"Remove all MCP servers ({count})?", abort=True)

    config.mcp_servers.clear()
    _config.save_config(config)

    # Delete .mcp.json
    mcp_json = Path.cwd() / ".mcp.json"
    if mcp_json.exists():
        mcp_json.unlink()
        click.echo(".mcp.json deleted.")

    click.echo(f"All MCP servers ({count}) removed.")
