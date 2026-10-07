"""Orca Runtime Adapter — observes agent sessions via the official Orca CLI.

Distinct from any Configuration Plane code: this adapter only *reads* Orca
state. It never creates worktrees, never sends input to agents, and never
modifies Orca settings.

Observation priority (design §4.1): official CLI JSON first. P0-Spike
(2026-10-07, verified live) confirmed:

- ``orca terminal list --json`` → ``result.terminals[]`` with ``handle``,
  ``worktreePath``, ``agentIdentity``, ``lastOutputAt`` (epoch ms), ``preview``
- ``orca worktree ps --json`` → ``result.worktrees[]`` with ``repo``, ``path``,
  ``workspaceStatus``, ``lastActivityAt`` (epoch ms) and ``agents[]``
  (``agentType``, ``state``, ``stateStartedAt``, ``updatedAt``, ``taskTitle``)

Both surfaces feed the Canonical Model with ``source=cli`` / ``confidence=high``.
Agent state vocabulary beyond what Orca reports is never guessed: an unmapped
or missing state yields ``UNKNOWN`` (design §2.4).
"""

from __future__ import annotations

import shutil

from ai_adapter.runtime.adapters.base import (
    DEFAULT_TIMEOUT_SECONDS,
    RuntimeAdapter,
    parse_json_payload,
    run_host_command,
    unavailable_capabilities,
)
from ai_adapter.runtime.models import (
    RuntimeCapabilities,
    RuntimeSession,
    RuntimeSource,
    RuntimeStatus,
)
from ai_adapter.runtime.normalizer import (
    confidence_for_source,
    epoch_millis_to_datetime,
    normalize_agent,
    project_name,
)

HOST_NAME = "orca"

#: Orca ``agents[].state`` → canonical status. Unmapped values → UNKNOWN.
ORCA_STATE_MAP: dict[str, RuntimeStatus] = {
    "working": RuntimeStatus.WORKING,
    "in_progress": RuntimeStatus.WORKING,
    "in-progress": RuntimeStatus.WORKING,
    "running": RuntimeStatus.WORKING,
    "waiting": RuntimeStatus.WAITING,
    "needs_input": RuntimeStatus.WAITING,
    "paused": RuntimeStatus.WAITING,
    "blocked": RuntimeStatus.BLOCKED,
    "error": RuntimeStatus.BLOCKED,
    "failed": RuntimeStatus.BLOCKED,
    "done": RuntimeStatus.DONE,
    "completed": RuntimeStatus.DONE,
    "finished": RuntimeStatus.DONE,
    "idle": RuntimeStatus.IDLE,
}


def agent_state_status(entry: dict | None) -> RuntimeStatus:
    """Map an Orca agent entry's state to a canonical status.

    Missing or unrecognized state → UNKNOWN (never guessed).
    """
    if not entry:
        return RuntimeStatus.UNKNOWN
    state = str(entry.get("state") or "").strip().lower()
    return ORCA_STATE_MAP.get(state, RuntimeStatus.UNKNOWN)


def find_agent_entry(worktree: dict | None, agent: str) -> dict | None:
    """Find the agent entry matching ``agent`` inside a worktree's agents[]."""
    if not worktree:
        return None
    for entry in worktree.get("agents") or []:
        if isinstance(entry, dict) and normalize_agent(str(entry.get("agentType") or "")) == agent:
            return entry
    return None


class OrcaAdapter(RuntimeAdapter):
    """Discover Orca agent sessions through the official CLI JSON surfaces."""

    def __init__(self, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> None:
        self._timeout = timeout

    @property
    def host_name(self) -> str:
        return HOST_NAME

    def is_available(self) -> bool:
        return shutil.which("orca") is not None

    def discover(self) -> list[RuntimeSession]:
        """Merge terminal-list and worktree-ps data into sessions. Never raises."""
        try:
            terminals = self._fetch_terminals()
            worktrees = self._fetch_worktrees()
            return self._merge_sessions(terminals, worktrees)
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
        # Official CLI JSON exposes agent identity, workspace, agent state and
        # activity timestamps; needs_user has no dedicated field yet (P4).
        return RuntimeCapabilities(
            host=HOST_NAME,
            discover="YES",
            project="YES",
            agent="YES",
            activity="YES",
            working="YES",
            waiting="YES",
            done="YES",
            needs_user="UNKNOWN",
        )

    # --- data fetching ------------------------------------------------------

    def _fetch_result(self, argv: list[str]) -> dict | None:
        """Run one Orca CLI command and return its ``result`` object.

        A failed, timed-out, or malformed response degrades to ``None`` —
        the CLI layer never sees an exception.
        """
        result = run_host_command(argv, timeout=self._timeout)
        return parse_json_payload(result)

    def _fetch_terminals(self) -> list[dict]:
        payload = self._fetch_result(["orca", "terminal", "list", "--json"])
        terminals = payload.get("terminals") if payload else None
        return [t for t in terminals if isinstance(t, dict)] if isinstance(terminals, list) else []

    def _fetch_worktrees(self) -> list[dict]:
        payload = self._fetch_result(["orca", "worktree", "ps", "--json"])
        worktrees = payload.get("worktrees") if payload else None
        return [w for w in worktrees if isinstance(w, dict)] if isinstance(worktrees, list) else []

    # --- raw → Canonical ----------------------------------------------------

    def _merge_sessions(self, terminals: list[dict], worktrees: list[dict]) -> list[RuntimeSession]:
        """Build sessions from terminals, enriched by worktree agent state.

        Terminals carrying an ``agentIdentity`` become sessions; matching
        worktree agent entries enrich status/activity/timestamps. Agent
        entries without a live terminal still count as existing sessions.
        """
        worktree_by_path = {str(w.get("path") or ""): w for w in worktrees}
        sessions: list[RuntimeSession] = []
        # Track which worktree entries have been consumed by a terminal so
        # multi-pane worktrees keep every pane (review C1).
        consumed_entries: set[int] = set()

        for terminal in terminals:
            agent = normalize_agent(str(terminal.get("agentIdentity") or ""))
            if not agent:
                continue
            workspace = str(terminal.get("worktreePath") or "")
            worktree = worktree_by_path.get(workspace)
            entry = self._match_terminal_entry(worktree, agent, consumed_entries)
            sessions.append(self._session_from_terminal(terminal, worktree, entry, agent))
            if entry is not None:
                consumed_entries.add(id(entry))

        for worktree in worktrees:
            workspace = str(worktree.get("path") or "")
            for entry in worktree.get("agents") or []:
                agent = normalize_agent(str(entry.get("agentType") or "")) if isinstance(entry, dict) else ""
                if not agent:
                    continue
                if id(entry) in consumed_entries:
                    continue
                sessions.append(self._session_from_agent_entry(worktree, entry, agent))

        return sessions

    @staticmethod
    def _match_terminal_entry(worktree: dict | None, agent: str, consumed: set[int]) -> dict | None:
        """Return the first unconsumed worktree entry matching *agent*.

        Each terminal consumes at most one entry so multi-pane worktrees
        keep every pane (review C1).
        """
        if not worktree:
            return None
        for entry in worktree.get("agents") or []:
            if not isinstance(entry, dict):
                continue
            if id(entry) in consumed:
                continue
            if normalize_agent(str(entry.get("agentType") or "")) == agent:
                return entry
        return None

    def _session_from_terminal(
        self,
        terminal: dict,
        worktree: dict | None,
        entry: dict | None,
        agent: str,
    ) -> RuntimeSession:
        workspace = str(terminal.get("worktreePath") or "")
        repo = worktree.get("repo") if worktree else None
        return RuntimeSession(
            session_id=str(terminal.get("handle") or ""),
            host=HOST_NAME,
            agent=agent,
            project=project_name(str(repo) if repo else None, workspace),
            workspace=workspace,
            status=agent_state_status(entry),
            source=RuntimeSource.CLI,
            confidence=confidence_for_source(RuntimeSource.CLI),
            activity=_entry_activity(entry),
            needs_user=None,
            started_at=epoch_millis_to_datetime(_entry_field(entry, "stateStartedAt")),
            last_activity_at=_last_activity(terminal, worktree, entry),
        )

    def _session_from_agent_entry(self, worktree: dict, entry: dict, agent: str) -> RuntimeSession:
        workspace = str(worktree.get("path") or "")
        repo = str(worktree.get("repo") or "") or None
        fallback_id = f"{worktree.get('worktreeId') or workspace}::{agent}"
        return RuntimeSession(
            session_id=str(entry.get("paneKey") or fallback_id),
            host=HOST_NAME,
            agent=agent,
            project=project_name(repo, workspace),
            workspace=workspace,
            status=agent_state_status(entry),
            source=RuntimeSource.CLI,
            confidence=confidence_for_source(RuntimeSource.CLI),
            activity=_entry_activity(entry),
            needs_user=None,
            started_at=epoch_millis_to_datetime(_entry_field(entry, "stateStartedAt")),
            last_activity_at=_last_activity({}, worktree, entry),
        )


def _entry_field(entry: dict | None, key: str):
    return entry.get(key) if entry else None


def _entry_activity(entry: dict | None) -> str:
    """Human-readable activity from the agent's task title, if any."""
    if not entry:
        return ""
    return str(entry.get("taskTitle") or "").strip()


def _last_activity(terminal: dict, worktree: dict | None, entry: dict | None):
    """Most recent known activity timestamp across agent/worktree/terminal."""
    candidates = [
        _entry_field(entry, "updatedAt"),
        worktree.get("lastActivityAt") if worktree else None,
        terminal.get("lastOutputAt"),
    ]
    timestamps = [t for t in (epoch_millis_to_datetime(v) for v in candidates) if t is not None]
    return max(timestamps) if timestamps else None
