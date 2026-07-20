"""CLI エントリーポイント。

Click グループを定義し、全サブコマンドを統合する。
"""

from __future__ import annotations

import logging

import click

from ai_adapter import __version__
from ai_adapter import config as _config
from ai_adapter.agent import agent_group
from ai_adapter.bin import bin_group
from ai_adapter.env import env_group
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
    click.echo(f"  エージェント紐付け数: {len(config.agent_bindings)}")

    # ディレクトリ存在確認
    agents_dir = adapter_dir / "agents"
    bins_dir = adapter_dir / "bin"
    click.echo(f"  agents/ ディレクトリ: {'✓' if agents_dir.exists() else '✗'}")
    click.echo(f"  bin/ ディレクトリ: {'✓' if bins_dir.exists() else '✗'}")


# サブコマンドグループを登録
main.add_command(agent_group)
main.add_command(env_group)
main.add_command(bin_group)
main.add_command(sync_command)
