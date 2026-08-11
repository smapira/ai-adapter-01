"""Pytest configuration: isolate every test's working directory.

The test suite operates on ``Path.cwd() / ".github"`` (and opencode.json,
AGENTS.md, .mcp.json, etc.). If tests run from the repository root, a test
that backs up ``.github/``, deletes it, and fails before teardown permanently
destroys ``.github/workflows`` — which took down CI and PyPI publishing once.

This conftest changes the working directory to an isolated temp sandbox for
each test so ``Path.cwd()`` never points at the real repository. Combined with
``scripts/run_tests.sh`` (which chdirs into ``.testbox/`` before invoking the
suite) this gives defense in depth:

1. The runner keeps cwd outside the repo entirely.
2. Even if cwd somehow points at the repo (e.g. bare ``pytest``), this
   autouse fixture redirects each test into a fresh sandbox first.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterator

import pytest


@pytest.fixture(autouse=True)
def _isolate_cwd(tmp_path: Path) -> Iterator[None]:
    """Point each test's working directory at an isolated temp sandbox."""
    old_cwd = Path.cwd()
    os.chdir(tmp_path)
    yield
    os.chdir(old_cwd)


@pytest.fixture
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolate HOME (and the ai-adapter store) for scan/doctor tests.

    ``scan`` / ``doctor`` read ``Path.home()`` (``~/.claude``, ``~/.codex``,
    ``~/.cursor``, ``~/.config/opencode``); the cwd isolation provided by
    :func:`_isolate_cwd` does not protect those directories.  This fixture
    redirects ``Path.home()`` *and* the ``HOME`` environment variable to a
    temp directory, and re-points the module-level ``AI_ADAPTER_DIR`` which
    is evaluated at import time.
    """
    import pathlib

    monkeypatch.setattr(pathlib.Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))

    from ai_adapter import config as cfg

    monkeypatch.setattr(cfg, "AI_ADAPTER_DIR", tmp_path / ".ai-adapter")
    return tmp_path
