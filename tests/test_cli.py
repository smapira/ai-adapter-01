"""CLI integration tests."""

import json
import tempfile
import unittest
from pathlib import Path

from unittest.mock import patch, MagicMock

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
        self.assertIn("agent", result.output)
        self.assertIn("env", result.output)
        self.assertIn("bin", result.output)
        self.assertIn("skill", result.output)
        self.assertIn("mcp", result.output)
        self.assertIn("opencode", result.output)
        self.assertIn("command", result.output)
        self.assertIn("prompt", result.output)
        self.assertIn("add-all-rec", result.output)
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
        # init (空 Enter でリモート入力をSkip)
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
        result = self.runner.invoke(main, [
            "init", "--remote", "git@github.com:user/test.git",
        ])
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
        result = self.runner.invoke(main, ["agent", "--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("list", result.output)
        self.assertIn("add", result.output)
        self.assertIn("get", result.output)
        self.assertIn("remove", result.output)

    def test_agent_get_help(self):
        """Verify agent get --help shows --force option."""
        result = self.runner.invoke(main, ["agent", "get", "--help"])
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
        self.assertIn("export", result.output)
        self.assertIn("load", result.output)
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

        # Git リポジトリを模擬
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
        # clone 失敗 → 新規 init パス
        mock_clone.side_effect = GitError("clone failed")

        result = self.runner.invoke(main, [
            "start", "git@github.com:user/test.git",
        ])
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

        result = self.runner.invoke(main, [
            "start", "git@github.com:user/test.git",
        ], input="n\n")
        self.assertNotEqual(result.exit_code, 0)


class TestBinAddPathCommand(unittest.TestCase):
    """Tests for bin add-path command."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.runner = CliRunner()

    def tearDown(self):
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

    def tearDown(self):
        import pathlib
        pathlib.Path.home = staticmethod(self._original_home)
        import ai_adapter.config as cfg
        cfg.AI_ADAPTER_DIR = Path.home() / ".ai-adapter"
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

        # list で確認
        result = self.runner.invoke(main, ["agent", "list"])
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
        mcp_json.write_text(json.dumps({
            "mcpServers": {
                "test-server": {
                    "command": "npx",
                    "args": ["@test/server"],
                }
            }
        }))

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
