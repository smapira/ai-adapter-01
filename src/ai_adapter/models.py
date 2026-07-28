"""Data model definition module.

Provides dataclasses for Agent, Env, AgentBinding, Bin, Skill, MCPServer, Config
and their to_dict / from_dict methods for JSON serialization.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Agent:
    name: str
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"name": self.name}
        if self.description:
            d["description"] = self.description
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Agent:
        return cls(
            name=data["name"],
            description=data.get("description", ""),
        )


@dataclass
class Env:
    name: str
    description: str = ""
    is_default: bool = False

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"name": self.name}
        if self.description:
            d["description"] = self.description
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Env:
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            is_default=data.get("is_default", False),
        )


@dataclass
class AgentBinding:
    agent: str
    env: str

    def to_dict(self) -> dict[str, Any]:
        return {"agent": self.agent, "env": self.env}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentBinding:
        return cls(
            agent=data["agent"],
            env=data["env"],
        )


@dataclass
class Bin:
    name: str
    env: str | None = None
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"name": self.name}
        if self.env:
            d["env"] = self.env
        if self.description:
            d["description"] = self.description
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Bin:
        return cls(
            name=data["name"],
            env=data.get("env"),
            description=data.get("description", ""),
        )


@dataclass
class Skill:
    name: str
    description: str = ""
    path: str = ""
    tags: list[str] = field(default_factory=list)
    agent: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"name": self.name}
        if self.description:
            d["description"] = self.description
        if self.path:
            d["path"] = self.path
        if self.tags:
            d["tags"] = self.tags
        if self.agent:
            d["agent"] = self.agent
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Skill:
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            path=data.get("path", ""),
            tags=data.get("tags", []),
            agent=data.get("agent"),
        )


@dataclass
class Command:
    name: str
    description: str = ""
    content: str = ""

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"name": self.name}
        if self.description:
            d["description"] = self.description
        if self.content:
            d["content"] = self.content
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Command:
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            content=data.get("content", ""),
        )


@dataclass
class Prompt:
    name: str
    description: str = ""
    content: str = ""

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"name": self.name}
        if self.description:
            d["description"] = self.description
        if self.content:
            d["content"] = self.content
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Prompt:
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            content=data.get("content", ""),
        )


@dataclass
class Instruction:
    name: str
    description: str = ""
    content: str = ""

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"name": self.name}
        if self.description:
            d["description"] = self.description
        if self.content:
            d["content"] = self.content
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Instruction:
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            content=data.get("content", ""),
        )


@dataclass
class MCPServer:
    name: str
    command: str
    args: list[str] = field(default_factory=list)
    env_keys: list[str] = field(default_factory=list)
    enabled: bool = True
    tools: list[str] = field(default_factory=list)
    env: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"name": self.name, "command": self.command}
        if self.args:
            d["args"] = self.args
        if self.env_keys:
            d["env_keys"] = self.env_keys
        d["enabled"] = self.enabled
        if self.tools:
            d["tools"] = self.tools
        if self.env:
            d["env"] = self.env
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MCPServer:
        return cls(
            name=data["name"],
            command=data["command"],
            args=data.get("args", []),
            env_keys=data.get("env_keys", []),
            enabled=data.get("enabled", True),
            tools=data.get("tools", []),
            env=data.get("env"),
        )


def _ensure_list(data: dict[str, Any], key: str) -> list:
    """Get a list field from *data*, validating it is a list."""
    val = data.get(key, [])
    if not isinstance(val, list):
        raise ValueError(f"{key} must be a list, got {type(val).__name__}")
    return val


@dataclass
class Config:
    version: int = 1
    agents: list[Agent] = field(default_factory=list)
    envs: list[Env] = field(default_factory=list)
    bins: list[Bin] = field(default_factory=list)
    skills: list[Skill] = field(default_factory=list)
    commands: list[Command] = field(default_factory=list)
    prompts: list[Prompt] = field(default_factory=list)
    instructions: list[Instruction] = field(default_factory=list)
    mcp_servers: list[MCPServer] = field(default_factory=list)
    default_env: str = "default"
    agent_bindings: list[AgentBinding] = field(default_factory=list)
    remote: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "version": self.version,
            "default_env": self.default_env,
            "agent_bindings": [b.to_dict() for b in self.agent_bindings],
            "agents": [a.to_dict() for a in self.agents],
            "envs": [e.to_dict() for e in self.envs],
            "bins": [b.to_dict() for b in self.bins],
        }
        if self.skills:
            d["skills"] = [s.to_dict() for s in self.skills]
        if self.commands:
            d["commands"] = [c.to_dict() for c in self.commands]
        if self.prompts:
            d["prompts"] = [p.to_dict() for p in self.prompts]
        if self.instructions:
            d["instructions"] = [i.to_dict() for i in self.instructions]
        if self.mcp_servers:
            d["mcp_servers"] = [m.to_dict() for m in self.mcp_servers]
        if self.remote:
            d["remote"] = self.remote
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Config:
        """Create Config object from config data.

        Raises:
            ValueError: If the data types are invalid.
        """
        if not isinstance(data, dict):
            raise ValueError("Invalid config format: must be a dict")

        version = data.get("version", 1)
        if not isinstance(version, int):
            raise ValueError(f"version must be an integer: {version}")

        default_env = data.get("default_env", "default")
        if not isinstance(default_env, str):
            raise ValueError(f"default_env must be a string: {default_env}")

        return cls(
            version=version,
            default_env=default_env,
            agent_bindings=[AgentBinding.from_dict(b) for b in _ensure_list(data, "agent_bindings")],
            agents=[Agent.from_dict(a) for a in _ensure_list(data, "agents")],
            envs=[Env.from_dict(e) for e in _ensure_list(data, "envs")],
            bins=[Bin.from_dict(b) for b in _ensure_list(data, "bins")],
            skills=[Skill.from_dict(s) for s in _ensure_list(data, "skills")],
            commands=[Command.from_dict(c) for c in _ensure_list(data, "commands")],
            prompts=[Prompt.from_dict(p) for p in _ensure_list(data, "prompts")],
            instructions=[Instruction.from_dict(i) for i in _ensure_list(data, "instructions")],
            mcp_servers=[MCPServer.from_dict(m) for m in _ensure_list(data, "mcp_servers")],
            remote=data.get("remote"),
        )
