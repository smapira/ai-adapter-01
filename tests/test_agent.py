"""Tests for agent.py."""

import tempfile
import unittest
from pathlib import Path

from click.testing import CliRunner

from ai_adapter.cli import main
from ai_adapter.config import init


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

        # Create test agent file
        self.agent_file = Path(self.temp_dir.name) / "test-agent.md"
        self.agent_file.write_text("# Test Agent\nThis is a test agent.")

    def tearDown(self):
        import pathlib

        pathlib.Path.home = staticmethod(self._original_home)
        import ai_adapter.config as cfg

        cfg.AI_ADAPTER_DIR = Path.home() / ".ai-adapter"
        # Restore .github/ from backup
        if hasattr(self, '_github_bak') and self._github_bak and Path(self._github_bak).exists():
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
        import shutil

        shutil.rmtree(Path.cwd() / ".github", ignore_errors=True)

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

        import shutil

        shutil.rmtree(Path.cwd() / ".github", ignore_errors=True)

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

        import shutil

        shutil.rmtree(Path.cwd() / ".github", ignore_errors=True)

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

        import shutil

        shutil.rmtree(Path.cwd() / ".github", ignore_errors=True)

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

        import shutil

        shutil.rmtree(Path.cwd() / ".github", ignore_errors=True)


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
        if hasattr(self, '_github_bak') and self._github_bak and Path(self._github_bak).exists():
            import shutil

            github_dir = Path.cwd() / ".github"
            if github_dir.exists():
                shutil.rmtree(github_dir)
            shutil.copytree(self._github_bak, github_dir)
        self.temp_dir.cleanup()


    def test_agent_get_converts_tools_with_fix(self):
        """``agent get --fix`` converts array-format tools to object format."""
        src = Path(self.temp_dir.name) / "my.agent.md"
        src.write_text("---\nname: myagent\ntools: [execute, read]\n---\n# My Agent\n")
        # Default add = no conversion
        self.runner.invoke(main, ["sub-agent", "add", str(src)])

        # Run agent get with --fix to convert
        github_agents = Path.cwd() / ".github" / "agents"
        github_agents.mkdir(parents=True, exist_ok=True)

        result = self.runner.invoke(main, ["sub-agent", "get", "myagent", "--fix"])
        self.assertEqual(result.exit_code, 0)

        dest = github_agents / "my.agent.md"
        self.assertTrue(dest.exists())

        content = dest.read_text()
        self.assertIn("  execute: true", content)
        self.assertIn("  read: true", content)
        self.assertNotIn("[execute, read]", content)

        # Warning should be on stderr
        self.assertIn("Warning: converted tools format", result.output)

    def test_agent_get_warns_on_array_format(self):
        """``agent get`` warns on array-format tools but does NOT convert."""
        src = Path(self.temp_dir.name) / "my.agent.md"
        src.write_text("---\nname: myagent\ntools: [execute, read]\n---\n# My Agent\n")
        self.runner.invoke(main, ["sub-agent", "add", str(src)])

        github_agents = Path.cwd() / ".github" / "agents"
        github_agents.mkdir(parents=True, exist_ok=True)

        # Without --fix: warn but do NOT convert
        result = self.runner.invoke(main, ["sub-agent", "get", "myagent"])
        self.assertEqual(result.exit_code, 0)

        dest = github_agents / "my.agent.md"
        self.assertTrue(dest.exists())

        content = dest.read_text()
        self.assertIn("[execute, read]", content)  # kept as-is
        self.assertIn("Warning:", result.output)
        self.assertIn("--fix", result.output)

    def test_agent_get_all_converts_tools_with_fix(self):
        """``agent get-all --fix`` converts array-format tools for all agents."""
        src1 = Path(self.temp_dir.name) / "alpha.agent.md"
        src1.write_text("---\nname: alpha\ntools: [execute]\n---\n")
        src2 = Path(self.temp_dir.name) / "beta.agent.md"
        src2.write_text("---\nname: beta\ntools: [read, agent]\n---\n")
        # Default add = no conversion
        self.runner.invoke(main, ["sub-agent", "add", str(src1)])
        self.runner.invoke(main, ["sub-agent", "add", str(src2)])

        github_agents = Path.cwd() / ".github" / "agents"
        github_agents.mkdir(parents=True, exist_ok=True)

        result = self.runner.invoke(main, ["sub-agent", "get-all", "--fix"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("2", result.output)

        # Check both files were converted
        content_alpha = (github_agents / "alpha.agent.md").read_text()
        self.assertIn("  execute: true", content_alpha)

        content_beta = (github_agents / "beta.agent.md").read_text()
        self.assertIn("  read: true", content_beta)
        self.assertIn("  agent: true", content_beta)

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

    def test_agent_add_warns_on_array_format(self):
        """``agent add`` warns on array-format tools but does NOT convert."""
        src = Path(self.temp_dir.name) / "new.agent.md"
        src.write_text("---\nname: newagent\ntools: [execute, read]\n---\n# New Agent\n")

        result = self.runner.invoke(main, ["sub-agent", "add", str(src)])
        self.assertEqual(result.exit_code, 0)

        agents_dir = self.patch_home / ".ai-adapter" / "agents"
        dest = agents_dir / "new.agent.md"
        self.assertTrue(dest.exists())

        content = dest.read_text()
        # Array format should be preserved (no conversion by default)
        self.assertIn("[execute, read]", content)
        self.assertIn("Warning:", result.output)
        self.assertIn("--fix", result.output)

    def test_agent_add_fix_flag(self):
        """``agent add --fix`` converts array-format tools."""
        src = Path(self.temp_dir.name) / "raw.agent.md"
        src.write_text("---\nname: rawagent\ntools: [execute]\n---\n")

        result = self.runner.invoke(
            main,
            ["sub-agent", "add", str(src), "--fix"],
        )
        self.assertEqual(result.exit_code, 0)

        agents_dir = self.patch_home / ".ai-adapter" / "agents"
        dest = agents_dir / "raw.agent.md"
        self.assertTrue(dest.exists())

        content = dest.read_text()
        self.assertIn("  execute: true", content)  # converted
        self.assertNotIn("[execute]", content)
