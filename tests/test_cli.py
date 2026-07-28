"""CLI integration tests."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from ai_adapter.cli import main
from ai_adapter.git import GitError


class TestCLIIntegration(unittest.TestCase):
    """Overall CLI integration tests."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.patch_home = Path(self.temp_dir.name)
        self.runner = CliRunner()

        import pathlib

        self._original_home = pathlib.Path.home
        pathlib.Path.home = staticmethod(lambda: self.patch_home)

        import ai_adapter.config as cfg

        cfg.AI_ADAPTER_DIR = self.patch_home / ".ai-adapter"

    def tearDown(self):
        import pathlib

        pathlib.Path.home = staticmethod(self._original_home)
        import ai_adapter.config as cfg

        cfg.AI_ADAPTER_DIR = Path.home() / ".ai-adapter"
        self.temp_dir.cleanup()

    def test_help(self):
        """Verify --help displays correctly."""
        result = self.runner.invoke(main, ["--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("ai-adapter", result.output)
        self.assertIn("init", result.output)
        self.assertIn("status", result.output)
        self.assertIn("sub-agent", result.output)
        self.assertIn("env", result.output)
        self.assertIn("bin", result.output)
        self.assertIn("skill", result.output)
        self.assertIn("mcp", result.output)
        self.assertIn("opencode", result.output)
        self.assertIn("command", result.output)
        self.assertIn("prompt", result.output)
        self.assertIn("agent", result.output)
        self.assertIn("add-all-rec", result.output)
        self.assertIn("get-all-rec", result.output)
        self.assertIn("sync", result.output)
        self.assertIn("uninstall", result.output)
        self.assertIn("start", result.output)

    def test_version(self):
        """Verify --version is displayed."""
        from ai_adapter import __version__

        result = self.runner.invoke(main, ["--version"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn(__version__, result.output)

    def test_init_and_status(self):
        """Verify init → status flow."""
        # init (skip remote input with empty Enter)
        result = self.runner.invoke(main, ["init"], input="\n")
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Initialized", result.output)

        # status
        result = self.runner.invoke(main, ["status"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Status", result.output)
        self.assertIn("default", result.output)

    def test_init_with_remote(self):
        """Verify init --remote sets up a remote."""
        result = self.runner.invoke(
            main,
            [
                "init",
                "--remote",
                "git@github.com:user/test.git",
            ],
        )
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Remote set", result.output)
        self.assertIn("git@github.com:user/test.git", result.output)

    def test_status_before_init(self):
        """Verify status before init shows appropriate message."""
        result = self.runner.invoke(main, ["status"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("is not initialized", result.output)

    def test_agent_help(self):
        """Verify agent --help is displayed."""
        result = self.runner.invoke(main, ["sub-agent", "--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("list", result.output)
        self.assertIn("add", result.output)
        self.assertIn("get", result.output)
        self.assertIn("remove", result.output)

    def test_agent_get_help(self):
        """Verify agent get --help shows --force option."""
        result = self.runner.invoke(main, ["sub-agent", "get", "--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("--force", result.output)
        self.assertIn("Overwrite", result.output)

    def test_env_help(self):
        """Verify env --help is displayed."""
        result = self.runner.invoke(main, ["env", "--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("list", result.output)
        self.assertIn("add", result.output)
        self.assertIn("remove", result.output)
        self.assertIn("default", result.output)
        self.assertIn("set-default", result.output)
        self.assertIn("link-agent", result.output)
        self.assertIn("unlink-agent", result.output)

    def test_bin_help(self):
        """Verify bin --help is displayed."""
        result = self.runner.invoke(main, ["bin", "--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("list", result.output)
        self.assertIn("add", result.output)
        self.assertIn("get", result.output)
        self.assertIn("remove", result.output)

    def test_skill_help(self):
        """Verify skill --help is displayed."""
        result = self.runner.invoke(main, ["skill", "--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("list", result.output)
        self.assertIn("add", result.output)
        self.assertIn("get", result.output)
        self.assertIn("remove", result.output)
        self.assertIn("search", result.output)
        self.assertIn("link-agent", result.output)

    def test_mcp_help(self):
        """Verify mcp --help is displayed."""
        result = self.runner.invoke(main, ["mcp", "--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("list", result.output)
        self.assertIn("add", result.output)
        self.assertIn("remove", result.output)
        self.assertIn("get", result.output)
        self.assertIn("remove-all", result.output)

    def test_command_help(self):
        """Verify command --help is displayed."""
        result = self.runner.invoke(main, ["command", "--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("list", result.output)
        self.assertIn("add", result.output)
        self.assertIn("get", result.output)
        self.assertIn("remove", result.output)
        self.assertIn("add-rec", result.output)
        self.assertIn("get-all", result.output)
        self.assertIn("remove-all", result.output)

    def test_prompt_help(self):
        """Verify prompt --help is displayed."""
        result = self.runner.invoke(main, ["prompt", "--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("list", result.output)
        self.assertIn("add", result.output)
        self.assertIn("get", result.output)
        self.assertIn("remove", result.output)
        self.assertIn("add-rec", result.output)
        self.assertIn("get-all", result.output)
        self.assertIn("remove-all", result.output)

    def test_opencode_help(self):
        """Verify opencode --help is displayed."""
        result = self.runner.invoke(main, ["opencode", "--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("alias", result.output)
        self.assertIn("install", result.output)
        self.assertIn("uninstall", result.output)


class TestUninstallCommand(unittest.TestCase):
    """Tests for the uninstall command."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.patch_home = Path(self.temp_dir.name)
        self.runner = CliRunner()

        import pathlib

        self._original_home = pathlib.Path.home
        pathlib.Path.home = staticmethod(lambda: self.patch_home)

        import ai_adapter.config as cfg

        cfg.AI_ADAPTER_DIR = self.patch_home / ".ai-adapter"

    def tearDown(self):
        import pathlib

        pathlib.Path.home = staticmethod(self._original_home)
        import ai_adapter.config as cfg

        cfg.AI_ADAPTER_DIR = Path.home() / ".ai-adapter"
        self.temp_dir.cleanup()

    def test_uninstall_before_init(self):
        """Verify uninstall before init shows message."""
        result = self.runner.invoke(main, ["uninstall", "--force"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("is not initialized", result.output)
        self.assertIn("Nothing to delete", result.output)

    def test_uninstall_after_init(self):
        """Verify init → uninstall --force flow."""
        self.runner.invoke(main, ["init"], input="\n")
        adapter_dir = self.patch_home / ".ai-adapter"
        self.assertTrue(adapter_dir.exists())

        result = self.runner.invoke(main, ["uninstall", "--force"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Uninstalled:", result.output)
        self.assertFalse(adapter_dir.exists())

    def test_uninstall_keep_git(self):
        """Verify --keep-git preserves .git directory."""
        self.runner.invoke(main, ["init"], input="\n")
        adapter_dir = self.patch_home / ".ai-adapter"

        # Simulate Git repository
        git_dir = adapter_dir / ".git"
        git_dir.mkdir(parents=True, exist_ok=True)
        (git_dir / "HEAD").write_text("ref: refs/heads/main\n")

        result = self.runner.invoke(main, ["uninstall", "--force", "--keep-git"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Git repo kept", result.output)
        self.assertTrue((adapter_dir / ".git").exists())
        self.assertFalse((adapter_dir / "config.json").exists())

    def test_uninstall_cancel(self):
        """Verify selecting No at confirmation prompt does not remove."""
        self.runner.invoke(main, ["init"], input="\n")
        adapter_dir = self.patch_home / ".ai-adapter"
        self.assertTrue(adapter_dir.exists())

        result = self.runner.invoke(main, ["uninstall"], input="n\n")
        self.assertNotEqual(result.exit_code, 0)
        self.assertTrue(adapter_dir.exists())


class TestStartCommand(unittest.TestCase):
    """Tests for the start command."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.patch_home = Path(self.temp_dir.name)
        self.runner = CliRunner()

        import pathlib

        self._original_home = pathlib.Path.home
        pathlib.Path.home = staticmethod(lambda: self.patch_home)

        import ai_adapter.config as cfg

        cfg.AI_ADAPTER_DIR = self.patch_home / ".ai-adapter"

    def tearDown(self):
        import pathlib

        pathlib.Path.home = staticmethod(self._original_home)
        import ai_adapter.config as cfg

        cfg.AI_ADAPTER_DIR = Path.home() / ".ai-adapter"
        self.temp_dir.cleanup()

    @patch("ai_adapter.cli._git.clone")
    def test_start_new_repo(self, mock_clone):
        """Verify start command sets up a new repository."""
        # Clone failed → new init path
        mock_clone.side_effect = GitError("clone failed")

        result = self.runner.invoke(
            main,
            [
                "start",
                "git@github.com:user/test.git",
            ],
        )
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Setup complete", result.output)
        adapter_dir = self.patch_home / ".ai-adapter"
        self.assertTrue(adapter_dir.exists())
        self.assertTrue((adapter_dir / "agents").exists())
        self.assertTrue((adapter_dir / "bin").exists())

    @patch("ai_adapter.cli._git.clone")
    def test_start_existing_abort(self, mock_clone):
        """Confirmation prompt when directory already exists."""
        adapter_dir = self.patch_home / ".ai-adapter"
        adapter_dir.mkdir(parents=True)

        result = self.runner.invoke(
            main,
            [
                "start",
                "git@github.com:user/test.git",
            ],
            input="n\n",
        )
        self.assertNotEqual(result.exit_code, 0)


class TestBinAddPathCommand(unittest.TestCase):
    """Tests for bin add-path command."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.runner = CliRunner()

        # Backup real .github/ to protect from test cleanup
        self._github_bak = None
        github_dir = Path.cwd() / ".github"
        if github_dir.exists():
            import shutil

            self._github_bak = Path(self.temp_dir.name) / "github.bak"
            shutil.copytree(github_dir, self._github_bak)

    def tearDown(self):
        # Restore .github/ from backup
        if hasattr(self, '_github_bak') and self._github_bak and Path(self._github_bak).exists():
            import shutil

            github_dir = Path.cwd() / ".github"
            if github_dir.exists():
                shutil.rmtree(github_dir)
            shutil.copytree(self._github_bak, github_dir)
        self.temp_dir.cleanup()

    def test_bin_add_path_no_github_bin(self):
        """Verify message is shown when .github/bin is missing."""
        result = self.runner.invoke(main, ["bin", "add-path"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("not found", result.output)

    def test_bin_add_path_with_github_bin(self):
        """Verify PATH line is shown when .github/bin exists."""
        github_bin = Path.cwd() / ".github" / "bin"
        github_bin.mkdir(parents=True, exist_ok=True)
        (github_bin / "test.sh").write_text("#!/bin/bash")

        result = self.runner.invoke(main, ["bin", "add-path"], input="4\n")
        self.assertEqual(result.exit_code, 0)
        self.assertIn("export PATH", result.output)

        import shutil

        shutil.rmtree(Path.cwd() / ".github", ignore_errors=True)

    def test_bin_add_path_to_zshrc(self):
        """Verify bin add-path appends to zshrc."""
        import pathlib

        orig_home = pathlib.Path.home
        pathlib.Path.home = staticmethod(lambda: Path(self.temp_dir.name))

        github_bin = Path.cwd() / ".github" / "bin"
        github_bin.mkdir(parents=True, exist_ok=True)
        (github_bin / "test.sh").write_text("#!/bin/bash")

        result = self.runner.invoke(main, ["bin", "add-path"], input="1\n")
        self.assertEqual(result.exit_code, 0)
        self.assertIn("PATH setting added", result.output)

        zshrc = Path(self.temp_dir.name) / ".zshrc"
        self.assertTrue(zshrc.exists())
        content = zshrc.read_text()
        self.assertIn("export PATH", content)
        self.assertIn(".github/bin", content)

        import shutil

        pathlib.Path.home = staticmethod(orig_home)
        shutil.rmtree(Path.cwd() / ".github", ignore_errors=True)


class TestAddAllRecCommand(unittest.TestCase):
    """Tests for add-all-rec command."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.patch_home = Path(self.temp_dir.name)
        self.runner = CliRunner()

        import pathlib

        self._original_home = pathlib.Path.home
        pathlib.Path.home = staticmethod(lambda: self.patch_home)

        import ai_adapter.config as cfg

        cfg.AI_ADAPTER_DIR = self.patch_home / ".ai-adapter"

        # init
        from ai_adapter.config import init

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

    def test_add_all_rec_agents(self):
        """Verify agents are registered from .github/agents."""
        github_agents = Path.cwd() / ".github" / "agents"
        github_agents.mkdir(parents=True, exist_ok=True)
        (github_agents / "reviewer.md").write_text("# Reviewer")
        (github_agents / "implementer.md").write_text("# Implementer")

        result = self.runner.invoke(main, ["add-all-rec"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("agents", result.output)

        # Verify via list
        result = self.runner.invoke(main, ["sub-agent", "list"])
        self.assertIn("reviewer", result.output)
        self.assertIn("implementer", result.output)

        import shutil

        shutil.rmtree(Path.cwd() / ".github", ignore_errors=True)

    def test_add_all_rec_bins(self):
        """Verify scripts are registered from .github/bin."""
        github_bin = Path.cwd() / ".github" / "bin"
        github_bin.mkdir(parents=True, exist_ok=True)
        (github_bin / "script1.sh").write_text("#!/bin/bash")
        (github_bin / "script2.sh").write_text("#!/bin/bash")

        result = self.runner.invoke(main, ["add-all-rec"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("bin", result.output)

        import shutil

        shutil.rmtree(Path.cwd() / ".github", ignore_errors=True)

    def test_add_all_rec_skills(self):
        """Verify skills are registered from .github/skills."""
        github_skills = Path.cwd() / ".github" / "skills"
        github_skills.mkdir(parents=True, exist_ok=True)
        skill1 = github_skills / "my-skill"
        skill1.mkdir()
        (skill1 / "SKILL.md").write_text("---\nname: my-skill\n---\n# Skill\n")

        result = self.runner.invoke(main, ["add-all-rec"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("skills", result.output)

        import shutil

        shutil.rmtree(Path.cwd() / ".github", ignore_errors=True)

    def test_add_all_rec_mcp(self):
        """Verify MCP servers are registered from .mcp.json."""
        mcp_json = Path.cwd() / ".mcp.json"
        mcp_json.write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "test-server": {
                            "command": "npx",
                            "args": ["@test/server"],
                        }
                    }
                }
            )
        )

        result = self.runner.invoke(main, ["add-all-rec"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn(".mcp.json", result.output)
        self.assertIn("1", result.output)

        mcp_json.unlink()

    def test_add_all_rec_no_github(self):
        """Verify message is shown when .github is missing."""
        result = self.runner.invoke(main, ["add-all-rec"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("not found", result.output)


class TestGetAllRecCommand(unittest.TestCase):
    """Tests for get-all-rec command."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.patch_home = Path(self.temp_dir.name)
        self.runner = CliRunner()

        import pathlib

        self._original_home = pathlib.Path.home
        pathlib.Path.home = staticmethod(lambda: self.patch_home)

        import ai_adapter.config as cfg

        cfg.AI_ADAPTER_DIR = self.patch_home / ".ai-adapter"

        from ai_adapter.config import init

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

    def _populate_store(self):
        """Populate ~/.ai-adapter/ with test data for all categories."""
        cfg = __import__("ai_adapter.config", fromlist=["config"])
        from ai_adapter.models import Agent, Bin, Command, MCPServer, Prompt, Skill

        # agents
        agents_dir = cfg.get_agents_dir()
        agents_dir.mkdir(parents=True, exist_ok=True)
        (agents_dir / "reviewer.agent.md").write_text("---\nname: reviewer\n---\n# Reviewer")
        (agents_dir / "implementer.agent.md").write_text("---\nname: implementer\n---\n# Implementer")

        # bins
        bins_dir = cfg.get_bins_dir()
        bins_dir.mkdir(parents=True, exist_ok=True)
        (bins_dir / "build.sh").write_text("#!/bin/bash\necho build")
        (bins_dir / "deploy.sh").write_text("#!/bin/bash\necho deploy")

        # skills
        skills_dir = cfg.get_skills_dir()
        skills_dir.mkdir(parents=True, exist_ok=True)
        skill1 = skills_dir / "my-skill"
        skill1.mkdir()
        (skill1 / "SKILL.md").write_text("---\nname: my-skill\ndescription: A test skill\n---\n# My Skill")

        # commands
        commands_dir = cfg.get_commands_dir()
        commands_dir.mkdir(parents=True, exist_ok=True)
        (commands_dir / "hello.md").write_text("Say hello to the user")
        (commands_dir / "list-files.md").write_text("List all files")

        # prompts
        prompts_dir = cfg.get_prompts_dir()
        prompts_dir.mkdir(parents=True, exist_ok=True)
        (prompts_dir / "code-review.md").write_text("Review this code")
        (prompts_dir / "summarize.md").write_text("Summarize the content")

        # Update config
        config = __import__("ai_adapter.config", fromlist=["config"])
        cfg_obj = config.load_config()
        cfg_obj.agents = [Agent(name="reviewer"), Agent(name="implementer")]
        cfg_obj.bins = [Bin(name="build.sh", env="default"), Bin(name="deploy.sh", env="default")]
        cfg_obj.skills = [Skill(name="my-skill", description="A test skill", path="skills/my-skill")]
        cfg_obj.commands = [Command(name="hello"), Command(name="list-files")]
        cfg_obj.prompts = [Prompt(name="code-review"), Prompt(name="summarize")]
        cfg_obj.mcp_servers = [
            MCPServer(name="test-server", command="npx", args=["@test/server"], enabled=True),
            MCPServer(name="disabled-server", command="npx", args=["@test/old"], enabled=False),
        ]
        config.save_config(cfg_obj)

    def test_get_all_rec_before_init(self):
        """Verify message before init."""
        import shutil

        shutil.rmtree(self.patch_home / ".ai-adapter", ignore_errors=True)

        result = self.runner.invoke(main, ["get-all-rec"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("not found", result.output)  # config file not found

    def test_get_all_rec_empty(self):
        """Verify message when nothing registered."""
        result = self.runner.invoke(main, ["get-all-rec"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("skip", result.output)
        self.assertIn("Total:", result.output)

    def test_get_all_rec_all_categories(self):
        """Verify all categories are deployed to .github/."""
        self._populate_store()

        result = self.runner.invoke(main, ["get-all-rec", "--force"])
        self.assertEqual(result.exit_code, 0)

        # Check per-category output
        self.assertIn("agents/: 2 deployed", result.output)
        self.assertIn("bin/: 2 deployed", result.output)
        self.assertIn("skills/: 1 deployed", result.output)
        self.assertIn("commands/: 2 deployed", result.output)
        self.assertIn("prompts/: 2 deployed", result.output)
        self.assertIn(".mcp.json: 1 servers exported", result.output)

        # Verify files exist in .github/
        self.assertTrue((Path.cwd() / ".github" / "agents" / "reviewer.agent.md").exists())
        self.assertTrue((Path.cwd() / ".github" / "agents" / "implementer.agent.md").exists())
        self.assertTrue((Path.cwd() / ".github" / "bin" / "build.sh").exists())
        self.assertTrue((Path.cwd() / ".github" / "bin" / "deploy.sh").exists())
        self.assertTrue((Path.cwd() / ".github" / "skills" / "my-skill" / "SKILL.md").exists())
        self.assertTrue((Path.cwd() / ".github" / "commands" / "hello.md").exists())
        self.assertTrue((Path.cwd() / ".github" / "commands" / "list-files.md").exists())
        self.assertTrue((Path.cwd() / ".github" / "prompts" / "code-review.md").exists())
        self.assertTrue((Path.cwd() / ".github" / "prompts" / "summarize.md").exists())
        self.assertTrue((Path.cwd() / ".mcp.json").exists())

        # Verify .mcp.json content (only enabled servers)
        mcp_data = json.loads((Path.cwd() / ".mcp.json").read_text())
        self.assertIn("test-server", mcp_data["mcpServers"])
        self.assertNotIn("disabled-server", mcp_data["mcpServers"])

        # Cleanup
        import shutil

        shutil.rmtree(Path.cwd() / ".github", ignore_errors=True)
        (Path.cwd() / ".mcp.json").unlink(missing_ok=True)

    def test_get_all_rec_with_project_dir(self):
        """Verify --project-dir deploys to a custom directory."""
        self._populate_store()

        project_dir = Path(self.temp_dir.name) / "my-project"
        project_dir.mkdir(parents=True, exist_ok=True)

        result = self.runner.invoke(
            main,
            [
                "get-all-rec",
                "--force",
                "--project-dir",
                str(project_dir),
            ],
        )
        self.assertEqual(result.exit_code, 0)

        # Verify files in the custom project directory
        self.assertTrue((project_dir / ".github" / "agents" / "reviewer.agent.md").exists())
        self.assertTrue((project_dir / ".github" / "bin" / "build.sh").exists())
        self.assertTrue((project_dir / ".mcp.json").exists())

        # Cleanup
        import shutil

        shutil.rmtree(project_dir / ".github", ignore_errors=True)
        (project_dir / ".mcp.json").unlink(missing_ok=True)

    def test_get_all_rec_overwrite_prompt(self):
        """Verify confirmation prompt is shown without --force."""
        self._populate_store()

        # First deploy with --force
        result = self.runner.invoke(main, ["get-all-rec", "--force"])
        self.assertEqual(result.exit_code, 0)

        # Deploy again without --force → needs confirmation per file/dir
        # 2 agents + 2 bins + 1 skill + 2 commands + 2 prompts + 1 mcp = 10 prompts
        result = self.runner.invoke(main, ["get-all-rec"], input="\n".join(["y"] * 10))
        self.assertEqual(result.exit_code, 0)
        self.assertIn("agents", result.output)

        # Cleanup
        import shutil

        shutil.rmtree(Path.cwd() / ".github", ignore_errors=True)
        (Path.cwd() / ".mcp.json").unlink(missing_ok=True)
