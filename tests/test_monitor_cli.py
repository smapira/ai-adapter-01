"""Tests for the `ai-adapter monitor` CLI (Runtime Plane entry point)."""

from __future__ import annotations

import json
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from click.testing import CliRunner

from ai_adapter.cli import main
from ai_adapter.commands.monitor import render_session_table
from ai_adapter.runtime.models import (
    RuntimeConfidence,
    RuntimeSession,
    RuntimeSource,
    RuntimeStatus,
)


def _session(
    host: str,
    project: str,
    agent: str,
    status: RuntimeStatus,
    session_id: str = "s1",
    last_activity_at: datetime | None = None,
) -> RuntimeSession:
    return RuntimeSession(
        session_id=session_id,
        host=host,
        agent=agent,
        project=project,
        workspace=f"/w/{project}",
        status=status,
        source=RuntimeSource.CLI,
        confidence=RuntimeConfidence.HIGH,
        activity="working on it",
        needs_user=None,
        started_at=None,
        last_activity_at=last_activity_at,
    )


def _three_host_sessions(now: datetime) -> list[RuntimeSession]:
    return [
        _session("orca", "ec-cube-ai-chat", "opencode", RuntimeStatus.WORKING, "orca-1", now - timedelta(seconds=14)),
        _session("vscode", "kaseifu", "codex", RuntimeStatus.UNKNOWN, "vscode-1", now - timedelta(minutes=2)),
        _session("zed", "cannabinoid-trends", "claude", RuntimeStatus.DONE, "zed-1", now - timedelta(hours=3)),
    ]


class TestMonitorHelp(unittest.TestCase):
    def test_help_lists_option(self):
        result = CliRunner().invoke(main, ["monitor", "--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("--json", result.output)

    def test_registered_on_main(self):
        self.assertIn("monitor", main.commands)


class TestMonitorPlainTable(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    @patch("ai_adapter.commands.monitor.discover_sessions")
    @patch("ai_adapter.commands.monitor.create_adapters")
    def test_table_shows_all_three_hosts(self, mock_create, mock_discover):
        mock_create.return_value = [object(), object(), object()]
        mock_discover.side_effect = lambda adapters: _three_host_sessions(datetime.now(timezone.utc))
        result = self.runner.invoke(main, ["monitor"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Orca", result.output)
        self.assertIn("VSCode", result.output)
        self.assertIn("Zed", result.output)
        self.assertIn("ec-cube-ai-chat", result.output)
        self.assertIn("kaseifu", result.output)
        self.assertIn("cannabinoid-trends", result.output)

    @patch("ai_adapter.commands.monitor.discover_sessions")
    @patch("ai_adapter.commands.monitor.create_adapters")
    def test_table_classifies_activity_state(self, mock_create, mock_discover):
        mock_create.return_value = [object(), object(), object()]
        mock_discover.side_effect = lambda adapters: _three_host_sessions(datetime.now(timezone.utc))
        result = self.runner.invoke(main, ["monitor"])
        # P2: ACTIVE = working/waiting/blocked, INACTIVE = idle/done, UNKNOWN = unknown
        self.assertIn("ACTIVE", result.output)
        self.assertIn("INACTIVE", result.output)
        self.assertIn("UNKNOWN", result.output)

    @patch("ai_adapter.commands.monitor.discover_sessions")
    @patch("ai_adapter.commands.monitor.create_adapters")
    def test_empty_result_is_not_an_error(self, mock_create, mock_discover):
        mock_create.return_value = []
        mock_discover.return_value = []
        result = self.runner.invoke(main, ["monitor"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("(no sessions)", result.output)

    @patch("ai_adapter.commands.monitor.discover_sessions")
    @patch("ai_adapter.commands.monitor.create_adapters")
    def test_host_not_installed_does_not_crash(self, mock_create, mock_discover):
        # All hosts missing → create_adapters returns [] → empty discovery
        mock_create.return_value = []
        mock_discover.return_value = []
        result = self.runner.invoke(main, ["monitor"])
        self.assertEqual(result.exit_code, 0)
        self.assertNotIn("Traceback", result.output)


class TestMonitorJson(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    @patch("ai_adapter.commands.monitor.discover_sessions")
    @patch("ai_adapter.commands.monitor.create_adapters")
    def test_json_envelope_shape(self, mock_create, mock_discover):
        mock_create.return_value = [object(), object(), object()]
        mock_discover.side_effect = lambda adapters: _three_host_sessions(datetime.now(timezone.utc))
        result = self.runner.invoke(main, ["monitor", "--json"])
        self.assertEqual(result.exit_code, 0)
        payload = json.loads(result.output)
        self.assertIn("sessions", payload)
        self.assertEqual(len(payload["sessions"]), 3)

    @patch("ai_adapter.commands.monitor.discover_sessions")
    @patch("ai_adapter.commands.monitor.create_adapters")
    def test_json_values_are_lowercase(self, mock_create, mock_discover):
        mock_create.return_value = [object()]
        mock_discover.side_effect = lambda adapters: [
            _session("orca", "ec-cube", "opencode", RuntimeStatus.WORKING, "orca-1")
        ]
        result = self.runner.invoke(main, ["monitor", "--json"])
        session = json.loads(result.output)["sessions"][0]
        self.assertEqual(session["status"], "working")
        self.assertEqual(session["source"], "cli")
        self.assertEqual(session["confidence"], "high")

    @patch("ai_adapter.commands.monitor.discover_sessions")
    @patch("ai_adapter.commands.monitor.create_adapters")
    def test_json_identity_fields_present(self, mock_create, mock_discover):
        mock_create.return_value = [object()]
        mock_discover.side_effect = lambda adapters: [
            _session("orca", "ec-cube", "opencode", RuntimeStatus.WORKING, "orca-1")
        ]
        result = self.runner.invoke(main, ["monitor", "--json"])
        session = json.loads(result.output)["sessions"][0]
        for key in ("session_id", "host", "agent", "project", "workspace"):
            self.assertIn(key, session)
        self.assertEqual(session["host"], "orca")
        self.assertEqual(session["agent"], "opencode")
        self.assertEqual(session["project"], "ec-cube")

    @patch("ai_adapter.commands.monitor.discover_sessions")
    @patch("ai_adapter.commands.monitor.create_adapters")
    def test_json_empty_sessions(self, mock_create, mock_discover):
        mock_create.return_value = []
        mock_discover.return_value = []
        result = self.runner.invoke(main, ["monitor", "--json"])
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(json.loads(result.output), {"sessions": []})

    @patch("ai_adapter.commands.monitor.discover_sessions")
    @patch("ai_adapter.commands.monitor.create_adapters")
    def test_json_serializes_datetimes_as_iso8601(self, mock_create, mock_discover):
        mock_create.return_value = [object()]
        started = datetime(2026, 10, 6, 18, 32, 0, tzinfo=timezone.utc)
        mock_discover.side_effect = lambda adapters: [
            _session(
                "orca",
                "ec-cube",
                "opencode",
                RuntimeStatus.WORKING,
                "orca-1",
                last_activity_at=started,
            )
        ]
        result = self.runner.invoke(main, ["monitor", "--json"])
        session = json.loads(result.output)["sessions"][0]
        self.assertEqual(session["last_activity_at"], "2026-10-06T18:32:00+00:00")


class TestRenderSessionTable(unittest.TestCase):
    """render() is a pure function (design §6.2 contract)."""

    def setUp(self):
        self.now = datetime(2026, 10, 7, 9, 0, 0, tzinfo=timezone.utc)

    def test_empty_table_shows_placeholder(self):
        output = render_session_table([], now=self.now)
        self.assertIn("HOST", output)
        self.assertIn("(no sessions)", output)

    def test_age_formats_seconds(self):
        session = _session(
            "orca", "p", "opencode", RuntimeStatus.WORKING, last_activity_at=self.now - timedelta(seconds=14)
        )
        self.assertIn("14s", render_session_table([session], now=self.now))

    def test_age_formats_minutes(self):
        session = _session(
            "orca", "p", "opencode", RuntimeStatus.WORKING, last_activity_at=self.now - timedelta(minutes=5)
        )
        self.assertIn("5m", render_session_table([session], now=self.now))

    def test_age_formats_hours(self):
        session = _session("orca", "p", "opencode", RuntimeStatus.IDLE, last_activity_at=self.now - timedelta(hours=3))
        self.assertIn("3h", render_session_table([session], now=self.now))

    def test_age_unknown_without_timestamps(self):
        session = _session("orca", "p", "opencode", RuntimeStatus.UNKNOWN)
        output = render_session_table([session], now=self.now)
        self.assertIn("-", output)

    def test_state_column_uppercase(self):
        session = _session("orca", "p", "opencode", RuntimeStatus.BLOCKED)
        output = render_session_table([session], now=self.now)
        self.assertIn("ACTIVE", output)

    def test_long_project_truncated(self):
        long_project = "a" * 40
        session = _session("orca", long_project, "opencode", RuntimeStatus.WORKING)
        output = render_session_table([session], now=self.now)
        self.assertIn("…", output)


class TestMonitorIntegration(unittest.TestCase):
    """End-to-end through the real registry with all hosts unavailable."""

    @patch("ai_adapter.runtime.adapters.zed.shutil.which", return_value=None)
    @patch("ai_adapter.runtime.adapters.zed.observe_processes", return_value=[])
    @patch("ai_adapter.runtime.adapters.vscode.shutil.which", return_value=None)
    @patch("ai_adapter.runtime.adapters.vscode.observe_processes", return_value=[])
    @patch("ai_adapter.runtime.adapters.orca.shutil.which", return_value=None)
    def test_no_hosts_installed_json(self, _o, _v_which, _v_ps, _z_which, _z_ps):
        result = CliRunner().invoke(main, ["monitor", "--json"])
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(json.loads(result.output), {"sessions": []})

    @patch("ai_adapter.runtime.adapters.zed.shutil.which", return_value=None)
    @patch("ai_adapter.runtime.adapters.zed.observe_processes", return_value=[])
    @patch("ai_adapter.runtime.adapters.vscode.shutil.which", return_value=None)
    @patch("ai_adapter.runtime.adapters.vscode.observe_processes", return_value=[])
    @patch("ai_adapter.runtime.adapters.orca.shutil.which", return_value=None)
    def test_no_hosts_installed_plain_table(self, _o, _v_which, _v_ps, _z_which, _z_ps):
        result = CliRunner().invoke(main, ["monitor"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("(no sessions)", result.output)


if __name__ == "__main__":
    unittest.main()
