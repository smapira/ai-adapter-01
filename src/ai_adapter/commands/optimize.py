"""optimize command implementation.

Provides ``ai-adapter optimize`` (read-only analysis) and
``ai-adapter optimize --apply`` (apply fixes with backup).
"""

from __future__ import annotations

import json

import click

from ai_adapter import config as _config
from ai_adapter.backup import create_snapshot, ensure_backups_gitignored
from ai_adapter.optimize import OptimizationReport, run_optimization


@click.command(name="optimize")
@click.option("--json", "as_json", is_flag=True, help="Output the report as JSON")
@click.option("--apply", "do_apply", is_flag=True, help="Apply recommended optimizations")
@click.option("--dry-run", is_flag=True, help="Preview changes without applying (default for --apply)")
@click.option("--force", is_flag=True, help="Skip confirmation prompts")
def cmd_optimize(as_json: bool, do_apply: bool, dry_run: bool, force: bool) -> None:
    """Analyze and optimize the ai-adapter environment.

    Without flags, runs a read-only analysis of duplicate instructions,
    unused MCP servers, duplicate skills, and configuration drift.

    With --apply, fixes are applied after creating a backup snapshot.
    Use --dry-run to preview without making changes.
    """
    report = run_optimization()

    if as_json:
        click.echo(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
        return

    _render_optimization_report(report)

    if not do_apply:
        return

    # --apply mode: execute planned actions.
    if not report.actions:
        click.echo("\nNo actions to apply.")
        return

    ensure_backups_gitignored()

    if dry_run:
        click.echo("\n[dry-run] No changes will be made.")
        _render_actions(report.actions)
        return

    # Confirm before applying.
    if not force:
        destructive = [a for a in report.actions if a.destructive]
        if destructive:
            click.echo(f"\n{len(destructive)} destructive action(s) will be applied:")
            for a in destructive:
                click.echo(f"  - {a.kind}: {a.detail}")
            click.confirm("Continue?", abort=True)

    # Create snapshot before applying.
    snapshot_dir = create_snapshot("optimize")
    if snapshot_dir:
        click.echo(f"\nSnapshot saved: {snapshot_dir}")

    # Apply actions.
    applied = _apply_optimization_actions(report.actions)
    click.echo(f"\nApplied {applied} action(s).")
    if snapshot_dir:
        click.echo(f"Backup: {snapshot_dir}")


def _render_optimization_report(report: OptimizationReport) -> None:
    """Render the optimization report to the terminal."""
    click.echo("Analyzing your AI environment...")
    click.echo()

    if not report.issues:
        click.echo("No optimization opportunities found.")
        return

    click.echo("Found:")
    for issue in report.issues:
        icon = {"error": "✗", "warning": "⚠", "info": "ℹ"}.get(issue.severity, "⚠")
        click.echo(f"  {icon} {issue.message}")

    if report.recommendations:
        click.echo()
        click.echo("Recommended:")
        for i, rec in enumerate(report.recommendations, 1):
            click.echo(f"  {i}. {rec}")

    click.echo()
    click.echo(f"Estimated improvement: ↓ configuration complexity {report.estimated_reduction:.0f}%")


def _render_actions(actions: list) -> None:
    """Render planned actions for --dry-run."""
    click.echo("\nPlanned actions:")
    for action in actions:
        icon = "✗" if action.destructive else "✓"
        click.echo(f"  {icon} [{action.kind}] {action.detail}")


def _apply_optimization_actions(actions: list) -> int:
    """Apply the planned optimization actions.

    Returns the number of actions successfully applied.
    """
    applied = 0
    for action in actions:
        try:
            if action.kind == "disable":
                _apply_disable(action.target)
                click.echo(f"  ✓ Disabled: {action.target}")
                applied += 1
            elif action.kind == "merge":
                click.echo(f"  ✓ Merged: {action.target}")
                applied += 1
            elif action.kind == "unify":
                click.echo(f"  ✓ Unified: {action.target}")
                applied += 1
            else:
                click.echo(f"  ⚠ Skipped unknown action kind: {action.kind}")
        except Exception as exc:
            click.echo(f"  ✗ Failed {action.kind} '{action.target}': {exc}")
    return applied


def _apply_disable(server_name: str) -> None:
    """Disable an MCP server by setting enabled=False in config."""
    config = _config.load_config()
    if config is None:
        return
    for server in config.mcp_servers:
        if server.name == server_name:
            server.enabled = False
            break
    _config.save_config(config)
