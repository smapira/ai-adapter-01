"""VS Code provider integration.

Handles MCP server export and editor configuration management for
VS Code (https://code.visualstudio.com) — specifically ``.vscode/mcp.json``
(Copilot / MCP extension) and ``.vscode/extensions.json`` (recommended
extensions).

Supports:
- MCP server export (VS Code ``servers`` format with ``type: stdio``)
- Extension recommendation management (.vscode/extensions.json)
- Configuration validation (mcp.json + extensions.json)

VS Code uses a different MCP key than Claude Code: ``servers`` instead of
``mcpServers``, and every entry requires a ``"type"`` field. Env values use
VS Code's ``${env:KEY}`` setting-variable syntax.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import click

from ai_adapter import config as _config
from ai_adapter.models import MCPServer

# ── Path resolution ─────────────────────────────────────────────────────


def resolve_mcp_output_path(path: str | None) -> Path:
    """Determine the output path for ``.vscode/mcp.json``.

    Priority:
    1. ``--path`` / ``--project-dir`` explicitly given → ``{path}/.vscode/mcp.json``
    2. Fallback → ``{cwd}/.vscode/mcp.json``
    """
    base = Path(path).resolve() if path else Path.cwd()
    return base / ".vscode" / "mcp.json"


def resolve_extensions_path(path: str | None) -> Path:
    """Determine the output path for ``.vscode/extensions.json``."""
    base = Path(path).resolve() if path else Path.cwd()
    return base / ".vscode" / "extensions.json"


# ── MCP export ──────────────────────────────────────────────────────────


def export_mcp(servers: list[MCPServer]) -> dict:
    """Export MCP servers in VS Code format (``servers`` dict + ``type: stdio``).

    VS Code's MCP extension reads ``.vscode/mcp.json`` with a ``servers``
    key (not ``mcpServers``) and requires ``"type": "stdio"`` on each entry.
    Env values use VS Code's ``${env:KEY}`` setting-variable syntax.

    Only stdio servers are exported. Servers with no command (likely
    http/sse) are skipped with a warning.

    Args:
        servers: List of MCP server configurations from ai-adapter.
                 Disabled servers are filtered out automatically.

    Returns:
        Dict suitable for writing to ``.vscode/mcp.json``.
    """
    enabled_servers = [s for s in servers if s.enabled]
    servers_dict: dict[str, dict] = {}

    for s in enabled_servers:
        if not s.command:
            click.echo(
                f"Warning: skipping non-stdio MCP server '{s.name}' "
                "(http/sse servers are not supported by VS Code export).",
                err=True,
            )
            continue
        entry: dict[str, object] = {
            "type": "stdio",
            "command": s.command,
        }
        if s.args:
            entry["args"] = list(s.args)
        if s.env_keys:
            entry["env"] = {k: f"${{env:{k}}}" for k in s.env_keys}
        servers_dict[s.name] = entry

    return {"servers": servers_dict}


def merge_into_vscode_mcp_json(
    output_path: Path,
    vscode_data: dict,
    force: bool = False,
) -> None:
    """Merge ai-adapter's MCP data into ``.vscode/mcp.json``.

    Reads the existing file at *output_path* (if any) and merges
    ``servers`` server-name-based (new overwrites existing, unknown
    existing preserved). Writes a ``.bak`` backup before modifying.

    Args:
        output_path: Path to ``.vscode/mcp.json``.
        vscode_data: Dict from :func:`export_mcp`.
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
                loaded = json.load(f)
        except (json.JSONDecodeError, OSError):
            loaded = {}
        # Guard against non-object top level / non-dict servers (review M1):
        # a structurally odd file must not crash the merge with AttributeError.
        existing = loaded if isinstance(loaded, dict) else {}

    new_servers = dict(vscode_data.get("servers", {}))
    existing_servers = existing.get("servers", {})
    if not isinstance(existing_servers, dict):
        existing_servers = {}

    # Preserve servers not exported by ai-adapter (same-name is overwritten)
    managed_names = set(new_servers.keys())
    for name, existing_entry in existing_servers.items():
        if name not in managed_names:
            new_servers[name] = existing_entry

    existing["servers"] = new_servers

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)

    count = len(new_servers)
    click.echo("VS Code MCP configuration installed:")
    click.echo(f"  {output_path}")
    click.echo(f"  ({count} servers)")


# ── Extension recommendations ───────────────────────────────────────────


def load_extension_recommendations(ext_path: Path) -> list[str]:
    """Load the recommendations list from ``.vscode/extensions.json``.

    Returns an empty list when the file is missing or unreadable.
    """
    if not ext_path.is_file():
        return []
    try:
        data = json.loads(ext_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(data, dict):
        return []
    recommendations = data.get("recommendations", [])
    if not isinstance(recommendations, list):
        return []
    return [str(r) for r in recommendations]


def save_extension_recommendations(ext_path: Path, recommendations: list[str]) -> None:
    """Write the recommendations list to ``.vscode/extensions.json``.

    Preserves every other top-level key (e.g. ``unwantedRecommendations``)
    — only ``recommendations`` is replaced (review C1).  A ``.bak`` backup
    is taken before modifying an existing file; a corrupt file aborts
    instead of being silently overwritten.
    """
    data: dict = {}
    if ext_path.exists():
        bak_path = ext_path.with_suffix(ext_path.suffix + ".bak")
        shutil.copy2(ext_path, bak_path)
        try:
            loaded = json.loads(ext_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise click.ClickException(
                f"Cannot update '{ext_path}': file is not valid JSON ({exc}). "
                "Fix or remove the file first — refusing to overwrite VS Code settings."
            ) from exc
        if isinstance(loaded, dict):
            data = loaded
        else:
            raise click.ClickException(f"Cannot update '{ext_path}': top-level JSON value is not an object.")
    data["recommendations"] = recommendations
    ext_path.parent.mkdir(parents=True, exist_ok=True)
    with open(ext_path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ── Validation ──────────────────────────────────────────────────────────


def validate_vscode_mcp(path: Path) -> list[str]:
    """Validate ``.vscode/mcp.json`` structure.

    Checks: valid JSON, top-level object, ``servers`` key is an object,
    and each server entry is an object with ``command`` or ``url``.

    Returns a list of error messages (empty when valid).
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return [f"{path.name}: not valid JSON: {exc}"]

    if not isinstance(data, dict):
        return [f"{path.name}: must be a JSON object"]

    servers = data.get("servers")
    if servers is None:
        return [f"{path.name}: missing 'servers' key"]
    if not isinstance(servers, dict):
        return [f"{path.name}: 'servers' must be an object"]

    errors: list[str] = []
    for name, entry in servers.items():
        if not isinstance(entry, dict):
            errors.append(f"{path.name}: servers.{name} must be an object")
            continue
        if "command" not in entry and "url" not in entry:
            errors.append(f"{path.name}: servers.{name} must have 'command' or 'url'")
    return errors


def validate_extensions(path: Path) -> list[str]:
    """Validate ``.vscode/extensions.json`` structure.

    Checks: valid JSON, top-level object, ``recommendations`` is an array
    when present.

    Returns a list of error messages (empty when valid).
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return [f"{path.name}: not valid JSON: {exc}"]

    if not isinstance(data, dict):
        return [f"{path.name}: must be a JSON object"]

    recommendations = data.get("recommendations")
    if recommendations is not None and not isinstance(recommendations, list):
        return [f"{path.name}: 'recommendations' must be an array"]
    return []


# ── CLI group ───────────────────────────────────────────────────────────


@click.group(name="vscode")
def vscode_group() -> None:
    """Manage VS Code editor configuration (.vscode/)."""


@vscode_group.command(name="install")
@click.option("--force", is_flag=True, help="Overwrite existing mcp.json without prompting")
@click.option(
    "--project-dir",
    "-d",
    type=click.Path(exists=True, file_okay=False, readable=True),
    default=None,
    help="Target project directory (default: current directory)",
)
def vscode_install(force: bool, project_dir: str | None) -> None:
    """Generate .vscode/mcp.json from registered MCP servers.

    Reads enabled MCP servers from ~/.ai-adapter/ and exports them in
    VS Code format (servers key + type: stdio). Existing files are merged
    with a .bak backup.
    """
    config = _config.load_config()
    if config is None:
        click.echo("Configuration file not found. Run ai-adapter init first.")
        return

    enabled_servers = [s for s in config.mcp_servers if s.enabled]
    if not enabled_servers:
        click.echo("No MCP servers registered.")
        return

    output_path = resolve_mcp_output_path(project_dir)
    data = export_mcp(enabled_servers)
    merge_into_vscode_mcp_json(output_path, data, force=force)
    # Not gitignored: VS Code docs recommend committing .vscode/mcp.json to
    # share MCP servers with the team (review M2).  env values use ${env:KEY}
    # references, so no secrets are written to the file.


@vscode_group.group(name="extension")
def vscode_extension_group() -> None:
    """Manage VS Code extension recommendations (.vscode/extensions.json)."""


@vscode_extension_group.command(name="add")
@click.argument("extension_id")
@click.option(
    "--project-dir",
    "-d",
    type=click.Path(exists=True, file_okay=False, readable=True),
    default=None,
    help="Target project directory (default: current directory)",
)
def vscode_extension_add(extension_id: str, project_dir: str | None) -> None:
    """Add an extension to .vscode/extensions.json recommendations.

    EXTENSION_ID: VS Code extension identifier (e.g. ms-vscode.copilot-chat).
    """
    ext_path = resolve_extensions_path(project_dir)
    recommendations = load_extension_recommendations(ext_path)

    if extension_id in recommendations:
        click.echo("Extension already recommended.")
        return

    recommendations.append(extension_id)
    save_extension_recommendations(ext_path, recommendations)
    click.echo(f"Extension '{extension_id}' added to {ext_path}.")


@vscode_extension_group.command(name="list")
@click.option(
    "--project-dir",
    "-d",
    type=click.Path(exists=True, file_okay=False, readable=True),
    default=None,
    help="Target project directory (default: current directory)",
)
def vscode_extension_list(project_dir: str | None) -> None:
    """List recommended extensions from .vscode/extensions.json."""
    ext_path = resolve_extensions_path(project_dir)
    if not ext_path.is_file():
        click.echo("No extensions.json found.")
        return

    recommendations = load_extension_recommendations(ext_path)
    if not recommendations:
        click.echo("No extensions recommended.")
        return

    click.echo("Recommended extensions:")
    for ext in recommendations:
        click.echo(f"  - {ext}")


@vscode_group.command(name="validate")
@click.option("--json", "as_json", is_flag=True, help="Output the report as JSON")
@click.option(
    "--project-dir",
    "-d",
    type=click.Path(exists=True, file_okay=False, readable=True),
    default=None,
    help="Target project directory (default: current directory)",
)
def vscode_validate(as_json: bool, project_dir: str | None) -> None:
    """Validate .vscode/mcp.json and .vscode/extensions.json.

    Exit code: 0 if all valid, 1 if any errors found.
    """
    base_dir = Path(project_dir).resolve() if project_dir else Path.cwd()
    all_errors: list[str] = []

    mcp_path = base_dir / ".vscode" / "mcp.json"
    if mcp_path.is_file():
        all_errors.extend(validate_vscode_mcp(mcp_path))

    ext_path = base_dir / ".vscode" / "extensions.json"
    if ext_path.is_file():
        all_errors.extend(validate_extensions(ext_path))

    if as_json:
        click.echo(json.dumps({"valid": not all_errors, "errors": all_errors}, indent=2))
    elif all_errors:
        for err in all_errors:
            click.echo(err, err=True)
    else:
        click.echo("VS Code configuration is valid.")

    if all_errors:
        raise SystemExit(1)
