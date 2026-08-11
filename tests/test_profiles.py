"""Tests for profiles.py — Profile/Pack data classes and YAML loading."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from ai_adapter.profiles import (
    MCPServerSpec,
    Pack,
    Profile,
    load_packs,
    load_profiles,
    resolve_skill_source,
)

# ---------------------------------------------------------------------------
# MCPServerSpec
# ---------------------------------------------------------------------------


class TestMCPServerSpec:
    def test_from_dict_minimal(self):
        spec = MCPServerSpec.from_dict({"name": "github", "command": "npx"})
        assert spec.name == "github"
        assert spec.command == "npx"
        assert spec.args == []

    def test_from_dict_with_args(self):
        spec = MCPServerSpec.from_dict(
            {"name": "pw", "command": "npx", "args": ["@modelcontextprotocol/server-playwright"]}
        )
        assert spec.args == ["@modelcontextprotocol/server-playwright"]

    def test_to_dict_roundtrip(self):
        spec = MCPServerSpec(name="x", command="echo", args=["a", "b"])
        d = spec.to_dict()
        assert d == {"name": "x", "command": "echo", "args": ["a", "b"]}
        restored = MCPServerSpec.from_dict(d)
        assert restored == spec

    def test_to_dict_omits_empty_args(self):
        spec = MCPServerSpec(name="x", command="echo")
        d = spec.to_dict()
        assert "args" not in d


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------


class TestProfile:
    def test_from_dict_minimal(self):
        p = Profile.from_dict({"name": "test"})
        assert p.name == "test"
        assert p.description == ""
        assert p.skills == []
        assert p.mcp == []
        assert p.agents == []
        assert p.commands == []

    def test_from_dict_full(self):
        data = {
            "name": "web-dev",
            "description": "Web development",
            "skills": ["frontend", "react"],
            "mcp": [{"name": "gh", "command": "npx"}],
            "agents": ["reviewer"],
            "commands": ["deploy"],
        }
        p = Profile.from_dict(data)
        assert p.name == "web-dev"
        assert p.description == "Web development"
        assert p.skills == ["frontend", "react"]
        assert len(p.mcp) == 1
        assert p.mcp[0].name == "gh"
        assert p.agents == ["reviewer"]
        assert p.commands == ["deploy"]

    def test_to_dict_roundtrip(self):
        p = Profile(
            name="a",
            description="desc",
            skills=["s1"],
            mcp=[MCPServerSpec(name="m1", command="c1")],
            agents=["ag1"],
            commands=["cmd1"],
        )
        d = p.to_dict()
        restored = Profile.from_dict(d)
        assert restored == p

    def test_to_dict_omits_empty_fields(self):
        p = Profile(name="minimal")
        d = p.to_dict()
        assert d == {"name": "minimal"}


# ---------------------------------------------------------------------------
# Pack
# ---------------------------------------------------------------------------


class TestPack:
    def test_from_dict_minimal(self):
        pk = Pack.from_dict({"name": "my-pack"})
        assert pk.name == "my-pack"
        assert pk.description == ""
        assert pk.profiles == []

    def test_from_dict_full(self):
        pk = Pack.from_dict({"name": "full", "description": "A pack", "profiles": ["p1", "p2"]})
        assert pk.profiles == ["p1", "p2"]

    def test_to_dict_roundtrip(self):
        pk = Pack(name="x", description="y", profiles=["a", "b"])
        d = pk.to_dict()
        restored = Pack.from_dict(d)
        assert restored == pk


# ---------------------------------------------------------------------------
# load_profiles
# ---------------------------------------------------------------------------


class TestLoadProfiles:
    def test_loads_from_single_dir(self, tmp_path: Path):
        profile_dir = tmp_path / "profiles"
        profile_dir.mkdir()
        (profile_dir / "dev.yaml").write_text(
            yaml.dump({"name": "dev", "description": "Dev profile", "skills": ["s1"]})
        )
        profiles = load_profiles([profile_dir])
        assert "dev" in profiles
        assert profiles["dev"].skills == ["s1"]

    def test_user_overrides_standard(self, tmp_path: Path):
        std = tmp_path / "std"
        std.mkdir()
        (std / "web.yaml").write_text(yaml.dump({"name": "web", "skills": ["std-skill"]}))
        user = tmp_path / "user"
        user.mkdir()
        (user / "web.yaml").write_text(yaml.dump({"name": "web", "skills": ["user-skill"]}))
        profiles = load_profiles([std, user])
        assert profiles["web"].skills == ["user-skill"]

    def test_skips_missing_dir(self):
        profiles = load_profiles([Path("/nonexistent")])
        assert profiles == {}

    def test_skips_nameless_yaml(self, tmp_path: Path):
        d = tmp_path / "p"
        d.mkdir()
        (d / "bad.yaml").write_text(yaml.dump({"description": "no name"}))
        profiles = load_profiles([d])
        assert profiles == {}

    def test_invalid_yaml_raises_click_exception(self, tmp_path: Path):
        d = tmp_path / "p"
        d.mkdir()
        (d / "bad.yaml").write_text("{{invalid yaml")
        import click

        with pytest.raises(click.ClickException, match="YAML parse error"):
            load_profiles([d])


# ---------------------------------------------------------------------------
# load_packs
# ---------------------------------------------------------------------------


class TestLoadPacks:
    def test_loads_packs(self, tmp_path: Path):
        pack_dir = tmp_path / "packs"
        pack_dir.mkdir()
        (pack_dir / "starter.yaml").write_text(yaml.dump({"name": "starter", "profiles": ["web-dev"]}))
        packs = load_packs([pack_dir])
        assert "starter" in packs
        assert packs["starter"].profiles == ["web-dev"]

    def test_user_overrides_standard(self, tmp_path: Path):
        std = tmp_path / "std"
        std.mkdir()
        (std / "p.yaml").write_text(yaml.dump({"name": "p", "profiles": ["std-only"]}))
        user = tmp_path / "user"
        user.mkdir()
        (user / "p.yaml").write_text(yaml.dump({"name": "p", "profiles": ["user-p"]}))
        packs = load_packs([std, user])
        assert packs["p"].profiles == ["user-p"]


# ---------------------------------------------------------------------------
# resolve_skill_source
# ---------------------------------------------------------------------------


class TestResolveSkillSource:
    def test_returns_none_when_not_found(self):
        result = resolve_skill_source("totally-nonexistent-skill-xyz")
        assert result is None

    def test_finds_bundled_skill(self, monkeypatch: pytest.MonkeyPatch):
        """If a bundled skill directory exists, resolve_skill_source returns it."""

        bundled_base = Path(__file__).resolve().parent.parent / "src" / "ai_adapter" / "bundled"
        test_skill = bundled_base / "test-bundled-skill"
        test_skill.mkdir(parents=True, exist_ok=True)
        try:
            result = resolve_skill_source("test-bundled-skill")
            assert result is not None
            assert result.name == "test-bundled-skill"
        finally:
            import shutil

            shutil.rmtree(test_skill, ignore_errors=True)
