"""npx wrapper module.

Provides functions to detect, query, and execute ``npx`` commands,
with a focus on wrapping ``npx skills`` for seamless integration with
ai-adapter's skill management.
"""

from __future__ import annotations

import shutil
import subprocess


def find_npx() -> str | None:
    """Detect the ``npx`` executable on PATH.

    Returns the absolute path to ``npx`` when found, or ``None`` when
    it is not installed or not reachable.
    """
    return shutil.which("npx")


def get_npx_version() -> str | None:
    """Return the ``npx`` version string (e.g. ``"10.9.2"``).

    Returns ``None`` when npx is not installed or the version cannot
    be determined.
    """
    npx_path = find_npx()
    if npx_path is None:
        return None
    try:
        result = subprocess.run(
            [npx_path, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


def run_npx_skills(
    args: list[str],
    timeout: int = 60,
) -> tuple[int, str, str]:
    """Execute ``npx skills`` with the given arguments.

    Args:
        args: Arguments passed after ``npx skills``.
        timeout: Maximum execution time in seconds (default 60).

    Returns:
        A ``(exit_code, stdout, stderr)`` tuple.

    Exit codes:
        - 0: Success
        - 127: npx not found
        - 124: Timeout
        - Other: npx/skills exit code
    """
    npx_path = find_npx()
    if npx_path is None:
        return (127, "", "npx is not installed or not in PATH")

    cmd = [npx_path, "skills"] + args
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return (result.returncode, result.stdout, result.stderr)
    except subprocess.TimeoutExpired:
        return (124, "", f"npx skills timed out after {timeout}s")
    except FileNotFoundError:
        return (127, "", f"npx not found at {npx_path}")


def is_npx_available() -> bool:
    """Return True when npx is installed and reachable."""
    return find_npx() is not None
