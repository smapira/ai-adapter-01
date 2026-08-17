"""setup subcommand implementation.

Applies a named profile, registering its skills / MCP / agents / commands
via the existing ``add`` subcommands.

Usage:
    ai-adapter setup apply <profile>       # apply the profile
    ai-adapter setup apply <profile> --dry-run  # preview only
    ai-adapter setup list                  # list available profiles
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import click

from ai_adapter.config import (
    get_skills_dir,
    load_config,
    save_config,
)
from ai_adapter.models import MCPServer, Skill
from ai_adapter.profiles import (
    MCPServerSpec,
    Profile,
    load_profiles,
    resolve_skill_source,
)

logger = logging.getLogger(__name__)

# Directories searched for profile YAMLs (standard first, user overrides).
_PACKAGE_PROFILES_DIR = Path(__file__).resolve().parent.parent / "profiles"


def _get_user_profiles_dir() -> Path:
    """Return ``~/.ai-adapter/profiles/`` (resolved lazily so monkeypatching Path.home works)."""
    return Path.home() / ".ai-adapter" / "profiles"


def _collect_profile_dirs() -> list[Path]:
    """Return profile directories in priority order (low → high)."""
    return [_PACKAGE_PROFILES_DIR, _get_user_profiles_dir()]


# ---------------------------------------------------------------------------
# Group
# ---------------------------------------------------------------------------


@click.group(name="setup")
def setup_group() -> None:
    """Apply a named profile (preset) to configure skills / MCP / agents / commands."""


# ---------------------------------------------------------------------------
# setup list
# ---------------------------------------------------------------------------


@setup_group.command(name="list")
def setup_list() -> None:
    """List available profiles."""
    profiles = load_profiles(_collect_profile_dirs())
    if not profiles:
        click.echo("No profiles found.")
        return

    click.echo("Available profiles:")
    click.echo("-" * 50)
    for name, profile in sorted(profiles.items()):
        desc = f" — {profile.description}" if profile.description else ""
        click.echo(f"  {name}{desc}")


# ---------------------------------------------------------------------------
# setup apply
# ---------------------------------------------------------------------------


def _resolve_mcp_source(spec: MCPServerSpec) -> MCPServer:
    """Convert a profile MCPServerSpec into a full MCPServer for registration."""
    return MCPServer(
        name=spec.name,
        command=spec.command,
        args=spec.args,
        enabled=True,
    )


def _apply_skill(
    name: str,
    *,
    dry_run: bool,
    registered_names: set[str],
    already_registered: list[str],
    would_register: list[str],
    install_missing: bool = False,
) -> None:
    """Handle a single skill entry from a profile."""
    if name in registered_names:
        already_registered.append(name)
        return

    source = resolve_skill_source(name)
    if source is None:
        if install_missing and not dry_run:
            # Auto-install missing skill via the core installer (no Click context needed).
            from ai_adapter.commands.skill import install_skill_core

            click.echo(f"  ⏳ Skill '{name}': installing automatically…")
            try:
                install_skill_core(name, None, force=True)
            except click.ClickException as exc:
                click.echo(f"  ✗ Skill '{name}': install failed — {exc.format_message()}")
                return
            # Refresh source after install
            source = resolve_skill_source(name)
            if source is None:
                click.echo(f"  ✗ Skill '{name}': install succeeded but source still unresolved (skipped)")
                return
        else:
            click.echo(f"  ⚠ Skill '{name}': source not found (skipped)")
            return

    would_register.append(name)
    if dry_run:
        return

    # Import here to avoid circular imports at module level
    from ai_adapter.commands.skill import _parse_skill_metadata
    from ai_adapter.config import is_safe_store_name

    metadata = _parse_skill_metadata(source)
    skill_name = metadata.get("name") or name
    if not is_safe_store_name(str(skill_name)):
        click.echo(f"  ⚠ Skill '{name}': invalid name '{skill_name}' (skipped)")
        return

    skills_dir = get_skills_dir()
    skills_dir.mkdir(parents=True, exist_ok=True)
    dest = skills_dir / skill_name

    # Only copy if source is different from destination (avoids copytree to self)
    if source.resolve() != dest.resolve():
        import shutil

        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(source, dest)

    config = load_config()
    if config is None:
        return

    # Update or append in config
    for existing in config.skills:
        if existing.name == skill_name:
            existing.description = metadata.get("description", "")
            existing.tags = metadata.get("tags", [])
            existing.path = f"skills/{skill_name}"
            save_config(config)
            return

    config.skills.append(
        Skill(
            name=skill_name,
            description=metadata.get("description", ""),
            path=f"skills/{skill_name}",
            tags=metadata.get("tags", []),
        )
    )
    save_config(config)


def _apply_mcp(
    spec: MCPServerSpec,
    *,
    dry_run: bool,
    registered_names: set[str],
    already_registered: list[str],
    would_register: list[str],
) -> None:
    """Handle a single MCP entry from a profile."""
    if spec.name in registered_names:
        already_registered.append(spec.name)
        return

    would_register.append(spec.name)
    if dry_run:
        return

    config = load_config()
    if config is None:
        return

    server = _resolve_mcp_source(spec)
    config.mcp_servers.append(server)
    save_config(config)


def _apply_agent(
    name: str,
    *,
    dry_run: bool,
    registered_names: set[str],
    already_registered: list[str],
    would_register: list[str],
) -> None:
    """Handle a single agent entry from a profile."""
    if name in registered_names:
        already_registered.append(name)
        return

    source = resolve_skill_source(name)
    if source is None:
        click.echo(f"  ⚠ Agent '{name}': source not found (skipped)")
        return

    would_register.append(name)
    if dry_run:
        return

    # Agents can be resolved from skill directories or from the agents store.
    # For now we register the name in config; file deployment is handled by
    # ``sub-agent get-all``.
    config = load_config()
    if config is None:
        return

    from ai_adapter.models import Agent

    for existing in config.agents:
        if existing.name == name:
            return

    config.agents.append(Agent(name=name))
    save_config(config)


def _apply_command(
    name: str,
    *,
    dry_run: bool,
    registered_names: set[str],
    already_registered: list[str],
    would_register: list[str],
) -> None:
    """Handle a single command entry from a profile."""
    if name in registered_names:
        already_registered.append(name)
        return

    source = resolve_skill_source(name)
    if source is None:
        click.echo(f"  ⚠ Command '{name}': source not found (skipped)")
        return

    would_register.append(name)
    if dry_run:
        return

    config = load_config()
    if config is None:
        return

    from ai_adapter.models import Command as CommandModel

    for existing in config.commands:
        if existing.name == name:
            return

    config.commands.append(CommandModel(name=name))
    save_config(config)


def _apply_category(
    items: list,
    apply_fn: Any,
    registered_names: set[str],
    *,
    dry_run: bool,
    prefix: str,
    label: str,
    **kwargs: object,
) -> None:
    """Apply items of a single category and print results.

    Shared helper for ``_apply_profile`` to avoid repeating the same loop
    for skills / MCP / agents / commands.
    """
    for item in items:
        already: list[str] = []
        would: list[str] = []
        name = item.name if hasattr(item, "name") else item
        apply_fn(
            item,
            dry_run=dry_run,
            registered_names=registered_names,
            already_registered=already,
            would_register=would,
            **kwargs,
        )
        if already:
            click.echo(f"  {prefix}✓ {label} '{name}': already registered")
        elif would:
            click.echo(f"  {prefix}✓ {label} '{name}': registered")


def _apply_profile(
    profile: Profile,
    *,
    dry_run: bool,
    yes: bool,
    install_missing: bool = False,
) -> None:
    """Apply a resolved Profile object, registering its skills/MCP/agents/commands.

    This is the core logic shared by ``setup apply`` and ``pack install``.
    """
    # --- Gather current registrations ---
    config = load_config()
    registered_skill_names: set[str] = {s.name for s in (config.skills if config else [])}
    registered_mcp_names: set[str] = {s.name for s in (config.mcp_servers if config else [])}
    registered_agent_names: set[str] = {a.name for a in (config.agents if config else [])}
    registered_command_names: set[str] = {c.name for c in (config.commands if config else [])}

    # --- Preview header ---
    click.echo(f"Profile: {profile.name}")
    if profile.description:
        click.echo(f"  {profile.description}")

    # --- Confirmation (unless --yes or --dry-run) ---
    if not dry_run and not yes:
        click.confirm("Proceed?", abort=True)

    # --- Apply each category (works for both normal and dry-run) ---
    click.echo()
    prefix = "[dry-run] " if dry_run else ""

    _apply_category(
        profile.skills,
        _apply_skill,
        registered_skill_names,
        dry_run=dry_run,
        prefix=prefix,
        label="Skill",
        install_missing=install_missing,
    )
    _apply_category(
        profile.mcp,
        _apply_mcp,
        registered_mcp_names,
        dry_run=dry_run,
        prefix=prefix,
        label="MCP",
    )
    _apply_category(
        profile.agents,
        _apply_agent,
        registered_agent_names,
        dry_run=dry_run,
        prefix=prefix,
        label="Agent",
    )
    _apply_category(
        profile.commands,
        _apply_command,
        registered_command_names,
        dry_run=dry_run,
        prefix=prefix,
        label="Command",
    )

    if dry_run:
        click.echo()
        click.echo("[dry-run] No changes were made.")
    else:
        click.echo()
        click.echo("Profile applied.")


@setup_group.command(name="apply")
@click.argument("profile_name", required=False)
@click.option("--dry-run", is_flag=True, help="Preview changes without modifying anything")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
@click.option("--install-missing", is_flag=True, help="Automatically install skills not found locally")
def setup_apply(profile_name: str | None, dry_run: bool, yes: bool, install_missing: bool) -> None:
    """Apply a named profile to register skills / MCP / agents / commands.

    PROFILE_NAME: Name of the profile to apply (see ``setup list``).

    Without PROFILE_NAME, lists all available profiles.
    """
    # --- AC1: no name → list available profiles ---
    if not profile_name:
        profiles = load_profiles(_collect_profile_dirs())
        if not profiles:
            click.echo("No profiles found.")
            return
        click.echo("Available profiles:")
        click.echo("-" * 50)
        for name, p in sorted(profiles.items()):
            desc = f" — {p.description}" if p.description else ""
            click.echo(f"  {name}{desc}")
        return

    profiles = load_profiles(_collect_profile_dirs())

    if profile_name not in profiles:
        available = ", ".join(sorted(profiles.keys())) or "(none)"
        click.echo(f"Profile '{profile_name}' not found.")
        click.echo(f"Available profiles: {available}")
        raise click.ClickException(f"Profile '{profile_name}' not found.")

    profile = profiles[profile_name]
    _apply_profile(profile, dry_run=dry_run, yes=yes, install_missing=install_missing)
