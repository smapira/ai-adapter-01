"""instruction subcommand implementation.

Manages root-level agent instruction files (AGENTS.md, AGENT.md, etc.)
under ~/.ai-adapter/instructions/. Deploys to project root.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import click

from ai_adapter.config import (
    add_to_gitignore,
    get_github_instructions_dir,
    get_instructions_dir,
    load_config,
    save_config,
)
from ai_adapter.models import Instruction


@click.group(name="instruction")
def instruction_group() -> None:
    """Manage root-level agent instruction files (AGENTS.md)."""


@instruction_group.command(name="list")
def instruction_list() -> None:
    """List registered instructions."""
    config = load_config()
    if config is None:
        click.echo("Configuration file not found. Run ai-adapter init first.")
        return

    if not config.instructions:
        click.echo("No instructions registered.")
        return

    click.echo("Instructions:")
    click.echo("-" * 40)
    for inst in config.instructions:
        desc = f" - {inst.description}" if inst.description else ""
        click.echo(f"  {inst.name}{desc}")


@instruction_group.command(name="add")
@click.argument("path", type=click.Path(exists=True, readable=True))
def instruction_add(path: str) -> None:
    """Add an instruction file to ~/.ai-adapter/instructions/.

    PATH: Path to the instruction file (e.g. AGENTS.md, CLAUDE.md).
    """
    src = Path(path).resolve()
    instructions_dir = get_instructions_dir()
    instructions_dir.mkdir(parents=True, exist_ok=True)

    name = src.stem
    dest = instructions_dir / src.name

    if dest.exists():
        click.confirm(f"'{dest.name}' already exists. Overwrite?", abort=True)

    shutil.copy2(src, dest)
    content = src.read_text(encoding="utf-8")[:200]
    click.echo(f"Instruction '{name}' added: {dest}")

    config = load_config()
    if config is None:
        return

    for existing in config.instructions:
        if existing.name == name:
            save_config(config)
            return

    config.instructions.append(Instruction(name=name, content=content))
    save_config(config)


def _find_instruction_by_name(instructions_dir: Path, name: str) -> Path | None:
    """Find an instruction file by name."""
    # 1. Exact match
    exact = instructions_dir / name
    if exact.exists() and exact.is_file():
        return exact

    # 2. Search with extension
    for f in sorted(instructions_dir.iterdir()):
        if f.is_file() and f.stem == name:
            return f

    return None


@instruction_group.command(name="get")
@click.argument("name")
@click.option(
    "--project-dir",
    "-d",
    type=click.Path(exists=True, file_okay=False, readable=True),
    default=None,
    help="Target project directory (default: current directory)",
)
@click.option("--force", is_flag=True, help="Overwrite existing file without prompting")
def instruction_get(name: str, project_dir: str | None, force: bool) -> None:
    """Copy instruction to project root (./AGENTS.md etc.).

    NAME: Instruction name to retrieve (no extension needed).
    """
    instructions_dir = get_instructions_dir()
    src = _find_instruction_by_name(instructions_dir, name)

    if src is None:
        click.echo(f"Instruction '{name}' not found.", err=True)
        raise click.ClickException(f"Instruction '{name}' is not registered.")

    project_path = Path(project_dir).resolve() if project_dir else None
    root_dir = get_github_instructions_dir(project_path)

    dest = root_dir / src.name

    if dest.exists() and not force:
        click.confirm(f"'{dest.name}' already exists. Overwrite?", abort=True)

    shutil.copy2(src, dest)
    add_to_gitignore(dest)
    click.echo(f"Instruction '{name}' copied to {dest}.")


@instruction_group.command(name="remove")
@click.argument("name")
def instruction_remove(name: str) -> None:
    """Remove an instruction."""
    config = load_config()
    if config is None:
        return

    found = None
    for inst in config.instructions:
        if inst.name == name:
            found = inst
            break

    if found is None:
        click.echo(f"Instruction '{name}' is not registered.", err=True)
        raise click.ClickException(f"Instruction '{name}' not found.")

    config.instructions.remove(found)
    save_config(config)

    instructions_dir = get_instructions_dir()
    for f in instructions_dir.iterdir():
        if f.stem == name or f.name == name:
            f.unlink()
            click.echo(f"File {f.name} removed.")
            break

    # Also delete from project root
    root_dir = get_github_instructions_dir()
    if root_dir.exists():
        for f in root_dir.iterdir():
            if f.stem == name or f.name == name:
                f.unlink()
                break

    click.echo(f"Instruction '{name}' removed.")


@instruction_group.command(name="add-rec")
@click.argument("dir_path", type=click.Path(exists=True, file_okay=False, readable=True))
def instruction_add_rec(dir_path: str) -> None:
    """Recursively add all files in a directory to ~/.ai-adapter/instructions/."""
    src_dir = Path(dir_path).resolve()
    instructions_dir = get_instructions_dir()
    instructions_dir.mkdir(parents=True, exist_ok=True)

    config = load_config()
    if config is None:
        click.echo("Configuration file not found. Run ai-adapter init first.")
        return

    added = 0
    for f in sorted(src_dir.rglob("*")):
        if not f.is_file():
            continue
        dest = instructions_dir / f.name
        config.instructions = [i for i in config.instructions if i.name != f.stem]
        shutil.copy2(f, dest)
        content = f.read_text(encoding="utf-8")[:200]
        config.instructions.append(Instruction(name=f.stem, content=content))
        added += 1

    save_config(config)
    click.echo(f"Instructions added: {added}")


@instruction_group.command(name="get-all")
@click.option(
    "--project-dir",
    "-d",
    type=click.Path(exists=True, file_okay=False, readable=True),
    default=None,
    help="Target project directory (default: current directory)",
)
@click.option("--force", is_flag=True, help="Overwrite existing files without prompting")
def instruction_get_all(project_dir: str | None, force: bool) -> None:
    """Copy all registered instructions to project root."""
    config = load_config()
    if config is None or not config.instructions:
        click.echo("No instructions registered.")
        return

    instructions_dir = get_instructions_dir()
    project_path = Path(project_dir).resolve() if project_dir else None
    root_dir = get_github_instructions_dir(project_path)

    copied = 0
    for inst_entry in config.instructions:
        src = _find_instruction_by_name(instructions_dir, inst_entry.name)
        if src is None:
            click.echo(f"   Skip: '{inst_entry.name}' file not found.")
            continue
        dest = root_dir / src.name
        if dest.exists() and not force:
            click.confirm(f"Overwrite '{dest.name}'?", abort=True)
        shutil.copy2(src, dest)
        add_to_gitignore(dest)
        copied += 1

    click.echo(f"All instructions ({copied}) copied to {root_dir}.")


@instruction_group.command(name="remove-all")
@click.option("--force", is_flag=True, help="Delete without confirmation")
def instruction_remove_all(force: bool) -> None:
    """Remove all registered instructions."""
    config = load_config()
    if config is None or not config.instructions:
        click.echo("No instructions registered.")
        return

    count = len(config.instructions)
    if not force:
        click.confirm(f"All instructions ({count})?", abort=True)

    config.instructions.clear()
    save_config(config)
    click.echo(f"All instructions ({count}) removed.")
