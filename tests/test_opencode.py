"""Tests for opencode.py."""

import json
import os
import tempfile
import unittest
from pathlib import Path

from click.testing import CliRunner

from ai_adapter.cli import main
from ai_adapter.config import init


class TestOpencodeCommands(unittest.TestCase):
    """Tests for opencode subcommands."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.orig_cwd = Path.cwd()
        self.isolated_dir = Path(self.temp_dir.name) / "project"
        self.isolated_dir.mkdir(parents=True)
        os.chdir(self.isolated_dir)

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
        os.chdir(self.orig_cwd)
        self.temp_dir.cleanup()

    def test_opencode_install_default(self):
        """Verify opencode install generates opencode.json with default instructions when nothing registered."""
        result = self.runner.invoke(main, ["opencode", "install"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("opencode.json", result.output)

        output_path = Path.cwd() / "opencode.json"
        self.assertTrue(output_path.exists())
        with open(output_path) as f:
            data = json.load(f)
        self.assertIn("$schema", data)
        self.assertIn("instructions", data)
        self.assertIn("permission", data)
        # No agents/instructions registered → only the fallback
        self.assertIn(".github/copilot-instructions.md", data["instructions"])
        self.assertNotIn(".github/agents/*.agent.md", data["instructions"])

        output_path.unlink()

    def test_opencode_install_with_agents(self):
        """Registered agents → .github/agents/*.agent.md appears."""
        agent_file = Path(self.temp_dir.name) / "reviewer.md"
        agent_file.write_text("# Reviewer")
        self.runner.invoke(main, ["sub-agent", "add", str(agent_file)])

        result = self.runner.invoke(main, ["opencode", "install"])
        self.assertEqual(result.exit_code, 0)

        output_path = Path.cwd() / "opencode.json"
        with open(output_path) as f:
            data = json.load(f)
        self.assertIn(".github/agents/*.agent.md", data["instructions"])
        output_path.unlink()

    def test_opencode_install_with_instructions(self):
        """Registered root-level instructions → file name appears."""
        inst_file = Path(self.temp_dir.name) / "AGENTS.md"
        inst_file.write_text("# Root Agent")
        self.runner.invoke(main, ["agent", "add", str(inst_file)])

        result = self.runner.invoke(main, ["opencode", "install"])
        self.assertEqual(result.exit_code, 0)

        output_path = Path.cwd() / "opencode.json"
        with open(output_path) as f:
            data = json.load(f)
        self.assertIn("AGENTS.md", data["instructions"])
        self.assertNotIn(".github/agents/*.agent.md", data["instructions"])
        output_path.unlink()

    def test_opencode_install_with_both(self):
        """Both agents and instructions registered → both appear."""
        inst_file = Path(self.temp_dir.name) / "AGENTS.md"
        inst_file.write_text("# Root Agent")
        self.runner.invoke(main, ["agent", "add", str(inst_file)])
        agent_file = Path(self.temp_dir.name) / "reviewer.md"
        agent_file.write_text("# Reviewer")
        self.runner.invoke(main, ["sub-agent", "add", str(agent_file)])

        result = self.runner.invoke(main, ["opencode", "install"])
        self.assertEqual(result.exit_code, 0)

        output_path = Path.cwd() / "opencode.json"
        with open(output_path) as f:
            data = json.load(f)
        self.assertIn("AGENTS.md", data["instructions"])
        self.assertIn(".github/agents/*.agent.md", data["instructions"])
        output_path.unlink()

    def test_opencode_uninstall(self):
        """Verify opencode uninstall removes opencode.json."""
        # Install first
        output_path = Path.cwd() / "opencode.json"
        output_path.write_text("{}")

        result = self.runner.invoke(main, ["opencode", "uninstall"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("opencode.json", result.output)
        self.assertFalse(output_path.exists())

    def test_opencode_uninstall_not_found(self):
        """Verify uninstall does not error when no opencode.json."""
        result = self.runner.invoke(main, ["opencode", "uninstall"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("not found", result.output)

    def test_opencode_alias_no_github(self):
        """Verify alias errors when .github does not exist."""
        result = self.runner.invoke(main, ["opencode", "alias"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn(".github", result.output)

    def test_opencode_install_template_structure_default(self):
        """Verify default opencode.json structure when nothing registered."""
        result = self.runner.invoke(main, ["opencode", "install"])
        self.assertEqual(result.exit_code, 0)

        output_path = Path.cwd() / "opencode.json"
        self.assertTrue(output_path.exists())
        with open(output_path) as f:
            data = json.load(f)

        # Verify all permissions are "ask"
        perm = data.get("permission", {})
        for key in ["read", "edit", "glob", "grep", "list", "bash", "task", "webfetch", "websearch", "todowrite"]:
            self.assertEqual(perm.get(key), "ask", f"permission.{key} is not ask")

        # instructions includes copilot-instructions.md
        self.assertIn(".github/copilot-instructions.md", data.get("instructions", []))
        # No agents registered, so .agent.md glob should NOT appear
        self.assertNotIn(".github/agents/*.agent.md", data.get("instructions", []))
        # No MCP or skills registered
        self.assertNotIn("mcp", data)
        self.assertNotIn("skills", data)

        output_path.unlink()

    def test_opencode_install_with_mcp_single(self):
        """Single MCP server → mcp section with correct format."""
        self.runner.invoke(
            main,
            [
                "mcp",
                "add",
                "github",
                "--command",
                "npx",
                "--args",
                "@modelcontextprotocol/server-github",
            ],
        )

        result = self.runner.invoke(main, ["opencode", "install"])
        self.assertEqual(result.exit_code, 0)

        output_path = Path.cwd() / "opencode.json"
        with open(output_path) as f:
            data = json.load(f)
        self.assertIn("mcp", data)
        self.assertIn("github", data["mcp"])
        self.assertEqual(data["mcp"]["github"]["type"], "local")
        self.assertEqual(data["mcp"]["github"]["command"], ["npx", "@modelcontextprotocol/server-github"])
        self.assertTrue(data["mcp"]["github"]["enabled"])
        output_path.unlink()

    def test_opencode_install_with_mcp_multiple(self):
        """Multiple MCP servers → all appear in mcp section."""
        self.runner.invoke(
            main,
            ["mcp", "add", "github", "--command", "npx", "--args", "pkg1"],
        )
        self.runner.invoke(
            main,
            ["mcp", "add", "playwright", "--command", "npx", "--args", "pkg2"],
        )

        result = self.runner.invoke(main, ["opencode", "install"])
        self.assertEqual(result.exit_code, 0)

        output_path = Path.cwd() / "opencode.json"
        with open(output_path) as f:
            data = json.load(f)
        self.assertIn("github", data["mcp"])
        self.assertIn("playwright", data["mcp"])
        self.assertEqual(data["mcp"]["github"]["command"], ["npx", "pkg1"])
        self.assertEqual(data["mcp"]["playwright"]["command"], ["npx", "pkg2"])
        output_path.unlink()

    def test_opencode_install_with_mcp_env_keys(self):
        """MCP server with env_keys → environment section with ${VAR} format."""
        self.runner.invoke(
            main,
            [
                "mcp",
                "add",
                "github",
                "--command",
                "npx",
                "--args",
                "pkg",
                "--env-key",
                "GITHUB_TOKEN",
            ],
        )

        result = self.runner.invoke(main, ["opencode", "install"])
        self.assertEqual(result.exit_code, 0)

        output_path = Path.cwd() / "opencode.json"
        with open(output_path) as f:
            data = json.load(f)
        self.assertIn("environment", data["mcp"]["github"])
        self.assertEqual(data["mcp"]["github"]["environment"]["GITHUB_TOKEN"], "${GITHUB_TOKEN}")
        output_path.unlink()

    def test_opencode_install_with_mcp_disabled(self):
        """Disabled MCP server → enabled: false in output."""
        self.runner.invoke(
            main,
            ["mcp", "add", "test-srv", "--command", "npx", "--args", "pkg"],
        )
        # Manually disable the server via config
        from ai_adapter.config import load_config, save_config

        cfg = load_config()
        for s in cfg.mcp_servers:
            if s.name == "test-srv":
                s.enabled = False
        save_config(cfg)

        result = self.runner.invoke(main, ["opencode", "install"])
        self.assertEqual(result.exit_code, 0)

        output_path = Path.cwd() / "opencode.json"
        with open(output_path) as f:
            data = json.load(f)
        self.assertFalse(data["mcp"]["test-srv"]["enabled"])
        output_path.unlink()

    def test_opencode_install_with_mcp_no_args(self):
        """MCP server with no args → command array has single element."""
        self.runner.invoke(
            main,
            ["mcp", "add", "simple", "--command", "my-server"],
        )

        result = self.runner.invoke(main, ["opencode", "install"])
        self.assertEqual(result.exit_code, 0)

        output_path = Path.cwd() / "opencode.json"
        with open(output_path) as f:
            data = json.load(f)
        self.assertEqual(data["mcp"]["simple"]["command"], ["my-server"])
        output_path.unlink()

    def test_opencode_install_with_skills(self):
        """Registered skills → skills.paths section added."""
        skill_dir = Path(self.temp_dir.name) / "my-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("---\nname: my-skill\n---\n# Skill\n")
        self.runner.invoke(main, ["skill", "add", str(skill_dir)])

        result = self.runner.invoke(main, ["opencode", "install"])
        self.assertEqual(result.exit_code, 0)

        output_path = Path.cwd() / "opencode.json"
        with open(output_path) as f:
            data = json.load(f)
        self.assertIn("skills", data)
        self.assertIn(".github/skills", data["skills"]["paths"])
        # instructions also includes SKILL.md glob
        self.assertIn(".github/skills/*/SKILL.md", data["instructions"])
        output_path.unlink()

    def test_opencode_install_with_mcp_and_skills(self):
        """Both MCP and skills registered → both sections present."""
        self.runner.invoke(
            main,
            ["mcp", "add", "github", "--command", "npx", "--args", "pkg"],
        )
        skill_dir = Path(self.temp_dir.name) / "my-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("---\nname: my-skill\n---\n# Skill\n")
        self.runner.invoke(main, ["skill", "add", str(skill_dir)])

        result = self.runner.invoke(main, ["opencode", "install"])
        self.assertEqual(result.exit_code, 0)

        output_path = Path.cwd() / "opencode.json"
        with open(output_path) as f:
            data = json.load(f)
        self.assertIn("mcp", data)
        self.assertIn("skills", data)
        self.assertIn("instructions", data)
        output_path.unlink()

    def test_opencode_install_with_prompts(self):
        """Registered prompts → command section with template and description."""
        prompt_file = Path(self.temp_dir.name) / "code-review.md"
        prompt_file.write_text("Review this code for bugs and improvements.")
        self.runner.invoke(main, ["prompt", "add", str(prompt_file)])

        result = self.runner.invoke(main, ["opencode", "install"])
        self.assertEqual(result.exit_code, 0)

        output_path = Path.cwd() / "opencode.json"
        with open(output_path) as f:
            data = json.load(f)
        self.assertIn("command", data)
        self.assertIn("code-review", data["command"])
        self.assertEqual(
            data["command"]["code-review"]["template"],
            "Review this code for bugs and improvements.",
        )
        output_path.unlink()

    def test_opencode_install_with_prompts_multiple(self):
        """Multiple prompts → all appear in command section."""
        prompt1 = Path(self.temp_dir.name) / "review.md"
        prompt1.write_text("Review prompt content")
        self.runner.invoke(main, ["prompt", "add", str(prompt1)])

        prompt2 = Path(self.temp_dir.name) / "refactor.md"
        prompt2.write_text("Refactor prompt content")
        self.runner.invoke(main, ["prompt", "add", str(prompt2)])

        result = self.runner.invoke(main, ["opencode", "install"])
        self.assertEqual(result.exit_code, 0)

        output_path = Path.cwd() / "opencode.json"
        with open(output_path) as f:
            data = json.load(f)
        self.assertIn("review", data["command"])
        self.assertIn("refactor", data["command"])
        self.assertEqual(data["command"]["review"]["template"], "Review prompt content")
        self.assertEqual(data["command"]["refactor"]["template"], "Refactor prompt content")
        output_path.unlink()

    def test_opencode_install_with_all_features(self):
        """All features registered → all sections present."""
        # MCP
        self.runner.invoke(
            main,
            ["mcp", "add", "github", "--command", "npx", "--args", "pkg"],
        )
        # Skills
        skill_dir = Path(self.temp_dir.name) / "my-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("---\nname: my-skill\n---\n# Skill\n")
        self.runner.invoke(main, ["skill", "add", str(skill_dir)])
        # Prompts
        prompt_file = Path(self.temp_dir.name) / "review.md"
        prompt_file.write_text("Review content")
        self.runner.invoke(main, ["prompt", "add", str(prompt_file)])
        # Agents
        agent_file = Path(self.temp_dir.name) / "reviewer.md"
        agent_file.write_text("# Reviewer")
        self.runner.invoke(main, ["sub-agent", "add", str(agent_file)])

        result = self.runner.invoke(main, ["opencode", "install"])
        self.assertEqual(result.exit_code, 0)

        output_path = Path.cwd() / "opencode.json"
        with open(output_path) as f:
            data = json.load(f)
        self.assertIn("mcp", data)
        self.assertIn("skills", data)
        self.assertIn("command", data)
        self.assertIn(".github/agents/*.agent.md", data["instructions"])
        self.assertIn(".github/skills/*/SKILL.md", data["instructions"])
        output_path.unlink()

    def test_opencode_install_prompt_file_not_found(self):
        """Prompt file deleted after registration → warning and skipped."""
        prompt_file = Path(self.temp_dir.name) / "review.md"
        prompt_file.write_text("Review content")
        self.runner.invoke(main, ["prompt", "add", str(prompt_file)])
        # Delete the file after registration
        prompts_dir = Path.home() / ".ai-adapter" / "prompts"
        (prompts_dir / "review.md").unlink()

        result = self.runner.invoke(main, ["opencode", "install"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("not found", result.output)

        output_path = Path.cwd() / "opencode.json"
        with open(output_path) as f:
            data = json.load(f)
        # command section should not exist since prompt was skipped
        self.assertNotIn("command", data)
        output_path.unlink()

    def test_opencode_install_prompt_txt_extension(self):
        """Prompt with .txt extension → found and included."""
        prompt_file = Path(self.temp_dir.name) / "review.txt"
        prompt_file.write_text("Review content from txt")
        self.runner.invoke(main, ["prompt", "add", str(prompt_file)])

        result = self.runner.invoke(main, ["opencode", "install"])
        self.assertEqual(result.exit_code, 0)

        output_path = Path.cwd() / "opencode.json"
        with open(output_path) as f:
            data = json.load(f)
        self.assertIn("command", data)
        self.assertIn("review", data["command"])
        self.assertEqual(data["command"]["review"]["template"], "Review content from txt")
        output_path.unlink()

    def test_opencode_install_no_command_when_no_prompts(self):
        """No prompts registered → command section absent."""
        result = self.runner.invoke(main, ["opencode", "install"])
        self.assertEqual(result.exit_code, 0)

        output_path = Path.cwd() / "opencode.json"
        with open(output_path) as f:
            data = json.load(f)
        self.assertNotIn("command", data)
        output_path.unlink()


class TestOpencodeValidateCommand(unittest.TestCase):
    """Tests for opencode validate subcommand."""

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

        # Backup real .github/ to protect from test cleanup
        self._github_bak = None
        github_dir = Path.cwd() / ".github"
        if github_dir.exists():
            import shutil

            self._github_bak = Path(self.temp_dir.name) / "github.bak"
            shutil.copytree(github_dir, self._github_bak)

    def tearDown(self):
        import pathlib

        pathlib.Path.home = staticmethod(self._original_home)
        import ai_adapter.config as cfg

        cfg.AI_ADAPTER_DIR = Path.home() / ".ai-adapter"
        # Restore .github/ from backup
        if hasattr(self, "_github_bak") and self._github_bak and Path(self._github_bak).exists():
            import shutil

            github_dir = Path.cwd() / ".github"
            if github_dir.exists():
                shutil.rmtree(github_dir)
            shutil.copytree(self._github_bak, github_dir)
        self.temp_dir.cleanup()

    def _create_github_agents(self) -> Path:
        """Create .github/agents/ in temp dir and return the path."""
        agents_dir = Path.cwd() / ".github" / "agents"
        agents_dir.mkdir(parents=True, exist_ok=True)
        return agents_dir

    def test_opencode_validate_valid(self):
        """All files valid → exit 0."""
        # Create a valid opencode.json
        config_path = Path.cwd() / "opencode.json"
        config_path.write_text(
            json.dumps(
                {
                    "$schema": "https://opencode.ai/config.json",
                    "instructions": [".github/copilot-instructions.md"],
                    "permission": {"read": "ask", "edit": "ask"},
                }
            )
        )
        agents_dir = self._create_github_agents()
        (agents_dir / "good.agent.md").write_text("---\nname: good\ntools:\n  execute: true\n---\n")
        result = self.runner.invoke(main, ["opencode", "validate"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("All validations passed", result.output)

    def test_opencode_validate_invalid(self):
        """Invalid files detected → exit 1."""
        agents_dir = self._create_github_agents()
        (agents_dir / "bad.agent.md").write_text("---\nname: bad\ntools: [execute]\n---\n")
        result = self.runner.invoke(main, ["opencode", "validate"])
        self.assertEqual(result.exit_code, 1)
        self.assertIn("array format", result.output)

    def test_opencode_validate_fix(self):
        """``--fix`` automatically repairs invalid files."""
        agents_dir = self._create_github_agents()
        bad_file = agents_dir / "bad.agent.md"
        bad_file.write_text("---\nname: bad\ntools: [execute]\n---\n")
        # Provide a valid opencode.json so the run is self-contained: without it,
        # validate --fix reports "opencode.json not found" as an error (rc=1).
        config_path = Path.cwd() / "opencode.json"
        config_path.write_text(
            json.dumps(
                {
                    "$schema": "https://opencode.ai/config.json",
                    "instructions": [".github/copilot-instructions.md"],
                    "permission": {"read": "ask", "edit": "ask"},
                }
            )
        )
        result = self.runner.invoke(main, ["opencode", "validate", "--fix"])
        self.assertEqual(result.exit_code, 0)  # fixed, so no errors

        content = bad_file.read_text()
        # But wait -- after fixing, validate returns no errors,
        # so exit code should be 0.
        self.assertIn("  execute: true", content)

    def test_opencode_validate_quiet(self):
        """``--quiet`` minimises output, still returns exit code."""
        agents_dir = self._create_github_agents()
        (agents_dir / "bad.agent.md").write_text("---\nname: bad\ntools: [execute]\n---\n")
        result = self.runner.invoke(main, ["opencode", "validate", "--quiet"])
        self.assertEqual(result.exit_code, 1)
        self.assertEqual(result.output.strip(), "")

    def test_opencode_validate_no_agents_dir(self):
        """No ``.github/agents/`` and no opencode.json → exit 1 with error."""
        # Ensure agents/ doesn't exist for this test
        agents_dir = Path.cwd() / ".github" / "agents"
        if agents_dir.exists():
            import shutil

            shutil.rmtree(agents_dir)
        # Also remove any existing opencode.json
        config_path = Path.cwd() / "opencode.json"
        if config_path.exists():
            config_path.unlink()
        result = self.runner.invoke(main, ["opencode", "validate"])
        self.assertEqual(result.exit_code, 1)
        self.assertIn("opencode.json not found", result.output)

    def test_opencode_validate_config_valid(self):
        """Valid opencode.json → exit 0."""
        config_path = Path.cwd() / "opencode.json"
        config_path.write_text(
            json.dumps(
                {
                    "$schema": "https://opencode.ai/config.json",
                    "instructions": [".github/copilot-instructions.md"],
                    "permission": {"read": "ask", "edit": "ask"},
                }
            )
        )
        result = self.runner.invoke(main, ["opencode", "validate", "--config-only"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("All validations passed", result.output)

    def test_opencode_validate_config_invalid_json(self):
        """Invalid JSON → exit 1 with error."""
        config_path = Path.cwd() / "opencode.json"
        config_path.write_text("{invalid json}}")
        result = self.runner.invoke(main, ["opencode", "validate", "--config-only"])
        self.assertEqual(result.exit_code, 1)
        self.assertIn("Invalid JSON", result.output)

    def test_opencode_validate_config_not_object(self):
        """JSON not an object → exit 1."""
        config_path = Path.cwd() / "opencode.json"
        config_path.write_text('"just a string"')
        result = self.runner.invoke(main, ["opencode", "validate", "--config-only"])
        self.assertEqual(result.exit_code, 1)
        self.assertIn("must be a JSON object", result.output)

    def test_opencode_validate_config_invalid_permission_key(self):
        """Unknown permission key → exit 1."""
        config_path = Path.cwd() / "opencode.json"
        config_path.write_text(
            json.dumps(
                {
                    "permission": {"invalid_key": "ask"},
                }
            )
        )
        result = self.runner.invoke(main, ["opencode", "validate", "--config-only"])
        self.assertEqual(result.exit_code, 1)
        self.assertIn("Unknown permission key", result.output)

    def test_opencode_validate_config_invalid_permission_value(self):
        """Invalid permission value → exit 1."""
        config_path = Path.cwd() / "opencode.json"
        config_path.write_text(
            json.dumps(
                {
                    "permission": {"read": "invalid"},
                }
            )
        )
        result = self.runner.invoke(main, ["opencode", "validate", "--config-only"])
        self.assertEqual(result.exit_code, 1)
        self.assertIn("invalid value", result.output)

    def test_opencode_validate_config_mcp_missing_type(self):
        """MCP server missing type → exit 1."""
        config_path = Path.cwd() / "opencode.json"
        config_path.write_text(
            json.dumps(
                {
                    "mcp": {"github": {"command": ["npx", "pkg"]}},
                }
            )
        )
        result = self.runner.invoke(main, ["opencode", "validate", "--config-only"])
        self.assertEqual(result.exit_code, 1)
        self.assertIn("missing 'type'", result.output)

    def test_opencode_validate_config_mcp_invalid_type(self):
        """MCP server with invalid type → exit 1."""
        config_path = Path.cwd() / "opencode.json"
        config_path.write_text(
            json.dumps(
                {
                    "mcp": {"github": {"type": "invalid", "command": ["npx"]}},
                }
            )
        )
        result = self.runner.invoke(main, ["opencode", "validate", "--config-only"])
        self.assertEqual(result.exit_code, 1)
        self.assertIn("invalid type", result.output)

    def test_opencode_validate_config_mcp_missing_command(self):
        """MCP server missing command → exit 1."""
        config_path = Path.cwd() / "opencode.json"
        config_path.write_text(
            json.dumps(
                {
                    "mcp": {"github": {"type": "local"}},
                }
            )
        )
        result = self.runner.invoke(main, ["opencode", "validate", "--config-only"])
        self.assertEqual(result.exit_code, 1)
        self.assertIn("missing 'command'", result.output)

    def test_opencode_validate_config_command_missing_template(self):
        """Command missing template → exit 1."""
        config_path = Path.cwd() / "opencode.json"
        config_path.write_text(
            json.dumps(
                {
                    "command": {"review": {"description": "Review code"}},
                }
            )
        )
        result = self.runner.invoke(main, ["opencode", "validate", "--config-only"])
        self.assertEqual(result.exit_code, 1)
        self.assertIn("missing required 'template'", result.output)

    def test_opencode_validate_config_skills_not_array(self):
        """skills.paths not an array → exit 1."""
        config_path = Path.cwd() / "opencode.json"
        config_path.write_text(
            json.dumps(
                {
                    "skills": {"paths": "not-an-array"},
                }
            )
        )
        result = self.runner.invoke(main, ["opencode", "validate", "--config-only"])
        self.assertEqual(result.exit_code, 1)
        self.assertIn("'skills.paths' must be an array", result.output)

    def test_opencode_validate_config_instructions_not_array(self):
        """instructions not an array → exit 1."""
        config_path = Path.cwd() / "opencode.json"
        config_path.write_text(
            json.dumps(
                {
                    "instructions": "not-an-array",
                }
            )
        )
        result = self.runner.invoke(main, ["opencode", "validate", "--config-only"])
        self.assertEqual(result.exit_code, 1)
        self.assertIn("'instructions' must be an array", result.output)

    def test_opencode_validate_config_no_file(self):
        """No opencode.json → exit 1 with error."""
        # Remove any existing opencode.json
        config_path = Path.cwd() / "opencode.json"
        if config_path.exists():
            config_path.unlink()
        result = self.runner.invoke(main, ["opencode", "validate", "--config-only"])
        self.assertEqual(result.exit_code, 1)
        self.assertIn("opencode.json not found", result.output)

    def test_opencode_validate_generated_config_is_valid(self):
        """Config generated by opencode install → passes validation."""
        self.runner.invoke(main, ["opencode", "install"])
        result = self.runner.invoke(main, ["opencode", "validate", "--config-only"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("All validations passed", result.output)


class TestOpencodeAliasValidation(unittest.TestCase):
    """Tests for opencode alias validation logic."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        # Work inside temp dir so CWD is isolated
        self.orig_cwd = Path.cwd()
        self.work_dir = Path(self.temp_dir.name) / "project"
        self.work_dir.mkdir(parents=True)
        self.work_dir = self.work_dir.resolve()
        os.chdir(self.work_dir)

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
        os.chdir(self.orig_cwd)

    def _create_github_with_agents(self) -> Path:
        """Create .github/agents/ with a valid agent file."""
        agents_dir = self.work_dir / ".github" / "agents"
        agents_dir.mkdir(parents=True, exist_ok=True)
        return agents_dir

    def test_opencode_alias_validates_and_fixes(self):
        """Alias detects invalid agents and prompts to fix."""
        agents_dir = self._create_github_with_agents()
        bad_file = agents_dir / "bad.agent.md"
        bad_file.write_text("---\nname: bad\ntools: [execute]\n---\n")

        # Input 'y' to confirm fixing
        result = self.runner.invoke(
            main,
            ["opencode", "alias"],
            input="y\n",
        )
        # After fixing, symlink should be created
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Symlink created", result.output)

        # File should be fixed
        content = bad_file.read_text()
        self.assertIn("  execute: true", content)
        self.assertNotIn("[execute]", content)

        # Cleanup symlink
        (self.work_dir / ".opencode").unlink()

    def test_opencode_alias_no_github_agents(self):
        """No ``.github/agents/`` → alias proceeds without validation."""
        # Create .github without agents/
        (self.work_dir / ".github").mkdir(parents=True)

        result = self.runner.invoke(main, ["opencode", "alias"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Symlink created", result.output)

        (self.work_dir / ".opencode").unlink()
