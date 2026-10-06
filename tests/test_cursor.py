"""Tests for the Cursor provider and --format cursor support."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import click
from click.testing import CliRunner

from ai_adapter.cli import main
from ai_adapter.config import init
from ai_adapter.models import MCPServer, Skill
from ai_adapter.providers.cursor import (
    CURSORRULES_FILENAME,
    deploy_skills,
    deploy_skills_plugin,
    export_cursorrules,
    export_mcp,
    generate_plugin_manifest,
    merge_into_cursor_mcp_json,
    resolve_mcp_output_path,
    resolve_plugin_root,
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


class TestCursorrulesExport(unittest.TestCase):
    """Unit tests for providers.cursor.export_cursorrules() (design 07)."""

    def test_single_instruction_strips_frontmatter(self):
        """A single instruction is emitted as plain text, no separator."""
        out = export_cursorrules([("AGENTS", "---\nname: AGENTS\n---\n# Root\n")])
        self.assertEqual(out, "# Root")

    def test_single_instruction_no_frontmatter_passthrough(self):
        """Content without frontmatter is returned unchanged (stripped)."""
        out = export_cursorrules([("AGENTS", "# Root agent\n\nRules here.\n")])
        self.assertEqual(out, "# Root agent\n\nRules here.")

    def test_multiple_instructions_with_separators(self):
        """Multiple instructions are joined with # --- <name> --- comments."""
        out = export_cursorrules([("AGENTS", "# A\n"), ("STYLE", "# S\n")])
        self.assertEqual(out, "# --- AGENTS ---\n# A\n\n# --- STYLE ---\n# S")

    def test_empty_content(self):
        """Empty content yields an empty block."""
        self.assertEqual(export_cursorrules([("AGENTS", "")]), "")

    def test_empty_list(self):
        """No instructions yields an empty string."""
        self.assertEqual(export_cursorrules([]), "")


class TestCursorPluginDeploy(unittest.TestCase):
    """Unit tests for providers.cursor.deploy_skills_plugin() (design 07)."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.home = Path(self.temp_dir.name) / "home"
        self.home.mkdir()

        import pathlib

        self._original_home = pathlib.Path.home
        pathlib.Path.home = staticmethod(lambda: self.home)

        self.store = Path(self.temp_dir.name) / "store"
        skill_dir = self.store / "db-schema"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("---\nname: db-schema\n---\n# DB\n")
        (skill_dir / "scripts").mkdir()
        (skill_dir / "scripts" / "query.sql").write_text("SELECT 1;\n")

        self.project = Path(self.temp_dir.name) / "my-project"
        self.project.mkdir()

    def tearDown(self):
        import pathlib

        pathlib.Path.home = staticmethod(self._original_home)
        self.temp_dir.cleanup()

    def _entry(self, name="db-schema"):
        return Skill(name=name)

    def test_deploy_writes_manifest_and_skill(self):
        """plugin.json + skills/<name>/SKILL.md are generated."""
        deploy_skills_plugin([self._entry()], self.store, force=True, project_dir=str(self.project))
        root = self.home / ".cursor" / "plugins" / "local" / "my-project"
        manifest = root / ".cursor-plugin" / "plugin.json"
        self.assertTrue(manifest.exists())
        data = json.loads(manifest.read_text())
        self.assertEqual(data["name"], "my-project")
        self.assertTrue((root / "skills" / "db-schema" / "SKILL.md").exists())

    def test_deploy_copies_auxiliary_files(self):
        """scripts/ and other auxiliary files are copied verbatim."""
        deploy_skills_plugin([self._entry()], self.store, force=True, project_dir=str(self.project))
        root = self.home / ".cursor" / "plugins" / "local" / "my-project"
        self.assertTrue((root / "skills" / "db-schema" / "scripts" / "query.sql").exists())

    def test_deploy_frontmatter_preserved(self):
        """SKILL.md keeps its frontmatter (Cursor reads it directly)."""
        deploy_skills_plugin([self._entry()], self.store, force=True, project_dir=str(self.project))
        skill_md = self.home / ".cursor" / "plugins" / "local" / "my-project" / "skills" / "db-schema" / "SKILL.md"
        self.assertTrue(skill_md.read_text().startswith("---"))

    def test_deploy_skips_missing_skill_but_writes_manifest(self):
        """Manifest is always written even when the skill dir is missing."""
        deploy_skills_plugin([self._entry("ghost")], self.store, force=True, project_dir=str(self.project))
        root = self.home / ".cursor" / "plugins" / "local" / "my-project"
        self.assertTrue((root / ".cursor-plugin" / "plugin.json").exists())
        self.assertFalse((root / "skills" / "ghost").exists())

    def test_deploy_prompts_without_force(self):
        """An existing plugin package prompts unless --force is given."""
        deploy_skills_plugin([self._entry()], self.store, force=True, project_dir=str(self.project))
        with mock.patch("ai_adapter.providers.cursor.click.confirm", side_effect=click.exceptions.Abort):
            with self.assertRaises(click.exceptions.Abort):
                deploy_skills_plugin([self._entry()], self.store, force=False, project_dir=str(self.project))

    def test_deploy_force_skips_prompt(self):
        """--force overwrites an existing package without prompting."""
        deploy_skills_plugin([self._entry()], self.store, force=True, project_dir=str(self.project))
        with mock.patch("ai_adapter.providers.cursor.click.confirm") as m:
            deploy_skills_plugin([self._entry()], self.store, force=True, project_dir=str(self.project))
        m.assert_not_called()

    def test_resolve_plugin_root_uses_project_basename(self):
        """Plugin root is ~/.cursor/plugins/local/<project-dir basename>."""
        root = resolve_plugin_root(str(self.project))
        self.assertEqual(root, self.home / ".cursor" / "plugins" / "local" / "my-project")

    def test_generate_plugin_manifest(self):
        """Manifest contains name/version/description (mandatory keys)."""
        m = generate_plugin_manifest("proj")
        self.assertEqual(m["name"], "proj")
        self.assertEqual(m["version"], "1.0.0")
        self.assertIn("description", m)


class TestCursorrulesCLI(unittest.TestCase):
    """CLI integration: --format cursorrules on agent get / get-all."""

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

        self.inst_a = Path(self.temp_dir.name) / "AGENTS.md"
        self.inst_a.write_text("---\nname: AGENTS\n---\n# Agents rules\n")
        self.inst_b = Path(self.temp_dir.name) / "STYLE.md"
        self.inst_b.write_text("# Style rules\n")

    def tearDown(self):
        import pathlib

        pathlib.Path.home = staticmethod(self._original_home)
        import ai_adapter.config as cfg

        cfg.AI_ADAPTER_DIR = Path.home() / ".ai-adapter"
        self.temp_dir.cleanup()

    def test_agent_get_cursorrules(self):
        """agent get --format cursorrules writes one instruction, no separator."""
        self.runner.invoke(main, ["agent", "add", str(self.inst_a)])
        result = self.runner.invoke(main, ["agent", "get", "AGENTS", "--format", "cursorrules"])
        self.assertEqual(result.exit_code, 0, result.output)
        out = Path.cwd() / CURSORRULES_FILENAME
        self.assertTrue(out.exists())
        content = out.read_text()
        self.assertNotIn("---", content)
        self.assertIn("# Agents rules", content)

    def test_agent_get_all_cursorrules_concatenates(self):
        """agent get-all --format cursorrules joins instructions with separators."""
        self.runner.invoke(main, ["agent", "add", str(self.inst_a)])
        self.runner.invoke(main, ["agent", "add", str(self.inst_b)])
        result = self.runner.invoke(main, ["agent", "get-all", "--format", "cursorrules"])
        self.assertEqual(result.exit_code, 0, result.output)
        content = (Path.cwd() / CURSORRULES_FILENAME).read_text()
        self.assertIn("# --- AGENTS ---\n# Agents rules", content)
        self.assertIn("# --- STYLE ---\n# Style rules", content)

    def test_agent_get_cursorrules_existing_prompt(self):
        """Existing .cursorrules prompts without --force."""
        self.runner.invoke(main, ["agent", "add", str(self.inst_a)])
        self.runner.invoke(main, ["agent", "get", "AGENTS", "--format", "cursorrules"])
        result = self.runner.invoke(main, ["agent", "get", "AGENTS", "--format", "cursorrules"], input="n\n")
        self.assertNotEqual(result.exit_code, 0)
        result2 = self.runner.invoke(main, ["agent", "get", "AGENTS", "--format", "cursorrules", "--force"])
        self.assertEqual(result2.exit_code, 0, result2.output)

    def test_agent_get_cursorrules_scope_user_rejected(self):
        """--format cursorrules --scope user is rejected (project-root only)."""
        self.runner.invoke(main, ["agent", "add", str(self.inst_a)])
        result = self.runner.invoke(main, ["agent", "get", "AGENTS", "--format", "cursorrules", "--scope", "user"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("does not support --scope user", result.output)

    def test_agent_get_all_cursor_exit2_preserved(self):
        """--format cursor on get-all still exits 2 (distinct from cursorrules)."""
        self.runner.invoke(main, ["agent", "add", str(self.inst_a)])
        result = self.runner.invoke(main, ["agent", "get-all", "--format", "cursor"])
        self.assertEqual(result.exit_code, 2)
        self.assertIn("not supported", result.output)

    def test_agent_get_cursorrules_project_dir(self):
        """--project-dir is respected for .cursorrules output."""
        self.runner.invoke(main, ["agent", "add", str(self.inst_a)])
        project_dir = Path(self.temp_dir.name) / "proj"
        project_dir.mkdir()
        result = self.runner.invoke(
            main, ["agent", "get", "AGENTS", "--format", "cursorrules", "--project-dir", str(project_dir)]
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertTrue((project_dir / CURSORRULES_FILENAME).exists())


class TestCursorPluginCLI(unittest.TestCase):
    """CLI integration: --format cursor-plugin on skill get / get-all."""

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

        skill_dir = Path(self.temp_dir.name) / "test-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("---\nname: test-skill\n---\n# Test\n")
        (skill_dir / "scripts").mkdir()
        (skill_dir / "scripts" / "run.sh").write_text("#!/bin/sh\necho hi\n")
        self.runner.invoke(main, ["skill", "add", str(skill_dir)])

        self.project_dir = Path(self.temp_dir.name) / "my-proj"
        self.project_dir.mkdir()

    def tearDown(self):
        import pathlib

        pathlib.Path.home = staticmethod(self._original_home)
        import ai_adapter.config as cfg

        cfg.AI_ADAPTER_DIR = Path.home() / ".ai-adapter"
        self.temp_dir.cleanup()

    def test_skill_get_cursor_plugin(self):
        """skill get --format cursor-plugin builds a plugin package."""
        result = self.runner.invoke(
            main,
            ["skill", "get", "test-skill", "--format", "cursor-plugin", "--project-dir", str(self.project_dir)],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        root = self.patch_home / ".cursor" / "plugins" / "local" / "my-proj"
        self.assertTrue((root / ".cursor-plugin" / "plugin.json").exists())
        self.assertTrue((root / "skills" / "test-skill" / "SKILL.md").exists())
        self.assertTrue((root / "skills" / "test-skill" / "scripts" / "run.sh").exists())

    def test_skill_get_cursor_plugin_manifest_mandatory(self):
        """plugin.json manifest is always generated (AC: manifest required)."""
        self.runner.invoke(
            main,
            ["skill", "get", "test-skill", "--format", "cursor-plugin", "--project-dir", str(self.project_dir)],
        )
        manifest = self.patch_home / ".cursor" / "plugins" / "local" / "my-proj" / ".cursor-plugin" / "plugin.json"
        data = json.loads(manifest.read_text())
        self.assertEqual(data["name"], "my-proj")

    def test_skill_get_all_cursor_plugin(self):
        """skill get-all --format cursor-plugin installs every skill."""
        result = self.runner.invoke(
            main,
            ["skill", "get-all", "--format", "cursor-plugin", "--project-dir", str(self.project_dir), "--force"],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        root = self.patch_home / ".cursor" / "plugins" / "local" / "my-proj"
        self.assertTrue((root / "skills" / "test-skill" / "SKILL.md").exists())
        self.assertTrue((root / ".cursor-plugin" / "plugin.json").exists())

    def test_skill_get_all_cursor_plugin_env_filter(self):
        """--env filter works with cursor-plugin (task 07-3 AC2)."""
        staging_dir = Path(self.temp_dir.name) / "staging-skill"
        staging_dir.mkdir()
        (staging_dir / "SKILL.md").write_text("---\nname: staging-skill\n---\n# S\n")
        self.runner.invoke(main, ["skill", "add", str(staging_dir), "--env", "staging"])

        prod_dir = Path(self.temp_dir.name) / "prod-skill"
        prod_dir.mkdir()
        (prod_dir / "SKILL.md").write_text("---\nname: prod-skill\n---\n# P\n")
        self.runner.invoke(main, ["skill", "add", str(prod_dir), "--env", "production"])

        result = self.runner.invoke(
            main,
            [
                "skill",
                "get-all",
                "--format",
                "cursor-plugin",
                "--env",
                "staging",
                "--project-dir",
                str(self.project_dir),
                "--force",
            ],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        skills_root = self.patch_home / ".cursor" / "plugins" / "local" / "my-proj" / "skills"
        self.assertTrue((skills_root / "staging-skill").exists())
        self.assertFalse((skills_root / "prod-skill").exists())

    def test_skill_get_cursor_plugin_existing_prompts(self):
        """Existing plugin package prompts without --force."""
        self.runner.invoke(
            main,
            ["skill", "get", "test-skill", "--format", "cursor-plugin", "--project-dir", str(self.project_dir)],
        )
        result = self.runner.invoke(
            main,
            ["skill", "get", "test-skill", "--format", "cursor-plugin", "--project-dir", str(self.project_dir)],
            input="n\n",
        )
        self.assertNotEqual(result.exit_code, 0)
        result2 = self.runner.invoke(
            main,
            [
                "skill",
                "get",
                "test-skill",
                "--format",
                "cursor-plugin",
                "--project-dir",
                str(self.project_dir),
                "--force",
            ],
        )
        self.assertEqual(result2.exit_code, 0, result2.output)

    def test_skill_get_format_cursor_rules_unchanged(self):
        """--format cursor on skill get still deploys .mdc rules (AC4)."""
        result = self.runner.invoke(
            main,
            ["skill", "get", "test-skill", "--format", "cursor", "--project-dir", str(self.project_dir)],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertTrue((self.project_dir / ".cursor" / "rules" / "test-skill.mdc").exists())


class TestCursorPluginNameSanitize(unittest.TestCase):
    """QA NEW-ISSUE-2: _sanitize_plugin_name must comply with Cursor schema."""

    def test_underscore_becomes_hyphen(self):
        """My_Project → my-project (underscore is invalid per Cursor schema)."""
        from ai_adapter.providers.cursor import _sanitize_plugin_name

        self.assertEqual(_sanitize_plugin_name("My_Project"), "my-project")

    def test_space_becomes_hyphen(self):
        from ai_adapter.providers.cursor import _sanitize_plugin_name

        self.assertEqual(_sanitize_plugin_name("my project"), "my-project")

    def test_trailing_hyphen_gets_alnum(self):
        """proj- → proj-0 (trailing hyphen must become alphanumeric)."""
        from ai_adapter.providers.cursor import _sanitize_plugin_name

        self.assertEqual(_sanitize_plugin_name("proj-"), "proj-0")

    def test_empty_falls_back(self):
        from ai_adapter.providers.cursor import _sanitize_plugin_name

        self.assertEqual(_sanitize_plugin_name(""), "ai-adapter")
        self.assertEqual(_sanitize_plugin_name("..."), "ai-adapter")

    def test_dotdot_not_leaked(self):
        """.. must not survive sanitization."""
        from ai_adapter.providers.cursor import _sanitize_plugin_name

        name = _sanitize_plugin_name("../evil")
        self.assertNotIn("..", name)
        self.assertNotIn("/", name)

    def test_result_matches_cursor_schema(self):
        """All outputs must match ^[a-z0-9]([a-z0-9.-]*[a-z0-9])?$."""
        import re

        from ai_adapter.providers.cursor import _sanitize_plugin_name

        pattern = re.compile(r"^[a-z0-9]([a-z0-9.-]*[a-z0-9])?$")
        for raw in ["My_Project", "my project", "proj-", "-lead", "UPPER", "a..b", "x_y_z"]:
            result = _sanitize_plugin_name(raw)
            self.assertRegex(result, pattern, f"input={raw!r} → {result!r}")


class TestCursorPluginPathTraversal(unittest.TestCase):
    """QA C1-GAP: deploy_skills_plugin must block path-traversal names."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_deploy_blocks_dotdot_skill_name(self):
        """Skill(name='../../evil') must be skipped, not deployed outside."""
        from ai_adapter.models import Skill
        from ai_adapter.providers.cursor import deploy_skills_plugin

        store = self.base / "store"
        (store / "evil").mkdir(parents=True)
        (store / "evil" / "SKILL.md").write_text("---\nname: evil\ndescription: d\n---\n# e\n", encoding="utf-8")
        # Decoy that must survive untouched.
        victim = self.base / "victim"
        victim.mkdir()
        (victim / "precious.txt").write_text("keep me", encoding="utf-8")

        project_dir = self.base / "proj"
        project_dir.mkdir()

        with mock.patch("ai_adapter.config.Path.cwd", return_value=project_dir):
            deploy_skills_plugin(
                [Skill(name="../../victim")],
                store,
                force=True,
                project_dir=str(project_dir),
            )
        # Decoy file must be untouched.
        self.assertEqual((victim / "precious.txt").read_text(), "keep me")
        # The escaped directory must not contain SKILL.md from our store.
        self.assertFalse((victim / "SKILL.md").exists())

    def test_deploy_blocks_prefix_sibling(self):
        """'../skills-evil' must be skipped (prefix-sibling escape)."""
        from ai_adapter.models import Skill
        from ai_adapter.providers.cursor import deploy_skills_plugin

        store = self.base / "store"
        (store / "x").mkdir(parents=True)
        (store / "x" / "SKILL.md").write_text("# x\n", encoding="utf-8")
        project_dir = self.base / "proj"
        project_dir.mkdir()

        with mock.patch("ai_adapter.config.Path.cwd", return_value=project_dir):
            deploy_skills_plugin(
                [Skill(name="../skills-evil")],
                store,
                force=True,
                project_dir=str(project_dir),
            )
        escaped = self.base / "cursor-plugins-evil"
        self.assertFalse(escaped.exists())
