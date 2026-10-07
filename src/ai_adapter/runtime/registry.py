"""Adapter registry: static types list plus availability-filtered creation.

PoC policy (design §12.5): a module-level static list, no entry-point
dynamic loading. One adapter failing must never take down discovery for the
other hosts.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from ai_adapter.runtime.adapters.base import RuntimeAdapter
from ai_adapter.runtime.adapters.orca import OrcaAdapter
from ai_adapter.runtime.adapters.vscode import VSCodeAdapter
from ai_adapter.runtime.adapters.zed import ZedAdapter
from ai_adapter.runtime.models import RuntimeSession

#: Registered adapter types, in display order (design §12.5).
ADAPTER_TYPES: list[type[RuntimeAdapter]] = [OrcaAdapter, VSCodeAdapter, ZedAdapter]

_HOST_SORT_ORDER = {"orca": 0, "vscode": 1, "zed": 2}


def create_adapters() -> list[RuntimeAdapter]:
    """Instantiate all adapters whose host is reachable on this machine.

    Unavailable hosts are skipped; an adapter raising during construction or
    availability probing is isolated (design §12.5).
    """
    adapters: list[RuntimeAdapter] = []
    for adapter_type in ADAPTER_TYPES:
        try:
            adapter = adapter_type()
            if adapter.is_available():
                adapters.append(adapter)
        except Exception:
            continue
    return adapters


def discover_sessions(adapters: list[RuntimeAdapter]) -> list[RuntimeSession]:
    """Run ``discover()`` on all adapters concurrently (design §3).

    Results are sorted deterministically by host order, project, agent and
    session id so output is stable across runs. Exceptions are isolated:
    one adapter failing yields no sessions for that host, never a crash.
    """
    if not adapters:
        return []
    sessions: list[RuntimeSession] = []
    with ThreadPoolExecutor(max_workers=len(adapters)) as pool:
        futures = [pool.submit(_safe_discover, adapter) for adapter in adapters]
        for future in as_completed(futures):
            try:
                sessions.extend(future.result())
            except Exception:
                continue
    sessions.sort(key=_session_sort_key)
    return sessions


def _safe_discover(adapter: RuntimeAdapter) -> list[RuntimeSession]:
    try:
        return adapter.discover()
    except Exception:
        return []


def _session_sort_key(session: RuntimeSession) -> tuple[int, str, str, str]:
    return (
        _HOST_SORT_ORDER.get(session.host, 99),
        session.project,
        session.agent,
        session.session_id,
    )
