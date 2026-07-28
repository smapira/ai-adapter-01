"""Tests for instruction.py."""

import tempfile
import unittest
from pathlib import Path

from click.testing import CliRunner

from ai_adapter.cli import main
from ai_adapter.config import init


class TestInstructionCommands(unittest.TestCase):
    """Tests for instruction subcommands."""

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

        self.inst_file = Path(self.temp_dir.name) / "AGENTS.md"
        self.inst_file.write_text("# Root Agent\n\nThis is the root agent.\n")

    def tearDown(self):
        import pathlib

        pathlib.Path.home = staticmethod(self._original_home)
        import ai_adapter.config as cfg

        cfg.AI_ADAPTER_DIR = Path.home() / ".ai-adapter"
        self.temp_dir.cleanup()

    def test_instruction_list_empty(self):
        """Verify empty message is shown when no instructions registered."""
        result = self.runner.invoke(main, ["agent", "list"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("No instructions registered.", result.output)

    def test_instruction_add(self):
        """Verify instruction add adds an instruction."""
        result = self.runner.invoke(main, ["agent", "add", str(self.inst_file)])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("AGENTS", result.output)

        # Verify file was copied
        inst_dir = self.patch_home / ".ai-adapter" / "instructions"
        self.assertTrue((inst_dir / "AGENTS.md").exists())

    def test_instruction_add_and_list(self):
        """Verify instruction add → instruction list flow."""
        self.runner.invoke(main, ["agent", "add", str(self.inst_file)])
        result = self.runner.invoke(main, ["agent", "list"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("AGENTS", result.output)

    def test_instruction_get(self):
        """Verify instruction get copies to project root."""
        self.runner.invoke(main, ["agent", "add", str(self.inst_file)])

        result = self.runner.invoke(main, ["agent", "get", "AGENTS"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("AGENTS.md", result.output)
        root_file = Path.cwd() / "AGENTS.md"
        self.assertTrue(root_file.exists())

        # Cleanup
        root_file.unlink(missing_ok=True)

    def test_instruction_get_with_project_dir(self):
        """Verify instruction get --project-dir copies to specified directory root."""
        self.runner.invoke(main, ["agent", "add", str(self.inst_file)])

        project_dir = Path(self.temp_dir.name) / "my-project"
        project_dir.mkdir(parents=True)

        result = self.runner.invoke(
            main,
            [
                "agent",
                "get",
                "AGENTS",
                "--project-dir",
                str(project_dir),
            ],
        )
        self.assertEqual(result.exit_code, 0)
        self.assertTrue((project_dir / "AGENTS.md").exists())

    def test_instruction_get_not_found(self):
        """Verify get fails for non-existent instruction."""
        result = self.runner.invoke(main, ["agent", "get", "nonexistent"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("not found", result.output)

    def test_instruction_get_with_force(self):
        """Verify instruction get --force overwrites without confirmation."""
        self.runner.invoke(main, ["agent", "add", str(self.inst_file)])

        # First get to create the file
        self.runner.invoke(main, ["agent", "get", "AGENTS"])

        # Second get with --force
        result = self.runner.invoke(main, ["agent", "get", "AGENTS", "--force"])
        self.assertEqual(result.exit_code, 0)
        self.assertTrue((Path.cwd() / "AGENTS.md").exists())

        (Path.cwd() / "AGENTS.md").unlink(missing_ok=True)

    def test_instruction_remove(self):
        """Verify instruction remove removes an instruction."""
        self.runner.invoke(main, ["agent", "add", str(self.inst_file)])
        result = self.runner.invoke(main, ["agent", "remove", "AGENTS"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("AGENTS", result.output)

        # Verify list is empty
        result = self.runner.invoke(main, ["agent", "list"])
        self.assertIn("No instructions registered.", result.output)

    def test_instruction_add_rec(self):
        """Verify add-rec registers all files in a directory."""
        src_dir = Path(self.temp_dir.name) / "inst_dir"
        src_dir.mkdir()
        (src_dir / "AGENTS.md").write_text("# Agents\n")
        (src_dir / "CLAUDE.md").write_text("# Claude\n")

        result = self.runner.invoke(main, ["agent", "add-rec", str(src_dir)])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("2", result.output)

        result = self.runner.invoke(main, ["agent", "list"])
        self.assertIn("AGENTS", result.output)
        self.assertIn("CLAUDE", result.output)

    def test_instruction_get_all(self):
        """Verify get-all copies all instructions to project root."""
        self.runner.invoke(main, ["agent", "add", str(self.inst_file)])
        inst2 = Path(self.temp_dir.name) / "CLAUDE.md"
        inst2.write_text("# Claude\n")
        self.runner.invoke(main, ["agent", "add", str(inst2)])

        result = self.runner.invoke(main, ["agent", "get-all", "--force"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("2", result.output)
        self.assertTrue((Path.cwd() / "AGENTS.md").exists())
        self.assertTrue((Path.cwd() / "CLAUDE.md").exists())

        (Path.cwd() / "AGENTS.md").unlink(missing_ok=True)
        (Path.cwd() / "CLAUDE.md").unlink(missing_ok=True)

    def test_instruction_remove_all(self):
        """Verify remove-all --force removes all instructions."""
        inst2 = Path(self.temp_dir.name) / "CLAUDE.md"
        inst2.write_text("# Claude\n")
        self.runner.invoke(main, ["agent", "add", str(self.inst_file)])
        self.runner.invoke(main, ["agent", "add", str(inst2)])

        result = self.runner.invoke(main, ["agent", "remove-all", "--force"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("2", result.output)

        result = self.runner.invoke(main, ["agent", "list"])
        self.assertIn("No instructions registered.", result.output)
