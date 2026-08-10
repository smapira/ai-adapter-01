"""Tests for the plugin CLI subcommand."""

import json
import tempfile
import unittest
from pathlib import Path

from click.testing import CliRunner

from ai_adapter.agent_plugins import PLUGIN_SCHEMA
from ai_adapter.cli import main


class TestPluginCommand(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "my-plugin"
        self.root.mkdir(parents=True)
        (self.root / "plugin.json").write_text(
            json.dumps({"$schema": PLUGIN_SCHEMA, "name": "my-plugin"}),
            encoding="utf-8",
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_validate_valid_package(self):
        result = self.runner.invoke(main, ["plugin", "validate", str(self.root)])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("valid", result.output.lower())

    def test_validate_invalid_package(self):
        (self.root / "plugin.json").write_text(
            json.dumps({"name": "Bad Name"}),
            encoding="utf-8",
        )
        result = self.runner.invoke(main, ["plugin", "validate", str(self.root)])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("not valid", result.output.lower())

    def test_validate_json_output(self):
        result = self.runner.invoke(main, ["plugin", "validate", str(self.root), "--json"])
        self.assertEqual(result.exit_code, 0, result.output)
        payload = json.loads(result.output)
        self.assertTrue(payload["valid"])
        self.assertIsInstance(payload["issues"], list)

    def test_validate_json_failure_raises_nonzero_exit(self):
        (self.root / "plugin.json").write_text(
            json.dumps({"name": "Bad Name"}),
            encoding="utf-8",
        )
        result = self.runner.invoke(main, ["plugin", "validate", str(self.root), "--json"])
        self.assertNotEqual(result.exit_code, 0)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["valid"])

    def test_validate_missing_path(self):
        result = self.runner.invoke(main, ["plugin", "validate", str(self.root / "nope")])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("does not exist", result.output)

    def test_build_creates_package(self):
        with self.runner.isolated_filesystem():
            result = self.runner.invoke(main, ["plugin", "build", "test-plugin", "--description", "Test"])
            self.assertEqual(result.exit_code, 0, result.output)
            pkg = Path("test-plugin")
            self.assertTrue((pkg / "plugin.json").is_file())
            self.assertTrue((pkg / "mcp.json").is_file())
            self.assertTrue((pkg / "skills").is_dir())
            manifest = json.loads((pkg / "plugin.json").read_text())
            self.assertEqual(manifest["name"], "test-plugin")
            self.assertEqual(manifest["description"], "Test")

    def test_build_invalid_name(self):
        result = self.runner.invoke(main, ["plugin", "build", "Bad Name"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Invalid plugin name", result.output)

    def test_build_existing_dir(self):
        with self.runner.isolated_filesystem():
            Path("taken").mkdir()
            result = self.runner.invoke(main, ["plugin", "build", "taken"])
            self.assertNotEqual(result.exit_code, 0)


if __name__ == "__main__":
    unittest.main()
