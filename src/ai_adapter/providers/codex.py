"""Codex CLI provider integration.

Generates AGENTS.md files for OpenAI Codex CLI from ai-adapter's
registered agents, skills, and instructions.

Codex CLI reads AGENTS.md as plain Markdown (no YAML frontmatter).
"""

from __future__ import annotations

import re
from pathlib import Path

import click

from ai_adapter import config as _config
from ai_adapter.agent_format import parse_frontmatter


def _extract_agents_section(agents_dir: Path) -> list[str]:
    """Extract agent content from .agent.md files (without frontmatter)."""
    sections: list[str] = []
    if not agents_dir.exists():
        return sections

    for f in sorted(agents_dir.iterdir()):
        if not f.is_file():
            continue
        if not (str(f).endswith(".agent.md") or str(f).endswith(".md")):
            continue
        content = f.read_text(encoding="utf-8")
        fm = parse_frontmatter(f)
        name = fm.get("name", "").strip() or f.stem

        # Strip YAML frontmatter block
        stripped = re.sub(r"^---\s*\n.*?\n---\s*\n?", "", content, flags=re.DOTALL).strip()
        if stripped:
            sections.append(stripped)
        else:
            sections.append(f"## {name}")

    return sections


def _extract_instructions_section(instructions_dir: Path) -> list[str]:
    """Extract content from root-level instruction files."""
    sections: list[str] = []
    if not instructions_dir.exists():
        return sections

    for f in sorted(instructions_dir.iterdir()):
        if not f.is_file():
            continue
        if not f.suffix == ".md":
            continue
        content = f.read_text(encoding="utf-8").strip()
        if content:
            sections.append(content)

    return sections


def _extract_skills_section(skills_dir: Path) -> list[str]:
    """Extract skill content from SKILL.md files."""
    sections: list[str] = []
    if not skills_dir.exists():
        return sections

    for d in sorted(skills_dir.iterdir()):
        if not d.is_dir():
            continue
        skill_file = d / "SKILL.md"
        if not skill_file.exists():
            continue
        content = skill_file.read_text(encoding="utf-8").strip()
        if content:
            sections.append(content)

    return sections


def generate_agents_md() -> str:
    """Generate AGENTS.md content from ai-adapter store.

    Combines agents, instructions, and skills into a single
    plain Markdown file suitable for Codex CLI.
    """
    agents_dir = _config.get_agents_dir()
    instructions_dir = _config.get_instructions_dir()
    skills_dir = _config.get_skills_dir()

    sections: list[str] = []

    agents = _extract_agents_section(agents_dir)
    if agents:
        sections.extend(agents)

    instructions = _extract_instructions_section(instructions_dir)
    if instructions:
        sections.extend(instructions)

    skills = _extract_skills_section(skills_dir)
    if skills:
        sections.extend(skills)

    return "\n\n---\n\n".join(sections) + "\n" if sections else ""


@click.group(name="codex")
def codex_group() -> None:
    """Manage Codex CLI integration settings."""


@codex_group.command(name="install")
@click.option("--force", is_flag=True, help="Overwrite existing AGENTS.md without prompting")
def codex_install(force: bool) -> None:
    """Generate AGENTS.md in the current directory for Codex CLI.

    Reads registered agents, instructions, and skills from
    ``~/.ai-adapter/`` and generates a plain Markdown AGENTS.md file.
    """
    content = generate_agents_md()
    if not content:
        click.echo("No agents, instructions, or skills registered.")
        click.echo("Nothing to generate.")
        return

    output_path = Path.cwd() / "AGENTS.md"

    if output_path.exists() and not force:
        click.confirm(f"'{output_path.name}' already exists. Overwrite?", abort=True)

    output_path.write_text(content, encoding="utf-8")
    _config.add_to_gitignore(output_path)
    click.echo(f"AGENTS.md generated: {output_path}")


@codex_group.command(name="uninstall")
def codex_uninstall() -> None:
    """Remove AGENTS.md from the current directory."""
    output_path = Path.cwd() / "AGENTS.md"

    if not output_path.exists():
        click.echo("AGENTS.md not found.")
        return

    output_path.unlink()
    click.echo(f"AGENTS.md removed: {output_path}")
