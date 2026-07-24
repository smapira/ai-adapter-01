"""Tests for mcp.py."""

import json
import tempfile
import unittest
from pathlib import Path

from click.testing import CliRunner

from ai_adapter.cli import main
from ai_adapter.config import init


class TestMCPCommands(unittest.TestCase):
    """Tests for mcp subcommands."""

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
        """Verify empty message is shown when no MCP servers registered."""
        result = self.runner.invoke(main, ["mcp", "list"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("No MCP servers registered.", result.output)

    def test_mcp_add(self):
        """Verify mcp add adds an MCP server."""
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
        """Verify mcp add → mcp list flow."""
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
        """Verify duplicate MCP server name raises error."""
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
        self.assertIn("already exists", result.output)

    def test_mcp_remove(self):
        """Verify mcp remove removes an MCP server."""
        self.runner.invoke(main, [
            "mcp", "add", "github",
            "--command", "npx",
            "--args", "@modelcontextprotocol/server-github",
        ])
        result = self.runner.invoke(main, ["mcp", "remove", "github"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("github", result.output)

    def test_mcp_add_bulk(self):
        """Verify mcp add --file imports from .mcp.json."""
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
            "mcp", "add", "--file", str(mcp_file),
        ])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("imported", result.output.lower())

    def test_mcp_get(self):
        """Verify mcp get outputs .mcp.json."""
        self.runner.invoke(main, [
            "mcp", "add", "github",
            "--command", "npx",
            "--args", "@modelcontextprotocol/server-github",
            "--env-key", "GITHUB_TOKEN",
            "--tool", "vscode",
        ])

        result = self.runner.invoke(main, ["mcp", "get"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn(".mcp.json", result.output)

        # .mcp.json is output to the current directory
        output_path = Path.cwd() / ".mcp.json"
        self.assertTrue(output_path.exists())
        with open(output_path) as f:
            data = json.load(f)
        self.assertIn("github", data["mcpServers"])

        output_path.unlink()

    def test_mcp_get_with_path(self):
        """Verify mcp get --path outputs to specified directory."""
        self.runner.invoke(main, [
            "mcp", "add", "github",
            "--command", "npx",
            "--args", "@modelcontextprotocol/server-github",
        ])

        export_dir = Path(self.temp_dir.name) / "my-project"
        export_dir.mkdir(parents=True)

        result = self.runner.invoke(main, ["mcp", "get", "--path", str(export_dir)])
        self.assertEqual(result.exit_code, 0)
        self.assertTrue((export_dir / ".mcp.json").exists())
