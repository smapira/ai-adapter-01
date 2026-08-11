"""Version tracking for skills, plugins, and MCP servers.

Reads installed versions from frontmatter and optionally queries GitHub
tags for the latest available version.  Designed to be used both by the
``ai-adapter version`` command and by the ``doctor`` diagnostic (phase 3).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from ai_adapter import config as _config
from ai_adapter.agent_format import parse_frontmatter
from ai_adapter.git import GitError, _run_git

logger = logging.getLogger(__name__)


@dataclass
class VersionInfo:
    """Version metadata for a single skill, plugin, or MCP server."""

    name: str
    category: str  # "skill" | "plugin" | "mcp"
    installed: str | None
    latest: str | None
    source: str | None  # e.g. "github:user/repo" or None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "category": self.category,
            "installed": self.installed,
            "latest": self.latest,
            "source": self.source,
        }

    @property
    def update_available(self) -> bool:
        """Return True when *latest* is newer than *installed*."""
        if self.installed is None or self.latest is None:
            return False
        if self.latest == "unknown":
            return False
        return self.installed != self.latest


def _skill_installed_version(skill_dir: Path) -> str | None:
    """Return the frontmatter ``version`` of a skill directory, or None."""
    skill_file = skill_dir / "SKILL.md"
    if not skill_file.is_file():
        return None
    try:
        fm = parse_frontmatter(skill_file)
    except Exception:
        return None
    version = fm.get("version") if isinstance(fm, dict) else None
    return str(version) if version is not None else None


def get_latest_github_tag(repo: str) -> str | None:
    """Fetch the latest ``v*`` tag from a GitHub repository via ``git ls-remote``.

    Args:
        repo: GitHub path in ``user/repo`` format.

    Returns:
        The latest tag string (e.g. ``v1.5``), or ``None`` on failure.
    """
    url = f"https://github.com/{repo}.git"
    try:
        result = _run_git(["ls-remote", "--tags", "--sort=-v:refname", url])
    except GitError:
        logger.debug("Failed to ls-remote %s (offline or invalid repo)", repo)
        return None

    for line in result.stdout.strip().splitlines():
        # Lines look like:  abc123  refs/tags/v1.5
        parts = line.split()
        if len(parts) < 2:
            continue
        ref = parts[1]
        if ref.startswith("refs/tags/v"):
            tag = ref[len("refs/tags/") :]
            # Skip annotated-tag derefs (v1.5^{})
            if "^{}" not in tag:
                return tag
    return None


def check_versions(skills_dir: Path | None = None) -> list[VersionInfo]:
    """Return version info for all registered skills.

    Compares the ``installed`` frontmatter version against the ``latest``
    GitHub tag when a ``source`` (``github:user/repo``) is discoverable.

    When the GitHub tag cannot be fetched (offline, missing repo, etc.),
    ``latest`` is set to ``"unknown"`` — an error is never raised.
    """
    config = _config.load_config()
    if config is None:
        return []

    store_dir = skills_dir or _config.get_skills_dir()
    results: list[VersionInfo] = []

    for skill in config.skills:
        skill_dir = store_dir / skill.name
        installed = _skill_installed_version(skill_dir)

        # Determine GitHub source from skill description or config.
        # Convention: description may contain "github:user/repo".
        source = _extract_github_source(skill.description)
        if source is not None:
            repo = source[len("github:") :]
            latest = get_latest_github_tag(repo)
            if latest is None:
                latest = "unknown"
        else:
            source = None
            latest = None

        results.append(
            VersionInfo(
                name=skill.name,
                category="skill",
                installed=installed,
                latest=latest,
                source=source,
            )
        )

    return sorted(results, key=lambda v: v.name)


def _extract_github_source(description: str) -> str | None:
    """Extract a ``github:user/repo`` source from a description string, or None."""
    if not description:
        return None
    for token in description.split():
        if token.startswith("github:") and "/" in token:
            return token
    return None


def render_version_table(versions: list[VersionInfo]) -> str:
    """Render a human-readable version table."""
    if not versions:
        return "No skills registered."

    header = f"{'Name':<30} {'Installed':<15} {'Latest':<15} {'Source':<30}"
    lines = [header, "-" * len(header)]
    for v in versions:
        installed = v.installed or "unknown"
        latest = v.latest or "n/a"
        source = v.source or ""
        lines.append(f"{v.name:<30} {installed:<15} {latest:<15} {source:<30}")

    updates = [v for v in versions if v.update_available]
    if updates:
        lines.append("")
        lines.append(f"{len(updates)} update(s) available.")
    else:
        lines.append("")
        lines.append("All skills are up to date (or latest is unknown).")

    return "\n".join(lines)
