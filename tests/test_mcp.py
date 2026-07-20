"""mcp.py のテスト。"""

import json
import tempfile
import unittest
from pathlib import Path

from click.testing import CliRunner

from ai_adapter.cli import main
from ai_adapter.config import init


class TestMCPCommands(unittest.TestCase):
    """mcp サブコマンドのテスト。"""

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

    def test_mcp_list_empty(self):
        """MCP 未登録時に空メッセージが表示されることを確認する。"""
        result = self.runner.invoke(main, ["mcp", "list"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("登録済みの MCP サーバーはありません", result.output)

    def test_mcp_add(self):
        """mcp add で MCP サーバーが追加されることを確認する。"""
        result = self.runner.invoke(main, [
            "mcp", "add", "github",
            "--command", "npx",
            "--args", "@modelcontextprotocol/server-github",
            "--env-key", "GITHUB_TOKEN",
            "--tool", "vscode",
            "--tool", "claude",
        ])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("github", result.output)

    def test_mcp_add_and_list(self):
        """mcp add → mcp list の流れを確認する。"""
        self.runner.invoke(main, [
            "mcp", "add", "github",
            "--command", "npx",
            "--args", "@modelcontextprotocol/server-github",
            "--env-key", "GITHUB_TOKEN",
        ])
        result = self.runner.invoke(main, ["mcp", "list"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("github", result.output)

    def test_mcp_add_duplicate(self):
        """重複した MCP サーバーの追加でエラーになることを確認する。"""
        self.runner.invoke(main, [
            "mcp", "add", "github",
            "--command", "npx",
            "--args", "@modelcontextprotocol/server-github",
        ])
        result = self.runner.invoke(main, [
            "mcp", "add", "github",
            "--command", "npx",
            "--args", "@modelcontextprotocol/server-github",
        ])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("既に存在", result.output)

    def test_mcp_remove(self):
        """mcp remove で MCP サーバーが削除されることを確認する。"""
        self.runner.invoke(main, [
            "mcp", "add", "github",
            "--command", "npx",
            "--args", "@modelcontextprotocol/server-github",
        ])
        result = self.runner.invoke(main, ["mcp", "remove", "github"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("github", result.output)

    def test_mcp_load(self):
        """mcp load --file で .mcp.json から一括読み込みできることを確認する。"""
        mcp_file = Path(self.temp_dir.name) / ".mcp.json"
        mcp_file.write_text(json.dumps({
            "mcpServers": {
                "github": {
                    "command": "npx",
                    "args": ["@modelcontextprotocol/server-github"],
                    "env": {"GITHUB_TOKEN": "${GITHOT_TOKEN}"},
                },
                "filesystem": {
                    "command": "npx",
                    "args": ["@modelcontextprotocol/server-filesystem", "."],
                },
            }
        }, indent=2))

        result = self.runner.invoke(main, [
            "mcp", "load", "--file", str(mcp_file),
        ])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("2件追加", result.output)

    def test_mcp_enable_disable(self):
        """mcp enable/disable で有効/無効が切り替わることを確認する。"""
        self.runner.invoke(main, [
            "mcp", "add", "github",
            "--command", "npx",
            "--args", "@modelcontextprotocol/server-github",
        ])

        # disable
        result = self.runner.invoke(main, ["mcp", "disable", "github"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("無効化", result.output)

        # enable
        result = self.runner.invoke(main, ["mcp", "enable", "github"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("有効化", result.output)

    def test_mcp_export(self):
        """mcp export で .mcp.json が出力されることを確認する。"""
        self.runner.invoke(main, [
            "mcp", "add", "github",
            "--command", "npx",
            "--args", "@modelcontextprotocol/server-github",
            "--env-key", "GITHUB_TOKEN",
            "--tool", "vscode",
        ])

        result = self.runner.invoke(main, ["mcp", "export"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn(".mcp.json", result.output)

        # カレントディレクトリに .mcp.json が出力される
        output_path = Path.cwd() / ".mcp.json"
        self.assertTrue(output_path.exists())
        with open(output_path) as f:
            data = json.load(f)
        self.assertIn("github", data["mcpServers"])

        output_path.unlink()

    def test_mcp_export_with_path(self):
        """mcp export --path で指定ディレクトリに出力されることを確認する。"""
        self.runner.invoke(main, [
            "mcp", "add", "github",
            "--command", "npx",
            "--args", "@modelcontextprotocol/server-github",
        ])

        export_dir = Path(self.temp_dir.name) / "my-project"
        export_dir.mkdir(parents=True)

        result = self.runner.invoke(main, ["mcp", "export", "--path", str(export_dir)])
        self.assertEqual(result.exit_code, 0)
        self.assertTrue((export_dir / ".mcp.json").exists())
