"""doctor diagnostic logic — read-only diagnostics and fix planning.

Reports the health of the local ai-adapter store and its tool integrations:

- Health summary (registered skills / MCP servers / agents / instructions)
- Updates available (store skill version vs. project ``.github/skills``)
- Compatibility issues (invalid JSON configs, invalid opencode.json)
- MCP server executability checks (``shutil.which``)
- Fix planning (``HealthReport``) for ``doctor --fix``

Phase 3 adds :class:`HealthReport`, :class:`FixAction`, and the fix-planning
logic while preserving the existing read-only diagnostic interface.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from ai_adapter import config as _config
from ai_adapter.agent_plugins import ValidationIssue
from ai_adapter.models import FixAction  # re-export for backward compat


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

    # Claude Code user-scope MCP (design 02): ~/.claude.json is Claude Code's
    # own user data, so doctor only validates the mcpServers subtree shape —
    # never writes, never prints values.
    issues.extend(_claude_user_mcp_issues(home))

    # Codex config.toml [mcp_servers] (design 03): validated read-only for
    # both user and project scope; auth.json is never opened.
    issues.extend(_codex_config_toml_issues(home, project_dir))

    # VS Code editor config (design 08): validate .vscode/mcp.json and
    # .vscode/extensions.json structure when present.
    issues.extend(_vscode_config_issues(project_dir))

    # Gemini CLI config (design 05): settings.json, command TOMLs, and
    # extension manifests — validated read-only, reusing the provider's
    # validate_* helpers so doctor and `gemini validate` never drift apart.
    issues.extend(_gemini_config_issues(project_dir, home))

    # Zed editor config (design 06): settings.json (project + OS-specific
    # user dir) — validated read-only, reusing the provider's
    # validate_settings so doctor and `zed validate` never drift apart.
    issues.extend(_zed_config_issues(project_dir, home))

    return issues


def _zed_config_issues(project_dir: Path, home: Path) -> list[ValidationIssue]:
    """Validate Zed settings.json files (design 06): project + user scope.

    Missing files are valid — Zed works without them.  Malformed JSON or
    wrong shapes are reported as warnings.  The user-scope directory is
    OS-dependent and resolved through ``config.get_zed_user_dir`` so the
    platform mapping stays single-sourced.
    """
    from ai_adapter.config import get_zed_user_dir
    from ai_adapter.providers.zed import validate_settings

    issues: list[ValidationIssue] = []
    targets = [
        ("zed project settings (.zed/settings.json)", project_dir / ".zed" / "settings.json"),
        ("zed user settings", get_zed_user_dir(home) / "settings.json"),
    ]
    for label, path in targets:
        if not path.is_file():
            continue
        for message in validate_settings(path):
            issues.append(ValidationIssue("doctor", f"{label}: {message}", severity="warning", path=str(path)))
    return issues


def _gemini_config_issues(project_dir: Path, home: Path) -> list[ValidationIssue]:
    """Validate Gemini CLI configs (design 05): settings, commands, manifests.

    Missing files are valid — Gemini CLI works without them.  Malformed
    JSON/TOML or wrong schema shapes are reported as warnings.
    """
    from ai_adapter.providers.gemini import (
        validate_command_toml,
        validate_extension_manifest,
        validate_settings,
    )

    issues: list[ValidationIssue] = []

    def _report_file(path: Path, label: str, validator) -> None:
        if not path.is_file():
            return
        for message in validator(path):
            issues.append(ValidationIssue("doctor", f"{label}: {message}", severity="warning", path=str(path)))

    def _report_tree(root: Path, pattern: str, label: str, validator) -> None:
        if not root.is_dir():
            return
        for path in sorted(root.rglob(pattern)):
            for message in validator(path):
                issues.append(ValidationIssue("doctor", f"{label}: {message}", severity="warning", path=str(path)))

    home_gemini = home / ".gemini"
    project_gemini = project_dir / ".gemini"
    _report_file(home_gemini / "settings.json", "gemini settings (~/.gemini/settings.json)", validate_settings)
    # When home == project_dir the user pass above already covered the
    # project's ".gemini/" — skip it so the same file is not reported twice.
    if project_gemini.resolve() != home_gemini.resolve():
        _report_file(project_gemini / "settings.json", "gemini settings (.gemini/settings.json)", validate_settings)
        _report_tree(project_gemini / "commands", "*.toml", "gemini command", validate_command_toml)
    _report_tree(home_gemini / "extensions", "gemini-extension.json", "gemini extension", validate_extension_manifest)
    return issues


def _vscode_config_issues(project_dir: Path) -> list[ValidationIssue]:
    """Validate ``.vscode/mcp.json`` and ``.vscode/extensions.json`` (read-only).

    Missing files are valid — VS Code works without them. Malformed JSON
    or wrong schema shapes are reported as warnings.
    """
    from ai_adapter.providers.vscode import validate_extensions, validate_vscode_mcp

    issues: list[ValidationIssue] = []
    targets = [
        ("vscode mcp (.vscode/mcp.json)", project_dir / ".vscode" / "mcp.json", validate_vscode_mcp),
        (
            "vscode extensions (.vscode/extensions.json)",
            project_dir / ".vscode" / "extensions.json",
            validate_extensions,
        ),
    ]
    for label, path, validator in targets:
        if not path.is_file():
            continue
        for message in validator(path):
            issues.append(ValidationIssue("doctor", f"{label}: {message}", severity="warning", path=str(path)))
    return issues


def _codex_config_toml_issues(home: Path, project_dir: Path) -> list[ValidationIssue]:
    """Validate ``[mcp_servers]`` in Codex config.toml files (read-only).

    Covers ``~/.codex/config.toml`` (user) and ``<project>/.codex/config.toml``
    (project).  Missing files are valid — Codex works without config.toml.
    When home and project_dir resolve to the same directory, the project
    pass is skipped so the same file is not validated twice (review N1).
    """
    from ai_adapter.providers.codex import validate_config_toml_mcp

    issues: list[ValidationIssue] = []
    targets = [
        ("codex user config (~/.codex/config.toml)", home / ".codex" / "config.toml"),
    ]
    project_config = project_dir / ".codex" / "config.toml"
    if project_config.resolve() != (home / ".codex" / "config.toml").resolve():
        targets.append(("codex project config (.codex/config.toml)", project_config))
    for label, path in targets:
        for message in validate_config_toml_mcp(path):
            issues.append(ValidationIssue("doctor", f"{label}: {message}", severity="warning", path=str(path)))
    return issues


def _claude_user_mcp_issues(home: Path) -> list[ValidationIssue]:
    """Validate the ``mcpServers`` subtree of ``~/.claude.json`` (read-only).

    Checks: valid JSON, ``mcpServers`` is an object, and every server entry
    is an object containing ``command``.  Missing file or missing key means
    "nothing to validate" — Claude Code works without user-scope MCP.
    """
    path = home / ".claude.json"
    if not path.is_file():
        return []

    label = "claude user config (~/.claude.json)"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [ValidationIssue("doctor", f"{label} is not valid JSON: {exc}", severity="warning", path=str(path))]

    if not isinstance(data, dict):
        return [ValidationIssue("doctor", f"{label} must be a JSON object", severity="warning", path=str(path))]

    servers = data.get("mcpServers")
    if servers is None:
        return []
    if not isinstance(servers, dict):
        return [ValidationIssue("doctor", f"{label}: mcpServers must be an object", severity="warning", path=str(path))]

    issues: list[ValidationIssue] = []
    for name, entry in servers.items():
        if not isinstance(entry, dict) or "command" not in entry:
            issues.append(
                ValidationIssue(
                    "doctor",
                    f"{label}: mcpServers.{name} must be an object with a 'command' key",
                    severity="warning",
                    path=str(path),
                )
            )
    return issues


# ── Phase 3: HealthReport ────────────────────────────────────────────────


@dataclass
class HealthReport:
    """Comprehensive health report including issues, updates, and fix plans."""

    issues: list[ValidationIssue]
    updates: list[UpdateInfo]
    fixes: list[FixAction]
    skills_total: int = 0
    mcp_total: int = 0
    agents_total: int = 0
    instructions_total: int = 0
    initialized: bool = True

    def to_dict(self) -> dict:
        return {
            "initialized": self.initialized,
            "skills": {
                "total": self.skills_total,
                "updates_available": len(self.updates),
                "updates": [u.to_dict() for u in self.updates],
            },
            "mcp_servers": self.mcp_total,
            "agents": self.agents_total,
            "instructions": self.instructions_total,
            "issues": [
                {"component": i.component, "message": i.message, "severity": i.severity, "path": i.path}
                for i in self.issues
            ],
            "fixes": [f.to_dict() for f in self.fixes],
        }


def run_health_report(
    config: _config.Config | None = None,
    project_dir: Path | None = None,
    home: Path | None = None,
) -> HealthReport:
    """Build a :class:`HealthReport` with issues, updates, and planned fixes.

    Reuses the phase-1 diagnostic logic and adds:
    - Version update detection (``check_versions``)
    - MCP server executability checks (``shutil.which``)
    - Fix planning for detected issues
    """
    if config is None:
        config = _config.load_config()

    if config is None:
        return HealthReport(
            issues=[
                ValidationIssue(
                    "doctor",
                    "ai-adapter is not initialized; run 'ai-adapter init' first",
                    severity="warning",
                )
            ],
            updates=[],
            fixes=[],
            initialized=False,
        )

    project = (project_dir or Path.cwd()).resolve()
    resolved_home = home or Path.home()

    # Collect issues from existing diagnostics.
    issues: list[ValidationIssue] = []
    issues.extend(_compatibility_issues(project, resolved_home))
    issues.extend(_mcp_executability_issues(config))

    # Collect version updates.
    updates = _find_skill_updates(config, project)

    # Plan fix actions.
    fixes = _plan_fixes(config, issues, updates)

    return HealthReport(
        issues=issues,
        updates=updates,
        fixes=fixes,
        skills_total=len(config.skills),
        mcp_total=len(config.mcp_servers),
        agents_total=len(config.agents),
        instructions_total=len(config.instructions),
        initialized=True,
    )


def _mcp_executability_issues(config: _config.Config) -> list[ValidationIssue]:
    """Check whether MCP server commands are reachable via ``shutil.which``."""
    issues: list[ValidationIssue] = []
    for server in config.mcp_servers:
        if not server.enabled:
            continue
        if not server.command:
            continue
        # Resolve to the first token (handle edge case of command with spaces).
        cmd_token = server.command.split()[0] if server.command else ""
        if cmd_token and shutil.which(cmd_token) is None:
            issues.append(
                ValidationIssue(
                    "mcp",
                    f"MCP server '{server.name}' command '{cmd_token}' not found in PATH",
                    severity="warning",
                    path=server.command,
                )
            )
    return issues


def _plan_fixes(
    config: _config.Config,
    issues: list[ValidationIssue],
    updates: list[UpdateInfo],
) -> list[FixAction]:
    """Derive :class:`FixAction` items from detected issues and updates."""
    fixes: list[FixAction] = []

    # Fix: update skills with available updates.
    for update in updates:
        fixes.append(
            FixAction(
                kind="update",
                target=update.name,
                detail=f"Update skill '{update.name}' from {update.store_version} to {update.upstream_version}",
                destructive=False,
            )
        )

    # Fix: disable MCP servers whose command is not found.
    for issue in issues:
        if issue.component == "mcp" and "command" in issue.message and "not found in PATH" in issue.message:
            # Extract server name from the message: "MCP server '<name>' command ..."
            start = issue.message.find("'") + 1
            end = issue.message.find("'", start)
            server_name = issue.message[start:end] if end > start else "unknown"
            fixes.append(
                FixAction(
                    kind="disable",
                    target=server_name,
                    detail=f"Disable MCP server '{server_name}' (command not in PATH)",
                    destructive=False,
                )
            )

    return sorted(fixes, key=lambda f: (f.kind, f.target))
