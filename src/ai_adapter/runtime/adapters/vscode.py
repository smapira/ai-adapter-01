"""VS Code Runtime Adapter — observes agent sessions via process fallback.

Distinct from :mod:`ai_adapter.providers.vscode` (Configuration Plane:
settings/MCP export). This adapter only *reads* runtime state and never
changes VS Code settings or extensions.

P0-Spike (2026-10-07) findings:

- ``code --status`` exposes process/GPU diagnostics only — no session API.
- ``code --list-extensions`` lists extensions, not running sessions.
- Process observation reaches VS Code-hosted agents:
  - extension-hosted agents (``codex`` under ``.vscode/extensions/``)
  - SDK runtimes (``copilot-runtime`` under the VS Code app bundle)
  - terminal-spawned agents (``opencode --session …`` under the VS Code tree)

Fallback path therefore uses ``ps`` + ancestor attribution. Process existence
never implies WORKING / WAITING / DONE (design §4.4): sessions report
``status=unknown``, ``source=process``, ``confidence=low`` until an official
session API becomes available.
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

HOST_NAME = "vscode"

#: App-bundle marker for VS Code processes (macOS).
HOST_MARKER = "Visual Studio Code.app"

#: Direct attribution marker for extension-hosted agent binaries.
EXTENSION_MARKER = ".vscode/extensions/"


class VSCodeAdapter(RuntimeAdapter):
    """Discover VS Code agent sessions through process observation."""

    @property
    def host_name(self) -> str:
        return HOST_NAME

    def is_available(self) -> bool:
        """Available when the ``code`` CLI exists or VS Code is running."""
        if shutil.which("code") is not None:
            return True
        return any(HOST_MARKER in process.command for process in observe_processes())

    def discover(self) -> list[RuntimeSession]:
        """Discover VS Code-hosted agent processes. Never raises."""
        try:
            processes = observe_processes()
            agents = find_host_agent_processes(processes, HOST_MARKER, EXTENSION_MARKER)
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
        # Process fallback: identity is reliable, activity/status are not.
        return RuntimeCapabilities(
            host=HOST_NAME,
            discover="PARTIAL",
            project="PARTIAL",
            agent="YES",
            activity="NO",
            working="NO",
            waiting="NO",
            done="NO",
            needs_user="NO",
        )
