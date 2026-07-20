"""env.py のテスト。"""

import tempfile
import unittest
from pathlib import Path

from click.testing import CliRunner

from ai_adapter.cli import main
from ai_adapter.config import init


class TestEnvCommands(unittest.TestCase):
    """env サブコマンドのテスト。"""

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
        """env list でデフォルト環境が表示されることを確認する。"""
        result = self.runner.invoke(main, ["env", "list"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("default", result.output)
        self.assertIn("*", result.output)  # デフォルトマーク

    def test_env_add(self):
        """env add で環境が追加されることを確認する。"""
        result = self.runner.invoke(main, ["env", "add", "myenv"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("myenv", result.output)

        # list で表示されるか
        result = self.runner.invoke(main, ["env", "list"])
        self.assertIn("myenv", result.output)

    def test_env_add_duplicate(self):
        """重複した環境名の追加でエラーになることを確認する。"""
        self.runner.invoke(main, ["env", "add", "myenv"])
        result = self.runner.invoke(main, ["env", "add", "myenv"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("既に存在", result.output)

    def test_env_remove(self):
        """env remove で環境が削除されることを確認する。"""
        self.runner.invoke(main, ["env", "add", "myenv"])
        result = self.runner.invoke(main, ["env", "remove", "myenv"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("myenv", result.output)

    def test_env_remove_default_fails(self):
        """デフォルト環境の削除がエラーになることを確認する。"""
        result = self.runner.invoke(main, ["env", "remove", "default"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("削除できません", result.output)

    def test_env_remove_nonexistent(self):
        """存在しない環境の削除でエラーになることを確認する。"""
        result = self.runner.invoke(main, ["env", "remove", "nonexistent"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("見つかりません", result.output)

    def test_env_default(self):
        """env default でデフォルト環境名が表示されることを確認する。"""
        result = self.runner.invoke(main, ["env", "default"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("default", result.output)

    def test_env_set_default(self):
        """env set-default でデフォルト環境が変更されることを確認する。"""
        self.runner.invoke(main, ["env", "add", "myenv"])
        result = self.runner.invoke(main, ["env", "set-default", "myenv"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("myenv", result.output)

        result = self.runner.invoke(main, ["env", "default"])
        self.assertIn("myenv", result.output)

    def test_env_set_default_nonexistent(self):
        """存在しない環境名の set-default でエラーになることを確認する。"""
        result = self.runner.invoke(main, ["env", "set-default", "nonexistent"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("見つかりません", result.output)

    def test_env_link_agent(self):
        """env link-agent でエージェントと環境の紐付けができることを確認する。"""
        self.runner.invoke(main, ["env", "add", "myenv"])
        result = self.runner.invoke(main, ["env", "link-agent", "reviewer", "myenv"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("reviewer", result.output)
        self.assertIn("myenv", result.output)

    def test_env_link_agent_nonexistent_env(self):
        """存在しない環境への link-agent でエラーになることを確認する。"""
        result = self.runner.invoke(main, ["env", "link-agent", "reviewer", "nonexistent"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("見つかりません", result.output)

    def test_env_unlink_agent(self):
        """env unlink-agent で紐付けが解除できることを確認する。"""
        self.runner.invoke(main, ["env", "add", "myenv"])
        self.runner.invoke(main, ["env", "link-agent", "reviewer", "myenv"])
        result = self.runner.invoke(main, ["env", "unlink-agent", "reviewer"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("reviewer", result.output)

    def test_env_unlink_agent_nonexistent(self):
        """存在しないエージェントの unlink-agent でエラーになることを確認する。"""
        result = self.runner.invoke(main, ["env", "unlink-agent", "nonexistent"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("見つかりません", result.output)
