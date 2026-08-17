"""npx subcommand implementation.

Wraps ``npx`` commands (primarily ``npx skills``) so they can be
invoked through ai-adapter when npx is installed locally.
"""

from __future__ import annotations

import click

from ai_adapter.npx import find_npx, get_npx_version, run_npx_skills


@click.group(name="npx")
def npx_group() -> None:
    """Run npx commands (when npx is installed)."""


@npx_group.command(name="skills")
@click.argument("args", nargs=-1)
@click.option("--check", is_flag=True, help="Check if npx is available")
@click.option("--version", is_flag=True, help="Show npx version")
@click.option(
    "--timeout",
    type=int,
    default=60,
    help="Timeout in seconds (default: 60)",
)
def npx_skills(
    args: tuple[str, ...],
    check: bool,
    version: bool,
    timeout: int,
) -> None:
    """Run 'npx skills' with given arguments.

    \b
    Examples:
      ai-adapter npx skills find react
      ai-adapter npx skills add owner/repo
      ai-adapter npx skills add owner/repo --list
      ai-adapter npx skills list
      ai-adapter npx skills update
      ai-adapter npx skills remove my-skill
      ai-adapter npx skills use owner/repo@my-skill
      ai-adapter npx skills init my-skill
      ai-adapter npx --check
      ai-adapter npx --version
    """
    if check:
        _handle_check()
        return

    if version:
        _handle_version()
        return

    exit_code, stdout, stderr = run_npx_skills(list(args), timeout=timeout)
    if stdout:
        click.echo(stdout, nl=False)
    if stderr:
        click.echo(stderr, nl=False, err=True)
    if exit_code != 0:
        raise SystemExit(exit_code)


def _handle_check() -> None:
    """Print npx availability and version."""
    npx_path = find_npx()
    if npx_path:
        click.echo(f"npx found: {npx_path}")
        ver = get_npx_version()
        if ver:
            click.echo(f"version: {ver}")
    else:
        click.echo("npx is not installed or not in PATH", err=True)
        raise click.ClickException("npx not found")


def _handle_version() -> None:
    """Print npx version only."""
    ver = get_npx_version()
    if ver:
        click.echo(ver)
    else:
        click.echo("npx is not installed or not in PATH", err=True)
        raise click.ClickException("npx not found")
