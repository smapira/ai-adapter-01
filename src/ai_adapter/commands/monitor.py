"""monitor command — Runtime Plane entry point (read-only observability).

Answers "What is happening now?" by discovering AI agent sessions running in
Orca / VS Code / Zed. Read-only by design: this command never sends input to
agents, never changes IDE settings, and never stops processes.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import click

from ai_adapter.runtime.models import RuntimeSession
from ai_adapter.runtime.normalizer import derive_activity_state, runtime_session_to_dict
from ai_adapter.runtime.registry import create_adapters, discover_sessions

#: Host id → display label (design §6.1 table example).
HOST_LABELS = {"orca": "Orca", "vscode": "VSCode", "zed": "Zed"}

_TABLE_HEADER = f"{'HOST':<10}{'PROJECT':<28}{'AGENT':<12}{'STATE':<10}{'AGE':>6}"
_TABLE_RULE = "─" * 66


@click.command(name="monitor")
@click.option("--json", "as_json", is_flag=True, help="Output sessions as JSON")
def cmd_monitor(as_json: bool) -> None:
    """Discover AI agent sessions running in Orca / VS Code / Zed (read-only).

    Without --json a plain table is printed. With --json the Canonical
    Runtime Model is serialized (lowercase enum values, ISO 8601 datetimes).
    Missing hosts are skipped; an empty result is not an error.
    """
    adapters = create_adapters()
    sessions = discover_sessions(adapters)
    if as_json:
        payload = {"sessions": [runtime_session_to_dict(s) for s in sessions]}
        click.echo(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    click.echo(render_session_table(sessions))


def render_session_table(sessions: list[RuntimeSession], now: datetime | None = None) -> str:
    """Pure renderer: canonical sessions → plain table (design §6.1).

    STATE shows the P2 activity classification (ACTIVE / INACTIVE / UNKNOWN,
    uppercase for display; serialized values stay lowercase).
    """
    reference = now or datetime.now(timezone.utc)
    lines = [_TABLE_HEADER, _TABLE_RULE]
    lines.extend(_format_row(session, reference) for session in sessions)
    if not sessions:
        lines.append("(no sessions)")
    return "\n".join(lines)


def _format_row(session: RuntimeSession, now: datetime) -> str:
    host = HOST_LABELS.get(session.host, session.host)
    project = _truncate(session.project or "-", 27)
    agent = _truncate(session.agent or "-", 11)
    state = derive_activity_state(session.status).upper()
    age = _format_age(session, now)
    return f"{host:<10}{project:<28}{agent:<12}{state:<10}{age:>6}"


def _format_age(session: RuntimeSession, now: datetime) -> str:
    """Human-readable age from the most recent known timestamp."""
    anchor = session.last_activity_at or session.started_at
    if anchor is None:
        return "-"
    if anchor.tzinfo is None:
        anchor = anchor.replace(tzinfo=timezone.utc)
    seconds = max(0, int((now - anchor).total_seconds()))
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m"
    if seconds < 86400:
        return f"{seconds // 3600}h"
    return f"{seconds // 86400}d"


def _truncate(text: str, width: int) -> str:
    return text if len(text) <= width else text[: width - 1] + "…"
