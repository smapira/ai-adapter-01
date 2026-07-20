"""bin サブコマンドの実装。

~/.ai-adapter/bin/ 配下のスクリプトファイルを管理する。
env 引数が省略された場合は環境解決ロジックで補完する。
"""

from __future__ import annotations

import shutil
from pathlib import Path

import click

from ai_adapter.config import (
    get_bins_dir,
    get_github_bins_dir,
    load_config,
    save_config,
)
from ai_adapter.models import Bin, Config


def resolve_env(config: Config, env_arg: str | None, agent_name: str | None = None) -> str:
    """env 引数が省略された場合に、エージェント紐付け → デフォルト環境の順で解決する。

    Args:
        config: Config オブジェクト。
        env_arg: 明示指定された env 名（None の場合は解決が必要）。
        agent_name: 現在のエージェント名（省略可）。

    Returns:
        解決された環境名。
    """
    if env_arg:
        return env_arg
    if agent_name:
        for binding in config.agent_bindings:
            if binding.agent == agent_name:
                return binding.env
    return config.default_env


@click.group(name="bin")
def bin_group() -> None:
    """スクリプトファイルを管理する。"""


@bin_group.command(name="list")
@click.option("--env", "-e", default=None, help="環境名（省略時は全環境のスクリプトを表示）")
def bin_list(env: str | None) -> None:
    """スクリプト一覧を表示する。

    --env で環境名を指定するとフィルタリングされます。
    """
    config = load_config()
    if config is None:
        click.echo("設定ファイルが見つかりません。ai-adapter init を実行してください。")
        return

    if not config.bins:
        click.echo("登録済みのスクリプトはありません。")
        return

    if env:
        filtered = [b for b in config.bins if b.env == env]
        if not filtered:
            click.echo(f"環境 '{env}' に登録されたスクリプトはありません。")
            return
        click.echo(f"スクリプト一覧 (環境: {env}):")
        click.echo("-" * 40)
        for b in filtered:
            desc = f" - {b.description}" if b.description else ""
            click.echo(f"  {b.name}{desc}")
    else:
        click.echo("全スクリプト一覧:")
        click.echo("-" * 40)
        for b in config.bins:
            desc = f" - {b.description}" if b.description else ""
            click.echo(f"  [{b.env}] {b.name}{desc}")


@bin_group.command(name="add")
@click.argument("path", type=click.Path(exists=True, readable=True))
@click.option("--env", "-e", default=None, help="環境名（省略時は環境解決ロジックで補完）")
@click.option("--description", "-d", default="", help="スクリプトの説明")
@click.option("--agent", help="エージェント名（環境解決用）")
def bin_add(path: str, env: str | None, description: str, agent: str | None) -> None:
    """スクリプトを ~/.ai-adapter/bin/ に追加する。

    PATH: 追加するスクリプトファイルのパス。

    --env を省略した場合、環境解決ロジックで自動補完されます。
    """
    config = load_config()
    if config is None:
        click.echo("設定ファイルが見つかりません。ai-adapter init を実行してください。")
        return

    resolved_env = resolve_env(config, env, agent)
    src = Path(path).resolve()
    bins_dir = get_bins_dir()
    bins_dir.mkdir(parents=True, exist_ok=True)

    dest = bins_dir / src.name

    if dest.exists():
        click.confirm(f"'{dest.name}' は既に存在します。上書きしますか？", abort=True)

    shutil.copy2(src, dest)
    click.echo(f"スクリプト '{src.name}' を追加しました (環境: {resolved_env}): {dest}")

    # 重複チェック
    for existing in config.bins:
        if existing.name == src.name and existing.env == resolved_env:
            save_config(config)
            return

    config.bins.append(Bin(name=src.name, env=resolved_env, description=description))
    save_config(config)


@bin_group.command(name="get")
@click.argument("name")
@click.option("--env", "-e", default=None, help="環境名（省略時は環境解決ロジックで補完）")
@click.option("--agent", help="エージェント名（環境解決用）")
@click.option(
    "--project-dir", "-d",
    type=click.Path(exists=True, file_okay=False, readable=True),
    default=None,
    help="展開先プロジェクトディレクトリ（デフォルト: カレントディレクトリ）",
)
def bin_get(name: str, env: str | None, agent: str | None, project_dir: str | None) -> None:
    """スクリプトを .github/bin/ にコピーする。

    NAME: 取得するスクリプト名。

    --env を省略した場合、環境解決ロジックで自動補完されます。
    """
    config = load_config()
    if config is None:
        click.echo("設定ファイルが見つかりません。ai-adapter init を実行してください。")
        return

    resolved_env = resolve_env(config, env, agent)

    # config から検索
    bin_entry = None
    for b in config.bins:
        if b.name == name and b.env == resolved_env:
            bin_entry = b
            break

    if bin_entry is None:
        click.echo(f"スクリプト '{name}' (環境: {resolved_env}) は登録されていません。", err=True)
        raise click.ClickException(f"スクリプト '{name}' が見つかりません。")

    bins_dir = get_bins_dir()
    src = bins_dir / name
    if not src.exists():
        click.echo(f"ファイル '{src}' が見つかりません。", err=True)
        raise click.ClickException(f"ファイル '{name}' が ~/.ai-adapter/bin/ に存在しません。")

    project_path = Path(project_dir).resolve() if project_dir else None
    github_dir = get_github_bins_dir(project_path)
    github_dir.mkdir(parents=True, exist_ok=True)

    dest = github_dir / name
    shutil.copy2(src, dest)
    click.echo(f"スクリプト '{name}' を {dest} にコピーしました。")


@bin_group.command(name="get-all")
@click.option("--env", "-e", default=None, help="環境名（省略時は全環境）")
@click.option(
    "--project-dir", "-d",
    type=click.Path(exists=True, file_okay=False, readable=True),
    default=None,
    help="展開先プロジェクトディレクトリ（デフォルト: カレントディレクトリ）",
)
def bin_get_all(env: str | None, project_dir: str | None) -> None:
    """全ての登録済みスクリプトを .github/bin/ にコピーする（--env でフィルタ可能）。"""
    config = load_config()
    if config is None or not config.bins:
        click.echo("登録済みのスクリプトはありません。")
        return

    bins_dir = get_bins_dir()
    project_path = Path(project_dir).resolve() if project_dir else None
    github_dir = get_github_bins_dir(project_path)
    github_dir.mkdir(parents=True, exist_ok=True)

    targets = config.bins
    if env:
        targets = [b for b in targets if b.env == env]

    copied = 0
    for bin_entry in targets:
        src = bins_dir / bin_entry.name
        if not src.exists():
            click.echo(f"  スキップ: '{bin_entry.name}' のファイルが見つかりません。")
            continue
        dest = github_dir / bin_entry.name
        shutil.copy2(src, dest)
        copied += 1

    env_info = f" (環境: {env})" if env else ""
    click.echo(f"全てのスクリプト ({copied}件){env_info} を {github_dir} にコピーしました。")


@bin_group.command(name="remove")
@click.argument("name")
@click.option("--env", "-e", default=None, help="環境名（省略時は環境解決ロジックで補完）")
@click.option("--agent", help="エージェント名（環境解決用）")
def bin_remove(name: str, env: str | None, agent: str | None) -> None:
    """スクリプトの登録を解除する（ファイルは削除しない）。

    NAME: 削除するスクリプト名。

    --env を省略した場合、環境解決ロジックで自動補完されます。
    """
    config = load_config()
    if config is None:
        click.echo("設定ファイルが見つかりません。ai-adapter init を実行してください。")
        return

    resolved_env = resolve_env(config, env, agent)

    # config から削除
    found = None
    for b in config.bins:
        if b.name == name and b.env == resolved_env:
            found = b
            break

    if found is None:
        click.echo(f"スクリプト '{name}' (環境: {resolved_env}) は登録されていません。", err=True)
        raise click.ClickException(f"スクリプト '{name}' が見つかりません。")

    config.bins.remove(found)
    save_config(config)
    click.echo(f"スクリプト '{name}' (環境: {resolved_env}) の登録を解除しました。")


@bin_group.command(name="remove-all")
@click.option("--force", is_flag=True, help="確認プロンプトを表示せずに削除する")
def bin_remove_all(force: bool) -> None:
    """全てのスクリプトの登録を解除する（ファイルは削除しない）。"""
    config = load_config()
    if config is None or not config.bins:
        click.echo("登録済みのスクリプトはありません。")
        return

    count = len(config.bins)
    if not force:
        click.confirm(f"全てのスクリプト ({count}件) の登録を解除しますか？", abort=True)

    config.bins.clear()
    save_config(config)
    click.echo(f"全てのスクリプト ({count}件) の登録を解除しました。")
