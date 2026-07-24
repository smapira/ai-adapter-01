"""Tests for sync.py."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from ai_adapter.cli import main


class TestSyncCommand(unittest.TestCase):
    """Tests for the sync command."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.patch_home = Path(self.temp_dir.name)
        self.runner = CliRunner()

        import pathlib
        self._original_home = pathlib.Path.home
        pathlib.Path.home = staticmethod(lambda: self.patch_home)

        import ai_adapter.config as cfg
        cfg.AI_ADAPTER_DIR = self.patch_home / ".ai-adapter"

        # init
        from ai_adapter.config import init
        init()

    def tearDown(self):
        import pathlib
        pathlib.Path.home = staticmethod(self._original_home)
        import ai_adapter.config as cfg
        cfg.AI_ADAPTER_DIR = Path.home() / ".ai-adapter"
        self.temp_dir.cleanup()

    @patch("ai_adapter.sync.is_repo")
    @patch("ai_adapter.sync.has_remote")
    @patch("ai_adapter.sync.add_all")
    @patch("ai_adapter.sync.commit")
    @patch("ai_adapter.sync.get_current_branch")
    @patch("ai_adapter.sync.test_remote_connectivity")
    @patch("ai_adapter.sync.remote_branch_exists")
    @patch("ai_adapter.sync.pull_rebase")
    @patch("ai_adapter.sync.push")
    def test_sync_success(
        self,
        mock_push,
        mock_pull,
        mock_remote_branch_exists,
        mock_connectivity,
        mock_get_branch,
        mock_commit,
        mock_add_all,
        mock_has_remote,
        mock_is_repo,
    ):
        """Verify sync command executes successfully."""
        mock_is_repo.return_value = True
        mock_has_remote.return_value = True
        mock_add_all.return_value = False  # no changes
        mock_get_branch.return_value = "main"
        mock_connectivity.return_value = True
        mock_remote_branch_exists.return_value = True

        result = self.runner.invoke(main, ["sync"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Sync", result.output)
        mock_is_repo.assert_called_once()
        mock_has_remote.assert_called_once()
        mock_add_all.assert_called_once()
        mock_commit.assert_not_called()  # no changes
        mock_pull.assert_called_once()
        mock_push.assert_called_once()

    @patch("ai_adapter.sync.is_repo")
    @patch("ai_adapter.sync.has_remote")
    def test_sync_not_initialized(self, mock_has_remote, mock_is_repo):
        """Verify sync command shows init required message."""
        # Remove temp init directory to create uninitialized status
        import shutil
        shutil.rmtree(self.patch_home / ".ai-adapter")

        result = self.runner.invoke(main, ["sync"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("init", result.output)

    @patch("ai_adapter.sync._config.load_config")
    @patch("ai_adapter.sync.get_remotes")
    @patch("ai_adapter.sync.is_repo")
    @patch("ai_adapter.sync.has_remote")
    def test_sync_no_remote_skip(
        self, mock_has_remote, mock_is_repo, mock_get_remotes, mock_load_config,
    ):
        """Verify sync can be skipped when no remote is configured."""
        from ai_adapter.models import Config
        mock_is_repo.return_value = True
        mock_has_remote.return_value = False
        mock_get_remotes.return_value = []
        mock_load_config.return_value = Config()

        # Skip with Enter
        result = self.runner.invoke(main, ["sync"], input="\n")
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Skipping sync", result.output)
