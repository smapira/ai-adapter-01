"""Tests for opencode.py."""

import json
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
