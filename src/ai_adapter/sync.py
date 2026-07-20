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
    get_remotes,
    has_remote,
    init_repo,
    is_repo,
    pull_rebase,
    push,
)

logger = logging.getLogger(__name__)


@click.command(name="sync")
def sync_command() -> None:
    """~/.ai-adapter/ を GitHub リモートと同期する。"""
    adapter_dir = _config.AI_ADAPTER_DIR

    if not adapter_dir.exists():
        click.echo(f"'{adapter_dir}' が見つかりません。ai-adapter init を実行してください。")
        raise click.ClickException("ai-adapter が初期化されていません。")

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
        commit(adapter_dir)
        click.echo("  変更をコミットしました。")
    else:
        click.echo("  変更はありません。")

    # Step 3: git pull --rebase
    click.echo("Step 3: リモートの変更を取り込み中...")
    try:
        pull_rebase(adapter_dir)
        click.echo("  pull --rebase 完了。")
    except GitError as e:
        logger.error("pull --rebase 失敗: %s", e)
        click.echo(f"  pull --rebase に失敗しました: {e}", err=True)
        click.echo("  手動で git rebase --abort 後、コンフリクトを解決してください。")
        raise click.ClickException("同期に失敗しました。手動解決が必要です。")

    # Step 4: git push
    click.echo("Step 4: リモートにプッシュ中...")
    try:
        push(adapter_dir)
        click.echo("  push 完了。")
    except GitError as e:
        logger.error("push 失敗: %s", e)
        click.echo(f"  push に失敗しました: {e}", err=True)
        raise click.ClickException("プッシュに失敗しました。")

    click.echo("同期が完了しました。")
