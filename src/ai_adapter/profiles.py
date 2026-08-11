"""Profile and Pack data definitions.

Provides dataclasses for Profile, Pack, and MCPServerSpec, along with
YAML loading utilities and skill-source resolution.

Profile YAML files live in:
  - Standard (bundled):  ``src/ai_adapter/profiles/*.yaml``
  - User (override):     ``~/.ai-adapter/profiles/*.yaml``

Pack YAML files live in:
  - Standard (bundled):  ``src/ai_adapter/packs/*.yaml``
  - User (override):     ``~/.ai-adapter/packs/*.yaml``

Resolution order: user > standard (later wins).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import click
import yaml

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class MCPServerSpec:
    """Lightweight MCP server definition inside a Profile."""

    name: str
    command: str
    args: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"name": self.name, "command": self.command}
        if self.args:
            d["args"] = self.args
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MCPServerSpec:
        return cls(
            name=data["name"],
            command=data["command"],
            args=data.get("args", []),
        )


@dataclass
class Profile:
    """A named preset that bundles skills, MCP servers, agents, and commands."""

    name: str
    description: str = ""
    skills: list[str] = field(default_factory=list)
    mcp: list[MCPServerSpec] = field(default_factory=list)
    agents: list[str] = field(default_factory=list)
    commands: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"name": self.name}
        if self.description:
            d["description"] = self.description
        if self.skills:
            d["skills"] = self.skills
        if self.mcp:
            d["mcp"] = [m.to_dict() for m in self.mcp]
        if self.agents:
            d["agents"] = self.agents
        if self.commands:
            d["commands"] = self.commands
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Profile:
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            skills=data.get("skills", []),
            mcp=[MCPServerSpec.from_dict(m) for m in data.get("mcp", [])],
            agents=data.get("agents", []),
            commands=data.get("commands", []),
        )


@dataclass
class Pack:
    """A named collection of profiles applied in order."""

    name: str
    description: str = ""
    profiles: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"name": self.name}
        if self.description:
            d["description"] = self.description
        if self.profiles:
            d["profiles"] = self.profiles
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Pack:
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            profiles=data.get("profiles", []),
        )


# ---------------------------------------------------------------------------
# YAML helpers
# ---------------------------------------------------------------------------

_KNOWN_PROFILE_KEYS = {"name", "description", "skills", "mcp", "agents", "commands"}
_KNOWN_PACK_KEYS = {"name", "description", "profiles"}


def _load_yaml_file(path: Path) -> dict[str, Any]:
    """Parse a single YAML file and return its contents as a dict.

    Raises ``click.ClickException`` on parse errors so the user gets a
    clear, actionable message.
    """
    try:
        raw = path.read_text(encoding="utf-8")
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise click.ClickException(f"YAML parse error in {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise click.ClickException(f"Expected a YAML mapping in {path}, got {type(data).__name__}")
    return data


def _warn_unknown_keys(path: Path, data: dict, known: set[str]) -> None:
    """Emit a warning for every unexpected key in *data*."""
    unknown = set(data.keys()) - known
    for key in sorted(unknown):
        logger.warning("Unknown key '%s' in %s (ignored)", key, path)


# ---------------------------------------------------------------------------
# Profile loading
# ---------------------------------------------------------------------------


def load_profiles(profile_dirs: list[Path]) -> dict[str, Profile]:
    """Load all ``*.yaml`` files from *profile_dirs* into a name→Profile map.

    Later directories override earlier ones (user > standard).
    """
    profiles: dict[str, Profile] = {}
    for profile_dir in profile_dirs:
        if not profile_dir.is_dir():
            continue
        for yaml_path in sorted(profile_dir.glob("*.yaml")):
            data = _load_yaml_file(yaml_path)
            _warn_unknown_keys(yaml_path, data, _KNOWN_PROFILE_KEYS)
            if "name" not in data:
                logger.warning("Profile YAML %s missing 'name' key (skipped)", yaml_path)
                continue
            profile = Profile.from_dict(data)
            profiles[profile.name] = profile
    return profiles


# ---------------------------------------------------------------------------
# Pack loading
# ---------------------------------------------------------------------------


def load_packs(pack_dirs: list[Path]) -> dict[str, Pack]:
    """Load all ``*.yaml`` files from *pack_dirs* into a name→Pack map.

    Later directories override earlier ones (user > standard).
    """
    packs: dict[str, Pack] = {}
    for pack_dir in pack_dirs:
        if not pack_dir.is_dir():
            continue
        for yaml_path in sorted(pack_dir.glob("*.yaml")):
            data = _load_yaml_file(yaml_path)
            _warn_unknown_keys(yaml_path, data, _KNOWN_PACK_KEYS)
            if "name" not in data:
                logger.warning("Pack YAML %s missing 'name' key (skipped)", yaml_path)
                continue
            pack = Pack.from_dict(data)
            packs[pack.name] = pack
    return packs


# ---------------------------------------------------------------------------
# Skill-source resolution
# ---------------------------------------------------------------------------

# Resolve order (task 2-1 AC2):
#   1. Already installed:  ~/.ai-adapter/skills/<name>/
#   2. Bundled:            src/ai_adapter/bundled/<name>/
#   3. None (caller decides whether to error or skip)


def resolve_skill_source(name: str) -> Path | None:
    """Resolve a skill name to a filesystem path.

    Resolution order:
      1. Installed skill directory  (``~/.ai-adapter/skills/<name>/``)
      2. Bundled skill directory    (``src/ai_adapter/bundled/<name>/``)

    Returns ``None`` when the skill cannot be found anywhere.

    Note:
        ``skill install`` (task 2-5) is *not* called automatically here.
        The caller is responsible for deciding how to handle unresolvable
        names (e.g. calling ``skill install`` or printing an error).
    """
    from ai_adapter import config as _cfg

    # 1. Installed (read AI_ADAPTER_DIR at call time to respect monkeypatching)
    installed = _cfg.AI_ADAPTER_DIR / "skills" / name
    if installed.is_dir():
        return installed

    # 2. Bundled (next to this file)
    bundled = Path(__file__).parent / "bundled" / name
    if bundled.is_dir():
        return bundled

    return None
