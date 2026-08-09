"""Tests for --env support across skill, command, prompt, and sub-agent commands."""

import tempfile
import unittest
from pathlib import Path

from click.testing import CliRunner

from ai_adapter.cli import main
from ai_adapter.config import init


class TestSkillEnv(unittest.TestCase):
    """Tests for skill --env support."""

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

        # Create test skill directories
        self.skill_dir_a = Path(self.temp_dir.name) / "skill-a"
        self.skill_dir_a.mkdir(parents=True)
        (self.skill_dir_a / "SKILL.md").write_text("---\nname: skill-a\ndescription: Skill A\n---\n# Skill A\n")

        self.skill_dir_b = Path(self.temp_dir.name) / "skill-b"
        self.skill_dir_b.mkdir(parents=True)
        (self.skill_dir_b / "SKILL.md").write_text("---\nname: skill-b\ndescription: Skill B\n---\n# Skill B\n")

    def tearDown(self):
        import pathlib

        pathlib.Path.home = staticmethod(self._original_home)
        import ai_adapter.config as cfg

        cfg.AI_ADAPTER_DIR = Path.home() / ".ai-adapter"
        self.temp_dir.cleanup()

    def test_skill_add_with_env(self):
        """Verify skill add --env assigns env to skill."""
        result = self.runner.invoke(main, ["skill", "add", str(self.skill_dir_a), "--env", "production"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("production", result.output)

        result = self.runner.invoke(main, ["skill", "list"])
        self.assertIn("[production]", result.output)

    def test_skill_list_filter_by_env(self):
        """Verify skill list --env filters skills."""
        self.runner.invoke(main, ["skill", "add", str(self.skill_dir_a), "--env", "production"])
        self.runner.invoke(main, ["skill", "add", str(self.skill_dir_b), "--env", "staging"])

        result = self.runner.invoke(main, ["skill", "list", "--env", "production"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("skill-a", result.output)
        self.assertNotIn("skill-b", result.output)

    def test_skill_get_all_filter_by_env(self):
        """Verify skill get-all --env filters deployment."""
        self.runner.invoke(main, ["skill", "add", str(self.skill_dir_a), "--env", "production"])
        self.runner.invoke(main, ["skill", "add", str(self.skill_dir_b), "--env", "staging"])

        github_skills = Path.cwd() / ".github" / "skills"
        github_skills.mkdir(parents=True, exist_ok=True)

        result = self.runner.invoke(main, ["skill", "get-all", "--env", "production", "--force"])
        self.assertEqual(result.exit_code, 0)
        self.assertTrue((github_skills / "skill-a" / "SKILL.md").exists())
        self.assertFalse((github_skills / "skill-b" / "SKILL.md").exists())

    def test_skill_remove_all_filter_by_env(self):
        """Verify skill remove-all --env removes only matching skills."""
        self.runner.invoke(main, ["skill", "add", str(self.skill_dir_a), "--env", "production"])
        self.runner.invoke(main, ["skill", "add", str(self.skill_dir_b), "--env", "staging"])

        result = self.runner.invoke(main, ["skill", "remove-all", "--env", "production", "--force"])
        self.assertEqual(result.exit_code, 0)

        result = self.runner.invoke(main, ["skill", "list"])
        self.assertNotIn("skill-a", result.output)
        self.assertIn("skill-b", result.output)

    def test_skill_add_rec_with_env(self):
        """Verify skill add-rec --env assigns env to all skills."""
        src_dir = Path(self.temp_dir.name) / "skills_bulk"
        src_dir.mkdir()
        (src_dir / "s1").mkdir()
        (src_dir / "s1" / "SKILL.md").write_text("---\nname: s1\n---\n")
        (src_dir / "s2").mkdir()
        (src_dir / "s2" / "SKILL.md").write_text("---\nname: s2\n---\n")

        result = self.runner.invoke(main, ["skill", "add-rec", str(src_dir), "--env", "dev"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("2", result.output)

        result = self.runner.invoke(main, ["skill", "list", "--env", "dev"])
        self.assertIn("s1", result.output)
        self.assertIn("s2", result.output)


class TestCommandEnv(unittest.TestCase):
    """Tests for command --env support."""

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

        self.cmd_file = Path(self.temp_dir.name) / "deploy.sh"
        self.cmd_file.write_text("#!/bin/bash\necho deploy\n")

        self.cmd_file2 = Path(self.temp_dir.name) / "build.sh"
        self.cmd_file2.write_text("#!/bin/bash\necho build\n")

    def tearDown(self):
        import pathlib

        pathlib.Path.home = staticmethod(self._original_home)
        import ai_adapter.config as cfg

        cfg.AI_ADAPTER_DIR = Path.home() / ".ai-adapter"
        self.temp_dir.cleanup()

    def test_command_add_with_env(self):
        """Verify command add --env assigns env."""
        result = self.runner.invoke(main, ["command", "add", str(self.cmd_file), "--env", "prod"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("prod", result.output)

    def test_command_list_filter_by_env(self):
        """Verify command list --env filters commands."""
        self.runner.invoke(main, ["command", "add", str(self.cmd_file), "--env", "prod"])
        self.runner.invoke(main, ["command", "add", str(self.cmd_file2), "--env", "dev"])

        result = self.runner.invoke(main, ["command", "list", "--env", "prod"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("deploy", result.output)
        self.assertNotIn("build", result.output)

    def test_command_remove_all_filter_by_env(self):
        """Verify command remove-all --env removes only matching."""
        self.runner.invoke(main, ["command", "add", str(self.cmd_file), "--env", "prod"])
        self.runner.invoke(main, ["command", "add", str(self.cmd_file2), "--env", "dev"])

        result = self.runner.invoke(main, ["command", "remove-all", "--env", "prod", "--force"])
        self.assertEqual(result.exit_code, 0)

        result = self.runner.invoke(main, ["command", "list"])
        self.assertNotIn("deploy", result.output)
        self.assertIn("build", result.output)


class TestPromptEnv(unittest.TestCase):
    """Tests for prompt --env support."""

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

        self.prompt_file = Path(self.temp_dir.name) / "review.md"
        self.prompt_file.write_text("Review checklist\n")

        self.prompt_file2 = Path(self.temp_dir.name) / "summary.md"
        self.prompt_file2.write_text("Summary template\n")

    def tearDown(self):
        import pathlib

        pathlib.Path.home = staticmethod(self._original_home)
        import ai_adapter.config as cfg

        cfg.AI_ADAPTER_DIR = Path.home() / ".ai-adapter"
        self.temp_dir.cleanup()

    def test_prompt_add_with_env(self):
        """Verify prompt add --env assigns env."""
        result = self.runner.invoke(main, ["prompt", "add", str(self.prompt_file), "--env", "staging"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("staging", result.output)

    def test_prompt_list_filter_by_env(self):
        """Verify prompt list --env filters prompts."""
        self.runner.invoke(main, ["prompt", "add", str(self.prompt_file), "--env", "prod"])
        self.runner.invoke(main, ["prompt", "add", str(self.prompt_file2), "--env", "dev"])

        result = self.runner.invoke(main, ["prompt", "list", "--env", "prod"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("review", result.output)
        self.assertNotIn("summary", result.output)

    def test_prompt_remove_all_filter_by_env(self):
        """Verify prompt remove-all --env removes only matching."""
        self.runner.invoke(main, ["prompt", "add", str(self.prompt_file), "--env", "prod"])
        self.runner.invoke(main, ["prompt", "add", str(self.prompt_file2), "--env", "dev"])

        result = self.runner.invoke(main, ["prompt", "remove-all", "--env", "prod", "--force"])
        self.assertEqual(result.exit_code, 0)

        result = self.runner.invoke(main, ["prompt", "list"])
        self.assertNotIn("review", result.output)
        self.assertIn("summary", result.output)


class TestAgentEnv(unittest.TestCase):
    """Tests for sub-agent --env support."""

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

        self.agent_file = Path(self.temp_dir.name) / "reviewer.md"
        self.agent_file.write_text("# Reviewer\n")

        self.agent_file2 = Path(self.temp_dir.name) / "coder.md"
        self.agent_file2.write_text("# Coder\n")

    def tearDown(self):
        import pathlib

        pathlib.Path.home = staticmethod(self._original_home)
        import ai_adapter.config as cfg

        cfg.AI_ADAPTER_DIR = Path.home() / ".ai-adapter"
        self.temp_dir.cleanup()

    def test_agent_add_with_env(self):
        """Verify sub-agent add --env creates binding."""
        result = self.runner.invoke(main, ["sub-agent", "add", str(self.agent_file), "--env", "prod"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("bound to env", result.output)

    def test_agent_list_filter_by_env(self):
        """Verify sub-agent list --env filters by binding."""
        self.runner.invoke(main, ["sub-agent", "add", str(self.agent_file), "--env", "prod"])
        self.runner.invoke(main, ["sub-agent", "add", str(self.agent_file2), "--env", "dev"])

        result = self.runner.invoke(main, ["sub-agent", "list", "--env", "prod"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("reviewer", result.output)
        self.assertNotIn("coder", result.output)

    def test_agent_remove_env_binding(self):
        """Verify sub-agent remove --env only removes binding."""
        self.runner.invoke(main, ["sub-agent", "add", str(self.agent_file), "--env", "prod"])
        self.runner.invoke(main, ["sub-agent", "add", str(self.agent_file), "--env", "dev"])

        # Remove only prod binding
        result = self.runner.invoke(main, ["sub-agent", "remove", "reviewer", "--env", "prod"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("unbound from env", result.output)

        # Agent should still exist with dev binding
        result = self.runner.invoke(main, ["sub-agent", "list"])
        self.assertIn("reviewer", result.output)

        # But not in prod anymore
        result = self.runner.invoke(main, ["sub-agent", "list", "--env", "prod"])
        self.assertNotIn("reviewer", result.output)

    def test_agent_get_all_filter_by_env(self):
        """Verify sub-agent get-all --env filters by binding."""
        self.runner.invoke(main, ["sub-agent", "add", str(self.agent_file), "--env", "prod"])
        self.runner.invoke(main, ["sub-agent", "add", str(self.agent_file2), "--env", "dev"])

        github_agents = Path.cwd() / ".github" / "agents"
        github_agents.mkdir(parents=True, exist_ok=True)

        result = self.runner.invoke(main, ["sub-agent", "get-all", "--env", "prod"])
        self.assertEqual(result.exit_code, 0)
        self.assertTrue((github_agents / "reviewer.md").exists())
        self.assertFalse((github_agents / "coder.md").exists())

    def test_agent_add_rec_with_env(self):
        """Verify sub-agent add-rec --env creates bindings."""
        src_dir = Path(self.temp_dir.name) / "agents_bulk"
        src_dir.mkdir()
        (src_dir / "a1.md").write_text("# Agent 1")
        (src_dir / "a2.md").write_text("# Agent 2")

        result = self.runner.invoke(main, ["sub-agent", "add-rec", str(src_dir), "--env", "staging"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("2", result.output)

        result = self.runner.invoke(main, ["sub-agent", "list", "--env", "staging"])
        self.assertIn("a1", result.output)
        self.assertIn("a2", result.output)


class TestModelEnvField(unittest.TestCase):
    """Tests for model env field serialization."""

    def test_skill_env_serialization(self):
        """Verify Skill env field is serialized/deserialized."""
        from ai_adapter.models import Skill

        skill = Skill(name="test", env="production")
        d = skill.to_dict()
        self.assertEqual(d["env"], "production")

        restored = Skill.from_dict(d)
        self.assertEqual(restored.env, "production")

    def test_skill_env_none_not_serialized(self):
        """Verify Skill env=None is not serialized."""
        from ai_adapter.models import Skill

        skill = Skill(name="test")
        d = skill.to_dict()
        self.assertNotIn("env", d)

    def test_command_env_serialization(self):
        """Verify Command env field is serialized/deserialized."""
        from ai_adapter.models import Command

        cmd = Command(name="test", env="staging")
        d = cmd.to_dict()
        self.assertEqual(d["env"], "staging")

        restored = Command.from_dict(d)
        self.assertEqual(restored.env, "staging")

    def test_prompt_env_serialization(self):
        """Verify Prompt env field is serialized/deserialized."""
        from ai_adapter.models import Prompt

        prompt = Prompt(name="test", env="dev")
        d = prompt.to_dict()
        self.assertEqual(d["env"], "dev")

        restored = Prompt.from_dict(d)
        self.assertEqual(restored.env, "dev")

    def test_instruction_env_serialization(self):
        """Verify Instruction env field is serialized/deserialized."""
        from ai_adapter.models import Instruction

        inst = Instruction(name="test", env="prod")
        d = inst.to_dict()
        self.assertEqual(d["env"], "prod")

        restored = Instruction.from_dict(d)
        self.assertEqual(restored.env, "prod")

    def test_config_backward_compatibility(self):
        """Verify config without env fields still loads correctly."""
        from ai_adapter.models import Config

        data = {
            "version": 1,
            "default_env": "default",
            "skills": [{"name": "old-skill"}],
            "commands": [{"name": "old-cmd"}],
            "prompts": [{"name": "old-prompt"}],
        }
        config = Config.from_dict(data)
        self.assertEqual(config.skills[0].env, None)
        self.assertEqual(config.commands[0].env, None)
        self.assertEqual(config.prompts[0].env, None)


if __name__ == "__main__":
    unittest.main()
