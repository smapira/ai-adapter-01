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
from ai_adapter import git as _git
from ai_adapter.agent import agent_group
from ai_adapter.bin import bin_group
from ai_adapter.env import env_group
from ai_adapter.mcp import mcp_group
from ai_adapter.opencode import opencode_group
from ai_adapter.skill import skill_group
from ai_adapter.git import GitError, is_rebasing, get_conflicted_files
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
@click.option("--remote", "-r", help="Git リモートリポジトリのURL")
def cmd_init(remote: str | None) -> None:
    """~/.ai-adapter/ を初期化する。

    リモートURLが未指定の場合、対話的に入力を促します。
    """
    created = _config.init()
    if created:
        click.echo(f"初期化しました: {_config.AI_ADAPTER_DIR}")
        click.echo(f"設定ファイル: {_config.get_config_path()}")
    else:
        click.echo(f"既に初期化されています: {_config.AI_ADAPTER_DIR}")

    # リモート設定
    adapter_dir = _config.AI_ADAPTER_DIR

    if not _git.is_repo(adapter_dir):
        _git.init_repo(adapter_dir)

    if not _git.has_remote(adapter_dir):
        if remote is None:
            click.echo()
            click.echo("--- GitHub 同期の設定 ---")
            click.echo("設定を複数PCで共有するには、GitHub リポジトリのURLを入力してください。")
            click.echo("（スキップする場合は何も入力せず Enter を押してください）")
            remote_input = click.prompt(
                "Git リモートリポジトリURL",
                default="",
                show_default=False,
            ).strip()
            remote = remote_input if remote_input else None

        if remote:
            _git.add_remote(adapter_dir, "origin", remote)
            config = _config.load_config()
            if config:
                config.remote = remote
                _config.save_config(config)
            click.echo(f"リモートを設定しました: {remote}")
            click.echo("ai-adapter sync で設定を同期できます。")
        else:
            click.echo("リモートは設定されませんでした。")
            click.echo("後から ai-adapter start <URL> で設定することもできます。")
    else:
        remotes = _git.get_remotes(adapter_dir)
        click.echo(f"リモートは既に設定されています: {', '.join(remotes)}")


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
    if config.remote:
        click.echo(f"  リモート: {config.remote}")

    # ディレクトリ存在確認
    agents_dir = adapter_dir / "agents"
    bins_dir = adapter_dir / "bin"
    skills_dir = adapter_dir / "skills"
    mcp_dir = adapter_dir / "mcp"
    click.echo(f"  agents/ ディレクトリ: {'✓' if agents_dir.exists() else '✗'}")
    click.echo(f"  bin/ ディレクトリ: {'✓' if bins_dir.exists() else '✗'}")
    click.echo(f"  skills/ ディレクトリ: {'✓' if skills_dir.exists() else '✗'}")
    click.echo(f"  mcp/ ディレクトリ: {'✓' if mcp_dir.exists() else '✗'}")

    # リベース状態
    rebasing = is_rebasing(adapter_dir)
    click.echo(f"  リベース状態: {'⚠ 中断中' if rebasing else '✓'}")
    if rebasing:
        conflicted = get_conflicted_files(adapter_dir)
        if conflicted:
            click.echo(f"  コンフリクトファイル: {', '.join(conflicted)}")


@main.command(name="start")
@click.argument("url")
def cmd_start(url: str) -> None:
    """GitHub リモートと連携して ~/.ai-adapter/ を初期化する。

    URL: Git リモートリポジトリのURL（例: git@github.com:user/my-agent-config.git）
    """
    adapter_dir = _config.AI_ADAPTER_DIR

    if adapter_dir.exists():
        click.echo(f"'{adapter_dir}' は既に存在します。")
        click.confirm("既存の設定を上書きしますか？（設定はマージされます）", abort=True)

    # Step 1: git clone を試みる
    click.echo(f"リモートリポジトリからクローン中: {url}")
    try:
        _git.clone(url, adapter_dir)
        click.echo("クローンしました。")
    except _git.GitError:
        click.echo("クローンに失敗しました。新規リポジトリとして初期化します。")
        adapter_dir.mkdir(parents=True, exist_ok=True)
        _git.init_repo(adapter_dir)
        _git.add_remote(adapter_dir, "origin", url)
        click.echo(f"リモートを設定しました: {url}")

    # Step 2: ディレクトリ構造を初期化
    dirs = [
        adapter_dir / "agents",
        adapter_dir / "bin",
        adapter_dir / "skills",
        adapter_dir / "mcp",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)

    # Step 3: config.json がなければデフォルト生成
    from ai_adapter.models import Config, Env
    config_path = _config.get_config_path()
    if not config_path.exists():
        config = Config(
            version=1,
            default_env="default",
            envs=[Env(name="default", description="デフォルト環境")],
            agent_bindings=[],
            remote=url,
        )
        _config.save_config(config)
        click.echo("デフォルト設定ファイルを生成しました。")
    else:
        # remote フィールドを更新
        cfg = _config.load_config()
        if cfg:
            cfg.remote = url
            _config.save_config(cfg)

    click.echo(f"セットアップ完了: {adapter_dir}")
    click.echo(f"リモート: {url}")
    click.echo("ai-adapter sync で設定を同期できます。")


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
main.add_command(opencode_group)


@main.command(name="export")
@click.option("--shell", default=None,
              type=click.Choice(["zshrc", "bash_profile", "bashrc"], case_sensitive=False),
              help="シェル設定ファイル（省略時は対話的に選択）")
def cmd_export(shell: str | None) -> None:
    """~/.github/bin を PATH に追加するシェル設定を出力・適用する。"""
    github_bin = Path.cwd() / ".github" / "bin"

    if not github_bin.exists():
        click.echo(f"'.github/bin' ディレクトリが見つかりません: {github_bin}")
        click.echo("ai-adapter bin get <name> または ai-adapter bin get-all で先にスクリプトを展開してください。")
        return

    export_line = f'export PATH="$PATH:{github_bin.resolve()}"'

    # シェル設定ファイルの候補
    home = Path.home()
    shell_configs = {
        "zshrc": home / ".zshrc",
        "bash_profile": home / ".bash_profile",
        "bashrc": home / ".bashrc",
    }

    chosen = None
    if shell:
        chosen = shell.lower()
    else:
        click.echo()
        click.echo(f"以下の行をシェル設定ファイルに追加すると、スクリプトを短い名前で実行できます:")
        click.echo(f"  {export_line}")
        click.echo()
        click.echo("シェル設定ファイルを選択してください:")
        for i, (key, path) in enumerate(shell_configs.items(), 1):
            exists_mark = " ✓" if path.exists() else ""
            click.echo(f"  {i}) {key} ({path}{exists_mark})")
        click.echo("  4) 表示のみ（自動追加しない）")
        click.echo()
        choice = click.prompt("番号を選択", type=int, default=4)

        if 1 <= choice <= 3:
            chosen = list(shell_configs.keys())[choice - 1]

    if chosen and chosen in shell_configs:
        config_path = shell_configs[chosen]
        config_path.parent.mkdir(parents=True, exist_ok=True)

        if config_path.exists():
            content = config_path.read_text()
            if export_line in content:
                click.echo(f"既に設定されています: {config_path}")
                click.echo(f"  {export_line}")
                return

        with open(config_path, "a") as f:
            f.write(f"\n# ai-adapter PATH\n{export_line}\n")

        click.echo(f"PATH 設定を追加しました: {config_path}")
        click.echo(f"  {export_line}")
        click.echo("設定を反映するには、シェルを再起動するか以下を実行してください:")
        click.echo(f"  source {config_path}")
    else:
        click.echo("以下の行を ~/.zshrc などに追加してください:")
        click.echo(f"  {export_line}")


@main.command(name="sync")
@click.option("--continue", "do_continue", is_flag=True, help="中断されたリベースを続行")
@click.option("--abort", "do_abort", is_flag=True, help="リベースを中断")
@click.option("--skip", "do_skip", is_flag=True, help="コミットをスキップ")
def cmd_sync(do_continue: bool, do_abort: bool, do_skip: bool) -> None:
    """~/.ai-adapter/ を GitHub リモートと同期する。"""
    adapter_dir = _config.AI_ADAPTER_DIR

    if not adapter_dir.exists():
        click.echo(f"'{adapter_dir}' が見つかりません。ai-adapter init を実行してください。")
        raise click.ClickException("ai-adapter が初期化されていません。")

    # リベース操作モード
    if do_continue or do_abort or do_skip:
        _handle_rebase_operation(adapter_dir, do_continue, do_abort, do_skip)
        return

    # 通常の sync
    from ai_adapter.sync import sync_command
    try:
        sync_command(adapter_dir)
    except GitError as e:
        click.echo(f"エラー: {e}", err=True)
        raise click.ClickException(str(e))


def _handle_rebase_operation(
    adapter_dir: Path, do_continue: bool, do_abort: bool, do_skip: bool
) -> None:
    """リベース操作を処理する。"""
    if not is_rebasing(adapter_dir):
        click.echo("リベース中の状態ではありません。")
        return

    if do_abort:
        click.echo("リベースを中断中...")
        _git._run_git(["rebase", "--abort"], cwd=adapter_dir)
        click.echo("リベースを中断しました。元の状態に戻りました。")
    elif do_skip:
        click.echo("コミットをスキップしてリベースを続行中...")
        _git._run_git(["rebase", "--skip"], cwd=adapter_dir)
        if is_rebasing(adapter_dir):
            click.echo("まだリベース中のコミットがあります。git status で確認してください。")
        else:
            click.echo("ai-adapter sync でプッシュしてください。")
    elif do_continue:
        click.echo("リベースを続行中...")
        try:
            _git._run_git(["rebase", "--continue"], cwd=adapter_dir)
            if is_rebasing(adapter_dir):
                click.echo("まだリベース中のコミットがあります。")
            else:
                click.echo("ai-adapter sync でプッシュしてください。")
        except GitError as e:
            if "Author identity unknown" in str(e):
                click.echo("Git ユーザー設定がされていません。")
                click.echo("  git config --global user.email 'you@example.com'")
                click.echo("  git config --global user.name 'Your Name'")
            else:
                click.echo(f"リベース続行に失敗: {e}")
