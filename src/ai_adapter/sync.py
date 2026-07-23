"""sync command implementation.

Syncs ~/.ai-adapter/ with a GitHub remote as a Git repository.
"""

from __future__ import annotations

import logging

import click

from ai_adapter import config as _config
from ai_adapter.git import (
    GitError,
    add_all,
    add_remote,
    commit,
    get_current_branch,
    get_conflicted_files,
    get_remotes,
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


def sync_command(adapter_dir: Path | None = None) -> None:
    """Sync ~/.ai-adapter/ with a GitHub remote."""
    if adapter_dir is None:
        adapter_dir = _config.AI_ADAPTER_DIR

    if not adapter_dir.exists():
        click.echo(f"'{adapter_dir}' not found. Run ai-adapter init first.")
        raise click.ClickException("ai-adapter is not initialized.")

    # リベース中断検出
    if is_rebasing(adapter_dir):
        conflicted = get_conflicted_files(adapter_dir)
        click.echo("⚠ A rebase was left unfinished from the previous sync.")
        if conflicted:
            click.echo("  Conflicted files:")
            for f in conflicted:
                click.echo(f"    - {f}")
        click.echo("  Resolution: ai-adapter sync --continue / --abort / --skip")
        raise click.ClickException("Resolve the rebase first.")

    # Step 1: Git リポジトリ確認
    click.echo("Step 1: Checking Git repository status...")
    if not is_repo(adapter_dir):
        click.echo("  ~/.ai-adapter/ is not a Git repository. Initializing...")
        init_repo(adapter_dir)
        click.echo("  git init completed.")

    if not has_remote(adapter_dir):
        click.echo()
        click.echo("  No remote repository configured.")

        # config.json に保存された remote を確認
        config = _config.load_config()
        saved_remote = config.remote if config else None

        if saved_remote:
            click.echo(f"  Saved remote URL found: {saved_remote}")
            add_remote(adapter_dir, "origin", saved_remote)
            click.echo("  Remote set.")
        else:
            remote = click.prompt(
                "  Git remote repository URL (press Enter to skip)",
                default="",
                show_default=False,
            ).strip()

            if not remote:
                click.echo("  No remote configured. Skipping sync.")
                click.echo("  You can set it later with ai-adapter start <URL>.")
                return

            add_remote(adapter_dir, "origin", remote)
            click.echo(f"  Remote configured: {remote}")
            if config:
                config.remote = remote
                _config.save_config(config)

    # Step 2: git add + commit
    click.echo("Step 2: Committing changes...")
    has_changes = add_all(adapter_dir)
    if has_changes:
        try:
            commit(adapter_dir)
            click.echo("  Changes committed.")
        except GitError as e:
            logger.error("commit failed: %s", e)
            click.echo(f"  Commit failed.")
            click.echo("  Git user configuration may not be set.")
            click.echo("  Run the following and try again:")
            click.echo("    git config --global user.email 'you@example.com'")
            click.echo("    git config --global user.name 'Your Name'")
            click.echo("  Or set only for the ~/.ai-adapter repository:")
            click.echo("    cd ~/.ai-adapter")
            click.echo("    git config user.email 'you@example.com'")
            click.echo("    git config user.name 'Your Name'")
            return
    else:
        click.echo("  No changes to commit.")

    # Step 3: git pull --rebase
    click.echo("Step 3: Pulling remote changes...")
    branch = get_current_branch(adapter_dir)

    # 接続確認
    if not test_remote_connectivity(adapter_dir):
        click.echo("  ⚠ Cannot connect to the remote repository.")
        click.echo("  Possible causes:")
        click.echo("    - SSH key not configured (needs ssh-keygen + GitHub registration)")
        click.echo("    - Remote URL is incorrect (check with git remote -v)")
        click.echo("    - GitHub access token has expired")
        click.echo("  Check if git fetch works: cd ~/.ai-adapter && git fetch")
        click.echo("  Skipping Step 4 push.")
        return

    # ブランチ存在確認（空リポジトリ対策）
    if not remote_branch_exists(adapter_dir, branch):
        click.echo(f"  Remote branch '{branch}' does not exist. An initial push is required.")
        click.echo("  Will push in Step 4.")
    else:
        try:
            pull_rebase(adapter_dir, branch)
            click.echo("  pull --rebase completed.")
        except GitError as e:
            logger.error("pull --rebase failed: %s", e)
            if "would be overwritten by rebase" in str(e).lower() or "conflict" in str(e).lower():
                click.echo("  Conflict occurred. Resolve it manually.")
                click.echo(f"    cd ~/.ai-adapter && git status")
                click.echo(f"    git rebase --abort  # to abort")
            else:
                click.echo(f"  Branch name may not match.")
                click.echo(f"  Current branch: {branch}")
                click.echo(f"  Check status: cd ~/.ai-adapter && git branch -a")
            return

    # Step 4: git push
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
            click.echo(f"  Push failed.")
            click.echo(f"    Branch: {branch}")
            click.echo(f"    Run manually: cd ~/.ai-adapter && git push origin {branch}")

    click.echo("Sync completed. (Some steps may have been skipped.)")
