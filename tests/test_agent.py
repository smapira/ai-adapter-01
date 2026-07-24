"""Tests for agent.py."""

import os
import tempfile
import unittest
from pathlib import Path

from click.testing import CliRunner

from ai_adapter.cli import main
from ai_adapter.config import init
from ai_adapter.models import Agent, Config, Env


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

        result = self.runner.invoke(main, ["agent", "add-rec", str(src_dir)])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("2", result.output)

        # Verify via list
        result = self.runner.invoke(main, ["agent", "list"])
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
        self.temp_dir.cleanup()

    def test_agent_list_empty(self):
        """Verify empty message is shown when no agents registered."""
        result = self.runner.invoke(main, ["agent", "list"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("No agents registered.", result.output)

    def test_agent_add(self):
        """Verify agent add adds an agent."""
        result = self.runner.invoke(main, ["agent", "add", str(self.agent_file)])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("test-agent", result.output)

        # Verify file was copied
        agents_dir = self.patch_home / ".ai-adapter" / "agents"
        self.assertTrue((agents_dir / "test-agent.md").exists())

    def test_agent_add_and_list(self):
        """Verify agent add → agent list flow."""
        self.runner.invoke(main, ["agent", "add", str(self.agent_file)])
        result = self.runner.invoke(main, ["agent", "list"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("test-agent", result.output)

    def test_agent_get(self):
        """Verify agent get copies to .github/agents/."""
        self.runner.invoke(main, ["agent", "add", str(self.agent_file)])

        # Create .github/agents/ in the current directory (inside temp dir)
        github_agents = Path.cwd() / ".github" / "agents"
        github_agents.mkdir(parents=True, exist_ok=True)

        result = self.runner.invoke(main, ["agent", "get", "test-agent"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("test-agent.md", result.output)
        self.assertTrue((github_agents / "test-agent.md").exists())

        # Cleanup
        import shutil
        shutil.rmtree(Path.cwd() / ".github", ignore_errors=True)

    def test_agent_get_not_found(self):
        """Verify get fails for non-existent agent."""
        result = self.runner.invoke(main, ["agent", "get", "nonexistent"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("not found", result.output)

    def test_agent_get_force_overwrite(self):
        """Verify agent get --force overwrites without confirmation."""
        self.runner.invoke(main, ["agent", "add", str(self.agent_file)])

        github_dir = Path.cwd() / ".github" / "agents"
        github_dir.mkdir(parents=True, exist_ok=True)

        # First get
        result = self.runner.invoke(main, ["agent", "get", "test-agent"])
        self.assertEqual(result.exit_code, 0)

        # Second get with --force to overwrite
        result = self.runner.invoke(main, ["agent", "get", "test-agent", "--force"])
        self.assertEqual(result.exit_code, 0)
        self.assertTrue((github_dir / "test-agent.md").exists())

        import shutil
        shutil.rmtree(Path.cwd() / ".github", ignore_errors=True)

    def test_agent_get_with_project_dir(self):
        """Verify agent get --project-dir copies to the specified directory."""
        self.runner.invoke(main, ["agent", "add", str(self.agent_file)])

        # Create a custom project directory
        project_dir = Path(self.temp_dir.name) / "my-project"
        project_dir.mkdir(parents=True)

        result = self.runner.invoke(main, [
            "agent", "get", "test-agent",
            "--project-dir", str(project_dir),
        ])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("test-agent.md", result.output)
        self.assertTrue((project_dir / ".github" / "agents" / "test-agent.md").exists())

    def test_agent_get_all(self):
        """Verify agent get-all copies all agents to .github/agents/."""
        agent1 = Path(self.temp_dir.name) / "agent1.md"
        agent1.write_text("# Agent 1")
        agent2 = Path(self.temp_dir.name) / "agent2.md"
        agent2.write_text("# Agent 2")
        self.runner.invoke(main, ["agent", "add", str(agent1)])
        self.runner.invoke(main, ["agent", "add", str(agent2)])

        github_agents = Path.cwd() / ".github" / "agents"
        github_agents.mkdir(parents=True, exist_ok=True)

        result = self.runner.invoke(main, ["agent", "get-all"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("2", result.output)
        self.assertTrue((github_agents / "agent1.md").exists())
        self.assertTrue((github_agents / "agent2.md").exists())

        import shutil
        shutil.rmtree(Path.cwd() / ".github", ignore_errors=True)

    def test_agent_remove(self):
        """Verify agent remove removes an agent."""
        self.runner.invoke(main, ["agent", "add", str(self.agent_file)])
        result = self.runner.invoke(main, ["agent", "remove", "test-agent"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("test-agent", result.output)

        # Verify it is not displayed in list
        result = self.runner.invoke(main, ["agent", "list"])
        self.assertIn("No agents registered.", result.output)

    def test_agent_remove_all(self):
        """Verify agent remove-all removes all agents."""
        # Add two agents
        agent1 = Path(self.temp_dir.name) / "agent1.md"
        agent1.write_text("# Agent 1")
        agent2 = Path(self.temp_dir.name) / "agent2.md"
        agent2.write_text("# Agent 2")
        self.runner.invoke(main, ["agent", "add", str(agent1)])
        self.runner.invoke(main, ["agent", "add", str(agent2)])

        result = self.runner.invoke(main, ["agent", "remove-all", "--force"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("All agents", result.output)

        # List is now empty
        result = self.runner.invoke(main, ["agent", "list"])
        self.assertIn("No agents registered.", result.output)

    def test_agent_add_agent_md_with_frontmatter(self):
        """Verify registering an .agent.md file uses the frontmatter name."""
        agent_md_file = Path(self.temp_dir.name) / "reviewer.agent.md"
        agent_md_file.write_text(
            "---\n"
            "name: Implementer\n"
            "description: Dev Agent\n"
            "---\n"
            "\n"
            "# Implementer\n"
            "This is an implementer agent.\n"
        )

        result = self.runner.invoke(main, ["agent", "add", str(agent_md_file)])
        self.assertEqual(result.exit_code, 0)
        # Registered name becomes "Implementer" (from frontmatter name)
        self.assertIn("'Implementer'", result.output)

        # "Implementer" is shown in list, "reviewer" is not
        result = self.runner.invoke(main, ["agent", "list"])
        self.assertIn("Implementer", result.output)
        self.assertNotIn("reviewer", result.output)

    def test_agent_add_agent_md_without_frontmatter_fails(self):
        """Verify .agent.md without frontmatter raises an error."""
        bad_file = Path(self.temp_dir.name) / "bad.agent.md"
        bad_file.write_text("# Just a markdown\nNo frontmatter here.\n")

        result = self.runner.invoke(main, ["agent", "add", str(bad_file)])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("frontmatter", result.output)

    def test_agent_add_agent_md_without_name_fails(self):
        """Verify .agent.md without name in frontmatter raises an error."""
        bad_file = Path(self.temp_dir.name) / "bad.agent.md"
        bad_file.write_text(
            "---\n"
            "description: no name here\n"
            "---\n"
            "# Bad\n"
        )

        result = self.runner.invoke(main, ["agent", "add", str(bad_file)])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("name", result.output)

    def test_agent_get_agent_md_backward_compat(self):
        """Verify an agent registered with .agent.md can be retrieved by short name."""
        agent_md_file = Path(self.temp_dir.name) / "reviewer.agent.md"
        agent_md_file.write_text(
            "---\n"
            "name: Implementer\n"
            "---\n"
            "# Implementer\n"
        )
        self.runner.invoke(main, ["agent", "add", str(agent_md_file)])

        github_agents = Path.cwd() / ".github" / "agents"
        github_agents.mkdir(parents=True, exist_ok=True)

        # Can be retrieved with "Implementer"
        result = self.runner.invoke(main, ["agent", "get", "Implementer"])
        self.assertEqual(result.exit_code, 0)
        self.assertTrue((github_agents / "reviewer.agent.md").exists())

        import shutil
        shutil.rmtree(Path.cwd() / ".github", ignore_errors=True)

    def test_agent_get_with_dot_agent_suffix(self):
        """Verify backward compatibility: agents can be retrieved with .agent suffix."""
        agent_md_file = Path(self.temp_dir.name) / "reviewer.agent.md"
        agent_md_file.write_text(
            "---\n"
            "name: Implementer\n"
            "---\n"
            "# Implementer\n"
        )
        self.runner.invoke(main, ["agent", "add", str(agent_md_file)])

        github_agents = Path.cwd() / ".github" / "agents"
        github_agents.mkdir(parents=True, exist_ok=True)

        # Can also be retrieved with "reviewer.agent" (backward compatibility)
        result = self.runner.invoke(main, ["agent", "get", "reviewer.agent"])
        self.assertEqual(result.exit_code, 0)
        self.assertTrue((github_agents / "reviewer.agent.md").exists())

        import shutil
        shutil.rmtree(Path.cwd() / ".github", ignore_errors=True)
