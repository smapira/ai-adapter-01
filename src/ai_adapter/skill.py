"""skill サブコマンドの実装。

~/.ai-adapter/skills/ 配下のスキルディレクトリを管理する。
SKILL.md の YAML frontmatter からメタデータをパースする。
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import click
import yaml

from ai_adapter.config import (
    get_github_skills_dir,
    get_skills_dir,
    load_config,
    save_config,
)
from ai_adapter.models import Skill


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
def skill_list(tag: str | None) -> None:
    """List registered skills."""
    config = load_config()
    if config is None:
        click.echo("Configuration file not found. Run ai-adapter init first.")
        return

    skills = config.skills
    if tag:
        skills = [s for s in skills if tag in s.tags]

    if not skills:
        click.echo("No skills registered.")
        return

    click.echo("Skills:")
    click.echo("-" * 60)
    for skill in skills:
        agent_info = f" [agent: {skill.agent}]" if skill.agent else ""
        tags_str = f" ({', '.join(skill.tags)})" if skill.tags else ""
        desc = f" - {skill.description}" if skill.description else ""
        click.echo(f"  {skill.name}{tags_str}{agent_info}{desc}")


@skill_group.command(name="add")
@click.argument("path", type=click.Path(exists=True, file_okay=False, readable=True))
def skill_add(path: str) -> None:
    """Add a skill directory to ~/.ai-adapter/skills/.

    PATH: Path to the skill directory containing SKILL.md.
    """
    src = Path(path).resolve()
    metadata = _parse_skill_metadata(src)
    name = metadata.get("name") or src.name

    skills_dir = get_skills_dir()
    skills_dir.mkdir(parents=True, exist_ok=True)
    dest = skills_dir / name

    if dest.exists():
        click.confirm(f"Skill '{name}' already exists. Overwrite?", abort=True)
        shutil.rmtree(dest)

    shutil.copytree(src, dest)
    click.echo(f"Skill '{name}' added: {dest}")

    config = load_config()
    if config is None:
        click.echo("Configuration file not found. Run ai-adapter init first.")
        return

    # 重複チェック
    for existing in config.skills:
        if existing.name == name:
            existing.description = metadata.get("description", "")
            existing.tags = metadata.get("tags", [])
            existing.path = f"skills/{name}"
            save_config(config)
            return

    config.skills.append(Skill(
        name=name,
        description=metadata.get("description", ""),
        path=f"skills/{name}",
        tags=metadata.get("tags", []),
    ))
    save_config(config)


@skill_group.command(name="add-rec")
@click.argument("dir_path", type=click.Path(exists=True, file_okay=False, readable=True))
def skill_add_rec(dir_path: str) -> None:
    """Recursively register all skill directories in a directory."""
    src_dir = Path(dir_path).resolve()
    skills_dir = get_skills_dir()
    skills_dir.mkdir(parents=True, exist_ok=True)

    config = load_config()
    if config is None:
        click.echo("Configuration file not found. Run ai-adapter init first.")
        return

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
        dest = skills_dir / name
        if dest.exists():
            shutil.rmtree(dest)
        config.skills = [s for s in config.skills if s.name != name]
        shutil.copytree(d, dest)
        config.skills.append(Skill(
            name=name,
            description=metadata.get("description", ""),
            path=f"skills/{name}",
            tags=metadata.get("tags", []),
        ))
        added += 1

    save_config(config)
    click.echo(f"Skills added: {added}")


@skill_group.command(name="get")
@click.argument("name")
@click.option("--force", is_flag=True, help="Overwrite existing skills")
@click.option(
    "--project-dir", "-d",
    type=click.Path(exists=True, file_okay=False, readable=True),
    default=None,
    help="Target project directory (default: current directory)",
)
def skill_get(name: str, force: bool, project_dir: str | None) -> None:
    """スキルを .github/skills/ にコピーする。

    NAME: 取得するスキル名。
    """
    config = load_config()
    if config is None:
        click.echo("Configuration file not found. Run ai-adapter init first.")
        return

    # 検索
    skill_entry = None
    for s in config.skills:
        if s.name == name:
            skill_entry = s
            break

    if skill_entry is None:
        click.echo(f"Skill '{name}' is not registered.", err=True)
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
    click.echo(f"Skill '{name}' copied to {dest}.")


@skill_group.command(name="remove")
@click.argument("name")
@click.option("--purge", is_flag=True, help="Also delete skill files")
def skill_remove(name: str, purge: bool) -> None:
    """Remove a skill.

    NAME: Name of the skill to remove.
    """
    config = load_config()
    if config is None:
        click.echo("Configuration file not found. Run ai-adapter init first.")
        return

    found = None
    for s in config.skills:
        if s.name == name:
            found = s
            break

    if found is None:
        click.echo(f"Skill '{name}' is not registered.", err=True)
        raise click.ClickException(f"Skill '{name}' not found.")

    config.skills.remove(found)
    save_config(config)

    if purge:
        skills_dir = get_skills_dir()
        target = skills_dir / name
        if target.exists():
            shutil.rmtree(target)
            click.echo(f"Skill directory {target} removed.")

    # .github/skills/ からも削除
    github_dir = get_github_skills_dir()
    target_gh = github_dir / name
    if target_gh.exists():
        shutil.rmtree(target_gh)
        click.echo(f"Removed {name} from .github/skills/.")

    click.echo(f"Skill '{name}' removed.")


@skill_group.command(name="search")
@click.argument("keyword")
def skill_search(keyword: str) -> None:
    """Search skills by keyword.

    KEYWORD: Keyword to match against skill name, description, and tags.
    """
    config = load_config()
    if config is None:
        click.echo("Configuration file not found. Run ai-adapter init first.")
        return

    kw = keyword.lower()
    results = []
    for s in config.skills:
        if (kw in s.name.lower()
                or kw in s.description.lower()
                or any(kw in t.lower() for t in s.tags)):
            results.append(s)

    if not results:
        click.echo(f"No skills matching '{keyword}'.")
        return

    click.echo(f"Search results: '{keyword}'")
    click.echo("-" * 60)
    for s in results:
        tags_str = f" ({', '.join(s.tags)})" if s.tags else ""
        agent_info = f" [agent: {s.agent}]" if s.agent else ""
        desc = f" - {s.description}" if s.description else ""
        click.echo(f"  {s.name}{tags_str}{agent_info}{desc}")


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

    # スキル存在チェック
    skill_entry = None
    for s in config.skills:
        if s.name == skill:
            skill_entry = s
            break

    if skill_entry is None:
        click.echo(f"Skill '{skill}' is not registered.", err=True)
        raise click.ClickException(f"Skill '{skill}' not found.")

    # エージェント存在チェック
    agent_found = any(a.name == agent for a in config.agents)
    if not agent_found:
        click.echo(f"Agent '{agent}' は登録されていません。", err=True)
        raise click.ClickException(f"Agent '{agent}' not found.")

    skill_entry.agent = agent
    save_config(config)
    click.echo(f"Skill '{skill}' linked to agent '{agent}'.")


@skill_group.command(name="get-all")
@click.option("--force", is_flag=True, help="Overwrite existing skills")
@click.option(
    "--project-dir", "-d",
    type=click.Path(exists=True, file_okay=False, readable=True),
    default=None,
    help="Target project directory (default: current directory)",
)
def skill_get_all(force: bool, project_dir: str | None) -> None:
    """All imports済みスキルを .github/skills/ にコピーする。"""
    config = load_config()
    if config is None or not config.skills:
        click.echo("No skills registered.")
        return

    skills_dir = get_skills_dir()
    project_path = Path(project_dir).resolve() if project_dir else None
    claude_dir = get_github_skills_dir(project_path)
    claude_dir.mkdir(parents=True, exist_ok=True)

    copied = 0
    for skill_entry in config.skills:
        src = skills_dir / skill_entry.name
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
        copied += 1

    click.echo(f"All skills ({copied}) を {claude_dir} にコピーしました。")


@skill_group.command(name="remove-all")
@click.option("--force", is_flag=True, help="Delete without confirmation prompt")
@click.option("--purge", is_flag=True, help="Also delete skill files")
def skill_remove_all(force: bool, purge: bool) -> None:
    """Remove all skills."""
    config = load_config()
    if config is None or not config.skills:
        click.echo("No skills registered.")
        return

    count = len(config.skills)
    if not force:
        click.confirm(f"All skills ({count})?", abort=True)

    if purge:
        skills_dir = get_skills_dir()
        for s in config.skills:
            target = skills_dir / s.name
            if target.exists():
                shutil.rmtree(target)

    config.skills.clear()
    save_config(config)
    click.echo(f"All skills ({count}) removed.")
