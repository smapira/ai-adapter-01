"""sync コマンドの実装。

~/.ai-adapter/ を Git リポジトリとして GitHub リモートと同期する。
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
    """~/.ai-adapter/ を GitHub リモートと同期する。"""
    if adapter_dir is None:
        adapter_dir = _config.AI_ADAPTER_DIR

    if not adapter_dir.exists():
        click.echo(f"'{adapter_dir}' が見つかりません。ai-adapter init を実行してください。")
        raise click.ClickException("ai-adapter が初期化されていません。")

    # リベース中断検出
    if is_rebasing(adapter_dir):
        conflicted = get_conflicted_files(adapter_dir)
        click.echo("⚠ 前回の sync でリベースが中断されたままです。")
        if conflicted:
            click.echo("  コンフリクトファイル:")
            for f in conflicted:
                click.echo(f"    - {f}")
        click.echo("  解決方法: ai-adapter sync --continue / --abort / --skip")
        raise click.ClickException("リベースを先に解決してください。")

    # Step 1: Git リポジトリ確認
    click.echo("Step 1: Git リポジトリを確認中...")
    if not is_repo(adapter_dir):
        click.echo("  ~/.ai-adapter/ が Git リポジトリではありません。初期化します...")
        init_repo(adapter_dir)
        click.echo("  git init 完了。")

    if not has_remote(adapter_dir):
        click.echo()
        click.echo("  リモートリポジトリが設定されていません。")

        # config.json に保存された remote を確認
        config = _config.load_config()
        saved_remote = config.remote if config else None

        if saved_remote:
            click.echo(f"  保存されたリモートURLが見つかりました: {saved_remote}")
            add_remote(adapter_dir, "origin", saved_remote)
            click.echo("  リモートを設定しました。")
        else:
            remote = click.prompt(
                "  Git リモートリポジトリURL（スキップするには Enter）",
                default="",
                show_default=False,
            ).strip()

            if not remote:
                click.echo("  リモートが設定されていないため、同期をスキップします。")
                click.echo("  ai-adapter start <URL> で後から設定できます。")
                return

            add_remote(adapter_dir, "origin", remote)
            click.echo(f"  リモートを設定しました: {remote}")
            if config:
                config.remote = remote
                _config.save_config(config)

    # Step 2: git add + commit
    click.echo("Step 2: 変更をコミット中...")
    has_changes = add_all(adapter_dir)
    if has_changes:
        try:
            commit(adapter_dir)
            click.echo("  変更をコミットしました。")
        except GitError as e:
            logger.error("commit 失敗: %s", e)
            click.echo(f"  コミットに失敗しました。")
            click.echo("  Git のユーザー設定がされていない可能性があります。")
            click.echo("  以下を実行してからもう一度試してください:")
            click.echo("    git config --global user.email 'you@example.com'")
            click.echo("    git config --global user.name 'Your Name'")
            click.echo("  または ~/.ai-adapter リポジトリのみに設定:")
            click.echo("    cd ~/.ai-adapter")
            click.echo("    git config user.email 'you@example.com'")
            click.echo("    git config user.name 'Your Name'")
            return
    else:
        click.echo("  変更はありません。")

    # Step 3: git pull --rebase
    click.echo("Step 3: リモートの変更を取り込み中...")
    branch = get_current_branch(adapter_dir)

    # 接続確認
    if not test_remote_connectivity(adapter_dir):
        click.echo("  ⚠ リモートリポジトリに接続できません。")
        click.echo("  考えられる原因:")
        click.echo("    - SSH キーが設定されていない（ssh-keygen + GitHub 登録が必要）")
        click.echo("    - リモートURLが間違っている（git remote -v で確認）")
        click.echo("    - GitHub のアクセストークンが切れている")
        click.echo("  git fetch が通るか確認: cd ~/.ai-adapter && git fetch")
        click.echo("  Step 4 の push はスキップします。")
        return

    # ブランチ存在確認（空リポジトリ対策）
    if not remote_branch_exists(adapter_dir, branch):
        click.echo(f"  リモートにブランチ '{branch}' が存在しません。初回プッシュが必要です。")
        click.echo("  Step 4 でプッシュします。")
    else:
        try:
            pull_rebase(adapter_dir, branch)
            click.echo("  pull --rebase 完了。")
        except GitError as e:
            logger.error("pull --rebase 失敗: %s", e)
            if "would be overwritten by rebase" in str(e).lower() or "conflict" in str(e).lower():
                click.echo("  コンフリクトが発生しました。手動で解決してください。")
                click.echo(f"    cd ~/.ai-adapter && git status")
                click.echo(f"    git rebase --abort  # 中断する場合")
            else:
                click.echo(f"  ブランチ名が不一致の可能性があります。")
                click.echo(f"  現在のブランチ: {branch}")
                click.echo(f"  cd ~/.ai-adapter && git branch -a で状態を確認してください。")
            return

    # Step 4: git push
    click.echo("Step 4: リモートにプッシュ中...")
    try:
        push(adapter_dir, branch)
        click.echo("  push 完了。")
    except GitError as e:
        logger.error("push 失敗: %s", e)
        if "Repository not found" in str(e) or "Could not read from remote" in str(e):
            click.echo("  リモートリポジトリにアクセスできません。")
            click.echo("    cd ~/.ai-adapter && git remote -v でURLを確認")
            click.echo("    git remote set-url origin <正しいURL> で修正")
        elif "408" in str(e) or "Timeout" in str(e):
            click.echo("  タイムアウトしました。ネットワーク接続を確認してください。")
        else:
            click.echo(f"  push に失敗しました。")
            click.echo(f"    ブランチ: {branch}")
            click.echo(f"    cd ~/.ai-adapter && git push origin {branch} を手動で実行してください。")

    click.echo("同期が完了しました。（一部の処理はスキップされた可能性があります）")
