"""Zed Runtime Adapter — observes agent sessions via process fallback.

Distinct from :mod:`ai_adapter.providers.zed` (Configuration Plane:
settings export). This adapter only *reads* runtime state and never changes
Zed configuration.

P0-Spike (2026-10-07) findings:

- ``zed --help`` exposes no status/session subcommands (open/wait/add only).
- ``~/.config/zed/conversations/`` was empty; no thread metadata surface found.
- ACP (Agent Client Protocol) is the designed first choice for Zed agents
  (design §4.3) but is not reachable from the CLI in the PoC scope.
- Process observation reaches Zed-terminal-spawned external agents
  (``claude`` / ``codex`` / ``opencode`` under the ``Zed.app`` tree).

The ACP gap is itself a PoC result (design §4.3): sessions discovered via
fallback report ``status=unknown``, ``source=process``, ``confidence=low``.
Zed's built-in agent is not separable via process observation, so the
``agent`` capability is declared PARTIAL.
"""

from __future__ import annotations

import shutil

from ai_adapter.runtime.adapters.base import (
    RuntimeAdapter,
    find_host_agent_processes,
    observe_processes,
    session_from_process,
    unavailable_capabilities,
)
from ai_adapter.runtime.models import RuntimeCapabilities, RuntimeSession

HOST_NAME = "zed"

#: App-bundle marker for Zed processes (macOS).
HOST_MARKER = "Zed.app"


class ZedAdapter(RuntimeAdapter):
    """Discover Zed agent sessions through process observation."""

    @property
    def host_name(self) -> str:
        return HOST_NAME

    def is_available(self) -> bool:
        """Available when the ``zed`` CLI exists or Zed is running."""
        if shutil.which("zed") is not None:
            return True
        return any(HOST_MARKER in process.command for process in observe_processes())

    def discover(self) -> list[RuntimeSession]:
        """Discover Zed-terminal-spawned agent processes. Never raises."""
        try:
            processes = observe_processes()
            agents = find_host_agent_processes(processes, HOST_MARKER)
            return [session_from_process(HOST_NAME, process) for process in agents]
        except Exception:
            return []

    def inspect(self, session_id: str) -> RuntimeSession | None:
        for session in self.discover():
            if session.session_id == session_id:
                return session
        return None

    def capabilities(self) -> RuntimeCapabilities:
        if not self.is_available():
            return unavailable_capabilities(HOST_NAME)
        # ACP is unreachable in the PoC; Zed's built-in agent is not
        # separable via process observation → agent PARTIAL.
        return RuntimeCapabilities(
            host=HOST_NAME,
            discover="PARTIAL",
            project="PARTIAL",
            agent="PARTIAL",
            activity="NO",
            working="NO",
            waiting="NO",
            done="NO",
            needs_user="NO",
        )
