"""Tests for skill.py."""

import tempfile
import unittest
from pathlib import Path

from click.testing import CliRunner

from ai_adapter.cli import main
from ai_adapter.config import init


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

        import shutil
        shutil.rmtree(Path.cwd() / ".github", ignore_errors=True)

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

        result = self.runner.invoke(main, [
            "skill", "get", "test-skill",
            "--project-dir", str(project_dir),
            "--force",
        ])
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
        """Verify skill search shows message when no match."""
        self.runner.invoke(main, ["skill", "add", str(self.skill_dir)])
        result = self.runner.invoke(main, ["skill", "search", "nonexistent"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("No skills matching", result.output)

    def test_skill_link_agent(self):
        """Verify skill link-agent binds skill to agent."""
        # First add the agent
        agent_file = Path(self.temp_dir.name) / "test-agent.md"
        agent_file.write_text("# Test Agent")
        self.runner.invoke(main, ["agent", "add", str(agent_file)])
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

        import shutil
        shutil.rmtree(Path.cwd() / ".github", ignore_errors=True)

    def test_skill_remove_all(self):
        """Verify skill remove-all removes all skills."""
        self.runner.invoke(main, ["skill", "add", str(self.skill_dir)])

        result = self.runner.invoke(main, ["skill", "remove-all", "--force"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("All skills", result.output)

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
        (skill1 / "SKILL.md").write_text(
            "---\nname: skill1\ntags: [test]\n---\n# Skill 1\n"
        )
        skill2 = src_dir / "skill2"
        skill2.mkdir()
        (skill2 / "SKILL.md").write_text(
            "---\nname: skill2\ntags: [test]\n---\n# Skill 2\n"
        )

        result = self.runner.invoke(main, ["skill", "add-rec", str(src_dir)])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("2", result.output)

        result = self.runner.invoke(main, ["skill", "list"])
        self.assertIn("skill1", result.output)
        self.assertIn("skill2", result.output)


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

        # Create OpenClaw dir (simulate installed)
        self.openclaw_dir = self.patch_home / ".openclaw"
        self.openclaw_dir.mkdir(parents=True)

        # Create and register test skill
        self.skill_dir = Path(self.temp_dir.name) / "my-skill"
        self.skill_dir.mkdir(parents=True)
        (self.skill_dir / "SKILL.md").write_text(
            "---\nname: my-skill\ndescription: My Test Skill\n---\n# My Skill\n"
        )
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
        self.temp_dir.cleanup()

    def test_get_all_openclaw_basic(self):
        """Skills deployed to ~/.openclaw/skills/."""
        result = self.runner.invoke(main, [
            "skill", "get-all", "--format", "openclaw", "--force",
        ])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("(2) copied to", result.output)

        oc_skills = self.openclaw_dir / "skills"
        self.assertTrue((oc_skills / "my-skill" / "SKILL.md").exists())
        self.assertTrue((oc_skills / "another-skill" / "SKILL.md").exists())

    def test_get_all_openclaw_preserves_existing(self):
        """Non-ai-adapter skills in OpenClaw are preserved."""
        self.runner.invoke(main, [
            "skill", "get-all", "--format", "openclaw", "--force",
        ])
        # existing-skill was placed before the deploy and should still be there
        oc_skills = self.openclaw_dir / "skills"
        self.assertTrue((oc_skills / "existing-skill" / "SKILL.md").exists())

    def test_get_all_openclaw_overwrites_managed(self):
        """Ai-adapter managed skill overwrites same-named skill in OpenClaw."""
        # Pre-place a skill with the same name as our managed one but different content
        preplaced = self.openclaw_dir / "skills" / "my-skill"
        preplaced.mkdir(parents=True, exist_ok=True)
        (preplaced / "SKILL.md").write_text("---\nname: old\n---\nOld content\n")

        self.runner.invoke(main, [
            "skill", "get-all", "--format", "openclaw", "--force",
        ])
        # Should be overwritten with our version
        content = (self.openclaw_dir / "skills" / "my-skill" / "SKILL.md").read_text()
        self.assertIn("My Test Skill", content)
        self.assertNotIn("Old content", content)

    def test_get_all_openclaw_not_installed(self):
        """Warning when ~/.openclaw/ doesn't exist."""
        import shutil
        shutil.rmtree(self.openclaw_dir)

        result = self.runner.invoke(main, [
            "skill", "get-all", "--format", "openclaw", "--force",
        ])
        # Should show warning but not error
        self.assertEqual(result.exit_code, 0)
        self.assertIn("No OpenClaw install detected", result.output)
        self.assertIn("Nothing was written", result.output)

    def test_get_all_standard_still_works(self):
        """--format standard (default) still deploys to .github/skills/."""
        result = self.runner.invoke(main, [
            "skill", "get-all", "--force",
        ])
        self.assertEqual(result.exit_code, 0)
        self.assertTrue((Path.cwd() / ".github" / "skills" / "my-skill" / "SKILL.md").exists())

        import shutil
        shutil.rmtree(Path.cwd() / ".github", ignore_errors=True)

    def test_get_all_openclaw_no_skills(self):
        """Message when no skills registered."""
        # Remove all skills
        self.runner.invoke(main, ["skill", "remove-all", "--force", "--purge"])

        result = self.runner.invoke(main, [
            "skill", "get-all", "--format", "openclaw",
        ])
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
