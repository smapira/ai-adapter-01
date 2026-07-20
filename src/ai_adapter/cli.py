"""CLI エントリーポイント。

Click グループを定義し、全サブコマンドを統合する。
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

import click

from ai_adapter import __version__
from ai_adapter import config as _config
from ai_adapter.agent import agent_group
from ai_adapter.bin import bin_group
from ai_adapter.env import env_group
from ai_adapter.mcp import mcp_group
from ai_adapter.skill import skill_group
from ai_adapter.sync import sync_command

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
)


@click.group()
@click.version_option(version=__version__, prog_name="ai-adapter")
def main() -> None:
    """AIエージェント・スクリプトの共通管理基盤 CLI ツール"""


@main.command(name="init")
def cmd_init() -> None:
    """~/.ai-adapter/ を初期化する。"""
    created = _config.init()
    if created:
        click.echo(f"初期化しました: {_config.AI_ADAPTER_DIR}")
        click.echo(f"設定ファイル: {_config.get_config_path()}")
    else:
        click.echo(f"既に初期化されています: {_config.AI_ADAPTER_DIR}")


@main.command(name="status")
def cmd_status() -> None:
    """現在の状態を表示する。"""
    adapter_dir = _config.AI_ADAPTER_DIR
    if not adapter_dir.exists():
        click.echo("ai-adapter は初期化されていません。")
        click.echo("ai-adapter init を実行してください。")
        return

    config = _config.load_config()
    if config is None:
        click.echo("設定ファイルが見つかりません。")
        click.echo("ai-adapter init を実行してください。")
        return

    click.echo("ai-adapter 状態:")
    click.echo(f"  データディレクトリ: {adapter_dir}")
    click.echo(f"  設定ファイル: {_config.get_config_path()}")
    click.echo(f"  バージョン: {config.version}")
    click.echo(f"  デフォルト環境: {config.default_env}")
    click.echo(f"  登録エージェント数: {len(config.agents)}")
    click.echo(f"  登録環境数: {len(config.envs)}")
    click.echo(f"  登録スクリプト数: {len(config.bins)}")
    click.echo(f"  登録スキル数: {len(config.skills)}")
    click.echo(f"  MCP サーバー数: {len(config.mcp_servers)}")
    click.echo(f"  エージェント紐付け数: {len(config.agent_bindings)}")

    # ディレクトリ存在確認
    agents_dir = adapter_dir / "agents"
    bins_dir = adapter_dir / "bin"
    skills_dir = adapter_dir / "skills"
    mcp_dir = adapter_dir / "mcp"
    click.echo(f"  agents/ ディレクトリ: {'✓' if agents_dir.exists() else '✗'}")
    click.echo(f"  bin/ ディレクトリ: {'✓' if bins_dir.exists() else '✗'}")
    click.echo(f"  skills/ ディレクトリ: {'✓' if skills_dir.exists() else '✗'}")
    click.echo(f"  mcp/ ディレクトリ: {'✓' if mcp_dir.exists() else '✗'}")


@main.command(name="uninstall")
@click.option("--force", is_flag=True, help="確認プロンプトを表示せずに削除する")
@click.option("--keep-git", is_flag=True, help="Git リポジトリ情報を保持する")
def cmd_uninstall(force: bool, keep_git: bool) -> None:
    """~/.ai-adapter/ を削除して初期状態に戻す。"""
    adapter_dir = _config.AI_ADAPTER_DIR

    if not adapter_dir.exists():
        click.echo("ai-adapter は初期化されていません。")
        click.echo("削除するデータはありません。")
        return

    # Git リポジトリ確認
    git_dir = adapter_dir / ".git"
    is_git_repo = git_dir.exists()

    if is_git_repo and not keep_git:
        click.echo("警告: ~/.ai-adapter/ は Git リポジトリとして管理されています。")
        click.echo("リモートの変更を先にプッシュすることを推奨します。")
        click.echo("  cd ~/.ai-adapter && git status")
        click.echo("  git push")

    # 確認プロンプト
    if not force:
        size_info = _get_dir_size(adapter_dir)
        click.echo(f"削除対象: {adapter_dir} ({size_info})")
        click.confirm("本当に削除しますか？", abort=True)

    # ~/.ai-adapter/ を削除
    if keep_git and is_git_repo:
        _remove_contents_except_git(adapter_dir)
        click.echo(f"データを削除しました (Git リポジトリは保持): {adapter_dir}")
    else:
        shutil.rmtree(adapter_dir)
        click.echo(f"アンインストールしました: {adapter_dir}")

    click.echo("ai-adapter init で再初期化できます。")


def _get_dir_size(path: Path) -> str:
    """ディレクトリのサイズを人間が読める形式で返す。"""
    total = 0
    for f in path.rglob("*"):
        if f.is_file():
            total += f.stat().st_size
    if total < 1024:
        return f"{total} B"
    elif total < 1024 * 1024:
        return f"{total / 1024:.1f} KB"
    else:
        return f"{total / 1024 / 1024:.1f} MB"


def _remove_contents_except_git(path: Path) -> None:
    """Git リポジトリ（.git）を残して中身をすべて削除する。"""
    for item in path.iterdir():
        if item.name == ".git":
            continue
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()


# サブコマンドグループを登録
main.add_command(agent_group)
main.add_command(env_group)
main.add_command(bin_group)
main.add_command(skill_group)
main.add_command(mcp_group)
main.add_command(sync_command)
