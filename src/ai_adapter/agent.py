"""agent subcommand implementation.

Manages agent files under ~/.ai-adapter/agents/.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import click
import yaml

from ai_adapter.config import (
    get_agents_dir,
    get_github_agents_dir,
    load_config,
    save_config,
)
from ai_adapter.models import Agent


def _parse_frontmatter(path: Path) -> dict:
    """Parse YAML frontmatter from a file."""
    content = path.read_text(encoding="utf-8")
    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if match:
        data = yaml.safe_load(match.group(1))
        return data if isinstance(data, dict) else {}
    return {}


def _get_agent_name_from_path(path: Path) -> str:
    """Get agent name from a file path.

    For .agent.md files, prefers the YAML frontmatter name.
    Otherwise strips all extensions from the filename.
    """
    if path.suffixes == [".agent", ".md"] or str(path).endswith(".agent.md"):
        # .agent.md: prefer the name from YAML frontmatter
        frontmatter = _parse_frontmatter(path)
        name_from_fm = frontmatter.get("name", "").strip()
        if name_from_fm:
            return name_from_fm
        # If no frontmatter, strip all extensions
        p = path
        while p.suffix:
            p = p.with_suffix("")
        return p.name

    # Otherwise: strip all extensions
    p = path
    while p.suffix:
        p = p.with_suffix("")
    return p.name


@click.group(name="agent")
def agent_group() -> None:
    """Manage AI agent instruction files."""


@agent_group.command(name="list")
def agent_list() -> None:
    """List registered agents."""
    config = load_config()
    if config is None:
        click.echo("Configuration file not found. Run ai-adapter init first.")
        return

    if not config.agents:
        click.echo("No agents registered.。")
        return

    click.echo("Agents:")
    click.echo("-" * 40)
    for agent in config.agents:
        desc = f" - {agent.description}" if agent.description else ""
        click.echo(f"  {agent.name}{desc}")


@agent_group.command(name="add")
@click.argument("path", type=click.Path(exists=True, readable=True))
def agent_add(path: str) -> None:
    """Add an agent file to ~/.ai-adapter/agents/.

    PATH: Path to the agent file to add.
    """
    src = Path(path).resolve()
    agents_dir = get_agents_dir()
    agents_dir.mkdir(parents=True, exist_ok=True)

    # .agent.md format validation
    if str(src).endswith(".agent.md"):
        frontmatter = _parse_frontmatter(src)
        if not frontmatter:
            raise click.ClickException(
                ".agent.md files require YAML frontmatter."
            )
        name_from_fm = frontmatter.get("name", "").strip()
        if not name_from_fm:
            raise click.ClickException(
                ".agent.md files require a name property in frontmatter."
            )

    name = _get_agent_name_from_path(src)
    dest = agents_dir / src.name

    if dest.exists():
        click.confirm(f"'{dest.name}' already exists. Overwrite?", abort=True)

    shutil.copy2(src, dest)
    click.echo(f"Agent '{name}' added: {dest}")

    config = load_config()
    if config is None:
        click.echo("Configuration file not found. Run ai-adapter init first.")
        return

    # Duplicate check
    for existing in config.agents:
        if existing.name == name:
            # On overwrite, do not update description (file-based anyway)
            save_config(config)
            return

    config.agents.append(Agent(name=name))
    save_config(config)


@agent_group.command(name="add-rec")
@click.argument("dir_path", type=click.Path(exists=True, file_okay=False, readable=True))
def agent_add_rec(dir_path: str) -> None:
    """Recursively register all agent files in a directory."""
    src_dir = Path(dir_path).resolve()
    agents_dir = get_agents_dir()
    agents_dir.mkdir(parents=True, exist_ok=True)

    config = load_config()
    if config is None:
        click.echo("Configuration file not found. Run ai-adapter init first.")
        return

    added = 0
    for f in sorted(src_dir.rglob("*")):
        if not f.is_file():
            continue
        if str(f).endswith(".agent.md"):
            frontmatter = _parse_frontmatter(f)
            if not frontmatter or not frontmatter.get("name", "").strip():
                continue

        name = _get_agent_name_from_path(f)
        dest = agents_dir / f.name
        config.agents = [a for a in config.agents if a.name != name]
        shutil.copy2(f, dest)
        config.agents.append(Agent(name=name))
        added += 1

    save_config(config)
    click.echo(f"Agents added: {added}")


@agent_group.command(name="get")
@click.argument("name")
@click.option("--force", is_flag=True, help="Overwrite existing files without prompting")
@click.option(
    "--project-dir", "-d",
    type=click.Path(exists=True, file_okay=False, readable=True),
    default=None,
    help="Target project directory (default: current directory)",
)
def agent_get(name: str, force: bool, project_dir: str | None) -> None:
    """Copy agent file to .github/agents/.

    NAME: Agent name to retrieve (no extension needed).
    """
    config = load_config()
    agents_dir = get_agents_dir()

    src = None

    # Step 1: If the name is in config, look for the agent file
    if config:
        for agent_cfg in config.agents:
            if agent_cfg.name == name:
                # Name matches config: search all files in agents_dir for matching frontmatter name
                for f in agents_dir.iterdir():
                    if not f.is_file():
                        continue
                    try:
                        fm = _parse_frontmatter(f)
                        if fm.get("name", "").strip() == name:
                            src = f
                            break
                    except Exception:
                        continue
                if src is None:
                    # If no frontmatter found, check by filename
                    if (agents_dir / f"{name}.agent.md").exists():
                        src = agents_dir / f"{name}.agent.md"
                    elif (agents_dir / f"{name}.md").exists():
                        src = agents_dir / f"{name}.md"
                    elif (agents_dir / name).exists():
                        src = agents_dir / name
                break

    # Step 2: If not in config, search by filename (backward compatibility)
    if src is None:
        candidates = [
            agents_dir / f"{name}.agent.md",
            agents_dir / f"{name}.md",
            agents_dir / name,
        ]
        for c in candidates:
            if c.exists() and c.is_file():
                src = c
                break

    if src is None:
        click.echo(f"Agent '{name}' not found.", err=True)
        raise click.ClickException(f"Agent '{name}' is not registered.")

    project_path = Path(project_dir).resolve() if project_dir else None
    github_dir = get_github_agents_dir(project_path)
    github_dir.mkdir(parents=True, exist_ok=True)

    dest = github_dir / src.name

    if dest.exists() and not force:
        click.confirm(f"'{dest.name}' already exists. Overwrite?", abort=True)

    shutil.copy2(src, dest)
    click.echo(f"Agent '{name}' copied to {dest}.")


@agent_group.command(name="get-all")
@click.option(
    "--project-dir", "-d",
    type=click.Path(exists=True, file_okay=False, readable=True),
    default=None,
    help="Target project directory (default: current directory)",
)
def agent_get_all(project_dir: str | None) -> None:
    """Copy all registered agents to .github/agents/."""
    config = load_config()
    if config is None or not config.agents:
        click.echo("No agents registered.。")
        return

    agents_dir = get_agents_dir()
    project_path = Path(project_dir).resolve() if project_dir else None
    github_dir = get_github_agents_dir(project_path)
    github_dir.mkdir(parents=True, exist_ok=True)

    copied = 0
    for agent_cfg in config.agents:
        name = agent_cfg.name
        src = None
        # Search for file
        for f in agents_dir.iterdir():
            if not f.is_file():
                continue
            try:
                fm = _parse_frontmatter(f)
                if fm.get("name", "").strip() == name:
                    src = f
                    break
            except Exception:
                continue
        if src is None:
            candidates = [
                agents_dir / f"{name}.agent.md",
                agents_dir / f"{name}.md",
                agents_dir / name,
            ]
            for c in candidates:
                if c.exists() and c.is_file():
                    src = c
                    break
        if src is None:
            click.echo(f"  Skip: '{name}' file not found.")
            continue

        dest = github_dir / src.name
        shutil.copy2(src, dest)
        copied += 1

    click.echo(f"All agents ({copied}) copied to {github_dir}.")


@agent_group.command(name="remove")
@click.argument("name")
@click.option(
    "--keep-file/--no-keep-file",
    default=False,
    help="Keep physical files (default: also delete files)",
)
def agent_remove(name: str, keep_file: bool) -> None:
    """Remove an agent.

    NAME: Name of the agent to remove.
    """
    config = load_config()
    if config is None:
        click.echo("Configuration file not found. Run ai-adapter init first.")
        return

    # Remove from config
    found = False
    for agent in list(config.agents):
        if agent.name == name:
            config.agents.remove(agent)
            found = True
            break

    if not found:
        click.echo(f"Agent '{name}' is not registered.", err=True)
        raise click.ClickException(f"Agent '{name}' not found.")

    save_config(config)

    # Delete file
    if not keep_file:
        agents_dir = get_agents_dir()
        for f in agents_dir.iterdir():
            # Check for .agent.md / .md / exact name patterns
            candidates = [
                f.name == f"{name}.agent.md",
                f.name == f"{name}.md",
                f.name == name,
                _get_agent_name_from_path(f) == name,
            ]
            if any(candidates):
                f.unlink()
                click.echo(f"File {f.name} deleted.")
                break

    # Also delete from .github/agents/
    github_dir = get_github_agents_dir()
    if github_dir.exists():
        for f in github_dir.iterdir():
            candidates = [
                f.name == f"{name}.agent.md",
                f.name == f"{name}.md",
                f.name == name,
            ]
            if any(candidates):
                f.unlink()
                click.echo(f"Removed {f.name} from .github/agents/.")
                break

    click.echo(f"Agent '{name}' removed.")


@agent_group.command(name="remove-all")
@click.option(
    "--keep-file/--no-keep-file",
    default=False,
    help="Keep physical files (default: also delete files)",
)
@click.option("--force", is_flag=True, help="Delete without confirmation prompt")
def agent_remove_all(keep_file: bool, force: bool) -> None:
    """Remove all agents."""
    config = load_config()
    if config is None or not config.agents:
        click.echo("No agents registered.。")
        return

    count = len(config.agents)
    if not force:
        click.confirm(f"Remove all agents ({count})?", abort=True)

    agents_dir = get_agents_dir()

    # Delete files
    if not keep_file and agents_dir.exists():
        for f in agents_dir.iterdir():
            if f.is_file():
                f.unlink()

    config.agents.clear()
    save_config(config)
    click.echo(f"All agents ({count}) removed.")
