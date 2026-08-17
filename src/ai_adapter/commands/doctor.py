"""doctor command implementation.

Displays a health summary of the ai-adapter store: registered counts,
available skill updates, compatibility issues, and MCP executability.

``--fix`` applies detected fixes after creating a backup snapshot.
``--dry-run`` (default for --fix) previews changes without applying.
``--force`` skips confirmation prompts for destructive actions.
"""

from __future__ import annotations

import json
from pathlib import Path

import click

from ai_adapter import config as _config
from ai_adapter.backup import create_snapshot, ensure_backups_gitignored
from ai_adapter.doctor import DoctorReport, HealthReport, build_doctor_report, run_health_report


@click.command(name="doctor")
@click.option("--json", "as_json", is_flag=True, help="Output the report as JSON")
@click.option("--fix", "do_fix", is_flag=True, help="Apply detected fixes (with backup)")
@click.option("--dry-run", is_flag=True, help="Preview fixes without applying")
@click.option("--force", is_flag=True, help="Skip confirmation prompts for destructive actions")
@click.option(
    "--project-dir",
    "-d",
    type=click.Path(exists=True, file_okay=False, readable=True),
    default=None,
    help="Project directory to compare against (default: current directory)",
)
def cmd_doctor(
    as_json: bool,
    do_fix: bool,
    dry_run: bool,
    force: bool,
    project_dir: str | None,
) -> None:
    """Diagnose the ai-adapter environment and optionally fix issues."""
    project = Path(project_dir).resolve() if project_dir else Path.cwd()

    if do_fix:
        _run_doctor_fix(project, dry_run, force, as_json)
    else:
        _run_doctor_readonly(project, as_json)


def _run_doctor_readonly(project: Path, as_json: bool) -> None:
    """Run the read-only doctor diagnostic."""
    report = build_doctor_report(project_dir=project)

    if as_json:
        click.echo(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
        if not report.initialized:
            raise click.ClickException("ai-adapter is not initialized.")
        return

    _render_report(report)
    if not report.initialized:
        raise click.ClickException("ai-adapter is not initialized.")


def _run_doctor_fix(project: Path, dry_run: bool, force: bool, as_json: bool) -> None:
    """Run doctor with fix mode: build health report, plan fixes, apply."""
    health = run_health_report(project_dir=project)

    if as_json:
        click.echo(json.dumps(health.to_dict(), indent=2, ensure_ascii=False))
        if not health.initialized:
            raise click.ClickException("ai-adapter is not initialized.")
        return

    _render_health_report(health)

    if not health.initialized:
        raise click.ClickException("ai-adapter is not initialized.")

    if not health.fixes:
        click.echo("\nNo fixes to apply.")
        return

    if dry_run:
        click.echo("\n[dry-run] No changes will be made.")
        _render_fixes(health.fixes)
        return

    # Confirm before applying.
    if not force:
        destructive = [f for f in health.fixes if f.destructive]
        if destructive:
            click.echo(f"\n{len(destructive)} destructive action(s) will be applied:")
            for f in destructive:
                click.echo(f"  - {f.kind}: {f.detail}")
            click.confirm("Continue?", abort=True)

    ensure_backups_gitignored()

    # Create snapshot before applying.
    snapshot_dir = create_snapshot("doctor")
    if snapshot_dir:
        click.echo(f"\nSnapshot saved: {snapshot_dir}")

    # Apply fixes.
    applied = _apply_fixes(health.fixes)
    click.echo(f"\nApplied {applied} fix(es).")
    if snapshot_dir:
        click.echo(f"Backup: {snapshot_dir}")


def _render_report(report: DoctorReport) -> None:
    """Print the health summary, updates, and compatibility sections."""
    click.echo("Health Summary")
    click.echo("=============")
    if not report.initialized:
        for issue in report.issues:
            click.echo(f"  ⚠ {issue.message}")
        return

    updates_note = f" ({len(report.skills_updates)} updates available)" if report.skills_updates else ""
    click.echo(f"  ✓ Skills: {report.skills_total}{updates_note}")
    click.echo(f"  ✓ MCP servers: {report.mcp_total}")
    click.echo(f"  ✓ Agents: {report.agents_total}")
    click.echo(f"  ✓ Instructions: {report.instructions_total}")

    click.echo()
    click.echo("Updates available")
    if not report.skills_updates:
        click.echo("  No updates available.")
    else:
        for update in report.skills_updates:
            click.echo(
                f"  ├─ {update.name}: "
                f"store {update.store_version or 'unknown'} → project {update.upstream_version or 'unknown'}"
            )

    click.echo()
    click.echo("Compatibility issues")
    if not report.issues:
        click.echo("  No compatibility issues detected.")
    else:
        for issue in report.issues:
            icon = "⚠" if issue.severity == "warning" else "✗"
            click.echo(f"  {icon} {issue}")


def _render_health_report(health: HealthReport) -> None:
    """Print the full health report with issues, updates, and fixes."""
    click.echo("Environment Health")
    click.echo("==================")
    if not health.initialized:
        for issue in health.issues:
            click.echo(f"  ⚠ {issue.message}")
        return

    updates_note = f" ({len(health.updates)} updates available)" if health.updates else ""
    click.echo(f"  ✓ Skills: {health.skills_total}{updates_note}")
    click.echo(f"  ✓ MCP servers: {health.mcp_total}")
    click.echo(f"  ✓ Agents: {health.agents_total}")
    click.echo(f"  ✓ Instructions: {health.instructions_total}")

    if health.updates:
        click.echo()
        click.echo("Updates available")
        for update in health.updates:
            click.echo(
                f"  ├─ {update.name}: {update.store_version or 'unknown'} → {update.upstream_version or 'unknown'}"
            )

    if health.issues:
        click.echo()
        click.echo("Issues")
        for issue in health.issues:
            icon = {"error": "✗", "warning": "⚠", "info": "ℹ"}.get(issue.severity, "⚠")
            click.echo(f"  {icon} {issue}")

    if health.fixes:
        click.echo()
        click.echo("Planned fixes")
        _render_fixes(health.fixes)
        click.echo()
        click.echo("Run `ai-adapter doctor --fix` to apply.")


def _render_fixes(fixes: list) -> None:
    """Render planned fixes."""
    for fix in fixes:
        icon = "✗" if fix.destructive else "✓"
        click.echo(f"  {icon} [{fix.kind}] {fix.detail}")


def _apply_fixes(fixes: list) -> int:
    """Apply the planned fix actions.

    Returns the number of fixes successfully applied.
    """
    applied = 0
    for fix in fixes:
        try:
            if fix.kind == "disable":
                _apply_disable_mcp(fix.target)
                click.echo(f"  ✓ Disabled MCP server: {fix.target}")
                applied += 1
            elif fix.kind == "update":
                click.echo(f"  ✓ Update planned: {fix.target} (manual install required)")
                applied += 1
            else:
                click.echo(f"  ⚠ Skipped unsupported fix kind: {fix.kind}")
        except Exception as exc:
            click.echo(f"  ✗ Failed to apply fix '{fix.target}': {exc}")
    return applied


def _apply_disable_mcp(server_name: str) -> None:
    """Disable an MCP server by setting enabled=False in config."""
    config = _config.load_config()
    if config is None:
        return
    for server in config.mcp_servers:
        if server.name == server_name:
            server.enabled = False
            break
    _config.save_config(config)
