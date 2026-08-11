"""Tests for the Cursor provider and --format cursor support."""

import json
import tempfile
import unittest
from pathlib import Path

from click.testing import CliRunner

from ai_adapter.cli import main
from ai_adapter.config import init
from ai_adapter.models import MCPServer
from ai_adapter.providers.cursor import (
    deploy_skills,
    export_mcp,
    merge_into_cursor_mcp_json,
    resolve_mcp_output_path,
    resolve_rules_dir,
)

# ── Test fixture servers ────────────────────────────────────────────────

SERVER_GITHUB = MCPServer(
    name="github",
    command="npx",
    args=["@modelcontextprotocol/server-github"],
    env_keys=["GITHUB_TOKEN"],
    enabled=True,
)

SERVER_PLAYWRIGHT = MCPServer(
    name="playwright",
    command="npx",
    args=["@playwright/mcp@latest"],
    env_keys=[],
    enabled=True,
)

SERVER_NO_ARGS = MCPServer(
    name="no-args",
    command="/usr/bin/python",
    args=[],
    env_keys=["API_KEY"],
    enabled=True,
)

SERVER_DISABLED = MCPServer(
    name="legacy-db",
    command="/usr/bin/python",
    args=["server.py"],
    env_keys=["DB_URL"],
    enabled=False,
)


class TestCursorMCPExport(unittest.TestCase):
    """Unit tests for providers.cursor.export_mcp()."""

    def test_export_mcp_basic(self):
        """Enabled servers exported under mcpServers with command/args."""
        result = export_mcp([SERVER_GITHUB])
        self.assertIn("mcpServers", result)
        self.assertIn("github", result["mcpServers"])
        entry = result["mcpServers"]["github"]
        self.assertEqual(entry["command"], "npx")
        self.assertEqual(entry["args"], ["@modelcontextprotocol/server-github"])

    def test_export_mcp_disabled_excluded(self):
        """Disabled servers are filtered out."""
        result = export_mcp([SERVER_GITHUB, SERVER_DISABLED])
        self.assertNotIn("legacy-db", result["mcpServers"])

    def test_export_mcp_env_keys(self):
        """env_keys are mapped to ${KEY} placeholders."""
        result = export_mcp([SERVER_GITHUB])
        env = result["mcpServers"]["github"]["env"]
        self.assertEqual(env["GITHUB_TOKEN"], "${GITHUB_TOKEN}")

    def test_export_mcp_empty_args_omitted(self):
        """Empty args → args key omitted."""
        result = export_mcp([SERVER_NO_ARGS])
        self.assertNotIn("args", result["mcpServers"]["no-args"])

    def test_export_mcp_only_disabled(self):
        """Only disabled servers → empty mcpServers."""
        result = export_mcp([SERVER_DISABLED])
        self.assertEqual(result["mcpServers"], {})


class TestCursorPathResolution(unittest.TestCase):
    """Unit tests for cursor path resolution helpers."""

    def test_resolve_mcp_output_path_explicit(self):
        """--path given → {path}/.cursor/mcp.json."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "proj"
            result = resolve_mcp_output_path(str(base))
            self.assertEqual(result, (base / ".cursor" / "mcp.json").resolve())

    def test_resolve_mcp_output_path_fallback(self):
        """No path → {cwd}/.cursor/mcp.json."""
        old_cwd = Path.cwd()
        with tempfile.TemporaryDirectory() as tmp:
            import os

            os.chdir(tmp)
            try:
                result = resolve_mcp_output_path(None)
                self.assertEqual(result, Path.cwd() / ".cursor" / "mcp.json")
            finally:
                os.chdir(old_cwd)

    def test_resolve_rules_dir_explicit(self):
        """project_dir given → {project_dir}/.cursor/rules."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "proj"
            result = resolve_rules_dir(str(base))
            self.assertEqual(result, base.resolve() / ".cursor" / "rules")


class TestCursorMergeMCP(unittest.TestCase):
    """Unit tests for merge_into_cursor_mcp_json()."""

    def test_merge_new_file(self):
        """No existing file → creates .cursor/mcp.json with mcpServers."""
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "mcp.json"
            data = export_mcp([SERVER_GITHUB])
            merge_into_cursor_mcp_json(output_path, data, force=True)

            self.assertTrue(output_path.exists())
            with open(output_path) as f:
                result = json.load(f)
            self.assertIn("github", result["mcpServers"])
            self.assertEqual(result["mcpServers"]["github"]["command"], "npx")

    def test_merge_preserves_unmanaged(self):
        """Existing unmanaged servers preserved; same-name overwritten; backup created."""
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "mcp.json"
            existing = {"mcpServers": {"existing-server": {"command": "legacy"}}}
            output_path.write_text(json.dumps(existing), encoding="utf-8")

            merge_into_cursor_mcp_json(output_path, export_mcp([SERVER_GITHUB]), force=True)

            with open(output_path) as f:
                result = json.load(f)
            self.assertIn("existing-server", result["mcpServers"])
            self.assertIn("github", result["mcpServers"])
            self.assertTrue(output_path.with_suffix(".json.bak").exists())


class TestCursorSkillDeploy(unittest.TestCase):
    """Unit tests for providers.cursor.deploy_skills()."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)
        self.store = self.base / "store"
        self.target = self.base / "target"
        self.rules_dir = self.target / ".cursor" / "rules"

        from ai_adapter.models import Skill

        self.skill_entry = Skill(name="database-schema", description="DB skill", tags=["database"])
        self.skill_dir = self.store / "database-schema"
        self.skill_dir.mkdir(parents=True)
        (self.skill_dir / "SKILL.md").write_text(
            "---\n"
            "name: database-schema\n"
            "description: Database schema reference\n"
            "globs: '*.sql'\n"
            "---\n"
            "# Database Schema\n"
            "Query reference.\n",
            encoding="utf-8",
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_deploy_writes_mdc(self):
        """SKILL.md is deployed as {name}.mdc under .cursor/rules/."""
        deploy_skills([self.skill_entry], self.store, force=True, project_dir=str(self.target))
        self.assertTrue((self.rules_dir / "database-schema.mdc").exists())

    def test_deploy_converts_frontmatter(self):
        """Frontmatter: description + globs are carried over."""
        deploy_skills([self.skill_entry], self.store, force=True, project_dir=str(self.target))
        content = (self.rules_dir / "database-schema.mdc").read_text(encoding="utf-8")
        self.assertIn("description: Database schema reference", content)
        self.assertIn("globs: '*.sql'", content)
        # Body preserved after frontmatter
        self.assertIn("# Database Schema", content)

    def test_deploy_preserves_existing_rules(self):
        """Non-ai-adapter rules in the target are left untouched."""
        self.rules_dir.mkdir(parents=True)
        (self.rules_dir / "existing-rule.mdc").write_text("---\ndescription: Pre-existing\n---\nKeep me\n")

        deploy_skills([self.skill_entry], self.store, force=True, project_dir=str(self.target))
        self.assertTrue((self.rules_dir / "existing-rule.mdc").exists())

    def test_deploy_skips_missing_dir(self):
        """Skill whose directory is missing is skipped with a warning."""
        from ai_adapter.models import Skill

        missing = Skill(name="missing-skill", description="", tags=[])
        deploy_skills([missing], self.store, force=True, project_dir=str(self.target))
        self.assertFalse((self.rules_dir / "missing-skill.mdc").exists())

    def test_deploy_force_overwrite(self):
        """--force overwrites a same-name .mdc."""
        self.rules_dir.mkdir(parents=True)
        (self.rules_dir / "database-schema.mdc").write_text("old content")

        deploy_skills([self.skill_entry], self.store, force=True, project_dir=str(self.target))
        content = (self.rules_dir / "database-schema.mdc").read_text(encoding="utf-8")
        self.assertIn("Database schema reference", content)
        self.assertNotEqual(content, "old content")


class TestCursorCLI(unittest.TestCase):
    """CLI integration: --format cursor on skill / mcp / agent commands."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.patch_home = Path(self.temp_dir.name)
        self.runner = CliRunner()

        import pathlib

        self._original_home = pathlib.Path.home
        pathlib.Path.home = staticmethod(lambda: self.patch_home)

        import ai_adapter.config as cfg

        cfg.AI_ADAPTER_DIR = self.patch_home / ".ai-adapter"

        init()

        # Create and register a test skill
        skill_dir = Path(self.temp_dir.name) / "test-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "---\nname: test-skill\ndescription: Test Skill\n---\n# Test Skill\n",
            encoding="utf-8",
        )
        self.runner.invoke(main, ["skill", "add", str(skill_dir)])

    def tearDown(self):
        import pathlib

        pathlib.Path.home = staticmethod(self._original_home)
        import ai_adapter.config as cfg

        cfg.AI_ADAPTER_DIR = Path.home() / ".ai-adapter"
        self.temp_dir.cleanup()

    def test_skill_get_all_cursor(self):
        """skill get-all --format cursor deploys .mdc to project .cursor/rules/."""
        project_dir = Path(self.temp_dir.name) / "proj"
        project_dir.mkdir(parents=True)

        result = self.runner.invoke(
            main,
            ["skill", "get-all", "--format", "cursor", "--project-dir", str(project_dir), "--force"],
        )
        self.assertEqual(result.exit_code, 0)
        self.assertIn("(1) deployed as Cursor rules", result.output)
        self.assertTrue((project_dir / ".cursor" / "rules" / "test-skill.mdc").exists())

    def test_mcp_get_cursor(self):
        """mcp get --format cursor writes .cursor/mcp.json."""
        self.runner.invoke(
            main,
            ["mcp", "add", "github", "--command", "npx", "--args", "@modelcontextprotocol/server-github"],
        )

        export_dir = Path(self.temp_dir.name) / "proj-mcp"
        export_dir.mkdir(parents=True)

        result = self.runner.invoke(
            main,
            ["mcp", "get", "--format", "cursor", "--path", str(export_dir), "--force"],
        )
        self.assertEqual(result.exit_code, 0)
        self.assertIn(".cursor/mcp.json", result.output)

        output_path = export_dir / ".cursor" / "mcp.json"
        self.assertTrue(output_path.exists())
        with open(output_path) as f:
            data = json.load(f)
        self.assertIn("github", data["mcpServers"])

    def test_agent_get_cursor_error(self):
        """agent get --format cursor fails with exit code 2 and a clear reason."""
        result = self.runner.invoke(main, ["agent", "get", "whatever", "--format", "cursor"])
        self.assertEqual(result.exit_code, 2)
        self.assertIn("not supported", result.output)
        self.assertIn("no native 'agent' concept", result.output)

    def test_skill_get_all_standard_regression(self):
        """Default format still deploys to .github/skills/ (backward compat)."""
        result = self.runner.invoke(main, ["skill", "get-all", "--force"])
        self.assertEqual(result.exit_code, 0)
        self.assertTrue((Path.cwd() / ".github" / "skills" / "test-skill" / "SKILL.md").exists())

    def test_mcp_get_standard_regression(self):
        """Default format still writes .mcp.json (backward compat)."""
        self.runner.invoke(
            main,
            ["mcp", "add", "github", "--command", "npx", "--args", "@modelcontextprotocol/server-github"],
        )
        result = self.runner.invoke(main, ["mcp", "get"])
        self.assertEqual(result.exit_code, 0)
        output_path = Path.cwd() / ".mcp.json"
        self.assertTrue(output_path.exists())
        output_path.unlink(missing_ok=True)
