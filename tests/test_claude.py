"""Tests for the Claude Code provider and --format claude support (design 02).

Covers:
- Path resolution (project/user scope via resolve_scope_path)
- Agent deployment (.agent.md → .md rename + tools conversion)
- Skill deployment (.claude/skills/)
- User-scope MCP export + ~/.claude.json merge (preserve keys, .bak)
- CLI: skill get-all / sub-agent get / mcp get with --format claude
- Scope validation (user scope only valid with --format claude)
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import click
from click.exceptions import Abort
from click.testing import CliRunner

from ai_adapter import config as cfg
from ai_adapter.cli import main
from ai_adapter.config import init
from ai_adapter.models import MCPServer, Skill
from ai_adapter.providers.claude import (
    claude_agent_filename,
    deploy_agent_file,
    deploy_agents,
    deploy_skills,
    export_mcp_user,
    merge_into_claude_json,
    resolve_agents_path,
    resolve_skills_path,
    resolve_user_json_path,
    validate_claude_scope,
)

# ── Fixture servers / skills ────────────────────────────────────────────

SERVER_GITHUB = MCPServer(
    name="github",
    command="npx",
    args=["@modelcontextprotocol/server-github"],
    env_keys=["GITHUB_TOKEN"],
    enabled=True,
)

SERVER_NO_ARGS = MCPServer(
    name="no-args",
    command="/usr/bin/python",
    args=[],
    env_keys=[],
    enabled=True,
)

SERVER_DISABLED = MCPServer(
    name="legacy-db",
    command="/usr/bin/python",
    args=["server.py"],
    env_keys=["DB_URL"],
    enabled=False,
)

SKILL_DB = Skill(name="db-schema", description="Schema skill")


class _ClaudeTestBase(unittest.TestCase):
    """Shared setup: isolated HOME + ai-adapter store + cwd sandbox."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.patch_home = Path(self.temp_dir.name) / "home"
        self.patch_home.mkdir(parents=True)
        self.runner = CliRunner()

        import pathlib

        self._original_home = pathlib.Path.home
        pathlib.Path.home = staticmethod(lambda: self.patch_home)
        cfg.AI_ADAPTER_DIR = self.patch_home / ".ai-adapter"
        init()

        # Project dir separate from HOME (design 02: project .claude/ vs ~/.claude/)
        self.project_dir = Path(self.temp_dir.name) / "proj"
        self.project_dir.mkdir(parents=True)

    def tearDown(self):
        import pathlib

        pathlib.Path.home = staticmethod(self._original_home)
        cfg.AI_ADAPTER_DIR = Path.home() / ".ai-adapter"
        self.temp_dir.cleanup()


# ── Path resolution ─────────────────────────────────────────────────────


class TestClaudePathResolution(_ClaudeTestBase):
    """resolve_agents_path / resolve_skills_path for both scopes."""

    def test_agents_path_project(self):
        """Project scope → <project>/.claude/agents/."""
        path = resolve_agents_path("project", self.project_dir)
        self.assertEqual(path, self.project_dir / ".claude" / "agents")

    def test_agents_path_user(self):
        """User scope → ~/.claude/agents/."""
        path = resolve_agents_path("user")
        self.assertEqual(path, self.patch_home / ".claude" / "agents")

    def test_skills_path_project(self):
        """Project scope → <project>/.claude/skills/."""
        path = resolve_skills_path("project", self.project_dir)
        self.assertEqual(path, self.project_dir / ".claude" / "skills")

    def test_skills_path_user(self):
        """User scope → ~/.claude/skills/."""
        path = resolve_skills_path("user")
        self.assertEqual(path, self.patch_home / ".claude" / "skills")

    def test_resolve_user_json_path(self):
        """User-scope MCP file is ~/.claude.json."""
        self.assertEqual(resolve_user_json_path(), self.patch_home / ".claude.json")

    def test_invalid_scope_rejected(self):
        """Unknown scope raises ValueError (delegates to resolve_scope_path)."""
        with self.assertRaises(ValueError):
            resolve_agents_path("global", self.project_dir)


# ── Agent filename + deployment ─────────────────────────────────────────


class TestClaudeAgentFilename(unittest.TestCase):
    """claude_agent_filename: .agent.md → .md, others unchanged."""

    def test_agent_md_renamed(self):
        self.assertEqual(claude_agent_filename("reviewer.agent.md"), "reviewer.md")

    def test_plain_md_unchanged(self):
        self.assertEqual(claude_agent_filename("reviewer.md"), "reviewer.md")

    def test_extensionless_unchanged(self):
        self.assertEqual(claude_agent_filename("reviewer"), "reviewer")


class TestClaudeDeployAgentFile(_ClaudeTestBase):
    """deploy_agent_file: rename, tools conversion, force/confirm."""

    def _write_agent_md(self, name: str, tools_line: str = "") -> Path:
        store = self.patch_home / ".ai-adapter" / "agents"
        store.mkdir(parents=True, exist_ok=True)
        tools_block = f"{tools_line}\n" if tools_line else ""
        f = store / f"{name}.agent.md"
        f.write_text(
            f"---\nname: {name}\ndescription: Test agent\n{tools_block}---\n# {name}\n",
            encoding="utf-8",
        )
        return f

    def test_agent_md_renamed_to_md(self):
        src = self._write_agent_md("reviewer")
        dest_dir = self.project_dir / ".claude" / "agents"
        dest = deploy_agent_file(src, dest_dir)
        self.assertEqual(dest.name, "reviewer.md")
        self.assertTrue(dest.exists())
        self.assertFalse((dest_dir / "reviewer.agent.md").exists())

    def test_tools_array_converted_to_object(self):
        """Array-format tools become object format in the deployed .md."""
        src = self._write_agent_md("reviewer", tools_line="tools: [read, grep]")
        dest = deploy_agent_file(src, self.project_dir / ".claude" / "agents")
        content = dest.read_text(encoding="utf-8")
        self.assertIn("tools:\n  read: true\n  grep: true", content)

    def test_store_file_not_modified(self):
        """Conversion happens on the copy — the store keeps the original."""
        src = self._write_agent_md("reviewer", tools_line="tools: [read]")
        deploy_agent_file(src, self.project_dir / ".claude" / "agents")
        self.assertIn("tools: [read]", src.read_text(encoding="utf-8"))

    def test_no_staging_left_behind(self):
        """The temp .agent.md staging file is always cleaned up."""
        src = self._write_agent_md("reviewer", tools_line="tools: [read]")
        dest_dir = self.project_dir / ".claude" / "agents"
        deploy_agent_file(src, dest_dir)
        leftovers = [f.name for f in dest_dir.iterdir() if "staging" in f.name]
        self.assertEqual(leftovers, [])

    def test_plain_md_copied_as_is(self):
        store = self.patch_home / ".ai-adapter" / "agents"
        store.mkdir(parents=True, exist_ok=True)
        src = store / "helper.md"
        src.write_text("# Helper\n", encoding="utf-8")
        dest = deploy_agent_file(src, self.project_dir / ".claude" / "agents")
        self.assertEqual(dest.name, "helper.md")
        self.assertEqual(dest.read_text(encoding="utf-8"), "# Helper\n")

    def test_plain_md_fix_converts_array_tools(self):
        """W1 (QA): fix=True converts plain .md array tools via staging."""
        store = self.patch_home / ".ai-adapter" / "agents"
        store.mkdir(parents=True, exist_ok=True)
        src = store / "helper.md"
        src.write_text(
            "---\nname: helper\ndescription: Helper\ntools: [read, grep]\n---\n# Helper\n",
            encoding="utf-8",
        )
        dest = deploy_agent_file(src, self.project_dir / ".claude" / "agents", fix=True)
        content = dest.read_text(encoding="utf-8")
        self.assertIn("tools:\n  read: true\n  grep: true", content)
        # Store keeps the original.
        self.assertIn("tools: [read, grep]", src.read_text())
        # No staging leftovers.
        leftovers = [f.name for f in (self.project_dir / ".claude" / "agents").iterdir() if "staging" in f.name]
        self.assertEqual(leftovers, [])

    def test_plain_md_without_fix_keeps_array(self):
        """fix=False (default) leaves plain .md array tools untouched."""
        store = self.patch_home / ".ai-adapter" / "agents"
        store.mkdir(parents=True, exist_ok=True)
        src = store / "helper.md"
        src.write_text(
            "---\nname: helper\ndescription: Helper\ntools: [read]\n---\n# Helper\n",
            encoding="utf-8",
        )
        dest = deploy_agent_file(src, self.project_dir / ".claude" / "agents")
        self.assertIn("tools: [read]", dest.read_text())

    def test_existing_prompts_without_force(self):
        """Without --force an existing destination aborts and stays untouched."""
        src = self._write_agent_md("reviewer")
        dest_dir = self.project_dir / ".claude" / "agents"
        dest_dir.mkdir(parents=True)
        (dest_dir / "reviewer.md").write_text("old", encoding="utf-8")

        import click as _click

        old_confirm = _click.confirm

        def _deny(*_a, **_k):
            raise Abort()

        _click.confirm = _deny
        try:
            with self.assertRaises(Abort):
                deploy_agent_file(src, dest_dir, force=False)
        finally:
            _click.confirm = old_confirm
        self.assertEqual((dest_dir / "reviewer.md").read_text(encoding="utf-8"), "old")

    def test_force_overwrites_without_prompt(self):
        src = self._write_agent_md("reviewer")
        dest_dir = self.project_dir / ".claude" / "agents"
        dest_dir.mkdir(parents=True)
        (dest_dir / "reviewer.md").write_text("old", encoding="utf-8")
        dest = deploy_agent_file(src, dest_dir, force=True)
        self.assertIn("# reviewer", dest.read_text(encoding="utf-8"))


# ── deploy_agents (batch) ───────────────────────────────────────────────


class TestClaudeDeployAgents(_ClaudeTestBase):
    """deploy_agents: batch copy, skip missing, gitignore policy."""

    def _register_agent(self, name: str) -> None:
        """Write an .agent.md source outside the store, then register it."""
        src_dir = Path(self.temp_dir.name) / "agent-src"
        src_dir.mkdir(parents=True, exist_ok=True)
        src = src_dir / f"{name}.agent.md"
        src.write_text(
            f"---\nname: {name}\ndescription: d\n---\n# {name}\n",
            encoding="utf-8",
        )
        result = self.runner.invoke(main, ["sub-agent", "add", str(src)])
        self.assertEqual(result.exit_code, 0, result.output)

    def test_batch_deploy_renames_all(self):
        self._register_agent("reviewer")
        self._register_agent("implementer")
        config = cfg.load_config()
        store = self.patch_home / ".ai-adapter" / "agents"
        deploy_agents(config.agents, store, "project", self.project_dir)
        agents_dir = self.project_dir / ".claude" / "agents"
        self.assertTrue((agents_dir / "reviewer.md").exists())
        self.assertTrue((agents_dir / "implementer.md").exists())

    def test_missing_file_skipped_with_notice(self):
        """A registered agent without a store file is skipped, not fatal."""
        from ai_adapter.models import Agent

        store = self.patch_home / ".ai-adapter" / "agents"
        store.mkdir(parents=True, exist_ok=True)
        deploy_agents([Agent(name="ghost")], store, "project", self.project_dir)
        agents_dir = self.project_dir / ".claude" / "agents"
        self.assertEqual(list(agents_dir.iterdir()), [])

    def test_user_scope_not_gitignored(self):
        """User-scope deploys never touch any .gitignore."""
        self._register_agent("reviewer")
        config = cfg.load_config()
        store = self.patch_home / ".ai-adapter" / "agents"
        deploy_agents(config.agents, store, "user")
        self.assertTrue((self.patch_home / ".claude" / "agents" / "reviewer.md").exists())
        self.assertFalse((self.patch_home / ".gitignore").exists())

    def test_project_scope_gitignored(self):
        """Project-scope deploys are added to .gitignore (when a repo exists)."""
        git_dir = self.project_dir / ".git"
        git_dir.mkdir(parents=True)
        self._register_agent("reviewer")
        config = cfg.load_config()
        store = self.patch_home / ".ai-adapter" / "agents"
        deploy_agents(config.agents, store, "project", self.project_dir)
        gitignore = self.project_dir / ".gitignore"
        self.assertTrue(gitignore.exists())
        self.assertIn(".claude/agents", gitignore.read_text(encoding="utf-8"))


# ── deploy_skills ───────────────────────────────────────────────────────


class TestClaudeDeploySkills(_ClaudeTestBase):
    """deploy_skills: directory copy, frontmatter preserved, force."""

    def _write_skill_store(self, name: str, body: str = "# Skill\n") -> Path:
        store = self.patch_home / ".ai-adapter" / "skills" / name
        store.mkdir(parents=True, exist_ok=True)
        (store / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: d\ntags: [t1]\n---\n{body}",
            encoding="utf-8",
        )
        return store.parent

    def test_skill_directory_copied(self):
        store = self._write_skill_store("db-schema")
        deploy_skills([SKILL_DB], store, "project", self.project_dir)
        skill_dir = self.project_dir / ".claude" / "skills" / "db-schema"
        self.assertTrue((skill_dir / "SKILL.md").exists())

    def test_frontmatter_preserved(self):
        store = self._write_skill_store("db-schema")
        deploy_skills([SKILL_DB], store, "project", self.project_dir)
        content = (self.project_dir / ".claude" / "skills" / "db-schema" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("name: db-schema", content)
        self.assertIn("tags: [t1]", content)

    def test_user_scope_target(self):
        store = self._write_skill_store("db-schema")
        deploy_skills([SKILL_DB], store, "user")
        self.assertTrue((self.patch_home / ".claude" / "skills" / "db-schema" / "SKILL.md").exists())

    def test_missing_skill_skipped(self):
        store = self.patch_home / ".ai-adapter" / "skills"
        store.mkdir(parents=True, exist_ok=True)
        deploy_skills([SKILL_DB], store, "project", self.project_dir)
        self.assertFalse((self.project_dir / ".claude" / "skills" / "db-schema").exists())

    def test_force_overwrites_existing(self):
        store = self._write_skill_store("db-schema")
        dest = self.project_dir / ".claude" / "skills" / "db-schema"
        dest.mkdir(parents=True)
        (dest / "SKILL.md").write_text("old", encoding="utf-8")
        deploy_skills([SKILL_DB], store, "project", self.project_dir, force=True)
        self.assertIn("name: db-schema", (dest / "SKILL.md").read_text(encoding="utf-8"))

    def test_existing_prompts_without_force(self):
        import click as _click

        store = self._write_skill_store("db-schema")
        dest = self.project_dir / ".claude" / "skills" / "db-schema"
        dest.mkdir(parents=True)
        (dest / "SKILL.md").write_text("old", encoding="utf-8")

        old_confirm = _click.confirm

        def _deny(*_a, **_k):
            raise Abort()

        _click.confirm = _deny
        try:
            with self.assertRaises(Abort):
                deploy_skills([SKILL_DB], store, "project", self.project_dir, force=False)
        finally:
            _click.confirm = old_confirm
        self.assertEqual((dest / "SKILL.md").read_text(encoding="utf-8"), "old")


# ── MCP export + merge ──────────────────────────────────────────────────


class TestClaudeMCPExport(unittest.TestCase):
    """export_mcp_user: mcpServers dict with ${ENV} placeholders."""

    def test_export_basic(self):
        result = export_mcp_user([SERVER_GITHUB])
        self.assertIn("mcpServers", result)
        entry = result["mcpServers"]["github"]
        self.assertEqual(entry["command"], "npx")
        self.assertEqual(entry["args"], ["@modelcontextprotocol/server-github"])
        self.assertEqual(entry["env"]["GITHUB_TOKEN"], "${GITHUB_TOKEN}")

    def test_disabled_excluded(self):
        result = export_mcp_user([SERVER_GITHUB, SERVER_DISABLED])
        self.assertNotIn("legacy-db", result["mcpServers"])

    def test_empty_args_omitted(self):
        result = export_mcp_user([SERVER_NO_ARGS])
        self.assertNotIn("args", result["mcpServers"]["no-args"])
        self.assertNotIn("env", result["mcpServers"]["no-args"])

    def test_empty_list(self):
        self.assertEqual(export_mcp_user([]), {"mcpServers": {}})


class TestClaudeMergeIntoJson(_ClaudeTestBase):
    """merge_into_claude_json: preserve keys, .bak, managed overwrite."""

    def test_creates_minimal_file_when_missing(self):
        """Missing ~/.claude.json → created with mcpServers only."""
        path = self.patch_home / ".claude.json"
        self.assertFalse(path.exists())
        merge_into_claude_json(path, export_mcp_user([SERVER_GITHUB]), force=True)
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(set(data.keys()), {"mcpServers"})
        self.assertIn("github", data["mcpServers"])

    def test_preserves_unmanaged_keys(self):
        """projects etc. (Claude Code's own data) survive the merge."""
        path = self.patch_home / ".claude.json"
        original = {
            "projects": {"/path/to/repo": {"allowedTools": ["Read"]}},
            "mcpServers": {"existing-server": {"command": "node", "args": ["server.js"]}},
        }
        path.write_text(json.dumps(original), encoding="utf-8")
        merge_into_claude_json(path, export_mcp_user([SERVER_GITHUB]), force=True)
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(data["projects"], original["projects"])
        self.assertIn("existing-server", data["mcpServers"])
        self.assertIn("github", data["mcpServers"])

    def test_managed_name_overwrites(self):
        """ai-adapter managed names are overwritten, others preserved."""
        path = self.patch_home / ".claude.json"
        original = {
            "mcpServers": {
                "github": {"command": "old-cmd"},
                "other": {"command": "keep-me"},
            }
        }
        path.write_text(json.dumps(original), encoding="utf-8")
        merge_into_claude_json(path, export_mcp_user([SERVER_GITHUB]), force=True)
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(data["mcpServers"]["github"]["command"], "npx")
        self.assertEqual(data["mcpServers"]["other"]["command"], "keep-me")

    def test_bak_backup_taken(self):
        path = self.patch_home / ".claude.json"
        path.write_text('{"mcpServers": {}}', encoding="utf-8")
        merge_into_claude_json(path, export_mcp_user([SERVER_GITHUB]), force=True)
        bak = self.patch_home / ".claude.json.bak"
        self.assertTrue(bak.exists())
        self.assertEqual(json.loads(bak.read_text(encoding="utf-8")), {"mcpServers": {}})

    def test_no_bak_for_new_file(self):
        path = self.patch_home / ".claude.json"
        merge_into_claude_json(path, export_mcp_user([SERVER_GITHUB]), force=True)
        self.assertFalse((self.patch_home / ".claude.json.bak").exists())

    def test_force_skips_prompt(self):
        path = self.patch_home / ".claude.json"
        path.write_text('{"mcpServers": {}}', encoding="utf-8")
        merge_into_claude_json(path, export_mcp_user([SERVER_GITHUB]), force=True)
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertIn("github", data["mcpServers"])

    def test_existing_prompts_without_force(self):
        import click as _click

        path = self.patch_home / ".claude.json"
        path.write_text('{"mcpServers": {}}', encoding="utf-8")

        old_confirm = _click.confirm

        def _deny(*_a, **_k):
            raise Abort()

        _click.confirm = _deny
        try:
            with self.assertRaises(Abort):
                merge_into_claude_json(path, export_mcp_user([SERVER_GITHUB]), force=False)
        finally:
            _click.confirm = old_confirm
        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"mcpServers": {}})

    def test_corrupt_json_aborts_merge(self):
        """Unreadable/corrupt existing file → merge aborts (protects Claude user data)."""
        path = self.patch_home / ".claude.json"
        path.write_text("{not json", encoding="utf-8")
        with self.assertRaises(click.ClickException) as ctx:
            merge_into_claude_json(path, export_mcp_user([SERVER_GITHUB]), force=True)
        self.assertIn("not valid JSON", str(ctx.exception))
        # File must NOT be overwritten.
        self.assertEqual(path.read_text(encoding="utf-8"), "{not json")

    def test_non_dict_top_level_aborts_merge(self):
        """Top-level JSON that is not an object → merge aborts."""
        path = self.patch_home / ".claude.json"
        path.write_text('["not", "a", "dict"]', encoding="utf-8")
        with self.assertRaises(click.ClickException) as ctx:
            merge_into_claude_json(path, export_mcp_user([SERVER_GITHUB]), force=True)
        self.assertIn("not an object", str(ctx.exception))
        self.assertEqual(path.read_text(encoding="utf-8"), '["not", "a", "dict"]')

    def test_non_dict_mcp_servers_treated_as_empty(self):
        """mcpServers: null (or a list) does not crash the merge."""
        path = self.patch_home / ".claude.json"
        path.write_text('{"projects": {}, "mcpServers": null}', encoding="utf-8")
        merge_into_claude_json(path, export_mcp_user([SERVER_GITHUB]), force=True)
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(data["projects"], {})
        self.assertIn("github", data["mcpServers"])


# ── Scope validation ────────────────────────────────────────────────────


class TestValidateClaudeScope(_ClaudeTestBase):
    """validate_claude_scope: user scope requires --format claude."""

    def test_claude_user_ok(self):
        validate_claude_scope("claude", "user")  # no raise

    def test_claude_project_ok(self):
        validate_claude_scope("claude", "project")

    def test_standard_user_rejected(self):
        with self.assertRaises(Exception) as ctx:
            validate_claude_scope("standard", "user")
        self.assertIn("--scope user is only supported with --format claude", str(ctx.exception))

    def test_openclaw_user_rejected(self):
        with self.assertRaises(Exception):
            validate_claude_scope("openclaw", "user")

    def test_ignored_option_warns(self):
        """A user-scope deploy warns that --project-dir no longer applies."""
        import io

        import click as _click

        captured = io.StringIO()
        old_echo = _click.echo

        def _capture(message=None, err=False, **k):
            if err:
                captured.write(str(message))
            else:
                old_echo(message, err=err, **k)

        _click.echo = _capture
        try:
            validate_claude_scope("claude", "user", ignored_option="--project-dir")
        finally:
            _click.echo = old_echo
        self.assertIn("--project-dir is ignored with --scope user", captured.getvalue())


# ── CLI integration ─────────────────────────────────────────────────────


class TestSkillGetAllClaudeCLI(_ClaudeTestBase):
    """skill get-all --format claude."""

    def _add_skill(self, name: str) -> None:
        d = Path(self.temp_dir.name) / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: Test skill\n---\n# {name}\n",
            encoding="utf-8",
        )
        self.runner.invoke(main, ["skill", "add", str(d)])

    def test_project_scope_default(self):
        """--format claude (default scope=project) → <project>/.claude/skills/."""
        self._add_skill("db-schema")
        result = self.runner.invoke(
            main,
            ["skill", "get-all", "--format", "claude", "--project-dir", str(self.project_dir)],
        )
        self.assertEqual(result.exit_code, 0)
        self.assertTrue((self.project_dir / ".claude" / "skills" / "db-schema" / "SKILL.md").exists())
        self.assertFalse((self.project_dir / ".github" / "skills" / "db-schema").exists())

    def test_user_scope(self):
        self._add_skill("db-schema")
        result = self.runner.invoke(main, ["skill", "get-all", "--format", "claude", "--scope", "user"])
        self.assertEqual(result.exit_code, 0)
        self.assertTrue((self.patch_home / ".claude" / "skills" / "db-schema" / "SKILL.md").exists())

    def test_env_filter_works_with_claude(self):
        """AC4: --env filtering still applies under --format claude."""
        self._add_skill("env-a")
        self._add_skill("env-b")
        config = cfg.load_config()
        for s in config.skills:
            s.env = "prod" if s.name == "env-a" else "staging"
        cfg.save_config(config)

        result = self.runner.invoke(
            main,
            [
                "skill",
                "get-all",
                "--format",
                "claude",
                "--env",
                "prod",
                "--project-dir",
                str(self.project_dir),
            ],
        )
        self.assertEqual(result.exit_code, 0)
        skills_dir = self.project_dir / ".claude" / "skills"
        self.assertTrue((skills_dir / "env-a").exists())
        self.assertFalse((skills_dir / "env-b").exists())

    def test_standard_still_works(self):
        """AC1: --format standard keeps deploying to .github/skills/."""
        self._add_skill("db-schema")
        result = self.runner.invoke(
            main,
            ["skill", "get-all", "--project-dir", str(self.project_dir)],
        )
        self.assertEqual(result.exit_code, 0)
        self.assertTrue((self.project_dir / ".github" / "skills" / "db-schema" / "SKILL.md").exists())

    def test_scope_user_rejected_for_standard(self):
        self._add_skill("db-schema")
        result = self.runner.invoke(
            main,
            ["skill", "get-all", "--format", "standard", "--scope", "user"],
        )
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("--scope user is only supported with --format claude", result.output)

    def test_existing_prompts_without_force(self):
        self._add_skill("db-schema")
        dest = self.project_dir / ".claude" / "skills" / "db-schema"
        dest.mkdir(parents=True)
        (dest / "SKILL.md").write_text("old", encoding="utf-8")
        result = self.runner.invoke(
            main,
            ["skill", "get-all", "--format", "claude", "--project-dir", str(self.project_dir)],
            input="n\n",
        )
        self.assertNotEqual(result.exit_code, 0)
        self.assertEqual((dest / "SKILL.md").read_text(encoding="utf-8"), "old")

    def test_force_overwrites(self):
        self._add_skill("db-schema")
        dest = self.project_dir / ".claude" / "skills" / "db-schema"
        dest.mkdir(parents=True)
        (dest / "SKILL.md").write_text("old", encoding="utf-8")
        result = self.runner.invoke(
            main,
            [
                "skill",
                "get-all",
                "--format",
                "claude",
                "--force",
                "--project-dir",
                str(self.project_dir),
            ],
        )
        self.assertEqual(result.exit_code, 0)
        self.assertIn("name: db-schema", (dest / "SKILL.md").read_text(encoding="utf-8"))


class TestSubAgentGetClaudeCLI(_ClaudeTestBase):
    """sub-agent get/get-all --format claude."""

    def _add_agent(self, filename: str, content: str) -> str:
        f = Path(self.temp_dir.name) / filename
        f.write_text(content, encoding="utf-8")
        result = self.runner.invoke(main, ["sub-agent", "add", str(f)])
        self.assertEqual(result.exit_code, 0, result.output)
        # Return the registered name (from frontmatter when present)
        for line in content.splitlines():
            if line.startswith("name:"):
                return line.split(":", 1)[1].strip()
        return filename.removesuffix(".md")

    def test_get_claude_renames_agent_md(self):
        """AC1: .agent.md → .md deployed to .claude/agents/."""
        name = self._add_agent(
            "reviewer.agent.md",
            "---\nname: reviewer\ndescription: Code review specialist\n---\n# Reviewer\n",
        )
        result = self.runner.invoke(
            main,
            [
                "sub-agent",
                "get",
                name,
                "--format",
                "claude",
                "--project-dir",
                str(self.project_dir),
            ],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        dest = self.project_dir / ".claude" / "agents" / "reviewer.md"
        self.assertTrue(dest.exists())
        self.assertFalse((self.project_dir / ".claude" / "agents" / "reviewer.agent.md").exists())

    def test_get_claude_converts_tools(self):
        """AC2: tools conversion reused via agent_format.convert_agent_file."""
        name = self._add_agent(
            "reviewer.agent.md",
            "---\nname: reviewer\ndescription: d\ntools: [read, grep]\n---\n# R\n",
        )
        result = self.runner.invoke(
            main,
            [
                "sub-agent",
                "get",
                name,
                "--format",
                "claude",
                "--project-dir",
                str(self.project_dir),
            ],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        content = (self.project_dir / ".claude" / "agents" / "reviewer.md").read_text(encoding="utf-8")
        self.assertIn("tools:\n  read: true\n  grep: true", content)

    def test_get_claude_user_scope(self):
        """AC3: --scope user → ~/.claude/agents/."""
        name = self._add_agent(
            "reviewer.agent.md",
            "---\nname: reviewer\ndescription: d\n---\n# R\n",
        )
        result = self.runner.invoke(
            main,
            ["sub-agent", "get", name, "--format", "claude", "--scope", "user"],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertTrue((self.patch_home / ".claude" / "agents" / "reviewer.md").exists())

    def test_get_all_claude(self):
        self._add_agent(
            "reviewer.agent.md",
            "---\nname: reviewer\ndescription: d\n---\n# R\n",
        )
        self._add_agent(
            "impl.agent.md",
            "---\nname: impl\ndescription: d\n---\n# I\n",
        )
        result = self.runner.invoke(
            main,
            [
                "sub-agent",
                "get-all",
                "--format",
                "claude",
                "--project-dir",
                str(self.project_dir),
            ],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        agents_dir = self.project_dir / ".claude" / "agents"
        self.assertTrue((agents_dir / "reviewer.md").exists())
        self.assertTrue((agents_dir / "impl.md").exists())

    def test_get_standard_still_works(self):
        """Backward compat: default format keeps .github/agents/ + .agent.md name."""
        name = self._add_agent(
            "reviewer.agent.md",
            "---\nname: reviewer\ndescription: d\n---\n# R\n",
        )
        result = self.runner.invoke(
            main,
            ["sub-agent", "get", name, "--project-dir", str(self.project_dir)],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertTrue((self.project_dir / ".github" / "agents" / "reviewer.agent.md").exists())

    def test_scope_user_rejected_for_standard(self):
        name = self._add_agent(
            "reviewer.agent.md",
            "---\nname: reviewer\ndescription: d\n---\n# R\n",
        )
        result = self.runner.invoke(
            main,
            ["sub-agent", "get", name, "--format", "standard", "--scope", "user"],
        )
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("--scope user is only supported with --format claude", result.output)


class TestMcpGetClaudeCLI(_ClaudeTestBase):
    """mcp get --format claude --scope user|project."""

    def _add_server(self, name: str, command: str = "npx", args=(), env_keys=()) -> None:
        cmd = ["mcp", "add", name, "--command", command]
        for a in args:
            cmd += ["--args", a]
        for e in env_keys:
            cmd += ["--env-key", e]
        self.runner.invoke(main, cmd)

    def test_user_scope_merges_claude_json(self):
        """AC: --scope user merges ~/.claude.json mcpServers."""
        self._add_server("github", "npx", ["@modelcontextprotocol/server-github"], ["GITHUB_TOKEN"])
        result = self.runner.invoke(main, ["mcp", "get", "--format", "claude", "--scope", "user"])
        self.assertEqual(result.exit_code, 0, result.output)
        data = json.loads((self.patch_home / ".claude.json").read_text(encoding="utf-8"))
        self.assertIn("github", data["mcpServers"])
        self.assertEqual(data["mcpServers"]["github"]["env"]["GITHUB_TOKEN"], "${GITHUB_TOKEN}")

    def test_user_scope_preserves_projects_key(self):
        """AC2: non-managed keys (projects etc.) are never modified."""
        claude_json = self.patch_home / ".claude.json"
        original = {"projects": {"/x": {"y": 1}}, "mcpServers": {}}
        claude_json.write_text(json.dumps(original), encoding="utf-8")
        self._add_server("github", "npx", ["@modelcontextprotocol/server-github"])
        result = self.runner.invoke(
            main,
            ["mcp", "get", "--format", "claude", "--scope", "user", "--force"],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        data = json.loads(claude_json.read_text(encoding="utf-8"))
        self.assertEqual(data["projects"], {"/x": {"y": 1}})
        self.assertIn("github", data["mcpServers"])

    def test_user_scope_creates_missing_file(self):
        """AC: missing ~/.claude.json → created from {"mcpServers": {}}."""
        self.assertFalse((self.patch_home / ".claude.json").exists())
        self._add_server("github", "npx", ["@modelcontextprotocol/server-github"])
        result = self.runner.invoke(
            main,
            ["mcp", "get", "--format", "claude", "--scope", "user"],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertTrue((self.patch_home / ".claude.json").exists())

    def test_user_scope_takes_bak(self):
        claude_json = self.patch_home / ".claude.json"
        claude_json.write_text('{"mcpServers": {}}', encoding="utf-8")
        self._add_server("github", "npx")
        result = self.runner.invoke(
            main,
            ["mcp", "get", "--format", "claude", "--scope", "user", "--force"],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertTrue((self.patch_home / ".claude.json.bak").exists())

    def test_project_scope_writes_mcp_json(self):
        """AC5: --format claude --scope project → .mcp.json (same as standard)."""
        self._add_server("github", "npx", ["@modelcontextprotocol/server-github"])
        result = self.runner.invoke(
            main,
            [
                "mcp",
                "get",
                "--format",
                "claude",
                "--scope",
                "project",
                "--path",
                str(self.project_dir),
            ],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        data = json.loads((self.project_dir / ".mcp.json").read_text(encoding="utf-8"))
        self.assertIn("github", data["mcpServers"])
        # User file untouched by project scope
        self.assertFalse((self.patch_home / ".claude.json").exists())

    def test_default_claude_format_is_project(self):
        """--format claude without --scope behaves like standard (.mcp.json)."""
        self._add_server("github", "npx")
        result = self.runner.invoke(
            main,
            ["mcp", "get", "--format", "claude", "--path", str(self.project_dir)],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertTrue((self.project_dir / ".mcp.json").exists())

    def test_scope_user_rejected_for_standard(self):
        self._add_server("github", "npx")
        result = self.runner.invoke(
            main,
            ["mcp", "get", "--format", "standard", "--scope", "user"],
        )
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("--scope user is only supported with --format claude", result.output)

    def test_scope_user_rejected_for_openclaw(self):
        self._add_server("github", "npx")
        result = self.runner.invoke(
            main,
            ["mcp", "get", "--format", "openclaw", "--scope", "user"],
        )
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("--scope user is only supported with --format claude", result.output)

    def test_force_skips_prompt_on_existing(self):
        claude_json = self.patch_home / ".claude.json"
        claude_json.write_text('{"mcpServers": {}}', encoding="utf-8")
        self._add_server("github", "npx")
        result = self.runner.invoke(
            main,
            ["mcp", "get", "--format", "claude", "--scope", "user", "--force"],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        data = json.loads(claude_json.read_text(encoding="utf-8"))
        self.assertIn("github", data["mcpServers"])

    def test_prompt_aborts_on_existing_without_force(self):
        claude_json = self.patch_home / ".claude.json"
        claude_json.write_text('{"mcpServers": {}}', encoding="utf-8")
        self._add_server("github", "npx")
        result = self.runner.invoke(
            main,
            ["mcp", "get", "--format", "claude", "--scope", "user"],
            input="n\n",
        )
        self.assertNotEqual(result.exit_code, 0)
        self.assertEqual(json.loads(claude_json.read_text(encoding="utf-8")), {"mcpServers": {}})


# ── Doctor: ~/.claude.json mcpServers validation ────────────────────────


class TestDoctorClaudeUserJson(_ClaudeTestBase):
    """doctor validates the mcpServers subtree of ~/.claude.json (read-only)."""

    def _issues(self):
        from ai_adapter.doctor import build_doctor_report

        report = build_doctor_report(project_dir=self.project_dir, home=self.patch_home)
        return [i for i in report.issues if ".claude.json" in (i.path or "")]

    def test_missing_file_no_issue(self):
        self.assertEqual(self._issues(), [])

    def test_invalid_json_warns(self):
        (self.patch_home / ".claude.json").write_text("{not json", encoding="utf-8")
        issues = self._issues()
        self.assertEqual(len(issues), 1)
        self.assertIn("not valid JSON", issues[0].message)
        self.assertEqual(issues[0].severity, "warning")

    def test_valid_config_no_issue(self):
        (self.patch_home / ".claude.json").write_text(
            json.dumps({"projects": {}, "mcpServers": {"github": {"command": "npx"}}}),
            encoding="utf-8",
        )
        self.assertEqual(self._issues(), [])

    def test_mcp_servers_not_object_warns(self):
        (self.patch_home / ".claude.json").write_text(
            json.dumps({"mcpServers": ["oops"]}),
            encoding="utf-8",
        )
        issues = self._issues()
        self.assertEqual(len(issues), 1)
        self.assertIn("mcpServers must be an object", issues[0].message)

    def test_server_entry_missing_command_warns(self):
        (self.patch_home / ".claude.json").write_text(
            json.dumps({"mcpServers": {"broken": {"args": []}}}),
            encoding="utf-8",
        )
        issues = self._issues()
        self.assertEqual(len(issues), 1)
        self.assertIn("mcpServers.broken", issues[0].message)

    def test_no_mcp_servers_key_no_issue(self):
        (self.patch_home / ".claude.json").write_text(
            json.dumps({"projects": {}}),
            encoding="utf-8",
        )
        self.assertEqual(self._issues(), [])


if __name__ == "__main__":
    unittest.main()
