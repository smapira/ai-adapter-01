"""Git operation wrapper module.

Wraps git commands via subprocess.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional


class GitError(Exception):
    """Error related to git operations."""


def _run_git(
    args: list[str],
    cwd: Optional[Path] = None,
) -> subprocess.CompletedProcess:
    """Execute a git command.

    Args:
        args: List of git subcommand arguments.
        cwd: Working directory. Defaults to current if None.

    Returns:
        subprocess.CompletedProcess.

    Raises:
        GitError: If the command fails.
    """
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise GitError(
                f"git {' '.join(args)} failed:\n{result.stderr.strip()}"
            )
        return result
    except FileNotFoundError:
        raise GitError("git command not found. Make sure Git is installed.")


def is_repo(path: Path) -> bool:
    """Check if the given directory is a Git repository.

    Uses git rev-parse --git-dir.
    """
    try:
        result = _run_git(["rev-parse", "--git-dir"], cwd=path)
        return result.returncode == 0
    except GitError:
        return False


def init_repo(path: Path) -> None:
    """Initialize a Git repository.

    Runs git init.
    """
    _run_git(["init"], cwd=path)


def has_remote(path: Path) -> bool:
    """Check if a remote repository is configured."""
    try:
        result = _run_git(["remote", "-v"], cwd=path)
        return bool(result.stdout.strip())
    except GitError:
        return False


def add_all(path: Path) -> bool:
    """Run git add -A.

    Returns:
        True if there are staged changes, False otherwise.
    """
    _run_git(["add", "-A"], cwd=path)
    # 変更があるか確認
    # git diff --cached --quiet は変更ありのとき exit code 1 を返す（正常）
    try:
        _run_git(["diff", "--cached", "--quiet"], cwd=path)
        return False  # no changes
    except GitError:
        return True  # changes exist


def commit(path: Path, message: str = "ai-adapter sync") -> None:
    """Run git commit."""
    try:
        _run_git(["commit", "-m", message], cwd=path)
    except GitError as e:
        err_msg = str(e)
        if "Author identity unknown" in err_msg or "Please tell me who you are" in err_msg:
            raise GitError(
                "Git user configuration is not set.\n"
                "Run the following to set user.name and user.email:\n"
                "  git config --global user.email \"you@example.com\"\n"
                "  git config --global user.name \"Your Name\"\n"
                "Or set only for the ~/.ai-adapter repository:\n"
                "  cd ~/.ai-adapter\n"
                "  git config user.email \"you@example.com\"\n"
                "  git config user.name \"Your Name\""
            )
        raise


def is_rebasing(path: Path) -> bool:
    """Check if a rebase is in progress.

    Checks for .git/rebase-apply or .git/rebase-merge.
    """
    try:
        result = _run_git(["rev-parse", "--git-dir"], cwd=path)
        git_dir = Path(result.stdout.strip())
        return (git_dir / "rebase-apply").exists() or (git_dir / "rebase-merge").exists()
    except GitError:
        return False


def get_conflicted_files(path: Path) -> list[str]:
    """Get a list of conflicted files.

    Uses git diff --name-only --diff-filter=U to get Unmerged paths.
    """
    try:
        result = _run_git(["diff", "--name-only", "--diff-filter=U"], cwd=path)
        return [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]
    except GitError:
        return []


def pull_rebase(path: Path, branch: str = "main") -> None:
    """Run git pull --rebase origin <branch>.

    Does not auto-abort on conflict; leaves it to the user.

    Args:
        path: Repository path.
        branch: Branch name (default: main).

    Raises:
        GitError: If pull fails. Includes resolution steps for conflicts.
    """
    try:
        _run_git(["pull", "--rebase", "origin", branch], cwd=path)
    except GitError as e:
        err_msg = str(e)
        if is_rebasing(path):
            conflicted = get_conflicted_files(path)
            detail = ""
            if conflicted:
                detail = "\n  Conflicted files:\n" + "\n".join(
                    f"    - {f}" for f in conflicted
                )
            raise GitError(
                f"Conflict occurred during pull --rebase.{detail}\n\n"
                "  Resolve manually with these commands:\n\n"
                "  1. Resolve conflicts and continue:\n"
                "     cd ~/.ai-adapter && git add <file> && git rebase --continue\n\n"
                "  2. Abort the rebase:\n"
                "     cd ~/.ai-adapter && git rebase --abort\n\n"
                "  3. Skip the current commit:\n"
                "     cd ~/.ai-adapter && git rebase --skip\n\n"
                "  ai-adapter sync --continue   # Continue rebase\n"
                "  ai-adapter sync --abort      # Abort rebase\n"
                "  ai-adapter sync --skip       # Skip commit"
            )
        raise GitError(f"pull --rebase failed:\n{err_msg}")


def push(path: Path, branch: str = "main") -> None:
    """Run git push origin <branch>.

    Args:
        path: Repository path.
        branch: Branch name (default: main).
    """
    _run_git(["push", "origin", branch], cwd=path)


def get_remotes(path: Path) -> list[str]:
    """Get the list of remote repositories."""
    result = _run_git(["remote"], cwd=path)
    return [r.strip() for r in result.stdout.strip().split("\n") if r.strip()]


def get_current_branch(path: Path) -> str:
    """Get the current branch name."""
    result = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=path)
    return result.stdout.strip()


def remote_branch_exists(path: Path, branch: str = "main") -> bool:
    """Check if a remote branch exists.

    Uses git ls-remote --heads origin <branch>.
    """
    try:
        result = _run_git(
            ["ls-remote", "--heads", "origin", branch], cwd=path
        )
        return bool(result.stdout.strip())
    except GitError:
        return False


def test_remote_connectivity(path: Path) -> bool:
    """Check connectivity to the remote repository.

    Uses git ls-remote --heads origin.
    """
    try:
        _run_git(["ls-remote", "--heads", "origin"], cwd=path)
        return True
    except GitError:
        return False


def clone(url: str, dest: Path) -> None:
    """Run git clone."""
    _run_git(["clone", url, str(dest.name)], cwd=dest.parent)


def add_remote(path: Path, name: str, url: str) -> None:
    """Run git remote add."""
    _run_git(["remote", "add", name, url], cwd=path)


def set_remote_url(path: Path, name: str, url: str) -> None:
    """Run git remote set-url."""
    _run_git(["remote", "set-url", name, url], cwd=path)
