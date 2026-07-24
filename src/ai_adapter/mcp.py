"""mcp subcommand implementation.

Manages MCP server configurations under ~/.ai-adapter/mcp/.
Exports settings in formats compatible with various tools (VS Code / Claude / Cursor).
"""

from __future__ import annotations

import json
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
@click.argument("name")
@click.option("--command", "-c", help="Command to execute")
@click.option("--args", "-a", multiple=True, help="Command arguments (can be specified multiple times)")
@click.option("--env-key", "-e", multiple=True, help="Required environment variable keys (can be specified multiple times)")
@click.option("--tool", "-t", multiple=True, help="Compatible tools: vscode/claude/cursor (can be specified multiple times)")
@click.option("--env", help="Target environment")
def mcp_add(
    name: str,
    command: str | None,
    args: tuple[str, ...],
    env_key: tuple[str, ...],
    tool: tuple[str, ...],
    env: str | None,
) -> None:
    """Add an MCP server configuration.

    NAME: MCP server name.
    """
    config = _config.load_config()
    if config is None:
        click.echo("Configuration file not found. Run ai-adapter init first.")
        return

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


@mcp_group.command(name="export")
@click.option("--path", default=None,
              help="Output directory (default: current directory)")
def mcp_export(path: str | None) -> None:
    """Export MCP configuration to .mcp.json."""
    config = _config.load_config()
    if config is None:
        click.echo("Configuration file not found. Run ai-adapter init first.")
        return

    enabled_servers = [s for s in config.mcp_servers if s.enabled]

    mcp_config: dict = {"mcpServers": {}}
    for server in enabled_servers:
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

    click.echo(f"MCP configuration exported: {output_path}")


@mcp_group.command(name="load")
@click.option("--file", "-f", "json_path", type=click.Path(exists=True, readable=True),
              default=".mcp.json",
              help="Path to .mcp.json file (default: .mcp.json)")
def mcp_load(json_path: str) -> None:
    """Load MCP server configurations from .mcp.json."""
    config = _config.load_config()
    if config is None:
        click.echo("Configuration file not found. Run ai-adapter init first.")
        return

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
    click.echo(f"MCP server configurations loaded: {loaded} added, {skipped} skipped (duplicate)")


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
        click.echo(f".mcp.json deleted.")

    click.echo(f"All MCP servers ({count}) removed.")
