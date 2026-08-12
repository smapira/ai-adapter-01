"""Optimization diagnostics for the ai-adapter environment.

Analyses the store for:
- Duplicate instructions (same name or similar content)
- Unused MCP servers (not referenced by any skill or agent)
- Duplicate skills (same name across multiple environments)
- Configuration drift (Claude / Codex / Cursor inconsistencies)

Phase 3 adds read-only analysis and ``--apply`` fix logic. The shared
:class:`~ai_adapter.agent_plugins.ValidationIssue` model is used for
consistent reporting.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from ai_adapter import config as _config
from ai_adapter.agent_plugins import ValidationIssue
from ai_adapter.models import FixAction, Skill  # noqa: F811 — re-export for backward compat


@dataclass
class OptimizationReport:
    """Result of the optimization analysis."""

    issues: list[ValidationIssue]
    recommendations: list[str]
    estimated_reduction: float  # 0.0 – 100.0, percentage
    actions: list[FixAction]

    def to_dict(self) -> dict:
        return {
            "issues": [
                {"component": i.component, "message": i.message, "severity": i.severity, "path": i.path}
                for i in self.issues
            ],
            "recommendations": self.recommendations,
            "estimated_reduction": self.estimated_reduction,
            "actions": [a.to_dict() for a in self.actions],
        }


# ── Analysis helpers ────────────────────────────────────────────────────


def _file_content_hash(path: Path) -> str | None:
    """Return a SHA-256 digest of *path*'s text content, or None on error."""
    try:
        return hashlib.sha256(path.read_text(encoding="utf-8").encode()).hexdigest()
    except (OSError, ValueError):
        return None


def _detect_duplicate_instructions(config: _config.Config, home: Path) -> tuple[list[ValidationIssue], list[FixAction]]:
    """Find instruction files with identical content across locations.

    Returns (issues, planned_actions).
    """
    issues: list[ValidationIssue] = []
    actions: list[FixAction] = []

    instructions_dir = home / ".ai-adapter" / "instructions"
    if not instructions_dir.is_dir():
        return issues, actions

    # Group files by content hash.
    hash_to_names: dict[str, list[str]] = {}
    for f in sorted(instructions_dir.iterdir()):
        if not f.is_file() or f.suffix != ".md":
            continue
        h = _file_content_hash(f)
        if h:
            hash_to_names.setdefault(h, []).append(f.name)

    for h, names in hash_to_names.items():
        if len(names) > 1:
            issues.append(
                ValidationIssue(
                    "optimize",
                    f"Duplicate instructions detected: {', '.join(names)}",
                    severity="warning",
                )
            )
            actions.append(
                FixAction(
                    kind="merge",
                    target=", ".join(names),
                    detail=f"Merge {len(names)} identical instruction files into one",
                    destructive=False,
                )
            )

    return issues, actions


def _detect_unused_mcp(config: _config.Config) -> tuple[list[ValidationIssue], list[FixAction]]:
    """Find MCP servers not referenced by any registered skill or agent.

    A server is considered "unused" if its name doesn't appear in any
    skill's tools list or agent's tool requirements.
    """
    issues: list[ValidationIssue] = []
    actions: list[FixAction] = []

    # Collect all referenced MCP names from skills and agents.
    referenced: set[str] = set()
    for skill in config.skills:
        # Skills reference MCP tools via their `tools` list (stored as tags).
        referenced.update(skill.tags)
    for agent in config.agents:
        # Agents reference MCP via their description (loose heuristic).
        if agent.description:
            for token in agent.description.split():
                token_clean = token.strip(",.")
                if token_clean:
                    referenced.add(token_clean)

    for server in config.mcp_servers:
        if not server.enabled:
            continue
        if server.name not in referenced and not server.tools:
            issues.append(
                ValidationIssue(
                    "optimize",
                    f"Unused MCP server '{server.name}' (no skill or agent references it)",
                    severity="info",
                )
            )
            actions.append(
                FixAction(
                    kind="disable",
                    target=server.name,
                    detail=f"Disable unused MCP server '{server.name}'",
                    destructive=False,
                )
            )

    return issues, actions


def _detect_duplicate_skills(config: _config.Config) -> tuple[list[ValidationIssue], list[FixAction]]:
    """Find skills registered multiple times (e.g. same name, different envs)."""
    issues: list[ValidationIssue] = []
    actions: list[FixAction] = []

    by_name: dict[str, list[Skill]] = {}
    for skill in config.skills:
        by_name.setdefault(skill.name, []).append(skill)

    for name, entries in by_name.items():
        if len(entries) > 1:
            envs = [e.env or "default" for e in entries]
            issues.append(
                ValidationIssue(
                    "optimize",
                    f"Duplicate skill '{name}' registered in environments: {', '.join(envs)}",
                    severity="warning",
                )
            )
            actions.append(
                FixAction(
                    kind="unify",
                    target=name,
                    detail=f"Consolidate {len(entries)} registrations of skill '{name}'",
                    destructive=False,
                )
            )

    return issues, actions


def _detect_config_drift(home: Path) -> tuple[list[ValidationIssue], list[FixAction]]:
    """Detect configuration drift between Claude, Codex, and Cursor."""
    issues: list[ValidationIssue] = []
    actions: list[FixAction] = []

    # Compare MCP server configs across tools.
    configs_to_compare: dict[str, Path] = {
        "claude": home / ".claude" / "settings.json",
        "cursor": home / ".cursor" / "mcp.json",
        "opencode": home / ".config" / "opencode" / "opencode.json",
    }

    tool_servers: dict[str, set[str]] = {}
    for tool, path in configs_to_compare.items():
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        servers: set[str] = set()
        for key in ("mcpServers", "mcp"):
            entries = data.get(key)
            if isinstance(entries, dict):
                servers.update(str(n) for n in entries.keys())
        tool_servers[tool] = servers

    # Find servers present in some but not all tools.
    all_names = set()
    for servers in tool_servers.values():
        all_names.update(servers)

    if len(tool_servers) > 1:
        for name in sorted(all_names):
            present_in = sorted(t for t, s in tool_servers.items() if name in s)
            absent_from = sorted(t for t, s in tool_servers.items() if name not in s)
            if present_in and absent_from:
                present_str = ", ".join(present_in)
                absent_str = ", ".join(absent_from)
                issues.append(
                    ValidationIssue(
                        "optimize",
                        f"MCP server '{name}' present in {present_str} but missing from {absent_str}",
                        severity="info",
                    )
                )
                actions.append(
                    FixAction(
                        kind="unify",
                        target=name,
                        detail=f"Unify MCP server '{name}' across tools (add to {absent_str})",
                        destructive=False,
                    )
                )

    return issues, actions


# ── Main analysis ───────────────────────────────────────────────────────


def run_optimization(
    config: _config.Config | None = None,
    home: Path | None = None,
) -> OptimizationReport:
    """Run the full optimization analysis and return a report.

    Read-only: no files are modified.
    """
    if config is None:
        config = _config.load_config()

    resolved_home = home or Path.home()
    issues: list[ValidationIssue] = []
    actions: list[FixAction] = []
    recommendations: list[str] = []

    if config is None:
        return OptimizationReport(
            issues=[
                ValidationIssue(
                    "optimize",
                    "ai-adapter is not initialized; run 'ai-adapter init' first",
                    severity="warning",
                )
            ],
            recommendations=[],
            estimated_reduction=0.0,
            actions=[],
        )

    # 1. Duplicate instructions.
    dup_issues, dup_actions = _detect_duplicate_instructions(config, resolved_home)
    issues.extend(dup_issues)
    actions.extend(dup_actions)
    if dup_issues:
        recommendations.append(f"Merge {len(dup_issues)} duplicate instruction file(s)")

    # 2. Unused MCP servers.
    unused_issues, unused_actions = _detect_unused_mcp(config)
    issues.extend(unused_issues)
    actions.extend(unused_actions)
    if unused_issues:
        recommendations.append(f"Disable {len(unused_issues)} unused MCP server(s)")

    # 3. Duplicate skills.
    dup_skill_issues, dup_skill_actions = _detect_duplicate_skills(config)
    issues.extend(dup_skill_issues)
    actions.extend(dup_skill_actions)
    if dup_skill_issues:
        recommendations.append(f"Consolidate {len(dup_skill_issues)} duplicate skill registration(s)")

    # 4. Config drift.
    drift_issues, drift_actions = _detect_config_drift(resolved_home)
    issues.extend(drift_issues)
    actions.extend(drift_actions)
    if drift_issues:
        recommendations.append(f"Unify {len(drift_issues)} MCP server(s) across tools")

    # Estimate complexity reduction.
    total_items = len(config.skills) + len(config.mcp_servers) + len(config.agents) + len(config.instructions)
    issues_count = len(issues)
    if total_items > 0 and issues_count > 0:
        # Rough heuristic: each issue represents ~5% complexity overhead.
        estimated_reduction = min(issues_count * 5.0, 50.0)
    else:
        estimated_reduction = 0.0

    return OptimizationReport(
        issues=issues,
        recommendations=recommendations,
        estimated_reduction=estimated_reduction,
        actions=actions,
    )
