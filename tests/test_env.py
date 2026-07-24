"""Tests for env.py."""

import tempfile
import unittest
from pathlib import Path

from click.testing import CliRunner

from ai_adapter.cli import main
from ai_adapter.config import init


class TestEnvCommands(unittest.TestCase):
    """Tests for env subcommands."""

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

    def test_env_list_default(self):
        """Verify env list shows default environment."""
        result = self.runner.invoke(main, ["env", "list"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("default", result.output)
        self.assertIn("*", result.output)  # default mark

    def test_env_add(self):
        """Verify env add adds an environment."""
        result = self.runner.invoke(main, ["env", "add", "myenv"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("myenv", result.output)

        # Verify it is displayed via list
        result = self.runner.invoke(main, ["env", "list"])
        self.assertIn("myenv", result.output)

    def test_env_add_duplicate(self):
        """Verify duplicate env name raises error."""
        self.runner.invoke(main, ["env", "add", "myenv"])
        result = self.runner.invoke(main, ["env", "add", "myenv"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("already exists", result.output)

    def test_env_remove(self):
        """Verify env remove removes an environment."""
        self.runner.invoke(main, ["env", "add", "myenv"])
        result = self.runner.invoke(main, ["env", "remove", "myenv"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("myenv", result.output)

    def test_env_remove_default_fails(self):
        """Verify removing default environment raises error."""
        result = self.runner.invoke(main, ["env", "remove", "default"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("cannot be removed", result.output)

    def test_env_remove_nonexistent(self):
        """Verify removing non-existent environment raises error."""
        result = self.runner.invoke(main, ["env", "remove", "nonexistent"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("not found", result.output)

    def test_env_default(self):
        """Verify env default shows the default environment name."""
        result = self.runner.invoke(main, ["env", "default"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("default", result.output)

    def test_env_set_default(self):
        """Verify env set-default changes the default environment."""
        self.runner.invoke(main, ["env", "add", "myenv"])
        result = self.runner.invoke(main, ["env", "set-default", "myenv"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("myenv", result.output)

        result = self.runner.invoke(main, ["env", "default"])
        self.assertIn("myenv", result.output)

    def test_env_set_default_nonexistent(self):
        """Verify set-default fails for non-existent env name."""
        result = self.runner.invoke(main, ["env", "set-default", "nonexistent"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("not found", result.output)

    def test_env_link_agent(self):
        """Verify env link-agent binds agent to environment."""
        self.runner.invoke(main, ["env", "add", "myenv"])
        result = self.runner.invoke(main, ["env", "link-agent", "reviewer", "myenv"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("reviewer", result.output)
        self.assertIn("myenv", result.output)

    def test_env_link_agent_nonexistent_env(self):
        """Verify link-agent fails for non-existent environment."""
        result = self.runner.invoke(main, ["env", "link-agent", "reviewer", "nonexistent"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("not found", result.output)

    def test_env_unlink_agent(self):
        """Verify env unlink-agent unbinds agent from environment."""
        self.runner.invoke(main, ["env", "add", "myenv"])
        self.runner.invoke(main, ["env", "link-agent", "reviewer", "myenv"])
        result = self.runner.invoke(main, ["env", "unlink-agent", "reviewer"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("reviewer", result.output)

    def test_env_unlink_agent_nonexistent(self):
        """Verify unlink-agent fails for non-existent agent."""
        result = self.runner.invoke(main, ["env", "unlink-agent", "nonexistent"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("not found", result.output)

    def test_env_remove_all(self):
        """Verify env remove-all removes all environments except default."""
        self.runner.invoke(main, ["env", "add", "myenv"])
        self.runner.invoke(main, ["env", "add", "otherenv"])

        result = self.runner.invoke(main, ["env", "remove-all", "--force"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("All environments", result.output)
        self.assertIn("default", result.output)

        # Only default remains
        result = self.runner.invoke(main, ["env", "list"])
        self.assertIn("default", result.output)
        self.assertNotIn("myenv", result.output)
