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
    commands: list[Command] = field(default_factory=list)
    prompts: list[Prompt] = field(default_factory=list)
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
        if self.mcp_servers:
            d["mcp_servers"] = [m.to_dict() for m in self.mcp_servers]
        if self.remote:
            d["remote"] = self.remote
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Config:
        """設定ファイルから Config オブジェクトを生成する。

        Raises:
            ValueError: データの型が不正な場合。
        """
        if not isinstance(data, dict):
            raise ValueError("Invalid config format: must be a dict")

        # version のバリデーション
        version = data.get("version", 1)
        if not isinstance(version, int):
            raise ValueError(f"version must be an integer: {version}")

        # default_env のバリデーション
        default_env = data.get("default_env", "default")
        if not isinstance(default_env, str):
            raise ValueError(f"default_env must be a string: {default_env}")

        # 各リストフィールドのバリデーション
        agents_data = data.get("agents", [])
        if not isinstance(agents_data, list):
            raise ValueError(f"agents must be a list")

        envs_data = data.get("envs", [])
        if not isinstance(envs_data, list):
            raise ValueError(f"envs must be a list")

        bins_data = data.get("bins", [])
        if not isinstance(bins_data, list):
            raise ValueError(f"bins must be a list")

        skills_data = data.get("skills", [])
        if not isinstance(skills_data, list):
            raise ValueError(f"skills must be a list")

        commands_data = data.get("commands", [])
        if not isinstance(commands_data, list):
            raise ValueError(f"commands must be a list")

        prompts_data = data.get("prompts", [])
        if not isinstance(prompts_data, list):
            raise ValueError(f"prompts must be a list")

        mcp_servers_data = data.get("mcp_servers", [])
        if not isinstance(mcp_servers_data, list):
            raise ValueError(f"mcp_servers must be a list")

        agent_bindings_data = data.get("agent_bindings", [])
        if not isinstance(agent_bindings_data, list):
            raise ValueError(f"agent_bindings must be a list")

        return cls(
            version=version,
            default_env=default_env,
            agent_bindings=[
                AgentBinding.from_dict(b)
                for b in agent_bindings_data
            ],
            agents=[Agent.from_dict(a) for a in agents_data],
            envs=[Env.from_dict(e) for e in envs_data],
            bins=[Bin.from_dict(b) for b in bins_data],
            skills=[Skill.from_dict(s) for s in skills_data],
            commands=[Command.from_dict(c) for c in commands_data],
            prompts=[Prompt.from_dict(p) for p in prompts_data],
            mcp_servers=[MCPServer.from_dict(m) for m in mcp_servers_data],
            remote=data.get("remote"),
        )
