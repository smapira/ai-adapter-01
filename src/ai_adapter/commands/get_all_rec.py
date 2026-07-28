"""get-all-rec command implementation.

Deploys all registered items from ~/.ai-adapter/ to .github/.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import click

from ai_adapter import config as _config
from ai_adapter.agent_format import parse_frontmatter as _parse_frontmatter


def _find_agent_source(agents_dir: Path, name: str) -> Path | None:
    """Find an agent file by frontmatter name or filename."""
    for f in agents_dir.iterdir():
        if not f.is_file():
            continue
        try:
            fm = _parse_frontmatter(f)
            if fm.get("name", "").strip() == name:
                return f
        except Exception:
            continue
    candidates = [
        agents_dir / f"{name}.agent.md",
        agents_dir / f"{name}.md",
        agents_dir / name,
    ]
    for c in candidates:
        if c.exists() and c.is_file():
            return c
    return None


def _copy_with_confirm(src: Path, dest: Path, force: bool) -> None:
    """Copy *src* to *dest*, prompting before overwrite unless *force*."""
    if dest.exists() and not force:
        click.confirm(f"Overwrite '{dest.name}'?", abort=True)
    shutil.copy2(src, dest)
    _config.add_to_gitignore(dest)


def _deploy_agents(config: _config.Config, project_path: Path | None, force: bool) -> int:
    """Deploy registered agents to .github/agents/."""
    agents_dir = _config.get_agents_dir()
    if not agents_dir.exists() or not config.agents:
        click.echo("  agents/: skip (no registered agents)")
        return 0
    github_agents_dir = _config.get_github_agents_dir(project_path)
    github_agents_dir.mkdir(parents=True, exist_ok=True)
    deployed = 0
    for agent_cfg in config.agents:
        src = _find_agent_source(agents_dir, agent_cfg.name)
        if src is None:
            click.echo(f"   Skip agent: '{agent_cfg.name}' file not found.")
            continue
        dest = github_agents_dir / src.name
        _copy_with_confirm(src, dest, force)
        deployed += 1
    click.echo(f"  agents/: {deployed} deployed")
    return deployed


def _deploy_bins(config: _config.Config, project_path: Path | None, force: bool) -> int:
    """Deploy registered scripts to .github/bin/."""
    bins_dir = _config.get_bins_dir()
    if not bins_dir.exists() or not config.bins:
        click.echo("  bin/: skip (no registered scripts)")
        return 0
    github_bins_dir = _config.get_github_bins_dir(project_path)
    github_bins_dir.mkdir(parents=True, exist_ok=True)
    deployed = 0
    for bin_entry in config.bins:
        src = bins_dir / bin_entry.name
        if not src.exists():
            click.echo(f"   Skip script: '{bin_entry.name}' file not found.")
            continue
        dest = github_bins_dir / bin_entry.name
        _copy_with_confirm(src, dest, force)
        deployed += 1
    click.echo(f"  bin/: {deployed} deployed")
    return deployed


def _deploy_skills(config: _config.Config, project_path: Path | None, force: bool) -> int:
    """Deploy registered skills to .github/skills/."""
    skills_dir = _config.get_skills_dir()
    if not skills_dir.exists() or not config.skills:
        click.echo("  skills/: skip (no registered skills)")
        return 0
    github_skills_dir = _config.get_github_skills_dir(project_path)
    github_skills_dir.mkdir(parents=True, exist_ok=True)
    deployed = 0
    for skill_entry in config.skills:
        src = skills_dir / skill_entry.name
        if not src.exists():
            click.echo(f"   Skip skill: '{skill_entry.name}' directory not found.")
            continue
        dest = github_skills_dir / skill_entry.name
        if dest.exists():
            if force:
                shutil.rmtree(dest)
            else:
                click.confirm(f"Overwrite '{dest.name}'?", abort=True)
                shutil.rmtree(dest)
        shutil.copytree(src, dest)
        _config.add_to_gitignore(dest)
        deployed += 1
    click.echo(f"  skills/: {deployed} deployed")
    return deployed


def _deploy_commands(config: _config.Config, project_path: Path | None, force: bool) -> int:
    """Deploy registered commands to .github/commands/."""
    commands_dir = _config.get_commands_dir()
    if not commands_dir.exists() or not config.commands:
        click.echo("  commands/: skip (no registered commands)")
        return 0
    github_commands_dir = _config.get_github_commands_dir(project_path)
    github_commands_dir.mkdir(parents=True, exist_ok=True)
    deployed = 0
    for cmd_entry in config.commands:
        src = _find_command_file(commands_dir, cmd_entry.name)
        if src is None:
            click.echo(f"   Skip command: '{cmd_entry.name}' file not found.")
            continue
        dest = github_commands_dir / src.name
        _copy_with_confirm(src, dest, force)
        deployed += 1
    click.echo(f"  commands/: {deployed} deployed")
    return deployed


def _deploy_prompts(config: _config.Config, project_path: Path | None, force: bool) -> int:
    """Deploy registered prompts to .github/prompts/."""
    prompts_dir = _config.get_prompts_dir()
    if not prompts_dir.exists() or not config.prompts:
        click.echo("  prompts/: skip (no registered prompts)")
        return 0
    github_prompts_dir = _config.get_github_prompts_dir(project_path)
    github_prompts_dir.mkdir(parents=True, exist_ok=True)
    deployed = 0
    for prompt_entry in config.prompts:
        src = _find_prompt_file(prompts_dir, prompt_entry.name)
        if src is None:
            click.echo(f"   Skip prompt: '{prompt_entry.name}' file not found.")
            continue
        dest = github_prompts_dir / src.name
        _copy_with_confirm(src, dest, force)
        deployed += 1
    click.echo(f"  prompts/: {deployed} deployed")
    return deployed


def _deploy_mcp(config: _config.Config, project_path: Path | None, force: bool) -> int:
    """Deploy enabled MCP servers to .mcp.json."""
    import json

    enabled_servers = [s for s in config.mcp_servers if s.enabled]
    if not enabled_servers:
        click.echo("  .mcp.json: skip (no enabled MCP servers)")
        return 0

    mcp_config: dict = {"mcpServers": {}}
    for server in enabled_servers:
        env_dict = {}
        for key in server.env_keys:
            env_dict[key] = f"${{{key}}}"
        entry: dict = {"command": server.command, "args": server.args}
        if env_dict:
            entry["env"] = env_dict
        mcp_config["mcpServers"][server.name] = entry

    base = project_path or Path.cwd()
    output_path = base / ".mcp.json"
    if output_path.exists() and not force:
        click.confirm("Overwrite '.mcp.json'?", abort=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(mcp_config, f, indent=2, ensure_ascii=False)
    _config.add_to_gitignore(output_path)
    click.echo(f"  .mcp.json: {len(enabled_servers)} servers exported")
    return 1


def _deploy_instructions(config: _config.Config, project_path: Path | None, force: bool) -> int:
    """Deploy registered instructions to .github/ root."""
    instructions_dir = _config.get_instructions_dir()
    if not instructions_dir.exists() or not config.instructions:
        click.echo("  instructions/: skip (no registered instructions)")
        return 0
    root_dir = _config.get_github_instructions_dir(project_path)
    deployed = 0
    for inst_entry in config.instructions:
        src = _find_instruction_file(instructions_dir, inst_entry.name)
        if src is None:
            click.echo(f"   Skip instruction: '{inst_entry.name}' file not found.")
            continue
        dest = root_dir / src.name
        _copy_with_confirm(src, dest, force)
        deployed += 1
    click.echo(f"  instructions/: {deployed} deployed")
    return deployed


@click.command(name="get-all-rec")
@click.option("--force", is_flag=True, help="Overwrite existing files without prompting")
@click.option(
    "--project-dir",
    "-d",
    type=click.Path(exists=True, file_okay=False, readable=True),
    default=None,
    help="Target project directory (default: current directory)",
)
def cmd_get_all_rec(force: bool, project_dir: str | None) -> None:
    """Deploy all registered items to .github/ (reverse of add-all-rec)."""
    config = _config.load_config()
    if config is None:
        click.echo("Configuration file not found. Run ai-adapter init first.")
        return

    project_path = Path(project_dir).resolve() if project_dir else None
    total = 0
    total += _deploy_agents(config, project_path, force)
    total += _deploy_bins(config, project_path, force)
    total += _deploy_skills(config, project_path, force)
    total += _deploy_commands(config, project_path, force)
    total += _deploy_prompts(config, project_path, force)
    total += _deploy_mcp(config, project_path, force)
    total += _deploy_instructions(config, project_path, force)
    click.echo(f"All deployments completed: Total: {total}")


def _find_command_file(commands_dir: Path, name: str) -> Path | None:
    """Find a command file by name in the store directory."""
    exact = commands_dir / name
    if exact.exists() and exact.is_file():
        return exact
    for f in sorted(commands_dir.iterdir()):
        if f.is_file() and f.stem == name:
            return f
    return None


def _find_prompt_file(prompts_dir: Path, name: str) -> Path | None:
    """Find a prompt file by name in the store directory."""
    exact = prompts_dir / name
    if exact.exists() and exact.is_file():
        return exact
    for f in sorted(prompts_dir.iterdir()):
        if f.is_file() and f.stem == name:
            return f
    return None


def _find_instruction_file(instructions_dir: Path, name: str) -> Path | None:
    """Find an instruction file by name in the store directory."""
    exact = instructions_dir / name
    if exact.exists() and exact.is_file():
        return exact
    for f in sorted(instructions_dir.iterdir()):
        if f.is_file() and f.stem == name:
            return f
    return None
