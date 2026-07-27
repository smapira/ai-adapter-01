"""prompt subcommand implementation.

Manages prompt files under ~/.ai-adapter/prompts/.
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
    save_config,
)
from ai_adapter.models import Prompt


@click.group(name="prompt")
def prompt_group() -> None:
    """Manage prompt templates."""


@prompt_group.command(name="list")
def prompt_list() -> None:
    """List registered prompts."""
    config = load_config()
    if config is None:
        click.echo("Configuration file not found. Run ai-adapter init first.")
        return

    if not config.prompts:
        click.echo("No prompts registered.")
        return

    click.echo("Prompts:")
    click.echo("-" * 40)
    for p in config.prompts:
        desc = f" - {p.description}" if p.description else ""
        click.echo(f"  {p.name}{desc}")


@prompt_group.command(name="add")
@click.argument("path", type=click.Path(exists=True, readable=True))
def prompt_add(path: str) -> None:
    """Add a prompt file to ~/.ai-adapter/prompts/."""
    src = Path(path).resolve()
    prompts_dir = get_prompts_dir()
    prompts_dir.mkdir(parents=True, exist_ok=True)

    name = src.stem
    dest = prompts_dir / src.name

    if dest.exists():
        click.confirm(f"'{dest.name}' already exists. Overwrite?", abort=True)

    shutil.copy2(src, dest)
    content = src.read_text(encoding="utf-8")[:200]
    click.echo(f"Prompt '{name}' added: {dest}")

    config = load_config()
    if config is None:
        return

    for existing in config.prompts:
        if existing.name == name:
            save_config(config)
            return

    config.prompts.append(Prompt(name=name, content=content))
    save_config(config)


def _find_prompt_by_name(prompts_dir: Path, name: str) -> Path | None:
    """Find a prompt file by name."""
    # 1. Exact match
    exact = prompts_dir / name
    if exact.exists() and exact.is_file():
        return exact

    # 2. Search with extension
    for f in sorted(prompts_dir.iterdir()):
        if f.is_file() and f.stem == name:
            return f

    return None


@prompt_group.command(name="get")
@click.argument("name")
@click.option("--project-dir", "-d", type=click.Path(exists=True, file_okay=False, readable=True), default=None)
def prompt_get(name: str, project_dir: str | None) -> None:
    """Copy prompt to .github/prompts/."""
    prompts_dir = get_prompts_dir()
    src = _find_prompt_by_name(prompts_dir, name)

    if src is None:
        click.echo(f"Prompt '{name}' not found.", err=True)
        raise click.ClickException(f"Prompt '{name}' is not registered.")

    project_path = Path(project_dir).resolve() if project_dir else None
    github_dir = get_github_prompts_dir(project_path)
    github_dir.mkdir(parents=True, exist_ok=True)

    dest = github_dir / src.name
    shutil.copy2(src, dest)
    add_to_gitignore(dest)
    click.echo(f"Prompt '{name}' copied to {dest}.")


@prompt_group.command(name="remove")
@click.argument("name")
def prompt_remove(name: str) -> None:
    """Remove a prompt."""
    config = load_config()
    if config is None:
        return

    found = None
    for p in config.prompts:
        if p.name == name:
            found = p
            break

    if found is None:
        click.echo(f"Prompt '{name}' is not registered.", err=True)
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
def prompt_add_rec(dir_path: str) -> None:
    """Recursively add all files in a directory to ~/.ai-adapter/prompts/."""
    src_dir = Path(dir_path).resolve()
    prompts_dir = get_prompts_dir()
    prompts_dir.mkdir(parents=True, exist_ok=True)

    config = load_config()
    if config is None:
        click.echo("Configuration file not found. Run ai-adapter init first.")
        return

    added = 0
    for f in sorted(src_dir.rglob("*")):
        if not f.is_file():
            continue
        dest = prompts_dir / f.name
        config.prompts = [p for p in config.prompts if p.name != f.stem]
        shutil.copy2(f, dest)
        content = f.read_text(encoding="utf-8")[:200]
        config.prompts.append(Prompt(name=f.stem, content=content))
        added += 1

    save_config(config)
    click.echo(f"Prompts added: {added}")


@prompt_group.command(name="get-all")
@click.option("--project-dir", "-d", type=click.Path(exists=True, file_okay=False, readable=True), default=None)
def prompt_get_all(project_dir: str | None) -> None:
    """Copy all registered prompts to .github/prompts/."""
    config = load_config()
    if config is None or not config.prompts:
        click.echo("No prompts registered.")
        return

    prompts_dir = get_prompts_dir()
    project_path = Path(project_dir).resolve() if project_dir else None
    github_dir = get_github_prompts_dir(project_path)
    github_dir.mkdir(parents=True, exist_ok=True)

    copied = 0
    for prompt_entry in config.prompts:
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
@click.option("--force", is_flag=True, help="Delete without confirmation")
def prompt_remove_all(force: bool) -> None:
    """Remove all registered prompts."""
    config = load_config()
    if config is None or not config.prompts:
        click.echo("No prompts registered.")
        return

    count = len(config.prompts)
    if not force:
        click.confirm(f"All prompts ({count})?", abort=True)

    config.prompts.clear()
    save_config(config)
    click.echo(f"All prompts ({count}) removed.")
