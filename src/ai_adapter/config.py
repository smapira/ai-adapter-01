"""Configuration file management module.

Handles reading, writing, and validation of ~/.ai-adapter/config.json.
"""

from __future__ import annotations

import json
import os
import platform
from dataclasses import dataclass
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


def get_instructions_dir() -> Path:
    """Return ~/.ai-adapter/instructions/."""
    return AI_ADAPTER_DIR / "instructions"


def get_github_commands_dir(project_dir: Path | None = None) -> Path:
    """Return the current project's .github/commands/ directory."""
    base = project_dir or Path.cwd()
    return base / ".github" / "commands"


def get_github_prompts_dir(project_dir: Path | None = None) -> Path:
    """Return the current project's .github/prompts/ directory."""
    base = project_dir or Path.cwd()
    return base / ".github" / "prompts"


def get_github_instructions_dir(project_dir: Path | None = None) -> Path:
    """Return the project root directory.

    Used for deploying AGENTS.md (or similar root-level agent files).
    """
    base = project_dir or Path.cwd()
    return base


# Default instruction filename each platform reads (design 01 §2.2).
# get-all --scope user maps every registered file to this name; on
# collision the original filename is kept instead (see instruction.py).
USER_INSTRUCTION_FILENAMES: dict[str, str] = {
    "codex": "AGENTS.md",
    "claude": "CLAUDE.md",
    "opencode": "AGENTS.md",
    "gemini": "GEMINI.md",
    "zed": "AGENTS.md",
}


def get_user_tool_dir(tool: str) -> Path:
    """Return the platform-specific user configuration directory.

    Directories are never created here — deploy commands mkdir at write time,
    so merely asking for a path has no side effects.

    Raises:
        ValueError: When *tool* has no user configuration directory.
    """
    if tool == "zed":
        return get_zed_user_dir()
    if tool not in USER_INSTRUCTION_FILENAMES:
        raise ValueError(f"Unknown tool: {tool}")
    if tool == "opencode":
        return Path.home() / ".config" / "opencode"
    # codex / claude / gemini all follow ~/.<tool>/.
    return Path.home() / f".{tool}"


def get_zed_user_dir(home: Path | None = None) -> Path:
    """Return the OS-specific Zed user config directory.

    Single source of truth for every OS-dependent Zed path (design 06,
    Plan Architect M6-3) — providers, scan, and doctor all resolve through
    here instead of re-deriving platform branches.

    Zed resolves settings.json and the user AGENTS.md from its **config
    directory** (review C1 — verified against Zed source
    ``crates/paths/src/paths.rs`` and https://zed.dev/docs/ai/instructions):

    - macOS: ``~/.config/zed`` (NOT ``~/Library/Application Support/Zed``,
      which is Zed's *data* dir)
    - Linux: ``$XDG_CONFIG_HOME/zed`` if set, else ``~/.config/zed``
    - Windows: ``%APPDATA%\\Zed\\`` (falls back to ``~/AppData/Roaming/Zed/``)

    Args:
        home: Base home directory (defaults to ``Path.home()``).  Scan and
            tests pass an isolated home so path resolution stays testable
            without touching the real user profile.
    """
    base = Path.home() if home is None else Path(home)
    system = platform.system()
    if system == "Windows":
        appdata = os.environ.get("APPDATA")
        appdata_base = Path(appdata) if appdata else base / "AppData" / "Roaming"
        return appdata_base / "Zed"
    # macOS and Linux both use ~/.config/zed (XDG config dir).
    # When an explicit `home` is passed (tests, scan isolation), ignore
    # XDG_CONFIG_HOME so paths stay relative to that home.
    if home is not None:
        return base / ".config" / "zed"
    xdg = os.environ.get("XDG_CONFIG_HOME")
    config_base = Path(xdg) if xdg else base / ".config"
    return config_base / "zed"


def get_user_instruction_path(tool: str, filename: str | None = None) -> Path:
    """Return the platform-specific user-scope instruction file path.

    Args:
        tool: One of codex | claude | opencode | gemini | zed.
        filename: Destination filename. Defaults to the name the platform
            actually reads (see :data:`USER_INSTRUCTION_FILENAMES`).

    Raises:
        ValueError: When *tool* has no user instruction location (e.g. cursor).
    """
    if tool == "cursor":
        raise ValueError("Cursor has no native user instruction path.")
    return get_user_tool_dir(tool) / (filename or USER_INSTRUCTION_FILENAMES[tool])


# Deploy targets for tool × category (design 01 §2.3; reused by designs 02/03/04).
# project paths are relative to the project directory, user paths to the home
# directory. Only listed combinations are valid — anything else raises ValueError.
_PROJECT_SCOPE_DIRS: dict[tuple[str, str], str] = {
    ("claude", "agents"): ".claude/agents",
    ("claude", "skills"): ".claude/skills",
    ("claude", "commands"): ".claude/commands",
    ("claude", "prompts"): ".claude/prompts",
    ("codex", "agents"): ".codex/agents",
    ("codex", "skills"): ".agents/skills",  # spec path (design 03)
    ("codex", "skills_compat"): ".codex/skills",  # opt-in compat mirror (--also-codex-dir)
    ("codex", "rules"): ".codex/rules",
    ("codex", "mcp"): ".codex",  # parent of config.toml (design 03)
    # OpenCode reads .github/* through the .opencode symlink (design 04 §2.2:
    # existing project deploy stays unchanged).
    ("opencode", "agents"): ".github/agents",
    ("opencode", "commands"): ".github/commands",
    ("opencode", "skills"): ".github/skills",
    # Gemini CLI reads custom commands from .gemini/commands/ and MCP
    # servers from .gemini/settings.json (design 05).
    ("gemini", "commands"): ".gemini/commands",
    ("gemini", "mcp"): ".gemini",  # parent of settings.json (design 05)
    # Zed discovers skills at .agents/skills/ (design 06, Plan C6-1 —
    # NOT .zed/skills/, which is not a Zed discovery path). Settings
    # live under .zed/ (parent of settings.json / tasks.json).
    ("zed", "skills"): ".agents/skills",
    ("zed", "settings"): ".zed",
}

_USER_SCOPE_DIRS: dict[tuple[str, str], str] = {
    ("claude", "agents"): ".claude/agents",
    ("claude", "skills"): ".claude/skills",
    ("claude", "commands"): ".claude/commands",
    ("claude", "prompts"): ".claude/prompts",
    ("codex", "agents"): ".codex/agents",
    ("codex", "skills"): ".agents/skills",  # spec path (design 03)
    ("codex", "skills_compat"): ".codex/skills",  # opt-in compat mirror (--also-codex-dir)
    ("codex", "rules"): ".codex/rules",
    ("codex", "mcp"): ".codex",  # parent of config.toml (design 03)
    ("opencode", "agents"): ".config/opencode/agents",
    ("opencode", "commands"): ".config/opencode/commands",
    ("opencode", "skills"): ".config/opencode/skills",
    # Gemini CLI user scope: ~/.gemini/commands/ + ~/.gemini/settings.json.
    ("gemini", "commands"): ".gemini/commands",
    ("gemini", "mcp"): ".gemini",  # parent of settings.json (design 05)
    # Cursor plugin packages live under ~/.cursor/plugins/local/ (design 07).
    # Only user scope exists — Cursor ignores project-local plugin dirs.
    ("cursor", "skills"): ".cursor/plugins/local",
    # Zed global skills live at ~/.agents/skills/ regardless of OS
    # (design 06, Plan C6-1). Settings/instructions stay in the
    # OS-dependent Zed directory (see _resolve_user_scope_dir).
    ("zed", "skills"): ".agents/skills",
}
# zed settings/instruction are OS-dependent → get_user_tool_dir("zed")
# (get_zed_user_dir) instead of this map.


@dataclass(frozen=True)
class ScopeTarget:
    """Resolved deploy destination for one tool × category × scope.

    Attributes:
        path: Destination directory (callers append the file/folder name).
        use_gitignore: Whether the caller should run add_to_gitignore() on the
            deployed file. False for user scope — walking up from $HOME could
            append to a dotfiles repo's .gitignore.
    """

    path: Path
    use_gitignore: bool


def resolve_scope_path(
    tool: str,
    category: str,
    scope: str,
    project_dir: Path | None = None,
) -> ScopeTarget:
    """Resolve the deploy destination for a tool × category × scope.

    Args:
        tool: Platform name (claude, codex, opencode, gemini, zed).
        category: Content category (agents, skills, commands, prompts,
            rules, instruction).
        scope: "project" or "user".
        project_dir: Project directory for project scope (defaults to cwd).

    Returns:
        ScopeTarget with the destination path and the gitignore flag.

    Raises:
        ValueError: Unknown scope, or a tool × category combination that is
            not defined in the matrices above.
    """
    if scope not in ("project", "user"):
        raise ValueError(f"Unknown scope: {scope}")
    use_gitignore = scope == "project"
    if scope == "user":
        path = _resolve_user_scope_dir(tool, category)
    else:
        path = _resolve_project_scope_dir(tool, category, project_dir)
    return ScopeTarget(path=path, use_gitignore=use_gitignore)


def _resolve_user_scope_dir(tool: str, category: str) -> Path:
    """Return the user-scope directory for a tool × category."""
    if category == "instruction":
        # Root-level instruction files (AGENTS.md / CLAUDE.md / GEMINI.md)
        # live directly in the platform directory (Zed is OS-dependent).
        return get_user_tool_dir(tool)
    if tool == "zed" and category == "settings":
        # Zed settings/keymap live in the OS-dependent user directory
        # (get_zed_user_dir) — not expressible in the static map.
        return get_user_tool_dir(tool)
    relative = _USER_SCOPE_DIRS.get((tool, category))
    if relative is None:
        raise ValueError(f"Unsupported tool × category: {tool} × {category}")
    return Path.home() / relative


def _resolve_project_scope_dir(tool: str, category: str, project_dir: Path | None) -> Path:
    """Return the project-scope directory for a tool × category."""
    base = project_dir or Path.cwd()
    if category == "instruction":
        # Root-level instruction files deploy to the project root.
        return base
    relative = _PROJECT_SCOPE_DIRS.get((tool, category))
    if relative is None:
        raise ValueError(f"Unsupported tool × category: {tool} × {category}")
    return base / relative


def is_safe_store_name(name: str) -> bool:
    """Return True when *name* can be used as a single store path component.

    Frontmatter ``name`` values are attacker-controllable (e.g. a skill
    whose SKILL.md declares ``name: ../../evil``).  Joining such a value
    onto a store directory would escape it, and a later ``rmtree`` could
    delete files outside the store.  Rejecting empty names, path
    separators, and "." / ".." keeps every store join inside the store.

    Shared by the scan import hook and ``add-all-rec`` so both follow the
    same policy.
    """
    if not name:
        return False
    return "/" not in name and "\\" not in name and name not in (".", "..")


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
        AI_ADAPTER_DIR / "instructions",
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


def add_to_gitignore(path: Path) -> None:
    """Append a path to .gitignore if not already present.

    Creates .gitignore if it does not exist. Handles project root and
    nested .gitignore files by walking up to the nearest .git directory.

    Args:
        path: The absolute path to add to .gitignore (converted to relative).
    """
    gitignore_path = _find_gitignore_path(path)
    if gitignore_path is None:
        return

    # Compute relative path from the .gitignore's directory
    try:
        rel_path = path.relative_to(gitignore_path.parent)
    except ValueError:
        rel_path = path

    rel_str = str(rel_path)
    if rel_str.startswith("/"):
        pass  # already absolute-style, keep as-is
    elif not rel_str.startswith("/"):
        # Ensure it's rooted so it only matches this specific path
        rel_str = "/" + rel_str

    # Append trailing slash for directories
    if path.is_dir() and not rel_str.endswith("/"):
        rel_str += "/"

    existing = ""
    if gitignore_path.exists():
        existing = gitignore_path.read_text(encoding="utf-8")

    lines = existing.splitlines()
    if rel_str in lines:
        return  # already present

    with open(gitignore_path, "a") as f:
        if existing and not existing.endswith("\n"):
            f.write("\n")
        f.write(f"{rel_str}\n")


def _find_gitignore_path(path: Path) -> Path | None:
    """Find the appropriate .gitignore for a path by walking up to .git.

    Returns the .gitignore path, or None if no .git directory is found.
    """
    for parent in [path] + list(path.parents):
        if (parent / ".git").exists() or (parent / ".git").is_dir():
            return parent / ".gitignore"
    return None


def resolve_env(config: Config, env_arg: str | None, agent_name: str | None = None) -> str:
    """Resolve env when the --env argument is omitted.

    Resolution order:
    1. Explicitly specified --env value
    2. Agent binding (if agent_name is given)
    3. Default environment (config.default_env)

    Args:
        config: Config object.
        env_arg: Explicitly specified env name (None means resolution needed).
        agent_name: Current agent name (optional).

    Returns:
        Resolved environment name.
    """
    if env_arg:
        return env_arg
    if agent_name:
        for binding in config.agent_bindings:
            if binding.agent == agent_name:
                return binding.env
    return config.default_env
