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
