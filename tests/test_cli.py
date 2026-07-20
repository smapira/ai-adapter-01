"""CLI 統合テスト。"""

import tempfile
import unittest
from pathlib import Path

from click.testing import CliRunner

from ai_adapter.cli import main


class TestCLIIntegration(unittest.TestCase):
    """CLI 全体の統合テスト。"""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.patch_home = Path(self.temp_dir.name)
        self.runner = CliRunner()

        import pathlib
        self._original_home = pathlib.Path.home
        pathlib.Path.home = staticmethod(lambda: self.patch_home)

        import ai_adapter.config as cfg
        cfg.AI_ADAPTER_DIR = self.patch_home / ".ai-adapter"

    def tearDown(self):
        import pathlib
        pathlib.Path.home = staticmethod(self._original_home)
        import ai_adapter.config as cfg
        cfg.AI_ADAPTER_DIR = Path.home() / ".ai-adapter"
        self.temp_dir.cleanup()

    def test_help(self):
        """--help が正常に表示されることを確認する。"""
        result = self.runner.invoke(main, ["--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("ai-adapter", result.output)
        self.assertIn("init", result.output)
        self.assertIn("status", result.output)
        self.assertIn("agent", result.output)
        self.assertIn("env", result.output)
        self.assertIn("bin", result.output)
        self.assertIn("sync", result.output)

    def test_version(self):
        """--version が表示されることを確認する。"""
        result = self.runner.invoke(main, ["--version"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("0.1.0", result.output)

    def test_init_and_status(self):
        """init → status の流れを確認する。"""
        # init
        result = self.runner.invoke(main, ["init"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("初期化", result.output)

        # status
        result = self.runner.invoke(main, ["status"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("状態", result.output)
        self.assertIn("default", result.output)

    def test_status_before_init(self):
        """init 前の status で適切なメッセージが表示されることを確認する。"""
        result = self.runner.invoke(main, ["status"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("初期化されていません", result.output)

    def test_agent_help(self):
        """agent --help が表示されることを確認する。"""
        result = self.runner.invoke(main, ["agent", "--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("list", result.output)
        self.assertIn("add", result.output)
        self.assertIn("get", result.output)
        self.assertIn("remove", result.output)

    def test_env_help(self):
        """env --help が表示されることを確認する。"""
        result = self.runner.invoke(main, ["env", "--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("list", result.output)
        self.assertIn("add", result.output)
        self.assertIn("remove", result.output)
        self.assertIn("default", result.output)
        self.assertIn("set-default", result.output)
        self.assertIn("link-agent", result.output)
        self.assertIn("unlink-agent", result.output)

    def test_bin_help(self):
        """bin --help が表示されることを確認する。"""
        result = self.runner.invoke(main, ["bin", "--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("list", result.output)
        self.assertIn("add", result.output)
        self.assertIn("get", result.output)
        self.assertIn("remove", result.output)
