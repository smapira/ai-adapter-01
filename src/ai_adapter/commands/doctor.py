"""doctor command implementation (read-only diagnostics).

Displays a health summary of the ai-adapter store: registered counts,
available skill updates, and compatibility issues.  ``--fix`` is
implemented in phase 3 — this command never modifies anything.
"""

from __future__ import annotations

import json
from pathlib import Path

import click

from ai_adapter.doctor import DoctorReport, build_doctor_report


@click.command(name="doctor")
@click.option("--json", "as_json", is_flag=True, help="Output the report as JSON")
@click.option(
    "--project-dir",
    "-d",
    type=click.Path(exists=True, file_okay=False, readable=True),
    default=None,
    help="Project directory to compare against (default: current directory)",
)
def cmd_doctor(as_json: bool, project_dir: str | None) -> None:
    """Diagnose the ai-adapter environment (read-only)."""
    project = Path(project_dir).resolve() if project_dir else Path.cwd()
    report = build_doctor_report(project_dir=project)

    if as_json:
        click.echo(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
        return

    _render_report(report)


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
