"""Tests for the version tracking module.

Covers:
- frontmatter version extraction
- VersionInfo dataclass and update_available property
- check_versions with registered skills
- get_latest_github_tag (mocked git)
- Offline behavior (latest: unknown)
- render_version_table formatting
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from ai_adapter import config as cfg
from ai_adapter.git import GitError
from ai_adapter.models import Skill
from ai_adapter.version import (
    VersionInfo,
    _skill_installed_version,
    check_versions,
    get_latest_github_tag,
    render_version_table,
)

# ── Helpers ─────────────────────────────────────────────────────────────


def _init_store() -> None:
    cfg.init()


def _write_skill(skill_dir: Path, name: str, version: str | None = None) -> None:
    """Write a SKILL.md with optional frontmatter version."""
    skill_file = skill_dir / name / "SKILL.md"
    skill_file.parent.mkdir(parents=True, exist_ok=True)
    fm_lines = [f"name: {name}"]
    if version is not None:
        fm_lines.append(f"version: {version}")
    fm_lines.append(f"description: Skill {name}")
    fm_text = "\n".join(fm_lines)
    skill_file.write_text(f"---\n{fm_text}\n---\n# {name}\n", encoding="utf-8")


def _register_skill(name: str, version: str | None = None, description: str = "") -> None:
    _init_store()
    _write_skill(cfg.get_skills_dir(), name, version)
    config = cfg.load_config()
    assert config is not None
    config.skills.append(Skill(name=name, description=description))
    cfg.save_config(config)


# ── VersionInfo tests ───────────────────────────────────────────────────


def test_version_info_to_dict():
    v = VersionInfo(name="test", category="skill", installed="1.0", latest="2.0", source="github:u/r")
    d = v.to_dict()
    assert d["name"] == "test"
    assert d["category"] == "skill"
    assert d["installed"] == "1.0"
    assert d["latest"] == "2.0"
    assert d["source"] == "github:u/r"


def test_version_info_update_available_true():
    v = VersionInfo(name="test", category="skill", installed="1.0", latest="2.0", source=None)
    assert v.update_available is True


def test_version_info_update_available_false_when_same():
    v = VersionInfo(name="test", category="skill", installed="1.0", latest="1.0", source=None)
    assert v.update_available is False


def test_version_info_update_available_false_when_latest_unknown():
    v = VersionInfo(name="test", category="skill", installed="1.0", latest="unknown", source=None)
    assert v.update_available is False


def test_version_info_update_available_false_when_none():
    v = VersionInfo(name="test", category="skill", installed="1.0", latest=None, source=None)
    assert v.update_available is False


# ── Frontmatter extraction ──────────────────────────────────────────────


def test_skill_installed_version_with_version(isolated_home: Path):
    _write_skill(cfg.get_skills_dir(), "my-skill", "1.2.3")
    v = _skill_installed_version(cfg.get_skills_dir() / "my-skill")
    assert v == "1.2.3"


def test_skill_installed_version_without_version(isolated_home: Path):
    _write_skill(cfg.get_skills_dir(), "no-ver")
    v = _skill_installed_version(cfg.get_skills_dir() / "no-ver")
    assert v is None


def test_skill_installed_version_missing_dir(isolated_home: Path):
    v = _skill_installed_version(cfg.get_skills_dir() / "nonexistent")
    assert v is None


# ── check_versions ──────────────────────────────────────────────────────


def test_check_versions_returns_registered_skills(isolated_home: Path):
    _register_skill("alpha", "1.0")
    _register_skill("beta", "2.0")
    results = check_versions()
    names = [r.name for r in results]
    assert "alpha" in names
    assert "beta" in names


def test_check_versions_installed_matches(isolated_home: Path):
    _register_skill("my-skill", "3.1")
    results = check_versions()
    mine = next(r for r in results if r.name == "my-skill")
    assert mine.installed == "3.1"
    assert mine.category == "skill"


def test_check_versions_no_source_latest_is_none(isolated_home: Path):
    _register_skill("no-source", "1.0")
    results = check_versions()
    mine = next(r for r in results if r.name == "no-source")
    assert mine.latest is None
    assert mine.source is None


def test_check_versions_empty_store(isolated_home: Path):
    _init_store()
    results = check_versions()
    assert results == []


# ── get_latest_github_tag ───────────────────────────────────────────────


def test_get_latest_github_tag_offline_returns_none():
    """When git ls-remote fails (network), return None instead of raising."""
    with patch("ai_adapter.version._run_git", side_effect=GitError("network error")):
        result = get_latest_github_tag("user/repo")
        assert result is None


def test_get_latest_github_tag_parses_tags():
    """Parse multiple tags and return the latest (first v* found, sorted by git)."""
    # git --sort=-v:refname returns highest version first.
    mock_result = type(
        "Result",
        (),
        {
            "stdout": "def456\trefs/tags/v2.0\nabc123\trefs/tags/v1.0\n",
        },
    )()
    with patch("ai_adapter.version._run_git", return_value=mock_result):
        result = get_latest_github_tag("user/repo")
        assert result == "v2.0"


def test_get_latest_github_tag_skips_annotated_deref():
    """Annotated tag derefs (v1.0^{}) should be skipped."""
    mock_result = type(
        "Result",
        (),
        {
            "stdout": "ghi789\trefs/tags/v2.0\nabc123\trefs/tags/v1.0\ndef456\trefs/tags/v1.0^{}\n",
        },
    )()
    with patch("ai_adapter.version._run_git", return_value=mock_result):
        result = get_latest_github_tag("user/repo")
        assert result == "v2.0"


def test_get_latest_github_tag_no_v_prefix():
    """Tags without v prefix are skipped."""
    mock_result = type(
        "Result",
        (),
        {
            "stdout": "abc123\trefs/tags/1.0\ndef456\trefs/tags/2.0\n",
        },
    )()
    with patch("ai_adapter.version._run_git", return_value=mock_result):
        result = get_latest_github_tag("user/repo")
        assert result is None


def test_get_latest_github_tag_empty_output():
    """Empty output returns None."""
    mock_result = type("Result", (), {"stdout": ""})()
    with patch("ai_adapter.version._run_git", return_value=mock_result):
        result = get_latest_github_tag("user/repo")
        assert result is None


# ── render_version_table ────────────────────────────────────────────────


def test_render_version_table_empty():
    output = render_version_table([])
    assert output == "No skills registered."


def test_render_version_table_with_skills():
    versions = [
        VersionInfo(name="alpha", category="skill", installed="1.0", latest=None, source=None),
        VersionInfo(name="beta", category="skill", installed="2.0", latest="3.0", source="github:u/r"),
    ]
    output = render_version_table(versions)
    assert "alpha" in output
    assert "beta" in output
    assert "1.0" in output
    assert "3.0" in output
    assert "1 update(s) available" in output


def test_render_version_table_all_up_to_date():
    versions = [
        VersionInfo(name="alpha", category="skill", installed="1.0", latest="1.0", source=None),
    ]
    output = render_version_table(versions)
    assert "All skills are up to date" in output
