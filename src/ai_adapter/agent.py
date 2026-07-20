"""agent サブコマンドの実装。

~/.ai-adapter/agents/ 配下のエージェントファイルを管理する。
"""

from __future__ import annotations

import shutil
from pathlib import Path

import click

from ai_adapter.config import (
    get_agents_dir,
    get_github_agents_dir,
    load_config,
    save_config,
)
from ai_adapter.models import Agent


def _get_agent_name_from_path(path: Path) -> str:
    """ファイルパスからエージェント名（拡張子除く）を取得する。"""
    return path.stem


@click.group(name="agent")
def agent_group() -> None:
    """AIエージェント指示ファイルを管理する。"""


@agent_group.command(name="list")
def agent_list() -> None:
    """登録済みエージェント一覧を表示する。"""
    config = load_config()
    if config is None:
        click.echo("設定ファイルが見つかりません。ai-adapter init を実行してください。")
        return

    if not config.agents:
        click.echo("登録済みのエージェントはありません。")
        return

    click.echo("エージェント一覧:")
    click.echo("-" * 40)
    for agent in config.agents:
        desc = f" - {agent.description}" if agent.description else ""
        click.echo(f"  {agent.name}{desc}")


@agent_group.command(name="add")
@click.argument("path", type=click.Path(exists=True, readable=True))
def agent_add(path: str) -> None:
    """エージェントファイルを ~/.ai-adapter/agents/ に追加する。

    PATH: 追加するエージェントファイルのパス。
    """
    src = Path(path).resolve()
    agents_dir = get_agents_dir()
    agents_dir.mkdir(parents=True, exist_ok=True)

    name = _get_agent_name_from_path(src)
    dest = agents_dir / src.name

    if dest.exists():
        click.confirm(f"'{dest.name}' は既に存在します。上書きしますか？", abort=True)

    shutil.copy2(src, dest)
    click.echo(f"エージェント '{name}' を追加しました: {dest}")

    config = load_config()
    if config is None:
        click.echo("設定ファイルが見つかりません。ai-adapter init を実行してください。")
        return

    # 重複チェック
    for existing in config.agents:
        if existing.name == name:
            # 上書きの場合は description を更新しない（ファイルベースなので）
            save_config(config)
            return

    config.agents.append(Agent(name=name))
    save_config(config)


@agent_group.command(name="get")
@click.argument("name")
def agent_get(name: str) -> None:
    """エージェントファイルを .github/agents/ にコピーする。

    NAME: 取得するエージェント名（拡張子不要）。
    """
    agents_dir = get_agents_dir()
    # .md 拡張子を試す
    src_md = agents_dir / f"{name}.md"
    src_try = agents_dir / name

    if src_md.exists():
        src = src_md
    elif src_try.exists() and src_try.is_file():
        src = src_try
    else:
        click.echo(f"エージェント '{name}' が見つかりません。", err=True)
        raise click.ClickException(f"エージェント '{name}' は登録されていません。")

    github_dir = get_github_agents_dir()
    github_dir.mkdir(parents=True, exist_ok=True)

    dest = github_dir / src.name
    shutil.copy2(src, dest)
    click.echo(f"エージェント '{name}' を {dest} にコピーしました。")


@agent_group.command(name="remove")
@click.argument("name")
@click.option(
    "--keep-file/--no-keep-file",
    default=False,
    help="実体ファイルを削除しない（デフォルト: ファイルも削除）",
)
def agent_remove(name: str, keep_file: bool) -> None:
    """エージェントを削除する。

    NAME: 削除するエージェント名。
    """
    config = load_config()
    if config is None:
        click.echo("設定ファイルが見つかりません。ai-adapter init を実行してください。")
        return

    # config から削除
    found = False
    for agent in list(config.agents):
        if agent.name == name:
            config.agents.remove(agent)
            found = True
            break

    if not found:
        click.echo(f"エージェント '{name}' は登録されていません。", err=True)
        raise click.ClickException(f"エージェント '{name}' が見つかりません。")

    save_config(config)

    # ファイル削除
    if not keep_file:
        agents_dir = get_agents_dir()
        for f in agents_dir.iterdir():
            if f.stem == name or f.name == name:
                f.unlink()
                click.echo(f"ファイル {f.name} を削除しました。")
                break

    click.echo(f"エージェント '{name}' を削除しました。")
