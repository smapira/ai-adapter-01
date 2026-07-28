"""Tests for bin.py."""

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


class TestBinAddRecCommand(unittest.TestCase):
    """Tests for the bin add-rec command."""

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

    def test_bin_add_rec(self):
        """Verify add-rec registers all scripts in a directory."""
        src_dir = Path(self.temp_dir.name) / "scripts_dir"
        src_dir.mkdir()
        (src_dir / "script1.sh").write_text("#!/bin/bash")
        (src_dir / "script2.sh").write_text("#!/bin/bash")

        result = self.runner.invoke(main, ["bin", "add-rec", "--env", "default", str(src_dir)])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("2", result.output)

        # Verify via list
        result = self.runner.invoke(main, ["bin", "list"])
        self.assertIn("script1.sh", result.output)
        self.assertIn("script2.sh", result.output)


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


class TestBinCommands(unittest.TestCase):
    """Tests for bin subcommands."""

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

        # Create test script file
        self.script_file = Path(self.temp_dir.name) / "deploy-test.sh"
        self.script_file.write_text("#!/bin/bash\necho 'deploy test'\n")

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

    def test_bin_list_empty(self):
        """Verify empty message is shown when no scripts registered."""
        result = self.runner.invoke(main, ["bin", "list"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("No scripts registered.", result.output)

    def test_bin_add(self):
        """Verify bin add adds a script."""
        result = self.runner.invoke(
            main,
            [
                "bin",
                "add",
                "--env",
                "default",
                str(self.script_file),
                "--description",
                "Test script",
            ],
        )
        self.assertEqual(result.exit_code, 0)
        self.assertIn("deploy-test.sh", result.output)

        bins_dir = self.patch_home / ".ai-adapter" / "bin"
        self.assertTrue((bins_dir / "deploy-test.sh").exists())

    def test_bin_add_and_list(self):
        """Verify bin add → bin list flow."""
        self.runner.invoke(main, ["bin", "add", "--env", "default", str(self.script_file)])
        result = self.runner.invoke(main, ["bin", "list"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("deploy-test.sh", result.output)

    def test_bin_add_and_list_filtered(self):
        """Verify bin add → bin list filters by env."""
        self.runner.invoke(main, ["bin", "add", "--env", "default", str(self.script_file)])
        result = self.runner.invoke(main, ["bin", "list", "--env", "default"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("deploy-test.sh", result.output)

        result = self.runner.invoke(main, ["bin", "list", "--env", "nonexistent"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("has no scripts registered", result.output)

    def test_bin_get(self):
        """Verify bin get copies to .github/bin/."""
        self.runner.invoke(main, ["bin", "add", "--env", "default", str(self.script_file)])

        github_bin = Path.cwd() / ".github" / "bin"
        github_bin.mkdir(parents=True, exist_ok=True)

        result = self.runner.invoke(main, ["bin", "get", "--env", "default", "deploy-test.sh"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("deploy-test.sh", result.output)
        self.assertTrue((github_bin / "deploy-test.sh").exists())


        _safe_github_cleanup(Path.cwd())

    def test_bin_get_not_found(self):
        """Verify get fails for non-existent script."""
        result = self.runner.invoke(main, ["bin", "get", "--env", "default", "nonexistent.sh"])
        self.assertNotEqual(result.exit_code, 0)

    def test_bin_get_with_project_dir(self):
        """Verify bin get --project-dir copies to the specified directory."""
        self.runner.invoke(main, ["bin", "add", "--env", "default", str(self.script_file)])

        project_dir = Path(self.temp_dir.name) / "my-project"
        project_dir.mkdir(parents=True)

        result = self.runner.invoke(
            main,
            [
                "bin",
                "get",
                "--env",
                "default",
                "deploy-test.sh",
                "--project-dir",
                str(project_dir),
            ],
        )
        self.assertEqual(result.exit_code, 0)
        self.assertTrue((project_dir / ".github" / "bin" / "deploy-test.sh").exists())

    def test_bin_get_all(self):
        """Verify bin get-all copies all scripts to .github/bin/."""
        script1 = Path(self.temp_dir.name) / "test1.sh"
        script1.write_text("#!/bin/bash")
        script2 = Path(self.temp_dir.name) / "test2.sh"
        script2.write_text("#!/bin/bash")
        self.runner.invoke(main, ["bin", "add", "--env", "default", str(script1)])
        self.runner.invoke(main, ["bin", "add", "--env", "default", str(script2)])

        github_bin = Path.cwd() / ".github" / "bin"
        github_bin.mkdir(parents=True, exist_ok=True)

        result = self.runner.invoke(main, ["bin", "get-all"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("2", result.output)
        self.assertTrue((github_bin / "test1.sh").exists())
        self.assertTrue((github_bin / "test2.sh").exists())


        _safe_github_cleanup(Path.cwd())

    def test_bin_remove(self):
        """Verify bin remove unregisters a script."""
        self.runner.invoke(main, ["bin", "add", "--env", "default", str(self.script_file)])
        result = self.runner.invoke(main, ["bin", "remove", "--env", "default", "deploy-test.sh"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("deploy-test.sh", result.output)

        # Verify file is not removed
        bins_dir = self.patch_home / ".ai-adapter" / "bin"
        self.assertTrue((bins_dir / "deploy-test.sh").exists())

    def test_bin_remove_not_found(self):
        """Verify remove fails for non-existent script."""
        result = self.runner.invoke(main, ["bin", "remove", "--env", "default", "nonexistent.sh"])
        self.assertNotEqual(result.exit_code, 0)

    def test_bin_remove_all(self):
        """Verify bin remove-all unregisters all scripts."""
        script1 = Path(self.temp_dir.name) / "test1.sh"
        script1.write_text("#!/bin/bash")
        script2 = Path(self.temp_dir.name) / "test2.sh"
        script2.write_text("#!/bin/bash")
        self.runner.invoke(main, ["bin", "add", "--env", "default", str(script1)])
        self.runner.invoke(main, ["bin", "add", "--env", "default", str(script2)])

        result = self.runner.invoke(main, ["bin", "remove-all", "--force"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("All scripts", result.output)

        # List is now empty
        result = self.runner.invoke(main, ["bin", "list"])
        self.assertIn("No scripts registered.", result.output)
