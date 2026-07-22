"""skill.py のテスト。"""

import tempfile
import unittest
from pathlib import Path

from click.testing import CliRunner

from ai_adapter.cli import main
from ai_adapter.config import init


class TestSkillCommands(unittest.TestCase):
    """skill サブコマンドのテスト。"""

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

        # テスト用スキルディレクトリ作成
        self.skill_dir = Path(self.temp_dir.name) / "test-skill"
        self.skill_dir.mkdir(parents=True)
        skill_md = self.skill_dir / "SKILL.md"
        skill_md.write_text(
            "---\n"
            "name: test-skill\n"
            "description: テスト用スキル\n"
            "tags: [test, python]\n"
            "---\n"
            "\n"
            "# Test Skill\n"
            "テスト用スキルです。\n"
        )

    def tearDown(self):
        import pathlib
        pathlib.Path.home = staticmethod(self._original_home)
        import ai_adapter.config as cfg
        cfg.AI_ADAPTER_DIR = Path.home() / ".ai-adapter"
        self.temp_dir.cleanup()

    def test_skill_list_empty(self):
        """スキル未登録時に空メッセージが表示されることを確認する。"""
        result = self.runner.invoke(main, ["skill", "list"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("No skills registered.", result.output)

    def test_skill_add(self):
        """skill add でスキルが追加されることを確認する。"""
        result = self.runner.invoke(main, ["skill", "add", str(self.skill_dir)])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("test-skill", result.output)

        skills_dir = self.patch_home / ".ai-adapter" / "skills"
        self.assertTrue((skills_dir / "test-skill" / "SKILL.md").exists())

    def test_skill_add_and_list(self):
        """skill add → skill list の流れを確認する。"""
        self.runner.invoke(main, ["skill", "add", str(self.skill_dir)])
        result = self.runner.invoke(main, ["skill", "list"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("test-skill", result.output)

    def test_skill_get(self):
        """skill get で .github/skills/ にコピーされることを確認する。"""
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
        """存在しないスキルの get でエラーになることを確認する。"""
        result = self.runner.invoke(main, ["skill", "get", "nonexistent"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("not found", result.output)

    def test_skill_get_with_project_dir(self):
        """skill get --project-dir で指定ディレクトリにコピーされることを確認する。"""
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
        """skill remove でスキルがremovされることを確認する。"""
        self.runner.invoke(main, ["skill", "add", str(self.skill_dir)])
        result = self.runner.invoke(main, ["skill", "remove", "test-skill"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("test-skill", result.output)

        # list で表示されないことを確認
        result = self.runner.invoke(main, ["skill", "list"])
        self.assertIn("No skills registered.", result.output)

    def test_skill_search(self):
        """skill search でスキルが検索できることを確認する。"""
        self.runner.invoke(main, ["skill", "add", str(self.skill_dir)])
        result = self.runner.invoke(main, ["skill", "search", "python"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("test-skill", result.output)

    def test_skill_search_no_match(self):
        """skill search で一致しない場合のメッセージを確認する。"""
        self.runner.invoke(main, ["skill", "add", str(self.skill_dir)])
        result = self.runner.invoke(main, ["skill", "search", "nonexistent"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("No skills matching", result.output)

    def test_skill_link_agent(self):
        """skill link-agent でスキルとエージェントがbindられることを確認する。"""
        # 先にエージェントを追加
        agent_file = Path(self.temp_dir.name) / "test-agent.md"
        agent_file.write_text("# Test Agent")
        self.runner.invoke(main, ["agent", "add", str(agent_file)])
        self.runner.invoke(main, ["skill", "add", str(self.skill_dir)])

        result = self.runner.invoke(main, ["skill", "link-agent", "test-skill", "test-agent"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("test-skill", result.output)
        self.assertIn("test-agent", result.output)

    def test_skill_get_all(self):
        """skill get-all で全スキルが .github/skills/ にコピーされることを確認する。"""
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
        """skill remove-all で全スキルがremovされることを確認する。"""
        self.runner.invoke(main, ["skill", "add", str(self.skill_dir)])

        result = self.runner.invoke(main, ["skill", "remove-all", "--force"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("All skills", result.output)

        # remove-all は config のみ解除（ディレクトリは保持されるが list は config 参照）
        result = self.runner.invoke(main, ["skill", "list"])
        self.assertIn("No skills registered.", result.output)


class TestSkillAddRecCommand(unittest.TestCase):
    """skill add-rec コマンドのテスト。"""

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
        """add-rec でディレクトリ内の全スキルが登録されることを確認する。"""
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
