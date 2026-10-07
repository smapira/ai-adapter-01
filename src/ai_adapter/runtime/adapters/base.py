"""RuntimeAdapter contract, host-CLI gateway, and fallback process observation.

This module owns:

- :class:`RuntimeAdapter` — the ABC every host adapter implements
- :func:`run_host_command` — the single subprocess gateway used by all
  adapters (list argv, ``shell=False``, timeout mandatory, never raises)
- process-observation helpers shared by the VS Code / Zed fallback adapters

Host differences stay inside each adapter; nothing host-specific leaks here.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import PurePosixPath

from ai_adapter.runtime.models import (
    RuntimeCapabilities,
    RuntimeSession,
    RuntimeSource,
    RuntimeStatus,
)
from ai_adapter.runtime.normalizer import confidence_for_source, project_name

DEFAULT_TIMEOUT_SECONDS = 10.0
PS_TIMEOUT_SECONDS = 5.0

#: Command basename → canonical agent name (design §9 vocabulary).
AGENT_BINARIES: dict[str, str] = {
    "opencode": "opencode",
    "codex": "codex",
    "claude": "claude",
    "copilot": "copilot",
    "copilot-runtime": "copilot",
}

#: Paths that indicate an app-internal cwd, not a user workspace.
_APP_INTERNAL_MARKERS = (".app/", "Application Support", ".vscode/extensions")


@dataclass
class CommandResult:
    """Outcome of a host CLI invocation. Never an exception."""

    argv: list[str]
    returncode: int | None
    stdout: str
    stderr: str
    error: str | None = None

    @property
    def ok(self) -> bool:
        """True when the command ran and exited 0."""
        return self.error is None and self.returncode == 0


def run_host_command(argv: list[str], timeout: float = DEFAULT_TIMEOUT_SECONDS) -> CommandResult:
    """Run a host CLI safely: list argv, ``shell=False``, timeout enforced.

    Returns a :class:`CommandResult` instead of raising, so a missing or
    hanging host degrades to an empty discovery instead of crashing the CLI.
    """
    try:
        completed = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, shell=False)
    except FileNotFoundError:
        return CommandResult(argv=argv, returncode=None, stdout="", stderr="", error="not-found")
    except subprocess.TimeoutExpired:
        return CommandResult(argv=argv, returncode=None, stdout="", stderr="", error="timeout")
    except OSError as exc:
        return CommandResult(argv=argv, returncode=None, stdout="", stderr=str(exc), error="failed")
    return CommandResult(
        argv=argv,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def parse_json_payload(result: CommandResult) -> dict | None:
    """Parse a successful command's stdout as a JSON object.

    Returns ``None`` when the command failed, the output is not JSON, or the
    payload declares ``ok: false`` (Orca CLI convention).
    """
    if not result.ok or not result.stdout:
        return None
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict) or payload.get("ok") is False:
        return None
    inner = payload.get("result")
    return inner if isinstance(inner, dict) else None


# --- Process observation (fallback for VS Code / Zed) -----------------------


@dataclass
class ProcessInfo:
    """One row from a ``ps`` snapshot."""

    pid: int
    ppid: int
    command: str
    elapsed_seconds: int | None = None


def parse_elapsed_seconds(raw: str) -> int | None:
    """Parse ``ps etime`` (``[[dd-]hh:]mm:ss`` or bare seconds) to seconds.

    Returns None for unparseable input — callers treat that as "unknown
    start time" rather than guessing.
    """
    text = raw.strip()
    if not text:
        return None
    days = 0
    if "-" in text:
        day_part, text = text.split("-", 1)
        if not day_part.isdigit():
            return None
        days = int(day_part)
    parts = text.split(":")
    try:
        if len(parts) == 1 and parts[0].isdigit():
            return days * 86400 + int(parts[0])
        if len(parts) == 2 and all(p.isdigit() for p in parts):
            return days * 86400 + int(parts[0]) * 60 + int(parts[1])
        if len(parts) == 3 and all(p.isdigit() for p in parts):
            return days * 86400 + int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    except ValueError:
        return None
    return None


def observe_processes(timeout: float = PS_TIMEOUT_SECONDS) -> list[ProcessInfo]:
    """Snapshot the process table via ``ps``. Returns [] on any failure."""
    result = run_host_command(["ps", "-axo", "pid=,ppid=,etime=,command="], timeout=timeout)
    if not result.ok:
        return []
    return parse_ps_output(result.stdout)


def parse_ps_output(output: str) -> list[ProcessInfo]:
    """Parse ``ps -axo pid=,ppid=,etime=,command=`` output into records.

    Also accepts the older 3-column ``pid=,ppid=,command=`` layout (no
    etime): a third token is treated as elapsed time only when it parses
    as etime, otherwise it is joined back into the command.
    """
    processes: list[ProcessInfo] = []
    for line in output.splitlines():
        parts = line.split(None, 3)
        if len(parts) < 3:
            continue
        try:
            pid = int(parts[0])
            ppid = int(parts[1])
        except ValueError:
            continue
        elapsed: int | None = None
        if len(parts) == 3:
            command = parts[2].strip()
        else:
            maybe_elapsed = parse_elapsed_seconds(parts[2])
            if maybe_elapsed is not None and all(ch.isdigit() or ch in "-:" for ch in parts[2]):
                elapsed = maybe_elapsed
                command = parts[3].strip()
            else:
                command = f"{parts[2]} {parts[3]}".strip()
        processes.append(ProcessInfo(pid=pid, ppid=ppid, command=command, elapsed_seconds=elapsed))
    return processes


def detect_agent(command: str) -> str | None:
    """Map a process command line to a canonical agent name, if any.

    Matches only argv[0] (first token) or tokens that look like absolute
    paths (contain ``/``). Full-token scanning of every argument would
    false-positive on commands like ``grep claude`` or ``echo opencode``
    (review M2). Path tokens are still matched because host app paths may
    contain spaces (``Visual Studio Code.app``), which break naive argv[0]
    extraction — interpreter launches like ``node /path/to/codex`` remain
    detectable.
    """
    tokens = command.split()
    if not tokens:
        return None
    candidates = [tokens[0]] + [t for t in tokens[1:] if "/" in t]
    for token in candidates:
        mapped = AGENT_BINARIES.get(PurePosixPath(token).name.lower())
        if mapped:
            return mapped
    return None


def has_ancestor(
    process: ProcessInfo,
    by_pid: dict[int, ProcessInfo],
    root_pids: set[int],
    max_depth: int = 32,
) -> bool:
    """True when ``process`` descends from any pid in ``root_pids``."""
    seen: set[int] = set()
    current: ProcessInfo | None = process
    depth = 0
    while current is not None and depth < max_depth:
        if current.pid in root_pids:
            return True
        if current.pid in seen:
            return False
        seen.add(current.pid)
        current = by_pid.get(current.ppid)
        depth += 1
    return False


def find_host_agent_processes(
    processes: list[ProcessInfo],
    host_marker: str,
    extension_marker: str = "",
) -> list[ProcessInfo]:
    """Select agent processes attributable to a host.

    Attribution: the process command contains ``host_marker`` (e.g. the IDE
    app bundle) directly, or contains ``extension_marker`` (e.g.
    ``.vscode/extensions/`` for VS Code extension-hosted agents), or descends
    from a host process. The agent-identity check runs first so that agent
    runtimes shipped inside the host bundle (e.g. ``copilot-runtime``) are
    still reported as agent sessions rather than host infrastructure.
    """
    by_pid = {p.pid: p for p in processes}
    host_pids = {p.pid for p in processes if host_marker in p.command}
    selected: list[ProcessInfo] = []
    for process in processes:
        if detect_agent(process.command) is None:
            continue
        if host_marker in process.command or (extension_marker and extension_marker in process.command):
            selected.append(process)
            continue
        if has_ancestor(process, by_pid, host_pids):
            selected.append(process)
    return selected


def session_token(command: str) -> str | None:
    """Extract an explicit session token (``--session <id>``) from a command."""
    tokens = command.split()
    for index, token in enumerate(tokens):
        if token == "--session" and index + 1 < len(tokens):
            return tokens[index + 1]
    return None


def process_cwd(pid: int, timeout: float = PS_TIMEOUT_SECONDS) -> str:
    """Best-effort working directory of a process via ``lsof`` ("" on failure)."""
    if shutil.which("lsof") is None:
        return ""
    result = run_host_command(["lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn"], timeout=timeout)
    if not result.ok:
        return ""
    for line in result.stdout.splitlines():
        if line.startswith("n") and len(line) > 1:
            return line[1:]
    return ""


def process_open_handles(pids: list[int], timeout: float = PS_TIMEOUT_SECONDS) -> dict[int, set[str]]:
    """Open file/directory paths per pid via a single ``lsof`` call.

    One bulk invocation keeps macOS ``lsof`` overhead acceptable when many
    IDE processes must be inspected. Returns {} when ``lsof`` is missing or
    the command fails; never raises.
    """
    if not pids or shutil.which("lsof") is None:
        return {}
    argv = ["lsof", "-p", ",".join(str(pid) for pid in pids)]
    result = run_host_command(argv, timeout=timeout)
    if not result.ok:
        return {}
    handles: dict[int, set[str]] = {}
    for line in result.stdout.splitlines():
        fields = line.split()
        if len(fields) < 9 or not fields[1].isdigit():
            continue
        path = fields[-1]
        if not path.startswith("/"):
            continue
        handles.setdefault(int(fields[1]), set()).add(path)
    return handles


def usable_workspace(cwd: str) -> str:
    """Return ``cwd`` unless it is unusable as a project path.

    Filters out empty strings, app-bundle internals, and bare ``"/"`` —
    extension-hosted agents inherit the IDE's cwd (often ``/``), which
    carries no project context (review M1).
    """
    if not cwd or cwd == "/":
        return ""
    if any(marker in cwd for marker in _APP_INTERNAL_MARKERS):
        return ""
    return cwd


def session_from_process(host: str, process: ProcessInfo, fallback_workspace: str = "") -> RuntimeSession:
    """Build a Canonical session from a process observation (fallback path).

    Process existence alone never implies WORKING / WAITING / DONE
    (design §4.4), so the status is always UNKNOWN and confidence LOW.

    ``fallback_workspace`` is used only when the process cwd is unusable —
    callers pass a host-resolved workspace (e.g. VS Code window folder
    attribution); it is never guessed here.
    """
    workspace = usable_workspace(process_cwd(process.pid)) or usable_workspace(fallback_workspace)
    started_at: datetime | None = None
    if process.elapsed_seconds is not None:
        started_at = datetime.now(timezone.utc) - timedelta(seconds=process.elapsed_seconds)
    return RuntimeSession(
        session_id=session_token(process.command) or str(process.pid),
        host=host,
        agent=detect_agent(process.command) or "unknown",
        project=project_name(None, workspace),
        workspace=workspace,
        status=RuntimeStatus.UNKNOWN,
        source=RuntimeSource.PROCESS,
        confidence=confidence_for_source(RuntimeSource.PROCESS),
        activity="",
        needs_user=None,
        started_at=started_at,
        last_activity_at=None,
    )


def unavailable_capabilities(host: str) -> RuntimeCapabilities:
    """Capability declaration for a host that is not installed (all NO)."""
    return RuntimeCapabilities(
        host=host,
        discover="NO",
        project="NO",
        agent="NO",
        activity="NO",
        working="NO",
        waiting="NO",
        done="NO",
        needs_user="NO",
    )


class RuntimeAdapter(ABC):
    """Common interface for all host adapters.

    Contract (design §3):

    - ``discover()`` never raises; an unreachable host yields ``[]``
    - ``capabilities()`` returns a declaration even when the host is absent
    - host-specific knowledge stays inside the adapter implementation
    """

    @abstractmethod
    def discover(self) -> list[RuntimeSession]:
        """Discover running or existing agent sessions. Never raises."""

    @abstractmethod
    def inspect(self, session_id: str) -> RuntimeSession | None:
        """Return detailed session information for a host-scoped session id."""

    @abstractmethod
    def capabilities(self) -> RuntimeCapabilities:
        """Describe observable capabilities honestly (YES/PARTIAL/NO/UNKNOWN)."""

    @property
    @abstractmethod
    def host_name(self) -> str:
        """Return the host identifier (e.g. 'orca', 'vscode', 'zed')."""

    @abstractmethod
    def is_available(self) -> bool:
        """Return True when the host CLI/API is reachable on this machine."""
