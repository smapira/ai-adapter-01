"""Tests for the Gemini CLI provider (design 05).

Covers:
- ``gemini install`` → .gemini/settings.json + commands/*.toml + GEMINI.md
- ``gemini install --scope user`` → ~/.gemini/ placement
- ``gemini install --with-extension`` → ~/.gemini/extensions/<name>/ manifest
- ``command get`` / ``prompt get`` --format gemini → Markdown → TOML
- ``mcp get --format gemini`` → settings.json merge
- ``gemini validate`` → JSON/TOML checks + ``--json`` output
- Unit tests for the pure conversion/validation helpers
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from click.testing import CliRunner

from ai_adapter.cli import main
from ai_adapter.config import init
from ai_adapter.models import Command, MCPServer
from ai_adapter.providers.gemini import (
    export_command_toml,
    export_mcp,
    generate_extension_manifest,
    parse_command_markdown,
    validate_command_toml,
    validate_extension_manifest,
    validate_settings,
)

# tomllib is stdlib from Python 3.11; 3.10 falls back to tomli (same
# marker-based pattern as the provider itself).
try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib  # type: ignore[no-redef]

_MD_WITH_FRONTMATTER = "---\ndescription: Deploy the application\n---\n# Deploy steps\n1. Run tests\n2. Deploy\n"
_MD_WITHOUT_FRONTMATTER = "Just do the thing.\n"


class _GeminiTestBase(unittest.TestCase):
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

    def _add_command(self, name: str = "deploy", content: str = _MD_WITH_FRONTMATTER):
        """Register a command via the CLI (store file + config entry)."""
        src = Path(self.temp_dir.name) / f"{name.replace('/', '_')}.md"
        src.write_text(content, encoding="utf-8")
        return self.runner.invoke(main, ["command", "add", str(src)])

    def _add_instruction(self, name: str = "rules", content: str = "Always be polite.\n"):
        """Register an instruction via the CLI (`agent add`)."""
        src = Path(self.temp_dir.name) / f"{name}.md"
        src.write_text(content, encoding="utf-8")
        return self.runner.invoke(main, ["agent", "add", str(src)])

    def _add_mcp(self, name: str = "github", command: str = "npx", args=("-y", "srv"), env_keys=("GITHUB_TOKEN",)):
        """Register an MCP server via the CLI."""
        cmd = ["mcp", "add", name, "--command", command]
        for a in args:
            cmd += ["--args", a]
        for e in env_keys:
            cmd += ["--env-key", e]
        return self.runner.invoke(main, cmd)


class TestGeminiInstallProject(_GeminiTestBase):
    """gemini install (project scope) — design 05 task 05-1."""

    def test_install_generates_all_files(self):
        """T1/AC1: settings.json + commands/*.toml + GEMINI.md are generated."""
        self._add_command("deploy")
        self._add_mcp()
        self._add_instruction()

        result = self.runner.invoke(main, ["gemini", "install", "--project-dir", str(self.project_dir)])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Gemini CLI configuration installed:", result.output)
        self.assertTrue((self.project_dir / ".gemini" / "settings.json").is_file())
        self.assertTrue((self.project_dir / ".gemini" / "commands" / "deploy.toml").is_file())
        self.assertTrue((self.project_dir / "GEMINI.md").is_file())

    def test_install_command_toml_parses(self):
        """AC1/T11: the generated TOML loads with tomllib/tomli."""
        self._add_command("deploy")
        result = self.runner.invoke(main, ["gemini", "install", "--project-dir", str(self.project_dir)])
        self.assertEqual(result.exit_code, 0, result.output)
        data = tomllib.loads((self.project_dir / ".gemini" / "commands" / "deploy.toml").read_text(encoding="utf-8"))
        self.assertEqual(data["description"], "Deploy the application")
        self.assertIn("# Deploy steps", data["prompt"])

    def test_install_settings_env_uses_dollar_brace(self):
        """AC2: mcpServers env values use ${ENV_KEY} format."""
        self._add_mcp()
        result = self.runner.invoke(main, ["gemini", "install", "--project-dir", str(self.project_dir), "--force"])
        self.assertEqual(result.exit_code, 0, result.output)
        data = json.loads((self.project_dir / ".gemini" / "settings.json").read_text(encoding="utf-8"))
        self.assertEqual(data["mcpServers"]["github"]["env"], {"GITHUB_TOKEN": "${GITHUB_TOKEN}"})

    def test_install_merges_existing_settings_preserves_keys(self):
        """AC3: non-managed keys and servers survive the merge."""
        settings = self.project_dir / ".gemini" / "settings.json"
        settings.parent.mkdir(parents=True, exist_ok=True)
        settings.write_text(
            json.dumps(
                {
                    "theme": "GitHub",
                    "mcpServers": {"hand-rolled": {"command": "custom-bin"}},
                }
            ),
            encoding="utf-8",
        )
        self._add_mcp()

        result = self.runner.invoke(main, ["gemini", "install", "--project-dir", str(self.project_dir), "--force"])
        self.assertEqual(result.exit_code, 0, result.output)
        data = json.loads(settings.read_text(encoding="utf-8"))
        self.assertEqual(data["theme"], "GitHub")
        self.assertIn("hand-rolled", data["mcpServers"])
        self.assertIn("github", data["mcpServers"])

    def test_install_generated_files_gitignored(self):
        """AC4: generated files are registered in the project .gitignore."""
        (self.project_dir / ".git").mkdir()
        self._add_command("deploy")
        self._add_mcp()
        self._add_instruction()

        result = self.runner.invoke(main, ["gemini", "install", "--project-dir", str(self.project_dir), "--force"])
        self.assertEqual(result.exit_code, 0, result.output)
        gitignore = (self.project_dir / ".gitignore").read_text(encoding="utf-8")
        self.assertIn(".gemini", gitignore)
        self.assertIn("GEMINI.md", gitignore)

    def test_install_empty_store_prints_nothing(self):
        """Empty store → "Nothing to install." and exit 0 (not an error)."""
        result = self.runner.invoke(main, ["gemini", "install", "--project-dir", str(self.project_dir)])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Nothing to install.", result.output)

    def test_install_prompts_when_settings_exist_without_force(self):
        """Existing settings.json requires --force or confirmation."""
        settings = self.project_dir / ".gemini" / "settings.json"
        settings.parent.mkdir(parents=True, exist_ok=True)
        settings.write_text("{}", encoding="utf-8")
        self._add_mcp()

        result = self.runner.invoke(main, ["gemini", "install", "--project-dir", str(self.project_dir)])
        self.assertNotEqual(result.exit_code, 0)


class TestGeminiInstallUserScope(_GeminiTestBase):
    """gemini install --scope user — design 05 task 05-2."""

    def test_user_scope_places_files_under_home_gemini(self):
        """T2/AC1: ~/.gemini/ is created and populated."""
        self._add_command("deploy")
        self._add_mcp()
        self._add_instruction()

        result = self.runner.invoke(main, ["gemini", "install", "--scope", "user", "--force"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertTrue((self.patch_home / ".gemini" / "settings.json").is_file())
        self.assertTrue((self.patch_home / ".gemini" / "commands" / "deploy.toml").is_file())
        self.assertTrue((self.patch_home / ".gemini" / "GEMINI.md").is_file())

    def test_user_scope_merges_existing_settings(self):
        """AC2: existing user settings are preserved while merging."""
        user_settings = self.patch_home / ".gemini" / "settings.json"
        user_settings.parent.mkdir(parents=True, exist_ok=True)
        user_settings.write_text(json.dumps({"mcpServers": {"local": {"command": "x"}}}), encoding="utf-8")
        self._add_mcp()

        result = self.runner.invoke(main, ["gemini", "install", "--scope", "user", "--force"])
        self.assertEqual(result.exit_code, 0, result.output)
        data = json.loads(user_settings.read_text(encoding="utf-8"))
        self.assertIn("local", data["mcpServers"])
        self.assertIn("github", data["mcpServers"])


class TestGeminiInstallExtension(_GeminiTestBase):
    """gemini install --with-extension — design 05 task 05-3."""

    def test_extension_manifest_generated_under_home(self):
        """AC1: manifest lands in ~/.gemini/extensions/<name>/."""
        self._add_mcp()
        result = self.runner.invoke(
            main,
            ["gemini", "install", "--project-dir", str(self.project_dir), "--with-extension", "--force"],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        manifest = self.patch_home / ".gemini" / "extensions" / self.project_dir.name / "gemini-extension.json"
        self.assertTrue(manifest.is_file())

    def test_extension_manifest_not_in_project_root(self):
        """AC4: no manifest is written to the project root (Gemini ignores it)."""
        self._add_mcp()
        result = self.runner.invoke(
            main,
            ["gemini", "install", "--project-dir", str(self.project_dir), "--with-extension", "--force"],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertFalse((self.project_dir / "gemini-extension.json").exists())

    def test_extension_manifest_content(self):
        """Manifest carries name/version/mcpServers/contextFileName per spec."""
        self._add_mcp()
        result = self.runner.invoke(
            main,
            ["gemini", "install", "--project-dir", str(self.project_dir), "--with-extension", "--force"],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        manifest_path = self.patch_home / ".gemini" / "extensions" / self.project_dir.name / "gemini-extension.json"
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(data["name"], self.project_dir.name)
        self.assertEqual(data["version"], "1.0.0")
        self.assertEqual(data["contextFileName"], "GEMINI.md")
        self.assertIn("github", data["mcpServers"])

    def test_extension_install_instructions_printed(self):
        """AC3: the `gemini extensions install` command line is shown."""
        self._add_mcp()
        result = self.runner.invoke(
            main,
            ["gemini", "install", "--project-dir", str(self.project_dir), "--with-extension", "--force"],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Install with: gemini extensions install", result.output)
        self.assertIn(str(self.patch_home / ".gemini" / "extensions" / self.project_dir.name), result.output)

    def test_extension_existing_dir_prompts(self):
        """Re-running with an existing extension dir asks for confirmation."""
        self._add_mcp()
        args = ["gemini", "install", "--project-dir", str(self.project_dir), "--with-extension", "--force"]
        self.runner.invoke(main, args)

        # Second run without --force must prompt; declining aborts.
        result = self.runner.invoke(main, args[:-1], input="n\n")
        self.assertNotEqual(result.exit_code, 0)


class TestGeminiCommandTomlConversion(_GeminiTestBase):
    """command/prompt get --format gemini — design 05 task 05-4."""

    def test_command_get_gemini_converts_markdown(self):
        """T4: frontmatter description → TOML description, body → prompt."""
        self._add_command("deploy", _MD_WITH_FRONTMATTER)
        result = self.runner.invoke(
            main,
            ["command", "get", "deploy", "--format", "gemini", "--project-dir", str(self.project_dir)],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        dest = self.project_dir / ".gemini" / "commands" / "deploy.toml"
        self.assertTrue(dest.is_file())
        data = tomllib.loads(dest.read_text(encoding="utf-8"))
        self.assertEqual(data["description"], "Deploy the application")
        self.assertIn("# Deploy steps", data["prompt"])

    def test_command_get_gemini_without_frontmatter(self):
        """T5: no frontmatter → whole body becomes the prompt, description empty."""
        self._add_command("plain", _MD_WITHOUT_FRONTMATTER)
        result = self.runner.invoke(
            main,
            ["command", "get", "plain", "--format", "gemini", "--project-dir", str(self.project_dir)],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        dest = self.project_dir / ".gemini" / "commands" / "plain.toml"
        data = tomllib.loads(dest.read_text(encoding="utf-8"))
        self.assertEqual(data["description"], "")
        self.assertEqual(data["prompt"].strip(), "Just do the thing.")

    def test_command_get_gemini_nested_name(self):
        """AC3: nested command dir/name → .gemini/commands/dir/name.toml."""
        store_dir = Path(self.patch_home) / ".ai-adapter" / "commands" / "dir"
        store_dir.mkdir(parents=True, exist_ok=True)
        (store_dir / "review.md").write_text("---\ndescription: Nested review\n---\nReview it.\n", encoding="utf-8")
        import ai_adapter.config as cfg

        config = cfg.load_config()
        config.commands.append(Command(name="dir/review", content="x"))
        cfg.save_config(config)

        result = self.runner.invoke(
            main,
            ["command", "get", "dir/review", "--format", "gemini", "--project-dir", str(self.project_dir)],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        dest = self.project_dir / ".gemini" / "commands" / "dir" / "review.toml"
        self.assertTrue(dest.is_file())
        data = tomllib.loads(dest.read_text(encoding="utf-8"))
        self.assertEqual(data["description"], "Nested review")

    def test_command_get_gemini_scope_user(self):
        """--scope user → ~/.gemini/commands/."""
        self._add_command("deploy")
        result = self.runner.invoke(main, ["command", "get", "deploy", "--format", "gemini", "--scope", "user"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertTrue((self.patch_home / ".gemini" / "commands" / "deploy.toml").is_file())

    def test_prompt_get_gemini_converts_to_toml(self):
        """prompt get --format gemini → .gemini/commands/<name>.toml."""
        src = Path(self.temp_dir.name) / "summarize.md"
        src.write_text("---\ndescription: Summarize\n---\nSummarize the text.\n", encoding="utf-8")
        self.runner.invoke(main, ["prompt", "add", str(src)])

        result = self.runner.invoke(
            main,
            ["prompt", "get", "summarize", "--format", "gemini", "--project-dir", str(self.project_dir)],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        dest = self.project_dir / ".gemini" / "commands" / "summarize.toml"
        self.assertTrue(dest.is_file())
        data = tomllib.loads(dest.read_text(encoding="utf-8"))
        self.assertEqual(data["description"], "Summarize")
        self.assertIn("Summarize the text.", data["prompt"])


class TestGeminiMcpGet(_GeminiTestBase):
    """mcp get --format gemini — design 05 task 05-5."""

    def test_mcp_get_gemini_creates_settings(self):
        """AC1: .gemini/settings.json is created with the mcpServers key."""
        self._add_mcp()
        result = self.runner.invoke(main, ["mcp", "get", "--format", "gemini", "--path", str(self.project_dir)])
        self.assertEqual(result.exit_code, 0, result.output)
        settings = self.project_dir / ".gemini" / "settings.json"
        self.assertTrue(settings.is_file())
        data = json.loads(settings.read_text(encoding="utf-8"))
        self.assertIn("mcpServers", data)
        self.assertEqual(data["mcpServers"]["github"]["command"], "npx")

    def test_mcp_get_gemini_merges_existing_settings(self):
        """AC1-3: existing settings + unmanaged servers are preserved, .bak taken."""
        settings = self.project_dir / ".gemini" / "settings.json"
        settings.parent.mkdir(parents=True, exist_ok=True)
        settings.write_text(
            json.dumps({"theme": "Dark", "mcpServers": {"hand-rolled": {"command": "x"}}}),
            encoding="utf-8",
        )
        self._add_mcp()

        result = self.runner.invoke(
            main, ["mcp", "get", "--format", "gemini", "--path", str(self.project_dir), "--force"]
        )
        self.assertEqual(result.exit_code, 0, result.output)
        data = json.loads(settings.read_text(encoding="utf-8"))
        self.assertEqual(data["theme"], "Dark")
        self.assertIn("hand-rolled", data["mcpServers"])
        self.assertIn("github", data["mcpServers"])
        self.assertTrue(settings.with_suffix(".json.bak").is_file())

    def test_mcp_get_gemini_scope_user(self):
        """--scope user → ~/.gemini/settings.json."""
        self._add_mcp()
        result = self.runner.invoke(main, ["mcp", "get", "--format", "gemini", "--scope", "user"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertTrue((self.patch_home / ".gemini" / "settings.json").is_file())

    def test_mcp_get_gemini_gitignored(self):
        """Project-scope settings.json is registered in .gitignore."""
        (self.project_dir / ".git").mkdir()
        self._add_mcp()
        result = self.runner.invoke(main, ["mcp", "get", "--format", "gemini", "--path", str(self.project_dir)])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn(".gemini", (self.project_dir / ".gitignore").read_text(encoding="utf-8"))


class TestGeminiValidate(_GeminiTestBase):
    """gemini validate — design 05 task 05-6."""

    def test_validate_valid_configuration(self):
        """T7: valid config → success message, exit 0."""
        self._add_command("deploy")
        self._add_mcp()
        self.runner.invoke(main, ["gemini", "install", "--project-dir", str(self.project_dir), "--force"])

        result = self.runner.invoke(main, ["gemini", "validate", "--project-dir", str(self.project_dir)])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Gemini CLI configuration is valid.", result.output)

    def test_validate_invalid_toml_reports_error(self):
        """T8: broken command TOML → error message, exit 1."""
        commands_dir = self.project_dir / ".gemini" / "commands"
        commands_dir.mkdir(parents=True)
        (commands_dir / "broken.toml").write_text('prompt = """unterminated\n', encoding="utf-8")

        result = self.runner.invoke(main, ["gemini", "validate", "--project-dir", str(self.project_dir)])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("broken.toml", result.output)
        self.assertIn("not valid TOML", result.output)

    def test_validate_invalid_settings_json_reports_error(self):
        """Broken settings.json → JSON parse error, exit 1."""
        settings = self.project_dir / ".gemini" / "settings.json"
        settings.parent.mkdir(parents=True)
        settings.write_text("{not json", encoding="utf-8")

        result = self.runner.invoke(main, ["gemini", "validate", "--project-dir", str(self.project_dir)])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("not valid JSON", result.output)

    def test_validate_invalid_mcp_servers_shape(self):
        """mcpServers must be an object of objects."""
        settings = self.project_dir / ".gemini" / "settings.json"
        settings.parent.mkdir(parents=True)
        settings.write_text(json.dumps({"mcpServers": {"bad": "not-an-object"}}), encoding="utf-8")

        result = self.runner.invoke(main, ["gemini", "validate", "--project-dir", str(self.project_dir)])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("mcpServers.bad must be an object", result.output)

    def test_validate_json_output_valid(self):
        """AC2: --json emits structured output with valid=true."""
        self._add_command("deploy")
        self._add_mcp()
        self.runner.invoke(main, ["gemini", "install", "--project-dir", str(self.project_dir), "--force"])

        result = self.runner.invoke(main, ["gemini", "validate", "--project-dir", str(self.project_dir), "--json"])
        self.assertEqual(result.exit_code, 0, result.output)
        data = json.loads(result.output)
        self.assertTrue(data["valid"])
        self.assertEqual(data["errors"], [])
        self.assertTrue(any("settings.json" in p for p in data["checked"]))

    def test_validate_json_output_invalid(self):
        """AC2: --json emits valid=false plus the error list."""
        commands_dir = self.project_dir / ".gemini" / "commands"
        commands_dir.mkdir(parents=True)
        (commands_dir / "broken.toml").write_text("prompt = [broken\n", encoding="utf-8")

        result = self.runner.invoke(main, ["gemini", "validate", "--project-dir", str(self.project_dir), "--json"])
        self.assertNotEqual(result.exit_code, 0)
        data = json.loads(result.output)
        self.assertFalse(data["valid"])
        self.assertTrue(data["errors"])

    def test_validate_missing_files_is_valid(self):
        """No Gemini config at all → still valid (nothing to validate)."""
        result = self.runner.invoke(main, ["gemini", "validate", "--project-dir", str(self.project_dir)])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Gemini CLI configuration is valid.", result.output)

    def test_validate_extension_manifest_checked(self):
        """Installed extension manifests are validated when present."""
        manifest_dir = self.patch_home / ".gemini" / "extensions" / "my-ext"
        manifest_dir.mkdir(parents=True)
        (manifest_dir / "gemini-extension.json").write_text(
            json.dumps({"mcpServers": {}}),
            encoding="utf-8",  # missing required "name"
        )

        result = self.runner.invoke(main, ["gemini", "validate", "--project-dir", str(self.project_dir), "--json"])
        self.assertNotEqual(result.exit_code, 0)
        data = json.loads(result.output)
        self.assertTrue(any("missing required 'name'" in e for e in data["errors"]))


class TestGeminiUnitExport(unittest.TestCase):
    """Pure-function tests for conversion and validation helpers."""

    def test_export_command_toml_with_frontmatter(self):
        """T4: frontmatter description + body → TOML description + prompt."""
        text = export_command_toml("deploy", _MD_WITH_FRONTMATTER)
        data = tomllib.loads(text)
        self.assertEqual(data["description"], "Deploy the application")
        self.assertIn("# Deploy steps", data["prompt"])

    def test_export_command_toml_without_frontmatter(self):
        """T5: body-only content keeps the whole text as the prompt."""
        text = export_command_toml("plain", _MD_WITHOUT_FRONTMATTER)
        data = tomllib.loads(text)
        self.assertEqual(data["description"], "")
        self.assertEqual(data["prompt"].strip(), "Just do the thing.")

    def test_export_command_toml_escapes_triple_quotes(self):
        """`\"\"\"` inside the prompt is escaped (design M5-3) and round-trips."""
        tricky = 'before """ inside after\n'
        text = export_command_toml("tricky", tricky)
        self.assertIn('""\\"', text)
        data = tomllib.loads(text)
        self.assertEqual(data["prompt"], tricky)

    def test_export_command_toml_escapes_trailing_backslash(self):
        """A trailing backslash must not escape the closing delimiter."""
        tricky = "ends with backslash \\"
        text = export_command_toml("slash", tricky)
        data = tomllib.loads(text)
        self.assertEqual(data["prompt"], tricky + "\n")

    def test_parse_command_markdown_no_frontmatter(self):
        """T5: no frontmatter → (\"\", whole content)."""
        description, body = parse_command_markdown(_MD_WITHOUT_FRONTMATTER)
        self.assertEqual(description, "")
        self.assertEqual(body, _MD_WITHOUT_FRONTMATTER)

    def test_export_mcp_env_format(self):
        """AC2: env values use ${KEY} expansion syntax."""
        server = MCPServer(name="github", command="npx", args=["-y"], env_keys=["GITHUB_TOKEN"])
        data = export_mcp([server])
        self.assertEqual(data["mcpServers"]["github"]["env"], {"GITHUB_TOKEN": "${GITHUB_TOKEN}"})

    def test_export_mcp_skips_disabled(self):
        """Disabled servers are filtered out."""
        server = MCPServer(name="off", command="x", enabled=False)
        self.assertEqual(export_mcp([server])["mcpServers"], {})

    def test_generate_extension_manifest_fields(self):
        """Manifest dict carries the spec fields (name/version/context)."""
        manifest = generate_extension_manifest("my-project", context_file="GEMINI.md")
        self.assertEqual(manifest["name"], "my-project")
        self.assertEqual(manifest["version"], "1.0.0")
        self.assertEqual(manifest["contextFileName"], "GEMINI.md")
        self.assertNotIn("mcpServers", manifest)  # no servers → key omitted

    def test_validate_settings_rejects_bad_shapes(self):
        """JSON errors and non-object mcpServers are reported."""
        with tempfile.TemporaryDirectory() as tmp:
            bad_json = Path(tmp) / "settings.json"
            bad_json.write_text("{oops", encoding="utf-8")
            self.assertTrue(validate_settings(bad_json))

            bad_shape = Path(tmp) / "shape.json"
            bad_shape.write_text(json.dumps({"mcpServers": []}), encoding="utf-8")
            self.assertTrue(any("'mcpServers' must be an object" in e for e in validate_settings(bad_shape)))

    def test_validate_extension_manifest_requires_name(self):
        """A manifest without a non-empty name is rejected."""
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "gemini-extension.json"
            manifest.write_text(json.dumps({"version": "1.0.0"}), encoding="utf-8")
            self.assertTrue(any("missing required 'name'" in e for e in validate_extension_manifest(manifest)))

    def test_validate_command_toml_rejects_bad_toml(self):
        """Unparseable TOML and wrong prompt types are reported."""
        with tempfile.TemporaryDirectory() as tmp:
            broken = Path(tmp) / "broken.toml"
            broken.write_text("prompt = [oops\n", encoding="utf-8")
            self.assertTrue(any("not valid TOML" in e for e in validate_command_toml(broken)))

            wrong_type = Path(tmp) / "wrong.toml"
            wrong_type.write_text("prompt = 42\n", encoding="utf-8")
            self.assertTrue(any("'prompt' must be a string" in e for e in validate_command_toml(wrong_type)))


if __name__ == "__main__":
    unittest.main()
