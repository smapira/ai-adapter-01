"""Normalizer: raw host data → canonical Runtime Model conversions.

Single source of truth for the normalization vocabulary shared by all
runtime adapters:

- the Source→Confidence mapping table (design §2.5)
- the P2 activity-state derivation rule (design §2.4.1): ACTIVE / INACTIVE /
  UNKNOWN, serialized lowercase
- project normalization: host-reported name wins, otherwise ``basename(workspace)``
- agent-name normalization to the canonical vocabulary
  (codex / claude / opencode / copilot / zed-agent)
- the JSON serializer for :class:`~ai_adapter.runtime.models.RuntimeSession`

Adapters own their raw→RuntimeSession mapping; this module owns the shared
vocabulary and pure conversion helpers.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Any

from ai_adapter.runtime.models import (
    RuntimeConfidence,
    RuntimeSession,
    RuntimeSource,
    RuntimeStatus,
)

# --- Source → Confidence (design §2.5) -------------------------------------
#
# Where the design gives a range (e.g. "Official Session Metadata: HIGH /
# MEDIUM"), the conservative end is chosen so confidence is never overstated.

SOURCE_CONFIDENCE: dict[RuntimeSource, RuntimeConfidence] = {
    RuntimeSource.HOOK: RuntimeConfidence.HIGH,
    RuntimeSource.CLI: RuntimeConfidence.HIGH,
    RuntimeSource.API: RuntimeConfidence.HIGH,
    RuntimeSource.ACP: RuntimeConfidence.HIGH,
    RuntimeSource.METADATA: RuntimeConfidence.MEDIUM,
    RuntimeSource.TERMINAL: RuntimeConfidence.MEDIUM,
    RuntimeSource.FILE: RuntimeConfidence.LOW,
    RuntimeSource.PROCESS: RuntimeConfidence.LOW,
    RuntimeSource.HEURISTIC: RuntimeConfidence.LOW,
}

# --- P2 activity-state derivation (design §2.4.1) --------------------------

ACTIVE_STATUSES = {RuntimeStatus.WORKING, RuntimeStatus.WAITING, RuntimeStatus.BLOCKED}
INACTIVE_STATUSES = {RuntimeStatus.IDLE, RuntimeStatus.DONE}

# --- Agent vocabulary -------------------------------------------------------

AGENT_ALIASES: dict[str, str] = {
    "copilot-runtime": "copilot",
    "claude-code": "claude",
    "open-code": "opencode",
}


def confidence_for_source(source: RuntimeSource) -> RuntimeConfidence:
    """Return the confidence implied by an observation source."""
    return SOURCE_CONFIDENCE.get(source, RuntimeConfidence.LOW)


def derive_activity_state(status: RuntimeStatus) -> str:
    """Map a canonical status to the P2 activity state (lowercase).

    ACTIVE = working / waiting / blocked, INACTIVE = idle / done,
    UNKNOWN = unknown (never guessed).
    """
    if status in ACTIVE_STATUSES:
        return "active"
    if status in INACTIVE_STATUSES:
        return "inactive"
    return "unknown"


def project_name(host_reported: str | None, workspace: str) -> str:
    """Normalize a project name: host-reported value wins, else basename."""
    if host_reported and host_reported.strip():
        return host_reported.strip()
    if not workspace:
        return ""
    return PurePosixPath(workspace.rstrip("/")).name


def normalize_agent(raw: str) -> str:
    """Normalize a host-reported agent identity to the canonical vocabulary."""
    cleaned = raw.strip().lower().replace(" ", "-")
    return AGENT_ALIASES.get(cleaned, cleaned)


def epoch_millis_to_datetime(value: Any) -> datetime | None:
    """Convert epoch milliseconds (Orca-style) to an aware UTC datetime."""
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(float(value) / 1000, tz=timezone.utc)
    except (TypeError, ValueError, OSError, OverflowError):
        return None


def runtime_session_to_dict(session: RuntimeSession) -> dict[str, Any]:
    """Serialize a session per the JSON envelope (design §6.3).

    Enum values are lowercase; datetimes are ISO 8601 with timezone;
    missing values become ``null``.
    """
    return {
        "session_id": session.session_id,
        "host": session.host,
        "agent": session.agent,
        "project": session.project,
        "workspace": session.workspace,
        "status": session.status.value,
        "activity": session.activity,
        "needs_user": session.needs_user,
        "started_at": session.started_at.isoformat() if session.started_at else None,
        "last_activity_at": session.last_activity_at.isoformat() if session.last_activity_at else None,
        "source": session.source.value,
        "confidence": session.confidence.value,
    }
