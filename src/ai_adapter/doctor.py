"""doctor diagnostic logic (read-only).

Reports the health of the local ai-adapter store and its tool integrations:

- Health summary (registered skills / MCP servers / agents / instructions)
- Updates available (store skill version vs. project ``.github/skills``)
- Compatibility issues (invalid JSON configs, invalid opencode.json)

``--fix`` is intentionally out of scope (implemented in phase 3) — this
module only inspects and reports, using the shared
:class:`~ai_adapter.agent_plugins.ValidationIssue` model.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from ai_adapter import config as _config
from ai_adapter.agent_plugins import ValidationIssue


@dataclass
class UpdateInfo:
    """A skill whose store version differs from the project version."""

    name: str
    store_version: str | None
    upstream_version: str | None
    source: str

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "store_version": self.store_version,
            "upstream_version": self.upstream_version,
            "source": self.source,
        }


@dataclass
class DoctorReport:
    """Health snapshot of the ai-adapter environment."""

    skills_total: int
    skills_updates: list[UpdateInfo]
    mcp_total: int
    agents_total: int
    instructions_total: int
    issues: list[ValidationIssue] = field(default_factory=list)
    initialized: bool = True

    def to_dict(self) -> dict:
        return {
            "initialized": self.initialized,
            "skills": {
                "total": self.skills_total,
                "updates_available": len(self.skills_updates),
                "updates": [u.to_dict() for u in self.skills_updates],
            },
            "mcp_servers": self.mcp_total,
            "agents": self.agents_total,
            "instructions": self.instructions_total,
            "issues": [
                {"component": i.component, "message": i.message, "severity": i.severity, "path": i.path}
                for i in self.issues
            ],
        }


def build_doctor_report(project_dir: Path | None = None, home: Path | None = None) -> DoctorReport:
    """Build a :class:`DoctorReport` from the local store and project.

    Args:
        project_dir: Project to compare against (defaults to ``Path.cwd()``).
        home: Directory used as ``~`` (defaults to ``Path.home()``).
    """
    config = _config.load_config()
    if config is None:
        return DoctorReport(
            skills_total=0,
            skills_updates=[],
            mcp_total=0,
            agents_total=0,
            instructions_total=0,
            issues=[
                ValidationIssue(
                    "doctor",
                    "ai-adapter is not initialized; run 'ai-adapter init' first",
                    severity="warning",
                )
            ],
            initialized=False,
        )

    project = (project_dir or Path.cwd()).resolve()
    issues: list[ValidationIssue] = []
    issues.extend(_compatibility_issues(project, home or Path.home()))
    return DoctorReport(
        skills_total=len(config.skills),
        skills_updates=_find_skill_updates(config, project),
        mcp_total=len(config.mcp_servers),
        agents_total=len(config.agents),
        instructions_total=len(config.instructions),
        issues=issues,
        initialized=True,
    )


def _skill_version(skill_dir: Path) -> str | None:
    """Return the frontmatter ``version`` of ``skill_dir/SKILL.md``, or None."""
    from ai_adapter.agent_format import parse_frontmatter

    skill_file = skill_dir / "SKILL.md"
    if not skill_file.is_file():
        return None
    try:
        fm = parse_frontmatter(skill_file)
    except Exception:
        return None
    version = fm.get("version") if isinstance(fm, dict) else None
    return str(version) if version is not None else None


def _find_skill_updates(config: _config.Config, project_dir: Path) -> list[UpdateInfo]:
    """Compare store skill versions with project ``.github/skills/`` versions.

    A skill is reported as updatable when the project's version differs
    from the store's (the project is the upstream source).
    """
    store_dir = _config.get_skills_dir()
    project_skills = project_dir / ".github" / "skills"
    updates: list[UpdateInfo] = []
    for skill in config.skills:
        store_version = _skill_version(store_dir / skill.name)
        upstream_version = _skill_version(project_skills / skill.name)
        if store_version is None or upstream_version is None:
            continue
        if store_version != upstream_version:
            updates.append(
                UpdateInfo(
                    name=skill.name,
                    store_version=store_version,
                    upstream_version=upstream_version,
                    source=str(project_skills / skill.name),
                )
            )
    return sorted(updates, key=lambda u: u.name)


def _compatibility_issues(project_dir: Path, home: Path) -> list[ValidationIssue]:
    """Detect config-level compatibility problems (read-only)."""
    issues: list[ValidationIssue] = []

    # opencode.json schema validation — reuses the existing opencode logic
    # so doctor and `opencode validate` never drift apart.
    opencode_json = project_dir / "opencode.json"
    if opencode_json.is_file():
        from ai_adapter.providers.opencode import _validate_opencode_config

        for message in _validate_opencode_config(opencode_json):
            issues.append(ValidationIssue("opencode.json", message, severity="error", path=str(opencode_json)))

    # JSON parse checks for tool MCP configs.
    for label, path in (
        ("claude settings", home / ".claude" / "settings.json"),
        ("cursor mcp", home / ".cursor" / "mcp.json"),
        ("project .mcp.json", project_dir / ".mcp.json"),
    ):
        if not path.is_file():
            continue
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            issues.append(
                ValidationIssue("doctor", f"{label} is not valid JSON: {exc}", severity="warning", path=str(path))
            )

    return issues
