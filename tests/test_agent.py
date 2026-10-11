"""Tests for agent.py."""

import tempfile
import unittest
from pathlib import Path

from click.testing import CliRunner

from ai_adapter.cli import main
from ai_adapter.config import init


def _safe_github_cleanup(base_dir):
    """Remove only test-created files from .github/ subdirectories.

    Preserves directory structure and workflow files.
    """
    github = Path(base_dir) / ".github"
    if not github.exists():
        return
    for sub in ("agents", "bin", "skills", "commands", "prompts"):
        d = github / sub
        if d.exists() and d.is_dir():
            for f in d.iterdir():
                if f.is_file() and f.name != "ci.yml":
                    f.unlink(missing_ok=True)


class TestAgentAddRecCommand(unittest.TestCase):
    """Tests for the agent add-rec command."""

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

    def test_agent_add_rec(self):
        """Verify add-rec registers all agents in a directory."""
        src_dir = Path(self.temp_dir.name) / "agents_dir"
        src_dir.mkdir()
        (src_dir / "agent1.md").write_text("# Agent 1")
        (src_dir / "agent2.md").write_text("# Agent 2")

        result = self.runner.invoke(main, ["sub-agent", "add-rec", str(src_dir)])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("2", result.output)

        # Verify via list
        result = self.runner.invoke(main, ["sub-agent", "list"])
        self.assertIn("agent1", result.output)
        self.assertIn("agent2", result.output)


class TestAgentCommands(unittest.TestCase):
    """Tests for agent subcommands."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.patch_home = Path(self.temp_dir.name)
        self.runner = CliRunner()

        # Replace Home
        import pathlib

        self._original_home = pathlib.Path.home
        pathlib.Path.home = staticmethod(lambda: self.patch_home)

        import ai_adapter.config as cfg

        cfg.AI_ADAPTER_DIR = self.patch_home / ".ai-adapter"

        # init
        init()

        # Backup real .github/ to protect from test cleanup
        self._github_bak = None
        github_dir = Path.cwd() / ".github"
        if github_dir.exists():
            import shutil

            self._github_bak = Path(self.temp_dir.name) / "github.bak"
            shutil.copytree(github_dir, self._github_bak)

        # Ensure .github/agents/ is empty for test isolation
        github_agents = Path.cwd() / ".github" / "agents"
        if github_agents.exists():
            for f in github_agents.iterdir():
                if f.is_file():
                    f.unlink()

        # Create test agent file
        self.agent_file = Path(self.temp_dir.name) / "test-agent.md"
        self.agent_file.write_text("# Test Agent\nThis is a test agent.")

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

    def test_agent_list_empty(self):
        """Verify empty message is shown when no agents registered."""
        result = self.runner.invoke(main, ["sub-agent", "list"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("No agents registered.", result.output)

    def test_agent_add(self):
        """Verify agent add adds an agent."""
        result = self.runner.invoke(main, ["sub-agent", "add", str(self.agent_file)])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("test-agent", result.output)

        # Verify file was copied
        agents_dir = self.patch_home / ".ai-adapter" / "agents"
        self.assertTrue((agents_dir / "test-agent.md").exists())

    def test_agent_add_and_list(self):
        """Verify agent add → agent list flow."""
        self.runner.invoke(main, ["sub-agent", "add", str(self.agent_file)])
        result = self.runner.invoke(main, ["sub-agent", "list"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("test-agent", result.output)

    def test_agent_get(self):
        """Verify agent get copies to .github/agents/."""
        self.runner.invoke(main, ["sub-agent", "add", str(self.agent_file)])

        # Create .github/agents/ in the current directory (inside temp dir)
        github_agents = Path.cwd() / ".github" / "agents"
        github_agents.mkdir(parents=True, exist_ok=True)

        result = self.runner.invoke(main, ["sub-agent", "get", "test-agent"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("test-agent.md", result.output)
        self.assertTrue((github_agents / "test-agent.md").exists())

        # Cleanup

    def test_agent_get_not_found(self):
        """Verify get fails for non-existent agent."""
        result = self.runner.invoke(main, ["sub-agent", "get", "nonexistent"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("not found", result.output)

    def test_agent_get_force_overwrite(self):
        """Verify agent get --force overwrites without confirmation."""
        self.runner.invoke(main, ["sub-agent", "add", str(self.agent_file)])

        github_dir = Path.cwd() / ".github" / "agents"
        github_dir.mkdir(parents=True, exist_ok=True)

        # First get
        result = self.runner.invoke(main, ["sub-agent", "get", "test-agent"])
        self.assertEqual(result.exit_code, 0)

        # Second get with --force to overwrite
        result = self.runner.invoke(main, ["sub-agent", "get", "test-agent", "--force"])
        self.assertEqual(result.exit_code, 0)
        self.assertTrue((github_dir / "test-agent.md").exists())

    def test_agent_get_with_project_dir(self):
        """Verify agent get --project-dir copies to the specified directory."""
        self.runner.invoke(main, ["sub-agent", "add", str(self.agent_file)])

        # Create a custom project directory
        project_dir = Path(self.temp_dir.name) / "my-project"
        project_dir.mkdir(parents=True)

        result = self.runner.invoke(
            main,
            [
                "sub-agent",
                "get",
                "test-agent",
                "--project-dir",
                str(project_dir),
            ],
        )
        self.assertEqual(result.exit_code, 0)
        self.assertIn("test-agent.md", result.output)
        self.assertTrue((project_dir / ".github" / "agents" / "test-agent.md").exists())

    def test_agent_get_all(self):
        """Verify agent get-all copies all agents to .github/agents/."""
        agent1 = Path(self.temp_dir.name) / "agent1.md"
        agent1.write_text("# Agent 1")
        agent2 = Path(self.temp_dir.name) / "agent2.md"
        agent2.write_text("# Agent 2")
        self.runner.invoke(main, ["sub-agent", "add", str(agent1)])
        self.runner.invoke(main, ["sub-agent", "add", str(agent2)])

        github_agents = Path.cwd() / ".github" / "agents"
        github_agents.mkdir(parents=True, exist_ok=True)

        result = self.runner.invoke(main, ["sub-agent", "get-all"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("2", result.output)
        self.assertTrue((github_agents / "agent1.md").exists())
        self.assertTrue((github_agents / "agent2.md").exists())

    def test_agent_remove(self):
        """Verify agent remove removes an agent."""
        self.runner.invoke(main, ["sub-agent", "add", str(self.agent_file)])
        result = self.runner.invoke(main, ["sub-agent", "remove", "test-agent"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("test-agent", result.output)

        # Verify it is not displayed in list
        result = self.runner.invoke(main, ["sub-agent", "list"])
        self.assertIn("No agents registered.", result.output)

    def test_agent_remove_all(self):
        """Verify agent remove-all removes all agents."""
        # Add two agents
        agent1 = Path(self.temp_dir.name) / "agent1.md"
        agent1.write_text("# Agent 1")
        agent2 = Path(self.temp_dir.name) / "agent2.md"
        agent2.write_text("# Agent 2")
        self.runner.invoke(main, ["sub-agent", "add", str(agent1)])
        self.runner.invoke(main, ["sub-agent", "add", str(agent2)])

        result = self.runner.invoke(main, ["sub-agent", "remove-all", "--force"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("All agents", result.output)

        # List is now empty
        result = self.runner.invoke(main, ["sub-agent", "list"])
        self.assertIn("No agents registered.", result.output)

    def test_agent_add_agent_md_with_frontmatter(self):
        """Verify registering an .agent.md file uses the frontmatter name."""
        agent_md_file = Path(self.temp_dir.name) / "reviewer.agent.md"
        agent_md_file.write_text(
            "---\nname: Implementer\ndescription: Dev Agent\n---\n\n# Implementer\nThis is an implementer agent.\n"
        )

        result = self.runner.invoke(main, ["sub-agent", "add", str(agent_md_file)])
        self.assertEqual(result.exit_code, 0)
        # Registered name becomes "Implementer" (from frontmatter name)
        self.assertIn("'Implementer'", result.output)

        # "Implementer" is shown in list, "reviewer" is not
        result = self.runner.invoke(main, ["sub-agent", "list"])
        self.assertIn("Implementer", result.output)
        self.assertNotIn("reviewer", result.output)

    def test_agent_add_agent_md_without_frontmatter_fails(self):
        """Verify .agent.md without frontmatter raises an error."""
        bad_file = Path(self.temp_dir.name) / "bad.agent.md"
        bad_file.write_text("# Just a markdown\nNo frontmatter here.\n")

        result = self.runner.invoke(main, ["sub-agent", "add", str(bad_file)])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("frontmatter", result.output)

    def test_agent_add_agent_md_without_name_fails(self):
        """Verify .agent.md without name in frontmatter raises an error."""
        bad_file = Path(self.temp_dir.name) / "bad.agent.md"
        bad_file.write_text("---\ndescription: no name here\n---\n# Bad\n")

        result = self.runner.invoke(main, ["sub-agent", "add", str(bad_file)])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("name", result.output)

    def test_agent_get_agent_md_backward_compat(self):
        """Verify an agent registered with .agent.md can be retrieved by short name."""
        agent_md_file = Path(self.temp_dir.name) / "reviewer.agent.md"
        agent_md_file.write_text("---\nname: Implementer\n---\n# Implementer\n")
        self.runner.invoke(main, ["sub-agent", "add", str(agent_md_file)])

        github_agents = Path.cwd() / ".github" / "agents"
        github_agents.mkdir(parents=True, exist_ok=True)

        # Can be retrieved with "Implementer"
        result = self.runner.invoke(main, ["sub-agent", "get", "Implementer"])
        self.assertEqual(result.exit_code, 0)
        self.assertTrue((github_agents / "reviewer.agent.md").exists())

    def test_agent_get_with_dot_agent_suffix(self):
        """Verify backward compatibility: agents can be retrieved with .agent suffix."""
        agent_md_file = Path(self.temp_dir.name) / "reviewer.agent.md"
        agent_md_file.write_text("---\nname: Implementer\n---\n# Implementer\n")
        self.runner.invoke(main, ["sub-agent", "add", str(agent_md_file)])

        github_agents = Path.cwd() / ".github" / "agents"
        github_agents.mkdir(parents=True, exist_ok=True)

        # Can also be retrieved with "reviewer.agent" (backward compatibility)
        result = self.runner.invoke(main, ["sub-agent", "get", "reviewer.agent"])
        self.assertEqual(result.exit_code, 0)
        self.assertTrue((github_agents / "reviewer.agent.md").exists())


class TestAgentToolsConversion(unittest.TestCase):
    """Tests for tools format conversion in agent commands."""

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

    def test_agent_get_converts_tools_with_fix(self):
        """``sub-agent get --fix`` converts object-format tools to array format."""
        src = Path(self.temp_dir.name) / "my.agent.md"
        src.write_text("---\nname: myagent\ntools:\n  execute: true\n  read: true\n---\n# My Agent\n")
        # Default add = no conversion
        self.runner.invoke(main, ["sub-agent", "add", str(src)])

        # Run sub-agent get with --fix to convert
        github_agents = Path.cwd() / ".github" / "agents"
        github_agents.mkdir(parents=True, exist_ok=True)

        result = self.runner.invoke(main, ["sub-agent", "get", "myagent", "--fix"])
        self.assertEqual(result.exit_code, 0)

        dest = github_agents / "my.agent.md"
        self.assertTrue(dest.exists())

        content = dest.read_text()
        self.assertIn("tools: [execute, read]", content)
        self.assertNotIn("  execute: true", content)

        # Warning should be on stderr
        self.assertIn("Warning: converted tools format", result.output)

    def test_agent_get_warns_on_object_format(self):
        """``sub-agent get`` warns on object-format tools but does NOT convert."""
        src = Path(self.temp_dir.name) / "my.agent.md"
        src.write_text("---\nname: myagent\ntools:\n  execute: true\n  read: true\n---\n# My Agent\n")
        self.runner.invoke(main, ["sub-agent", "add", str(src)])

        github_agents = Path.cwd() / ".github" / "agents"
        github_agents.mkdir(parents=True, exist_ok=True)

        # Without --fix: warn but do NOT convert
        result = self.runner.invoke(main, ["sub-agent", "get", "myagent"])
        self.assertEqual(result.exit_code, 0)

        dest = github_agents / "my.agent.md"
        self.assertTrue(dest.exists())

        content = dest.read_text()
        self.assertIn("  execute: true", content)  # kept as-is
        self.assertIn("Warning:", result.output)
        self.assertIn("--fix", result.output)

    def test_agent_get_array_format_no_warning(self):
        """``sub-agent get`` passes array-format tools through silently (VS Code canonical)."""
        src = Path(self.temp_dir.name) / "my.agent.md"
        src.write_text("---\nname: myagent\ntools: [execute, read]\n---\n# My Agent\n")
        self.runner.invoke(main, ["sub-agent", "add", str(src)])

        github_agents = Path.cwd() / ".github" / "agents"
        github_agents.mkdir(parents=True, exist_ok=True)

        result = self.runner.invoke(main, ["sub-agent", "get", "myagent"])
        self.assertEqual(result.exit_code, 0)
        self.assertNotIn("Warning", result.output)
        self.assertIn("[execute, read]", (github_agents / "my.agent.md").read_text())

    def test_agent_get_all_converts_tools_with_fix(self):
        """``sub-agent get-all --fix`` converts object-format tools for all agents."""
        src1 = Path(self.temp_dir.name) / "alpha.agent.md"
        src1.write_text("---\nname: alpha\ntools:\n  execute: true\n---\n")
        src2 = Path(self.temp_dir.name) / "beta.agent.md"
        src2.write_text("---\nname: beta\ntools:\n  read: true\n  agent: true\n  skipme: false\n---\n")
        # Default add = no conversion
        self.runner.invoke(main, ["sub-agent", "add", str(src1)])
        self.runner.invoke(main, ["sub-agent", "add", str(src2)])

        github_agents = Path.cwd() / ".github" / "agents"
        github_agents.mkdir(parents=True, exist_ok=True)

        result = self.runner.invoke(main, ["sub-agent", "get-all", "--fix"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("2", result.output)

        # Check both files were converted (falsy entries dropped)
        content_alpha = (github_agents / "alpha.agent.md").read_text()
        self.assertIn("tools: [execute]", content_alpha)

        content_beta = (github_agents / "beta.agent.md").read_text()
        self.assertIn("tools: [read, agent]", content_beta)
        self.assertNotIn("skipme", content_beta)

    def test_agent_get_non_agent_md_unchanged(self):
        """Non-``.agent.md`` files are not converted (plain copy2)."""
        src = Path(self.temp_dir.name) / "plain.md"
        src.write_text("# Plain markdown\n")
        self.runner.invoke(main, ["sub-agent", "add", str(src)])

        github_agents = Path.cwd() / ".github" / "agents"
        github_agents.mkdir(parents=True, exist_ok=True)

        result = self.runner.invoke(main, ["sub-agent", "get", "plain"])
        self.assertEqual(result.exit_code, 0)

        dest = github_agents / "plain.md"
        self.assertTrue(dest.exists())
        self.assertEqual(dest.read_text(), "# Plain markdown\n")

    def test_agent_add_warns_on_object_format(self):
        """``sub-agent add`` warns on object-format tools but does NOT convert."""
        src = Path(self.temp_dir.name) / "new.agent.md"
        src.write_text("---\nname: newagent\ntools:\n  execute: true\n  read: true\n---\n# New Agent\n")

        result = self.runner.invoke(main, ["sub-agent", "add", str(src)])
        self.assertEqual(result.exit_code, 0)

        agents_dir = self.patch_home / ".ai-adapter" / "agents"
        dest = agents_dir / "new.agent.md"
        self.assertTrue(dest.exists())

        content = dest.read_text()
        # Object format should be preserved (no conversion by default)
        self.assertIn("  execute: true", content)
        self.assertIn("Warning:", result.output)
        self.assertIn("--fix", result.output)

    def test_agent_add_fix_flag(self):
        """``sub-agent add --fix`` converts object-format tools to array."""
        src = Path(self.temp_dir.name) / "raw.agent.md"
        src.write_text("---\nname: rawagent\ntools:\n  execute: true\n---\n")

        result = self.runner.invoke(
            main,
            ["sub-agent", "add", str(src), "--fix"],
        )
        self.assertEqual(result.exit_code, 0)

        agents_dir = self.patch_home / ".ai-adapter" / "agents"
        dest = agents_dir / "raw.agent.md"
        self.assertTrue(dest.exists())

        content = dest.read_text()
        self.assertIn("tools: [execute]", content)  # converted
        self.assertNotIn("  execute: true", content)


class TestAgentClaudeFormat(unittest.TestCase):
    """sub-agent get/get-all --format claude (design 02 task 02-2)."""

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

        src = Path(self.temp_dir.name) / "reviewer.agent.md"
        src.write_text(
            "---\nname: reviewer\ndescription: Code review specialist\ntools: [read, grep]\n---\n# Reviewer\n"
        )
        result = self.runner.invoke(main, ["sub-agent", "add", str(src)])
        self.assertEqual(result.exit_code, 0, result.output)

    def tearDown(self):
        import pathlib

        pathlib.Path.home = staticmethod(self._original_home)
        import ai_adapter.config as cfg

        cfg.AI_ADAPTER_DIR = Path.home() / ".ai-adapter"
        self.temp_dir.cleanup()

    def test_get_claude_renames_agent_md_to_md(self):
        """AC1: .agent.md → .md deployed to .claude/agents/."""
        result = self.runner.invoke(
            main,
            [
                "sub-agent",
                "get",
                "reviewer",
                "--format",
                "claude",
                "--project-dir",
                str(self.project_dir),
            ],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        agents_dir = self.project_dir / ".claude" / "agents"
        self.assertTrue((agents_dir / "reviewer.md").exists())
        self.assertFalse((agents_dir / "reviewer.agent.md").exists())

    def test_get_claude_converts_tools_array_to_comma_string(self):
        """AC2: tools conversion via agent_format.convert_agent_file_to_string."""
        result = self.runner.invoke(
            main,
            [
                "sub-agent",
                "get",
                "reviewer",
                "--format",
                "claude",
                "--project-dir",
                str(self.project_dir),
            ],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        content = (self.project_dir / ".claude" / "agents" / "reviewer.md").read_text()
        self.assertIn("tools: read, grep", content)

    def test_get_claude_scope_user(self):
        """AC3: --scope user → ~/.claude/agents/."""
        result = self.runner.invoke(
            main,
            ["sub-agent", "get", "reviewer", "--format", "claude", "--scope", "user"],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertTrue((self.patch_home / ".claude" / "agents" / "reviewer.md").exists())

    def test_get_all_claude(self):
        """get-all --format claude deploys every registered agent."""
        result = self.runner.invoke(
            main,
            [
                "sub-agent",
                "get-all",
                "--format",
                "claude",
                "--project-dir",
                str(self.project_dir),
            ],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertTrue((self.project_dir / ".claude" / "agents" / "reviewer.md").exists())

    def test_get_claude_fix_converts_plain_md_array_tools(self):
        """W1 (QA): --fix + --format claude converts plain .md array tools via staging."""
        store = self.patch_home / ".ai-adapter" / "agents"
        plain = store / "helper.md"
        plain.write_text(
            "---\nname: helper\ndescription: Helper\ntools: [read, grep]\n---\n# Helper\n",
            encoding="utf-8",
        )
        result = self.runner.invoke(
            main,
            [
                "sub-agent",
                "get",
                "helper",
                "--fix",
                "--format",
                "claude",
                "--project-dir",
                str(self.project_dir),
            ],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        content = (self.project_dir / ".claude" / "agents" / "helper.md").read_text()
        self.assertIn("tools: read, grep", content)
        self.assertIn("Warning: converted tools format", result.output)
        # Store keeps the original array format.
        self.assertIn("tools: [read, grep]", plain.read_text())

    def test_get_claude_without_fix_keeps_plain_md_array(self):
        """Without --fix, plain .md array tools stay as-is (pass-through)."""
        store = self.patch_home / ".ai-adapter" / "agents"
        plain = store / "helper.md"
        plain.write_text(
            "---\nname: helper\ndescription: Helper\ntools: [read, grep]\n---\n# Helper\n",
            encoding="utf-8",
        )
        result = self.runner.invoke(
            main,
            [
                "sub-agent",
                "get",
                "helper",
                "--format",
                "claude",
                "--project-dir",
                str(self.project_dir),
            ],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        content = (self.project_dir / ".claude" / "agents" / "helper.md").read_text()
        self.assertIn("tools: [read, grep]", content)

    def test_get_all_claude_fix_converts_plain_md(self):
        """W1 (QA): get-all --fix --format claude also converts plain .md array tools."""
        # Write to a temp source location (not the store) so `sub-agent add`
        # copies it into the store and registers it in config.
        src_path = Path(self.temp_dir.name) / "src" / "helper.md"
        src_path.parent.mkdir(parents=True, exist_ok=True)
        src_path.write_text(
            "---\nname: helper\ndescription: Helper\ntools: [read]\n---\n# Helper\n",
            encoding="utf-8",
        )
        add_result = self.runner.invoke(main, ["sub-agent", "add", str(src_path)])
        self.assertEqual(add_result.exit_code, 0, add_result.output)
        result = self.runner.invoke(
            main,
            [
                "sub-agent",
                "get-all",
                "--fix",
                "--format",
                "claude",
                "--project-dir",
                str(self.project_dir),
            ],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        content = (self.project_dir / ".claude" / "agents" / "helper.md").read_text()
        self.assertIn("tools: read", content)

    def test_get_standard_unchanged(self):
        """Backward compat: default format still writes .github/agents/ with .agent.md."""
        result = self.runner.invoke(
            main,
            ["sub-agent", "get", "reviewer", "--project-dir", str(self.project_dir)],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertTrue((self.project_dir / ".github" / "agents" / "reviewer.agent.md").exists())

    def test_scope_user_rejected_for_standard(self):
        """--scope user requires --format claude."""
        result = self.runner.invoke(
            main,
            [
                "sub-agent",
                "get",
                "reviewer",
                "--format",
                "standard",
                "--scope",
                "user",
            ],
        )
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("--scope user is only supported with --format claude", result.output)


class TestAgentOpencodeFormat(unittest.TestCase):
    """sub-agent get/get-all --format opencode (design 04 task 04-3)."""

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

        src = Path(self.temp_dir.name) / "reviewer.agent.md"
        src.write_text(
            "---\nname: reviewer\ndescription: Code review specialist\ntools: [read, grep]\n---\n# Reviewer\n"
        )
        result = self.runner.invoke(main, ["sub-agent", "add", str(src)])
        self.assertEqual(result.exit_code, 0, result.output)

    def tearDown(self):
        import pathlib

        pathlib.Path.home = staticmethod(self._original_home)
        import ai_adapter.config as cfg

        cfg.AI_ADAPTER_DIR = Path.home() / ".ai-adapter"
        self.temp_dir.cleanup()

    def test_get_opencode_scope_user_renames_agent_md(self):
        """AC3 (M1 fix): --scope user → ~/.config/opencode/agents/<name>.md.

        OpenCode derives the agent name from the file name (``review.md``
        → ``review``), so ``.agent.md`` sources are renamed to ``.md``.
        """
        result = self.runner.invoke(
            main,
            ["sub-agent", "get", "reviewer", "--format", "opencode", "--scope", "user"],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        dest = self.patch_home / ".config" / "opencode" / "agents" / "reviewer.md"
        self.assertTrue(dest.exists())
        self.assertFalse((dest.parent / "reviewer.agent.md").exists())
        # AC1: frontmatter is preserved (OpenCode reads Markdown+YAML).
        self.assertIn("name: reviewer", dest.read_text())

    def test_get_opencode_project_scope(self):
        """--format opencode --scope project → .github/agents/ (agent name derived from file)."""
        result = self.runner.invoke(
            main,
            [
                "sub-agent",
                "get",
                "reviewer",
                "--format",
                "opencode",
                "--project-dir",
                str(self.project_dir),
            ],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        # OpenCode derives agent names from file names; .agent.md → .md.
        self.assertTrue((self.project_dir / ".github" / "agents" / "reviewer.md").exists())

    def test_get_all_opencode_scope_user(self):
        """get-all --format opencode --scope user deploys every agent with .md names."""
        result = self.runner.invoke(
            main,
            ["sub-agent", "get-all", "--format", "opencode", "--scope", "user"],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        dest = self.patch_home / ".config" / "opencode" / "agents" / "reviewer.md"
        self.assertTrue(dest.exists())

    def test_get_opencode_fix_converts_tools_array(self):
        """--fix converts array-format tools for opencode too (object format expected)."""
        result = self.runner.invoke(
            main,
            ["sub-agent", "get", "reviewer", "--fix", "--format", "opencode", "--scope", "user"],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        content = (self.patch_home / ".config" / "opencode" / "agents" / "reviewer.md").read_text()
        self.assertIn("tools:\n  read: true\n  grep: true", content)


class TestAgentConvertCommand(unittest.TestCase):
    """sub-agent convert: single file → one platform, prefixed filename."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.runner = CliRunner()
        self.src_dir = Path(self.temp_dir.name)
        # Object-format tools + a model list: exercises both conversions.
        self.src = self.src_dir / "content-marketing.agent.md"
        self.src.write_text(
            "---\n"
            "name: Content Marketing\n"
            "description: Plans content.\n"
            "temperature: 0.4\n"
            "model: [gpt-6-luna, gpt-6.1-sol]\n"
            "tools:\n"
            "  read: true\n"
            "  write: true\n"
            "  edit: false\n"
            "---\n"
            "# Content Marketing\n\nYou plan content.\n"
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def _convert(self, fmt, *extra):
        return self.runner.invoke(
            main,
            ["sub-agent", "convert", str(self.src), "--format", fmt, *extra],
        )

    def test_vscode_array_prefix(self):
        """vscode → .agent.md with array tools and vscode-- prefix."""
        out = self.src_dir / "out"
        result = self._convert("vscode", "--output-dir", str(out))
        self.assertEqual(result.exit_code, 0, result.output)
        dest = out / "vscode--content-marketing.agent.md"
        self.assertTrue(dest.exists())
        content = dest.read_text()
        self.assertIn("tools: [read, write]", content)  # edit: false dropped
        self.assertNotIn("  read: true", content)

    def test_claude_comma_string_prefix(self):
        """claude → .md with comma-separated tools and claude-- prefix."""
        out = self.src_dir / "out"
        result = self._convert("claude", "--output-dir", str(out))
        self.assertEqual(result.exit_code, 0, result.output)
        dest = out / "claude--content-marketing.md"
        self.assertTrue(dest.exists())
        self.assertIn("tools: read, write", dest.read_text())

    def test_opencode_object_prefix(self):
        """opencode → .md with object tools (edit:false preserved) and opencode-- prefix."""
        out = self.src_dir / "out"
        result = self._convert("opencode", "--output-dir", str(out))
        self.assertEqual(result.exit_code, 0, result.output)
        dest = out / "opencode--content-marketing.md"
        self.assertTrue(dest.exists())
        content = dest.read_text()
        self.assertIn("  read: true", content)
        self.assertIn("  edit: false", content)  # deny preserved

    def test_gemini_array_slug_prefix(self):
        """gemini → .md with slug name, array tools, gemini-- prefix."""
        out = self.src_dir / "out"
        result = self._convert("gemini", "--output-dir", str(out))
        self.assertEqual(result.exit_code, 0, result.output)
        dest = out / "gemini--content-marketing.md"
        self.assertTrue(dest.exists())
        content = dest.read_text()
        self.assertIn("name: content-marketing", content)
        self.assertIn('tools: ["read", "write"]', content)
        self.assertIn("You plan content.", content)  # body = system prompt

    def test_codex_toml_prefix(self):
        """codex → .toml with name/description/developer_instructions, codex-- prefix."""
        out = self.src_dir / "out"
        result = self._convert("codex", "--output-dir", str(out))
        self.assertEqual(result.exit_code, 0, result.output)
        dest = out / "codex--content-marketing.toml"
        self.assertTrue(dest.exists())
        content = dest.read_text()
        self.assertIn('name = "content-marketing"', content)
        self.assertIn("developer_instructions =", content)
        self.assertIn('model = "gpt-6-luna"', content)  # list → first

    def test_no_prefix(self):
        """--no-prefix keeps the original stem."""
        out = self.src_dir / "out"
        result = self._convert("claude", "--output-dir", str(out), "--no-prefix")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertTrue((out / "content-marketing.md").exists())
        self.assertFalse((out / "claude--content-marketing.md").exists())

    def test_stdout(self):
        """--stdout prints converted content and writes no file."""
        result = self._convert("codex", "--stdout")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("developer_instructions =", result.output)
        # No codex-- file written next to the source.
        self.assertFalse((self.src_dir / "codex--content-marketing.toml").exists())

    def test_default_output_alongside_source(self):
        """Default output dir is the source's parent."""
        result = self._convert("codex")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertTrue((self.src_dir / "codex--content-marketing.toml").exists())

    def test_overwrite_prompts(self):
        """Existing output aborts without --force-style confirmation."""
        out = self.src_dir / "out"
        self._convert("codex", "--output-dir", str(out))
        result = self._convert("codex", "--output-dir", str(out))
        # confirm() aborts (exit 1) when stdin is empty.
        self.assertNotEqual(result.exit_code, 0)


class TestAgentCodexFormat(unittest.TestCase):
    """sub-agent get/get-all --format codex → .codex/agents/*.toml."""

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

        src = Path(self.temp_dir.name) / "reviewer.agent.md"
        src.write_text(
            "---\n"
            "name: Code Reviewer\n"
            "description: Reviews code for defects\n"
            "model: [gpt-6-luna, gpt-6.1-sol]\n"
            "---\n"
            "# Reviewer\n\nReview code like an owner.\n"
        )
        result = self.runner.invoke(main, ["sub-agent", "add", str(src)])
        self.assertEqual(result.exit_code, 0, result.output)

    def tearDown(self):
        import pathlib

        pathlib.Path.home = staticmethod(self._original_home)
        import ai_adapter.config as cfg

        cfg.AI_ADAPTER_DIR = Path.home() / ".ai-adapter"
        self.temp_dir.cleanup()

    def test_get_codex_converts_to_toml(self):
        """get --format codex → .codex/agents/<slug>.toml with required keys."""
        result = self.runner.invoke(
            main,
            [
                "sub-agent",
                "get",
                "Code Reviewer",
                "--format",
                "codex",
                "--project-dir",
                str(self.project_dir),
            ],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        dest = self.project_dir / ".codex" / "agents" / "code-reviewer.toml"
        self.assertTrue(dest.exists())
        content = dest.read_text()
        self.assertIn('name = "code-reviewer"', content)
        self.assertIn('description = "Reviews code for defects"', content)
        self.assertIn("developer_instructions =", content)
        self.assertIn("Review code like an owner.", content)
        # model list → first entry (Codex takes a single string).
        self.assertIn('model = "gpt-6-luna"', content)
        # Frontmatter must be stripped from the body.
        self.assertNotIn("name: Code Reviewer", content)

    def test_get_codex_scope_user(self):
        """get --format codex --scope user → ~/.codex/agents/."""
        result = self.runner.invoke(
            main,
            ["sub-agent", "get", "Code Reviewer", "--format", "codex", "--scope", "user"],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        dest = self.patch_home / ".codex" / "agents" / "code-reviewer.toml"
        self.assertTrue(dest.exists())

    def test_get_all_codex(self):
        """get-all --format codex converts every registered agent."""
        result = self.runner.invoke(
            main,
            [
                "sub-agent",
                "get-all",
                "--format",
                "codex",
                "--project-dir",
                str(self.project_dir),
            ],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertTrue((self.project_dir / ".codex" / "agents" / "code-reviewer.toml").exists())

    def test_get_codex_output_is_valid_toml(self):
        """The generated agent TOML must round-trip through tomllib."""
        try:
            import tomllib
        except ModuleNotFoundError:  # Python 3.10
            import tomli as tomllib

        result = self.runner.invoke(
            main,
            [
                "sub-agent",
                "get",
                "Code Reviewer",
                "--format",
                "codex",
                "--project-dir",
                str(self.project_dir),
            ],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        dest = self.project_dir / ".codex" / "agents" / "code-reviewer.toml"
        data = tomllib.loads(dest.read_text())
        self.assertEqual(data["name"], "code-reviewer")
        self.assertIn("developer_instructions", data)


class TestAgentGeminiFormat(unittest.TestCase):
    """sub-agent get/get-all --format gemini → .gemini/agents/*.md."""

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

        src = Path(self.temp_dir.name) / "reviewer.agent.md"
        src.write_text(
            "---\n"
            "name: Code Reviewer\n"
            "description: Reviews code for defects\n"
            "model: gpt-6.1-sol\n"
            "tools:\n"
            "  read: true\n"
            "  edit: false\n"
            "---\n"
            "# Reviewer\n\nReview code like an owner.\n"
        )
        result = self.runner.invoke(main, ["sub-agent", "add", str(src)])
        self.assertEqual(result.exit_code, 0, result.output)

    def tearDown(self):
        import pathlib

        pathlib.Path.home = staticmethod(self._original_home)
        import ai_adapter.config as cfg

        cfg.AI_ADAPTER_DIR = Path.home() / ".ai-adapter"
        self.temp_dir.cleanup()

    def test_get_gemini_converts_to_subagent_md(self):
        """get --format gemini → .gemini/agents/<slug>.md with slug name."""
        result = self.runner.invoke(
            main,
            [
                "sub-agent",
                "get",
                "Code Reviewer",
                "--format",
                "gemini",
                "--project-dir",
                str(self.project_dir),
            ],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        dest = self.project_dir / ".gemini" / "agents" / "code-reviewer.md"
        self.assertTrue(dest.exists())
        content = dest.read_text()
        # Gemini requires a slug-style name.
        self.assertIn("name: code-reviewer", content)
        self.assertIn('model: "gpt-6.1-sol"', content)
        # Object tools → array (truthy entries only).
        self.assertIn('tools: ["read"]', content)
        # Body becomes the system prompt; frontmatter stripped.
        self.assertIn("Review code like an owner.", content)
        self.assertNotIn("name: Code Reviewer", content)

    def test_get_gemini_scope_user(self):
        """get --format gemini --scope user → ~/.gemini/agents/."""
        result = self.runner.invoke(
            main,
            ["sub-agent", "get", "Code Reviewer", "--format", "gemini", "--scope", "user"],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        dest = self.patch_home / ".gemini" / "agents" / "code-reviewer.md"
        self.assertTrue(dest.exists())

    def test_get_all_gemini(self):
        """get-all --format gemini converts every registered agent."""
        result = self.runner.invoke(
            main,
            [
                "sub-agent",
                "get-all",
                "--format",
                "gemini",
                "--project-dir",
                str(self.project_dir),
            ],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertTrue((self.project_dir / ".gemini" / "agents" / "code-reviewer.md").exists())

    def test_get_gemini_missing_tools_key_omitted(self):
        """No tools key in the source → no tools line (inherit parent tools)."""
        src = Path(self.temp_dir.name) / "writer.agent.md"
        src.write_text("---\nname: writer\ndescription: Writes docs\n---\nWrite docs.\n")
        result = self.runner.invoke(main, ["sub-agent", "add", str(src)])
        self.assertEqual(result.exit_code, 0, result.output)

        result = self.runner.invoke(
            main,
            [
                "sub-agent",
                "get",
                "writer",
                "--format",
                "gemini",
                "--project-dir",
                str(self.project_dir),
            ],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        content = (self.project_dir / ".gemini" / "agents" / "writer.md").read_text()
        self.assertNotIn("tools:", content)


class TestInstructionTargetOption(unittest.TestCase):
    """agent get --target (design 08 tasks 08-1/08-2)."""

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

        self.inst_file = Path(self.temp_dir.name) / "STYLE.md"
        self.inst_file.write_text("# Style Guide\n\nUse consistent formatting.\n")
        self.runner.invoke(main, ["agent", "add", str(self.inst_file)])

    def tearDown(self):
        import pathlib

        pathlib.Path.home = staticmethod(self._original_home)
        import ai_adapter.config as cfg

        cfg.AI_ADAPTER_DIR = Path.home() / ".ai-adapter"
        self.temp_dir.cleanup()

    def test_target_root_default(self):
        """AC1: --target root (default) deploys to project root."""
        result = self.runner.invoke(main, ["agent", "get", "STYLE", "--project-dir", str(self.project_dir)])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertTrue((self.project_dir / "STYLE.md").exists())

    def test_target_github_instructions(self):
        """AC2: --target github-instructions deploys to .github/instructions/."""
        result = self.runner.invoke(
            main, ["agent", "get", "STYLE", "--target", "github-instructions", "--project-dir", str(self.project_dir)]
        )
        self.assertEqual(result.exit_code, 0, result.output)
        dest = self.project_dir / ".github" / "instructions" / "STYLE.md"
        self.assertTrue(dest.exists())
        self.assertIn("copied to", result.output)

    def test_target_github_instructions_creates_dir(self):
        """.github/instructions/ is created when missing."""
        result = self.runner.invoke(
            main, ["agent", "get", "STYLE", "--target", "github-instructions", "--project-dir", str(self.project_dir)]
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertTrue((self.project_dir / ".github" / "instructions").is_dir())

    def test_target_github_copilot(self):
        """AC3: --target github-copilot deploys to .github/copilot-instructions.md."""
        result = self.runner.invoke(
            main, ["agent", "get", "STYLE", "--target", "github-copilot", "--project-dir", str(self.project_dir)]
        )
        self.assertEqual(result.exit_code, 0, result.output)
        dest = self.project_dir / ".github" / "copilot-instructions.md"
        self.assertTrue(dest.exists())
        self.assertIn("Use consistent formatting.", dest.read_text())

    def test_target_github_copilot_fixed_filename(self):
        """Filename is always copilot-instructions.md regardless of source name."""
        result = self.runner.invoke(
            main, ["agent", "get", "STYLE", "--target", "github-copilot", "--project-dir", str(self.project_dir)]
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertTrue((self.project_dir / ".github" / "copilot-instructions.md").exists())
        self.assertFalse((self.project_dir / ".github" / "STYLE.md").exists())

    def test_target_with_format_is_error(self):
        """--target + --format is an error (mutual exclusion)."""
        result = self.runner.invoke(
            main,
            [
                "agent",
                "get",
                "STYLE",
                "--target",
                "github-instructions",
                "--format",
                "codex",
                "--project-dir",
                str(self.project_dir),
            ],
        )
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("incompatible", result.output)

    def test_target_with_format_standard_is_error(self):
        """--target + --format standard is also an error (explicit format)."""
        result = self.runner.invoke(
            main,
            [
                "agent",
                "get",
                "STYLE",
                "--target",
                "github-instructions",
                "--format",
                "standard",
                "--project-dir",
                str(self.project_dir),
            ],
        )
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("incompatible", result.output)

    def test_target_with_scope_user_is_error(self):
        """--target github-* with --scope user is rejected."""
        result = self.runner.invoke(
            main,
            ["agent", "get", "STYLE", "--target", "github-instructions", "--scope", "user"],
        )
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("only supported", result.output)
