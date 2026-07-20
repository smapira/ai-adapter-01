"""agent サブコマンドの実装。

~/.ai-adapter/agents/ 配下のエージェントファイルを管理する。
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import click
import yaml

from ai_adapter.config import (
    get_agents_dir,
    get_github_agents_dir,
    load_config,
    save_config,
)
from ai_adapter.models import Agent


def _parse_frontmatter(path: Path) -> dict:
    """ファイルの YAML frontmatter をパースする。"""
    content = path.read_text(encoding="utf-8")
    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if match:
        data = yaml.safe_load(match.group(1))
        return data if isinstance(data, dict) else {}
    return {}


def _get_agent_name_from_path(path: Path) -> str:
    """ファイルパスからエージェント名を取得する。

    .agent.md ファイルの場合、YAML frontmatter の name を優先する。
    それ以外は全拡張子を除去したファイル名を使用する。
    """
    if path.suffixes == [".agent", ".md"] or str(path).endswith(".agent.md"):
        # .agent.md: frontmatter の name を優先
        frontmatter = _parse_frontmatter(path)
        name_from_fm = frontmatter.get("name", "").strip()
        if name_from_fm:
            return name_from_fm
        # frontmatter がなければ全拡張子除去
        p = path
        while p.suffix:
            p = p.with_suffix("")
        return p.name

    # それ以外: 全拡張子を除去
    p = path
    while p.suffix:
        p = p.with_suffix("")
    return p.name


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

    # .agent.md のフォーマットバリデーション
    if str(src).endswith(".agent.md"):
        frontmatter = _parse_frontmatter(src)
        if not frontmatter:
            raise click.ClickException(
                ".agent.md ファイルには YAML frontmatter が必要です。"
            )
        name_from_fm = frontmatter.get("name", "").strip()
        if not name_from_fm:
            raise click.ClickException(
                ".agent.md ファイルの frontmatter に name プロパティが必要です。"
            )

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
@click.option(
    "--project-dir", "-d",
    type=click.Path(exists=True, file_okay=False, readable=True),
    default=None,
    help="展開先プロジェクトディレクトリ（デフォルト: カレントディレクトリ）",
)
def agent_get(name: str, project_dir: str | None) -> None:
    """エージェントファイルを .github/agents/ にコピーする。

    NAME: 取得するエージェント名（拡張子不要）。
    """
    config = load_config()
    agents_dir = get_agents_dir()

    src = None

    # Step 1: config に登録名があれば、そのエージェントのファイルを探す
    if config:
        for agent_cfg in config.agents:
            if agent_cfg.name == name:
                # 登録名が一致: agents_dir 内の全ファイルから frontmatter name が一致するものを探す
                for f in agents_dir.iterdir():
                    if not f.is_file():
                        continue
                    try:
                        fm = _parse_frontmatter(f)
                        if fm.get("name", "").strip() == name:
                            src = f
                            break
                    except Exception:
                        continue
                if src is None:
                    # frontmatter が見つからなければファイル名で一致確認
                    if (agents_dir / f"{name}.agent.md").exists():
                        src = agents_dir / f"{name}.agent.md"
                    elif (agents_dir / f"{name}.md").exists():
                        src = agents_dir / f"{name}.md"
                    elif (agents_dir / name).exists():
                        src = agents_dir / name
                break

    # Step 2: config にない場合はファイル名ベースで探索（後方互換性）
    if src is None:
        candidates = [
            agents_dir / f"{name}.agent.md",
            agents_dir / f"{name}.md",
            agents_dir / name,
        ]
        for c in candidates:
            if c.exists() and c.is_file():
                src = c
                break

    if src is None:
        click.echo(f"エージェント '{name}' が見つかりません。", err=True)
        raise click.ClickException(f"エージェント '{name}' は登録されていません。")

    project_path = Path(project_dir).resolve() if project_dir else None
    github_dir = get_github_agents_dir(project_path)
    github_dir.mkdir(parents=True, exist_ok=True)

    dest = github_dir / src.name
    shutil.copy2(src, dest)
    click.echo(f"エージェント '{name}' を {dest} にコピーしました。")


@agent_group.command(name="get-all")
@click.option(
    "--project-dir", "-d",
    type=click.Path(exists=True, file_okay=False, readable=True),
    default=None,
    help="展開先プロジェクトディレクトリ（デフォルト: カレントディレクトリ）",
)
def agent_get_all(project_dir: str | None) -> None:
    """全ての登録済みエージェントを .github/agents/ にコピーする。"""
    config = load_config()
    if config is None or not config.agents:
        click.echo("登録済みのエージェントはありません。")
        return

    agents_dir = get_agents_dir()
    project_path = Path(project_dir).resolve() if project_dir else None
    github_dir = get_github_agents_dir(project_path)
    github_dir.mkdir(parents=True, exist_ok=True)

    copied = 0
    for agent_cfg in config.agents:
        name = agent_cfg.name
        src = None
        # ファイル探索
        for f in agents_dir.iterdir():
            if not f.is_file():
                continue
            try:
                fm = _parse_frontmatter(f)
                if fm.get("name", "").strip() == name:
                    src = f
                    break
            except Exception:
                continue
        if src is None:
            candidates = [
                agents_dir / f"{name}.agent.md",
                agents_dir / f"{name}.md",
                agents_dir / name,
            ]
            for c in candidates:
                if c.exists() and c.is_file():
                    src = c
                    break
        if src is None:
            click.echo(f"  スキップ: '{name}' のファイルが見つかりません。")
            continue

        dest = github_dir / src.name
        shutil.copy2(src, dest)
        copied += 1

    click.echo(f"全てのエージェント ({copied}件) を {github_dir} にコピーしました。")


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
            # .agent.md / .md / そのまま のパターンで一致確認
            candidates = [
                f.name == f"{name}.agent.md",
                f.name == f"{name}.md",
                f.name == name,
                _get_agent_name_from_path(f) == name,
            ]
            if any(candidates):
                f.unlink()
                click.echo(f"ファイル {f.name} を削除しました。")
                break

    click.echo(f"エージェント '{name}' を削除しました。")


@agent_group.command(name="remove-all")
@click.option(
    "--keep-file/--no-keep-file",
    default=False,
    help="実体ファイルを削除しない（デフォルト: ファイルも削除）",
)
@click.option("--force", is_flag=True, help="確認プロンプトを表示せずに削除する")
def agent_remove_all(keep_file: bool, force: bool) -> None:
    """全てのエージェントを削除する。"""
    config = load_config()
    if config is None or not config.agents:
        click.echo("登録済みのエージェントはありません。")
        return

    count = len(config.agents)
    if not force:
        click.confirm(f"全てのエージェント ({count}件) を削除しますか？", abort=True)

    agents_dir = get_agents_dir()

    # ファイル削除
    if not keep_file and agents_dir.exists():
        for f in agents_dir.iterdir():
            if f.is_file():
                f.unlink()

    config.agents.clear()
    save_config(config)
    click.echo(f"全てのエージェント ({count}件) を削除しました。")
