"""Diff module for comparing ~/.ai-adapter/ with project .github/ directories.

Provides the status comparison logic used by `ai-adapter status --diff`.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import NamedTuple

from ai_adapter import config as _config
from ai_adapter.models import Config


class FileDiff(NamedTuple):
    """Diff result for a single file."""

    name: str
    status: str  # "up-to-date", "added", "modified", "orphaned", "missing_source"
    rel_path: str  # Relative path within the category


class CategoryDiff(NamedTuple):
    """Diff result for a whole category."""

    category: str
    store_dir: Path
    project_dir: Path
    files: list[FileDiff]


def _file_hash(path: Path) -> str | None:
    """Return SHA-256 hex digest of a file, or None if unreadable."""
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except (OSError, PermissionError):
        return None


def _list_store_files(store_dir: Path, is_dir_category: bool = False) -> dict[str, Path]:
    """List files in a store directory, returning {name: path}.

    For file-based categories (agents, bins, commands, prompts) scans files.
    For directory-based categories (skills) scans subdirectories.
    """
    result: dict[str, Path] = {}
    if not store_dir.exists():
        return result

    if is_dir_category:
        for d in sorted(store_dir.iterdir()):
            if d.is_dir():
                result[d.name] = d
    else:
        for f in sorted(store_dir.iterdir()):
            if f.is_file():
                result[f.name] = f
    return result


def _list_project_files(project_dir: Path, is_dir_category: bool = False) -> dict[str, Path]:
    """List files in a project .github/ directory."""
    result: dict[str, Path] = {}
    if not project_dir.exists():
        return result

    if is_dir_category:
        for d in sorted(project_dir.iterdir()):
            if d.is_dir():
                result[d.name] = d
    else:
        for f in sorted(project_dir.iterdir()):
            if f.is_file():
                result[f.name] = f
    return result


def _compare_file_dicts(
    store_files: dict[str, Path],
    project_files: dict[str, Path],
    is_dir_category: bool = False,
) -> list[FileDiff]:
    """Compare two file dicts and produce diffs."""
    diffs: list[FileDiff] = []
    all_names = set(store_files) | set(project_files)

    for name in sorted(all_names):
        store_path = store_files.get(name)
        project_path = project_files.get(name)

        if store_path and project_path:
            if is_dir_category:
                store_hash = _file_hash(store_path / "SKILL.md")
                project_hash = _file_hash(project_path / "SKILL.md")
            else:
                store_hash = _file_hash(store_path)
                project_hash = _file_hash(project_path)

            if store_hash == project_hash and store_hash is not None:
                status = "up-to-date"
            else:
                status = "modified"
        elif store_path and not project_path:
            status = "added"
        else:
            status = "orphaned"

        diffs.append(FileDiff(name=name, status=status, rel_path=name))

    return diffs


def compare_agents(project_dir: Path | None = None) -> CategoryDiff:
    """Compare ~/.ai-adapter/agents/ with .github/agents/."""
    store_dir = _config.get_agents_dir()
    github_dir = _config.get_github_agents_dir(project_dir)
    store_files = _list_store_files(store_dir)
    project_files = _list_project_files(github_dir)
    diffs = _compare_file_dicts(store_files, project_files)
    return CategoryDiff("agents", store_dir, github_dir, diffs)


def compare_bins(project_dir: Path | None = None) -> CategoryDiff:
    """Compare ~/.ai-adapter/bin/ with .github/bin/."""
    store_dir = _config.get_bins_dir()
    github_dir = _config.get_github_bins_dir(project_dir)
    store_files = _list_store_files(store_dir)
    project_files = _list_project_files(github_dir)
    diffs = _compare_file_dicts(store_files, project_files)
    return CategoryDiff("bins", store_dir, github_dir, diffs)


def compare_skills(project_dir: Path | None = None) -> CategoryDiff:
    """Compare ~/.ai-adapter/skills/ with .github/skills/."""
    store_dir = _config.get_skills_dir()
    github_dir = _config.get_github_skills_dir(project_dir)
    store_dirs = _list_store_files(store_dir, is_dir_category=True)
    project_dirs = _list_project_files(github_dir, is_dir_category=True)
    diffs = _compare_file_dicts(store_dirs, project_dirs, is_dir_category=True)
    return CategoryDiff("skills", store_dir, github_dir, diffs)


def compare_commands(project_dir: Path | None = None) -> CategoryDiff:
    """Compare ~/.ai-adapter/commands/ with .github/commands/."""
    store_dir = _config.get_commands_dir()
    github_dir = _config.get_github_commands_dir(project_dir)
    store_files = _list_store_files(store_dir)
    project_files = _list_project_files(github_dir)
    diffs = _compare_file_dicts(store_files, project_files)
    return CategoryDiff("commands", store_dir, github_dir, diffs)


def compare_prompts(project_dir: Path | None = None) -> CategoryDiff:
    """Compare ~/.ai-adapter/prompts/ with .github/prompts/."""
    store_dir = _config.get_prompts_dir()
    github_dir = _config.get_github_prompts_dir(project_dir)
    store_files = _list_store_files(store_dir)
    project_files = _list_project_files(github_dir)
    diffs = _compare_file_dicts(store_files, project_files)
    return CategoryDiff("prompts", store_dir, github_dir, diffs)


def compare_mcp(project_dir: Path | None = None) -> CategoryDiff:
    """Compare MCP servers in config.json with .mcp.json in the project root."""
    config = _config.load_config()
    config_servers: set[str] = set()
    if config:
        config_servers = {s.name for s in config.mcp_servers if s.enabled}

    base = Path(project_dir).resolve() if project_dir else Path.cwd()
    mcp_json_path = base / ".mcp.json"
    mcp_json_servers: set[str] = set()
    if mcp_json_path.exists():
        try:
            data = json.loads(mcp_json_path.read_text())
            mcp_json_servers = set(data.get("mcpServers", {}).keys())
        except (json.JSONDecodeError, OSError):
            pass

    all_servers = sorted(config_servers | mcp_json_servers)
    diffs: list[FileDiff] = []
    for name in all_servers:
        in_config = name in config_servers
        in_file = name in mcp_json_servers
        if in_config and in_file:
            status = "up-to-date"
        elif in_config and not in_file:
            status = "added"
        else:
            status = "orphaned"
        diffs.append(FileDiff(name=name, status=status, rel_path=name))

    return CategoryDiff(
        "mcp",
        _config.AI_ADAPTER_DIR / "config.json",
        mcp_json_path,
        diffs,
    )


def compare_all(project_dir: Path | None = None) -> list[CategoryDiff]:
    """Run comparison for all categories."""
    return [
        compare_agents(project_dir),
        compare_bins(project_dir),
        compare_skills(project_dir),
        compare_commands(project_dir),
        compare_prompts(project_dir),
        compare_mcp(project_dir),
    ]
