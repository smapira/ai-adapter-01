"""env サブコマンドの実装。

config.yaml で環境名を管理する。
デフォルト環境の設定、エージェントと環境の紐付けを行う。
"""

from __future__ import annotations

import click

from ai_adapter.config import load_config, save_config
from ai_adapter.models import AgentBinding, Env


@click.group(name="env")
def env_group() -> None:
    """環境設定を管理する。"""


@env_group.command(name="list")
def env_list() -> None:
    """環境一覧を表示する（* 付きでデフォルト環境を表示）。"""
    config = load_config()
    if config is None:
        click.echo("設定ファイルが見つかりません。ai-adapter init を実行してください。")
        return

    if not config.envs:
        click.echo("登録済みの環境はありません。")
        return

    click.echo("環境一覧:")
    click.echo("-" * 40)
    for env in config.envs:
        default_mark = " *" if env.name == config.default_env else " "
        desc = f" - {env.description}" if env.description else ""
        click.echo(f"  {default_mark}{env.name}{desc}")


@env_group.command(name="add")
@click.argument("name")
@click.option("--description", "-d", default="", help="環境の説明")
def env_add(name: str, description: str) -> None:
    """新しい環境を追加する。

    NAME: 追加する環境名。
    """
    config = load_config()
    if config is None:
        click.echo("設定ファイルが見つかりません。ai-adapter init を実行してください。")
        return

    # 重複チェック
    for env in config.envs:
        if env.name == name:
            click.echo(f"環境 '{name}' は既に存在します。", err=True)
            raise click.ClickException(f"環境 '{name}' は既に登録されています。")

    config.envs.append(Env(name=name, description=description))
    save_config(config)
    click.echo(f"環境 '{name}' を追加しました。")


@env_group.command(name="remove")
@click.argument("name")
@click.option("--force", is_flag=True, help="bin で参照されていても強制的に削除する")
def env_remove(name: str, force: bool) -> None:
    """環境を削除する。

    NAME: 削除する環境名。デフォルト環境は削除不可。
    """
    config = load_config()
    if config is None:
        click.echo("設定ファイルが見つかりません。ai-adapter init を実行してください。")
        return

    # デフォルト環境は削除不可
    if name == config.default_env:
        click.echo(f"デフォルト環境 '{name}' は削除できません。", err=True)
        raise click.ClickException("デフォルト環境は削除できません。set-default で変更してください。")

    # 存在チェック
    target = None
    for env in config.envs:
        if env.name == name:
            target = env
            break

    if target is None:
        click.echo(f"環境 '{name}' は登録されていません。", err=True)
        raise click.ClickException(f"環境 '{name}' が見つかりません。")

    # bin での参照チェック
    ref_bins = [b for b in config.bins if b.env == name]
    if ref_bins and not force:
        click.echo(
            f"環境 '{name}' は {len(ref_bins)} 個の bin で参照されています。"
            f" --force で強制的に削除できます。",
            err=True,
        )
        raise click.ClickException("bin で参照中の環境は削除できません。--force を使用してください。")

    config.envs.remove(target)

    # エージェント紐付けも削除
    config.agent_bindings = [
        b for b in config.agent_bindings if b.env != name
    ]

    save_config(config)
    click.echo(f"環境 '{name}' を削除しました。")


@env_group.command(name="default")
def env_default() -> None:
    """現在のデフォルト環境名を表示する。"""
    config = load_config()
    if config is None:
        click.echo("設定ファイルが見つかりません。ai-adapter init を実行してください。")
        return

    click.echo(f"デフォルト環境: {config.default_env}")


@env_group.command(name="set-default")
@click.argument("name")
def env_set_default(name: str) -> None:
    """デフォルト環境を変更する。

    NAME: デフォルトに設定する環境名。
    """
    config = load_config()
    if config is None:
        click.echo("設定ファイルが見つかりません。ai-adapter init を実行してください。")
        return

    # 存在チェック
    found = any(env.name == name for env in config.envs)
    if not found:
        click.echo(f"環境 '{name}' は登録されていません。", err=True)
        raise click.ClickException(f"環境 '{name}' が見つかりません。")

    config.default_env = name
    save_config(config)
    click.echo(f"デフォルト環境を '{name}' に変更しました。")


@env_group.command(name="link-agent")
@click.argument("agent")
@click.argument("env")
def env_link_agent(agent: str, env: str) -> None:
    """エージェント名と環境を紐付ける。

    AGENT: エージェント名。
    ENV: 紐付ける環境名。
    """
    config = load_config()
    if config is None:
        click.echo("設定ファイルが見つかりません。ai-adapter init を実行してください。")
        return

    # 環境存在チェック
    env_found = any(e.name == env for e in config.envs)
    if not env_found:
        click.echo(f"環境 '{env}' は登録されていません。", err=True)
        raise click.ClickException(f"環境 '{env}' が見つかりません。")

    # 既存の同名エージェント紐付けがあれば上書き
    for binding in config.agent_bindings:
        if binding.agent == agent:
            old_env = binding.env
            binding.env = env
            save_config(config)
            click.echo(
                f"エージェント '{agent}' の紐付けを '{old_env}' から '{env}' に変更しました。"
            )
            return

    config.agent_bindings.append(AgentBinding(agent=agent, env=env))
    save_config(config)
    click.echo(f"エージェント '{agent}' を環境 '{env}' に紐付けました。")


@env_group.command(name="unlink-agent")
@click.argument("agent")
def env_unlink_agent(agent: str) -> None:
    """エージェントと環境の紐付けを解除する。

    AGENT: 紐付けを解除するエージェント名。
    """
    config = load_config()
    if config is None:
        click.echo("設定ファイルが見つかりません。ai-adapter init を実行してください。")
        return

    found = None
    for binding in config.agent_bindings:
        if binding.agent == agent:
            found = binding
            break

    if found is None:
        click.echo(f"エージェント '{agent}' の紐付けはありません。", err=True)
        raise click.ClickException(f"エージェント '{agent}' の紐付けが見つかりません。")

    config.agent_bindings.remove(found)
    save_config(config)
    click.echo(f"エージェント '{agent}' の紐付けを解除しました。")
