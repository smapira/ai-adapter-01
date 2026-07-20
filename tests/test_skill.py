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
        self.assertIn("登録済みのスキルはありません", result.output)

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
        self.assertIn("見つかりません", result.output)

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
        """skill remove でスキルが削除されることを確認する。"""
        self.runner.invoke(main, ["skill", "add", str(self.skill_dir)])
        result = self.runner.invoke(main, ["skill", "remove", "test-skill"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("test-skill", result.output)

        # list で表示されないことを確認
        result = self.runner.invoke(main, ["skill", "list"])
        self.assertIn("登録済みのスキルはありません", result.output)

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
        self.assertIn("一致するスキルはありません", result.output)

    def test_skill_link_agent(self):
        """skill link-agent でスキルとエージェントが紐付けられることを確認する。"""
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
        self.assertIn("1件", result.output)
        self.assertTrue((github_skills / "test-skill" / "SKILL.md").exists())

        import shutil
        shutil.rmtree(Path.cwd() / ".github", ignore_errors=True)

    def test_skill_remove_all(self):
        """skill remove-all で全スキルが削除されることを確認する。"""
        self.runner.invoke(main, ["skill", "add", str(self.skill_dir)])

        result = self.runner.invoke(main, ["skill", "remove-all", "--force"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("全てのスキル", result.output)

        # list で空になる
        result = self.runner.invoke(main, ["skill", "list"])
        self.assertIn("登録済みのスキルはありません", result.output)
