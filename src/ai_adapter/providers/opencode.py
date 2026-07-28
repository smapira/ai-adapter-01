"""opencode subcommand implementation.

Manages .opencode symlinks and opencode.json installation/uninstallation.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import click

from ai_adapter import config as _config
from ai_adapter.agent_format import batch_validate_and_fix, convert_agent_file


@click.group(name="opencode")
def opencode_group() -> None:
    """Manage OpenCode integration settings."""


@opencode_group.command(name="alias")
def opencode_alias() -> None:
    """Create a .opencode → .github symlink in the current directory.

    Creates a .opencode symlink pointing to the absolute path of .github/.
    Before creating the symlink, validates ``.github/agents/*.agent.md``
    files and offers to fix any format issues.
    """
    github_path = Path.cwd().resolve() / ".github"
    opencode_path = Path.cwd().resolve() / ".opencode"

    if not github_path.exists():
        click.echo(f"'.github' directory not found: {github_path}", err=True)
        raise click.ClickException(".github directory does not exist.")

    # Validate agent files before symlink creation
    agents_dir = github_path / "agents"
    if agents_dir.exists():
        errors = batch_validate_and_fix(agents_dir, fix=False)
        if errors:
            click.echo(
                "Warning: the following agent files have array-format tools (expected object format):",
                err=True,
            )
            for err in errors:
                click.echo(f"  {err}", err=True)
            click.echo("")
            if click.confirm("Fix them automatically?"):
                fixed = 0
                for f in sorted(agents_dir.iterdir()):
                    if f.is_file() and str(f).endswith(".agent.md"):
                        if convert_agent_file(f):
                            fixed += 1
                click.echo(f"Fixed {fixed} file(s).")
            else:
                raise click.ClickException("Agent file format validation failed. Run 'opencode validate --fix' to fix.")

    if opencode_path.exists() or opencode_path.is_symlink():
        click.echo("'.opencode' already exists.")
        click.confirm("Replace it?", abort=True)
        if opencode_path.is_symlink() or opencode_path.is_dir():
            import shutil

            if opencode_path.is_symlink() or opencode_path.is_file():
                opencode_path.unlink()
            else:
                shutil.rmtree(opencode_path)

    os.symlink(str(github_path), str(opencode_path))
    _config.add_to_gitignore(opencode_path.resolve())
    click.echo(f"Symlink created: {opencode_path} → {github_path}")


@opencode_group.command(name="install")
def opencode_install() -> None:
    """Generate opencode.json in the current directory.

    Dynamically builds the ``instructions`` array based on what is registered
    in ``~/.ai-adapter/config.json``:

    - Root-level agent files (``AGENTS.md``, ``CLAUDE.md``, etc.) → project root
    - ``.agent.md`` files → ``.github/agents/*.agent.md`` glob
    - ``.github/copilot-instructions.md`` → always included as fallback
    """
    cfg = _config.load_config()

    instructions: list[str] = []

    # Always include copilot-instructions.md as a standard fallback
    instructions.append(".github/copilot-instructions.md")

    if cfg:
        # Root-level instruction files (e.g., AGENTS.md, CLAUDE.md)
        if cfg.instructions:
            instructions_dir = _config.get_instructions_dir()
            for inst in cfg.instructions:
                # Find the actual filename in the store
                for f in sorted(instructions_dir.iterdir()):
                    if f.is_file() and f.stem == inst.name:
                        instructions.append(f.name)
                        break
                else:
                    # Fallback: assume name + .md
                    instructions.append(f"{inst.name}.md")

        # .agent.md files in .github/agents/
        if cfg.agents:
            instructions.append(".github/agents/*.agent.md")

        # SKILL.md files in .github/skills/
        if cfg.skills:
            instructions.append(".github/skills/*/SKILL.md")

    config = {
        "$schema": "https://opencode.ai/config.json",
        "instructions": instructions,
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

    _config.add_to_gitignore(output_path)
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


@opencode_group.command(name="validate")
@click.option(
    "--fix",
    is_flag=True,
    help="Automatically fix agent file format issues.",
)
@click.option(
    "--quiet",
    is_flag=True,
    help="Minimal output; only exit code indicates result (0 = valid).",
)
@click.option(
    "--project-dir",
    "-d",
    type=click.Path(exists=True, file_okay=False, readable=True),
    default=None,
    help="Target project directory (default: current directory)",
)
def opencode_validate(fix: bool, quiet: bool, project_dir: str | None) -> None:
    """Validate agent file formats in ``.github/agents/``.

    Checks that all ``.agent.md`` files have ``tools`` in object format
    (``tools:\n  execute: true\n  read: true``) rather than array format
    (``tools: [execute, read]``).

    Exit code: 0 if all valid, 1 if any issues found.
    """
    base_dir = Path(project_dir).resolve() if project_dir else Path.cwd()
    agents_dir = base_dir / ".github" / "agents"

    if not agents_dir.exists():
        if not quiet:
            click.echo("No .github/agents/ directory found.")
        return

    errors = batch_validate_and_fix(agents_dir, fix=fix)

    if errors:
        if not quiet:
            for err in errors:
                click.echo(err, err=True)
            if fix:
                click.echo(f"Fixed {len(errors)} file(s).")
            else:
                click.echo(
                    "Run with --fix to automatically correct format.",
                    err=True,
                )
        raise SystemExit(1)

    if not quiet:
        click.echo("All agent files are valid.")
