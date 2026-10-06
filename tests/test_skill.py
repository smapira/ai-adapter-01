"""Tests for skill.py."""

import tempfile
import unittest
from pathlib import Path

from click.testing import CliRunner

from ai_adapter.cli import main
from ai_adapter.config import init, load_config, save_config


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


class TestSkillCommands(unittest.TestCase):
    """Tests for skill subcommands."""

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

        # Create test skill directory
        self.skill_dir = Path(self.temp_dir.name) / "test-skill"
        self.skill_dir.mkdir(parents=True)
        skill_md = self.skill_dir / "SKILL.md"
        skill_md.write_text(
            "---\n"
            "name: test-skill\n"
            "description: Test Skill\n"
            "tags: [test, python]\n"
            "---\n"
            "\n"
            "# Test Skill\n"
            "This is a test skill.\n"
        )

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

    def test_skill_list_empty(self):
        """Verify empty message when no skills registered."""
        result = self.runner.invoke(main, ["skill", "list"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("No skills registered.", result.output)

    def test_skill_add(self):
        """Verify skill add adds a skill."""
        result = self.runner.invoke(main, ["skill", "add", str(self.skill_dir)])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("test-skill", result.output)

        skills_dir = self.patch_home / ".ai-adapter" / "skills"
        self.assertTrue((skills_dir / "test-skill" / "SKILL.md").exists())

    def test_skill_add_rejects_unsafe_name(self):
        """Security: frontmatter ``name: ../../evil`` must be rejected by skill add.

        Joining the declared name onto the store would escape it
        (~/.ai-adapter/skills/../../evil → ~/evil), so the command must
        abort with an error (ClickException, surfaced as exit code 1)
        before anything is written.
        """
        unsafe_dir = Path(self.temp_dir.name) / "unsafe-skill"
        unsafe_dir.mkdir(parents=True)
        (unsafe_dir / "SKILL.md").write_text(
            "---\nname: ../../evil\ndescription: sneaky\n---\n# Sneaky\n",
            encoding="utf-8",
        )

        result = self.runner.invoke(main, ["skill", "add", str(unsafe_dir)])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Invalid skill name", result.output)

        # Nothing may be written inside the store or at the escape target (~/evil).
        skills_dir = self.patch_home / ".ai-adapter" / "skills"
        self.assertFalse((skills_dir / "unsafe-skill").exists())
        self.assertFalse((self.patch_home / "evil").exists())

    def test_skill_add_and_list(self):
        """Verify skill add → skill list flow."""
        self.runner.invoke(main, ["skill", "add", str(self.skill_dir)])
        result = self.runner.invoke(main, ["skill", "list"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("test-skill", result.output)

    def test_skill_get(self):
        """Verify skill get copies to .github/skills/."""
        self.runner.invoke(main, ["skill", "add", str(self.skill_dir)])

        github_skills = Path.cwd() / ".github" / "skills"
        github_skills.mkdir(parents=True, exist_ok=True)

        result = self.runner.invoke(main, ["skill", "get", "test-skill"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("test-skill", result.output)
        self.assertTrue((github_skills / "test-skill" / "SKILL.md").exists())

    def test_skill_get_not_found(self):
        """Verify get fails for non-existent skill."""
        result = self.runner.invoke(main, ["skill", "get", "nonexistent"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("not found", result.output)

    def test_skill_get_with_project_dir(self):
        """Verify skill get --project-dir copies to specified directory."""
        self.runner.invoke(main, ["skill", "add", str(self.skill_dir)])

        project_dir = Path(self.temp_dir.name) / "my-project"
        project_dir.mkdir(parents=True)

        result = self.runner.invoke(
            main,
            [
                "skill",
                "get",
                "test-skill",
                "--project-dir",
                str(project_dir),
                "--force",
            ],
        )
        self.assertEqual(result.exit_code, 0)
        self.assertTrue((project_dir / ".github" / "skills" / "test-skill" / "SKILL.md").exists())

    def test_skill_remove(self):
        """Verify skill remove removes a skill."""
        self.runner.invoke(main, ["skill", "add", str(self.skill_dir)])
        result = self.runner.invoke(main, ["skill", "remove", "test-skill"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("test-skill", result.output)

        # Verify it is not displayed in list
        result = self.runner.invoke(main, ["skill", "list"])
        self.assertIn("No skills registered.", result.output)

    def test_skill_search(self):
        """Verify skill search finds skills."""
        self.runner.invoke(main, ["skill", "add", str(self.skill_dir)])
        result = self.runner.invoke(main, ["skill", "search", "python"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("test-skill", result.output)

    def test_skill_search_no_match(self):
        """Verify search shows no-match message and hint when nothing found."""
        self.runner.invoke(main, ["skill", "add", str(self.skill_dir)])
        result = self.runner.invoke(main, ["skill", "search", "nonexistent"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("No matching skills found", result.output)
        self.assertIn("Hint:", result.output)

    def test_skill_search_tag_filter(self):
        """Verify --tag narrows search results to skills having that tag."""
        self.runner.invoke(main, ["skill", "add", str(self.skill_dir)])
        # Second skill matching the keyword but with a different tag
        other_dir = Path(self.temp_dir.name) / "other-skill"
        other_dir.mkdir(parents=True)
        (other_dir / "SKILL.md").write_text(
            "---\nname: other-skill\ndescription: Python based\ntags: [react]\n---\n# Other\n"
        )
        self.runner.invoke(main, ["skill", "add", str(other_dir)])

        result = self.runner.invoke(main, ["skill", "search", "python", "--tag", "test"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("test-skill", result.output)
        self.assertNotIn("other-skill", result.output)

    def test_skill_list_tag_case_insensitive(self):
        """Verify skill list --tag matching is case-insensitive (--tag PYTHON matches tags: [python])."""
        self.runner.invoke(main, ["skill", "add", str(self.skill_dir)])
        result = self.runner.invoke(main, ["skill", "list", "--tag", "PYTHON"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("test-skill", result.output)

    def test_skill_search_tag_case_insensitive(self):
        """Verify --tag matching is case-insensitive (--tag PYTHON matches tags: [python])."""
        self.runner.invoke(main, ["skill", "add", str(self.skill_dir)])
        result = self.runner.invoke(main, ["skill", "search", "python", "--tag", "PYTHON"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("test-skill", result.output)

    def test_skill_search_tag_no_match(self):
        """Verify tag filter with no matching tag shows no-match message."""
        self.runner.invoke(main, ["skill", "add", str(self.skill_dir)])
        result = self.runner.invoke(main, ["skill", "search", "python", "--tag", "database"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("No matching skills found", result.output)
        self.assertIn("Hint:", result.output)
        self.assertIn("database", result.output)

    def test_skill_search_env_compat(self):
        """Verify --env still filters search results (argument compatibility)."""
        self.runner.invoke(main, ["skill", "add", str(self.skill_dir), "--env", "prod"])
        result = self.runner.invoke(main, ["skill", "search", "python", "--env", "prod"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("test-skill", result.output)

        # A different environment must not match
        result = self.runner.invoke(main, ["skill", "search", "python", "--env", "staging"])
        self.assertIn("No matching skills found", result.output)

    def test_skill_search_tag_and_env_compat(self):
        """Verify --tag and --env combine with the keyword."""
        self.runner.invoke(main, ["skill", "add", str(self.skill_dir), "--env", "prod"])
        result = self.runner.invoke(
            main,
            ["skill", "search", "python", "--tag", "test", "--env", "prod"],
        )
        self.assertEqual(result.exit_code, 0)
        self.assertIn("test-skill", result.output)

    def test_skill_link_agent(self):
        """Verify skill link-agent binds skill to agent."""
        # First add the agent
        agent_file = Path(self.temp_dir.name) / "test-agent.md"
        agent_file.write_text("# Test Agent")
        self.runner.invoke(main, ["sub-agent", "add", str(agent_file)])
        self.runner.invoke(main, ["skill", "add", str(self.skill_dir)])

        result = self.runner.invoke(main, ["skill", "link-agent", "test-skill", "test-agent"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("test-skill", result.output)
        self.assertIn("test-agent", result.output)

    def test_skill_get_all(self):
        """Verify skill get-all copies all skills to .github/skills/."""
        self.runner.invoke(main, ["skill", "add", str(self.skill_dir)])

        github_skills = Path.cwd() / ".github" / "skills"
        github_skills.mkdir(parents=True, exist_ok=True)

        result = self.runner.invoke(main, ["skill", "get-all", "--force"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("1", result.output)
        self.assertTrue((github_skills / "test-skill" / "SKILL.md").exists())

    def test_skill_get_all_cursor_choice(self):
        """Verify --format cursor is a valid Choice (deploys .mdc rule)."""
        self.runner.invoke(main, ["skill", "add", str(self.skill_dir)])

        project_dir = Path(self.temp_dir.name) / "cursor-proj"
        project_dir.mkdir(parents=True)

        result = self.runner.invoke(
            main,
            [
                "skill",
                "get-all",
                "--format",
                "cursor",
                "--project-dir",
                str(project_dir),
                "--force",
            ],
        )
        self.assertEqual(result.exit_code, 0)
        self.assertTrue((project_dir / ".cursor" / "rules" / "test-skill.mdc").exists())

    def test_skill_get_all_invalid_format(self):
        """Verify an invalid --format value is rejected by the Choice."""
        result = self.runner.invoke(main, ["skill", "get-all", "--format", "bogus"])
        self.assertEqual(result.exit_code, 2)
        self.assertIn("Invalid value", result.output)

    def test_skill_remove_all(self):
        """Verify skill remove-all removes all skills."""
        self.runner.invoke(main, ["skill", "add", str(self.skill_dir)])

        result = self.runner.invoke(main, ["skill", "remove-all", "--force"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Removed", result.output)

        # remove-all only clears config (directory is preserved, but list reads from config)
        result = self.runner.invoke(main, ["skill", "list"])
        self.assertIn("No skills registered.", result.output)


class TestSkillAddRecCommand(unittest.TestCase):
    """Tests for the skill add-rec command."""

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

    def test_skill_add_rec(self):
        """Verify add-rec registers all skills in a directory."""
        src_dir = Path(self.temp_dir.name) / "skills_dir"
        src_dir.mkdir()
        skill1 = src_dir / "skill1"
        skill1.mkdir()
        (skill1 / "SKILL.md").write_text("---\nname: skill1\ntags: [test]\n---\n# Skill 1\n")
        skill2 = src_dir / "skill2"
        skill2.mkdir()
        (skill2 / "SKILL.md").write_text("---\nname: skill2\ntags: [test]\n---\n# Skill 2\n")

        result = self.runner.invoke(main, ["skill", "add-rec", str(src_dir)])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("2", result.output)

        result = self.runner.invoke(main, ["skill", "list"])
        self.assertIn("skill1", result.output)
        self.assertIn("skill2", result.output)

    def test_skill_add_rec_skips_unsafe_name(self):
        """Security: add-rec must skip a skill with path-traversal frontmatter name.

        The unsafe name (``../../evil``) is skipped with a message before any
        copy/delete, so nothing outside the store is written or removed.
        """
        src_dir = Path(self.temp_dir.name) / "skills_dir"
        src_dir.mkdir()
        skill1 = src_dir / "skill1"
        skill1.mkdir()
        (skill1 / "SKILL.md").write_text(
            "---\nname: skill1\ntags: [test]\n---\n# Skill 1\n",
            encoding="utf-8",
        )
        sneaky = src_dir / "sneaky"
        sneaky.mkdir()
        (sneaky / "SKILL.md").write_text(
            "---\nname: ../../evil\n---\n# Evil\n",
            encoding="utf-8",
        )

        # Decoy at exactly the path a traversal rmtree would target (~/evil).
        decoy = self.patch_home / "evil"
        decoy.mkdir()
        (decoy / "precious.txt").write_text("keep me\n")

        result = self.runner.invoke(main, ["skill", "add-rec", str(src_dir)])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("skip 'sneaky': invalid skill name", result.output)
        self.assertIn("Skills added: 1", result.output)

        # The escape target is untouched and nothing escaped the store.
        self.assertEqual((decoy / "precious.txt").read_text(), "keep me\n")
        skills_dir = self.patch_home / ".ai-adapter" / "skills"
        self.assertFalse((skills_dir / "evil").exists())

        # Only the safe skill is registered; the unsafe one is absent.
        import ai_adapter.config as cfg

        config = cfg.load_config()
        self.assertIsNotNone(config)
        skill_names = [s.name for s in config.skills] if config else []
        self.assertIn("skill1", skill_names)
        self.assertNotIn("../../evil", skill_names)


class TestSkillOpenClawExport(unittest.TestCase):
    """Tests for skill get-all --format openclaw."""

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

        # Create OpenClaw dir (simulate installed)
        self.openclaw_dir = self.patch_home / ".openclaw"
        self.openclaw_dir.mkdir(parents=True)

        # Create and register test skill
        self.skill_dir = Path(self.temp_dir.name) / "my-skill"
        self.skill_dir.mkdir(parents=True)
        (self.skill_dir / "SKILL.md").write_text("---\nname: my-skill\ndescription: My Test Skill\n---\n# My Skill\n")
        self.runner.invoke(main, ["skill", "add", str(self.skill_dir)])

        # Create a second skill to verify multiple
        self.skill_dir2 = Path(self.temp_dir.name) / "another-skill"
        self.skill_dir2.mkdir(parents=True)
        (self.skill_dir2 / "SKILL.md").write_text(
            "---\nname: another-skill\ndescription: Another Skill\ntags: [demo]\n---\n# Another\n"
        )
        self.runner.invoke(main, ["skill", "add", str(self.skill_dir2)])

        # Place an existing skill in OpenClaw (simulate pre-existing non-ai-adapter skill)
        self.existing_skill_dir = self.openclaw_dir / "skills" / "existing-skill"
        self.existing_skill_dir.mkdir(parents=True)
        (self.existing_skill_dir / "SKILL.md").write_text(
            "---\nname: existing-skill\ndescription: Pre-existing\n---\n# Existing\n"
        )

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

    def test_get_all_openclaw_basic(self):
        """Skills deployed to ~/.openclaw/skills/."""
        result = self.runner.invoke(
            main,
            [
                "skill",
                "get-all",
                "--format",
                "openclaw",
                "--force",
            ],
        )
        self.assertEqual(result.exit_code, 0)
        self.assertIn("(2) copied to", result.output)

        oc_skills = self.openclaw_dir / "skills"
        self.assertTrue((oc_skills / "my-skill" / "SKILL.md").exists())
        self.assertTrue((oc_skills / "another-skill" / "SKILL.md").exists())

    def test_get_all_openclaw_preserves_existing(self):
        """Non-ai-adapter skills in OpenClaw are preserved."""
        self.runner.invoke(
            main,
            [
                "skill",
                "get-all",
                "--format",
                "openclaw",
                "--force",
            ],
        )
        # existing-skill was placed before the deploy and should still be there
        oc_skills = self.openclaw_dir / "skills"
        self.assertTrue((oc_skills / "existing-skill" / "SKILL.md").exists())

    def test_get_all_openclaw_overwrites_managed(self):
        """Ai-adapter managed skill overwrites same-named skill in OpenClaw."""
        # Pre-place a skill with the same name as our managed one but different content
        preplaced = self.openclaw_dir / "skills" / "my-skill"
        preplaced.mkdir(parents=True, exist_ok=True)
        (preplaced / "SKILL.md").write_text("---\nname: old\n---\nOld content\n")

        self.runner.invoke(
            main,
            [
                "skill",
                "get-all",
                "--format",
                "openclaw",
                "--force",
            ],
        )
        # Should be overwritten with our version
        content = (self.openclaw_dir / "skills" / "my-skill" / "SKILL.md").read_text()
        self.assertIn("My Test Skill", content)
        self.assertNotIn("Old content", content)

    def test_get_all_openclaw_not_installed(self):
        """Warning when ~/.openclaw/ doesn't exist."""
        import shutil

        shutil.rmtree(self.openclaw_dir)

        result = self.runner.invoke(
            main,
            [
                "skill",
                "get-all",
                "--format",
                "openclaw",
                "--force",
            ],
        )
        # Should show warning but not error
        self.assertEqual(result.exit_code, 0)
        self.assertIn("No OpenClaw install detected", result.output)
        self.assertIn("Nothing was written", result.output)

    def test_get_all_standard_still_works(self):
        """--format standard (default) still deploys to .github/skills/."""
        result = self.runner.invoke(
            main,
            [
                "skill",
                "get-all",
                "--force",
            ],
        )
        self.assertEqual(result.exit_code, 0)
        self.assertTrue((Path.cwd() / ".github" / "skills" / "my-skill" / "SKILL.md").exists())

    def test_get_all_openclaw_no_skills(self):
        """Message when no skills registered."""
        # Remove all skills
        self.runner.invoke(main, ["skill", "remove-all", "--force", "--purge"])

        result = self.runner.invoke(
            main,
            [
                "skill",
                "get-all",
                "--format",
                "openclaw",
            ],
        )
        self.assertEqual(result.exit_code, 0)
        self.assertIn("No skills registered", result.output)

    def test_get_all_openclaw_force_prompt(self):
        """Without --force, prompt is shown for existing skills."""
        # Pre-place a skill
        preplaced = self.openclaw_dir / "skills" / "my-skill"
        preplaced.mkdir(parents=True, exist_ok=True)
        (preplaced / "SKILL.md").write_text("---\nname: old\n---\nOld\n")

        # Without --force, should abort on prompt (we pass 'n' via input)
        result = self.runner.invoke(
            main,
            ["skill", "get-all", "--format", "openclaw"],
            input="n\n",  # answer no to the prompt
        )
        self.assertNotEqual(result.exit_code, 0)
        # Content should remain old
        content = (self.openclaw_dir / "skills" / "my-skill" / "SKILL.md").read_text()
        self.assertIn("Old", content)


class TestSkillClaudeFormat(unittest.TestCase):
    """skill get-all --format claude (design 02 task 02-1)."""

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

        skill_dir = Path(self.temp_dir.name) / "test-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "---\nname: test-skill\ndescription: Test Skill\n---\n# Test Skill\n",
            encoding="utf-8",
        )
        self.runner.invoke(main, ["skill", "add", str(skill_dir)])

    def tearDown(self):
        import pathlib

        pathlib.Path.home = staticmethod(self._original_home)
        import ai_adapter.config as cfg

        cfg.AI_ADAPTER_DIR = Path.home() / ".ai-adapter"
        self.temp_dir.cleanup()

    def test_get_all_claude_project_scope(self):
        """--format claude deploys to <project>/.claude/skills/."""
        result = self.runner.invoke(
            main,
            ["skill", "get-all", "--format", "claude", "--project-dir", str(self.project_dir)],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertTrue((self.project_dir / ".claude" / "skills" / "test-skill" / "SKILL.md").exists())

    def test_get_all_claude_user_scope(self):
        """--scope user deploys to ~/.claude/skills/."""
        result = self.runner.invoke(
            main,
            ["skill", "get-all", "--format", "claude", "--scope", "user"],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertTrue((self.patch_home / ".claude" / "skills" / "test-skill" / "SKILL.md").exists())

    def test_get_all_claude_rejects_scope_user_with_standard(self):
        """--scope user is only valid with --format claude."""
        result = self.runner.invoke(
            main,
            ["skill", "get-all", "--format", "standard", "--scope", "user"],
        )
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("--scope user is only supported with --format claude", result.output)

    def test_get_all_claude_env_filter(self):
        """--env filtering works under --format claude (AC4)."""
        config = load_config()
        for s in config.skills:
            s.env = "prod"
        save_config(config)

        result = self.runner.invoke(
            main,
            [
                "skill",
                "get-all",
                "--format",
                "claude",
                "--env",
                "staging",
                "--project-dir",
                str(self.project_dir),
            ],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertFalse((self.project_dir / ".claude" / "skills" / "test-skill").exists())

    def test_get_all_claude_force_overwrites(self):
        """--force overwrites an existing skill directory without prompting."""
        dest = self.project_dir / ".claude" / "skills" / "test-skill"
        dest.mkdir(parents=True)
        (dest / "SKILL.md").write_text("old", encoding="utf-8")
        result = self.runner.invoke(
            main,
            [
                "skill",
                "get-all",
                "--format",
                "claude",
                "--force",
                "--project-dir",
                str(self.project_dir),
            ],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("name: test-skill", (dest / "SKILL.md").read_text(encoding="utf-8"))


class TestSkillInstall(unittest.TestCase):
    """Tests for ``ai-adapter skill install``."""

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

        # Create a local skill source directory (simulates bundled/installed skill)
        self.skill_source = Path(self.temp_dir.name) / "local-skill"
        self.skill_source.mkdir(parents=True)
        (self.skill_source / "SKILL.md").write_text(
            "---\nname: local-skill\ndescription: A local test skill\ntags: [test]\n---\n\n# Local Skill\n",
            encoding="utf-8",
        )

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

    def test_skill_install_local_cache(self):
        """Verify skill install copies from a local source directory."""
        from unittest.mock import patch

        with patch(
            "ai_adapter.profiles.resolve_skill_source",
            return_value=self.skill_source,
        ):
            result = self.runner.invoke(main, ["skill", "install", "local-skill"])

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("installed", result.output)

        # Verify the skill was copied to the store
        skills_dir = self.patch_home / ".ai-adapter" / "skills"
        self.assertTrue((skills_dir / "local-skill" / "SKILL.md").exists())

        # Verify the skill is registered in config
        from ai_adapter.config import load_config

        config = load_config()
        assert config is not None
        self.assertTrue(any(s.name == "local-skill" for s in config.skills))

    def test_skill_install_rejects_unsafe_name(self):
        """Security: install must reject path-traversal frontmatter names."""
        unsafe_source = Path(self.temp_dir.name) / "unsafe-install"
        unsafe_source.mkdir(parents=True)
        (unsafe_source / "SKILL.md").write_text(
            "---\nname: ../../evil\ndescription: sneaky\n---\n# Evil\n",
            encoding="utf-8",
        )

        from unittest.mock import patch

        with patch(
            "ai_adapter.profiles.resolve_skill_source",
            return_value=unsafe_source,
        ):
            result = self.runner.invoke(main, ["skill", "install", "evil"])

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Invalid skill name", result.output)

        # Nothing may be written inside the store or at the escape target
        skills_dir = self.patch_home / ".ai-adapter" / "skills"
        self.assertFalse((skills_dir / "evil").exists())
        self.assertFalse((self.patch_home / "evil").exists())

    def test_skill_install_validates_frontmatter(self):
        """Install aborts when SKILL.md has invalid frontmatter (missing description)."""
        bad_source = Path(self.temp_dir.name) / "bad-skill"
        bad_source.mkdir(parents=True)
        # Missing required 'description' field
        (bad_source / "SKILL.md").write_text(
            "---\nname: bad-skill\n---\n\n# Bad Skill\n",
            encoding="utf-8",
        )

        from unittest.mock import patch

        with patch(
            "ai_adapter.profiles.resolve_skill_source",
            return_value=bad_source,
        ):
            result = self.runner.invoke(main, ["skill", "install", "bad-skill"])

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("failed validation", result.output)

        # The dest directory should have been removed after validation failure
        skills_dir = self.patch_home / ".ai-adapter" / "skills"
        self.assertFalse((skills_dir / "bad-skill").exists())

    def test_skill_install_force_overwrites(self):
        """Verify --force overwrites an existing skill without prompting."""
        from unittest.mock import patch

        # First install
        with patch(
            "ai_adapter.profiles.resolve_skill_source",
            return_value=self.skill_source,
        ):
            result = self.runner.invoke(main, ["skill", "install", "local-skill"])
        self.assertEqual(result.exit_code, 0, result.output)

        # Modify the source
        (self.skill_source / "SKILL.md").write_text(
            "---\nname: local-skill\ndescription: Updated description\n---\n\n# Updated\n",
            encoding="utf-8",
        )

        # Second install with --force (no prompt)
        with patch(
            "ai_adapter.profiles.resolve_skill_source",
            return_value=self.skill_source,
        ):
            result = self.runner.invoke(main, ["skill", "install", "local-skill", "--force"])

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("installed", result.output)

        # Verify the content was updated
        skills_dir = self.patch_home / ".ai-adapter" / "skills"
        content = (skills_dir / "local-skill" / "SKILL.md").read_text()
        self.assertIn("Updated description", content)

    def test_skill_install_not_found_without_source(self):
        """Verify install fails when skill is not found and no --source given."""
        from unittest.mock import patch

        with patch(
            "ai_adapter.profiles.resolve_skill_source",
            return_value=None,
        ):
            result = self.runner.invoke(main, ["skill", "install", "nonexistent"])

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("not found", result.output)


class TestSkillCursorPlugin(unittest.TestCase):
    """skill get/get-all --format cursor-plugin (design 07 tasks 07-2/07-3)."""

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

        self.project_dir = Path(self.temp_dir.name) / "my-project"
        self.project_dir.mkdir(parents=True)

        skill_dir = Path(self.temp_dir.name) / "db-schema"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "---\nname: db-schema\ndescription: DB skill\n---\n# DB Schema\n",
            encoding="utf-8",
        )
        (skill_dir / "scripts").mkdir()
        (skill_dir / "scripts" / "query.sql").write_text("SELECT 1;\n", encoding="utf-8")
        self.runner.invoke(main, ["skill", "add", str(skill_dir)])

    def tearDown(self):
        import pathlib

        pathlib.Path.home = staticmethod(self._original_home)
        import ai_adapter.config as cfg

        cfg.AI_ADAPTER_DIR = Path.home() / ".ai-adapter"
        self.temp_dir.cleanup()

    @property
    def plugin_root(self):
        return self.patch_home / ".cursor" / "plugins" / "local" / "my-project"

    def test_skill_get_cursor_plugin_package(self):
        """AC1: skill get --format cursor-plugin builds a plugin package."""
        result = self.runner.invoke(
            main,
            [
                "skill",
                "get",
                "db-schema",
                "--format",
                "cursor-plugin",
                "--project-dir",
                str(self.project_dir),
            ],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertTrue((self.plugin_root / ".cursor-plugin" / "plugin.json").exists())
        self.assertTrue((self.plugin_root / "skills" / "db-schema" / "SKILL.md").exists())

    def test_skill_get_cursor_plugin_aux_files_copied(self):
        """Auxiliary files (scripts/) are copied into the package."""
        self.runner.invoke(
            main,
            [
                "skill",
                "get",
                "db-schema",
                "--format",
                "cursor-plugin",
                "--project-dir",
                str(self.project_dir),
            ],
        )
        self.assertTrue((self.plugin_root / "skills" / "db-schema" / "scripts" / "query.sql").exists())

    def test_skill_get_cursor_plugin_manifest_mandatory(self):
        """AC2: .cursor-plugin/plugin.json is always generated."""
        self.runner.invoke(
            main,
            [
                "skill",
                "get",
                "db-schema",
                "--format",
                "cursor-plugin",
                "--project-dir",
                str(self.project_dir),
            ],
        )
        import json

        data = json.loads((self.plugin_root / ".cursor-plugin" / "plugin.json").read_text())
        self.assertEqual(data["name"], "my-project")
        self.assertEqual(data["version"], "1.0.0")

    def test_skill_get_cursor_plugin_existing_prompts(self):
        """Existing plugin package prompts without --force."""
        invoke_args = [
            "skill",
            "get",
            "db-schema",
            "--format",
            "cursor-plugin",
            "--project-dir",
            str(self.project_dir),
        ]
        self.runner.invoke(main, invoke_args)
        result = self.runner.invoke(main, invoke_args, input="n\n")
        self.assertNotEqual(result.exit_code, 0)
        result2 = self.runner.invoke(main, invoke_args + ["--force"])
        self.assertEqual(result2.exit_code, 0, result2.output)

    def test_skill_get_all_cursor_plugin(self):
        """AC: skill get-all --format cursor-plugin installs every skill."""
        result = self.runner.invoke(
            main,
            [
                "skill",
                "get-all",
                "--format",
                "cursor-plugin",
                "--project-dir",
                str(self.project_dir),
                "--force",
            ],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertTrue((self.plugin_root / "skills" / "db-schema" / "SKILL.md").exists())
        self.assertTrue((self.plugin_root / ".cursor-plugin" / "plugin.json").exists())

    def test_skill_get_all_cursor_plugin_env_filter(self):
        """AC2 (task 07-3): --env filter works with cursor-plugin."""
        staging_dir = Path(self.temp_dir.name) / "staging-skill"
        staging_dir.mkdir()
        (staging_dir / "SKILL.md").write_text("---\nname: staging-skill\n---\n# S\n")
        self.runner.invoke(main, ["skill", "add", str(staging_dir), "--env", "staging"])

        prod_dir = Path(self.temp_dir.name) / "prod-skill"
        prod_dir.mkdir()
        (prod_dir / "SKILL.md").write_text("---\nname: prod-skill\n---\n# P\n")
        self.runner.invoke(main, ["skill", "add", str(prod_dir), "--env", "production"])

        result = self.runner.invoke(
            main,
            [
                "skill",
                "get-all",
                "--format",
                "cursor-plugin",
                "--env",
                "staging",
                "--project-dir",
                str(self.project_dir),
                "--force",
            ],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        skills_root = self.plugin_root / "skills"
        self.assertTrue((skills_root / "staging-skill").exists())
        self.assertFalse((skills_root / "prod-skill").exists())

    def test_skill_get_format_cursor_rules_unchanged(self):
        """AC4: --format cursor still deploys .cursor/rules/*.mdc."""
        result = self.runner.invoke(
            main,
            [
                "skill",
                "get",
                "db-schema",
                "--format",
                "cursor",
                "--project-dir",
                str(self.project_dir),
            ],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertTrue((self.project_dir / ".cursor" / "rules" / "db-schema.mdc").exists())
        self.assertFalse(self.plugin_root.exists())

    def test_skill_get_standard_default_unchanged(self):
        """Default format still copies to .github/skills/ (backward compat)."""
        result = self.runner.invoke(
            main,
            ["skill", "get", "db-schema", "--project-dir", str(self.project_dir)],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertTrue((self.project_dir / ".github" / "skills" / "db-schema" / "SKILL.md").exists())

    def test_skill_get_format_choices_shared_with_get_all(self):
        """AC5: skill get accepts the same --format choices as get-all."""
        result = self.runner.invoke(main, ["skill", "get", "--help"])
        self.assertIn("cursor-plugin", result.output)
        result_all = self.runner.invoke(main, ["skill", "get-all", "--help"])
        self.assertIn("cursor-plugin", result_all.output)
