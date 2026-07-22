"""config.py のテスト。"""

import os
import tempfile
import unittest
from pathlib import Path

from ai_adapter.config import (
    AI_ADAPTER_DIR,
    get_agents_dir,
    get_bins_dir,
    get_github_skills_dir,
    get_config_path,
    get_mcp_dir,
    get_skills_dir,
    init,
    load_config,
    save_config,
)
from ai_adapter.models import Config, Env


class TestConfigPaths(unittest.TestCase):
    """設定ファイルのパス解決のテスト。"""

    def test_get_config_path_default(self):
        """デフォルトの設定ファイルパスを確認する。"""
        expected = AI_ADAPTER_DIR / "config.json"
        self.assertEqual(get_config_path(), expected)

    def test_get_config_path_env_override(self):
        """環境変数で設定ファイルパスを上書きできることを確認する。"""
        with tempfile.NamedTemporaryFile(suffix=".json") as f:
            os.environ["AI_ADAPTER_CONFIG"] = f.name
            try:
                self.assertEqual(get_config_path(), Path(f.name))
            finally:
                del os.environ["AI_ADAPTER_CONFIG"]

    def test_get_agents_dir(self):
        """agents/ ディレクトリのパスを確認する。"""
        self.assertEqual(get_agents_dir(), AI_ADAPTER_DIR / "agents")

    def test_get_bins_dir(self):
        """bin/ ディレクトリのパスを確認する。"""
        self.assertEqual(get_bins_dir(), AI_ADAPTER_DIR / "bin")

    def test_get_skills_dir(self):
        """skills/ ディレクトリのパスを確認する。"""
        self.assertEqual(get_skills_dir(), AI_ADAPTER_DIR / "skills")

    def test_get_mcp_dir(self):
        """mcp/ ディレクトリのパスを確認する。"""
        self.assertEqual(get_mcp_dir(), AI_ADAPTER_DIR / "mcp")

    def test_get_github_skills_dir(self):
        """.github/skills/ ディレクトリのパスを確認する。"""
        expected = Path.cwd() / ".github" / "skills"
        self.assertEqual(get_github_skills_dir(), expected)


class TestConfigInit(unittest.TestCase):
    """init 関数のテスト。"""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.patch_home = Path(self.temp_dir.name)
        self._original_home = Path.home

        # Home を一時ディレクトリに差し替え
        import builtins
        import pathlib

        def mock_home():
            return self.patch_home

        pathlib.Path.home = staticmethod(mock_home)
        # config モジュール内の AI_ADAPTER_DIR も更新
        import ai_adapter.config as cfg
        cfg.AI_ADAPTER_DIR = self.patch_home / ".ai-adapter"

    def tearDown(self):
        import pathlib
        pathlib.Path.home = staticmethod(self._original_home)
        # config モジュールの AI_ADAPTER_DIR を戻す
        import ai_adapter.config as cfg
        cfg.AI_ADAPTER_DIR = Path.home() / ".ai-adapter"
        self.temp_dir.cleanup()

    def test_init_creates_directories(self):
        """init でディレクトリが作成されることを確認する。"""
        adapter_dir = self.patch_home / ".ai-adapter"
        self.assertFalse(adapter_dir.exists())

        result = init()
        self.assertTrue(result)
        self.assertTrue(adapter_dir.exists())
        self.assertTrue((adapter_dir / "agents").exists())
        self.assertTrue((adapter_dir / "bin").exists())
        self.assertTrue((adapter_dir / "skills").exists())
        self.assertTrue((adapter_dir / "mcp").exists())

    def test_init_creates_config(self):
        """init で設定ファイルが作成されることを確認する。"""
        init()
        config_path = self.patch_home / ".ai-adapter" / "config.json"
        self.assertTrue(config_path.exists())

        config = load_config()
        self.assertIsNotNone(config)
        self.assertEqual(config.default_env, "default")
        self.assertEqual(len(config.envs), 1)
        self.assertEqual(config.envs[0].name, "default")

    def test_init_idempotent(self):
        """init が冪等であることを確認する（2回実行してもエラーにならない）。"""
        init()
        result = init()
        self.assertFalse(result)


class TestConfigSaveLoad(unittest.TestCase):
    """Config の保存と読み込みのテスト。"""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = Path(self.temp_dir.name) / "config.json"
        os.environ["AI_ADAPTER_CONFIG"] = str(self.config_path)

    def tearDown(self):
        del os.environ["AI_ADAPTER_CONFIG"]
        self.temp_dir.cleanup()

    def test_save_and_load(self):
        """保存した Config が正しく読み込めることを確認する。"""
        config = Config(
            version=1,
            default_env="myenv",
            agents=[],
            envs=[Env(name="myenv", description="テスト環境")],
            bins=[],
            agent_bindings=[],
        )
        save_config(config)

        loaded = load_config()
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.default_env, "myenv")
        self.assertEqual(len(loaded.envs), 1)
        self.assertEqual(loaded.envs[0].name, "myenv")

    def test_load_nonexistent(self):
        """存在しない設定ファイルを読み込むと None が返ることを確認する。"""
        config = load_config()
        self.assertIsNone(config)


class TestConfigFromDictValidation(unittest.TestCase):
    """Config.from_dict のバリデーションのテスト。"""

    def test_from_dict_invalid_version(self):
        """version が整数でない場合に ValueError が上がることを確認する。"""
        with self.assertRaises(ValueError):
            Config.from_dict({"version": "1"})

    def test_from_dict_invalid_agents(self):
        """agents が配列でない場合に ValueError が上がることを確認する。"""
        with self.assertRaises(ValueError):
            Config.from_dict({"agents": "not a list"})

    def test_from_dict_invalid_default_env(self):
        """default_env が文字列でない場合に ValueError が上がることを確認する。"""
        with self.assertRaises(ValueError):
            Config.from_dict({"default_env": 123})
