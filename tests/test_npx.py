"""Tests for the npx wrapper module and CLI command."""

import subprocess
import unittest
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from ai_adapter.cli import main
from ai_adapter.npx import find_npx, get_npx_version, is_npx_available, run_npx_skills


class TestFindNpx(unittest.TestCase):
    """Tests for find_npx()."""

    @patch("ai_adapter.npx.shutil.which")
    def test_found(self, mock_which):
        mock_which.return_value = "/usr/local/bin/npx"
        self.assertEqual(find_npx(), "/usr/local/bin/npx")
        mock_which.assert_called_once_with("npx")

    @patch("ai_adapter.npx.shutil.which")
    def test_not_found(self, mock_which):
        mock_which.return_value = None
        self.assertIsNone(find_npx())


class TestGetNpxVersion(unittest.TestCase):
    """Tests for get_npx_version()."""

    @patch("ai_adapter.npx.find_npx")
    def test_returns_version(self, mock_find):
        mock_find.return_value = "/usr/local/bin/npx"
        with patch("ai_adapter.npx.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="10.9.2\n",
            )
            self.assertEqual(get_npx_version(), "10.9.2")

    @patch("ai_adapter.npx.find_npx")
    def test_not_found(self, mock_find):
        mock_find.return_value = None
        self.assertIsNone(get_npx_version())

    @patch("ai_adapter.npx.find_npx")
    def test_timeout(self, mock_find):
        mock_find.return_value = "/usr/local/bin/npx"
        with patch("ai_adapter.npx.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="npx", timeout=10)
            self.assertIsNone(get_npx_version())

    @patch("ai_adapter.npx.find_npx")
    def test_nonzero_exit(self, mock_find):
        mock_find.return_value = "/usr/local/bin/npx"
        with patch("ai_adapter.npx.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="")
            self.assertIsNone(get_npx_version())


class TestRunNpxSkills(unittest.TestCase):
    """Tests for run_npx_skills()."""

    @patch("ai_adapter.npx.find_npx")
    def test_success(self, mock_find):
        mock_find.return_value = "/usr/local/bin/npx"
        with patch("ai_adapter.npx.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="skill-a\nskill-b\n",
                stderr="",
            )
            code, out, err = run_npx_skills(["list"])
            self.assertEqual(code, 0)
            self.assertIn("skill-a", out)
            mock_run.assert_called_once_with(
                ["/usr/local/bin/npx", "skills", "list"],
                capture_output=True,
                text=True,
                timeout=60,
            )

    @patch("ai_adapter.npx.find_npx")
    def test_not_found(self, mock_find):
        mock_find.return_value = None
        code, out, err = run_npx_skills(["find", "react"])
        self.assertEqual(code, 127)
        self.assertIn("npx is not installed", err)

    @patch("ai_adapter.npx.find_npx")
    def test_timeout(self, mock_find):
        mock_find.return_value = "/usr/local/bin/npx"
        with patch("ai_adapter.npx.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="npx", timeout=5)
            code, out, err = run_npx_skills(["add", "owner/repo"], timeout=5)
            self.assertEqual(code, 124)
            self.assertIn("timed out", err)

    @patch("ai_adapter.npx.find_npx")
    def test_custom_timeout(self, mock_find):
        mock_find.return_value = "/usr/local/bin/npx"
        with patch("ai_adapter.npx.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            run_npx_skills(["list"], timeout=120)
            mock_run.assert_called_once_with(
                ["/usr/local/bin/npx", "skills", "list"],
                capture_output=True,
                text=True,
                timeout=120,
            )

    @patch("ai_adapter.npx.find_npx")
    def test_nonzero_exit(self, mock_find):
        mock_find.return_value = "/usr/local/bin/npx"
        with patch("ai_adapter.npx.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="",
                stderr="Error: skill not found",
            )
            code, out, err = run_npx_skills(["remove", "nonexistent"])
            self.assertEqual(code, 1)
            self.assertIn("skill not found", err)


class TestIsNpxAvailable(unittest.TestCase):
    """Tests for is_npx_available()."""

    @patch("ai_adapter.npx.find_npx")
    def test_available(self, mock_find):
        mock_find.return_value = "/usr/local/bin/npx"
        self.assertTrue(is_npx_available())

    @patch("ai_adapter.npx.find_npx")
    def test_not_available(self, mock_find):
        mock_find.return_value = None
        self.assertFalse(is_npx_available())


class TestNpxCLI(unittest.TestCase):
    """CLI integration tests for the npx command."""

    def setUp(self):
        self.runner = CliRunner()

    def test_npx_help(self):
        """Verify --help displays correctly."""
        result = self.runner.invoke(main, ["npx", "--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("npx", result.output)
        self.assertIn("skills", result.output)

    def test_npx_skills_help(self):
        """Verify skills subcommand --help."""
        result = self.runner.invoke(main, ["npx", "skills", "--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("--check", result.output)
        self.assertIn("--version", result.output)
        self.assertIn("--timeout", result.output)

    @patch("ai_adapter.commands.npx.find_npx")
    def test_npx_skills_check_found(self, mock_find):
        """Verify skills --check shows npx path when found."""
        mock_find.return_value = "/usr/local/bin/npx"
        with patch("ai_adapter.commands.npx.get_npx_version") as mock_ver:
            mock_ver.return_value = "10.9.2"
            result = self.runner.invoke(main, ["npx", "skills", "--check"])
            self.assertEqual(result.exit_code, 0)
            self.assertIn("npx found", result.output)
            self.assertIn("10.9.2", result.output)

    @patch("ai_adapter.commands.npx.find_npx")
    def test_npx_skills_check_not_found(self, mock_find):
        """Verify skills --check shows error when npx not found."""
        mock_find.return_value = None
        result = self.runner.invoke(main, ["npx", "skills", "--check"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("npx not found", result.output)

    @patch("ai_adapter.commands.npx.get_npx_version")
    def test_npx_skills_version(self, mock_ver):
        """Verify skills --version shows version."""
        mock_ver.return_value = "10.9.2"
        result = self.runner.invoke(main, ["npx", "skills", "--version"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("10.9.2", result.output)

    @patch("ai_adapter.commands.npx.get_npx_version")
    def test_npx_skills_version_not_found(self, mock_ver):
        """Verify skills --version shows error when npx not found."""
        mock_ver.return_value = None
        result = self.runner.invoke(main, ["npx", "skills", "--version"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("npx not found", result.output)

    @patch("ai_adapter.commands.npx.run_npx_skills")
    def test_npx_skills_passthrough(self, mock_run):
        """Verify skills arguments are passed through."""
        mock_run.return_value = (0, "skill-a\nskill-b\n", "")
        result = self.runner.invoke(main, ["npx", "skills", "list"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("skill-a", result.output)
        mock_run.assert_called_once_with(["list"], timeout=60)

    @patch("ai_adapter.commands.npx.run_npx_skills")
    def test_npx_skills_find(self, mock_run):
        """Verify skills find passes arguments."""
        mock_run.return_value = (0, "Found: react-performance\n", "")
        result = self.runner.invoke(main, ["npx", "skills", "find", "react"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("react-performance", result.output)
        mock_run.assert_called_once_with(["find", "react"], timeout=60)

    @patch("ai_adapter.commands.npx.run_npx_skills")
    def test_npx_skills_error(self, mock_run):
        """Verify non-zero exit code propagates."""
        mock_run.return_value = (1, "", "Error: skill not found")
        result = self.runner.invoke(main, ["npx", "skills", "remove", "x"])
        self.assertNotEqual(result.exit_code, 0)

    @patch("ai_adapter.commands.npx.run_npx_skills")
    def test_npx_skills_timeout_option(self, mock_run):
        """Verify --timeout is respected."""
        mock_run.return_value = (0, "", "")
        self.runner.invoke(main, ["npx", "skills", "list", "--timeout", "30"])
        mock_run.assert_called_once_with(["list"], timeout=30)


if __name__ == "__main__":
    unittest.main()
