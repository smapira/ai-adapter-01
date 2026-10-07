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

Workspace attribution (follow-up, 2026-10-07): macOS VS Code processes run
with cwd ``/``, so process cwd alone cannot identify the project. The adapter
therefore correlates via two extra signals:

1. ``windowsState`` in VS Code ``globalStorage/storage.json`` lists the
   folders currently open in VS Code windows.
2. Each per-window host process tree keeps an open directory handle on its
   workspace folder (verified via ``lsof``). Grouping handles by window root
   attributes agent processes to a folder — only when exactly one folder maps
   to that window root. Ambiguity is never guessed.
"""

from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path
from urllib.parse import unquote, urlparse

from ai_adapter.runtime.adapters.base import (
    RuntimeAdapter,
    find_host_agent_processes,
    observe_processes,
    process_open_handles,
    session_from_process,
    unavailable_capabilities,
)
from ai_adapter.runtime.models import RuntimeCapabilities, RuntimeSession

HOST_NAME = "vscode"

#: App-bundle marker for VS Code processes (macOS).
HOST_MARKER = "Visual Studio Code.app"

#: Direct attribution marker for extension-hosted agent binaries.
EXTENSION_MARKER = ".vscode/extensions/"

#: Main-process detection: ``/Contents/MacOS/Code`` without Helper/--type.
_MAIN_PROCESS_RE = re.compile(r"/Contents/MacOS/(Code|Electron)\b")


def _is_vs_process(command: str) -> bool:
    """True when a ``ps`` command belongs to the VS Code process tree."""
    return HOST_MARKER in command or EXTENSION_MARKER in command


def _is_main_process(command: str) -> bool:
    """True for the main Electron process (not a Code Helper child)."""
    return bool(_MAIN_PROCESS_RE.search(command)) and "Helper" not in command and "--type=" not in command


def _default_user_data_dirs() -> list[Path]:
    """Candidate VS Code user-data dirs for storage.json (macOS, Linux)."""
    home = Path.home()
    return [
        home / "Library/Application Support/Code",
        home / ".config/Code",
        home / ".config/Code - Insiders",
    ]


def open_workspace_folders(user_data_dir: str | os.PathLike[str] | None = None) -> set[str]:
    """Folders currently open in VS Code windows (local ``file://`` only).

    Reads ``User/globalStorage/storage.json`` → ``windowsState``. Returns an
    empty set when the file is missing, unparsable, or lists no existing
    local folder. Remote workspaces (``vscode-remote://``) are skipped —
    local processes cannot be attributed to remote folders.
    """
    dirs = [Path(user_data_dir)] if user_data_dir else _default_user_data_dirs()
    for base in dirs:
        storage = base / "User/globalStorage/storage.json"
        if not storage.is_file():
            continue
        try:
            payload = json.loads(storage.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        windows_state = payload.get("windowsState") or {}
        candidates = [windows_state.get("lastActiveWindow") or {}]
        candidates.extend(windows_state.get("openedWindows") or [])
        folders: set[str] = set()
        for window in candidates:
            uri = (window or {}).get("folder") or (window or {}).get("workspace") or ""
            parsed = urlparse(uri)
            if parsed.scheme != "file":
                continue
            path = unquote(parsed.path)
            if path and os.path.isdir(path):
                folders.add(path.rstrip("/") or "/")
        if folders:
            return folders
    return set()


def _window_root(pid: int, by_pid: dict[int, tuple[int, str]]) -> int | None:
    """Highest VS-tree ancestor that is not the main Electron process.

    The walk continues through non-VS processes because terminal-spawned
    agents (e.g. ``opencode`` under a VS Code integrated terminal) carry no
    VS marker themselves yet still descend from a per-window host process.
    Returns None when no VS ancestor exists at all.
    """
    current: int | None = pid
    root: int | None = None
    seen: set[int] = set()
    while current is not None and current in by_pid and current not in seen:
        seen.add(current)
        ppid, command = by_pid[current]
        if _is_vs_process(command) and not _is_main_process(command):
            root = current
        current = ppid
    return root


def attribute_workspaces(processes: list, folders: set[str]) -> dict[int, str]:
    """Map VS Code window-root pids to exactly-one workspace folder.

    Handles found on ``folders`` paths are grouped by window root. A root is
    attributed only when all of its handles point at a single folder —
    multiple folders mean ambiguity and are never guessed. Returns {} when
    ``lsof`` is unavailable or nothing resolves.
    """
    if not folders:
        return {}
    by_pid = {p.pid: (p.ppid, p.command) for p in processes}
    vs_pids = [p.pid for p in processes if _is_vs_process(p.command)]
    if not vs_pids:
        return {}
    handles = process_open_handles(vs_pids)
    root_folders: dict[int, set[str]] = {}
    for pid, paths in handles.items():
        root = _window_root(pid, by_pid)
        if root is None:
            continue
        for path in paths:
            for folder in folders:
                if path == folder or path.startswith(folder + "/"):
                    root_folders.setdefault(root, set()).add(folder)
    return {root: next(iter(fl)) for root, fl in root_folders.items() if len(fl) == 1}


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
            if not agents:
                return []
            by_pid = {p.pid: (p.ppid, p.command) for p in processes}
            workspaces = attribute_workspaces(processes, open_workspace_folders())
            sessions: list[RuntimeSession] = []
            for process in agents:
                root = _window_root(process.pid, by_pid)
                fallback = workspaces.get(root, "") if root is not None else ""
                sessions.append(session_from_process(HOST_NAME, process, fallback_workspace=fallback))
            return sessions
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
