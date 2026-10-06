"""Tests for instruction.py."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from click.testing import CliRunner

from ai_adapter.cli import main
from ai_adapter.config import init


class TestInstructionCommands(unittest.TestCase):
    """Tests for instruction subcommands."""

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

        self.inst_file = Path(self.temp_dir.name) / "AGENTS.md"
        self.inst_file.write_text("# Root Agent\n\nThis is the root agent.\n")

    def tearDown(self):
        import pathlib

        pathlib.Path.home = staticmethod(self._original_home)
        import ai_adapter.config as cfg

        cfg.AI_ADAPTER_DIR = Path.home() / ".ai-adapter"
        self.temp_dir.cleanup()

    def test_instruction_list_empty(self):
        """Verify empty message is shown when no instructions registered."""
        result = self.runner.invoke(main, ["agent", "list"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("No instructions registered.", result.output)

    def test_instruction_add(self):
        """Verify instruction add adds an instruction."""
        result = self.runner.invoke(main, ["agent", "add", str(self.inst_file)])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("AGENTS", result.output)

        # Verify file was copied
        inst_dir = self.patch_home / ".ai-adapter" / "instructions"
        self.assertTrue((inst_dir / "AGENTS.md").exists())

    def test_instruction_add_and_list(self):
        """Verify instruction add → instruction list flow."""
        self.runner.invoke(main, ["agent", "add", str(self.inst_file)])
        result = self.runner.invoke(main, ["agent", "list"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("AGENTS", result.output)

    def test_instruction_get(self):
        """Verify instruction get copies to project root."""
        self.runner.invoke(main, ["agent", "add", str(self.inst_file)])

        result = self.runner.invoke(main, ["agent", "get", "AGENTS"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("AGENTS.md", result.output)
        root_file = Path.cwd() / "AGENTS.md"
        self.assertTrue(root_file.exists())

        # Cleanup
        root_file.unlink(missing_ok=True)

    def test_instruction_get_with_project_dir(self):
        """Verify instruction get --project-dir copies to specified directory root."""
        self.runner.invoke(main, ["agent", "add", str(self.inst_file)])

        project_dir = Path(self.temp_dir.name) / "my-project"
        project_dir.mkdir(parents=True)

        result = self.runner.invoke(
            main,
            [
                "agent",
                "get",
                "AGENTS",
                "--project-dir",
                str(project_dir),
            ],
        )
        self.assertEqual(result.exit_code, 0)
        self.assertTrue((project_dir / "AGENTS.md").exists())

    def test_instruction_get_not_found(self):
        """Verify get fails for non-existent instruction."""
        result = self.runner.invoke(main, ["agent", "get", "nonexistent"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("not found", result.output)

    def test_instruction_get_with_force(self):
        """Verify instruction get --force overwrites without confirmation."""
        self.runner.invoke(main, ["agent", "add", str(self.inst_file)])

        # First get to create the file
        self.runner.invoke(main, ["agent", "get", "AGENTS"])

        # Second get with --force
        result = self.runner.invoke(main, ["agent", "get", "AGENTS", "--force"])
        self.assertEqual(result.exit_code, 0)
        self.assertTrue((Path.cwd() / "AGENTS.md").exists())

        (Path.cwd() / "AGENTS.md").unlink(missing_ok=True)

    def test_instruction_remove(self):
        """Verify instruction remove removes an instruction."""
        self.runner.invoke(main, ["agent", "add", str(self.inst_file)])
        result = self.runner.invoke(main, ["agent", "remove", "AGENTS"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("AGENTS", result.output)

        # Verify list is empty
        result = self.runner.invoke(main, ["agent", "list"])
        self.assertIn("No instructions registered.", result.output)

    def test_instruction_add_rec(self):
        """Verify add-rec registers all files in a directory."""
        src_dir = Path(self.temp_dir.name) / "inst_dir"
        src_dir.mkdir()
        (src_dir / "AGENTS.md").write_text("# Agents\n")
        (src_dir / "CLAUDE.md").write_text("# Claude\n")

        result = self.runner.invoke(main, ["agent", "add-rec", str(src_dir)])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("2", result.output)

        result = self.runner.invoke(main, ["agent", "list"])
        self.assertIn("AGENTS", result.output)
        self.assertIn("CLAUDE", result.output)

    def test_instruction_get_all(self):
        """Verify get-all copies all instructions to project root."""
        self.runner.invoke(main, ["agent", "add", str(self.inst_file)])
        inst2 = Path(self.temp_dir.name) / "CLAUDE.md"
        inst2.write_text("# Claude\n")
        self.runner.invoke(main, ["agent", "add", str(inst2)])

        result = self.runner.invoke(main, ["agent", "get-all", "--force"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("2", result.output)
        self.assertTrue((Path.cwd() / "AGENTS.md").exists())
        self.assertTrue((Path.cwd() / "CLAUDE.md").exists())

        (Path.cwd() / "AGENTS.md").unlink(missing_ok=True)
        (Path.cwd() / "CLAUDE.md").unlink(missing_ok=True)

    def test_instruction_remove_all(self):
        """Verify remove-all --force removes all instructions."""
        inst2 = Path(self.temp_dir.name) / "CLAUDE.md"
        inst2.write_text("# Claude\n")
        self.runner.invoke(main, ["agent", "add", str(self.inst_file)])
        self.runner.invoke(main, ["agent", "add", str(inst2)])

        result = self.runner.invoke(main, ["agent", "remove-all", "--force"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("2", result.output)

        result = self.runner.invoke(main, ["agent", "list"])
        self.assertIn("No instructions registered.", result.output)


class TestInstructionScopeFormat(unittest.TestCase):
    """Tests for --format/--scope on agent get / get-all (design 01).

    T1-T12 of the design's test plan. ``agent`` here is instruction.py;
    tests/test_agent.py covers the separate sub-agent command.
    """

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

        self.inst_file = Path(self.temp_dir.name) / "AGENTS.md"
        self.inst_file.write_text("# Root Agent\n\nThis is the root agent.\n")

    def tearDown(self):
        import pathlib

        pathlib.Path.home = staticmethod(self._original_home)
        import ai_adapter.config as cfg

        cfg.AI_ADAPTER_DIR = Path.home() / ".ai-adapter"
        self.temp_dir.cleanup()

    def test_get_scope_user_platform_paths(self):
        """--format <platform> --scope user deploys to the platform user path."""
        self.runner.invoke(main, ["agent", "add", str(self.inst_file)])
        cases = [
            ("codex", self.patch_home / ".codex" / "AGENTS.md"),
            ("claude", self.patch_home / ".claude" / "AGENTS.md"),
            ("opencode", self.patch_home / ".config" / "opencode" / "AGENTS.md"),
            ("gemini", self.patch_home / ".gemini" / "AGENTS.md"),
        ]
        for format_name, expected in cases:
            with self.subTest(format=format_name):
                result = self.runner.invoke(
                    main,
                    ["agent", "get", "AGENTS", "--format", format_name, "--scope", "user"],
                )
                self.assertEqual(result.exit_code, 0, result.output)
                self.assertTrue(expected.exists(), f"{expected} was not created")

    def test_get_scope_user_zed_paths(self):
        """--format zed --scope user uses the OS-specific Zed directory.

        C1 fix: Zed resolves settings/instructions from the config dir
        (~/.config/zed) on macOS and Linux alike — NOT Application Support.
        """
        self.runner.invoke(main, ["agent", "add", str(self.inst_file)])
        expectations = [
            ("Darwin", self.patch_home / ".config" / "zed" / "AGENTS.md"),
            ("Linux", self.patch_home / ".config" / "zed" / "AGENTS.md"),
        ]
        with mock.patch.dict("os.environ", {}, clear=False):
            import os as _os

            _os.environ.pop("XDG_CONFIG_HOME", None)
            for system, expected in expectations:
                with self.subTest(system=system), mock.patch("ai_adapter.config.platform.system", return_value=system):
                    result = self.runner.invoke(
                        main, ["agent", "get", "AGENTS", "--format", "zed", "--scope", "user", "--force"]
                    )
                    self.assertEqual(result.exit_code, 0, result.output)
                    self.assertTrue(expected.exists(), f"{expected} was not created")

    def test_get_scope_user_standard_error(self):
        """--format standard --scope user is rejected with a clear error."""
        self.runner.invoke(main, ["agent", "add", str(self.inst_file)])
        result = self.runner.invoke(main, ["agent", "get", "AGENTS", "--format", "standard", "--scope", "user"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("--format standard does not support --scope user", result.output)

    def test_get_format_cursor_exit2(self):
        """--format cursor stays Exit(2) for both scopes (existing behaviour)."""
        self.runner.invoke(main, ["agent", "add", str(self.inst_file)])
        for scope_args in ([], ["--scope", "user"]):
            with self.subTest(scope_args=scope_args):
                result = self.runner.invoke(
                    main,
                    ["agent", "get", "AGENTS", "--format", "cursor", *scope_args],
                )
                self.assertEqual(result.exit_code, 2)
                self.assertIn("not supported", result.output)

    def test_get_scope_user_project_dir_ignored(self):
        """--project-dir is ignored (with a warning) under --scope user."""
        self.runner.invoke(main, ["agent", "add", str(self.inst_file)])
        project_dir = Path(self.temp_dir.name) / "ignored-project"
        project_dir.mkdir()
        result = self.runner.invoke(
            main,
            [
                "agent",
                "get",
                "AGENTS",
                "--format",
                "codex",
                "--scope",
                "user",
                "--project-dir",
                str(project_dir),
            ],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("ignored", result.output)
        self.assertTrue((self.patch_home / ".codex" / "AGENTS.md").exists())
        self.assertFalse((project_dir / "AGENTS.md").exists())

    def test_get_scope_user_skips_gitignore(self):
        """--scope user never calls add_to_gitignore (protects dotfiles repos)."""
        self.runner.invoke(main, ["agent", "add", str(self.inst_file)])
        with mock.patch("ai_adapter.commands.instruction.add_to_gitignore") as mocked:
            result = self.runner.invoke(main, ["agent", "get", "AGENTS", "--format", "codex", "--scope", "user"])
        self.assertEqual(result.exit_code, 0, result.output)
        mocked.assert_not_called()

    def test_get_scope_project_still_calls_gitignore(self):
        """Regression: project scope keeps calling add_to_gitignore."""
        self.runner.invoke(main, ["agent", "add", str(self.inst_file)])
        with mock.patch("ai_adapter.commands.instruction.add_to_gitignore") as mocked:
            result = self.runner.invoke(main, ["agent", "get", "AGENTS"])
        self.assertEqual(result.exit_code, 0, result.output)
        mocked.assert_called_once()
        (Path.cwd() / "AGENTS.md").unlink(missing_ok=True)

    def test_get_scope_user_overwrite_force(self):
        """Existing user file is overwritten when --force is given."""
        self.runner.invoke(main, ["agent", "add", str(self.inst_file)])
        self.runner.invoke(main, ["agent", "get", "AGENTS", "--format", "codex", "--scope", "user"])
        result = self.runner.invoke(
            main,
            ["agent", "get", "AGENTS", "--format", "codex", "--scope", "user", "--force"],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertTrue((self.patch_home / ".codex" / "AGENTS.md").exists())

    def test_get_scope_user_overwrite_prompts(self):
        """Existing user file without --force asks for confirmation."""
        self.runner.invoke(main, ["agent", "add", str(self.inst_file)])
        self.runner.invoke(main, ["agent", "get", "AGENTS", "--format", "codex", "--scope", "user"])
        result = self.runner.invoke(
            main,
            ["agent", "get", "AGENTS", "--format", "codex", "--scope", "user"],
            input="n\n",
        )
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("already exists", result.output)

    def test_get_all_scope_user_maps_filenames(self):
        """get-all --scope user maps files to the platform's filename."""
        self.runner.invoke(main, ["agent", "add", str(self.inst_file)])  # AGENTS.md
        style = Path(self.temp_dir.name) / "STYLE.md"
        style.write_text("# Style\n")
        self.runner.invoke(main, ["agent", "add", str(style)])

        result = self.runner.invoke(
            main,
            ["agent", "get-all", "--format", "claude", "--scope", "user", "--force"],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        claude_dir = self.patch_home / ".claude"
        # First file maps AGENTS.md → CLAUDE.md (Claude's actual filename).
        mapped = claude_dir / "CLAUDE.md"
        self.assertTrue(mapped.exists())
        self.assertEqual(mapped.read_text(), "# Root Agent\n\nThis is the root agent.\n")
        # Second file collides on CLAUDE.md → kept under its original name.
        self.assertTrue((claude_dir / "STYLE.md").exists())
        self.assertIn("conflict", result.output)
        self.assertIn("Copied 2 instructions", result.output)

    def test_get_all_scope_user_all_platforms(self):
        """Filename mapping works for every platform."""
        self.runner.invoke(main, ["agent", "add", str(self.inst_file)])  # AGENTS.md
        cases = [
            ("codex", self.patch_home / ".codex" / "AGENTS.md"),
            ("claude", self.patch_home / ".claude" / "CLAUDE.md"),
            ("opencode", self.patch_home / ".config" / "opencode" / "AGENTS.md"),
            ("gemini", self.patch_home / ".gemini" / "GEMINI.md"),
        ]
        for format_name, expected in cases:
            with self.subTest(format=format_name):
                result = self.runner.invoke(
                    main,
                    ["agent", "get-all", "--format", format_name, "--scope", "user", "--force"],
                )
                self.assertEqual(result.exit_code, 0, result.output)
                self.assertTrue(expected.exists(), f"{expected} was not created")

    def test_get_all_scope_user_zed(self):
        """get-all --scope user --format zed uses the OS-specific Zed directory."""
        self.runner.invoke(main, ["agent", "add", str(self.inst_file)])
        with mock.patch("ai_adapter.config.platform.system", return_value="Linux"):
            result = self.runner.invoke(
                main,
                ["agent", "get-all", "--format", "zed", "--scope", "user", "--force"],
            )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertTrue((self.patch_home / ".config" / "zed" / "AGENTS.md").exists())

    def test_get_all_scope_user_collision_keeps_existing(self):
        """Mapped-name collision with an existing disk file keeps the source name."""
        self.runner.invoke(main, ["agent", "add", str(self.inst_file)])  # AGENTS.md
        style = Path(self.temp_dir.name) / "STYLE.md"
        style.write_text("# Style\n")
        self.runner.invoke(main, ["agent", "add", str(style)])
        claude_dir = self.patch_home / ".claude"
        claude_dir.mkdir(parents=True)
        existing = claude_dir / "CLAUDE.md"
        existing.write_text("# Existing\n")

        result = self.runner.invoke(main, ["agent", "get-all", "--format", "claude", "--scope", "user"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(existing.read_text(), "# Existing\n")
        self.assertTrue((claude_dir / "AGENTS.md").exists())
        self.assertTrue((claude_dir / "STYLE.md").exists())
        self.assertIn("conflict", result.output)

    def test_get_all_scope_user_reverse_order_no_overwrite(self):
        """C1 regression: STYLE.md mapped to CLAUDE.md must not be overwritten by later CLAUDE.md."""
        style = Path(self.temp_dir.name) / "STYLE.md"
        style.write_text("# Style content\n")
        self.runner.invoke(main, ["agent", "add", str(style)])
        claude_md = Path(self.temp_dir.name) / "CLAUDE.md"
        claude_md.write_text("# Claude content\n")
        self.runner.invoke(main, ["agent", "add", str(claude_md)])

        claude_dir = self.patch_home / ".claude"
        result = self.runner.invoke(main, ["agent", "get-all", "--format", "claude", "--scope", "user", "--force"])
        self.assertEqual(result.exit_code, 0, result.output)
        # STYLE.md was mapped to CLAUDE.md first; CLAUDE.md must not overwrite it.
        self.assertEqual((claude_dir / "CLAUDE.md").read_text(), "# Style content\n")
        # The native CLAUDE.md keeps a numbered name.
        self.assertEqual((claude_dir / "CLAUDE (1).md").read_text(), "# Claude content\n")
        self.assertIn("conflict", result.output)

    def test_get_all_scope_user_reverse_order_prompt(self):
        """C1 regression without --force: prompt is shown, not silent overwrite."""
        style = Path(self.temp_dir.name) / "STYLE.md"
        style.write_text("# Style content\n")
        self.runner.invoke(main, ["agent", "add", str(style)])
        claude_md = Path(self.temp_dir.name) / "CLAUDE.md"
        claude_md.write_text("# Claude content\n")
        self.runner.invoke(main, ["agent", "add", str(claude_md)])

        claude_dir = self.patch_home / ".claude"
        # First file maps to CLAUDE.md; second file also maps to CLAUDE.md → prompt.
        result = self.runner.invoke(
            main,
            ["agent", "get-all", "--format", "claude", "--scope", "user"],
            input="y\n",
        )
        self.assertEqual(result.exit_code, 0, result.output)
        # STYLE.md's mapping target must survive.
        self.assertEqual((claude_dir / "CLAUDE.md").read_text(), "# Style content\n")

    def test_get_all_scope_user_identity_mapping_shown(self):
        """Identity mapping (AGENTS.md → AGENTS.md) is shown in output."""
        self.runner.invoke(main, ["agent", "add", str(self.inst_file)])  # AGENTS.md
        result = self.runner.invoke(main, ["agent", "get-all", "--format", "codex", "--scope", "user"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("AGENTS.md → AGENTS.md", result.output)

    def test_get_all_format_cursor_rejected(self):
        """get-all --format cursor exits with code 2 (same as get)."""
        self.runner.invoke(main, ["agent", "add", str(self.inst_file)])
        result = self.runner.invoke(main, ["agent", "get-all", "--format", "cursor"])
        self.assertEqual(result.exit_code, 2)
        self.assertIn("not supported", result.output)

    def test_get_all_format_standard_scope_user_error(self):
        """get-all --format standard --scope user is an error."""
        self.runner.invoke(main, ["agent", "add", str(self.inst_file)])
        result = self.runner.invoke(main, ["agent", "get-all", "--format", "standard", "--scope", "user"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("standard", result.output)

    def test_get_all_scope_project_calls_gitignore(self):
        """get-all --scope project calls add_to_gitignore (mirror of T12)."""
        self.runner.invoke(main, ["agent", "add", str(self.inst_file)])
        with mock.patch("ai_adapter.commands.instruction.add_to_gitignore") as mocked:
            result = self.runner.invoke(main, ["agent", "get-all", "--scope", "project", "--force"])
        self.assertEqual(result.exit_code, 0, result.output)
        mocked.assert_called()
        (Path.cwd() / "AGENTS.md").unlink(missing_ok=True)

    def test_get_all_scope_user_skips_gitignore(self):
        """get-all --scope user never calls add_to_gitignore."""
        self.runner.invoke(main, ["agent", "add", str(self.inst_file)])
        with mock.patch("ai_adapter.commands.instruction.add_to_gitignore") as mocked:
            result = self.runner.invoke(
                main,
                ["agent", "get-all", "--format", "codex", "--scope", "user", "--force"],
            )
        self.assertEqual(result.exit_code, 0, result.output)
        mocked.assert_not_called()

    def test_get_all_scope_project_keeps_filenames(self):
        """--scope project keeps original filenames regardless of --format."""
        self.runner.invoke(main, ["agent", "add", str(self.inst_file)])
        style = Path(self.temp_dir.name) / "STYLE.md"
        style.write_text("# Style\n")
        self.runner.invoke(main, ["agent", "add", str(style)])

        result = self.runner.invoke(
            main,
            ["agent", "get-all", "--format", "claude", "--scope", "project", "--force"],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertTrue((Path.cwd() / "AGENTS.md").exists())
        self.assertTrue((Path.cwd() / "STYLE.md").exists())
        self.assertFalse((Path.cwd() / "CLAUDE.md").exists())
        (Path.cwd() / "AGENTS.md").unlink(missing_ok=True)
        (Path.cwd() / "STYLE.md").unlink(missing_ok=True)

    def test_get_all_scope_user_empty(self):
        """Empty store with --scope user is not an error."""
        result = self.runner.invoke(main, ["agent", "get-all", "--format", "claude", "--scope", "user"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("No instructions registered.", result.output)


class TestInstructionGithubTargetLifecycle(unittest.TestCase):
    """QA M3: --target github-* deploy → remove must clean up files."""

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

        self.inst_file = Path(self.temp_dir.name) / "AGENTS.md"
        self.inst_file.write_text("# Agents\n")
        self.runner.invoke(main, ["agent", "add", str(self.inst_file)])

    def tearDown(self):
        import pathlib

        pathlib.Path.home = staticmethod(self._original_home)
        import ai_adapter.config as cfg

        cfg.AI_ADAPTER_DIR = Path.home() / ".ai-adapter"
        self.temp_dir.cleanup()

    def test_github_instructions_deploy_then_remove_cleans_up(self):
        """--target github-instructions deploy → remove deletes the file."""
        proj = Path(self.temp_dir.name) / "proj"
        proj.mkdir()
        result = self.runner.invoke(
            main,
            ["agent", "get", "AGENTS", "--target", "github-instructions", "--project-dir", str(proj)],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        deployed = proj / ".github" / "instructions" / "AGENTS.md"
        self.assertTrue(deployed.exists())

        import os

        old_cwd = Path.cwd()
        os.chdir(proj)
        try:
            remove_result = self.runner.invoke(main, ["agent", "remove", "AGENTS"])
        finally:
            os.chdir(old_cwd)
        self.assertEqual(remove_result.exit_code, 0, remove_result.output)
        self.assertFalse(deployed.exists())

    def test_github_copilot_deploy_then_remove_cleans_up(self):
        """QA M3: --target github-copilot deploy → remove deletes the fixed-name file.

        Any instruction name (e.g. AGENTS) may be deployed as
        copilot-instructions.md; remove must delete it regardless of name.
        """
        proj = Path(self.temp_dir.name) / "proj"
        proj.mkdir()
        result = self.runner.invoke(
            main,
            ["agent", "get", "AGENTS", "--target", "github-copilot", "--project-dir", str(proj)],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        deployed = proj / ".github" / "copilot-instructions.md"
        self.assertTrue(deployed.exists())

        import os

        old_cwd = Path.cwd()
        os.chdir(proj)
        try:
            remove_result = self.runner.invoke(main, ["agent", "remove", "AGENTS"])
        finally:
            os.chdir(old_cwd)
        self.assertEqual(remove_result.exit_code, 0, remove_result.output)
        self.assertFalse(deployed.exists())


class TestInstructionCursorrulesFormat(unittest.TestCase):
    """agent get/get-all --format cursorrules (design 07 task 07-1).

    ``agent`` here is instruction.py (see module docstring of
    TestInstructionScopeFormat); test_cursor.py covers provider-level and
    CLI-integration cases.
    """

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

        self.inst_file = Path(self.temp_dir.name) / "AGENTS.md"
        self.inst_file.write_text("---\nname: AGENTS\n---\n# Root Agent\n\nRules.\n")

    def tearDown(self):
        import pathlib

        pathlib.Path.home = staticmethod(self._original_home)
        import ai_adapter.config as cfg

        cfg.AI_ADAPTER_DIR = Path.home() / ".ai-adapter"
        self.temp_dir.cleanup()

    def test_get_cursorrules_strips_frontmatter(self):
        """AC1: frontmatter is removed from the emitted .cursorrules."""
        self.runner.invoke(main, ["agent", "add", str(self.inst_file)])
        result = self.runner.invoke(main, ["agent", "get", "AGENTS", "--format", "cursorrules"])
        self.assertEqual(result.exit_code, 0, result.output)
        out = Path.cwd() / ".cursorrules"
        self.assertTrue(out.exists())
        content = out.read_text()
        self.assertNotIn("---", content)
        self.assertIn("# Root Agent", content)

    def test_get_cursorrules_single_instruction_only(self):
        """agent get emits only the named instruction (no concatenation)."""
        style = Path(self.temp_dir.name) / "STYLE.md"
        style.write_text("# Style\n")
        self.runner.invoke(main, ["agent", "add", str(self.inst_file)])
        self.runner.invoke(main, ["agent", "add", str(style)])
        result = self.runner.invoke(main, ["agent", "get", "AGENTS", "--format", "cursorrules"])
        self.assertEqual(result.exit_code, 0, result.output)
        content = (Path.cwd() / ".cursorrules").read_text()
        self.assertIn("# Root Agent", content)
        self.assertNotIn("# Style", content)

    def test_get_all_cursorrules_concatenates_with_separators(self):
        """AC2: instructions are joined with # --- <name> --- separators."""
        style = Path(self.temp_dir.name) / "STYLE.md"
        style.write_text("# Style prefs\n")
        self.runner.invoke(main, ["agent", "add", str(self.inst_file)])
        self.runner.invoke(main, ["agent", "add", str(style)])
        result = self.runner.invoke(main, ["agent", "get-all", "--format", "cursorrules"])
        self.assertEqual(result.exit_code, 0, result.output)
        content = (Path.cwd() / ".cursorrules").read_text()
        self.assertIn("# --- AGENTS ---", content)
        self.assertIn("# --- STYLE ---", content)

    def test_get_all_cursorrules_project_dir(self):
        """--project-dir is respected for cursorrules output."""
        self.runner.invoke(main, ["agent", "add", str(self.inst_file)])
        project_dir = Path(self.temp_dir.name) / "proj"
        project_dir.mkdir()
        result = self.runner.invoke(
            main, ["agent", "get-all", "--format", "cursorrules", "--project-dir", str(project_dir)]
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertTrue((project_dir / ".cursorrules").exists())

    def test_get_cursorrules_existing_prompts(self):
        """Existing .cursorrules prompts without --force."""
        self.runner.invoke(main, ["agent", "add", str(self.inst_file)])
        self.runner.invoke(main, ["agent", "get", "AGENTS", "--format", "cursorrules"])
        result = self.runner.invoke(main, ["agent", "get", "AGENTS", "--format", "cursorrules"], input="n\n")
        self.assertNotEqual(result.exit_code, 0)
        result2 = self.runner.invoke(main, ["agent", "get", "AGENTS", "--format", "cursorrules", "--force"])
        self.assertEqual(result2.exit_code, 0, result2.output)

    def test_get_cursorrules_scope_user_rejected(self):
        """--scope user is rejected for cursorrules (project-root only)."""
        self.runner.invoke(main, ["agent", "add", str(self.inst_file)])
        result = self.runner.invoke(main, ["agent", "get", "AGENTS", "--format", "cursorrules", "--scope", "user"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("does not support --scope user", result.output)

    def test_format_cursor_stays_exit2(self):
        """--format cursor remains Exit(2) — distinct from cursorrules."""
        self.runner.invoke(main, ["agent", "add", str(self.inst_file)])
        for command in ("get", "get-all"):
            with self.subTest(command=command):
                args = ["agent", command]
                if command == "get":
                    args.append("AGENTS")
                args += ["--format", "cursor"]
                result = self.runner.invoke(main, args)
                self.assertEqual(result.exit_code, 2)
                self.assertIn("not supported", result.output)
