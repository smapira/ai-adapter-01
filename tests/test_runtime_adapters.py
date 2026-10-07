"""Tests for Runtime adapters, the subprocess gateway, and the registry.

All host CLIs are mocked via fixture raw data (design §8): the suite must
pass on machines where Orca / VS Code / Zed are not installed.
"""

from __future__ import annotations

import json
import subprocess
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from ai_adapter.runtime.adapters.base import (
    CommandResult,
    RuntimeAdapter,
    detect_agent,
    find_host_agent_processes,
    parse_elapsed_seconds,
    parse_json_payload,
    parse_ps_output,
    run_host_command,
    session_from_process,
    session_token,
    unavailable_capabilities,
    usable_workspace,
)
from ai_adapter.runtime.adapters.orca import OrcaAdapter, agent_state_status
from ai_adapter.runtime.adapters.vscode import (
    VSCodeAdapter,
    attribute_workspaces,
    open_workspace_folders,
)
from ai_adapter.runtime.adapters.zed import ZedAdapter
from ai_adapter.runtime.models import (
    RuntimeConfidence,
    RuntimeSession,
    RuntimeSource,
    RuntimeStatus,
)
from ai_adapter.runtime.normalizer import derive_activity_state
from ai_adapter.runtime.registry import ADAPTER_TYPES, create_adapters, discover_sessions

FIXTURES = Path(__file__).parent / "fixtures" / "runtime"


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _ok_result(argv: list[str], stdout: str) -> CommandResult:
    return CommandResult(argv=argv, returncode=0, stdout=stdout, stderr="")


def _fail_result(argv: list[str]) -> CommandResult:
    return CommandResult(argv=argv, returncode=1, stdout="", stderr="boom")


class TestSubprocessGateway(unittest.TestCase):
    """run_host_command: list argv, shell=False, timeout, never raises."""

    @patch("ai_adapter.runtime.adapters.base.subprocess.run")
    def test_uses_list_argv_and_no_shell(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="{}", stderr="")
        result = run_host_command(["orca", "terminal", "list", "--json"], timeout=7.0)
        self.assertTrue(result.ok)
        mock_run.assert_called_once_with(
            ["orca", "terminal", "list", "--json"],
            capture_output=True,
            text=True,
            timeout=7.0,
            shell=False,
        )

    @patch("ai_adapter.runtime.adapters.base.subprocess.run")
    def test_timeout_reported_not_raised(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="orca", timeout=10)
        result = run_host_command(["orca", "status", "--json"])
        self.assertFalse(result.ok)
        self.assertEqual(result.error, "timeout")

    @patch("ai_adapter.runtime.adapters.base.subprocess.run")
    def test_missing_binary_reported_not_raised(self, mock_run):
        mock_run.side_effect = FileNotFoundError()
        result = run_host_command(["orca", "status", "--json"])
        self.assertFalse(result.ok)
        self.assertEqual(result.error, "not-found")

    @patch("ai_adapter.runtime.adapters.base.subprocess.run")
    def test_os_error_reported_not_raised(self, mock_run):
        mock_run.side_effect = OSError("permission denied")
        result = run_host_command(["ps", "-axo", "pid="])
        self.assertFalse(result.ok)
        self.assertEqual(result.error, "failed")

    @patch("ai_adapter.runtime.adapters.base.subprocess.run")
    def test_nonzero_exit_is_not_ok(self, mock_run):
        mock_run.return_value = MagicMock(returncode=2, stdout="", stderr="err")
        result = run_host_command(["orca", "bad"])
        self.assertFalse(result.ok)


class TestJsonPayloadParsing(unittest.TestCase):
    """parse_json_payload handles Orca's ok/result envelope defensively."""

    def test_extracts_result_object(self):
        payload = {"ok": True, "result": {"terminals": []}}
        parsed = parse_json_payload(_ok_result(["x"], json.dumps(payload)))
        self.assertEqual(parsed, {"terminals": []})

    def test_ok_false_returns_none(self):
        parsed = parse_json_payload(_ok_result(["x"], json.dumps({"ok": False})))
        self.assertIsNone(parsed)

    def test_malformed_json_returns_none(self):
        self.assertIsNone(parse_json_payload(_ok_result(["x"], "{not json")))

    def test_failed_command_returns_none(self):
        self.assertIsNone(parse_json_payload(_fail_result(["x"])))


class TestProcessObservationHelpers(unittest.TestCase):
    """ps parsing, agent detection, and attribution for the fallback path."""

    def test_parse_ps_output(self):
        output = _fixture("vscode_ps.txt")
        processes = parse_ps_output(output)
        self.assertEqual(len(processes), 7)
        self.assertEqual(processes[0].pid, 11820)
        self.assertIn("Visual Studio Code.app", processes[0].command)

    def test_detect_agent_by_basename(self):
        self.assertEqual(detect_agent("/Users/x/.local/bin/opencode --session ses_1"), "opencode")
        self.assertEqual(detect_agent("/Applications/.../copilot-runtime --headless"), "copilot")
        self.assertIsNone(detect_agent("/bin/zsh -l"))

    def test_detect_agent_via_interpreter(self):
        command = "node /Users/x/.vscode/extensions/openai.chatgpt/bin/codex app-server"
        self.assertEqual(detect_agent(command), "codex")

    def test_session_token_extraction(self):
        self.assertEqual(session_token("opencode --session ses_abc123"), "ses_abc123")
        self.assertIsNone(session_token("codex app-server"))

    def test_usable_workspace_filters_app_internal_paths(self):
        self.assertEqual(usable_workspace("/Users/x/proj"), "/Users/x/proj")
        self.assertEqual(usable_workspace("/Users/x/Library/Application Support/Code"), "")
        self.assertEqual(usable_workspace(""), "")

    def test_find_host_agent_processes_vscode(self):
        processes = parse_ps_output(_fixture("vscode_ps.txt"))
        agents = find_host_agent_processes(processes, "Visual Studio Code.app", ".vscode/extensions/")
        commands = [a.command for a in agents]
        self.assertEqual(len(agents), 3)
        self.assertTrue(any("copilot-runtime" in c for c in commands))
        self.assertTrue(any("codex" in c for c in commands))
        self.assertTrue(any("opencode" in c for c in commands))
        # claude under a bare pid-1 parent must not be attributed to VS Code
        self.assertFalse(any("claude" in c for c in commands))

    def test_find_host_agent_processes_zed(self):
        processes = parse_ps_output(_fixture("zed_ps.txt"))
        agents = find_host_agent_processes(processes, "Zed.app")
        self.assertEqual(len(agents), 1)
        self.assertIn("claude", agents[0].command)

    @patch("ai_adapter.runtime.adapters.base.process_cwd", return_value="/Users/x/proj")
    def test_session_from_process_maps_to_canonical(self, _mock_cwd):
        processes = parse_ps_output(_fixture("vscode_ps.txt"))
        agent_process = next(p for p in processes if "opencode" in p.command)
        session = session_from_process("vscode", agent_process)
        self.assertEqual(session.host, "vscode")
        self.assertEqual(session.agent, "opencode")
        self.assertEqual(session.project, "proj")
        self.assertEqual(session.session_id, "ses_abc123def456")
        # Process existence never implies a working state (design §4.4)
        self.assertEqual(session.status, RuntimeStatus.UNKNOWN)
        self.assertEqual(session.source, RuntimeSource.PROCESS)
        self.assertEqual(session.confidence, RuntimeConfidence.LOW)
        self.assertEqual(derive_activity_state(session.status), "unknown")


class TestOrcaAdapter(unittest.TestCase):
    """Orca raw JSON → Canonical via mocked CLI surfaces."""

    def _adapter_with_fixtures(self) -> OrcaAdapter:
        terminal_json = _fixture("orca_terminal_list.json")
        worktree_json = _fixture("orca_worktree_ps.json")

        def fake_run(argv, timeout=10.0):
            if argv[:3] == ["orca", "terminal", "list"]:
                return _ok_result(argv, terminal_json)
            return _ok_result(argv, worktree_json)

        adapter = OrcaAdapter()
        patcher = patch("ai_adapter.runtime.adapters.orca.run_host_command", side_effect=fake_run)
        patcher.start()
        self.addCleanup(patcher.stop)
        return adapter

    def test_discover_builds_sessions_from_both_surfaces(self):
        adapter = self._adapter_with_fixtures()
        sessions = adapter.discover()
        # 2 terminal-based sessions + 1 worktree-only agent session
        self.assertEqual(len(sessions), 3)
        for session in sessions:
            self.assertEqual(session.host, "orca")
            self.assertEqual(session.source, RuntimeSource.CLI)
            self.assertEqual(session.confidence, RuntimeConfidence.HIGH)

    def test_terminal_enriched_with_agent_state(self):
        adapter = self._adapter_with_fixtures()
        sessions = {s.session_id: s for s in adapter.discover()}
        session = sessions["term_74adc5b8-8539-4151-9d75-9a3ed2a0ae10"]
        self.assertEqual(session.agent, "opencode")
        self.assertEqual(session.status, RuntimeStatus.DONE)
        self.assertEqual(session.project, "social-media-operations")
        self.assertEqual(session.activity, "Daily logbook update")
        self.assertEqual(derive_activity_state(session.status), "inactive")

    def test_terminal_without_worktree_is_unknown(self):
        adapter = self._adapter_with_fixtures()
        sessions = {s.session_id: s for s in adapter.discover()}
        session = sessions["term_dbdb9172-e057-44d1-9c65-61f242f24ae1"]
        self.assertEqual(session.agent, "claude")
        self.assertEqual(session.status, RuntimeStatus.UNKNOWN)
        # No host-reported repo → project falls back to basename(workspace)
        self.assertEqual(session.project, "japan-cannabinoid-trends")

    def test_worktree_agent_without_terminal_becomes_session(self):
        adapter = self._adapter_with_fixtures()
        sessions = {s.session_id: s for s in adapter.discover()}
        session = sessions["pane-0002"]
        self.assertEqual(session.agent, "codex")
        self.assertEqual(session.status, RuntimeStatus.WORKING)
        self.assertEqual(session.project, "agent-bank")
        self.assertEqual(derive_activity_state(session.status), "active")

    def test_shell_terminal_without_agent_identity_skipped(self):
        adapter = self._adapter_with_fixtures()
        sessions = adapter.discover()
        self.assertFalse(any(s.session_id == "term_plain_shell" for s in sessions))

    def test_unknown_agent_state_maps_to_unknown(self):
        self.assertEqual(agent_state_status({"state": "daydreaming"}), RuntimeStatus.UNKNOWN)
        self.assertEqual(agent_state_status(None), RuntimeStatus.UNKNOWN)
        self.assertEqual(agent_state_status({"state": "done"}), RuntimeStatus.DONE)

    @patch("ai_adapter.runtime.adapters.orca.run_host_command")
    def test_discover_returns_empty_on_cli_failure(self, mock_run):
        mock_run.side_effect = lambda argv, timeout=10.0: _fail_result(argv)
        self.assertEqual(OrcaAdapter().discover(), [])

    @patch("ai_adapter.runtime.adapters.orca.run_host_command")
    def test_discover_returns_empty_on_malformed_json(self, mock_run):
        mock_run.side_effect = lambda argv, timeout=10.0: _ok_result(argv, "{broken")
        self.assertEqual(OrcaAdapter().discover(), [])

    @patch("ai_adapter.runtime.adapters.orca.run_host_command")
    def test_discover_never_raises_on_internal_exception(self, mock_run):
        mock_run.side_effect = RuntimeError("unexpected")
        self.assertEqual(OrcaAdapter().discover(), [])

    @patch("ai_adapter.runtime.adapters.orca.shutil.which", return_value=None)
    def test_is_available_false_without_cli(self, _mock_which):
        self.assertFalse(OrcaAdapter().is_available())

    @patch("ai_adapter.runtime.adapters.orca.shutil.which", return_value="/usr/local/bin/orca")
    def test_is_available_true_with_cli(self, _mock_which):
        self.assertTrue(OrcaAdapter().is_available())

    @patch("ai_adapter.runtime.adapters.orca.shutil.which", return_value=None)
    def test_capabilities_declare_no_when_unavailable(self, _mock_which):
        caps = OrcaAdapter().capabilities()
        self.assertEqual(caps.host, "orca")
        for value in (
            caps.discover,
            caps.project,
            caps.agent,
            caps.activity,
            caps.working,
            caps.waiting,
            caps.done,
            caps.needs_user,
        ):
            self.assertIn(value, ("NO", "UNKNOWN"))

    @patch("ai_adapter.runtime.adapters.orca.shutil.which", return_value="/usr/local/bin/orca")
    def test_capabilities_declare_observables_when_available(self, _mock_which):
        caps = OrcaAdapter().capabilities()
        self.assertEqual(caps.discover, "YES")
        self.assertEqual(caps.agent, "YES")
        self.assertEqual(caps.needs_user, "UNKNOWN")


class TestVSCodeAdapter(unittest.TestCase):
    """VS Code process-observation fallback with mocked ps output."""

    def _adapter_with_ps(self) -> VSCodeAdapter:
        processes = parse_ps_output(_fixture("vscode_ps.txt"))
        patcher = patch(
            "ai_adapter.runtime.adapters.vscode.observe_processes",
            return_value=processes,
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        cwd_patcher = patch(
            "ai_adapter.runtime.adapters.base.process_cwd",
            side_effect=lambda pid, timeout=5.0: (
                "/Users/x/OS/home/Codes/github.com/routeflags/demo-project" if pid == 40001 else ""
            ),
        )
        cwd_patcher.start()
        self.addCleanup(cwd_patcher.stop)
        return VSCodeAdapter()

    def test_discovers_attributed_agent_processes(self):
        adapter = self._adapter_with_ps()
        sessions = adapter.discover()
        self.assertEqual(len(sessions), 3)
        agents = {s.agent for s in sessions}
        self.assertEqual(agents, {"copilot", "codex", "opencode"})
        for session in sessions:
            self.assertEqual(session.host, "vscode")
            self.assertEqual(session.status, RuntimeStatus.UNKNOWN)
            self.assertEqual(session.source, RuntimeSource.PROCESS)
            self.assertEqual(session.confidence, RuntimeConfidence.LOW)

    def test_workspace_enriches_project(self):
        adapter = self._adapter_with_ps()
        sessions = {s.session_id: s for s in adapter.discover()}
        session = sessions["ses_abc123def456"]
        self.assertEqual(session.workspace, "/Users/x/OS/home/Codes/github.com/routeflags/demo-project")
        self.assertEqual(session.project, "demo-project")

    @patch("ai_adapter.runtime.adapters.vscode.observe_processes", return_value=[])
    def test_discover_returns_empty_when_ps_fails(self, _mock_ps):
        self.assertEqual(VSCodeAdapter().discover(), [])

    @patch("ai_adapter.runtime.adapters.vscode.observe_processes")
    def test_discover_never_raises_on_internal_exception(self, mock_ps):
        mock_ps.side_effect = RuntimeError("ps exploded")
        self.assertEqual(VSCodeAdapter().discover(), [])

    @patch("ai_adapter.runtime.adapters.vscode.shutil.which", return_value=None)
    @patch("ai_adapter.runtime.adapters.vscode.observe_processes", return_value=[])
    def test_is_available_false_without_cli_or_process(self, _mock_ps, _mock_which):
        self.assertFalse(VSCodeAdapter().is_available())

    @patch("ai_adapter.runtime.adapters.vscode.shutil.which", return_value=None)
    @patch(
        "ai_adapter.runtime.adapters.vscode.observe_processes",
        return_value=parse_ps_output(_fixture("vscode_ps.txt")),
    )
    def test_is_available_true_when_host_process_running(self, _mock_ps, _mock_which):
        self.assertTrue(VSCodeAdapter().is_available())

    @patch("ai_adapter.runtime.adapters.vscode.shutil.which", return_value=None)
    @patch("ai_adapter.runtime.adapters.vscode.observe_processes", return_value=[])
    def test_capabilities_declare_partial_for_fallback(self, _mock_ps, _mock_which):
        # Not installed → NO; availability is exercised via a separate path
        caps = VSCodeAdapter().capabilities()
        self.assertEqual(caps.host, "vscode")
        self.assertEqual(caps.discover, "NO")

    @patch("ai_adapter.runtime.adapters.vscode.shutil.which", return_value="/usr/local/bin/code")
    def test_capabilities_declare_partial_when_available(self, _mock_which):
        caps = VSCodeAdapter().capabilities()
        self.assertEqual(caps.discover, "PARTIAL")
        self.assertEqual(caps.agent, "YES")
        self.assertEqual(caps.working, "NO")


class TestZedAdapter(unittest.TestCase):
    """Zed process-observation fallback with mocked ps output."""

    def _adapter_with_ps(self) -> ZedAdapter:
        processes = parse_ps_output(_fixture("zed_ps.txt"))
        patcher = patch("ai_adapter.runtime.adapters.zed.observe_processes", return_value=processes)
        patcher.start()
        self.addCleanup(patcher.stop)
        return ZedAdapter()

    def test_discovers_terminal_spawned_agent(self):
        adapter = self._adapter_with_ps()
        sessions = adapter.discover()
        self.assertEqual(len(sessions), 1)
        session = sessions[0]
        self.assertEqual(session.host, "zed")
        self.assertEqual(session.agent, "claude")
        self.assertEqual(session.status, RuntimeStatus.UNKNOWN)
        self.assertEqual(session.source, RuntimeSource.PROCESS)
        self.assertEqual(session.confidence, RuntimeConfidence.LOW)
        # Zed's own processes must not be reported as agent sessions
        self.assertNotEqual(session.session_id, "25194")

    @patch("ai_adapter.runtime.adapters.zed.observe_processes", return_value=[])
    def test_discover_returns_empty_when_ps_fails(self, _mock_ps):
        self.assertEqual(ZedAdapter().discover(), [])

    @patch("ai_adapter.runtime.adapters.zed.shutil.which", return_value=None)
    @patch("ai_adapter.runtime.adapters.zed.observe_processes", return_value=[])
    def test_capabilities_declare_no_when_unavailable(self, _mock_ps, _mock_which):
        caps = ZedAdapter().capabilities()
        self.assertEqual(caps.host, "zed")
        self.assertEqual(caps.discover, "NO")

    @patch("ai_adapter.runtime.adapters.zed.shutil.which", return_value="/usr/local/bin/zed")
    def test_capabilities_declare_partial_when_available(self, _mock_which):
        caps = ZedAdapter().capabilities()
        self.assertEqual(caps.discover, "PARTIAL")
        self.assertEqual(caps.agent, "PARTIAL")


class TestAdapterContract(unittest.TestCase):
    """Every registered adapter implements the RuntimeAdapter interface."""

    def test_registered_types_are_runtime_adapters(self):
        self.assertEqual(ADAPTER_TYPES, [OrcaAdapter, VSCodeAdapter, ZedAdapter])
        for adapter_type in ADAPTER_TYPES:
            self.assertTrue(issubclass(adapter_type, RuntimeAdapter))

    def test_host_names(self):
        self.assertEqual(OrcaAdapter().host_name, "orca")
        self.assertEqual(VSCodeAdapter().host_name, "vscode")
        self.assertEqual(ZedAdapter().host_name, "zed")

    def test_unavailable_capabilities_helper(self):
        caps = unavailable_capabilities("ghost-host")
        self.assertEqual(caps.host, "ghost-host")
        self.assertEqual(caps.discover, "NO")
        self.assertEqual(caps.needs_user, "NO")


class TestRegistry(unittest.TestCase):
    """create_adapters / discover_sessions: availability + exception isolation."""

    @patch("ai_adapter.runtime.adapters.zed.shutil.which", return_value=None)
    @patch("ai_adapter.runtime.adapters.zed.observe_processes", return_value=[])
    @patch("ai_adapter.runtime.adapters.vscode.shutil.which", return_value=None)
    @patch("ai_adapter.runtime.adapters.vscode.observe_processes", return_value=[])
    @patch("ai_adapter.runtime.adapters.orca.shutil.which", return_value=None)
    def test_create_adapters_skips_all_unavailable(self, _o, _v_which, _v_ps, _z_which, _z_ps):
        self.assertEqual(create_adapters(), [])

    def test_create_adapters_isolates_raising_adapter(self):
        class _BoomAdapter:
            def __init__(self):
                raise RuntimeError("adapter exploded")

        class _GoodAdapter(RuntimeAdapter):
            @property
            def host_name(self) -> str:
                return "good"

            def is_available(self) -> bool:
                return True

            def discover(self) -> list[RuntimeSession]:
                return []

            def inspect(self, session_id: str) -> RuntimeSession | None:
                return None

            def capabilities(self):
                return unavailable_capabilities(self.host_name)

        with patch("ai_adapter.runtime.registry.ADAPTER_TYPES", [_BoomAdapter, _GoodAdapter]):
            adapters = create_adapters()
        self.assertEqual(len(adapters), 1)
        self.assertEqual(adapters[0].host_name, "good")

    def test_discover_sessions_empty_input(self):
        self.assertEqual(discover_sessions([]), [])

    def test_discover_sessions_merges_and_isolates_failures(self):
        def _session(host: str, project: str) -> RuntimeSession:
            return RuntimeSession(
                session_id=f"{host}-1",
                host=host,
                agent="codex",
                project=project,
                workspace=f"/w/{project}",
                status=RuntimeStatus.UNKNOWN,
                source=RuntimeSource.PROCESS,
                confidence=RuntimeConfidence.LOW,
            )

        class _FakeAdapter(RuntimeAdapter):
            def __init__(self, host: str, sessions: list[RuntimeSession], explode: bool = False):
                self._host = host
                self._sessions = sessions
                self._explode = explode

            @property
            def host_name(self) -> str:
                return self._host

            def is_available(self) -> bool:
                return True

            def discover(self) -> list[RuntimeSession]:
                if self._explode:
                    raise RuntimeError("discover exploded")
                return self._sessions

            def inspect(self, session_id: str) -> RuntimeSession | None:
                return None

            def capabilities(self):
                return unavailable_capabilities(self.host_name)

        adapters = [
            _FakeAdapter("orca", [_session("orca", "alpha")]),
            _FakeAdapter("vscode", [_session("vscode", "beta")], explode=True),
            _FakeAdapter("zed", [_session("zed", "gamma")]),
        ]
        sessions = discover_sessions(adapters)
        self.assertEqual([s.host for s in sessions], ["orca", "zed"])

    def test_discover_sessions_sorts_deterministically(self):
        class _FixedAdapter(RuntimeAdapter):
            @property
            def host_name(self) -> str:
                return "orca"

            def is_available(self) -> bool:
                return True

            def discover(self) -> list[RuntimeSession]:
                return [
                    RuntimeSession(
                        session_id="b",
                        host="orca",
                        agent="codex",
                        project="zeta",
                        workspace="/w/zeta",
                        status=RuntimeStatus.UNKNOWN,
                        source=RuntimeSource.CLI,
                        confidence=RuntimeConfidence.HIGH,
                    ),
                    RuntimeSession(
                        session_id="a",
                        host="orca",
                        agent="claude",
                        project="alpha",
                        workspace="/w/alpha",
                        status=RuntimeStatus.UNKNOWN,
                        source=RuntimeSource.CLI,
                        confidence=RuntimeConfidence.HIGH,
                    ),
                ]

            def inspect(self, session_id: str) -> RuntimeSession | None:
                return None

            def capabilities(self):
                return unavailable_capabilities(self.host_name)

        sessions = discover_sessions([_FixedAdapter()])
        self.assertEqual([s.project for s in sessions], ["alpha", "zeta"])


class TestInspect(unittest.TestCase):
    """inspect() returns a matching session or None (contract §3)."""

    def test_inspect_matches_discovered_session(self):
        session = RuntimeSession(
            session_id="term-1",
            host="orca",
            agent="opencode",
            project="ec-cube",
            workspace="/w/ec-cube",
            status=RuntimeStatus.DONE,
            source=RuntimeSource.CLI,
            confidence=RuntimeConfidence.HIGH,
            started_at=datetime(2026, 10, 6, 18, 0, 0, tzinfo=timezone.utc),
        )

        class _OneSessionAdapter(OrcaAdapter):
            def discover(self) -> list[RuntimeSession]:
                return [session]

        adapter = _OneSessionAdapter()
        self.assertEqual(adapter.inspect("term-1"), session)
        self.assertIsNone(adapter.inspect("missing"))


if __name__ == "__main__":
    unittest.main()


class TestOrcaMultiPaneRegression(unittest.TestCase):
    """Review C1: multi-pane worktrees must keep every pane."""

    def test_multi_pane_same_agent_kept(self):
        """Two opencode panes in one worktree → 2 sessions, not 1."""
        from ai_adapter.runtime.adapters.orca import OrcaAdapter

        terminals = [
            {"paneKey": "p1", "agentIdentity": "opencode", "worktreePath": "/w/dup", "lastOutputAt": 1000},
            {"paneKey": "p2", "agentIdentity": "opencode", "worktreePath": "/w/dup", "lastOutputAt": 2000},
        ]
        worktrees = [
            {
                "path": "/w/dup",
                "agents": [
                    {"paneKey": "p1", "agentType": "opencode", "state": "working"},
                    {"paneKey": "p2", "agentType": "opencode", "state": "waiting"},
                ],
            }
        ]
        adapter = OrcaAdapter.__new__(OrcaAdapter)
        sessions = adapter._merge_sessions(terminals, worktrees)
        self.assertEqual(len(sessions), 2)
        states = sorted(s.status.value for s in sessions)
        self.assertEqual(states, ["waiting", "working"])


class TestDetectAgentFalsePositive(unittest.TestCase):
    """Review M2: non-agent argument tokens must not match."""

    def test_grep_claude_not_detected(self):
        from ai_adapter.runtime.adapters.base import detect_agent

        self.assertIsNone(detect_agent("grep claude notes.txt"))

    def test_echo_opencode_not_detected(self):
        from ai_adapter.runtime.adapters.base import detect_agent

        self.assertIsNone(detect_agent("echo opencode"))

    def test_interpreter_path_still_detected(self):
        """node /path/to/codex must still be detected (path token)."""
        from ai_adapter.runtime.adapters.base import detect_agent

        self.assertIsNotNone(detect_agent("node /usr/local/bin/codex --serve"))

    def test_argv0_still_detected(self):
        from ai_adapter.runtime.adapters.base import detect_agent

        self.assertIsNotNone(detect_agent("claude --resume"))


class TestVSCodeWorkspaceAttribution(unittest.TestCase):
    """VS Code project attribution via windowsState + lsof window handles."""

    def _write_storage(self, base: Path, payload: dict) -> Path:
        target = base / "User/globalStorage"
        target.mkdir(parents=True)
        (target / "storage.json").write_text(json.dumps(payload), encoding="utf-8")
        return base

    def test_open_workspace_folders_parses_windows_state(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "proj-a").mkdir()
            (base / "proj b").mkdir()
            self._write_storage(
                base,
                {
                    "windowsState": {
                        "lastActiveWindow": {"folder": f"file://{base}/proj-a"},
                        "openedWindows": [
                            {"folder": f"file://{base}/proj%20b"},
                            {"folder": "vscode-remote://ssh-2Bremote/home/remote"},
                        ],
                    }
                },
            )
            folders = open_workspace_folders(user_data_dir=base)
            self.assertEqual(folders, {f"{base}/proj-a", f"{base}/proj b"})

    def test_open_workspace_folders_missing_file_returns_empty(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(open_workspace_folders(user_data_dir=Path(tmp)), set())

    def test_open_workspace_folders_corrupt_json_returns_empty(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            target = base / "User/globalStorage"
            target.mkdir(parents=True)
            (target / "storage.json").write_text("{not json", encoding="utf-8")
            self.assertEqual(open_workspace_folders(user_data_dir=base), set())

    def test_open_workspace_folders_skips_nonexistent_paths(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            base = self._write_storage(
                Path(tmp),
                {"windowsState": {"lastActiveWindow": {"folder": f"file://{tmp}/does-not-exist"}}},
            )
            self.assertEqual(open_workspace_folders(user_data_dir=base), set())

    def _processes(self):
        return parse_ps_output(_fixture("vscode_ps.txt"))

    def test_attribute_workspaces_single_folder_per_root(self):
        processes = self._processes()
        handles = {
            13311: {"/Users/x/project-a"},  # copilot-runtime window root
            33658: {"/Users/x/project-b"},  # codex/opencode window root
        }
        with patch(
            "ai_adapter.runtime.adapters.vscode.process_open_handles",
            return_value=handles,
        ):
            result = attribute_workspaces(processes, {"/Users/x/project-a", "/Users/x/project-b"})
        self.assertEqual(result, {13311: "/Users/x/project-a", 33658: "/Users/x/project-b"})

    def test_attribute_workspaces_ambiguous_root_not_attributed(self):
        processes = self._processes()
        folders = {"/Users/x/project-b", "/Users/x/project-c"}
        handles = {33658: {"/Users/x/project-b", "/Users/x/project-c"}}
        with patch(
            "ai_adapter.runtime.adapters.vscode.process_open_handles",
            return_value=handles,
        ):
            result = attribute_workspaces(processes, folders)
        self.assertEqual(result, {})

    def test_attribute_workspaces_empty_folders_returns_empty(self):
        self.assertEqual(attribute_workspaces(self._processes(), set()), {})

    def test_attribute_workspaces_nested_path_matches_folder(self):
        """A file handle under the folder root maps to that folder."""
        processes = self._processes()
        handles = {33658: {"/Users/x/project-b/.vscode/mcp.json"}}
        with patch(
            "ai_adapter.runtime.adapters.vscode.process_open_handles",
            return_value=handles,
        ):
            result = attribute_workspaces(processes, {"/Users/x/project-b"})
        self.assertEqual(result, {33658: "/Users/x/project-b"})

    def _adapter_with_attribution(self, handles: dict, folders: set | None = None) -> VSCodeAdapter:
        processes = parse_ps_output(_fixture("vscode_ps.txt"))
        patcher = patch(
            "ai_adapter.runtime.adapters.vscode.observe_processes",
            return_value=processes,
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        folders_patcher = patch(
            "ai_adapter.runtime.adapters.vscode.open_workspace_folders",
            return_value=folders if folders is not None else {"/Users/x/project-a", "/Users/x/project-b"},
        )
        folders_patcher.start()
        self.addCleanup(folders_patcher.stop)
        handles_patcher = patch(
            "ai_adapter.runtime.adapters.vscode.process_open_handles",
            return_value=handles,
        )
        handles_patcher.start()
        self.addCleanup(handles_patcher.stop)
        # cwd unusable on macOS: all VS Code processes run with cwd "/"
        cwd_patcher = patch(
            "ai_adapter.runtime.adapters.base.process_cwd",
            side_effect=lambda pid, timeout=5.0: "",
        )
        cwd_patcher.start()
        self.addCleanup(cwd_patcher.stop)
        return VSCodeAdapter()

    def test_discover_fills_project_from_window_attribution(self):
        adapter = self._adapter_with_attribution({13311: {"/Users/x/project-a"}, 33658: {"/Users/x/project-b"}})
        sessions = {s.session_id: s for s in adapter.discover()}
        self.assertEqual(len(sessions), 3)
        self.assertEqual(sessions["ses_abc123def456"].project, "project-b")
        self.assertEqual(sessions["ses_abc123def456"].workspace, "/Users/x/project-b")
        copilot = next(s for s in sessions.values() if s.agent == "copilot")
        self.assertEqual(copilot.project, "project-a")

    def test_discover_leaves_project_empty_when_ambiguous(self):
        adapter = self._adapter_with_attribution(
            {33658: {"/Users/x/project-b", "/Users/x/project-c"}},
            folders={"/Users/x/project-b", "/Users/x/project-c"},
        )
        for session in adapter.discover():
            self.assertEqual(session.project, "")
            self.assertEqual(session.workspace, "")

    def test_discover_leaves_project_empty_when_no_handles(self):
        adapter = self._adapter_with_attribution({})
        for session in adapter.discover():
            self.assertEqual(session.project, "")


class TestElapsedTimeParsing(unittest.TestCase):
    """ps etime parsing feeds the monitor AGE column."""

    def test_parse_elapsed_variants(self):
        self.assertEqual(parse_elapsed_seconds("45"), 45)
        self.assertEqual(parse_elapsed_seconds("05:45"), 345)
        self.assertEqual(parse_elapsed_seconds("01:05:45"), 3945)
        self.assertEqual(parse_elapsed_seconds("1-02:03:04"), 93784)
        self.assertIsNone(parse_elapsed_seconds(""))
        self.assertIsNone(parse_elapsed_seconds("n/a"))

    def test_parse_ps_output_with_etime_column(self):
        processes = parse_ps_output(_fixture("vscode_ps.txt"))
        by_pid = {p.pid: p for p in processes}
        self.assertEqual(by_pid[11820].elapsed_seconds, 192)  # 3:12
        self.assertEqual(by_pid[33729].elapsed_seconds, 47)  # 0:47
        self.assertIn("codex", by_pid[33729].command)
        self.assertIn("Electron", by_pid[11820].command)

    def test_parse_ps_output_without_etime_column(self):
        """Legacy 3-column layout still parses; elapsed stays None."""
        output = "  1234     5 /usr/bin/node server.js --port 8080\n"
        processes = parse_ps_output(output)
        self.assertEqual(len(processes), 1)
        self.assertEqual(processes[0].command, "/usr/bin/node server.js --port 8080")
        self.assertIsNone(processes[0].elapsed_seconds)

    def test_command_starting_with_number_not_mistaken_for_etime(self):
        """A command whose first word is numeric must not lose that token."""
        output = "  1234     5 2ndword --flag value\n"
        processes = parse_ps_output(output)
        self.assertEqual(processes[0].command, "2ndword --flag value")
        self.assertIsNone(processes[0].elapsed_seconds)

    def test_session_from_process_sets_started_at(self):
        processes = parse_ps_output(_fixture("vscode_ps.txt"))
        opencode = next(p for p in processes if p.pid == 40001)
        with patch(
            "ai_adapter.runtime.adapters.base.process_cwd",
            side_effect=lambda pid, timeout=5.0: "",
        ):
            session = session_from_process("vscode", opencode)
        self.assertIsNotNone(session.started_at)
        age_seconds = (datetime.now(timezone.utc) - session.started_at).total_seconds()
        self.assertGreaterEqual(age_seconds, 0)
        self.assertLess(age_seconds, 120)  # etime was 0:12

    def test_zed_fixture_parses_etime(self):
        processes = parse_ps_output(_fixture("zed_ps.txt"))
        by_pid = {p.pid: p for p in processes}
        self.assertEqual(by_pid[60001].elapsed_seconds, 75)  # 1:15
