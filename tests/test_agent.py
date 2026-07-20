"""agent.py のテスト。"""

import os
import tempfile
import unittest
from pathlib import Path

from click.testing import CliRunner

from ai_adapter.cli import main
from ai_adapter.config import init
from ai_adapter.models import Agent, Config, Env


class TestAgentCommands(unittest.TestCase):
    """agent サブコマンドのテスト。"""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.patch_home = Path(self.temp_dir.name)
        self.runner = CliRunner()

        # Home 差し替え
        import pathlib
        self._original_home = pathlib.Path.home
        pathlib.Path.home = staticmethod(lambda: self.patch_home)

        import ai_adapter.config as cfg
        cfg.AI_ADAPTER_DIR = self.patch_home / ".ai-adapter"

        # init
        init()

        # テスト用エージェントファイル作成
        self.agent_file = Path(self.temp_dir.name) / "test-agent.md"
        self.agent_file.write_text("# Test Agent\nThis is a test agent.")

    def tearDown(self):
        import pathlib
        pathlib.Path.home = staticmethod(self._original_home)
        import ai_adapter.config as cfg
        cfg.AI_ADAPTER_DIR = Path.home() / ".ai-adapter"
        self.temp_dir.cleanup()

    def test_agent_list_empty(self):
        """エージェント未登録時に空メッセージが表示されることを確認する。"""
        result = self.runner.invoke(main, ["agent", "list"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("登録済みのエージェントはありません", result.output)

    def test_agent_add(self):
        """agent add でエージェントが追加されることを確認する。"""
        result = self.runner.invoke(main, ["agent", "add", str(self.agent_file)])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("test-agent", result.output)

        # ファイルがコピーされたか確認
        agents_dir = self.patch_home / ".ai-adapter" / "agents"
        self.assertTrue((agents_dir / "test-agent.md").exists())

    def test_agent_add_and_list(self):
        """agent add → agent list の流れを確認する。"""
        self.runner.invoke(main, ["agent", "add", str(self.agent_file)])
        result = self.runner.invoke(main, ["agent", "list"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("test-agent", result.output)

    def test_agent_get(self):
        """agent get で .github/agents/ にコピーされることを確認する。"""
        self.runner.invoke(main, ["agent", "add", str(self.agent_file)])

        # カレントディレクトリに .github/agents/ を作成（一時ディレクトリ内）
        github_agents = Path.cwd() / ".github" / "agents"
        github_agents.mkdir(parents=True, exist_ok=True)

        result = self.runner.invoke(main, ["agent", "get", "test-agent"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("test-agent.md", result.output)
        self.assertTrue((github_agents / "test-agent.md").exists())

        # クリーンアップ
        import shutil
        shutil.rmtree(Path.cwd() / ".github", ignore_errors=True)

    def test_agent_get_not_found(self):
        """存在しないエージェントの get でエラーになることを確認する。"""
        result = self.runner.invoke(main, ["agent", "get", "nonexistent"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("見つかりません", result.output)

    def test_agent_remove(self):
        """agent remove でエージェントが削除されることを確認する。"""
        self.runner.invoke(main, ["agent", "add", str(self.agent_file)])
        result = self.runner.invoke(main, ["agent", "remove", "test-agent"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("test-agent", result.output)

        # list で表示されないことを確認
        result = self.runner.invoke(main, ["agent", "list"])
        self.assertIn("登録済みのエージェントはありません", result.output)
