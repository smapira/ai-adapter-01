"""mcp subcommand implementation.

Manages MCP server configurations under ~/.ai-adapter/mcp/.
Exports settings in formats compatible with various tools (VS Code / Claude / Cursor / OpenClaw).
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import click

from ai_adapter import config as _config
from ai_adapter.models import MCPServer


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
@click.option("--env-key", "-e", multiple=True,
              help="Required env var keys (can be specified multiple times)")
@click.option("--tool", "-t", multiple=True,
              help="Compatible tools: vscode/claude/cursor (can be specified multiple times)")
@click.option("--env", help="Target environment")
@click.option("--file", "-f", "json_path", type=click.Path(exists=True, readable=True),
              help="Path to .mcp.json file for bulk import")
def mcp_add(
    name: str | None,
    command: str | None,
    args: tuple[str, ...],
    env_key: tuple[str, ...],
    tool: tuple[str, ...],
    env: str | None,
    json_path: str | None,
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
        _import_mcp_from_file(config, json_path)
        return

    # Interactive single-server mode
    if not name:
        click.echo("NAME is required when --file is not used.", err=True)
        raise click.ClickException("Provide NAME or use --file.")

    # Duplicate check
    for existing in config.mcp_servers:
        if existing.name == name:
            click.echo(f"MCP server '{name}' already exists.", err=True)
            raise click.ClickException(f"MCP server '{name}' is already registered.")

    if not command:
        click.echo("--command is required.", err=True)
        raise click.ClickException("--command option is required.")

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


def export_openclaw_mcp(servers: list[MCPServer]) -> dict:
    """Export MCP servers in OpenClaw format (mcp.servers array).

    Args:
        servers: List of MCP server configurations from ai-adapter.
                 Disabled servers are filtered out automatically.

    Returns:
        Dict suitable for writing to openclaw.json's mcp.servers section.
    """
    env_key_pattern = re.compile(r'^[A-Z_][A-Z0-9_]*$')

    enabled_servers = [s for s in servers if s.enabled]
    managed_names: list[str] = []
    servers_dict: dict[str, dict] = {}

    for s in enabled_servers:
        managed_names.append(s.name)
        entry: dict[str, object] = {
            "enabled": True,
            "command": s.command,
        }
        if s.args:
            entry["args"] = list(s.args)
        if s.env_keys:
            # Warn about env keys that don't match OpenClaw's strict naming pattern
            for key in s.env_keys:
                if not env_key_pattern.match(key):
                    click.echo(
                        f"Warning: env key '{key}' in server '{s.name}' may not be valid "
                        f"in OpenClaw format. OpenClaw only supports [A-Z_][A-Z0-9_]* pattern.",
                        err=True,
                    )
            entry["env"] = {k: f"${{{k}}}" for k in s.env_keys}

        servers_dict[s.name] = entry

    return {
        "x-ai-adapter": {
            "version": 1,
            "managed_mcp_servers": managed_names,
        },
        "mcp": {
            "servers": servers_dict,
        },
    }


def merge_into_openclaw_json(output_path: Path, openclaw_data: dict, force: bool = False) -> None:
    """Merge OpenClaw MCP data into an openclaw.json file.

    Reads existing file at output_path (if any), merges mcp.servers
    server-name-based (new overwrites existing, unknown existing preserved),
    writes backup before modifying.

    Args:
        output_path: Path to openclaw.json
        openclaw_data: Dict from export_openclaw_mcp()
        force: Skip confirmation prompt if True
    """
    # Load existing or start empty
    existing: dict = {}
    if output_path.exists():
        if not force:
            click.confirm(f"Overwrite MCP servers in '{output_path}'?", abort=True)
        # Create backup before modifying
        bak_path = output_path.with_suffix(output_path.suffix + ".bak")
        shutil.copy2(output_path, bak_path)
        try:
            with open(output_path) as f:
                existing = json.load(f)
        except (json.JSONDecodeError, OSError):
            existing = {}

    # Merge: existing servers not in ai-adapter are preserved
    new_servers = openclaw_data.get("mcp", {}).get("servers", {})
    existing_servers = existing.get("mcp", {}).get("servers", {})

    # Preserve servers not managed by ai-adapter
    managed_names = set(openclaw_data.get("x-ai-adapter", {}).get("managed_mcp_servers", []))
    for name in list(existing_servers.keys()):
        if name not in managed_names:
            new_servers[name] = existing_servers[name]

    # Ensure mcp struct exists
    if "mcp" not in existing:
        existing["mcp"] = {}
    existing["mcp"]["servers"] = new_servers

    # Write x-ai-adapter marker
    existing["x-ai-adapter"] = openclaw_data["x-ai-adapter"]

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)

    count = len(new_servers)
    click.echo(f"OpenClaw MCP configuration written: {output_path} ({count} servers)")


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

    Determines output path based on --path flag and ~/.openclaw/ detection,
    then merges ai-adapter's MCP servers into the target openclaw.json.
    """
    output_dir = Path(path).resolve() if path else Path.cwd()

    # Determine output path
    if path:
        openclaw_path = output_dir / "openclaw.json"
    else:
        openclaw_dir = Path.home() / ".openclaw"
        if openclaw_dir.exists():
            openclaw_path = openclaw_dir / "openclaw.json"
        else:
            click.echo(
                "Warning: OpenClaw not found (~/.openclaw/ not detected). "
                "Run 'npm install -g openclaw' first.",
                err=True,
            )
            openclaw_path = output_dir / "openclaw.json"

    data = export_openclaw_mcp(servers)
    merge_into_openclaw_json(openclaw_path, data, force=force)


@mcp_group.command(name="get")
@click.option("--path", default=None,
              help="Output directory (default: current directory). "
                   "With --format standard: writes .mcp.json. "
                   "With --format openclaw: writes openclaw.json.")
@click.option(
    "--format", "-f",
    type=click.Choice(["standard", "openclaw"]),
    default="standard",
    help="Output format (standard=.mcp.json, openclaw=openclaw.json)",
)
@click.option(
    "--force",
    is_flag=True,
    help="Overwrite output file without confirmation",
)
def mcp_get(path: str | None, format: str, force: bool) -> None:
    """Export MCP configuration to .mcp.json or openclaw.json."""
    config = _config.load_config()
    if config is None:
        click.echo("Configuration file not found. Run ai-adapter init first.")
        return

    enabled_servers = [s for s in config.mcp_servers if s.enabled]
    if not enabled_servers:
        click.echo("No enabled MCP servers registered.")
        return

    if format == "openclaw":
        _mcp_get_openclaw(enabled_servers, path, force)
    else:
        _mcp_get_standard(enabled_servers, path, force)


def _import_mcp_from_file(config, json_path: str) -> None:
    """Import MCP server configurations from a .mcp.json file."""
    with open(json_path) as f:
        data = json.load(f)

    servers_data = data.get("mcpServers", {})
    if not servers_data:
        click.echo(f"'{json_path}' has no mcpServers.", err=True)
        raise click.ClickException("Not a valid .mcp.json file.")

    loaded = 0
    skipped = 0
    for name, server_data in servers_data.items():
        # Duplicate check
        exists = any(s.name == name for s in config.mcp_servers)
        if exists:
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
    click.echo(f"MCP configurations imported: {loaded} added, {skipped} skipped (duplicate)")


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
