"""CLI entry point.

Defines Click groups and integrates all subcommands.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

import click

from ai_adapter import __version__
from ai_adapter import config as _config
from ai_adapter import diff as _diff
from ai_adapter import git as _git
from ai_adapter.agent import agent_group
from ai_adapter.bin import bin_group
from ai_adapter.command import command_group
from ai_adapter.env import env_group
from ai_adapter.mcp import mcp_group
from ai_adapter.opencode import opencode_group
from ai_adapter.prompt import prompt_group
from ai_adapter.skill import skill_group
from ai_adapter.git import GitError, is_rebasing, get_conflicted_files
from ai_adapter.sync import sync_command

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
)


@click.group()
@click.version_option(version=__version__, prog_name="ai-adapter")
def main() -> None:
    """Unified CLI tool for managing AI agent configurations and scripts"""


@main.command(name="init")
@click.option("--remote", "-r", help="Git remote repository URL")
def cmd_init(remote: str | None) -> None:
    """Initialize ~/.ai-adapter/.

    Prompts interactively when no remote URL is provided.
    """
    created = _config.init()
    if created:
        click.echo(f"Initialized: {_config.AI_ADAPTER_DIR}")
        click.echo(f"Config file: {_config.get_config_path()}")
    else:
        click.echo(f"Already initialized: {_config.AI_ADAPTER_DIR}")

    # Remote configuration
    adapter_dir = _config.AI_ADAPTER_DIR

    if not _git.is_repo(adapter_dir):
        _git.init_repo(adapter_dir)

    if not _git.has_remote(adapter_dir):
        if remote is None:
            click.echo()
            click.echo("--- GitHub Sync Configuration ---")
            click.echo("Enter a GitHub repository URL to share settings across PCs.")
            click.echo("(Press Enter with no input to skip)")
            remote_input = click.prompt(
                "Git remote repository URL",
                default="",
                show_default=False,
            ).strip()
            remote = remote_input if remote_input else None

        if remote:
            _git.add_remote(adapter_dir, "origin", remote)
            config = _config.load_config()
            if config:
                config.remote = remote
                _config.save_config(config)
            click.echo(f"Remote set: {remote}")
            click.echo("Use ai-adapter sync to sync settings.")
        else:
            click.echo("Remote was not configured.")
            click.echo("You can also set it later with ai-adapter start <URL>.")
    else:
        remotes = _git.get_remotes(adapter_dir)
        click.echo(f"Remote already configured: {', '.join(remotes)}")


@main.command(name="status")
def cmd_status() -> None:
    """Show current status with sync diff."""
    adapter_dir = _config.AI_ADAPTER_DIR
    if not adapter_dir.exists():
        click.echo("ai-adapter is not initialized.")
        click.echo("Run ai-adapter init first.")
        return

    config = _config.load_config()
    if config is None:
        click.echo("Configuration file not found.")
        click.echo("Run ai-adapter init first.")
        return

    click.echo("ai-adapter Status:")
    click.echo(f"  Data directory: {adapter_dir}")
    click.echo(f"  Config file: {_config.get_config_path()}")
    click.echo(f"  Version: {config.version}")
    click.echo(f"  Default environment: {config.default_env}")
    click.echo(f"  Registered agents: {len(config.agents)}")
    click.echo(f"  Environments: {len(config.envs)}")
    click.echo(f"  Registered scripts: {len(config.bins)}")
    click.echo(f"  Registered skills: {len(config.skills)}")
    click.echo(f"  MCP servers: {len(config.mcp_servers)}")
    click.echo(f"  Agent bindings: {len(config.agent_bindings)}")
    if config.remote:
        click.echo(f"  Remote: {config.remote}")

    # Directory existence check
    agents_dir = adapter_dir / "agents"
    bins_dir = adapter_dir / "bin"
    skills_dir = adapter_dir / "skills"
    mcp_dir = adapter_dir / "mcp"
    click.echo(f"  agents/ directory: {'✓' if agents_dir.exists() else '✗'}")
    click.echo(f"  bin/ directory: {'✓' if bins_dir.exists() else '✗'}")
    click.echo(f"  skills/ directory: {'✓' if skills_dir.exists() else '✗'}")
    click.echo(f"  mcp/ directory: {'✓' if mcp_dir.exists() else '✗'}")

    # Rebase status
    rebasing = is_rebasing(adapter_dir)
    click.echo(f"  Rebase state: {'⚠ In progress' if rebasing else '✓'}")
    if rebasing:
        conflicted = get_conflicted_files(adapter_dir)
        if conflicted:
            click.echo(f"  Conflicted files: {', '.join(conflicted)}")

    # Sync diff section
    _show_diff(None)


@main.command(name="start")
@click.argument("url")
def cmd_start(url: str) -> None:
    """Initialize ~/.ai-adapter/ with a GitHub remote.

    URL: Git remote repository URL (e.g. git@github.com:user/my-agent-config.git)
    """
    adapter_dir = _config.AI_ADAPTER_DIR

    if adapter_dir.exists():
        click.echo(f"'{adapter_dir}' already exists.")
        click.confirm("Overwrite existing settings? (Settings will be merged)", abort=True)

    # Step 1: Attempt git clone
    click.echo(f"Cloning from remote repository: {url}")
    try:
        _git.clone(url, adapter_dir)
        click.echo("Cloned.")
    except _git.GitError:
        click.echo("Clone failed. Initializing as a new repository.")
        adapter_dir.mkdir(parents=True, exist_ok=True)
        _git.init_repo(adapter_dir)
        _git.add_remote(adapter_dir, "origin", url)
        click.echo(f"Remote set: {url}")

    # Step 2: Initialize directory structure
    dirs = [
        adapter_dir / "agents",
        adapter_dir / "bin",
        adapter_dir / "skills",
        adapter_dir / "mcp",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)

    # Step 3: Generate default config.json if missing
    from ai_adapter.models import Config, Env
    config_path = _config.get_config_path()
    if not config_path.exists():
        config = Config(
            version=1,
            default_env="default",
            envs=[Env(name="default", description="Default environment")],
            agent_bindings=[],
            remote=url,
        )
        _config.save_config(config)
        click.echo("Default configuration file generated.")
    else:
        # Update remote field
        cfg = _config.load_config()
        if cfg:
            cfg.remote = url
            _config.save_config(cfg)

    click.echo(f"Setup complete: {adapter_dir}")
    click.echo(f"Remote: {url}")
    click.echo("Use ai-adapter sync to sync settings.")


@main.command(name="uninstall")
@click.option("--force", is_flag=True, help="Delete without confirmation prompt")
@click.option("--keep-git", is_flag=True, help="Keep Git repository information")
def cmd_uninstall(force: bool, keep_git: bool) -> None:
    """Remove ~/.ai-adapter/ and reset to initial state."""
    adapter_dir = _config.AI_ADAPTER_DIR

    if not adapter_dir.exists():
        click.echo("ai-adapter is not initialized.")
        click.echo("Nothing to delete.")
        return

    # Git repository check
    git_dir = adapter_dir / ".git"
    is_git_repo = git_dir.exists()

    if is_git_repo and not keep_git:
        click.echo("Warning: ~/.ai-adapter/ is managed as a Git repository.")
        click.echo("It is recommended to push remote changes first.")
        click.echo("  cd ~/.ai-adapter && git status")
        click.echo("  git push")

    # Confirmation prompt
    if not force:
        size_info = _get_dir_size(adapter_dir)
        click.echo(f"Delete target: {adapter_dir} ({size_info})")
        click.confirm("Are you sure you want to delete?", abort=True)

    # Delete ~/.ai-adapter/
    if keep_git and is_git_repo:
        _remove_contents_except_git(adapter_dir)
        click.echo(f"Data removed (Git repo kept): {adapter_dir}")
    else:
        shutil.rmtree(adapter_dir)
        click.echo(f"Uninstalled: {adapter_dir}")

    click.echo("You can reinitialize with ai-adapter init.")


def _show_diff(project_dir: str | None) -> None:
    """Show the sync diff between ~/.ai-adapter/ and project .github/ directories."""
    project_path = Path(project_dir).resolve() if project_dir else None

    categories = _diff.compare_all(project_path)
    has_diff = any(c.files for c in categories)

    if not has_diff:
        click.echo()
        click.echo("Sync status: No files found in any category.")
        return

    click.echo()
    click.echo("Sync status (store → project):")
    click.echo("=" * 60)

    for cat in categories:
        if not cat.files:
            continue

        click.echo()
        click.echo(f"  [{cat.category}]")
        click.echo(f"    Store:   {cat.store_dir}")
        click.echo(f"    Project: {cat.project_dir}")

        has_any = False
        for f in cat.files:
            icon = {
                "up-to-date": "✓",
                "added": "➕",
                "modified": "✏️",
                "orphaned": "🗑️",
                "missing_source": "⚠️",
            }.get(f.status, "?")

            label = {
                "up-to-date": "Up to date",
                "added": "Added (use get/get-all)",
                "modified": "Modified (use get/get-all)",
                "orphaned": "Orphaned (not in store)",
                "missing_source": "Source missing",
            }.get(f.status, f.status)

            click.echo(f"    {icon} {f.name:30s} {label}")
            has_any = True

        if not has_any:
            click.echo("    (empty)")

    click.echo()
    click.echo("  Legend: ✓=up-to-date  ➕=added  ✏️=modified  🗑️=orphaned")


def _get_dir_size(path: Path) -> str:
    """Return directory size in human-readable format."""
    total = 0
    for f in path.rglob("*"):
        if f.is_file():
            total += f.stat().st_size
    if total < 1024:
        return f"{total} B"
    elif total < 1024 * 1024:
        return f"{total / 1024:.1f} KB"
    else:
        return f"{total / 1024 / 1024:.1f} MB"


def _remove_contents_except_git(path: Path) -> None:
    """Remove all contents except the Git repository (.git)."""
    for item in path.iterdir():
        if item.name == ".git":
            continue
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()


# Register subcommand groups
main.add_command(agent_group)
main.add_command(env_group)
main.add_command(bin_group)
main.add_command(skill_group)
main.add_command(command_group)
main.add_command(prompt_group)
main.add_command(mcp_group)
main.add_command(opencode_group)


@main.command(name="add-all-rec")
def cmd_add_all_rec() -> None:
    """Import all files under .github/ into ~/.ai-adapter/."""
    github_dir = Path.cwd() / ".github"
    if not github_dir.exists():
        click.echo(f"'.github' directory not found.")

    config = _config.load_config()
    if config is None:
        click.echo("Configuration file not found. Run ai-adapter init first.")
        return

    from ai_adapter.agent import _get_agent_name_from_path
    from ai_adapter.agent_format import parse_frontmatter
    from ai_adapter.models import Agent, Bin, Skill, MCPServer
    from ai_adapter.skill import _parse_skill_metadata
    import json

    total_added = 0

    # 1) agents/
    agents_src = github_dir / "agents"
    if agents_src.exists():
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
        if added:
            click.echo(f"  agents/: {added} registered")
            total_added += added

    # 2) bin/
    bins_src = github_dir / "bin"
    if bins_src.exists():
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
        if added:
            click.echo(f"  bin/: {added} registered")
            total_added += added

    # 3) skills/
    skills_src = github_dir / "skills"
    if skills_src.exists():
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
            config.skills.append(Skill(
                name=name,
                description=metadata.get("description", ""),
                path=f"skills/{name}",
                tags=metadata.get("tags", []),
            ))
            added += 1
        if added:
            click.echo(f"  skills/: {added} registered")
            total_added += added

    # 4) .mcp.json
    mcp_json = Path.cwd() / ".mcp.json"
    if mcp_json.exists():
        try:
            with open(mcp_json) as f:
                data = json.load(f)
            servers_data = data.get("mcpServers", {})
            added = 0
            for name, sd in servers_data.items():
                if not any(s.name == name for s in config.mcp_servers):
                    config.mcp_servers.append(MCPServer(
                        name=name,
                        command=sd.get("command", ""),
                        args=sd.get("args", []),
                        env_keys=list(sd.get("env", {}).keys()),
                        enabled=sd.get("enabled", True),
                        tools=[],
                        env=None,
                    ))
                    added += 1
            if added:
                click.echo(f"  .mcp.json: {added} registered")
                total_added += added
        except (json.JSONDecodeError, Exception) as e:
            click.echo(f"  .mcp.json  failed to load: {e}")

    _config.save_config(config)
    click.echo(f"All imports completed: Total: {total_added}")


@main.command(name="sync")
@click.option("--continue", "do_continue", is_flag=True, help="Continue an interrupted rebase")
@click.option("--abort", "do_abort", is_flag=True, help="Abort the rebase")
@click.option("--skip", "do_skip", is_flag=True, help="Skip the commit")
def cmd_sync(do_continue: bool, do_abort: bool, do_skip: bool) -> None:
    """Sync ~/.ai-adapter/ with a GitHub remote."""
    adapter_dir = _config.AI_ADAPTER_DIR

    if not adapter_dir.exists():
        click.echo(f"'{adapter_dir}' not found. Run ai-adapter init first.")
        raise click.ClickException("ai-adapter is not initialized.")

    # Rebase operation mode
    if do_continue or do_abort or do_skip:
        _handle_rebase_operation(adapter_dir, do_continue, do_abort, do_skip)
        return

    # Normal sync
    from ai_adapter.sync import sync_command
    try:
        sync_command(adapter_dir)
    except GitError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.ClickException(str(e))


def _handle_rebase_operation(
    adapter_dir: Path, do_continue: bool, do_abort: bool, do_skip: bool
) -> None:
    """Handle rebase operations."""
    if not is_rebasing(adapter_dir):
        click.echo("Not currently in a rebase state.")
        return

    if do_abort:
        click.echo("Aborting rebase...")
        _git._run_git(["rebase", "--abort"], cwd=adapter_dir)
        click.echo("Rebase aborted. Restored to original state.")
    elif do_skip:
        click.echo("Skipping commit and continuing rebase...")
        _git._run_git(["rebase", "--skip"], cwd=adapter_dir)
        if is_rebasing(adapter_dir):
            click.echo("There are still commits in the rebase. Check with git status.")
        else:
            click.echo("Push with ai-adapter sync.")
    elif do_continue:
        click.echo("continuing rebase...")
        try:
            _git._run_git(["rebase", "--continue"], cwd=adapter_dir)
            if is_rebasing(adapter_dir):
                click.echo("There are still commits in the rebase.")
            else:
                click.echo("Push with ai-adapter sync.")
        except GitError as e:
            if "Author identity unknown" in str(e):
                click.echo("Git user configuration not set.")
                click.echo("  git config --global user.email 'you@example.com'")
                click.echo("  git config --global user.name 'Your Name'")
            else:
                click.echo(f"Failed to continue rebase: {e}")
