"""plugin subcommand implementation.

Provides Agent Plugins 1.0.0 (https://agent-plugins.org) validation and
package generation:

- ``ai-adapter plugin validate PATH`` — validate an Agent Plugins package
- ``ai-adapter plugin build PATH`` — scaffold a new 1.0.0 package layout
"""

from __future__ import annotations

import json
from pathlib import Path

import click

from ai_adapter.agent_plugins import (
    PLUGIN_SCHEMA,
    ValidationResult,
    validate_plugin_package,
)


@click.group(name="plugin")
def plugin_group() -> None:
    """Validate and build Agent Plugins 1.0.0 packages."""


@plugin_group.command(name="validate")
@click.argument("path", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--json", "as_json", is_flag=True, help="Output result as JSON")
@click.option("--strict", is_flag=True, help="Fail on warnings as well as errors")
def plugin_validate(path: Path, as_json: bool, strict: bool) -> None:
    """Validate an Agent Plugins 1.0.0 package.

    PATH: path to a plugin package directory containing plugin.json.
    """
    result = validate_plugin_package(path)

    if as_json:
        payload = _emit_json(result, strict)
        if not payload["valid"]:
            raise click.ClickException("Plugin validation failed.")
        return

    click.echo(f"Validating Agent Plugins package: {path}")
    click.echo("-" * 70)
    if not result.issues:
        click.echo("No validation issues found.")
        _emit_summary(result.valid, strict)
        return

    for issue in result.issues:
        line = str(issue)
        if issue.severity == "warning":
            click.echo(click.style(line, fg="yellow"))
        else:
            click.echo(click.style(line, fg="red"))

    click.echo("-" * 70)
    _emit_summary(result.valid, strict)
    if strict and result.issues:
        raise click.ClickException("Plugin validation failed (strict mode).")
    if not result.valid:
        raise click.ClickException("Plugin validation failed.")


@plugin_group.command(name="build")
@click.argument("name")
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    default=".",
    help="Output directory (default: current directory)",
)
@click.option("--description", help="Plugin description for plugin.json")
@click.option("--version", default="0.1.0", help="Initial version (default: 0.1.0)")
def plugin_build(name: str, output: Path, description: str | None, version: str) -> None:
    """Scaffold a new Agent Plugins 1.0.0 package.

    NAME: plugin name (1-64 chars, lowercase alphanumeric, hyphens, periods).
    """
    from ai_adapter.agent_plugins import validate_plugin_name

    name_err = validate_plugin_name(name)
    if name_err:
        raise click.ClickException(f"Invalid plugin name: {name_err}")

    target = output / name
    if target.exists():
        raise click.ClickException(f"Output directory already exists: {target}")

    skills_dir = target / "skills"
    skills_dir.mkdir(parents=True)

    manifest: dict = {
        "$schema": PLUGIN_SCHEMA,
        "name": name,
        "version": version,
    }
    if description:
        manifest["description"] = description

    (target / "plugin.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (target / "mcp.json").write_text(
        json.dumps(
            {
                "$schema": "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json",
                "mcpServers": {},
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    click.echo(f"Created Agent Plugins package: {target}")
    click.echo("  plugin.json  - manifest")
    click.echo("  mcp.json     - MCP server configuration (empty)")
    click.echo("  skills/      - place skills here (e.g. skills/<name>/SKILL.md)")
    click.echo()
    click.echo("Next steps:")
    click.echo(f"  ai-adapter plugin validate {target}")


def _emit_json(result: ValidationResult, strict: bool) -> dict:
    """Emit validation result as JSON and return the payload for exit-status handling."""
    payload = {
        "valid": result.valid and not (strict and any(i.severity == "warning" for i in result.issues)),
        "issues": [
            {
                "component": i.component,
                "message": i.message,
                "severity": i.severity,
                "path": i.path,
            }
            for i in result.issues
        ],
    }
    click.echo(json.dumps(payload, indent=2, ensure_ascii=False))
    return payload


def _emit_summary(valid: bool, strict: bool) -> None:
    """Print a human-readable pass/fail summary line."""
    if valid:
        click.echo(click.style("✓ Plugin package is valid.", fg="green"))
    else:
        click.echo(click.style("✗ Plugin package is NOT valid.", fg="red", bold=True))
    if strict:
        click.echo("strict mode: warnings are treated as errors")
