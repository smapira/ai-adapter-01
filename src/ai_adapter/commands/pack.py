"""pack subcommand implementation.

Manages Pack definitions — named collections of profiles that are applied
in sequence.

Usage:
    ai-adapter pack list                  # list available packs
    ai-adapter pack install <name>        # apply all profiles in the pack
"""

from __future__ import annotations

from pathlib import Path

import click

from ai_adapter.profiles import load_packs

# Directories searched for pack YAMLs (standard first, user overrides).
_PACKAGE_PACKS_DIR = Path(__file__).resolve().parent.parent / "packs"


def _get_user_packs_dir() -> Path:
    """Return ``~/.ai-adapter/packs/`` (resolved lazily so monkeypatching Path.home works)."""
    return Path.home() / ".ai-adapter" / "packs"


def _collect_pack_dirs() -> list[Path]:
    """Return pack directories in priority order (low → high)."""
    return [_PACKAGE_PACKS_DIR, _get_user_packs_dir()]


# ---------------------------------------------------------------------------
# Group
# ---------------------------------------------------------------------------


@click.group(name="pack")
def pack_group() -> None:
    """Manage packs (named collections of profiles)."""


# ---------------------------------------------------------------------------
# pack list
# ---------------------------------------------------------------------------


@pack_group.command(name="list")
def pack_list() -> None:
    """List available packs."""
    packs = load_packs(_collect_pack_dirs())
    if not packs:
        click.echo("No packs found.")
        return

    click.echo("Available packs:")
    click.echo("-" * 50)
    for name, pack in sorted(packs.items()):
        desc = f" — {pack.description}" if pack.description else ""
        profiles_str = ", ".join(pack.profiles) if pack.profiles else "(empty)"
        click.echo(f"  {name}{desc}")
        click.echo(f"    profiles: {profiles_str}")


# ---------------------------------------------------------------------------
# pack install
# ---------------------------------------------------------------------------


@pack_group.command(name="install")
@click.argument("pack_name")
@click.option("--dry-run", is_flag=True, help="Preview changes without modifying anything")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
def pack_install(pack_name: str, dry_run: bool, yes: bool) -> None:
    """Apply all profiles in a named pack (in order).

    PROFILE_NAME: Name of the pack to install (see ``pack list``).
    """
    packs = load_packs(_collect_pack_dirs())

    if pack_name not in packs:
        available = ", ".join(sorted(packs.keys())) or "(none)"
        click.echo(f"Pack '{pack_name}' not found.")
        click.echo(f"Available packs: {available}")
        raise click.ClickException(f"Pack '{pack_name}' not found.")

    pack = packs[pack_name]

    if not pack.profiles:
        click.echo(f"Pack '{pack_name}' has no profiles.")
        return

    click.echo(f"Pack: {pack.name}")
    if pack.description:
        click.echo(f"  {pack.description}")
    click.echo(f"  Profiles: {', '.join(pack.profiles)}")
    click.echo()

    # Delegate each profile to ``_apply_profile`` (shared core logic with setup apply).
    from ai_adapter.commands.setup import _apply_profile, _collect_profile_dirs
    from ai_adapter.profiles import load_profiles

    all_profiles = load_profiles(_collect_profile_dirs())

    for idx, profile_name in enumerate(pack.profiles, 1):
        click.echo(f"[{idx}/{len(pack.profiles)}] Applying profile: {profile_name}")

        if profile_name not in all_profiles:
            click.echo(f"  ⚠ Profile '{profile_name}' not found (skipped)")
            continue

        profile = all_profiles[profile_name]
        _apply_profile(profile, dry_run=dry_run, yes=True)

    if not dry_run:
        click.echo("Pack installed.")
    else:
        click.echo("[dry-run] No changes were made.")
