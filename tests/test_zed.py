"""Tests for the Zed editor provider (design 06).

Covers:
- ``zed install`` → AGENTS.md + .agents/skills/ (project scope)
- ``zed install --scope user`` → OS-specific Zed dir + ~/.agents/skills/
- ``zed validate`` → AGENTS.md existence, settings.json parse,
  SKILL.md frontmatter, ``--json`` output
- Unit tests for the path/validation helpers (macOS vs Linux paths)
- Doctor integration: broken Zed settings are reported
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from click.testing import CliRunner

from ai_adapter.cli import main
from ai_adapter.config import init
from ai_adapter.providers.zed import (
    get_user_config_dir,
    resolve_instructions_path,
    resolve_settings_path,
    resolve_skills_path,
    validate_settings,
    validate_skill_frontmatter,
)

_MD_WITH_FRONTMATTER = "---\nname: rules\ndescription: House rules\n---\n# Rules\nAlways be polite.\n"
_SKILL_MD = "---\nname: db-schema\ndescription: DB schema reference\n---\n# DB Schema\n"


class _ZedTestBase(unittest.TestCase):
    """Shared setUp/tearDown: isolated HOME + ai-adapter store."""

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

    def tearDown(self):
        import pathlib

        pathlib.Path.home = staticmethod(self._original_home)
        import ai_adapter.config as cfg

        cfg.AI_ADAPTER_DIR = Path.home() / ".ai-adapter"
        self.temp_dir.cleanup()

    def _add_instruction(self, name: str = "rules", content: str = _MD_WITH_FRONTMATTER):
        """Register an instruction via the CLI (`agent add`)."""
        src = Path(self.temp_dir.name) / f"{name}.md"
        src.write_text(content, encoding="utf-8")
        return self.runner.invoke(main, ["agent", "add", str(src)])

    def _add_skill(self, name: str = "db-schema", content: str = _SKILL_MD):
        """Register a skill via the CLI (`skill add`)."""
        skill_dir = Path(self.temp_dir.name) / f"skill-{name}"
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")
        return self.runner.invoke(main, ["skill", "add", str(skill_dir)])


class TestZedInstallProject(_ZedTestBase):
    """zed install (project scope) — design 06 task 06-1."""

    def test_install_generates_agents_md_and_skills(self):
        """T1/AC1: AGENTS.md + .agents/skills/<name>/SKILL.md deployed."""
        self._add_instruction()
        self._add_skill()

        result = self.runner.invoke(main, ["zed", "install", "--project-dir", str(self.project_dir)])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Zed configuration installed:", result.output)

        agents_md = self.project_dir / "AGENTS.md"
        self.assertTrue(agents_md.is_file())
        content = agents_md.read_text(encoding="utf-8")
        self.assertIn("# rules", content)
        self.assertIn("Always be polite.", content)

        skill_md = self.project_dir / ".agents" / "skills" / "db-schema" / "SKILL.md"
        self.assertTrue(skill_md.is_file())
        self.assertIn("name: db-schema", skill_md.read_text(encoding="utf-8"))

        # Phase A policy: settings.json is never generated.
        self.assertFalse((self.project_dir / ".zed" / "settings.json").exists())
        # Zed does not read .zed/skills/ — it must not be created.
        self.assertFalse((self.project_dir / ".zed" / "skills").exists())

    def test_install_concatenates_multiple_instructions(self):
        """AC1: every registered instruction contributes a section."""
        self._add_instruction("rules", "# Rules\nAlways be polite.\n")
        self._add_instruction("style", "# Style\nUse British spelling.\n")

        result = self.runner.invoke(main, ["zed", "install", "--project-dir", str(self.project_dir)])
        self.assertEqual(result.exit_code, 0, result.output)
        content = (self.project_dir / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("# rules", content)
        self.assertIn("# style", content)

    def test_install_empty_store_says_nothing(self):
        """Empty store → 'Nothing to install.' (not an error)."""
        result = self.runner.invoke(main, ["zed", "install", "--project-dir", str(self.project_dir)])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Nothing to install.", result.output)
        self.assertFalse((self.project_dir / "AGENTS.md").exists())

    def test_install_existing_agents_md_prompts_without_force(self):
        """AC3: existing AGENTS.md triggers a confirm prompt."""
        self._add_instruction()
        agents_md = self.project_dir / "AGENTS.md"
        agents_md.write_text("hand-written\n", encoding="utf-8")

        result = self.runner.invoke(main, ["zed", "install", "--project-dir", str(self.project_dir)])
        self.assertNotEqual(result.exit_code, 0)
        self.assertEqual(agents_md.read_text(encoding="utf-8"), "hand-written\n")

    def test_install_force_overwrites_existing(self):
        """AC3: --force overwrites without prompting."""
        self._add_instruction()
        agents_md = self.project_dir / "AGENTS.md"
        agents_md.write_text("hand-written\n", encoding="utf-8")

        result = self.runner.invoke(main, ["zed", "install", "--project-dir", str(self.project_dir), "--force"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("# rules", agents_md.read_text(encoding="utf-8"))

    def test_install_uninitialized_store(self):
        """No ai-adapter store → friendly message, exit 0."""
        import ai_adapter.config as cfg

        cfg.AI_ADAPTER_DIR = Path(self.temp_dir.name) / ".missing-adapter-dir"
        result = self.runner.invoke(main, ["zed", "install", "--project-dir", str(self.project_dir)])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Configuration file not found", result.output)


class TestZedInstallUserScope(_ZedTestBase):
    """zed install --scope user — design 06 task 06-2 (T2/T3)."""

    def _install_user(self):
        self._add_instruction()
        self._add_skill()
        return self.runner.invoke(main, ["zed", "install", "--scope", "user"])

    def test_user_scope_macos_paths(self):
        """T2: macOS → ~/.config/zed/ + ~/.agents/skills/ (C1 fix)."""
        with mock.patch("ai_adapter.config.platform.system", return_value="Darwin"):
            result = self._install_user()
        self.assertEqual(result.exit_code, 0, result.output)

        zed_dir = self.patch_home / ".config" / "zed"
        self.assertTrue((zed_dir / "AGENTS.md").is_file())
        self.assertTrue((self.patch_home / ".agents" / "skills" / "db-schema" / "SKILL.md").is_file())

    def test_user_scope_linux_paths(self):
        """T3: Linux → ~/.config/zed/ + ~/.agents/skills/."""
        with mock.patch("ai_adapter.config.platform.system", return_value="Linux"):
            result = self._install_user()
        self.assertEqual(result.exit_code, 0, result.output)

        self.assertTrue((self.patch_home / ".config" / "zed" / "AGENTS.md").is_file())
        self.assertTrue((self.patch_home / ".agents" / "skills" / "db-schema" / "SKILL.md").is_file())

    def test_user_scope_creates_missing_directories(self):
        """AC2: missing target directories are created."""
        self._add_instruction()
        zed_dir = self.patch_home / ".config" / "zed"
        self.assertFalse(zed_dir.exists())
        with mock.patch("ai_adapter.config.platform.system", return_value="Linux"):
            result = self.runner.invoke(main, ["zed", "install", "--scope", "user"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertTrue((zed_dir / "AGENTS.md").is_file())


class TestZedValidate(_ZedTestBase):
    """zed validate — design 06 task 06-4."""

    def _install_project(self):
        self._add_instruction()
        self._add_skill()
        self.runner.invoke(main, ["zed", "install", "--project-dir", str(self.project_dir), "--force"])

    def test_validate_valid_configuration(self):
        """T5: installed config → 'Zed configuration is valid.', exit 0."""
        self._install_project()
        (self.project_dir / ".zed").mkdir(parents=True)
        (self.project_dir / ".zed" / "settings.json").write_text(
            json.dumps({"theme": "One Dark", "context_servers": {}}), encoding="utf-8"
        )

        result = self.runner.invoke(main, ["zed", "validate", "--project-dir", str(self.project_dir)])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Zed configuration is valid.", result.output)

    def test_validate_missing_agents_md_errors(self):
        """AGENTS.md must exist in project root or the Zed user dir."""
        result = self.runner.invoke(main, ["zed", "validate", "--project-dir", str(self.project_dir)])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("AGENTS.md not found", result.output)

    def test_validate_user_scope_agents_md_satisfies(self):
        """A user-scope AGENTS.md alone satisfies the existence check."""
        (self.patch_home / ".config" / "zed").mkdir(parents=True)
        (self.patch_home / ".config" / "zed" / "AGENTS.md").write_text("# rules\n", encoding="utf-8")
        with mock.patch("ai_adapter.config.platform.system", return_value="Linux"):
            result = self.runner.invoke(main, ["zed", "validate", "--project-dir", str(self.project_dir)])
        self.assertEqual(result.exit_code, 0, result.output)

    def test_validate_broken_settings_json_reports_error(self):
        """T6: broken .zed/settings.json → error, exit 1."""
        self._install_project()
        (self.project_dir / ".zed").mkdir(parents=True)
        (self.project_dir / ".zed" / "settings.json").write_text("{not json", encoding="utf-8")

        result = self.runner.invoke(main, ["zed", "validate", "--project-dir", str(self.project_dir)])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("not valid JSON", result.output)

    def test_validate_bad_context_servers_shape(self):
        """context_servers entries must be objects."""
        self._install_project()
        (self.project_dir / ".zed").mkdir(parents=True)
        (self.project_dir / ".zed" / "settings.json").write_text(
            json.dumps({"context_servers": {"bad": "not-an-object"}}), encoding="utf-8"
        )

        result = self.runner.invoke(main, ["zed", "validate", "--project-dir", str(self.project_dir)])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("context_servers.bad must be an object", result.output)

    def test_validate_broken_skill_frontmatter_reports_error(self):
        """SKILL.md without required frontmatter fields is an error."""
        self._add_instruction()
        self.runner.invoke(main, ["zed", "install", "--project-dir", str(self.project_dir), "--force"])
        bad_skill = self.project_dir / ".agents" / "skills" / "broken" / "SKILL.md"
        bad_skill.parent.mkdir(parents=True)
        bad_skill.write_text("---\ndescription: no name field\n---\n# Broken\n", encoding="utf-8")

        result = self.runner.invoke(main, ["zed", "validate", "--project-dir", str(self.project_dir)])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("missing required 'name' field", result.output)

    def test_validate_nested_skill_md_is_ignored(self):
        """T4b: nested SKILL.md is not a Zed discovery path — not validated."""
        self._install_project()
        nested = self.project_dir / ".agents" / "skills" / "group" / "inner" / "SKILL.md"
        nested.parent.mkdir(parents=True)
        nested.write_text("no frontmatter at all", encoding="utf-8")

        result = self.runner.invoke(main, ["zed", "validate", "--project-dir", str(self.project_dir)])
        self.assertEqual(result.exit_code, 0, result.output)

    def test_validate_json_output_valid(self):
        """AC2: --json emits structured output with valid=true."""
        self._install_project()

        result = self.runner.invoke(main, ["zed", "validate", "--project-dir", str(self.project_dir), "--json"])
        self.assertEqual(result.exit_code, 0, result.output)
        data = json.loads(result.output)
        self.assertTrue(data["valid"])
        self.assertEqual(data["errors"], [])
        self.assertTrue(any("AGENTS.md" in p for p in data["checked"]))

    def test_validate_json_output_invalid(self):
        """AC2: --json emits valid=false plus the error list."""
        result = self.runner.invoke(main, ["zed", "validate", "--project-dir", str(self.project_dir), "--json"])
        self.assertNotEqual(result.exit_code, 0)
        data = json.loads(result.output)
        self.assertFalse(data["valid"])
        self.assertTrue(any("AGENTS.md not found" in e for e in data["errors"]))


class TestZedSkillGetAllFormat(_ZedTestBase):
    """skill get-all --format zed — design 06 task 06-3."""

    def test_get_all_zed_project_scope(self):
        """--format zed deploys to <project>/.agents/skills/."""
        self._add_skill()
        result = self.runner.invoke(
            main,
            ["skill", "get-all", "--format", "zed", "--project-dir", str(self.project_dir)],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        skill_md = self.project_dir / ".agents" / "skills" / "db-schema" / "SKILL.md"
        self.assertTrue(skill_md.is_file())
        # AC1: frontmatter is preserved verbatim.
        self.assertIn("name: db-schema", skill_md.read_text(encoding="utf-8"))
        # The Zed-ignored path must never be written.
        self.assertFalse((self.project_dir / ".zed" / "skills").exists())

    def test_get_all_zed_user_scope(self):
        """--scope user deploys to ~/.agents/skills/ (global discovery path)."""
        self._add_skill()
        with mock.patch("ai_adapter.config.platform.system", return_value="Linux"):
            result = self.runner.invoke(main, ["skill", "get-all", "--format", "zed", "--scope", "user"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertTrue((self.patch_home / ".agents" / "skills" / "db-schema" / "SKILL.md").is_file())

    def test_get_all_zed_scope_user_rejected_with_standard(self):
        """--scope user still requires a native-path format."""
        result = self.runner.invoke(main, ["skill", "get-all", "--format", "standard", "--scope", "user"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("--scope user is only supported with --format", result.output)


class TestZedUnitHelpers(unittest.TestCase):
    """Pure helper tests: path resolution + validators."""

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

    def test_resolve_settings_path_project_and_user(self):
        project = Path("/tmp/proj")
        self.assertEqual(resolve_settings_path("project", project), project / ".zed" / "settings.json")
        with mock.patch("ai_adapter.config.platform.system", return_value="Linux"):
            self.assertEqual(
                resolve_settings_path("user"),
                self.patch_home / ".config" / "zed" / "settings.json",
            )

    def test_resolve_instructions_path_project_and_user(self):
        project = Path("/tmp/proj")
        self.assertEqual(resolve_instructions_path("project", project), project / "AGENTS.md")
        with mock.patch("ai_adapter.config.platform.system", return_value="Darwin"):
            self.assertEqual(
                resolve_instructions_path("user"),
                self.patch_home / ".config" / "zed" / "AGENTS.md",
            )

    def test_resolve_skills_path_uses_agents_discovery_path(self):
        """T4/Plan C6-1: skills resolve to .agents/skills/, never .zed/skills/."""
        project = Path("/tmp/proj")
        self.assertEqual(resolve_skills_path("project", project), project / ".agents" / "skills")
        self.assertEqual(resolve_skills_path("user"), self.patch_home / ".agents" / "skills")

    def test_get_user_config_dir_os_dependent(self):
        """T9: macOS and Linux resolve different user directories."""
        with mock.patch("ai_adapter.config.platform.system", return_value="Darwin"):
            self.assertEqual(
                get_user_config_dir(),
                self.patch_home / ".config" / "zed",
            )
        with mock.patch("ai_adapter.config.platform.system", return_value="Linux"):
            self.assertEqual(get_user_config_dir(), self.patch_home / ".config" / "zed")

    def test_get_zed_user_dir_accepts_custom_home(self):
        """config.get_zed_user_dir(home) resolves under the given home."""
        from ai_adapter.config import get_zed_user_dir

        custom = Path("/elsewhere")
        with mock.patch("ai_adapter.config.platform.system", return_value="Linux"):
            self.assertEqual(get_zed_user_dir(custom), custom / ".config" / "zed")

    def test_validate_settings_accepts_valid_json(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump({"theme": "One Dark", "context_servers": {"docs": {"command": "mcp-docs"}}}, f)
            path = Path(f.name)
        self.addCleanup(path.unlink)
        self.assertEqual(validate_settings(path), [])

    def test_validate_settings_rejects_bad_json_and_shapes(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            f.write("{not json")
            bad_json = Path(f.name)
        self.addCleanup(bad_json.unlink)
        self.assertTrue(any("not valid JSON" in e for e in validate_settings(bad_json)))

        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(["not", "an", "object"], f)
            bad_list = Path(f.name)
        self.addCleanup(bad_list.unlink)
        self.assertTrue(any("must be a JSON object" in e for e in validate_settings(bad_list)))

        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump({"context_servers": {"bad": 42}}, f)
            bad_entry = Path(f.name)
        self.addCleanup(bad_entry.unlink)
        self.assertTrue(any("context_servers.bad must be an object" in e for e in validate_settings(bad_entry)))

    def _write_skill_md(self, content: str) -> Path:
        skill_dir = Path(self.temp_dir.name) / "unit-skill"
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text(content, encoding="utf-8")
        return skill_md

    def test_validate_skill_frontmatter_accepts_valid(self):
        skill_md = self._write_skill_md(_SKILL_MD)
        self.assertEqual(validate_skill_frontmatter(skill_md), [])

    def test_validate_skill_frontmatter_rejects_missing_fields(self):
        no_frontmatter = self._write_skill_md("# Just markdown\n")
        self.assertTrue(
            any("must start with '---' frontmatter" in e for e in validate_skill_frontmatter(no_frontmatter))
        )

        missing_name = self._write_skill_md("---\ndescription: d\n---\n# x\n")
        self.assertTrue(any("missing required 'name' field" in e for e in validate_skill_frontmatter(missing_name)))

        missing_description = self._write_skill_md("---\nname: n\n---\n# x\n")
        self.assertTrue(
            any("missing required 'description' field" in e for e in validate_skill_frontmatter(missing_description))
        )


class TestZedDoctorIntegration(_ZedTestBase):
    """doctor reports broken Zed settings (design 06 doctor integration)."""

    def test_doctor_flags_broken_zed_settings(self):
        (self.project_dir / ".zed").mkdir(parents=True)
        (self.project_dir / ".zed" / "settings.json").write_text("{broken", encoding="utf-8")

        from ai_adapter.doctor import build_doctor_report

        report = build_doctor_report(project_dir=self.project_dir, home=self.patch_home)
        joined = " | ".join(str(issue) for issue in report.issues)
        self.assertIn("zed project settings", joined)

    def test_doctor_flags_broken_user_zed_settings(self):
        user_dir = self.patch_home / ".config" / "zed"
        user_dir.mkdir(parents=True)
        (user_dir / "settings.json").write_text("{broken", encoding="utf-8")

        from ai_adapter.doctor import build_doctor_report

        with mock.patch("ai_adapter.config.platform.system", return_value="Linux"):
            report = build_doctor_report(project_dir=self.project_dir, home=self.patch_home)
        joined = " | ".join(str(issue) for issue in report.issues)
        self.assertIn("zed user settings", joined)


if __name__ == "__main__":
    unittest.main()


class TestZedSecurityGuards(unittest.TestCase):
    """QA C2/M1: path traversal guard and YAML parse safety."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_deploy_skills_blocks_prefix_sibling_escape(self):
        """C2: '../skills-evil' must be skipped (prefix-sibling escape)."""
        from ai_adapter.models import Skill
        from ai_adapter.providers.zed import deploy_skills

        src_dir = self.base / "store"
        (src_dir / "normal").mkdir(parents=True)
        (src_dir / "normal" / "SKILL.md").write_text("---\nname: normal\ndescription: d\n---\n# n\n", encoding="utf-8")
        (src_dir / "evil").mkdir(parents=True)
        (src_dir / "evil" / "SKILL.md").write_text("---\nname: evil\ndescription: d\n---\n# e\n", encoding="utf-8")
        # Skill entry whose name traverses out via prefix-sibling.
        skills = [
            Skill(name="normal"),
            Skill(name="../skills-evil"),
        ]
        with mock.patch("ai_adapter.config.Path.cwd", return_value=self.base / "proj"):
            (self.base / "proj").mkdir(parents=True)
            deployed = deploy_skills(skills, src_dir, scope="project", force=True)
        # Only the safe skill deployed.
        self.assertEqual(len(deployed), 1)
        self.assertIn("normal", deployed[0])
        # The escaped destination must NOT exist.
        escaped = self.base / "proj" / ".agents" / "skills-evil"
        self.assertFalse(escaped.exists())

    def test_deploy_skills_blocks_dotdot_name(self):
        """C2: '..' as skill name must be skipped."""
        from ai_adapter.models import Skill
        from ai_adapter.providers.zed import deploy_skills

        src_dir = self.base / "store"
        (src_dir / "x").mkdir(parents=True)
        (src_dir / "x" / "SKILL.md").write_text("# x\n", encoding="utf-8")
        (self.base / "proj").mkdir(parents=True)
        with mock.patch("ai_adapter.config.Path.cwd", return_value=self.base / "proj"):
            deployed = deploy_skills([Skill(name="..")], src_dir, scope="project", force=True)
        self.assertEqual(deployed, [])

    def test_validate_broken_yaml_returns_error_not_crash(self):
        """M1: YAML syntax error in SKILL.md → error message, no crash."""
        from ai_adapter.providers.zed import validate_skill_frontmatter

        bad = self.base / "skills" / "broken" / "SKILL.md"
        bad.parent.mkdir(parents=True)
        bad.write_text("---\nname: [unclosed\ndescription: d\n---\n# x\n", encoding="utf-8")
        errors = validate_skill_frontmatter(bad)
        self.assertTrue(errors)
        self.assertIn("YAML", errors[0])
