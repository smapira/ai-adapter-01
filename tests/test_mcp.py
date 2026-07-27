"""Tests for mcp.py."""

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

from click.testing import CliRunner

from ai_adapter.cli import main
from ai_adapter.config import init
from ai_adapter.models import MCPServer
from ai_adapter.providers.openclaw import export_mcp, merge_into_openclaw_json

# ── Test fixture servers (from plan's BDD scenarios) ──

SERVER_GITHUB = MCPServer(
    name="github",
    command="npx",
    args=["@modelcontextprotocol/server-github"],
    env_keys=["GITHUB_TOKEN"],
    enabled=True,
)

SERVER_PLAYWRIGHT = MCPServer(
    name="playwright",
    command="npx",
    args=["@playwright/mcp@latest"],
    env_keys=[],
    enabled=True,
)

SERVER_NO_ARGS = MCPServer(
    name="no-args",
    command="/usr/bin/python",
    args=[],
    env_keys=["API_KEY"],
    enabled=True,
)

SERVER_DISABLED = MCPServer(
    name="legacy-db",
    command="/usr/bin/python",
    args=["server.py"],
    env_keys=["DB_URL"],
    enabled=False,
)

SERVER_INVALID_ENV_KEY = MCPServer(
    name="bad-env",
    command="node",
    args=["server.js"],
    env_keys=["myApiKey"],  # lowercase camelCase → warning target
    enabled=True,
)


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


class TestOpenClawMCPExport(unittest.TestCase):
    """Tests for OpenClaw MCP export functionality."""

    # ── Unit tests for providers.openclaw.export_mcp() ──

    def test_export_openclaw_basic(self):
        """4 servers (normal, empty env, empty args, disabled) → correct output."""
        result = export_mcp([
            SERVER_GITHUB, SERVER_PLAYWRIGHT, SERVER_NO_ARGS, SERVER_DISABLED,
        ])
        # x-ai-adapter marker with managed names (disabled excluded)
        self.assertIn("x-ai-adapter", result)
        self.assertEqual(
            result["x-ai-adapter"]["managed_mcp_servers"],
            ["github", "playwright", "no-args"],
        )
        # Disabled server excluded from servers dict
        self.assertNotIn("legacy-db", result["mcp"]["servers"])
        # GitHub: has env
        self.assertIn("env", result["mcp"]["servers"]["github"])
        self.assertEqual(
            result["mcp"]["servers"]["github"]["env"]["GITHUB_TOKEN"],
            "${GITHUB_TOKEN}",
        )
        # Playwright: empty env → key omitted
        self.assertNotIn("env", result["mcp"]["servers"]["playwright"])
        # No-args: empty args → key omitted
        self.assertNotIn("args", result["mcp"]["servers"]["no-args"])

    def test_export_openclaw_disabled_excluded(self):
        """Only disabled servers → empty mcp.servers and empty managed list."""
        result = export_mcp([SERVER_DISABLED])
        self.assertEqual(result["mcp"]["servers"], {})
        self.assertEqual(result["x-ai-adapter"]["managed_mcp_servers"], [])

    def test_export_openclaw_empty_env_omitted(self):
        """Empty env_keys → no env key in output entry."""
        result = export_mcp([SERVER_PLAYWRIGHT])
        self.assertNotIn("env", result["mcp"]["servers"]["playwright"])

    def test_export_openclaw_empty_args_omitted(self):
        """Empty args → no args key in output entry."""
        result = export_mcp([SERVER_NO_ARGS])
        self.assertNotIn("args", result["mcp"]["servers"]["no-args"])

    def test_export_openclaw_invalid_env_key_warning(self):
        """Invalid env key name emits warning on stderr but still produces output."""
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            result = export_mcp([SERVER_INVALID_ENV_KEY])
        self.assertIn("Warning:", stderr.getvalue())
        self.assertIn("myApiKey", stderr.getvalue())
        # Output still produced despite warning
        self.assertIn("bad-env", result["mcp"]["servers"])

    def test_export_openclaw_x_ai_adapter_marker(self):
        """x-ai-adapter marker has correct version and managed names."""
        result = export_mcp([SERVER_GITHUB])
        self.assertEqual(result["x-ai-adapter"]["version"], 1)
        self.assertEqual(result["x-ai-adapter"]["managed_mcp_servers"], ["github"])

    # ── Unit tests for merge_into_openclaw_json() ──

    def test_merge_into_openclaw_new_file(self):
        """No existing file → creates new openclaw.json with correct content."""
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "openclaw.json"
            data = export_mcp([SERVER_GITHUB])
            merge_into_openclaw_json(output_path, data, force=True)

            self.assertTrue(output_path.exists())
            with open(output_path) as f:
                result = json.load(f)
            self.assertIn("github", result["mcp"]["servers"])
            self.assertEqual(
                result["x-ai-adapter"]["managed_mcp_servers"],
                ["github"],
            )

    def test_merge_into_openclaw_merge(self):
        """Existing unmanaged servers preserved; same-name servers overwritten; backup created."""
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "openclaw.json"

            # Create existing file with a server NOT managed by ai-adapter
            existing_data = {
                "mcp": {
                    "servers": {
                        "existing-server": {
                            "enabled": True,
                            "command": "legacy",
                        },
                    },
                },
            }
            with open(output_path, "w") as f:
                json.dump(existing_data, f, indent=2)

            # Merge with ai-adapter's github server
            data = export_mcp([SERVER_GITHUB])
            merge_into_openclaw_json(output_path, data, force=True)

            with open(output_path) as f:
                result = json.load(f)

            # Existing unmanaged server preserved
            self.assertIn("existing-server", result["mcp"]["servers"])
            # New server added
            self.assertIn("github", result["mcp"]["servers"])
            # x-ai-adapter marker only lists managed servers
            self.assertEqual(
                result["x-ai-adapter"]["managed_mcp_servers"],
                ["github"],
            )
            # Backup file created
            bak_path = output_path.with_suffix(output_path.suffix + ".bak")
            self.assertTrue(bak_path.exists())

    # ── CLI integration tests ──

    def setUp(self):
        """Set up patched home directory and initialize config."""
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
        """Restore original home directory and clean up."""
        import pathlib
        pathlib.Path.home = staticmethod(self._original_home)
        import ai_adapter.config as cfg
        cfg.AI_ADAPTER_DIR = Path.home() / ".ai-adapter"
        self.temp_dir.cleanup()

    def _add_server(self, name, command, args=None, env_keys=None):
        """Helper: add an MCP server via CLI."""
        cmd = ["mcp", "add", name, "--command", command]
        if args:
            for a in args:
                cmd.extend(["--args", a])
        if env_keys:
            for k in env_keys:
                cmd.extend(["--env-key", k])
        return self.runner.invoke(main, cmd)

    def test_cli_mcp_get_openclaw(self):
        """CLI: --format openclaw writes openclaw.json with correct structure."""
        # Add 3 enabled servers (disabled server tested in unit tests)
        self._add_server("github", "npx",
                         args=["@modelcontextprotocol/server-github"],
                         env_keys=["GITHUB_TOKEN"])
        self._add_server("playwright", "npx",
                         args=["@playwright/mcp@latest"])
        self._add_server("no-args", "/usr/bin/python",
                         env_keys=["API_KEY"])

        export_dir = Path(self.temp_dir.name) / "openclaw-out"
        export_dir.mkdir(parents=True, exist_ok=True)

        result = self.runner.invoke(main, [
            "mcp", "get", "--format", "openclaw", "--path", str(export_dir),
        ])
        self.assertEqual(result.exit_code, 0)

        output_path = export_dir / "openclaw.json"
        self.assertTrue(output_path.exists())

        with open(output_path) as f:
            data = json.load(f)

        # Top-level structure
        self.assertIn("x-ai-adapter", data)
        self.assertIn("mcp", data)
        servers = data["mcp"]["servers"]

        # All 3 enabled servers present
        self.assertIn("github", servers)
        self.assertIn("playwright", servers)
        self.assertIn("no-args", servers)

        # GitHub has env
        self.assertIn("env", servers["github"])
        self.assertEqual(servers["github"]["env"]["GITHUB_TOKEN"], "${GITHUB_TOKEN}")

        # Playwright (empty env_keys) → no env key
        self.assertNotIn("env", servers["playwright"])

        # No-args (empty args) → no args key
        self.assertNotIn("args", servers["no-args"])

    def test_cli_mcp_get_standard_still_works(self):
        """CLI: default format (standard) still produces .mcp.json (backward compat)."""
        self._add_server("github", "npx",
                         args=["@modelcontextprotocol/server-github"])

        # Default invocation (no --format) → standard
        result = self.runner.invoke(main, ["mcp", "get"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn(".mcp.json", result.output)

        output_path = Path.cwd() / ".mcp.json"
        self.assertTrue(output_path.exists())
        with open(output_path) as f:
            data = json.load(f)
        self.assertIn("mcpServers", data)
        self.assertIn("github", data["mcpServers"])
        output_path.unlink(missing_ok=True)

        # Explicit --format standard
        result2 = self.runner.invoke(main, ["mcp", "get", "--format", "standard"])
        self.assertEqual(result2.exit_code, 0)

    def test_cli_mcp_get_openclaw_not_installed(self):
        """CLI: no ~/.openclaw/ dir → warning on stderr, still writes to CWD."""
        # Ensure ~/.openclaw/ does NOT exist in the patched home
        self.assertFalse((self.patch_home / ".openclaw").exists())

        self._add_server("github", "npx",
                         args=["@modelcontextprotocol/server-github"])

        # Change CWD to an isolated temp dir so we don't pollute the real project
        old_cwd = os.getcwd()
        tmp_cwd = Path(self.temp_dir.name) / "cwd"
        tmp_cwd.mkdir(parents=True, exist_ok=True)
        os.chdir(str(tmp_cwd))
        try:
            result = self.runner.invoke(main, ["mcp", "get", "--format", "openclaw"])
            self.assertEqual(result.exit_code, 0)
            # Warning should be present in output (stderr)
            self.assertIn("Warning: OpenClaw not found", result.output)
            # File written to current working directory
            self.assertTrue((tmp_cwd / "openclaw.json").exists())
        finally:
            os.chdir(old_cwd)

    def test_cli_mcp_get_no_servers(self):
        """CLI: no enabled servers → error message, no file output."""
        # No servers added at all
        result = self.runner.invoke(main, ["mcp", "get", "--format", "openclaw"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("No enabled MCP servers registered.", result.output)
        # No file should be created in CWD
        self.assertFalse(Path.cwd().joinpath("openclaw.json").exists())

    def test_cli_mcp_get_force_overwrite(self):
        """CLI: --format openclaw --force overwrites without confirmation prompt."""
        self._add_server("github", "npx",
                         args=["@modelcontextprotocol/server-github"])

        export_dir = Path(self.temp_dir.name) / "force-out"
        export_dir.mkdir(parents=True, exist_ok=True)

        # First write: creates new file (with --force, no confirm needed)
        result1 = self.runner.invoke(main, [
            "mcp", "get", "--format", "openclaw",
            "--path", str(export_dir), "--force",
        ])
        self.assertEqual(result1.exit_code, 0)
        output_path = export_dir / "openclaw.json"
        self.assertTrue(output_path.exists())

        # Second write with --force: overwrites existing without prompt
        result2 = self.runner.invoke(main, [
            "mcp", "get", "--format", "openclaw",
            "--path", str(export_dir), "--force",
        ])
        self.assertEqual(result2.exit_code, 0)

        # Verify content is still valid
        with open(output_path) as f:
            data = json.load(f)
        self.assertIn("github", data["mcp"]["servers"])
