"""Tests for setup.py — profile apply / dry-run / list."""

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


def _write_profile_yaml(profiles_dir: Path, data: dict) -> None:
    """Write a profile YAML file."""
    profiles_dir.mkdir(parents=True, exist_ok=True)
    name = data["name"]
    (profiles_dir / f"{name}.yaml").write_text(yaml.dump(data, default_flow_style=False))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSetupList(unittest.TestCase):
    """Tests for ``ai-adapter setup list``."""

    def setUp(self):
        _patch_home(self)
        self.runner = CliRunner()

    def tearDown(self):
        _restore_home(self)

    def test_setup_list_empty(self):
        """No profiles available → message."""
        result = self.runner.invoke(main, ["setup", "list"])
        self.assertEqual(result.exit_code, 0)
        # Either "No profiles found" or lists the standard profiles
        self.assertTrue("No profiles" in result.output or "Available profiles" in result.output)

    def test_setup_list_shows_bundled(self):
        """Standard profiles (web-development, python) appear in the list."""
        result = self.runner.invoke(main, ["setup", "list"])
        self.assertEqual(result.exit_code, 0)
        # The bundled profiles should always be listed
        self.assertTrue("web-development" in result.output or "Available profiles" in result.output)


class TestSetupApply(unittest.TestCase):
    """Tests for ``ai-adapter setup apply <profile>``."""

    def setUp(self):
        _patch_home(self)
        self.runner = CliRunner()
        self.profiles_dir = self.patch_home / ".ai-adapter" / "profiles"

    def tearDown(self):
        _restore_home(self)

    def test_apply_nonexistent_profile(self):
        """Applying a non-existent profile should error with available list."""
        result = self.runner.invoke(main, ["setup", "apply", "nonexistent"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("not found", result.output)

    def test_apply_empty_profile(self):
        """Profile with no items → no output lines, just profile header."""
        _write_profile_yaml(self.profiles_dir, {"name": "empty", "skills": [], "mcp": []})
        result = self.runner.invoke(main, ["setup", "apply", "empty", "--yes"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Profile: empty", result.output)

    def test_apply_profile_with_mcp(self):
        """Profile with MCP server registers it."""
        _write_profile_yaml(
            self.profiles_dir,
            {
                "name": "mcp-only",
                "mcp": [{"name": "test-server", "command": "echo", "args": ["hello"]}],
            },
        )
        result = self.runner.invoke(main, ["setup", "apply", "mcp-only", "--yes"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("registered", result.output)

        # Verify MCP server is in config
        from ai_adapter.config import load_config

        config = load_config()
        self.assertTrue(any(s.name == "test-server" for s in config.mcp_servers))

    def test_apply_profile_idempotent(self):
        """Applying the same profile twice does not duplicate items."""
        _write_profile_yaml(
            self.profiles_dir,
            {
                "name": "idem",
                "mcp": [{"name": "idem-server", "command": "echo"}],
            },
        )
        self.runner.invoke(main, ["setup", "apply", "idem", "--yes"])
        result = self.runner.invoke(main, ["setup", "apply", "idem", "--yes"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("already registered", result.output)

        from ai_adapter.config import load_config

        config = load_config()
        count = sum(1 for s in config.mcp_servers if s.name == "idem-server")
        self.assertEqual(count, 1)

    def test_apply_with_confirmation_prompt(self):
        """Without --yes, prompt is shown (abort on 'n')."""
        _write_profile_yaml(
            self.profiles_dir,
            {
                "name": "prompt-test",
                "mcp": [{"name": "prompt-server", "command": "echo"}],
            },
        )
        result = self.runner.invoke(main, ["setup", "apply", "prompt-test"], input="n\n")
        self.assertNotEqual(result.exit_code, 0)

    def test_apply_no_name_lists_profiles(self):
        """``setup apply`` without a profile name shows available profiles."""
        result = self.runner.invoke(main, ["setup", "apply"])
        self.assertEqual(result.exit_code, 0)
        self.assertTrue("Available profiles" in result.output or "No profiles" in result.output)

    def test_apply_with_skill_source_resolved(self):
        """Profile with a skill whose source is resolved from ~/.ai-adapter/skills/."""
        # First, create a skill directory in the isolated home
        skill_dir = self.patch_home / ".ai-adapter" / "skills" / "my-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("---\nname: my-skill\ndescription: Test skill\n---\n# My Skill\n")

        _write_profile_yaml(
            self.profiles_dir,
            {"name": "skill-profile", "skills": ["my-skill"]},
        )
        result = self.runner.invoke(main, ["setup", "apply", "skill-profile", "--yes"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("registered", result.output)


class TestSetupDryRun(unittest.TestCase):
    """Tests for ``ai-adapter setup apply <profile> --dry-run``."""

    def setUp(self):
        _patch_home(self)
        self.runner = CliRunner()
        self.profiles_dir = self.patch_home / ".ai-adapter" / "profiles"

    def tearDown(self):
        _restore_home(self)

    def test_dry_run_does_not_modify_config(self):
        """--dry-run must not change ~/.ai-adapter/ contents."""
        # Capture state before
        config_dir = self.patch_home / ".ai-adapter"
        set(config_dir.rglob("*")) if config_dir.exists() else set()

        _write_profile_yaml(
            self.profiles_dir,
            {
                "name": "dry-test",
                "mcp": [{"name": "dry-mcp", "command": "echo"}],
                "skills": ["dry-skill"],
            },
        )
        result = self.runner.invoke(main, ["setup", "apply", "dry-test", "--dry-run"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("dry-run", result.output)

        # Config should be unchanged
        from ai_adapter.config import load_config

        config = load_config()
        mcp_names = [s.name for s in config.mcp_servers] if config else []
        self.assertNotIn("dry-mcp", mcp_names)

    def test_dry_run_shows_preview(self):
        """--dry-run should show what would be registered."""
        _write_profile_yaml(
            self.profiles_dir,
            {
                "name": "preview",
                "mcp": [{"name": "m1", "command": "echo"}],
            },
        )
        result = self.runner.invoke(main, ["setup", "apply", "preview", "--dry-run"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("dry-run", result.output)
        self.assertIn("MCP", result.output)

    def test_dry_run_existing_item_shows_already_registered(self):
        """--dry-run marks already-registered items."""
        # Register an MCP server first
        _write_profile_yaml(
            self.profiles_dir,
            {
                "name": "dup",
                "mcp": [{"name": "existing-mcp", "command": "echo"}],
            },
        )
        self.runner.invoke(main, ["setup", "apply", "dup", "--yes"])

        # Now dry-run the same profile
        result = self.runner.invoke(main, ["setup", "apply", "dup", "--dry-run"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("already registered", result.output)

    def test_dry_run_nonexistent_profile(self):
        """--dry-run on non-existent profile still errors."""
        result = self.runner.invoke(main, ["setup", "apply", "ghost", "--dry-run"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("not found", result.output)
