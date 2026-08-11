"""skill subcommand implementation.

Manages skill directories under ~/.ai-adapter/skills/.
Parses metadata from SKILL.md YAML frontmatter.
Supports --env for environment-scoped registration and filtering.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import click
import yaml

from ai_adapter.config import (
    add_to_gitignore,
    get_github_skills_dir,
    get_skills_dir,
    is_safe_store_name,
    load_config,
    resolve_env,
    save_config,
)
from ai_adapter.models import Skill
from ai_adapter.providers.cursor import deploy_skills as _cursor_deploy_skills
from ai_adapter.providers.openclaw import deploy_skills as _openclaw_deploy_skills


def _parse_skill_metadata(skill_dir: Path) -> dict:
    """Parse frontmatter from SKILL.md and return metadata."""
    skill_file = skill_dir / "SKILL.md"
    if not skill_file.exists():
        raise click.ClickException(f"SKILL.md not found: {skill_file}")

    content = skill_file.read_text(encoding="utf-8")
    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not match:
        raise click.ClickException("No YAML frontmatter found in SKILL.md")

    return yaml.safe_load(match.group(1)) or {}


@click.group(name="skill")
def skill_group() -> None:
    """Manage skills."""


@skill_group.command(name="list")
@click.option("--tag", help="Filter by tag")
@click.option("--env", "-e", default=None, help="Filter by environment name")
def skill_list(tag: str | None, env: str | None) -> None:
    """List registered skills."""
    config = load_config()
    if config is None:
        click.echo("Configuration file not found. Run ai-adapter init first.")
        return

    skills = config.skills
    if env:
        skills = [s for s in skills if s.env is None or s.env == env]
    if tag:
        skills = [s for s in skills if tag.lower() in {t.lower() for t in s.tags}]

    if not skills:
        click.echo("No skills registered.")
        return

    if env:
        click.echo(f"Skills (env: {env}):")
    else:
        click.echo("Skills:")
    click.echo("-" * 60)
    for skill in skills:
        env_info = f" [{skill.env}]" if skill.env else ""
        agent_info = f" [agent: {skill.agent}]" if skill.agent else ""
        tags_str = f" ({', '.join(skill.tags)})" if skill.tags else ""
        desc = f" - {skill.description}" if skill.description else ""
        click.echo(f"  {skill.name}{env_info}{tags_str}{agent_info}{desc}")


@skill_group.command(name="add")
@click.argument("path", type=click.Path(exists=True, file_okay=False, readable=True))
@click.option("--env", "-e", default=None, help="Environment name (auto-resolved when omitted)")
@click.option("--agent", help="Agent name (for env resolution)")
def skill_add(path: str, env: str | None, agent: str | None) -> None:
    """Add a skill directory to ~/.ai-adapter/skills/.

    PATH: Path to the skill directory containing SKILL.md.

    When --env is omitted, auto-resolves via environment resolution logic.
    """
    src = Path(path).resolve()
    metadata = _parse_skill_metadata(src)
    name = metadata.get("name") or src.name
    if not is_safe_store_name(str(name)):
        raise click.ClickException(f"Invalid skill name '{name}': must be a single path component")

    skills_dir = get_skills_dir()
    skills_dir.mkdir(parents=True, exist_ok=True)
    dest = skills_dir / name

    if dest.exists():
        click.confirm(f"Skill '{name}' already exists. Overwrite?", abort=True)
        shutil.rmtree(dest)

    shutil.copytree(src, dest)

    config = load_config()
    if config is None:
        click.echo("Configuration file not found. Run ai-adapter init first.")
        return

    resolved_env = resolve_env(config, env, agent)
    click.echo(f"Skill '{name}' added (env: {resolved_env}): {dest}")

    # Duplicate check
    for existing in config.skills:
        if existing.name == name and existing.env == resolved_env:
            existing.description = metadata.get("description", "")
            existing.tags = metadata.get("tags", [])
            existing.path = f"skills/{name}"
            save_config(config)
            return

    config.skills.append(
        Skill(
            name=name,
            description=metadata.get("description", ""),
            path=f"skills/{name}",
            tags=metadata.get("tags", []),
            env=resolved_env,
        )
    )
    save_config(config)


@skill_group.command(name="add-rec")
@click.argument("dir_path", type=click.Path(exists=True, file_okay=False, readable=True))
@click.option("--env", "-e", default=None, help="Environment name (auto-resolved when omitted)")
@click.option("--agent", help="Agent name (for env resolution)")
def skill_add_rec(dir_path: str, env: str | None, agent: str | None) -> None:
    """Recursively register all skill directories in a directory."""
    src_dir = Path(dir_path).resolve()
    skills_dir = get_skills_dir()
    skills_dir.mkdir(parents=True, exist_ok=True)

    config = load_config()
    if config is None:
        click.echo("Configuration file not found. Run ai-adapter init first.")
        return

    resolved_env = resolve_env(config, env, agent)
    added = 0
    for d in sorted(src_dir.iterdir()):
        if not d.is_dir():
            continue
        skill_file = d / "SKILL.md"
        if not skill_file.exists():
            continue

        try:
            metadata = _parse_skill_metadata(d)
        except click.ClickException:
            continue

        name = metadata.get("name") or d.name
        if not is_safe_store_name(str(name)):
            click.echo(f"    skip '{d.name}': invalid skill name '{name}'")
            continue
        dest = skills_dir / name
        if dest.exists():
            shutil.rmtree(dest)
        config.skills = [s for s in config.skills if s.name != name or s.env != resolved_env]
        shutil.copytree(d, dest)
        config.skills.append(
            Skill(
                name=name,
                description=metadata.get("description", ""),
                path=f"skills/{name}",
                tags=metadata.get("tags", []),
                env=resolved_env,
            )
        )
        added += 1

    save_config(config)
    click.echo(f"Skills added: {added}")


@skill_group.command(name="get")
@click.argument("name")
@click.option("--env", "-e", default=None, help="Environment name (auto-resolved when omitted)")
@click.option("--agent", help="Agent name (for env resolution)")
@click.option("--force", is_flag=True, help="Overwrite existing skills")
@click.option(
    "--project-dir",
    "-d",
    type=click.Path(exists=True, file_okay=False, readable=True),
    default=None,
    help="Target project directory (default: current directory)",
)
def skill_get(name: str, env: str | None, agent: str | None, force: bool, project_dir: str | None) -> None:
    """Copy skill to .github/skills/.

    NAME: Name of the skill to retrieve.

    When --env is omitted, auto-resolves via environment resolution logic.
    """
    config = load_config()
    if config is None:
        click.echo("Configuration file not found. Run ai-adapter init first.")
        return

    resolved_env = resolve_env(config, env, agent)

    # Search
    skill_entry = None
    for s in config.skills:
        if s.name == name and (s.env is None or s.env == resolved_env):
            skill_entry = s
            break

    if skill_entry is None:
        click.echo(f"Skill '{name}' (env: {resolved_env}) is not registered.", err=True)
        raise click.ClickException(f"Skill '{name}' not found.")

    skills_dir = get_skills_dir()
    src = skills_dir / name
    if not src.exists():
        click.echo(f"Skill directory '{src}' not found.", err=True)
        raise click.ClickException(f"Skill '{name}' directory does not exist.")

    project_path = Path(project_dir).resolve() if project_dir else None
    claude_dir = get_github_skills_dir(project_path)
    claude_dir.mkdir(parents=True, exist_ok=True)
    dest = claude_dir / name

    if dest.exists():
        if force:
            shutil.rmtree(dest)
        else:
            click.confirm(f"'{dest}' already exists. Overwrite?", abort=True)
            shutil.rmtree(dest)

    shutil.copytree(src, dest)
    add_to_gitignore(dest)
    click.echo(f"Skill '{name}' copied to {dest}.")


@skill_group.command(name="remove")
@click.argument("name")
@click.option("--env", "-e", default=None, help="Environment name (auto-resolved when omitted)")
@click.option("--agent", help="Agent name (for env resolution)")
@click.option("--purge", is_flag=True, help="Also delete skill files")
def skill_remove(name: str, env: str | None, agent: str | None, purge: bool) -> None:
    """Remove a skill.

    NAME: Name of the skill to remove.

    When --env is omitted, auto-resolves via environment resolution logic.
    """
    config = load_config()
    if config is None:
        click.echo("Configuration file not found. Run ai-adapter init first.")
        return

    resolved_env = resolve_env(config, env, agent)

    found = None
    for s in config.skills:
        if s.name == name and (s.env is None or s.env == resolved_env):
            found = s
            break

    if found is None:
        click.echo(f"Skill '{name}' (env: {resolved_env}) is not registered.", err=True)
        raise click.ClickException(f"Skill '{name}' not found.")

    config.skills.remove(found)
    save_config(config)

    if purge:
        skills_dir = get_skills_dir()
        target = skills_dir / name
        if target.exists():
            shutil.rmtree(target)
            click.echo(f"Skill directory {target} removed.")

    # Also delete from .github/skills/
    github_dir = get_github_skills_dir()
    target_gh = github_dir / name
    if target_gh.exists():
        shutil.rmtree(target_gh)
        click.echo(f"Removed {name} from .github/skills/.")

    click.echo(f"Skill '{name}' removed.")


def _matching_skills(
    skills: list[Skill],
    keyword: str,
    tag: str | None,
    env: str | None,
) -> list[Skill]:
    """Return registered skills matching *keyword* (name / description / tags).

    Filters are applied in order: environment, then tag, then keyword.
    """
    kw = keyword.lower()
    results: list[Skill] = []
    for s in skills:
        if env and s.env is not None and s.env != env:
            continue
        if tag and tag.lower() not in {t.lower() for t in s.tags}:
            continue
        if kw in s.name.lower() or kw in s.description.lower() or any(kw in t.lower() for t in s.tags):
            results.append(s)
    return results


def _echo_search_hint(tag: str | None) -> None:
    """Print a hint pointing to ``skill list`` after an empty search."""
    if tag:
        click.echo(
            f"Hint: No skill has the tag '{tag}'. Run 'ai-adapter skill list' to see registered skills and tags."
        )
    else:
        click.echo("Hint: Run 'ai-adapter skill list' to see all registered skills.")


@skill_group.command(name="search")
@click.argument("keyword")
@click.option("--tag", help="Filter by tag")
@click.option("--env", "-e", default=None, help="Filter by environment name")
def skill_search(keyword: str, tag: str | None, env: str | None) -> None:
    """Search registered skills by keyword.

    KEYWORD: Keyword to match against skill name, description, and tags.
    """
    config = load_config()
    if config is None:
        click.echo("Configuration file not found. Run ai-adapter init first.")
        return

    results = _matching_skills(config.skills, keyword, tag, env)
    if not results:
        click.echo(f"No matching skills found for '{keyword}'.")
        _echo_search_hint(tag)
        return

    click.echo(f"Search results: '{keyword}'")
    click.echo("-" * 60)
    for s in results:
        env_info = f" [{s.env}]" if s.env else ""
        tags_str = f" ({', '.join(s.tags)})" if s.tags else ""
        agent_info = f" [agent: {s.agent}]" if s.agent else ""
        desc = f" - {s.description}" if s.description else ""
        click.echo(f"  {s.name}{env_info}{tags_str}{agent_info}{desc}")


@skill_group.command(name="link-agent")
@click.argument("skill")
@click.argument("agent")
def skill_link_agent(skill: str, agent: str) -> None:
    """Link a skill to an agent.

    SKILL: Skill name.
    AGENT: Agent name.
    """
    config = load_config()
    if config is None:
        click.echo("Configuration file not found. Run ai-adapter init first.")
        return

    # Skill existence check
    skill_entry = None
    for s in config.skills:
        if s.name == skill:
            skill_entry = s
            break

    if skill_entry is None:
        click.echo(f"Skill '{skill}' is not registered.", err=True)
        raise click.ClickException(f"Skill '{skill}' not found.")

    # Agent existence check
    agent_found = any(a.name == agent for a in config.agents)
    if not agent_found:
        click.echo(f"Agent '{agent}' is not registered.", err=True)
        raise click.ClickException(f"Agent '{agent}' not found.")

    skill_entry.agent = agent
    save_config(config)
    click.echo(f"Skill '{skill}' linked to agent '{agent}'.")


@skill_group.command(name="get-all")
@click.option("--env", "-e", default=None, help="Filter by environment name")
@click.option("--force", is_flag=True, help="Overwrite existing skills")
@click.option(
    "--project-dir",
    "-d",
    type=click.Path(exists=True, file_okay=False, readable=True),
    default=None,
    help="Target project directory (default: current directory)",
)
@click.option(
    "--format",
    "-f",
    "format_name",
    type=click.Choice(["standard", "openclaw", "cursor"]),
    default="standard",
    help="Output format (standard=.github/skills/, openclaw=~/.openclaw/skills/, cursor=.cursor/rules/)",
)
def skill_get_all(env: str | None, force: bool, project_dir: str | None, format_name: str) -> None:
    """Copy all registered skills to project .github/skills/, OpenClaw, or Cursor rules.

    With --format openclaw, deploys to ~/.openclaw/skills/ (OpenClaw user skills).
    With --format cursor, deploys as .cursor/rules/*.mdc files (Cursor rules).
    Existing non-ai-adapter files in the target directory are preserved.
    Use --env to filter by environment.
    """
    config = load_config()
    if config is None or not config.skills:
        click.echo("No skills registered.")
        return

    skills_dir = get_skills_dir()
    targets = config.skills
    if env:
        targets = [s for s in targets if s.env is None or s.env == env]

    if format_name == "openclaw":
        _openclaw_deploy_skills(targets, skills_dir, force)
    elif format_name == "cursor":
        _cursor_deploy_skills(targets, skills_dir, force, project_dir)
    else:
        _deploy_skills_standard(targets, skills_dir, force, project_dir)


def _deploy_skills_standard(
    skills: list[Skill],
    skills_store_dir: Path,
    force: bool,
    project_dir: str | None,
) -> None:
    """Deploy skills to .github/skills/ (standard format)."""
    project_path = Path(project_dir).resolve() if project_dir else None
    claude_dir = get_github_skills_dir(project_path)
    claude_dir.mkdir(parents=True, exist_ok=True)

    copied = 0
    for skill_entry in skills:
        src = skills_store_dir / skill_entry.name
        if not src.exists():
            click.echo(f"   Skip: '{skill_entry.name}' directory not found.")
            continue
        dest = claude_dir / skill_entry.name
        if dest.exists():
            if force:
                shutil.rmtree(dest)
            else:
                click.confirm(f"'{dest}' already exists. Overwrite?", abort=True)
                shutil.rmtree(dest)
        shutil.copytree(src, dest)
        add_to_gitignore(dest)
        copied += 1

    click.echo(f"All skills ({copied}) copied to {claude_dir}.")


@skill_group.command(name="remove-all")
@click.option("--env", "-e", default=None, help="Remove only skills for this environment")
@click.option("--force", is_flag=True, help="Delete without confirmation prompt")
@click.option("--purge", is_flag=True, help="Also delete skill files")
def skill_remove_all(env: str | None, force: bool, purge: bool) -> None:
    """Remove all skills (or only skills matching --env)."""
    config = load_config()
    if config is None or not config.skills:
        click.echo("No skills registered.")
        return

    targets = config.skills
    if env:
        targets = [s for s in targets if s.env == env]
        if not targets:
            click.echo(f"No skills registered for environment '{env}'.")
            return

    count = len(targets)
    if not force:
        click.confirm(f"Remove {count} skill(s)?", abort=True)

    if purge:
        skills_dir = get_skills_dir()
        for s in targets:
            target = skills_dir / s.name
            if target.exists():
                shutil.rmtree(target)

    if env:
        config.skills = [s for s in config.skills if s.env != env]
    else:
        config.skills.clear()
    save_config(config)
    click.echo(f"Removed {count} skill(s).")
