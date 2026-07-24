"""bin subcommand implementation.

Manages script files under ~/.ai-adapter/bin/.
Auto-resolves env via environment resolution logic when omitted.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import click

from ai_adapter.config import (
    get_bins_dir,
    get_github_bins_dir,
    load_config,
    save_config,
)
from ai_adapter.models import Bin, Config


def resolve_env(config: Config, env_arg: str | None, agent_name: str | None = None) -> str:
    """Resolve env when the argument is omitted.
    Order: agent binding -> default environment.

    Args:
        config: Config object.
        env_arg: Explicitly specified env name (None means resolution needed).
        agent_name: Current agent name (optional).

    Returns:
        Resolved environment name.
    """
    if env_arg:
        return env_arg
    if agent_name:
        for binding in config.agent_bindings:
            if binding.agent == agent_name:
                return binding.env
    return config.default_env


@click.group(name="bin")
def bin_group() -> None:
    """Manage script files."""


@bin_group.command(name="list")
@click.option("--env", "-e", default=None, help="Environment name (default: show all environments)")
def bin_list(env: str | None) -> None:
    """List scripts.

    Use --env to filter by environment name.
    """
    config = load_config()
    if config is None:
        click.echo("Configuration file not found. Run ai-adapter init first.")
        return

    if not config.bins:
        click.echo("No scripts registered.")
        return

    if env:
        filtered = [b for b in config.bins if b.env == env]
        if not filtered:
            click.echo(f"Environment '{env}' has no scripts registered.")
            return
        click.echo(f"Scripts (env: {env}):")
        click.echo("-" * 40)
        for b in filtered:
            desc = f" - {b.description}" if b.description else ""
            click.echo(f"  {b.name}{desc}")
    else:
        click.echo("All Scripts:")
        click.echo("-" * 40)
        for b in config.bins:
            desc = f" - {b.description}" if b.description else ""
            click.echo(f"  [{b.env}] {b.name}{desc}")


@bin_group.command(name="add")
@click.argument("path", type=click.Path(exists=True, readable=True))
@click.option("--env", "-e", default=None, help="Environment name (auto-resolved when omitted)")
@click.option("--description", "-d", default="", help="Script description")
@click.option("--agent", help="Agent name (for env resolution)")
def bin_add(path: str, env: str | None, description: str, agent: str | None) -> None:
    """Add a script to ~/.ai-adapter/bin/.

    PATH: Path to the script file to add.

    When --env is omitted, auto-resolves via environment resolution logic.
    """
    config = load_config()
    if config is None:
        click.echo("Configuration file not found. Run ai-adapter init first.")
        return

    resolved_env = resolve_env(config, env, agent)
    src = Path(path).resolve()
    bins_dir = get_bins_dir()
    bins_dir.mkdir(parents=True, exist_ok=True)

    dest = bins_dir / src.name

    if dest.exists():
        click.confirm(f"'{dest.name}' already exists. Overwrite?", abort=True)

    shutil.copy2(src, dest)
    click.echo(f"Script '{src.name}' added (env: {resolved_env}): {dest}")

    # Duplicate check
    for existing in config.bins:
        if existing.name == src.name and existing.env == resolved_env:
            save_config(config)
            return

    config.bins.append(Bin(name=src.name, env=resolved_env, description=description))
    save_config(config)


@bin_group.command(name="add-rec")
@click.argument("dir_path", type=click.Path(exists=True, file_okay=False, readable=True))
@click.option("--env", "-e", default=None, help="Environment name (auto-resolved when omitted)")
@click.option("--agent", help="Agent name (for env resolution)")
def bin_add_rec(dir_path: str, env: str | None, agent: str | None) -> None:
    """Recursively register all scripts in a directory."""
    config = load_config()
    if config is None:
        click.echo("Configuration file not found. Run ai-adapter init first.")
        return

    resolved_env = resolve_env(config, env, agent)
    src_dir = Path(dir_path).resolve()
    bins_dir = get_bins_dir()
    bins_dir.mkdir(parents=True, exist_ok=True)

    added = 0
    for f in sorted(src_dir.rglob("*")):
        if not f.is_file():
            continue
        dest = bins_dir / f.name
        config.bins = [b for b in config.bins if b.name != f.name]
        shutil.copy2(f, dest)
        config.bins.append(Bin(name=f.name, env=resolved_env))
        added += 1

    save_config(config)
    click.echo(f"Scripts added: {added}")


@bin_group.command(name="get")
@click.argument("name")
@click.option("--env", "-e", default=None, help="Environment name (auto-resolved when omitted)")
@click.option("--agent", help="Agent name (for env resolution)")
@click.option(
    "--project-dir", "-d",
    type=click.Path(exists=True, file_okay=False, readable=True),
    default=None,
    help="Target project directory (default: current directory)",
)
def bin_get(name: str, env: str | None, agent: str | None, project_dir: str | None) -> None:
    """Copy script to .github/bin/.

    NAME: Name of the script to retrieve.

    When --env is omitted, auto-resolves via environment resolution logic.
    """
    config = load_config()
    if config is None:
        click.echo("Configuration file not found. Run ai-adapter init first.")
        return

    resolved_env = resolve_env(config, env, agent)

    # Search from config
    bin_entry = None
    for b in config.bins:
        if b.name == name and b.env == resolved_env:
            bin_entry = b
            break

    if bin_entry is None:
        click.echo(f"Script '{name}' (env: {resolved_env}) is not registered.", err=True)
        raise click.ClickException(f"Script '{name}' not found.")

    bins_dir = get_bins_dir()
    src = bins_dir / name
    if not src.exists():
        click.echo(f"File '{src}' not found.", err=True)
        raise click.ClickException(f"File '{name}' does not exist in ~/.ai-adapter/bin/.")

    project_path = Path(project_dir).resolve() if project_dir else None
    github_dir = get_github_bins_dir(project_path)
    github_dir.mkdir(parents=True, exist_ok=True)

    dest = github_dir / name
    shutil.copy2(src, dest)
    click.echo(f"Script '{name}' copied to {dest}.")


@bin_group.command(name="get-all")
@click.option("--env", "-e", default=None, help="Environment name (default: show all)")
@click.option(
    "--project-dir", "-d",
    type=click.Path(exists=True, file_okay=False, readable=True),
    default=None,
    help="Target project directory (default: current directory)",
)
def bin_get_all(env: str | None, project_dir: str | None) -> None:
    """Copy all registered scripts to .github/bin/ (--env to filter)."""
    config = load_config()
    if config is None or not config.bins:
        click.echo("No scripts registered.")
        return

    bins_dir = get_bins_dir()
    project_path = Path(project_dir).resolve() if project_dir else None
    github_dir = get_github_bins_dir(project_path)
    github_dir.mkdir(parents=True, exist_ok=True)

    targets = config.bins
    if env:
        targets = [b for b in targets if b.env == env]

    copied = 0
    for bin_entry in targets:
        src = bins_dir / bin_entry.name
        if not src.exists():
            click.echo(f"   Skip: '{bin_entry.name}'  file not found.")
            continue
        dest = github_dir / bin_entry.name
        shutil.copy2(src, dest)
        copied += 1

    env_info = f" (env: {env})" if env else ""
    click.echo(f"All scripts ({copied}){env_info} copied to {github_dir}.")


@bin_group.command(name="remove")
@click.argument("name")
@click.option("--env", "-e", default=None, help="Environment name (auto-resolved when omitted)")
@click.option("--agent", help="Agent name (for env resolution)")
def bin_remove(name: str, env: str | None, agent: str | None) -> None:
    """Unregister a script (does not delete the file).

    NAME: Script name to remove.

    When --env is omitted, auto-resolves via environment resolution logic.
    """
    config = load_config()
    if config is None:
        click.echo("Configuration file not found. Run ai-adapter init first.")
        return

    resolved_env = resolve_env(config, env, agent)

    # Remove from config
    found = None
    for b in config.bins:
        if b.name == name and b.env == resolved_env:
            found = b
            break

    if found is None:
        click.echo(f"Script '{name}' (env: {resolved_env}) is not registered.", err=True)
        raise click.ClickException(f"Script '{name}' not found.")

    config.bins.remove(found)
    save_config(config)

    # Also delete from .github/bin/
    github_dir = get_github_bins_dir()
    target = github_dir / name
    if target.exists():
        target.unlink()
        click.echo(f"Removed {name} from .github/bin/.")

    click.echo(f"Script '{name}' (env: {resolved_env}) unregistered.")


@bin_group.command(name="remove-all")
@click.option("--force", is_flag=True, help="Delete without confirmation prompt")
def bin_remove_all(force: bool) -> None:
    """Unregister all scripts (files are not deleted)."""
    config = load_config()
    if config is None or not config.bins:
        click.echo("No scripts registered.")
        return

    count = len(config.bins)
    if not force:
        click.confirm(f"Unregister all scripts ({count})?", abort=True)

    config.bins.clear()
    save_config(config)
    click.echo(f"All scripts ({count}) unregistered.")


@bin_group.command(name="add-path")
@click.option("--shell", default=None,
              type=click.Choice(["zshrc", "bash_profile", "bashrc"], case_sensitive=False),
              help="Shell config file (interactive selection when omitted)")
def bin_add_path(shell: str | None) -> None:
    """Add current project .github/bin to PATH."""
    github_bin = Path.cwd() / ".github" / "bin"

    if not github_bin.exists():
        click.echo(f"'.github/bin' directory not found: {github_bin}")
        click.echo("Run ai-adapter bin get <name> or ai-adapter bin get-all to deploy scripts first.")
        return

    export_line = f'export PATH="$PATH:{github_bin.resolve()}"'

    home = Path.home()
    shell_configs = {
        "zshrc": home / ".zshrc",
        "bash_profile": home / ".bash_profile",
        "bashrc": home / ".bashrc",
    }

    chosen = None
    if shell:
        chosen = shell.lower()
    else:
        click.echo()
        click.echo(f"Add the following line to your shell config to run scripts by short name:")
        click.echo(f"  {export_line}")
        click.echo()
        click.echo("Select a shell config file:")
        for i, (key, path) in enumerate(shell_configs.items(), 1):
            exists_mark = " ✓" if path.exists() else ""
            click.echo(f"  {i}) {key} ({path}{exists_mark})")
        click.echo("  4) Display only (do not auto-add)")
        click.echo()
        choice = click.prompt("Choose a number", type=int, default=4)

        if 1 <= choice <= 3:
            chosen = list(shell_configs.keys())[choice - 1]

    if chosen and chosen in shell_configs:
        config_path = shell_configs[chosen]
        config_path.parent.mkdir(parents=True, exist_ok=True)

        if config_path.exists():
            content = config_path.read_text()
            if export_line in content:
                click.echo(f"Already configured: {config_path}")
                click.echo(f"  {export_line}")
                return

        with open(config_path, "a") as f:
            f.write(f"\n# ai-adapter PATH\n{export_line}\n")

        click.echo(f"PATH setting added: {config_path}")
        click.echo(f"  {export_line}")
        click.echo("To apply, restart your shell or run:")
        click.echo(f"  source {config_path}")
    else:
        click.echo("Add the following line to ~/.zshrc etc.:")
        click.echo(f"  {export_line}")
