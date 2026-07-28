"""Tests for opencode.py."""

import json
import os
import tempfile
import unittest
from pathlib import Path

from click.testing import CliRunner

from ai_adapter.cli import main
from ai_adapter.config import init


class TestOpencodeCommands(unittest.TestCase):
    """Tests for opencode subcommands."""

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

    def test_opencode_install(self):
        """Verify opencode install generates opencode.json template."""
        result = self.runner.invoke(main, ["opencode", "install"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("opencode.json", result.output)

        output_path = Path.cwd() / "opencode.json"
        self.assertTrue(output_path.exists())
        with open(output_path) as f:
            data = json.load(f)
        self.assertIn("$schema", data)
        self.assertIn("instructions", data)
        self.assertIn("permission", data)
        self.assertIn(".github/agents/*.agent.md", data["instructions"])

        output_path.unlink()

    def test_opencode_uninstall(self):
        """Verify opencode uninstall removes opencode.json."""
        # Install first
        output_path = Path.cwd() / "opencode.json"
        output_path.write_text("{}")

        result = self.runner.invoke(main, ["opencode", "uninstall"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("opencode.json", result.output)
        self.assertFalse(output_path.exists())

    def test_opencode_uninstall_not_found(self):
        """Verify uninstall does not error when no opencode.json."""
        result = self.runner.invoke(main, ["opencode", "uninstall"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("not found", result.output)

    def test_opencode_alias_no_github(self):
        """Verify alias errors when .github does not exist."""
        result = self.runner.invoke(main, ["opencode", "alias"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn(".github", result.output)

    def test_opencode_install_template_structure(self):
        """Verify generated opencode.json has correct template structure."""
        result = self.runner.invoke(main, ["opencode", "install"])
        self.assertEqual(result.exit_code, 0)

        output_path = Path.cwd() / "opencode.json"
        self.assertTrue(output_path.exists())
        with open(output_path) as f:
            data = json.load(f)

        # Verify all permissions are "ask"
        perm = data.get("permission", {})
        for key in ["execute", "read", "edit", "search", "agent", "browser", "web", "todo"]:
            self.assertEqual(perm.get(key), "ask", f"permission.{key} is not ask")

        # instructions includes .agent.md
        self.assertIn(".github/agents/*.agent.md", data.get("instructions", []))

        output_path.unlink()


class TestOpencodeValidateCommand(unittest.TestCase):
    """Tests for opencode validate subcommand."""

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
        import shutil

        shutil.rmtree(Path.cwd() / ".github", ignore_errors=True)

    def _create_github_agents(self) -> Path:
        """Create .github/agents/ in temp dir and return the path."""
        agents_dir = Path.cwd() / ".github" / "agents"
        agents_dir.mkdir(parents=True, exist_ok=True)
        return agents_dir

    def test_opencode_validate_valid(self):
        """All files valid → exit 0."""
        agents_dir = self._create_github_agents()
        (agents_dir / "good.agent.md").write_text("---\nname: good\ntools:\n  execute: true\n---\n")
        result = self.runner.invoke(main, ["opencode", "validate"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("All agent files are valid", result.output)

    def test_opencode_validate_invalid(self):
        """Invalid files detected → exit 1."""
        agents_dir = self._create_github_agents()
        (agents_dir / "bad.agent.md").write_text("---\nname: bad\ntools: [execute]\n---\n")
        result = self.runner.invoke(main, ["opencode", "validate"])
        self.assertEqual(result.exit_code, 1)
        self.assertIn("array format", result.output)

    def test_opencode_validate_fix(self):
        """``--fix`` automatically repairs invalid files."""
        agents_dir = self._create_github_agents()
        bad_file = agents_dir / "bad.agent.md"
        bad_file.write_text("---\nname: bad\ntools: [execute]\n---\n")
        result = self.runner.invoke(main, ["opencode", "validate", "--fix"])
        self.assertEqual(result.exit_code, 0)  # fixed, so no errors

        content = bad_file.read_text()
        # But wait -- after fixing, validate returns no errors,
        # so exit code should be 0.
        self.assertIn("  execute: true", content)

    def test_opencode_validate_quiet(self):
        """``--quiet`` minimises output, still returns exit code."""
        agents_dir = self._create_github_agents()
        (agents_dir / "bad.agent.md").write_text("---\nname: bad\ntools: [execute]\n---\n")
        result = self.runner.invoke(main, ["opencode", "validate", "--quiet"])
        self.assertEqual(result.exit_code, 1)
        self.assertEqual(result.output.strip(), "")

    def test_opencode_validate_no_agents_dir(self):
        """No ``.github/agents/`` → exit 0 with message."""
        result = self.runner.invoke(main, ["opencode", "validate"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("No .github/agents/ directory found", result.output)


class TestOpencodeAliasValidation(unittest.TestCase):
    """Tests for opencode alias validation logic."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        # Work inside temp dir so CWD is isolated
        self.orig_cwd = Path.cwd()
        self.work_dir = Path(self.temp_dir.name) / "project"
        self.work_dir.mkdir(parents=True)
        self.work_dir = self.work_dir.resolve()
        os.chdir(self.work_dir)

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
        os.chdir(self.orig_cwd)

    def _create_github_with_agents(self) -> Path:
        """Create .github/agents/ with a valid agent file."""
        agents_dir = self.work_dir / ".github" / "agents"
        agents_dir.mkdir(parents=True, exist_ok=True)
        return agents_dir

    def test_opencode_alias_validates_and_fixes(self):
        """Alias detects invalid agents and prompts to fix."""
        agents_dir = self._create_github_with_agents()
        bad_file = agents_dir / "bad.agent.md"
        bad_file.write_text("---\nname: bad\ntools: [execute]\n---\n")

        # Input 'y' to confirm fixing
        result = self.runner.invoke(
            main,
            ["opencode", "alias"],
            input="y\n",
        )
        # After fixing, symlink should be created
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Symlink created", result.output)

        # File should be fixed
        content = bad_file.read_text()
        self.assertIn("  execute: true", content)
        self.assertNotIn("[execute]", content)

        # Cleanup symlink
        (self.work_dir / ".opencode").unlink()

    def test_opencode_alias_no_github_agents(self):
        """No ``.github/agents/`` → alias proceeds without validation."""
        # Create .github without agents/
        (self.work_dir / ".github").mkdir(parents=True)

        result = self.runner.invoke(main, ["opencode", "alias"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Symlink created", result.output)

        (self.work_dir / ".opencode").unlink()
