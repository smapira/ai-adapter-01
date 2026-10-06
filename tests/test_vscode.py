"""Tests for the VS Code provider (design 08).

Covers:
- ``vscode install`` → .vscode/mcp.json generation (servers + type: stdio)
- ``vscode install`` merge with .bak backup and unmanaged-server preservation
- ``vscode extension add`` / ``list`` → .vscode/extensions.json management
- ``vscode validate`` → JSON parse + schema checks, --json output
- ``mcp get --format vscode`` → .vscode/mcp.json via the mcp command
- export_mcp unit tests (env syntax, non-stdio skip)
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from click.testing import CliRunner

from ai_adapter.cli import main
from ai_adapter.config import init
from ai_adapter.models import MCPServer
from ai_adapter.providers.vscode import export_mcp, validate_extensions, validate_vscode_mcp


class _VscodeTestBase(unittest.TestCase):
    """Shared setUp/tearDown: isolated HOME + ai-adapter store."""

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

        self.project_dir = Path(self.temp_dir.name) / "proj"
        self.project_dir.mkdir(parents=True)

    def tearDown(self):
        import pathlib

        pathlib.Path.home = staticmethod(self._original_home)
        import ai_adapter.config as cfg

        cfg.AI_ADAPTER_DIR = Path.home() / ".ai-adapter"
        self.temp_dir.cleanup()

    def _add_mcp_server(
        self,
        name: str = "github",
        command: str = "npx",
        args: list[str] | None = None,
        env_keys: list[str] | None = None,
    ) -> None:
        """Register an MCP server via the CLI (mcp add has no --project-dir)."""
        cmd = ["mcp", "add", name, "--command", command]
        for a in args or []:
            cmd += ["--args", a]
        for e in env_keys or []:
            cmd += ["--env-key", e]
        result = self.runner.invoke(main, cmd)
        self.assertEqual(result.exit_code, 0, result.output)


class TestVscodeInstall(_VscodeTestBase):
    """vscode install → .vscode/mcp.json generation."""

    def test_install_creates_mcp_json(self):
        """AC1: .vscode/mcp.json is generated with servers + type: stdio."""
        self._add_mcp_server("github", "npx", ["-y", "@modelcontextprotocol/server-github"], ["GITHUB_TOKEN"])
        result = self.runner.invoke(main, ["vscode", "install", "--project-dir", str(self.project_dir)])
        self.assertEqual(result.exit_code, 0, result.output)
        mcp_path = self.project_dir / ".vscode" / "mcp.json"
        self.assertTrue(mcp_path.exists())
        data = json.loads(mcp_path.read_text())
        self.assertIn("servers", data)
        self.assertIn("github", data["servers"])
        entry = data["servers"]["github"]
        self.assertEqual(entry["type"], "stdio")
        self.assertEqual(entry["command"], "npx")
        self.assertEqual(entry["args"], ["-y", "@modelcontextprotocol/server-github"])
        # AC5: env uses ${env:KEY} syntax
        self.assertEqual(entry["env"], {"GITHUB_TOKEN": "${env:GITHUB_TOKEN}"})

    def test_install_no_servers(self):
        """Empty store → 'No MCP servers registered.'"""
        result = self.runner.invoke(main, ["vscode", "install", "--project-dir", str(self.project_dir)])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("No MCP servers registered.", result.output)

    def test_install_merge_preserves_unmanaged(self):
        """AC3: merge preserves servers not managed by ai-adapter."""
        self._add_mcp_server("github", "npx", ["-y", "@modelcontextprotocol/server-github"])
        # Pre-existing mcp.json with an unmanaged server
        mcp_path = self.project_dir / ".vscode" / "mcp.json"
        mcp_path.parent.mkdir(parents=True, exist_ok=True)
        mcp_path.write_text(
            json.dumps({"servers": {"my-own": {"type": "stdio", "command": "python", "args": ["server.py"]}}})
        )
        result = self.runner.invoke(main, ["vscode", "install", "--project-dir", str(self.project_dir), "--force"])
        self.assertEqual(result.exit_code, 0, result.output)
        data = json.loads(mcp_path.read_text())
        self.assertIn("github", data["servers"])
        self.assertIn("my-own", data["servers"])

    def test_install_backup_created(self):
        """AC2: merge writes a .bak backup before modifying."""
        self._add_mcp_server("github", "npx", ["-y", "@modelcontextprotocol/server-github"])
        mcp_path = self.project_dir / ".vscode" / "mcp.json"
        mcp_path.parent.mkdir(parents=True, exist_ok=True)
        mcp_path.write_text(json.dumps({"servers": {"old": {"type": "stdio", "command": "x"}}}))
        self.runner.invoke(main, ["vscode", "install", "--project-dir", str(self.project_dir), "--force"])
        self.assertTrue(mcp_path.with_suffix(".json.bak").exists())

    def test_install_skips_non_stdio(self):
        """AC4: servers with no command are skipped with a warning."""
        self._add_mcp_server("github", "npx", ["-y", "pkg"])
        # Manually add a server with empty command (simulating http/sse)
        import ai_adapter.config as cfg

        config = cfg.load_config()
        config.mcp_servers.append(MCPServer(name="http-server", command="", enabled=True))
        cfg.save_config(config)
        result = self.runner.invoke(main, ["vscode", "install", "--project-dir", str(self.project_dir)])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("skipping non-stdio", result.output)
        mcp_path = self.project_dir / ".vscode" / "mcp.json"
        data = json.loads(mcp_path.read_text())
        self.assertIn("github", data["servers"])
        self.assertNotIn("http-server", data["servers"])


class TestVscodeExtensionAdd(_VscodeTestBase):
    """vscode extension add / list → .vscode/extensions.json."""

    def test_extension_add_creates_file(self):
        """AC1: extensions.json is created when missing."""
        result = self.runner.invoke(
            main, ["vscode", "extension", "add", "ms-vscode.copilot-chat", "--project-dir", str(self.project_dir)]
        )
        self.assertEqual(result.exit_code, 0, result.output)
        ext_path = self.project_dir / ".vscode" / "extensions.json"
        self.assertTrue(ext_path.exists())
        data = json.loads(ext_path.read_text())
        self.assertEqual(data["recommendations"], ["ms-vscode.copilot-chat"])

    def test_extension_add_duplicate(self):
        """AC2: duplicate extensions are not added twice."""
        self.runner.invoke(
            main, ["vscode", "extension", "add", "ms-vscode.copilot-chat", "--project-dir", str(self.project_dir)]
        )
        result = self.runner.invoke(
            main, ["vscode", "extension", "add", "ms-vscode.copilot-chat", "--project-dir", str(self.project_dir)]
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Extension already recommended.", result.output)
        ext_path = self.project_dir / ".vscode" / "extensions.json"
        data = json.loads(ext_path.read_text())
        self.assertEqual(len(data["recommendations"]), 1)

    def test_extension_add_preserves_existing(self):
        """AC3: existing recommendations are preserved."""
        ext_path = self.project_dir / ".vscode" / "extensions.json"
        ext_path.parent.mkdir(parents=True, exist_ok=True)
        ext_path.write_text(json.dumps({"recommendations": ["existing.ext"]}))
        self.runner.invoke(main, ["vscode", "extension", "add", "new.ext", "--project-dir", str(self.project_dir)])
        data = json.loads(ext_path.read_text())
        self.assertIn("existing.ext", data["recommendations"])
        self.assertIn("new.ext", data["recommendations"])

    def test_extension_list(self):
        """extension list shows recommendations."""
        self.runner.invoke(
            main, ["vscode", "extension", "add", "ms-vscode.copilot-chat", "--project-dir", str(self.project_dir)]
        )
        result = self.runner.invoke(main, ["vscode", "extension", "list", "--project-dir", str(self.project_dir)])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("ms-vscode.copilot-chat", result.output)


class TestVscodeValidate(_VscodeTestBase):
    """vscode validate → JSON parse + schema checks."""

    def test_validate_valid_config(self):
        """AC1: valid config → 'VS Code configuration is valid.'"""
        mcp_path = self.project_dir / ".vscode" / "mcp.json"
        mcp_path.parent.mkdir(parents=True, exist_ok=True)
        mcp_path.write_text(json.dumps({"servers": {"github": {"type": "stdio", "command": "npx"}}}))
        ext_path = self.project_dir / ".vscode" / "extensions.json"
        ext_path.write_text(json.dumps({"recommendations": ["ms-vscode.copilot-chat"]}))
        result = self.runner.invoke(main, ["vscode", "validate", "--project-dir", str(self.project_dir)])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("VS Code configuration is valid.", result.output)

    def test_validate_broken_mcp_json(self):
        """T10: broken mcp.json → error shown, exit code 1."""
        mcp_path = self.project_dir / ".vscode" / "mcp.json"
        mcp_path.parent.mkdir(parents=True, exist_ok=True)
        mcp_path.write_text("{ not valid json")
        result = self.runner.invoke(main, ["vscode", "validate", "--project-dir", str(self.project_dir)])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("not valid JSON", result.output)

    def test_validate_missing_servers_key(self):
        """mcp.json without 'servers' key → error."""
        mcp_path = self.project_dir / ".vscode" / "mcp.json"
        mcp_path.parent.mkdir(parents=True, exist_ok=True)
        mcp_path.write_text(json.dumps({"mcpServers": {}}))
        result = self.runner.invoke(main, ["vscode", "validate", "--project-dir", str(self.project_dir)])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("missing 'servers' key", result.output)

    def test_validate_json_output(self):
        """AC2: --json outputs structured result."""
        mcp_path = self.project_dir / ".vscode" / "mcp.json"
        mcp_path.parent.mkdir(parents=True, exist_ok=True)
        mcp_path.write_text(json.dumps({"servers": {"github": {"type": "stdio", "command": "npx"}}}))
        result = self.runner.invoke(main, ["vscode", "validate", "--json", "--project-dir", str(self.project_dir)])
        self.assertEqual(result.exit_code, 0, result.output)
        data = json.loads(result.output)
        self.assertTrue(data["valid"])
        self.assertEqual(data["errors"], [])

    def test_validate_json_output_with_errors(self):
        """--json with errors: valid=False, errors populated, exit 1."""
        mcp_path = self.project_dir / ".vscode" / "mcp.json"
        mcp_path.parent.mkdir(parents=True, exist_ok=True)
        mcp_path.write_text("{ broken")
        result = self.runner.invoke(main, ["vscode", "validate", "--json", "--project-dir", str(self.project_dir)])
        self.assertNotEqual(result.exit_code, 0)
        data = json.loads(result.output)
        self.assertFalse(data["valid"])
        self.assertTrue(len(data["errors"]) > 0)

    def test_validate_no_files(self):
        """No .vscode files → valid (nothing to validate)."""
        result = self.runner.invoke(main, ["vscode", "validate", "--project-dir", str(self.project_dir)])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("VS Code configuration is valid.", result.output)


class TestMcpGetVscodeFormat(_VscodeTestBase):
    """mcp get --format vscode → .vscode/mcp.json."""

    def test_mcp_get_vscode_generates_mcp_json(self):
        """T12: mcp get --format vscode generates .vscode/mcp.json."""
        self._add_mcp_server("github", "npx", ["-y", "@modelcontextprotocol/server-github"], ["GITHUB_TOKEN"])
        result = self.runner.invoke(main, ["mcp", "get", "--format", "vscode", "--path", str(self.project_dir)])
        self.assertEqual(result.exit_code, 0, result.output)
        mcp_path = self.project_dir / ".vscode" / "mcp.json"
        self.assertTrue(mcp_path.exists())
        data = json.loads(mcp_path.read_text())
        self.assertIn("servers", data)
        entry = data["servers"]["github"]
        self.assertEqual(entry["type"], "stdio")
        self.assertEqual(entry["env"], {"GITHUB_TOKEN": "${env:GITHUB_TOKEN}"})

    def test_mcp_get_vscode_scope_user_rejected(self):
        """--scope user with --format vscode is rejected."""
        self._add_mcp_server("github", "npx")
        result = self.runner.invoke(
            main, ["mcp", "get", "--format", "vscode", "--scope", "user", "--path", str(self.project_dir)]
        )
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("only supported", result.output)


class TestExportMcpVscode(unittest.TestCase):
    """Unit tests for export_mcp (VS Code format)."""

    def test_export_format(self):
        """servers key + type: stdio + ${env:KEY} syntax."""
        servers = [
            MCPServer(name="github", command="npx", args=["-y", "pkg"], env_keys=["GITHUB_TOKEN"], enabled=True),
            MCPServer(name="playwright", command="npx", args=[], env_keys=[], enabled=True),
        ]
        data = export_mcp(servers)
        self.assertIn("servers", data)
        self.assertNotIn("mcpServers", data)
        self.assertEqual(data["servers"]["github"]["type"], "stdio")
        self.assertEqual(data["servers"]["github"]["command"], "npx")
        self.assertEqual(data["servers"]["github"]["args"], ["-y", "pkg"])
        self.assertEqual(data["servers"]["github"]["env"], {"GITHUB_TOKEN": "${env:GITHUB_TOKEN}"})
        self.assertEqual(data["servers"]["playwright"]["type"], "stdio")
        self.assertNotIn("env", data["servers"]["playwright"])

    def test_export_skips_disabled(self):
        """Disabled servers are excluded."""
        servers = [
            MCPServer(name="active", command="npx", enabled=True),
            MCPServer(name="disabled", command="npx", enabled=False),
        ]
        data = export_mcp(servers)
        self.assertIn("active", data["servers"])
        self.assertNotIn("disabled", data["servers"])

    def test_export_skips_non_stdio(self):
        """Servers with empty command are skipped."""
        servers = [
            MCPServer(name="stdio", command="npx", enabled=True),
            MCPServer(name="http", command="", enabled=True),
        ]
        data = export_mcp(servers)
        self.assertIn("stdio", data["servers"])
        self.assertNotIn("http", data["servers"])


class TestValidateFunctions(unittest.TestCase):
    """Unit tests for validate_vscode_mcp and validate_extensions."""

    def test_validate_mcp_valid(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "mcp.json"
            p.write_text(json.dumps({"servers": {"a": {"type": "stdio", "command": "x"}}}))
            self.assertEqual(validate_vscode_mcp(p), [])

    def test_validate_mcp_broken_json(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "mcp.json"
            p.write_text("{ broken")
            errors = validate_vscode_mcp(p)
            self.assertEqual(len(errors), 1)
            self.assertIn("not valid JSON", errors[0])

    def test_validate_mcp_missing_servers(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "mcp.json"
            p.write_text(json.dumps({"other": {}}))
            errors = validate_vscode_mcp(p)
            self.assertTrue(any("missing 'servers'" in e for e in errors))

    def test_validate_mcp_server_missing_command(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "mcp.json"
            p.write_text(json.dumps({"servers": {"a": {"type": "stdio"}}}))
            errors = validate_vscode_mcp(p)
            self.assertTrue(any("'command'" in e for e in errors))

    def test_validate_extensions_valid(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "extensions.json"
            p.write_text(json.dumps({"recommendations": ["a", "b"]}))
            self.assertEqual(validate_extensions(p), [])

    def test_validate_extensions_broken_json(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "extensions.json"
            p.write_text("not json")
            errors = validate_extensions(p)
            self.assertEqual(len(errors), 1)

    def test_validate_extensions_wrong_type(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "extensions.json"
            p.write_text(json.dumps({"recommendations": "not-a-list"}))
            errors = validate_extensions(p)
            self.assertTrue(any("must be an array" in e for e in errors))


if __name__ == "__main__":
    unittest.main()


class TestVscodeReviewFixes(unittest.TestCase):
    """Review C1/M1/M4 fixes for the VS Code provider."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_save_extensions_preserves_other_keys(self):
        """C1: unwantedRecommendations and other keys survive extension add."""
        from ai_adapter.providers.vscode import save_extension_recommendations

        ext = self.base / ".vscode" / "extensions.json"
        ext.parent.mkdir(parents=True)
        ext.write_text(
            json.dumps({"recommendations": ["a.b"], "unwantedRecommendations": ["x.y"]}),
            encoding="utf-8",
        )
        save_extension_recommendations(ext, ["a.b", "c.d"])
        data = json.loads(ext.read_text(encoding="utf-8"))
        self.assertEqual(data["recommendations"], ["a.b", "c.d"])
        self.assertEqual(data["unwantedRecommendations"], ["x.y"])

    def test_save_extensions_corrupt_aborts(self):
        """C1: corrupt extensions.json aborts instead of silent overwrite."""
        import click

        from ai_adapter.providers.vscode import save_extension_recommendations

        ext = self.base / ".vscode" / "extensions.json"
        ext.parent.mkdir(parents=True)
        ext.write_text("{not json", encoding="utf-8")
        with self.assertRaises(click.ClickException):
            save_extension_recommendations(ext, ["a.b"])
        self.assertEqual(ext.read_text(encoding="utf-8"), "{not json")

    def test_merge_mcp_list_top_level_no_crash(self):
        """M1: top-level list JSON does not crash the merge."""
        from ai_adapter.providers.vscode import merge_into_vscode_mcp_json

        path = self.base / ".vscode" / "mcp.json"
        path.parent.mkdir(parents=True)
        path.write_text('[{"servers": {}}]', encoding="utf-8")
        merge_into_vscode_mcp_json(path, {"servers": {"x": {"type": "stdio", "command": "npx"}}}, force=True)
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertIn("x", data["servers"])

    def test_merge_mcp_servers_not_dict_no_crash(self):
        """M1: servers as a list does not crash the merge."""
        from ai_adapter.providers.vscode import merge_into_vscode_mcp_json

        path = self.base / ".vscode" / "mcp.json"
        path.parent.mkdir(parents=True)
        path.write_text('{"servers": ["not-a-dict"]}', encoding="utf-8")
        merge_into_vscode_mcp_json(path, {"servers": {"x": {"type": "stdio", "command": "npx"}}}, force=True)
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertIn("x", data["servers"])

    def test_install_prompts_when_existing(self):
        """M4: merge_into_vscode_mcp_json prompts before overwriting (force=False)."""
        import click as _click
        from click.exceptions import Abort

        from ai_adapter.providers.vscode import merge_into_vscode_mcp_json

        path = self.base / ".vscode" / "mcp.json"
        path.parent.mkdir(parents=True)
        path.write_text(
            json.dumps({"servers": {"legacy": {"type": "stdio", "command": "node"}}}),
            encoding="utf-8",
        )
        old_confirm = _click.confirm

        def _deny(*_a, **_k):
            raise Abort()

        _click.confirm = _deny
        try:
            with self.assertRaises(Abort):
                merge_into_vscode_mcp_json(path, {"servers": {"x": {"type": "stdio", "command": "npx"}}}, force=False)
        finally:
            _click.confirm = old_confirm
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertIn("legacy", data["servers"])
