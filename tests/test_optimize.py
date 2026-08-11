"""Tests for the optimize module and ``ai-adapter optimize`` command.

Covers:
- Duplicate instruction detection
- Unused MCP server detection
- Duplicate skill registration detection
- Configuration drift detection
- OptimizationReport structure and serialization
- --apply with --dry-run safety
- --apply with backup snapshot creation
- MCP server disable on --apply
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from ai_adapter import config as cfg
from ai_adapter.cli import main
from ai_adapter.models import Agent, Instruction, MCPServer, Skill
from ai_adapter.optimize import (
    OptimizationReport,
    _detect_config_drift,
    _detect_duplicate_instructions,
    _detect_duplicate_skills,
    _detect_unused_mcp,
    run_optimization,
)

# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


# ── Helpers ─────────────────────────────────────────────────────────────


def _init_store() -> None:
    cfg.init()


def _register_skill(name: str, env: str | None = None, tags: list[str] | None = None) -> None:
    _init_store()
    config = cfg.load_config()
    assert config is not None
    config.skills.append(Skill(name=name, tags=tags or [], env=env))
    cfg.save_config(config)


def _register_mcp(name: str, command: str = "mcp-cmd", enabled: bool = True, tools: list[str] | None = None) -> None:
    _init_store()
    config = cfg.load_config()
    assert config is not None
    config.mcp_servers.append(MCPServer(name=name, command=command, enabled=enabled, tools=tools or []))
    cfg.save_config(config)


def _register_agent(name: str, description: str = "") -> None:
    _init_store()
    config = cfg.load_config()
    assert config is not None
    config.agents.append(Agent(name=name, description=description))
    cfg.save_config(config)


# ── Duplicate instructions ──────────────────────────────────────────────


def test_duplicate_instructions_detected(isolated_home: Path):
    """Two instruction files with identical content are detected."""
    instructions_dir = isolated_home / ".ai-adapter" / "instructions"
    instructions_dir.mkdir(parents=True, exist_ok=True)
    content = "# Shared instructions\nBe helpful."
    (instructions_dir / "shared1.md").write_text(content, encoding="utf-8")
    (instructions_dir / "shared2.md").write_text(content, encoding="utf-8")

    _init_store()
    config = cfg.load_config()
    assert config is not None
    config.instructions.append(Instruction(name="shared1"))
    config.instructions.append(Instruction(name="shared2"))
    cfg.save_config(config)

    issues, actions = _detect_duplicate_instructions(config, isolated_home)
    assert len(issues) == 1
    assert "Duplicate instructions" in issues[0].message
    assert len(actions) == 1
    assert actions[0].kind == "merge"


def test_no_duplicate_instructions(isolated_home: Path):
    """Different instruction files produce no issues."""
    instructions_dir = isolated_home / ".ai-adapter" / "instructions"
    instructions_dir.mkdir(parents=True, exist_ok=True)
    (instructions_dir / "a.md").write_text("Content A", encoding="utf-8")
    (instructions_dir / "b.md").write_text("Content B", encoding="utf-8")

    _init_store()
    config = cfg.load_config()
    assert config is not None
    issues, actions = _detect_duplicate_instructions(config, isolated_home)
    assert len(issues) == 0
    assert len(actions) == 0


# ── Unused MCP ──────────────────────────────────────────────────────────


def test_unused_mcp_detected(isolated_home: Path):
    """MCP server not referenced by any skill or agent is flagged."""
    _register_mcp("orphan-mcp", tools=[])
    _init_store()
    config = cfg.load_config()
    assert config is not None
    issues, actions = _detect_unused_mcp(config)
    names = [a.target for a in actions if a.kind == "disable"]
    assert "orphan-mcp" in names


def test_mcp_with_tools_not_unused(isolated_home: Path):
    """MCP server with tools list is not flagged as unused."""
    _register_mcp("useful-mcp", tools=["vscode"])
    _init_store()
    config = cfg.load_config()
    assert config is not None
    issues, actions = _detect_unused_mcp(config)
    disable_actions = [a for a in actions if a.kind == "disable" and a.target == "useful-mcp"]
    assert len(disable_actions) == 0


# ── Duplicate skills ────────────────────────────────────────────────────


def test_duplicate_skill_detected(isolated_home: Path):
    """Same skill name in multiple envs is flagged."""
    _register_skill("shared", env="dev")
    _register_skill("shared", env="prod")
    _init_store()
    config = cfg.load_config()
    assert config is not None
    issues, actions = _detect_duplicate_skills(config)
    assert len(issues) == 1
    assert "shared" in issues[0].message
    assert len(actions) == 1
    assert actions[0].kind == "unify"


def test_no_duplicate_skills(isolated_home: Path):
    """Different skill names produce no issues."""
    _register_skill("alpha")
    _register_skill("beta")
    _init_store()
    config = cfg.load_config()
    assert config is not None
    issues, actions = _detect_duplicate_skills(config)
    assert len(issues) == 0


# ── Config drift ────────────────────────────────────────────────────────


def test_config_drift_detected(isolated_home: Path):
    """MCP server present in one tool but not another is flagged."""
    # Create a Claude settings with an MCP server.
    claude_dir = isolated_home / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    (claude_dir / "settings.json").write_text(
        json.dumps({"mcpServers": {"drift-mcp": {"command": "test"}}}),
        encoding="utf-8",
    )
    # Cursor has no such server.
    cursor_dir = isolated_home / ".cursor"
    cursor_dir.mkdir(parents=True, exist_ok=True)
    (cursor_dir / "mcp.json").write_text(
        json.dumps({"mcpServers": {}}),
        encoding="utf-8",
    )

    issues, actions = _detect_config_drift(isolated_home)
    drift_issues = [i for i in issues if "drift-mcp" in i.message]
    assert len(drift_issues) == 1
    assert "claude" in drift_issues[0].message
    assert "cursor" in drift_issues[0].message


# ── OptimizationReport ─────────────────────────────────────────────────


def test_optimization_report_structure(isolated_home: Path):
    """run_optimization returns a valid OptimizationReport."""
    _init_store()
    report = run_optimization()
    assert isinstance(report, OptimizationReport)
    assert isinstance(report.issues, list)
    assert isinstance(report.recommendations, list)
    assert isinstance(report.estimated_reduction, float)
    assert isinstance(report.actions, list)


def test_optimization_report_json_serializable(isolated_home: Path):
    """OptimizationReport.to_dict() produces valid JSON."""
    _init_store()
    report = run_optimization()
    payload = report.to_dict()
    json.dumps(payload)


def test_optimization_report_uninitialized(isolated_home: Path):
    """Uninitialized store produces a warning."""
    report = run_optimization()
    assert len(report.issues) == 1
    assert report.issues[0].severity == "warning"
    assert report.actions == []


# ── CLI tests ───────────────────────────────────────────────────────────


def test_optimize_cli_renders_report(isolated_home: Path, runner: CliRunner):
    """optimize command renders analysis output."""
    _register_mcp("orphan-mcp", tools=[])
    result = runner.invoke(main, ["optimize"])
    assert result.exit_code == 0, result.output
    assert "Analyzing" in result.output


def test_optimize_cli_json(isolated_home: Path, runner: CliRunner):
    """optimize --json outputs valid JSON."""
    _init_store()
    result = runner.invoke(main, ["optimize", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert "issues" in payload
    assert "actions" in payload


def test_optimize_apply_dry_run(isolated_home: Path, runner: CliRunner):
    """optimize --apply --dry-run shows planned actions without applying."""
    _register_mcp("orphan-mcp", tools=[])
    result = runner.invoke(main, ["optimize", "--apply", "--dry-run"])
    assert result.exit_code == 0, result.output
    assert "dry-run" in result.output.lower() or "[dry-run]" in result.output


def test_optimize_apply_disables_unused_mcp(isolated_home: Path, runner: CliRunner):
    """optimize --apply --force disables unused MCP servers."""
    _register_mcp("orphan-mcp", tools=[])
    result = runner.invoke(main, ["optimize", "--apply", "--force"])
    assert result.exit_code == 0, result.output

    # Verify the server is now disabled.
    config = cfg.load_config()
    assert config is not None
    server = next(s for s in config.mcp_servers if s.name == "orphan-mcp")
    assert server.enabled is False


def test_optimize_apply_creates_snapshot(isolated_home: Path, runner: CliRunner):
    """optimize --apply creates a backup snapshot."""
    from ai_adapter.commands.optimize import _get_backup_dir

    _register_mcp("orphan-mcp", tools=[])
    result = runner.invoke(main, ["optimize", "--apply", "--force"])
    assert result.exit_code == 0, result.output
    assert "Snapshot saved" in result.output or "Backup:" in result.output

    backup_dir = _get_backup_dir()
    assert backup_dir.exists()
    snapshots = [d for d in backup_dir.iterdir() if d.is_dir() and d.name.startswith("20")]
    assert len(snapshots) >= 1


def test_optimize_no_actions_needed(isolated_home: Path, runner: CliRunner):
    """optimize with no issues shows no actions."""
    _init_store()
    result = runner.invoke(main, ["optimize"])
    assert result.exit_code == 0, result.output
    # Should still work without errors
