"""bin.py のテスト。"""

import tempfile
import unittest
from pathlib import Path

from click.testing import CliRunner

from ai_adapter.cli import main
from ai_adapter.config import init
from ai_adapter.models import Bin, Config


class TestBinAddRecCommand(unittest.TestCase):
    """bin add-rec コマンドのテスト。"""

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
        """add-rec でディレクトリ内の全スクリプトが登録されることを確認する。"""
        src_dir = Path(self.temp_dir.name) / "scripts_dir"
        src_dir.mkdir()
        (src_dir / "script1.sh").write_text("#!/bin/bash")
        (src_dir / "script2.sh").write_text("#!/bin/bash")

        result = self.runner.invoke(main, ["bin", "add-rec", "--env", "default", str(src_dir)])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("2", result.output)

        # list で確認
        result = self.runner.invoke(main, ["bin", "list"])
        self.assertIn("script1.sh", result.output)
        self.assertIn("script2.sh", result.output)


class TestBinCommands(unittest.TestCase):
    """bin サブコマンドのテスト。"""

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

        # テスト用スクリプトファイル作成
        self.script_file = Path(self.temp_dir.name) / "deploy-test.sh"
        self.script_file.write_text("#!/bin/bash\necho 'deploy test'\n")

    def tearDown(self):
        import pathlib
        pathlib.Path.home = staticmethod(self._original_home)
        import ai_adapter.config as cfg
        cfg.AI_ADAPTER_DIR = Path.home() / ".ai-adapter"
        self.temp_dir.cleanup()

    def test_bin_list_empty(self):
        """bin list で空メッセージが表示されることを確認する。"""
        result = self.runner.invoke(main, ["bin", "list"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("No scripts registered.", result.output)

    def test_bin_add(self):
        """bin add でスクリプトが追加されることを確認する。"""
        result = self.runner.invoke(main, [
            "bin", "add", "--env", "default", str(self.script_file),
            "--description", "テスト用スクリプト",
        ])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("deploy-test.sh", result.output)

        bins_dir = self.patch_home / ".ai-adapter" / "bin"
        self.assertTrue((bins_dir / "deploy-test.sh").exists())

    def test_bin_add_and_list(self):
        """bin add → bin list の流れを確認する。"""
        self.runner.invoke(main, ["bin", "add", "--env", "default", str(self.script_file)])
        result = self.runner.invoke(main, ["bin", "list"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("deploy-test.sh", result.output)

    def test_bin_add_and_list_filtered(self):
        """bin add → bin list env でフィルタリングされることを確認する。"""
        self.runner.invoke(main, ["bin", "add", "--env", "default", str(self.script_file)])
        result = self.runner.invoke(main, ["bin", "list", "--env", "default"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("deploy-test.sh", result.output)

        result = self.runner.invoke(main, ["bin", "list", "--env", "nonexistent"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("has no scripts registered", result.output)

    def test_bin_get(self):
        """bin get で .github/bin/ にコピーされることを確認する。"""
        self.runner.invoke(main, ["bin", "add", "--env", "default", str(self.script_file)])

        github_bin = Path.cwd() / ".github" / "bin"
        github_bin.mkdir(parents=True, exist_ok=True)

        result = self.runner.invoke(main, ["bin", "get", "--env", "default", "deploy-test.sh"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("deploy-test.sh", result.output)
        self.assertTrue((github_bin / "deploy-test.sh").exists())

        import shutil
        shutil.rmtree(Path.cwd() / ".github", ignore_errors=True)

    def test_bin_get_not_found(self):
        """存在しないスクリプトの get でエラーになることを確認する。"""
        result = self.runner.invoke(main, ["bin", "get", "--env", "default", "nonexistent.sh"])
        self.assertNotEqual(result.exit_code, 0)

    def test_bin_get_with_project_dir(self):
        """bin get --project-dir で指定ディレクトリにコピーされることを確認する。"""
        self.runner.invoke(main, ["bin", "add", "--env", "default", str(self.script_file)])

        project_dir = Path(self.temp_dir.name) / "my-project"
        project_dir.mkdir(parents=True)

        result = self.runner.invoke(main, [
            "bin", "get", "--env", "default", "deploy-test.sh",
            "--project-dir", str(project_dir),
        ])
        self.assertEqual(result.exit_code, 0)
        self.assertTrue((project_dir / ".github" / "bin" / "deploy-test.sh").exists())

    def test_bin_get_all(self):
        """bin get-all で全スクリプトが .github/bin/ にコピーされることを確認する。"""
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

        import shutil
        shutil.rmtree(Path.cwd() / ".github", ignore_errors=True)

    def test_bin_remove(self):
        """bin remove で登録が解除されることを確認する。"""
        self.runner.invoke(main, ["bin", "add", "--env", "default", str(self.script_file)])
        result = self.runner.invoke(main, ["bin", "remove", "--env", "default", "deploy-test.sh"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("deploy-test.sh", result.output)

        # ファイルはremovされないことを確認
        bins_dir = self.patch_home / ".ai-adapter" / "bin"
        self.assertTrue((bins_dir / "deploy-test.sh").exists())

    def test_bin_remove_not_found(self):
        """存在しないスクリプトの remove でエラーになることを確認する。"""
        result = self.runner.invoke(main, ["bin", "remove", "--env", "default", "nonexistent.sh"])
        self.assertNotEqual(result.exit_code, 0)

    def test_bin_remove_all(self):
        """bin remove-all で全スクリプトの登録が解除されることを確認する。"""
        script1 = Path(self.temp_dir.name) / "test1.sh"
        script1.write_text("#!/bin/bash")
        script2 = Path(self.temp_dir.name) / "test2.sh"
        script2.write_text("#!/bin/bash")
        self.runner.invoke(main, ["bin", "add", "--env", "default", str(script1)])
        self.runner.invoke(main, ["bin", "add", "--env", "default", str(script2)])

        result = self.runner.invoke(main, ["bin", "remove-all", "--force"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("All scripts", result.output)

        # list で空になる
        result = self.runner.invoke(main, ["bin", "list"])
        self.assertIn("No scripts registered.", result.output)
