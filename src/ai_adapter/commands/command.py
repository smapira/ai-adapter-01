"""command subcommand implementation.

Manages command files under ~/.ai-adapter/commands/.
Supports --env for environment-scoped registration and filtering.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import click

from ai_adapter.config import (
    add_to_gitignore,
    get_commands_dir,
    get_github_commands_dir,
    load_config,
    resolve_env,
    save_config,
)
from ai_adapter.models import Command


@click.group(name="command")
def command_group() -> None:
    """Manage command definitions."""


@command_group.command(name="list")
@click.option("--env", "-e", default=None, help="Filter by environment name")
def command_list(env: str | None) -> None:
    """List registered commands."""
    config = load_config()
    if config is None:
        click.echo("Configuration file not found. Run ai-adapter init first.")
        return

    if not config.commands:
        click.echo("No commands registered.")
        return

    commands = config.commands
    if env:
        commands = [c for c in commands if c.env is None or c.env == env]

    if not commands:
        click.echo(f"No commands registered for environment '{env}'.")
        return

    if env:
        click.echo(f"Commands (env: {env}):")
    else:
        click.echo("Commands:")
    click.echo("-" * 40)
    for cmd in commands:
        env_info = f" [{cmd.env}]" if cmd.env else ""
        desc = f" - {cmd.description}" if cmd.description else ""
        click.echo(f"  {cmd.name}{env_info}{desc}")


@command_group.command(name="add")
@click.argument("path", type=click.Path(exists=True, readable=True))
@click.option("--env", "-e", default=None, help="Environment name (auto-resolved when omitted)")
@click.option("--agent", help="Agent name (for env resolution)")
def command_add(path: str, env: str | None, agent: str | None) -> None:
    """Add a command file to ~/.ai-adapter/commands/.

    When --env is omitted, auto-resolves via environment resolution logic.
    """
    src = Path(path).resolve()
    commands_dir = get_commands_dir()
    commands_dir.mkdir(parents=True, exist_ok=True)

    name = src.stem
    dest = commands_dir / src.name

    if dest.exists():
        click.confirm(f"'{dest.name}' already exists. Overwrite?", abort=True)

    shutil.copy2(src, dest)
    content = src.read_text(encoding="utf-8")[:200]

    config = load_config()
    if config is None:
        click.echo("Configuration file not found. Run ai-adapter init first.")
        return

    resolved_env = resolve_env(config, env, agent)
    click.echo(f"Command '{name}' added (env: {resolved_env}): {dest}")

    for existing in config.commands:
        if existing.name == name and (existing.env is None or existing.env == resolved_env):
            existing.content = content
            save_config(config)
            return

    config.commands.append(Command(name=name, content=content, env=resolved_env))
    save_config(config)


def _find_command_by_name(commands_dir: Path, name: str) -> Path | None:
    """Find a command file by name."""
    # 1. Exact match
    exact = commands_dir / name
    if exact.exists() and exact.is_file():
        return exact

    # 2. Search with extension
    for f in sorted(commands_dir.iterdir()):
        if f.is_file() and f.stem == name:
            return f

    return None


@command_group.command(name="get")
@click.argument("name")
@click.option("--env", "-e", default=None, help="Environment name (auto-resolved when omitted)")
@click.option("--agent", help="Agent name (for env resolution)")
@click.option("--project-dir", "-d", type=click.Path(exists=True, file_okay=False, readable=True), default=None)
def command_get(name: str, env: str | None, agent: str | None, project_dir: str | None) -> None:
    """Copy command to .github/commands/.

    When --env is omitted, auto-resolves via environment resolution logic.
    """
    commands_dir = get_commands_dir()
    src = _find_command_by_name(commands_dir, name)

    if src is None:
        click.echo(f"Command '{name}' not found.", err=True)
        raise click.ClickException(f"Command '{name}' is not registered.")

    project_path = Path(project_dir).resolve() if project_dir else None
    github_dir = get_github_commands_dir(project_path)
    github_dir.mkdir(parents=True, exist_ok=True)

    dest = github_dir / src.name
    shutil.copy2(src, dest)
    add_to_gitignore(dest)
    click.echo(f"Command '{name}' copied to {dest}.")


@command_group.command(name="remove")
@click.argument("name")
@click.option("--env", "-e", default=None, help="Environment name (auto-resolved when omitted)")
@click.option("--agent", help="Agent name (for env resolution)")
def command_remove(name: str, env: str | None, agent: str | None) -> None:
    """Remove a command.

    When --env is omitted, auto-resolves via environment resolution logic.
    """
    config = load_config()
    if config is None:
        return

    resolved_env = resolve_env(config, env, agent)

    found = None
    for cmd in config.commands:
        if cmd.name == name and (cmd.env is None or cmd.env == resolved_env):
            found = cmd
            break

    if found is None:
        click.echo(f"Command '{name}' (env: {resolved_env}) is not registered.", err=True)
        raise click.ClickException(f"Command '{name}' not found.")

    config.commands.remove(found)
    save_config(config)

    commands_dir = get_commands_dir()
    for f in commands_dir.iterdir():
        if f.stem == name or f.name == name:
            f.unlink()
            click.echo(f"File {f.name} deleted.")
            break

    # Also delete from .github/commands/
    github_dir = get_github_commands_dir()
    if github_dir.exists():
        for f in github_dir.iterdir():
            if f.stem == name or f.name == name:
                f.unlink()
                break

    click.echo(f"Command '{name}' removed.")


@command_group.command(name="add-rec")
@click.argument("dir_path", type=click.Path(exists=True, file_okay=False, readable=True))
@click.option("--env", "-e", default=None, help="Environment name (auto-resolved when omitted)")
@click.option("--agent", help="Agent name (for env resolution)")
def command_add_rec(dir_path: str, env: str | None, agent: str | None) -> None:
    """Recursively add all files in a directory to ~/.ai-adapter/commands/."""
    src_dir = Path(dir_path).resolve()
    commands_dir = get_commands_dir()
    commands_dir.mkdir(parents=True, exist_ok=True)

    config = load_config()
    if config is None:
        click.echo("Configuration file not found. Run ai-adapter init first.")
        return

    resolved_env = resolve_env(config, env, agent)
    added = 0
    for f in sorted(src_dir.rglob("*")):
        if not f.is_file():
            continue
        dest = commands_dir / f.name
        config.commands = [c for c in config.commands if c.name != f.stem or c.env != resolved_env]
        shutil.copy2(f, dest)
        content = f.read_text(encoding="utf-8")[:200]
        config.commands.append(Command(name=f.stem, content=content, env=resolved_env))
        added += 1

    save_config(config)
    click.echo(f"Commands added: {added}")


@command_group.command(name="get-all")
@click.option("--env", "-e", default=None, help="Filter by environment name")
@click.option("--project-dir", "-d", type=click.Path(exists=True, file_okay=False, readable=True), default=None)
def command_get_all(env: str | None, project_dir: str | None) -> None:
    """Copy all registered commands to .github/commands/."""
    config = load_config()
    if config is None or not config.commands:
        click.echo("No commands registered.")
        return

    commands_dir = get_commands_dir()
    project_path = Path(project_dir).resolve() if project_dir else None
    github_dir = get_github_commands_dir(project_path)
    github_dir.mkdir(parents=True, exist_ok=True)

    targets = config.commands
    if env:
        targets = [c for c in targets if c.env is None or c.env == env]

    copied = 0
    for cmd_entry in targets:
        src = _find_command_by_name(commands_dir, cmd_entry.name)
        if src is None:
            click.echo(f"   Skip: '{cmd_entry.name}' file not found.")
            continue
        dest = github_dir / src.name
        shutil.copy2(src, dest)
        add_to_gitignore(dest)
        copied += 1

    click.echo(f"All commands ({copied}) copied to {github_dir}.")


@command_group.command(name="remove-all")
@click.option("--env", "-e", default=None, help="Remove only commands for this environment")
@click.option("--force", is_flag=True, help="Delete without confirmation")
def command_remove_all(env: str | None, force: bool) -> None:
    """Remove all registered commands (or only commands matching --env)."""
    config = load_config()
    if config is None or not config.commands:
        click.echo("No commands registered.")
        return

    targets = config.commands
    if env:
        targets = [c for c in targets if c.env == env]
        if not targets:
            click.echo(f"No commands registered for environment '{env}'.")
            return

    count = len(targets)
    if not force:
        click.confirm(f"Remove {count} command(s)?", abort=True)

    if env:
        config.commands = [c for c in config.commands if c.env != env]
    else:
        config.commands.clear()
    save_config(config)
    click.echo(f"Removed {count} command(s).")
