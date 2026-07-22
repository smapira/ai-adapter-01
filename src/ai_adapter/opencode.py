"""opencode subcommand implementation.

Manages .opencode symlinks and opencode.json installation/uninstallation.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import click

from ai_adapter import config as _config


@click.group(name="opencode")
def opencode_group() -> None:
    """Manage OpenCode integration settings."""


@opencode_group.command(name="alias")
def opencode_alias() -> None:
    """Create a .opencode → .github symlink in the current directory.

    Creates a .opencode symlink pointing to the absolute path of .github/.
    """
    github_path = Path.cwd().resolve() / ".github"
    opencode_path = Path.cwd().resolve() / ".opencode"

    if not github_path.exists():
        click.echo(f"'.github' directory not found: {github_path}", err=True)
        raise click.ClickException(".github directory does not exist.")

    if opencode_path.exists() or opencode_path.is_symlink():
        click.echo(f"'.opencode' already exists.")
        click.confirm("Replace it?", abort=True)
        if opencode_path.is_symlink() or opencode_path.is_dir():
            import shutil
            if opencode_path.is_symlink() or opencode_path.is_file():
                opencode_path.unlink()
            else:
                shutil.rmtree(opencode_path)

    os.symlink(str(github_path), str(opencode_path))
    click.echo(f"Symlink created: {opencode_path} → {github_path}")


@opencode_group.command(name="install")
def opencode_install() -> None:
    """Generate opencode.json in the current directory."""
    config = {
        "$schema": "https://opencode.ai/config.json",
        "instructions": [
            ".github/copilot-instructions.md",
            ".github/agents/*.agent.md",
        ],
        "permission": {
            "execute": "ask",
            "read": "ask",
            "edit": "ask",
            "search": "ask",
            "agent": "ask",
            "browser": "ask",
            "web": "ask",
            "todo": "ask",
        },
    }
    output_path = Path.cwd() / "opencode.json"

    with open(output_path, "w") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    click.echo(f"opencode.json generated: {output_path}")


@opencode_group.command(name="uninstall")
def opencode_uninstall() -> None:
    """Remove opencode.json from the current directory."""
    output_path = Path.cwd() / "opencode.json"

    if not output_path.exists():
        click.echo("opencode.json not found.")
        return

    output_path.unlink()
    click.echo(f"opencode.json removed: {output_path}")
