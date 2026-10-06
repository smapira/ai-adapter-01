"""prompt subcommand implementation.

Manages prompt files under ~/.ai-adapter/prompts/.
Supports --env for environment-scoped registration and filtering.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import click

from ai_adapter.config import (
    add_to_gitignore,
    get_github_prompts_dir,
    get_prompts_dir,
    load_config,
    resolve_env,
    resolve_scope_path,
    save_config,
)
from ai_adapter.models import Prompt
from ai_adapter.providers.claude import validate_claude_scope
from ai_adapter.providers.gemini import export_command_toml


@click.group(name="prompt")
def prompt_group() -> None:
    """Manage prompt templates."""


@prompt_group.command(name="list")
@click.option("--env", "-e", default=None, help="Filter by environment name")
def prompt_list(env: str | None) -> None:
    """List registered prompts."""
    config = load_config()
    if config is None:
        click.echo("Configuration file not found. Run ai-adapter init first.")
        return

    if not config.prompts:
        click.echo("No prompts registered.")
        return

    prompts = config.prompts
    if env:
        prompts = [p for p in prompts if p.env is None or p.env == env]

    if not prompts:
        click.echo(f"No prompts registered for environment '{env}'.")
        return

    if env:
        click.echo(f"Prompts (env: {env}):")
    else:
        click.echo("Prompts:")
    click.echo("-" * 40)
    for p in prompts:
        env_info = f" [{p.env}]" if p.env else ""
        desc = f" - {p.description}" if p.description else ""
        click.echo(f"  {p.name}{env_info}{desc}")


@prompt_group.command(name="add")
@click.argument("path", type=click.Path(exists=True, readable=True))
@click.option("--env", "-e", default=None, help="Environment name (auto-resolved when omitted)")
@click.option("--agent", help="Agent name (for env resolution)")
def prompt_add(path: str, env: str | None, agent: str | None) -> None:
    """Add a prompt file to ~/.ai-adapter/prompts/.

    When --env is omitted, auto-resolves via environment resolution logic.
    """
    src = Path(path).resolve()
    prompts_dir = get_prompts_dir()
    prompts_dir.mkdir(parents=True, exist_ok=True)

    name = src.stem
    dest = prompts_dir / src.name

    if dest.exists():
        click.confirm(f"'{dest.name}' already exists. Overwrite?", abort=True)

    shutil.copy2(src, dest)
    content = src.read_text(encoding="utf-8")[:200]

    config = load_config()
    if config is None:
        click.echo("Configuration file not found. Run ai-adapter init first.")
        return

    resolved_env = resolve_env(config, env, agent)
    click.echo(f"Prompt '{name}' added (env: {resolved_env}): {dest}")

    for existing in config.prompts:
        if existing.name == name and (existing.env is None or existing.env == resolved_env):
            existing.content = content
            save_config(config)
            return

    config.prompts.append(Prompt(name=name, content=content, env=resolved_env))
    save_config(config)


def _find_prompt_by_name(prompts_dir: Path, name: str) -> Path | None:
    """Find a prompt file by name, supporting nested names (``dir/name``).

    Gemini CLI nests custom commands as ``.gemini/commands/<dir>/<name>.toml``
    (design 05 task 05-4), so the lookup must accept slash-separated names
    as well as flat ones.
    """
    # 1. Exact match (flat or nested relative path)
    exact = prompts_dir / name
    if exact.exists() and exact.is_file():
        return exact

    # 2. Stem match within the name's parent directory — covers both
    #    flat "summarize" → "summarize.md" and nested "dir/name" → "dir/name.md".
    relative = Path(name)
    parent = prompts_dir / relative.parent
    if not parent.is_dir():
        return None
    for f in sorted(parent.iterdir()):
        if f.is_file() and f.stem == relative.name:
            return f

    return None


@prompt_group.command(name="get")
@click.argument("name")
@click.option("--env", "-e", default=None, help="Environment name (auto-resolved when omitted)")
@click.option("--agent", help="Agent name (for env resolution)")
@click.option("--project-dir", "-d", type=click.Path(exists=True, file_okay=False, readable=True), default=None)
@click.option(
    "--format",
    "-f",
    "format_name",
    type=click.Choice(["standard", "gemini"]),
    default="standard",
    help=("Output format (standard=.github/prompts/, gemini=.gemini/commands/*.toml or ~/.gemini/commands/*.toml)"),
)
@click.option(
    "--scope",
    type=click.Choice(["project", "user"]),
    default="project",
    help="Deploy scope for --format gemini: project=.gemini/commands/, user=~/.gemini/commands/",
)
def prompt_get(
    name: str,
    env: str | None,
    agent: str | None,
    project_dir: str | None,
    format_name: str,
    scope: str,
) -> None:
    """Copy prompt to .github/prompts/ (or .gemini/commands/ with --format gemini).

    When --env is omitted, auto-resolves via environment resolution logic.
    """
    validate_claude_scope(format_name, scope, ignored_option="--project-dir" if project_dir else None)
    prompts_dir = get_prompts_dir()
    src = _find_prompt_by_name(prompts_dir, name)

    if src is None:
        click.echo(f"Prompt '{name}' not found.", err=True)
        raise click.ClickException(f"Prompt '{name}' is not registered.")

    project_path = Path(project_dir).resolve() if project_dir else None

    if format_name == "gemini":
        _deploy_prompt_gemini(name, src, scope, project_path)
        return

    github_dir = get_github_prompts_dir(project_path)
    github_dir.mkdir(parents=True, exist_ok=True)

    dest = github_dir / src.name
    shutil.copy2(src, dest)
    add_to_gitignore(dest)
    click.echo(f"Prompt '{name}' copied to {dest}.")


def _deploy_prompt_gemini(name: str, src: Path, scope: str, project_path: Path | None) -> None:
    """Convert *src* Markdown to Gemini TOML under .gemini/commands/ (design 05).

    Gemini has one custom-command namespace, so prompts export into the
    same ``.gemini/commands/`` tree as commands.
    """
    target = resolve_scope_path("gemini", "commands", scope, project_path)
    dest = target.path / f"{name}.toml"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(export_command_toml(name, src.read_text(encoding="utf-8")), encoding="utf-8")
    if target.use_gitignore:
        add_to_gitignore(dest)
    click.echo(f"Prompt '{name}' exported to {dest} (gemini TOML).")


@prompt_group.command(name="remove")
@click.argument("name")
@click.option("--env", "-e", default=None, help="Environment name (auto-resolved when omitted)")
@click.option("--agent", help="Agent name (for env resolution)")
def prompt_remove(name: str, env: str | None, agent: str | None) -> None:
    """Remove a prompt.

    When --env is omitted, auto-resolves via environment resolution logic.
    """
    config = load_config()
    if config is None:
        return

    resolved_env = resolve_env(config, env, agent)

    found = None
    for p in config.prompts:
        if p.name == name and (p.env is None or p.env == resolved_env):
            found = p
            break

    if found is None:
        click.echo(f"Prompt '{name}' (env: {resolved_env}) is not registered.", err=True)
        raise click.ClickException(f"Prompt '{name}' not found.")

    config.prompts.remove(found)
    save_config(config)

    prompts_dir = get_prompts_dir()
    for f in prompts_dir.iterdir():
        if f.stem == name or f.name == name:
            f.unlink()
            click.echo(f"File {f.name} removed.")
            break

    # Also delete from .github/prompts/
    github_dir = get_github_prompts_dir()
    if github_dir.exists():
        for f in github_dir.iterdir():
            if f.stem == name or f.name == name:
                f.unlink()
                break

    click.echo(f"Prompt '{name}' removed.")


@prompt_group.command(name="add-rec")
@click.argument("dir_path", type=click.Path(exists=True, file_okay=False, readable=True))
@click.option("--env", "-e", default=None, help="Environment name (auto-resolved when omitted)")
@click.option("--agent", help="Agent name (for env resolution)")
def prompt_add_rec(dir_path: str, env: str | None, agent: str | None) -> None:
    """Recursively add all files in a directory to ~/.ai-adapter/prompts/."""
    src_dir = Path(dir_path).resolve()
    prompts_dir = get_prompts_dir()
    prompts_dir.mkdir(parents=True, exist_ok=True)

    config = load_config()
    if config is None:
        click.echo("Configuration file not found. Run ai-adapter init first.")
        return

    resolved_env = resolve_env(config, env, agent)
    added = 0
    for f in sorted(src_dir.rglob("*")):
        if not f.is_file():
            continue
        dest = prompts_dir / f.name
        config.prompts = [p for p in config.prompts if p.name != f.stem or p.env != resolved_env]
        shutil.copy2(f, dest)
        content = f.read_text(encoding="utf-8")[:200]
        config.prompts.append(Prompt(name=f.stem, content=content, env=resolved_env))
        added += 1

    save_config(config)
    click.echo(f"Prompts added: {added}")


@prompt_group.command(name="get-all")
@click.option("--env", "-e", default=None, help="Filter by environment name")
@click.option("--project-dir", "-d", type=click.Path(exists=True, file_okay=False, readable=True), default=None)
def prompt_get_all(env: str | None, project_dir: str | None) -> None:
    """Copy all registered prompts to .github/prompts/."""
    config = load_config()
    if config is None or not config.prompts:
        click.echo("No prompts registered.")
        return

    prompts_dir = get_prompts_dir()
    project_path = Path(project_dir).resolve() if project_dir else None
    github_dir = get_github_prompts_dir(project_path)
    github_dir.mkdir(parents=True, exist_ok=True)

    targets = config.prompts
    if env:
        targets = [p for p in targets if p.env is None or p.env == env]

    copied = 0
    for prompt_entry in targets:
        src = _find_prompt_by_name(prompts_dir, prompt_entry.name)
        if src is None:
            click.echo(f"   Skip: '{prompt_entry.name}' file not found.")
            continue
        dest = github_dir / src.name
        shutil.copy2(src, dest)
        add_to_gitignore(dest)
        copied += 1

    click.echo(f"All prompts ({copied}) copied to {github_dir}.")


@prompt_group.command(name="remove-all")
@click.option("--env", "-e", default=None, help="Remove only prompts for this environment")
@click.option("--force", is_flag=True, help="Delete without confirmation")
def prompt_remove_all(env: str | None, force: bool) -> None:
    """Remove all registered prompts (or only prompts matching --env)."""
    config = load_config()
    if config is None or not config.prompts:
        click.echo("No prompts registered.")
        return

    targets = config.prompts
    if env:
        targets = [p for p in targets if p.env == env]
        if not targets:
            click.echo(f"No prompts registered for environment '{env}'.")
            return

    count = len(targets)
    if not force:
        click.confirm(f"Remove {count} prompt(s)?", abort=True)

    if env:
        config.prompts = [p for p in config.prompts if p.env != env]
    else:
        config.prompts.clear()
    save_config(config)
    click.echo(f"Removed {count} prompt(s).")
