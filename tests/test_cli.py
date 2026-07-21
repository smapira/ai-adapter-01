"""CLI 統合テスト。"""

import json
import tempfile
import unittest
from pathlib import Path

from unittest.mock import patch, MagicMock

from click.testing import CliRunner

from ai_adapter.cli import main
from ai_adapter.git import GitError


class TestCLIIntegration(unittest.TestCase):
    """CLI 全体の統合テスト。"""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.patch_home = Path(self.temp_dir.name)
        self.runner = CliRunner()

        import pathlib
        self._original_home = pathlib.Path.home
        pathlib.Path.home = staticmethod(lambda: self.patch_home)

        import ai_adapter.config as cfg
        cfg.AI_ADAPTER_DIR = self.patch_home / ".ai-adapter"

    def tearDown(self):
        import pathlib
        pathlib.Path.home = staticmethod(self._original_home)
        import ai_adapter.config as cfg
        cfg.AI_ADAPTER_DIR = Path.home() / ".ai-adapter"
        self.temp_dir.cleanup()

    def test_help(self):
        """--help が正常に表示されることを確認する。"""
        result = self.runner.invoke(main, ["--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("ai-adapter", result.output)
        self.assertIn("init", result.output)
        self.assertIn("status", result.output)
        self.assertIn("agent", result.output)
        self.assertIn("env", result.output)
        self.assertIn("bin", result.output)
        self.assertIn("skill", result.output)
        self.assertIn("mcp", result.output)
        self.assertIn("opencode", result.output)
        self.assertIn("add-all-rec", result.output)
        self.assertIn("sync", result.output)
        self.assertIn("uninstall", result.output)
        self.assertIn("start", result.output)

    def test_version(self):
        """--version が表示されることを確認する。"""
        from ai_adapter import __version__
        result = self.runner.invoke(main, ["--version"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn(__version__, result.output)

    def test_init_and_status(self):
        """init → status の流れを確認する。"""
        # init (空 Enter でリモート入力をスキップ)
        result = self.runner.invoke(main, ["init"], input="\n")
        self.assertEqual(result.exit_code, 0)
        self.assertIn("初期化", result.output)

        # status
        result = self.runner.invoke(main, ["status"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("状態", result.output)
        self.assertIn("default", result.output)

    def test_init_with_remote(self):
        """init --remote でリモートが設定されることを確認する。"""
        result = self.runner.invoke(main, [
            "init", "--remote", "git@github.com:user/test.git",
        ])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("リモートを設定しました", result.output)
        self.assertIn("git@github.com:user/test.git", result.output)

    def test_status_before_init(self):
        """init 前の status で適切なメッセージが表示されることを確認する。"""
        result = self.runner.invoke(main, ["status"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("初期化されていません", result.output)

    def test_agent_help(self):
        """agent --help が表示されることを確認する。"""
        result = self.runner.invoke(main, ["agent", "--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("list", result.output)
        self.assertIn("add", result.output)
        self.assertIn("get", result.output)
        self.assertIn("remove", result.output)

    def test_env_help(self):
        """env --help が表示されることを確認する。"""
        result = self.runner.invoke(main, ["env", "--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("list", result.output)
        self.assertIn("add", result.output)
        self.assertIn("remove", result.output)
        self.assertIn("default", result.output)
        self.assertIn("set-default", result.output)
        self.assertIn("link-agent", result.output)
        self.assertIn("unlink-agent", result.output)

    def test_bin_help(self):
        """bin --help が表示されることを確認する。"""
        result = self.runner.invoke(main, ["bin", "--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("list", result.output)
        self.assertIn("add", result.output)
        self.assertIn("get", result.output)
        self.assertIn("remove", result.output)

    def test_skill_help(self):
        """skill --help が表示されることを確認する。"""
        result = self.runner.invoke(main, ["skill", "--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("list", result.output)
        self.assertIn("add", result.output)
        self.assertIn("get", result.output)
        self.assertIn("remove", result.output)
        self.assertIn("search", result.output)
        self.assertIn("link-agent", result.output)

    def test_mcp_help(self):
        """mcp --help が表示されることを確認する。"""
        result = self.runner.invoke(main, ["mcp", "--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("list", result.output)
        self.assertIn("add", result.output)
        self.assertIn("remove", result.output)
        self.assertIn("export", result.output)
        self.assertIn("load", result.output)
        self.assertIn("remove-all", result.output)

    def test_opencode_help(self):
        """opencode --help が表示されることを確認する。"""
        result = self.runner.invoke(main, ["opencode", "--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("alias", result.output)
        self.assertIn("install", result.output)
        self.assertIn("uninstall", result.output)


class TestUninstallCommand(unittest.TestCase):
    """uninstall コマンドのテスト。"""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.patch_home = Path(self.temp_dir.name)
        self.runner = CliRunner()

        import pathlib
        self._original_home = pathlib.Path.home
        pathlib.Path.home = staticmethod(lambda: self.patch_home)

        import ai_adapter.config as cfg
        cfg.AI_ADAPTER_DIR = self.patch_home / ".ai-adapter"

    def tearDown(self):
        import pathlib
        pathlib.Path.home = staticmethod(self._original_home)
        import ai_adapter.config as cfg
        cfg.AI_ADAPTER_DIR = Path.home() / ".ai-adapter"
        self.temp_dir.cleanup()

    def test_uninstall_before_init(self):
        """未初期化時に uninstall するとメッセージが表示されることを確認する。"""
        result = self.runner.invoke(main, ["uninstall", "--force"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("初期化されていません", result.output)
        self.assertIn("削除するデータはありません", result.output)

    def test_uninstall_after_init(self):
        """init → uninstall --force の流れを確認する。"""
        self.runner.invoke(main, ["init"], input="\n")
        adapter_dir = self.patch_home / ".ai-adapter"
        self.assertTrue(adapter_dir.exists())

        result = self.runner.invoke(main, ["uninstall", "--force"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("アンインストールしました", result.output)
        self.assertFalse(adapter_dir.exists())

    def test_uninstall_keep_git(self):
        """--keep-git で .git が保持されることを確認する。"""
        self.runner.invoke(main, ["init"], input="\n")
        adapter_dir = self.patch_home / ".ai-adapter"

        # Git リポジトリを模擬
        git_dir = adapter_dir / ".git"
        git_dir.mkdir(parents=True, exist_ok=True)
        (git_dir / "HEAD").write_text("ref: refs/heads/main\n")

        result = self.runner.invoke(main, ["uninstall", "--force", "--keep-git"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Git リポジトリは保持", result.output)
        self.assertTrue((adapter_dir / ".git").exists())
        self.assertFalse((adapter_dir / "config.json").exists())

    def test_uninstall_cancel(self):
        """確認プロンプトで No を選択すると削除されないことを確認する。"""
        self.runner.invoke(main, ["init"], input="\n")
        adapter_dir = self.patch_home / ".ai-adapter"
        self.assertTrue(adapter_dir.exists())

        result = self.runner.invoke(main, ["uninstall"], input="n\n")
        self.assertNotEqual(result.exit_code, 0)
        self.assertTrue(adapter_dir.exists())


class TestStartCommand(unittest.TestCase):
    """start コマンドのテスト。"""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.patch_home = Path(self.temp_dir.name)
        self.runner = CliRunner()

        import pathlib
        self._original_home = pathlib.Path.home
        pathlib.Path.home = staticmethod(lambda: self.patch_home)

        import ai_adapter.config as cfg
        cfg.AI_ADAPTER_DIR = self.patch_home / ".ai-adapter"

    def tearDown(self):
        import pathlib
        pathlib.Path.home = staticmethod(self._original_home)
        import ai_adapter.config as cfg
        cfg.AI_ADAPTER_DIR = Path.home() / ".ai-adapter"
        self.temp_dir.cleanup()

    @patch("ai_adapter.cli._git.clone")
    def test_start_new_repo(self, mock_clone):
        """start コマンドで新規リポジトリがセットアップされることを確認する。"""
        # clone 失敗 → 新規 init パス
        mock_clone.side_effect = GitError("clone failed")

        result = self.runner.invoke(main, [
            "start", "git@github.com:user/test.git",
        ])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("セットアップ完了", result.output)
        adapter_dir = self.patch_home / ".ai-adapter"
        self.assertTrue(adapter_dir.exists())
        self.assertTrue((adapter_dir / "agents").exists())
        self.assertTrue((adapter_dir / "bin").exists())

    @patch("ai_adapter.cli._git.clone")
    def test_start_existing_abort(self, mock_clone):
        """既存ディレクトリがある場合の確認プロンプト。"""
        adapter_dir = self.patch_home / ".ai-adapter"
        adapter_dir.mkdir(parents=True)

        result = self.runner.invoke(main, [
            "start", "git@github.com:user/test.git",
        ], input="n\n")
        self.assertNotEqual(result.exit_code, 0)


class TestBinAddPathCommand(unittest.TestCase):
    """bin add-path コマンドのテスト。"""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.runner = CliRunner()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_bin_add_path_no_github_bin(self):
        """.github/bin がない場合にメッセージが表示されることを確認する。"""
        result = self.runner.invoke(main, ["bin", "add-path"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("見つかりません", result.output)

    def test_bin_add_path_with_github_bin(self):
        """.github/bin がある場合に PATH 行が表示されることを確認する。"""
        github_bin = Path.cwd() / ".github" / "bin"
        github_bin.mkdir(parents=True, exist_ok=True)
        (github_bin / "test.sh").write_text("#!/bin/bash")

        result = self.runner.invoke(main, ["bin", "add-path"], input="4\n")
        self.assertEqual(result.exit_code, 0)
        self.assertIn("export PATH", result.output)

        import shutil
        shutil.rmtree(Path.cwd() / ".github", ignore_errors=True)

    def test_bin_add_path_to_zshrc(self):
        """bin add-path で zshrc に追記されることを確認する。"""
        import pathlib
        orig_home = pathlib.Path.home
        pathlib.Path.home = staticmethod(lambda: Path(self.temp_dir.name))

        github_bin = Path.cwd() / ".github" / "bin"
        github_bin.mkdir(parents=True, exist_ok=True)
        (github_bin / "test.sh").write_text("#!/bin/bash")

        result = self.runner.invoke(main, ["bin", "add-path"], input="1\n")
        self.assertEqual(result.exit_code, 0)
        self.assertIn("PATH 設定を追加しました", result.output)

        zshrc = Path(self.temp_dir.name) / ".zshrc"
        self.assertTrue(zshrc.exists())
        content = zshrc.read_text()
        self.assertIn("export PATH", content)
        self.assertIn(".github/bin", content)

        import shutil
        pathlib.Path.home = staticmethod(orig_home)
        shutil.rmtree(Path.cwd() / ".github", ignore_errors=True)


class TestAddAllRecCommand(unittest.TestCase):
    """add-all-rec コマンドのテスト。"""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.patch_home = Path(self.temp_dir.name)
        self.runner = CliRunner()

        import pathlib
        self._original_home = pathlib.Path.home
        pathlib.Path.home = staticmethod(lambda: self.patch_home)

        import ai_adapter.config as cfg
        cfg.AI_ADAPTER_DIR = self.patch_home / ".ai-adapter"

        # init
        from ai_adapter.config import init
        init()

    def tearDown(self):
        import pathlib
        pathlib.Path.home = staticmethod(self._original_home)
        import ai_adapter.config as cfg
        cfg.AI_ADAPTER_DIR = Path.home() / ".ai-adapter"
        self.temp_dir.cleanup()

    def test_add_all_rec_agents(self):
        """.github/agents からエージェントが登録されることを確認する。"""
        github_agents = Path.cwd() / ".github" / "agents"
        github_agents.mkdir(parents=True, exist_ok=True)
        (github_agents / "reviewer.md").write_text("# Reviewer")
        (github_agents / "implementer.md").write_text("# Implementer")

        result = self.runner.invoke(main, ["add-all-rec"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("agents", result.output)

        # list で確認
        result = self.runner.invoke(main, ["agent", "list"])
        self.assertIn("reviewer", result.output)
        self.assertIn("implementer", result.output)

        import shutil
        shutil.rmtree(Path.cwd() / ".github", ignore_errors=True)

    def test_add_all_rec_bins(self):
        """.github/bin からスクリプトが登録されることを確認する。"""
        github_bin = Path.cwd() / ".github" / "bin"
        github_bin.mkdir(parents=True, exist_ok=True)
        (github_bin / "script1.sh").write_text("#!/bin/bash")
        (github_bin / "script2.sh").write_text("#!/bin/bash")

        result = self.runner.invoke(main, ["add-all-rec"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("bin", result.output)

        import shutil
        shutil.rmtree(Path.cwd() / ".github", ignore_errors=True)

    def test_add_all_rec_skills(self):
        """.github/skills からスキルが登録されることを確認する。"""
        github_skills = Path.cwd() / ".github" / "skills"
        github_skills.mkdir(parents=True, exist_ok=True)
        skill1 = github_skills / "my-skill"
        skill1.mkdir()
        (skill1 / "SKILL.md").write_text("---\nname: my-skill\n---\n# Skill\n")

        result = self.runner.invoke(main, ["add-all-rec"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("skills", result.output)

        import shutil
        shutil.rmtree(Path.cwd() / ".github", ignore_errors=True)

    def test_add_all_rec_mcp(self):
        """.mcp.json から MCP サーバーが登録されることを確認する。"""
        mcp_json = Path.cwd() / ".mcp.json"
        mcp_json.write_text(json.dumps({
            "mcpServers": {
                "test-server": {
                    "command": "npx",
                    "args": ["@test/server"],
                }
            }
        }))

        result = self.runner.invoke(main, ["add-all-rec"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn(".mcp.json", result.output)
        self.assertIn("1件", result.output)

        mcp_json.unlink()

    def test_add_all_rec_no_github(self):
        """.github がない場合にメッセージが表示されることを確認する。"""
        result = self.runner.invoke(main, ["add-all-rec"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("見つかりません", result.output)
