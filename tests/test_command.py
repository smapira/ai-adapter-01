"""Tests for command.py."""

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

    def test_command_get_opencode_scope_user(self):
        """--format opencode --scope user → ~/.config/opencode/commands/ (task 04-4)."""
        self.runner.invoke(main, ["command", "add", str(self.cmd_file)])
        result = self.runner.invoke(
            main,
            ["command", "get", "deploy", "--format", "opencode", "--scope", "user"],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        dest = self.patch_home / ".config" / "opencode" / "commands" / "deploy.sh"
        self.assertTrue(dest.exists())

    def test_command_get_opencode_project_scope(self):
        """--format opencode --scope project → .github/commands/ (unchanged)."""
        self.runner.invoke(main, ["command", "add", str(self.cmd_file)])
        result = self.runner.invoke(
            main,
            ["command", "get", "deploy", "--format", "opencode", "--project-dir", str(Path.cwd())],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertTrue((Path.cwd() / ".github" / "commands" / "deploy.sh").exists())

    def test_command_get_scope_user_rejected_for_standard(self):
        """--scope user requires --format opencode (standard has no user path)."""
        self.runner.invoke(main, ["command", "add", str(self.cmd_file)])
        result = self.runner.invoke(
            main,
            ["command", "get", "deploy", "--format", "standard", "--scope", "user"],
        )
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("--scope user is only supported with --format claude", result.output)

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


class TestCommandGeminiFormat(unittest.TestCase):
    """command/prompt get --format gemini (design 05 task 05-4)."""

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

    def test_command_get_gemini_converts_to_toml(self):
        """--format gemini converts Markdown frontmatter + body to TOML."""
        src = Path(self.temp_dir.name) / "deploy.md"
        src.write_text("---\ndescription: Deploy the app\n---\n# Steps\n1. test\n", encoding="utf-8")
        self.runner.invoke(main, ["command", "add", str(src)])

        result = self.runner.invoke(
            main, ["command", "get", "deploy", "--format", "gemini", "--project-dir", str(self.project_dir)]
        )
        self.assertEqual(result.exit_code, 0, result.output)
        dest = self.project_dir / ".gemini" / "commands" / "deploy.toml"
        self.assertTrue(dest.exists())

        try:
            import tomllib
        except ModuleNotFoundError:  # Python 3.10
            import tomli as tomllib  # type: ignore[no-redef]

        data = tomllib.loads(dest.read_text(encoding="utf-8"))
        self.assertEqual(data["description"], "Deploy the app")
        self.assertIn("# Steps", data["prompt"])

    def test_command_get_gemini_nested_name(self):
        """Nested command dir/name → .gemini/commands/dir/name.toml."""
        store_dir = self.patch_home / ".ai-adapter" / "commands" / "dir"
        store_dir.mkdir(parents=True, exist_ok=True)
        (store_dir / "review.md").write_text("---\ndescription: Nested\n---\nReview it.\n", encoding="utf-8")
        import ai_adapter.config as cfg
        from ai_adapter.models import Command

        config = cfg.load_config()
        config.commands.append(Command(name="dir/review", content="x"))
        cfg.save_config(config)

        result = self.runner.invoke(
            main, ["command", "get", "dir/review", "--format", "gemini", "--project-dir", str(self.project_dir)]
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertTrue((self.project_dir / ".gemini" / "commands" / "dir" / "review.toml").exists())

    def test_command_get_gemini_scope_user(self):
        """--format gemini --scope user → ~/.gemini/commands/."""
        src = Path(self.temp_dir.name) / "deploy.md"
        src.write_text("---\ndescription: Deploy\n---\nGo.\n", encoding="utf-8")
        self.runner.invoke(main, ["command", "add", str(src)])

        result = self.runner.invoke(main, ["command", "get", "deploy", "--format", "gemini", "--scope", "user"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertTrue((self.patch_home / ".gemini" / "commands" / "deploy.toml").exists())

    def test_prompt_get_gemini_converts_to_toml(self):
        """prompt get --format gemini → .gemini/commands/<name>.toml."""
        src = Path(self.temp_dir.name) / "summarize.md"
        src.write_text("---\ndescription: Summarize\n---\nSummarize the text.\n", encoding="utf-8")
        self.runner.invoke(main, ["prompt", "add", str(src)])

        result = self.runner.invoke(
            main, ["prompt", "get", "summarize", "--format", "gemini", "--project-dir", str(self.project_dir)]
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertTrue((self.project_dir / ".gemini" / "commands" / "summarize.toml").exists())
