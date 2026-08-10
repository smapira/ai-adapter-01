#!/usr/bin/env bash
# run_tests.sh — Run the test suite inside an isolated sandbox directory.
#
# WHY THIS EXISTS
# The tests operate on `Path.cwd() / ".github"` (and opencode.json, AGENTS.md,
# .mcp.json, etc.). Running them from the repository root would let them touch
# the **real** `.github/` directory — backing it up, deleting it, and restoring
# it mid-run. If the run is interrupted before teardown, `.github/workflows`
# is permanently lost (this happened and took down CI + PyPI publishing).
#
# This runner changes the working directory to a sandbox (`.testbox/`) and
# executes the suite there, so `Path.cwd()` points inside the sandbox and the
# real repository files are never touched.
#
# CRITICAL: we run under **pytest**, not `unittest discover`, because
# `tests/conftest.py` (which chdirs every test into a fresh tmp dir) is a pytest
# plugin. Under a bare `unittest` run, `add_to_gitignore()` walks up from
# `.testbox/`, finds the real repo's `.git`, and appends test artefacts to the
# real `.gitignore` — polluting the repository. pytest + conftest closes that
# hole.
#
# USAGE
#   bash scripts/run_tests.sh            # full suite, quiet
#   bash scripts/run_tests.sh -v         # full suite, verbose
#   bash scripts/run_tests.sh tests/test_prompt.py  # single test file
#   bash scripts/run_tests.sh tests/test_env.py -k add  # file + keyword filter
#
# The script forwards extra arguments to pytest. `uv run --project ..` makes
# sure the project's own venv/config (pyproject.toml) is used even though we
# run from inside the sandbox directory.
set -euo pipefail

# Resolve the repository root (parent of this script's directory).
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# Guard against an empty ROOT (cd failure would make `rm -rf /.testbox`).
[[ -n "$ROOT" ]] || { echo "run_tests.sh: failed to resolve repo root" >&2; exit 1; }
SANDBOX="$ROOT/.testbox"

# Reset the sandbox directory for a clean slate. A stale sandbox (e.g. from an
# aborted run) can mask test-environment problems, so always start fresh.
rm -rf "$SANDBOX"
mkdir -p "$SANDBOX"

# Run tests with the sandbox as the working directory (cwd = sandbox).
# - `--project "$ROOT"` : use the project's pyproject.toml / venv from anywhere
# - `--rootdir "$ROOT"` : pytest resolves conftest + config from the repo root
# - default target      : the real suite; any `tests/...` positional arg given
#   by the caller is resolved to an absolute path so it works despite the
#   sandbox cwd (a relative `tests/x.py` would resolve inside .testbox/).
cd "$SANDBOX"

args=()
target_given=0
for a in "$@"; do
    if [[ $a == tests/* ]]; then
        # tests/test_env.py -> absolute path (sandbox cwd would mis-resolve)
        args+=("$ROOT/$a")
        target_given=1
    elif [[ $a == tests\.* ]]; then
        # tests.test_env (legacy dotted form) -> tests/test_env.py
        # NB: use ${a//.//} (not ${a//./\/}) — bash 3.2 on macOS escapes the
        # replacement slash, yielding a literal backslash in the path.
        file="${a//.//}"        # tests.test_env -> tests/test_env
        args+=("$ROOT/${file}.py")
        target_given=1
    elif [[ $a != -* ]]; then
        args+=("$a")
        target_given=1
    else
        args+=("$a")
    fi
done

# Default: run the whole suite unless the caller supplied a path target.
# (A plain flag like `-v` must not suppress the default — it would collect 0
# items from the empty sandbox cwd and fail CI with exit code 5.)
if [[ $target_given -eq 0 ]]; then
    args+=("$ROOT/tests")
fi

exec uv run --project "$ROOT" python -m pytest --rootdir "$ROOT" "${args[@]}"