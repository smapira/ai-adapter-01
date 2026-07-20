"""データモデル定義モジュール。

Agent, Env, AgentBinding, Bin, Config の dataclass と
YAML シリアライズのための to_dict / from_dict メソッドを提供する。
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
class Config:
    version: int = 1
    agents: list[Agent] = field(default_factory=list)
    envs: list[Env] = field(default_factory=list)
    bins: list[Bin] = field(default_factory=list)
    default_env: str = "default"
    agent_bindings: list[AgentBinding] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "default_env": self.default_env,
            "agent_bindings": [b.to_dict() for b in self.agent_bindings],
            "agents": [a.to_dict() for a in self.agents],
            "envs": [e.to_dict() for e in self.envs],
            "bins": [b.to_dict() for b in self.bins],
        }

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
        )
