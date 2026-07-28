"""OpenClaw provider integration.

Handles format conversion, file I/O, and deployment logic specific to
OpenClaw (https://github.com/openclaw/openclaw) — a personal AI assistant
with a multi-channel gateway.

Supports:
- MCP server export (openclaw.json format)
- Skill deployment (~/.openclaw/skills/)
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import click

from ai_adapter.models import MCPServer

# ── Helpers ─────────────────────────────────────────────────────────────

_env_key_pattern = re.compile(r"^[A-Z_][A-Z0-9_]*$")


def _warn_invalid_env_key(key: str, server_name: str) -> None:
    """Emit warning if an env key doesn't match OpenClaw's naming rules."""
    if not _env_key_pattern.match(key):
        click.echo(
            f"Warning: env key '{key}' in server '{server_name}' may not be "
            f"valid in OpenClaw format. OpenClaw only supports "
            f"[A-Z_][A-Z0-9_]* pattern.",
            err=True,
        )


def _get_openclaw_dir() -> Path | None:
    """Return ~/.openclaw/ if it exists, else None."""
    d = Path.home() / ".openclaw"
    return d if d.exists() else None


# ── MCP ─────────────────────────────────────────────────────────────────


def export_mcp(servers: list[MCPServer]) -> dict:
    """Export MCP servers in OpenClaw format (mcp.servers array).

    Args:
        servers: List of MCP server configurations from ai-adapter.
                 Disabled servers are filtered out automatically.

    Returns:
        Dict suitable for writing to openclaw.json's mcp.servers section.
    """
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
            for key in s.env_keys:
                _warn_invalid_env_key(key, s.name)
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


def merge_into_openclaw_json(
    output_path: Path,
    openclaw_data: dict,
    force: bool = False,
) -> None:
    """Merge ai-adapter's MCP data into an openclaw.json file.

    Reads existing file at *output_path* (if any), merges ``mcp.servers``
    server-name-based (new overwrites existing, unknown existing preserved),
    writes ``.bak`` backup before modifying.

    Args:
        output_path: Path to openclaw.json.
        openclaw_data: Dict from :func:`export_mcp`.
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

    new_servers = openclaw_data.get("mcp", {}).get("servers", {})
    existing_servers = existing.get("mcp", {}).get("servers", {})

    # Preserve servers not managed by ai-adapter
    managed_names = set(
        openclaw_data.get("x-ai-adapter", {}).get("managed_mcp_servers", []),
    )
    for name in list(existing_servers.keys()):
        if name not in managed_names:
            new_servers[name] = existing_servers[name]

    if "mcp" not in existing:
        existing["mcp"] = {}
    existing["mcp"]["servers"] = new_servers
    existing["x-ai-adapter"] = openclaw_data["x-ai-adapter"]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)

    count = len(new_servers)
    click.echo(
        f"OpenClaw MCP configuration written: {output_path} ({count} servers)",
    )


def resolve_mcp_output_path(path: str | None) -> Path:
    """Determine the output path for openclaw.json.

    Priority:
    1. ``--path`` explicitly given → ``{path}/openclaw.json``
    2. ``~/.openclaw/`` exists → ``~/.openclaw/openclaw.json``
    3. Fallback → ``{cwd}/openclaw.json``
    """
    if path:
        return Path(path).resolve() / "openclaw.json"

    oc_dir = _get_openclaw_dir()
    if oc_dir is not None:
        return oc_dir / "openclaw.json"

    click.echo(
        "Warning: OpenClaw not found (~/.openclaw/ not detected). Run 'npm install -g openclaw' first.",
        err=True,
    )
    return Path.cwd() / "openclaw.json"


# ── Skills ──────────────────────────────────────────────────────────────


def get_skills_dir() -> Path | None:
    """Return the OpenClaw skills directory if OpenClaw is installed.

    Returns ``~/.openclaw/skills/`` (creating it if needed), or None if
    OpenClaw is not installed.
    """
    oc_dir = _get_openclaw_dir()
    if oc_dir is None:
        return None
    sd = oc_dir / "skills"
    sd.mkdir(parents=True, exist_ok=True)
    return sd


def deploy_skills(
    skills: list,
    skills_store_dir: Path,
    force: bool = False,
) -> None:
    """Deploy ai-adapter skills to ~/.openclaw/skills/.

    Each skill is a directory containing ``SKILL.md``.  Existing
    non-ai-adapter skills in the target directory are preserved
    (only ai-adapter managed skills are written, leaving others untouched).

    Args:
        skills: List of Skill entries from ai-adapter config.
        skills_store_dir: Path to the ai-adapter skills store.
        force: Skip confirmation prompt if True.
    """
    oc_skills_dir = get_skills_dir()
    if oc_skills_dir is None:
        click.echo(
            "Warning: OpenClaw not found (~/.openclaw/ not detected). Run 'npm install -g openclaw' first.",
            err=True,
        )

    copied = 0
    for skill_entry in skills:
        src = skills_store_dir / skill_entry.name
        if not src.exists():
            click.echo(f"   Skip: '{skill_entry.name}' directory not found.")
            continue

        if oc_skills_dir is not None:
            dest = oc_skills_dir / skill_entry.name
            if dest.exists():
                if force:
                    shutil.rmtree(dest)
                else:
                    click.confirm(
                        f"Overwrite '{skill_entry.name}' in OpenClaw skills?",
                        abort=True,
                    )
                    shutil.rmtree(dest)
            shutil.copytree(src, dest)
            copied += 1

    if oc_skills_dir is not None:
        click.echo(f"All skills ({copied}) copied to {oc_skills_dir}.")
    else:
        click.echo("No OpenClaw install detected (~/.openclaw/ not found).")
        click.echo("Nothing was written. Run 'npm install -g openclaw' first.")
