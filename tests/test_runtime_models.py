"""Tests for the Canonical Runtime Model and the normalizer vocabulary."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from ai_adapter.runtime.models import (
    RuntimeCapabilities,
    RuntimeConfidence,
    RuntimeSession,
    RuntimeSource,
    RuntimeStatus,
)
from ai_adapter.runtime.normalizer import (
    SOURCE_CONFIDENCE,
    confidence_for_source,
    derive_activity_state,
    epoch_millis_to_datetime,
    normalize_agent,
    project_name,
    runtime_session_to_dict,
)


class TestRuntimeEnums(unittest.TestCase):
    """Enum vocabulary is lowercase and matches the design (§2.3)."""

    def test_status_values(self):
        self.assertEqual(
            [s.value for s in RuntimeStatus],
            ["working", "waiting", "blocked", "done", "idle", "unknown"],
        )

    def test_confidence_values(self):
        self.assertEqual([c.value for c in RuntimeConfidence], ["high", "medium", "low"])

    def test_source_values(self):
        self.assertEqual(
            [s.value for s in RuntimeSource],
            ["hook", "cli", "api", "acp", "metadata", "terminal", "file", "process", "heuristic"],
        )

    def test_serialized_values_are_lowercase(self):
        """JSON serialization must emit lowercase enum values (design §6.3)."""
        self.assertEqual(RuntimeStatus.WORKING.value, "working")
        self.assertEqual(RuntimeSource.PROCESS.value, "process")
        self.assertEqual(RuntimeConfidence.LOW.value, "low")


class TestRuntimeSessionModel(unittest.TestCase):
    """RuntimeSession dataclass structure and defaults."""

    def _session(self, **overrides) -> RuntimeSession:
        base = dict(
            session_id="abc123",
            host="orca",
            agent="opencode",
            project="ec-cube",
            workspace="/path/to/ec-cube",
            status=RuntimeStatus.UNKNOWN,
            source=RuntimeSource.CLI,
            confidence=RuntimeConfidence.HIGH,
        )
        base.update(overrides)
        return RuntimeSession(**base)

    def test_required_fields(self):
        session = self._session()
        self.assertEqual(session.session_id, "abc123")
        self.assertEqual(session.host, "orca")
        self.assertEqual(session.agent, "opencode")
        self.assertEqual(session.project, "ec-cube")
        self.assertEqual(session.workspace, "/path/to/ec-cube")

    def test_optional_defaults(self):
        session = self._session()
        self.assertEqual(session.activity, "")
        self.assertIsNone(session.needs_user)
        self.assertIsNone(session.started_at)
        self.assertIsNone(session.last_activity_at)

    def test_needs_user_is_independent_of_status(self):
        """BLOCKED + needs_user=True is a valid combination (design §7)."""
        session = self._session(status=RuntimeStatus.BLOCKED, needs_user=True)
        self.assertEqual(session.status, RuntimeStatus.BLOCKED)
        self.assertIs(session.needs_user, True)

    def test_capabilities_dataclass(self):
        caps = RuntimeCapabilities(
            host="orca",
            discover="YES",
            project="YES",
            agent="YES",
            activity="YES",
            working="YES",
            waiting="YES",
            done="YES",
            needs_user="UNKNOWN",
        )
        self.assertEqual(caps.host, "orca")
        self.assertEqual(caps.needs_user, "UNKNOWN")


class TestActivityStateDerivation(unittest.TestCase):
    """P2 derivation rule (design §2.4.1): ACTIVE / INACTIVE / UNKNOWN."""

    def test_active_statuses(self):
        for status in (RuntimeStatus.WORKING, RuntimeStatus.WAITING, RuntimeStatus.BLOCKED):
            self.assertEqual(derive_activity_state(status), "active", status)

    def test_inactive_statuses(self):
        for status in (RuntimeStatus.IDLE, RuntimeStatus.DONE):
            self.assertEqual(derive_activity_state(status), "inactive", status)

    def test_unknown_status(self):
        self.assertEqual(derive_activity_state(RuntimeStatus.UNKNOWN), "unknown")

    def test_derived_values_are_lowercase(self):
        self.assertEqual(derive_activity_state(RuntimeStatus.WORKING), "active")


class TestSourceConfidenceMapping(unittest.TestCase):
    """Confidence follows the Source→Confidence table (design §2.5)."""

    def test_high_confidence_sources(self):
        for source in (RuntimeSource.HOOK, RuntimeSource.CLI, RuntimeSource.API, RuntimeSource.ACP):
            self.assertEqual(confidence_for_source(source), RuntimeConfidence.HIGH, source)

    def test_medium_confidence_sources(self):
        for source in (RuntimeSource.METADATA, RuntimeSource.TERMINAL):
            self.assertEqual(confidence_for_source(source), RuntimeConfidence.MEDIUM, source)

    def test_low_confidence_sources(self):
        for source in (RuntimeSource.FILE, RuntimeSource.PROCESS, RuntimeSource.HEURISTIC):
            self.assertEqual(confidence_for_source(source), RuntimeConfidence.LOW, source)

    def test_mapping_table_covers_all_sources(self):
        for source in RuntimeSource:
            self.assertIn(source, SOURCE_CONFIDENCE)


class TestProjectNormalization(unittest.TestCase):
    """P1: host-reported project wins, fallback is basename(workspace)."""

    def test_host_reported_value_wins(self):
        self.assertEqual(project_name("ec-cube", "/somewhere/else"), "ec-cube")

    def test_falls_back_to_workspace_basename(self):
        self.assertEqual(project_name(None, "/path/to/kaseifu"), "kaseifu")

    def test_empty_host_reported_falls_back(self):
        self.assertEqual(project_name("", "/path/to/kaseifu"), "kaseifu")

    def test_blank_host_reported_falls_back(self):
        self.assertEqual(project_name("   ", "/path/to/kaseifu"), "kaseifu")

    def test_trailing_slash_stripped(self):
        self.assertEqual(project_name(None, "/path/to/kaseifu/"), "kaseifu")

    def test_empty_everything(self):
        self.assertEqual(project_name(None, ""), "")


class TestAgentNormalization(unittest.TestCase):
    """Agent identity uses the canonical vocabulary (design §9)."""

    def test_lowercased(self):
        self.assertEqual(normalize_agent("OpenCode"), "opencode")
        self.assertEqual(normalize_agent("Claude"), "claude")

    def test_aliases(self):
        self.assertEqual(normalize_agent("copilot-runtime"), "copilot")
        self.assertEqual(normalize_agent("claude-code"), "claude")

    def test_whitespace_stripped(self):
        self.assertEqual(normalize_agent("  codex "), "codex")

    def test_unknown_passthrough(self):
        self.assertEqual(normalize_agent("some-future-agent"), "some-future-agent")


class TestEpochMillisConversion(unittest.TestCase):
    """Orca timestamps are epoch milliseconds → aware UTC datetimes."""

    def test_converts_millis(self):
        converted = epoch_millis_to_datetime(1791208780272)
        self.assertIsNotNone(converted)
        self.assertEqual(converted.tzinfo, timezone.utc)

    def test_none_returns_none(self):
        self.assertIsNone(epoch_millis_to_datetime(None))

    def test_invalid_returns_none(self):
        self.assertIsNone(epoch_millis_to_datetime("not-a-number"))

    def test_zero_returns_epoch(self):
        converted = epoch_millis_to_datetime(0)
        self.assertEqual(converted, datetime(1970, 1, 1, tzinfo=timezone.utc))


class TestRuntimeSessionSerialization(unittest.TestCase):
    """JSON envelope per design §6.3: lowercase values, ISO 8601, null."""

    def _session(self, **overrides) -> RuntimeSession:
        base = dict(
            session_id="abc123",
            host="orca",
            agent="opencode",
            project="ec-cube",
            workspace="/path/to/ec-cube",
            status=RuntimeStatus.WORKING,
            source=RuntimeSource.CLI,
            confidence=RuntimeConfidence.HIGH,
            activity="Running tests",
            needs_user=False,
            started_at=datetime(2026, 10, 6, 18, 32, 0, tzinfo=timezone.utc),
            last_activity_at=datetime(2026, 10, 6, 18, 41, 12, tzinfo=timezone.utc),
        )
        base.update(overrides)
        return RuntimeSession(**base)

    def test_full_envelope(self):
        data = runtime_session_to_dict(self._session())
        self.assertEqual(
            set(data.keys()),
            {
                "session_id",
                "host",
                "agent",
                "project",
                "workspace",
                "status",
                "activity",
                "needs_user",
                "started_at",
                "last_activity_at",
                "source",
                "confidence",
            },
        )

    def test_lowercase_enum_values(self):
        data = runtime_session_to_dict(self._session())
        self.assertEqual(data["status"], "working")
        self.assertEqual(data["source"], "cli")
        self.assertEqual(data["confidence"], "high")

    def test_iso8601_datetimes(self):
        data = runtime_session_to_dict(self._session())
        self.assertEqual(data["started_at"], "2026-10-06T18:32:00+00:00")
        self.assertEqual(data["last_activity_at"], "2026-10-06T18:41:12+00:00")

    def test_none_values_become_null(self):
        data = runtime_session_to_dict(self._session(needs_user=None, started_at=None, last_activity_at=None))
        self.assertIsNone(data["needs_user"])
        self.assertIsNone(data["started_at"])
        self.assertIsNone(data["last_activity_at"])


if __name__ == "__main__":
    unittest.main()
