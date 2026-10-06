"""Tests for config.py."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ai_adapter.config import (
    AI_ADAPTER_DIR,
    get_agents_dir,
    get_bins_dir,
    get_config_path,
    get_github_skills_dir,
    get_mcp_dir,
    get_skills_dir,
    get_user_instruction_path,
    get_zed_user_dir,
    init,
    load_config,
    resolve_scope_path,
    save_config,
)
from ai_adapter.models import Config, Env


class TestConfigPaths(unittest.TestCase):
    """Tests for configuration file path resolution."""

    def test_get_config_path_default(self):
        """Verify default config file path."""
        expected = AI_ADAPTER_DIR / "config.json"
        self.assertEqual(get_config_path(), expected)

    def test_get_config_path_env_override(self):
        """Verify config file path can be overridden by env var."""
        with tempfile.NamedTemporaryFile(suffix=".json") as f:
            os.environ["AI_ADAPTER_CONFIG"] = f.name
            try:
                self.assertEqual(get_config_path(), Path(f.name))
            finally:
                del os.environ["AI_ADAPTER_CONFIG"]

    def test_get_agents_dir(self):
        """Verify agents/ directory path."""
        self.assertEqual(get_agents_dir(), AI_ADAPTER_DIR / "agents")

    def test_get_bins_dir(self):
        """Verify bin/ directory path."""
        self.assertEqual(get_bins_dir(), AI_ADAPTER_DIR / "bin")

    def test_get_skills_dir(self):
        """Verify skills/ directory path."""
        self.assertEqual(get_skills_dir(), AI_ADAPTER_DIR / "skills")

    def test_get_mcp_dir(self):
        """Verify mcp/ directory path."""
        self.assertEqual(get_mcp_dir(), AI_ADAPTER_DIR / "mcp")

    def test_get_github_skills_dir(self):
        """.github/Verify skills/ directory path."""
        expected = Path.cwd() / ".github" / "skills"
        self.assertEqual(get_github_skills_dir(), expected)


class TestConfigInit(unittest.TestCase):
    """Tests for the init function."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.patch_home = Path(self.temp_dir.name)
        self._original_home = Path.home

        # Replace Home with a temporary directory
        import pathlib

        def mock_home():
            return self.patch_home

        pathlib.Path.home = staticmethod(mock_home)
        # Also update AI_ADAPTER_DIR in the config module
        import ai_adapter.config as cfg

        cfg.AI_ADAPTER_DIR = self.patch_home / ".ai-adapter"

    def tearDown(self):
        import pathlib

        pathlib.Path.home = staticmethod(self._original_home)
        # Restore AI_ADAPTER_DIR in the config module
        import ai_adapter.config as cfg

        cfg.AI_ADAPTER_DIR = Path.home() / ".ai-adapter"
        self.temp_dir.cleanup()

    def test_init_creates_directories(self):
        """Verify init creates directories."""
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
        """Verify init creates config file."""
        init()
        config_path = self.patch_home / ".ai-adapter" / "config.json"
        self.assertTrue(config_path.exists())

        config = load_config()
        self.assertIsNotNone(config)
        self.assertEqual(config.default_env, "default")
        self.assertEqual(len(config.envs), 1)
        self.assertEqual(config.envs[0].name, "default")

    def test_init_idempotent(self):
        """Verify init is idempotent (running twice does not error)."""
        init()
        result = init()
        self.assertFalse(result)


class TestConfigSaveLoad(unittest.TestCase):
    """Tests for saving and loading Config."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = Path(self.temp_dir.name) / "config.json"
        os.environ["AI_ADAPTER_CONFIG"] = str(self.config_path)

    def tearDown(self):
        del os.environ["AI_ADAPTER_CONFIG"]
        self.temp_dir.cleanup()

    def test_save_and_load(self):
        """Verify saved Config loads correctly."""
        config = Config(
            version=1,
            default_env="myenv",
            agents=[],
            envs=[Env(name="myenv", description="Test environment")],
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
        """Verify loading non-existent config returns None."""
        config = load_config()
        self.assertIsNone(config)


class TestConfigFromDictValidation(unittest.TestCase):
    """Tests for Config.from_dict validation."""

    def test_from_dict_invalid_version(self):
        """Verify ValueError is raised when version is not an integer."""
        with self.assertRaises(ValueError):
            Config.from_dict({"version": "1"})

    def test_from_dict_invalid_agents(self):
        """Verify ValueError is raised when agents is not a list."""
        with self.assertRaises(ValueError):
            Config.from_dict({"agents": "not a list"})

    def test_from_dict_invalid_default_env(self):
        """Verify ValueError is raised when default_env is not a string."""
        with self.assertRaises(ValueError):
            Config.from_dict({"default_env": 123})


class _PatchedHomeTestCase(unittest.TestCase):
    """Base class that redirects Path.home() to a temp directory."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.patch_home = Path(self.temp_dir.name)
        import pathlib

        self._original_home = pathlib.Path.home
        pathlib.Path.home = staticmethod(lambda: self.patch_home)

    def tearDown(self):
        import pathlib

        pathlib.Path.home = staticmethod(self._original_home)
        self.temp_dir.cleanup()


class TestGetUserInstructionPath(_PatchedHomeTestCase):
    """Tests for get_user_instruction_path (design 01 task 01-4)."""

    def test_default_filenames_per_tool(self):
        """Each platform resolves to the filename it actually reads."""
        self.assertEqual(get_user_instruction_path("codex"), self.patch_home / ".codex" / "AGENTS.md")
        self.assertEqual(get_user_instruction_path("claude"), self.patch_home / ".claude" / "CLAUDE.md")
        self.assertEqual(
            get_user_instruction_path("opencode"),
            self.patch_home / ".config" / "opencode" / "AGENTS.md",
        )
        self.assertEqual(get_user_instruction_path("gemini"), self.patch_home / ".gemini" / "GEMINI.md")

    def test_custom_filename(self):
        """A custom filename overrides the platform default."""
        self.assertEqual(
            get_user_instruction_path("gemini", "CONTEXT.md"),
            self.patch_home / ".gemini" / "CONTEXT.md",
        )

    def test_zed_macos_path(self):
        """macOS Zed config lives under ~/.config/zed (C1 fix)."""
        with mock.patch("ai_adapter.config.platform.system", return_value="Darwin"):
            self.assertEqual(
                get_user_instruction_path("zed"),
                self.patch_home / ".config" / "zed" / "AGENTS.md",
            )

    def test_zed_linux_path(self):
        """Linux Zed lives under ~/.config/zed/."""
        with mock.patch("ai_adapter.config.platform.system", return_value="Linux"):
            self.assertEqual(
                get_user_instruction_path("zed"),
                self.patch_home / ".config" / "zed" / "AGENTS.md",
            )

    def test_zed_windows_path(self):
        """Windows Zed lives under %APPDATA%\\Zed\\."""
        appdata = self.patch_home / "AppData" / "Roaming"
        env = {"APPDATA": str(appdata)}
        with mock.patch("ai_adapter.config.platform.system", return_value="Windows"), mock.patch.dict(os.environ, env):
            self.assertEqual(get_user_instruction_path("zed"), appdata / "Zed" / "AGENTS.md")

    def test_zed_windows_path_without_appdata(self):
        """Windows falls back to ~/AppData/Roaming when APPDATA is unset."""
        with (
            mock.patch("ai_adapter.config.platform.system", return_value="Windows"),
            mock.patch.dict(os.environ, {}, clear=False),
        ):
            os.environ.pop("APPDATA", None)
            self.assertEqual(
                get_user_instruction_path("zed"),
                self.patch_home / "AppData" / "Roaming" / "Zed" / "AGENTS.md",
            )

    def test_does_not_create_directories(self):
        """Asking for a path must never create it (deploy time mkdir only)."""
        get_user_instruction_path("claude")
        self.assertFalse((self.patch_home / ".claude").exists())

    def test_unknown_tool_raises(self):
        """Unknown tools raise ValueError."""
        with self.assertRaises(ValueError):
            get_user_instruction_path("nope")

    def test_cursor_raises(self):
        """Cursor has no native user instruction path."""
        with self.assertRaises(ValueError):
            get_user_instruction_path("cursor")


class TestResolveScopePath(_PatchedHomeTestCase):
    """Tests for resolve_scope_path (design 01 task 01-5)."""

    def test_claude_agents_project(self):
        """Project scope resolves under the project directory with gitignore."""
        target = resolve_scope_path("claude", "agents", "project", Path("/tmp/proj"))
        self.assertEqual(target.path, Path("/tmp/proj") / ".claude" / "agents")
        self.assertTrue(target.use_gitignore)

    def test_claude_agents_user(self):
        """User scope resolves under $HOME without gitignore."""
        target = resolve_scope_path("claude", "agents", "user")
        self.assertEqual(target.path, self.patch_home / ".claude" / "agents")
        self.assertFalse(target.use_gitignore)

    def test_codex_skills_user_spec_path(self):
        """Codex skills deploy to the spec path ~/.agents/skills/ (design 03)."""
        target = resolve_scope_path("codex", "skills", "user")
        self.assertEqual(target.path, self.patch_home / ".agents" / "skills")
        self.assertFalse(target.use_gitignore)

    def test_opencode_commands_user(self):
        """OpenCode commands deploy under ~/.config/opencode/ (design 04)."""
        target = resolve_scope_path("opencode", "commands", "user")
        self.assertEqual(target.path, self.patch_home / ".config" / "opencode" / "commands")
        self.assertFalse(target.use_gitignore)

    def test_instruction_user_paths(self):
        """Instruction user scope resolves to each platform's directory."""
        cases = [
            ("codex", self.patch_home / ".codex"),
            ("claude", self.patch_home / ".claude"),
            ("opencode", self.patch_home / ".config" / "opencode"),
            ("gemini", self.patch_home / ".gemini"),
        ]
        for tool, expected in cases:
            with self.subTest(tool=tool):
                target = resolve_scope_path(tool, "instruction", "user")
                self.assertEqual(target.path, expected)
                self.assertFalse(target.use_gitignore)

    def test_instruction_zed_user_path_os_dependent(self):
        """Zed instruction user scope follows the OS-specific directory."""
        with mock.patch("ai_adapter.config.platform.system", return_value="Linux"):
            target = resolve_scope_path("zed", "instruction", "user")
        self.assertEqual(target.path, self.patch_home / ".config" / "zed")
        self.assertFalse(target.use_gitignore)

    def test_instruction_project_is_project_root(self):
        """Instruction project scope deploys to the project root."""
        target = resolve_scope_path("codex", "instruction", "project", Path("/tmp/proj"))
        self.assertEqual(target.path, Path("/tmp/proj"))
        self.assertTrue(target.use_gitignore)

    def test_unknown_tool_category_raises(self):
        """Undefined tool × category combinations raise ValueError."""
        with self.assertRaises(ValueError):
            resolve_scope_path("claude", "unknown-category", "user")
        with self.assertRaises(ValueError):
            resolve_scope_path("unknown-tool", "agents", "user")
        with self.assertRaises(ValueError):
            resolve_scope_path("cursor", "instruction", "user")

    def test_unknown_scope_raises(self):
        """Unknown scopes raise ValueError."""
        with self.assertRaises(ValueError):
            resolve_scope_path("claude", "agents", "global")


class TestGetZedUserDir(_PatchedHomeTestCase):
    """Tests for get_zed_user_dir (design 06 task 06-2, Plan Architect M6-3)."""

    def test_linux_default(self):
        """Linux resolves ~/.config/zed/."""
        with mock.patch("ai_adapter.config.platform.system", return_value="Linux"):
            self.assertEqual(get_zed_user_dir(), self.patch_home / ".config" / "zed")

    def test_macos_default(self):
        """macOS resolves ~/.config/zed/ (C1 fix)."""
        with mock.patch("ai_adapter.config.platform.system", return_value="Darwin"):
            self.assertEqual(
                get_zed_user_dir(),
                self.patch_home / ".config" / "zed",
            )

    def test_custom_home_parameter(self):
        """An explicit *home* replaces Path.home() (used by scan)."""
        custom = Path("/elsewhere")
        with mock.patch("ai_adapter.config.platform.system", return_value="Linux"):
            self.assertEqual(get_zed_user_dir(custom), custom / ".config" / "zed")
        with mock.patch("ai_adapter.config.platform.system", return_value="Darwin"):
            self.assertEqual(
                get_zed_user_dir(custom),
                custom / ".config" / "zed",
            )

    def test_does_not_create_directories(self):
        """Asking for the path must never create it (deploy-time mkdir only)."""
        with mock.patch("ai_adapter.config.platform.system", return_value="Linux"):
            get_zed_user_dir()
        self.assertFalse((self.patch_home / ".config" / "zed").exists())


class TestZedScopePaths(_PatchedHomeTestCase):
    """Tests for zed skills/settings scope resolution (design 06)."""

    def test_skills_project_scope(self):
        """Project skills resolve to <project>/.agents/skills/ (Plan C6-1)."""
        target = resolve_scope_path("zed", "skills", "project", Path("/tmp/proj"))
        self.assertEqual(target.path, Path("/tmp/proj") / ".agents" / "skills")
        self.assertTrue(target.use_gitignore)

    def test_skills_user_scope(self):
        """Global skills resolve to ~/.agents/skills/ — OS-independent."""
        target = resolve_scope_path("zed", "skills", "user")
        self.assertEqual(target.path, self.patch_home / ".agents" / "skills")
        self.assertFalse(target.use_gitignore)

    def test_settings_project_scope(self):
        """Project settings resolve to <project>/.zed/ (settings.json parent)."""
        target = resolve_scope_path("zed", "settings", "project", Path("/tmp/proj"))
        self.assertEqual(target.path, Path("/tmp/proj") / ".zed")
        self.assertTrue(target.use_gitignore)

    def test_settings_user_scope_os_dependent(self):
        """User settings resolve to the OS-specific Zed directory."""
        with mock.patch("ai_adapter.config.platform.system", return_value="Linux"):
            target = resolve_scope_path("zed", "settings", "user")
        self.assertEqual(target.path, self.patch_home / ".config" / "zed")
        self.assertFalse(target.use_gitignore)

    def test_unknown_zed_category_raises(self):
        """Unsupported zed × category combinations raise ValueError."""
        with self.assertRaises(ValueError):
            resolve_scope_path("zed", "agents", "project")
