"""skill サブコマンドの実装。

~/.ai-adapter/skills/ 配下のスキルディレクトリを管理する。
SKILL.md の YAML frontmatter からメタデータをパースする。
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import click
import yaml

from ai_adapter.config import (
    get_github_skills_dir,
    get_skills_dir,
    load_config,
    save_config,
)
from ai_adapter.models import Skill


def _parse_skill_metadata(skill_dir: Path) -> dict:
    """SKILL.md から frontmatter をパースしてメタデータを返す。"""
    skill_file = skill_dir / "SKILL.md"
    if not skill_file.exists():
        raise click.ClickException(f"SKILL.md が見つかりません: {skill_file}")

    content = skill_file.read_text(encoding="utf-8")
    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not match:
        raise click.ClickException("SKILL.md に YAML frontmatter が見つかりません")

    return yaml.safe_load(match.group(1)) or {}


@click.group(name="skill")
def skill_group() -> None:
    """スキルを管理する。"""


@skill_group.command(name="list")
@click.option("--tag", help="タグでフィルタリング")
def skill_list(tag: str | None) -> None:
    """登録済みスキル一覧を表示する。"""
    config = load_config()
    if config is None:
        click.echo("設定ファイルが見つかりません。ai-adapter init を実行してください。")
        return

    skills = config.skills
    if tag:
        skills = [s for s in skills if tag in s.tags]

    if not skills:
        click.echo("登録済みのスキルはありません。")
        return

    click.echo("スキル一覧:")
    click.echo("-" * 60)
    for skill in skills:
        agent_info = f" [agent: {skill.agent}]" if skill.agent else ""
        tags_str = f" ({', '.join(skill.tags)})" if skill.tags else ""
        desc = f" - {skill.description}" if skill.description else ""
        click.echo(f"  {skill.name}{tags_str}{agent_info}{desc}")


@skill_group.command(name="add")
@click.argument("path", type=click.Path(exists=True, file_okay=False, readable=True))
def skill_add(path: str) -> None:
    """スキルディレクトリを ~/.ai-adapter/skills/ に追加する。

    PATH: SKILL.md を含むスキルディレクトリのパス。
    """
    src = Path(path).resolve()
    metadata = _parse_skill_metadata(src)
    name = metadata.get("name") or src.name

    skills_dir = get_skills_dir()
    skills_dir.mkdir(parents=True, exist_ok=True)
    dest = skills_dir / name

    if dest.exists():
        click.confirm(f"スキル '{name}' は既に存在します。上書きしますか？", abort=True)
        shutil.rmtree(dest)

    shutil.copytree(src, dest)
    click.echo(f"スキル '{name}' を追加しました: {dest}")

    config = load_config()
    if config is None:
        click.echo("設定ファイルが見つかりません。ai-adapter init を実行してください。")
        return

    # 重複チェック
    for existing in config.skills:
        if existing.name == name:
            existing.description = metadata.get("description", "")
            existing.tags = metadata.get("tags", [])
            existing.path = f"skills/{name}"
            save_config(config)
            return

    config.skills.append(Skill(
        name=name,
        description=metadata.get("description", ""),
        path=f"skills/{name}",
        tags=metadata.get("tags", []),
    ))
    save_config(config)


@skill_group.command(name="get")
@click.argument("name")
@click.option("--force", is_flag=True, help="既存のスキルを上書きする")
@click.option(
    "--project-dir", "-d",
    type=click.Path(exists=True, file_okay=False, readable=True),
    default=None,
    help="展開先プロジェクトディレクトリ（デフォルト: カレントディレクトリ）",
)
def skill_get(name: str, force: bool, project_dir: str | None) -> None:
    """スキルを .claude/skills/ にコピーする。

    NAME: 取得するスキル名。
    """
    config = load_config()
    if config is None:
        click.echo("設定ファイルが見つかりません。ai-adapter init を実行してください。")
        return

    # 検索
    skill_entry = None
    for s in config.skills:
        if s.name == name:
            skill_entry = s
            break

    if skill_entry is None:
        click.echo(f"スキル '{name}' は登録されていません。", err=True)
        raise click.ClickException(f"スキル '{name}' が見つかりません。")

    skills_dir = get_skills_dir()
    src = skills_dir / name
    if not src.exists():
        click.echo(f"スキルディレクトリ '{src}' が見つかりません。", err=True)
        raise click.ClickException(f"スキル '{name}' のディレクトリが存在しません。")

    project_path = Path(project_dir).resolve() if project_dir else None
    claude_dir = get_github_skills_dir(project_path)
    claude_dir.mkdir(parents=True, exist_ok=True)
    dest = claude_dir / name

    if dest.exists():
        if force:
            shutil.rmtree(dest)
        else:
            click.confirm(f"'{dest}' は既に存在します。上書きしますか？", abort=True)
            shutil.rmtree(dest)

    shutil.copytree(src, dest)
    click.echo(f"スキル '{name}' を {dest} にコピーしました。")


@skill_group.command(name="remove")
@click.argument("name")
@click.option("--purge", is_flag=True, help="スキルファイルも削除する")
def skill_remove(name: str, purge: bool) -> None:
    """スキルを削除する。

    NAME: 削除するスキル名。
    """
    config = load_config()
    if config is None:
        click.echo("設定ファイルが見つかりません。ai-adapter init を実行してください。")
        return

    found = None
    for s in config.skills:
        if s.name == name:
            found = s
            break

    if found is None:
        click.echo(f"スキル '{name}' は登録されていません。", err=True)
        raise click.ClickException(f"スキル '{name}' が見つかりません。")

    config.skills.remove(found)
    save_config(config)

    if purge:
        skills_dir = get_skills_dir()
        target = skills_dir / name
        if target.exists():
            shutil.rmtree(target)
            click.echo(f"スキルディレクトリ {target} を削除しました。")

    click.echo(f"スキル '{name}' を削除しました。")


@skill_group.command(name="search")
@click.argument("keyword")
def skill_search(keyword: str) -> None:
    """スキルをキーワード検索する。

    KEYWORD: スキル名、説明、タグに部分一致するキーワード。
    """
    config = load_config()
    if config is None:
        click.echo("設定ファイルが見つかりません。ai-adapter init を実行してください。")
        return

    kw = keyword.lower()
    results = []
    for s in config.skills:
        if (kw in s.name.lower()
                or kw in s.description.lower()
                or any(kw in t.lower() for t in s.tags)):
            results.append(s)

    if not results:
        click.echo(f"キーワード '{keyword}' に一致するスキルはありません。")
        return

    click.echo(f"検索結果: '{keyword}'")
    click.echo("-" * 60)
    for s in results:
        tags_str = f" ({', '.join(s.tags)})" if s.tags else ""
        agent_info = f" [agent: {s.agent}]" if s.agent else ""
        desc = f" - {s.description}" if s.description else ""
        click.echo(f"  {s.name}{tags_str}{agent_info}{desc}")


@skill_group.command(name="link-agent")
@click.argument("skill")
@click.argument("agent")
def skill_link_agent(skill: str, agent: str) -> None:
    """スキルとエージェントを紐付ける。

    SKILL: スキル名。
    AGENT: エージェント名。
    """
    config = load_config()
    if config is None:
        click.echo("設定ファイルが見つかりません。ai-adapter init を実行してください。")
        return

    # スキル存在チェック
    skill_entry = None
    for s in config.skills:
        if s.name == skill:
            skill_entry = s
            break

    if skill_entry is None:
        click.echo(f"スキル '{skill}' は登録されていません。", err=True)
        raise click.ClickException(f"スキル '{skill}' が見つかりません。")

    # エージェント存在チェック
    agent_found = any(a.name == agent for a in config.agents)
    if not agent_found:
        click.echo(f"エージェント '{agent}' は登録されていません。", err=True)
        raise click.ClickException(f"エージェント '{agent}' が見つかりません。")

    skill_entry.agent = agent
    save_config(config)
    click.echo(f"スキル '{skill}' をエージェント '{agent}' に紐付けました。")


@skill_group.command(name="get-all")
@click.option("--force", is_flag=True, help="既存のスキルを上書きする")
@click.option(
    "--project-dir", "-d",
    type=click.Path(exists=True, file_okay=False, readable=True),
    default=None,
    help="展開先プロジェクトディレクトリ（デフォルト: カレントディレクトリ）",
)
def skill_get_all(force: bool, project_dir: str | None) -> None:
    """全ての登録済みスキルを .claude/skills/ にコピーする。"""
    config = load_config()
    if config is None or not config.skills:
        click.echo("登録済みのスキルはありません。")
        return

    skills_dir = get_skills_dir()
    project_path = Path(project_dir).resolve() if project_dir else None
    claude_dir = get_github_skills_dir(project_path)
    claude_dir.mkdir(parents=True, exist_ok=True)

    copied = 0
    for skill_entry in config.skills:
        src = skills_dir / skill_entry.name
        if not src.exists():
            click.echo(f"  スキップ: '{skill_entry.name}' のディレクトリが見つかりません。")
            continue
        dest = claude_dir / skill_entry.name
        if dest.exists():
            if force:
                shutil.rmtree(dest)
            else:
                click.confirm(f"'{dest}' は既に存在します。上書きしますか？", abort=True)
                shutil.rmtree(dest)
        shutil.copytree(src, dest)
        copied += 1

    click.echo(f"全てのスキル ({copied}件) を {claude_dir} にコピーしました。")


@skill_group.command(name="remove-all")
@click.option("--force", is_flag=True, help="確認プロンプトを表示せずに削除する")
@click.option("--purge", is_flag=True, help="スキルファイルも削除する")
def skill_remove_all(force: bool, purge: bool) -> None:
    """全てのスキルを削除する。"""
    config = load_config()
    if config is None or not config.skills:
        click.echo("登録済みのスキルはありません。")
        return

    count = len(config.skills)
    if not force:
        click.confirm(f"全てのスキル ({count}件) を削除しますか？", abort=True)

    if purge:
        skills_dir = get_skills_dir()
        for s in config.skills:
            target = skills_dir / s.name
            if target.exists():
                shutil.rmtree(target)

    config.skills.clear()
    save_config(config)
    click.echo(f"全てのスキル ({count}件) を削除しました。")
