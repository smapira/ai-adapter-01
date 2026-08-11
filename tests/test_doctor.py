"""Tests for the doctor diagnostic module and ``ai-adapter doctor`` command.

Covers:
- Health summary counts (skills / MCP / agents / instructions)
- Update detection (store version vs. project ``.github/skills`` version)
- Compatibility issues (invalid opencode.json, invalid MCP JSON)
- Uninitialized-store warning
- CLI rendering and ``--json`` output

All tests use the :func:`isolated_home` fixture (real ``~`` is never read).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from ai_adapter import config as cfg
from ai_adapter.cli import main
from ai_adapter.doctor import UpdateInfo, build_doctor_report
from ai_adapter.models import Agent, Instruction, MCPServer, Skill

# ── Fixtures & helpers ──────────────────────────────────────────────────


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def _init_store() -> None:
    """Initialize the isolated ai-adapter store (no-op if already done)."""
    cfg.init()


def _write_versioned_skill(skill_dir: Path, name: str, version: str) -> None:
    """Write ``<skill_dir>/<name>/SKILL.md`` with a frontmatter version."""
    skill_file = skill_dir / name / "SKILL.md"
    skill_file.parent.mkdir(parents=True, exist_ok=True)
    skill_file.write_text(
        f"---\nname: {name}\nversion: {version}\ndescription: Skill {name}\n---\n# {name}\n",
        encoding="utf-8",
    )


def _register_skill(name: str, store_version: str, project_version: str) -> None:
    """Register a skill in the store + project with distinct versions."""
    _init_store()
    _write_versioned_skill(cfg.get_skills_dir(), name, store_version)
    _write_versioned_skill(Path.cwd() / ".github" / "skills", name, project_version)
    config = cfg.load_config()
    assert config is not None
    config.skills.append(Skill(name=name))
    cfg.save_config(config)


def _add_agent(name: str = "reviewer") -> None:
    _init_store()
    config = cfg.load_config()
    assert config is not None
    config.agents.append(Agent(name=name))
    cfg.save_config(config)


def _add_mcp(name: str = "github", command: str = "gh-mcp") -> None:
    _init_store()
    config = cfg.load_config()
    assert config is not None
    config.mcp_servers.append(MCPServer(name=name, command=command))
    cfg.save_config(config)


def _add_instruction(name: str = "AGENTS.md") -> None:
    _init_store()
    config = cfg.load_config()
    assert config is not None
    config.instructions.append(Instruction(name=name))
    cfg.save_config(config)


# ── Health summary ──────────────────────────────────────────────────────


def test_doctor_uninitialized_warns(isolated_home: Path):
    report = build_doctor_report(project_dir=Path.cwd())
    assert report.initialized is False
    assert report.skills_total == 0
    assert report.mcp_total == 0
    assert report.agents_total == 0
    assert report.instructions_total == 0
    assert len(report.issues) == 1
    assert report.issues[0].severity == "warning"
    assert "not initialized" in report.issues[0].message


def test_doctor_health_summary_counts(isolated_home: Path):
    _register_skill("frontend", "1.0.0", "1.0.0")
    _add_agent("reviewer")
    _add_mcp("github")
    _add_instruction("AGENTS.md")
    report = build_doctor_report(project_dir=Path.cwd())
    assert report.initialized is True
    assert report.skills_total == 1
    assert report.mcp_total == 1
    assert report.agents_total == 1
    assert report.instructions_total == 1
    assert report.skills_updates == []
    assert report.issues == []


def test_doctor_json_output_structure(isolated_home: Path):
    _register_skill("frontend", "1.0.0", "1.0.0")
    _add_mcp("github")
    report = build_doctor_report(project_dir=Path.cwd())
    payload = report.to_dict()
    assert payload["initialized"] is True
    assert payload["skills"] == {"total": 1, "updates_available": 0, "updates": []}
    assert payload["mcp_servers"] == 1
    assert payload["agents"] == 0
    assert payload["instructions"] == 0
    assert payload["issues"] == []
    json.dumps(payload)  # serializable


def test_doctor_uninitialized_json(isolated_home: Path):
    report = build_doctor_report(project_dir=Path.cwd())
    payload = report.to_dict()
    assert payload["initialized"] is False
    assert payload["issues"][0]["severity"] == "warning"


# ── Update detection ────────────────────────────────────────────────────


def test_doctor_update_available_when_versions_differ(isolated_home: Path):
    _register_skill("frontend", "1.0.0", "1.1.0")
    report = build_doctor_report(project_dir=Path.cwd())
    assert len(report.skills_updates) == 1
    update = report.skills_updates[0]
    assert isinstance(update, UpdateInfo)
    assert update.name == "frontend"
    assert update.store_version == "1.0.0"
    assert update.upstream_version == "1.1.0"
    assert update.source.endswith(Path(".github/skills/frontend").as_posix())


def test_doctor_no_update_when_versions_match(isolated_home: Path):
    _register_skill("frontend", "2.0.0", "2.0.0")
    report = build_doctor_report(project_dir=Path.cwd())
    assert report.skills_updates == []


def test_doctor_missing_version_skipped(isolated_home: Path):
    _init_store()
    _write_versioned_skill(Path.cwd() / ".github" / "skills", "frontend", "1.0.0")
    config = cfg.load_config()
    assert config is not None
    config.skills.append(Skill(name="frontend"))
    cfg.save_config(config)
    # Store copy has no version → no comparison possible → skipped.
    report = build_doctor_report(project_dir=Path.cwd())
    assert report.skills_updates == []


def test_doctor_updates_sorted_by_name(isolated_home: Path):
    _register_skill("zeta", "1.0.0", "2.0.0")
    _register_skill("alpha", "1.0.0", "2.0.0")
    report = build_doctor_report(project_dir=Path.cwd())
    assert [u.name for u in report.skills_updates] == ["alpha", "zeta"]


# ── Compatibility issues ────────────────────────────────────────────────


def test_doctor_invalid_opencode_json_is_error(isolated_home: Path):
    _init_store()
    (Path.cwd() / "opencode.json").write_text("{not valid json", encoding="utf-8")
    report = build_doctor_report(project_dir=Path.cwd())
    errors = [i for i in report.issues if i.severity == "error" and i.component == "opencode.json"]
    assert len(errors) == 1
    assert "Invalid JSON" in errors[0].message


def test_doctor_invalid_mcp_json_is_warning(isolated_home: Path):
    _init_store()
    (Path.cwd() / ".mcp.json").write_text("{broken", encoding="utf-8")
    report = build_doctor_report(project_dir=Path.cwd())
    warnings = [i for i in report.issues if i.severity == "warning" and ".mcp.json" in i.message]
    assert len(warnings) == 1


def test_doctor_valid_configs_no_issues(isolated_home: Path):
    _init_store()
    (Path.cwd() / "opencode.json").write_text('{"$schema": "https://opencode.ai/config.json"}', encoding="utf-8")
    (Path.cwd() / ".mcp.json").write_text('{"mcpServers": {}}', encoding="utf-8")
    report = build_doctor_report(project_dir=Path.cwd())
    assert report.issues == []


# ── CLI ─────────────────────────────────────────────────────────────────


def test_doctor_cli_renders_summary(isolated_home: Path, runner: CliRunner):
    _register_skill("frontend", "1.0.0", "1.0.0")
    _add_mcp("github")
    _add_agent("reviewer")
    result = runner.invoke(main, ["doctor", "--project-dir", str(Path.cwd())])
    assert result.exit_code == 0, result.output
    assert "Health Summary" in result.output
    assert "✓ Skills: 1" in result.output
    assert "✓ MCP servers: 1" in result.output
    assert "✓ Agents: 1" in result.output
    assert "✓ Instructions: 0" in result.output
    assert "No updates available." in result.output
    assert "No compatibility issues detected." in result.output


def test_doctor_cli_uninitialized_warns(isolated_home: Path, runner: CliRunner):
    result = runner.invoke(main, ["doctor", "--project-dir", str(Path.cwd())])
    assert result.exit_code == 0, result.output
    assert "Health Summary" in result.output
    assert "not initialized" in result.output
    assert "✓ Skills" not in result.output


def test_doctor_cli_shows_updates(isolated_home: Path, runner: CliRunner):
    _register_skill("frontend", "1.0.0", "1.1.0")
    result = runner.invoke(main, ["doctor", "--project-dir", str(Path.cwd())])
    assert result.exit_code == 0, result.output
    assert "1 updates available" in result.output
    assert "frontend" in result.output
    assert "store 1.0.0 → project 1.1.0" in result.output


def test_doctor_cli_json(isolated_home: Path, runner: CliRunner):
    _register_skill("frontend", "1.0.0", "1.1.0")
    result = runner.invoke(main, ["doctor", "--json", "--project-dir", str(Path.cwd())])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["initialized"] is True
    assert payload["skills"]["total"] == 1
    assert payload["skills"]["updates_available"] == 1
    assert payload["skills"]["updates"][0]["name"] == "frontend"


# ── Phase 3: HealthReport + FixAction ───────────────────────────────────


def test_health_report_structure(isolated_home: Path):
    """HealthReport contains issues, updates, fixes, and counts."""
    from ai_adapter.doctor import HealthReport, run_health_report

    _register_skill("frontend", "1.0.0", "1.0.0")
    _add_mcp("github")
    report = run_health_report(project_dir=Path.cwd())
    assert isinstance(report, HealthReport)
    assert report.initialized is True
    assert report.skills_total == 1
    assert report.mcp_total == 1
    assert isinstance(report.issues, list)
    assert isinstance(report.updates, list)
    assert isinstance(report.fixes, list)


def test_health_report_json_serializable(isolated_home: Path):
    """HealthReport.to_dict() produces valid JSON."""
    from ai_adapter.doctor import run_health_report

    _register_skill("frontend", "1.0.0", "1.0.0")
    report = run_health_report(project_dir=Path.cwd())
    payload = report.to_dict()
    json.dumps(payload)  # must not raise


def test_health_report_uninitialized(isolated_home: Path):
    """Uninitialized store produces a warning issue."""
    from ai_adapter.doctor import run_health_report

    report = run_health_report(project_dir=Path.cwd())
    assert report.initialized is False
    assert len(report.issues) == 1
    assert report.issues[0].severity == "warning"
    assert report.fixes == []


def test_health_report_detects_mcp_executability(isolated_home: Path):
    """MCP servers with unreachable commands produce warnings."""
    from ai_adapter.doctor import run_health_report

    _init_store()
    config = cfg.load_config()
    assert config is not None
    config.mcp_servers.append(MCPServer(name="fake-server", command="definitely-not-a-real-binary-xyz123"))
    cfg.save_config(config)
    report = run_health_report(project_dir=Path.cwd())
    warnings = [i for i in report.issues if i.component == "mcp" and "not found in PATH" in i.message]
    assert len(warnings) == 1


def test_health_report_fixes_for_updates(isolated_home: Path):
    """Available updates produce fix actions of kind 'update'."""
    from ai_adapter.doctor import run_health_report

    _register_skill("frontend", "1.0.0", "2.0.0")
    report = run_health_report(project_dir=Path.cwd())
    update_fixes = [f for f in report.fixes if f.kind == "update"]
    assert len(update_fixes) == 1
    assert update_fixes[0].target == "frontend"
    assert update_fixes[0].destructive is False


def test_health_report_fixes_for_mcp_disable(isolated_home: Path):
    """Unreachable MCP servers produce fix actions of kind 'disable'."""
    from ai_adapter.doctor import run_health_report

    _init_store()
    config = cfg.load_config()
    assert config is not None
    config.mcp_servers.append(MCPServer(name="broken-mcp", command="no-such-binary"))
    cfg.save_config(config)
    report = run_health_report(project_dir=Path.cwd())
    disable_fixes = [f for f in report.fixes if f.kind == "disable"]
    assert len(disable_fixes) == 1
    assert disable_fixes[0].target == "broken-mcp"


def test_doctor_cli_fix_dry_run(isolated_home: Path, runner: CliRunner):
    """doctor --fix --dry-run shows fixes without applying."""
    _register_skill("frontend", "1.0.0", "2.0.0")
    result = runner.invoke(main, ["doctor", "--fix", "--dry-run", "--project-dir", str(Path.cwd())])
    assert result.exit_code == 0, result.output
    assert "dry-run" in result.output.lower() or "[dry-run]" in result.output
    assert "frontend" in result.output


def test_doctor_fix_dry_run_no_snapshot(isolated_home: Path):
    """--dry-run should not create a backup snapshot."""
    from ai_adapter.commands.doctor import _get_backup_dir

    _register_skill("frontend", "1.0.0", "2.0.0")
    runner = CliRunner()
    runner.invoke(main, ["doctor", "--fix", "--dry-run", "--project-dir", str(Path.cwd())])
    backup_dir = _get_backup_dir()
    # No backups directory should be created in dry-run mode
    # (or at most an empty one from _ensure_backups_gitignored)
    if backup_dir.exists():
        snapshots = [d for d in backup_dir.iterdir() if d.is_dir() and d.name.startswith("20")]
        assert len(snapshots) == 0


def test_doctor_fix_applies_disable(isolated_home: Path, runner: CliRunner):
    """doctor --fix --force disables unreachable MCP servers."""
    _init_store()
    config = cfg.load_config()
    assert config is not None
    config.mcp_servers.append(MCPServer(name="broken-mcp", command="no-such-binary-xyz"))
    cfg.save_config(config)

    result = runner.invoke(main, ["doctor", "--fix", "--force", "--project-dir", str(Path.cwd())])
    assert result.exit_code == 0, result.output
    assert "Applied" in result.output

    # Verify the server is now disabled.
    config = cfg.load_config()
    assert config is not None
    server = next(s for s in config.mcp_servers if s.name == "broken-mcp")
    assert server.enabled is False


def test_doctor_fix_creates_snapshot(isolated_home: Path, runner: CliRunner):
    """doctor --fix creates a backup snapshot before applying."""
    from ai_adapter.commands.doctor import _get_backup_dir

    _init_store()
    config = cfg.load_config()
    assert config is not None
    config.mcp_servers.append(MCPServer(name="broken-mcp", command="no-such-binary"))
    cfg.save_config(config)

    result = runner.invoke(main, ["doctor", "--fix", "--force", "--project-dir", str(Path.cwd())])
    assert result.exit_code == 0, result.output
    assert "Snapshot saved" in result.output or "Backup:" in result.output

    backup_dir = _get_backup_dir()
    assert backup_dir.exists()
    snapshots = [d for d in backup_dir.iterdir() if d.is_dir() and d.name.startswith("20")]
    assert len(snapshots) >= 1
