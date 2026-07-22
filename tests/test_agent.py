"""agent.py のテスト。"""

import os
import tempfile
import unittest
from pathlib import Path

from click.testing import CliRunner

from ai_adapter.cli import main
from ai_adapter.config import init
from ai_adapter.models import Agent, Config, Env


class TestAgentAddRecCommand(unittest.TestCase):
    """agent add-rec コマンドのテスト。"""

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

    def test_agent_add_rec(self):
        """add-rec でディレクトリ内の全エージェントが登録されることを確認する。"""
        src_dir = Path(self.temp_dir.name) / "agents_dir"
        src_dir.mkdir()
        (src_dir / "agent1.md").write_text("# Agent 1")
        (src_dir / "agent2.md").write_text("# Agent 2")

        result = self.runner.invoke(main, ["agent", "add-rec", str(src_dir)])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("2", result.output)

        # list で確認
        result = self.runner.invoke(main, ["agent", "list"])
        self.assertIn("agent1", result.output)
        self.assertIn("agent2", result.output)


class TestAgentCommands(unittest.TestCase):
    """agent サブコマンドのテスト。"""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.patch_home = Path(self.temp_dir.name)
        self.runner = CliRunner()

        # Home 差し替え
        import pathlib
        self._original_home = pathlib.Path.home
        pathlib.Path.home = staticmethod(lambda: self.patch_home)

        import ai_adapter.config as cfg
        cfg.AI_ADAPTER_DIR = self.patch_home / ".ai-adapter"

        # init
        init()

        # テスト用エージェントファイル作成
        self.agent_file = Path(self.temp_dir.name) / "test-agent.md"
        self.agent_file.write_text("# Test Agent\nThis is a test agent.")

    def tearDown(self):
        import pathlib
        pathlib.Path.home = staticmethod(self._original_home)
        import ai_adapter.config as cfg
        cfg.AI_ADAPTER_DIR = Path.home() / ".ai-adapter"
        self.temp_dir.cleanup()

    def test_agent_list_empty(self):
        """エージェント未登録時に空メッセージが表示されることを確認する。"""
        result = self.runner.invoke(main, ["agent", "list"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("No agents registered.", result.output)

    def test_agent_add(self):
        """agent add でエージェントが追加されることを確認する。"""
        result = self.runner.invoke(main, ["agent", "add", str(self.agent_file)])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("test-agent", result.output)

        # ファイルがコピーされたか確認
        agents_dir = self.patch_home / ".ai-adapter" / "agents"
        self.assertTrue((agents_dir / "test-agent.md").exists())

    def test_agent_add_and_list(self):
        """agent add → agent list の流れを確認する。"""
        self.runner.invoke(main, ["agent", "add", str(self.agent_file)])
        result = self.runner.invoke(main, ["agent", "list"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("test-agent", result.output)

    def test_agent_get(self):
        """agent get で .github/agents/ にコピーされることを確認する。"""
        self.runner.invoke(main, ["agent", "add", str(self.agent_file)])

        # カレントディレクトリに .github/agents/ を作成（一時ディレクトリ内）
        github_agents = Path.cwd() / ".github" / "agents"
        github_agents.mkdir(parents=True, exist_ok=True)

        result = self.runner.invoke(main, ["agent", "get", "test-agent"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("test-agent.md", result.output)
        self.assertTrue((github_agents / "test-agent.md").exists())

        # クリーンアップ
        import shutil
        shutil.rmtree(Path.cwd() / ".github", ignore_errors=True)

    def test_agent_get_not_found(self):
        """存在しないエージェントの get でエラーになることを確認する。"""
        result = self.runner.invoke(main, ["agent", "get", "nonexistent"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("not found", result.output)

    def test_agent_get_force_overwrite(self):
        """agent get --force で確認なしで上書きされることを確認する。"""
        self.runner.invoke(main, ["agent", "add", str(self.agent_file)])

        github_dir = Path.cwd() / ".github" / "agents"
        github_dir.mkdir(parents=True, exist_ok=True)

        # 一回目の get
        result = self.runner.invoke(main, ["agent", "get", "test-agent"])
        self.assertEqual(result.exit_code, 0)

        # 二回目は --force で上書き
        result = self.runner.invoke(main, ["agent", "get", "test-agent", "--force"])
        self.assertEqual(result.exit_code, 0)
        self.assertTrue((github_dir / "test-agent.md").exists())

        import shutil
        shutil.rmtree(Path.cwd() / ".github", ignore_errors=True)

    def test_agent_get_with_project_dir(self):
        """agent get --project-dir で指定ディレクトリにコピーされることを確認する。"""
        self.runner.invoke(main, ["agent", "add", str(self.agent_file)])

        # 任意のプロジェクトディレクトリを作成
        project_dir = Path(self.temp_dir.name) / "my-project"
        project_dir.mkdir(parents=True)

        result = self.runner.invoke(main, [
            "agent", "get", "test-agent",
            "--project-dir", str(project_dir),
        ])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("test-agent.md", result.output)
        self.assertTrue((project_dir / ".github" / "agents" / "test-agent.md").exists())

    def test_agent_get_all(self):
        """agent get-all で全エージェントが .github/agents/ にコピーされることを確認する。"""
        agent1 = Path(self.temp_dir.name) / "agent1.md"
        agent1.write_text("# Agent 1")
        agent2 = Path(self.temp_dir.name) / "agent2.md"
        agent2.write_text("# Agent 2")
        self.runner.invoke(main, ["agent", "add", str(agent1)])
        self.runner.invoke(main, ["agent", "add", str(agent2)])

        github_agents = Path.cwd() / ".github" / "agents"
        github_agents.mkdir(parents=True, exist_ok=True)

        result = self.runner.invoke(main, ["agent", "get-all"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("2", result.output)
        self.assertTrue((github_agents / "agent1.md").exists())
        self.assertTrue((github_agents / "agent2.md").exists())

        import shutil
        shutil.rmtree(Path.cwd() / ".github", ignore_errors=True)

    def test_agent_remove(self):
        """agent remove でエージェントがremovされることを確認する。"""
        self.runner.invoke(main, ["agent", "add", str(self.agent_file)])
        result = self.runner.invoke(main, ["agent", "remove", "test-agent"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("test-agent", result.output)

        # list で表示されないことを確認
        result = self.runner.invoke(main, ["agent", "list"])
        self.assertIn("No agents registered.", result.output)

    def test_agent_remove_all(self):
        """agent remove-all で全エージェントがremovされることを確認する。"""
        # 2つのエージェントを追加
        agent1 = Path(self.temp_dir.name) / "agent1.md"
        agent1.write_text("# Agent 1")
        agent2 = Path(self.temp_dir.name) / "agent2.md"
        agent2.write_text("# Agent 2")
        self.runner.invoke(main, ["agent", "add", str(agent1)])
        self.runner.invoke(main, ["agent", "add", str(agent2)])

        result = self.runner.invoke(main, ["agent", "remove-all", "--force"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("All agents", result.output)

        # list で空になる
        result = self.runner.invoke(main, ["agent", "list"])
        self.assertIn("No agents registered.", result.output)

    def test_agent_add_agent_md_with_frontmatter(self):
        """.agent.md ファイル追加時に frontmatter の name が登録名になることを確認する。"""
        agent_md_file = Path(self.temp_dir.name) / "reviewer.agent.md"
        agent_md_file.write_text(
            "---\n"
            "name: Implementer\n"
            "description: 実装用エージェント\n"
            "---\n"
            "\n"
            "# Implementer\n"
            "This is an implementer agent.\n"
        )

        result = self.runner.invoke(main, ["agent", "add", str(agent_md_file)])
        self.assertEqual(result.exit_code, 0)
        # 登録名は "Implementer"（frontmatter の name）になる
        self.assertIn("'Implementer'", result.output)

        # list で "Implementer" と表示され、"reviewer" は表示されない
        result = self.runner.invoke(main, ["agent", "list"])
        self.assertIn("Implementer", result.output)
        self.assertNotIn("reviewer", result.output)

    def test_agent_add_agent_md_without_frontmatter_fails(self):
        """frontmatter がない .agent.md ファイルはエラーになることを確認する。"""
        bad_file = Path(self.temp_dir.name) / "bad.agent.md"
        bad_file.write_text("# Just a markdown\nNo frontmatter here.\n")

        result = self.runner.invoke(main, ["agent", "add", str(bad_file)])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("frontmatter", result.output)

    def test_agent_add_agent_md_without_name_fails(self):
        """frontmatter に name がない .agent.md ファイルはエラーになることを確認する。"""
        bad_file = Path(self.temp_dir.name) / "bad.agent.md"
        bad_file.write_text(
            "---\n"
            "description: no name here\n"
            "---\n"
            "# Bad\n"
        )

        result = self.runner.invoke(main, ["agent", "add", str(bad_file)])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("name", result.output)

    def test_agent_get_agent_md_backward_compat(self):
        """.agent.md で登録したエージェントを短い名前で取得できることを確認する。"""
        agent_md_file = Path(self.temp_dir.name) / "reviewer.agent.md"
        agent_md_file.write_text(
            "---\n"
            "name: Implementer\n"
            "---\n"
            "# Implementer\n"
        )
        self.runner.invoke(main, ["agent", "add", str(agent_md_file)])

        github_agents = Path.cwd() / ".github" / "agents"
        github_agents.mkdir(parents=True, exist_ok=True)

        # "Implementer" で取得できる
        result = self.runner.invoke(main, ["agent", "get", "Implementer"])
        self.assertEqual(result.exit_code, 0)
        self.assertTrue((github_agents / "reviewer.agent.md").exists())

        import shutil
        shutil.rmtree(Path.cwd() / ".github", ignore_errors=True)

    def test_agent_get_with_dot_agent_suffix(self):
        """後方互換性: .agent 付きの名前でも取得できることを確認する。"""
        agent_md_file = Path(self.temp_dir.name) / "reviewer.agent.md"
        agent_md_file.write_text(
            "---\n"
            "name: Implementer\n"
            "---\n"
            "# Implementer\n"
        )
        self.runner.invoke(main, ["agent", "add", str(agent_md_file)])

        github_agents = Path.cwd() / ".github" / "agents"
        github_agents.mkdir(parents=True, exist_ok=True)

        # "reviewer.agent" でも取得できる（後方互換性）
        result = self.runner.invoke(main, ["agent", "get", "reviewer.agent"])
        self.assertEqual(result.exit_code, 0)
        self.assertTrue((github_agents / "reviewer.agent.md").exists())

        import shutil
        shutil.rmtree(Path.cwd() / ".github", ignore_errors=True)
