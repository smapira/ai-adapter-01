"""sync command implementation.

Syncs ~/.ai-adapter/ with a GitHub remote as a Git repository.
"""

from __future__ import annotations

import logging
from pathlib import Path

import click

from ai_adapter import config as _config
from ai_adapter.git import (
    GitError,
    _run_git,
    add_all,
    add_remote,
    commit,
    get_conflicted_files,
    get_current_branch,
    has_remote,
    init_repo,
    is_rebasing,
    is_repo,
    pull_rebase,
    push,
    remote_branch_exists,
    test_remote_connectivity,
)

logger = logging.getLogger(__name__)


def _check_rebase_interruption(adapter_dir: Path) -> None:
    """Check and report if a rebase was left unfinished."""
    if not is_rebasing(adapter_dir):
        return
    conflicted = get_conflicted_files(adapter_dir)
    click.echo("⚠ A rebase was left unfinished from the previous sync.")
    if conflicted:
        click.echo("  Conflicted files:")
        for f in conflicted:
            click.echo(f"    - {f}")
    click.echo("  Resolution: ai-adapter sync --continue / --abort / --skip")
    raise click.ClickException("Resolve the rebase first.")


def _ensure_git_repo(adapter_dir: Path) -> None:
    """Initialize git repo if not already one."""
    click.echo("Step 1: Checking Git repository status...")
    if is_repo(adapter_dir):
        return
    click.echo("  ~/.ai-adapter/ is not a Git repository. Initializing...")
    init_repo(adapter_dir)
    click.echo("  git init completed.")


def _ensure_remote(adapter_dir: Path) -> bool:
    """Configure remote if not already set. Returns False if user skips."""
    if has_remote(adapter_dir):
        return True
    click.echo()
    click.echo("  No remote repository configured.")
    config = _config.load_config()
    saved_remote = config.remote if config else None

    if saved_remote:
        click.echo(f"  Saved remote URL found: {saved_remote}")
        add_remote(adapter_dir, "origin", saved_remote)
        click.echo("  Remote set.")
        return True

    remote = click.prompt(
        "  Git remote repository URL (press Enter to skip)",
        default="",
        show_default=False,
    ).strip()
    if not remote:
        click.echo("  No remote configured. Skipping sync.")
        click.echo("  You can set it later with ai-adapter start <URL>.")
        return False
    add_remote(adapter_dir, "origin", remote)
    click.echo(f"  Remote configured: {remote}")
    if config:
        config.remote = remote
        _config.save_config(config)
    return True


def _step_commit(adapter_dir: Path) -> None:
    """git add + commit."""
    click.echo("Step 2: Committing changes...")
    if not add_all(adapter_dir):
        click.echo("  No changes to commit.")
        return
    try:
        commit(adapter_dir)
        click.echo("  Changes committed.")
    except GitError as e:
        logger.error("commit failed: %s", e)
        click.echo("  Commit failed.")
        click.echo("  Git user configuration may not be set.")
        click.echo("  Run the following and try again:")
        click.echo("    git config --global user.email 'you@example.com'")
        click.echo("    git config --global user.name 'Your Name'")
        click.echo("  Or set only for the ~/.ai-adapter repository:")
        click.echo("    cd ~/.ai-adapter")
        click.echo("    git config user.email 'you@example.com'")
        click.echo("    git config user.name 'Your Name'")
        raise


def _step_pull(adapter_dir: Path, branch: str) -> None:
    """git pull --rebase."""
    click.echo("Step 3: Pulling remote changes...")
    if not test_remote_connectivity(adapter_dir):
        click.echo("  ⚠ Cannot connect to the remote repository.")
        click.echo("  Possible causes:")
        click.echo("    - SSH key not configured (needs ssh-keygen + GitHub registration)")
        click.echo("    - Remote URL is incorrect (check with git remote -v)")
        click.echo("    - GitHub access token has expired")
        click.echo("  Check if git fetch works: cd ~/.ai-adapter && git fetch")
        raise click.ClickException("Cannot connect to remote.")

    if not remote_branch_exists(adapter_dir, branch):
        click.echo(f"  Remote branch '{branch}' does not exist. An initial push is required.")
        click.echo("  Will push in Step 4.")
        return

    try:
        pull_rebase(adapter_dir, branch)
        click.echo("  pull --rebase completed.")
    except GitError as e:
        logger.error("pull --rebase failed: %s", e)
        if "would be overwritten by rebase" in str(e).lower() or "conflict" in str(e).lower():
            click.echo("  Conflict occurred. Resolve it manually.")
            click.echo("    cd ~/.ai-adapter && git status")
            click.echo("    git rebase --abort  # to abort")
        else:
            click.echo("  Branch name may not match.")
            click.echo(f"  Current branch: {branch}")
            click.echo("  Check status: cd ~/.ai-adapter && git branch -a")
        raise


def _step_push(adapter_dir: Path, branch: str) -> None:
    """git push."""
    click.echo("Step 4: Pushing to remote...")
    try:
        push(adapter_dir, branch)
        click.echo("  Push completed.")
    except GitError as e:
        logger.error("push failed: %s", e)
        if "Repository not found" in str(e) or "Could not read from remote" in str(e):
            click.echo("  Cannot access remote repository.")
            click.echo("    Check URL: cd ~/.ai-adapter && git remote -v")
            click.echo("    Fix: git remote set-url origin <correct-url>")
        elif "408" in str(e) or "Timeout" in str(e):
            click.echo("  Timeout. Check your network connection.")
        else:
            click.echo("  Push failed.")
            click.echo(f"    Branch: {branch}")
            click.echo(f"    Run manually: cd ~/.ai-adapter && git push origin {branch}")
        raise


def sync_command(adapter_dir: Path | None = None) -> None:
    """Sync ~/.ai-adapter/ with a GitHub remote."""
    if adapter_dir is None:
        adapter_dir = _config.AI_ADAPTER_DIR

    if not adapter_dir.exists():
        click.echo(f"'{adapter_dir}' not found. Run ai-adapter init first.")
        raise click.ClickException("ai-adapter is not initialized.")

    _check_rebase_interruption(adapter_dir)
    _ensure_git_repo(adapter_dir)
    if not _ensure_remote(adapter_dir):
        return

    try:
        _step_commit(adapter_dir)
    except GitError:
        return

    branch = get_current_branch(adapter_dir)
    try:
        _step_pull(adapter_dir, branch)
    except GitError:
        return

    try:
        _step_push(adapter_dir, branch)
    except GitError:
        pass

    click.echo("Sync completed. (Some steps may have been skipped.)")


def handle_rebase_operation(
    adapter_dir: Path,
    do_continue: bool,
    do_abort: bool,
    do_skip: bool,
) -> None:
    """Handle rebase operations."""
    if not is_rebasing(adapter_dir):
        click.echo("Not currently in a rebase state.")
        return

    if do_abort:
        click.echo("Aborting rebase...")
        _run_git(["rebase", "--abort"], cwd=adapter_dir)
        click.echo("Rebase aborted. Restored to original state.")
    elif do_skip:
        click.echo("Skipping commit and continuing rebase...")
        _run_git(["rebase", "--skip"], cwd=adapter_dir)
        if is_rebasing(adapter_dir):
            click.echo("There are still commits in the rebase. Check with git status.")
        else:
            click.echo("Push with ai-adapter sync.")
    elif do_continue:
        click.echo("continuing rebase...")
        try:
            _run_git(["rebase", "--continue"], cwd=adapter_dir)
            if is_rebasing(adapter_dir):
                click.echo("There are still commits in the rebase.")
            else:
                click.echo("Push with ai-adapter sync.")
        except GitError as e:
            if "Author identity unknown" in str(e):
                click.echo("Git user configuration not set.")
                click.echo("  git config --global user.email 'you@example.com'")
                click.echo("  git config --global user.name 'Your Name'")
            else:
                click.echo(f"Failed to continue rebase: {e}")
