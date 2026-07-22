"""Configuration file management module.

Handles reading, writing, and validation of ~/.ai-adapter/config.json.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

import click

from ai_adapter.models import Config, Env

AI_ADAPTER_DIR = Path.home() / ".ai-adapter"


def get_config_path() -> Path:
    """Return the path to the config file.

    Can be overridden via the AI_ADAPTER_CONFIG environment variable.
    """
    env = os.environ.get("AI_ADAPTER_CONFIG")
    if env:
        return Path(env)
    return AI_ADAPTER_DIR / "config.json"


def get_agents_dir() -> Path:
    """Return ~/.ai-adapter/agents/."""
    return AI_ADAPTER_DIR / "agents"


def get_bins_dir() -> Path:
    """Return ~/.ai-adapter/bin/."""
    return AI_ADAPTER_DIR / "bin"


def get_skills_dir() -> Path:
    """Return ~/.ai-adapter/skills/."""
    return AI_ADAPTER_DIR / "skills"


def get_mcp_dir() -> Path:
    """Return ~/.ai-adapter/mcp/."""
    return AI_ADAPTER_DIR / "mcp"


def get_github_agents_dir(project_dir: Path | None = None) -> Path:
    """Return the current project's .github/agents/ directory.

    Args:
        project_dir: Project directory. Defaults to current directory if None.
    """
    base = project_dir or Path.cwd()
    return base / ".github" / "agents"


def get_github_bins_dir(project_dir: Path | None = None) -> Path:
    """Return the current project's .github/bin/ directory.

    Args:
        project_dir: Project directory. Defaults to current directory if None.
    """
    base = project_dir or Path.cwd()
    return base / ".github" / "bin"


def get_github_skills_dir(project_dir: Path | None = None) -> Path:
    """Return the current project's .github/skills/ directory."""
    base = project_dir or Path.cwd()
    return base / ".github" / "skills"


def get_commands_dir() -> Path:
    """Return ~/.ai-adapter/commands/."""
    return AI_ADAPTER_DIR / "commands"


def get_prompts_dir() -> Path:
    """Return ~/.ai-adapter/prompts/."""
    return AI_ADAPTER_DIR / "prompts"


def get_github_commands_dir(project_dir: Path | None = None) -> Path:
    """Return the current project's .github/commands/ directory."""
    base = project_dir or Path.cwd()
    return base / ".github" / "commands"


def get_github_prompts_dir(project_dir: Path | None = None) -> Path:
    """Return the current project's .github/prompts/ directory."""
    base = project_dir or Path.cwd()
    return base / ".github" / "prompts"


def init() -> bool:
    """Initialize the ~/.ai-adapter/ directory.

    Returns:
        True if newly created, False if already exists.
    """
    dirs = [
        AI_ADAPTER_DIR,
        AI_ADAPTER_DIR / "agents",
        AI_ADAPTER_DIR / "bin",
        AI_ADAPTER_DIR / "skills",
        AI_ADAPTER_DIR / "commands",
        AI_ADAPTER_DIR / "prompts",
        AI_ADAPTER_DIR / "mcp",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)

    config_path = get_config_path()
    if config_path.exists():
        return False

    config = Config(
        version=1,
        default_env="default",
        envs=[
            Env(name="default", description="Default environment"),
        ],
        agent_bindings=[],
    )
    save_config(config)
    return True


def load_config() -> Optional[Config]:
    """Load the configuration file.

    Returns:
        Config object if found, None otherwise.

    Raises:
        click.ClickException: If the configuration file format is invalid.
    """
    config_path = get_config_path()
    if not config_path.exists():
        return None

    with open(config_path) as f:
        data = json.load(f)

    try:
        return Config.from_dict(data)
    except ValueError as e:
        click.echo(f"Invalid configuration file format: {e}", err=True)
        click.echo(f"  File: {config_path}", err=True)
        click.echo("  Fix config.json or run ai-adapter uninstall to reset.", err=True)
        raise click.ClickException("Failed to load configuration file.")


def save_config(config: Config) -> None:
    """Save the configuration file."""
    config_path = get_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w") as f:
        json.dump(config.to_dict(), f, indent=2, ensure_ascii=False)
