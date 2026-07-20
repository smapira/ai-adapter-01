"""データモデル定義モジュール。

Agent, Env, AgentBinding, Bin, Skill, MCPServer, Config の dataclass と
JSON シリアライズのための to_dict / from_dict メソッドを提供する。
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


@dataclass
class Config:
    version: int = 1
    agents: list[Agent] = field(default_factory=list)
    envs: list[Env] = field(default_factory=list)
    bins: list[Bin] = field(default_factory=list)
    skills: list[Skill] = field(default_factory=list)
    mcp_servers: list[MCPServer] = field(default_factory=list)
    default_env: str = "default"
    agent_bindings: list[AgentBinding] = field(default_factory=list)

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
        if self.mcp_servers:
            d["mcp_servers"] = [m.to_dict() for m in self.mcp_servers]
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Config:
        return cls(
            version=data.get("version", 1),
            default_env=data.get("default_env", "default"),
            agent_bindings=[
                AgentBinding.from_dict(b)
                for b in data.get("agent_bindings", [])
            ],
            agents=[Agent.from_dict(a) for a in data.get("agents", [])],
            envs=[Env.from_dict(e) for e in data.get("envs", [])],
            bins=[Bin.from_dict(b) for b in data.get("bins", [])],
            skills=[Skill.from_dict(s) for s in data.get("skills", [])],
            mcp_servers=[MCPServer.from_dict(m) for m in data.get("mcp_servers", [])],
        )
