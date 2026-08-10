"""Tests for the Agent Plugins 1.0.0 validation module."""

import json
import tempfile
import unittest
from pathlib import Path

from ai_adapter.agent_plugins import (
    MCP_SCHEMA,
    PLUGIN_SCHEMA,
    validate_mcp_config,
    validate_plugin_manifest,
    validate_plugin_name,
    validate_plugin_package,
    validate_skill_dir,
)


def _write(path: Path, data: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def _manifest(**overrides: object) -> dict:
    base: dict = {"$schema": PLUGIN_SCHEMA, "name": "my-plugin"}
    base.update(overrides)
    return base


class TestValidatePluginName(unittest.TestCase):
    def test_valid_names(self):
        for name in ("my-plugin", "my.plugin", "a", "com.example.plugin", "my-plugin2"):
            self.assertIsNone(validate_plugin_name(name), name)

    def test_too_long(self):
        self.assertIsNotNone(validate_plugin_name("a" * 65))

    def test_uppercase_rejected(self):
        self.assertIsNotNone(validate_plugin_name("MyPlugin"))

    def test_special_chars_rejected(self):
        for name in ("my plugin", "my_plugin", "my/plugin", "my-plugin!"):
            self.assertIsNotNone(validate_plugin_name(name), name)

    def test_double_hyphen_and_dot(self):
        self.assertIsNotNone(validate_plugin_name("my--plugin"))
        self.assertIsNotNone(validate_plugin_name("my..plugin"))

    def test_start_end_alphanumeric(self):
        self.assertIsNotNone(validate_plugin_name("-my-plugin"))
        self.assertIsNotNone(validate_plugin_name("my-plugin-"))
        self.assertIsNotNone(validate_plugin_name(".my-plugin"))
        self.assertIsNotNone(validate_plugin_name("my-plugin."))

    def test_non_string(self):
        self.assertIsNotNone(validate_plugin_name(123))


class TestValidatePluginManifest(unittest.TestCase):
    def test_valid_manifest(self):
        result = validate_plugin_manifest(_manifest())
        self.assertTrue(result.valid)
        self.assertEqual(result.issues, [])

    def test_missing_schema(self):
        data = {"name": "my-plugin"}
        result = validate_plugin_manifest(data)
        self.assertFalse(result.valid)
        self.assertTrue(any("$schema" in i.message for i in result.issues))

    def test_wrong_schema(self):
        result = validate_plugin_manifest(_manifest(**{"$schema": "https://example.com/x"}))
        self.assertFalse(result.valid)

    def test_missing_name(self):
        result = validate_plugin_manifest({"$schema": PLUGIN_SCHEMA})
        self.assertFalse(result.valid)
        self.assertTrue(any("name" in i.message for i in result.issues))

    def test_invalid_name(self):
        result = validate_plugin_manifest(_manifest(name="Bad Name"))
        self.assertFalse(result.valid)

    def test_unknown_field_is_warning(self):
        result = validate_plugin_manifest(_manifest(foo="bar"))
        self.assertTrue(result.valid)
        self.assertTrue(any(i.severity == "warning" for i in result.issues))

    def test_extensions_non_object_warning(self):
        result = validate_plugin_manifest(_manifest(extensions=["x"]))
        self.assertTrue(result.valid)
        self.assertTrue(any("extensions" in i.message for i in result.issues))

    def test_bad_field_types_are_fatal(self):
        for field, value in (("version", 3), ("description", ["x"]), ("keywords", "x")):
            result = validate_plugin_manifest(_manifest(**{field: value}))
            self.assertFalse(result.valid, field)
            self.assertTrue(any(field in i.message for i in result.issues), field)

    def test_bad_author(self):
        result = validate_plugin_manifest(_manifest(author="smapira"))
        self.assertFalse(result.valid)

    def test_author_unknown_field(self):
        result = validate_plugin_manifest(_manifest(author={"name": "x", "github": "y"}))
        self.assertTrue(any("github" in i.message for i in result.issues))

    def test_non_object_manifest(self):
        result = validate_plugin_manifest(["x"])
        self.assertFalse(result.valid)


class TestValidateMCPConfig(unittest.TestCase):
    def _basic_mcp(self, servers: dict) -> dict:
        return {"$schema": MCP_SCHEMA, "mcpServers": servers}

    def test_valid_stdio(self):
        data = self._basic_mcp(
            {
                "echo": {
                    "type": "stdio",
                    "command": "echo",
                    "args": ["--flag"],
                    "env": {"FOO": "${PLUGIN_ROOT}/data"},
                }
            }
        )
        result = validate_mcp_config(data)
        self.assertTrue(result.valid, [str(i) for i in result.issues])

    def test_valid_streamable_http(self):
        data = self._basic_mcp({"api": {"type": "streamable-http", "url": "https://example.com/mcp"}})
        result = validate_mcp_config(data)
        self.assertTrue(result.valid)

    def test_valid_loopback_http(self):
        data = self._basic_mcp({"local": {"type": "streamable-http", "url": "http://127.0.0.1:8080/mcp"}})
        result = validate_mcp_config(data)
        self.assertTrue(result.valid)

    def test_non_loopback_http_rejected(self):
        data = self._basic_mcp({"api": {"type": "streamable-http", "url": "http://example.com/mcp"}})
        result = validate_mcp_config(data)
        self.assertFalse(result.valid)
        self.assertTrue(any("https" in i.message for i in result.issues))

    def test_missing_type(self):
        data = self._basic_mcp({"echo": {"command": "echo"}})
        result = validate_mcp_config(data)
        self.assertFalse(result.valid)
        self.assertTrue(any("type" in i.message for i in result.issues))

    def test_unknown_server_type(self):
        data = self._basic_mcp({"x": {"type": "tcp", "url": "https://example.com"}})
        result = validate_mcp_config(data)
        self.assertFalse(result.valid)
        self.assertTrue(any("tcp" in i.message for i in result.issues))

    def test_command_with_spaces(self):
        data = self._basic_mcp({"echo": {"type": "stdio", "command": "npx foo"}})
        result = validate_mcp_config(data)
        self.assertFalse(result.valid)

    def test_command_placeholder_rejected(self):
        data = self._basic_mcp({"echo": {"type": "stdio", "command": "${PLUGIN_ROOT}/bin"}})
        result = validate_mcp_config(data)
        self.assertFalse(result.valid)

    def test_env_reserved_key(self):
        data = self._basic_mcp({"echo": {"type": "stdio", "command": "echo", "env": {"PLUGIN_ROOT": "/x"}}})
        result = validate_mcp_config(data)
        self.assertFalse(result.valid)
        self.assertTrue(any("PLUGIN_ROOT" in i.message for i in result.issues))

    def test_missing_schema(self):
        data = {"mcpServers": {}}
        result = validate_mcp_config(data)
        self.assertFalse(result.valid)

    def test_missing_servers(self):
        result = validate_mcp_config({"$schema": MCP_SCHEMA})
        self.assertFalse(result.valid)
        self.assertTrue(any("mcpServers" in i.message for i in result.issues))

    def test_duplicate_headers_case_insensitive(self):
        data = self._basic_mcp(
            {"api": {"type": "streamable-http", "url": "https://example.com", "headers": {"X-A": "1", "x-a": "2"}}}
        )
        result = validate_mcp_config(data)
        self.assertFalse(result.valid)


class TestValidateSkillDir(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.skill = Path(self.tmp.name) / "skills" / "summarize"
        self.skill.mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def _issues(self):
        issues: list = []
        validate_skill_dir(self.skill, issues)
        return issues

    def test_missing_skill_md(self):
        issues = self._issues()
        self.assertEqual(len(issues), 1)
        self.assertIn("SKILL.md", issues[0].message)

    def test_valid_skill(self):
        (self.skill / "SKILL.md").write_text(
            "---\nname: summarize\ndescription: Summarize text\n---\n\n# Summarize\n",
            encoding="utf-8",
        )
        self.assertEqual(self._issues(), [])

    def test_missing_frontmatter(self):
        (self.skill / "SKILL.md").write_text("# Summarize\n", encoding="utf-8")
        issues = self._issues()
        self.assertTrue(any("frontmatter" in i.message for i in issues))

    def test_missing_name(self):
        (self.skill / "SKILL.md").write_text("---\ndescription: x\n---\n", encoding="utf-8")
        issues = self._issues()
        self.assertTrue(any("name" in i.message for i in issues))

    def test_missing_description(self):
        (self.skill / "SKILL.md").write_text("---\nname: x\n---\n", encoding="utf-8")
        issues = self._issues()
        self.assertTrue(any("description" in i.message for i in issues))


class TestValidatePluginPackage(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "my-plugin"
        self.root.mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_missing_plugin_json(self):
        result = validate_plugin_package(self.root)
        self.assertFalse(result.valid)
        self.assertTrue(any("plugin.json" in i.message for i in result.issues))

    def test_invalid_json(self):
        (self.root / "plugin.json").write_text("{not json", encoding="utf-8")
        result = validate_plugin_package(self.root)
        self.assertFalse(result.valid)

    def test_valid_package(self):
        _write(self.root / "plugin.json", _manifest())
        result = validate_plugin_package(self.root)
        self.assertTrue(result.valid, [str(i) for i in result.issues])

    def test_invalid_mcp_makes_package_invalid(self):
        _write(self.root / "plugin.json", _manifest())
        _write(self.root / "mcp.json", {"$schema": MCP_SCHEMA, "mcpServers": {"x": {"command": "echo"}}})
        result = validate_plugin_package(self.root)
        self.assertFalse(result.valid)
        self.assertTrue(any(i.component == "mcp.json" and "type" in i.message for i in result.issues))

    def test_bad_skill_gives_warning(self):
        _write(self.root / "plugin.json", _manifest())
        (self.root / "skills" / "bad").mkdir(parents=True)  # no SKILL.md
        result = validate_plugin_package(self.root)
        self.assertTrue(result.valid)
        self.assertTrue(any(i.component == "skills" for i in result.issues))


if __name__ == "__main__":
    unittest.main()
