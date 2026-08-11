"""Tests for pack.py — Pack install / list."""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

import yaml
from click.testing import CliRunner

from ai_adapter.cli import main
from ai_adapter.config import init


def _patch_home(test_case):
    """Redirect HOME and AI_ADAPTER_DIR for a test class."""
    import pathlib

    test_case.temp_dir = tempfile.TemporaryDirectory()
    test_case.patch_home = Path(test_case.temp_dir.name)

    test_case._original_home = pathlib.Path.home
    pathlib.Path.home = staticmethod(lambda: test_case.patch_home)

    import ai_adapter.config as cfg

    cfg.AI_ADAPTER_DIR = test_case.patch_home / ".ai-adapter"
    init()

    # Backup .github
    test_case._github_bak = None
    github_dir = Path.cwd() / ".github"
    if github_dir.exists():
        test_case._github_bak = Path(test_case.temp_dir.name) / "github.bak"
        shutil.copytree(github_dir, test_case._github_bak)


def _restore_home(test_case):
    import pathlib

    pathlib.Path.home = staticmethod(test_case._original_home)
    import ai_adapter.config as cfg

    cfg.AI_ADAPTER_DIR = Path.home() / ".ai-adapter"
    if hasattr(test_case, "_github_bak") and test_case._github_bak and Path(test_case._github_bak).exists():
        github_dir = Path.cwd() / ".github"
        if github_dir.exists():
            shutil.rmtree(github_dir)
        shutil.copytree(test_case._github_bak, github_dir)
    test_case.temp_dir.cleanup()


class TestPackList(unittest.TestCase):
    """Tests for ``ai-adapter pack list``."""

    def setUp(self):
        _patch_home(self)
        self.runner = CliRunner()

    def tearDown(self):
        _restore_home(self)

    def test_pack_list_empty(self):
        """No packs → message."""
        result = self.runner.invoke(main, ["pack", "list"])
        self.assertEqual(result.exit_code, 0)
        self.assertTrue("No packs found" in result.output or "Available packs" in result.output)

    def test_pack_list_shows_user_packs(self):
        """User pack appears in list."""
        packs_dir = self.patch_home / ".ai-adapter" / "packs"
        packs_dir.mkdir(parents=True, exist_ok=True)
        (packs_dir / "starter.yaml").write_text(
            yaml.dump({"name": "starter", "description": "Starter pack", "profiles": ["web-dev"]})
        )
        result = self.runner.invoke(main, ["pack", "list"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("starter", result.output)
        self.assertIn("Starter pack", result.output)


class TestPackInstall(unittest.TestCase):
    """Tests for ``ai-adapter pack install <name>``."""

    def setUp(self):
        _patch_home(self)
        self.runner = CliRunner()
        self.packs_dir = self.patch_home / ".ai-adapter" / "packs"
        self.packs_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        _restore_home(self)

    def test_install_nonexistent_pack(self):
        """Installing a non-existent pack errors with available list."""
        result = self.runner.invoke(main, ["pack", "install", "nonexistent"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("not found", result.output)

    def test_install_pack_with_single_profile(self):
        """Pack with one profile applies that profile."""
        # Create the pack
        (self.packs_dir / "single.yaml").write_text(yaml.dump({"name": "single", "profiles": ["web-dev"]}))
        result = self.runner.invoke(main, ["pack", "install", "single", "--yes"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("single", result.output)

    def test_install_pack_with_multiple_profiles(self):
        """Pack with multiple profiles applies them in order."""
        (self.packs_dir / "multi.yaml").write_text(
            yaml.dump(
                {
                    "name": "multi",
                    "description": "Multi profile pack",
                    "profiles": ["profile-a", "profile-b"],
                }
            )
        )
        result = self.runner.invoke(main, ["pack", "install", "multi", "--yes"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("1/2", result.output)
        self.assertIn("2/2", result.output)
        self.assertIn("profile-a", result.output)
        self.assertIn("profile-b", result.output)

    def test_install_empty_pack(self):
        """Pack with no profiles → message."""
        (self.packs_dir / "empty.yaml").write_text(yaml.dump({"name": "empty", "profiles": []}))
        result = self.runner.invoke(main, ["pack", "install", "empty"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("no profiles", result.output)

    def test_install_dry_run(self):
        """Pack install --dry-run does not modify anything."""
        (self.packs_dir / "dry.yaml").write_text(yaml.dump({"name": "dry", "profiles": ["web-dev"]}))
        result = self.runner.invoke(main, ["pack", "install", "dry", "--dry-run"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("dry-run", result.output)

    def test_install_pack_applies_mcp_profile(self):
        """Pack with an MCP-only profile registers the MCP server."""
        profiles_dir = self.patch_home / ".ai-adapter" / "profiles"
        profiles_dir.mkdir(parents=True, exist_ok=True)
        (profiles_dir / "mcp-prof.yaml").write_text(
            yaml.dump(
                {
                    "name": "mcp-prof",
                    "mcp": [{"name": "pack-mcp", "command": "echo"}],
                }
            )
        )
        (self.packs_dir / "mcp-pack.yaml").write_text(yaml.dump({"name": "mcp-pack", "profiles": ["mcp-prof"]}))
        result = self.runner.invoke(main, ["pack", "install", "mcp-pack", "--yes"])
        self.assertEqual(result.exit_code, 0)

        from ai_adapter.config import load_config

        config = load_config()
        self.assertTrue(any(s.name == "pack-mcp" for s in config.mcp_servers))
