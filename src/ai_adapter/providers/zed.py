"""Zed editor provider integration (design 06).

Phase A scope:
- Instructions deployment (``AGENTS.md``) from the registered store
- Skills deployment to Zed's actual discovery paths
- Settings **validation only** — ``settings.json`` is never generated or
  merged in Phase A.  Zed's settings carry user-owned editor preferences
  (theme, font, LSP, …); Phase B will merge only the ``agent.*`` section.

Zed discovery paths (Plan C6-1):
- Project skills: ``<project>/.agents/skills/`` — NOT ``.zed/skills/``
  (Zed does not search there).  Nested skills are unsupported: each skill
  must be a direct child of the skills root.
- Global skills: ``~/.agents/skills/``
- Instructions: ``<project>/AGENTS.md`` and the OS-specific Zed user
  directory's ``AGENTS.md``
- Settings: ``<project>/.zed/settings.json`` and the Zed user directory's
  ``settings.json`` (OS-dependent — see ``config.get_zed_user_dir()``)
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import click
import yaml

from ai_adapter import config as _config
from ai_adapter.agent_format import parse_frontmatter_text
from ai_adapter.config import add_to_gitignore, is_safe_store_name, resolve_scope_path
from ai_adapter.models import Config, Skill

# ── Path resolution ─────────────────────────────────────────────────────
# All destinations come from resolve_scope_path() (design 01) — this module
# never re-implements the scope policy.  OS-dependent Zed paths are
# resolved once in config.get_zed_user_dir() (Plan Architect M6-3).


def get_user_config_dir() -> Path:
    """Return the OS-specific Zed user directory.

    macOS: ~/Library/Application Support/Zed/
    Linux: ~/.config/zed/
    Windows: %APPDATA%\\Zed\\

    Thin re-export of :func:`ai_adapter.config.get_zed_user_dir` so
    provider callers keep a Zed-centric entry point while the OS mapping
    stays single-sourced in config.
    """
    return _config.get_zed_user_dir()


def resolve_settings_path(scope: str, project_dir: Path | None = None) -> Path:
    """Return the settings.json path for *scope* (validate-only surface)."""
    base = resolve_scope_path("zed", "settings", scope, project_dir).path
    return base / "settings.json"


def resolve_instructions_path(scope: str, project_dir: Path | None = None, filename: str = "AGENTS.md") -> Path:
    """Return the AGENTS.md path for *scope* (project root or Zed user dir)."""
    base = resolve_scope_path("zed", "instruction", scope, project_dir).path
    return base / filename


def resolve_skills_path(scope: str, project_dir: Path | None = None) -> Path:
    """Return Zed's skill discovery directory for *scope*.

    Zed discovers skills at ``.agents/skills/`` (project) and
    ``~/.agents/skills/`` (global) — Plan C6-1.  ``.zed/skills/`` is NOT a
    Zed discovery path and must never be used as a deploy target.
    """
    return resolve_scope_path("zed", "skills", scope, project_dir).path


# ── Validation helpers (Phase A: validate, never merge) ─────────────────


def validate_settings(path: Path) -> list[str]:
    """Validate a Zed ``settings.json`` structure.

    Checks: valid JSON, top-level object, and ``context_servers`` (Zed's
    MCP key — not ``mcpServers``) is an object of objects when present.
    Returns error messages (empty when valid).
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return [f"{path.name}: not valid JSON: {exc}"]
    if not isinstance(data, dict):
        return [f"{path.name}: must be a JSON object"]
    errors: list[str] = []
    context_servers = data.get("context_servers")
    if context_servers is None:
        return errors
    if not isinstance(context_servers, dict):
        return [f"{path.name}: 'context_servers' must be an object"]
    for name, entry in context_servers.items():
        if not isinstance(entry, dict):
            errors.append(f"{path.name}: context_servers.{name} must be an object")
    return errors


def validate_skill_frontmatter(path: Path) -> list[str]:
    """Validate one ``SKILL.md`` frontmatter block.

    Requires a parseable YAML frontmatter mapping with non-empty ``name``
    and ``description`` — the fields Agent Skills consumers rely on.
    Returns error messages (empty when valid).
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"skill '{path.parent.name}': could not read SKILL.md: {exc}"]
    if not raw.lstrip().startswith("---"):
        return [f"skill '{path.parent.name}': SKILL.md must start with '---' frontmatter"]
    try:
        frontmatter = parse_frontmatter_text(raw)
    except yaml.YAMLError as exc:
        return [f"skill '{path.parent.name}': frontmatter is not valid YAML: {exc}"]
    if not frontmatter:
        return [f"skill '{path.parent.name}': frontmatter is empty or not a mapping"]
    errors: list[str] = []
    if not str(frontmatter.get("name") or "").strip():
        errors.append(f"skill '{path.parent.name}': missing required 'name' field")
    if not str(frontmatter.get("description") or "").strip():
        errors.append(f"skill '{path.parent.name}': missing required 'description' field")
    return errors


# ── Store lookup ────────────────────────────────────────────────────────


def _find_instruction_file(instructions_dir: Path, name: str) -> Path | None:
    """Find a registered instruction file by name (exact file, then stem)."""
    if not instructions_dir.is_dir():
        return None
    exact = instructions_dir / name
    if exact.is_file():
        return exact
    for candidate in sorted(instructions_dir.iterdir()):
        if candidate.is_file() and candidate.stem == name:
            return candidate
    return None


def _build_agents_md(config: Config) -> str:
    """Concatenate registered instruction files into one AGENTS.md body.

    Each instruction gets a ``# <name>`` heading so merged sections stay
    attributable.  Full file content is read from the store — the config
    entry only keeps a short preview.
    """
    instructions_dir = _config.get_instructions_dir()
    sections: list[str] = []
    for inst in config.instructions:
        src = _find_instruction_file(instructions_dir, inst.name)
        body = (src.read_text(encoding="utf-8") if src else inst.content).strip()
        if body:
            sections.append(f"# {inst.name}\n\n{body}")
    if not sections:
        return ""
    return "\n\n".join(sections) + "\n"


# ── Deployment ──────────────────────────────────────────────────────────


def deploy_agents_md(content: str, scope: str, project_dir: Path | None = None, force: bool = False) -> Path:
    """Deploy *content* as the AGENTS.md file for *scope*.

    Uses :func:`resolve_scope_path` for the destination directory and
    honours its gitignore flag (project scope only).
    """
    target = resolve_scope_path("zed", "instruction", scope, project_dir)
    dest = target.path / "AGENTS.md"
    if dest.exists() and not force:
        click.confirm(f"'{dest}' already exists. Overwrite?", abort=True)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(content, encoding="utf-8")
    if target.use_gitignore:
        add_to_gitignore(dest)
    return dest


def deploy_skills(
    skills: list[Skill],
    src_dir: Path,
    scope: str,
    project_dir: Path | None = None,
    force: bool = False,
) -> list[str]:
    """Copy skill directories to Zed's discovery path ``.agents/skills/``.

    Destination (Plan C6-1): ``<project>/.agents/skills/`` for project
    scope, ``~/.agents/skills/`` for user scope — Zed does NOT read
    ``.zed/skills/``.  Skill names are flat (single path component), so
    every skill lands as a direct child of the skills root — the only
    layout Zed discovers.  Project-scope destinations are added to
    ``.gitignore``; user scope never is.

    Returns the deployed ``SKILL.md`` paths.
    """
    target = resolve_scope_path("zed", "skills", scope, project_dir)
    dest_dir = target.path
    dest_dir.mkdir(parents=True, exist_ok=True)

    deployed: list[str] = []
    for skill_entry in skills:
        src = src_dir / skill_entry.name
        if not src.exists():
            click.echo(f"   Skip: '{skill_entry.name}' directory not found.")
            continue
        # Multi-layer guard against path traversal via skill names (QA C2):
        # (1) is_safe_store_name rejects names containing path separators;
        # (2) is_relative_to blocks prefix-sibling escapes like "../skills-evil"
        # that a plain startswith() check would let through.
        if not is_safe_store_name(skill_entry.name):
            click.echo(f"   Skip: '{skill_entry.name}' is not a safe store name.", err=True)
            continue
        dest = (dest_dir / skill_entry.name).resolve()
        if not dest.is_relative_to(dest_dir.resolve()):
            click.echo(
                f"   Skip: '{skill_entry.name}' resolves outside the skills directory.",
                err=True,
            )
            continue
        if dest.exists():
            if force:
                shutil.rmtree(dest)
            else:
                click.confirm(f"'{dest}' already exists. Overwrite?", abort=True)
                shutil.rmtree(dest)
        shutil.copytree(src, dest)
        if target.use_gitignore:
            add_to_gitignore(dest)
        deployed.append(str(dest / "SKILL.md"))

    click.echo(f"Copied {len(deployed)} skills to {dest_dir}.")
    return deployed


# ── CLI group ───────────────────────────────────────────────────────────


@click.group(name="zed")
def zed_group() -> None:
    """Manage Zed editor configuration."""


@zed_group.command(name="install")
@click.option(
    "--scope",
    type=click.Choice(["project", "user"]),
    default="project",
    help=("Deploy scope: project=AGENTS.md + .agents/skills/, user=<Zed user dir>/AGENTS.md + ~/.agents/skills/"),
)
@click.option(
    "--project-dir",
    "-d",
    type=click.Path(exists=True, file_okay=False, readable=True),
    default=None,
    help="Target project directory (default: current directory)",
)
@click.option("--force", is_flag=True, help="Overwrite existing files without prompting")
def zed_install(scope: str, project_dir: str | None, force: bool) -> None:
    """Install Zed configuration from the ai-adapter store.

    Deploys ``AGENTS.md`` (instructions concatenated) and skills to Zed's
    discovery path ``.agents/skills/``.  settings.json is **not** generated
    (Phase A policy — validate only); see ``zed validate``.
    """
    config = _config.load_config()
    if config is None:
        click.echo("Configuration file not found. Run ai-adapter init first.")
        return

    project_path = Path(project_dir).resolve() if project_dir else None
    installed = _install_all(config, scope, project_path, force)
    if not installed:
        click.echo("Nothing to install.")
        return

    click.echo("Zed configuration installed:")
    for path in installed:
        click.echo(f"  {path}")


def _install_all(config: Config, scope: str, project_path: Path | None, force: bool) -> list[str]:
    """Install every store artifact for *scope*; returns the written paths."""
    installed: list[str] = []
    installed.extend(_install_instructions(config, scope, project_path, force))
    installed.extend(_install_skills(config, scope, project_path, force))
    return installed


def _install_instructions(config: Config, scope: str, project_path: Path | None, force: bool) -> list[str]:
    """Deploy concatenated instruction content as AGENTS.md for *scope*."""
    content = _build_agents_md(config)
    if not content:
        return []
    dest = deploy_agents_md(content, scope, project_path, force=force)
    return [str(dest)]


def _install_skills(config: Config, scope: str, project_path: Path | None, force: bool) -> list[str]:
    """Deploy registered skills to Zed's discovery path for *scope*."""
    if not config.skills:
        return []
    return deploy_skills(config.skills, _config.get_skills_dir(), scope, project_dir=project_path, force=force)


@zed_group.command(name="validate")
@click.option("--json", "as_json", is_flag=True, help="Output the report as JSON")
@click.option(
    "--project-dir",
    "-d",
    type=click.Path(exists=True, file_okay=False, readable=True),
    default=None,
    help="Target project directory (default: current directory)",
)
def zed_validate(as_json: bool, project_dir: str | None) -> None:
    """Validate Zed configuration files.

    Checks: AGENTS.md existence (project root or Zed user directory),
    ``.zed/settings.json`` / user ``settings.json`` JSON parse (when
    present), and ``.agents/skills/*/SKILL.md`` frontmatter (when
    present — direct children only, matching Zed's discovery).  Exit
    code: 0 valid, 1 errors.
    """
    base_dir = Path(project_dir).resolve() if project_dir else Path.cwd()
    errors, checked = _run_validations(base_dir)

    if as_json:
        click.echo(json.dumps({"valid": not errors, "errors": errors, "checked": checked}, indent=2))
    elif errors:
        for err in errors:
            click.echo(err, err=True)
    else:
        click.echo("Zed configuration is valid.")

    if errors:
        raise SystemExit(1)


def _run_validations(base_dir: Path) -> tuple[list[str], list[str]]:
    """Validate every Zed config surface; returns ``(errors, checked)``.

    AGENTS.md must exist in at least one scope — design 06 task 06-4 lists
    its existence as a validation target (settings.json, by contrast, is
    optional).  Skills and settings are validated only when present.
    """
    errors: list[str] = []
    checked: list[str] = []

    def _check_file(path: Path, validator) -> None:
        if not path.is_file():
            return
        checked.append(str(path))
        errors.extend(validator(path))

    def _check_skills(root: Path) -> None:
        # Direct children only — Zed does not discover nested skills
        # (Plan C6-1), so deeper SKILL.md files are out of scope here.
        if not root.is_dir():
            return
        for skill_md in sorted(root.glob("*/SKILL.md")):
            checked.append(str(skill_md))
            errors.extend(validate_skill_frontmatter(skill_md))

    user_dir = get_user_config_dir()
    project_agents = base_dir / "AGENTS.md"
    user_agents = user_dir / "AGENTS.md"
    if project_agents.is_file():
        checked.append(str(project_agents))
    if user_agents.is_file():
        checked.append(str(user_agents))
    if not project_agents.is_file() and not user_agents.is_file():
        errors.append("AGENTS.md not found (project root or Zed user directory) — run 'ai-adapter zed install'")

    _check_file(base_dir / ".zed" / "settings.json", validate_settings)
    _check_file(user_dir / "settings.json", validate_settings)
    _check_skills(base_dir / ".agents" / "skills")
    _check_skills(Path.home() / ".agents" / "skills")
    return errors, checked
