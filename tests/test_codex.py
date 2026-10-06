"""Tests for codex.py."""

import tempfile
import unittest
from pathlib import Path

from click.testing import CliRunner

from ai_adapter.cli import main
from ai_adapter.config import init


class TestCodexInstallCommand(unittest.TestCase):
    """Tests for codex install subcommand."""

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

    def tearDown(self):
        import pathlib

        pathlib.Path.home = staticmethod(self._original_home)
        import ai_adapter.config as cfg

        cfg.AI_ADAPTER_DIR = Path.home() / ".ai-adapter"
        self.temp_dir.cleanup()

    def test_codex_install_nothing_registered(self):
        """No agents/instructions/skills registered → no AGENTS.md generated."""
        result = self.runner.invoke(main, ["codex", "install"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("No agents", result.output)

    def test_codex_install_with_agent(self):
        """Registered agent → AGENTS.md contains agent content."""
        agent_file = Path(self.temp_dir.name) / "reviewer.md"
        agent_file.write_text("# Reviewer\nCode review agent.\n")
        self.runner.invoke(main, ["sub-agent", "add", str(agent_file)])

        result = self.runner.invoke(main, ["codex", "install"])
        self.assertEqual(result.exit_code, 0)

        output_path = Path.cwd() / "AGENTS.md"
        self.assertTrue(output_path.exists())
        content = output_path.read_text()
        self.assertIn("Reviewer", content)
        self.assertIn("Code review agent", content)
        output_path.unlink()

    def test_codex_install_with_agent_md(self):
        """Registered .agent.md → AGENTS.md contains frontmatter name."""
        agent_md = Path(self.temp_dir.name) / "reviewer.agent.md"
        agent_md.write_text("---\nname: Reviewer\n---\n\n# Reviewer\nReview code.\n")
        self.runner.invoke(main, ["sub-agent", "add", str(agent_md)])

        result = self.runner.invoke(main, ["codex", "install"])
        self.assertEqual(result.exit_code, 0)

        output_path = Path.cwd() / "AGENTS.md"
        self.assertTrue(output_path.exists())
        content = output_path.read_text()
        self.assertIn("Reviewer", content)
        # Frontmatter should be stripped
        self.assertNotIn("---", content)
        output_path.unlink()

    def test_codex_install_with_instruction(self):
        """Registered root-level instruction → AGENTS.md contains it."""
        inst_file = Path(self.temp_dir.name) / "AGENTS.md"
        inst_file.write_text("# Project Rules\n- Use TypeScript\n")
        self.runner.invoke(main, ["agent", "add", str(inst_file)])

        result = self.runner.invoke(main, ["codex", "install"])
        self.assertEqual(result.exit_code, 0)

        output_path = Path.cwd() / "AGENTS.md"
        self.assertTrue(output_path.exists())
        content = output_path.read_text()
        self.assertIn("Project Rules", content)
        output_path.unlink()

    def test_codex_install_with_skill(self):
        """Registered skill → AGENTS.md contains SKILL.md content."""
        skill_dir = Path(self.temp_dir.name) / "database-schema"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("---\nname: database-schema\n---\n\n# DB Schema\nSchema knowledge.\n")
        self.runner.invoke(main, ["skill", "add", str(skill_dir)])

        result = self.runner.invoke(main, ["codex", "install"])
        self.assertEqual(result.exit_code, 0)

        output_path = Path.cwd() / "AGENTS.md"
        self.assertTrue(output_path.exists())
        content = output_path.read_text()
        self.assertIn("DB Schema", content)
        output_path.unlink()

    def test_codex_install_with_all_categories(self):
        """All categories → all sections present."""
        agent_file = Path(self.temp_dir.name) / "reviewer.md"
        agent_file.write_text("# Reviewer\nReview code.\n")
        self.runner.invoke(main, ["sub-agent", "add", str(agent_file)])

        inst_file = Path(self.temp_dir.name) / "CLAUDE.md"
        inst_file.write_text("# Project Rules\n- TypeScript\n")
        self.runner.invoke(main, ["agent", "add", str(inst_file)])

        skill_dir = Path(self.temp_dir.name) / "db-schema"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("---\nname: db-schema\n---\n\n# DB Schema\nSchema.\n")
        self.runner.invoke(main, ["skill", "add", str(skill_dir)])

        result = self.runner.invoke(main, ["codex", "install"])
        self.assertEqual(result.exit_code, 0)

        output_path = Path.cwd() / "AGENTS.md"
        self.assertTrue(output_path.exists())
        content = output_path.read_text()
        self.assertIn("Reviewer", content)
        self.assertIn("Project Rules", content)
        self.assertIn("DB Schema", content)
        # Sections separated by ---
        self.assertIn("---", content)
        output_path.unlink()

    def test_codex_install_force_overwrite(self):
        """--force overwrites existing AGENTS.md without prompt."""
        output_path = Path.cwd() / "AGENTS.md"
        output_path.write_text("# Old content\n")

        agent_file = Path(self.temp_dir.name) / "reviewer.md"
        agent_file.write_text("# Reviewer\nReview code.\n")
        self.runner.invoke(main, ["sub-agent", "add", str(agent_file)])

        result = self.runner.invoke(main, ["codex", "install", "--force"])
        self.assertEqual(result.exit_code, 0)
        content = output_path.read_text()
        self.assertIn("Reviewer", content)
        self.assertNotIn("Old content", content)
        output_path.unlink()

    def test_codex_uninstall(self):
        """codex uninstall removes AGENTS.md."""
        output_path = Path.cwd() / "AGENTS.md"
        output_path.write_text("# AGENTS\n")

        result = self.runner.invoke(main, ["codex", "uninstall"])
        self.assertEqual(result.exit_code, 0)
        self.assertFalse(output_path.exists())

    def test_codex_uninstall_not_found(self):
        """Uninstall without AGENTS.md → message."""
        result = self.runner.invoke(main, ["codex", "uninstall"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("not found", result.output)


class TestCodexTOMLMerge(unittest.TestCase):
    """Design 03: TOML text-splice merge for config.toml (review M1/M2/M4)."""

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
        self.codex_dir = self.patch_home / ".codex"
        self.codex_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        import pathlib

        pathlib.Path.home = staticmethod(self._original_home)
        import ai_adapter.config as cfg

        cfg.AI_ADAPTER_DIR = Path.home() / ".ai-adapter"
        self.temp_dir.cleanup()

    def _merge(self, existing_text: str, servers: dict, force: bool = True) -> str:
        """Run merge_into_config_toml on a config.toml with *existing_text*."""
        from ai_adapter.providers.codex import merge_into_config_toml

        path = self.codex_dir / "config.toml"
        if existing_text is not None:
            path.write_text(existing_text, encoding="utf-8")
        mcp_data = {"mcp_servers": servers}
        merge_into_config_toml(path, mcp_data, force=force)
        return path.read_text(encoding="utf-8")

    def test_merge_preserves_comments_and_key_order(self):
        """AC2: comments and key order outside managed tables are preserved."""
        existing = (
            "# Primary model\n"
            'model = "gpt-5"\n'
            'approval_policy = "untrusted"\n'
            "\n"
            "[mcp_servers.legacy]\n"
            "# legacy comment stays\n"
            'command = "node"\n'
            'args = ["legacy.js"]\n'
        )
        result = self._merge(existing, {"new-mcp": {"command": "npx", "args": ["-y", "x"]}})
        self.assertIn("# Primary model", result)
        self.assertIn('model = "gpt-5"', result)
        self.assertIn('approval_policy = "untrusted"', result)
        self.assertIn("# legacy comment stays", result)
        self.assertIn("[mcp_servers.new-mcp]", result)
        # Key order: model appears before mcp_servers.new-mcp
        self.assertLess(result.index('model = "gpt-5"'), result.index("[mcp_servers.new-mcp]"))

    def test_merge_creates_bak_backup(self):
        """.bak backup is taken before modifying an existing file."""
        from ai_adapter.providers.codex import merge_into_config_toml

        path = self.codex_dir / "config.toml"
        path.write_text('model = "gpt-5"\n', encoding="utf-8")
        merge_into_config_toml(path, {"mcp_servers": {"x": {"command": "npx"}}}, force=True)
        bak = self.codex_dir / "config.toml.bak"
        self.assertTrue(bak.exists())
        self.assertIn('model = "gpt-5"', bak.read_text(encoding="utf-8"))

    def test_merge_refuses_inline_table_form(self):
        """C2: inline-table mcp_servers form is refused (not silently corrupted)."""
        import click

        existing = 'mcp_servers = { foo = { command = "x" } }\n'
        with self.assertRaises(click.ClickException) as ctx:
            self._merge(existing, {"bar": {"command": "npx"}})
        self.assertIn("inline table", str(ctx.exception))

    def test_merge_refuses_dotted_key_form(self):
        """C2: dotted-key mcp_servers form is refused."""
        import click

        existing = 'mcp_servers.foo = { command = "x" }\n'
        with self.assertRaises(click.ClickException) as ctx:
            self._merge(existing, {"bar": {"command": "npx"}})
        self.assertIn("dotted key", str(ctx.exception))

    def test_merge_output_is_valid_toml(self):
        """M4: spliced result is validated with tomllib before writing."""
        try:
            import tomllib
        except ModuleNotFoundError:
            import tomli as tomllib  # type: ignore[no-redef]

        existing = '[mcp_servers.legacy]\ncommand = "node"\n'
        result = self._merge(existing, {"new": {"command": "npx", "args": ["-y"]}})
        parsed = tomllib.loads(result)
        self.assertIn("mcp_servers", parsed)
        self.assertIn("legacy", parsed["mcp_servers"])
        self.assertIn("new", parsed["mcp_servers"])

    def test_merge_preserves_unmanaged_servers(self):
        """Unmanaged [mcp_servers.*] tables are kept verbatim."""
        existing = '[mcp_servers.legacy]\ncommand = "node"\nargs = ["legacy.js"]\n'
        result = self._merge(existing, {"managed": {"command": "npx"}})
        self.assertIn("[mcp_servers.legacy]", result)
        self.assertIn('args = ["legacy.js"]', result)
        self.assertIn("[mcp_servers.managed]", result)

    def test_merge_does_not_touch_auth_json(self):
        """M2/security: auth.json is never read or written by the merge."""
        from ai_adapter.providers.codex import merge_into_config_toml

        auth = self.codex_dir / "auth.json"
        auth.write_text('{"OPENAI_API_KEY": "sk-secret"}\n', encoding="utf-8")
        auth_mtime = auth.stat().st_mtime_ns

        path = self.codex_dir / "config.toml"
        path.write_text('model = "gpt-5"\n', encoding="utf-8")
        merge_into_config_toml(path, {"mcp_servers": {"x": {"command": "npx"}}}, force=True)

        self.assertEqual(auth.read_text(encoding="utf-8"), '{"OPENAI_API_KEY": "sk-secret"}\n')
        self.assertEqual(auth.stat().st_mtime_ns, auth_mtime)

    def test_scan_never_reports_auth_json(self):
        """M2/security: scan excludes auth.json via SCAN_IGNORE_PATTERNS."""
        from ai_adapter.scan import scan_codex

        auth = self.codex_dir / "auth.json"
        auth.write_text('{"OPENAI_API_KEY": "sk-secret"}\n', encoding="utf-8")
        (self.codex_dir / "config.toml").write_text('model = "gpt-5"\n', encoding="utf-8")

        items = scan_codex(self.patch_home)
        paths = [str(i.path) for i in items if i.path is not None]
        self.assertFalse(any("auth.json" in p for p in paths))
        # config.toml is still detected.
        self.assertTrue(any("config.toml" in p for p in paths))

    def test_merge_validation_failure_preserves_original(self):
        """W1 (QA): invalid splice result → ClickException, original file untouched."""
        import click

        # Force a validation failure by monkeypatching tomllib.loads in codex module.
        from ai_adapter.providers import codex as codex_mod

        path = self.codex_dir / "config.toml"
        original = 'model = "gpt-5"\n'
        path.write_text(original, encoding="utf-8")

        real_loads = codex_mod.tomllib.loads

        def _bad_loads(_text):
            raise codex_mod.tomllib.TOMLDecodeError("simulated", 0, 0)

        codex_mod.tomllib.loads = _bad_loads
        try:
            with self.assertRaises(click.ClickException) as ctx:
                codex_mod.merge_into_config_toml(path, {"x": {"command": "npx"}}, force=True)
        finally:
            codex_mod.tomllib.loads = real_loads
        self.assertIn("invalid TOML", str(ctx.exception))
        # Original file must be untouched.
        self.assertEqual(path.read_text(encoding="utf-8"), original)
