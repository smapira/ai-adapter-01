"""env subcommand implementation.

Manages environment names in config.json.
Handles default environment settings and agent-to-environment bindings.
"""

from __future__ import annotations

import click

from ai_adapter.config import load_config, save_config
from ai_adapter.models import AgentBinding, Env


@click.group(name="env")
def env_group() -> None:
    """Manage environment settings."""


@env_group.command(name="list")
def env_list() -> None:
    """List environments (default marked with *)."""
    config = load_config()
    if config is None:
        click.echo("Configuration file not found. Run ai-adapter init first.")
        return

    if not config.envs:
        click.echo("No environments registered.")
        return

    click.echo("Environments:")
    click.echo("-" * 40)
    for env in config.envs:
        default_mark = " *" if env.name == config.default_env else " "
        desc = f" - {env.description}" if env.description else ""
        click.echo(f"  {default_mark}{env.name}{desc}")


@env_group.command(name="add")
@click.argument("name")
@click.option("--description", "-d", default="", help="Environment description")
def env_add(name: str, description: str) -> None:
    """Add a new environment.

    NAME: Name of the environment to add.
    """
    config = load_config()
    if config is None:
        click.echo("Configuration file not found. Run ai-adapter init first.")
        return

    # Duplicate check
    for env in config.envs:
        if env.name == name:
            click.echo(f"Environment '{name}' already exists.", err=True)
            raise click.ClickException(f"Environment '{name}' is already registered.")

    config.envs.append(Env(name=name, description=description))
    save_config(config)
    click.echo(f"Environment '{name}' added.")


@env_group.command(name="remove")
@click.argument("name")
@click.option("--force", is_flag=True, help="Force removal even if referenced by bins")
def env_remove(name: str, force: bool) -> None:
    """Remove an environment.

    NAME: Name of the environment to remove. Default environment cannot be removed.
    """
    config = load_config()
    if config is None:
        click.echo("Configuration file not found. Run ai-adapter init first.")
        return

    # Default environment cannot be removed
    if name == config.default_env:
        click.echo(f"Default environment '{name}' cannot be removed.", err=True)
        raise click.ClickException("Default environment cannot be removed. Use set-default to change it first.")

    # Existence check
    target = None
    for env in config.envs:
        if env.name == name:
            target = env
            break

    if target is None:
        click.echo(f"Environment '{name}' is not registered.", err=True)
        raise click.ClickException(f"Environment '{name}' not found.")

    # Check references in bins
    ref_bins = [b for b in config.bins if b.env == name]
    if ref_bins and not force:
        click.echo(
            f"Environment '{name}' is referenced by {len(ref_bins)} bin(s). Use --force to force removal."
            f" Use --force to force removal.",
            err=True,
        )
        raise click.ClickException("Cannot remove environment referenced by bins. Use --force.")

    config.envs.remove(target)

    # Also remove agent associations
    config.agent_bindings = [
        b for b in config.agent_bindings if b.env != name
    ]

    save_config(config)
    click.echo(f"Environment '{name}' removed.")


@env_group.command(name="default")
def env_default() -> None:
    """Show the current default environment name."""
    config = load_config()
    if config is None:
        click.echo("Configuration file not found. Run ai-adapter init first.")
        return

    click.echo(f"Default environment: {config.default_env}")


@env_group.command(name="set-default")
@click.argument("name")
def env_set_default(name: str) -> None:
    """Change the default environment.

    NAME: Name of the environment to set as default.
    """
    config = load_config()
    if config is None:
        click.echo("Configuration file not found. Run ai-adapter init first.")
        return

    # Existence check
    found = any(env.name == name for env in config.envs)
    if not found:
        click.echo(f"Environment '{name}' is not registered.", err=True)
        raise click.ClickException(f"Environment '{name}' not found.")

    config.default_env = name
    save_config(config)
    click.echo(f"Default environment changed to '{name}'.")


@env_group.command(name="link-agent")
@click.argument("agent")
@click.argument("env")
def env_link_agent(agent: str, env: str) -> None:
    """Bind an agent name to an environment.

    AGENT: Agent name.
    ENV: Environment name to bind.
    """
    config = load_config()
    if config is None:
        click.echo("Configuration file not found. Run ai-adapter init first.")
        return

    # Environment existence check
    env_found = any(e.name == env for e in config.envs)
    if not env_found:
        click.echo(f"Environment '{env}' is not registered.", err=True)
        raise click.ClickException(f"Environment '{env}' not found.")

    # Overwrite if an association with the same agent name already exists
    for binding in config.agent_bindings:
        if binding.agent == agent:
            old_env = binding.env
            binding.env = env
            save_config(config)
            click.echo(
                f"Agent '{agent}' binding changed from '{old_env}' to '{env}'."
            )
            return

    config.agent_bindings.append(AgentBinding(agent=agent, env=env))
    save_config(config)
    click.echo(f"Agent '{agent}' bound to environment '{env}'.")


@env_group.command(name="unlink-agent")
@click.argument("agent")
def env_unlink_agent(agent: str) -> None:
    """Unbind an agent from its environment.

    AGENT: Agent name to unbind.
    """
    config = load_config()
    if config is None:
        click.echo("Configuration file not found. Run ai-adapter init first.")
        return

    found = None
    for binding in config.agent_bindings:
        if binding.agent == agent:
            found = binding
            break

    if found is None:
        click.echo(f"No binding found for agent '{agent}'.", err=True)
        raise click.ClickException(f"Binding for agent '{agent}' not found.")

    config.agent_bindings.remove(found)
    save_config(config)
    click.echo(f"Agent '{agent}' unbound.")


@env_group.command(name="remove-all")
@click.option("--force", is_flag=True, help="Delete without confirmation prompt")
def env_remove_all(force: bool) -> None:
    """Remove all environments (except the default)."""
    config = load_config()
    if config is None:
        click.echo("Configuration file not found. Run ai-adapter init first.")
        return

    non_default = [e for e in config.envs if e.name != config.default_env]
    if not non_default:
        click.echo("No environments other than the default.")
        return

    count = len(non_default)
    if not force:
        click.confirm(f"Remove all environments ({count})? (Default will be kept)", abort=True)

    # Check references in bins
    ref_bins = [b for b in config.bins if b.env in [e.name for e in non_default]]
    if ref_bins and not force:
        click.echo(
            f"Target environments are referenced by {len(ref_bins)} bin(s)."
            f" Use --force to force removal.",
            err=True,
        )
        raise click.ClickException("Cannot remove environment referenced by bins. Use --force.")

    removed_names = [e.name for e in non_default]
    config.envs = [e for e in config.envs if e.name == config.default_env]

    # Also remove agent associations
    config.agent_bindings = [
        b for b in config.agent_bindings if b.env not in removed_names
    ]

    save_config(config)
    click.echo(f"All environments ({count}) removed. Default '{config.default_env}' kept.")
