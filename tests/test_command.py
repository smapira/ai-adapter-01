"""Tests for command.py."""

import tempfile
import unittest
from pathlib import Path

from click.testing import CliRunner

from ai_adapter.cli import main
from ai_adapter.config import init


def _safe_github_cleanup(base_dir: "Path") -> None:
    """Remove test artifacts from .github/ without deleting .github/workflows/."""
    import shutil as _shutil

    github = Path(base_dir) / ".github"
    if not github.exists():
        return
    for sub in ("agents", "bin", "skills", "commands", "prompts"):
        d = github / sub
        if d.exists():
            _shutil.rmtree(d, ignore_errors=True)
    for f in github.glob(".mcp.json"):
        f.unlink(missing_ok=True)


class TestCommandCommands(unittest.TestCase):
    """Tests for command subcommands."""

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

        self.cmd_file = Path(self.temp_dir.name) / "deploy.sh"
        self.cmd_file.write_text("#!/bin/bash\necho 'deploy'\n")

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

    def test_command_list_empty(self):
        result = self.runner.invoke(main, ["command", "list"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("No commands registered.", result.output)

    def test_command_add(self):
        result = self.runner.invoke(main, ["command", "add", str(self.cmd_file)])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("deploy", result.output)

    def test_command_add_and_list(self):
        self.runner.invoke(main, ["command", "add", str(self.cmd_file)])
        result = self.runner.invoke(main, ["command", "list"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("deploy", result.output)

    def test_command_get(self):
        self.runner.invoke(main, ["command", "add", str(self.cmd_file)])
        github_dir = Path.cwd() / ".github" / "commands"
        github_dir.mkdir(parents=True, exist_ok=True)
        result = self.runner.invoke(main, ["command", "get", "deploy"])
        self.assertEqual(result.exit_code, 0)
        self.assertTrue((github_dir / "deploy.sh").exists())

        _safe_github_cleanup(Path.cwd())

    def test_command_remove(self):
        self.runner.invoke(main, ["command", "add", str(self.cmd_file)])
        result = self.runner.invoke(main, ["command", "remove", "deploy"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("deploy", result.output)

    def test_command_add_rec(self):
        """Verify add-rec registers all files in a directory."""
        src_dir = Path(self.temp_dir.name) / "cmd_dir"
        src_dir.mkdir()
        (src_dir / "build.sh").write_text("#!/bin/bash\necho build\n")
        (src_dir / "test.py").write_text("print('test')\n")

        result = self.runner.invoke(main, ["command", "add-rec", str(src_dir)])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("2", result.output)

        result = self.runner.invoke(main, ["command", "list"])
        self.assertIn("build", result.output)
        self.assertIn("test", result.output)

    def test_command_get_all(self):
        """Verify get-all copies all commands to .github/commands/."""
        self.runner.invoke(main, ["command", "add", str(self.cmd_file)])
        cmd2 = Path(self.temp_dir.name) / "build.sh"
        cmd2.write_text("#!/bin/bash\necho build\n")
        self.runner.invoke(main, ["command", "add", str(cmd2)])

        github_dir = Path.cwd() / ".github" / "commands"
        github_dir.mkdir(parents=True, exist_ok=True)

        result = self.runner.invoke(main, ["command", "get-all"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("2", result.output)
        self.assertTrue((github_dir / "deploy.sh").exists())
        self.assertTrue((github_dir / "build.sh").exists())


        _safe_github_cleanup(Path.cwd())

    def test_command_remove_all(self):
        """Verify remove-all --force removes all commands."""
        cmd2 = Path(self.temp_dir.name) / "build.sh"
        cmd2.write_text("#!/bin/bash\necho build\n")
        self.runner.invoke(main, ["command", "add", str(self.cmd_file)])
        self.runner.invoke(main, ["command", "add", str(cmd2)])

        result = self.runner.invoke(main, ["command", "remove-all", "--force"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("2", result.output)

        result = self.runner.invoke(main, ["command", "list"])
        self.assertIn("No commands registered.", result.output)
