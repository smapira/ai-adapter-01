"""opencode.py のテスト。"""

import json
import tempfile
import unittest
from pathlib import Path

from click.testing import CliRunner

from ai_adapter.cli import main
from ai_adapter.config import init


class TestOpencodeCommands(unittest.TestCase):
    """opencode サブコマンドのテスト。"""

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
        """opencode install で opencode.json が生成されることを確認する。"""
        # MCP サーバーを追加しておく
        self.runner.invoke(main, [
            "mcp", "add", "github",
            "--command", "npx",
            "--args", "@modelcontextprotocol/server-github",
            "--env-key", "GITHUB_TOKEN",
        ])

        result = self.runner.invoke(main, ["opencode", "install"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("opencode.json", result.output)

        output_path = Path.cwd() / "opencode.json"
        self.assertTrue(output_path.exists())
        with open(output_path) as f:
            data = json.load(f)
        self.assertIn("hooks", data)
        self.assertIn("github", data["hooks"])

        output_path.unlink()

    def test_opencode_uninstall(self):
        """opencode uninstall で opencode.json が削除されることを確認する。"""
        # 先にインストール
        output_path = Path.cwd() / "opencode.json"
        output_path.write_text("{}")

        result = self.runner.invoke(main, ["opencode", "uninstall"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("opencode.json", result.output)
        self.assertFalse(output_path.exists())

    def test_opencode_uninstall_not_found(self):
        """opencode.json がない状態で uninstall してもエラーにならない。"""
        result = self.runner.invoke(main, ["opencode", "uninstall"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("見つかりません", result.output)

    def test_opencode_alias_no_github(self):
        """.github がない状態で alias するとエラーになることを確認する。"""
        result = self.runner.invoke(main, ["opencode", "alias"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn(".github", result.output)

    def test_opencode_install_empty_config(self):
        """MCP サーバー未登録でも opencode.json が生成されることを確認する。"""
        result = self.runner.invoke(main, ["opencode", "install"])
        self.assertEqual(result.exit_code, 0)

        output_path = Path.cwd() / "opencode.json"
        self.assertTrue(output_path.exists())
        with open(output_path) as f:
            data = json.load(f)
        self.assertIn("hooks", data)

        output_path.unlink()
