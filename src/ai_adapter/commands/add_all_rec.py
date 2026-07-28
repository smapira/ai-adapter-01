"""add-all-rec command implementation.

Imports all files under .github/ into ~/.ai-adapter/.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import click

from ai_adapter import config as _config


def _import_agents(config: _config.Config, github_dir: Path) -> int:
    """Import .github/agents/ files into config."""
    agents_src = github_dir / "agents"
    if not agents_src.exists():
        click.echo("  agents/: skip (directory not found)")
        return 0

    from ai_adapter.agent_format import parse_frontmatter
    from ai_adapter.commands.agent import _get_agent_name_from_path
    from ai_adapter.models import Agent

    agents_dir = _config.get_agents_dir()
    agents_dir.mkdir(parents=True, exist_ok=True)
    added = 0
    for f in sorted(agents_src.rglob("*")):
        if not f.is_file():
            continue
        dest = agents_dir / f.name
        if str(f).endswith(".agent.md"):
            fm = parse_frontmatter(f)
            if not fm or not fm.get("name", "").strip():
                continue
        name = _get_agent_name_from_path(f)
        config.agents = [a for a in config.agents if a.name != name]
        shutil.copy2(f, dest)
        config.agents.append(Agent(name=name))
        added += 1
    click.echo(f"  agents/: {added} registered")
    return added


def _import_bins(config: _config.Config, github_dir: Path) -> int:
    """Import .github/bin/ files into config."""
    bins_src = github_dir / "bin"
    if not bins_src.exists():
        click.echo("  bin/: skip (directory not found)")
        return 0

    from ai_adapter.models import Bin

    bins_dir = _config.get_bins_dir()
    bins_dir.mkdir(parents=True, exist_ok=True)
    resolved_env = config.default_env
    added = 0
    for f in sorted(bins_src.rglob("*")):
        if not f.is_file():
            continue
        dest = bins_dir / f.name
        config.bins = [b for b in config.bins if b.name != f.name]
        shutil.copy2(f, dest)
        config.bins.append(Bin(name=f.name, env=resolved_env))
        added += 1
    click.echo(f"  bin/: {added} registered")
    return added


def _import_skills(config: _config.Config, github_dir: Path) -> int:
    """Import .github/skills/ directories into config."""
    skills_src = github_dir / "skills"
    if not skills_src.exists():
        click.echo("  skills/: skip (directory not found)")
        return 0

    from ai_adapter.commands.skill import _parse_skill_metadata
    from ai_adapter.models import Skill

    skills_dir = _config.get_skills_dir()
    skills_dir.mkdir(parents=True, exist_ok=True)
    added = 0
    for d in sorted(skills_src.iterdir()):
        if not d.is_dir():
            continue
        skill_file = d / "SKILL.md"
        if not skill_file.exists():
            continue
        try:
            metadata = _parse_skill_metadata(d)
        except Exception:
            continue
        name = metadata.get("name") or d.name
        dest = skills_dir / name
        if dest.exists():
            shutil.rmtree(dest)
        config.skills = [s for s in config.skills if s.name != name]
        shutil.copytree(d, dest)
        config.skills.append(
            Skill(
                name=name,
                description=metadata.get("description", ""),
                path=f"skills/{name}",
                tags=metadata.get("tags", []),
            )
        )
        added += 1
    click.echo(f"  skills/: {added} registered")
    return added


def _import_mcp_servers(config: _config.Config) -> int:
    """Import .mcp.json server entries into config."""
    import json

    mcp_json = Path.cwd() / ".mcp.json"
    if not mcp_json.exists():
        click.echo("  .mcp.json: skip (file not found)")
        return 0

    from ai_adapter.models import MCPServer

    try:
        with open(mcp_json) as f:
            data = json.load(f)
        servers_data = data.get("mcpServers", {})
        added = 0
        for name, sd in servers_data.items():
            if not any(s.name == name for s in config.mcp_servers):
                config.mcp_servers.append(
                    MCPServer(
                        name=name,
                        command=sd.get("command", ""),
                        args=sd.get("args", []),
                        env_keys=list(sd.get("env", {}).keys()),
                        enabled=sd.get("enabled", True),
                        tools=[],
                        env=None,
                    )
                )
                added += 1
        click.echo(f"  .mcp.json: {added} registered")
        return added
    except (json.JSONDecodeError, Exception) as e:
        click.echo(f"  .mcp.json  failed to load: {e}")
        return 0


def _import_root_instructions(config: _config.Config) -> int:
    """Import root-level instruction files (AGENTS.md, CLAUDE.md, etc.)."""
    from ai_adapter.models import Instruction

    root_names = ["AGENTS.md", "AGENT.md", "CLAUDE.md", "copilot-instructions.md"]
    instructions_dir = _config.get_instructions_dir()
    instructions_dir.mkdir(parents=True, exist_ok=True)
    added = 0
    for fname in root_names:
        candidate = Path.cwd() / fname
        if not candidate.exists():
            continue
        dest = instructions_dir / fname
        if not dest.exists():
            shutil.copy2(candidate, dest)
        name = candidate.stem
        config.instructions = [i for i in config.instructions if i.name != name]
        config.instructions.append(Instruction(name=name))
        added += 1
    if added:
        click.echo(f"  root instructions/: {added} registered")
    else:
        click.echo("  root instructions: skip (no root-level files found)")
    return added


@click.command(name="add-all-rec")
def cmd_add_all_rec() -> None:
    """Import all files under .github/ into ~/.ai-adapter/."""
    github_dir = Path.cwd() / ".github"
    if not github_dir.exists():
        github_dir.mkdir(parents=True, exist_ok=True)
        click.echo(f"'{github_dir}/' created.")

    config = _config.load_config()
    if config is None:
        click.echo("Configuration file not found. Run ai-adapter init first.")
        return

    total = 0
    total += _import_agents(config, github_dir)
    total += _import_bins(config, github_dir)
    total += _import_skills(config, github_dir)
    total += _import_mcp_servers(config)
    total += _import_root_instructions(config)

    _config.save_config(config)
    click.echo(f"All imports completed: Total: {total}")
