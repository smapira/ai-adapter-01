"""Tests for prompt.py."""

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


class TestPromptCommands(unittest.TestCase):
    """Tests for prompt subcommands."""

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

        self.prompt_file = Path(self.temp_dir.name) / "review.md"
        self.prompt_file.write_text("Code review checklist:\n- Security\n- Performance\n")

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

    def test_prompt_list_empty(self):
        result = self.runner.invoke(main, ["prompt", "list"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("No prompts registered.", result.output)

    def test_prompt_add(self):
        result = self.runner.invoke(main, ["prompt", "add", str(self.prompt_file)])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("review", result.output)

    def test_prompt_add_and_list(self):
        self.runner.invoke(main, ["prompt", "add", str(self.prompt_file)])
        result = self.runner.invoke(main, ["prompt", "list"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("review", result.output)

    def test_prompt_get(self):
        self.runner.invoke(main, ["prompt", "add", str(self.prompt_file)])
        github_dir = Path.cwd() / ".github" / "prompts"
        github_dir.mkdir(parents=True, exist_ok=True)
        result = self.runner.invoke(main, ["prompt", "get", "review"])
        self.assertEqual(result.exit_code, 0)
        self.assertTrue((github_dir / "review.md").exists())

        _safe_github_cleanup(Path.cwd())

    def test_prompt_remove(self):
        self.runner.invoke(main, ["prompt", "add", str(self.prompt_file)])
        result = self.runner.invoke(main, ["prompt", "remove", "review"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("review", result.output)

    def test_prompt_add_rec(self):
        """Verify add-rec registers all files in a directory."""
        src_dir = Path(self.temp_dir.name) / "prompt_dir"
        src_dir.mkdir()
        (src_dir / "code-review.md").write_text("Code review checklist:\n")
        (src_dir / "summary.txt").write_text("Summary:\n")

        result = self.runner.invoke(main, ["prompt", "add-rec", str(src_dir)])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("2", result.output)

        result = self.runner.invoke(main, ["prompt", "list"])
        self.assertIn("code-review", result.output)
        self.assertIn("summary", result.output)

    def test_prompt_get_all(self):
        """Verify get-all copies all prompts to .github/prompts/."""
        self.runner.invoke(main, ["prompt", "add", str(self.prompt_file)])
        prompt2 = Path(self.temp_dir.name) / "summary.md"
        prompt2.write_text("Summary:\n")
        self.runner.invoke(main, ["prompt", "add", str(prompt2)])

        github_dir = Path.cwd() / ".github" / "prompts"
        github_dir.mkdir(parents=True, exist_ok=True)

        result = self.runner.invoke(main, ["prompt", "get-all"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("2", result.output)
        self.assertTrue((github_dir / "review.md").exists())
        self.assertTrue((github_dir / "summary.md").exists())

        _safe_github_cleanup(Path.cwd())

    def test_prompt_remove_all(self):
        """Verify remove-all --force removes all prompts."""
        prompt2 = Path(self.temp_dir.name) / "summary.md"
        prompt2.write_text("Summary:\n")
        self.runner.invoke(main, ["prompt", "add", str(self.prompt_file)])
        self.runner.invoke(main, ["prompt", "add", str(prompt2)])

        result = self.runner.invoke(main, ["prompt", "remove-all", "--force"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("2", result.output)

        result = self.runner.invoke(main, ["prompt", "list"])
        self.assertIn("No prompts registered.", result.output)
