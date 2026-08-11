"""Tests for the scan module and ``ai-adapter scan`` command.

Covers (plan §5):
- Tool detection for Claude Code / Codex / Cursor / OpenCode / project
- Security: credential files and full file contents never appear
- Merged rendering and ``--json`` output
- Problem diagnosis (duplicate MCP, skill mismatch, stale skills)
- The init import hook (interactive only)

HOME isolation: every test uses the :func:`isolated_home` fixture so scan
never reads the real ``~/.claude`` etc. (cwd isolation alone is not enough).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from ai_adapter import config as cfg
from ai_adapter.cli import main
from ai_adapter.scan import (
    SCAN_IGNORE_PATTERNS,
    ScanItem,
    ScanResult,
    diagnose,
    import_detected_items,
    is_ignored,
    scan_all,
    scan_result_to_dict,
)

# ── Fixtures & helpers ──────────────────────────────────────────────────


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def _write_skill(root: Path, tool: str, dir_name: str, description: str = "Desc", **extra: object) -> Path:
    """Create ``<root>/.<tool>/skills/<dir_name>/SKILL.md`` and return its path.

    ``extra`` may override the frontmatter (e.g. ``name=``, ``version=``).
    """
    skill_file = root / f".{tool}" / "skills" / dir_name / "SKILL.md"
    frontmatter: dict[str, object] = {"name": dir_name, "description": description}
    frontmatter.update(extra)
    skill_name = frontmatter["name"]
    body = (
        ["---"]
        + [f"{k}: {v}" for k, v in frontmatter.items()]
        + ["---", "", f"# {skill_name}", f"Sensitive body of {skill_name}"]
    )
    skill_file.parent.mkdir(parents=True, exist_ok=True)
    skill_file.write_text("\n".join(body) + "\n", encoding="utf-8")
    return skill_file


def _write_agent(root: Path, tool: str, name: str, description: str = "Agent desc") -> Path:
    """Create ``<root>/.<tool>/agents/<name>.agent.md`` and return its path."""
    agent_file = root / f".{tool}" / "agents" / f"{name}.agent.md"
    agent_file.parent.mkdir(parents=True, exist_ok=True)
    agent_file.write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n# {name}\nSensitive body of agent\n",
        encoding="utf-8",
    )
    return agent_file


def _write_json_config(path: Path, data: object) -> Path:
    """Write a JSON config file, creating parent directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def _claude_env(home: Path) -> None:
    """Create a representative ~/.claude/ layout."""
    _write_agent(home, "claude", "reviewer")
    _write_skill(home, "claude", "database-schema", description="Schema skill")
    _write_json_config(
        home / ".claude" / "settings.json",
        {"mcpServers": {"github": {"command": "gh-mcp", "args": []}}},
    )


def _project_env(project: Path) -> None:
    """Create a representative project .github/ + root layout."""
    (project / ".github" / "agents").mkdir(parents=True)
    (project / ".github" / "agents" / "reviewer.agent.md").write_text(
        "---\nname: reviewer\ndescription: Review agent\n---\n# reviewer\n",
        encoding="utf-8",
    )
    (project / ".github" / "skills").mkdir(parents=True)
    _write_skill(project, "github", "frontend", description="Frontend skill")
    (project / "AGENTS.md").write_text("# Project instructions\n", encoding="utf-8")
    (project / "CLAUDE.md").write_text("# Claude instructions\n", encoding="utf-8")


# ── 1-1a: Claude Code detection ─────────────────────────────────────────


def test_scan_claude_agents_detected(isolated_home: Path):
    _write_agent(isolated_home, "claude", "reviewer")
    result = scan_all(project_dir=Path.cwd())
    agents = [i for i in result.items if i.tool == "claude" and i.category == "agent"]
    assert len(agents) == 1
    assert agents[0].name == "reviewer"
    assert agents[0].description == "Agent desc"
    assert agents[0].path is not None and agents[0].path.name == "reviewer.agent.md"


def test_scan_claude_skills_detected(isolated_home: Path):
    _write_skill(isolated_home, "claude", "database-schema", description="Schema skill")
    result = scan_all(project_dir=Path.cwd())
    skills = [i for i in result.items if i.tool == "claude" and i.category == "skill"]
    assert len(skills) == 1
    assert skills[0].name == "database-schema"
    assert skills[0].description == "Schema skill"
    assert skills[0].path is not None and skills[0].path.name == "SKILL.md"


def test_scan_claude_skill_uses_frontmatter_name(isolated_home: Path):
    # Directory name differs from frontmatter name: frontmatter wins.
    _write_skill(isolated_home, "claude", "dir-name", name="actual-name")
    result = scan_all(project_dir=Path.cwd())
    skills = [i for i in result.items if i.tool == "claude" and i.category == "skill"]
    assert len(skills) == 1
    assert skills[0].name == "actual-name"


def test_scan_claude_settings_detected(isolated_home: Path):
    _write_json_config(isolated_home / ".claude" / "settings.json", {})
    result = scan_all(project_dir=Path.cwd())
    settings = [i for i in result.items if i.tool == "claude" and i.category == "settings"]
    assert len(settings) == 1
    assert settings[0].name == "settings.json"


def test_scan_claude_mcp_servers_from_settings(isolated_home: Path):
    _write_json_config(
        isolated_home / ".claude" / "settings.json",
        {"mcpServers": {"github": {"command": "gh-mcp"}, "context7": {"command": "ctx7"}}},
    )
    result = scan_all(project_dir=Path.cwd())
    mcp = [i for i in result.items if i.tool == "claude" and i.category == "mcp"]
    assert {i.name for i in mcp} == {"github", "context7"}


def test_scan_claude_not_installed(isolated_home: Path):
    result = scan_all(project_dir=Path.cwd())
    assert result.count(tool="claude") == 0


# ── 1-1b: Codex / Cursor detection ──────────────────────────────────────


def test_scan_codex_config_agents_skills(isolated_home: Path):
    (isolated_home / ".codex").mkdir(parents=True)
    (isolated_home / ".codex" / "config.toml").write_text("model = 'gpt-5'\n", encoding="utf-8")
    _write_agent(isolated_home, "codex", "coder")
    _write_skill(isolated_home, "codex", "frontend", description="Frontend skill")
    result = scan_all(project_dir=Path.cwd())
    assert result.count(tool="codex", category="settings") == 1
    assert result.count(tool="codex", category="agent") == 1
    assert result.count(tool="codex", category="skill") == 1


def test_scan_codex_not_installed(isolated_home: Path):
    result = scan_all(project_dir=Path.cwd())
    assert result.count(tool="codex") == 0


def test_scan_cursor_rules_and_mcp(isolated_home: Path):
    rules = isolated_home / ".cursor" / "rules"
    rules.mkdir(parents=True)
    (rules / "frontend.mdc").write_text("---\ndescription: Frontend rule\n---\nbody\n", encoding="utf-8")
    _write_json_config(
        isolated_home / ".cursor" / "mcp.json",
        {"mcpServers": {"playwright": {"command": "npx", "args": ["@playwright/mcp"]}}},
    )
    result = scan_all(project_dir=Path.cwd())
    skills = [i for i in result.items if i.tool == "cursor" and i.category == "skill"]
    assert len(skills) == 1
    assert skills[0].name == "frontend"
    assert result.count(tool="cursor", category="mcp") == 1


def test_scan_cursor_not_installed(isolated_home: Path):
    result = scan_all(project_dir=Path.cwd())
    assert result.count(tool="cursor") == 0


def test_scan_codex_auth_json_excluded(isolated_home: Path):
    """Security: ~/.codex/auth.json must never appear in scan results."""
    codex_dir = isolated_home / ".codex"
    codex_dir.mkdir(parents=True)
    (codex_dir / "config.toml").write_text("model = 'gpt-5'\n", encoding="utf-8")
    (codex_dir / "auth.json").write_text('{"OPENAI_API_KEY": "sk-secret-value"}\n', encoding="utf-8")
    result = scan_all(project_dir=Path.cwd())
    items = result.items
    assert not any(i.path is not None and i.path.name == "auth.json" for i in items)
    assert not any("auth.json" in str(i.path) for i in items)
    # The rest of the codex config is still detected.
    assert result.count(tool="codex", category="settings") == 1


def test_scan_ignores_generic_secrets(isolated_home: Path):
    """Security: .env / *.key / *secret* / *token* are excluded."""
    claude_dir = isolated_home / ".claude"
    claude_dir.mkdir(parents=True)
    (claude_dir / ".env").write_text("API_KEY=leaked\n", encoding="utf-8")
    (claude_dir / "deploy.key").write_text("PRIVATE KEY material\n", encoding="utf-8")
    (claude_dir / "secrets.json").write_text('{"token": "leaked"}\n', encoding="utf-8")
    _write_agent(isolated_home, "claude", "reviewer")
    result = scan_all(project_dir=Path.cwd())
    assert all(
        i.path is None or not is_ignored(str(i.path).replace(str(isolated_home), "").lstrip("/")) for i in result.items
    )
    names = [i.name for i in result.items]
    assert ".env" not in names
    assert "deploy.key" not in names
    assert "secrets.json" not in names


# ── 1-1c: OpenCode / project detection ──────────────────────────────────


def test_scan_opencode_global_config(isolated_home: Path):
    _write_json_config(
        isolated_home / ".config" / "opencode" / "opencode.json",
        {"mcp": {"github": {"type": "local", "command": ["gh-mcp"]}}},
    )
    result = scan_all(project_dir=Path.cwd())
    assert result.count(tool="opencode", category="settings") == 1
    mcp = [i for i in result.items if i.tool == "opencode" and i.category == "mcp"]
    assert [i.name for i in mcp] == ["github"]


def test_scan_project_github_agents_and_skills(isolated_home: Path):
    project = Path.cwd()
    _project_env(project)
    result = scan_all(project_dir=project)
    assert result.count(tool="project", category="agent") == 1
    skills = [i for i in result.items if i.tool == "project" and i.category == "skill"]
    assert len(skills) == 1
    assert skills[0].name == "frontend"


def test_scan_project_root_instructions(isolated_home: Path):
    project = Path.cwd()
    _project_env(project)
    result = scan_all(project_dir=project)
    instructions = [i.name for i in result.items if i.category == "instruction"]
    assert "AGENTS.md" in instructions
    assert "CLAUDE.md" in instructions


def test_scan_project_mcp_json(isolated_home: Path):
    project = Path.cwd()
    _write_json_config(
        project / ".mcp.json",
        {"mcpServers": {"github": {"command": "gh-mcp", "args": []}}},
    )
    result = scan_all(project_dir=project)
    mcp = [i for i in result.items if i.tool == "project" and i.category == "mcp"]
    assert [i.name for i in mcp] == ["github"]


def test_scan_project_dir_option(isolated_home: Path, tmp_path: Path):
    """scan_all honors an explicit project_dir (default is cwd)."""
    other = tmp_path / "other-project"
    other.mkdir(parents=True)
    (other / "AGENTS.md").write_text("# Other\n", encoding="utf-8")
    result = scan_all(project_dir=other)
    assert any(i.category == "instruction" and i.name == "AGENTS.md" for i in result.items)


def test_scan_project_not_detected(isolated_home: Path):
    result = scan_all(project_dir=Path.cwd())
    assert result.count(tool="project") == 0


# ── 1-1d: Merged rendering & JSON ───────────────────────────────────────


def test_scan_result_counts(isolated_home: Path):
    _claude_env(isolated_home)
    _project_env(Path.cwd())
    result = scan_all(project_dir=Path.cwd())
    assert result.count(tool="claude", category="agent") == 1
    assert result.count(tool="claude", category="skill") == 1
    assert result.count(category="instruction") >= 2


def test_scan_json_output_structure(isolated_home: Path):
    _claude_env(isolated_home)
    result = scan_all(project_dir=Path.cwd())
    payload = scan_result_to_dict(result)
    assert payload["agents"]["claude"] >= 1
    assert payload["skills"]["total"] >= 1
    assert payload["mcp"]["total"] >= 1
    assert isinstance(payload["problems"], list)
    # Items are JSON-serializable.
    json.dumps(payload)


def test_scan_json_uninstalled_tools_are_zero(isolated_home: Path):
    result = scan_all(project_dir=Path.cwd())
    payload = scan_result_to_dict(result)
    for tool in ("claude", "codex", "cursor", "opencode", "project"):
        assert payload["agents"][tool] == 0, tool


def test_scan_json_per_tool_installed_flags(isolated_home: Path):
    """JSON exposes per-tool installed/settings so settings-only installs
    are distinguishable from missing tools (F2)."""
    (isolated_home / ".codex").mkdir(parents=True)
    (isolated_home / ".codex" / "config.toml").write_text("model = 'gpt-5'\n", encoding="utf-8")
    result = scan_all(project_dir=Path.cwd())
    payload = scan_result_to_dict(result)
    assert payload["tools"]["codex"]["installed"] is True
    assert payload["tools"]["codex"]["settings"] == 1
    assert payload["tools"]["claude"]["installed"] is False
    assert payload["tools"]["claude"]["settings"] == 0


def test_scan_cli_settings_only_tool_not_reported_not_installed(isolated_home: Path, runner: CliRunner):
    """A settings-only install (config.toml, no agents) must not be shown
    as 'not installed' (F2)."""
    (isolated_home / ".codex").mkdir(parents=True)
    (isolated_home / ".codex" / "config.toml").write_text("model = 'gpt-5'\n", encoding="utf-8")
    result = runner.invoke(main, ["scan", "--project-dir", str(Path.cwd())], input="n\n")
    assert result.exit_code == 0, result.output
    assert "Codex: installed (no agents/skills)" in result.output
    assert "Codex: 0 detected (not installed)" not in result.output


def test_scan_cli_output_summary(isolated_home: Path, runner: CliRunner):
    _claude_env(isolated_home)
    _write_skill(isolated_home, "claude", "frontend", description="Frontend")
    result = runner.invoke(main, ["scan", "--project-dir", str(Path.cwd())], input="n\n")
    assert result.exit_code == 0, result.output
    assert "AI Environment" in result.output
    assert "Claude Code: 1 detected" in result.output
    assert "Codex: 0 detected (not installed)" in result.output
    assert "Skills" in result.output
    assert "database-schema" in result.output
    assert "Potential problems" in result.output


def test_scan_cli_json(isolated_home: Path, runner: CliRunner):
    _claude_env(isolated_home)
    result = runner.invoke(main, ["scan", "--json", "--project-dir", str(Path.cwd())])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["agents"]["claude"] >= 1


# ── 1-2: Problem diagnosis ──────────────────────────────────────────────


def test_diagnose_duplicate_mcp_across_tools(isolated_home: Path):
    _write_json_config(
        isolated_home / ".config" / "opencode" / "opencode.json",
        {"mcp": {"github": {"type": "local", "command": ["gh-mcp"]}}},
    )
    _write_json_config(
        Path.cwd() / ".mcp.json",
        {"mcpServers": {"github": {"command": "gh-mcp", "args": []}}},
    )
    result = scan_all(project_dir=Path.cwd())
    problems = [p for p in result.problems if p.severity == "warning" and "duplicate MCP" in p.message]
    assert len(problems) == 1
    assert "github" in problems[0].message


def test_diagnose_no_duplicate_mcp(isolated_home: Path):
    _write_json_config(
        Path.cwd() / ".mcp.json",
        {"mcpServers": {"github": {"command": "gh-mcp"}}},
    )
    result = scan_all(project_dir=Path.cwd())
    assert not any("duplicate MCP" in p.message for p in result.problems)


def test_diagnose_skill_mismatch_between_claude_and_codex(isolated_home: Path):
    _write_skill(isolated_home, "claude", "frontend", description="Same")
    _write_skill(isolated_home, "codex", "frontend", description="Different body")
    result = scan_all(project_dir=Path.cwd())
    problems = [p for p in result.problems if "differs between Claude" in p.message]
    assert len(problems) == 1
    assert "frontend" in problems[0].message


def test_diagnose_skill_mismatch_same_content_no_issue(isolated_home: Path):
    body = "---\nname: frontend\ndescription: Same\n---\n# Same body\n"
    for tool in ("claude", "codex"):
        skill_file = isolated_home / f".{tool}" / "skills" / "frontend" / "SKILL.md"
        skill_file.parent.mkdir(parents=True, exist_ok=True)
        skill_file.write_text(body, encoding="utf-8")
    result = scan_all(project_dir=Path.cwd())
    assert not any("differs between Claude" in p.message for p in result.problems)


def test_diagnose_stale_skill_reports_info(isolated_home: Path):
    _write_skill(isolated_home, "claude", "old-skill", update_date="2000-01-01")
    result = scan_all(project_dir=Path.cwd())
    problems = [p for p in result.problems if p.severity == "info" and "has not been updated" in p.message]
    assert len(problems) == 1
    assert "old-skill" in problems[0].message


def test_diagnose_fresh_skill_no_issue(isolated_home: Path):
    from datetime import date

    _write_skill(isolated_home, "claude", "fresh-skill", update_date=date.today().isoformat())
    result = scan_all(project_dir=Path.cwd())
    assert not any("has not been updated" in p.message for p in result.problems)


def test_diagnose_invalid_skill_version_is_ignored(isolated_home: Path):
    # Non-date update_date values are skipped without crashing.
    _write_skill(isolated_home, "claude", "odd-skill", update_date="not-a-date")
    result = scan_all(project_dir=Path.cwd())
    assert not any("has not been updated" in p.message for p in result.problems)


def test_diagnose_no_problems(isolated_home: Path):
    result = scan_all(project_dir=Path.cwd())
    assert result.problems == []


def test_scan_cli_problems_section(isolated_home: Path, runner: CliRunner):
    _write_json_config(
        isolated_home / ".config" / "opencode" / "opencode.json",
        {"mcp": {"github": {"type": "local", "command": ["gh-mcp"]}}},
    )
    _write_json_config(Path.cwd() / ".mcp.json", {"mcpServers": {"github": {"command": "gh-mcp"}}})
    result = runner.invoke(main, ["scan", "--project-dir", str(Path.cwd())], input="n\n")
    assert result.exit_code == 0, result.output
    assert "Potential problems" in result.output
    assert "duplicate MCP server" in result.output


def test_scan_cli_no_problems_message(isolated_home: Path, runner: CliRunner):
    result = runner.invoke(main, ["scan", "--project-dir", str(Path.cwd())])
    assert result.exit_code == 0, result.output
    assert "No potential problems detected." in result.output


def test_scan_json_includes_problems(isolated_home: Path, runner: CliRunner):
    _write_json_config(
        isolated_home / ".config" / "opencode" / "opencode.json",
        {"mcp": {"github": {"type": "local", "command": ["gh-mcp"]}}},
    )
    _write_json_config(Path.cwd() / ".mcp.json", {"mcpServers": {"github": {"command": "gh-mcp"}}})
    result = runner.invoke(main, ["scan", "--json", "--project-dir", str(Path.cwd())])
    payload = json.loads(result.output)
    assert any("duplicate MCP" in p["message"] for p in payload["problems"])


# ── Security ────────────────────────────────────────────────────────────


def test_scan_result_never_contains_credential_paths(isolated_home: Path):
    """The full scan output must not mention any credential file."""
    codex_dir = isolated_home / ".codex"
    codex_dir.mkdir(parents=True)
    (codex_dir / "auth.json").write_text('{"key": "sk-abc"}\n', encoding="utf-8")
    (codex_dir / "config.toml").write_text("model = 'x'\n", encoding="utf-8")
    _write_json_config(isolated_home / ".claude" / ".credentials.json", {"token": "abc"})
    _write_json_config(isolated_home / ".claude" / ".env", {"TOKEN": "abc"})
    _write_agent(isolated_home, "claude", "reviewer")

    result = scan_all(project_dir=Path.cwd())
    rendered = repr([i.to_dict() for i in result.items])
    assert "auth.json" not in rendered
    assert ".credentials.json" not in rendered
    assert "sk-abc" not in rendered
    assert "TOKEN" not in rendered


def test_scan_output_hides_full_file_content(isolated_home: Path, runner: CliRunner):
    """Frontmatter is shown; body content and credential values are not."""
    _write_skill(isolated_home, "claude", "database-schema", description="Schema skill")
    _write_json_config(isolated_home / ".claude" / "settings.json", {"mcpServers": {"github": {"command": "x"}}})
    result = runner.invoke(main, ["scan", "--project-dir", str(Path.cwd())], input="n\n")
    assert result.exit_code == 0, result.output
    assert "database-schema" in result.output
    assert "Sensitive body" not in result.output  # body of SKILL.md never printed
    assert "mcpServers" not in result.output  # raw JSON structure never printed


def test_is_ignored_patterns():
    assert is_ignored(".codex/auth.json")
    assert is_ignored(".claude/.credentials.json")
    assert is_ignored(".cursor/auth.json")
    assert is_ignored(".cursor/credentials.json")
    assert is_ignored(".cursor/keys.json")
    assert is_ignored(".env")
    assert is_ignored(".claude/prod.env")
    assert is_ignored("deploy.pem")
    assert is_ignored("deploy.key")
    assert is_ignored("secrets.json")
    assert is_ignored("tokens.txt")
    assert is_ignored("credentials.json")
    assert is_ignored("jwt-token.json")
    # Normal files are not ignored.
    assert not is_ignored(".claude/settings.json")
    assert not is_ignored(".codex/config.toml")
    assert not is_ignored(".github/agents/reviewer.agent.md")
    # Generic secret words match filename components exactly, never as
    # substrings: "secretary" / "tokensmith" must not be collapsed into
    # "secret" / "token" (F1 regression).
    assert not is_ignored(".github/agents/secretary.agent.md")
    assert not is_ignored("tokensmith.md")


def test_scan_detects_secretary_agent(isolated_home: Path):
    """Security: component-wise secret matching must not hide secretary.agent.md."""
    project = Path.cwd()
    agents_dir = project / ".github" / "agents"
    agents_dir.mkdir(parents=True)
    (agents_dir / "secretary.agent.md").write_text(
        "---\nname: secretary\ndescription: Office agent\n---\n# secretary\n",
        encoding="utf-8",
    )
    result = scan_all(project_dir=project)
    agents = [i for i in result.items if i.tool == "project" and i.category == "agent"]
    assert [a.name for a in agents] == ["secretary"]


def test_scan_ignore_patterns_are_defined():
    assert SCAN_IGNORE_PATTERNS
    assert ".codex/auth.json" in SCAN_IGNORE_PATTERNS


# ── 1-3: init import hook ───────────────────────────────────────────────


def test_scan_offers_import_when_uninitialized(isolated_home: Path, runner: CliRunner):
    _claude_env(isolated_home)
    assert not cfg.get_config_path().exists()
    result = runner.invoke(main, ["scan", "--project-dir", str(Path.cwd())], input="n\n")
    assert result.exit_code == 0, result.output
    assert "Import them into" in result.output
    assert "reviewer" in result.output


def test_scan_import_yes_imports_items(isolated_home: Path, runner: CliRunner):
    _claude_env(isolated_home)
    _project_env(Path.cwd())
    result = runner.invoke(main, ["scan", "--project-dir", str(Path.cwd())], input="y\n")
    assert result.exit_code == 0, result.output
    assert "Imported" in result.output
    config = cfg.load_config()
    assert config is not None
    assert any(a.name == "reviewer" for a in config.agents)
    assert any(s.name == "database-schema" for s in config.skills)
    assert any(s.name == "github" for s in config.mcp_servers)


def test_scan_import_no_skips(isolated_home: Path, runner: CliRunner):
    _claude_env(isolated_home)
    result = runner.invoke(main, ["scan", "--project-dir", str(Path.cwd())], input="n\n")
    assert result.exit_code == 0, result.output
    assert cfg.get_config_path().exists() is False
    assert cfg.load_config() is None


def test_scan_no_import_prompt_in_json_mode(isolated_home: Path, runner: CliRunner):
    _claude_env(isolated_home)
    result = runner.invoke(main, ["scan", "--json", "--project-dir", str(Path.cwd())])
    assert result.exit_code == 0, result.output
    assert "Import them into" not in result.output
    json.loads(result.output)


def test_scan_no_import_prompt_when_initialized(isolated_home: Path, runner: CliRunner):
    cfg.init()
    _claude_env(isolated_home)
    result = runner.invoke(main, ["scan", "--project-dir", str(Path.cwd())])
    assert result.exit_code == 0, result.output
    assert "Import them into" not in result.output


def test_scan_no_import_prompt_when_no_items(isolated_home: Path, runner: CliRunner):
    result = runner.invoke(main, ["scan", "--project-dir", str(Path.cwd())])
    assert result.exit_code == 0, result.output
    assert "Import them into" not in result.output


def test_import_detected_items_registers_mcp_and_skills(isolated_home: Path):
    _write_json_config(
        isolated_home / ".config" / "opencode" / "opencode.json",
        {"mcp": {"github": {"type": "local", "command": ["gh-mcp", "--flag"]}}},
    )
    _write_skill(isolated_home, "claude", "db-schema", description="Schema")
    result = scan_all(project_dir=Path.cwd())
    imported = import_detected_items(result)
    assert imported >= 2
    config = cfg.load_config()
    assert config is not None
    assert any(s.name == "db-schema" for s in config.skills)
    server = next((s for s in config.mcp_servers if s.name == "github"), None)
    assert server is not None
    assert server.command == "gh-mcp"
    assert server.args == ["--flag"]


def test_import_skill_rejects_path_traversal_name(isolated_home: Path):
    """Security: frontmatter ``name: ../../evil`` must not escape the store (F3).

    The destination is built from the frontmatter name and replaced with
    ``shutil.rmtree`` on collision; an unsafe name must be skipped before
    any copy/delete so nothing outside the store is written or removed.
    """
    skill_dir = isolated_home / ".claude" / "skills" / "sneaky"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: ../../evil\ndescription: sneaky\n---\n# sneaky\n",
        encoding="utf-8",
    )
    # Decoy at exactly the path a traversal rmtree would target
    # (~/.ai-adapter/skills/../../evil → ~/evil).
    decoy = isolated_home / "evil"
    decoy.mkdir()
    (decoy / "precious.txt").write_text("keep me\n", encoding="utf-8")

    result = scan_all(project_dir=Path.cwd())
    imported = import_detected_items(result)

    assert imported == 0
    # Nothing was deleted or written outside the store.
    assert (decoy / "precious.txt").read_text(encoding="utf-8") == "keep me\n"
    assert not (cfg.AI_ADAPTER_DIR / "evil").exists()
    config = cfg.load_config()
    assert config is not None
    assert not any(s.name == "../../evil" for s in config.skills)


def test_scan_import_prompt_closed_stdin_skips(isolated_home: Path, runner: CliRunner):
    """Closed stdin (EOF) with detected items must not abort the scan (F4).

    ``click.confirm`` raises ``Abort`` on EOF; the read-only diagnostic
    must degrade to "Import skipped." with exit code 0 instead of failing.
    """
    _claude_env(isolated_home)
    result = runner.invoke(main, ["scan", "--project-dir", str(Path.cwd())], input="")
    assert result.exit_code == 0, result.output
    assert "Import skipped." in result.output
    assert "Aborted!" not in result.output


# ── Data structure sanity ───────────────────────────────────────────────


def test_scanitem_to_dict_only_public_fields():
    item = ScanItem("claude", "skill", "name", description="desc", tags=["a"], path=Path("/x/SKILL.md"))
    d = item.to_dict()
    assert d["tool"] == "claude"
    assert d["category"] == "skill"
    assert d["name"] == "name"
    assert d["description"] == "desc"
    assert d["tags"] == ["a"]
    assert d["path"] == "/x/SKILL.md"


def test_scanresult_count_and_by_category():
    result = ScanResult(
        items=[
            ScanItem("claude", "agent", "a"),
            ScanItem("codex", "agent", "b"),
            ScanItem("claude", "skill", "c"),
        ]
    )
    assert result.count() == 3
    assert result.count(tool="claude") == 2
    assert result.count(category="agent") == 2
    assert result.count(tool="claude", category="agent") == 1
    assert [i.name for i in result.by_category("skill")] == ["c"]


def test_diagnose_is_read_only(isolated_home: Path):
    """Diagnosis must not create or modify any files."""
    _write_skill(isolated_home, "claude", "s", update_date="2000-01-01")
    before = set(p for p in isolated_home.rglob("*") if p.is_file())
    result = scan_all(project_dir=Path.cwd())
    diagnose(result)
    after = set(p for p in isolated_home.rglob("*") if p.is_file())
    assert after == before
