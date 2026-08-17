"""scan command implementation.

Discovers AI agent tool configurations across the environment and the
current project, reports a merged summary, runs read-only diagnostics,
and (when the store is uninitialized) offers to import the findings.
"""

from __future__ import annotations

import json
from pathlib import Path

import click

from ai_adapter import config as _config
from ai_adapter.agent_plugins import ValidationIssue
from ai_adapter.scan import (
    TOOL_LABELS,
    TOOL_ORDER,
    ScanResult,
    import_detected_items,
    scan_all,
    scan_result_to_dict,
)

_SEVERITY_ICONS = {"error": "✗", "warning": "⚠", "info": "ℹ"}


@click.command(name="scan")
@click.option("--json", "as_json", is_flag=True, help="Output results as JSON (for CI)")
@click.option(
    "--project-dir",
    "-d",
    type=click.Path(exists=True, file_okay=False, readable=True),
    default=None,
    help="Project directory to scan (default: current directory)",
)
@click.option(
    "--yes",
    is_flag=True,
    help="Accept the import prompt without asking (interactive only)",
)
def cmd_scan(as_json: bool, project_dir: str | None, yes: bool) -> None:
    """Scan the environment for AI agent tool configurations."""
    project = Path(project_dir).resolve() if project_dir else Path.cwd()
    result = scan_all(project_dir=project)

    if as_json:
        click.echo(json.dumps(scan_result_to_dict(result), indent=2, ensure_ascii=False))
        return

    _render_result(result)
    _offer_import(result, project, yes)


def _render_result(result: ScanResult) -> None:
    """Print the merged scan report (1-1d) followed by diagnostics (1-2)."""
    click.echo("AI Environment")
    click.echo("=============")
    click.echo()
    _render_agents(result)
    click.echo()
    _render_list(result, "skill", "Skills", "detected")
    click.echo()
    _render_list(result, "mcp", "MCP", "configured")
    click.echo()
    _render_list(result, "instruction", "Instructions", "detected")
    click.echo()
    _render_problems(result.problems)


def _render_agents(result: ScanResult) -> None:
    """Print the per-tool status with agent counts when installed.

    A tool counts as installed when *any* item was detected (agents,
    skills, settings, MCP, instructions) — not just agents — so a
    settings-only install (e.g. ``~/.codex/config.toml``) is never
    reported as "not installed".
    """
    click.echo("Agents")
    for tool in TOOL_ORDER:
        count = result.count(tool=tool, category="agent")
        if not result.count(tool=tool):
            click.echo(f"  - {TOOL_LABELS[tool]}: not detected")
        elif count:
            click.echo(f"  ✓ {TOOL_LABELS[tool]}: {count} detected")
        else:
            click.echo(f"  ✓ {TOOL_LABELS[tool]}: installed (no agents/skills)")


def _render_list(result: ScanResult, category: str, heading: str, noun: str) -> None:
    """Print a category section with a count line and an indented item list."""
    items = result.by_category(category)
    click.echo(heading)
    click.echo(f"  {len(items)} {noun}")
    for index, item in enumerate(items):
        branch = "└─" if index == len(items) - 1 else "├─"
        click.echo(f"  {branch} {item.name}")


def _render_problems(problems: list[ValidationIssue]) -> None:
    """Print the Potential problems section (1-2)."""
    click.echo("Potential problems")
    if not problems:
        click.echo("  No potential problems detected.")
        return
    for problem in problems:
        icon = _SEVERITY_ICONS.get(problem.severity, "?")
        click.echo(f"  {icon} {problem}")


def _offer_import(result: ScanResult, project_dir: Path, yes: bool) -> None:
    """Offer to import detected settings into the store (interactive only).

    The prompt is only shown when the store is uninitialized, items were
    detected, and output is not JSON.  The target list is shown before the
    confirmation (AC3).
    """
    if _config.get_config_path().exists():
        return
    if not result.items:
        return

    click.echo()
    click.echo(f"Detected {len(result.items)} settings:")
    for item in result.items:
        label = TOOL_LABELS.get(item.tool, item.tool)
        click.echo(f"  - [{item.category}] {item.name} ({label})")

    try:
        confirmed = yes or click.confirm(f"Import them into {_config.AI_ADAPTER_DIR}?", default=False)
    except click.exceptions.Abort:
        # Non-interactive runs (e.g. pipelines with closed stdin) must not
        # turn a read-only diagnostic into an exit-code-1 failure.
        click.echo("Import skipped.")
        return
    if not confirmed:
        click.echo("Import skipped.")
        return

    imported = import_detected_items(result)
    click.echo(f"Imported {imported} settings into {_config.AI_ADAPTER_DIR}.")
    click.echo("Run 'ai-adapter status' to see the result.")
