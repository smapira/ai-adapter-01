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
from ai_adapter.providers.claude import deploy_skills as _claude_deploy_skills
from ai_adapter.providers.claude import validate_claude_scope
from ai_adapter.providers.codex import deploy_skills as _codex_deploy_skills
from ai_adapter.providers.cursor import deploy_skills as _cursor_deploy_skills
from ai_adapter.providers.cursor import deploy_skills_plugin
from ai_adapter.providers.openclaw import deploy_skills as _openclaw_deploy_skills
from ai_adapter.providers.zed import deploy_skills as _zed_deploy_skills

# --format choices shared by `skill get` and `skill get-all` (design 07 AC5:
# both commands accept the same format list). "cursor-plugin" installs a true
# Cursor plugin package under ~/.cursor/plugins/local/ (design 07 task 07-2).
SKILL_FORMAT_CHOICES: tuple[str, ...] = (
    "standard",
    "openclaw",
    "cursor",
    "claude",
    "codex",
    "zed",
    "cursor-plugin",
)


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
@click.option(
    "--format",
    "-f",
    "format_name",
    type=click.Choice(SKILL_FORMAT_CHOICES),
    default="standard",
    help=(
        "Output format (standard=.github/skills/, openclaw=~/.openclaw/skills/, "
        "cursor=.cursor/rules/, cursor-plugin=~/.cursor/plugins/local/<project>/, "
        "claude=.claude/skills/, codex=.agents/skills/, "
        "zed=.agents/skills/ — Zed's discovery path)"
    ),
)
def skill_get(
    name: str,
    env: str | None,
    agent: str | None,
    force: bool,
    project_dir: str | None,
    format_name: str,
) -> None:
    """Copy one skill to .github/skills/ or deploy via --format.

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

    if format_name != "standard":
        # Non-standard formats share get-all's provider dispatch (design 07
        # AC5: same --format choices on both commands). skill get has no
        # --scope, so platform formats deploy at project scope.
        _deploy_skills_for_format([skill_entry], skills_dir, format_name, "project", project_dir, force)
        return

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
    help="Target project directory (default: current directory; ignored with --scope user)",
)
@click.option(
    "--format",
    "-f",
    "format_name",
    type=click.Choice(SKILL_FORMAT_CHOICES),
    default="standard",
    help=(
        "Output format (standard=.github/skills/, openclaw=~/.openclaw/skills/, "
        "cursor=.cursor/rules/, cursor-plugin=~/.cursor/plugins/local/<project>/, "
        "claude=.claude/skills/, codex=.agents/skills/, "
        "zed=.agents/skills/ — Zed's discovery path)"
    ),
)
@click.option(
    "--scope",
    type=click.Choice(["project", "user"]),
    default="project",
    help=(
        "Deploy scope for --format claude/codex/zed: project=.claude/skills/ or .agents/skills/, "
        "user=~/.claude/skills/ or ~/.agents/skills/"
    ),
)
@click.option(
    "--also-codex-dir",
    is_flag=True,
    help=(
        "With --format codex: additionally copy each skill to the Codex-native "
        ".codex/skills/ directory (opt-in compat mirror)"
    ),
)
def skill_get_all(
    env: str | None,
    force: bool,
    project_dir: str | None,
    format_name: str,
    scope: str,
    also_codex_dir: bool,
) -> None:
    """Copy all registered skills to project .github/skills/, OpenClaw, Cursor, Claude Code, Codex, or Zed.

    With --format openclaw, deploys to ~/.openclaw/skills/ (OpenClaw user skills).
    With --format cursor, deploys as .cursor/rules/*.mdc files (Cursor rules).
    With --format cursor-plugin, installs a Cursor plugin package under
    ~/.cursor/plugins/local/<project-name>/ (plugin.json + skills/, design 07).
    With --format claude, deploys to .claude/skills/ (or ~/.claude/skills/ with --scope user).
    With --format codex, deploys to .agents/skills/ (or ~/.agents/skills/ with --scope user);
    add --also-codex-dir to also mirror into .codex/skills/.
    With --format zed, deploys to Zed's discovery path .agents/skills/
    (or ~/.agents/skills/ with --scope user) — never .zed/skills/.
    Existing non-ai-adapter files in the target directory are preserved.
    Use --env to filter by environment.
    """
    validate_claude_scope(format_name, scope, ignored_option="--project-dir" if project_dir else None)
    if also_codex_dir and format_name != "codex":
        click.echo("Warning: --also-codex-dir is ignored without --format codex.", err=True)

    config = load_config()
    if config is None or not config.skills:
        click.echo("No skills registered.")
        return

    skills_dir = get_skills_dir()
    targets = config.skills
    if env:
        targets = [s for s in targets if s.env is None or s.env == env]

    _deploy_skills_for_format(
        targets,
        skills_dir,
        format_name,
        scope,
        project_dir,
        force,
        also_codex_dir=also_codex_dir,
    )


def _deploy_skills_for_format(
    targets: list[Skill],
    skills_dir: Path,
    format_name: str,
    scope: str,
    project_dir: str | None,
    force: bool,
    also_codex_dir: bool = False,
) -> None:
    """Deploy *targets* to the destination for *format_name*.

    Shared by ``skill get`` (single skill, project scope) and
    ``skill get-all`` so both commands accept the same ``--format``
    choices (design 07 AC5).
    """
    if format_name == "claude":
        project_path = Path(project_dir).resolve() if project_dir else None
        _claude_deploy_skills(targets, skills_dir, scope=scope, project_dir=project_path, force=force)
    elif format_name == "codex":
        project_path = Path(project_dir).resolve() if project_dir else None
        _codex_deploy_skills(
            targets,
            skills_dir,
            scope=scope,
            project_dir=project_path,
            force=force,
            also_codex_dir=also_codex_dir,
        )
    elif format_name == "zed":
        project_path = Path(project_dir).resolve() if project_dir else None
        _zed_deploy_skills(targets, skills_dir, scope=scope, project_dir=project_path, force=force)
    elif format_name == "openclaw":
        _openclaw_deploy_skills(targets, skills_dir, force)
    elif format_name == "cursor":
        _cursor_deploy_skills(targets, skills_dir, force, project_dir)
    elif format_name == "cursor-plugin":
        deploy_skills_plugin(targets, skills_dir, force=force, project_dir=project_dir)
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


# ---------------------------------------------------------------------------
# skill install (core logic — callable without Click context)
# ---------------------------------------------------------------------------


def install_skill_core(name: str, source: str | None, *, force: bool = False) -> None:
    """Install a skill from a local cache or GitHub repository.

    This is the core logic shared by the ``skill install`` CLI command and
    ``setup apply --install-missing``.  It does **not** depend on a Click
    context, so it can be called as a plain function.

    NAME: Skill name to install.
    SOURCE: Optional ``github:user/repo`` string.  When *None*, resolves
    from the local ``~/.ai-adapter/skills/`` cache.

    Raises ``click.ClickException`` on validation or registration errors so
    callers can present a user-friendly message.
    """
    from ai_adapter.agent_plugins import ValidationIssue, validate_skill_dir

    skills_dir = get_skills_dir()
    skills_dir.mkdir(parents=True, exist_ok=True)
    dest = skills_dir / name

    # --- If skill already exists locally ---
    if dest.is_dir():
        if force:
            shutil.rmtree(dest)
        else:
            click.confirm(f"Skill '{name}' already exists. Overwrite?", abort=True)
            shutil.rmtree(dest)

    if source:
        # --- GitHub source ---
        _install_from_github(name, source, dest)
    else:
        # --- Local cache ---
        from ai_adapter.profiles import resolve_skill_source

        cached = resolve_skill_source(name)
        if cached is None:
            click.echo(f"Skill '{name}' not found locally and no --source specified.", err=True)
            raise click.ClickException(
                f"Skill '{name}' not found. Use --source github:user/repo to install from GitHub."
            )
        shutil.copytree(cached, dest)

    # --- Validate frontmatter before registering ---
    issues: list[ValidationIssue] = []
    validate_skill_dir(dest, issues)
    has_errors = any(i.severity == "error" for i in issues)
    for issue in issues:
        level = "⚠" if issue.severity == "warning" else "✗"
        click.echo(f"  {level} {issue.message}", err=True)
    if has_errors:
        shutil.rmtree(dest)
        raise click.ClickException(f"Skill '{name}' failed validation. Install aborted.")

    # --- Register in config ---
    metadata = _parse_skill_metadata(dest)
    skill_name = metadata.get("name") or name
    if not is_safe_store_name(skill_name):
        shutil.rmtree(dest)
        raise click.ClickException(f"Invalid skill name '{skill_name}': must be a single path component")

    config = load_config()
    if config is None:
        click.echo("Configuration file not found. Run ai-adapter init first.")
        return

    # Duplicate check
    for existing in config.skills:
        if existing.name == skill_name:
            existing.description = metadata.get("description", "")
            existing.tags = metadata.get("tags", [])
            existing.path = f"skills/{skill_name}"
            save_config(config)
            click.echo(f"Skill '{skill_name}' installed and updated.")
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
    click.echo(f"Skill '{skill_name}' installed.")


# ---------------------------------------------------------------------------
# skill install (Click command)
# ---------------------------------------------------------------------------


@skill_group.command(name="install")
@click.argument("name")
@click.option("--source", default=None, help="Source (github:user/repo). Default: local cache.")
@click.option("--force", is_flag=True, help="Overwrite existing skill without confirmation")
def skill_install(name: str, source: str | None, force: bool) -> None:
    """Install a skill from a local cache or GitHub repository.

    NAME: Skill name to install.

    Resolution order (when --source is omitted):
      1. Local cache:  ~/.ai-adapter/skills/<name>/ (if present, reuse)
      2. Error: skill not found locally
    """
    install_skill_core(name, source, force=force)


def _install_from_github(name: str, source: str, dest: Path) -> None:
    """Clone a skill from a GitHub repository.

    ``source`` format: ``github:user/repo``
    """
    from ai_adapter.git import GitError, _run_git

    if not source.startswith("github:"):
        raise click.ClickException(f"Invalid source format '{source}'. Expected 'github:user/repo'.")

    repo_path = source[len("github:") :]
    if "/" not in repo_path:
        raise click.ClickException(f"Invalid GitHub source '{repo_path}'. Expected format: user/repo")

    url = f"https://github.com/{repo_path}.git"

    click.echo(f"Cloning from {url}...")
    tmp_dir = dest.parent / f".tmp-{name}"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    try:
        _run_git(["clone", "--depth", "1", url, str(tmp_dir)])

        # Look for SKILL.md in the cloned repo
        skill_md = tmp_dir / "SKILL.md"
        if skill_md.exists():
            shutil.copytree(tmp_dir, dest)
        else:
            # Maybe the skill is in a subdirectory
            sub = tmp_dir / name
            if sub.is_dir() and (sub / "SKILL.md").exists():
                shutil.copytree(sub, dest)
            else:
                raise click.ClickException(f"No SKILL.md found in {repo_path}. Is this a valid skill repository?")
    except GitError as e:
        raise click.ClickException(f"Git clone failed: {e}")
    finally:
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir)
