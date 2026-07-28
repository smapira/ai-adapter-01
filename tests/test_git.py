"""Tests for git.py."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ai_adapter.git import (
    GitError,
    add_all,
    commit,
    get_remotes,
    has_remote,
    init_repo,
    is_repo,
)


class TestGitFunctions(unittest.TestCase):
    """Tests for git operation wrapper (using mocks)."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    @patch("ai_adapter.git._run_git")
    def test_is_repo_true(self, mock_run_git):
        """Verify returns True for a Git repository."""
        mock_run_git.return_value.returncode = 0
        result = is_repo(self.test_path)
        self.assertTrue(result)
        mock_run_git.assert_called_once_with(["rev-parse", "--git-dir"], cwd=self.test_path)

    @patch("ai_adapter.git._run_git")
    def test_is_repo_false(self, mock_run_git):
        """Verify returns False for a non-Git directory."""
        mock_run_git.side_effect = GitError("not a git repository")
        result = is_repo(self.test_path)
        self.assertFalse(result)

    @patch("ai_adapter.git._run_git")
    def test_init_repo(self, mock_run_git):
        """Verify init_repo calls git init."""
        mock_run_git.return_value.returncode = 0
        init_repo(self.test_path)
        mock_run_git.assert_called_once_with(["init"], cwd=self.test_path)

    @patch("ai_adapter.git._run_git")
    def test_has_remote_true(self, mock_run_git):
        """Verify returns True when remote exists."""
        mock_run_git.return_value.stdout = "origin\tgit@github.com:user/repo.git (fetch)\n"
        mock_run_git.return_value.returncode = 0
        result = has_remote(self.test_path)
        self.assertTrue(result)

    @patch("ai_adapter.git._run_git")
    def test_has_remote_false(self, mock_run_git):
        """Verify returns False when no remote exists."""
        mock_run_git.return_value.stdout = ""
        mock_run_git.return_value.returncode = 0
        result = has_remote(self.test_path)
        self.assertFalse(result)

    @patch("ai_adapter.git._run_git")
    def test_add_all(self, mock_run_git):
        """Verify add_all calls git add -A."""
        # 1st: add -A success, 2nd: diff --cached --quiet (changes exist=exit code 1)
        mock_run_git.side_effect = [
            type("Result", (), {"returncode": 0})(),
            GitError("git diff --cached --quiet failed"),
        ]
        result = add_all(self.test_path)
        self.assertTrue(result)

    @patch("ai_adapter.git._run_git")
    def test_add_all_no_changes(self, mock_run_git):
        """Verify add_all returns False when no changes."""
        mock_run_git.side_effect = [
            type("Result", (), {"returncode": 0})(),
            type("Result", (), {"returncode": 0})(),
        ]
        result = add_all(self.test_path)
        self.assertFalse(result)

    @patch("ai_adapter.git._run_git")
    def test_commit(self, mock_run_git):
        """Verify commit calls git commit."""
        mock_run_git.return_value.returncode = 0
        commit(self.test_path, "test commit")
        mock_run_git.assert_called_once_with(["commit", "-m", "test commit"], cwd=self.test_path)

    @patch("ai_adapter.git._run_git")
    def test_get_remotes(self, mock_run_git):
        """Verify get_remotes returns the remote list."""
        mock_run_git.return_value.stdout = "origin\nupstream\n"
        mock_run_git.return_value.returncode = 0
        remotes = get_remotes(self.test_path)
        self.assertEqual(remotes, ["origin", "upstream"])


class TestGitRebaseDetection(unittest.TestCase):
    """Tests for rebase detection."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    @patch("ai_adapter.git._run_git")
    def test_is_rebasing_true(self, mock_run_git):
        """Verify returns True when rebase-apply exists."""
        from ai_adapter.git import is_rebasing

        git_dir = self.test_path / ".git"
        git_dir.mkdir()
        (git_dir / "rebase-apply").mkdir()
        # rev-parse returns absolute path of .git
        mock_run_git.return_value = type("R", (), {"stdout": str(git_dir), "returncode": 0})()
        self.assertTrue(is_rebasing(self.test_path))

    @patch("ai_adapter.git._run_git")
    def test_is_rebasing_false(self, mock_run_git):
        """Verify returns False for a normal repository."""
        from ai_adapter.git import is_rebasing

        git_dir = self.test_path / ".git"
        git_dir.mkdir()
        mock_run_git.return_value = type("R", (), {"stdout": str(git_dir), "returncode": 0})()
        self.assertFalse(is_rebasing(self.test_path))

    @patch("ai_adapter.git._run_git")
    def test_get_conflicted_files(self, mock_run_git):
        """Verify conflicted files list retrieval."""
        from ai_adapter.git import get_conflicted_files

        mock_run_git.return_value = type("R", (), {"stdout": "config.json\nagents/reviewer.md\n", "returncode": 0})()
        files = get_conflicted_files(self.test_path)
        self.assertEqual(files, ["config.json", "agents/reviewer.md"])

    @patch("ai_adapter.git._run_git")
    def test_get_conflicted_files_empty(self, mock_run_git):
        """Verify returns empty list when no conflicts."""
        from ai_adapter.git import get_conflicted_files

        # diff-filter=U outputs nothing
        mock_run_git.side_effect = GitError("no output")
        files = get_conflicted_files(self.test_path)
        self.assertEqual(files, [])
