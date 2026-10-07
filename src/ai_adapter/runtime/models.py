"""Canonical Runtime Model for Runtime Monitoring (Runtime Plane).

Defines the host-agnostic session model observed by ``ai-adapter monitor``.
All host adapters convert their raw host data into these types; host-specific
fields never leak into this module.

Distinct from :mod:`ai_adapter.models` (Configuration Plane data model).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class RuntimeStatus(str, Enum):
    """Canonical status values. Serialization uses lowercase."""

    WORKING = "working"
    WAITING = "waiting"
    BLOCKED = "blocked"
    DONE = "done"
    IDLE = "idle"
    UNKNOWN = "unknown"


class RuntimeConfidence(str, Enum):
    """Observation confidence derived from the observation source."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RuntimeSource(str, Enum):
    """Canonical observation-source vocabulary."""

    HOOK = "hook"
    CLI = "cli"
    API = "api"
    ACP = "acp"
    METADATA = "metadata"
    TERMINAL = "terminal"
    FILE = "file"
    PROCESS = "process"
    HEURISTIC = "heuristic"


@dataclass
class RuntimeSession:
    """One observed agent session on one host.

    ``session_id`` is host-scoped: external integrations should key on the
    ``(host, session_id)`` pair.
    """

    session_id: str
    host: str
    agent: str
    project: str
    workspace: str
    status: RuntimeStatus
    source: RuntimeSource
    confidence: RuntimeConfidence
    activity: str = ""
    needs_user: bool | None = None
    started_at: datetime | None = None
    last_activity_at: datetime | None = None


@dataclass
class RuntimeCapabilities:
    """What a host adapter can observe, declared honestly.

    Values are ``YES`` / ``PARTIAL`` / ``NO`` / ``UNKNOWN``. When the host
    is not installed the adapter still returns a declaration (all ``NO``)
    rather than raising.
    """

    host: str
    discover: str
    project: str
    agent: str
    activity: str
    working: str
    waiting: str
    done: str
    needs_user: str
