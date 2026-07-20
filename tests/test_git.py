"""git.py のテスト。"""

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
    pull_rebase,
    push,
)


class TestGitFunctions(unittest.TestCase):
    """git 操作ラッパーのテスト（モック使用）。"""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    @patch("ai_adapter.git._run_git")
    def test_is_repo_true(self, mock_run_git):
        """Git リポジトリの場合 True を返すことを確認する。"""
        mock_run_git.return_value.returncode = 0
        result = is_repo(self.test_path)
        self.assertTrue(result)
        mock_run_git.assert_called_once_with(
            ["rev-parse", "--git-dir"], cwd=self.test_path
        )

    @patch("ai_adapter.git._run_git")
    def test_is_repo_false(self, mock_run_git):
        """Git リポジトリでない場合 False を返すことを確認する。"""
        mock_run_git.side_effect = GitError("not a git repository")
        result = is_repo(self.test_path)
        self.assertFalse(result)

    @patch("ai_adapter.git._run_git")
    def test_init_repo(self, mock_run_git):
        """init_repo が git init を呼ぶことを確認する。"""
        mock_run_git.return_value.returncode = 0
        init_repo(self.test_path)
        mock_run_git.assert_called_once_with(
            ["init"], cwd=self.test_path
        )

    @patch("ai_adapter.git._run_git")
    def test_has_remote_true(self, mock_run_git):
        """リモートがある場合 True を返すことを確認する。"""
        mock_run_git.return_value.stdout = "origin\tgit@github.com:user/repo.git (fetch)\n"
        mock_run_git.return_value.returncode = 0
        result = has_remote(self.test_path)
        self.assertTrue(result)

    @patch("ai_adapter.git._run_git")
    def test_has_remote_false(self, mock_run_git):
        """リモートがない場合 False を返すことを確認する。"""
        mock_run_git.return_value.stdout = ""
        mock_run_git.return_value.returncode = 0
        result = has_remote(self.test_path)
        self.assertFalse(result)

    @patch("ai_adapter.git._run_git")
    def test_add_all(self, mock_run_git):
        """add_all が git add -A を呼ぶことを確認する。"""
        # 1回目: add -A, 2回目: diff --cached --quiet (変更あり=returncode 1)
        mock_run_git.side_effect = [
            type("Result", (), {"returncode": 0})(),
            type("Result", (), {"returncode": 1})(),
        ]
        result = add_all(self.test_path)
        self.assertTrue(result)

    @patch("ai_adapter.git._run_git")
    def test_add_all_no_changes(self, mock_run_git):
        """変更がない場合 add_all が False を返すことを確認する。"""
        mock_run_git.side_effect = [
            type("Result", (), {"returncode": 0})(),
            type("Result", (), {"returncode": 0})(),
        ]
        result = add_all(self.test_path)
        self.assertFalse(result)

    @patch("ai_adapter.git._run_git")
    def test_commit(self, mock_run_git):
        """commit が git commit を呼ぶことを確認する。"""
        mock_run_git.return_value.returncode = 0
        commit(self.test_path, "test commit")
        mock_run_git.assert_called_once_with(
            ["commit", "-m", "test commit"], cwd=self.test_path
        )

    @patch("ai_adapter.git._run_git")
    def test_get_remotes(self, mock_run_git):
        """get_remotes がリモート一覧を返すことを確認する。"""
        mock_run_git.return_value.stdout = "origin\nupstream\n"
        mock_run_git.return_value.returncode = 0
        remotes = get_remotes(self.test_path)
        self.assertEqual(remotes, ["origin", "upstream"])
